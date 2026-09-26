# Daedalus TUI Personal Shared Supabase

## Summary
Two-phase personal Supabase support for Daedalus-managed target projects on one
operator-owned shared database. Phase 1 scaffolds durable project files so
humans and agents can develop against a dedicated schema. Phase 2 (Activate)
is software-owned Daedalus ecosystem readiness: commit the scaffold onto the
already-checked-out operating branch, live-preflight Supabase connectivity, and
orchestration-owned `supabase db push`. File scaffolding alone is not
ecosystem-ready. Operators set each project's credentials manually via a setup
wizard; Daedalus never copies credentials between project `.env` files.

## Key Points
- **Shared database, per-project schema**: Schema identity is always the validated
  project slug. Apps share auth on the single Supabase project; agents must never
  default to `public`.
- **Project-local credentials**: Prefer `SUPABASE_URL`,
  `SUPABASE_PUBLISHABLE_KEY`, and `SUPABASE_SECRET_KEY` (Supabase's new API key
  names). Legacy `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` and
  `SUPABASE_PRIVATE_KEY` (secret alias) still resolve. `SUPABASE_PROJECT_REF` is
  optional when the URL is `https://<ref>.supabase.co`.
- **Database access is separate from API keys**: Activate / `db push` still need
  one of `SUPABASE_DB_URL` or `SUPABASE_ACCESS_TOKEN`; publishable/secret keys
  cannot apply SQL migrations.
- **Phase 1 — Scaffold**: Writes durable project files only (`supabase/` config +
  `CREATE SCHEMA` migration, `.env.example`, coding/architecture profile guidance,
  and a `.daedalus` marker with `registered=true`, `activated=false`). Does not
  claim ecosystem readiness.
- **Setup wizard**: After name confirmation, Register opens a setup wizard that
  scaffolds files, then instructs the operator to set the active project's
  ignored `.env` values and shows the absolute path of that file. Continue runs
  `python -m tui.env_presence_probe` with cwd = the project root and gates on
  the child exit code (key-name diagnostics only; secret values stay in the child).
  Missing credentials keep the wizard open with an "Environment variables still
  not detected" correction that repeats the checked path. Daedalus does not
  write `.env` files.
- **Phase 2 — Activate**: After the wizard succeeds, the software runs Activate when
  gates pass: require HEAD already on the selected operating/target branch (no
  checkout/switch), refuse unrelated dirty files, software-owned local commit of
  known scaffold paths + marker, project-local env validation (read-only),
  access-method-aware live preflight, then `db push`. Remote Git publish remains
  the optional operator Push action in the Command Menu.
- **Existing projects only**: Personal Supabase is post-init for projects already
  in the Daedalus format. New Project has no personal-Supabase opt-in.
- **Retry**: Scaffolded or Activate-blocked projects reuse the Command Menu (`Ctrl+K`) with the
  same name confirmation and setup wizard; skip re-scaffold when registered, validate
  completeness, and re-run Phase 2. Incomplete scaffolds fail closed.
- **Local cleanup**: The Command Menu also offers an exact-name-confirmed debug
  cleanup that removes the local `supabase/` directory and generated integration
  content while preserving unrelated `.daedalus`, profile, and environment values;
  it never changes the remote database.
- **Status model**: Distinguish unregistered, scaffolded (`registered`, not
  `activated`), activated, and blocked reasons (`last_activate_status` /
  redacted error class—no credentials). Launch validates all registered projects;
  launch `db push` runs only for activated projects when `supabase_db_push_enabled`.
- **Supabase connected**: Project-local required API settings + one DB access method
  (`SUPABASE_DB_URL` or `SUPABASE_ACCESS_TOKEN`), `supabase` on PATH, and a
  bounded non-destructive access-method-aware reachability probe before push.
  For canonical direct database hosts, activation checks the host project ref
  against `SUPABASE_URL` and gives a DNS-specific correction when resolution fails.
- **Deliberate linking**: Confirmation warns about scaffold + Activate prerequisites;
  the Activate action stays disabled until the exact project name is entered.
- **Agent teaching**: Idempotently appends a Personal Supabase Schema section to
  `.agents/profiles/coding.md` and `architecture.md` (no Cursor skill file).
- **Canonical environment**: Each project's ignored `.env` owns its connection
  values; orchestration reads that file for personal-Supabase validation and CLI
  overlays (broader agent env loading may still apply process overrides
  elsewhere). The Register wizard presence gate probes only the active project's
  file via child exit code. Project `.env.example` documents placeholders;
  Daedalus never syncs credentials between project `.env` files.
