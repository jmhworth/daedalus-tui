# Daedalus TUI Personal Shared Supabase

## Summary
Two-phase personal Supabase support for Daedalus-managed target projects on one
operator-owned shared database. Phase 1 scaffolds durable project files so
humans and agents can develop against a dedicated schema. Phase 2 (Activate)
is software-owned Daedalus ecosystem readiness: commit the scaffold onto the
already-checked-out operating branch, live-preflight Supabase connectivity, and
TUI-root-owned Supabase CLI migration application. File scaffolding alone is not
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
  optional when the URL is `https://<ref>.supabase.co`; Daedalus derives the ref
  and supplies temporary Supabase CLI link state for migration pushes.
- **Database access is separate from API keys**: Activate / `db push` still need
  one of `SUPABASE_DB_URL`, `SUPABASE_DB_URL_IPV4`, `SUPABASE_DB_URL_IPV6`, or
  `SUPABASE_ACCESS_TOKEN`; publishable/secret keys cannot apply SQL migrations.
  Optional family-specific URLs are probed in IPv4, IPv6, then default order;
  Activate pushes with the first reachable URL. The IPv4 URL should use the
  Supabase Session pooler. `SUPABASE_URL` remains the separate PostgREST/API URL.
- **Phase 1 — Scaffold**: Writes durable project files only (`daedalus-migrations/`
  with a uniquely named `CREATE SCHEMA` migration, `.env.example`, coding/architecture profile guidance,
  and a `.daedalus` marker with `registered=true`, `activated=false`). Does not
  claim ecosystem readiness. Migration SQL is project-owned, while CLI configuration
  and the aggregate migration history are owned by the Daedalus TUI root.
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
  access-method-aware live preflight, then synchronize project migrations to the TUI root and apply them into the
  project's remote schema. Activate assumes the schema is a blank canvas and
  never clears remote objects or migration history.
  Remote Git publish remains the optional operator Push action in the Command Menu.
- **Existing projects only**: Personal Supabase is post-init for projects already
  in the Daedalus format. New Project has no personal-Supabase opt-in.
- **Retry**: Scaffolded or Activate-blocked projects reuse the Command Menu (`Ctrl+K`) with the
  same name confirmation and setup wizard; skip re-scaffold when registered, validate
  completeness, and re-run Phase 2. Incomplete scaffolds fail closed.
- **Local cleanup**: The Command Menu also offers an exact-name-confirmed debug
  cleanup that removes the project's `daedalus-migrations/` directory and generated integration
  content while preserving unrelated `.daedalus` and profile content. The
  operator-managed `.env` is left untouched; operators can delete personal
  Supabase variables from it manually if they are no longer needed. Cleanup never
  changes the remote database.
- **Status model**: Distinguish unregistered, scaffolded (`registered`, not
  `activated`), activated, and blocked reasons (`last_activate_status` /
  redacted error class—no credentials). Launch validates all registered projects;
  launch `db push` runs only for activated projects when `supabase_db_push_enabled`.
- **Supabase connected**: Project-local required API settings + one DB access method
  (`SUPABASE_DB_URL`, either family-specific URL, or `SUPABASE_ACCESS_TOKEN`), `supabase` on PATH, and a
  bounded non-destructive access-method-aware reachability probe before push.
  For canonical direct database hosts, activation checks the host project ref
  against `SUPABASE_URL` and gives a DNS-specific correction when resolution fails.
  That correction explains that direct endpoints are IPv6 by default and recommends
  the dashboard Session pooler connection string for networks that cannot use IPv6.
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
- **Hosted API exposure**: The local TUI `supabase/config.toml` does not configure hosted
  PostgREST. Operators must add the project schema to Dashboard > Project Settings >
  Data API > Exposed schemas after the migration is applied. Generated agent guidance
  explains `.schema(...)` usage and how to diagnose `PGRST106`, including a stale
  `authenticator` role override that can conflict with Dashboard settings.
- **Ownership**: Agents never `db push` or push remotes; software owns Activate
  commits and migration push.
- **Blank schema assumption**: Operators provide an empty project schema before
  Activate. The migration push applies local migrations without attempting to
  remove or reconcile pre-existing remote objects or migration history.
- **Migration synchronization**: Registered projects keep SQL in
  `daedalus-migrations/`, named `<YYYYMMDDHHMM>_<schema>_<description>.sql`.
  Activation, launch, and post-verification handling copy missing files into the
  TUI root `supabase/migrations/`, skip identical files, and preserve unrelated
  root migrations. A same-name/different-content conflict trusts the root copy
  and sends both SQL bodies to a repair agent.
