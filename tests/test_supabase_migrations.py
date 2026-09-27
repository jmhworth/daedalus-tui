import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from tui.supabase_migrations import migrations_pending, push_migrations, synchronize_personal_migrations


class SupabaseMigrationsTests(unittest.TestCase):
    @patch("tui.supabase_migrations.subprocess.run")
    def test_pending_when_migration_paths_differ(self, run):
        run.return_value = Mock(returncode=0, stdout="supabase/migrations/20240101000000_init.sql\n", stderr="")
        self.assertTrue(migrations_pending(Path("/worktree"), "abc123"))
        self.assertEqual(run.call_args_list[0].args[0], [
            "git", "diff", "--name-only", "abc123", "--", "daedalus-migrations", "supabase/migrations/"
        ])
        self.assertEqual(run.call_args_list[1].args[0], [
            "git", "ls-files", "--others", "--exclude-standard", "--", "daedalus-migrations", "supabase/migrations/"
        ])

    def test_personal_sync_copies_new_migrations_and_skips_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tui"
            project = Path(tmp) / "project"
            (root / "supabase" / "migrations").mkdir(parents=True)
            (project / "daedalus-migrations").mkdir(parents=True)
            (project / ".daedalus").write_text('[personal_supabase]\nschema = "demo_app"\n', encoding="utf-8")
            name = "202609261230_demo_app_create_schema.sql"
            sql = 'CREATE SCHEMA IF NOT EXISTS "demo_app";\n'
            (project / "daedalus-migrations" / name).write_text(sql, encoding="utf-8")
            with patch("tui.supabase_migrations.TUI_ROOT", root):
                first = synchronize_personal_migrations(project)
                second = synchronize_personal_migrations(project)
            self.assertTrue(first.succeeded)
            self.assertEqual(first.copied, (name,))
            self.assertTrue(second.succeeded)
            self.assertEqual(second.copied, ())
            self.assertEqual((root / "supabase" / "migrations" / name).read_text(encoding="utf-8"), sql)

    def test_personal_sync_reports_conflicts_and_preserves_root_sql(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tui"
            project = Path(tmp) / "project"
            destination = root / "supabase" / "migrations"
            source = project / "daedalus-migrations"
            destination.mkdir(parents=True)
            source.mkdir(parents=True)
            (project / ".daedalus").write_text('[personal_supabase]\nschema = "demo_app"\n', encoding="utf-8")
            name = "202609261230_demo_app_create_schema.sql"
            root_sql, project_sql = "SELECT 1;\n", "SELECT 2;\n"
            (destination / name).write_text(root_sql, encoding="utf-8")
            (source / name).write_text(project_sql, encoding="utf-8")
            with patch("tui.supabase_migrations.TUI_ROOT", root):
                result = synchronize_personal_migrations(project)
            self.assertTrue(result.succeeded)
            self.assertEqual(result.conflicts, ((name, root_sql, project_sql),))
            self.assertEqual((destination / name).read_text(encoding="utf-8"), root_sql)
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
