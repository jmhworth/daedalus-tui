import tempfile
import tomllib
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from tui.personal_supabase import (
    bootstrap_personal_supabase,
    is_personal_supabase_registered,
    load_personal_supabase_status,
    profile_guidance_section,
    register_personal_supabase,
    schema_from_project_root,
    temporary_supabase_cli_config,
)
from tui.project_initializer import initialize_project


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

            migration = (
                project / "supabase" / "migrations" / "20260101000000_create_personal_schema.sql"
            )
            self.assertTrue((project / "supabase" / "config.toml").is_file())
            self.assertTrue(migration.is_file())
            migration_text = migration.read_text(encoding="utf-8")
            self.assertIn('CREATE SCHEMA IF NOT EXISTS "example-project";', migration_text)

            env_text = (project / ".env.example").read_text(encoding="utf-8")
            self.assertIn("SUPABASE_URL=", env_text)
            self.assertIn("SUPABASE_ANON_KEY=", env_text)
            self.assertIn("SUPABASE_SERVICE_ROLE_KEY=", env_text)
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
            self.assertEqual(status.schema, "example-project")
            self.assertTrue(is_personal_supabase_registered(project, "example-project"))

            with (project / ".daedalus").open("rb") as source:
                values = tomllib.load(source)
            self.assertEqual(values["worktree"]["install_command"], [])
            self.assertEqual(values["personal_supabase"]["schema"], "example-project")

    def test_registration_is_idempotent_for_same_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._seed_project(Path(tmp))
            first = register_personal_supabase(project)
            second = register_personal_supabase(project)
            self.assertEqual(first.status, "success")
            self.assertEqual(second.status, "success")
            self.assertTrue(second.already_registered)
            self.assertEqual(
                list((project / "supabase" / "migrations").iterdir()),
                [project / "supabase" / "migrations" / "20260101000000_create_personal_schema.sql"],
            )

    def test_conflicting_marker_and_foreign_migrations_fail_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._seed_project(Path(tmp), "alpha")
            register_personal_supabase(project, schema="alpha")
            conflict = register_personal_supabase(project, schema="beta")
            self.assertEqual(conflict.status, "failed")
            self.assertIn("already registered for schema 'alpha'", conflict.message)

            other = self._seed_project(Path(tmp), "other-app")
            migrations = other / "supabase" / "migrations"
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

    def test_launch_bootstrap_syncs_root_env_and_restores_placeholder_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = root / "launch"
            project = launch / "demo-app"
            project.mkdir(parents=True)
            self._seed_project(launch, "demo-app")
            register_personal_supabase(project, schema="demo-app")
            (launch / ".env").write_text(
                "SUPABASE_PROJECT_REF=shared-ref\n"
                "SUPABASE_URL=https://example.test\n"
                "SUPABASE_ANON_KEY=anon-key\n"
                "SUPABASE_SERVICE_ROLE_KEY=service-key\n"
                "SUPABASE_DB_URL=postgres://user:password@example.test/db\n",
                encoding="utf-8",
            )
            config = project / "supabase" / "config.toml"
            original = config.read_text(encoding="utf-8")

            result = bootstrap_personal_supabase(project, launch)
            self.assertEqual(result.status, "success")
            self.assertEqual(result.project_ref, "shared-ref")
            project_env = (project / ".env").read_text(encoding="utf-8")
            self.assertIn("SUPABASE_PROJECT_REF=shared-ref", project_env)
            self.assertIn("SUPABASE_SCHEMA=demo-app", project_env)
            with temporary_supabase_cli_config(project, "shared-ref"):
                self.assertIn('project_id = "shared-ref"', config.read_text(encoding="utf-8"))
            self.assertEqual(config.read_text(encoding="utf-8"), original)

    def test_launch_bootstrap_reports_missing_credentials_without_writing_project_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = root / "launch"
            self._seed_project(launch, "demo-app")
            project = launch / "demo-app"
            register_personal_supabase(project, schema="demo-app")

            result = bootstrap_personal_supabase(project, launch)

            self.assertEqual(result.status, "failed")
            self.assertIn("database access", result.message)
            self.assertFalse((project / ".env").exists())

    def test_disabled_push_bootstrap_syncs_without_database_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = root / "launch"
            self._seed_project(launch, "demo-app")
            project = launch / "demo-app"
            register_personal_supabase(project, schema="demo-app")
            (launch / ".env").write_text(
                "SUPABASE_PROJECT_REF=shared-ref\n"
                "SUPABASE_URL=https://example.test\n"
                "SUPABASE_ANON_KEY=anon-key\n"
                "SUPABASE_SERVICE_ROLE_KEY=service-key\n",
                encoding="utf-8",
            )

            result = bootstrap_personal_supabase(
                project,
                launch,
                require_database_access=False,
            )

            self.assertEqual(result.status, "success")
            self.assertIn("SUPABASE_PROJECT_REF=shared-ref", (project / ".env").read_text(encoding="utf-8"))

    def test_launch_bootstrap_rejects_project_env_conflict_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = root / "launch"
            self._seed_project(launch, "demo-app")
            project = launch / "demo-app"
            register_personal_supabase(project, schema="demo-app")
            (launch / ".env").write_text(
                "SUPABASE_PROJECT_REF=shared-ref\n"
                "SUPABASE_URL=https://example.test\n"
                "SUPABASE_ANON_KEY=anon-key\n"
                "SUPABASE_SERVICE_ROLE_KEY=service-key\n"
                "SUPABASE_DB_URL=postgres://user:password@example.test/db\n",
                encoding="utf-8",
            )
            project_env = project / ".env"
            project_env.write_text("# preserve\nSUPABASE_URL=https://other.test\n", encoding="utf-8")
            before = project_env.read_text(encoding="utf-8")

            result = bootstrap_personal_supabase(project, launch)

            self.assertEqual(result.status, "failed")
            self.assertIn("conflicting", result.message)
            self.assertEqual(project_env.read_text(encoding="utf-8"), before)

    def test_new_project_flag_registers_before_git_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = []

            def fake_run(command, cwd, capture_output, text, shell):
                calls.append((command, Path(cwd)))
                if command[:2] == ["git", "init"]:
                    (Path(cwd) / ".git").mkdir()
                if command[:2] == ["git", "add"]:
                    destination = Path(cwd)
                    self.assertTrue((destination / "supabase" / "config.toml").is_file())
                    self.assertTrue((destination / ".env.example").is_file())
                    self.assertTrue(
                        is_personal_supabase_registered(destination, "schema-app")
                    )
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            result = initialize_project(
                {
                    "requestId": str(uuid.uuid4()),
                    "projectName": "schema-app",
                    "createGitHubRepository": False,
                    "registerPersonalSupabase": True,
                },
                execution_root=root,
                run_process=fake_run,
                find_executable=lambda executable: f"/bin/{executable}",
            )
            self.assertEqual(result["status"], "success")
            destination = root / "schema-app"
            self.assertTrue(is_personal_supabase_registered(destination, "schema-app"))
            env_text = (destination / ".env.example").read_text(encoding="utf-8")
            self.assertIn("SUPABASE_SCHEMA=schema-app", env_text)
            self.assertIn(
                ["git", "add", "."],
                [command for command, _ in calls],
            )


if __name__ == "__main__":
    unittest.main()
