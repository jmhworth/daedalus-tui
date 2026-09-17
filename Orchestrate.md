# Orchestrate Mode implementation plan

Planning date: September 16, 2026. This document describes the work needed to
add **Orchestrate Mode** to the Daedalus TUI. It does not implement anything.


The sections are written so several agents can work on them at the same time.
Section 0 is the shared contract every other section must follow. Sections 1
through 7 each name their inputs, outputs, owned files, and the sections they
depend on. A section with no dependency can start immediately; a dependent
section may start against the interfaces in Section 0 and reconcile when the
upstream section lands.

## Goal

Orchestrate Mode is a second tab inside Daedalus. The operator writes one main
prompt. A **Planner** agent (Claude Fable) decomposes it into small,
self-contained tasks with checklists, delegates them to at most *N* **Worker**
agents (Claude Opus, *N* chosen by the operator), watches their progress,
re-issues failed work, and resolves merge conflicts. Workers execute one task
each and report back in a fixed format. The point of the design is that each
worker receives the **minimum context** needed for its task, so the same amount
of work costs fewer tokens than running every task with the full prompt and
full repository exploration.

## What already exists and what changes

| Area | Current implementation | What Orchestrate Mode adds |
| --- | --- | --- |
| Task execution | `tui/task_coordinator.py` runs up to four independent coding tasks through `tui/orchestrator.py`: worktree, agent, verification with repairs, serialized integration, resolver on conflicts, promotion. | Workers reuse this pipeline unchanged. A new dispatcher submits worker tasks and feeds their results to the planner. |
| Structured agent output | `tui/plan.py` parses a `BEGIN_DAEDALUS_PLAN … END_DAEDALUS_PLAN` JSON payload from Plan mode. | The same pattern is reused for the planner's task list and for worker reports. |
| Prompt wrappers | `tui/prompts.py` builds task, repair, and resolver prompts and embeds the repository profile and topic. | New planner and worker wrappers that embed a terse role block and a task card instead of the full user prompt. |
| Conflict resolution | `LocalOrchestrator.resolve_integration` launches the task's own provider/model as a resolver. | The resolver runs with the planner's model in Orchestrate Mode, so conflict resolution stays with the role that knows the whole plan. |
| Persistence | `tui/memory.py` stores task snapshots in `.daedalus-memory.json`; `tui/local_storage.py` owns `prompts/` and `errors/`. | A session snapshot plus session files (plan, task cards, checklists, reports) under the TUI storage root. |
| UI | `tui/app.py` composes one project view: task bar, settings row, output panel, plan review, composer. Modal screens exist for statistics, push history, and topics. | An `Orchestrate Mode` button and `Ctrl+O` switch the project area to an orchestrate view with role settings, a max-workers control, a session board, and a planner log. |
| Configuration | Feature/parameter pairs under `feature_files/` and `parameter_files/`; settings loaders in `tui/config.py`. | `feature_files/daedalus-tui-orchestrate-mode.md` and `parameter_files/daedalus-tui-orchestrate-mode.toml` with a loader. |

## Design decisions

- **Workers are ordinary coding tasks.** Every worker task is submitted to the
  existing `TaskCoordinator` in `coding` mode. It gets its own `agent/task-<id>`
  worktree, verification, repairs, integration, and promotion for free, and it
  appears in the existing task inbox tagged with its session. No second
  execution engine is written.
- **The planner never edits files.** Like Plan mode, the planner runs in a
  worktree that is reset to its base commit afterwards. It reads the repository
  and returns a JSON payload. The TUI, not the agent, materializes the plan,
  task cards, and checklists from that payload. This keeps planner output
  parseable and prevents a planner from silently doing worker work.
- **Context is minimized by construction, not by instruction.** A worker
  prompt contains only: the terse worker role block, the repository coding
  profile (required by existing profile policy), one task card, and the
  standard worktree boundary text. It never contains the operator's original
  prompt, other tasks, the planner's reasoning, or conversation history. The
  planner is told to write cards that let a worker start without exploring:
  goal, acceptance checklist, file scope, files to read first, interface
  contracts, and the verification command.
