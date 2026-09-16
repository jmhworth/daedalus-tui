# Daedalus TUI

This directory is an independently exportable project. It contains the
Textual interface and all local agent orchestration code; it does not import
the Daedalus daemon, use a database, or communicate with Supabase.

Install it into the Python environment used from the target repository:

```bash
python3 -m pip install -e /path/to/tui
```

The standalone call-graph visualizer can inspect an arbitrary Python checkout
without adding Daedalus files first. Edit
`parameter_files/daedalus-tui-call-graph-visualization.toml` and set
`analysis_project` to the checkout directory name. `current` analyzes the
working directory; any other name resolves automatically under `projects_root`
(default `~/Projects`). For a checkout elsewhere, add an optional
`[projects."name"]` table with a `root` path and any project-specific analysis
overrides. The generic project defaults discover Python files recursively, and
a target-local call-graph parameter file takes precedence when available.

Launch it from a directory containing one or more Daedalus-supported
projects:

```bash
python3 -m tui
```

The launch directory is treated as a project workspace. The TUI discovers its
immediate child directories; nested descendants are not traversed or listed.
Folders with a `feature_files/` directory are listed first as Daedalus
projects, and plain Git checkouts are listed after them so the TUI is not
limited to projects you have already converted. The selector shows each
project's plain directory name. Set `include_all_directories = true` in the
`[projects]` table of
`parameter_files/daedalus-tui.toml` to list every child directory, or
`include_git_repositories = false` to show Daedalus projects only. If no
eligible child project exists, the launch directory remains available as a
usability fallback. Each project
has its own task coordinator, task numbering, Git worktrees, and transcripts;
switching the sidebar does not interrupt tasks running in another project.

A project that lives somewhere else — created, cloned, or moved outside the
launch root — is reachable through the project selector's trailing **Open
directory…** entry. It asks for one path (absolute, `~`-relative, or relative
to the launch root), then adds that directory to the selector and switches
onto it. Opened directories are remembered in `.daedalus-memory.json` and
return on the next launch, so the selector only
ever grows by the projects you actually open, and an opened directory that no
longer exists is dropped and forgotten at startup.

The layout adapts to terminal size. Below the configured compact-width safety
guard, or whenever a wide task/settings control is actually clipped, the task
inbox becomes a short full-width panel, the main workspace stacks vertically,
and the task toolbar's project and action controls remain available without
clipping. The wide settings row is replaced by a category and value picker
covering provider, model, reasoning, mode, topic, and operating branch. Short
terminals also use a smaller prompt and reduced vertical chrome. Tune these
defaults in the `[layout]` table of
`parameter_files/daedalus-tui.toml` (`compact_width`, `short_height`,
`compact_task_sidebar_height`, and `compact_prompt_height`).

## Providers and sign-in

Three providers are available: Codex (`codex`), Claude Code (`claude`), and
Cursor CLI (`agent`). Each provider's models and effort levels live in
`parameter_files/daedalus-tui.toml`; Claude Code has its own effort scale that
adds `max`, and Cursor is a provider-only choice with model and reasoning
disabled. Claude Code runs with `--permission-mode acceptEdits`, so it edits
files without prompting while orchestration still runs verification itself.
Because `claude --print` is non-interactive, nobody can answer a permission
prompt: any Bash command that is not pre-approved is denied. The TUI therefore
passes `--allowedTools` with `[claude] allowed_tools` from
`parameter_files/daedalus-tui.toml` (test runners, `npm run`, read-only `git`)
plus the project's discovered verification commands, so agents can run the
same checks orchestration will. Widen that list for other commands, or set
`[claude] permission_mode = "bypassPermissions"` to let it run anything; that
grants autonomy comparable to Codex but without Codex's sandbox.

