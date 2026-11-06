"""Discovery of Daedalus-supported repositories beneath a launch root."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DaedalusProject:
    """A repository recognized by the presence of a ``feature_files`` folder."""

    path: Path
    launch_root: Path

    @property
    def name(self) -> str:
        return self.path.name or str(self.path)

    @property
    def display_name(self) -> str:
        project_path = self.path.expanduser().resolve()
        launch_root = self.launch_root.expanduser().resolve()
        if project_path == launch_root:
            return f"{project_path.name or self.name} (root)"
        return project_path.name or self.name


_SKIPPED_DIRECTORY_NAMES = {
    ".git",
    ".daedalus-worktrees",
    ".venv",
    "__pycache__",
    "node_modules",
}


def is_direct_child_project(path: Path, launch_root: Path) -> bool:
    """Return whether ``path`` is an immediate child of ``launch_root``."""

    project_path = path.expanduser().resolve()
    resolved_root = launch_root.expanduser().resolve()
    return project_path != resolved_root and project_path.parent == resolved_root


def discover_projects(root: Path) -> tuple[DaedalusProject, ...]:
    """Find immediate child folders containing a direct ``feature_files`` child.

    Git metadata, generated worktrees, virtual environments, and dependency
    folders are skipped. Descendants below an immediate child are never
    traversed, so nested projects cannot appear in the project selector.
    """

    launch_root = root.expanduser().resolve()
    if not launch_root.is_dir():
        return ()

    discovered: list[DaedalusProject] = []
    for candidate in sorted(launch_root.iterdir(), key=lambda path: path.name):
        if candidate.name in _SKIPPED_DIRECTORY_NAMES or not candidate.is_dir():
            continue
        candidate_path = candidate.resolve()
        if not is_direct_child_project(candidate_path, launch_root):
            continue
        if (candidate_path / "feature_files").is_dir():
            discovered.append(DaedalusProject(candidate_path, launch_root))

    return tuple(
        sorted(
            discovered,
            key=lambda project: project.display_name,
        )
    )


__all__ = ["DaedalusProject", "discover_projects", "is_direct_child_project"]
