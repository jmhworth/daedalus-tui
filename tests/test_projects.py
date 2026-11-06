import tempfile
import unittest
from pathlib import Path

from tui.projects import discover_projects


class ProjectDiscoveryTests(unittest.TestCase):
    def test_finds_only_immediate_child_projects_in_deterministic_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "feature_files").mkdir()
            (root / "zeta" / "feature_files").mkdir(parents=True)
            (root / "daedalus" / "feature_files").mkdir(parents=True)
            (root / "project-initialization" / "feature_files").mkdir(parents=True)
            (root / "daedalus" / "project-initialization" / "other-project" / "feature_files").mkdir(
                parents=True
            )
            (root / "project-initialization" / "other-project" / "feature_files").mkdir(
                parents=True
            )
            (root / ".daedalus-worktrees" / "ignored" / "feature_files").mkdir(parents=True)
            (root / "node_modules" / "dependency" / "feature_files").mkdir(parents=True)
            (root / ".git" / "ignored" / "feature_files").mkdir(parents=True)
            (root / ".venv" / "ignored" / "feature_files").mkdir(parents=True)
            (root / "__pycache__" / "ignored" / "feature_files").mkdir(parents=True)

            projects = discover_projects(root)

            self.assertEqual(
                [project.path for project in projects],
                [
                    (root / "daedalus").resolve(),
                    (root / "project-initialization").resolve(),
                    (root / "zeta").resolve(),
                ],
            )
            self.assertEqual(
                [project.display_name for project in projects],
                ["daedalus", "project-initialization", "zeta"],
            )

    def test_ignores_launch_root_feature_files_when_no_child_is_eligible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "feature_files").mkdir()

            self.assertEqual(discover_projects(root), ())

    def test_returns_no_projects_for_missing_root(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"

            self.assertEqual(discover_projects(missing), ())


if __name__ == "__main__":
    unittest.main()
