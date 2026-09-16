"""Periodic provider usage readings for the usage bar.

Neither provider CLI exposes a non-interactive ``usage`` subcommand (Claude
Code 2.1 hangs waiting for a terminal and Codex 0.154 refuses without one), so
by default the monitor reads the same local data those CLIs display in their
own ``/usage`` and ``/status`` views: Codex writes rate-limit windows into its
session logs after every turn, and Claude Code maintains a per-day token
statistics cache that may also include its status-line rate-limit windows. A
command can be configured per provider instead; it runs with stdin closed, a
bounded timeout, and process-group termination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from .debug_log import LOGGER, scrub_credentials


DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_COMMAND_TIMEOUT_SECONDS = 20
DEFAULT_SESSION_SCAN_LIMIT = 12
DEFAULT_SESSION_TAIL_BYTES = 262_144
DEFAULT_BAR_WIDTH = 12

# Codex window keys in display order, with the label used when a payload omits
# ``window_minutes`` (newer Codex builds send the windows without it).
_CODEX_WINDOW_KEYS = (("primary", "session"), ("secondary", "weekly"))
_CLAUDE_WINDOW_KEYS = (
    ("five_hour", "5h"),
    ("seven_day", "7d"),
    ("spend_limit", "spend"),
)
_CLAUDE_CONTEXT_KEYS = (("used_percentage", "context"),)


@dataclass(frozen=True)
class UsageProviderSettings:
    """How one provider's usage is read: a command, or the default local reader."""

    label: str
    command: tuple[str, ...] = ()


@dataclass(frozen=True)
class UsageSettings:
    enabled: bool = True
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    command_timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS
    codex_sessions_dir: str = "~/.codex/sessions"
    claude_stats_file: str = "~/.claude/stats-cache.json"
    # A freshly started Codex session has no rate-limit payload until its first
    # turn finishes, so reading only the newest file reports "no usage data"
    # while a slightly older session holds the current numbers. Scan back
    # through this many session logs before giving up.
    session_scan_limit: int = DEFAULT_SESSION_SCAN_LIMIT
    # Session logs grow without bound; only their tail can hold the newest
    # rate-limit payload, so never read more than this many trailing bytes.
    session_tail_bytes: int = DEFAULT_SESSION_TAIL_BYTES
    # Cells used by each percentage bar in the usage panel.
    bar_width: int = DEFAULT_BAR_WIDTH
    providers: dict[str, UsageProviderSettings] = field(
        default_factory=lambda: {
            "claude": UsageProviderSettings("Claude"),
            "codex": UsageProviderSettings("Codex"),
        }
    )


@dataclass(frozen=True)
class UsageWindow:
    """One rate-limit window with a percentage the usage panel can draw."""

    label: str
    used_percent: float
    reset_text: str = ""


@dataclass(frozen=True)
class ProviderUsage:
    """One provider's latest reading, ready to display."""

    provider: str
    label: str
    summary: str
    detail: str = ""
    ok: bool = True
    checked_at: float = 0.0
    source: str = ""
    windows: tuple[UsageWindow, ...] = ()


