"""Periodic provider usage readings for the usage bar.

The percentages each provider's own ``/usage`` view reports are the only
numbers that are actually right, so the monitor asks the provider CLIs for
them first and only falls back to reading local files.

Asking is awkward because neither CLI is built to be scripted: Claude Code
hangs waiting for a terminal, Codex refuses without one, and both stop on a
permission prompt when run headless. So a provider's usage commands run
attached to a pseudo-terminal, with permission prompts overridden on the
command line, and their rendered output is scraped for labelled percentages.
A CLI that draws a panel and then waits is handled by the timeout: whatever it
printed before being killed is still parsed, because that text already holds
the numbers. Several candidate commands can be listed per provider and are
tried in order until one yields windows, so a CLI that renamed its usage
command does not silently blank the bar.

When no command yields usable windows, the monitor reads the same local data
those views are drawn from: Codex writes rate-limit windows into its session
logs after every turn (a snapshot, so a window whose recorded reset time has
passed is reported as refilled rather than redrawn at its last percentage),
and Claude Code maintains a per-day token statistics cache that may also
include its status-line rate-limit windows. Claude Code's cache is only a
derived summary, so its session transcripts are read as the raw record of what
was actually spent, and when Claude Code publishes no rate-limit payload those
transcripts also supply the rolling 5h and 7d windows its progress bars are
drawn from. Those transcript-derived bars are calibrated against the operator's
own busiest window rather than a real quota, which is exactly why the CLIs are
asked first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time

from .debug_log import LOGGER, scrub_credentials


DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_COMMAND_TIMEOUT_SECONDS = 20
# How often the provider CLIs are actually asked for their usage. The bar still
# refreshes every ``interval_seconds``; between command runs it redraws the last
# reading. Rate-limit windows move over hours, so five minutes is far finer than
# the numbers being shown.
DEFAULT_COMMAND_INTERVAL_SECONDS = 300.0
DEFAULT_SESSION_SCAN_LIMIT = 12
DEFAULT_SESSION_TAIL_BYTES = 262_144
DEFAULT_BAR_WIDTH = 12
# How far back transcripts are read. Every transcript touched inside this
# window is parsed once in full and then only from where the previous scan
# stopped, so the window bounds the one-time cost of the first reading.
DEFAULT_CLAUDE_TRANSCRIPT_DAYS = 30
# The coding statistics screen reports every Claude Code token the operator has
# spent, not just the recent window the usage bar draws, so its own reader looks
# back far enough to cover the whole retained transcript history.
DEFAULT_CLAUDE_ACCOUNT_SCAN_DAYS = 3650
# Transcript tokens are bucketed by time so a rolling window can be summed
# without keeping one entry per turn. Five minutes is finer than any window the
# panel draws and still leaves fewer than ten thousand buckets for a month.
ROLLING_BUCKET_SECONDS = 300
# The rolling windows Claude's own /usage view reports, drawn as progress bars
# from transcript tokens when Claude Code publishes no rate-limit payload.
_CLAUDE_ROLLING_WINDOWS = (("5h", 5 * 3600), ("7d", 7 * 86_400))

# Codex window keys in display order, with the label used when a payload omits
# ``window_minutes`` (newer Codex builds send the windows without it).
_CODEX_WINDOW_KEYS = (("primary", "session"), ("secondary", "weekly"))
_CLAUDE_WINDOW_KEYS = (
    ("five_hour", "5h"),
    ("seven_day", "7d"),
    ("spend_limit", "spend"),
)
_CLAUDE_CONTEXT_KEYS = (("used_percentage", "context"),)

# Size the pseudo-terminal is opened at. A CLI that draws a usage panel lays it
# out against the terminal width, so a narrow terminal wraps or truncates the
# very percentages being scraped.
DEFAULT_PTY_COLUMNS = 200
DEFAULT_PTY_LINES = 60
# How long to wait after a command starts before typing into its terminal, so
# an interactive CLI has finished starting up and is listening for input.
DEFAULT_INPUT_DELAY_SECONDS = 1.5

# Both CLIs stop on a permission prompt when run headless, so the usage
# commands carry each CLI's documented permission override. Without it the
# command sits at a prompt until the timeout and the bar stays empty.
CLAUDE_PERMISSION_FLAGS = ("--permission-mode", "bypassPermissions")
CODEX_PERMISSION_FLAGS = ("--ask-for-approval", "never", "--sandbox", "read-only")

# Candidate usage commands, tried in order until one produces percentages.
# Listing more than one is deliberate: these subcommands are not a stable
# scripting interface, and a candidate that does not exist fails immediately
# and costs nothing.
DEFAULT_CLAUDE_USAGE_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("claude", *CLAUDE_PERMISSION_FLAGS, "-p", "/usage"),
    ("claude", *CLAUDE_PERMISSION_FLAGS, "-p", "/status"),
)
DEFAULT_CODEX_USAGE_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("codex", "exec", *CODEX_PERMISSION_FLAGS, "--skip-git-repo-check", "/status"),
    ("codex", "exec", *CODEX_PERMISSION_FLAGS, "--skip-git-repo-check", "/usage"),
)

# Escape sequences a CLI emits to colour and position its usage panel. They sit
# between the label and the percentage, so they have to go before the text is
# read.
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
# A percentage anywhere in a line, with the text that precedes it on the line.
_PERCENT = re.compile(r"(?P<before>.*?)(?P<percent>\d{1,3}(?:\.\d+)?)\s*%")
# "Resets 3:45pm", "resets in 2h 10m", "Resets Nov 5 (UTC)" -- the phrase a
# usage view prints beside a window, kept verbatim rather than re-derived. It
# runs to the end of its line or to a separator, so a parenthesised time zone
# stays part of it.
_RESET_PHRASE = re.compile(r"(resets?(?:\s+in)?\b[^.|\]]*)", re.IGNORECASE)
# Phrases a provider uses for a window, mapped onto the short labels the panel
# draws. Checked in order, so the more specific phrases come first.
_TEXT_WINDOW_LABELS: tuple[tuple[str, str], ...] = (
    ("context", "context"),
    ("opus", "opus"),
    ("sonnet", "sonnet"),
    ("spend", "spend"),
    ("credit", "spend"),
    ("current session", "5h"),
    ("5-hour", "5h"),
    ("5 hour", "5h"),
    ("five-hour", "5h"),
    ("session", "5h"),
    ("hourly", "5h"),
    ("weekly", "7d"),
    ("this week", "7d"),
    ("current week", "7d"),
    ("7-day", "7d"),
    ("7 day", "7d"),
    ("week", "7d"),
    ("daily", "1d"),
    ("today", "1d"),
    ("monthly", "30d"),
)


@dataclass(frozen=True)
class UsageProviderSettings:
    """How one provider's usage is read: its CLI commands, then the local reader.

    ``command`` is the single-command spelling kept for existing configs;
    ``commands`` lists candidates tried in order. ``use_pty`` runs them under a
    pseudo-terminal, which is what makes a CLI that refuses or hangs without a
    terminal produce output at all, and ``input_text`` is typed into that
    terminal once the CLI has started, for a CLI whose usage view is only
    reachable as a slash command. ``fallback_to_local`` keeps the bar drawn
    from local files when no command works, so adding a command can never make
    the panel worse than not having one.
    """

    label: str
    command: tuple[str, ...] = ()
    commands: tuple[tuple[str, ...], ...] = ()
    use_pty: bool = False
    input_text: str = ""
    env: dict[str, str] = field(default_factory=dict)
    fallback_to_local: bool = True

    def resolved_commands(self) -> tuple[tuple[str, ...], ...]:
        """Every command to try, the single-command spelling first."""
        candidates = ([tuple(self.command)] if self.command else []) + [
            tuple(entry) for entry in self.commands if entry
        ]
        seen: set[tuple[str, ...]] = set()
        ordered: list[tuple[str, ...]] = []
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                ordered.append(candidate)
        return tuple(ordered)


@dataclass(frozen=True)
class UsageSettings:
    enabled: bool = True
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    command_timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS
    # Starting a provider CLI is far more expensive than reading a local file,
    # and these are rate-limit windows measured in hours, so the commands run
    # on their own slower cadence and the bar reuses the last reading in
    # between. Without this the panel would launch two CLIs a minute.
    command_interval_seconds: float = DEFAULT_COMMAND_INTERVAL_SECONDS
    codex_sessions_dir: str = "~/.codex/sessions"
    claude_stats_file: str = "~/.claude/stats-cache.json"
    # Claude Code appends one JSON line per turn to a session transcript under
    # this directory. The transcripts, not the statistics cache, are the
    # authoritative record of tokens and messages.
    claude_projects_dir: str = "~/.claude/projects"
    claude_transcript_days: int = DEFAULT_CLAUDE_TRANSCRIPT_DAYS
    # How far back the coding statistics screen reads transcripts for its
    # account-wide Claude total. This is deliberately much larger than
    # ``claude_transcript_days``: the bar wants a cheap recent reading, the
    # statistics screen wants everything the operator has spent.
    claude_account_scan_days: int = DEFAULT_CLAUDE_ACCOUNT_SCAN_DAYS
    # Token budgets the Claude progress bars are drawn against. Claude Code
    # publishes no limit locally, so 0 means "calibrate against the busiest
    # equivalent window in the scanned transcripts" -- a bar that is always
    # meaningful, where a full bar means the operator's own busiest stretch.
    claude_five_hour_token_limit: int = 0
    claude_weekly_token_limit: int = 0
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
    # Terminal geometry and typing delay used when a usage command runs under a
    # pseudo-terminal.
    pty_columns: int = DEFAULT_PTY_COLUMNS
    pty_lines: int = DEFAULT_PTY_LINES
    input_delay_seconds: float = DEFAULT_INPUT_DELAY_SECONDS
    providers: dict[str, UsageProviderSettings] = field(
        default_factory=lambda: {
            "claude": UsageProviderSettings(
                "Claude",
                commands=DEFAULT_CLAUDE_USAGE_COMMANDS,
                use_pty=True,
            ),
            "codex": UsageProviderSettings(
                "Codex",
                commands=DEFAULT_CODEX_USAGE_COMMANDS,
                use_pty=True,
            ),
        }
    )


@dataclass(frozen=True)
class UsageWindow:
    """One rate-limit window with a percentage the usage panel can draw."""

    label: str
    used_percent: float
    reset_text: str = ""


@dataclass(frozen=True)
class _CommandResult:
    """What one usage command printed, and how it ended.

    ``timed_out`` is not by itself a failure: a CLI that draws its usage panel
    and then waits for a keypress always ends this way, and the output captured
    before it was killed is exactly what needs parsing.
    """

    output: str = ""
    returncode: int | None = None
    timed_out: bool = False
    error: str = ""


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


def _epoch(value: object) -> float | None:
    """Return an epoch time from an ISO timestamp or a numeric one."""
    number = _number(value)
    if number is not None:
        return number
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _window_reset_seconds(window: dict, recorded_at: float) -> float | None:
    """Return seconds from ``recorded_at`` until a window resets.

    Codex reports ``resets_in_seconds`` (a duration counted from the moment the
    payload was written); other payloads carry ``resets_at`` as an absolute
    epoch or ISO timestamp. Reading only one spelling silently drops the reset
    time from the panel, so all are accepted. ``recorded_at`` is when the
    payload was written, which is ``now`` only for a reading taken live.
    """
    relative = _number(window.get("resets_in_seconds"))
    if relative is not None:
        return relative
    absolute = _number(window.get("resets_at"))
    if absolute is not None:
        return absolute - recorded_at
    reset_text = window.get("resets_at")
    if not isinstance(reset_text, str) or not reset_text.strip():
        return None
    try:
        reset_at = datetime.fromisoformat(reset_text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if reset_at.tzinfo is None:
        reset_at = reset_at.replace(tzinfo=timezone.utc)
    return reset_at.timestamp() - recorded_at


def _window_remaining_seconds(window: dict, recorded_at: float, now: float) -> float | None:
    """Return seconds from ``now`` until a recorded window resets.

    A stored payload's countdown has been running since the payload was
    written, so the duration Codex recorded has to be anchored to that moment
    before it is compared with the present. Anchoring it to ``now`` instead
    would restart the countdown on every poll and the window would never be
    seen to reset.
    """
    offset = _window_reset_seconds(window, recorded_at)
    if offset is None:
        return None
    return recorded_at + offset - now


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
    """Describe a window read live, whose countdown starts at this moment."""
    return _format_duration(_window_reset_seconds(window, now))


def _format_rolloff(remaining: float | None) -> str:
    """Describe when a rolling window's oldest tokens leave it.

    A rolling window never resets the way a provider's quota window does, so
    saying "resets in" would misdescribe it; what actually happens is that the
    oldest tokens age out and the bar falls.
    """
    if remaining is None:
        return ""
    total = int(remaining)
    if total <= 0:
        return "frees up now"
    hours, minutes = divmod(total // 60, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"frees up in {days}d {hours}h"
    if hours:
        return f"frees up in {hours}h {minutes:02d}m"
    return f"frees up in {minutes}m"


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


# Block and box drawing runs make up the progress bars a usage view draws; they
# sit between a window's name and its percentage.
_BAR_CHARS = re.compile(r"[─-◿]+")


def _text_window_label(text: str) -> str:
    """Map a provider's wording for a window onto the label the panel draws."""
    lowered = text.lower()
    for phrase, label in _TEXT_WINDOW_LABELS:
        if phrase in lowered:
            return label
    return ""


