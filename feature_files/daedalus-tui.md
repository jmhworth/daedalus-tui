# Daedalus Textual TUI

## Summary
The standalone Daedalus TUI is an installable Textual application that runs from a target repository and submits independent local, orchestrated coding tasks concurrently.

## Key Points
- **Independent project boundary**: The exported `tui` project owns its UI, provider execution, configuration, tests, and local orchestration modules without importing `local-daemon`.
- **Provider controls**: Codex exposes GPT-6 Astra, Luna, Terra, and Sol with
  light, medium, high, extra-high, and max reasoning; Cursor CLI is a
  provider-only choice with model and reasoning disabled. The settings bar also
  exposes a per-project
  Branch Select for the operating branch used by new task worktrees, with an
  operator Push control that publishes that branch to `origin`.
- **Responsive layouts**: Terminal resize events switch narrow screens to a
  vertical workspace with a compact full-width task inbox and stacked project
  selector. The wide task and settings bars are measured after layout, so the
  compact category/value picker appears when a control is actually clipped or
  when a settings selector falls below its parameterized readable width; a
  conservative parameterized safety guard covers very narrow or not-yet-laid-
  out terminals. The picker keeps provider, model, reasoning, mode, topic, and
  operating-branch choices available, while short terminals reduce prompt and
  surrounding vertical chrome.
- **Optional Topics**: A Topic Select lists `(None)` plus `topic_files/*.md`
  stems so related tasks can share goal/status/state-log memory without
  requiring a topic on every submission.
- **Local execution**: Prompts run in isolated Git worktrees without daemon RPC or a local database; orchestration may push pending Supabase migrations for target projects when migration files change, while agents still do not own DB push or Git remotes. An explicit operator Push button may publish the selected operating branch.
- **Concurrent task inbox**: Up to four independent prompts can run at once, each with its own configuration snapshot, branch, worktree, status, and transcript; the left-side inbox promotes tasks with unseen updates.
- **Plan-first task route**: Plan tasks remain selectable through `planning` and `questioning` states, support follow-up planning passes, and can promote their preserved context into the normal coding, verification, and integration route.
- **Plan custom answers**: Plan review renders a software-owned custom-answer choice alongside the agent's reasonable options and collects free text only when that choice is selected; the agent protocol remains unchanged.
- **Plan question clarifications**: Each plan question exposes a `?` control on the same row as its answer dropdown (dropdown narrowed, button at the trailing end) that opens a side-channel ask about that question alone; answers stay off the plan follow-up transcript and are browsable from a per-question dropdown on the review page.
- **Literal plan review text**: `#plan-display` and dynamic plan-question Static widgets render agent-generated text with `markup=False` so brackets and scientific notation cannot trigger Textual/Rich markup parsing. Plan answer Select option labels are wrapped as literal Rich `Text` for the same reason.
- **Plan completion crash guard**: Deferred `PlanAnswerSelect` initialization catches illegal leftover option ids and half-removed overlays so a follow-up plan round cannot fatal-exit the TUI; fatal Textual exceptions also print a stderr pointer to the launch-root debug log.
- **Plan recommended defaults**: Plan and follow-up prompts require every multiple-choice question to mark exactly one option with ` (Recommended)` so a safe default is always visible when the user does not care which answer to pick.
- **Filtered logs and copying**: The output pane uses Textual's selectable `Log` widget for completed assistant messages; Vim yank commands copy selected transcript or diagnostic text to the system clipboard.
- **Full-size output toggle**: Agent transcript and task diagnostics share one full-height output panel; a toggle shows either log at the same readable size while preserving selection and copying.
- **Readable streamed output**: Assistant messages are separated by a blank line, transcript lines reflow at word boundaries with hyphenation only for overlong words, and the output pane keeps a small width buffer so long responses remain visible.
- **Incremental Vim input**: The prompt uses a modal VimTextArea with a practical command subset; additional Vim commands can be added as they become useful instead of implementing the entire Vim language up front.
- **Project selection**: Launching from a root directory discovers only immediate child directories with `feature_files` folders; nested descendants are excluded, and the launch root is used only as a fallback when no eligible child exists. The task toolbar selects the project for new submissions, editable prompt drafts survive project switches, and focusing an inbox row synchronizes the active project without mixing transcripts or worktrees. Each project's remembered operating branch is restored independently when focus returns.
- **Project initialization**: `CapsLock+2` opens New Project, which materializes bundled Daedalus templates (including a scaffold `.daedalus` TOML) under the launch root, runs Graphify/Git setup, optionally creates a private GitHub repo, optionally registers a personal shared-Supabase schema (files only), then refreshes discovery onto the new project.
- **Actionable task history**: The task inbox keeps every failed task, active or paused work, and all tasks from the current TUI session while hiding older completed, blocked, and cancelled tasks.
- **Stable task inbox layout**: The task inbox uses fixed, parameterized marker/project/task/status widths and visible ellipses so background update markers cannot resize or horizontally scroll the sidebar.
- **Retryable failures**: Failed agent tasks expose their diagnostics and a Retry action so transient connectivity or service failures can be recovered in place.
- **Prompt mode toggle**: On the main prompting screen, `Tab` toggles the new-task mode between Coding and Plan; the existing Ask mode remains available from the selector.
- **Submission focus**: Every newly submitted task becomes the selected task immediately, regardless of mode, so its status, transcript, plan review, and task context are visible while it runs.
- **Keyboard-first actions**: Low-frequency actions stay out of the project toolbar and are available through `CapsLock+2` (new project), `CapsLock+3` (create topic), `CapsLock+4` (activate personal Supabase), and `Ctrl+T` (new task); `Ctrl+U` opens coding statistics, while `Ctrl+K` opens the shortcut reference and is the only global binding shown in the bottom footer.
- **Scrollable vertical workspace**: Compact-width terminals use a scrollable vertical screen with a three-column settings grid above the output and composer, giving the transcript and prompt larger starting heights while retaining independent scrolling inside each widget.