- **Manual API exposure**: Operators must allow-list the schema in Supabase Dashboard
  Data API / PostgREST settings after the migration is applied remotely.
- **Ownership**: Agents never `db push` or push remotes; software owns Activate
  commits and migration push.

## Relevant Files
- `tui/personal_supabase.py`: Scaffold helper, marker I/O, local cleanup, Git
  gate/commit, live preflight, Activate orchestration, project-local env validation,
  child-process env presence probe, and temporary CLI configuration.
- `tui/env_presence_probe.py`: Project-root cwd child entry that exits 0/1 after
  resolving required Supabase keys (stderr key names only).
- `tui/environment.py`: Comment-preserving `.env` reading/loading helpers (no
  personal-Supabase credential writes); BOM-safe parse and process overrides.
- `tui/app.py`: Command Menu, confirmation modal, setup wizard, activation progress
  modal, and scaffold+Activate / retry worker.
- `tui/supabase_migrations.py`: Orchestration-owned non-interactive `db push`.
- `parameter_files/daedalus-tui-personal-supabase.toml`: Env keys, confirmation and
  wizard copy, activate commit message, and preflight timeout.
- `tests/test_personal_supabase.py`, `tests/test_app.py`, `tests/test_environment.py`: Coverage.

## Dev Mode
HACKING

## State Log
- 2026-09-26: Activation now catches canonical direct database URL project-ref mismatches and gives a targeted DNS resolution explanation, including that CLI login cannot fix DNS.
- 2026-09-16: Activation now tolerates the operator-managed project `.env` during its narrow scaffold Git gate without staging it, and the UI test follows the project-local activation call signature.
- 2026-09-16: Wizard Continue now probes the active project's `.env` via a child-process exit code (never loads secrets in the TUI), shows the absolute path being checked, and no longer depends on the launch-root `.env`.
- 2026-09-16: Removed the unused `synchronize_env_file` credential-copy helper; project `.env` remains operator-managed with the Register setup wizard as the only guidance path.
- 2026-09-16: Replaced automatic project `.env` sync with a Register setup wizard that scaffolds files, instructs manual project env setup, and blocks Continue until credentials are detected.
- 2026-09-16: Aligned the missing-credentials bootstrap test with simplified API keys so it asserts the database-access failure without writing a project `.env`.
- 2026-09-16: Simplified launch-root Supabase env to URL + publishable/secret keys (with anon/service_role/private aliases), auto-derived project ref from `*.supabase.co` URLs, and clarified that DB URL or access token remains required only for migration push.
- 2026-09-16: Repaired local cleanup so generated `.env.example` files are fully removed when empty and TUI callbacks preserve operator-supplied project paths across symlinked temporary directories.
- 2026-09-14: Renamed the progress modal's activation-state flag to avoid colliding with Textual's internal message-pump lifecycle field, restoring modal composition and completion rendering.
- 2026-09-14: Redesigned personal Supabase into Phase 1 scaffold plus Phase 2 Activate with operating-branch Git gate, live preflight, activated-only launch push, and F4 retry; removed New Project opt-in.
- 2026-09-13: Added launch-root canonical environment synchronization and idempotent bootstrap preparation for all discovered registered projects.
- 2026-09-13: Added file-only personal Supabase schema registration with New Project checkbox, task-bar button, profile guidance, and target `.env.example` placeholders.
- 2026-09-13: Added an exact-project-name confirmation gate to both registration entry points so shared-Supabase linking is always deliberate.
- 2026-09-14: Moved existing-project schema registration from the task bar to the `F4` shortcut.
- 2026-09-14: Added a non-dismissible-during-work activation progress modal with scaffold, Git, environment, connectivity, migration, completion, blocked, and already-activated states.
- 2026-09-14: Deferred activation until the confirmation modal is popped and buffered fast worker updates until the progress modal is mounted.
- 2026-09-15: Rebound personal-Supabase activation and retry from CapsLock+4 to Option+4 for terminal compatibility.
- 2026-09-15: Replaced the non-portable CapsLock/Option activation chord with the Textual-native `F4` binding.
- 2026-09-16: Rebound personal-Supabase activation and retry from F4 to the Control-based Ctrl+Shift+S shortcut.
- 2026-09-16: Moved personal-Supabase activation into the Ctrl+K Command Menu and removed its standalone keyboard shortcut.
- 2026-09-16: Added exact-name-confirmed local Supabase cleanup for debugging and hardened scaffold commits to preserve deletions, isolate selected paths, and detect files changing during the commit.
