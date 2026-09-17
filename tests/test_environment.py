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
