import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from tui.codex_usage import fetch_codex_usage, parse_codex_usage
from tui.config import CodexUsageSettings


class CodexUsageTests(unittest.TestCase):
    def test_parses_five_hour_and_weekly_remaining_windows(self):
        snapshot = parse_codex_usage(
            {
                "rateLimits": {
                    "planType": "plus",
                    "primary": {
                        "usedPercent": 25,
                        "windowDurationMins": 300,
                        "resetsAt": 1_798_000_000,
                    },
                    "secondary": {
                        "usedPercent": 40,
                        "windowDurationMins": 10_080,
                        "resetsAt": 1_798_500_000,
                    },
                }
            }
        )

        self.assertEqual(snapshot.plan_type, "plus")
        self.assertEqual(snapshot.five_hour.remaining_percent, 75)
        self.assertEqual(snapshot.weekly.remaining_percent, 60)
        self.assertEqual(
            snapshot.five_hour.resets_at,
            datetime.fromtimestamp(1_798_000_000, timezone.utc),
        )

    def test_keeps_missing_five_hour_window_unavailable(self):
        snapshot = parse_codex_usage(
            {
                "rateLimits": {
                    "primary": {
                        "usedPercent": 31,
                        "windowDurationMins": 10_080,
                    }
                }
            }
        )

        self.assertIsNone(snapshot.five_hour)
        self.assertEqual(snapshot.weekly.remaining_percent, 69)

    @patch("tui.codex_usage.shutil.which", return_value="/usr/local/bin/codex")
    @patch("tui.codex_usage.subprocess.run")
    def test_fetches_rate_limits_after_app_server_handshake(self, run, _which):
        output = "\n".join(
            [
                json.dumps({"jsonrpc": "2.0", "id": "initialize", "result": {}}),
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": "rate-limits",
                        "result": {
                            "rateLimits": {
                                "primary": {
                                    "usedPercent": 5,
                                    "windowDurationMins": 300,
                                }
                            }
                        },
                    }
                ),
            ]
        )
        run.return_value.stdout = output
        run.return_value.returncode = 0

        snapshot = fetch_codex_usage(CodexUsageSettings())

        self.assertEqual(snapshot.five_hour.remaining_percent, 95)
        command = run.call_args.args[0]
        self.assertEqual(command[-2:], ["app-server", "--stdio"])
        self.assertIn('"method": "account/rateLimits/read"', run.call_args.kwargs["input"])


if __name__ == "__main__":
    unittest.main()