- **Planner rounds receive digests, not transcripts.** After each worker
  finishes, the planner sees a bounded status digest: task id, status,
  checklist ticks, files changed, and the worker's report. Transcripts stay on
  disk.
- **Dependencies are ordered by promotion.** A task may declare `depends_on`.
  It is dispatched only after those tasks have been promoted into the operating
  branch, so its worktree already contains their changes. Independent tasks in
  the same wave must be given disjoint file scopes by the planner; residual
  conflicts fall through to the existing resolver, now run with the planner
  model.
- **Bounded loops everywhere.** Planner rounds, per-task re-issues, and worker
  count are all capped by parameters. Exhausting a cap ends the session with
  a clear status; nothing retries forever.
- **Dev Mode is HACKING** for the new feature. Readable, direct code first.
  Do not add command-line flags for any of this; every tunable lives in the
  parameter file.

---

## Section 0 — Shared contract (read by every section; owned by no one)

No agent edits this section's content into code directly; it fixes the names
and shapes other sections implement so they fit together.

### 0.1 Names

| Thing | Name |
| --- | --- |
| Feature file | `feature_files/daedalus-tui-orchestrate-mode.md` |
| Parameter file | `parameter_files/daedalus-tui-orchestrate-mode.toml` |
| Settings dataclass and loader | `OrchestrateSettings`, `load_orchestrate_settings()` in `tui/config.py` |
| Protocol module | `tui/orchestrate_protocol.py` |
| Session/file module | `tui/orchestrate_session.py` |
| Dispatcher module | `tui/orchestrate_coordinator.py` |
| Prompt builders | `build_planner_prompt`, `build_planner_round_prompt`, `build_worker_prompt` in `tui/prompts.py` |
| Bundled role rules | `tui/templates/orchestrate/AGENTS.md` |
| Bundled card template | `tui/templates/orchestrate/task-card.md` |
| Task modes | `"orchestrate-plan"` (planner) and `"coding"` (worker, unchanged) |
| Session id | `orc-<sequence:03d>-<8 hex>` |
| Worker task id | existing coordinator task id; the record gains `session_id` and `card_id` |
| Storage | `<data_root>/prompts/<project-key>/orchestrate/<session-id>/` |
| Worktree runtime artifact | `.daedalus-orchestration/` (directory, never staged) |
| UI ids | `#orchestrate-mode-button`, `#orchestrate-view`, `#tasks-view`, `#view-switcher`, `#planner-model-select`, `#worker-model-select`, `#max-workers-input`, `#orchestrate-prompt`, `#orchestrate-board`, `#planner-log`, `#orchestrate-start-button`, `#orchestrate-stop-button` |
| Shortcut | `Ctrl+O` toggles Task view and Orchestrate view |

### 0.2 Planner payload (planner → TUI)

Returned between `BEGIN_DAEDALUS_ORCHESTRATION` and
`END_DAEDALUS_ORCHESTRATION`, JSON only, no prose outside the markers.

```json
{
  "summary": "one paragraph describing the approach",
  "tasks": [
    {
      "id": "t1",
      "title": "short imperative title",
      "goal": "what done looks like, in two to five sentences",
      "checklist": ["verifiable item", "verifiable item"],
      "file_scope": ["tui/foo.py", "tests/test_foo.py"],
      "read_first": ["tui/bar.py:120-180", "feature_files/x.md"],
      "interfaces": "signatures or contracts this task must expose or consume",
      "verify": "pytest tests/test_foo.py",
      "depends_on": []
    }
  ],
  "done": false
}
```

Rules enforced by the parser: unique ids; every task has at least one
checklist item and a non-empty `file_scope`; `depends_on` refers only to
existing ids and forms no cycle; two tasks with no dependency between them may
not share a path in `file_scope`; `done=true` is only valid with an empty task
list and is how the planner declares the session finished in a later round.

### 0.3 Planner round input (TUI → planner)

