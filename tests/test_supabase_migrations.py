import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tui.supabase_migrations import migrations_pending, push_migrations


class SupabaseMigrationsTests(unittest.TestCase):
    @patch("tui.supabase_migrations.subprocess.run")
    def test_pending_when_migration_paths_differ(self, run):
        run.return_value = Mock(returncode=0, stdout="supabase/migrations/20240101000000_init.sql\n", stderr="")
        self.assertTrue(migrations_pending(Path("/worktree"), "abc123"))
        self.assertEqual(
            run.call_args.args[0],
            ["git", "diff", "--name-only", "abc123", "--", "supabase/migrations/"],
        )
        self.assertEqual(run.call_args.kwargs["cwd"], Path("/worktree"))

    @patch("tui.supabase_migrations.subprocess.run")
    def test_not_pending_when_migration_paths_unchanged(self, run):
        run.return_value = Mock(returncode=0, stdout="", stderr="")
        self.assertFalse(migrations_pending(Path("/worktree"), "abc123"))

    @patch("tui.supabase_migrations.shutil.which", return_value=None)
    def test_missing_executable_is_failure(self, _which):
        result = push_migrations(Path("/worktree"))
        self.assertFalse(result.succeeded)
        self.assertIn("not available on PATH", result.output)

    @patch("tui.supabase_migrations.shutil.which", return_value="/usr/local/bin/supabase")
    @patch("tui.supabase_migrations.subprocess.run")
    def test_push_success_captures_output(self, run, _which):
        run.return_value = Mock(returncode=0, stdout="Remote database is up to date.\n", stderr="")
        result = push_migrations(Path("/worktree"), env={"SUPABASE_ACCESS_TOKEN": "tok"})
        self.assertTrue(result.succeeded)
        self.assertIn("up to date", result.output)
        self.assertEqual(
            run.call_args.args[0],
            ["/usr/local/bin/supabase", "db", "push", "--yes"],
        )
        self.assertEqual(run.call_args.kwargs["cwd"], Path("/worktree"))
        self.assertEqual(run.call_args.kwargs["env"]["SUPABASE_ACCESS_TOKEN"], "tok")

    @patch("tui.supabase_migrations.shutil.which", return_value="/usr/local/bin/supabase")
    @patch("tui.supabase_migrations.subprocess.run")
    def test_push_failure_captures_diagnostics(self, run, _which):
        run.return_value = Mock(returncode=1, stdout="", stderr="ERROR: relation already exists")
        result = push_migrations(Path("/worktree"))
        self.assertFalse(result.succeeded)
        self.assertIn("relation already exists", result.output)


if __name__ == "__main__":
    unittest.main()
