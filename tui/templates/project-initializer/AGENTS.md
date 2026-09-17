# Daedalus Project Instructions

This repository supports coding and non-coding work.

## Task mode

The prompt should declare modes, such as:

    TASK_MODE: coding
    TASK_MODE: planning
    TASK_MODE: integrating
    TASK_MODE: architecture

Read the corresponding profile:

    .agents/profiles/<TASK_MODE>.md

If no task mode is supplied, default to `coding`, unless there is an obvious mode that fits better (e.g. "There was a problem merging the git worktrees, go ahead and resolve the conflicts to the main branch" is more likely integrating than coding)

Do not read unrelated profiles.

Do not automatically read every file under `.agents/`.

## Topics

Optional topic umbrellas live in `topic_files/`. Not every task needs a topic.
When a task is tagged with a topic, follow the topic markdown and any
inline topic instructions supplied in the prompt (State Log as shared memory,
immutable Topic Goal unless the user asks otherwise, minimal Topic Status).

## Orchestrate Mode

A task whose worktree contains `.daedalus-orchestration/task.md` is a worker
task in an Orchestrate Mode session: a planner agent split one request into
small cards and gave you one of them. The card is authoritative. Do exactly
what it says, stay inside its file scope, tick its checklist items (`- [x]`) as
you finish them, and return the required report payload. Daedalus embeds the
full role rules in your prompt, so do not go looking for them.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