By default the TUI runs agents on your **signed-in account** rather than an API
key, so work bills your plan. In this mode it removes each provider's API-key
variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`,
`CURSOR_API_KEY`) from the agent subprocess environment, and a local `.env`
cannot put them back. Sign in once from your own terminal:

```bash
claude auth login
codex login
agent login
```

The task bar's **Sign In** control reports the selected provider's status and
repeats the exact command to run. The TUI does not host the login itself,
because an interactive CLI that takes over the terminal would hide the
interface.

To go back to key-based execution, set `mode = "api-key"` in the `[auth]` table
of `parameter_files/daedalus-tui.toml`. Cursor then reads `CURSOR_API_KEY` from
the process environment or a local `.env`:

```bash
cp .env.example .env
# edit .env and set CURSOR_API_KEY=...
```

API keys never belong in a parameter file; those tables list variable names
only.

## Project backends

New Project and the task bar's **Register Backend** control scaffold a backend
into a project: **Firebase** (`firebase.json`, deny-by-default
`firestore.rules`, `firestore.indexes.json`, `storage.rules`) or a **personal
Supabase** schema. Firebase is the default for new projects; change
`default_backend` in
`parameter_files/daedalus-tui-project-initialization.toml` to pick another.

Registration writes files only. After verification passes, orchestration
deploys changed Firestore rules and indexes with
`firebase deploy --only firestore:rules,firestore:indexes --non-interactive`,
and pushes pending Supabase migrations, repairing failures with the coding
agent before integration proceeds. Agents never run either command themselves.
Tune the deploy in `parameter_files/daedalus-tui-firebase.toml` and disable it
with `firebase_deploy_enabled = false` in the orchestration parameter file.

Each prompt creates an independent local Git worktree based on the configured
`target_branch` (default `main`; `primary_branch` remains accepted as an
alias), runs the selected agent (Codex, Claude Code, or Cursor) there, verifies
the result, resolves integration
failures with the selected agent, and fast-forwards that target branch after
successful checks. The operator does not need the target branch checked out.
Up to four prompts can run concurrently; integration and promotion remain
serialized. A dirty operating branch no longer stops a prompt: when the target
branch is checked out with uncommitted work, orchestration commits those
changes and pushes the branch to `origin` before creating the task worktree, so
the task starts from what you actually have. A missing remote or a failed push
is reported as a warning and the task still runs. Set
`dirty_primary_autocommit_enabled = false` in the orchestration parameter file
to get the old "primary worktree must be clean" error back, or
`dirty_primary_push_enabled = false` to commit without publishing. Apart from
that commit, automated orchestration does not push remotes; use the
settings-bar Push control when you want to publish the selected operating
branch to `origin`. Failed worktrees are preserved
for inspection. Task-owned commits use the task's readable title (derived from
the requested goal), adding a short repair, resolver, or graphify-stage suffix
when applicable, so the Git history describes the work that completed. A
successful Push reports the branch and commit in the status line and records
the full SHA in the launch-root `.daedalus-memory.json`; open the **Push log**
settings action or press `Ctrl+H` to browse those records. After a successful
promotion, the orchestrator refreshes and commits `graphify-out` onto the
target branch when the target repository has graphify configured; graph
refresh failures are reported as warnings and never trigger resolver attempts.

Target projects may add an optional `.daedalus` TOML file to prepare each task
worktree before the agent starts. The `[worktree]` table accepts one argv-style
`install_command` and repository-relative `readonly_paths`; the command runs in
the task worktree, then each declared path is symlinked from the primary
worktree. For example:

```toml
[worktree]
install_command = ["npm", "ci"]
readonly_paths = ["food-data"]
```

Symlinked paths are shared local resources and are not OS-enforced read-only;
agents and setup commands must treat them as immutable.

The launch root stores task history in `.daedalus-memory.json`. Its `tasks`
entry maps each task's stable logical key (`task-<id>`) to the submission
timestamp, prompt, generated title, provider/model/reasoning/mode selection,
current state, assistant outputs, token usage, resolved project path, any
error, and (schema version 2) the ordered conversation turns and runs. Older
worktree-keyed snapshots are migrated once and loaded with the original prompt
as the first turn. Failed tasks can be retried; tasks that were running when
the TUI stopped come back as `interrupted` and can be resumed or continued
with a new prompt, never auto-launched. The memory file also keeps a single
`last_opened_project` entry, an `opened_project_directories` list for projects
opened by path, and small UI preferences (viewer visibility, All tasks).
The first launch initializes the project marker to the default project, every
sidebar focus change updates it, and the next startup restores it when that
project still exists. The file is intentionally ignored by Git.

## Prompts, drafts, and errors on disk

Every prompt you send and every draft you type is saved under the TUI's own
`prompts/` folder, and every diagnostic under its `errors/` folder. Both live
under the storage root configured in
`parameter_files/daedalus-tui-prompting.toml` (`[storage] data_root`, default
`.` = the TUI project directory that owns `parameter_files`); a relative root
never depends on the working directory or on which repository a task targets,
and packaged installs in a read-only location should point it at a writable
absolute path such as `~/.local/share/daedalus-tui`. Both folders are
gitignored and never appear as projects in the selector.

```text
daedalus-tui/
  prompts/<project-basename>-<digest>/
    drafts/new-task.json              # unsent new-task draft
    <task-id>/draft.json              # follow-up or recovered draft
    <task-id>/turn-0001.md            # exact first submission
    <task-id>/turn-0002.md            # exact next submission
  errors/
    daedalus.log                      # rotating runtime log (2 MB × 3)
    faults.log                        # fault-handler and SIGUSR1 stack dumps
    <project-basename>-<digest>/<task-id>/turn-0002-run-0001.log