Each round after the first, the planner receives the original prompt, the
current plan summary, and a **digest** bounded by
`planner_digest_budget_chars`:

```text
SESSION orc-001-ab12cd34  round 2 of 6  workers 2/3 busy
t1  promoted   4/4 checklist  files: tui/foo.py, tests/test_foo.py
t2  failed     1/3 checklist  error: verification exhausted (pytest tests/test_bar.py)
    report: <worker report text, bounded>
t3  waiting    depends_on t2
```

The planner replies with the same payload shape. It may add new tasks, re-issue
a failed task under a new id with a revised card (optionally `"reissues": "t2"`),
or set `done=true`.

### 0.4 Worker report (worker → TUI)

Returned at the end of the worker's response between
`BEGIN_DAEDALUS_WORKER_REPORT` and `END_DAEDALUS_WORKER_REPORT`:

```json
{
  "task": "t2",
  "status": "done",
  "checklist": [true, true, false],
  "files_changed": ["tui/bar.py"],
  "errors": "empty string, or what blocked the unfinished items",
  "notes": "anything the planner must know: interface changes, follow-ups"
}
```

`status` is one of `done`, `partial`, `blocked`. A missing or malformed report
is treated as `partial` with an error describing the parse failure. The
checklist array is reconciled with the ticks in the worker's card file
(Section 3); the card file wins when both are present.

### 0.5 Task card file (TUI → worker worktree)

Written to `<worktree>/.daedalus-orchestration/task.md` before the worker runs.
The directory is a runtime artifact so it is never staged or committed.

```markdown
# t2 — Add bar parsing

## Goal
…

## Checklist
- [ ] item one
- [ ] item two

## File scope
- tui/bar.py
- tests/test_bar.py

## Read first
- tui/foo.py:120-180

## Interfaces
…

## Verify
pytest tests/test_bar.py
```

Workers tick items (`- [x]`) in this file as they finish them. The TUI reads it
back after the run and before the worktree is removed.

### 0.6 Session states and events

Session status: `planning`, `dispatching`, `waiting`, `resolving`, `completed`,
`failed`, `stopped`. Task-card status: `pending`, `waiting`, `running`,
`verifying`, `integrating`, `promoted`, `failed`, `reissued`, `stopped`.

Events flow through the existing `TaskEventCallback` with a new phase family
`orchestrate` so the app's existing event queue delivers them; the payload is
`(session_id, message, kind)` carried on a lightweight `SessionEventRecord`
that satisfies the fields the app reads (`task_id`, `phase`, `status`).

### 0.7 Parameter keys

```toml
# parameter_files/daedalus-tui-orchestrate-mode.toml
[roles]
planner_provider = "claude"
planner_model = "claude-fable-5-1"
planner_reasoning = "high"
worker_provider = "claude"
worker_model = "claude-opus-5"
worker_reasoning = "high"

[limits]
default_max_workers = 3
max_workers_limit = 8          # upper bound the UI control allows
planner_round_limit = 6        # planner rounds per session including the first
task_reissue_limit = 2         # times one card may be re-issued after failure
planner_digest_budget_chars = 12000
worker_report_budget_chars = 4000
worker_card_budget_chars = 6000

[files]
session_dirname = "orchestrate"
card_filename = "task.md"
runtime_artifact_dirname = ".daedalus-orchestration"

[ui]
board_title_width = 28
planner_log_lines = 400
```

---

## Section 1 — Foundations: feature file, parameter file, settings loader, bundled templates

Depends on: nothing. Blocks: 2, 3, 4, 5, 6.

1. Create `feature_files/daedalus-tui-orchestrate-mode.md` using the required
   schema: H1, `## Summary`, `## Key Points`, `## Relevant Files`,
   `## Dev Mode` (`HACKING`), `## State Log`. Describe the Planner/Worker
   roles, the context-minimization rule, the "workers are ordinary coding
   tasks" decision, and the cross-feature interface to
   `feature_files/daedalus-tui-orchestration.md` (worktrees, verification,
   integration, resolver are that feature's; this feature only selects the
   resolver model and injects the card).
