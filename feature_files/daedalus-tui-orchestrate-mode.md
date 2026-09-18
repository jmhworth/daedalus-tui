# Daedalus TUI Orchestrate Mode

## Summary
Orchestrate Mode is a second view inside the TUI where the operator writes one
prompt and a **Planner** agent (Claude Fable by default) decomposes it into
small, self-contained task cards, delegates them to at most *N* **Worker**
agents (Claude Opus by default, *N* chosen by the operator), watches their
reports, re-issues failed cards, and resolves merge conflicts. Either role may
run on any provider the settings bar offers (Claude Code, Codex / ChatGPT, or
Cursor CLI); the orchestrate view has a provider, model, and effort selector
per role. The point of the design is cost:
each worker receives the minimum context its card needs, so the same amount of
work costs fewer tokens than running every task with the full prompt and full
repository exploration.

## Key Points
- **Planner and Worker roles**: The Planner runs in a read-only worktree in
  mode `orchestrate-plan`, returns a JSON payload between
  `BEGIN_DAEDALUS_ORCHESTRATION` and `END_DAEDALUS_ORCHESTRATION`, and never
  edits files — the TUI materializes the plan, cards, and checklists from that
  payload so a planner cannot silently do worker work. Workers run in mode
  `coding` and return a report between `BEGIN_DAEDALUS_WORKER_REPORT` and
  `END_DAEDALUS_WORKER_REPORT`.
- **Workers are ordinary coding tasks**: every card is submitted to the
  existing `TaskCoordinator`, so it gets its own `agent/task-<id>` worktree,
  verification, repairs, integration, and promotion for free and appears in the
  existing task inbox tagged with its session. No second execution engine
  exists.
- **Context is minimized by construction, not by instruction**: a worker prompt
  contains only the terse worker role block, the repository coding profile, one
  task card, and the standard worktree boundary text. It never contains the
  operator's original prompt, other cards, the planner's reasoning, or
  conversation history. Planner rounds after the first receive a bounded status
  digest, not worker transcripts.
- **Cards are files, not prose**: the card is written to
  `<worktree>/.daedalus-orchestration/task.md` before the worker runs. Workers
  tick `- [x]` items as they finish them and the TUI reads the ticks back before
  the worktree is removed. The directory is registered as a Daedalus runtime
  artifact so it is never staged or committed.
- **Dependencies are ordered by promotion**: a card may declare `depends_on`
  and is dispatched only after those cards have been promoted into the
  operating branch, so its worktree already contains their changes. Cards with
  no dependency between them must have disjoint file scopes; the payload parser
  rejects a plan that violates that.
- **The planner decides how many rounds the work needs**: there is no fixed
  round count. After each wave the planner is called again and either adds
  cards, re-issues a failed one, or declares the session done. A round that
  adds no runnable card and does not finish fails the session, each card may
  be re-issued only `task_reissue_limit` times, and `planner_round_limit` is
  an optional safety cap (0, the default, means none). Exhausting a cap ends
  the session with a clear status; nothing retries forever.
- **The planner is kept fast and visible**: the first turn embeds a bounded
  `git ls-files` map (`planner_repository_map_chars`) so the planner can name
  `read_first` paths without exploring, the prompt tells it not to run tests or
  builds, the default planner effort is `medium`, and streamed planner
  messages are written to the session log with elapsed seconds while the
  round runs.
- **The context file is the one session artifact that reaches the repository**:
  after every accepted planner round and when a session ends, the coordinator
  renders every session of the project (prompt, summary, full cards with
  ticks, scope, interfaces, verify command, worker notes, and outcome) to
  `DAEDALUS_CONTEXT.md` (`context_filename`), commits only that file onto the
  operating branch through the task coordinator's integration gate (so it can
  never land between a worker's base capture and its promotion), and pushes it
  immediately when `promotion_push_enabled` is on. The round-one write precedes
  dispatch, so worker worktrees already carry it. The next session's first
  planner turn embeds the file inline (bounded by `planner_context_chars`,
  dropping the oldest sessions whole) and the planner rules say to continue
  from it, which is what makes "assign the cards you already made" work in a
  fresh session instead of failing on a bare repository. A failed write or
  push is logged on the session and never fails it.
- **Interface to orchestration**: worktrees, verification, repairs, the
  integration gate, promotion, and the conflict resolver all belong to
  `feature_files/daedalus-tui-orchestration.md`. Orchestrate Mode only selects
  the resolver's model (the planner's, so conflict resolution stays with the
  role that knows the whole plan) and injects the card into the worktree
  through before/after agent hooks. Concurrency is bounded by both the session's
  max-workers value and that feature's `max_concurrent_tasks`, whichever is
  smaller.

## Relevant Files
- `parameter_files/daedalus-tui-orchestrate-mode.toml`: Role selections, session
  caps, context budgets, storage names, and view dimensions.
- `tui/config.py`: `OrchestrateSettings` and `load_orchestrate_settings()`.
- `tui/templates/orchestrate/AGENTS.md`: The `## Shared`, `## Planner`, and
  `## Worker` role rule blocks the prompt builders embed by heading.
