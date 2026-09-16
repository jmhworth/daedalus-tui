# Mike's Daedalus TUI improvement plan

Planning date: September 15, 2026. This document describes implementation work; it does not implement the features.

The result should be a TUI where prompts support familiar Vim editing, an optional Markdown viewer occupies the right third of the screen, every prompt is saved locally, interrupted prompts return to the editor, conversations can continue within one automatically named task, and errors are available in a local folder.

**Paths and scope**

Treat `/daedalus-tui/prompts` and `/daedalus-tui/errors` as folders inside the Daedalus TUI project. In this checkout, those paths are:

- `/Users/mike/daedalus/daedalus-tui/prompts/`
- `/Users/mike/daedalus/daedalus-tui/errors/`

Resolve this storage root independently of the selected target repository, task worktree, and current working directory. Launching Daedalus against another project must not move the saved prompts or errors into that project. Make the storage root configurable through a parameter file so the TUI remains independently exportable; do not hardcode this user's absolute path in application code or introduce new command-line options.

“Claude-style prompting” means the interaction requested here: stop a run, get the submitted prompt back, edit or extend it, and send another turn in the same task. Apply that behavior to all existing providers. Native provider conversation/session resumption is not required for the first implementation; persisted conversation context can support it across providers.

**What already exists**

| Area | Current implementation | Work needed |
| --- | --- | --- |
| Prompt editor | `tui/vim_text_area.py` extends `VimTextArea`; Insert, Normal, Visual, whole-line selection, yank, paste, and native clipboard helpers already exist. | Verify and complete cut/copy/paste behavior, operator coverage, and key routing. |
| Output | `tui/transcript.py` provides a selectable plain-text log. `tui/app.py` toggles between transcript and errors in one central panel. | Add an optional right-side viewer with rendered Markdown and a raw-text mode. |
| Prompts and tasks | `TaskRecord` stores the original prompt and a string-based `prompt_history`; `.daedalus-memory.json` stores task snapshots. | Add durable drafts, exact prompt files, explicit turns, and follow-up submission for every mode. |
| Cancellation | `Ctrl+C` copies text. Cancel/`Ctrl+X` can stop the agent and remove its worktree. Pause preserves work. | Make Cancel and `Ctrl+C` interrupt the current run without discarding progress, then restore its prompt. |
| Task names | The inbox displays a shortened version of `record.prompt`; there is no dedicated persisted title. | Generate and store a stable readable title. |
| Diagnostics | `tui/debug_log.py` writes a rotating `.daedalus-debug.log` under the launch root. Task error text can be truncated. | Route diagnostics into `errors/`, retain useful per-run errors, and expose their location. |

Relevant feature context was read from `feature_files/daedalus-tui.md`, `feature_files/daedalus-tui-local-memory.md`, and `feature_files/daedalus-tui-orchestration.md`. The saved Graphify report was also consulted. A focused Graphify query could not run because the `graphify` executable is unavailable in this environment; source inspection supplied the implementation details below.

**Step 1 — Establish the interaction and state model**

1. Define a **task** as the durable conversation, a **turn** as one submitted user prompt, and a **run** as an execution attempt for a turn. Retrying an unchanged prompt creates another run; submitting an edited or additional prompt creates another turn.
2. Keep the original request and every submitted turn immutable. Use a separate editable draft for the composer. Editing a restored prompt must not rewrite the previously submitted prompt.
3. Make New Task explicitly start a separate conversation. When a task is selected, Send submits a follow-up to that task, with its title visible above the composer.
4. Allow one executing run per task. Independent tasks retain the existing concurrency limit and serialized integration gate. Users may compose the next prompt while a run is active, but Send remains disabled until that run has stopped or finished.
5. Specify these controls before changing the event handlers:

