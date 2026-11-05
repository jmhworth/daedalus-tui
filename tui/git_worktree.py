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


class SyncMergeConflictError(GitWorktreeError):
    """Raised when an operator Sync pull/merge leaves unmerged paths.

    The conflicted sync worktree is preserved so recovery can plan and resolve
    conflicts without leaving the project's primary checkout mid-merge.
    """

    def __init__(
        self,
        message: str,
        *,
        repository: Path,
        branch: str,
        remote: str,
        worktree_path: Path,
        conflicted_paths: tuple[str, ...],
        used_temp_branch: bool,
        temp_branch_name: str | None,
        merge_failure: str,
    ) -> None:
        super().__init__(message)
        self.repository = repository
        self.branch = branch
        self.remote = remote
        self.worktree_path = worktree_path
        self.conflicted_paths = conflicted_paths
        self.used_temp_branch = used_temp_branch
        self.temp_branch_name = temp_branch_name
        self.merge_failure = merge_failure


SYNC_MERGE_COMMIT_MESSAGE = "Daedalus sync conflict resolution"


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


def _worktree_path_for_branch(repository: Path, branch: str) -> Path | None:
    """Return the worktree path that has ``branch`` checked out, if any."""
    try:
        process = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repository,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if process.returncode != 0:
        return None
    current_path: Path | None = None
    expected = f"branch refs/heads/{branch}"
    for line in process.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree "))
        elif line.strip() == expected:
            return current_path
        elif not line.strip():
            current_path = None
    return None


def _is_ancestor(repository: Path, ancestor: str, descendant: str) -> bool:
    process = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repository,
        capture_output=True,
        text=True,
    )
    return process.returncode == 0


def _remote_ref_missing(stderr: str) -> bool:
    lowered = stderr.lower()
    return any(
        marker in lowered
        for marker in (
            "couldn't find remote ref",
            "could not find remote ref",
            "does not exist",
            "couldn't find remote",
            "not found",
        )
    )


def list_unmerged_paths(directory: Path) -> tuple[str, ...]:
    """Return paths with unmerged (conflict) index entries in ``directory``."""
    try:
        process = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=directory,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ()
    if process.returncode != 0:
        return ()
    return tuple(line.strip() for line in process.stdout.splitlines() if line.strip())


def _sync_worktree_parent(repository: Path) -> Path:
    parent = repository.parent / ".daedalus-worktrees" / repository.name
    parent.mkdir(parents=True, exist_ok=True)
    return parent


def _sanitize_branch_for_name(branch: str) -> str:
    return branch.replace("/", "-").replace(" ", "-")


def _create_isolated_sync_worktree(
    repository: Path,
    branch: str,
    local_sha: str,
) -> tuple[Path, bool, str | None]:
    """Create an isolated sync worktree for merging; never reuse an existing checkout.

    When ``branch`` is already checked out elsewhere, attach via a temporary
    ``daedalus/sync-resolve-*`` branch from the operating tip. Otherwise check out
    ``branch`` directly in the new sync worktree.
    """
    sync_id = uuid.uuid4().hex[:8]
    existing_checkout = _worktree_path_for_branch(repository, branch)
    if existing_checkout is not None:
        temp_branch = f"daedalus/sync-resolve-{_sanitize_branch_for_name(branch)}-{sync_id}"
        temporary = _sync_worktree_parent(repository) / f".sync-resolve-{sync_id}"
        add_command = ["git", "worktree", "add", "-b", temp_branch, str(temporary), local_sha]
        used_temp_branch = True
        temp_branch_name: str | None = temp_branch
    else:
        temporary = _sync_worktree_parent(repository) / f".sync-pull-{sync_id}"
        add_command = ["git", "worktree", "add", str(temporary), branch]
        used_temp_branch = False
        temp_branch_name = None
    try:
        added = subprocess.run(
            add_command,
            cwd=repository,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise GitWorktreeError(f"Failed to create sync worktree: {error}") from error
    if added.returncode != 0:
        raise GitWorktreeError(GitWorktreeManager.format_failure(add_command, added))
    return temporary, used_temp_branch, temp_branch_name


def _force_remove_worktree(repository: Path, worktree: Path) -> None:
    remove = subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree)],
        cwd=repository,
        capture_output=True,
        text=True,
    )
    if remove.returncode != 0:
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=repository,
            capture_output=True,
            text=True,
        )