## Relevant Files
- `tui/app.py`: Textual layout, selectors, task list, transcript replay, and task controls.
- `tui/app.tcss`: Shared full-height output-panel layout and readable transcript/diagnostic styling.
- `tui/config.py`: Read-only provider and responsive-layout configuration models and loaders.
- `tui/git_worktree.py`: Local Git helpers including operating-branch push for the operator Push control.
- `tui/prompts.py`: Task, repair, and resolver prompt wrappers, including plan-mode recommended-option instructions.
- `tui/topics.py`: Optional topic discovery, load, and prompt embedding.
- `tui/plan.py`: Agent plan parsing plus UI-owned custom-answer encoding, clarification prompts, and prompt formatting.
- `tui/vim_text_area.py`: Incremental modal Vim prompt adapter and system clipboard integration.
- `tui/agent_runner.py`: Independent Codex and Cursor subprocess adapter.
- `tui/task_coordinator.py`: Concurrent task executor, serialized integration gate, and plan-question clarification workers.
- `parameter_files/daedalus-tui.toml`: Provider, model, reasoning, and default UI settings.
- `tests/test_config.py`, `tests/test_app.py`: Configuration validation and responsive layout/compact-selection coverage.
- `feature_files/daedalus-tui-orchestration.md`: Local orchestration ownership boundary.
- `feature_files/daedalus-tui-topics.md`: Optional topic umbrellas and shared State Log memory.
- `feature_files/daedalus-tui-project-initialization.md`: Launch-root project scaffolding.
- `tests/test_plan.py`, `tests/test_app.py`, `tests/test_task_coordinator.py`: Coverage for custom-answer rendering, validation, and follow-up handoff.

## Dev Mode
HACKING

## State Log
- 2026-09-14: Relabeled Ctrl+Shift+S as activate personal Supabase after the scaffold+Activate redesign.
- 2026-09-13: Removed the per-project task-count suffix from the Project Select labels so options show only the project name.
- 2026-09-13: Adjusted the default readable selector floor to 13 cells to
  account for Textual's fractional-width rounding, allowing the wide settings
  row to restore at 180 columns while retaining compact mode at 125 columns.
- 2026-09-13: Lowered the default readable selector floor to 14 cells so
  the measured wide settings bar restores at 180 columns while the 125-column
  layout still routes provider and model controls through the compact picker.