| Control | Intended behavior |
| --- | --- |
| `Esc` | Return the prompt editor to Normal mode and clear pending selection/operator state. |
| `Enter` in Insert mode | Insert a newline. |
| `Ctrl+Enter` / Send | Submit the current draft to the selected task, or create a task from a new-task draft. |
| `Ctrl+C` / Cancel | Interrupt the selected task's active run, preserve progress, and restore that run's user prompt for editing. |
| `Ctrl+X` | Retain as an alias for the same interruption action. |
| `y`, `yy`, visual `y` | Copy using Vim semantics; keep `Ctrl+Alt+S` as the explicit selection-copy shortcut. |
| `Ctrl+Q` | Quit using the existing coordinated shutdown path, after flushing drafts. |
| New Task | Save the current draft and open a separate new-task draft. |

6. On the main screen, `Ctrl+C` must not copy text or quit, even when output is selected. With no active run, it leaves the draft intact and reports that nothing is running. Modal dialogs retain their own cancel/close behavior without accidentally interrupting a background task.
7. Show a brief `Stopping` state. The recovered prompt may be edited immediately, but a new run cannot start until the old worker and its subprocesses have acknowledged the stop.

Completion check: the task, turn, run, draft, and shortcut rules have one consistent meaning across Coding, Ask, and Plan.

**Step 2 — Add shared local storage settings**

1. Add a small path-resolution helper, proposed as `tui/local_storage.py`, and settings in `tui/config.py` with a paired feature/parameter file, proposed as `feature_files/daedalus-tui-prompting.md` and `parameter_files/daedalus-tui-prompting.toml`.
2. Resolve a relative `data_root` against the TUI project root associated with its configuration, following the existing configuration-loader convention. Default `data_root` to that project root. Support an explicit writable absolute root for packaged installations.
3. Create `prompts/` and `errors/` when needed. Inject these paths into stores and coordinators instead of deriving paths separately in each module.
4. Include tunable defaults for draft autosave delay (300 ms), task-title length (60 characters), viewer visibility and minimum widths, and error rotation limits. Preserve the existing debug log's initial 2 MB / three-backup policy.
5. Add `/prompts/` and `/errors/` to the TUI project's `.gitignore`. Exclude these generated directories from project discovery even when discovery includes all immediate child folders.
6. Include a project key in filenames or subdirectories: a readable project basename plus a short digest of its resolved path. Projects with the same basename must not share storage accidentally.
7. If storage is unavailable, keep the editor usable and show the exact failed path. Do not silently redirect the user's files to a different repository or claim an unsaved prompt is saved.

Proposed on-disk layout:

```text
daedalus-tui/
  prompts/
    <project-key>/
      drafts/
        <draft-id>.json             # New-task draft, exact text and editor state
      <task-id>/
        draft.json                  # Editable follow-up or recovered prompt
        turn-0001.md                # Exact first user submission
        turn-0002.md                # Exact next user submission
  errors/
    daedalus.log                    # Rotating runtime/error diagnostics
    faults.log                      # Separate fault-handler and stack-dump output
    <project-key>/
      <task-id>/
        turn-0002-run-0001.log       # Diagnostics for a particular attempt
```

Keep `.daedalus-memory.json` in its existing launch-root location during this change. It remains the task/conversation index; the new prompt folder supplies exact text archives and draft recovery. Link each indexed turn to its archived prompt path.

Completion check: running against two projects, or changing the working directory, still writes to the configured TUI storage root without filename collisions.

**Step 3 — Extend task persistence with turns and stable names**

