# Daedalus TUI Project Initialization

## Summary
The TUI can initialize a new Daedalus-compatible project under the launch root by materializing bundled templates (AGENTS.md, agent profiles, feature/parameter/topic directories, README, gitignore, and `.daedalus`), installing Graphify hooks, creating the initial Git commit, and optionally creating a private GitHub repository.

## Key Points
- **Launch-root destination**: The `CapsLock+2` shortcut opens a modal where the user supplies only a project slug and optional GitHub opt-in; the destination is always a direct child of the TUI launch root.
- **Template copy**: Initializer-owned files under `tui/templates/project-initializer/` are copied into an atomic temporary sibling, then renamed into place.
- **`.daedalus` scaffold**: New projects receive a TOML `.daedalus` with an empty `[worktree]` table (`install_command`, `readonly_paths`) so orchestration provisioning is ready to configure.
- **Recoverable requests**: A `.git/daedalus-initialization-request-id` marker lets retries recognize initializer-owned projects without overwriting unrelated directories.
- **Local by default**: Graphify install and Git init/commit always run; GitHub creation is optional and private.
- **Personal Supabase**: Not part of New Project. After init, operators activate personal Supabase on existing Daedalus-format projects via `CapsLock+4` (see personal-supabase feature).
- **Discovery refresh**: After success, the TUI rediscovers `feature_files` projects and switches to the new project.

## Relevant Files
- `tui/project_initializer.py`: Validation, template materialization, command steps, cleanup, and result construction.
- `tui/templates/project-initializer/`: Base Daedalus project assets copied into new projects.
- `tui/templates/project-initializer/.daedalus`: Default TOML worktree provisioning scaffold.
- `tui/app.py`: New Project modal and post-init project list refresh.
- `parameter_files/daedalus-tui-project-initialization.toml`: Initializer-owned settings.
- `tests/test_project_initializer.py`: Unit coverage for validation and initialization flows.

## Dev Mode
HACKING

## State Log
- 2026-09-14: Removed New Project personal-Supabase opt-in; Activate is post-init only via the personal-supabase feature.
- 2026-09-13: Updated initialization guidance so registered projects inherit shared Supabase connection details from the launch-root environment at launch.
- 2026-09-13: New Project can optionally register a personal shared-Supabase schema (file scaffolding only) before the initial commit.
- 2026-08-24: New Project templates now include an empty `topic_files/` directory for optional Topics.
- 2026-08-24: New Project template materialization now includes a scaffold `.daedalus` TOML with empty worktree install/readonly settings.
- 2026-08-23: Ported daemon project initialization into the standalone TUI with bundled templates and a New Project modal under the launch root.
- 2026-09-14: Moved New Project from the task toolbar to the `F2` shortcut after terminal encodings made Ctrl+Shift+N unreliable.