2. Create `parameter_files/daedalus-tui-orchestrate-mode.toml` with the keys in
   Section 0.7 and one comment per table explaining the effect. No API keys.
3. Add `OrchestrateSettings` (frozen dataclass mirroring 0.7) and
   `load_orchestrate_settings(parameter_path=None)` to `tui/config.py`,
   following the shape of `load_orchestration_settings`. Validate: models must
   exist in `claude_models` when the provider is `claude`; limits must be
   positive; `default_max_workers <= max_workers_limit`.
4. Add `tui/templates/orchestrate/AGENTS.md`, decently terse, with three
   blocks the prompt builders embed by heading: `## Planner`, `## Worker`,
   `## Shared`. Contents in full:
   - Shared: edit only inside your worktree; never run git write commands,
     graphify, or deploy commands; report in the required payload; stay inside
     your file scope; do not read files outside `read_first` unless a
     checklist item cannot be completed without it.
   - Planner: you own decomposition, ordering, and conflict resolution; every
     card must be completable by a worker that reads only `read_first`; give
     disjoint file scopes to tasks that run concurrently; a checklist item
     must be verifiable by a command or a diff; prefer more small tasks over
     fewer large ones; you never edit files yourself.
   - Worker: do exactly the card; tick checklist items in
     `.daedalus-orchestration/task.md` as you finish them; if an item cannot be
     done, leave it unticked and explain in `errors`; never expand scope; put
     interface changes in `notes`.
5. Add `tui/templates/orchestrate/task-card.md` matching Section 0.5 with
   `{{ }}` placeholders that `tui/orchestrate_session.py` fills.
6. Extend `tui/templates/project-initializer/AGENTS.md` (if present; create if
   the initializer writes one) with a short `## Orchestrate Mode` section that
   points to the role rules, so target projects initialized by Daedalus carry
   the same expectations. This repository's own `AGENTS.md` gets the same short
   section.
7. Add `.daedalus-orchestration` to `DAEDALUS_RUNTIME_ARTIFACTS` in
   `tui/git_worktree.py` so the card directory is never staged.
   `GitWorktreeManager.is_runtime_artifact` currently matches only an exact
   name or a rotated `name.N` suffix; extend it so an entry equal to
   `<artifact>/` or starting with `<artifact>/` also matches, because
   `git status --porcelain` reports an untracked directory with a trailing
   slash and its files with the directory prefix.

Tests: `tests/test_config.py` gains loader tests (defaults, invalid model,
limit ordering). `tests/test_git_worktree.py` gains a runtime-artifact test for
the card directory.

Completion check: settings load from the parameter file with the Fable/Opus
defaults, and the templates exist with the three headings.

---

## Section 2 — Protocols and prompt builders

Depends on: Section 0 shapes only (Section 1 for budget names; use constants
until it lands). Blocks: 3, 4, 5.

1. Create `tui/orchestrate_protocol.py` with:
   - `PlannerTask` (frozen): `task_id`, `title`, `goal`, `checklist: tuple[str, ...]`,
     `file_scope: tuple[str, ...]`, `read_first: tuple[str, ...]`, `interfaces: str`,
     `verify: str`, `depends_on: tuple[str, ...]`, `reissues: str | None`.
   - `PlannerPayload` (frozen): `summary`, `tasks`, `done`, `valid`, `error`.
   - `WorkerReport` (frozen): `task_id`, `status`, `checklist: tuple[bool, ...]`,
     `files_changed`, `errors`, `notes`, `valid`, `error`.
   - `parse_planner_payload(response: str) -> PlannerPayload` implementing every
     rule in Section 0.2, including cycle detection and the disjoint-scope check
     for tasks with no dependency path between them.
   - `parse_worker_report(response: str) -> WorkerReport` per Section 0.4.
   - `ready_tasks(tasks, promoted_ids, active_ids, failed_ids) -> list[PlannerTask]`
     returning dispatchable tasks in payload order.
   - Marker constants and a `_payload_text` helper modeled on `tui/plan.py`.
