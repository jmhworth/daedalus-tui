import json
import tempfile
import unittest
from pathlib import Path

from tui.memory import TaskMemoryStore


class TaskMemoryStoreTests(unittest.TestCase):
    def test_persists_conversation_chain_links(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskMemoryStore(Path(directory) / ".daedalus-memory.json")
            store.record_task(
                "task-follow-up", "Add context", "codex", "model", "medium",
                "coding", "queued", project=Path(directory),
                logical_task_id="002-child", chain_id="001-root", parent_task_id="001-root",
            )

            snapshot = store.get_tasks()["task-follow-up"]
            self.assertEqual(snapshot["chain_id"], "001-root")
            self.assertEqual(snapshot["parent_task_id"], "001-root")

    def test_records_task_metadata_with_nullable_provider_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            store = TaskMemoryStore(path)
            project = Path(directory) / "project"

            store.record_task(
                "task-one",
                "Make the change",
                "codex",
                "gpt-5.6-luna",
                "high",
                "coding",
                "completed",
                ["Done."],
                submitted_at=0,
                tokens=165,
                project=project,
            )
            store.record_task(
                "task-two",
                "Review the change",
                "cursor",
                None,
                None,
                "ask",
                "failed",
                ["I found an issue."],
                "The check failed.",
                submitted_at=1,
                tokens=321,
                project=project,
            )

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                [
                    {
                        "tasks": {
                            "task-one": {
                                "timestamp": "1970-01-01T00:00:00Z",
                                "prompt": "Make the change",
                                "provider": "codex",
                                "model": "gpt-5.6-luna",
                                "reasoning": "high",
                                "mode": "coding",
                                "state": "completed",
                                "outputs": ["Done."],
                                "error": None,
                                "tokens": 165,
                                "project": str(project.resolve()),
                            },
                            "task-two": {
                                "timestamp": "1970-01-01T00:00:01Z",
                                "prompt": "Review the change",
                                "provider": "cursor",
                                "model": None,
                                "reasoning": None,
                                "mode": "ask",
                                "state": "failed",
                                "outputs": ["I found an issue."],
                                "error": "The check failed.",
                                "tokens": 321,
                                "project": str(project.resolve()),
                            },
                        }
                    },
                ],
            )

    def test_removes_legacy_usage_entries_when_recording_a_task(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            path.write_text(
                json.dumps([{"timestamp": "1970-01-01T00:00:00Z", "tokens": 165}]),
                encoding="utf-8",
            )

            TaskMemoryStore(path).record_task(
                "task-one",
                "Make the change",
                "codex",
                "gpt-5.6-terra",
                "medium",
                "coding",
                "completed",
                submitted_at=1,
            )

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                [
                    {
                        "tasks": {
                            "task-one": {
                                "timestamp": "1970-01-01T00:00:01Z",
                                "prompt": "Make the change",
                                "provider": "codex",
                                "model": "gpt-5.6-terra",
                                "reasoning": "medium",
                                "mode": "coding",
                                "state": "completed",
                                "outputs": [],
                                "error": None,
                                "tokens": 0,
                                "project": None,
                            }
                        }
                    },
                ],
            )

    def test_records_plan_prompt_history_when_a_task_has_followups(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            TaskMemoryStore(path).record_task(
                "task-plan",
                "Choose a store",
                "codex",
                "luna",
                "medium",
                "plan",
                "awaiting_answers",
                prompt_history=(
                    "Choose a store",
                    "Re-evaluate the plan using the user's answers.",
                ),
            )

            task = TaskMemoryStore(path).get_tasks()["task-plan"]
            self.assertEqual(
                task["prompt_history"],
                ["Choose a store", "Re-evaluate the plan using the user's answers."],
            )

    def test_upserts_task_history_by_worktree_name(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            store = TaskMemoryStore(path)

            store.record_task(
                "task-one",
                "Make the change",
                "codex",
                "gpt-5.6-luna",
                "high",
                "coding",
                "running",
                ["Inspecting the worktree."],
                submitted_at=0,
            )
            store.record_task(
                "task-one-renamed",
                "Make the change",
                "codex",
                "gpt-5.6-luna",
                "high",
                "coding",
                "failed",
                ["Inspecting the worktree.", "The check failed."],
                "Verification failed.",
                previous_task_id="task-one",
                submitted_at=0,
            )

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                [
                    {
                        "tasks": {
                            "task-one-renamed": {
                                "timestamp": "1970-01-01T00:00:00Z",
                                "prompt": "Make the change",
                                "provider": "codex",
                                "model": "gpt-5.6-luna",
                                "reasoning": "high",
                                "mode": "coding",
                                "state": "failed",
                                "outputs": ["Inspecting the worktree.", "The check failed."],
                                "error": "Verification failed.",
                                "tokens": 0,
                                "project": None,
                            }
                        }
                    }
                ],
            )

    def test_does_not_replace_a_corrupt_memory_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            path.write_text("not json", encoding="utf-8")

            with self.assertRaises(ValueError):
                TaskMemoryStore(path).record_task(
                    "task-one", "Make the change", "codex", "luna", "medium", "coding", "failed"
                )

            self.assertEqual(path.read_text(encoding="utf-8"), "not json")

    def test_tracks_last_opened_project_without_replacing_task_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            store = TaskMemoryStore(path)
            first_project = Path(directory) / "first"
            second_project = Path(directory) / "second"

            store.record_task(
                "task-one",
                "Make the change",
                "codex",
                "luna",
                "medium",
                "coding",
                "completed",
                submitted_at=0,
            )
            store.set_last_opened_project(first_project)
            store.set_last_opened_project(second_project)

            self.assertEqual(store.get_last_opened_project(), second_project.resolve())
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                [
                    {
                        "tasks": {
                            "task-one": {
                                "timestamp": "1970-01-01T00:00:00Z",
                                "prompt": "Make the change",
                                "provider": "codex",
                                "model": "luna",
                                "reasoning": "medium",
                                "mode": "coding",
                                "state": "completed",
                                "outputs": [],
                                "error": None,
                                "tokens": 0,
                                "project": None,
                            }
                        }
                    },
                    {"last_opened_project": str(second_project.resolve())},
                ],
            )

    def test_set_last_opened_project_keeps_one_marker_when_focus_changes_repeatedly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            store = TaskMemoryStore(path)
            first_project = Path(directory) / "first"
            second_project = Path(directory) / "second"

            store.set_last_opened_project(first_project)
            store.set_last_opened_project(second_project)
            store.set_last_opened_project(first_project)

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                [{"last_opened_project": str(first_project.resolve())}],
            )

    def test_tracks_project_target_branches_without_replacing_other_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            store = TaskMemoryStore(path)
            first_project = Path(directory) / "first"
            second_project = Path(directory) / "second"

            store.record_task(
                "task-one",
                "Make the change",
                "codex",
                "luna",
                "medium",
                "coding",
                "completed",
                submitted_at=0,
            )
            store.set_last_opened_project(first_project)
            store.set_project_target_branch(first_project, "james")
            store.set_project_target_branch(second_project, "develop")
            store.set_project_target_branch(first_project, "feature")

            self.assertEqual(store.get_project_target_branch(first_project), "feature")
            self.assertEqual(store.get_project_target_branch(second_project), "develop")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload[0]["tasks"]["task-one"]["prompt"], "Make the change")
            self.assertEqual(
                payload[1],
                {"last_opened_project": str(first_project.resolve())},
            )
            self.assertEqual(
                payload[2],
                {
                    "project_target_branches": {
                        str(first_project.resolve()): "feature",
                        str(second_project.resolve()): "develop",
                    }
                },
            )

    def test_clear_project_target_branch_removes_only_that_project(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            store = TaskMemoryStore(path)
            first_project = Path(directory) / "first"
            second_project = Path(directory) / "second"

            store.set_project_target_branch(first_project, "james")
            store.set_project_target_branch(second_project, "develop")
            store.clear_project_target_branch(first_project)

            self.assertIsNone(store.get_project_target_branch(first_project))
            self.assertEqual(store.get_project_target_branch(second_project), "develop")
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                [
                    {
                        "project_target_branches": {
                            str(second_project.resolve()): "develop",
                        }
                    }
                ],
            )

    def test_clear_last_project_target_branch_omits_empty_map(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            store = TaskMemoryStore(path)
            project = Path(directory) / "project"

            store.set_last_opened_project(project)
            store.set_project_target_branch(project, "james")
            store.clear_project_target_branch(project)

            self.assertIsNone(store.get_project_target_branch(project))
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                [{"last_opened_project": str(project.resolve())}],
            )

    def test_tracks_project_topics_without_replacing_other_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            store = TaskMemoryStore(path)
            first_project = Path(directory) / "first"
            second_project = Path(directory) / "second"

            store.record_task(
                "task-one",
                "Make the change",
                "codex",
                "luna",
                "medium",
                "coding",
                "completed",
                submitted_at=0,
            )
            store.set_last_opened_project(first_project)
            store.set_project_topic(first_project, "mvp")
            store.set_project_topic(second_project, "release")
            store.set_project_topic(first_project, "trading")

            self.assertEqual(store.get_project_topic(first_project), "trading")
            self.assertEqual(store.get_project_topic(second_project), "release")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload[0]["tasks"]["task-one"]["prompt"], "Make the change")
            self.assertEqual(
                payload[2],
                {
                    "project_topics": {
                        str(first_project.resolve()): "trading",
                        str(second_project.resolve()): "release",
                    }
                },
            )

    def test_clear_project_topic_removes_only_that_project(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            store = TaskMemoryStore(path)
            first_project = Path(directory) / "first"
            second_project = Path(directory) / "second"

            store.set_project_topic(first_project, "mvp")
            store.set_project_topic(second_project, "release")
            store.clear_project_topic(first_project)

            self.assertIsNone(store.get_project_topic(first_project))
            self.assertEqual(store.get_project_topic(second_project), "release")
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                [{"project_topics": {str(second_project.resolve()): "release"}}],
            )

    def test_records_optional_topic_and_omits_when_untagged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            store = TaskMemoryStore(path)
            project = Path(directory) / "project"

            store.record_task(
                "task-tagged",
                "Work on MVP",
                "codex",
                "gpt-5.6-luna",
                "medium",
                "coding",
                "queued",
                submitted_at=0,
                project=project,
                topic="mvp",
            )
            store.record_task(
                "task-plain",
                "Unrelated fix",
                "codex",
                "gpt-5.6-luna",
                "medium",
                "coding",
                "queued",
                submitted_at=1,
                project=project,
            )

            tasks = store.get_tasks()
            self.assertEqual(tasks["task-tagged"]["topic"], "mvp")
            self.assertNotIn("topic", tasks["task-plain"])


if __name__ == "__main__":
    unittest.main()