```

Archived prompts are written byte-for-byte (indentation, blank lines, and
trailing newlines included) through atomic file replacement. Drafts save after
a short typing pause (`[drafts] autosave_delay_ms`) and before Send, Cancel,
task or project switches, New Task, and quit, so at most the last unflushed
interval can be lost. If storage cannot be written the editor stays usable and
the status line names the exact path that failed; a prompt that cannot be
archived is not sent. On restart the latest draft returns to the composer, a
missing archive is regenerated from the task index, and an archived prompt the
index does not know is offered back as a recovered draft.

`errors/daedalus.log` replaces the older launch-root `.daedalus-debug.log`
(existing files are left in place). It records UI exceptions, task/agent
lifecycle events with project, task, turn, run, phase, and provider, and
shutdown state, with known credential patterns redacted. Each run's complete
error text is also appended to its own `turn-NNNN-run-NNNN.log` before the
on-screen summary is truncated; the Errors view names both files. If the
process is stuck, run `kill -USR1 <pid>` to append all Python thread stacks to
`errors/faults.log`.

The task list keeps each prompt's provider, model, reasoning, status, branch,
worktree, and filtered assistant-message transcript separate. Raw diffs,
command telemetry, and successful process stderr are hidden. Select a task to
replay its transcript, then click-drag across any selectable label, log, or
error surface and use the Vim `y` command (or `Ctrl+C` / `Ctrl+Alt+S`) to copy
the highlighted text. Textual captures mouse input while the app is running;
if you want your terminal emulator's native selection instead, hold Option in
iTerm or Shift in Terminal.app while dragging.

Vim-style shortcuts are also available without changing normal prompt typing.
The prompt itself is a modal Vim text area with a compact INSERT/NORMAL/VISUAL
indicator: it starts in Insert mode and `Esc` enters Normal mode. Supported
commands: `i a I A o O` (Insert), `h j k l`, `w b e`, `0 $`, `gg G` (moves,
with counts such as `3j`), `v` / `V` (character / whole-line selection),
`x dd dw d$` and visual `d`/`x` (cut, `2dd` cuts two lines), visual `c`
(change), `yy yw y$` and visual `y` (copy, `2yy` copies two lines), `p` / `P`
(paste after / before; whole lines stay whole lines, including on the last
line), `u` / `Ctrl+R` (undo / redo while the prompt has focus). Every cut and
yank also copies to the system clipboard, even when the same text is yanked
twice; if the host clipboard is unavailable the text stays in the Vim
register and the status line says so. `p` uses the Vim register first and the
system clipboard when the register is empty; `"+y`, `"+p`, and `"+P` address
the system clipboard explicitly so newly copied external text is always
reachable. `Enter` inserts a newline; `Shift+Enter` and `Ctrl+Enter` both send,
from any Vim mode. Reporting a modifier on Enter at all requires a terminal
that implements the Kitty keyboard protocol (Ghostty, Kitty, WezTerm, or
iTerm2 with CSI u reporting enabled); terminals without it send a plain Enter
for every variant, and **Send** remains the way to submit there. Mouse clicks
and standard Textual key navigation remain available.

## Conversations, follow-ups, and stopping a run

Each task is a conversation with an automatically generated title taken from
the first meaningful line of its first prompt (Markdown decoration removed,
cut at a word boundary to `[titles] maximum_length`). The title is shown in
the inbox and above the composer and never changes on follow-ups. **New Task**
saves the current draft and starts a separate conversation; with a task
selected, **Send** (`Shift+Enter`) sends the composer text as the next turn of
that task. Sending is available once the task's current run has stopped or
finished; you can type the next prompt while a run is active. Follow-ups keep
the task's provider, model, reasoning, mode, and topic unless you change them
after selecting the task, in which case the change is recorded on the new
turn. The agent receives the original request, recent history, and the latest
instruction within a configurable character budget
(`[conversation] context_budget_chars`), with omitted older turns marked
explicitly; the complete history stays on disk. A preserved worktree is
reused; a cleaned-up one is replaced by a fresh worktree from the operating
branch under the same task. **Prompt history** above the composer reloads any
earlier prompt (or a saved follow-up) into the editor without changing its
archived file. The **All tasks** toggle under the inbox lists completed and
interrupted conversations so they can be reopened after a restart.

Focus a task row and press **`dd`** to delete an inactive conversation and its
task snapshot; active runs must be stopped first.

**`Ctrl+C`, Cancel, and `Ctrl+X`** all stop the selected task's active run
without discarding anything: the worktree, branch, and uncommitted files are
kept, the run is recorded as `interrupted` (not an error), and the interrupted
prompt's exact text returns to the composer in Insert mode with the cursor at
the end. If you had typed a different follow-up, it is saved first and listed
under Prompt history. Edit the restored prompt and Send to continue the same
task, or press Resume to continue in the existing worktree unchanged. Pressing
`Ctrl+C` repeatedly is harmless, with nothing running it leaves the draft
alone, and on the main screen it never copies text or quits (use
`Ctrl+Alt+S` to copy a selection and `Ctrl+Q` to quit; quitting saves drafts
first). Modal dialogs keep their own Escape/Cancel behavior.

