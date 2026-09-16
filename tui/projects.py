"""Discovery of repositories beneath a launch root."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .local_storage import GENERATED_DIRECTORY_NAMES

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from .config import ProjectDiscoverySettings


@dataclass(frozen=True)
class DaedalusProject:
    """A launch-root child the TUI can run tasks against.

    ``formatted`` marks the Daedalus layout (a ``feature_files`` folder). Plain
    Git checkouts are listed too so the TUI is not limited to projects that have
    already been converted; they are labelled so the difference stays visible.
    """

    path: Path
    launch_root: Path
    formatted: bool = True
    git_repository: bool = True

    @property
    def name(self) -> str:
        return self.path.name or str(self.path)

    @property
    def display_name(self) -> str:
        project_path = self.path.expanduser().resolve()
        launch_root = self.launch_root.expanduser().resolve()
        base = project_path.name or self.name
        if project_path == launch_root:
            return f"{base} (root)"
        markers: list[str] = []
        if project_path.parent != launch_root:
            # Opened by path from outside the launch root, where the basename
            # alone would not say which directory the option refers to.
            markers.append("external")
        if not self.formatted:
            # Tasks still run here, but no feature files exist to update yet.
            markers.append("unformatted")
        if markers:
            return f"{base} ({', '.join(markers)})"
        return base


_SKIPPED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".daedalus-worktrees",
        ".venv",
        "__pycache__",
        "node_modules",
    }
)


def is_direct_child_project(path: Path, launch_root: Path) -> bool:
    """Return whether ``path`` is an immediate child of ``launch_root``."""

    project_path = path.expanduser().resolve()
    resolved_root = launch_root.expanduser().resolve()
    return project_path != resolved_root and project_path.parent == resolved_root


def discover_projects(
    root: Path,
    settings: "ProjectDiscoverySettings | None" = None,
) -> tuple[DaedalusProject, ...]:
    """Find the immediate child folders the TUI can run tasks against.

    Daedalus-formatted folders (those with a direct ``feature_files`` child) are
    always listed. Plain Git checkouts are listed when
    ``include_git_repositories`` is set, and every remaining directory when
    ``include_all_directories`` is set, so the launch root is not restricted to
    projects that already use the Daedalus layout.

    Git metadata, generated worktrees, virtual environments, and dependency
    folders are skipped. Descendants below an immediate child are never
    traversed, so nested projects cannot appear in the project selector.
    """

    launch_root = root.expanduser().resolve()
    if not launch_root.is_dir():
        return ()

    # The TUI's own prompt and error archives are generated folders, never
    # projects, even when discovery lists every immediate child directory.
    skipped = (settings.skipped_directory_names if settings else _SKIPPED_DIRECTORY_NAMES) | GENERATED_DIRECTORY_NAMES
    include_git = settings.include_git_repositories if settings else False
    include_all = settings.include_all_directories if settings else False

    discovered: list[DaedalusProject] = []
    for candidate in sorted(launch_root.iterdir(), key=lambda path: path.name):
        if candidate.name in skipped or not candidate.is_dir():
            continue
        candidate_path = candidate.resolve()
        if not is_direct_child_project(candidate_path, launch_root):
            continue
        formatted = (candidate_path / "feature_files").is_dir()
        git_repository = (candidate_path / ".git").exists()
        if not formatted and not (include_all or (include_git and git_repository)):
            continue
        discovered.append(
            DaedalusProject(candidate_path, launch_root, formatted, git_repository)
        )

    return tuple(
        sorted(
            discovered,
            # Daedalus-formatted projects stay at the top of the selector.
            key=lambda project: (not project.formatted, project.display_name),
        )
    )


def project_from_directory(path: Path, launch_root: Path) -> DaedalusProject:
    """Build a project entry for a directory the operator named by hand.

    Discovery only walks the launch root, so a project created or cloned
    elsewhere would otherwise be unreachable without restarting the TUI in a
    different directory. The same Daedalus-format and Git checks used by
    discovery apply here, so an opened directory is labelled exactly as a
    discovered one would be.
    """

    candidate = path.expanduser().resolve()
    if not candidate.is_dir():
        raise ValueError(f"{candidate} is not an existing directory.")
    return DaedalusProject(
        candidate,
        launch_root.expanduser().resolve(),
        formatted=(candidate / "feature_files").is_dir(),
        git_repository=(candidate / ".git").exists(),
    )


__all__ = [
    "DaedalusProject",
    "discover_projects",
    "is_direct_child_project",
    "project_from_directory",
]
