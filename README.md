# Daedalus TUI

This directory is an independently exportable project. It contains the
Textual interface and all local agent orchestration code; it does not import
the Daedalus daemon or depend on a database service. Registered personal-Supabase
projects may use the locally installed Supabase CLI through orchestration.

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

The launch directory is treated as a project workspace. The TUI discovers only
its immediate child directories that contain a `feature_files/` folder; nested
descendants are not traversed or listed. If no eligible child project exists,
the launch directory remains available as a usability fallback. Each project
has its own task coordinator, task numbering, Git worktrees, and transcripts;
switching the sidebar does not interrupt tasks running in another project.

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

For Cursor CLI, set `CURSOR_API_KEY` once in the launch-root `.env` (copy
`.env.example` from the Daedalus TUI checkout if needed). Target projects such
as `wfinance2` do not need their own copy; the TUI injects the operator key
into Cursor worktree processes. When developing against an editable TUI
checkout, the package-root `.env` is also consulted as a fallback.

```bash
cp /path/to/daedalus-tui/.env.example .env   # in the launch root
# edit .env and set CURSOR_API_KEY=...
```

The TUI passes `CURSOR_API_KEY` to Cursor only when it is not already present
in the process environment or the active project's `.env`. You can also
authenticate with `agent login` instead of an API key.

For personal shared Supabase projects, keep `SUPABASE_URL`,
`SUPABASE_PUBLISHABLE_KEY`, and `SUPABASE_SECRET_KEY` in the active project's
ignored `.env` (legacy `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY`, and
`SUPABASE_PRIVATE_KEY` as a secret alias, still work). `SUPABASE_PROJECT_REF`
is optional when the URL is `https://<ref>.supabase.co`. For Activate and
migration push, also set either `SUPABASE_DB_URL` or `SUPABASE_ACCESS_TOKEN`
(API keys alone cannot push SQL). Registered projects store only their schema
marker; operators set project-local Supabase credentials manually (the Register
setup wizard checks the active project's file). Daedalus does not sync those
values into another project. When `supabase_db_push_enabled` is enabled,
startup pushes migrations only for projects that have been Activated (ecosystem-ready);
scaffolded projects wait for explicit Activate via the Command Menu (`Ctrl+K`).
The same menu provides an exact-project-name-confirmed local cleanup action for
removing a broken personal-Supabase scaffold; cleanup does not change the remote
database. Process environment variables remain runtime overrides and are never
written to disk. Copy the project's `.env.example` to `.env`; do not put
Supabase credentials in tracked feature, parameter, or `.env.example` files.

Each prompt creates an independent local Git worktree based on the configured
`target_branch` (default `main`; `primary_branch` remains accepted as an
alias), runs Codex or Cursor there, verifies the result, resolves integration
failures with the selected agent, and fast-forwards that target branch after
successful checks. The operator does not need the target branch checked out.
Up to four prompts can run concurrently; integration and promotion remain
serialized. Automated orchestration never pushes remotes; use the Command Menu
(`Ctrl+K`) when you want to publish the selected operating branch to `origin`.
Failed worktrees are preserved
for inspection. After a successful promotion, the orchestrator refreshes and
commits `graphify-out` onto the target branch when the target repository has
graphify configured; graph refresh failures are reported as warnings and never
trigger resolver attempts.

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
entry maps each task worktree directory name to the submission timestamp,
prompt, provider/model/reasoning/mode selection, current state, assistant
outputs, token usage, resolved project path, and any error so failed, paused,
and cancelled work can be reopened for analysis. Failed tasks and tasks
interrupted by a TUI restart are rehydrated into the task inbox; failed tasks
can be retried and interrupted tasks can be resumed when their worktrees still
exist. The memory file also keeps a single `last_opened_project` entry.
Plan tasks with submitted answers additionally retain generated review requests
in an optional `prompt_history` list on the same worktree record.
Runtime diagnostics are written to `.daedalus-debug.log` next to that memory
file (rotated at 2 MB). It records UI exceptions, task/agent lifecycle events,
and shutdown state. During Python exit it cancels active agent process groups
before the executor can block on their worker threads. If the process is
stuck, run `kill -USR1 <pid>` to append all Python thread stacks to the same
log before terminating it; this command writes only to the log by design.
The first launch initializes it to the default project, every sidebar focus
change updates it, and the next startup restores it when that project still
exists. The file is intentionally ignored by Git.

The task list keeps each prompt's provider, model, reasoning, status, branch,
worktree, and filtered assistant-message transcript separate. Raw diffs,
command telemetry, and successful process stderr are hidden. Select a task to
replay its transcript, then click-drag across any selectable label, log, or
error surface and use the Vim `y` command (or `Ctrl+C` / `Ctrl+Alt+S`) to copy
the highlighted text. Textual captures mouse input while the app is running;
if you want your terminal emulator's native selection instead, hold Option in
iTerm or Shift in Terminal.app while dragging.

Vim-style shortcuts are also available without changing normal prompt typing.
The prompt itself is a modal Vim text area: it starts in Insert mode, `Esc`
enters Normal mode, and `i`, `a`, `o`, `h/j/k/l`, `w`, `e`, `0`, `$`, `gg`, `G`,
`d`, `u`, `y`, `p`, Visual mode, and `Shift+V` visual-line mode are available.
`Enter` inserts a newline;
`Ctrl+Enter` submits the prompt. Yanks are mirrored to the system clipboard,
and `p` falls back to the system clipboard when the Vim register is empty.
The supported command subset is intentionally incremental so additional Vim
commands can be added as they become useful. Mouse clicks and standard
Textual key navigation remain available.

Use the mode selector for Coding, Ask, or Plan, or press `Tab` on the main
prompting screen to toggle between Coding and Plan. Ask runs are read-only and do
not promote file changes. Plan runs are read-only and remain selectable in the
task list through their `planning`, `questioning`, and answer-review states.
They return a structured implementation plan and multiple-choice questions;
submit selected answers for another review round, or use the follow-up
controls to continue planning. The Implement button remains unavailable until
the agent confirms that no questions remain, then creates a separate coding
task from the approved plan. Pause preserves the task worktree and allows
resume later; Cancel stops the agent and removes that task's worktree and
branch.

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