def _text_reset(tail: str, following: str) -> str:
    """Find the reset phrase a usage view prints beside a window.

    The phrase is kept as the provider worded it rather than recomputed: it is
    already correct, and the panel only has to repeat it. The line after the
    percentage is consulted too, because a usage view commonly puts the reset
    time on its own line -- but only when that line is not itself another
    window, whose reset time belongs to that window instead.
    """
    candidates = [tail]
    if following and not _PERCENT.search(following):
        candidates.append(following)
    for candidate in candidates:
        match = _RESET_PHRASE.search(candidate)
        if match:
            return " ".join(match.group(1).split())[:48]
    return ""


def _windows_from_text(output: str) -> tuple[UsageWindow, ...]:
    """Scrape labelled percentages out of a usage view's rendered output.

    Only percentages whose wording names a window this panel knows become bars.
    A usage view prints plenty of other numbers, and a bar built from an
    unrecognised one would be worse than no bar at all.

    A CLI drawing into a terminal repaints the same lines, so carriage returns
    are treated as line breaks and a later reading of a window replaces an
    earlier one: the last frame on screen is the current one.
    """
    lines = [
        " ".join(_BAR_CHARS.sub(" ", raw).split())
        for raw in _ANSI.sub("", output).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
    found: dict[str, UsageWindow] = {}
    previous = ""
    for index, line in enumerate(lines):
        if not line:
            continue
        matched = False
        for match in _PERCENT.finditer(line):
            percent = float(match.group("percent"))
            if percent > 100.0:
                continue
            before = match.group("before").strip(" .:·|-")
            # The window's name usually precedes its percentage; a view that
            # puts the name on its own line above the bar is read from there.
            label = _text_window_label(before) or _text_window_label(line) or _text_window_label(previous)
            if not label:
                continue
            following = lines[index + 1] if index + 1 < len(lines) else ""
            found[label] = UsageWindow(label, percent, _text_reset(line[match.end():], following))
            matched = True
        if not matched:
            previous = line
    return tuple(found.values())


@dataclass
class ClaudeDayUsage:
    """One local day's Claude Code totals, as counted from transcripts."""

    tokens: int = 0
    messages: int = 0
    sessions: set[str] = field(default_factory=set)


# Claude Code writes usage with snake_case keys; the camelCase spellings are
# accepted too so a future rename cannot silently zero the panel again.
_CLAUDE_TOKEN_FIELDS = (
    ("input_tokens", "inputTokens"),
    ("output_tokens", "outputTokens"),
    ("cache_read_input_tokens", "cacheReadInputTokens"),
    ("cache_creation_input_tokens", "cacheCreationInputTokens"),
)


class ClaudeTranscriptUsage:
    """Total Claude Code transcript usage per local day, reading each file once.

    Claude Code appends one JSON line per turn to
    ``~/.claude/projects/<project>/<session>.jsonl``; assistant lines carry a
    ``timestamp`` and a ``message.usage`` block. Transcripts are therefore the
    raw record of what the operator spent, unlike the statistics cache, which
    is a derived summary that may be missing, stale, or written with different
    keys.

    Transcripts only ever grow, so each file is parsed from the byte offset
    where the previous scan stopped. That keeps a once-a-minute poll cheap even
    when a session log has grown to megabytes. Entries are de-duplicated by
    their transcript ``uuid`` because resumed and forked sessions replay
    earlier turns into a new file.

    Alongside the per-day totals, tokens are bucketed by time so the rolling
    windows behind Claude's progress bars are a sum over a few buckets rather
    than a walk over every turn ever recorded.
    """

    def __init__(
        self,
        root: Path,
        *,
        scan_days: int = DEFAULT_CLAUDE_TRANSCRIPT_DAYS,
        bucket_seconds: int = ROLLING_BUCKET_SECONDS,
    ) -> None:
        self.root = root
        self.scan_days = max(1, int(scan_days))
        self.bucket_seconds = max(1, int(bucket_seconds))
        self.days: dict[str, ClaudeDayUsage] = {}
        # Tokens keyed by ``timestamp // bucket_seconds`` so a rolling window
        # is a sum over buckets rather than over every turn ever recorded.
        self.buckets: dict[int, int] = {}
        self.total_tokens = 0
        self.scanned_files = 0
        self.error: str | None = None
        # path -> (bytes already parsed, file identity) so a rotated or
        # truncated transcript is re-read from the start instead of skipped.
        self._offsets: dict[Path, tuple[int, tuple[int, int]]] = {}
        self._seen: set[str] = set()
        # The app polls usage from a worker thread. Without this guard, a scan
        # that outlives its poll interval would run beside the next one and
        # both would credit the same appended bytes.
        self._lock = threading.Lock()

    def day(self, date: str) -> ClaudeDayUsage:
        return self.days.get(date, ClaudeDayUsage())

    # --- rolling windows ----------------------------------------------------------

    def _span(self, seconds: float) -> int:
        """Buckets spanned by a window, excluding the bucket it ends in."""
        return max(0, int(seconds // self.bucket_seconds))

    def window_tokens(self, now: float, seconds: float) -> int:
        """Total tokens recorded in the ``seconds`` ending at ``now``."""
        cutoff = int((now - seconds) // self.bucket_seconds)
        return sum(tokens for bucket, tokens in self.buckets.items() if bucket >= cutoff)

    def peak_window_tokens(self, seconds: float) -> int:
        """Return the busiest window of this length anywhere in the history.

        Every window that could be the busiest one ends in a bucket that holds
        tokens, so sliding a running sum over the occupied buckets finds the
        peak in one pass. The current window is one of the candidates, so a
        percentage taken against this peak can never exceed 100%.
        """
        span = self._span(seconds)
        buckets = sorted(self.buckets)
        peak = 0
        total = 0
        start = 0
        for bucket in buckets:
            total += self.buckets[bucket]
            while buckets[start] < bucket - span:
                total -= self.buckets[buckets[start]]
                start += 1
            peak = max(peak, total)
        return peak

    def window_rolloff_seconds(self, now: float, seconds: float) -> float | None:
        """Seconds until the oldest tokens in the window fall out of it."""
        cutoff = int((now - seconds) // self.bucket_seconds)
        oldest = min((bucket for bucket in self.buckets if bucket >= cutoff), default=None)
        if oldest is None:
            return None
        return (oldest + 1) * self.bucket_seconds + seconds - now

    def _prune(self, now: float) -> None:
        """Drop buckets older than the scan window; the totals above stay whole."""
        cutoff = int((now - self.scan_days * 86_400) // self.bucket_seconds)
        for bucket in [bucket for bucket in self.buckets if bucket < cutoff]:
            del self.buckets[bucket]

    def refresh(self, now: float) -> int:
        """Parse transcript bytes appended since the last refresh.

        Returns the number of transcripts inside the scan window. Never
        raises: a missing or unreadable transcript directory is recorded in
        ``error`` and leaves previously counted totals intact. A poll that
        arrives while an earlier scan is still running reuses that scan's
        totals instead of reading the same bytes a second time.
        """
        if not self._lock.acquire(blocking=False):
            return self.scanned_files
        try:
            self.error = None
            cutoff = now - self.scan_days * 86_400
            try:
                paths = sorted(self.root.rglob("*.jsonl"))
            except OSError as error:
                self.error = f"{self.root}: {error}"
                return 0
            scanned = 0
            for path in paths:
                try:
                    info = path.stat()
                except OSError:
                    continue
                if info.st_mtime < cutoff:
                    continue
                scanned += 1
                self._scan(path, info)
            self._prune(now)
            self.scanned_files = scanned
            return scanned
        finally:
            self._lock.release()

    def _scan(self, path: Path, info: os.stat_result) -> None:
        identity = (info.st_ino, info.st_dev)
        offset, previous_identity = self._offsets.get(path, (0, identity))
        if previous_identity != identity or info.st_size < offset:
            offset = 0
        if info.st_size == offset:
            return
        try:
            with path.open("rb") as handle:
                handle.seek(offset)
                data = handle.read()
        except OSError as error:
            self.error = f"{path}: {error}"
            return
        # A turn may be half-written while Claude Code is running; stop at the
        # last complete line and re-read the remainder on the next refresh.
        consumed = data.rfind(b"\n") + 1
        if consumed <= 0:
            return
        session = path.stem
        for line in data[:consumed].splitlines():
            if line.strip():
                self._ingest(line, session)
        self._offsets[path] = (offset + consumed, identity)

    def _ingest(self, line: bytes, session: str) -> None:
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        if not isinstance(entry, dict):
            return
        kind = entry.get("type")
        if kind not in {"user", "assistant"} or entry.get("isMeta"):
            return
        identifier = entry.get("uuid")
        if isinstance(identifier, str) and identifier:
            if identifier in self._seen:
                return
            self._seen.add(identifier)
        moment = _local_moment(entry.get("timestamp"))
        if moment is None:
            return
        date, recorded_at = moment
        message = entry.get("message")
        message = message if isinstance(message, dict) else {}
        # Usage normally rides on the message; a few Claude Code builds put it
        # on the entry itself, and missing it there is what a zeroed panel
        # looks like.
        tokens = _claude_usage_tokens(message.get("usage")) or _claude_usage_tokens(entry.get("usage"))
        totals = self.days.setdefault(date, ClaudeDayUsage())
        totals.tokens += tokens
        self.total_tokens += tokens
        if tokens:
            bucket = int(recorded_at // self.bucket_seconds)
            self.buckets[bucket] = self.buckets.get(bucket, 0) + tokens
        totals.sessions.add(str(entry.get("sessionId") or session))
        if kind == "assistant" or not _is_tool_result(message):
            # Tool results are recorded as user turns; counting them would
            # report far more messages than the operator actually sent.
            totals.messages += 1


def _local_moment(value: object) -> tuple[str, float] | None:
    """Return the local calendar date and epoch time of a transcript timestamp.

    Both are read from one parse: the date groups a turn into its day, and the
    epoch time places it in the rolling windows the progress bars are drawn
    from.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone().date().isoformat(), parsed.timestamp()


def _claude_usage_tokens(usage: object) -> int:
    """Sum input, output, and both cache token counts from one ``usage`` block."""
    if not isinstance(usage, dict):
        return 0
    total = 0
    for key, alternate in _CLAUDE_TOKEN_FIELDS:
        value = _number(usage.get(key))
        if value is None:
            value = _number(usage.get(alternate))
        if value is not None:
            total += int(value)
    return total


def _is_tool_result(message: dict) -> bool:
    content = message.get("content")
    if not isinstance(content, list):
        return False
    return any(isinstance(block, dict) and block.get("type") == "tool_result" for block in content)


@dataclass(frozen=True)
class _ClaudeTotals:
    """One source's view of a day's Claude usage."""

    tokens: int = 0
    messages: int = 0
    sessions: int = 0


@dataclass(frozen=True)
class ClaudeAccountUsage:
    """Every Claude Code token recorded locally, across all projects.

    This is the operator's whole Claude spend, not the subset that Daedalus
    itself launched: it counts transcripts under every project directory Claude
    Code has written, plus the statistics cache's all-time model totals.
    """

    total_tokens: int = 0
    today_tokens: int = 0
    transcript_tokens: int = 0
    cache_tokens: int = 0
    messages: int = 0
    scanned_files: int = 0
    first_day: str = ""
    days_recorded: int = 0
    ok: bool = False
    detail: str = ""
    source: str = ""


class UsageMonitor:
    """Read each provider's usage on demand; the app schedules the cadence."""

    def __init__(self, settings: UsageSettings | None = None, *, home: Path | None = None):
        self.settings = settings or UsageSettings()
        self.home = home
        self._claude_transcripts: ClaudeTranscriptUsage | None = None
        # The account-wide reader keeps its own offsets and window so a wide
        # statistics scan never redefines what the usage bar's recent window
        # means, and so each reader only re-parses bytes it has not seen.
        self._claude_account_transcripts: ClaudeTranscriptUsage | None = None
        # provider -> (when the commands last ran, that run's reading, its notes)
        self._command_cache: dict[str, tuple[float, ProviderUsage | None, list[str]]] = {}
        # provider -> the command that last produced windows, tried first next
        # time so a working setup stops paying for the candidates before it.
        self._winning_command: dict[str, tuple[str, ...]] = {}

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
        """Ask the provider CLI for its own percentages, then fall back locally.

        The CLI's ``/usage`` view is the only source that knows the operator's
        real plan limits, so it wins whenever it yields windows. Anything else
        -- a missing CLI, a renamed subcommand, a permission prompt, a panel
        that never exits -- falls through to the local readers, and the reason
        each command failed is carried into the fallback's detail so the panel
        tooltip explains itself instead of silently showing worse numbers.
        """
        commands = self._ordered_commands(provider, provider_settings)
        command_reading: ProviderUsage | None = None
        notes: list[str] = []
        if commands:
            command_reading, notes = self._cached_commands(provider, provider_settings, commands, now)
            if command_reading is not None and command_reading.windows:
                return self._restamp(command_reading, now)

        local = self._read_local(provider, provider_settings, now)
        if local.ok:
            return self._with_notes(local, notes)
        # Neither source worked. A command that actually ran and failed says
        # more about why than "no usage data yet" does.
        if command_reading is not None:
            return self._with_notes(self._restamp(command_reading, now), [])
        if local.detail or local.summary:
            return self._with_notes(local, notes)
        return local

    def _read_local(self, provider: str, provider_settings: UsageProviderSettings, now: float) -> ProviderUsage:
        if not provider_settings.fallback_to_local:
            return ProviderUsage(
                provider,
                provider_settings.label,
                f"{provider_settings.label}: no usage data yet",
                "local fallback is disabled for this provider",
                False,
                now,
            )
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

    def _ordered_commands(
        self,
        provider: str,
        provider_settings: UsageProviderSettings,
    ) -> tuple[tuple[str, ...], ...]:
        """Candidate commands with the last one that worked moved to the front."""
        commands = provider_settings.resolved_commands()
        winner = self._winning_command.get(provider)
        if winner is None or winner not in commands:
            return commands
        return (winner,) + tuple(command for command in commands if command != winner)

    def _cached_commands(
        self,
        provider: str,
        provider_settings: UsageProviderSettings,
        commands: tuple[tuple[str, ...], ...],
        now: float,
    ) -> tuple[ProviderUsage | None, list[str]]:
        """Run the usage commands at most once per ``command_interval_seconds``.

        The bar refreshes every minute, but starting a provider CLI a minute is
        both slow and wasteful for windows that move over hours, so the previous
        run's reading is redrawn until the slower cadence comes round again.
        """
        cached = self._command_cache.get(provider)
        if cached is not None and now - cached[0] < self.settings.command_interval_seconds:
            return cached[1], list(cached[2])
        reading, notes = self._read_commands(provider, provider_settings, commands, now)
        self._command_cache[provider] = (now, reading, list(notes))
        return reading, notes

    @staticmethod
    def _restamp(reading: ProviderUsage, now: float) -> ProviderUsage:
        """Date a reused command reading to this poll, so the bar's clock moves."""
        if reading.checked_at == now:
            return reading
        return ProviderUsage(
            reading.provider,
            reading.label,
            reading.summary,
            reading.detail,
            reading.ok,
            now,
            reading.source,
            reading.windows,
        )

    @staticmethod
    def _with_notes(reading: ProviderUsage, notes: list[str]) -> ProviderUsage:
        """Append the usage-command diagnostics to a reading's tooltip detail."""
        if not notes:
            return reading
        detail = "\n".join([text for text in (reading.detail,) if text] + notes)
        return ProviderUsage(
            reading.provider,
            reading.label,
            reading.summary,
            detail,
            reading.ok,
            reading.checked_at,
            reading.source,
            reading.windows,
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

        The payload is a snapshot of a moment that has since passed. Each
        window carries the time it resets, so a window whose reset has already
        gone by is reported as empty: the quota really did refill, and
        redrawing the last recorded percentage would keep claiming usage the
        operator got back hours or days ago.
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
        found: tuple[dict, float, Path] | None = None
        for modified, path in scanned:
            reading = self._last_codex_rate_limits(path)
            if reading is not None:
                rate_limits, recorded_at = reading
                # The event's own timestamp dates the payload exactly; the
                # file's modification time is the closest stand-in when a Codex
                # build writes the line without one.
                found = (rate_limits, modified if recorded_at is None else recorded_at, path)
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

        rate_limits, recorded_at, path = found
        windows: list[UsageWindow] = []
        details: list[str] = []
        for key, fallback_label in _CODEX_WINDOW_KEYS:
            window = rate_limits.get(key)
            if not isinstance(window, dict):
                continue
            used = _number(window.get("used_percent"))
            if used is None:
                continue
            window_label = _window_label(window.get("window_minutes"), fallback_label)
            remaining = _window_remaining_seconds(window, recorded_at, now)
            if remaining is not None and remaining <= 0:
                # The window reset after this payload was written, so every
                # token it recorded has been given back.
                windows.append(UsageWindow(window_label, 0.0))
                details.append(
                    f"{window_label}: 0% used, reset after this reading "
                    f"(was {used:.0f}% {_format_age(now - recorded_at)})"
                )
                continue
            reset_text = _format_duration(remaining)
            windows.append(UsageWindow(window_label, used, reset_text))
            details.append(
                f"{window_label}: {used:.0f}% used" + (f", {reset_text}" if reset_text else "")
            )
        if not windows:
            return ProviderUsage("codex", label, f"{label}: no usage data yet", str(path), False, now, source)

        plan = rate_limits.get("plan_type")
        plan_text = f" ({plan})" if isinstance(plan, str) and plan else ""
        summary = f"{label} " + " · ".join(f"{window.label} {window.used_percent:.0f}%" for window in windows) + plan_text
        # The reading is only as fresh as the turn that produced it; showing
        # its age makes a stale number obvious instead of misleading.
        age = _format_age(now - recorded_at)
        details.append(f"from {path.name} ({age})")
        return ProviderUsage("codex", label, summary, "\n".join(details), True, now, source, tuple(windows))

    def _last_codex_rate_limits(self, path: Path) -> tuple[dict, float | None] | None:
        """Return the newest rate-limit payload in one session log and its time.

        Only the file's tail is read: session logs grow without bound and the
        newest payload is always at the end. A payload without a single usable
        percentage is skipped so an empty trailing entry cannot mask the real
        numbers written earlier in the same session.

        The event's ``timestamp`` is returned beside the payload because the
        reset times inside it are counted from the moment Codex wrote it, not
        from the moment it is read. ``None`` means the line carried no usable
        timestamp and the caller should date the payload some other way.
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
                return rate_limits, _epoch(event.get("timestamp") or payload.get("timestamp"))
        return None

    def read_claude(self, label: str, now: float) -> ProviderUsage:
        """Report today's Claude Code tokens and messages from both local sources.

        The statistics cache is a derived summary: it can be absent, stale, or
        written under keys this reader does not know, and each of those shows
        up as a flat "0 tok · 0 msgs" after a heavy day of work. Session
        transcripts are the raw record of every turn, so they are counted as
        well and each figure is taken from whichever source reports more --
        neither source is ever complete on its own, and a maximum can never
        double-count because both describe the same calendar day.
        """
        stats_path = self._expand(self.settings.claude_stats_file)
        transcripts = self._transcript_usage()
        transcripts.refresh(now)
        today = datetime.fromtimestamp(now).date().isoformat()
        source = f"{stats_path}; {transcripts.root}"

        data, cache_error = self._read_claude_stats(stats_path)
        cache_today, cache_total = self._claude_cache_totals(data, today)
        day = transcripts.day(today)
        transcript_today = _ClaudeTotals(day.tokens, day.messages, len(day.sessions))

        tokens_today = max(cache_today.tokens, transcript_today.tokens)
        messages_today = max(cache_today.messages, transcript_today.messages)
        sessions_today = max(cache_today.sessions, transcript_today.sessions)
        total_tokens = max(cache_total, transcripts.total_tokens)
        if not tokens_today and not messages_today and not total_tokens:
            reasons = [text for text in (cache_error, transcripts.error) if text]
            if not transcripts.scanned_files:
                reasons.append(f"no transcripts in the last {transcripts.scan_days} days under {transcripts.root}")
            return ProviderUsage(
                "claude",
                label,
                f"{label}: no usage data yet",
                "\n".join(reasons),
                False,
                now,
                source,
            )

        computed = (data or {}).get("lastComputedDate")
        computed_text = f" as of {computed}" if isinstance(computed, str) and computed else ""
        summary = f"{label} today {_format_tokens(tokens_today)} tok · {messages_today} msgs"
        # Claude Code publishes rate-limit percentages only on some builds; when
        # it does they are the truth and are drawn as-is. Otherwise the panel
        # would show Claude as bare numbers beside Codex's bars, so the same
        # rolling windows are measured from the transcripts instead.
        windows = self._claude_windows(data or {}, now)
        window_details: list[str] = []
        if not windows:
            windows, window_details = self._claude_rolling_windows(transcripts, now)
        details = [
            f"last {transcripts.scan_days}d {_format_tokens(total_tokens)} tokens; "
            f"{sessions_today} sessions today{computed_text}",
            *window_details,
            f"transcripts: {_format_tokens(transcript_today.tokens)} tok · "
            f"{transcript_today.messages} msgs today from {transcripts.scanned_files} files",
            f"stats cache: {_format_tokens(cache_today.tokens)} tok · {cache_today.messages} msgs today",
        ]
        if cache_error:
            details.append(cache_error)
        if transcripts.error:
            details.append(transcripts.error)
        return ProviderUsage(
            "claude",
            label,
            summary,
            "\n".join(details),
            True,
            now,
            source,
            windows,
        )

    def read_claude_account_usage(self, now: float | None = None) -> ClaudeAccountUsage:
        """Total every Claude Code token on this machine, not just Daedalus tasks.

        The coding statistics screen answers "how much Claude have I used?",
        which is a different question from the usage bar's "how much today?".
        Both local sources are read and each figure is taken from whichever
        reports more: the statistics cache keeps all-time per-model totals but
        can be missing or stale, while transcripts are the raw per-turn record
        but only for the sessions still on disk. Neither source is complete on
        its own, and a maximum cannot double-count because both describe the
        same spend.

        This scan can touch every transcript ever written, so callers should run
        it off the UI thread. It never raises: any problem is reported in
        ``detail`` with ``ok`` false.
        """
        now = time.time() if now is None else now
        stats_path = self._expand(self.settings.claude_stats_file)
        transcripts = self._account_transcript_usage()
        transcripts.refresh(now)
        today = datetime.fromtimestamp(now).date().isoformat()

        data, cache_error = self._read_claude_stats(stats_path)
        cache_today, cache_total = self._claude_cache_totals(data, today)
        day = transcripts.day(today)
        total_tokens = max(cache_total, transcripts.total_tokens)
        messages = sum(totals.messages for totals in transcripts.days.values())
        recorded_days = sorted(transcripts.days)

        details = [
            f"transcripts: {_format_tokens(transcripts.total_tokens)} tokens from "
            f"{transcripts.scanned_files} files under {transcripts.root}",
            f"stats cache: {_format_tokens(cache_total)} tokens from {stats_path}",
        ]
        for reason in (cache_error, transcripts.error):
            if reason:
                details.append(reason)
        if not total_tokens and not transcripts.scanned_files:
            details.append(f"no transcripts found under {transcripts.root}")
        return ClaudeAccountUsage(
            total_tokens=total_tokens,
            today_tokens=max(cache_today.tokens, day.tokens),
            transcript_tokens=transcripts.total_tokens,
            cache_tokens=cache_total,
            messages=messages,
            scanned_files=transcripts.scanned_files,
            first_day=recorded_days[0] if recorded_days else "",
            days_recorded=len(recorded_days),
            ok=total_tokens > 0,
            detail="\n".join(details),
            source=f"{stats_path}; {transcripts.root}",
        )

    def _account_transcript_usage(self) -> ClaudeTranscriptUsage:
        """Return the account-wide transcript reader, keeping its offsets between reads."""
        root = self._expand(self.settings.claude_projects_dir)
        if (
            self._claude_account_transcripts is None
            or self._claude_account_transcripts.root != root
        ):
            self._claude_account_transcripts = ClaudeTranscriptUsage(
                root,
                scan_days=self.settings.claude_account_scan_days,
            )
        return self._claude_account_transcripts

    def _claude_rolling_windows(
        self,
        transcripts: ClaudeTranscriptUsage,
        now: float,
    ) -> tuple[tuple[UsageWindow, ...], list[str]]:
        """Draw Claude's 5h and 7d token usage against its configured budgets.

        A budget of 0 means none was configured -- Claude Code stores no plan
        limit locally, so inventing one would draw a bar that is either pinned
        at 100% or permanently near empty. The busiest equivalent window in the
        scanned transcripts is used instead, which makes a full bar mean "as
        busy as you have ever been" and keeps the bar honest for any plan.
        """
        limits = (
            self.settings.claude_five_hour_token_limit,
            self.settings.claude_weekly_token_limit,
        )
        windows: list[UsageWindow] = []
        details: list[str] = []
        for (label, seconds), limit in zip(_CLAUDE_ROLLING_WINDOWS, limits):
            used = transcripts.window_tokens(now, seconds)
            budget = int(limit) if limit and limit > 0 else transcripts.peak_window_tokens(seconds)
            if budget <= 0:
                continue
            percent = min(100.0, used / budget * 100.0)
            rolloff = _format_rolloff(transcripts.window_rolloff_seconds(now, seconds))
            windows.append(UsageWindow(label, percent, rolloff))
            basis = (
                f"of a {_format_tokens(budget)} budget"
                if limit and limit > 0
                else f"of your busiest {label} in {transcripts.scan_days}d ({_format_tokens(budget)})"
            )
            details.append(
                f"{label}: {_format_tokens(used)} tokens, {percent:.0f}% {basis}"
                + (f", {rolloff}" if rolloff else "")
            )
        return tuple(windows), details

    def _transcript_usage(self) -> ClaudeTranscriptUsage:
        """Return the transcript reader, keeping its per-file offsets between polls."""
        root = self._expand(self.settings.claude_projects_dir)
        if self._claude_transcripts is None or self._claude_transcripts.root != root:
            self._claude_transcripts = ClaudeTranscriptUsage(
                root,
                scan_days=self.settings.claude_transcript_days,
            )
        return self._claude_transcripts

    @staticmethod
    def _read_claude_stats(path: Path) -> tuple[dict | None, str | None]:
        """Load the statistics cache, describing rather than raising any problem."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None, f"{path} not found"
        except (OSError, json.JSONDecodeError) as error:
            return None, f"{path}: {error}"
        if not isinstance(data, dict):
            return None, f"{path}: unexpected shape"
        return data, None

    @staticmethod
    def _claude_cache_totals(data: dict | None, today: str) -> tuple[_ClaudeTotals, int]:
        """Return the cache's totals for ``today`` and its all-time token count."""
        if not data:
            return _ClaudeTotals(), 0
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
                total_tokens += _claude_usage_tokens(usage)
        return _ClaudeTotals(tokens_today, messages_today, sessions_today), total_tokens

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

    def _read_commands(
        self,
        provider: str,
        provider_settings: UsageProviderSettings,
        commands: tuple[tuple[str, ...], ...],
        now: float,
    ) -> tuple[ProviderUsage | None, list[str]]:
        """Try each candidate command, stopping at the first that yields windows.

        Returns the best reading and a note per command that did not work. The
        notes are what make a misconfigured command diagnosable: without them a
        renamed subcommand looks identical to a provider with no usage at all.
        """
        notes: list[str] = []
        best: ProviderUsage | None = None
        for command in commands:
            reading = self._read_command(provider, provider_settings, command, now)
            if reading.windows:
                self._winning_command[provider] = command
                return reading, notes
            notes.append(f"{' '.join(command)}: {reading.detail or reading.summary}")
            if best is None or (reading.ok and not best.ok):
                best = reading
        self._winning_command.pop(provider, None)
        return best, notes

    def _read_command(
        self,
        provider: str,
        provider_settings: UsageProviderSettings,
        command: tuple[str, ...],
        now: float,
    ) -> ProviderUsage:
        source = " ".join(command)
        result = self._capture(command, provider_settings)
        if result.error:
            return ProviderUsage(
                provider,
                provider_settings.label,
                f"{provider_settings.label}: unavailable",
                f"{source}: {scrub_credentials(result.error)}",
                False,
                now,
                source,
            )
        output = result.output
        windows = self._windows_from_output(provider, output, now)
        if result.timed_out and not windows:
            return ProviderUsage(
                provider,
                provider_settings.label,
                f"{provider_settings.label}: usage command timed out",
                f"{source} produced no percentages within {self.settings.command_timeout_seconds:g}s",
                False,
                now,
                source,
            )
        # A CLI that renders a panel and then waits is killed at the timeout, so
        # a non-zero exit is expected whenever the output already holds the
        # numbers; only treat it as a failure when nothing was parsed.
        if not windows and result.returncode not in (0, None):
            text = output.strip()
            reason = scrub_credentials(text.splitlines()[-1] if text else f"exit {result.returncode}")
            return ProviderUsage(
                provider,
                provider_settings.label,
                f"{provider_settings.label}: unavailable",
                f"{source}: {reason}",
                False,
                now,
                source,
            )
        summary, detail = self._summarize_output(provider_settings.label, output)
        if windows:
            # The scraped percentages are the point of running the command, so
            # they lead the summary; the CLI's own first line stays in detail.
            summary = f"{provider_settings.label} " + " · ".join(
                f"{window.label} {window.used_percent:.0f}%" for window in windows
            )
            detail = "\n".join(
                [
                    f"{window.label}: {window.used_percent:.0f}% used"
                    + (f", {window.reset_text}" if window.reset_text else "")
                    for window in windows
                ]
                + [f"from `{source}`"]
            )
        return ProviderUsage(provider, provider_settings.label, summary, detail, True, now, source, windows)

    def _windows_from_output(self, provider: str, output: str, now: float) -> tuple[UsageWindow, ...]:
        """Read windows from a command's output, JSON first and then rendered text."""
        try:
            payload = json.loads(output.strip())
        except (json.JSONDecodeError, ValueError):
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
            if windows:
                return windows
        return _windows_from_text(output)

    # --- running a usage command -------------------------------------------------------

    def _command_env(self, provider_settings: UsageProviderSettings) -> dict[str, str]:
        """The environment a usage command runs in.

        ``TERM`` is set because a CLI that finds no terminal type falls back to
        a dumb terminal and may refuse to draw the panel being scraped.
        """
        env = dict(os.environ)
        env.setdefault("TERM", "xterm-256color")
        env.update(provider_settings.env)
        return env

    def _capture(self, command: tuple[str, ...], provider_settings: UsageProviderSettings) -> _CommandResult:
        """Run one usage command and return whatever it managed to print."""
        if provider_settings.use_pty and os.name == "posix":
            return self._capture_pty(command, provider_settings)
        return self._capture_pipe(command, provider_settings)

    def _capture_pipe(self, command: tuple[str, ...], provider_settings: UsageProviderSettings) -> _CommandResult:
        """Run a command on plain pipes with stdin closed."""
        try:
            process = subprocess.Popen(
                list(command),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=self._command_env(provider_settings),
                start_new_session=os.name == "posix",
            )
        except OSError as error:
            return _CommandResult(error=str(error))
        try:
            stdout, _ = process.communicate(timeout=self.settings.command_timeout_seconds)
            return _CommandResult(output=stdout or "", returncode=process.returncode)
        except subprocess.TimeoutExpired:
            self._terminate(process)
            stdout, _ = process.communicate()
            return _CommandResult(output=stdout or "", returncode=process.returncode, timed_out=True)

    def _capture_pty(self, command: tuple[str, ...], provider_settings: UsageProviderSettings) -> _CommandResult:
        """Run a command attached to a pseudo-terminal and read what it draws.

        This is what lets a CLI that refuses or hangs without a terminal be read
        at all. The panel is often drawn and then left on screen while the CLI
        waits for a keypress, so reaching the timeout is a normal outcome, not a
        failure: the text captured up to that point already contains the
        percentages and is returned for parsing.
        """
        import fcntl
        import pty
        import select
        import struct
        import termios

        try:
            pid, master = pty.fork()
        except OSError as error:
            return _CommandResult(error=str(error))
        if pid == 0:  # pragma: no cover - replaced by the CLI immediately
            try:
                os.execvpe(command[0], list(command), self._command_env(provider_settings))
            except BaseException:
                pass
            os._exit(127)

        try:
            fcntl.ioctl(
                master,
                termios.TIOCSWINSZ,
                struct.pack("HHHH", self.settings.pty_lines, self.settings.pty_columns, 0, 0),
            )
        except OSError:
            # A terminal that will not be resized still produces output.
            pass

        deadline = time.monotonic() + self.settings.command_timeout_seconds
        typed = not provider_settings.input_text
        type_at = time.monotonic() + max(0.0, self.settings.input_delay_seconds)
        chunks: list[bytes] = []
        timed_out = False
        try:
            os.set_blocking(master, False)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                if not typed and time.monotonic() >= type_at:
                    typed = True
                    try:
                        os.write(master, provider_settings.input_text.encode("utf-8"))
                    except OSError:
                        pass
                wait = min(0.2, remaining) if not typed else min(0.5, remaining)
                readable, _, _ = select.select([master], [], [], wait)
                if not readable:
                    continue
                try:
                    data = os.read(master, 65_536)
                except OSError:
                    # The child exited and closed its side of the terminal.
                    break
                if not data:
                    break
                chunks.append(data)
        finally:
            returncode = self._reap(pid, master, timed_out)
        return _CommandResult(
            output=b"".join(chunks).decode("utf-8", errors="replace"),
            returncode=returncode,
            timed_out=timed_out,
        )

    @staticmethod
    def _reap(pid: int, master: int, timed_out: bool) -> int | None:
        """Close the terminal and stop the child, returning its exit status."""
        if timed_out:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except OSError:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
        try:
            os.close(master)
        except OSError:
            pass
        try:
            _, status = os.waitpid(pid, 0)
        except OSError:
            return None
        if os.WIFEXITED(status):
            return os.WEXITSTATUS(status)
        return None

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
    "CLAUDE_PERMISSION_FLAGS",
    "CODEX_PERMISSION_FLAGS",
    "ROLLING_BUCKET_SECONDS",
    "DEFAULT_BAR_WIDTH",
    "DEFAULT_CLAUDE_USAGE_COMMANDS",
    "DEFAULT_CODEX_USAGE_COMMANDS",
    "DEFAULT_COMMAND_INTERVAL_SECONDS",
    "DEFAULT_INPUT_DELAY_SECONDS",
    "DEFAULT_PTY_COLUMNS",
    "DEFAULT_PTY_LINES",
    "DEFAULT_CLAUDE_ACCOUNT_SCAN_DAYS",
    "DEFAULT_CLAUDE_TRANSCRIPT_DAYS",
    "DEFAULT_COMMAND_TIMEOUT_SECONDS",
    "DEFAULT_INTERVAL_SECONDS",
    "DEFAULT_SESSION_SCAN_LIMIT",
    "DEFAULT_SESSION_TAIL_BYTES",
    "ClaudeAccountUsage",
    "ClaudeDayUsage",
    "ClaudeTranscriptUsage",
    "ProviderUsage",
    "UsageMonitor",
    "UsageProviderSettings",
    "UsageSettings",
    "UsageWindow",
    "format_bar",
    "format_usage_bar",
]
