# Daedalus TUI Personal Shared Supabase

## Summary
Opt-in registration that scaffolds a dedicated Postgres schema for a Daedalus-managed
target project inside one operator-owned shared Supabase database. Registration is
file-only (`supabase/` config + `CREATE SCHEMA` migration, `.env.example`, coding and
architecture profile guidance, and a `.daedalus` marker); orchestration continues to
own remote `supabase db push` after verification.

## Key Points
- **Shared database, per-project schema**: Schema identity is always the validated
  project slug. Apps share auth on the single Supabase project; agents must never
  default to `public`.
- **File-only register**: Writes durable project files only. Does not call the Supabase
  Management API or `supabase db push` at register time.
- **New Project opt-in**: Checkbox on the New Project modal; when selected, a separate
  confirmation requires typing the project name before registration runs after template
  materialization and before the initial `git add`/`git commit`.
- **Existing-project action**: Task-bar button beside New Project / Create Topic opens the
  same confirmation, requiring the selected project's name before scaffolding the schema;
  it disables once registered for that schema.
- **Deliberate linking**: The confirmation warns that registration joins the operator's
  internal shared-Supabase ecosystem, and the Register action remains disabled until the
  exact project name is entered.
- **Agent teaching**: Idempotently appends a Personal Supabase Schema section to
  `.agents/profiles/coding.md` and `architecture.md` (no Cursor skill file).
- **Env placeholders**: Only the target project's `.env.example` gets shared URL/key
  placeholders plus `SUPABASE_SCHEMA=<slug>` and a Data API allow-list reminder.
- **Idempotency / conflicts**: Same-schema re-register is a no-op success; conflicting
  markers or foreign `supabase/migrations` content fail without mutating the tree.
- **Manual API exposure**: Operators must allow-list the schema in Supabase Dashboard
  Data API / PostgREST settings after the migration is applied remotely.
- **Orchestration boundary**: Existing `supabase_db_push_enabled` verify→push path is
  unchanged; this feature only materializes migrations when opted in.

## Relevant Files
- `tui/personal_supabase.py`: Registration helper, marker I/O, env/profile/migration scaffolding.
- `tui/project_initializer.py`: Optional `registerPersonalSupabase` flag wired pre-commit.
- `tui/app.py`: New Project checkbox, confirmation modal, and task-bar Register Supabase Schema button.
- `parameter_files/daedalus-tui-personal-supabase.toml`: Snippet version, env key names, migration filename.
- `tests/test_personal_supabase.py`, `tests/test_app.py`, `tests/test_project_initializer.py`: Coverage.

## Dev Mode
HACKING

## State Log
- 2026-09-13: Added file-only personal Supabase schema registration with New Project checkbox, task-bar button, profile guidance, and target `.env.example` placeholders.
- 2026-09-13: Added an exact-project-name confirmation gate to both registration entry points so shared-Supabase linking is always deliberate.
