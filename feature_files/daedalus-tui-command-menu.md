# Daedalus TUI Command Menu

## Summary
The Command Menu makes infrequent but important project actions discoverable as buttons while preserving keyboard-first access through one global shortcut.

## Key Points
- `Ctrl+K` opens a modal Command Menu from the main TUI and focused prompt editor.
- The menu exposes New Task, Create Topic, Activate/remove personal Supabase,
  and Push to GitHub.
- The previous standalone shortcuts for those actions are removed so the menu is their single entry point.
- The full keyboard-shortcut reference remains available from the Command Menu.
- Push is enabled only when the selected operating branch and an `origin` remote are available.

## Relevant Files
- `tui/app.py`: Command Menu screen, activation/removal action dispatch, and push-button state.
- `tui/vim_text_area.py`: Routes Ctrl+K from the focused prompt editor.
- `tui/app.tcss`: Command Menu modal layout and button styling.
- `tests/test_app.py`: Command Menu, action routing, and push coverage.
- `parameter_files/daedalus-tui-command-menu.toml`: Paired feature settings.

## Dev Mode
HACKING

## State Log
- 2026-09-16: Added a Ctrl+K Command Menu for low-frequency task, topic, Supabase, and GitHub Push actions while retaining shortcut-reference access.
- 2026-09-16: Completed the Command Menu wiring, parameter loading, toolbar removal, shortcut migration, and read-only diff review.
- 2026-09-16: Fixed Command Menu Push state refresh to query the active modal screen, restoring disabled-state enforcement when no origin remote exists.
- 2026-09-16: Added a destructive-but-local personal-Supabase cleanup action with exact project-name confirmation for debugging broken scaffolds.
