# Daedalus TUI Coding Statistics

## Summary
The coding statistics tracker presents local task token usage and derived provider and time-window statistics from the TUI's persisted task history, alongside the operator's account-wide Claude Code token total.

## Key Points
- `Ctrl+T` opens a modal coding statistics view and is listed in the keyboard shortcuts menu.
- A fourth summary tile reports every Claude Code token recorded on the machine, not just the tasks Daedalus launched, because the operator's real question is how much Claude they have used in total.
- That account-wide total is supplied by the usage monitor's `read_claude_account_usage` reader (owned by `daedalus-tui-prompting.md`), which merges Claude's all-time statistics cache with its session transcripts; this feature only renders what the reader returns.
- The reader can touch every transcript ever written, so the screen opens immediately with the Daedalus figures and fills the tile from a background worker; the tile shows `reading…`, then the total, `no usage data`, or `unavailable` with the failure in its tooltip.
- The account-wide figure is always a token count and stays in tokens when the view is switched to task units, since Claude Code records tokens rather than Daedalus tasks.
- When usage readings are disabled in the parameter file, no reader is passed and the tile shows `—`, so the screen never reads provider data the operator turned off.
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
- `tui/usage_monitor.py`: Dependency owned by `daedalus-tui-prompting.md`; provides `read_claude_account_usage`, whose scan window lives under `[usage]` in `parameter_files/daedalus-tui.toml`.

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
- 2026-09-16: Added an "All Claude tokens" summary tile fed by a background account-wide read of Claude Code's local records, so `Ctrl+T` shows total Claude usage rather than only Daedalus-launched tasks.
