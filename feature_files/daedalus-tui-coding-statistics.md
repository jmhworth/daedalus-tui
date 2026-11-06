# Daedalus TUI Coding Statistics

## Summary
The coding statistics tracker presents local task token usage and derived provider and time-window statistics from the TUI's persisted task history.

## Key Points
- `Ctrl+U` opens a modal coding statistics view and is listed in the keyboard shortcuts menu.
- The left panel lists each task timestamp, provider, and recorded token total.
- The top metrics show cumulative usage, current-local-day usage, and a monthly projection extrapolated from current-month-to-date usage.
- The view toggles between token and task units; task counts use the same completed-task records as token accounting.
- The right panel shows per-provider average usage per prompt, recent-hour usage, current-week and current-month projections, and absolute provider usage totals in the selected unit.
- Average tokens per prompt are computed separately for each provider; providers are not merged into a single cross-provider average.
- Provider usage lists absolute token or task counts only; share-of-total percentages are not shown.
- The tracker reads the existing local task memory and overlays live task snapshots so current-session totals stay accurate.
- Only completed tasks contribute to token usage; this applies equally to completed plan and coding tasks.
- Usage-history columns are sized from their complete content before rows are rendered so timestamps and token counts are visible immediately.

## Relevant Files
- `tui/token_usage.py`: Usage records, aggregation utilities, and memory/live-record conversion.
- `tui/memory.py`: Read access to persisted task snapshots.
- `tui/app.py`: Shortcut binding and statistics modal.
- `tui/app.tcss`: Statistics modal layout and styling.
- `parameter_files/daedalus-tui-coding-statistics.toml`: Projection and recent-window settings.

## Dev Mode
HACKING

## State Log
- 2026-08-17: Added persisted and live token usage aggregation with a `Ctrl+T` coding statistics modal.
- 2026-08-17: Restricted token accounting to tasks that complete successfully, including plan tasks.
- 2026-08-17: Added task-unit statistics, a token/task toggle, and a configurable 30-day projection.
- 2026-08-20: Sized usage-history columns before row insertion to prevent initial clipped values that only repainted after mouse movement.
- 2026-08-20: Corrected the statistics layout regression fixture to mark its submitted task completed so it exercises real usage-row sizing.
- 2026-08-23: Replaced cross-provider average and percentage splits with per-provider averages and absolute usage totals.
- 2026-08-25: Changed weekly and monthly projections to extrapolate current calendar week/month-to-date usage so volatile daily usage is reflected without older history dilution.
- 2026-09-14: Moved the coding statistics shortcut from `Ctrl+T` to `Ctrl+U` so `Ctrl+T` can provide a convenient New Task action.
