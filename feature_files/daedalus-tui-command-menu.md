# Daedalus TUI Command Menu

## Summary
The Command Menu makes infrequent but important project actions discoverable as buttons while preserving keyboard-first access through one global shortcut. Its Technical and Appearance tabs group operational actions separately from app-wide color themes.

## Key Points
- `Ctrl+K` opens a modal Command Menu from the main TUI and focused prompt editor.
- The menu exposes New Task, New Project, Create Topic, Activate/remove
  personal Supabase, and Sync to GitHub (pull then push by default).
- New Task remains directly available with `Ctrl+T`, and New Project with
  `Ctrl+Shift+N`; both are also discoverable through the menu.
- The full keyboard-shortcut reference remains available from the Command Menu.
- The Appearance tab opens a theme picker with Rainbow, Jet Black & Light Blue, Ember, Forest, and Violet palettes; each theme changes Textual colors for text, surfaces, outlines, and status states.
- The selected theme is stored in the user's XDG config directory (`daedalus-tui/preferences.json`) and restored on later launches.
- Sync/Push is enabled only when the selected operating branch and an `origin` remote are available.
- By default the GitHub action pulls remote commits into the operating branch
  before pushing (`pull_before_push`); set that parameter false for push-only.
- Auto-sync after completed coding tasks is available as an in-session
  Command Menu toggle and defaults to off on each TUI launch. It uses the
  existing sync action for the active project and operating branch.
- Sync pull/merge conflicts (when `sync_conflict_recovery_enabled`) launch an
  operator-owned plan→auto-resolve→push recovery in an isolated sync worktree;
  Sync stays disabled while that recovery is active.

## Relevant Files
- `tui/app.py`: Command Menu sections, theme picker and palette registration, user theme persistence, activation/removal action dispatch, auto-sync toggle, and push-button state.
- `tui/git_worktree.py`: Operating-branch pull-then-push helper used by Sync to GitHub.
- `tui/vim_text_area.py`: Routes Ctrl+K from the focused prompt editor.
- `tui/app.tcss`: Command Menu modal layout and button styling.
- `tests/test_app.py`: Command Menu sections, theme selection and persistence, action routing, and push coverage.
- `tui/config.py`: Command Menu setting parsing.
- `parameter_files/daedalus-tui-command-menu.toml`: Paired feature settings.

## Dev Mode
HACKING

## State Log
- 2026-11-04: Added Technical and Appearance Command Menu tabs with five app-wide color themes and persistent user selection.
- 2026-09-19: Added Sync conflict recovery tunables and UI hooks that launch plan-mode recovery, disable Sync while active, and auto-finish resolve+push.
- 2026-09-19: Hotwired Command Menu Push into a default pull-then-push sync, with `pull_before_push` and a Sync to GitHub label.
- 2026-09-16: Added a Ctrl+K Command Menu for low-frequency task, topic, Supabase, and GitHub Push actions while retaining shortcut-reference access.
- 2026-09-16: Completed the Command Menu wiring, parameter loading, toolbar removal, shortcut migration, and read-only diff review.
- 2026-09-16: Fixed Command Menu Push state refresh to query the active modal screen, restoring disabled-state enforcement when no origin remote exists.
- 2026-09-16: Added a destructive-but-local personal-Supabase cleanup action with exact project-name confirmation for debugging broken scaffolds.
- 2026-09-16: Restored `Ctrl+T` as a direct New Task shortcut while keeping New Task available from the Command Menu.
- 2026-09-19: Added New Project to the Command Menu and routed it through the existing project initializer.
- 2026-10-29: Added an off-by-default Command Menu toggle to sync the active project after each completed coding task.
