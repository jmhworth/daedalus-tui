"""Storage tests for exact prompt archives, drafts, and the local storage root."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from tui.local_storage import LocalStorage, project_key
from tui.prompt_store import PromptStore, PromptStoreError


class LocalStorageTests(unittest.TestCase):
    def test_project_keys_distinguish_same_basename_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "work" / "app"
            second = root / "personal" / "app"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            self.assertNotEqual(project_key(first), project_key(second))
            self.assertTrue(project_key(first).startswith("app-"))
            storage = LocalStorage(root / "data")
            self.assertNotEqual(storage.task_prompts_dir(first, "001-abc"), storage.task_prompts_dir(second, "001-abc"))
            data_root = (root / "data").resolve()
            self.assertTrue(str(storage.task_prompts_dir(first, "001-abc")).startswith(str(data_root / "prompts")))
            self.assertTrue(str(storage.task_errors_dir(first, "001-abc")).startswith(str(data_root / "errors")))

    def test_storage_root_is_independent_of_working_directory_and_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            storage = LocalStorage(root / "tui-data")
            previous = os.getcwd()
            try:
                os.chdir(root)
                other_project = root / "elsewhere"
                other_project.mkdir()
                path = storage.task_prompts_dir(other_project, "001-abc")
            finally:
                os.chdir(previous)
            self.assertEqual(path.parents[1], (root / "tui-data" / "prompts").resolve())

    def test_unavailable_root_reports_the_exact_path(self):
        with tempfile.TemporaryDirectory() as directory:
            blocker = Path(directory) / "file"
            blocker.write_text("not a directory", encoding="utf-8")
            storage = LocalStorage(blocker / "nested")
            status = storage.ensure(storage.prompts_root)
            self.assertFalse(status.available)
            self.assertIn(str(storage.prompts_root), status.error)


class PromptStoreTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.storage = LocalStorage(self.root / "data")
        self.store = PromptStore(self.storage)

    def tearDown(self):
        self._directory.cleanup()

    def test_archives_exact_text_including_indentation_blank_lines_and_trailing_newlines(self):
        text = "  # Title\n\n    indented\n\n\n"
        path = self.store.archive_turn(self.project, "001-abc", 1, text)
        self.assertEqual(path.name, "turn-0001.md")
        self.assertEqual(path.read_text(encoding="utf-8"), text)
        # Idempotent for identical content; differing content is preserved aside.
        self.assertEqual(self.store.archive_turn(self.project, "001-abc", 1, text), path)
        self.store.archive_turn(self.project, "001-abc", 1, "different")
        stale = [entry for entry in path.parent.iterdir() if ".stale-" in entry.name]
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0].read_text(encoding="utf-8"), text)
        self.assertEqual(path.read_text(encoding="utf-8"), "different")
        self.assertFalse(any(entry.suffix == ".tmp" for entry in path.parent.iterdir()))

    def test_drafts_round_trip_cursor_revision_and_revised_turn(self):
        saved = self.store.save_draft(
            self.project, "001-abc", "partial\ntext", cursor=(1, 4), revision=3, revises_turn_id="turn-x"
        )
        self.assertEqual(saved.revision, 3)
        loaded = self.store.load_draft(self.project, "001-abc")
        self.assertEqual((loaded.text, loaded.cursor, loaded.revision, loaded.revises_turn_id), ("partial\ntext", (1, 4), 3, "turn-x"))
        self.assertEqual(loaded.project_key, project_key(self.project))
        new_task = self.store.save_draft(self.project, None, "new task draft", draft_id="new-task")
        self.assertIsNone(new_task.task_id)
        self.assertEqual(self.store.load_draft(self.project, None, "new-task").text, "new task draft")
        self.store.delete_draft(self.project, "001-abc")
        self.assertIsNone(self.store.load_draft(self.project, "001-abc"))

    def test_stale_autosave_cannot_replace_a_newer_draft(self):
        self.store.save_draft(self.project, "001-abc", "newer", revision=5)
        result = self.store.save_draft(self.project, "001-abc", "older", revision=4)
        self.assertEqual(result.text, "newer")
        self.assertEqual(self.store.load_draft(self.project, "001-abc").text, "newer")
        self.store.save_draft(self.project, "001-abc", "newest", revision=6)
        self.assertEqual(self.store.load_draft(self.project, "001-abc").text, "newest")

    def test_corrupt_draft_is_preserved_for_inspection(self):
        path = self.store.draft_path(self.project, "001-abc")
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(self.store.load_draft(self.project, "001-abc"))
        preserved = [entry for entry in path.parent.iterdir() if ".corrupt-" in entry.name]
        self.assertEqual(len(preserved), 1)
        self.assertEqual(preserved[0].read_text(encoding="utf-8"), "{not json")

    def test_reconcile_regenerates_missing_archives_and_reports_orphans(self):
        self.store.archive_turn(self.project, "001-abc", 1, "first")
        self.store.archive_turn(self.project, "001-abc", 3, "orphaned partial submission")
        orphans = self.store.reconcile(self.project, "001-abc", {1: "first", 2: "second"})
        self.assertEqual([turn.sequence for turn in orphans], [3])
        self.assertEqual(self.store.turn_path(self.project, "001-abc", 2).read_text(encoding="utf-8"), "second")
        self.assertEqual(self.store.read_turn(orphans[0].path), "orphaned partial submission")

    @unittest.skipIf(os.name != "posix" or os.geteuid() == 0, "requires POSIX permissions")
    def test_unwritable_path_raises_with_the_exact_path(self):
        task_dir = self.store.task_dir(self.project, "001-abc")
        task_dir.mkdir(parents=True)
        os.chmod(task_dir, stat.S_IRUSR | stat.S_IXUSR)
        try:
            with self.assertRaises(PromptStoreError) as raised:
                self.store.archive_turn(self.project, "001-abc", 1, "text")
            self.assertIn(str(task_dir), str(raised.exception))
            with self.assertRaises(PromptStoreError):
                self.store.save_draft(self.project, "001-abc", "text")
        finally:
            os.chmod(task_dir, stat.S_IRWXU)

    def test_list_drafts_returns_saved_follow_ups_newest_first(self):
        self.store.save_draft(self.project, "001-abc", "a", draft_id="stash-1", kind="stashed")
        self.store.save_draft(self.project, "001-abc", "b", draft_id="stash-2", kind="stashed")
        drafts = self.store.list_drafts(self.project, "001-abc")
        self.assertEqual({draft.draft_id for draft in drafts}, {"stash-1", "stash-2"})
        self.assertTrue(all(draft.kind == "stashed" for draft in drafts))
        data = json.loads(self.store.draft_path(self.project, "001-abc", "stash-1").read_text(encoding="utf-8"))
        self.assertEqual(data["kind"], "stashed")


if __name__ == "__main__":
    unittest.main()
