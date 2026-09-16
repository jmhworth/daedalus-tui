# Daedalus TUI Task Deletion

## Summary

The task sidebar supports Vim-style deletion of inactive Daedalus task
conversations. The task under the sidebar cursor is removed from the active
coordinator and its durable task snapshot when the user presses `dd`.

## Key Points

- **Sidebar command**: Focus the task inbox, navigate to a row, and press `dd`
  to delete that task; a single `d` is held as a pending command and does not
  affect prompt or output text.
- **Cursor-targeted**: Deletion uses the row under the `DataTable` cursor, not
  only the currently rendered conversation, so a task can be deleted without
  opening it first.
- **Active-run safety**: Active tasks and running plan clarifications remain in
  the inbox until their work stops. Preserved inactive worktrees use the same
  explicit cleanup route as task cancellation before the task is removed.
- **Persistence**: The in-memory coordinator record and the matching
  `.daedalus-memory.json` snapshot are removed together; other projects and
  task snapshots remain intact.

## Relevant Files

- `tui/app.py`: Sidebar cursor command sequence, deletion action, and shortcut
  reference.
- `tui/task_coordinator.py`: Inactive-task deletion and preserved-worktree
  cleanup.
- `tui/memory.py`: Atomic removal of one persisted task snapshot.
- `tests/test_app.py`, `tests/test_memory.py`: Sidebar command and snapshot
  isolation coverage.
- `parameter_files/daedalus-tui-task-deletion.toml`: Fixed sidebar command
  convention.

## Dev Mode

HACKING

## State Log

- 2026-09-16: Added cursor-targeted `dd` deletion for inactive sidebar tasks,
  coordinator cleanup, and durable snapshot removal.
