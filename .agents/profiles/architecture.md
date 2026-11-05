# Execution Boundaries (CRITICAL)

- NEVER EXECUTE SOURCE CODE (python, bash, node, script tasks) without
  explicit standalone user permission in the current turn. Scrapers, tests,
  skill plugins (including Graphify), research, and directory listing are
  permitted.
- NEVER implement CLI/Command Line Arguments (`--input`, `--mode`). Hardcode
  configurations directly into variables for manual tweaking.

# Evidence Extraction

Use Graphify and the feature-file system to obtain semantic and relational
understanding of the TUI. Use `git diff` to inspect relevant changes.

# Architecture Boundaries

- Feature files are read-only in architecture mode.
- A feature owns only the logic, configuration, and behavior it directly
  implements. Cross-feature references should describe interfaces and
  relationships rather than duplicate dependency internals.
- Keep the TUI independently exportable and do not introduce dependencies on
  the parent Daedalus daemon, site, database, or Supabase.

# Parameter Files

Parameter files are read-only in architecture mode. Tunable values belong in
the parameter file of the feature responsible for interpreting them. Do not
put API keys in parameter files.

# Development Lifecycle

The four stages are HACKING, TESTING, PRODUCTION-READY, and DEBUGGING. Do not
autonomously change a feature's stage.

## Personal Supabase Schema

This project uses a dedicated Postgres schema `daedalus-tui` on the operator's shared personal Supabase database. Do **not** use the default `public` schema for application tables or migrations.

- Read the schema name from `SUPABASE_SCHEMA` in `.env` (expected value: `daedalus-tui`).
- Qualify SQL, migrations, RLS policies, and client/API configuration for `daedalus-tui`.
- Never assume PostgREST or Supabase clients default to `public` for this app.
- Auth is shared across apps on this Supabase project; reuse the existing auth setup.
- Agents must not run `supabase db push`; orchestration owns remote migration apply after verification when `supabase/migrations/` changes.
- After the first remote apply, the operator must allow-list this schema in the Supabase Dashboard Data API / PostgREST exposed-schemas settings.