- `tui/templates/orchestrate/task-card.md`: Task card template filled per card.
- `tui/orchestrate_protocol.py`: Planner payload and worker report parsing,
  dispatch readiness, card rendering, tick parsing, and the card's verify
  command.
- `tui/orchestrate_session.py`: `OrchestrationSession`, `TaskCard`, and
  `SessionStore` (plan, card, report, and digest files; the worktree card),
  plus `render_context` for the repository context file.
- `tui/orchestrate_coordinator.py`: `OrchestrateCoordinator`, the per-project
  dispatcher running planner rounds, worker scheduling, and the failure loop
  on one thread per session, plus `SessionEventRecord` for the app's queue.
- `tui/prompts.py`: `build_planner_prompt`, `build_planner_round_prompt`,
  `build_worker_prompt`, and the card branch of `build_task_prompt`.
- `tui/orchestrator.py`: `orchestrate-plan` mode with `planner_output`, the
  `resolver_selection` override, and the `before_agent`/`after_agent` hooks.
- `tui/task_coordinator.py`: Worker fields on `TaskRecord`, the card and hook
  keywords of `submit`, and task observers.
- `tui/memory.py`: Orchestration snapshots and the worker `session_id` and
  `card_id` pass-through on task snapshots.
- `tui/app.py`, `tui/app.tcss`: The Orchestrate Mode button, `Ctrl+O`, the
  view switcher, the orchestrate view, and session event rendering.
- `tui/git_worktree.py`: `.daedalus-orchestration` registered as a runtime
  artifact, including its directory-prefixed status entries.
- `AGENTS.md`, `tui/templates/project-initializer/AGENTS.md`,
  `.agents/profiles/coding.md`: The Orchestrate Mode expectations carried into
  this repository, initialized projects, and coding agents.
- `tests/test_orchestrate_protocol.py`, `tests/test_orchestrate_session.py`,
  `tests/test_orchestrate_coordinator.py`, `tests/test_orchestrate_end_to_end.py`,
  `tests/test_prompts.py`, `tests/test_orchestrator.py`,
  `tests/test_task_coordinator.py`, `tests/test_app.py`, `tests/test_config.py`,
  `tests/test_git_worktree.py`: Coverage from parsing to the real-Git session.

## Dev Mode
HACKING

## State Log
- 2026-09-16: Added the foundations (feature and parameter files, the
  `OrchestrateSettings` loader, the bundled role-rule and task-card templates,
  the `## Orchestrate Mode` notes in both `AGENTS.md` files, and
  `.daedalus-orchestration` as a runtime artifact whose directory-prefixed
  status entries are also excluded from staging).
- 2026-09-16: Added `tui/orchestrate_protocol.py` (planner payload and worker
  report parsing with cycle and disjoint-scope checks, `ready_tasks`, card
  rendering and tick parsing) plus the planner, planner-round, and worker prompt
  builders, with the worker builder structurally unable to receive the
  operator's prompt.
- 2026-09-17: Added `tui/orchestrate_session.py` (session and card state, the
  `SessionStore` writing `PLAN.md`, cards, reports, digests, and the worktree
  card) and orchestration snapshots in memory; sessions restored mid-flight are
  marked `stopped` and never auto-resume.
- 2026-09-17: Taught the orchestrator the `orchestrate-plan` mode (planning
  profile, worktree reset, raw `planner_output`), a `resolver_selection`
  override, and `before_agent`/`after_agent` hooks; `build_task_prompt` and the
  repair and resolver prompts embed the card instead of the operator prompt for
  worker tasks, and `TaskCoordinator.submit` carries session, card, and hooks.
- 2026-09-17: Added `tui/orchestrate_coordinator.py`: one thread per session
  runs planner rounds with one corrective retry, dispatches ready cards bounded
  by max-workers and `max_concurrent_tasks`, captures reports and ticks through
  the hooks, re-issues failed cards within the reissue limit (a re-issued card's
  promotion satisfies its dependents), and ends on `done`, a cap, or a stop.
- 2026-09-17: Added the orchestrate view (button and `Ctrl+O`, role selects,
  max-workers input, autosaved prompt, Start/Stop, session selector, board,
  planner log, summary line, `PLAN.md` in the viewer, card ids on worker inbox
  rows) with one dispatcher per project created beside its task coordinator.
- 2026-09-17: Added the real-Git end-to-end and conflict tests, the README
  section, and the coding-profile paragraph on worker cards.
- 2026-09-18: Removed the fixed six-round planner cap (`planner_round_limit`
  is now an optional safety cap defaulting to 0, and the planner decides when
  the session is done), added the bounded repository map, medium default
  planner effort, and live planner progress lines to speed the planner up,
  and opened both roles to Codex (ChatGPT) and Cursor CLI with provider,
  model, and effort selectors per role in the orchestrate view.
- 2026-09-18: Added the repository context file: `render_context` writes every
  session's prompt, plan, and full card outcomes to `DAEDALUS_CONTEXT.md`,
  the coordinator commits and pushes it after each accepted planner round and
  at session end (through the integration gate, before dispatch), the first
  planner turn embeds it bounded by `planner_context_chars`, and the planner
  rules tell the planner to continue from it. Context-file pushes arrive as
  session events and are recorded in the Push log like task pushes.
