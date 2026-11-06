import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tui.memory import TaskMemoryStore
from tui.token_usage import TokenUsageEntry, calculate_token_usage, usage_entries_from_memory


class TokenUsageTests(unittest.TestCase):
    def test_calculates_windows_projection_and_provider_split(self):
        now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
        entries = (
            TokenUsageEntry("one", datetime(2026, 8, 17, 11, 30, tzinfo=timezone.utc), "codex", 100),
            TokenUsageEntry("two", datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc), "cursor", 300),
        )

        stats = calculate_token_usage(entries, now=now)

        self.assertEqual(stats.cumulative_tokens, 400)
        self.assertEqual(stats.daily_tokens, 100)
        self.assertEqual(stats.cumulative_tasks, 2)
        self.assertEqual(stats.daily_tasks, 1)
        self.assertEqual(stats.last_hour_tokens, 100)
        self.assertEqual(stats.last_hour_tasks, 1)
        self.assertEqual(
            stats.average_tokens_per_prompt_by_provider,
            (("cursor", 300.0), ("codex", 100.0)),
        )
        self.assertEqual(
            stats.average_tasks_per_prompt_by_provider,
            (("codex", 1.0), ("cursor", 1.0)),
        )
        self.assertEqual(stats.seven_day_expected_tokens, 700)
        self.assertEqual(stats.seven_day_expected_tasks, 7)
        self.assertEqual(stats.thirty_day_expected_tokens, 729)
        self.assertEqual(stats.thirty_day_expected_tasks, 4)
        self.assertEqual(stats.provider_tokens, (("cursor", 300), ("codex", 100)))
        self.assertEqual(stats.provider_tasks, (("codex", 1), ("cursor", 1)))
        self.assertEqual(stats.provider_split("tokens"), (("cursor", 300), ("codex", 100)))
        self.assertEqual(stats.provider_split("tasks"), (("codex", 1), ("cursor", 1)))
        self.assertEqual(
            stats.average_per_prompt("tokens"),
            (("cursor", 300.0), ("codex", 100.0)),
        )

    def test_reads_task_usage_from_persisted_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskMemoryStore(Path(directory) / ".daedalus-memory.json")
            store.record_task(
                "task-one",
                "Implement statistics",
                "codex",
                "luna",
                "high",
                "coding",
                "completed",
                submitted_at=0,
                tokens=165,
            )

            entries = usage_entries_from_memory(store)

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].task_id, "task-one")
            self.assertEqual(entries[0].provider, "codex")
            self.assertEqual(entries[0].tokens, 165)

    def test_counts_completed_plan_and_coding_tasks_only(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskMemoryStore(Path(directory) / ".daedalus-memory.json")
            store.record_task(
                "completed-plan",
                "Make a plan",
                "codex",
                "luna",
                "high",
                "plan",
                "completed",
                submitted_at=1,
                tokens=40,
            )
            store.record_task(
                "failed-coding",
                "Implement the plan",
                "codex",
                "luna",
                "high",
                "coding",
                "failed",
                submitted_at=2,
                tokens=300,
            )

            entries = usage_entries_from_memory(store)
            stats = calculate_token_usage(entries)

            self.assertEqual([entry.task_id for entry in entries], ["completed-plan"])
            self.assertEqual(stats.cumulative_tokens, 40)

    def test_calculation_ignores_non_completed_entries(self):
        entries = (
            TokenUsageEntry("completed", datetime.now(timezone.utc), "codex", 25),
            TokenUsageEntry("failed", datetime.now(timezone.utc), "codex", 100, state="failed"),
        )

        stats = calculate_token_usage(entries)

        self.assertEqual(stats.cumulative_tokens, 25)

    def test_projects_current_week_and_month_to_date_only(self):
        now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
        entries = (
            TokenUsageEntry(
                "today", datetime(2026, 8, 11, 11, 0, tzinfo=timezone.utc), "codex", 30_000_000
            ),
            TokenUsageEntry(
                "last-week", datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc), "codex", 50_000_000
            ),
            TokenUsageEntry(
                "last-month", datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc), "codex", 75_000_000
            ),
        )

        stats = calculate_token_usage(entries, now=now)

        self.assertEqual(stats.seven_day_expected_tokens, 105_000_000)
        self.assertEqual(stats.thirty_day_expected_tokens, round(30_000_000 * 31 / 11))

    def test_rejects_invalid_window_settings(self):
        with self.assertRaises(ValueError):
            calculate_token_usage((), recent_window_hours=0)
        with self.assertRaises(ValueError):
            calculate_token_usage((), forecast_days=0)
        with self.assertRaises(ValueError):
            calculate_token_usage((), thirty_day_forecast_days=0)


if __name__ == "__main__":
    unittest.main()
