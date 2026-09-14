# Daedalus TUI Personal Shared Supabase

## Summary
Two-phase personal Supabase support for Daedalus-managed target projects on one
operator-owned shared database. Phase 1 scaffolds durable project files so
humans and agents can develop against a dedicated schema. Phase 2 (Activate)
is software-owned Daedalus ecosystem readiness: commit the scaffold onto the
already-checked-out operating branch, live-preflight Supabase connectivity, and
orchestration-owned `supabase db push`. File scaffolding alone is not
ecosystem-ready.

## Key Points
- **Shared database, per-project schema**: Schema identity is always the validated
  project slug. Apps share auth on the single Supabase project; agents must never
  default to `public`.
- **Phase 1 — Scaffold**: Writes durable project files only (`supabase/` config +
  `CREATE SCHEMA` migration, `.env.example`, coding/architecture profile guidance,
  and a `.daedalus` marker with `registered=true`, `activated=false`). Does not
  claim ecosystem readiness.
- **Phase 2 — Activate**: Operator `F4` after name confirmation runs
  scaffold (when unregistered) then Activate when gates pass: require HEAD already
  on the selected operating/target branch (no checkout/switch), refuse unrelated
  dirty files, software-owned local commit of known scaffold paths + marker, launch-root
  env sync, access-method-aware live preflight, then `db push`. Remote Git publish
  remains the optional operator Push button.
- **Existing projects only**: Personal Supabase is post-init for projects already
  in the Daedalus format. New Project has no personal-Supabase opt-in.
- **Retry**: Scaffolded or Activate-blocked projects reuse `F4` with the
  same name confirmation; skip re-scaffold when registered, validate completeness,
  and re-run Phase 2. Incomplete scaffolds fail closed.
- **Status model**: Distinguish unregistered, scaffolded (`registered`, not
  `activated`), activated, and blocked reasons (`last_activate_status` /
  redacted error class—no credentials). Launch env-syncs all registered projects;
  launch `db push` runs only for activated projects when `supabase_db_push_enabled`.
- **Supabase connected**: Launch-root required keys + one DB access method
  (`SUPABASE_DB_URL` or `SUPABASE_ACCESS_TOKEN`), `supabase` on PATH, and a
  bounded non-destructive access-method-aware reachability probe before push.
- **Deliberate linking**: Confirmation warns about scaffold + Activate prerequisites;
  the Activate action stays disabled until the exact project name is entered.
- **Agent teaching**: Idempotently appends a Personal Supabase Schema section to
  `.agents/profiles/coding.md` and `architecture.md` (no Cursor skill file).
- **Canonical environment**: The launch-root `.env` owns shared connection values;
  each ignored project `.env` receives those plus `SUPABASE_SCHEMA`.
- **Manual API exposure**: Operators must allow-list the schema in Supabase Dashboard
  Data API / PostgREST settings after the migration is applied remotely.
- **Ownership**: Agents never `db push` or push remotes; software owns Activate
  commits and migration push.

## Relevant Files
- `tui/personal_supabase.py`: Scaffold helper, marker I/O, Git gate/commit, live
  preflight, Activate orchestration, canonical environment bootstrap, and temporary
  CLI configuration.
- `tui/environment.py`: Comment-preserving atomic `.env` synchronization and runtime loading.
- `tui/app.py`: Confirmation modal, activation progress modal, and `F4` scaffold+Activate / retry worker.
- `tui/supabase_migrations.py`: Orchestration-owned non-interactive `db push`.
- `parameter_files/daedalus-tui-personal-supabase.toml`: Env keys, confirmation copy,
  activate commit message, and preflight timeout.
- `tests/test_personal_supabase.py`, `tests/test_app.py`: Coverage.

## Dev Mode
HACKING

## State Log
- 2026-09-14: Renamed the progress modal's activation-state flag to avoid colliding with Textual's internal message-pump lifecycle field, restoring modal composition and completion rendering.
- 2026-09-14: Redesigned personal Supabase into Phase 1 scaffold plus Phase 2 Activate with operating-branch Git gate, live preflight, activated-only launch push, and F4 retry; removed New Project opt-in.
- 2026-09-13: Added launch-root canonical environment synchronization and idempotent bootstrap preparation for all discovered registered projects.
- 2026-09-13: Added file-only personal Supabase schema registration with New Project checkbox, task-bar button, profile guidance, and target `.env.example` placeholders.
- 2026-09-13: Added an exact-project-name confirmation gate to both registration entry points so shared-Supabase linking is always deliberate.
- 2026-09-14: Moved existing-project schema registration from the task bar to the `F4` shortcut.
- 2026-09-14: Added a non-dismissible-during-work activation progress modal with scaffold, Git, environment, connectivity, migration, completion, blocked, and already-activated states.
- 2026-09-14: Deferred activation until the confirmation modal is popped and buffered fast worker updates until the progress modal is mounted.
