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
  task/project switches, and New Task. Closing the Daedalus window deliberately
  clears the draft the composer was holding instead of saving it, so the next
  launch starts on an empty prompt rather than last session's unsent text;
  `[drafts] clear_on_exit = false` keeps the old carry-over behavior. Only that
  one draft is removed -- prompts stashed by an interruption and prompts
  recovered from an archive stay reachable from Prompt history because they
  were set aside deliberately -- and a crash never reaches the close hook, so
  its last autosave is still restored. The close hook is final: shutdown
  reaches the draft through several entry points that each force a flush, and
  one of them runs after the hook, so once the window has closed the draft no
  later flush may write it back out. Send validates emptiness with
  `strip()` but archives the raw text, allocates the turn, persists it, and
  only then dispatches a run; a storage failure keeps the draft visible,
  reports the exact path, and launches nothing. Repeated Send events while a
  submission is pending are ignored. View refreshes (streaming output, inbox
  updates) never touch the composer, focus, or cursor.
- **Submit keys**: `Shift+Enter` and `Ctrl+Enter` both send, from any Vim mode;
  plain `Enter` always inserts a newline. `SUBMIT_KEYS` in
  `tui/vim_text_area.py` is the single source of truth: the prompt editor
  routes those keys to the app before the Vim router or TextArea can consume
  them, and `app.GLOBAL_SHORTCUTS` derives both its binding and its menu label
  from them. A terminal that does not implement the Kitty keyboard protocol
  sends a plain Enter for every variant, so neither key can be delivered there
  and the Send button remains the way to submit.
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
- **Automatic line breaks**: `apply_hard_line_breaks` gives every single
  newline inside a paragraph the CommonMark two-space hard break before the
  text reaches the `Markdown` widget. Agents hard-wrap prose and write one line
  per thought, which strict paragraph joining would collapse into a block that
  looks nothing like the response. Fenced and indented code are left
  byte-exact, an unterminated fence keeps its streamed content intact while a
  response is still arriving, lines that already end in a hard break are not
  doubled, and the Raw surface and `current_text()` still carry the response
  unmodified. `[viewer] hard_line_breaks` turns it off.
- **Action items header**: `extract_action_items` reads the selected source and
  the viewer shows the result above the rendered output, in place of the muted
  run-identity line that used to sit there; the identity now rides on the
  header. Three signals are collected, strongest first: unchecked task-list
  boxes, list items under a heading naming follow-up work (next steps,
  follow-ups, todo, remaining work, recommendations), and `TODO:`/`NEXT:`/
  `ACTION:` lines. Checked boxes are finished work and are skipped, code blocks
  are ignored so a template checklist is not mistaken for real work, items are
  deduplicated case-insensitively, and the list is capped by `[viewer]
  action_item_limit`. Extraction is keyed on the source's identity and text so
  a streaming response is not re-scanned per chunk. `[viewer]
  action_items_by_default` hides the header entirely.
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
  every `[usage] interval_seconds` (default 60). Only each provider's own
  `/usage` view knows the operator's real plan limits, so the bar asks the CLIs
  first and treats the local readers as a fallback.
- **Asking the CLIs for their usage**: Neither CLI is built to be scripted --
  Claude Code waits for a terminal, Codex refuses without one, and both stop on
  a permission prompt when run headless -- so the commands in
  `[usage.<provider>] commands` carry each CLI's documented permission override
  (`--permission-mode bypassPermissions` for Claude, `--ask-for-approval never
  --sandbox read-only` for Codex) and run attached to a pseudo-terminal when
  `use_pty` is set. Reaching `command_timeout_seconds` is a normal outcome, not
  a failure: a CLI that draws its usage panel and then waits has already printed
  the percentages, so the process group is killed and the captured text is
  parsed anyway. Candidates are tried in order until one yields windows, the one
  that worked is tried first next time, and these subcommands are not a stable
  interface, which is why more than one is listed. Because starting a CLI is far
  more expensive than reading a file and rate-limit windows move over hours, the
  commands run only every `[usage] command_interval_seconds` (default 300) and
  the bar redraws the last reading in between.
- **Reading a rendered usage panel**: `_windows_from_text` strips ANSI escapes
  and block-drawing runs, treats carriage returns as line breaks so a repainted
  panel reports its latest frame, and turns labelled percentages into
  `UsageWindow` values. Only wording that names a known window (session/5h,
  week/7d, opus, sonnet, context, spend) becomes a bar; a usage view prints many
  other numbers and a bar built from an unrecognised one would be worse than no
  bar. The provider's own reset phrase is kept verbatim, including one taken
  from the following line when that line is not itself another window. JSON
  output is still parsed first, so a CLI that gains a machine-readable mode
  needs no change here.
- **Falling back to local data**: When no command yields windows, the readers
  use the same local data those views are drawn from -- Codex rate-limit windows
  from its session logs and Claude Code's per-day token statistics cache,
  including Claude's `five_hour`, `seven_day`, and `spend_limit` windows when
  present. Those fall-back Claude bars are calibrated against this machine's
  busiest window rather than a real quota, which is exactly why the CLIs are
  asked first. Why each command failed is appended to the reading's detail and
  so reaches the usage bar's tooltip, because a renamed subcommand would
  otherwise look identical to a provider with no usage at all. Setting
  `fallback_to_local = false` shows nothing instead of an approximation.
