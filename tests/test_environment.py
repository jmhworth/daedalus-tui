import tempfile
import unittest
from pathlib import Path

from tui.environment import cursor_environment, read_env_file, redact_environment_values


class EnvironmentTests(unittest.TestCase):
    def test_read_env_file_skips_comments_and_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "# comment\n"
                "export SUPABASE_URL=https://example.test\n"
                "LOCAL_SETTING=one\n"
                "QUOTED=\"value with spaces\"\n",
                encoding="utf-8",
            )
            values = read_env_file(path)
            self.assertEqual(values["SUPABASE_URL"], "https://example.test")
            self.assertEqual(values["LOCAL_SETTING"], "one")
            self.assertEqual(values["QUOTED"], "value with spaces")
            self.assertNotIn("# comment", values)

    def test_read_env_file_strips_bom_and_key_padding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_bytes(
                b"\xef\xbb\xbfSUPABASE_URL = https://bom.example.test\n"
                b"SUPABASE_PUBLISHABLE_KEY= publishable \n"
            )
            values = read_env_file(path)
            self.assertEqual(values["SUPABASE_URL"], "https://bom.example.test")
            self.assertEqual(values["SUPABASE_PUBLISHABLE_KEY"], "publishable")

    def test_apply_process_supabase_overrides_wins_when_non_empty(self):
        import os
        from unittest.mock import patch

        from tui.environment import apply_process_supabase_overrides

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://from-process.test", "SUPABASE_SECRET_KEY": "  "},
            clear=False,
        ):
            merged = apply_process_supabase_overrides(
                {
                    "SUPABASE_URL": "https://from-file.test",
                    "SUPABASE_SECRET_KEY": "from-file",
                }
            )
        self.assertEqual(merged["SUPABASE_URL"], "https://from-process.test")
        self.assertEqual(merged["SUPABASE_SECRET_KEY"], "from-file")

    def test_cursor_environment_prefers_process_over_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            (project / ".env").write_text("CURSOR_API_KEY=from-project\n", encoding="utf-8")
            launch = root / "launch.env"
            launch.write_text("CURSOR_API_KEY=from-launch\n", encoding="utf-8")
            import os
            from unittest.mock import patch

            with patch.dict(os.environ, {"CURSOR_API_KEY": "from-process"}, clear=False):
                environment = cursor_environment(project, (launch,))
            self.assertEqual(environment["CURSOR_API_KEY"], "from-process")

    def test_cursor_environment_skips_empty_assignments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            (project / ".env").write_text("CURSOR_API_KEY=\nOTHER=kept\n", encoding="utf-8")
            launch = root / "launch.env"
            launch.write_text("CURSOR_API_KEY=from-launch\n", encoding="utf-8")
            import os
            from unittest.mock import patch

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CURSOR_API_KEY", None)
                environment = cursor_environment(project, (launch,))
            self.assertEqual(environment["CURSOR_API_KEY"], "from-launch")
            self.assertEqual(environment["OTHER"], "kept")

    def test_agent_credential_fallbacks_use_launch_then_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            launch = root / "launch.env"
            package = root / "package.env"
            launch.write_text("CURSOR_API_KEY=from-launch\nSUPABASE_URL=https://launch.test\n", encoding="utf-8")
            package.write_text("CURSOR_API_KEY=from-package\n", encoding="utf-8")
            import os
            from unittest.mock import patch

            from tui.environment import with_agent_credential_fallbacks

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CURSOR_API_KEY", None)
                with patch("tui.environment.tui_package_env_path", return_value=package):
                    environment = with_agent_credential_fallbacks({}, (launch,))
            self.assertEqual(environment["CURSOR_API_KEY"], "from-launch")
            self.assertNotIn("SUPABASE_URL", environment)

    def test_agent_credential_fallbacks_prefer_existing_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            launch = root / "launch.env"
            launch.write_text("CURSOR_API_KEY=from-launch\n", encoding="utf-8")
            from tui.environment import with_agent_credential_fallbacks

            environment = with_agent_credential_fallbacks(
                {"CURSOR_API_KEY": "from-project"},
                (launch,),
            )
            self.assertEqual(environment["CURSOR_API_KEY"], "from-project")

    def test_redact_environment_values_masks_secrets(self):
        message = "failed with token=secret-value and url=https://example.test"
        redacted = redact_environment_values(
            message,
            {
                "SUPABASE_SECRET_KEY": "secret-value",
                "SUPABASE_URL": "https://example.test",
            },
        )
        self.assertNotIn("secret-value", redacted)
        self.assertNotIn("https://example.test", redacted)
        self.assertIn("[redacted]", redacted)


if __name__ == "__main__":
    unittest.main()