1. Extend `TaskRecord` in `tui/task_coordinator.py` with a persisted `title`, explicit ordered turns, an active turn/run identifier, and references to draft/archive files. Keep the logical task ID independent of any individual worktree name.
2. Give each turn an ID, sequence number, exact user text, submission timestamp, optional `revises_turn_id`, and its provider/model/reasoning/mode/topic/operating-branch snapshot. Give each run an attempt ID, lifecycle timestamps, status, assistant messages, diagnostics reference, token usage when available, and worktree context when present.
3. Tag streamed messages and callbacks with their task, turn, and run IDs. A late callback from an interrupted run must never append to the new run's response or change the new run's state.
4. Extend `TaskMemoryStore.record_task()` and restore logic to round-trip the new fields. Use the existing `logical_task_id` and `submission_sequence` persistence arguments explicitly. Introduce a version marker for the new task representation.
5. Store a task under a stable project-qualified logical key. Migrate its existing worktree-keyed entry once, preserving navigation settings and other tasks. New worktrees for later turns must not create duplicate inbox records or remove another project's entry.
6. Load legacy snapshots with no title or turns. Treat the original prompt as the first user turn and preserve legacy outputs, errors, and `prompt_history`. Retain older generated Plan follow-ups as legacy context rather than falsely labelling them verbatim user submissions. Leave unknown historical timestamps unknown.
7. Generate a title locally from the first meaningful line/sentence: remove leading Markdown decoration, collapse whitespace, and shorten at a word boundary to the configured limit. Fall back to `Task <short-id>` for content that produces no readable name. For example, `# Fix login validation\n...` becomes `Fix login validation`.
8. Persist the title once and show it in the inbox and task header. Follow-ups must not silently rename the task. Store filesystem paths using IDs, not titles; identical names remain distinct tasks. Keep the existing fixed-width inbox ellipsis behavior and provide the complete title in task details.
9. Add an All Tasks/history filter so completed and interrupted conversations remain reopenable after a restart; the current default hides older completed tasks.

Completion check: legacy history opens, a task keeps its name after restarting, and two turns plus multiple attempts still produce one logical task.

**Step 4 — Save drafts and submitted prompts automatically**

1. Implement a focused prompt store, proposed as `tui/prompt_store.py`, using UTF-8 and atomic temporary-file replacement. Reuse the existing memory store's locking and safe-write approach where appropriate.
2. Save draft text, task/project identity, cursor location, revision, and update timestamp after a short typing debounce. Flush immediately before Send, Cancel, task/project switches, New Task, and normal shutdown. Sudden process termination may lose only the most recent unflushed debounce interval.
3. Use a single ordered writer or revision checks so a delayed autosave cannot replace a newer draft. Scope drafts by project and logical task; retain a separate new-task draft.
4. On Send, validate emptiness with `text.strip()` but archive the original text unchanged, including indentation, blank lines, and trailing newlines. Do not store the system/profile wrapper in the user prompt file.
5. Allocate the turn ID, write the immutable `turn-NNNN.md`, and persist its queued metadata before dispatching an agent. Clear or transition the composer only after durable submission succeeds. A failed write leaves the draft visible, reports the failure, and does not launch an unrecorded run.
6. Make repeated Send events idempotent for the same draft revision while submission is pending. Reuse that pending turn ID when recovering a partial save instead of creating duplicate turns or files.
7. Define interrupted-write recovery: reconcile archived submissions and the task index using turn IDs; never automatically execute an orphaned/pending archive after restart. Offer it as a recoverable draft. Missing archive files can be regenerated from indexed exact turn text; corrupt files are preserved for inspection.
8. After a successful submission, start a blank follow-up draft while retaining the immutable submitted prompt in the conversation. Programmatic view refreshes must not trigger draft deletion or overwrite text being typed.
9. Restore the latest saved draft on restart. Provide prompt history selection so an earlier user prompt can be loaded into the composer without changing its original saved file.

Completion check: multiline prompts survive submission, cancellation, project switching, and restart, with exact text available under `prompts/`.

**Step 5 — Finish and verify Vim cut, copy, and paste**

1. Extend the existing `DaedalusVimTextArea`; do not replace it or build a second editor. First inspect the installed `vimkeys_input` implementation and confirm which commands already work before adding overrides.
2. Use this practical command set as the acceptance contract:

| Editing action | Required shortcuts |
| --- | --- |
| Change modes | `Esc`, `i`, `a`, `I`, `A`, `o`, `O` |
| Move | `h/j/k/l`, `w/b/e`, `0/$`, `gg/G` |
| Select | `v` for characters; `V` for whole lines |
| Cut | `x`, `dd`, `dw`, `d$`; visual `d` or `x` |
| Change selected text | Visual `c` cuts and enters Insert mode |
| Copy | `yy`, `yw`, `y$`; visual `y` |
| Paste | `p` after the cursor/line; `P` before it |
| Undo/redo | `u`, `Ctrl+R` while the prompt editor owns focus |
| Repeat common operations | Counts for the supported motions/operators, such as `3j`, `2dd`, and `2yy` |

