# Daedalus TUI Codex Plan Usage

## Summary
The main page shows the remaining authenticated Codex plan usage for the five-hour and weekly windows, including reset times when Codex provides them.

## Key Points
- Usage is read-only and comes from the local Codex app-server `account/rateLimits/read` request.
- Window identity is determined by the server-reported duration: 300 minutes for five hours and 10,080 minutes for weekly usage.
- The display reports remaining percentages, not local token estimates, because plan allowance usage varies by model, task, and settings.
- Missing windows remain explicitly unavailable; the TUI does not infer a five-hour value from weekly usage or local task history.
- Refreshes run in a daemon thread so app-server startup and network/authentication delays do not block the Textual event loop.
- The Codex CLI, authentication, and backend may be unavailable; failures are rendered as a concise unavailable message.

## Relevant Files
- `tui/codex_usage.py`: App-server request, response parsing, and usage window models.
- `tui/config.py`: Read-only usage polling settings loader.
- `tui/app.py`: Main-page usage line and background refresh lifecycle.
- `tui/app.tcss`: Usage-line layout styling.
- `parameter_files/daedalus-tui-codex-usage.toml`: CLI, timeout, and refresh interval settings.

## Dev Mode
HACKING

## State Log
- 2026-09-23: Added a non-blocking main-page display for Codex five-hour and weekly remaining plan usage from the local app-server rate-limit response.
