import socket
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tui.personal_supabase import (
    activate_personal_supabase,
    bootstrap_personal_supabase,
    commit_personal_supabase_scaffold,
    is_personal_supabase_activated,
    is_personal_supabase_registered,
    load_personal_supabase_status,
    preflight_personal_supabase,
    profile_guidance_section,
    project_ref_from_supabase_url,
    probe_project_personal_supabase_environment,
    remove_personal_supabase,
    register_personal_supabase,
    resolve_personal_supabase_environment,
    resolve_project_ref_from_environment,
    schema_from_project_root,
    temporary_supabase_cli_config,
)
from tui.supabase_migrations import PushResult


class PersonalSupabaseTests(unittest.TestCase):
    def _seed_project(self, root: Path, name: str = "example-project") -> Path:
        project = root / name
        (project / ".agents" / "profiles").mkdir(parents=True)
        (project / "feature_files").mkdir()
        (project / ".agents" / "profiles" / "coding.md").write_text("# Coding\n", encoding="utf-8")
        (project / ".agents" / "profiles" / "architecture.md").write_text(
            "# Architecture\n",
            encoding="utf-8",
        )
        (project / ".daedalus").write_text(
            "[worktree]\ninstall_command = []\nreadonly_paths = []\n",
            encoding="utf-8",
        )
        return project

    def _git(self, project: Path, *args: str) -> None:
        process = subprocess.run(
            ["git", *args],
            cwd=project,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(process.returncode, 0)

    def _init_git_repo(self, project: Path, branch: str = "main") -> None:
        self._git(project, "init", "-b", branch)
        self._git(project, "config", "user.email", "test@example.com")
        self._git(project, "config", "user.name", "Test")
        self._git(project, "add", ".")
        self._git(project, "commit", "-m", "initial")

    def _write_project_env(self, project: Path, *, token: bool = False, legacy_keys: bool = False) -> None:
        if legacy_keys:
            lines = [
                "SUPABASE_URL=https://shared-ref.supabase.co",
                "SUPABASE_ANON_KEY=anon-key",
                "SUPABASE_SERVICE_ROLE_KEY=service-key",
            ]
        else:
            lines = [
                "SUPABASE_URL=https://shared-ref.supabase.co",
                "SUPABASE_PUBLISHABLE_KEY=publishable-key",
                "SUPABASE_SECRET_KEY=secret-key",
            ]
        if token:
            lines.append("SUPABASE_ACCESS_TOKEN=access-token")
        else:
            lines.append("SUPABASE_DB_URL=postgres://user:password@example.test:5432/db")
        (project / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_schema_matches_validated_project_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "my-app"
            project.mkdir()
            self.assertEqual(schema_from_project_root(project), "my-app")
        with self.assertRaises(ValueError):
            schema_from_project_root(Path("/tmp/Not Valid"))

    def test_registration_writes_expected_files_without_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._seed_project(Path(tmp))
            result = register_personal_supabase(project)
            self.assertEqual(result.status, "success")
            self.assertEqual(result.schema, "example-project")
            self.assertFalse(result.already_registered)

            migration = next((project / "daedalus-migrations").glob("*.sql"))
            self.assertRegex(migration.name, r"^\d{12}_example-project_create_schema\.sql$")
            self.assertTrue(migration.is_file())
            migration_text = migration.read_text(encoding="utf-8")
            self.assertIn('CREATE SCHEMA IF NOT EXISTS "example-project";', migration_text)

            env_text = (project / ".env.example").read_text(encoding="utf-8")
            self.assertIn("SUPABASE_URL=", env_text)
            self.assertIn("SUPABASE_PUBLISHABLE_KEY=", env_text)
            self.assertIn("SUPABASE_SECRET_KEY=", env_text)
            self.assertIn("SUPABASE_SCHEMA=example-project", env_text)
            self.assertIn("allow-list", env_text.lower())
            self.assertNotRegex(env_text, r"(?i)(eyJ|sk-|service_role\.[A-Za-z0-9])")

            for relative in (
                ".agents/profiles/coding.md",
                ".agents/profiles/architecture.md",
            ):
                profile = (project / relative).read_text(encoding="utf-8")
                self.assertIn("## Personal Supabase Schema", profile)
                self.assertIn("example-project", profile)
                self.assertIn("public", profile.lower())
                self.assertIn("must not run `supabase db push`", profile)

            status = load_personal_supabase_status(project)
            self.assertTrue(status.registered)
            self.assertFalse(status.activated)
            self.assertEqual(status.schema, "example-project")
            self.assertTrue(is_personal_supabase_registered(project, "example-project"))
            self.assertFalse(is_personal_supabase_activated(project, "example-project"))

    def test_registration_is_idempotent_for_same_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._seed_project(Path(tmp))
            first = register_personal_supabase(project)
            second = register_personal_supabase(project)
            self.assertEqual(first.status, "success")
            self.assertEqual(second.status, "success")
            self.assertTrue(second.already_registered)
            self.assertEqual(len(list((project / "daedalus-migrations").iterdir())), 1)

    def test_remove_personal_supabase_removes_owned_artifacts_preserves_shared_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._seed_project(Path(tmp), "demo-app")
            register_personal_supabase(project, schema="demo-app")
            (project / ".env").write_text(
                "APP_SETTING=keep\nSUPABASE_PROJECT_REF=shared-ref\nSUPABASE_SCHEMA=demo-app\n",
                encoding="utf-8",
            )

            result = remove_personal_supabase(project)

            self.assertTrue(result.succeeded)
            self.assertFalse((project / "supabase").exists())
            self.assertFalse((project / ".env.example").exists())
            self.assertEqual(
                (project / ".env").read_text(encoding="utf-8"),
                "APP_SETTING=keep\nSUPABASE_PROJECT_REF=shared-ref\nSUPABASE_SCHEMA=demo-app\n",
            )
            self.assertEqual(
                (project / ".agents" / "profiles" / "coding.md").read_text(encoding="utf-8"),
                "# Coding\n",
            )
            marker = (project / ".daedalus").read_text(encoding="utf-8")
            self.assertIn("[worktree]", marker)
            self.assertNotIn("personal_supabase", marker)

    def test_remove_personal_supabase_deletes_marker_when_it_has_no_other_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "demo-app"
            project.mkdir()
            register_personal_supabase(project, schema="demo-app")

            result = remove_personal_supabase(project)

            self.assertTrue(result.succeeded)
            self.assertFalse((project / ".daedalus").exists())

    def test_conflicting_marker_and_foreign_migrations_fail_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._seed_project(Path(tmp), "alpha")
            register_personal_supabase(project, schema="alpha")
            conflict = register_personal_supabase(project, schema="beta")
            self.assertEqual(conflict.status, "failed")
            self.assertIn("already registered for schema 'alpha'", conflict.message)

            other = self._seed_project(Path(tmp), "other-app")
            migrations = other / "daedalus-migrations"
            migrations.mkdir(parents=True)
            (migrations / "20200101000000_unrelated.sql").write_text(
                "CREATE TABLE public.widgets (id int);\n",
                encoding="utf-8",
            )
            before = (other / ".daedalus").read_text(encoding="utf-8")
            blocked = register_personal_supabase(other)
            self.assertEqual(blocked.status, "failed")
            self.assertIn("incompatible", blocked.message.lower())
            self.assertEqual((other / ".daedalus").read_text(encoding="utf-8"), before)
            self.assertFalse((other / ".env.example").exists())

    def test_profile_guidance_mentions_schema_and_anti_public_rules(self):
        section = profile_guidance_section("demo-app")
        self.assertIn("## Personal Supabase Schema", section)
        self.assertIn("`demo-app`", section)
        self.assertIn("public", section)
        self.assertIn("supabase db push", section)
        self.assertIn("Activate", section)
        self.assertIn("never writes credentials", section)
        self.assertNotIn("synchronizes the ignored project", section)

    def test_project_bootstrap_validates_project_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = root / "launch"
            project = launch / "demo-app"
            project.mkdir(parents=True)
            self._seed_project(launch, "demo-app")
            register_personal_supabase(project, schema="demo-app")
            self._write_project_env(project)
            result = bootstrap_personal_supabase(project)
            self.assertEqual(result.status, "success")
            self.assertEqual(result.project_ref, "shared-ref")
            self.assertTrue((project / ".env").exists())
            self.assertIsNotNone(result.environment)
            assert result.environment is not None
            self.assertEqual(result.environment["SUPABASE_PROJECT_REF"], "shared-ref")
            self.assertEqual(result.environment["SUPABASE_PUBLISHABLE_KEY"], "publishable-key")
            self.assertEqual(result.environment["SUPABASE_SECRET_KEY"], "secret-key")
            cli_root = Path(tmp) / "tui-root"
            with patch("tui.personal_supabase.TUI_ROOT", cli_root):
                with temporary_supabase_cli_config(project, "shared-ref"):
                    config = cli_root / "supabase" / "config.toml"
                    self.assertIn('project_id = "shared-ref"', config.read_text(encoding="utf-8"))
                self.assertFalse((cli_root / "supabase" / "config.toml").exists())

    def test_probe_project_env_uses_child_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = root / "launch"
            project = self._seed_project(launch, "demo-app")
            self._write_project_env(launch)
            missing_ok, missing_error = probe_project_personal_supabase_environment(project)
            self.assertFalse(missing_ok)
            self.assertIsNotNone(missing_error)
            assert missing_error is not None
            self.assertIn("SUPABASE_URL", missing_error)
            self.assertNotIn("project-key", missing_error)
            self.assertNotIn("project-secret", missing_error)

            self._write_project_env(project)
            present_ok, present_error = probe_project_personal_supabase_environment(project)
            self.assertTrue(present_ok)
            self.assertIsNone(present_error)

    def test_project_bootstrap_reports_missing_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = root / "launch"
            self._seed_project(launch, "demo-app")
            project = launch / "demo-app"
            register_personal_supabase(project, schema="demo-app")
            # API credentials alone are not enough when database access is required.
            (project / ".env").write_text(
                "SUPABASE_URL=https://shared-ref.supabase.co\n"
                "SUPABASE_PUBLISHABLE_KEY=publishable-key\n"
                "SUPABASE_SECRET_KEY=secret-key\n",
                encoding="utf-8",
            )

            result = bootstrap_personal_supabase(project)

            self.assertEqual(result.status, "failed")
            self.assertIn("database access", result.message)
            self.assertTrue((project / ".env").exists())

    def test_disabled_push_bootstrap_validates_without_database_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = root / "launch"
            self._seed_project(launch, "demo-app")
            project = launch / "demo-app"
            register_personal_supabase(project, schema="demo-app")
            (project / ".env").write_text(
                "SUPABASE_URL=https://shared-ref.supabase.co\n"
                "SUPABASE_PUBLISHABLE_KEY=publishable-key\n"
                "SUPABASE_SECRET_KEY=secret-key\n",
                encoding="utf-8",
            )

            result = bootstrap_personal_supabase(
                project,
                require_database_access=False,
            )

            self.assertEqual(result.status, "success")
            self.assertTrue((project / ".env").exists())
            assert result.environment is not None
            self.assertEqual(result.environment["SUPABASE_PROJECT_REF"], "shared-ref")

    def test_project_bootstrap_accepts_legacy_and_private_key_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = root / "launch"
            self._seed_project(launch, "demo-app")
            project = launch / "demo-app"
            register_personal_supabase(project, schema="demo-app")
            self._write_project_env(project, legacy_keys=True)

            result = bootstrap_personal_supabase(project)

            self.assertEqual(result.status, "success")
            self.assertTrue((project / ".env").exists())
            assert result.environment is not None
            self.assertEqual(result.environment["SUPABASE_PUBLISHABLE_KEY"], "anon-key")
            self.assertEqual(result.environment["SUPABASE_SECRET_KEY"], "service-key")

            (project / ".env").write_text(
                "SUPABASE_URL=https://shared-ref.supabase.co\n"
                "SUPABASE_PUBLISHABLE_KEY=publishable-key\n"
                "SUPABASE_PRIVATE_KEY=private-key\n"
                "SUPABASE_DB_URL=postgres://user:password@example.test:5432/db\n",
                encoding="utf-8",
            )
            private = bootstrap_personal_supabase(project)
            self.assertEqual(private.status, "success")
            assert private.environment is not None
            self.assertEqual(private.environment["SUPABASE_SECRET_KEY"], "private-key")

    def test_resolve_helpers_derive_project_ref_from_url(self):
        self.assertEqual(
            project_ref_from_supabase_url("https://abc123.supabase.co"),
            "abc123",
        )
        self.assertIsNone(project_ref_from_supabase_url("https://example.test"))
        overlay, error = resolve_personal_supabase_environment(
            {
                "SUPABASE_URL": "https://abc123.supabase.co",
                "SUPABASE_PUBLISHABLE_KEY": "pub",
                "SUPABASE_SECRET_KEY": "sec",
                "SUPABASE_DB_URL": "postgres://db",
            }
        )
        self.assertIsNone(error)
        assert overlay is not None
        self.assertEqual(overlay["SUPABASE_PROJECT_REF"], "abc123")
        self.assertEqual(
            resolve_project_ref_from_environment(
                {"SUPABASE_URL": "https://abc123.supabase.co"}
            ),
            "abc123",
        )

    def test_wrong_branch_blocks_activate_without_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._seed_project(Path(tmp), "demo-app")
            self._init_git_repo(project, "main")
            register_personal_supabase(project, schema="demo-app")
            self._git(project, "checkout", "-b", "feature")

            result = commit_personal_supabase_scaffold(project, "main", schema="demo-app")

            self.assertFalse(result.succeeded)
            self.assertIn("feature", result.message)
            self.assertIn("main", result.message)
            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(branch, "feature")

    def test_unrelated_dirty_files_block_activate_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._seed_project(Path(tmp), "demo-app")
            self._init_git_repo(project, "main")
            register_personal_supabase(project, schema="demo-app")
            (project / "NOTES.md").write_text("unrelated\n", encoding="utf-8")

            result = commit_personal_supabase_scaffold(project, "main", schema="demo-app")

            self.assertFalse(result.succeeded)
            self.assertIn("Unrelated dirty", result.message)

    def test_activate_commits_personal_schema_migration_and_matching_supabase_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._seed_project(Path(tmp), "demo-app")
            self._init_git_repo(project, "main")
            register_personal_supabase(project, schema="demo-app")
            migrations = project / "supabase" / "migrations"
            migrations.mkdir(parents=True)
            (project / "supabase" / "config.toml").write_text(
                '[api]\nschemas = ["public", "demo-app"]\n',
                encoding="utf-8",
            )
            migration = migrations / "20260101000000_create_personal_schema.sql"
            migration.write_text(
                'CREATE SCHEMA IF NOT EXISTS "demo-app";\n',
                encoding="utf-8",
            )

            result = commit_personal_supabase_scaffold(project, "main", schema="demo-app")

            self.assertTrue(result.succeeded)
            self.assertTrue(result.committed)
            names = subprocess.run(
                ["git", "show", "--name-only", "--pretty=", "HEAD"],
                cwd=project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.splitlines()
            self.assertIn("supabase/config.toml", names)
            self.assertIn(
                "supabase/migrations/20260101000000_create_personal_schema.sql",
                names,
            )

    def test_unrelated_supabase_migration_still_blocks_activate_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._seed_project(Path(tmp), "demo-app")
            self._init_git_repo(project, "main")
            register_personal_supabase(project, schema="demo-app")
            migrations = project / "supabase" / "migrations"
            migrations.mkdir(parents=True)
            (migrations / "20260101000000_create_personal_schema.sql").write_text(
                'CREATE SCHEMA IF NOT EXISTS "demo-app";\n',
                encoding="utf-8",
            )
            (migrations / "20260101000001_add_users.sql").write_text(
                'CREATE TABLE "demo-app".users (id integer);\n',
                encoding="utf-8",
            )
            (project / "supabase" / "config.toml").write_text(
                '[api]\nschemas = ["public", "demo-app"]\n',
                encoding="utf-8",
            )

            result = commit_personal_supabase_scaffold(project, "main", schema="demo-app")

            self.assertFalse(result.succeeded)
            self.assertIn("supabase/migrations/20260101000001_add_users.sql", result.message)

    def test_clean_operating_branch_commits_only_scaffold_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._seed_project(Path(tmp), "demo-app")
            self._init_git_repo(project, "main")
            register_personal_supabase(project, schema="demo-app")

            result = commit_personal_supabase_scaffold(project, "main", schema="demo-app")

            self.assertTrue(result.succeeded)
            self.assertTrue(result.committed)
            names = subprocess.run(
                ["git", "show", "--name-only", "--pretty=", "HEAD"],
                cwd=project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.splitlines()
            self.assertTrue(any(name.startswith("daedalus-migrations/") for name in names))
            self.assertIn(".daedalus", names)
            self.assertNotIn("NOTES.md", names)
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(status, "")

    def test_preflight_token_requires_visible_project_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch = Path(tmp)
            self._write_project_env(launch, token=True)

            def fake_run(command, capture_output, text, env, timeout):
                self.assertEqual(command[:3], ["supabase", "projects", "list"])
                return SimpleNamespace(returncode=0, stdout="other-ref\n", stderr="")

            result = preflight_personal_supabase(
                launch,
                run_process=fake_run,
                find_executable=lambda name: f"/bin/{name}",
            )
            self.assertFalse(result.succeeded)
            self.assertIn("not visible", result.message)

            def ok_run(command, capture_output, text, env, timeout):
                return SimpleNamespace(returncode=0, stdout="shared-ref\n", stderr="")

            ok = preflight_personal_supabase(
                launch,
                run_process=ok_run,
                find_executable=lambda name: f"/bin/{name}",
            )
            self.assertTrue(ok.succeeded)
            self.assertEqual(ok.method, "access_token")

    def test_preflight_db_url_uses_reachability_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch = Path(tmp)
            self._write_project_env(launch, token=False)

            with patch("tui.personal_supabase.socket.create_connection") as connect:
                connect.return_value.__enter__ = lambda self: None
                connect.return_value.__exit__ = lambda *args: None
                result = preflight_personal_supabase(
                    launch,
                    find_executable=lambda name: "/bin/supabase" if name == "supabase" else None,
                )
            self.assertTrue(result.succeeded)
            self.assertEqual(result.method, "db_url")

    def test_preflight_db_url_reports_direct_host_project_ref_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch = Path(tmp)
            self._write_project_env(launch, token=False)
            env_path = launch / ".env"
            env_path.write_text(
                env_path.read_text(encoding="utf-8").replace(
                    "example.test", "db.other-ref.supabase.co"
                ),
                encoding="utf-8",
            )

            with patch("tui.personal_supabase.socket.create_connection") as connect:
                result = preflight_personal_supabase(
                    launch,
                    find_executable=lambda name: "/bin/supabase" if name == "supabase" else None,
                )

            self.assertFalse(result.succeeded)
            self.assertIn("points to database project 'other-ref'", result.message)
            self.assertIn("points to 'shared-ref'", result.message)
            connect.assert_not_called()

    def test_preflight_db_url_explains_dns_lookup_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch = Path(tmp)
            self._write_project_env(launch, token=False)
            env_path = launch / ".env"
            env_path.write_text(
                env_path.read_text(encoding="utf-8").replace(
                    "example.test", "db.shared-ref.supabase.co"
                ),
                encoding="utf-8",
            )

            with patch(
                "tui.personal_supabase.socket.create_connection",
                side_effect=socket.gaierror(8, "nodename nor servname provided, or not known"),
            ):
                result = preflight_personal_supabase(
                    launch,
                    find_executable=lambda name: "/bin/supabase" if name == "supabase" else None,
                )

            self.assertFalse(result.succeeded)
            self.assertIn("DNS could not resolve database host", result.message)
            self.assertIn("project's Connect settings", result.message)
            self.assertIn("direct db.* endpoint is IPv6 by default", result.message)
            self.assertIn("choose Session pooler", result.message)
            self.assertIn("SUPABASE_DB_URL", result.message)
            self.assertIn("CLI login does not affect DNS", result.message)

    def test_activate_success_pushes_once_and_marks_activated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = root / "launch"
            project = self._seed_project(launch, "demo-app")
            self._init_git_repo(project, "main")
            self._write_project_env(project)
            push_calls = []
            psql_calls = []
            progress = []

            def fake_run(command, capture_output, text, env=None, timeout=None, cwd=None):
                if command[0] in {"psql", "/bin/psql"}:
                    psql_calls.append(command)
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                raise AssertionError(f"Unexpected command: {command}")

            def fake_push(directory, *, executable="supabase", env=None, database_url=None):
                push_calls.append(directory)
                return PushResult(True, "ok")

            with patch("tui.personal_supabase.push_migrations", side_effect=fake_push), patch(
                "tui.personal_supabase.synchronize_personal_migrations",
                return_value=SimpleNamespace(succeeded=True, conflicts=()),
            ):
                result = activate_personal_supabase(
                    project,
                    "main",
                    schema="demo-app",
                    run_process=fake_run,
                    find_executable=lambda name: f"/bin/{name}",
                    progress_callback=progress.append,
                )

            self.assertEqual(result.status, "success")
            self.assertTrue(result.activated)
            self.assertTrue(result.scaffolded)
            self.assertEqual(len(push_calls), 1)
            self.assertEqual(len(psql_calls), 1)
            self.assertEqual(psql_calls[0][-1], "SELECT 1;")
            self.assertEqual(
                progress,
                [
                    "Checking registration",
                    "Scaffolding project migration files",
                    "Validating scaffold",
                    "Committing scaffold changes",
                    "Validating environment",
                    "Checking Supabase connection",
                    "Synchronize and apply migrations from the Daedalus TUI root",
                    "Complete",
                ],
            )
            status = load_personal_supabase_status(project)
            self.assertTrue(status.activated)
            self.assertEqual(status.last_activate_status, "success")
            self.assertTrue((project / "daedalus-migrations").is_dir())
            self.assertFalse((project / "supabase").exists())
            dirty = subprocess.run(
                ["git", "status", "--porcelain", "--", ".daedalus", "daedalus-migrations", ".env.example", ".agents"],
                cwd=project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(dirty, "")
            log = subprocess.run(
                ["git", "log", "--oneline"],
                cwd=project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            self.assertIn("activated", log.lower())
            with (project / ".daedalus").open("rb") as source:
                committed = tomllib.load(source)
            tip = subprocess.run(
                ["git", "show", "HEAD:.daedalus"],
                cwd=project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            self.assertIn("activated = true", tip)
            self.assertTrue(committed["personal_supabase"]["activated"])

    def test_activate_retry_skips_scaffold_and_reruns_phase_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = root / "launch"
            project = self._seed_project(launch, "demo-app")
            self._init_git_repo(project, "main")
            register_personal_supabase(project, schema="demo-app")
            migration = next((project / "daedalus-migrations").glob("*.sql"))
            before = migration.read_text(encoding="utf-8")
            self._write_project_env(project)

            def fake_run(command, capture_output, text, env=None, timeout=None, cwd=None):
                return SimpleNamespace(returncode=0, stdout="shared-ref\n", stderr="")

            with patch(
                "tui.personal_supabase.push_migrations",
                return_value=PushResult(True, "ok"),
            ), patch(
                "tui.personal_supabase.synchronize_personal_migrations",
                return_value=SimpleNamespace(succeeded=True, conflicts=()),
            ):
                result = activate_personal_supabase(
                    project,
                    "main",
                    schema="demo-app",
                    run_process=fake_run,
                    find_executable=lambda name: f"/bin/{name}",
                )

            self.assertEqual(result.status, "success")
            self.assertFalse(result.scaffolded)
            self.assertEqual(migration.read_text(encoding="utf-8"), before)
            self.assertTrue(is_personal_supabase_activated(project, "demo-app"))

    def test_failed_preflight_leaves_commit_and_records_blocked_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = root / "launch"
            project = self._seed_project(launch, "demo-app")
            self._init_git_repo(project, "main")
            self._write_project_env(project)

            def fake_run(command, capture_output, text, env=None, timeout=None, cwd=None):
                return SimpleNamespace(returncode=1, stdout="", stderr="auth failed")

            with patch("tui.personal_supabase.push_migrations") as push:
                result = activate_personal_supabase(
                    project,
                    "main",
                    schema="demo-app",
                    run_process=fake_run,
                    find_executable=lambda name: f"/bin/{name}",
                )
                push.assert_not_called()

            self.assertEqual(result.status, "blocked")
            self.assertEqual(result.blocked_reason, "blocked_supabase")
            status = load_personal_supabase_status(project)
            self.assertTrue(status.registered)
            self.assertFalse(status.activated)
            self.assertEqual(status.last_activate_status, "blocked_supabase")
            log = subprocess.run(
                ["git", "log", "--oneline"],
                cwd=project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            self.assertIn("personal Supabase", log)

    def test_activated_helper_distinguishes_scaffolded_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._seed_project(Path(tmp), "demo-app")
            register_personal_supabase(project, schema="demo-app")
            self.assertTrue(is_personal_supabase_registered(project, "demo-app"))
            self.assertFalse(is_personal_supabase_activated(project, "demo-app"))


if __name__ == "__main__":
    unittest.main()
