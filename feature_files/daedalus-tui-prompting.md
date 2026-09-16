# Daedalus TUI Prompting, Drafts, Interruption, and Local Diagnostics

## Summary
The TUI treats every task as one durable conversation: each submitted prompt is
an immutable turn archived verbatim under the TUI's own `prompts/` folder,
each execution attempt is a run, `Ctrl+C`/Cancel stop a run without discarding
its worktree and hand the interrupted prompt back to the Vim composer, drafts
are saved automatically, tasks receive stable readable titles, an optional
Markdown viewer occupies the right third of a wide terminal, complete
diagnostics are written under `errors/`, and a bottom-left usage bar refreshes
provider usage every minute.

## Key Points
- **Task, turn, run**: A task is the conversation (stable logical id and
  title). A turn is one submitted user prompt (generated Plan follow-ups and
  implementation prompts are recorded as `generated` turns, never as user
  text). A run is one execution attempt; Retry adds a run, an edited or
  additional prompt adds a turn. `TaskRecord.turns`/`runs` carry ids, sequence
  numbers, exact text, timestamps, `revises_turn_id`, the provider/model/
  reasoning/mode/topic/branch snapshot, lifecycle timestamps, message ranges,
  diagnostics paths, tokens, and worktree context. Streamed callbacks are
  tagged with the run id and dropped when a newer run is active.
- **Storage root**: `parameter_files/daedalus-tui-prompting.toml` sets
  `[storage] data_root`; a relative value resolves against the TUI project
  directory (the owner of `parameter_files`), never the working directory or
  the target repository. `tui/local_storage.py` derives
  `prompts/<project-key>/…` and `errors/<project-key>/…` where the project key
  is the target's basename plus an 8-character digest of its resolved path, so
  same-named projects never share storage. Both folders are gitignored and
  excluded from launch-root project discovery.
- **Exact archives and drafts**: `tui/prompt_store.py` writes
  `turn-NNNN.md` files with the original text unchanged (no wrapper, trailing
  newlines intact) through a temporary file and atomic replacement, and
  `draft.json` with text, cursor, revision, and `revises_turn_id`. Revision
  checks stop a delayed autosave from replacing newer text; corrupt files are
  preserved beside the original; missing archives are regenerated from the
  task index on restart; an archived turn the index does not know is offered
  back as a `recovered` draft and never executed automatically.
- **Composer behavior**: The composer is always an editable draft: the
  new-task draft (New Task) or the selected task's follow-up draft. Drafts
  autosave after the configured typing delay and flush before Send, Cancel,
  task/project switches, New Task, and shutdown. Send validates emptiness with
  `strip()` but archives the raw text, allocates the turn, persists it, and
  only then dispatches a run; a storage failure keeps the draft visible,
  reports the exact path, and launches nothing. Repeated Send events while a
  submission is pending are ignored. View refreshes (streaming output, inbox
  updates) never touch the composer, focus, or cursor.
- **Interruption**: `Ctrl+C`, Cancel, and `Ctrl+X` share one action
  (`TaskCoordinator.interrupt`). It saves the current draft, stashes a
  different unsent follow-up as a `stashed` draft reachable from Prompt
  history, requests a non-destructive stop (`AgentControl.request_interrupt`),
  and loads the interrupted turn's exact text into the composer in Insert mode
  with the cursor at the end. The run ends as `interrupted` (not an error),
  the worktree, branch, and uncommitted files stay, and the task is
  continuable by Resume or by sending the edited prompt as the next turn. A
  queued run is released without creating a worktree; a task waiting at the
  serialized integration gate observes the stop and leaves the queue; the
  stop is checked immediately before promotion, and an in-progress Git
  operation reaches a known state and is reported truthfully. Repeated presses
  are idempotent; with nothing running the draft stays intact and the status
  says so; modal dialogs keep their own Escape behavior. The explicit
  destructive discard (`TaskCoordinator.cancel`) is no longer reachable from
  the UI.
- **Follow-up turns**: `TaskCoordinator.submit_followup` requires an existing
  task with no active run. The transmitted prompt is provider-neutral
  conversation context (`tui/prompts.py: build_conversation_prompt`) holding
  the original request, recent user turns and assistant responses within the
  configured character budget with an explicit omission marker, and the latest
  instruction. A preserved worktree is reused (the agent is told to inspect
  existing work); a cleaned-up one is replaced by a fresh worktree from the
  operating branch under a new execution suffix (`<task>-r2`, …) while the
  logical task id and title stay. Stale retry prompts, stop flags, and
  `resume_from` are reset. Follow-ups default to the task's configuration;
  provider/model/reasoning/mode changes made after selecting the task are
  recorded on the new turn. Plan review keeps its question protocol, and
  Implement continues the same conversation as a coding run.
- **Titles and history**: Titles come from the first meaningful line or
  sentence (Markdown decoration removed, whitespace collapsed, cut at a word
  boundary to the configured length, `Task <short-id>` fallback), are
  persisted once, and never change on follow-ups. The inbox shows the title
  with the existing ellipsis; the composer header shows it in full. The All
  tasks toggle lists completed and interrupted history so any conversation can
  be reopened after a restart.