2. Add to `tui/prompts.py`:
   - `build_planner_prompt(user_prompt, role_rules, profile_text, topic_text, max_workers, verification_hint)`:
     `TASK_MODE: orchestrate-plan` header, the operator prompt, the embedded
     `## Shared` and `## Planner` blocks, the planning profile (the orchestrator
     loads route `plan` for this mode), the payload instructions from 0.2, the
     worker count so the planner sizes waves, and the read-only boundary text
     used by Plan mode.
   - `build_planner_round_prompt(user_prompt, summary, digest, role_rules, profile_text, round_number, round_limit)`:
     same header and rules plus the digest, plus the instruction that it may
     add, re-issue, or finish.
   - `build_worker_prompt(card_markdown, role_rules, profile_text, verify_command)`:
     `TASK_MODE: coding` header, the embedded `## Shared` and `## Worker`
     blocks, the coding profile, the card, the report instructions from 0.4,
     and the existing worktree boundary sentence. **It must not accept or
     include** the operator's prompt, other cards, or conversation history;
     make that a docstring rule and a test.
   - `bounded_digest(text, limit)` reuse of the existing `_bounded` helper.
3. Add `render_task_card(task: PlannerTask, template_text: str) -> str` and
   `parse_card_ticks(markdown: str) -> tuple[bool, ...]` in
   `tui/orchestrate_protocol.py` so Section 3 can write and read cards without
   a second Markdown parser.

Tests: `tests/test_orchestrate_protocol.py` (valid payload, missing checklist,
duplicate ids, cycle, shared scope between independent tasks, `done` with
tasks, malformed report defaults to `partial`, tick parsing). `tests/test_prompts.py`
gains planner and worker prompt tests, including the "worker prompt contains no
operator prompt" assertion and a size assertion against
`worker_card_budget_chars`.

Completion check: a sample planner response parses into ordered ready waves,
and a worker prompt for one card is under the configured budget.

---

## Section 3 — Session storage, cards, and checklists

Depends on: 1 (storage settings), 2 (`PlannerTask`, card render/parse).
Blocks: 5, 6.

1. Create `tui/orchestrate_session.py` with `OrchestrationSession` (mutable
   dataclass): `session_id`, `project_key`, `prompt`, `planner_selection`,
   `worker_selection`, `max_workers`, `status`, `round`, `summary`,
   `cards: dict[str, TaskCard]`, `started_at`, `finished_at`, `tokens_planner`,
   `tokens_workers`, `error`. `TaskCard`: the `PlannerTask` plus `status`,
   `worker_task_id`, `checklist_state: tuple[bool, ...]`, `report: WorkerReport | None`,
   `reissue_count`, `branch_name`, `promoted_commit`.
2. `SessionStore(storage: LocalStorage, settings: OrchestrateSettings)`:
   - `session_dir(project_key, session_id)` under
     `<data_root>/prompts/<project-key>/orchestrate/<session-id>/`.
   - `write_plan(session)` → `PLAN.md` (summary plus a table of cards and
     their status) and `plan-round-<n>.json` (raw payload).
   - `write_card(session, card)` → `cards/<card-id>.md` via `render_task_card`.
   - `write_report(session, card, raw_text)` → `reports/<card-id>-<n>.md`.
   - `place_card_in_worktree(card, worktree: Path)` → writes
     `<worktree>/.daedalus-orchestration/task.md`, creating the directory.
   - `read_card_from_worktree(worktree) -> tuple[bool, ...] | None`.
   - `write_digest(session) -> str` producing the Section 0.3 text bounded by
     `planner_digest_budget_chars`; also saved as `digest-round-<n>.txt`.
3. Persistence: add `record_orchestration(session_dict)` /
   `get_orchestrations()` / `delete_orchestration(session_id)` to
   `tui/memory.py`, stored beside tasks in `.daedalus-memory.json` with a
   `schema_version`. Worker task snapshots gain optional `session_id` and
   `card_id` fields (pass-through in `record_task`).
