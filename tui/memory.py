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
OPENED_PROJECT_DIRECTORIES_KEY = "opened_project_directories"
PROJECT_TARGET_BRANCHES_KEY = "project_target_branches"
PROJECT_TOPICS_KEY = "project_topics"
UI_PREFERENCES_KEY = "ui_preferences"
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

    def get_opened_project_directories(self) -> tuple[Path, ...]:
        """Return the directories opened by path, in the order they were added."""
        with self._lock:
            entries = self._read_entries()
        paths: list[Path] = []
        seen: set[Path] = set()
        for entry in entries:
            value = entry.get(OPENED_PROJECT_DIRECTORIES_KEY)
            if not isinstance(value, list):
                continue
            for item in value:
                if not isinstance(item, str) or not item:
                    continue
                resolved = Path(item).expanduser().resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    paths.append(resolved)
        return tuple(paths)

    def add_opened_project_directory(self, project_path: Path) -> None:
        """Remember a directory opened by path so it returns on the next launch."""
        self._write_opened_project_directories(add=project_path)

    def remove_opened_project_directory(self, project_path: Path) -> None:
        """Forget a directory opened by path, used when it no longer exists."""
        self._write_opened_project_directories(remove=project_path)

    def _write_opened_project_directories(
        self,
        add: Path | None = None,
        remove: Path | None = None,
    ) -> None:
        with self._lock:
            entries = self._read_entries()
            updated_entries: list[dict[str, object]] = []
            paths: list[str] = []
            seen: set[str] = set()
            for existing in entries:
                existing_paths = existing.get(OPENED_PROJECT_DIRECTORIES_KEY)
                if isinstance(existing_paths, list):
                    for item in existing_paths:
                        if isinstance(item, str) and item and item not in seen:
                            seen.add(item)
                            paths.append(item)
                    continue
                if "tokens" in existing:
                    continue
                updated_entries.append(existing)
            if remove is not None:
                key = str(remove.expanduser().resolve())
                paths = [item for item in paths if item != key]
            if add is not None:
                key = str(add.expanduser().resolve())
                if key not in paths:
                    paths.append(key)
            if paths:
                updated_entries.append({OPENED_PROJECT_DIRECTORIES_KEY: paths})
            self._write_entries(updated_entries)

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

    def get_ui_preference(self, key: str, default: object = None) -> object:
        """Return one remembered UI preference (for example viewer visibility)."""
        with self._lock:
            entries = self._read_entries()
        for entry in reversed(entries):
            mapping = entry.get(UI_PREFERENCES_KEY)
            if isinstance(mapping, dict) and key in mapping:
                return mapping[key]
        return default

    def set_ui_preference(self, key: str, value: object) -> None:
        """Remember one UI preference without losing other entries."""
        with self._lock:
            entries = self._read_entries()
            updated_entries: list[dict[str, object]] = []
            mapping: dict[str, object] = {}
            replaced = False
            for existing in entries:
                existing_map = existing.get(UI_PREFERENCES_KEY)
                if isinstance(existing_map, dict):
                    if not replaced:
                        mapping.update(existing_map)
                        replaced = True
                    continue
                if "tokens" in existing:
                    continue
                updated_entries.append(existing)
            mapping[key] = value
            updated_entries.append({UI_PREFERENCES_KEY: mapping})
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

    def delete_task(self, task_id: str) -> bool:
        """Remove one persisted task snapshot without touching other entries."""
        if not task_id:
            return False
        with self._lock:
            entries = self._read_entries()
            updated_entries: list[dict[str, object]] = []
            tasks: dict[str, object] = {}
            found = False
            for existing in entries:
                existing_tasks = existing.get(TASKS_KEY)
                if isinstance(existing_tasks, dict):
                    tasks.update(existing_tasks)
                    continue
                updated_entries.append(existing)
            if task_id not in tasks:
                return False
            tasks.pop(task_id, None)
            found = True
            if tasks:
                updated_entries.append({TASKS_KEY: tasks})
            self._write_entries(updated_entries)
            return found

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
        title: str | None = None,
        turns: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None,
        runs: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None,
        active_turn_id: str | None = None,
        active_run_id: str | None = None,
        schema_version: int | None = None,
        prompt_count: int | None = None,
        project_key: str | None = None,
        diagnostics_dir: Path | None = None,
        prompts_dir: Path | None = None,
    ) -> None:
        """Upsert a task snapshot keyed by its stable logical task key.

        Older snapshots were keyed by the worktree directory name; passing
        ``previous_task_id`` migrates such an entry onto the new key once while
        leaving every other entry untouched. The conversation fields (title,
        turns, runs, active identifiers) are written only when supplied so a
        legacy-shaped record stays byte-compatible.
        """
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
        if title is not None:
            task["title"] = title
        if turns is not None:
            task["turns"] = [dict(turn) for turn in turns]
        if runs is not None:
            task["runs"] = [dict(run) for run in runs]
        if active_turn_id is not None:
            task["active_turn_id"] = active_turn_id
        if active_run_id is not None:
            task["active_run_id"] = active_run_id
        if schema_version is not None:
            task["schema_version"] = int(schema_version)
        if prompt_count is not None:
            task["prompt_count"] = max(0, int(prompt_count))
        if project_key is not None:
            task["project_key"] = project_key
        if diagnostics_dir is not None:
            task["diagnostics_dir"] = str(diagnostics_dir)
        if prompts_dir is not None:
            task["prompts_dir"] = str(prompts_dir)
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
