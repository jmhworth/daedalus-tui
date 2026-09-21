"""Configuration supplied by a target project to prepare task worktrees."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


DAEDALUS_CONFIG_FILENAME = ".daedalus"


@dataclass(frozen=True)
class ProjectWorktreeSettings:
    """Install and shared-path settings from a target project's .daedalus file."""

    install_command: tuple[str, ...] = ()
    readonly_paths: tuple[str, ...] = ()
    environment_files: tuple[str, ...] = ()
    claude_settings_file: str = ""
    claude_allowed_tools: tuple[str, ...] = ()

    @property
    def configured(self) -> bool:
        return bool(
            self.install_command or self.readonly_paths or self.environment_files
            or self.claude_settings_file or self.claude_allowed_tools
        )


def load_project_worktree_settings(repository: Path) -> ProjectWorktreeSettings:
    """Load optional worktree provisioning settings from a target repository."""
    path = repository / DAEDALUS_CONFIG_FILENAME
    if not path.is_file():
        return ProjectWorktreeSettings()

    try:
        with path.open("rb") as source:
            values = tomllib.load(source)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"Could not read project configuration {path}: {error}") from error

    worktree = values.get("worktree", {})
    if not isinstance(worktree, dict):
        raise ValueError(f"{path} worktree must be a table.")

    install_command = _string_array(worktree.get("install_command", []), path, "install_command")
    readonly_paths = _string_array(worktree.get("readonly_paths", []), path, "readonly_paths")
    environment_files = _string_array(worktree.get("environment_files", []), path, "environment_files")
    for relative_path in (*readonly_paths, *environment_files):
        candidate = Path(relative_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"{path} worktree paths must be repository-relative.")

    claude = values.get("claude", {})
    if not isinstance(claude, dict):
        raise ValueError(f"{path} claude must be a table.")
    settings_file = claude.get("settings_file", "")
    if not isinstance(settings_file, str):
        raise ValueError(f"{path} claude.settings_file must be a string.")
    if settings_file and (Path(settings_file).is_absolute() or ".." in Path(settings_file).parts):
        raise ValueError(f"{path} claude.settings_file must be repository-relative.")
    allowed_tools = _string_array(claude.get("allowed_tools", []), path, "claude.allowed_tools")
    return ProjectWorktreeSettings(
        tuple(install_command), tuple(readonly_paths), tuple(environment_files),
        settings_file, tuple(allowed_tools)
    )


def _string_array(value: object, path: Path, key: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{path} {key} must be an array of non-empty strings.")
    return value