4. Restart behavior: a session restored from memory with active cards is
   marked `stopped` with a clear message; its worker tasks are restored by the
   existing task recovery as `interrupted`. No session auto-resumes.

Tests: `tests/test_orchestrate_session.py` (directory layout, card round trip
including ticks, digest bounding, memory round trip with schema version).

Completion check: a session can be created, its cards written, one card placed
in a temporary directory, ticked by hand, and read back correctly.

---

## Section 4 — Orchestrator changes for roles

Depends on: 2 (report parsing), 3 (card placement). Blocks: 5.

1. `LocalOrchestrator.run` accepts mode `"orchestrate-plan"`: treated like
   `plan` (planning profile route, worktree reset to base, no commit,
   `awaiting_plan`-style return) but the returned `OrchestrationResult` carries
   the raw agent output so the dispatcher can parse the payload. Add
   `planner_output: str | None` to `OrchestrationResult`.
2. Add optional constructor arguments to `LocalOrchestrator`:
   - `resolver_selection: tuple[str, str, str] | None` — when set,
     `resolve_integration` and post-merge repair prompts use it instead of the
     task selection. The dispatcher passes the planner selection here.
   - `before_agent: Callable[[WorktreeContext], None] | None` — invoked once
     after provisioning and before the first agent run; the dispatcher uses it
     to place the card in the worktree.
   - `after_agent: Callable[[WorktreeContext, AgentResult], None] | None` —
     invoked after the coding agent finishes and before the commit; the
     dispatcher reads the ticked card here (it is still present because the
     directory is a runtime artifact and is not staged).
3. `build_task_prompt` gains an `orchestrate_card: str | None` parameter that,
   when set, delegates to `build_worker_prompt` and ignores `resume_notes`
   history except the resumption sentence. `TaskCoordinator.submit` gains
   `session_id`, `card_id`, and `card_markdown` keyword arguments stored on
   `TaskRecord` and passed down so `_turn_prompt` produces the worker prompt.
4. Repair prompts for worker tasks (verification, migration, Firebase) keep the
   worker selection but embed the card instead of the original prompt, so a
   repair agent still sees only its task.
5. Event phases: worker events keep their existing phases; the dispatcher
   translates task events into card status changes.

Tests: `tests/test_orchestrator.py` gains tests for `orchestrate-plan` mode
(worktree reset, output captured), resolver selection override (fake runner
records the model per request), and the before/after hooks being called with
the worktree path. `tests/test_task_coordinator.py` covers `submit` with a
card producing a worker prompt without the operator prompt.

Completion check: with a fake runner, one planner run returns its raw output
and one worker run sees the card file in its worktree and runs the resolver
with the planner model when a merge conflict is scripted.

---

## Section 5 — Dispatcher: planner rounds, worker scheduling, failure loop

Depends on: 2, 3, 4. Blocks: 6 (real data), 7.

1. Create `tui/orchestrate_coordinator.py` with `OrchestrateCoordinator`
   (one per project, owned by the app beside the `TaskCoordinator`):
   - `__init__(task_coordinator, runner, orchestration_settings, orchestrate_settings, storage, memory, on_event)`.
   - `start(prompt, planner_selection, worker_selection, max_workers, topic=None) -> OrchestrationSession`.
   - `stop(session_id)`: interrupts active worker tasks through the existing
     `TaskCoordinator.interrupt` and marks the session `stopped`.
   - `sessions()`, `get(session_id)`, `delete(session_id)`.