3. Track whether the register contains characters or whole lines. Preserve Vim placement for `dd`/`yy` followed by `p`/`P`, including the last line without a newline.
4. Ensure every successful cut and yank updates the register and mirrors its contents through `copy_to_clipboard()`. Do not depend solely on the register text changing: yanking identical text twice must still refresh an externally changed clipboard.
5. Keep `p`/`P` using the Vim register first and the system clipboard when the register is empty. Provide explicit system-register commands `"+y`, `"+p`, and `"+P` so newly copied external text remains accessible after earlier Vim yanks.
6. If native clipboard access fails, keep the local Vim register and editing functional. Display a concise clipboard status rather than losing the cut text.
7. Resolve `Ctrl+R` deliberately: focused editable prompt means Vim redo; Resume remains available through its button and the app binding outside the editor. Route `Ctrl+C` to the main-screen interrupt action before dependency bindings can consume it.
8. Ensure read-only history/output supports selection and copying but cannot be changed by `d`, `c`, `p`, or undo. Recovered drafts enter Insert mode, focus the editor, and place the cursor at the end for adding text.
9. Update the keyboard-help dialog with exact commands and clipboard behavior. Use a compact Insert/Normal/Visual indicator in the composer or status area so the current mode is visible.

Completion check: a user can cut a line, paste it elsewhere, undo/redo, copy to another app, paste new external clipboard contents, and edit a restored prompt without losing text.

**Step 6 — Make interruption preserve progress and return the prompt**

1. Introduce one shared interruption action for `Ctrl+C`, Cancel, and the `Ctrl+X` alias. Capture the selected task and active run identity before any asynchronous stop request.
2. Save the current draft first. If a user already typed a different follow-up, preserve it as a recoverable draft before restoring the interrupted prompt; provide a clear way to restore that saved follow-up afterward.
3. Restore the active turn's exact user text, not `record.prompt` unconditionally and not a generated provider/Plan prompt. Associate the draft with that task and `revises_turn_id` so sending the edited text creates the next turn.
4. Reuse the preservation semantics of Pause or add an explicit non-destructive interrupt signal in `AgentControl`. Remove the normal Cancel UI route to `remove_cancelled()`. An interrupted run is recorded as `interrupted`, while its task remains continuable; it is not an error simply because the user stopped it.
5. For queued work, cancel the pending future and mark it interrupted without creating a worktree. For running agents, stop the subprocess group, wait for its exit, and preserve uncommitted files, branch identity, and worktree context.
6. Handle verification, waiting-for-integration, resolver activity, Plan questions, and clarification workers explicitly. Make integration-gate waiting observe interruption so a stopped queued task does not remain stuck behind another integration.
7. Check for interruption before promotion. If an atomic Git operation or existing external operation is already in progress, let it reach a known state and report the actual result. Do not claim committed/promoted work was undone or delete partially completed work.
8. Make repeated `Ctrl+C` presses idempotent. A completion racing with interruption must produce one truthful final run state. Keep the restored draft available even if the task finished before the stop took effect.
9. Stop UI render paths such as `_render_selected_task()` from reloading the immutable original prompt over an editable draft. Restore editor content only on deliberate draft/task transitions; background output must not steal focus or reset the cursor.
10. Keep existing Pause/Resume compatible. An unchanged Retry can resume the failed stage; a newly edited prompt must restart the appropriate agent/verification path rather than reuse an integration-only shortcut.

Completion check: interrupt any supported task state, extend the returned prompt, and continue without deleting progress, duplicating workers, or changing an unrelated task.

**Step 7 — Execute additional prompts within the same task**