- **Claude token and message reading**: Claude Code's statistics cache is a
  derived summary that can be absent, stale, or written under keys the reader
  does not know, each of which showed a flat `0 tok · 0 msgs` after a heavy
  day. Session transcripts under `[usage] claude_projects_dir` are therefore
  counted as the authoritative record -- every turn appends a JSON line whose
  `message.usage` holds input, output, and both cache token counts -- and each
  displayed figure is the larger of the two sources, which cannot double-count
  because both describe the same local calendar day. Transcripts touched
  within `[usage] claude_transcript_days` are parsed once and afterwards only
  from the byte offset where the previous poll stopped, a half-written trailing
  line is left for the next poll, turns replayed by a resumed or forked session
  are de-duplicated by their transcript `uuid`, tool results are not counted as
  messages, and a scan that outlives its poll interval blocks the next one
  rather than counting the same bytes twice.
- **Account-wide Claude total**: `UsageMonitor.read_claude_account_usage`
  answers "how much Claude have I used in total", which is a different question
  from the bar's "how much today". It merges the statistics cache's all-time
  `modelUsage` totals with a transcript scan that looks back `[usage]
  claude_account_scan_days` instead of `claude_transcript_days`, and takes the
  larger figure for the same reason the daily numbers do. It uses its own
  `ClaudeTranscriptUsage` instance so a wide scan can never redefine the recent
  window the bar reports, and so each reader re-parses only bytes it has not
  seen. The reading is returned as a `ClaudeAccountUsage` value with its source
  breakdown rather than being formatted here; the `Ctrl+T` statistics screen
  (`daedalus-tui-coding-statistics.md`) displays it from a background worker
  because the scan can touch every transcript on disk.
- **Codex rate-limit reading**: Codex writes rate limits only after a turn
  completes, so its most recently touched session log is frequently a
  just-started session holding none. The reader therefore scans back through
  `[usage] session_scan_limit` logs newest-first until a payload with a real
  percentage appears, reads only the last `session_tail_bytes` of each (the
  logs grow without bound and the newest payload is always at the end,
  tolerating a truncated leading line), skips a payload whose windows are all
  empty so a blank trailing entry cannot mask the current numbers, accepts both
  the `resets_in_seconds` duration Codex sends and the older `resets_at` epoch,
  takes `plan_type` from beside the windows or from the enclosing payload,
  falls back to `session`/`weekly` labels when a window omits
  `window_minutes`, and reports the reading's age in the tooltip so a stale
  number is visible as stale rather than presented as current.
- **Codex windows expire with their payload**: A session log holds a snapshot
  of a turn that has since finished, so a window's reset time is anchored to
  the moment Codex wrote it -- the event's own `timestamp`, or the session
  log's modification time when a build omits it -- and never to the moment the
  bar is drawn. Anchoring `resets_in_seconds` to the poll instead restarted the
  countdown every minute, so a window was never seen to reset and the bar kept
  redrawing the last recorded percentage: an idle 5-hour window showed 34% used
  when the quota had long since refilled. A window whose reset has passed is
  now reported at 0% with the percentage it held and the reading's age in the
  tooltip, so an empty bar is not mistaken for missing data; a window that has
  not reset keeps its recorded percentage with a countdown that actually
  elapses.
- **Claude rolling-window bars**: Claude Code publishes a rate-limit payload
  only on some builds, so the Claude row showed bare token counts beside
  Codex's bars. When no payload is present, the reader measures the same
  rolling `5h` and `7d` windows Claude's own `/usage` view reports from the
  transcript tokens it already counts: turns are bucketed into five-minute
  buckets (finer than any drawn window, under ten thousand buckets a month),
  a window is the sum of its buckets, and buckets older than
  `[usage] claude_transcript_days` are pruned while the day and lifetime
  totals stay whole. The bars are drawn against
  `[usage] claude_five_hour_token_limit` and `claude_weekly_token_limit`; both
  default to `0`, meaning calibrate against the busiest equivalent window in
  the scanned history, because no plan limit is stored locally and an invented
  one would pin the bar at 100% or leave it permanently near empty. The
  current window is one of the candidates for the peak, so a calibrated
  percentage can never exceed 100%. A published rate-limit payload always
  wins over the estimate. The tooltip names the basis (`of a 20.0k budget` or
  `of your busiest 5h in 30d`) and says when the oldest tokens leave the
  window -- "frees up in", not "resets in", because a rolling window never
  resets.
