import os
import shutil
import tempfile
import sys
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tui.agent_runner import AgentControl
from tui.verification import discover_commands, python_executable, run_verification


class VerificationTests(unittest.TestCase):
    def _suite_tree(self, root: Path) -> None:
        (root / "tests").mkdir()
        (root / "package.json").write_text('{"scripts":{"test":"pytest"}}', encoding="utf-8")
        child = root / "child"
        child.mkdir()
        (child / "tests").mkdir()

    def test_discovers_root_and_nested_test_suites(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._suite_tree(root)
            interpreter = python_executable(root)
            self.assertEqual(
                discover_commands(root, []),
                [
                    ["npm", "test"],
                    [interpreter, "-m", "pytest"],
                    [interpreter, "-m", "pytest", "child/tests"],
                ],
            )

    def test_falls_back_to_path_when_no_virtual_environment_is_available(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._suite_tree(root)
            with patch.dict(os.environ, {}, clear=True), patch(
                "tui.verification.shutil.which",
                side_effect=lambda name: "/usr/bin/python3" if name == "python3" else None,
            ):
                self.assertEqual(
                    discover_commands(root, []),
                    [
                        ["npm", "test"],
                        ["/usr/bin/python3", "-m", "pytest"],
                        ["/usr/bin/python3", "-m", "pytest", "child/tests"],
                    ],
                )

    def test_never_emits_a_bare_python_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._suite_tree(root)
            for command in discover_commands(root, []):
                self.assertNotEqual(command[0], "python")

    def test_python_executable_resolves_to_an_existing_interpreter(self):
        resolved = python_executable()
        self.assertTrue(shutil.which(resolved) or Path(resolved).exists())

    def test_discovered_interpreter_is_an_existing_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            command = discover_commands(root, [])[0]

            self.assertTrue(Path(command[0]).is_file(), command[0])
            self.assertTrue(os.access(command[0], os.X_OK), command[0])

    def test_prefers_a_virtual_environment_belonging_to_the_code_under_test(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binaries = root / ".venv" / "bin"
            binaries.mkdir(parents=True)
            interpreter = binaries / "python"
            interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
            interpreter.chmod(0o755)

            self.assertEqual(python_executable(root), str(interpreter))

    def test_missing_executable_is_reported_as_an_environment_problem(self):
        result = run_verification(Path("/"), [["daedalus-missing-executable"]])

        self.assertFalse(result.succeeded)
        self.assertIn("was not found on PATH", result.output)
        self.assertIn("verification_commands", result.output)

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
