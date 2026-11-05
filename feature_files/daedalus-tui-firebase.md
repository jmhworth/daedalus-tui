# Daedalus TUI Firebase Backend

## Summary
Opt-in Firebase registration scaffolds Firestore configuration, deny-by-default security rules, index definitions, and a `.daedalus` marker into a target project, and gives orchestration a deploy step that applies changed rules and indexes after verification passes.

## Key Points
- **File-only registration**: `register_firebase` writes `firebase.json`, `firestore.rules`, `firestore.indexes.json`, `storage.rules`, `.env.example` placeholders, profile guidance, and a `[firebase]` marker. It never contacts Firebase; remote apply belongs to orchestration.
- **Deny-by-default rules**: Scaffolded Firestore and Storage rules refuse all access so widening them is a deliberate, reviewable edit. The profile guidance and the repair prompt both forbid widening rules to `if true` in order to make a deploy pass.
- **Non-destructive scaffolding**: An existing `firebase.json` is merged rather than replaced, so hosting or functions configuration survives registration. Unreadable JSON, a conflicting registered project id, and a mismatched `.env.example` value all fail the registration instead of overwriting operator content.
- **Single-backend marker**: Registration refuses to claim a project already registered for a different Firebase project id. A project registers for Firebase or personal Supabase, and the TUI reads the `.daedalus` marker to decide which backend a project targets.
- **Change-gated deploy**: Orchestration deploys only when the task changed one of the parameterized `watched_paths` relative to the worktree base commit, and only for projects whose `.daedalus` marks them registered.
- **Deploy repair loop**: A failed deploy emits diagnostics and launches coding-profile repair attempts up to the verification attempt limit before blocking integration, mirroring the Supabase migration push.
- **Storage scaffolded, not deployed**: `storage.rules` is written and referenced from `firebase.json`, but `deploy_targets` defaults to Firestore rules and indexes because a Storage deploy fails until a default bucket exists on the Firebase project.
- **Agent boundary**: Agents edit Firebase files only. Task, repair, and resolver prompts forbid `firebase deploy` the same way they forbid `supabase db push`.

## Relevant Files
- `tui/firebase.py`: Registration, status marker reading, change detection, and the non-interactive deploy wrapper.
- `parameter_files/daedalus-tui-firebase.toml`: Filenames, env keys, watched paths, and deploy targets.
- `tui/orchestrator.py`: `deploy_firebase_with_repairs`, called after verification and the Supabase migration push.
- `tui/prompts.py`: `build_firebase_repair_prompt` and the shared remote-deploy prohibition.
- `tui/project_initializer.py`: Backend selection for newly created projects.
- `tui/app.py`: Backend registration modal and the task-bar Register Backend control.
- `tests/test_firebase.py`, `tests/test_orchestrator.py`: Registration, deploy, and orchestration-step coverage.
- `feature_files/daedalus-tui-orchestration.md`: Orchestration ownership of every remote apply.
- `feature_files/daedalus-tui-personal-supabase.md`: The sibling backend this feature parallels.

## Dev Mode
HACKING

## State Log
- 2026-09-15: Added opt-in Firebase backend registration with deny-by-default Firestore rules and an orchestration-owned deploy step that repairs failures before blocking integration.