- 2026-09-13: Fixed the measured settings-overflow path to pass its compact
  decision into the responsive layout, so a 125-column terminal now keeps the
  provider, model, and reasoning controls available through the compact picker.
- 2026-09-13: Added a measured minimum width for wide settings selectors so
  resize events switch to the compact picker before fractional controls hide
  their labels and dropdown affordances.
- 2026-09-13: Made compact mode respond to measured task/settings control bounds after layout, with a conservative width guard and deferred re-measurement when restoring the wide layout.
- 2026-09-13: Added resize-aware compact and short-height layouts with a two-level settings picker that preserves provider cascades, task metadata snapshots, and project topic/branch persistence on narrow terminals.
- 2026-09-13: Routed every new task submission through the shared task-focus path so Coding, Ask, Plan, and topic-created tasks select their running task immediately.
- 2026-09-05: Fixed task-inbox columns and bounded their displayed values so update markers do not change the sidebar's horizontal layout or hide the project, task, status, or exclamation mark until hover.
- 2026-09-05: Hardened deferred plan-answer Select init and Select change handlers so illegal leftover option ids after plan completion cannot fatal-exit the TUI, and fatal errors now print a stderr pointer to the debug log.
- 2026-09-05: Fixed the `Tab` mode toggle to recognize Textual's one-entry main screen stack while leaving modal screens untouched.
- 2026-09-05: Routed `Tab` from the focused prompt editor to the main-screen mode action so Vim input handling cannot consume the Coding/Plan toggle.
- 2026-09-05: Added a main-screen `Tab` shortcut that toggles the prompt mode between Coding and Plan and documents the shortcut in the keyboard help.
- 2026-08-25: Clarified that orchestration may push pending Supabase migrations for target projects while agents remain file-only for DB push and Git remotes.
- 2026-08-25: Guarded Push button refresh so Select.Changed during mount or teardown cannot query a missing #push-branch-button.
- 2026-08-25: Added a settings-bar Push control that publishes the Branch Select operating branch to origin without changing agent or orchestration auto-push boundaries.
- 2026-08-24: Preserved a final complete word at the reserved transcript edge buffer while retaining hyphenation for overlong words.
- 2026-08-24: Tightened transcript wrapping to the content region, hyphenated only overlong words, and set the output surface to a narrower border-box with horizontal overflow disabled.
- 2026-08-24: Repaired transcript boundary fitting and reserved a one-cell right-edge buffer so resized output reflows without clipping the final glyph.
- 2026-08-24: Wrapped transcript messages at word boundaries, hyphenated words that exceed the available cell width, and narrowed the output pane through the parameterized UI width setting.
- 2026-08-24: Kept both output logs hidden while the plan review replaces the output panel, preserving the toggle state for normal task views.
- 2026-08-24: Added a full-size toggle between agent transcript and task diagnostics so long errors can be read and copied without competing with the console for vertical space.
- 2026-08-24: Added optional Topics with a settings-bar Select and prompt embeds for tagged tasks.
- 2026-08-24: Moved the plan-question `?` clarification button onto the answer-select row so it shares the dropdown's y-level without a header gap.
- 2026-08-24: New Project scaffolding now includes a `.daedalus` TOML worktree config template alongside the other initializer assets.
- 2026-08-24: Added per-question plan clarifications with a `?` button, side-channel ask runs, and an on-page dropdown for answers that stay separate from plan follow-up.
- 2026-08-23: Added a settings-bar Branch Select that remembers each project's operating branch in launch-root memory and applies it to new task worktrees only.
- 2026-08-14: Moved the TUI feature ownership into the standalone project boundary and expanded provider/model/reasoning controls for local orchestration.
- 2026-08-14: Added concurrent task snapshots, assistant-message filtering, selectable transcript replay, and copy-all output for independent worktrees.
- 2026-08-14: Made failed diagnostics selectable and copyable, added Cursor failure guidance, and hardened successful worktree cleanup.
- 2026-08-14: Added ignored local Cursor credential loading and a native clipboard fallback for terminals without OSC 52 support.
- 2026-08-14: Added Coding, Ask, and Plan mode controls plus per-task pause, resume, and cancellation actions.
- 2026-08-14: Added optional per-resume notes and a continuation prompt that directs agents to inspect existing work before making updates.
- 2026-08-14: Routed Textual selection copies through the native clipboard fallback and added an explicit partial-output copy action.
- 2026-08-14: Clarified that task agents edit files only while orchestration owns Git operations and graph refreshes.
- 2026-08-14: Enabled global Textual selection copying for arbitrary UI text while preserving native TextArea selection and terminal modifier guidance.
- 2026-08-14: Added non-modal Vim-style output navigation and system clipboard y/p shortcuts without intercepting prompt editor typing.
- 2026-08-14: Added a modal VimTextArea prompt with multiline Insert mode, Normal/Visual commands, system clipboard yank/paste, and an intentionally incremental command subset for future additions.
- 2026-08-14: Removed Vim status and shortcut hints from the rendered interface and added Shift+V whole-line visual selection to the prompt editor.
- 2026-08-14: Added Daedalus project discovery from the launch root and a sidebar that preserves independent task coordinators for each supported project.
- 2026-08-16: Removed copy buttons and dedicated full-output/error copy actions in favor of Vim yank commands.
- 2026-08-16: Added standalone `AGENTS.md` and task-mode profiles so the TUI retains its operating instructions when moved into its own repository.
- 2026-08-16: Preserved submitted prompts in an immutable task view and added an explicit New Task action to unlock a blank prompt editor.
- 2026-08-16: Switched the output pane from RichLog to Log so transcript text supports click-drag selection and yank without editing.
- 2026-08-16: Kept task selection user-controlled during background events and streamed Cursor assistant deltas into the live transcript.
- 2026-08-17: Matched selectable output highlighting to the prompt selection colors so selected transcript characters remain readable.
- 2026-08-17: Added prompt `yy` coverage, reliable `e` word-end progression, Escape selection clearing, and a steady underline-style insert cursor.
- 2026-08-17: Added quieter progress-message text, a brighter final assistant summary, and faded styling for immutable submitted prompts.
- 2026-08-17: Switched the insert caret to a thin white bar, used an underline while yank is pending, and mapped `$` to line-end in command mode.
- 2026-08-17: Resolved the final transcript color through Textual before passing it to Rich, avoiding invalid `auto` CSS colors during pointer rendering.
- 2026-08-17: Kept the insert caret between characters so rendering a middle-of-line prompt does not hide the text to its right.
- 2026-08-17: Fixed insert caret rendering by splitting the full Textual strip at the cursor position and drawing a visible one-cell vertical bar.
- 2026-08-17: Used a left-aligned thin block for the insert caret so it sits on the left edge of the character cell at the insertion point.
- 2026-08-17: Kept Plan tasks selectable through a planning/questioning loop with follow-up controls, structured plan/questions review, and an explicit transition into coding.
- 2026-08-17: Made asynchronous plan-question rendering generation-safe and non-fatal so streamed completion events cannot close the TUI before the review controls appear.
- 2026-08-17: Suppressed Textual's inherited Select mount handler for dynamic plan answers, preventing a race where SelectCurrent lacked its internal `#label` node during initialization.
- 2026-08-17: Added visible retry controls for failed agent requests and preserved the last request prompt for connectivity recovery.
- 2026-08-17: Included the visible AI transcript from failed attempts in retry context while relying on the existing worktree diff for file-change state.
- 2026-08-17: Deferred dynamic plan Select initialization until after Textual's nested SelectCurrent label is mounted, preventing a lifecycle race from terminating the TUI.
- 2026-08-17: Detached task callbacks before coordinator shutdown, waited for executor workers to finish, and ignored late events after Textual closes.
- 2026-08-17: Replaced the insert caret's rendered cell instead of adding one, so middle-of-line text no longer shifts while the prompt document stays unchanged.
- 2026-08-17: Let Textual underline the real insert cursor cell with no background override so the character beneath the caret remains visible without a dark box.
- 2026-08-17: Disabled Textual's dark active-line highlight for the Vim prompt because it remained underneath the transparent cursor cell.
- 2026-08-17: Replaced project-focused sidebar navigation with a cross-project task update inbox, moved project selection into the task toolbar, and made task focus synchronize the active project context.
- 2026-08-17: Validated the toolbar project at submission time so a newly selected project receives the draft even before its queued selector event is processed.
- 2026-08-17: Limited task-update inbox promotion to completed or failed tasks and plan questions, leaving streaming progress events out of the update queue.
- 2026-08-17: Made task diagnostics use the selectable output-log surface so error text supports mouse selection, Vim yanks, and Ctrl+C copying.
- 2026-08-17: Made confirmed plan implementation a one-shot action and visibly faded the Implement button after it queues coding.
- 2026-08-20: Added a UI-owned Custom answer choice to plan questions, with conditional free-text input and encoded follow-up handoff that leaves agent-generated options unchanged.
- 2026-08-20: Filtered the task inbox to failed history, active work, and tasks from the current TUI session, while preserving visibility when an older task is resumed or retried.
- 2026-08-23: Added blank-line separation between streamed assistant messages and width-aware transcript wrapping that reflows when the terminal is resized.
- 2026-08-23: Updated final-tone verification to locate the final message after width-aware wrapping rather than assuming a fixed physical line index.
- 2026-08-23: Wrapped transcript lines to the output Log's content region so border and padding remain clear, with resize coverage for reflow.
- 2026-08-23: Reflowed cached transcript lines during rendering when a style width change does not emit a resize event.
- 2026-08-23: Used an explicit cell width immediately during transcript reflow so direct output width updates are reflected before the next layout pass.
- 2026-08-23: Accounted for border-box gutters when using an explicit output width, keeping wrapped text inside the Log content area.
- 2026-08-23: Folded transcript messages by cell width so constrained output panes visibly reflow on narrow resize changes without crossing the content boundary.
- 2026-08-23: Linked New Project initialization so launch-root scaffolding refreshes the discovered project list.
- 2026-08-23: Preserved editable prompt drafts across toolbar project switches so a mis-targeted draft can be redirected instead of erased.
- 2026-08-23: Required plan-mode questions to label exactly one option with (Recommended) via the plan and follow-up system prompts.
- 2026-08-23: Rendered agent plan and question text as literal Static content (`markup=False`) so square brackets and scientific notation cannot fail Textual markup parsing.
- 2026-09-05: Restored plan review questions from the latest persisted agent output and rendered that output as a fallback after a TUI restart leaves a task awaiting answers.
- 2026-09-05: Stopped remounting stale plan Select values after follow-up option ids change, avoiding InvalidSelectValueError crashes like illegal `'replace'`.
- 2026-09-05: Limited project discovery and selector refreshes to immediate launch-root children, using directory basenames and excluding nested project paths.
- 2026-09-05: Removed the blank option from the project selector so direct-child labels are the only displayed project choices.
- 2026-09-13: Added opt-in personal shared-Supabase schema registration from New Project and the project task bar (file scaffolding only).
- 2026-09-13: Repaired Textual 8.2 compatibility for responsive styling and compact selector cascades, including delayed event filtering and Scalar-aware resize assertions.
- 2026-09-14: Replaced low-frequency project-toolbar actions with keyboard shortcuts, moved coding statistics to `Ctrl+U`, and kept only the `Ctrl+K` shortcut-reference binding visible in the footer.
- 2026-09-14: Repaired Textual 8 binding compatibility and priority handling so global shortcuts import cleanly and remain active while the prompt editor has focus.
- 2026-09-14: Made compact-width mode a scrollable vertical workspace with a three-column settings grid and parameterized starting heights for the output transcript and prompt editor.
- 2026-09-14: Repaired the responsive-layout tests for Textual 8's Layout object API by asserting the grid layout name.
- 2026-09-14: Replaced terminal-ambiguous Ctrl+Shift letter bindings with reliable F2/F3/F4 shortcuts and covered the New Project modal path.
- 2026-09-15: Added selectable GPT-6 Astra support and mapped the new Max reasoning effort to Codex CLI's `max` value while preserving the Luna default.
- 2026-09-15: Rebound the project, topic, and personal-Supabase actions from F2/F3/F4 to the Caps Lock function layer as CapsLock+2/CapsLock+3/CapsLock+4.
- 2026-09-15: Updated the remaining personal-Supabase activation test to press CapsLock+4 after the function-key rebind.
