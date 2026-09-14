import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tui.environment import read_env_file, synchronize_env_file


class EnvironmentTests(unittest.TestCase):
    def test_sync_preserves_comments_unrelated_values_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / ".env"
            target = root / "project" / ".env"
            source.write_text(
                "# Shared connection\nSUPABASE_PROJECT_REF=shared-ref\nSUPABASE_URL=https://example.test\n",
                encoding="utf-8",
            )
            target.parent.mkdir()
            target.write_text(
                "# Keep this comment\nLOCAL_SETTING=one\nSUPABASE_PROJECT_REF=\n",
                encoding="utf-8",
            )

            first = synchronize_env_file(
                source,
                target,
                ("SUPABASE_PROJECT_REF", "SUPABASE_URL"),
                project_values={"SUPABASE_SCHEMA": "demo"},
                required_keys=("SUPABASE_PROJECT_REF",),
            )
            second = synchronize_env_file(
                source,
                target,
                ("SUPABASE_PROJECT_REF", "SUPABASE_URL"),
                project_values={"SUPABASE_SCHEMA": "demo"},
                required_keys=("SUPABASE_PROJECT_REF",),
            )

            self.assertTrue(first.succeeded)
            self.assertTrue(first.changed)
            self.assertTrue(second.succeeded)
            self.assertFalse(second.changed)
            text = target.read_text(encoding="utf-8")
            self.assertIn("# Keep this comment", text)
            self.assertIn("LOCAL_SETTING=one", text)
            self.assertEqual(read_env_file(target)["SUPABASE_SCHEMA"], "demo")

    def test_conflict_does_not_modify_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / ".env"
            target = root / "project.env"
            source.write_text("SUPABASE_PROJECT_REF=ref-a\n", encoding="utf-8")
            target.write_text("# untouched\nSUPABASE_PROJECT_REF=ref-b\n", encoding="utf-8")
            before = target.read_text(encoding="utf-8")

            result = synchronize_env_file(
                source,
                target,
                ("SUPABASE_PROJECT_REF",),
                required_keys=("SUPABASE_PROJECT_REF",),
            )

            self.assertFalse(result.succeeded)
            self.assertIn("SUPABASE_PROJECT_REF", result.message)
            self.assertEqual(target.read_text(encoding="utf-8"), before)

    def test_process_environment_is_not_written_by_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / ".env"
            target = root / "project.env"
            source.write_text("SUPABASE_PROJECT_REF=file-ref\n", encoding="utf-8")
            with patch.dict(os.environ, {"SUPABASE_PROJECT_REF": "runtime-ref"}):
                result = synchronize_env_file(
                    source,
                    target,
                    ("SUPABASE_PROJECT_REF",),
                    required_keys=("SUPABASE_PROJECT_REF",),
                )

            self.assertTrue(result.succeeded)
            self.assertEqual(read_env_file(target)["SUPABASE_PROJECT_REF"], "file-ref")


if __name__ == "__main__":
    unittest.main()
