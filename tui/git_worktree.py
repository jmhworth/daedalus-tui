"""Local Git worktree lifecycle used by the standalone orchestrator."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable
import uuid

from .project_config import ProjectWorktreeSettings


#: Files Daedalus itself writes into the project it is operating on. The TUI
#: appends to its debug log on every launch, so if these counted as working-tree
#: changes the primary worktree would be permanently dirty and *every* task
#: would fail at worktree creation before an agent ever ran.
DAEDALUS_RUNTIME_ARTIFACTS: tuple[str, ...] = (
    ".daedalus-debug.log",
    ".daedalus-memory.json",
    # Orchestrate Mode writes the worker's task card into this directory before
    # the agent runs and reads its ticked checklist back afterwards; it is
    # Daedalus' own bookkeeping and must never reach a commit.
    ".daedalus-orchestration",
)

#: Message used when Daedalus commits the operator's pending changes instead of
#: refusing to start a task on a dirty operating branch.
DIRTY_PRIMARY_COMMIT_MESSAGE = "Daedalus: commit pending changes before starting a task"

#: Callback used to report auto-commit and auto-push progress, as
#: ``(message, kind)``, so the orchestrator can surface it in the task panel.
NoticeCallback = Callable[[str, str], None]


def format_push_notice(branch: str, remote: str, commit: str = "") -> str:
    """Return the user-facing notice emitted after a successful branch push."""
    suffix = f" (commit {commit})" if isinstance(commit, str) and commit else ""
    return f"Pushed {branch} to {remote}{suffix}."


def parse_push_notice(message: str) -> tuple[str, str, str] | None:
    """Extract ``(branch, remote, commit)`` from :func:`format_push_notice`."""
    body = message.strip()
    if not body.startswith("Pushed ") or not body.endswith("."):
        return None
    body = body[:-1].removeprefix("Pushed ")
    branch_remote, separator, commit_part = body.rpartition(" (commit ")
    if not separator or not commit_part.endswith(")"):
        return None
    commit = commit_part[:-1].strip()
    branch, separator, remote = branch_remote.partition(" to ")
    if not branch.strip() or not remote.strip() or not commit:
        return None
    return branch.strip(), remote.strip(), commit


class GitWorktreeError(RuntimeError):
    pass


def list_local_branches(repository: Path) -> list[str]:
    """Return local branch names under ``refs/heads`` without checking anything out."""
    try:
        process = subprocess.run(
            ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"],
            cwd=repository,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []
    if process.returncode != 0:
        return []
    return [line.strip() for line in process.stdout.splitlines() if line.strip()]


def remote_exists(repository: Path, remote: str = "origin") -> bool:
    """Return whether ``remote`` is configured for ``repository``."""
    try:
        process = subprocess.run(
            ["git", "remote", "get-url", remote],
            cwd=repository,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return process.returncode == 0


def push_branch(repository: Path, branch: str, remote: str = "origin") -> str:
    """Push a local branch to ``remote``, setting upstream with ``-u`` when needed.

    Never force-pushes. Raises ``GitWorktreeError`` when the remote or branch is
    missing, or when ``git push`` fails (including auth errors). Returns the
    local branch tip SHA captured immediately before the push.
    """
    branch = branch.strip()
    if not branch:
        raise GitWorktreeError("Branch name cannot be empty.")
    if not remote_exists(repository, remote):
        raise GitWorktreeError(f"Remote {remote!r} is not configured.")
    verify = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repository,
        capture_output=True,
        text=True,
    )
    if verify.returncode != 0:
        raise GitWorktreeError(f"Local branch {branch!r} does not exist.")
    commit = verify.stdout.strip()
    command = ["git", "push", "-u", remote, branch]
    try:
        process = subprocess.run(
            command,
            cwd=repository,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise GitWorktreeError(f"Failed to run git push: {error}") from error
    if process.returncode != 0:
        raise GitWorktreeError(GitWorktreeManager.format_failure(command, process))
    return commit


@dataclass(frozen=True)
class WorktreeContext:
    repository: Path
    task_id: str
    base_commit: str
    branch_name: str
    path: Path


class GitWorktreeManager:
    def __init__(
        self,
        repository: Path,
        primary_branch: str = "main",
        root_name: str = ".daedalus-worktrees",
        runtime_artifacts: Sequence[str] = DAEDALUS_RUNTIME_ARTIFACTS,
        autocommit_primary: bool = True,
        autocommit_message: str = DIRTY_PRIMARY_COMMIT_MESSAGE,
        autocommit_push: bool = True,
        remote: str = "origin",
        on_notice: NoticeCallback | None = None,
    ):
        self.repository = repository.resolve()
        self.primary_branch = primary_branch
        self.root_name = root_name
        self.runtime_artifacts = tuple(name for name in runtime_artifacts if name)
        self.autocommit_primary = autocommit_primary
        self.autocommit_message = autocommit_message
        self.autocommit_push = autocommit_push
        self.remote = remote
        self.on_notice = on_notice

    def create(self, task_id: str) -> WorktreeContext:
        self._validate_primary()
        base_commit = self.git_output(["rev-parse", self.primary_branch])
        branch_name = f"agent/task-{task_id}"
        path = self.repository.parent / self.root_name / self.repository.name / f"task-{task_id}"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.run_git(["worktree", "add", "-b", branch_name, str(path), base_commit])
        return WorktreeContext(self.repository, task_id, base_commit, branch_name, path)

    def provision_worktree(self, context: WorktreeContext, settings: ProjectWorktreeSettings) -> None:
        """Install project resources and link declared shared read-only paths."""
        if settings.install_command:
            process = subprocess.run(
                list(settings.install_command),
                cwd=context.path,
                capture_output=True,
                text=True,
            )
            if process.returncode != 0:
                raise GitWorktreeError(
                    self.format_failure(list(settings.install_command), process)
                )

        for relative_path in settings.readonly_paths:
            source = self.repository / relative_path
            target = context.path / relative_path
            if not source.exists():
                raise GitWorktreeError(
                    f"Configured read-only path is missing from the primary worktree: {source}"
                )
            if target.is_symlink():
                if target.resolve(strict=False) == source.resolve():
                    continue
                raise GitWorktreeError(
                    f"Cannot link configured read-only path because the worktree destination exists: {target}"
                )
            if target.exists():
                raise GitWorktreeError(
                    f"Cannot link configured read-only path because the worktree destination exists: {target}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source, target_is_directory=source.is_dir())

    def commit_changes(self, directory: Path, message: str) -> bool:
        self.stage_changes(directory)
        # The only reported change may be Daedalus' ignored card directory.
        # Check the index after staging instead of committing an empty repair.
        if not self.git_output(["diff", "--cached", "--name-only"], directory):
            return False
        self.run_git(["commit", "-m", message], directory)
        return True

    def stage_changes(self, directory: Path) -> None:
        """Stage the worktree contents except Daedalus' own runtime files.

        Orchestrate Mode writes the worker's task card into
        ``.daedalus-orchestration/`` inside the worktree and reads its ticked
        checklist back after the agent finishes; a blanket ``git add -A`` would
        commit that bookkeeping (and the debug log) into the task's branch.
        """
        excludes: list[str] = []
        for artifact in self.runtime_artifacts:
            # A pathspec naming a directory also covers everything inside it;
            # the glob form catches rotated logs such as `.daedalus-debug.log.1`.
            excludes.append(f":(exclude){artifact}")
            excludes.append(f":(exclude,glob){artifact}.[0-9]*")
            # Atomic memory writes briefly create a dot-prefixed .tmp file.
            # It can disappear between status and git add during a busy session.
            excludes.append(f":(exclude,glob).{artifact}.*.tmp")
        self.run_git(["add", "-A", "--", ".", *excludes], directory)

    def discard_graphify_changes(self, directory: Path) -> None:
        """Remove graphify output changes from an agent worktree.

        Graphify refreshes belong to the primary-repository post-promotion
        hook.  A task agent that runs one in its isolated worktree must not
        turn generated graph files into task changes or merge conflicts.
        """
        graphify_path = "graphify-out"
        if not (directory / graphify_path).exists():
            return
        self.run_git(["restore", "--source=HEAD", "--staged", "--worktree", "--", graphify_path], directory)
        self.run_git(["clean", "-fd", "--", graphify_path], directory)

    def reset_task_to_base(self, context: WorktreeContext) -> None:
        """Keep a read-only planning pass from becoming an implementation change."""
        self.run_git(["reset", "--hard", context.base_commit], context.path)
        self.run_git(["clean", "-fd"], context.path)

    def commit_graphify_changes(self, message: str, directory: Path | None = None) -> bool:
        """Commit only the generated graph after a successful primary update."""
        checkout = directory or self.repository
        if not self.git_output(["status", "--porcelain", "--", "graphify-out"], checkout):
            return False
        self.run_git(["add", "--", "graphify-out"], checkout)
        self.run_git(["commit", "-m", message], checkout)
        return True

    def merge_primary_into_task(self, context: WorktreeContext) -> None:
        self.run_git(["merge", "--no-ff", "--no-edit", self.primary_branch], context.path)

    def promote(self, context: WorktreeContext, expected_base: str | None = None) -> None:
        self._validate_primary()
        expected_base = expected_base or context.base_commit
        current = self.git_output(["rev-parse", self.primary_branch])
        if current != expected_base:
            raise GitWorktreeError("Primary branch advanced outside the integration run.")
        task_tip = self.git_output(["rev-parse", context.branch_name])
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", expected_base, task_tip],
            cwd=self.repository,
            capture_output=True,
            text=True,
        )
        if ancestor.returncode != 0:
            raise GitWorktreeError("Task branch is not a fast-forward of the target branch.")
        if self.is_primary_checked_out():
            self.run_git(["merge", "--ff-only", context.branch_name])
            return
        # Fast-forward the target ref without requiring it to be checked out.
        self.run_git(
            ["update-ref", f"refs/heads/{self.primary_branch}", task_tip, expected_base]
        )

    def capture_primary(self) -> str:
        self._validate_primary()
        return self.git_output(["rev-parse", self.primary_branch])

    def prepare_primary_checkout(self) -> tuple[Path, Path | None]:
        """Return a directory whose HEAD matches the target branch tip.

        When the repository already has the target branch checked out, reuse it.
        Otherwise create a short-lived worktree checked out on the target branch
        so graph refreshes commit there without switching the operator's checkout.
        """
        if self.is_primary_checked_out():
            return self.repository, None
        path = (
            self.repository.parent
            / self.root_name
            / self.repository.name
            / f".graphify-{uuid.uuid4().hex[:8]}"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        self.run_git(["worktree", "add", str(path), self.primary_branch])
        return path, path

    def cleanup_temporary_checkout(self, temporary: Path | None) -> None:
        """Remove a short-lived primary checkout created for post-promotion work."""
        if temporary is None:
            return
        if temporary.exists():
            self.run_git(["worktree", "remove", "--force", str(temporary)])
        else:
            self.run_git(["worktree", "prune"])

    def remove_successful(self, context: WorktreeContext) -> None:
        if context.path.exists():
            self.run_git(["worktree", "remove", "--force", str(context.path)])
        else:
            self.run_git(["worktree", "prune"])
        self.run_git(["branch", "-d", context.branch_name])

    def remove_cancelled(self, context: WorktreeContext) -> None:
        """Remove a cancelled task even when its branch was never integrated."""
        if context.path.exists():
            self.run_git(["worktree", "remove", "--force", str(context.path)])
        else:
            self.run_git(["worktree", "prune"])
        self.run_git(["branch", "-D", context.branch_name])

    def is_runtime_artifact(self, relative_path: str) -> bool:
        """Return whether a status entry is one of Daedalus' own runtime files.

        Rotated log backups (``.daedalus-debug.log.1``) count too, because the
        rotating handler creates them without the project ever asking. An
        artifact that is a directory matches both spellings Git uses for it:
        ``git status --porcelain`` reports an untracked directory with a
        trailing slash, and its contents with the directory as a prefix.
        """
        entry = relative_path.strip()
        for artifact in self.runtime_artifacts:
            if entry == artifact or entry == f"{artifact}/":
                return True
            if entry.startswith(f"{artifact}/"):
                return True
            if entry.startswith(f"{artifact}.") and entry[len(artifact) + 1 :].isdigit():
                return True
            if entry.startswith(f".{artifact}.") and entry.endswith(".tmp"):
                return True
        return False

    def dirty_paths(self, directory: Path) -> list[str]:
        """Return working-tree changes excluding Daedalus' own runtime files."""
        # Read the raw stdout rather than git_output(): the porcelain status
        # column is leading whitespace for unstaged changes, and stripping it
        # would shift every path by one character.
        status = self.run_git(["status", "--porcelain"], directory).stdout
        paths: list[str] = []
        for line in status.splitlines():
            entry = line[3:] if len(line) > 3 else ""
            if " -> " in entry:
                entry = entry.split(" -> ", 1)[1]
            entry = entry.strip().strip('"')
            if entry and not self.is_runtime_artifact(entry):
                paths.append(entry)
        return paths

    def is_clean(self, directory: Path) -> bool:
        return not self.dirty_paths(directory)

    def head(self, directory: Path) -> str:
        return self.git_output(["rev-parse", "HEAD"], directory)

    def has_unmerged_paths(self, directory: Path) -> bool:
        return bool(self.git_output(["diff", "--name-only", "--diff-filter=U"], directory))

    def is_primary_checked_out(self) -> bool:
        return self.git_output(["branch", "--show-current"]) == self.primary_branch

    def validate_primary(self) -> None:
        """Ensure the configured target branch exists and is safe to integrate into.

        The operator does not need that branch checked out. Task worktrees are
        always created from the target branch tip. When it *is* checked out, the
        working tree must be clean so promotion and graph commits stay coherent;
        pending operator changes are committed (and pushed) rather than refused,
        so a dirty checkout no longer blocks a task from starting.
        """
        verify = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{self.primary_branch}"],
            cwd=self.repository,
            capture_output=True,
            text=True,
        )
        if verify.returncode != 0:
            raise GitWorktreeError(
                f"Target branch {self.primary_branch!r} does not exist as a local branch."
            )
        if not self.is_primary_checked_out():
            return
        dirty = self.dirty_paths(self.repository)
        if not dirty:
            return
        if self.autocommit_primary:
            self.commit_and_push_primary(dirty)
            return
        listed = ", ".join(dirty[:5])
        if len(dirty) > 5:
            listed += f", and {len(dirty) - 5} more"
        raise GitWorktreeError(
            "Primary worktree must be clean before starting or promoting an agent. "
            f"Uncommitted changes: {listed}."
        )

    def commit_and_push_primary(self, dirty: list[str] | None = None) -> bool:
        """Commit the operator's pending primary-worktree changes and publish them.

        A dirty operating branch used to abort the task before any agent ran.
        Committing first keeps every later step coherent: the task worktree is
        branched from a tip that already contains the operator's work, and
        promotion can still fast-forward the checked-out branch.
        """
        dirty = self.dirty_paths(self.repository) if dirty is None else dirty
        if not dirty:
            return False
        # Stage the real changes only. A blanket `git add -A` would also start
        # tracking Daedalus' own runtime files, which the TUI rewrites on every
        # launch. Anything the operator already staged is committed regardless,
        # because the commit takes the whole index.
        self.run_git(["add", "-A", "--", *dirty], self.repository)
        if not self.git_output(["diff", "--cached", "--name-only"], self.repository):
            return False
        self.run_git(["commit", "-m", self.autocommit_message], self.repository)
        self.notify(
            f"Committed {len(dirty)} pending change(s) on {self.primary_branch} before starting."
        )
        self.push_primary()
        return True

    def commit_primary_file(self, relative_path: str, content: str, message: str) -> bool:
        """Write one Daedalus-owned file onto the target branch and commit it.

        Used for the orchestration context file, which must reach the branch
        (and the remote) the moment it is written so a later planner, on this
        machine or another, starts from what was already planned. The target
        branch need not be checked out: a short-lived worktree is used
        otherwise. Only ``relative_path`` is committed, never anything else the
        operator may have staged. Returns False when the file was unchanged.
        """
        relative_path = relative_path.strip().strip("/")
        if not relative_path:
            raise GitWorktreeError("Context file path cannot be empty.")
        checkout, temporary = self.prepare_primary_checkout()
        try:
            target = checkout / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            self.run_git(["add", "--", relative_path], checkout)
            if not self.git_output(["diff", "--cached", "--name-only", "--", relative_path], checkout):
                return False
            self.run_git(["commit", "-m", message, "--", relative_path], checkout)
            return True
        finally:
            self.cleanup_temporary_checkout(temporary)

    def push_primary(self, enabled: bool | None = None) -> bool:
        """Publish the operating branch, treating a failed push as non-fatal.

        The point of the auto-commit is to let the task run. An unreachable or
        unauthenticated remote is reported and the work stays committed locally
        rather than turning into the start-up error this replaced.

        ``enabled`` overrides the auto-commit push flag for callers with their
        own setting, such as the post-promotion push and the orchestration
        context file; ``None`` keeps the auto-commit behaviour.
        """
        if not (self.autocommit_push if enabled is None else enabled):
            return False
        if not remote_exists(self.repository, self.remote):
            self.notify(
                f"No {self.remote!r} remote configured; kept the commit local.", "warning"
            )
            return False
        try:
            commit = push_branch(self.repository, self.primary_branch, self.remote)
        except GitWorktreeError as error:
            self.notify(
                f"Could not push {self.primary_branch} to {self.remote}: {error}", "warning"
            )
            return False
        self.notify(
            format_push_notice(self.primary_branch, self.remote, commit),
            "pushed",
        )
        return True

    def notify(self, message: str, kind: str = "status") -> None:
        if self.on_notice is not None:
            self.on_notice(message, kind)

    def _validate_primary(self) -> None:
        """Compatibility alias for callers that used the original private helper."""
        self.validate_primary()

    def run_git(self, arguments: list[str], directory: Path | None = None) -> subprocess.CompletedProcess[str]:
        process = subprocess.run(
            ["git", *arguments],
            cwd=directory or self.repository,
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            raise GitWorktreeError(self.format_failure(["git", *arguments], process))
        return process

    def git_output(self, arguments: list[str], directory: Path | None = None) -> str:
        return self.run_git(arguments, directory).stdout.strip()

    @staticmethod
    def format_failure(arguments: list[str], process: subprocess.CompletedProcess[str]) -> str:
        return (
            f"COMMAND: {' '.join(arguments)}\n"
            f"STDOUT:\n{process.stdout}\nSTDERR:\n{process.stderr}"
        ).strip()
