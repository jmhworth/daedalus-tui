# Daedalus TUI Personal Shared Supabase

## Summary
Opt-in registration that scaffolds a dedicated Postgres schema for a Daedalus-managed
target project inside one operator-owned shared Supabase database. Registration is
file-only (`supabase/` config + `CREATE SCHEMA` migration, `.env.example`, coding and
architecture profile guidance, and a `.daedalus` marker). At launch Daedalus uses the
launch-root `.env` as the canonical shared source, synchronizes each registered
project's ignored `.env`, and asks orchestration to push its migration.

## Key Points
- **Shared database, per-project schema**: Schema identity is always the validated
  project slug. Apps share auth on the single Supabase project; agents must never
  default to `public`.
- **File-only register**: Writes durable project files only. Does not call the Supabase
  Management API or `supabase db push` at register time; launch bootstrap owns preparation
  and orchestration remains the only remote push owner.
- **New Project opt-in**: Checkbox on the New Project modal; when selected, a separate
  confirmation requires typing the project name before registration runs after template
  materialization and before the initial `git add`/`git commit`.
- **Existing-project action**: The `Ctrl+Shift+S` shortcut opens the same
  confirmation, requiring the selected project's name before scaffolding the
  schema; repeated registration remains a no-op for that schema.
- **Deliberate linking**: The confirmation warns that registration joins the operator's
  internal shared-Supabase ecosystem, and the Register action remains disabled until the
  exact project name is entered.
- **Agent teaching**: Idempotently appends a Personal Supabase Schema section to
  `.agents/profiles/coding.md` and `architecture.md` (no Cursor skill file).
- **Canonical environment**: The launch-root `.env` owns `SUPABASE_PROJECT_REF`, shared
  URL and keys, and database access (`SUPABASE_DB_URL` or `SUPABASE_ACCESS_TOKEN`). Each
  ignored project `.env` receives those values plus only its own `SUPABASE_SCHEMA` marker;
  populated conflicts are refused and process variables remain runtime-only overrides.
- **Secret-free examples**: Root and generated project `.env.example` files contain names,
  blanks, and guidance only; credentials never belong in feature or parameter files.
- **Idempotency / conflicts**: Same-schema re-register is a no-op success; conflicting
  markers or foreign `supabase/migrations` content fail without mutating the tree.
- **Manual API exposure**: Operators must allow-list the schema in Supabase Dashboard
  Data API / PostgREST settings after the migration is applied remotely.
- **Launch bootstrap**: Every discovered registered project is synchronized and pushed at
  launch when `supabase_db_push_enabled` is enabled, without consulting `migrations_pending`.
  Disabled pushes still synchronize local ignored environments. Bootstrap is idempotent,
  redacts diagnostics, and temporarily supplies the shared project ref to the CLI without
  leaving tracked placeholder configuration dirty.

## Relevant Files
- `tui/personal_supabase.py`: Registration helper, marker I/O, canonical environment bootstrap,
  scaffold validation, and temporary CLI configuration.
- `tui/environment.py`: Comment-preserving atomic `.env` synchronization and runtime loading.
- `tui/project_initializer.py`: Optional `registerPersonalSupabase` flag wired pre-commit.
- `tui/app.py`: New Project checkbox, confirmation modal, and the
  `Ctrl+Shift+S` Register Supabase Schema shortcut.
- `parameter_files/daedalus-tui-personal-supabase.toml`: Env key definitions, required shared
  settings, and migration filename.
- `tests/test_personal_supabase.py`, `tests/test_app.py`, `tests/test_project_initializer.py`: Coverage.

## Dev Mode
HACKING

## State Log
- 2026-09-13: Added launch-root canonical environment synchronization and idempotent bootstrap preparation for all discovered registered projects.
- 2026-09-13: Added file-only personal Supabase schema registration with New Project checkbox, task-bar button, profile guidance, and target `.env.example` placeholders.
- 2026-09-13: Added an exact-project-name confirmation gate to both registration entry points so shared-Supabase linking is always deliberate.
- 2026-09-14: Moved existing-project schema registration from the task bar to the `Ctrl+Shift+S` shortcut.