1. Add a coordinator entry point for a follow-up turn. Validate that the logical task exists, its project is available, and no prior run is still active. New Task continues to use the separate task-creation path.
2. Build provider-neutral conversation context from ordered user turns and their assistant responses. Delimit historical text from the latest instruction and reload the current target-project profile/topic through the existing orchestration path.
3. Include the original goal, latest submitted instruction, and relevant recent responses. Bound transmitted history with a configurable context budget while retaining complete local history. Clearly identify omitted older context instead of silently treating it as absent.
4. Reuse a valid preserved worktree for interrupted/failed work. Inspect its existing changes before continuing. Reset stale `retry_prompt`, stop flags, and `resume_from` when the user submits new instructions that invalidate the previous execution stage.
5. For a completed coding or Ask run whose worktree was cleaned up, create a fresh worktree from the task's recorded operating branch. Give it a unique execution suffix while keeping the same logical task ID and title. Clear stale in-memory contexts; never pass a deleted worktree to the runner.
6. Preserve Plan question parsing, custom answers, clarifications, and confirmation. Record generated Plan prompts separately from actual user submissions. A Plan-to-Coding transition should retain the same visible conversation/title while recording a new execution context and the mode change; adapt the current separate coding-task promotion accordingly.
7. Keep provider/model/reasoning/topic/branch choices explicit. Follow-ups default to the task's existing configuration; any supported change is recorded on the next turn. An existing unmerged worktree cannot silently switch its base branch.
8. Render user and assistant turns in order with clear separators and per-run status. A provider's streaming deltas must append only to the current run's response, including Cursor's current last-message accumulation behavior.
9. Persist enough state to resume safely after restart. Previously active runs become interrupted/recoverable, with no automatic agent launch. Reopening a historical task allows another prompt immediately once its context has been validated.
10. Update task/prompt statistics so one conversation remains one task, each submitted user turn counts as a prompt, and retries are attempts rather than extra prompts. Preserve recorded totals for legacy data and count each run's reported usage once.

Completion check: send three prompts, interrupt and revise one of them, finish the task, restart the TUI, and send a fourth prompt from the same named task.

**Step 8 — Add the optional viewer in the right third**

1. Add an Output Viewer toggle to the output toolbar, available in wide and compact layouts. Default it off to preserve the existing layout; remember the user's choice in local UI preferences.
2. Add a viewer widget, proposed as `tui/output_viewer.py`, and restructure `tui/app.py` / `tui/app.tcss` so the viewer is a sibling of the existing main workspace. When visible on a wide terminal, reserve one third of the usable screen workspace for it; the task list and main composer/output share the other two thirds.
3. Measure against the full usable workspace, including the task sidebar—not just the remaining central panel. At 180 usable columns, target about 60 viewer columns and 120 main-workspace columns, allowing border rounding.
4. Keep task controls, prompt editing, and plan-answer controls in the main area. The viewer is read-only and displays the selected task's output alongside them.
5. Offer a source selector for Latest response, an earlier response, and the current plan text where present. Default to Latest response and show its task/turn identity. Changing the selected task updates the source without mixing projects.
6. Preserve scroll position when the user is reading older content; follow live output only when already at the bottom or when the user explicitly returns to Latest.
7. Add a minimum usable width calculation for both sides. On narrow screens, expose the same viewer as a full-width alternate view with a Back control; restore the one-third panel when enough width returns. Toggling or resizing must preserve the draft and viewer state.

Wide-screen layout:

```text
|             Main workspace: about 2/3             | Viewer: about 1/3 |
| Task inbox | Task controls and settings           | Output source     |
|            | Transcript or Plan review            | Rendered / Raw    |
|            |                                      | Markdown content  |
|            | Vim prompt composer and Send/Cancel  | Independent scroll|
```

Completion check: the viewer occupies the right third at a suitable terminal size, hides cleanly, and stays usable after narrowing and widening the window.

**Step 9 — Render Markdown in the viewer**

