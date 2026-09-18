import json
import tempfile
import unittest
from pathlib import Path

from tui.config import OrchestrateSettings
from tui.local_storage import LocalStorage
from tui.memory import TaskMemoryStore
from tui.orchestrate_protocol import PlannerTask, WorkerReport, parse_planner_payload
from tui.orchestrate_session import (
    RESTART_MESSAGE,
    OrchestrationSession,
    SessionStore,
    TaskCard,
    cards_from_payload,
    new_session_id,
    render_digest,
)


PAYLOAD = """BEGIN_DAEDALUS_ORCHESTRATION
{
  "summary": "Split parsing from rendering.",
  "tasks": [
    {"id": "t1", "title": "Add parser", "goal": "Parse the thing.",
     "checklist": ["parser exists", "tests pass"], "file_scope": ["tui/parse.py"],
     "read_first": ["tui/plan.py:1-40"], "interfaces": "parse(text) -> Result",
     "verify": "pytest tests/test_parse.py", "depends_on": []},
    {"id": "t2", "title": "Add renderer", "goal": "Render the thing.",
     "checklist": ["renderer exists"], "file_scope": ["tui/render.py"],
     "depends_on": ["t1"]}
  ],
  "done": false
}
END_DAEDALUS_ORCHESTRATION"""


def make_session(**overrides) -> OrchestrationSession:
    payload = parse_planner_payload(PAYLOAD)
    session = OrchestrationSession(
        session_id="orc-001-abcdef12",
        project_key="project-1234abcd",
        prompt="Build the thing.",
        planner_selection=("claude", "claude-fable-5-1", "high"),
        worker_selection=("claude", "claude-opus-5", "high"),
        max_workers=2,
        round=1,
        summary=payload.summary,
    )
    for card in cards_from_payload(payload):
        session.cards[card.card_id] = card
    for name, value in overrides.items():
        setattr(session, name, value)
    return session


class SessionShapeTests(unittest.TestCase):
    def test_session_ids_follow_the_documented_shape(self):
        session_id = new_session_id(7)
        self.assertRegex(session_id, r"^orc-007-[0-9a-f]{8}$")

    def test_ticks_are_padded_to_the_checklist_length(self):
        card = TaskCard(PlannerTask("t1", "T", "G", ("a", "b", "c"), ("f",)), checklist_state=(True,))
        self.assertEqual(card.ticks, (True, False, False))
        self.assertEqual(card.ticks_text, "1/3")

    def test_restart_marks_active_sessions_stopped_with_a_message(self):
        session = make_session(status="waiting")
        session.cards["t1"].status = "running"
        self.assertTrue(session.mark_stopped_by_restart())
        self.assertEqual(session.status, "stopped")
        self.assertEqual(session.error, RESTART_MESSAGE)
        self.assertEqual(session.cards["t1"].status, "stopped")
        self.assertEqual(session.cards["t2"].status, "stopped")
        finished = make_session(status="completed")
        self.assertFalse(finished.mark_stopped_by_restart())
        self.assertEqual(finished.status, "completed")


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name).resolve()
        self.storage = LocalStorage(self.root)
        self.settings = OrchestrateSettings()
        self.store = SessionStore(self.storage, self.settings)

    def tearDown(self):
        self._directory.cleanup()

    def test_session_files_land_under_the_prompts_root(self):
        session = make_session()
        plan_path = self.store.write_plan(session, raw_payload=PAYLOAD)
        card_path = self.store.write_card(session, session.cards["t1"])
        report_path = self.store.write_report(session, session.cards["t1"], "first report")
        second_report = self.store.write_report(session, session.cards["t1"], "second report")
        expected = self.root / "prompts" / "project-1234abcd" / "orchestrate" / "orc-001-abcdef12"
        self.assertEqual(self.store.session_dir("project-1234abcd", "orc-001-abcdef12"), expected)
        self.assertEqual(plan_path, expected / "PLAN.md")
        self.assertEqual(card_path, expected / "cards" / "t1.md")
        self.assertEqual(report_path, expected / "reports" / "t1-1.md")
        self.assertEqual(second_report, expected / "reports" / "t1-2.md")
        self.assertTrue((expected / "plan-round-1.json").is_file())
        plan = plan_path.read_text(encoding="utf-8")
        self.assertIn("Split parsing from rendering.", plan)
        self.assertIn("| t2 | Add renderer | pending | 0/1 | t1 | — |", plan)

    def test_card_round_trips_through_a_worktree_including_ticks(self):
        session = make_session()
        worktree = self.root / "worktree"
        worktree.mkdir()
        path = self.store.place_card_in_worktree(session.cards["t1"], worktree)
        self.assertEqual(path, worktree / ".daedalus-orchestration" / "task.md")
        text = path.read_text(encoding="utf-8")
        self.assertIn("# t1 — Add parser", text)
        self.assertIn("- [ ] parser exists", text)
        self.assertIn("pytest tests/test_parse.py", text)
        self.assertEqual(self.store.read_card_from_worktree(worktree), (False, False))
        path.write_text(text.replace("- [ ] parser exists", "- [x] parser exists"), encoding="utf-8")
        self.assertEqual(self.store.read_card_from_worktree(worktree), (True, False))
        self.assertIsNone(self.store.read_card_from_worktree(self.root / "missing"))

    def test_digest_follows_the_protocol_and_is_bounded(self):
        session = make_session(round=2)
        t1 = session.cards["t1"]
        t1.status = "promoted"
        t1.checklist_state = (True, True)
        t1.report = WorkerReport("t1", "done", (True, True), ("tui/parse.py", "tests/test_parse.py"))
        t2 = session.cards["t2"]
        t2.status = "failed"
        t2.error = "Verification failed after 3 attempts.\n\nboom"
        t2.report = WorkerReport("t2", "partial", (False,), (), "renderer needs the parser API", "x" * 500)
        digest = render_digest(session, 6, 90)
        lines = digest.splitlines()
        self.assertEqual(lines[0], "SESSION orc-001-abcdef12  round 2 of 6  workers 0/2 busy")
        self.assertTrue(lines[1].startswith("t1  promoted   2/2 checklist  files: tui/parse.py, tests/test_parse.py"))
        self.assertTrue(lines[2].startswith("t2  failed     0/1 checklist  error: Verification failed after 3 attempts. boom"))
        self.assertTrue(lines[3].startswith("    report: status=partial | errors: renderer needs the parser API"))
        self.assertIn("truncated", lines[3])
        self.assertLessEqual(len(lines[3]), len("    report: ") + 90)

        small = SessionStore(self.storage, OrchestrateSettings(planner_digest_budget_chars=80))
        bounded = small.write_digest(session)
        self.assertLessEqual(len(bounded), 80)
        self.assertTrue((self.store.session_dir(session.project_key, session.session_id) / "digest-round-2.txt").is_file())

    def test_waiting_cards_name_their_dependencies(self):
        session = make_session()
        session.cards["t2"].status = "waiting"
        digest = render_digest(session, 6, 100)
        self.assertIn("t2  waiting    depends_on t1", digest)
        self.assertIn("t1  pending    ready", digest)


