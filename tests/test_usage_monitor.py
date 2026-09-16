"""Usage bar readings from local provider data and configured commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from tui.usage_monitor import (
    ProviderUsage,
    UsageMonitor,
    UsageProviderSettings,
    UsageSettings,
    UsageWindow,
    format_bar,
    format_usage_bar,
)


class UsageMonitorTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.home = Path(self._directory.name)
        (self.home / ".codex" / "sessions" / "2026" / "09" / "15").mkdir(parents=True)
        (self.home / ".claude").mkdir()

    def tearDown(self):
        self._directory.cleanup()

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

    def test_codex_reading_accepts_the_relative_reset_field(self):
        """Codex reports ``resets_in_seconds``; only ``resets_at`` was read."""
        now = 1_800_000_000.0
        path = self.home / ".codex" / "sessions" / "2026" / "09" / "15" / "rollout.jsonl"
        path.write_text(
            json.dumps(
                {
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
            )
            + "\n",
            encoding="utf-8",
        )
        reading = UsageMonitor(UsageSettings(), home=self.home).read_codex("Codex", now)
        self.assertTrue(reading.ok)
        self.assertEqual(reading.summary, "Codex 5h 12% · week 88% (pro)")
        self.assertIn("resets in 1h 30m", reading.detail)
        self.assertIn("resets in 1d 1h", reading.detail)

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
