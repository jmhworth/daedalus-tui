"""Exact prompt archives and recoverable drafts under the shared ``prompts/`` root.

Every submitted user turn is written verbatim to ``turn-NNNN.md`` (no wrapper,
no normalization, trailing newlines intact) and the composer's editable text is
saved as ``draft.json`` with its cursor and revision. Writes go through a
temporary file and an atomic replacement so a crash never leaves a half-written
prompt, and revision checks stop a delayed autosave from overwriting newer text.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from threading import Lock
import time

from .debug_log import LOGGER
from .local_storage import LocalStorage, StorageStatus, project_key


DRAFT_FILENAME = "draft.json"
NEW_TASK_DRAFT_ID = "new-task"
TURN_FILE_PATTERN = re.compile(r"^turn-(\d{4,})\.md$")


class PromptStoreError(OSError):
    """A prompt or draft could not be written; the message names the exact path."""


@dataclass
class DraftRecord:
    """The editable composer text for one task (or the new-task composer)."""

    text: str
    project_key: str
    task_id: str | None = None
    draft_id: str = "draft"
    cursor: tuple[int, int] = (0, 0)
    revision: int = 0
    updated_at: str = ""
    revises_turn_id: str | None = None
    kind: str = "draft"

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["cursor"] = list(self.cursor)
        return data

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "DraftRecord | None":
        text = value.get("text")
        if not isinstance(text, str):
            return None
        cursor_value = value.get("cursor")
        cursor = (0, 0)
        if isinstance(cursor_value, list) and len(cursor_value) == 2:
            try:
                cursor = (max(0, int(cursor_value[0])), max(0, int(cursor_value[1])))
            except (TypeError, ValueError):
                cursor = (0, 0)
        task_id = value.get("task_id")
        revises = value.get("revises_turn_id")
        return cls(
            text=text,
            project_key=str(value.get("project_key", "")),
            task_id=task_id if isinstance(task_id, str) and task_id else None,
            draft_id=str(value.get("draft_id", "draft")),
            cursor=cursor,
            revision=_nonnegative(value.get("revision")),
            updated_at=str(value.get("updated_at", "")),
            revises_turn_id=revises if isinstance(revises, str) and revises else None,
            kind=str(value.get("kind", "draft")),
        )


@dataclass(frozen=True)
class ArchivedTurn:
    sequence: int
    path: Path


def _nonnegative(value: object) -> int:
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` through a temporary file and an atomic replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def turn_filename(sequence: int) -> str:
    return f"turn-{sequence:04d}.md"


class PromptStore:
    """Save drafts and immutable submitted prompts for every project and task."""

    _locks_guard = Lock()
    _locks: dict[Path, Lock] = {}

    def __init__(self, storage: LocalStorage):
        self.storage = storage

    # --- paths ----------------------------------------------------------------

    def task_dir(self, project: Path, task_id: str) -> Path:
        return self.storage.task_prompts_dir(project, task_id)

    def draft_path(self, project: Path, task_id: str | None, draft_id: str = "draft") -> Path:
        if task_id is None:
            return self.storage.drafts_dir(project) / f"{draft_id}.json"
        if draft_id == "draft":
            return self.task_dir(project, task_id) / DRAFT_FILENAME
        return self.task_dir(project, task_id) / f"{draft_id}.json"

    def turn_path(self, project: Path, task_id: str, sequence: int) -> Path:
        return self.task_dir(project, task_id) / turn_filename(sequence)

    def status(self, project: Path) -> StorageStatus:
        """Report whether this project's prompt folder can be written."""
        return self.storage.ensure(self.storage.project_prompts_dir(project))

    # --- drafts --------------------------------------------------------------------

    def save_draft(
        self,
        project: Path,
        task_id: str | None,
        text: str,
        *,
        cursor: tuple[int, int] = (0, 0),
        revision: int = 0,
        revises_turn_id: str | None = None,
        draft_id: str = "draft",
        kind: str = "draft",
    ) -> DraftRecord:
        """Persist a draft unless a newer revision is already on disk.

        Autosaves are debounced and may be scheduled from different moments of
        the editing session; the revision check guarantees that a delayed save
        never replaces text the user typed afterwards. Raises
        :class:`PromptStoreError` naming the path when the write fails.
        """
        path = self.draft_path(project, task_id, draft_id)
        record = DraftRecord(
            text=text,
            project_key=project_key(project),
            task_id=task_id,
            draft_id=draft_id,
            cursor=cursor,
            revision=revision,
            updated_at=_now(),
            revises_turn_id=revises_turn_id,
            kind=kind,
        )
        with self._lock_for(path):
            existing = self._read_draft(path)
            if existing is not None and existing.revision > revision:
                LOGGER.debug("Skipped stale draft save path=%s revision=%s newer=%s", path, revision, existing.revision)
                return existing
            try:
                atomic_write_text(path, json.dumps(record.to_dict(), indent=2, ensure_ascii=False) + "\n")
            except OSError as error:
                raise PromptStoreError(f"Could not save draft to {path}: {error}") from error
        return record

    def load_draft(self, project: Path, task_id: str | None, draft_id: str = "draft") -> DraftRecord | None:
        path = self.draft_path(project, task_id, draft_id)
        with self._lock_for(path):
            return self._read_draft(path)

    def delete_draft(self, project: Path, task_id: str | None, draft_id: str = "draft") -> None:
        path = self.draft_path(project, task_id, draft_id)
        with self._lock_for(path):
            try:
                path.unlink()
            except FileNotFoundError:
                return
            except OSError as error:
                raise PromptStoreError(f"Could not delete draft {path}: {error}") from error

    def list_drafts(self, project: Path, task_id: str | None) -> list[DraftRecord]:
        """Return every saved draft for a task (or the new-task drafts), newest first."""
        directory = self.storage.drafts_dir(project) if task_id is None else self.task_dir(project, task_id)
        drafts: list[DraftRecord] = []
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            return []
        for entry in entries:
            if entry.suffix != ".json":
                continue
            with self._lock_for(entry):
                draft = self._read_draft(entry)
            if draft is not None:
                drafts.append(draft)
        drafts.sort(key=lambda item: item.updated_at, reverse=True)
        return drafts

    def _read_draft(self, path: Path) -> DraftRecord | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as error:
            # A corrupt draft is preserved for inspection instead of deleted.
            LOGGER.warning("Unreadable draft preserved for inspection path=%s error=%s", path, error)
            self._preserve_corrupt(path)
            return None
        if not isinstance(value, dict):
            self._preserve_corrupt(path)
            return None
        return DraftRecord.from_dict(value)

    # --- immutable turns -----------------------------------------------------------

    def archive_turn(self, project: Path, task_id: str, sequence: int, text: str) -> Path:
        """Write one exact user submission and return its path.

        The write is idempotent: an identical existing file is kept as-is. A
        different existing file for the same sequence is preserved beside the
        new one (``turn-NNNN.md.stale-<timestamp>``) so nothing is silently
        overwritten. Raises :class:`PromptStoreError` naming the path when the
        write fails.
        """
        path = self.turn_path(project, task_id, sequence)
        with self._lock_for(path):
            try:
                existing = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                existing = None
            except OSError as error:
                raise PromptStoreError(f"Could not read existing prompt archive {path}: {error}") from error
            if existing == text:
                return path
            try:
                if existing is not None:
                    stale = path.with_name(f"{path.name}.stale-{int(time.time())}")
                    os.replace(path, stale)
                    LOGGER.warning("Preserved differing prompt archive path=%s as %s", path, stale)
                atomic_write_text(path, text)
            except OSError as error:
                raise PromptStoreError(f"Could not save prompt to {path}: {error}") from error
        return path

    def read_turn(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def archived_turns(self, project: Path, task_id: str) -> list[ArchivedTurn]:
        directory = self.task_dir(project, task_id)
        found: list[ArchivedTurn] = []
        try:
            entries = list(directory.iterdir())
        except OSError:
            return []
        for entry in entries:
            match = TURN_FILE_PATTERN.match(entry.name)
            if match:
                found.append(ArchivedTurn(int(match.group(1)), entry))
        found.sort(key=lambda item: item.sequence)
        return found

    def reconcile(
        self,
        project: Path,
        task_id: str,
        indexed: dict[int, str],
    ) -> list[ArchivedTurn]:
        """Regenerate missing archives from indexed text and return orphaned files.

        ``indexed`` maps each known turn sequence to its exact text. Missing
        files are rewritten from that text. Files whose sequence the index does
        not know are returned so the caller can offer them as recoverable
        drafts instead of executing them.
        """
        present = {turn.sequence: turn for turn in self.archived_turns(project, task_id)}
        for sequence, text in indexed.items():
            if sequence not in present:
                try:
                    self.archive_turn(project, task_id, sequence, text)
                except PromptStoreError as error:
                    LOGGER.warning("Could not regenerate prompt archive: %s", error)
        return [turn for sequence, turn in sorted(present.items()) if sequence not in indexed]

    # --- helpers -------------------------------------------------------------------

    @classmethod
    def _lock_for(cls, path: Path) -> Lock:
        with cls._locks_guard:
            return cls._locks.setdefault(path, Lock())

    @staticmethod
    def _preserve_corrupt(path: Path) -> None:
        try:
            os.replace(path, path.with_name(f"{path.name}.corrupt-{int(time.time())}"))
        except OSError:
            pass


__all__ = [
    "ArchivedTurn",
    "DRAFT_FILENAME",
    "DraftRecord",
    "NEW_TASK_DRAFT_ID",
    "PromptStore",
    "PromptStoreError",
    "atomic_write_text",
    "turn_filename",
]