def _delete_branch_if_present(repository: Path, branch_name: str | None) -> None:
    if not branch_name:
        return
    subprocess.run(
        ["git", "branch", "-D", branch_name],
        cwd=repository,
        capture_output=True,
        text=True,
    )


def abort_sync_merge(
    repository: Path,
    worktree_path: Path,
    *,
    temp_branch_name: str | None = None,
) -> None:
    """Abort a preserved sync merge and remove the sync worktree (and temp branch)."""
    if worktree_path.exists():
        subprocess.run(
            ["git", "merge", "--abort"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        _force_remove_worktree(repository, worktree_path)
    else:
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=repository,
            capture_output=True,
            text=True,
        )
    _delete_branch_if_present(repository, temp_branch_name)


def finalize_sync_merge(
    repository: Path,
    worktree_path: Path,
    operating_branch: str,
    *,
    used_temp_branch: bool = False,
    temp_branch_name: str | None = None,
    message: str = SYNC_MERGE_COMMIT_MESSAGE,
) -> None:
    """Stage resolutions, commit the merge, update the operating branch, and clean up."""
    if not worktree_path.exists():
        raise GitWorktreeError(f"Sync worktree no longer exists: {worktree_path}")
    add = subprocess.run(
        ["git", "add", "-A"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    if add.returncode != 0:
        raise GitWorktreeError(GitWorktreeManager.format_failure(["git", "add", "-A"], add))
    remaining = list_unmerged_paths(worktree_path)
    if remaining:
        raise GitWorktreeError(
            "Cannot finalize sync merge while unmerged paths remain: "
            + ", ".join(remaining)
        )
    commit = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    if commit.returncode != 0:
        raise GitWorktreeError(
            GitWorktreeManager.format_failure(["git", "commit", "-m", message], commit)
        )
    if used_temp_branch:
        if not temp_branch_name:
            raise GitWorktreeError("Temp sync branch name is required to update the operating branch.")
        tip = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        if tip.returncode != 0:
            raise GitWorktreeError(GitWorktreeManager.format_failure(["git", "rev-parse", "HEAD"], tip))
        update = subprocess.run(
            ["git", "update-ref", f"refs/heads/{operating_branch}", tip.stdout.strip()],
            cwd=repository,
            capture_output=True,
            text=True,
        )
        if update.returncode != 0:
            raise GitWorktreeError(
                GitWorktreeManager.format_failure(
                    ["git", "update-ref", f"refs/heads/{operating_branch}", tip.stdout.strip()],
                    update,
                )
            )
        _force_remove_worktree(repository, worktree_path)
        _delete_branch_if_present(repository, temp_branch_name)
    else:
        _force_remove_worktree(repository, worktree_path)


def pull_branch(repository: Path, branch: str, remote: str = "origin") -> None:
    """Integrate ``remote/branch`` into the local branch without switching checkout.

    Fast-forwards when the local tip is behind, no-ops when ahead or equal, and
    always merges in an isolated ``.sync-pull-*`` / ``.sync-resolve-*`` worktree
    when histories have diverged (never in an existing operating-branch checkout).
    Conflict-class failures preserve that worktree and raise
    ``SyncMergeConflictError``. Missing remote branches are ignored so a first
    push can still publish the local branch.
    """
    branch = branch.strip()
    if not branch:
        raise GitWorktreeError("Branch name cannot be empty.")
    remote_tracking = f"refs/remotes/{remote}/{branch}"
    fetch_command = [
        "git",
        "fetch",
        remote,
        f"refs/heads/{branch}:{remote_tracking}",
    ]
    try:
        fetch = subprocess.run(
            fetch_command,
            cwd=repository,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise GitWorktreeError(f"Failed to run git fetch: {error}") from error
    if fetch.returncode != 0:
        if _remote_ref_missing(fetch.stderr):
            return
        raise GitWorktreeError(GitWorktreeManager.format_failure(fetch_command, fetch))

    local_tip = subprocess.run(
        ["git", "rev-parse", f"refs/heads/{branch}"],
        cwd=repository,
        capture_output=True,
        text=True,
    )
    if local_tip.returncode != 0:
        raise GitWorktreeError(f"Local branch {branch!r} does not exist.")
    remote_tip = subprocess.run(
        ["git", "rev-parse", remote_tracking],
        cwd=repository,
        capture_output=True,
        text=True,
    )
    if remote_tip.returncode != 0:
        return
    local_sha = local_tip.stdout.strip()
    remote_sha = remote_tip.stdout.strip()
    if local_sha == remote_sha or _is_ancestor(repository, remote_sha, local_sha):
        return

    checkout = _worktree_path_for_branch(repository, branch)
    can_fast_forward = _is_ancestor(repository, local_sha, remote_sha)
    if can_fast_forward and checkout is None:
        update_command = ["git", "update-ref", f"refs/heads/{branch}", remote_sha]
        try:
            updated = subprocess.run(
                update_command,
                cwd=repository,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            raise GitWorktreeError(f"Failed to fast-forward branch: {error}") from error
        if updated.returncode != 0:
            raise GitWorktreeError(GitWorktreeManager.format_failure(update_command, updated))
        return

    temporary, used_temp_branch, temp_branch_name = _create_isolated_sync_worktree(
        repository, branch, local_sha
    )
    merge_command = (
        ["git", "merge", "--ff-only", f"{remote}/{branch}"]
        if can_fast_forward
        else ["git", "merge", "--no-edit", f"{remote}/{branch}"]
    )
    preserve_on_conflict = False
    try:
        try:
            merged = subprocess.run(
                merge_command,
                cwd=temporary,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            raise GitWorktreeError(f"Failed to run git merge: {error}") from error
        if merged.returncode != 0:
            failure = GitWorktreeManager.format_failure(merge_command, merged)
            conflicted = list_unmerged_paths(temporary)
            if conflicted:
                preserve_on_conflict = True
                raise SyncMergeConflictError(
                    failure,
                    repository=repository.resolve(),
                    branch=branch,
                    remote=remote,
                    worktree_path=temporary,
                    conflicted_paths=conflicted,
                    used_temp_branch=used_temp_branch,
                    temp_branch_name=temp_branch_name,
                    merge_failure=failure,
                )
            abort_sync_merge(repository, temporary, temp_branch_name=temp_branch_name)
            raise GitWorktreeError(failure)
        if used_temp_branch:
            tip = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=temporary,
                capture_output=True,
                text=True,
            )
            if tip.returncode != 0:
                raise GitWorktreeError(
                    GitWorktreeManager.format_failure(["git", "rev-parse", "HEAD"], tip)
                )
            update = subprocess.run(
                ["git", "update-ref", f"refs/heads/{branch}", tip.stdout.strip()],
                cwd=repository,
                capture_output=True,
                text=True,
            )
            if update.returncode != 0:
                raise GitWorktreeError(
                    GitWorktreeManager.format_failure(
                        ["git", "update-ref", f"refs/heads/{branch}", tip.stdout.strip()],
                        update,
                    )
                )
    finally:
        if not preserve_on_conflict:
            _force_remove_worktree(repository, temporary)
            if used_temp_branch:
                _delete_branch_if_present(repository, temp_branch_name)


def push_branch(
    repository: Path,
    branch: str,
    remote: str = "origin",
    *,
    pull_first: bool = True,
) -> str:
    """Push a local branch and return its SHA, optionally syncing first.

    The default pull supports operator Sync. Automated promotion and conflict
    recovery pass ``pull_first=False`` after integrating remote state. This
    function never force-pushes.
    """
    branch = branch.strip()
    if not branch:
        raise GitWorktreeError("Branch name cannot be empty.")
    if not remote_exists(repository, remote):
        raise GitWorktreeError(f"Remote {remote!r} is not configured.")
    if pull_first:
        pull_branch(repository, branch, remote)
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

    def create(self, task_id: str, *, validate: bool = True) -> WorktreeContext:
        if validate:
            # Auto-commit dirty primary files so send/start is not blocked.
            self.validate_primary(auto_commit_dirty=True)
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
        self.validate_primary(auto_commit_dirty=True)
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

    def validate_primary(self, *, auto_commit_dirty: bool = False) -> bool:
        """Ensure the configured target branch exists and is safe to integrate.

        The branch need not be checked out. When it is checked out, dirty files
        can be committed and published at task start if both this call and the
        manager settings allow it. Promotion calls this with auto-commit off so
        changes arriving after base capture cannot be swept into the task.
        Returns True when an auto-commit was created.
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
            return False
        dirty = self.dirty_paths(self.repository)
        if not dirty:
            return False
        if auto_commit_dirty and self.autocommit_primary:
            return self.commit_and_push_primary(dirty)
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

    def _validate_primary(self, *, auto_commit_dirty: bool = False) -> bool:
        """Compatibility alias for callers that used the original private helper."""
        return self.validate_primary(auto_commit_dirty=auto_commit_dirty)

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
