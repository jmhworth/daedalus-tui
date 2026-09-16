"""Periodic provider usage readings for the usage bar.

Neither provider CLI exposes a non-interactive ``usage`` subcommand (Claude
Code 2.1 hangs waiting for a terminal and Codex 0.154 refuses without one), so
by default the monitor reads the same local data those CLIs display in their
own ``/usage`` and ``/status`` views: Codex writes rate-limit windows into its
session logs after every turn, and Claude Code maintains a per-day token
statistics cache. A command can be configured per provider instead; it runs
with stdin closed, a bounded timeout, and process-group termination.
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
    providers: dict[str, UsageProviderSettings] = field(
        default_factory=lambda: {
            "claude": UsageProviderSettings("Claude"),
            "codex": UsageProviderSettings("Codex"),
        }
    )


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


def _format_tokens(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def _format_reset(resets_at: object, now: float) -> str:
    if not isinstance(resets_at, (int, float)) or isinstance(resets_at, bool):
        return ""
    remaining = int(resets_at - now)
    if remaining <= 0:
        return "resets now"
    hours, minutes = divmod(remaining // 60, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"resets in {days}d {hours}h"
    if hours:
        return f"resets in {hours}h {minutes:02d}m"
    return f"resets in {minutes}m"


def _window_label(window_minutes: object) -> str:
    if not isinstance(window_minutes, (int, float)) or isinstance(window_minutes, bool):
        return "window"
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
        """Read the newest ``rate_limits`` payload from Codex session logs."""
        sessions_dir = self._expand(self.settings.codex_sessions_dir)
        source = str(sessions_dir)
        newest: tuple[float, Path] | None = None
        try:
            for path in sessions_dir.rglob("*.jsonl"):
                try:
                    modified = path.stat().st_mtime
                except OSError:
                    continue
                if newest is None or modified > newest[0]:
                    newest = (modified, path)
        except OSError as error:
            return ProviderUsage("codex", label, f"{label}: unavailable", f"{source}: {error}", False, now, source)
        if newest is None:
            return ProviderUsage("codex", label, f"{label}: no sessions yet", "", False, now, source)
        rate_limits = self._last_codex_rate_limits(newest[1])
        if rate_limits is None:
            return ProviderUsage("codex", label, f"{label}: no usage data yet", str(newest[1]), False, now, source)
        parts = []
        details = []
        for key in ("primary", "secondary"):
            window = rate_limits.get(key)
            if not isinstance(window, dict):
                continue
            used = window.get("used_percent")
            if isinstance(used, bool) or not isinstance(used, (int, float)):
                continue
            window_label = _window_label(window.get("window_minutes"))
            parts.append(f"{window_label} {used:.0f}%")
            reset = _format_reset(window.get("resets_at"), now)
            if reset:
                details.append(f"{window_label}: {used:.0f}% used, {reset}")
        plan = rate_limits.get("plan_type")
        plan_text = f" ({plan})" if isinstance(plan, str) and plan else ""
        if not parts:
            return ProviderUsage("codex", label, f"{label}: no usage data yet", str(newest[1]), False, now, source)
        return ProviderUsage(
            "codex",
            label,
            f"{label} {' · '.join(parts)}{plan_text}",
            "\n".join(details) + f"\nfrom {newest[1].name}",
            True,
            now,
            source,
        )

    @staticmethod
    def _last_codex_rate_limits(path: Path) -> dict | None:
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                lines = handle.readlines()
        except OSError:
            return None
        for line in reversed(lines):
            if "rate_limits" not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = event.get("payload", event) if isinstance(event, dict) else None
            rate_limits = payload.get("rate_limits") if isinstance(payload, dict) else None
            if isinstance(rate_limits, dict):
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
        return ProviderUsage("claude", label, summary, detail, True, now, source)

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
        return ProviderUsage(provider, provider_settings.label, summary, detail, True, now, source)

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


def format_usage_bar(readings: tuple[ProviderUsage, ...], now: float | None = None) -> str:
    """Render the compact usage line shown at the bottom left of the UI."""
    if not readings:
        return "Usage: —"
    now = time.time() if now is None else now
    checked = max((reading.checked_at for reading in readings), default=0.0)
    stamp = datetime.fromtimestamp(checked).strftime("%H:%M") if checked else "—"
    return f"Usage ({stamp}): " + "   ".join(reading.summary for reading in readings)


__all__ = [
    "DEFAULT_COMMAND_TIMEOUT_SECONDS",
    "DEFAULT_INTERVAL_SECONDS",
    "ProviderUsage",
    "UsageMonitor",
    "UsageProviderSettings",
    "UsageSettings",
    "format_usage_bar",
]