1. Treat “Markdown compiler” as an in-app Markdown renderer. Evaluate the Markdown widgets available in the installed Textual version and use the existing dependency stack where it meets the requirements. Confirm actual APIs and supported extensions during implementation before adding another parser.
2. Render headings, paragraphs, emphasis, lists, task lists where supported, block quotes, links, fenced code blocks, and tables. Wrap prose; provide sensible horizontal scrolling or overflow handling for code and tables.
3. Keep the original Markdown as the canonical source. Feed the renderer from stored response text, never from the transcript's already-wrapped display lines, which can contain inserted hyphenation.
4. Add Rendered and Raw tabs/modes. Raw uses a selectable text surface and preserves exact source text for copying. Keep diagnostics available through the existing error view regardless of whether the Markdown viewer is open.
5. Parse structured Plan output with the existing plan parser first, then render `plan_text`; keep answer controls and protocol JSON out of the Markdown content.
6. Debounce live rendering so every token does not rebuild the whole panel. Show partial text safely while code fences or tables are incomplete, and flush the final response when the run ends. Discard outdated render results after task switches or newer updates.
7. On rendering failure, retain the raw response, offer the Raw view, and log one useful diagnostic. Do not crash the TUI or feed arbitrary Markdown into Rich markup-based labels.
8. Treat output as display data: do not execute code blocks, HTML, or embedded commands, and do not fetch remote images automatically. Link opening requires an explicit user action. Generated local file browsing can be added separately; response and plan rendering complete this requirement.
9. Route Vim output navigation to whichever surface owns focus. Ensure copying rendered content is predictable; use Raw mode for exact Markdown and fenced-code copying if the installed renderer cannot preserve native selection reliably.

Completion check: a long Markdown response with headings, a list, a code fence, a table, and literal brackets renders readably, stays responsive while streaming, and remains available as exact raw text.

**Step 10 — Consolidate local error logging**

1. Extend `tui/debug_log.py` rather than creating an unrelated logger. Configure the main rotating log under the shared `errors/` directory as early as possible, covering initialization failures before widget mounting.
2. Include UTC timestamp, severity, project key, logical task ID, turn/run ID, execution phase, and provider when known. Include a traceback for exceptions and exit status for subprocess failures.
3. Capture agent startup/auth/connectivity failures, worker exceptions, verification output, integration/resolver failures, persistence failures, Markdown rendering errors, Textual/asyncio exceptions, and shutdown problems. Reuse current event boundaries instead of logging the same failure at every UI repaint.
4. Append per-run diagnostic detail before the UI's `truncate_diagnostic()` step. Keep the compact on-screen error summary, but make complete error events available on disk within configured size/rotation limits.
5. Keep fault-handler output in its own file. The current handler retains an open file descriptor, so sharing a rotating file can leave stack dumps writing to an old rotated file. Reopen or rotate the fault file only when safe, such as startup, and record both paths in diagnostics.
6. Wire the Errors view to the selected run and show its local log path. Preserve Vim selection/copy support. New follow-ups must not erase previous attempts' diagnostics.
7. Treat requested interruptions as normal lifecycle events. A failed process stop or cleanup operation is an error and must remain visible.
8. Do not log credentials, full subprocess environments, or full prompts as generic debug messages. Prompts have their dedicated archive. Scrub known credential patterns from diagnostic output without removing useful failure information.
9. If logging cannot write because of permissions or a full disk, report that failure once through the UI/stderr and retain available in-memory diagnostics. Avoid recursive attempts to log the logger's own failure or false messages claiming the log exists.
10. Retain existing legacy `.daedalus-debug.log` files. Change the configured default destination and update all error-path references; old files can remain available for investigation.

Completion check: an agent error, verification failure, and UI rendering exception each leave a useful local record under `errors/`, associated with the correct task/run.

**Step 11 — Validate behavior and compatibility**