2. Session loop, run on one dedicated thread per session (never inside the
   task executor, which the workers need):
   1. `planning`: run the planner through `LocalOrchestrator` in
      `orchestrate-plan` mode; parse the payload; on invalid payload, one
      corrective planner round with the parse error; on second failure the
      session is `failed`. Write plan and cards.
   2. `dispatching`: compute `ready_tasks`; submit up to
      `max_workers - active` of them as coding tasks with their cards. The
      worker count is a session-level cap that must also respect
      `max_concurrent_tasks` of the task coordinator (effective cap is the
      smaller); surface that in the session log when it binds.
   3. `waiting`: block on worker completion events. On `completed`
      (promoted): mark `promoted`, record the commit, record ticks. On
      `failed` or `interrupted`: record the report and error, mark `failed`.
      On `paused`: treat as `stopped` for the card.
   4. When no card is `running` and either a card failed or all are settled,
      run a planner round with the digest. Apply the returned payload: new
      cards are added; a card marked `reissues` increments the original's
      `reissue_count` (refusing beyond `task_reissue_limit`); `done=true`
      finishes the session as `completed` only if every card is `promoted`
      or explicitly abandoned by the planner in `summary`.
   5. Stop when `planner_round_limit` is reached: status `failed` with the
      digest as the error.
   - `resolving` is shown while any worker task is inside the integration
     gate with a resolver running; it is derived from worker events, not a
     separate step.
3. Token accounting: planner and worker tokens are summed separately from
   `OrchestrationResult.tokens_consumed` and `TaskRecord.tokens_consumed`, and
   persisted on the session. Also record the number of characters sent per
   worker prompt so the UI can show the context saving.
4. Persistence: call `SessionStore` and `memory.record_orchestration` after
   every state change; snapshots are what the UI renders after restart.
5. Shutdown: `shutdown()` marks running sessions `stopped`, then defers to
   the task coordinator's existing shutdown so worker subprocesses stop.

Tests: `tests/test_orchestrate_coordinator.py` with a scripted fake runner that
returns, in order, a planner payload with three cards (t3 depends on t2), a
successful worker report for t1, a failed worker run for t2, a planner round
that re-issues t2 as t4, successful reports for t4 and t3, then `done=true`.
Assert: dispatch order, that at most `max_workers` workers were active at
once, that t3 started only after t2's replacement promoted, that the resolver
selection is the planner's, the final status, and that the worker prompts
never contained the operator prompt.

Completion check: the scripted scenario above completes with
`status == "completed"` and the expected card states.

---

## Section 6 — Orchestrate Mode UI

Depends on: 1 (settings), 3 (session shapes), 5 (coordinator API; build
against a stub until it lands).

1. Task bar: add `Button("Orchestrate Mode", id="orchestrate-mode-button")`
   next to New Task. Add `("Ctrl+O", "Toggle Orchestrate Mode", "toggle_orchestrate_mode")`
   to `GLOBAL_SHORTCUTS`.
2. Wrap the existing project main content (everything below the task bar in
   `_compose_project_main`) in a `ContentSwitcher(id="view-switcher")` with
   two children: `Vertical(id="tasks-view")` (existing widgets, unchanged ids)
   and `Vertical(id="orchestrate-view")`. The task sidebar and output viewer
   stay outside the switcher so worker tasks remain visible in the inbox. The
   button label flips to `Task Mode` while the orchestrate view is shown.
   Re-check `_wide_controls_overflow` and the compact layout so the extra
   button does not clip; add the new selects to the compact category picker.
3. Orchestrate view contents, top to bottom:
   - Role row: `Static("Planner")`, `Select(id="planner-model-select")` from
     `settings.models_for("claude")` defaulting to the parameter file's
     planner model; `Static("Worker")`, `Select(id="worker-model-select")`
     defaulting to the worker model; `Input(id="max-workers-input")` with
     integer validation `1..max_workers_limit`, default
     `default_max_workers`. Provider is fixed to the parameter file's provider
     for now (both Claude); the layout leaves room for a provider select later.
   - Prompt: `DaedalusVimTextArea(id="orchestrate-prompt")` with the same
     draft autosave as the composer (own draft key `orchestrate`).
   - Actions: `Start` (`#orchestrate-start-button`, primary), `Stop`
     (`#orchestrate-stop-button`, error, disabled when idle), and a status
     `Static`.
   - Board: `DataTable(id="orchestrate-board")` with columns Card, Title
     (width `board_title_width`), Status, Checklist (`3/4`), Worker task,
     Tokens. Selecting a row focuses the worker task in the inbox and the
     transcript panel, reusing `_focus_task`.
   - Planner log: `TranscriptLog(id="planner-log")` bounded to
     `planner_log_lines`, showing planner output, digests, and dispatch
     decisions. The Markdown viewer shows the current `PLAN.md` when the
     orchestrate view is active and a session is selected.
   - Summary line: planner tokens, worker tokens, total, and "context sent to
     workers: N chars over M tasks".
