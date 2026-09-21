import tempfile
import unittest
from pathlib import Path

from tui.project_config import ProjectWorktreeSettings, load_project_worktree_settings


class ProjectConfigTests(unittest.TestCase):
    def test_missing_project_config_uses_empty_worktree_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_project_worktree_settings(Path(directory)), ProjectWorktreeSettings())

    def test_loads_install_command_and_readonly_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / ".daedalus").write_text(
                '[worktree]\ninstall_command = ["npm", "ci"]\nreadonly_paths = ["food-data"]\n'
                'environment_files = ["fstore/.env"]\n',
                encoding="utf-8",
            )

            settings = load_project_worktree_settings(repository)

        self.assertEqual(settings.install_command, ("npm", "ci"))
        self.assertEqual(settings.readonly_paths, ("food-data",))
        self.assertEqual(settings.environment_files, ("fstore/.env",))
        self.assertTrue(settings.configured)

    def test_rejects_absolute_or_parent_readonly_paths(self):
        for readonly_path in ("/tmp/food-data", "../food-data"):
            with self.subTest(readonly_path=readonly_path), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory)
                (repository / ".daedalus").write_text(
                    f'[worktree]\nreadonly_paths = ["{readonly_path}"]\n',
                    encoding="utf-8",
                )

                with self.assertRaises(ValueError):
                    load_project_worktree_settings(repository)

    def test_rejects_environment_file_outside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / ".daedalus").write_text(
                '[worktree]\nenvironment_files = ["../secrets.env"]\n', encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_project_worktree_settings(repository)

    def test_loads_project_claude_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / ".daedalus").write_text(
                '[claude]\nsettings_file = "orchestrator/permissions.json"\n'
                'allowed_tools = ["Bash(python3:*)", "WebFetch"]\n',
                encoding="utf-8",
            )
            settings = load_project_worktree_settings(repository)
        self.assertEqual(settings.claude_settings_file, "orchestrator/permissions.json")
        self.assertEqual(settings.claude_allowed_tools, ("Bash(python3:*)", "WebFetch"))


if __name__ == "__main__":
    unittest.main()
