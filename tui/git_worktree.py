"""Local Git worktree lifecycle used by the standalone orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import uuid

from .project_config import ProjectWorktreeSettings


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


def push_branch(repository: Path, branch: str, remote: str = "origin") -> None:
    """Push a local branch to ``remote``, setting upstream with ``-u`` when needed.

    Never force-pushes. Raises ``GitWorktreeError`` when the remote or branch is
    missing, or when ``git push`` fails (including auth errors).
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


@dataclass(frozen=True)
class WorktreeContext:
    repository: Path
    task_id: str
    base_commit: str
    branch_name: str
    path: Path


class GitWorktreeManager:
    def __init__(self, repository: Path, primary_branch: str = "main", root_name: str = ".daedalus-worktrees"):
        self.repository = repository.resolve()
        self.primary_branch = primary_branch
        self.root_name = root_name

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
        if not self.git_output(["status", "--porcelain"], directory):
            return False
        self.stage_changes(directory)
        self.run_git(["commit", "-m", message], directory)
        return True

    def stage_changes(self, directory: Path) -> None:
        """Stage the current worktree contents for orchestration checks or commit."""
        self.run_git(["add", "-A"], directory)

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

    def is_clean(self, directory: Path) -> bool:
        return not self.git_output(["status", "--porcelain"], directory)

    def head(self, directory: Path) -> str:
        return self.git_output(["rev-parse", "HEAD"], directory)

    def has_unmerged_paths(self, directory: Path) -> bool:
        return bool(self.git_output(["diff", "--name-only", "--diff-filter=U"], directory))

    def is_primary_checked_out(self) -> bool:
        return self.git_output(["branch", "--show-current"]) == self.primary_branch

    def validate_primary(self, *, auto_commit_dirty: bool = False) -> bool:
        """Ensure the configured target branch exists and is safe to integrate into.

        The operator does not need that branch checked out. Task worktrees are
        always created from the target branch tip. When it *is* checked out, the
        working tree must be clean so promotion and graph commits stay coherent.

        When ``auto_commit_dirty`` is True (task start/resume), dirty primary
        files are staged and committed so the operator does not have to commit
        manually before sending. Promotion keeps ``auto_commit_dirty=False``
        because a new primary commit would advance the tip past the captured
        integration base.

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
        if not (self.is_primary_checked_out() and not self.is_clean(self.repository)):
            return False
        if auto_commit_dirty:
            committed = self.commit_changes(
                self.repository,
                "Daedalus: auto-commit dirty primary before starting agent",
            )
            if self.is_clean(self.repository):
                return committed
        raise GitWorktreeError(
            "Primary worktree must be clean before starting or promoting an agent."
        )

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
