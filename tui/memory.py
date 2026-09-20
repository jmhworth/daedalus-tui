"""Small local JSON stores for persistent task history."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from threading import Lock

from .verification import truncate_diagnostic


DEFAULT_MEMORY_FILE = ".daedalus-memory.json"
LAST_OPENED_PROJECT_KEY = "last_opened_project"
PROJECT_TARGET_BRANCHES_KEY = "project_target_branches"
PROJECT_TOPICS_KEY = "project_topics"
TASKS_KEY = "tasks"


class TaskMemoryStore:
    """Persist task history, last project, and per-project task defaults."""

    _locks_guard = Lock()
    _locks: dict[Path, Lock] = {}

    def __init__(self, path: Path):
        self.path = path
        lock_key = path.expanduser().resolve()
        with self._locks_guard:
            self._lock = self._locks.setdefault(lock_key, Lock())

    def get_last_opened_project(self) -> Path | None:
        """Return the remembered project path, if the memory contains one."""
        with self._lock:
            entries = self._read_entries()
        for entry in reversed(entries):
            value = entry.get(LAST_OPENED_PROJECT_KEY)
            if isinstance(value, str) and value:
                return Path(value).expanduser().resolve()
        return None

    def set_last_opened_project(self, project_path: Path) -> None:
        """Set the single project marker without losing task records."""
        entry = {LAST_OPENED_PROJECT_KEY: str(project_path.expanduser().resolve())}
        with self._lock:
            entries = self._read_entries()
            updated_entries: list[dict[str, object]] = []
            replaced = False
            for existing in entries:
                if LAST_OPENED_PROJECT_KEY in existing:
                    if not replaced:
                        updated_entries.append(entry)
                        replaced = True
                    continue
                if "tokens" in existing:
                    continue
                updated_entries.append(existing)
            if not replaced:
                updated_entries.append(entry)
            self._write_entries(updated_entries)

    def record_last_opened_project(self, project_path: Path) -> None:
        """Backward-compatible alias for :meth:`set_last_opened_project`."""
        self.set_last_opened_project(project_path)

    def get_project_target_branch(self, project_path: Path) -> str | None:
        """Return the remembered operating branch for a project, if any."""
        key = str(project_path.expanduser().resolve())
        with self._lock:
            entries = self._read_entries()
        for entry in reversed(entries):
            mapping = entry.get(PROJECT_TARGET_BRANCHES_KEY)
            if not isinstance(mapping, dict):
                continue
            value = mapping.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def set_project_target_branch(self, project_path: Path, branch: str) -> None:
        """Remember one project's operating branch without losing other entries."""
        key = str(project_path.expanduser().resolve())
        with self._lock:
            entries = self._read_entries()
            updated_entries: list[dict[str, object]] = []
            mapping: dict[str, object] = {}
            replaced = False
            for existing in entries:
                existing_map = existing.get(PROJECT_TARGET_BRANCHES_KEY)
                if isinstance(existing_map, dict):
                    if not replaced:
                        mapping.update(existing_map)
                        replaced = True
                    continue
                if "tokens" in existing:
                    continue
                updated_entries.append(existing)
            mapping[key] = branch
            updated_entries.append({PROJECT_TARGET_BRANCHES_KEY: mapping})
            self._write_entries(updated_entries)

    def clear_project_target_branch(self, project_path: Path) -> None:
        """Remove one project's operating-branch override (absent = use default)."""
        key = str(project_path.expanduser().resolve())
        with self._lock:
            entries = self._read_entries()
            updated_entries: list[dict[str, object]] = []
            mapping: dict[str, object] = {}
            replaced = False
            for existing in entries:
                existing_map = existing.get(PROJECT_TARGET_BRANCHES_KEY)
                if isinstance(existing_map, dict):
                    if not replaced:
                        mapping.update(existing_map)
                        replaced = True
                    continue
                if "tokens" in existing:
                    continue
                updated_entries.append(existing)
            mapping.pop(key, None)
            if mapping:
                updated_entries.append({PROJECT_TARGET_BRANCHES_KEY: mapping})
            self._write_entries(updated_entries)

    def get_project_topic(self, project_path: Path) -> str | None:
        """Return the remembered default topic for a project, if any."""
        key = str(project_path.expanduser().resolve())
        with self._lock:
            entries = self._read_entries()
        for entry in reversed(entries):
            mapping = entry.get(PROJECT_TOPICS_KEY)
            if not isinstance(mapping, dict):
                continue
            value = mapping.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def set_project_topic(self, project_path: Path, topic: str) -> None:
        """Remember one project's default topic without losing other entries."""
        key = str(project_path.expanduser().resolve())
        with self._lock:
            entries = self._read_entries()
            updated_entries: list[dict[str, object]] = []
            mapping: dict[str, object] = {}
            replaced = False
            for existing in entries:
                existing_map = existing.get(PROJECT_TOPICS_KEY)
                if isinstance(existing_map, dict):
                    if not replaced:
                        mapping.update(existing_map)
                        replaced = True
                    continue
                if "tokens" in existing:
                    continue
                updated_entries.append(existing)
            mapping[key] = topic
            updated_entries.append({PROJECT_TOPICS_KEY: mapping})
            self._write_entries(updated_entries)

    def clear_project_topic(self, project_path: Path) -> None:
        """Remove one project's topic override (absent = no default topic)."""
        key = str(project_path.expanduser().resolve())
        with self._lock:
            entries = self._read_entries()
            updated_entries: list[dict[str, object]] = []
            mapping: dict[str, object] = {}
            replaced = False
            for existing in entries:
                existing_map = existing.get(PROJECT_TOPICS_KEY)
                if isinstance(existing_map, dict):
                    if not replaced:
                        mapping.update(existing_map)
                        replaced = True
                    continue
                if "tokens" in existing:
                    continue
                updated_entries.append(existing)
            mapping.pop(key, None)
            if mapping:
                updated_entries.append({PROJECT_TOPICS_KEY: mapping})
            self._write_entries(updated_entries)

    def get_tasks(self) -> dict[str, dict[str, object]]:
        """Return persisted task snapshots keyed by their stable task ID."""
        with self._lock:
            entries = self._read_entries()
        tasks: dict[str, dict[str, object]] = {}
        for entry in entries:
            value = entry.get(TASKS_KEY)
            if not isinstance(value, dict):
                continue
            for task_id, task in value.items():
                if isinstance(task_id, str) and isinstance(task, dict):
                    tasks[task_id] = dict(task)
        return tasks

    def record_task(
        self,
        task_id: str,
        prompt: str,
        provider: str | None,
        model: str | None,
        reasoning: str | None,
        mode: str,
        state: str,
        outputs: list[str] | tuple[str, ...] = (),
        error: str | None = None,
        previous_task_id: str | None = None,
        submitted_at: float | None = None,
        tokens: int | None = 0,
        project: Path | None = None,
        prompt_history: list[str] | tuple[str, ...] = (),
        logical_task_id: str | None = None,
        branch_name: str | None = None,
        worktree_path: Path | None = None,
        base_commit: str | None = None,
        submission_sequence: int | None = None,
        resume_from: str | None = None,
        topic: str | None = None,
        sync_recovery: bool = False,
        sync_operating_branch: str | None = None,
        sync_remote: str | None = None,
        sync_used_temp_branch: bool = False,
        sync_temp_branch_name: str | None = None,
        sync_conflict_attempt_limit: int | None = None,
    ) -> None:
        """Upsert a task snapshot keyed by the task worktree's directory name."""
        task = {
            "timestamp": datetime.fromtimestamp(submitted_at or 0, timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
            if submitted_at is not None
            else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "prompt": prompt,
            "provider": provider,
            "model": model,
            "reasoning": reasoning,
            "mode": mode,
            "state": state,
            "outputs": list(outputs),
            "error": truncate_diagnostic(error) if isinstance(error, str) else error,
            "tokens": max(0, int(tokens)) if tokens is not None else None,
            "project": str(project.expanduser().resolve()) if project is not None else None,
        }
        if len(prompt_history) > 1:
            task["prompt_history"] = list(prompt_history)
        if logical_task_id is not None:
            task["task_id"] = logical_task_id
        if branch_name is not None:
            task["branch_name"] = branch_name
        if worktree_path is not None:
            task["worktree_path"] = str(worktree_path.expanduser().resolve())
        if base_commit is not None:
            task["base_commit"] = base_commit
        if submission_sequence is not None:
            task["submission_sequence"] = int(submission_sequence)
        if resume_from is not None:
            task["resume_from"] = resume_from
        cleaned_topic = topic.strip() if isinstance(topic, str) and topic.strip() else None
        if cleaned_topic is not None:
            task["topic"] = cleaned_topic
        if sync_recovery:
            task["sync_recovery"] = True
            if sync_operating_branch:
                task["sync_operating_branch"] = sync_operating_branch
            if sync_remote:
                task["sync_remote"] = sync_remote
            task["sync_used_temp_branch"] = bool(sync_used_temp_branch)
            if sync_temp_branch_name:
                task["sync_temp_branch_name"] = sync_temp_branch_name
            if sync_conflict_attempt_limit is not None:
                task["sync_conflict_attempt_limit"] = int(sync_conflict_attempt_limit)
        with self._lock:
            entries = self._read_entries()
            updated_entries: list[dict[str, object]] = []
            tasks: dict[str, object] = {}
            replaced = False
            for existing in entries:
                existing_tasks = existing.get(TASKS_KEY)
                if isinstance(existing_tasks, dict):
                    if not replaced:
                        tasks.update(existing_tasks)
                        replaced = True
                    continue
                if "tokens" in existing:
                    continue
                updated_entries.append(existing)
            if previous_task_id and previous_task_id != task_id:
                tasks.pop(previous_task_id, None)
            tasks[task_id] = task
            updated_entries.append({TASKS_KEY: tasks})
            self._write_entries(updated_entries)

    def _read_entries(self) -> list[dict[str, object]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except OSError as error:
            raise ValueError(f"Could not read memory file {self.path}: {error}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"Memory file {self.path} is not valid JSON.") from error
        if not isinstance(value, list):
            raise ValueError(f"Memory file {self.path} must contain a JSON list.")
        return [entry for entry in value if isinstance(entry, dict)]

    def _write_entries(self, entries: list[dict[str, object]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(entries, temporary, indent=2)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass
