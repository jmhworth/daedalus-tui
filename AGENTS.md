# Daedalus TUI Project Instructions

This repository is the standalone Daedalus TUI project. It contains the
Textual application, local agent execution, Git worktree orchestration,
verification, and tests. It does not depend on the Daedalus daemon, database,
Supabase, or remote Git operations.

## Task mode

The prompt should declare modes, such as:

    TASK_MODE: coding
    TASK_MODE: planning
    TASK_MODE: integrating
    TASK_MODE: architecture
    TASK_MODE: bridge

The orchestration layer may provide the selected profile inline in the prompt.
When an inline profile is present, apply its contents directly; do not open the
profile file merely to read it again. If no inline profile is supplied, read the
corresponding profile from the active worktree. The standard routes are
`coding` -> `.agents/profiles/coding.md`, `plan` ->
`.agents/profiles/planning.md`, and `integrating` ->
`.agents/profiles/integrating.md`.

If no task mode is supplied, default to `coding`, unless there is an obvious
mode that fits better.

Do not read unrelated profiles.

## Project boundaries

- Keep the TUI independently exportable; do not add imports from the parent
  Daedalus daemon or site.
- The TUI may launch against other repositories. Those target repositories
  have their own instructions and feature files; this `AGENTS.md` governs the
  TUI repository itself.
- Task agents edit files only. The orchestration layer owns staging, commits,
  merges, worktree cleanup, and graph refreshes.
- Keep feature context in `feature_files/` and tunable settings in the paired
  `parameter_files/` directory.
- Optional topic umbrellas live in `topic_files/` (shared recurrent memory for
  related tasks); not every task needs a topic.

## Orchestrate Mode

A task whose worktree contains `.daedalus-orchestration/task.md` is a worker
task in an Orchestrate Mode session. That card is authoritative: do exactly
what it says, stay inside its file scope, tick its checklist items as you
finish them, and return the required report payload. The full role rules are
bundled at `tui/templates/orchestrate/AGENTS.md`; they are embedded inline in
planner and worker prompts, so there is no need to open that file.

## graphify

This project has a knowledge graph at `graphify-out/` with community structure
and cross-file relationships.

When the user types `/graphify`, use the installed Graphify skill or
instructions before doing anything else.

Rules:

- For codebase questions, first run `graphify query "<question>"` when
  `graphify-out/graph.json` exists. Use `graphify path "<A>" "<B>"` for
  relationships and `graphify explain "<concept>"` for focused concepts.
- Dirty `graphify-out/` files are expected after hooks or incremental updates;
  dirty graph files are not a reason to skip Graphify.
- If `graphify-out/wiki/index.md` exists, use it for broad navigation instead
  of raw source browsing.
- Read `graphify-out/GRAPH_REPORT.md` for broad architecture review or when a
  focused query does not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current.