- **Root-owned CLI**: Registered-project CLI operations run with cwd at the TUI
  repository root and use the project's `.env` for connection details.
- **CLI launch path**: Migration pushes invoke the absolute Supabase CLI path
  resolved from the Daedalus process PATH. The project credential overlay may
  omit PATH and must not make an available CLI unlaunchable.
- **Temporary CLI link state**: `supabase db push` reads the linked project ref
  from the TUI root `supabase/.temp/project-ref`; setting `project_id` in `config.toml` alone
  does not link the CLI. Activate supplies that file only while pushing and
  restores any prior value afterward, so operators do not need to run
  `supabase link` in every project.
- **Network-family-aware migration URL**: Activate, launch bootstrap, and
  post-task orchestration pushes preflight project database URLs in IPv4,
  IPv6, then default order. Each push passes the first reachable URL with
  `supabase db push --db-url`, avoiding repeated CLI attempts against an
  unreachable IPv6 direct endpoint on IPv4-only networks. If no configured URL
  is reachable, preflight reports the Session pooler URL setting needed for
  IPv4-only networks before migration repair retries begin.

## Relevant Files
- `tui/personal_supabase.py`: Scaffold helper, marker I/O, local cleanup, Git
  gate/commit, live preflight, Activate orchestration,
  project-local env validation, child-process env presence probe, and temporary CLI configuration.
- `tui/env_presence_probe.py`: Project-root cwd child entry that exits 0/1 after
  resolving required Supabase keys (stderr key names only).
- `tui/environment.py`: Comment-preserving `.env` reading/loading helpers (no
  personal-Supabase credential writes); BOM-safe parse and process overrides.
- `tui/app.py`: Command Menu, confirmation modal, setup wizard, activation progress
  modal, and scaffold+Activate / retry worker.
- `tui/supabase_migrations.py`: Project-to-root migration synchronization and
  non-interactive `db push` from the TUI root for registered projects.
- `tui/orchestrator.py`, `tui/app.py`: Preflight registered project URLs and
  explicitly pass the reachable database URL for task and launch pushes.
- `parameter_files/daedalus-tui-personal-supabase.toml`: Env keys, confirmation and
  wizard copy, activate commit message, and preflight timeout.
- `tests/test_personal_supabase.py`, `tests/test_app.py`, `tests/test_environment.py`: Coverage.

## Dev Mode
HACKING

## State Log
- 2026-09-26: Fixed migration-directory Git ownership checks, made parameter lookup independent of a patched CLI root, and aligned generated guidance and regression fixtures with the current setup flow.
- 2026-09-26: Moved registered-project SQL to timestamped `daedalus-migrations/` files and routed synchronization and Supabase CLI work through the TUI root.
- 2026-09-26: Changed Activate to assume a blank remote schema and push local migrations without clearing remote objects or migration history.
- 2026-09-26: Corrected the remote-reset regression assertion to match the explicitly registered `demo-app` schema.
- 2026-09-26: Added local-source-of-truth Activate recovery that drops only the project's remote schema, clears matching local migration versions, and reapplies local migrations after warning about data loss.
- 2026-09-26: Personal Supabase cleanup now leaves the operator-managed `.env` untouched and reminds operators to remove Supabase variables manually if desired.
- 2026-09-26: Added project schemas to the generated local API config and clarified client schema selection plus hosted PostgREST `PGRST106` troubleshooting in generated agent guidance.
- 2026-09-26: Updated launch-bootstrap regression coverage to mock a successful IPv4 preflight and verify the reachable pooler URL reaches the activated-project migration push.
- 2026-09-26: Routed personal-Supabase task and launch pushes through endpoint preflight, passing a reachable configured database URL explicitly and surfacing IPv4 Session pooler guidance before any migration repair retries.
- 2026-09-26: Added optional IPv4/IPv6 Postgres URLs and use the first reachable endpoint explicitly for migration pushes, keeping the PostgREST API URL independent.
- 2026-09-26: Fixed Activate pushes failing with “Cannot find project ref” by temporarily supplying the derived ref in the Supabase CLI link-state file and restoring it after the push.
- 2026-09-26: Fixed Activate migration pushes to launch the PATH-resolved Supabase CLI path when the project credential overlay omits PATH.
- 2026-09-26: Aligned the DNS preflight regression fixture with a canonical direct Supabase database host so its IPv6 pooler guidance assertion tests the intended case.
- 2026-09-26: DNS failures for canonical direct database URLs now recommend the Dashboard Session pooler connection string for IPv4-only networks.
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
