# Daedalus TUI Local Persistent Memory

## Summary
The TUI persists task history and the last opened project in one launch-root
local JSON file so failed work can be reopened for analysis and project
navigation can survive application restarts without depending on the Daedalus
daemon, a remote service, or a database server.

## Key Points
- **Local persistence**: The launch root stores all task history in one
  `.daedalus-memory.json` file. The file is intentionally ignored by Git.
- **Task history**: A single `tasks` entry maps each task worktree directory
  name to an ISO-8601 UTC submission `timestamp`, prompt, provider, model,
  reasoning, mode, current state, assistant outputs, non-negative token usage,
  resolved project path, error, and (when available) branch/worktree identity.
  The entry is upserted as the task progresses, including for planning,
  questioning, failed, paused, and cancelled tasks. An optional `topic` slug
  is stored when the task was tagged; absent or null means untagged.
- **Restart recovery**: Each project coordinator rehydrates its persisted task
  snapshots at startup. Failed tasks retain Retry, while active snapshots are
  normalized to paused so their preserved worktrees can be resumed safely.
- **Prompt history**: Plan answer submissions are retained in the task's
  optional `prompt_history` list, so the original request and each generated
  review prompt remain visible without creating duplicate worktree records.
- **Upsert behavior**: A missing memory file starts as an empty list; each
  task creates or updates one worktree-keyed entry while preserving other task
  entries.
- **Project restoration**: The launch root's memory file keeps one
  `last_opened_project` entry. Startup selects it when it is still among the
  discovered projects, and otherwise selects the first discovered project and
  creates or repairs the marker.
- **Project updates**: Selecting a different project immediately replaces the
  existing `last_opened_project` entry, including when focus later switches
  back to an earlier project, without changing task-history entries.
- **Per-project operating branch**: A `project_target_branches` map keyed by
  resolved project path stores each project's Branch Select choice. Absent key
  means the orchestration parameter default (`main`). Choosing that parameter
  default clears the project's map entry instead of storing the seed. Stale
  remembered branches that are no longer local heads are cleared on Select
  refresh so the default applies again without rewriting the default into
  memory.
- **Safe writes**: Updates are serialized in-process and written through a
  temporary file followed by an atomic replacement, so a completed write does
  not leave a partially written JSON document.
- **Corrupt input**: Invalid JSON or a non-list top-level value raises a
  validation error and leaves the existing file unchanged. Memory errors are
  isolated from otherwise successful task completion.
- **Legacy cleanup**: Older standalone token-usage entries are removed the next
  time the memory file is saved; new token usage is stored directly on its
  central task record.

## Relevant Files
- `tui/memory.py`: `TaskMemoryStore`, the default memory filename, central JSON
  schema, task-history, last-project, and per-project target-branch entries,
  validation, locking, and atomic file replacement.
- `tui/app.py`: Restores the remembered project at startup and updates it on
  project selection; persists and restores each project's operating branch.
- `tui/task_coordinator.py`: Records and rehydrates project task snapshots,
  and preserves active worktrees during coordinator shutdown.
- `tests/test_memory.py`: Covers task-history creation and upserts, removal of
  legacy usage entries, project-marker and target-branch map updates, and
  preservation of a corrupt file.
- `tests/test_app.py`: Covers startup restoration and sidebar persistence of
  the last opened project and per-project operating branch.
- `tests/test_task_coordinator.py`: Covers task snapshots for successful and
  unsuccessful task results.
- `README.md`: Documents the launch-root file and its lifecycle.

## Dev Mode
HACKING

## State Log
- 2026-08-24: Persisted optional task `topic` slugs so tagged topics survive restart and rehydration.
- 2026-08-23: Added a per-project `project_target_branches` map so Branch Select choices persist in launch-root memory without rewriting the orchestration parameter default.
- 2026-08-16: Documented the existing local JSON token-usage store, its completion-only recording boundary, and its atomic write and validation behavior.
- 2026-08-16: Added an updatable launch-root project marker so startup restores the last available project and falls back to the first discovered project.
- 2026-08-16: Normalized discovered project paths at app startup so memory restoration and fallback remain canonical across symlinked temporary paths.
- 2026-08-16: Seeded the ignored launch-root memory file with the canonical path of the active daedalus-tui worktree.
- 2026-08-16: Added provider, model, and reasoning metadata to token-usage entries, with nullable fields for legacy records and providers without those controls.
- 2026-08-16: Made startup initialization and every project-focus transition use an explicit single-marker update, with coverage for first launch and repeated switching.
- 2026-08-17: Centralized all prompt telemetry in the launch-root memory file and recorded the resolved project destination for each completed prompt.
- 2026-08-17: Added worktree-keyed task history snapshots so prompt metadata, lifecycle state, outputs, and failure diagnostics survive task completion or failure.
- 2026-08-17: Replaced standalone token-usage entries with timestamped task records while preserving the last-opened-project marker.
- 2026-08-17: Folded the legacy token count and resolved project path into each central task record and removed the standalone store alias.
- 2026-08-17: Persisted Plan tasks while they await questions or approval so their planning state and transcript remain selectable.
- 2026-08-17: Persisted generated plan-review prompts alongside the original task snapshot so submitted answers leave an auditable request history.
- 2026-08-20: Added branch/worktree metadata and startup rehydration for failed and interrupted tasks, with shutdown pausing active work instead of deleting its worktree.
