"""Diagnostics logging: full capture, rotation, redaction, and failure fallback."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import stat
import tempfile
import unittest

from tui import debug_log
from tui.debug_log import (
    LOGGER,
    append_run_diagnostic,
    configure_debug_logging,
    format_context,
    log_event,
    scrub_credentials,
)


class DebugLogTests(unittest.TestCase):
    def tearDown(self):
        for handler in tuple(LOGGER.handlers):
            if handler.get_name() == debug_log._HANDLER_NAME:
                LOGGER.removeHandler(handler)
                handler.close()

    def test_configures_a_rotating_log_with_context_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "errors" / "daedalus.log"
            status = configure_debug_logging(path, max_bytes=2_000_000, backup_count=3)
            self.assertTrue(status.available)
            self.assertEqual(status.path, path)
            log_event(
                logging.ERROR,
                "Agent failed",
                project="app-1234abcd",
                task="001-abc",
                turn="turn-1",
                run="run-1",
                phase="agent",
                provider="codex",
                exit_status=1,
            )
            for handler in LOGGER.handlers:
                handler.flush()
            text = path.read_text(encoding="utf-8")
            self.assertIn("ERROR", text)
            self.assertIn("project=app-1234abcd task=001-abc turn=turn-1 run=run-1 phase=agent provider=codex exit_status=1 | Agent failed", text)
            self.assertRegex(text, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")

    def test_rotation_limits_keep_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daedalus.log"
            configure_debug_logging(path, max_bytes=500, backup_count=2)
            for index in range(200):
                LOGGER.info("line %s %s", index, "x" * 40)
            for handler in LOGGER.handlers:
                handler.flush()
            names = sorted(entry.name for entry in Path(directory).iterdir())
            self.assertIn("daedalus.log", names)
            self.assertIn("daedalus.log.1", names)
            self.assertIn("daedalus.log.2", names)
            self.assertNotIn("daedalus.log.3", names)

    def test_unavailable_log_path_is_reported_once_without_claiming_success(self):
        with tempfile.TemporaryDirectory() as directory:
            blocker = Path(directory) / "file"
            blocker.write_text("x", encoding="utf-8")
            status = configure_debug_logging(blocker / "nested" / "daedalus.log")
            self.assertFalse(status.available)
            self.assertIn(str(blocker / "nested" / "daedalus.log"), status.error)
            # Logging afterwards must not raise.
            LOGGER.error("still safe")

    def test_scrubs_known_credential_patterns_but_keeps_failure_text(self):
        text = (
            "Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123456789 failed\n"
            "OPENAI_API_KEY=sk-live-1234567890abcdefghijkl exited 1\n"
            "ANTHROPIC_API_KEY: 'sk-ant-api03-abcdefghijklmnop' rejected"
        )
        scrubbed = scrub_credentials(text)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz0123456789", scrubbed)
        self.assertNotIn("1234567890abcdefghijkl", scrubbed)
        self.assertIn("OPENAI_API_KEY=[redacted]", scrubbed)
        self.assertIn("failed", scrubbed)
        self.assertIn("exited 1", scrubbed)
        self.assertIn("rejected", scrubbed)

    def test_run_diagnostics_capture_full_text_and_trim_oldest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "turn-0001-run-0001.log"
            long_text = "verification output line\n" * 200
            self.assertTrue(
                append_run_diagnostic(path, "error", long_text, max_bytes=100_000, task="001", run="run-1", phase="verification")
            )
            content = path.read_text(encoding="utf-8")
            self.assertIn("=== ", content)
            self.assertIn("task=001 run=run-1 phase=verification", content)
            self.assertEqual(content.count("verification output line"), 200)
            for _ in range(20):
                append_run_diagnostic(path, "error", "y" * 2000, max_bytes=8_000, task="001")
            self.assertLessEqual(path.stat().st_size, 8_000 + 200)
            self.assertIn("older diagnostics trimmed", path.read_text(encoding="utf-8"))

    @unittest.skipIf(os.name != "posix" or os.geteuid() == 0, "requires POSIX permissions")
    def test_run_diagnostics_failure_is_reported_once_and_never_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            locked = Path(directory) / "locked"
            locked.mkdir()
            os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
            try:
                path = locked / "run.log"
                self.assertFalse(append_run_diagnostic(path, "error", "text", task="001"))
                self.assertFalse(append_run_diagnostic(path, "error", "text", task="001"))
            finally:
                os.chmod(locked, stat.S_IRWXU)

    def test_format_context_orders_known_fields_first(self):
        self.assertEqual(
            format_context(extra="z", provider="codex", task="t", project="p"),
            "project=p task=t provider=codex extra=z",
        )


if __name__ == "__main__":
    unittest.main()
