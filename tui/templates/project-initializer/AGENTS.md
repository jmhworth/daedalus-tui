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

## Shared personal Supabase

If this project has a `[personal_supabase]` registration in `.daedalus`, store
application data in its registered schema (the project's validated slug), never
in `public`. Activate copies the API URL and keys from the Daedalus TUI root
`.env` into a managed block at the end of this project's ignored `.env`; the
TUI root remains the credential source of truth. Put all migration SQL in the
project's `daedalus-migrations/` directory, named
`<YYYYMMDDHHMM>_<schema>_<description>.sql`. Do not create a project-local
`supabase/` directory or run `supabase db push`. The Daedalus TUI copies these
migrations into its root `supabase/migrations/` directory and handles schema
operations after verification or Activate. Use the registered schema explicitly
in client queries, RLS policies, and SQL. Use publishable keys in browser
clients; keep secret/service-role keys server-side. Never commit credentials.

## Topics

Optional topic umbrellas live in `topic_files/`. Not every task needs a topic.
When a task is tagged with a topic, follow the topic markdown and any
inline topic instructions supplied in the prompt (State Log as shared memory,
immutable Topic Goal unless the user asks otherwise, minimal Topic Status).

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