- **Usage progress bars**: Each reading carries its percentage windows as
  `UsageWindow` values, and `format_usage_bar` draws one labelled bar per
  window beneath its provider's summary line, `[usage] bar_width` cells wide.
  The bars are plain block text so they render on a markup-free `Static` in the
  fixed-width task sidebar; any non-zero usage keeps at least one filled cell
  and only a real 100% fills the bar, so neither a small number nor a near-limit
  one is rounded into a lie. Claude's daily token and message counts remain in
  its summary while any available rate-limit windows or configured context
  percentage get the same labelled bars as Codex.
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
- `tui/output_viewer.py`: Rendered/Raw Markdown viewer, source selection, hard line breaks, action-item extraction.
- `tui/debug_log.py`: Rotating runtime log, fault log, redaction, per-run diagnostics.
- `tui/usage_monitor.py`: Provider usage commands (pseudo-terminal execution, permission overrides, rendered-panel scraping), local usage readers, rate-limit windows, and progress-bar rendering.
- `tui/vim_text_area.py`: Completed Vim cut/copy/paste, registers, key routing.
- `tui/app.py`, `tui/app.tcss`: Composer drafts, interruption, follow-ups, viewer layout, history toggle, usage bar.
- `tui/memory.py`, `tui/token_usage.py`: Conversation snapshot fields, UI
  preferences, prompt/attempt accounting, and shared push-history storage.
- `parameter_files/daedalus-tui-prompting.toml`: Storage root, autosave delay, clear-on-exit, title length, viewer widths, line breaks, action-item header, context budget, error rotation.
- `parameter_files/daedalus-tui.toml`: `[usage]` cadence, command cadence and timeout, pseudo-terminal geometry, per-provider usage commands with their permission overrides and local fallback switch, session scan depth and tail size, transcript and account scan windows, bar width, Claude rolling-window token budgets.
- `tests/test_vim_text_area.py`, `tests/test_prompt_store.py`, `tests/test_debug_log.py`, `tests/test_output_viewer.py`, `tests/test_usage_monitor.py`, `tests/test_usage_command_settings.py`, plus extended `tests/test_app.py`, `tests/test_task_coordinator.py`, `tests/test_orchestrator.py`, `tests/test_agent_runner.py`, `tests/test_prompts.py`, `tests/test_token_usage.py`, `tests/test_memory.py`, `tests/test_config.py`.

## Dev Mode
HACKING

## State Log
- 2026-09-19: Made the usage bar ask the provider CLIs for their own
  percentages instead of only approximating them locally: usage commands now
  run attached to a pseudo-terminal with each CLI's permission prompt overridden
  (`--permission-mode bypassPermissions`, `--ask-for-approval never`), a panel
  that draws and then waits is killed at the timeout and its captured output
  scraped for labelled percentages anyway, candidates are tried in order with
  the winner remembered, the commands run on a slower `command_interval_seconds`
  cadence than the bar refreshes, and anything that fails falls back to the
  previous local readers with the reason recorded in the bar's tooltip.
- 2026-09-16: Made the composer's close hook final, so the forced draft flush
  that shutdown performs after it can no longer rewrite the prompt the close
  just cleared.
- 2026-09-16: Restored automatic clearing of the composer prompt when the
  Daedalus window is closed deliberately, behind `[drafts] clear_on_exit`, so a
  new session starts on an empty prompt while crash autosaves and stashed
  prompts stay recoverable.
- 2026-09-16: Fixed the Codex 5-hour bar, which reported stale usage (34% while
  the quota was untouched) because `resets_in_seconds` was measured from each
  poll rather than from the moment Codex wrote the payload, so a window was
  never observed to reset; reset times are now anchored to the payload's own
  timestamp and an expired window reads 0%.
- 2026-09-16: Added `UsageMonitor.read_claude_account_usage`, an account-wide Claude token total that scans `[usage] claude_account_scan_days` of transcripts through its own reader so the coding statistics screen can report total Claude usage without changing what the usage bar's recent window means.
- 2026-09-16: Gave the Claude usage row progress bars of its own by bucketing
  transcript tokens in time and measuring rolling 5-hour and 7-day windows
  against configurable token budgets that default to the busiest equivalent
  window on record, since Claude Code publishes no rate-limit payload locally
  and the row previously showed only token counts beside Codex's bars.
- 2026-09-16: Fixed the Claude usage reading, which reported zero tokens and
  zero messages whenever the statistics cache lacked today's entry, by counting
  Claude Code's session transcripts incrementally and showing the larger figure
  from the two sources, and added `Shift+Enter` beside `Ctrl+Enter` as a submit
  key routed by the prompt editor.
- 2026-09-16: Gave the Markdown viewer automatic line breaks and replaced its muted run-identity line with an action-items header extracted from the response; fixed the Codex usage reader, which reported "no usage data yet" whenever the newest session log was a just-started session and never read Codex's `resets_in_seconds` reset times, and added per-window progress bars to the usage panel.
- 2026-09-16: Extended usage-window parsing to Claude's documented rate-limit
  payloads and configured JSON sources, including 5-hour, 7-day, and spend
  bars with reset countdowns.
- 2026-09-15: Added conversation turns and runs, verbatim prompt archives and autosaved drafts under `prompts/`, non-destructive `Ctrl+C`/Cancel that restores the interrupted prompt, follow-up prompts within one named task, stable generated titles with an All tasks history filter, the optional right-third Markdown viewer, consolidated diagnostics under `errors/`, completed Vim cut/copy/paste with system-register commands, and a bottom-left usage bar that refreshes Codex and Claude usage every minute.