## Output viewer

**Show viewer** in the output toolbar opens a read-only Markdown viewer that
takes the right third of the whole usable width on a wide terminal (about 60
of 180 columns), leaving two thirds for the task inbox and the composer. Its
source selector offers the latest response, earlier responses, and the current
plan text; **Raw** shows the exact Markdown source on a selectable surface.

The response's action items head the viewer, above the rendered output: the
unchecked task-list boxes it contains, the list items under a "Next steps" or
"Follow-ups" heading, and any `TODO:`/`NEXT:`/`ACTION:` lines, with the run's
identity on the same header line. Set `[viewer] action_items_by_default =
false` in `parameter_files/daedalus-tui-prompting.toml` to hide that header,
or `action_item_limit` to change how many items it lists.

Every single newline inside a paragraph renders as a real line break, so a
hard-wrapped response reads the way the agent wrote it instead of reflowing
into one block. Fenced and indented code are untouched and **Raw** always
shows the response byte-for-byte; set `[viewer] hard_line_breaks = false` for
strict CommonMark paragraph joining.

Live output re-renders with a short debounce, follows streaming only when you
are already at the bottom, and the viewer never executes code blocks, opens
links, or fetches images (activating a link shows its target in the status
line). When the terminal is narrower than `[viewer] minimum_width +
main_minimum_width` or in compact mode, the same viewer becomes a full-width
alternate view with a **Back** control. The choice is remembered.

## Usage bar

The bottom-left usage bar refreshes every `[usage] interval_seconds` (default
60) in `parameter_files/daedalus-tui.toml`. Neither CLI offers a
non-interactive `usage` subcommand (Claude Code waits for a terminal; Codex
refuses without one), so by default the bar reads the same local data their
own `/usage` and `/status` views show: Codex rate-limit windows (5-hour and
weekly percentages with reset times) from its session logs under
`~/.codex/sessions`, and today's token and message totals for Claude Code.

Claude's `~/.claude/stats-cache.json` is only a derived summary and is often
absent or stale, which used to leave the bar reading `0 tok · 0 msgs` after a
heavy day, so the session transcripts under `[usage] claude_projects_dir`
(default `~/.claude/projects`) are counted as well: every turn appends a JSON
line carrying its `message.usage`, which makes them the authoritative record.
Each figure shown is the larger of the two sources, since neither is complete
on its own and both describe the same calendar day. Transcripts touched within
`[usage] claude_transcript_days` (default 30) are parsed once and afterwards
only from where the previous poll stopped, and turns replayed by a resumed or
forked session are counted once. Claude rate-limit windows (`five_hour`,
`seven_day`, and `spend_limit`) are also drawn when that cache or a configured
JSON command provides them. A configured Claude JSON source may also expose a
`context_window.used_percentage` bar. Every window that reports a percentage is
drawn as a progress bar under its provider's line; `[usage] bar_width` sets how
many cells each bar uses. Set `[usage.<provider>] command` to run any program
instead; it runs with stdin closed and a timeout, and its JSON usage fields or
first output line are shown. Hover the bar for details, including how old the
reading is.

Codex only writes rate limits once a turn finishes, so its most recently
touched session log is often a just-started session with no usage in it. The
reader scans back through `[usage] session_scan_limit` logs (newest first)
until it finds real percentages, reads only the last `session_tail_bytes` of
each, and accepts both the `resets_in_seconds` and `resets_at` spellings of a
window's reset time.

Use the mode selector for Coding, Ask, or Plan, or press `Tab` on the main
prompting screen to toggle between Coding and Plan. Ask runs are read-only and do
not promote file changes. Plan runs are read-only and remain selectable in the
task list through their `planning`, `questioning`, and answer-review states.
They return a structured implementation plan and multiple-choice questions;
submit selected answers for another review round, or use the follow-up
controls to continue planning. The Implement button remains unavailable until
the agent confirms that no questions remain, then continues the same
conversation as a coding run from the approved plan. Pause preserves the task
worktree and allows resume later; Cancel (or `Ctrl+C`) stops the run, keeps
its worktree and branch, and returns the prompt to the composer.

Optional Topics group closely related tasks under shared markdown in
`topic_files/` (Topic Goal, Topic Status, State Log). Create or edit those
files outside the TUI; the wide settings row and compact settings picker both
list existing stems and default to `(None)`. When tagged, coding/plan/ask
prompts embed the topic
plus usage instructions; coding tasks may append the topic State Log the same
way they update feature files.

When resuming, the optional notes field is sent to the agent only when it has
content. The resume prompt tells the agent to preserve existing work, inspect
`git status` and `git diff`, and continue from the current worktree.