1. Add focused tests while implementing each feature, then run the relevant combined suite. Use temporary directories and fake runners/processes for automated tests so validation does not launch paid agents or modify real projects.
2. Extend `tests/test_app.py` for key routing, restored prompts, draft protection during streaming, named task selection, follow-up submission, history reopening, viewer toggles, Plan controls, and responsive layout.
3. Add focused editor tests, proposed as `tests/test_vim_text_area.py`, covering multiline cuts, character/line registers, visual operations, repeated identical yanks, external clipboard freshness, failed clipboard access, Unicode text, undo/redo, and read-only protection.
4. Add storage tests, proposed as `tests/test_prompt_store.py`, and extend `tests/test_memory.py` / `tests/test_config.py` for exact text, atomic writes, autosave ordering, partial submissions, corrupted/legacy history, duplicate project names, unwritable paths, and restart recovery.
5. Extend `tests/test_task_coordinator.py`, `tests/test_orchestrator.py`, and `tests/test_agent_runner.py` for queued/running interruption, subprocess exit, integration-gate cancellation, safe promotion boundaries, idempotent stops, late callbacks, follow-ups after cleanup, and Plan-to-Coding continuity. Update existing tests that explicitly expect Cancel to delete worktrees.
6. Extend `tests/test_prompts.py` / `tests/test_plan.py` for ordered conversation context, the latest revised instruction, preserved Plan protocol, and bounded history. Extend `tests/test_token_usage.py` for the distinction between tasks, prompts, and attempts.
7. Add viewer/logger tests, proposed as `tests/test_output_viewer.py` and `tests/test_debug_log.py`, for incomplete Markdown, raw fallback, source switching during rendering, scroll retention, full diagnostic capture, file rotation, early failures, redaction, and logging failure fallback.
8. Run the targeted tests first, then the full existing suite once they pass. Review suite setup because `tests/conftest.py` can install a missing dependency; prepare the required environment before validation rather than relying on unexpected network access.
9. Complete a manual smoke test in a disposable project: create a named task, cut/paste a multiline prompt, send it, type a different follow-up, cancel, verify both drafts survived, edit the restored prompt, send again, inspect Markdown in the right third, induce a controlled error, and restart to reopen the same conversation.
10. Repeat the UI checks at wide, medium, narrow, and short terminal sizes, with two tasks running and a project switch. Verify native clipboard integration in the user's actual terminal; record any terminal-specific key limitations.

Completion check: the four requested features work together, existing provider/Plan flows remain functional, and no test relies only on the implementation's internal structure.

**Step 12 — Document and hand off the implementation**

1. Update the owning feature files using the repository's required Summary, Key Points, Relevant Files, Dev Mode, and State Log schema. Add paired parameter files for newly owned tunable settings; avoid duplicating orchestration internals in UI feature descriptions.
2. Update `README.md` and the keyboard-help dialog with Cancel's preservation behavior, the new `Ctrl+C` meaning, Vim clipboard commands, follow-up turns, automatic naming, history access, viewer behavior, and the exact configured prompt/error locations.
3. Document storage recovery, legacy history compatibility, log retention, and how to relocate the storage root when installing outside a writable source checkout.
4. During implementation, have the implementing orchestration workflow run `graphify update .` after code changes and handle its normal graph-refresh lifecycle. This planning-only change does not modify source code or require a graph refresh.
5. Review the final diff for generated prompt/log files, unrelated edits, and accidental changes to target-project behavior. Task agents remain file editors; orchestration continues to own staging, commits, merges, worktree cleanup, and graph refreshes.

**Recommended implementation order**

Complete Steps 1–4 first so task identity and prompt preservation are available before changing cancellation. Complete Step 5 for editor behavior, then Steps 6–7 for interruption and multi-turn execution. Build Steps 8–9 on the resulting conversation model. Add Step 10's logging foundation early enough to diagnose development failures, then finish its per-run integration. Apply Step 11 throughout and finish with Step 12.

**Final acceptance checklist**

- [ ] The input box supports the specified Vim cut/copy/paste commands, useful undo/redo, and system clipboard access.
- [ ] Output Viewer can be enabled, renders Markdown, and occupies the right third of a sufficiently wide screen.
- [ ] Exact submitted prompts and recoverable drafts are saved automatically under the configured `daedalus-tui/prompts/` folder.
- [ ] `Ctrl+C` and Cancel restore the interrupted user prompt in an editable composer while preserving task progress and any separately typed draft.
- [ ] A task accepts multiple prompts, including a follow-up after completion or restart, under the same logical identity.
- [ ] Tasks receive stable readable names automatically, and older tasks can be reopened.
- [ ] Errors are logged locally under the configured `daedalus-tui/errors/` folder with task/run context.
- [ ] Cancellation races, storage failures, resizing, project switches, and legacy memory recovery have been verified.
- [ ] Feature documentation, parameters, help text, and the code graph reflect the implemented behavior.