- **Restart**: Task snapshots are keyed by the stable logical id
  (`task-<id>`), migrating worktree-keyed entries once, and carry
  `schema_version` 2 with title, turns, runs, active ids, prompt count, and
  storage paths. Legacy snapshots load with the original prompt as the first
  user turn, `prompt_history` extras as generated context, and unknown
  timestamps left unknown. Runs active when the process ended become
  `interrupted` (recoverable, never auto-launched).
- **Output viewer**: `tui/output_viewer.py` is a sibling of the main
  workspace. When shown on a wide terminal it takes one third of the whole
  usable width (about 60 of 180 columns); below the configured minimum widths
  or in compact mode it becomes a full-width alternate view with a Back
  control. It renders Markdown with Textual's `Markdown` widget from stored
  response text (never wrapped transcript lines), offers Latest response,
  earlier responses, and the parsed plan text as sources, debounces streaming
  re-renders, discards outdated renders, follows live output only when already
  at the bottom, falls back to a Raw read-only text surface on render failure
  (logged once), reports links instead of opening them, and never executes
  code or fetches images. Its visibility is remembered in launch-root memory.
- **Diagnostics**: `tui/debug_log.py` writes `errors/daedalus.log` (rotating,
  default 2 MB × 3) from app construction onward, keeps fault-handler output
  in `errors/faults.log`, logs lifecycle events with UTC timestamp, severity,
  project key, task, turn, run, phase, and provider, scrubs known credential
  patterns, reports a log that cannot be written once on stderr without
  recursing, and appends each run's complete error text to
  `errors/<project-key>/<task-id>/turn-NNNN-run-NNNN.log` before the UI
  truncates it. The Errors view names the run file and the runtime log.
  Requested interruptions are lifecycle events; failed stops or cleanups stay
  errors. Legacy `.daedalus-debug.log` files are left in place.
- **Usage bar**: `tui/usage_monitor.py` refreshes the bottom-left usage bar
  every `[usage] interval_seconds` (default 60). Neither provider CLI has a
  non-interactive `usage` subcommand (Claude Code 2.1 waits for a terminal,
  Codex 0.154 refuses without one), so the default readers use the same local
  data those CLIs show in `/usage` and `/status`: Codex rate-limit windows from
  its newest session log and Claude Code's per-day token statistics cache. A
  `command` per provider runs any program instead (stdin closed, timeout,
  process-group kill) and shows its JSON usage fields or first line.
- **Vim composer**: `tui/vim_text_area.py` extends the installed
  `VimTextArea` with a line-aware register, counted `dd`/`yy`/`cc`, Vim `w`
  motion and in-line `dw`/`cw`/`yw`, anchor-based visual and visual-line
  modes, Vim paste placement including the last line, `"+y`/`"+p`/`"+P`,
  clipboard mirroring of every cut and yank (with a status note when the host
  clipboard is unavailable), `Ctrl+R` redo inside the editor, `Ctrl+C`/`Ctrl+X`
  routed to interruption, and a compact INSERT/NORMAL/VISUAL/V-LINE indicator.

## Relevant Files
- `tui/local_storage.py`: Storage root, project keys, prompt and error folders.
- `tui/prompt_store.py`: Exact turn archives, drafts, revision checks, reconciliation.
- `tui/conversation.py`: `TaskTurn`, `TaskRun`, schema version, title generation.
- `tui/task_coordinator.py`: Turns, runs, interrupt, follow-ups, stable keys, restore, run diagnostics.
- `tui/orchestrator.py`: Interrupted results, stop-aware integration gate, promotion boundary.
- `tui/agent_runner.py`: `AgentControl.request_interrupt`.
- `tui/prompts.py`: Bounded conversation context for follow-up turns.
- `tui/output_viewer.py`: Rendered/Raw Markdown viewer and source selection.
- `tui/debug_log.py`: Rotating runtime log, fault log, redaction, per-run diagnostics.
- `tui/usage_monitor.py`: Provider usage readers for the usage bar.
- `tui/vim_text_area.py`: Completed Vim cut/copy/paste, registers, key routing.
- `tui/app.py`, `tui/app.tcss`: Composer drafts, interruption, follow-ups, viewer layout, history toggle, usage bar.
- `tui/memory.py`, `tui/token_usage.py`: Conversation snapshot fields, UI preferences, prompt/attempt accounting.
- `parameter_files/daedalus-tui-prompting.toml`: Storage root, autosave delay, title length, viewer widths, context budget, error rotation.
- `parameter_files/daedalus-tui.toml`: `[usage]` cadence and per-provider sources.
- `tests/test_vim_text_area.py`, `tests/test_prompt_store.py`, `tests/test_debug_log.py`, `tests/test_output_viewer.py`, `tests/test_usage_monitor.py`, plus extended `tests/test_app.py`, `tests/test_task_coordinator.py`, `tests/test_orchestrator.py`, `tests/test_agent_runner.py`, `tests/test_prompts.py`, `tests/test_token_usage.py`, `tests/test_memory.py`, `tests/test_config.py`.

## Dev Mode
HACKING

## State Log
- 2026-09-15: Added conversation turns and runs, verbatim prompt archives and autosaved drafts under `prompts/`, non-destructive `Ctrl+C`/Cancel that restores the interrupted prompt, follow-up prompts within one named task, stable generated titles with an All tasks history filter, the optional right-third Markdown viewer, consolidated diagnostics under `errors/`, completed Vim cut/copy/paste with system-register commands, and a bottom-left usage bar that refreshes Codex and Claude usage every minute.
