import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tui.firebase import (
    deploy_firebase,
    firebase_changes_pending,
    is_firebase_registered,
    load_firebase_settings,
    load_firebase_status,
    profile_guidance_section,
    register_firebase,
)


class CompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FirebaseRegistrationTests(unittest.TestCase):
    def project(self, directory, name="demo-app"):
        project = Path(directory) / name
        (project / ".agents" / "profiles").mkdir(parents=True)
        return project

    def test_scaffolds_config_rules_indexes_env_and_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.project(directory)

            result = register_firebase(project)

            self.assertEqual(result.status, "success")
            config = json.loads((project / "firebase.json").read_text(encoding="utf-8"))
            self.assertEqual(config["firestore"]["rules"], "firestore.rules")
            self.assertEqual(config["firestore"]["indexes"], "firestore.indexes.json")
            self.assertIn("allow read, write: if false;", (project / "firestore.rules").read_text())
            self.assertEqual(
                json.loads((project / "firestore.indexes.json").read_text(encoding="utf-8")),
                {"indexes": [], "fieldOverrides": []},
            )
            self.assertIn("FIREBASE_PROJECT_ID=demo-app", (project / ".env.example").read_text())
            self.assertTrue(is_firebase_registered(project, "demo-app"))
            self.assertEqual(load_firebase_status(project).project_id, "demo-app")

    def test_registration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.project(directory)
            register_firebase(project)

            repeated = register_firebase(project)

            self.assertEqual(repeated.status, "success")
            self.assertTrue(repeated.already_registered)

    def test_refuses_a_second_project_id(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.project(directory)
            register_firebase(project)

            conflicting = register_firebase(project, project_id="other-app")

            self.assertEqual(conflicting.status, "failed")
            self.assertIn("already registered", conflicting.message)

    def test_rejects_unreadable_existing_config(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.project(directory)
            (project / "firebase.json").write_text("{not json", encoding="utf-8")

            result = register_firebase(project)

            self.assertEqual(result.status, "failed")
            self.assertIn("not readable JSON", result.message)

    def test_preserves_existing_hosting_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.project(directory)
            (project / "firebase.json").write_text(
                json.dumps({"hosting": {"public": "dist"}}), encoding="utf-8"
            )

            register_firebase(project)

            config = json.loads((project / "firebase.json").read_text(encoding="utf-8"))
            self.assertEqual(config["hosting"], {"public": "dist"})
            self.assertIn("firestore", config)

    def test_writes_profile_guidance_that_forbids_agent_deploys(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.project(directory)
            (project / ".agents" / "profiles" / "coding.md").write_text("# Coding\n", encoding="utf-8")

            register_firebase(project)

            coding = (project / ".agents" / "profiles" / "coding.md").read_text(encoding="utf-8")
            self.assertIn("# Coding", coding)
            self.assertIn("Firebase Backend", coding)
            self.assertIn("must not run `firebase deploy`", coding)

    def test_guidance_names_the_configured_deploy_targets(self):
        section = profile_guidance_section("demo-app")
        self.assertIn("firestore:rules, firestore:indexes", section)


class FirebaseDeployTests(unittest.TestCase):
    def test_pending_changes_use_the_watched_paths(self):
        with patch("tui.firebase.subprocess.run") as run:
            run.return_value = CompletedProcess(stdout="firestore.rules\n")

            self.assertTrue(firebase_changes_pending(Path("/w"), "abc123"))

            command = run.call_args.args[0]
            self.assertEqual(command[:4], ["git", "diff", "--name-only", "abc123"])
            self.assertIn("firestore.rules", command)
            self.assertIn("firebase.json", command)

    def test_no_pending_changes_when_the_diff_is_empty(self):
        with patch("tui.firebase.subprocess.run") as run:
            run.return_value = CompletedProcess(stdout="   \n")
            self.assertFalse(firebase_changes_pending(Path("/w"), "abc123"))

    def test_deploy_passes_targets_and_project_id(self):
        with patch("tui.firebase.shutil.which", return_value="/usr/bin/firebase"), patch(
            "tui.firebase.subprocess.run"
        ) as run:
            run.return_value = CompletedProcess(stdout="Deploy complete!")

            result = deploy_firebase(Path("/w"), project_id="demo-app")

            self.assertTrue(result.succeeded)
            self.assertEqual(
                run.call_args.args[0],
                [
                    "firebase", "deploy", "--only", "firestore:rules,firestore:indexes",
                    "--non-interactive", "--project", "demo-app",
                ],
            )

    def test_deploy_omits_the_placeholder_project_id(self):
        settings = load_firebase_settings()
        with patch("tui.firebase.shutil.which", return_value="/usr/bin/firebase"), patch(
            "tui.firebase.subprocess.run"
        ) as run:
            run.return_value = CompletedProcess()

            deploy_firebase(Path("/w"), project_id=settings["config_project_id_placeholder"])

            self.assertNotIn("--project", run.call_args.args[0])

    def test_deploy_reports_a_missing_executable(self):
        with patch("tui.firebase.shutil.which", return_value=None):
            result = deploy_firebase(Path("/w"))

        self.assertFalse(result.succeeded)
        self.assertIn("not available on PATH", result.output)

    def test_deploy_combines_stdout_and_stderr_on_failure(self):
        with patch("tui.firebase.shutil.which", return_value="/usr/bin/firebase"), patch(
            "tui.firebase.subprocess.run"
        ) as run:
            run.return_value = CompletedProcess(1, "partial output", "rules compile error")

            result = deploy_firebase(Path("/w"), project_id="demo-app")

        self.assertFalse(result.succeeded)
        self.assertIn("rules compile error", result.output)
        self.assertIn("partial output", result.output)

    def test_deploy_surfaces_os_errors(self):
        with patch("tui.firebase.shutil.which", return_value="/usr/bin/firebase"), patch(
            "tui.firebase.subprocess.run", side_effect=OSError("boom")
        ):
            result = deploy_firebase(Path("/w"))

        self.assertFalse(result.succeeded)
        self.assertIn("boom", result.output)


if __name__ == "__main__":
    unittest.main()