def _format_tokens(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def _number(value: object) -> float | None:
    """Return ``value`` as a float, rejecting booleans and non-numbers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _window_reset_seconds(window: dict, now: float) -> float | None:
    """Return seconds until a window resets from provider duration or timestamp.

    Codex reports ``resets_in_seconds`` (a duration); other payloads carry
    ``resets_at`` as an absolute epoch or ISO timestamp. Reading only one
    spelling silently drops the reset time from the panel, so all are accepted.
    """
    relative = _number(window.get("resets_in_seconds"))
    if relative is not None:
        return relative
    absolute = _number(window.get("resets_at"))
    if absolute is not None:
        return absolute - now
    reset_text = window.get("resets_at")
    if not isinstance(reset_text, str) or not reset_text.strip():
        return None
    try:
        reset_at = datetime.fromisoformat(reset_text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if reset_at.tzinfo is None:
        reset_at = reset_at.replace(tzinfo=timezone.utc)
    return reset_at.timestamp() - now


def _format_duration(remaining: float | None) -> str:
    if remaining is None:
        return ""
    total = int(remaining)
    if total <= 0:
        return "resets now"
    hours, minutes = divmod(total // 60, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"resets in {days}d {hours}h"
    if hours:
        return f"resets in {hours}h {minutes:02d}m"
    return f"resets in {minutes}m"


def _format_reset(window: dict, now: float) -> str:
    return _format_duration(_window_reset_seconds(window, now))


def format_bar(percent: float, width: int = DEFAULT_BAR_WIDTH) -> str:
    """Draw a fixed-width progress bar for a 0-100 percentage.

    The bar is plain block text so it renders on a ``Static`` with Textual
    markup disabled, and it never exceeds ``width`` cells, so the usage panel
    cannot widen the task sidebar.
    """
    width = max(1, int(width))
    ratio = min(1.0, max(0.0, percent / 100.0))
    filled = int(round(ratio * width))
    # Any non-zero usage should be visible, and anything short of the limit
    # should still show headroom.
    if percent > 0 and filled == 0:
        filled = 1
    if ratio < 1.0 and filled == width:
        filled = width - 1
    return "█" * filled + "░" * (width - filled)


def _format_age(seconds: float) -> str:
    """Describe how old a reading is, so stale numbers are visible as stale."""
    total = int(max(0.0, seconds))
    if total < 90:
        return "just now"
    minutes = total // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes:02d}m ago"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h ago"


def _window_label(window_minutes: object, fallback: str = "window") -> str:
    if not isinstance(window_minutes, (int, float)) or isinstance(window_minutes, bool):
        return fallback
    minutes = int(window_minutes)
    if minutes % 10080 == 0:
        weeks = minutes // 10080
        return "week" if weeks == 1 else f"{weeks}w"
    if minutes % 1440 == 0:
        days = minutes // 1440
        return "day" if days == 1 else f"{days}d"
    if minutes % 60 == 0:
        return f"{minutes // 60}h"
    return f"{minutes}m"


class UsageMonitor:
    """Read each provider's usage on demand; the app schedules the cadence."""

    def __init__(self, settings: UsageSettings | None = None, *, home: Path | None = None):
        self.settings = settings or UsageSettings()
        self.home = home

    # --- public -------------------------------------------------------------------

    def poll(self, now: float | None = None) -> tuple[ProviderUsage, ...]:
        """Return one reading per configured provider; never raises."""
        now = time.time() if now is None else now
        readings = []
        for provider, provider_settings in self.settings.providers.items():
            try:
                readings.append(self.read(provider, provider_settings, now))
            except Exception as error:  # A usage reading must never break the UI.
                LOGGER.warning("Usage reading failed provider=%s error=%s", provider, error)
                readings.append(
                    ProviderUsage(
                        provider,
                        provider_settings.label,
                        f"{provider_settings.label}: unavailable",
                        scrub_credentials(str(error)),
                        ok=False,
                        checked_at=now,
                    )
                )
        return tuple(readings)

    def read(self, provider: str, provider_settings: UsageProviderSettings, now: float) -> ProviderUsage:
        if provider_settings.command:
            return self._read_command(provider, provider_settings, now)
        if provider == "codex":
            return self.read_codex(provider_settings.label, now)
        if provider == "claude":
            return self.read_claude(provider_settings.label, now)
        return ProviderUsage(
            provider,
            provider_settings.label,
            f"{provider_settings.label}: no usage source configured",
            ok=False,
            checked_at=now,
        )

    # --- default readers ---------------------------------------------------------------

    def _expand(self, value: str) -> Path:
        path = Path(value)
        if self.home is not None and value.startswith("~"):
            return self.home / value[2:] if value.startswith("~/") else self.home
        return path.expanduser()

    def read_codex(self, label: str, now: float) -> ProviderUsage:
        """Read the newest usable ``rate_limits`` payload from Codex session logs.

        Codex only writes rate limits once a turn completes, so the most
        recently touched session log is frequently a just-started session with
        no usage in it at all. Scanning back through the newest few logs until
        a payload with real percentages appears keeps the panel showing the
        operator's actual limits instead of "no usage data yet".
        """
        sessions_dir = self._expand(self.settings.codex_sessions_dir)
        source = str(sessions_dir)
        try:
            candidates: list[tuple[float, Path]] = []
            for path in sessions_dir.rglob("*.jsonl"):
                try:
                    candidates.append((path.stat().st_mtime, path))
                except OSError:
                    continue
        except OSError as error:
            return ProviderUsage("codex", label, f"{label}: unavailable", f"{source}: {error}", False, now, source)
        if not candidates:
            return ProviderUsage("codex", label, f"{label}: no sessions yet", "", False, now, source)

        candidates.sort(key=lambda entry: entry[0], reverse=True)
        scanned = candidates[: max(1, self.settings.session_scan_limit)]
        found: tuple[dict, Path, float] | None = None
        for modified, path in scanned:
            rate_limits = self._last_codex_rate_limits(path)
            if rate_limits is not None:
                found = (rate_limits, path, modified)
                break
        if found is None:
            return ProviderUsage(
                "codex",
                label,
                f"{label}: no usage data yet",
                f"no rate limits in the newest {len(scanned)} session logs under {source}",
                False,
                now,
                source,
            )

        rate_limits, path, modified = found
        windows: list[UsageWindow] = []
        for key, fallback_label in _CODEX_WINDOW_KEYS:
            window = rate_limits.get(key)
            if not isinstance(window, dict):
                continue
            used = _number(window.get("used_percent"))
            if used is None:
                continue
            window_label = _window_label(window.get("window_minutes"), fallback_label)
            windows.append(UsageWindow(window_label, used, _format_reset(window, now)))
        if not windows:
            return ProviderUsage("codex", label, f"{label}: no usage data yet", str(path), False, now, source)

        plan = rate_limits.get("plan_type")
        plan_text = f" ({plan})" if isinstance(plan, str) and plan else ""
        summary = f"{label} " + " · ".join(f"{window.label} {window.used_percent:.0f}%" for window in windows) + plan_text
        details = [
            f"{window.label}: {window.used_percent:.0f}% used" + (f", {window.reset_text}" if window.reset_text else "")
            for window in windows
        ]
        # The reading is only as fresh as the turn that produced it; showing
        # its age makes a stale number obvious instead of misleading.
        age = _format_age(now - modified)
        details.append(f"from {path.name} ({age})")
        return ProviderUsage("codex", label, summary, "\n".join(details), True, now, source, tuple(windows))

    def _last_codex_rate_limits(self, path: Path) -> dict | None:
        """Return the newest rate-limit payload in one session log, if any.

        Only the file's tail is read: session logs grow without bound and the
        newest payload is always at the end. A payload without a single usable
        percentage is skipped so an empty trailing entry cannot mask the real
        numbers written earlier in the same session.
        """
        try:
            with path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                tail = max(0, self.settings.session_tail_bytes)
                handle.seek(max(0, size - tail))
                data = handle.read()
        except OSError:
            return None
        lines = data.decode("utf-8", errors="ignore").splitlines()
        for line in reversed(lines):
            if "rate_limits" not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                # A truncated first line from the tail read, or a partially
                # flushed final line while Codex is still running.
                continue
            if not isinstance(event, dict):
                continue
            payload = event.get("payload")
            payload = payload if isinstance(payload, dict) else event
            rate_limits = payload.get("rate_limits")
            if not isinstance(rate_limits, dict):
                continue
            if any(
                isinstance(rate_limits.get(key), dict) and _number(rate_limits[key].get("used_percent")) is not None
                for key, _fallback in _CODEX_WINDOW_KEYS
            ):
                if "plan_type" not in rate_limits and isinstance(payload.get("plan_type"), str):
                    # Newer Codex builds carry the plan beside the windows.
                    rate_limits = {**rate_limits, "plan_type": payload["plan_type"]}
                return rate_limits
        return None

    def read_claude(self, label: str, now: float) -> ProviderUsage:
        """Read today's token and message totals from Claude Code's stats cache."""
        path = self._expand(self.settings.claude_stats_file)
        source = str(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return ProviderUsage("claude", label, f"{label}: no usage data yet", f"{path} not found", False, now, source)
        except (OSError, json.JSONDecodeError) as error:
            return ProviderUsage("claude", label, f"{label}: unavailable", f"{path}: {error}", False, now, source)
        if not isinstance(data, dict):
            return ProviderUsage("claude", label, f"{label}: unavailable", f"{path}: unexpected shape", False, now, source)
        today = datetime.fromtimestamp(now).date().isoformat()
        tokens_today = 0
        for entry in data.get("dailyModelTokens") or ():
            if isinstance(entry, dict) and entry.get("date") == today:
                by_model = entry.get("tokensByModel")
                if isinstance(by_model, dict):
                    tokens_today += sum(
                        int(value) for value in by_model.values() if isinstance(value, (int, float)) and not isinstance(value, bool)
                    )
        messages_today = 0
        sessions_today = 0
        for entry in data.get("dailyActivity") or ():
            if isinstance(entry, dict) and entry.get("date") == today:
                messages_today += int(entry.get("messageCount") or 0)
                sessions_today += int(entry.get("sessionCount") or 0)
        total_tokens = 0
        model_usage = data.get("modelUsage")
        if isinstance(model_usage, dict):
            for usage in model_usage.values():
                if isinstance(usage, dict):
                    total_tokens += sum(
                        int(usage.get(key) or 0)
                        for key in ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")
                        if isinstance(usage.get(key), (int, float)) and not isinstance(usage.get(key), bool)
                    )
        computed = data.get("lastComputedDate")
        computed_text = f"as of {computed}" if isinstance(computed, str) and computed else ""
        summary = f"{label} today {_format_tokens(tokens_today)} tok · {messages_today} msgs"
        detail = f"all time {_format_tokens(total_tokens)} tokens; {sessions_today} sessions today {computed_text}".strip()
        return ProviderUsage(
            "claude",
            label,
            summary,
            detail,
            True,
            now,
            source,
            self._claude_windows(data, now),
        )

    @staticmethod
    def _claude_windows(data: dict, now: float) -> tuple[UsageWindow, ...]:
        """Read Claude's rate-limit and context percentages when present."""
        payload = data.get("rate_limits") or data.get("rateLimits")
        windows: tuple[UsageWindow, ...] = ()
        if isinstance(payload, dict):
            windows = UsageMonitor._windows_from_payload(payload, now, _CLAUDE_WINDOW_KEYS)
        context = data.get("context_window") or data.get("contextWindow")
        if isinstance(context, dict):
            windows += UsageMonitor._windows_from_payload(context, now, _CLAUDE_CONTEXT_KEYS)
        return windows

    # --- configured commands -----------------------------------------------------------

    def _read_command(self, provider: str, provider_settings: UsageProviderSettings, now: float) -> ProviderUsage:
        command = list(provider_settings.command)
        source = " ".join(command)
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=os.name == "posix",
            )
        except OSError as error:
            return ProviderUsage(provider, provider_settings.label, f"{provider_settings.label}: unavailable", f"{source}: {error}", False, now, source)
        try:
            stdout, stderr = process.communicate(timeout=self.settings.command_timeout_seconds)
        except subprocess.TimeoutExpired:
            self._terminate(process)
            stdout, stderr = process.communicate()
            return ProviderUsage(
                provider,
                provider_settings.label,
                f"{provider_settings.label}: usage command timed out",
                f"{source} produced no result within {self.settings.command_timeout_seconds:g}s",
                False,
                now,
                source,
            )
        if process.returncode != 0:
            reason = scrub_credentials((stderr or stdout).strip().splitlines()[-1] if (stderr or stdout).strip() else f"exit {process.returncode}")
            return ProviderUsage(provider, provider_settings.label, f"{provider_settings.label}: unavailable", f"{source}: {reason}", False, now, source)
        summary, detail = self._summarize_output(provider_settings.label, stdout)
        windows: tuple[UsageWindow, ...] = ()
        try:
            payload = json.loads(stdout.strip())
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            windows = self._windows_from_payload(payload, now, _CLAUDE_WINDOW_KEYS)
            if provider == "claude" and not windows:
                windows = self._windows_from_payload(
                    payload,
                    now,
                    (("context_window", "context"), ("contextWindow", "context")),
                )
            if not windows:
                windows = self._windows_from_payload(
                    payload,
                    now,
                    (
                        ("usage_percent", "usage"),
                        ("used_percent", "usage"),
                        ("used_percentage", "usage"),
                    ),
                )
        return ProviderUsage(provider, provider_settings.label, summary, detail, True, now, source, windows)

    @staticmethod
    def _windows_from_payload(
        payload: dict,
        now: float,
        keys: tuple[tuple[str, str], ...],
    ) -> tuple[UsageWindow, ...]:
        """Convert percentage-bearing provider JSON into display windows."""
        nested = payload.get("rate_limits") or payload.get("rateLimits")
        if isinstance(nested, dict):
            payload = nested
        windows: list[UsageWindow] = []
        for key, label in keys:
            value = payload.get(key)
            if isinstance(value, dict):
                used = _number(value.get("used_percentage"))
                if used is None:
                    used = _number(value.get("used_percent"))
                if used is None:
                    continue
                windows.append(UsageWindow(label, used, _format_reset(value, now)))
                continue
            used = _number(value)
            if used is not None:
                windows.append(UsageWindow(label, used))
        return tuple(windows)

    @staticmethod
    def _terminate(process: subprocess.Popen) -> None:
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            else:
                process.kill()
        except (OSError, ProcessLookupError):
            process.kill()

    @staticmethod
    def _summarize_output(label: str, stdout: str) -> tuple[str, str]:
        text = scrub_credentials(stdout.strip())
        if not text:
            return f"{label}: (no output)", ""
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            interesting = []
            for key, value in payload.items():
                lowered = key.lower()
                if any(token in lowered for token in ("usage", "used", "limit", "remaining", "percent", "reset", "quota")):
                    interesting.append(f"{key}={value}")
            if interesting:
                return f"{label} " + " · ".join(interesting[:3]), "\n".join(interesting)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return f"{label} {lines[0][:60]}", "\n".join(lines[:12])


def format_usage_bar(
    readings: tuple[ProviderUsage, ...],
    now: float | None = None,
    *,
    bar_width: int = DEFAULT_BAR_WIDTH,
) -> str:
    """Render the usage panel shown at the bottom left of the UI.

    Each provider contributes its summary line, followed by one progress bar
    per rate-limit window that reports a percentage. Claude Code's daily
    statistics remain in the summary while any accompanying rate-limit
    windows are rendered beneath it.
    """
    if not readings:
        return "Usage: —"
    checked = max((reading.checked_at for reading in readings), default=0.0)
    stamp = datetime.fromtimestamp(checked).strftime("%H:%M") if checked else "—"
    lines = [f"Usage ({stamp})"]
    label_width = max(
        (len(window.label) for reading in readings for window in reading.windows),
        default=0,
    )
    for reading in readings:
        lines.append(reading.summary)
        for window in reading.windows:
            lines.append(
                f"  {window.label:<{label_width}} {format_bar(window.used_percent, bar_width)} "
                f"{window.used_percent:3.0f}%"
            )
    return "\n".join(lines)


__all__ = [
    "DEFAULT_BAR_WIDTH",
    "DEFAULT_COMMAND_TIMEOUT_SECONDS",
    "DEFAULT_INTERVAL_SECONDS",
    "DEFAULT_SESSION_SCAN_LIMIT",
    "DEFAULT_SESSION_TAIL_BYTES",
    "ProviderUsage",
    "UsageMonitor",
    "UsageProviderSettings",
    "UsageSettings",
    "UsageWindow",
    "format_bar",
    "format_usage_bar",
]
