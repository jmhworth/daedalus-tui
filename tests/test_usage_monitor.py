"""Usage bar readings from local provider data and configured commands."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from tui.usage_monitor import (
    ClaudeTranscriptUsage,
    ProviderUsage,
    UsageMonitor,
    UsageProviderSettings,
    UsageSettings,
    UsageWindow,
    format_bar,
    format_usage_bar,
)


def _stamp(moment: float) -> str:
    """Render an epoch time the way Claude Code timestamps a transcript turn."""
    return datetime.fromtimestamp(moment, timezone.utc).isoformat().replace("+00:00", "Z")


class UsageMonitorTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.home = Path(self._directory.name)
        (self.home / ".codex" / "sessions" / "2026" / "09" / "15").mkdir(parents=True)
        (self.home / ".claude").mkdir()

    def tearDown(self):
        self._directory.cleanup()

    def write_claude_transcript(self, name: str, entries: list[dict], now: float) -> Path:
        """Write one session transcript and date it so the scan window keeps it."""
        path = self.home / ".claude" / "projects" / "-workspace-project" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8")
        os.utime(path, (now, now))
        return path

    @staticmethod
    def transcript_turn(uuid: str, timestamp: str, *, kind: str = "assistant", tokens: int = 0, content=None) -> dict:
        message: dict = {"role": kind, "content": content if content is not None else "text"}
        if kind == "assistant":
            message["usage"] = {
                "input_tokens": tokens,
                "output_tokens": 0,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            }
        return {
            "type": kind,
            "uuid": uuid,
            "sessionId": "session-1",
            "timestamp": timestamp,
            "message": message,
        }

    def write_codex_session(self, name: str, used_primary: float, used_secondary: float, now: float) -> None:
        path = self.home / ".codex" / "sessions" / "2026" / "09" / "15" / name
        events = [
            {"type": "event_msg", "payload": {"type": "agent_message", "message": "hi"}},
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "rate_limits": {
                        "primary": {"used_percent": used_primary, "window_minutes": 300, "resets_at": now + 3600 * 4 + 120},
                        "secondary": {"used_percent": used_secondary, "window_minutes": 10080, "resets_at": now + 86400 * 3},
                        "plan_type": "plus",
                    },
                },
            },
        ]
        path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")

    def test_codex_reading_uses_newest_session_rate_limits(self):
        now = 1_800_000_000.0
        self.write_codex_session("rollout-old.jsonl", 10, 20, now)
        self.write_codex_session("rollout-new.jsonl", 30, 46, now)
        newer = self.home / ".codex" / "sessions" / "2026" / "09" / "15" / "rollout-new.jsonl"
        os.utime(newer, (now + 10, now + 10))
        monitor = UsageMonitor(UsageSettings(), home=self.home)
        reading = monitor.read_codex("Codex", now)
        self.assertTrue(reading.ok)
        self.assertEqual(reading.summary, "Codex 5h 30% · week 46% (plus)")
        self.assertIn("resets in 4h 02m", reading.detail)
        self.assertIn("resets in 3d 0h", reading.detail)

    def test_claude_reading_sums_todays_tokens_and_messages(self):
        now = 1_800_000_000.0
        from datetime import datetime

        today = datetime.fromtimestamp(now).date().isoformat()
        stats = {
            "dailyActivity": [{"date": today, "messageCount": 8, "sessionCount": 2}, {"date": "2020-01-01", "messageCount": 99}],
            "dailyModelTokens": [{"date": today, "tokensByModel": {"claude-opus-5": 12_000, "claude-sonnet-5": 300}}],
            "modelUsage": {"claude-opus-5": {"inputTokens": 1_000_000, "outputTokens": 500}},
            "lastComputedDate": today,
        }
        (self.home / ".claude" / "stats-cache.json").write_text(json.dumps(stats), encoding="utf-8")
        reading = UsageMonitor(UsageSettings(), home=self.home).read_claude("Claude", now)
        self.assertTrue(reading.ok)
        self.assertEqual(reading.summary, "Claude today 12.3k tok · 8 msgs")
        self.assertIn("1.0M tokens", reading.detail)
        self.assertIn("2 sessions today", reading.detail)

    def test_claude_reading_counts_transcripts_when_the_stats_cache_is_stale(self):
        """A cache without today's numbers must not flatten the panel to zero."""
        now = 1_800_000_000.0
        stamp = datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")
        (self.home / ".claude" / "stats-cache.json").write_text(
            json.dumps(
                {
                    "dailyActivity": [{"date": "2020-01-01", "messageCount": 99, "sessionCount": 3}],
                    "lastComputedDate": "2020-01-01",
                }
            ),
            encoding="utf-8",
        )
        self.write_claude_transcript(
            "session-1.jsonl",
            [
                self.transcript_turn("u1", stamp, kind="user"),
                self.transcript_turn("a1", stamp, tokens=1_200),
                # Tool results are stored as user turns and are not messages.
                self.transcript_turn("u2", stamp, kind="user", content=[{"type": "tool_result", "content": "ok"}]),
                self.transcript_turn("a2", stamp, tokens=800),
                self.transcript_turn("a3", "2020-01-01T00:00:00Z", tokens=5_000),
            ],
            now,
        )

        reading = UsageMonitor(UsageSettings(), home=self.home).read_claude("Claude", now)

        self.assertTrue(reading.ok)
        self.assertEqual(reading.summary, "Claude today 2.0k tok · 3 msgs")
        self.assertIn("1 sessions today", reading.detail)
        self.assertEqual(reading.checked_at, now)
        self.assertIn(str(self.home / ".claude" / "projects"), reading.source)

    def test_transcripts_are_read_incrementally_and_replayed_turns_counted_once(self):
        now = 1_800_000_000.0
        today = datetime.fromtimestamp(now).date().isoformat()
        stamp = datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")
        path = self.write_claude_transcript(
            "session-1.jsonl",
            [self.transcript_turn("a1", stamp, tokens=100)],
            now,
        )
        usage = ClaudeTranscriptUsage(self.home / ".claude" / "projects")
        usage.refresh(now)
        self.assertEqual((usage.day(today).tokens, usage.day(today).messages), (100, 1))

        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(self.transcript_turn("a2", stamp, tokens=50)) + "\n")
            # A resumed or forked session replays earlier turns; the uuid keeps
            # them from being billed twice.
            handle.write(json.dumps(self.transcript_turn("a1", stamp, tokens=100)) + "\n")
            # A turn still being written has no line break yet.
            handle.write(json.dumps(self.transcript_turn("a3", stamp, tokens=25)))
        os.utime(path, (now, now))
        usage.refresh(now)
        self.assertEqual((usage.day(today).tokens, usage.day(today).messages), (150, 2))

        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n")
        os.utime(path, (now, now))
        usage.refresh(now)
        self.assertEqual((usage.day(today).tokens, usage.day(today).messages), (175, 3))
        self.assertEqual(usage.total_tokens, 175)

    def test_transcripts_outside_the_scan_window_are_skipped(self):
        now = 1_800_000_000.0
        stamp = datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")
        self.write_claude_transcript(
            "old-session.jsonl",
            [self.transcript_turn("a1", stamp, tokens=100)],
            now - 86_400 * 45,
        )
        usage = ClaudeTranscriptUsage(self.home / ".claude" / "projects", scan_days=30)

        self.assertEqual(usage.refresh(now), 0)
        self.assertEqual(usage.total_tokens, 0)

    def test_claude_account_usage_counts_every_project_beyond_the_bar_window(self):
        """Ctrl+T reports the whole Claude spend, not just the bar's recent window."""
        now = 1_800_000_000.0
        stamp = datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")
        old_stamp = datetime.fromtimestamp(now - 86_400 * 200, timezone.utc).isoformat().replace("+00:00", "Z")
        self.write_claude_transcript(
            "session-now.jsonl",
            [self.transcript_turn("a1", stamp, tokens=1_000)],
            now,
        )
        # A different project, last touched long before the usage bar's window.
        old = self.home / ".claude" / "projects" / "-workspace-other" / "session-old.jsonl"
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_text(json.dumps(self.transcript_turn("a2", old_stamp, tokens=9_000)) + "\n", encoding="utf-8")
        os.utime(old, (now - 86_400 * 200, now - 86_400 * 200))
        monitor = UsageMonitor(UsageSettings(), home=self.home)

        account = monitor.read_claude_account_usage(now)

        self.assertTrue(account.ok)
        self.assertEqual(account.total_tokens, 10_000)
        self.assertEqual(account.today_tokens, 1_000)
        self.assertEqual(account.scanned_files, 2)
        self.assertEqual(account.days_recorded, 2)
        # The bar's 30-day reading still sees only the recent transcript, so the
        # wide scan cannot have redefined the window the bar reports.
        self.assertIn("last 30d 1.0k tokens", monitor.read_claude("Claude", now).detail)

    def test_claude_account_usage_prefers_the_larger_of_cache_and_transcripts(self):
        """The cache keeps totals for transcripts that are no longer on disk."""
        now = 1_800_000_000.0
        stamp = datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")
        self.write_claude_transcript(
            "session-1.jsonl",
            [self.transcript_turn("a1", stamp, tokens=2_000)],
            now,
        )
        (self.home / ".claude" / "stats-cache.json").write_text(
            json.dumps({"modelUsage": {"claude-opus-5": {"inputTokens": 5_000_000, "outputTokens": 1_000}}}),
            encoding="utf-8",
        )

        account = UsageMonitor(UsageSettings(), home=self.home).read_claude_account_usage(now)

        self.assertEqual(account.total_tokens, 5_001_000)
        self.assertEqual(account.transcript_tokens, 2_000)
        self.assertEqual(account.cache_tokens, 5_001_000)
        self.assertIn("stats cache", account.detail)

    def test_claude_account_usage_reports_missing_data_without_raising(self):
        account = UsageMonitor(UsageSettings(), home=self.home).read_claude_account_usage(1_800_000_000.0)

        self.assertFalse(account.ok)
        self.assertEqual(account.total_tokens, 0)
        self.assertIn("no transcripts found", account.detail)

    def write_rolling_claude_history(self, now: float) -> None:
        """Three turns: one inside 5h, one inside 7d, and an older busier one."""
        self.write_claude_transcript(
            "session-rolling.jsonl",
            [
                self.transcript_turn("a1", _stamp(now - 4 * 3600), tokens=4_000),
                self.transcript_turn("a2", _stamp(now - 2 * 86_400), tokens=6_000),
                self.transcript_turn("a3", _stamp(now - 20 * 86_400), tokens=30_000),
            ],
            now,
        )

    def test_claude_bars_are_drawn_from_rolling_transcript_windows(self):
        """Without a published rate limit, Claude still gets 5h and 7d bars."""
        now = 1_800_000_000.0
        self.write_rolling_claude_history(now)

        reading = UsageMonitor(UsageSettings(), home=self.home).read_claude("Claude", now)

        self.assertTrue(reading.ok)
        windows = {window.label: window.used_percent for window in reading.windows}
        # The busiest 5h and 7d stretches both hold the older 30k turn, so the
        # current windows are measured against it.
        self.assertAlmostEqual(windows["5h"], 4_000 / 30_000 * 100, places=1)
        self.assertAlmostEqual(windows["7d"], 10_000 / 30_000 * 100, places=1)
        self.assertIn("of your busiest 5h in 30d (30.0k)", reading.detail)
        self.assertIn("frees up in", reading.detail)

    def test_configured_claude_budgets_replace_the_calibrated_ones(self):
        now = 1_800_000_000.0
        self.write_rolling_claude_history(now)
        settings = UsageSettings(
            claude_five_hour_token_limit=20_000,
            claude_weekly_token_limit=100_000,
        )

        reading = UsageMonitor(settings, home=self.home).read_claude("Claude", now)

        self.assertEqual(
            [(window.label, round(window.used_percent, 1)) for window in reading.windows],
            [("5h", 20.0), ("7d", 10.0)],
        )
        self.assertIn("of a 20.0k budget", reading.detail)

    def test_published_rate_limits_win_over_the_transcript_windows(self):
        """A real limit from Claude Code must never be replaced by an estimate."""
        now = 1_800_000_000.0
        self.write_rolling_claude_history(now)
        (self.home / ".claude" / "stats-cache.json").write_text(
            json.dumps({"rate_limits": {"five_hour": {"used_percentage": 71.0}}}),
            encoding="utf-8",
        )

        reading = UsageMonitor(UsageSettings(), home=self.home).read_claude("Claude", now)

        self.assertEqual([(window.label, window.used_percent) for window in reading.windows], [("5h", 71.0)])
        self.assertNotIn("busiest", reading.detail)

    def test_rolling_windows_sum_recent_tokens_and_track_the_peak(self):
        now = 1_800_000_000.0
        self.write_rolling_claude_history(now)
        usage = ClaudeTranscriptUsage(self.home / ".claude" / "projects")
        usage.refresh(now)

        self.assertEqual(usage.window_tokens(now, 5 * 3600), 4_000)
        self.assertEqual(usage.window_tokens(now, 7 * 86_400), 10_000)
        self.assertEqual(usage.peak_window_tokens(5 * 3600), 30_000)
        # The oldest tokens in the 5h window were spent four hours ago.
        rolloff = usage.window_rolloff_seconds(now, 5 * 3600)
        self.assertIsNotNone(rolloff)
        self.assertLessEqual(abs(rolloff - 3600), 300)
        # A window can never exceed the peak it is measured against.
        self.assertLessEqual(usage.window_tokens(now, 7 * 86_400), usage.peak_window_tokens(7 * 86_400))

    def test_rolling_buckets_are_pruned_to_the_scan_window(self):
        """Buckets must not accumulate forever while daily totals stay whole."""
        now = 1_800_000_000.0
        self.write_claude_transcript(
            "session-old.jsonl",
            [self.transcript_turn("a1", _stamp(now - 40 * 86_400), tokens=7_000)],
            now,
        )
        usage = ClaudeTranscriptUsage(self.home / ".claude" / "projects", scan_days=30)
        usage.refresh(now)

        self.assertEqual(usage.total_tokens, 7_000)
        self.assertEqual(usage.buckets, {})
        self.assertEqual(usage.peak_window_tokens(7 * 86_400), 0)

    def test_claude_reading_draws_rate_limit_windows_when_present(self):
        now = 1_800_000_000.0
        from datetime import datetime

        today = datetime.fromtimestamp(now).date().isoformat()
        stats = {
            "dailyActivity": [{"date": today, "messageCount": 8, "sessionCount": 2}],
            "dailyModelTokens": [{"date": today, "tokensByModel": {"claude-opus-5": 12_000}}],
            "rate_limits": {
                "five_hour": {"used_percentage": 23.5, "resets_at": now + 3600},
                "seven_day": {"used_percentage": 41.2, "resets_at": "2026-12-01T00:00:00Z"},
            },
        }
        (self.home / ".claude" / "stats-cache.json").write_text(json.dumps(stats), encoding="utf-8")

        reading = UsageMonitor(UsageSettings(), home=self.home).read_claude("Claude", now)

        self.assertEqual(
            [(window.label, window.used_percent) for window in reading.windows],
            [("5h", 23.5), ("7d", 41.2)],
        )
        self.assertEqual(reading.windows[0].reset_text, "resets in 1h 00m")

    def test_missing_data_is_reported_without_raising(self):
        monitor = UsageMonitor(UsageSettings(), home=self.home)
        readings = monitor.poll(now=1_800_000_000.0)
        self.assertEqual([reading.provider for reading in readings], ["claude", "codex"])
        self.assertFalse(any(reading.ok for reading in readings))
        self.assertIn("no usage data yet", readings[0].summary)
        self.assertIn("no sessions yet", readings[1].summary)

    def test_configured_command_runs_non_interactively_with_timeout(self):
        settings = UsageSettings(
            command_timeout_seconds=5,
            providers={
                "codex": UsageProviderSettings(
                    "Codex",
                    (sys.executable, "-c", "import sys; print('used 42% of weekly limit'); assert sys.stdin.read() == ''"),
                ),
                "claude": UsageProviderSettings(
                    "Claude",
                    (sys.executable, "-c", "import json; print(json.dumps({'usage_percent': 12, 'other': 1}))"),
                ),
            },
        )
        readings = UsageMonitor(settings, home=self.home).poll(now=1_800_000_000.0)
        by_provider = {reading.provider: reading for reading in readings}
        self.assertTrue(by_provider["codex"].ok)
        self.assertEqual(by_provider["codex"].summary, "Codex used 42% of weekly limit")
        self.assertEqual(by_provider["claude"].summary, "Claude usage_percent=12")

    def test_timed_out_and_failing_commands_are_reported(self):
        settings = UsageSettings(
            command_timeout_seconds=0.5,
            providers={
                "codex": UsageProviderSettings("Codex", (sys.executable, "-c", "import time; time.sleep(5)")),
                "claude": UsageProviderSettings("Claude", (sys.executable, "-c", "import sys; sys.exit('stdin is not a terminal')")),
            },
        )
        readings = UsageMonitor(settings, home=self.home).poll(now=1_800_000_000.0)
        by_provider = {reading.provider: reading for reading in readings}
        self.assertFalse(by_provider["codex"].ok)
        self.assertIn("timed out", by_provider["codex"].summary)
        self.assertFalse(by_provider["claude"].ok)
        self.assertIn("stdin is not a terminal", by_provider["claude"].detail)

    def test_format_usage_bar_lists_each_summary_with_a_timestamp(self):
        readings = (
            ProviderUsage("claude", "Claude", "Claude today 1.0k tok · 2 msgs", checked_at=1_800_000_000.0),
            ProviderUsage("codex", "Codex", "Codex 5h 30% · week 46%", checked_at=1_800_000_000.0),
        )
        text = format_usage_bar(readings)
        self.assertTrue(text.startswith("Usage ("))
        lines = text.splitlines()
        self.assertIn("Claude today 1.0k tok · 2 msgs", lines)
        self.assertIn("Codex 5h 30% · week 46%", lines)
        self.assertEqual(format_usage_bar(()), "Usage: —")

    def test_percentage_windows_are_drawn_as_progress_bars(self):
        readings = (
            ProviderUsage(
                "codex",
                "Codex",
                "Codex 5h 30% · week 46%",
                checked_at=1_800_000_000.0,
                windows=(UsageWindow("5h", 30.0, "resets in 2h"), UsageWindow("week", 46.0)),
            ),
            ProviderUsage(
                "claude",
                "Claude",
                "Claude today 1.0k tok",
                checked_at=1_800_000_000.0,
                windows=(UsageWindow("5h", 23.5),),
            ),
        )
        lines = format_usage_bar(readings, bar_width=10).splitlines()
        self.assertEqual(lines[2], "  5h   ███░░░░░░░  30%")
        self.assertEqual(lines[3], "  week █████░░░░░  46%")
        self.assertEqual(lines[4], "Claude today 1.0k tok")
        self.assertEqual(lines[5], "  5h   ██░░░░░░░░  24%")

    def test_bars_keep_any_usage_visible_and_the_limit_distinct(self):
        self.assertEqual(format_bar(0, 10), "░░░░░░░░░░")
        # Rounding to zero would hide real usage; a full bar must mean 100%.
        self.assertEqual(format_bar(1, 10), "█░░░░░░░░░")
        self.assertEqual(format_bar(99.6, 10), "█████████░")
        self.assertEqual(format_bar(100, 10), "██████████")
        self.assertEqual(format_bar(140, 10), "██████████")

    def test_codex_reading_skips_a_started_session_without_rate_limits(self):
        """A just-started session has no usage yet; older numbers still apply."""
        now = 1_800_000_000.0
        self.write_codex_session("rollout-old.jsonl", 62, 31, now)
        directory = self.home / ".codex" / "sessions" / "2026" / "09" / "15"
        started = directory / "rollout-fresh.jsonl"
        started.write_text(
            json.dumps({"type": "event_msg", "payload": {"type": "agent_message", "message": "hi"}}) + "\n",
            encoding="utf-8",
        )
        os.utime(started, (now + 30, now + 30))
        reading = UsageMonitor(UsageSettings(), home=self.home).read_codex("Codex", now)
        self.assertTrue(reading.ok)
        self.assertEqual(reading.summary, "Codex 5h 62% · week 31% (plus)")
        self.assertEqual([window.used_percent for window in reading.windows], [62, 31])

    def write_codex_relative_session(self, recorded_at: float, *, timestamp: bool = True) -> Path:
        """Write a payload whose resets are durations counted from its own time."""
        path = self.home / ".codex" / "sessions" / "2026" / "09" / "15" / "rollout.jsonl"
        event: dict = {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "plan_type": "pro",
                "rate_limits": {
                    "primary": {"used_percent": 12.4, "window_minutes": 300, "resets_in_seconds": 5_400},
                    "secondary": {"used_percent": 88.0, "window_minutes": 10080, "resets_in_seconds": 90_000},
                },
            },
        }
        if timestamp:
            event["timestamp"] = _stamp(recorded_at)
        path.write_text(json.dumps(event) + "\n", encoding="utf-8")
        os.utime(path, (recorded_at, recorded_at))
        return path

    def test_codex_reading_accepts_the_relative_reset_field(self):
        """Codex reports ``resets_in_seconds``; only ``resets_at`` was read."""
        now = 1_800_000_000.0
        self.write_codex_relative_session(now)
        reading = UsageMonitor(UsageSettings(), home=self.home).read_codex("Codex", now)
        self.assertTrue(reading.ok)
        self.assertEqual(reading.summary, "Codex 5h 12% · week 88% (pro)")
        self.assertIn("resets in 1h 30m", reading.detail)
        self.assertIn("resets in 1d 1h", reading.detail)

    def test_a_relative_reset_counts_down_from_when_codex_wrote_it(self):
        """The countdown must not restart on every poll of the same payload."""
        now = 1_800_000_000.0
        self.write_codex_relative_session(now - 3_600)
        reading = UsageMonitor(UsageSettings(), home=self.home).read_codex("Codex", now)
        # 5_400s recorded an hour ago leaves half an hour, not another 90m.
        self.assertIn("resets in 30m", reading.detail)
        self.assertEqual([window.used_percent for window in reading.windows], [12.4, 88.0])

    def test_a_window_that_has_already_reset_reports_no_usage(self):
        """The bug: a finished 5h window kept showing its last percentage."""
        now = 1_800_000_000.0
        self.write_codex_relative_session(now - 6 * 3_600)
        reading = UsageMonitor(UsageSettings(), home=self.home).read_codex("Codex", now)
        self.assertTrue(reading.ok)
        # The 5h window reset four and a half hours ago; the weekly one has not.
        self.assertEqual(reading.summary, "Codex 5h 0% · week 88% (pro)")
        self.assertEqual([window.used_percent for window in reading.windows], [0.0, 88.0])
        self.assertIn("5h: 0% used, reset after this reading (was 12%", reading.detail)
        self.assertIn("resets in 19h 00m", reading.detail)

    def test_a_reset_window_is_detected_without_an_event_timestamp(self):
        """An older Codex line without a timestamp is dated by the file itself."""
        now = 1_800_000_000.0
        self.write_codex_relative_session(now - 6 * 3_600, timestamp=False)
        reading = UsageMonitor(UsageSettings(), home=self.home).read_codex("Codex", now)
        self.assertEqual(reading.summary, "Codex 5h 0% · week 88% (pro)")

    def test_an_absolute_reset_that_has_passed_also_reports_no_usage(self):
        """``resets_at`` in the past means the quota refilled, whatever its age."""
        now = 1_800_000_000.0
        # The helper's resets_at values sit ahead of ``recorded``, so a session
        # written three days ago has a long-expired 5h window.
        recorded = now - 3 * 86_400
        self.write_codex_session("rollout.jsonl", 34, 12, recorded)
        path = self.home / ".codex" / "sessions" / "2026" / "09" / "15" / "rollout.jsonl"
        os.utime(path, (recorded, recorded))
        reading = UsageMonitor(UsageSettings(), home=self.home).read_codex("Codex", now)
        self.assertEqual(reading.summary, "Codex 5h 0% · week 0% (plus)")
        self.assertIn("3d 0h ago", reading.detail)

    def test_an_empty_trailing_payload_does_not_hide_the_real_numbers(self):
        now = 1_800_000_000.0
        path = self.home / ".codex" / "sessions" / "2026" / "09" / "15" / "rollout.jsonl"
        events = [
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "rate_limits": {"primary": {"used_percent": 55, "window_minutes": 300}},
                },
            },
            {"type": "event_msg", "payload": {"type": "token_count", "rate_limits": {"primary": None, "secondary": None}}},
        ]
        path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
        reading = UsageMonitor(UsageSettings(), home=self.home).read_codex("Codex", now)
        self.assertTrue(reading.ok)
        self.assertEqual(reading.summary, "Codex 5h 55%")

    def test_only_the_session_tail_is_read(self):
        now = 1_800_000_000.0
        path = self.home / ".codex" / "sessions" / "2026" / "09" / "15" / "rollout.jsonl"
        filler = json.dumps({"type": "event_msg", "payload": {"type": "agent_message", "message": "x" * 500}})
        current = json.dumps(
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "rate_limits": {"primary": {"used_percent": 7, "window_minutes": 300}},
                },
            }
        )
        path.write_text("\n".join([filler] * 200 + [current]) + "\n", encoding="utf-8")
        monitor = UsageMonitor(UsageSettings(session_tail_bytes=2_000), home=self.home)
        reading = monitor.read_codex("Codex", now)
        self.assertTrue(reading.ok)
        self.assertEqual(reading.summary, "Codex 5h 7%")

    def test_windows_without_a_declared_length_fall_back_to_named_labels(self):
        now = 1_800_000_000.0
        path = self.home / ".codex" / "sessions" / "2026" / "09" / "15" / "rollout.jsonl"
        path.write_text(
            json.dumps(
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "rate_limits": {
                            "primary": {"used_percent": 4},
                            "secondary": {"used_percent": 9},
                        },
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        reading = UsageMonitor(UsageSettings(), home=self.home).read_codex("Codex", now)
        self.assertEqual(reading.summary, "Codex session 4% · weekly 9%")

    def test_a_reading_reports_how_old_the_session_data_is(self):
        now = 1_800_000_000.0
        self.write_codex_session("rollout.jsonl", 20, 30, now)
        path = self.home / ".codex" / "sessions" / "2026" / "09" / "15" / "rollout.jsonl"
        os.utime(path, (now - 7_200, now - 7_200))
        reading = UsageMonitor(UsageSettings(), home=self.home).read_codex("Codex", now)
        self.assertIn("2h 00m ago", reading.detail)


if __name__ == "__main__":
    unittest.main()
