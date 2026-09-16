"""Shared local storage roots for prompt archives and error diagnostics.

The TUI keeps every saved prompt and every diagnostic log under one storage
root that belongs to the TUI installation itself, never under the project a
task runs against. That root defaults to the TUI project directory (the parent
of ``parameter_files``) and can be redirected through the prompting parameter
file for packaged installations that live in a read-only location.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re


PROMPTS_DIRECTORY = "prompts"
ERRORS_DIRECTORY = "errors"
DRAFTS_DIRECTORY = "drafts"
RUNTIME_LOG_FILENAME = "daedalus.log"
FAULT_LOG_FILENAME = "faults.log"
#: Generated storage folders that must never appear as launch-root projects.
GENERATED_DIRECTORY_NAMES = frozenset({PROMPTS_DIRECTORY, ERRORS_DIRECTORY})

_KEY_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def tui_project_root() -> Path:
    """Return the directory that owns ``parameter_files`` for this checkout."""
    return Path(__file__).resolve().parents[1]


def project_key(project_path: Path) -> str:
    """Return a readable, collision-safe key for one target project.

    The key combines the project's basename with a short digest of its
    resolved absolute path, so two projects that share a basename (for
    example ``~/work/app`` and ``~/personal/app``) never share prompt or error
    storage by accident.
    """
    resolved = Path(project_path).expanduser().resolve()
    digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:8]
    base = _KEY_SAFE.sub("-", resolved.name or "root").strip("-") or "root"
    return f"{base}-{digest}"


def safe_component(value: str) -> str:
    """Return a filesystem-safe path component derived from an identifier."""
    cleaned = _KEY_SAFE.sub("-", value).strip("-.")
    return cleaned or "item"


@dataclass(frozen=True)
class StorageStatus:
    """Whether a storage folder is writable, with the exact path that failed."""

    path: Path
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.error is None


class LocalStorage:
    """Resolve and create the prompt and error folders under one data root."""

    def __init__(self, data_root: Path | None = None):
        self.data_root = (data_root or tui_project_root()).expanduser().resolve()
        self.prompts_root = self.data_root / PROMPTS_DIRECTORY
        self.errors_root = self.data_root / ERRORS_DIRECTORY
        self._statuses: dict[Path, StorageStatus] = {}

    # --- runtime logs -------------------------------------------------

    @property
    def runtime_log_path(self) -> Path:
        return self.errors_root / RUNTIME_LOG_FILENAME

    @property
    def fault_log_path(self) -> Path:
        return self.errors_root / FAULT_LOG_FILENAME

    # --- per-project layout -----------------------------------------------

    def project_prompts_dir(self, project_path: Path) -> Path:
        return self.prompts_root / project_key(project_path)

    def drafts_dir(self, project_path: Path) -> Path:
        return self.project_prompts_dir(project_path) / DRAFTS_DIRECTORY

    def task_prompts_dir(self, project_path: Path, task_id: str) -> Path:
        return self.project_prompts_dir(project_path) / safe_component(task_id)

    def project_errors_dir(self, project_path: Path) -> Path:
        return self.errors_root / project_key(project_path)

    def task_errors_dir(self, project_path: Path, task_id: str) -> Path:
        return self.project_errors_dir(project_path) / safe_component(task_id)

    # --- creation -----------------------------------------------------------

    def ensure(self, path: Path) -> StorageStatus:
        """Create ``path`` when possible and report the exact failure otherwise.

        The result is cached per path so a persistent failure (read-only
        install, full disk) is reported once instead of on every keystroke.
        A later successful attempt clears the cached failure.
        """
        cached = self._statuses.get(path)
        if cached is not None and cached.available:
            return cached
        try:
            path.mkdir(parents=True, exist_ok=True)
            if not os.access(path, os.W_OK):
                raise PermissionError(f"{path} is not writable")
        except OSError as error:
            status = StorageStatus(path, f"{path}: {error}")
        else:
            status = StorageStatus(path)
        self._statuses[path] = status
        return status

    def ensure_roots(self) -> tuple[StorageStatus, StorageStatus]:
        """Create the prompt and error roots, returning their statuses."""
        return self.ensure(self.prompts_root), self.ensure(self.errors_root)

    def describe(self) -> str:
        return f"prompts: {self.prompts_root}    errors: {self.errors_root}"


__all__ = [
    "DRAFTS_DIRECTORY",
    "ERRORS_DIRECTORY",
    "FAULT_LOG_FILENAME",
    "GENERATED_DIRECTORY_NAMES",
    "LocalStorage",
    "PROMPTS_DIRECTORY",
    "RUNTIME_LOG_FILENAME",
    "StorageStatus",
    "project_key",
    "safe_component",
    "tui_project_root",
]
