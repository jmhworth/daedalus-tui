"""Usage bar readings from local provider data and configured commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from tui.usage_monitor import ProviderUsage, UsageMonitor, UsageProviderSettings, UsageSettings, format_usage_bar


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

    def test_format_usage_bar_joins_summaries_with_a_timestamp(self):
        readings = (
            ProviderUsage("claude", "Claude", "Claude today 1.0k tok · 2 msgs", checked_at=1_800_000_000.0),
            ProviderUsage("codex", "Codex", "Codex 5h 30% · week 46%", checked_at=1_800_000_000.0),
        )
        text = format_usage_bar(readings)
        self.assertTrue(text.startswith("Usage ("))
        self.assertIn("Claude today 1.0k tok · 2 msgs   Codex 5h 30% · week 46%", text)
        self.assertEqual(format_usage_bar(()), "Usage: —")


if __name__ == "__main__":
    unittest.main()
