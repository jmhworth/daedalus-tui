# Daedalus TUI Topics

## Summary
Optional Topics group closely related tasks and features under a shared
git-tracked markdown umbrella (`topic_files/{slug}.md`) so agents can carry
concise recurrent memory without replaying full conversations. The TUI can now
collect the topic context and queue an agent to initialize and populate the
markdown.

## Key Points
- **Optional attachment**: Tasks may omit a topic. The settings-bar Topic
  Select defaults to `(None)` and remembers the selected topic per project in
  launch-root memory; New Task and project switches restore that project-local
  default. Selecting `(None)` clears the project default.
- **Create Topic flow**: The `CapsLock+3` shortcut opens a modal for a topic
  name and the desired end state. It queues a coding task with the initialized
  template and asks the agent to expand the durable context in
  `topic_files/{slug}.md`.
- **Safe handoff**: The creation task writes the new file in its isolated
  worktree, allowing normal orchestration promotion to add it to the project
  without leaving an uncommitted primary-worktree file behind.
- **Schema**: Each topic file has an H1 name plus `## Topic Goal`,
  `## Topic Status` (`open` | `complete`), and `## State Log`.
- **Prompt embed**: When tagged, the orchestrator loads the topic from the
  task worktree and embeds it with mode-specific instructions (coding may
  append State Log / set Status; ask/plan are read-only for topic files;
  repair/resolver re-embed and only write when the umbrella outcome changes).
- **Read-only viewer**: A selected topic can be opened from the settings bar
  in a selectable, read-only modal so operators can inspect the markdown
  without leaving the TUI or changing the file.
- **Inheritance**: Plan → Implement, retry, resume, repair, resolver, and
  plan-question clarifications keep the originating task's topic slug.
- **Boundary**: Topics are project-local and optional; project discovery still
  keys only on `feature_files/`. Concurrent State Log appends can race the
  same way concurrent feature-file edits can.

## Relevant Files
- `tui/topics.py`: Discovery, creation validation/template helpers, load, and prompt embed.
- `tui/prompts.py`: Topic creation handoff plus optional topic blocks on task, repair, and resolver prompts.
- `tui/orchestrator.py`: Loads tagged topics from the task worktree before prompts.
- `tui/task_coordinator.py`: Optional `topic` on `TaskRecord` / submit and inheritance.
- `tui/memory.py`: Optional `topic` on persisted task snapshots.
- `tui/app.py`: Create Topic modal, task handoff, and Topic Select beside Mode / Branch.
- `parameter_files/daedalus-tui-topics.toml`: Topic creation length limits and paired settings.
- `tests/test_topics.py`, `tests/test_prompts.py`, `tests/test_app.py`,
  `tests/test_memory.py`, `tests/test_task_coordinator.py`: Coverage for
  discovery, embeds, UI, persistence, and inheritance.

## Dev Mode
HACKING

## State Log
- 2026-08-24: Introduced optional Topics with markdown schema, prompt embeds,
  settings-bar Select, memory persistence, and coding State Log updates.
- 2026-08-25: Added a Create Topic modal that queues an isolated coding task to
  initialize the schema and populate a new topic from the operator's desired end state.
- 2026-08-25: Added per-project topic defaults so New Task and project switches
  restore the last selected topic, with stale topic selections cleared safely.
- 2026-08-25: Persisted the selected topic during prompt submission so immediate
  New Task actions restore the project-local default before queued UI events run.
- 2026-09-01: Added a settings-bar View Topic action with a selectable
  read-only markdown modal for the active project topic.
- 2026-09-14: Moved Create Topic from the project toolbar to the `F3` keyboard
  shortcut after terminal encodings made Ctrl+Shift+T unreliable.