class SessionMemoryTests(unittest.TestCase):
    def test_sessions_round_trip_through_memory_with_a_schema_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".daedalus-memory.json"
            memory = TaskMemoryStore(path)
            memory.record_task("task-1", "prompt", "codex", "luna", "high", "coding", "completed", submitted_at=0)
            session = make_session(status="waiting", tokens_planner=12, tokens_workers=30)
            session.cards["t1"].status = "promoted"
            session.cards["t1"].worker_task_id = "003-abcd1234"
            session.cards["t1"].checklist_state = (True, True)
            session.cards["t1"].report = WorkerReport("t1", "done", (True, True), ("tui/parse.py",), "", "note")
            session.cards["t1"].prompt_chars = 1200
            session.log.append("planner round 1")
            memory.record_orchestration(session.to_dict())

            snapshots = memory.get_orchestrations()
            self.assertEqual(list(snapshots), ["orc-001-abcdef12"])
            self.assertEqual(snapshots["orc-001-abcdef12"]["schema_version"], 1)
            restored = OrchestrationSession.from_dict(snapshots["orc-001-abcdef12"])
            self.assertIsNotNone(restored)
            self.assertEqual(restored.status, "waiting")
            self.assertEqual(restored.planner_selection, ("claude", "claude-fable-5-1", "high"))
            self.assertEqual(restored.tokens_planner, 12)
            self.assertEqual(restored.tokens_workers, 30)
            self.assertEqual(restored.log, ["planner round 1"])
            card = restored.cards["t1"]
            self.assertEqual(card.status, "promoted")
            self.assertEqual(card.worker_task_id, "003-abcd1234")
            self.assertEqual(card.ticks, (True, True))
            self.assertEqual(card.report.files_changed, ("tui/parse.py",))
            self.assertEqual(card.prompt_chars, 1200)
            self.assertEqual(restored.cards["t2"].task.depends_on, ("t1",))
            self.assertIn("task-1", memory.get_tasks())

            self.assertTrue(memory.delete_orchestration("orc-001-abcdef12"))
            self.assertFalse(memory.delete_orchestration("orc-001-abcdef12"))
            self.assertEqual(memory.get_orchestrations(), {})
            self.assertIn("task-1", memory.get_tasks())
            entries = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(any("orchestrations" in entry for entry in entries))

    def test_worker_tasks_persist_their_session_and_card(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = TaskMemoryStore(Path(directory) / ".daedalus-memory.json")
            memory.record_task(
                "task-1", "card", "claude", "claude-opus-5", "high", "coding", "running",
                submitted_at=0, session_id="orc-001-abcdef12", card_id="t1",
            )
            memory.record_task("task-2", "plain", "claude", "claude-opus-5", "high", "coding", "running", submitted_at=0)
            tasks = memory.get_tasks()
            self.assertEqual((tasks["task-1"]["session_id"], tasks["task-1"]["card_id"]), ("orc-001-abcdef12", "t1"))
            self.assertNotIn("session_id", tasks["task-2"])


if __name__ == "__main__":
    unittest.main()
