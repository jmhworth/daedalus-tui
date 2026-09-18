# Execution Boundaries (CRITICAL)

- NEVER EXECUTE SOURCE CODE (python, bash, node, script tasks) without
  explicit standalone user permission in the current turn. Scrapers, tests,
  skill plugins (including Graphify), research, and directory listing are
  permitted.
- NEVER implement CLI/Command Line Arguments (`--input`, `--mode`). Hardcode
  configurations directly into variables for manual tweaking.

# Feature File Automation

- Use feature files to track feature context, important bugs fixed, and design
  philosophies.
- Feature files and Graphify coexist: Graphify describes where things exist;
  feature files describe why things exist.
- Track active progress in `feature_files/{feature_name}.md`. If missing,
  auto-generate on task initialization.
- A feature owns only the logic, configuration, and behavior it directly
  implements. Files that are merely called, launched, imported, orchestrated,
  or referenced are dependencies.
- Cross-feature references should describe the interface or relationship, not
  duplicate the dependency's internal configuration.
- Feature files use this schema: H1 title, `## Summary`, `## Key Points`,
  `## Relevant Files`, `## Dev Mode`, and `## State Log`.
- Append a one-sentence engineering log to the `State Log` before marking a
  task complete.

# Topics (when tagged)

- Topics under `topic_files/` are optional umbrellas for closely related
  tasks. Feature files remain the per-feature "why"; topics hold cross-feature
  shared memory.
- When a topic is embedded in the prompt, follow the injected topic
  instructions: keep **Topic Goal** immutable unless the user explicitly asks
  to change it; keep **Topic Status** minimal (`open` | `complete`); append
  one concise, topic-scoped **State Log** entry after completing a coding
  task.
- Concurrent tasks on the same topic may race on State Log appends the same
  way concurrent feature-file edits can.

# Parameter File Centralization

Each feature file must have a corresponding parameter file (`.toml`) in the
sibling `parameter_files/` directory. Parameter files are read-only sources
of truth for tunable configuration; source code may read them but must not
write runtime state back to them.

Keep parameters with the feature responsible for interpreting and acting on
them. Do not recreate another feature's internal settings in an orchestration
feature. Do not move every implementation constant into a parameter file.

Never put API keys in parameter files.

# 4-Stage Development Lifecycle

Adhere to the active feature file's `Dev Mode` and do not autonomously upgrade
it:

1. **HACKING**: Prototype phase; prioritize readable, direct implementation.
2. **TESTING**: Incremental hardening with structured tests and validation.
3. **PRODUCTION-READY**: Robust validation, edge-case coverage, and optimized
   structure.
4. **DEBUGGING**: Deep diagnostics, granular event logging, and execution
   tracing.

# Debugging

Every suspected root cause must include supporting evidence: file path,
relevant line numbers, and function names.

## Personal Supabase Schema

This project uses a dedicated Postgres schema `daedalus-tui` on the operator's shared personal Supabase database. Do **not** use the default `public` schema for application tables or migrations.

- Read the schema name from `SUPABASE_SCHEMA` in `.env` (expected value: `daedalus-tui`).
- Qualify SQL, migrations, RLS policies, and client/API configuration for `daedalus-tui`.
- Never assume PostgREST or Supabase clients default to `public` for this app.
- Auth is shared across apps on this Supabase project; reuse the existing auth setup.
- Agents must not run `supabase db push`; orchestration owns remote migration apply after verification when `supabase/migrations/` changes.
- After the first remote apply, the operator must allow-list this schema in the Supabase Dashboard Data API / PostgREST exposed-schemas settings.

# Orchestrate Mode worker cards
A task whose worktree contains `.daedalus-orchestration/task.md` is a worker task in an Orchestrate Mode session. That card is authoritative for scope: do exactly what it says, stay inside its file scope, tick its checklist items as you finish them, and end your response with the required `BEGIN_DAEDALUS_WORKER_REPORT` payload. The card directory is Daedalus bookkeeping and is never committed.