4. App wiring: create one `OrchestrateCoordinator` per project in
   `_coordinator_for`; route `orchestrate` phase events through the existing
   `_on_task_event` queue; refresh the board on session events; persist the
   view choice in `memory.set_ui_preference("orchestrate_view", …)`. Worker
   task rows in the inbox show a `⋯` marker or the card id in the project
   column so the operator can tell them apart from ordinary tasks.
5. Interrupts: `Ctrl+C` in the orchestrate view stops the session (not just
   one worker). `Ctrl+Q` flushes the orchestrate draft.
6. Styling in `tui/app.tcss` for the role row, board height, and log height;
   compact mode stacks the role row vertically.

Tests: `tests/test_app.py` gains compose tests (button present, switcher
toggles, defaults are Fable and Opus, max-workers validation), a session-event
rendering test with a stub coordinator, and a compact-layout test.

Completion check: the view toggles with the button and `Ctrl+O`, Start submits
to the coordinator with the chosen models and worker count, and the board
reflects a stubbed session.

---

## Section 7 — Integration tests, documentation, and profile updates

Depends on: all previous sections.

1. End-to-end test in `tests/test_orchestrate_end_to_end.py`: real temporary
   Git repository, fake runner that edits files according to the card and
   returns reports, `max_workers=2`, three cards with one dependency; assert
   the operating branch contains all three promotions in dependency order and
   that no `.daedalus-orchestration/` path was ever committed.
2. Conflict test: two independent cards scripted to touch the same line; the
   parser should have rejected that plan, so script the conflict via a card
   whose fake worker edits outside its scope and assert the resolver ran with
   the planner model and the session still completed.
3. README: new "Orchestrate Mode" section describing roles, defaults, the
   max-workers control, where session files live, and the context-minimization
   rule. Keep it as short as the topics section.
4. Feature file `## State Log` entries for each landed section; update
   `## Relevant Files` to the final module list. Add one State Log line to
   `feature_files/daedalus-tui-orchestration.md` noting the resolver
   selection override and the before/after agent hooks it now exposes.
5. Profiles: add one paragraph to `.agents/profiles/coding.md` and
   `tui/templates/project-initializer/.agents/profiles/coding.md` stating that
   a task carrying `.daedalus-orchestration/task.md` is a worker task, the
   card is authoritative for scope, and the report payload is required.
6. Keyboard shortcuts screen lists `Ctrl+O`.

Completion check: the full test suite passes with the end-to-end scenario, and
the README and feature files describe what shipped.

---

## Suggested assignment for concurrent agents

| Wave | Sections that can run at the same time | Notes |
| --- | --- | --- |
| 1 | 1, 2 | Independent. Section 2 uses literal budget constants until Section 1 lands. |
| 2 | 3, 4, 6 (scaffold) | 3 and 4 need 2. Section 6 can build the view, selects, board, and toggling against a stub coordinator with the Section 0 shapes. |
| 3 | 5 | Needs 3 and 4. |
| 4 | 6 (wiring), 7 | 6 wires the real coordinator; 7 runs once everything is merged. |

Each section's agent should read only its own section, Section 0, and the
files it names. That is the same context rule the feature itself enforces.

## Out of scope for this iteration

- Choosing non-Claude providers per role (the layout reserves space; the
  parameter file already keys provider per role).
- Resuming a session after a TUI restart (sessions restore as `stopped`).
- Planner-driven topic or feature-file edits (workers follow the existing
  coding profile rules for feature-file State Log lines).
- Cross-project sessions.
