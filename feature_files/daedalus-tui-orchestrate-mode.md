# Daedalus TUI Orchestrate Mode

## Summary
Orchestrate Mode is a second view inside the TUI where the operator writes one
prompt and a **Planner** agent (Claude Fable) decomposes it into small,
self-contained task cards, delegates them to at most *N* **Worker** agents
(Claude Opus, *N* chosen by the operator), watches their reports, re-issues
failed cards, and resolves merge conflicts. The point of the design is cost:
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
- **Bounded loops everywhere**: planner rounds, per-card re-issues, and worker
  count are all capped in the parameter file. Exhausting a cap ends the session
  with a clear status; nothing retries forever.
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
  dispatch readiness, card rendering, and checklist tick parsing.
- `tui/prompts.py`: `build_planner_prompt`, `build_planner_round_prompt`, and
  `build_worker_prompt`.
- `tui/git_worktree.py`: `.daedalus-orchestration` registered as a runtime
  artifact, including its directory-prefixed status entries.
- `AGENTS.md`, `tui/templates/project-initializer/AGENTS.md`: The Orchestrate
  Mode expectations carried into this repository and initialized projects.
- `tests/test_orchestrate_protocol.py`, `tests/test_prompts.py`,
  `tests/test_config.py`, `tests/test_git_worktree.py`: Coverage for parsing,
  prompt minimality, settings loading, and artifact exclusion.

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
