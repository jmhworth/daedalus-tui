import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from tui.project_config import load_project_worktree_settings
from tui.project_initializer import (
    REQUEST_MARKER,
    initialize_project,
    normalize_github_url,
    resolve_destination,
    validate_project_name,
)


class ProjectInitializerTests(unittest.TestCase):
    def test_normalizes_github_remote_urls(self):
        self.assertEqual(
            normalize_github_url("git@github.com:owner/example.git"),
            "https://github.com/owner/example",
        )

    def test_validates_and_normalizes_project_names(self):
        self.assertEqual(validate_project_name("  Example-Project  ", 100), "example-project")
        for invalid in ("", " ", ".", "..", ".hidden", "../project", "/tmp/project",
                        "C:\\project", "two words", "under_score", "trailing-"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_project_name(invalid, 100)
        with self.assertRaises(ValueError):
            validate_project_name("a" * 101, 100)

    def test_destination_is_a_direct_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(resolve_destination(root, "example"), root.resolve() / "example")

    def test_preflight_failure_does_not_create_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = initialize_project(
                {
                    "requestId": str(uuid.uuid4()),
                    "projectName": "example",
                    "createGitHubRepository": False,
                },
                execution_root=root,
                find_executable=lambda executable: None if executable == "graphify" else executable,
            )
            self.assertEqual(result["status"], "failed")
            self.assertFalse((root / "example").exists())

    def test_creates_templates_runs_commands_in_order_and_renames_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch_env = root / ".env"
            launch_env.write_text(
                "CURSOR_API_KEY=cursor-secret\nSUPABASE_URL=https://shared.supabase.co\n",
                encoding="utf-8",
            )
            calls = []

            def fake_run(command, cwd, capture_output, text, shell):
                calls.append((command, Path(cwd), shell))
                if command[:2] == ["git", "init"]:
                    (Path(cwd) / ".git").mkdir()
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            request_id = str(uuid.uuid4())
            progress = []
            result = initialize_project(
                {
                    "requestId": request_id,
                    "projectName": "example-project",
                    "createGitHubRepository": False,
                },
                progress=progress.append,
                execution_root=root,
                run_process=fake_run,
                find_executable=lambda executable: f"/bin/{executable}",
            )

            destination = root / "example-project"
            self.assertEqual(result["status"], "success")
            self.assertTrue((destination / "AGENTS.md").is_file())
            self.assertTrue((destination / ".agents" / "profiles" / "coding.md").is_file())
            self.assertEqual(
                (destination / ".env").read_bytes(),
                launch_env.read_bytes(),
            )
            self.assertEqual((destination / "README.md").read_text().splitlines()[0],
                             "# example-project")
            daedalus = destination / ".daedalus"
            self.assertTrue(daedalus.is_file())
            self.assertIn("[worktree]", daedalus.read_text(encoding="utf-8"))
            settings = load_project_worktree_settings(destination)
            self.assertEqual(settings.install_command, ())
            self.assertEqual(settings.readonly_paths, ())
            self.assertEqual(
                (destination / ".git" / REQUEST_MARKER).read_text(encoding="utf-8"),
                request_id,
            )
            self.assertEqual(
                [command for command, _, _ in calls],
                [
                    ["graphify", "codex", "install"],
                    ["graphify", "cursor", "install"],
                    ["git", "init", "-b", "main"],
                    ["git", "add", "."],
                    ["git", "commit", "-m", "Initialize Daedalus project"],
                ],
            )
            self.assertTrue(all(shell is False for _, _, shell in calls))
            self.assertTrue(all(call_root.name.startswith(".example-project.daedalus-init-")
                                for _, call_root, _ in calls))
            self.assertTrue(any(update["status"] == "running" for update in progress))

    def test_failure_cleans_temporary_directory_without_touching_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def fake_run(command, cwd, capture_output, text, shell):
                if command[:2] == ["git", "init"]:
                    return SimpleNamespace(returncode=1, stdout="", stderr="git failed")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            request_id = str(uuid.uuid4())
            result = initialize_project(
                {"requestId": request_id, "projectName": "example",
                 "createGitHubRepository": False},
                execution_root=root,
                run_process=fake_run,
                find_executable=lambda executable: executable,
            )
            self.assertEqual(result["status"], "failed")
            self.assertFalse(any(path.name.startswith(".example.daedalus-init-")
                                 for path in root.iterdir()))

            destination = root / "owned"
            destination.mkdir()
            (destination / "important.txt").write_text("keep", encoding="utf-8")
            protected = initialize_project(
                {"requestId": str(uuid.uuid4()), "projectName": "owned",
                 "createGitHubRepository": False},
                execution_root=root,
                run_process=fake_run,
                find_executable=lambda executable: executable,
            )
            self.assertEqual(protected["status"], "failed")
            self.assertTrue((destination / "important.txt").is_file())

    def test_github_failure_keeps_local_repository_and_uses_explicit_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = []

            def fake_run(command, cwd, capture_output, text, shell):
                calls.append(command)
                if command[:2] == ["git", "init"]:
                    (Path(cwd) / ".git").mkdir()
                if command[:4] == ["gh", "repo", "create", "example"]:
                    return SimpleNamespace(returncode=1, stdout="", stderr="push failed")
                if command == ["git", "remote", "get-url", "origin"]:
                    return SimpleNamespace(returncode=1, stdout="", stderr="")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            result = initialize_project(
                {"requestId": str(uuid.uuid4()), "projectName": "example",
                 "createGitHubRepository": True},
                execution_root=root,
                run_process=fake_run,
                find_executable=lambda executable: executable,
            )
            self.assertEqual(result["status"], "partial_success")
            self.assertTrue((root / "example" / ".git").is_dir())
            self.assertIn(
                ["gh", "repo", "create", "example", "--private", "--source=.",
                 "--remote=origin", "--push"],
                calls,
            )

    def test_optional_personal_supabase_registration_is_no_longer_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = []

            def fake_run(command, cwd, capture_output, text, shell):
                calls.append(command)
                if command[:2] == ["git", "init"]:
                    (Path(cwd) / ".git").mkdir()
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            result = initialize_project(
                {
                    "requestId": str(uuid.uuid4()),
                    "projectName": "with-schema",
                    "createGitHubRepository": False,
                    "registerPersonalSupabase": True,
                },
                execution_root=root,
                run_process=fake_run,
                find_executable=lambda executable: f"/bin/{executable}",
            )
            destination = root / "with-schema"
            self.assertEqual(result["status"], "success")
            self.assertFalse((destination / "supabase").exists())
            self.assertFalse(any(path.name.startswith(".with-schema.daedalus-init-")
                                 for path in root.iterdir()))
            self.assertIn(["git", "add", "."], calls)

    def test_matching_request_recovery_does_not_repeat_local_initialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "example"
            (destination / ".git").mkdir(parents=True)
            request_id = str(uuid.uuid4())
            (destination / ".git" / REQUEST_MARKER).write_text(request_id, encoding="utf-8")
            calls = []

            result = initialize_project(
                {"requestId": request_id, "projectName": "example",
                 "createGitHubRepository": False},
                execution_root=root,
                run_process=lambda *args, **kwargs: calls.append(args)
                or SimpleNamespace(returncode=0, stdout="", stderr=""),
                find_executable=lambda executable: executable,
            )
            self.assertEqual(result["status"], "success")
            self.assertEqual(calls, [])
            self.assertTrue(all(item["status"] == "skipped" for item in result["steps"]))


if __name__ == "__main__":
    unittest.main()
