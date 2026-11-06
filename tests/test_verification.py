import tempfile
import sys
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tui.agent_runner import AgentControl
from tui.verification import discover_commands, run_verification


class VerificationTests(unittest.TestCase):
    def test_discovers_root_and_nested_test_suites(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            (root / "package.json").write_text('{"scripts":{"test":"pytest"}}', encoding="utf-8")
            child = root / "child"
            child.mkdir()
            (child / "tests").mkdir()
            self.assertEqual(
                discover_commands(root, []),
                [["npm", "test"], ["python", "-m", "pytest"], ["python", "-m", "pytest", "child/tests"]],
            )

    @patch("tui.verification.subprocess.run")
    def test_stops_at_first_failed_command(self, run):
        success = unittest.mock.Mock(returncode=0, stdout="ok", stderr="")
        failure = unittest.mock.Mock(returncode=1, stdout="", stderr="failed")
        run.side_effect = [success, failure]

        result = run_verification(Path("/worktree"), [["first"], ["second"], ["third"]])

        self.assertFalse(result.succeeded)
        self.assertEqual(run.call_count, 2)
        self.assertIn("failed", result.output)

    def test_verification_process_stops_when_task_is_cancelled(self):
        control = AgentControl()
        result_holder = []

        def run_check():
            result_holder.append(
                run_verification(
                    Path("/tmp"),
                    [[sys.executable, "-c", "import time; time.sleep(10)"]],
                    control=control,
                )
            )

        worker = threading.Thread(target=run_check)
        started = time.monotonic()
        worker.start()
        time.sleep(0.15)
        control.request_cancel()
        worker.join(timeout=3)

        self.assertFalse(worker.is_alive())
        self.assertLess(time.monotonic() - started, 3)
        self.assertFalse(result_holder[0].succeeded)

    def test_verification_diagnostics_are_bounded(self):
        with patch("tui.verification.subprocess.run") as run:
            run.return_value = unittest.mock.Mock(
                returncode=1,
                stdout="x" * 100_000,
                stderr="y" * 100_000,
            )

            result = run_verification(Path("/worktree"), [["check"]])

        self.assertLessEqual(len(result.output), 64_000)
        self.assertIn("diagnostic truncated", result.output)


if __name__ == "__main__":
    unittest.main()
