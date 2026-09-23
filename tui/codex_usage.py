"""Read the authenticated Codex plan rate-limit windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import shutil
import subprocess

from .config import CodexUsageSettings


UTC = timezone.utc
FIVE_HOUR_WINDOW_MINUTES = 5 * 60
WEEKLY_WINDOW_MINUTES = 7 * 24 * 60


@dataclass(frozen=True)
class CodexUsageWindow:
    """A plan usage window as reported by Codex."""

    remaining_percent: int
    resets_at: datetime | None = None


@dataclass(frozen=True)
class CodexUsageSnapshot:
    """The two plan windows displayed by the main TUI page."""

    five_hour: CodexUsageWindow | None = None
    weekly: CodexUsageWindow | None = None
    plan_type: str | None = None
    error: str | None = None


def fetch_codex_usage(settings: CodexUsageSettings) -> CodexUsageSnapshot:
    """Fetch current plan usage through Codex's local app-server protocol."""
    executable = shutil.which(settings.executable)
    if executable is None:
        return CodexUsageSnapshot(error=f"{settings.executable} CLI not found")

    requests = (
        {
            "jsonrpc": "2.0",
            "id": "initialize",
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": "daedalus-tui",
                    "title": "Daedalus TUI",
                    "version": "0.1.0",
                },
                "capabilities": {"experimentalApi": True},
            },
        },
        {"jsonrpc": "2.0", "method": "initialized", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": "rate-limits",
            "method": "account/rateLimits/read",
            "params": None,
        },
    )
    payload = "\n".join(json.dumps(request) for request in requests) + "\n"
    try:
        result = subprocess.run(
            [executable, "app-server", "--stdio"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=settings.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CodexUsageSnapshot(error="Codex usage request timed out")
    except OSError:
        return CodexUsageSnapshot(error="Codex usage request could not start")

    response = _find_response(result.stdout)
    if response is None:
        return CodexUsageSnapshot(error="Codex usage data unavailable")
    if "error" in response:
        return CodexUsageSnapshot(error="Codex usage request was rejected")
    return parse_codex_usage(response.get("result"))


def parse_codex_usage(result: object) -> CodexUsageSnapshot:
    """Parse a rate-limits response without trusting optional backend fields."""
    if not isinstance(result, dict):
        return CodexUsageSnapshot(error="Codex returned an invalid usage response")

    snapshots: list[dict] = []
    primary = result.get("rateLimits")
    if isinstance(primary, dict):
        snapshots.append(primary)
    by_limit_id = result.get("rateLimitsByLimitId")
    if isinstance(by_limit_id, dict):
        snapshots.extend(value for value in by_limit_id.values() if isinstance(value, dict))

    five_hour: CodexUsageWindow | None = None
    weekly: CodexUsageWindow | None = None
    for snapshot in snapshots:
        for name in ("primary", "secondary"):
            candidate = _parse_window(snapshot.get(name))
            if candidate is None:
                continue
            duration = candidate[0]
            window = candidate[1]
            if duration == FIVE_HOUR_WINDOW_MINUTES and five_hour is None:
                five_hour = window
            elif duration == WEEKLY_WINDOW_MINUTES and weekly is None:
                weekly = window

    # Older responses consistently used primary for five hours and secondary
    # for weekly, even when they omitted windowDurationMins.
    if five_hour is None:
        five_hour = _first_undimensioned_window(snapshots, "primary")
    if weekly is None:
        weekly = _first_undimensioned_window(snapshots, "secondary")

    rate_limits = result.get("rateLimits")
    plan_type = rate_limits.get("planType") if isinstance(rate_limits, dict) else None
    return CodexUsageSnapshot(
        five_hour=five_hour,
        weekly=weekly,
        plan_type=str(plan_type) if plan_type else None,
    )


def _find_response(stdout: str) -> dict | None:
    for line in stdout.splitlines():
        try:
            message = json.loads(line)
        except (TypeError, ValueError):
            continue
        if isinstance(message, dict) and message.get("id") == "rate-limits":
            return message
    return None


def _parse_window(value: object) -> tuple[int | None, CodexUsageWindow] | None:
    if not isinstance(value, dict):
        return None
    used = value.get("usedPercent")
    if not isinstance(used, (int, float)) or isinstance(used, bool):
        return None
    duration = value.get("windowDurationMins")
    if not isinstance(duration, int) or isinstance(duration, bool):
        duration = None
    remaining = 100 - max(0, min(100, round(used)))
    return duration, CodexUsageWindow(remaining, _parse_reset(value.get("resetsAt")))


def _first_undimensioned_window(
    snapshots: list[dict], name: str
) -> CodexUsageWindow | None:
    for snapshot in snapshots:
        value = snapshot.get(name)
        parsed = _parse_window(value)
        if parsed is not None and parsed[0] is None:
            return parsed[1]
    return None


def _parse_reset(value: object) -> datetime | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value, UTC)
    except (OverflowError, OSError, ValueError):
        return None
