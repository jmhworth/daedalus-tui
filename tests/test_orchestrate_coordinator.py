import json
import re
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from tui.agent_runner import AgentLogEvent, AgentResult
from tui.config import OrchestrateSettings
from tui.firebase import FirebaseStatus
from tui.git_worktree import WorktreeContext
from tui.local_storage import LocalStorage
from tui.memory import TaskMemoryStore
from tui.orchestrate_coordinator import ORCHESTRATE_PHASE, OrchestrateCoordinator, SessionEventRecord
from tui.orchestrator import OrchestrationSettings
from tui.task_coordinator import TaskCoordinator
from tui.verification import VerificationResult


OPERATOR_PROMPT = "OPERATOR_PROMPT_SENTINEL: build the whole feature end to end."
PLANNER = ("claude", "claude-fable-5-1", "high")
WORKER = ("claude", "claude-opus-5", "high")


def planner_payload(summary, tasks, done=False):
    return (
        "BEGIN_DAEDALUS_ORCHESTRATION\n"
        + json.dumps({"summary": summary, "tasks": tasks, "done": done})
        + "\nEND_DAEDALUS_ORCHESTRATION"
    )


def card(task_id, scope, depends_on=(), reissues=None):
    value = {
        "id": task_id,
        "title": f"Do {task_id}",
        "goal": f"Complete {task_id}.",
        "checklist": [f"{task_id} first item", f"{task_id} second item"],
        "file_scope": [scope],
        "read_first": [],
        "interfaces": "",
        "verify": "true",
        "depends_on": list(depends_on),
    }
    if reissues:
        value["reissues"] = reissues
    return value


def worker_report(task_id, status="done", errors=""):
    return (
        f"Worked on {task_id}.\n\nBEGIN_DAEDALUS_WORKER_REPORT\n"
        + json.dumps(
            {
                "task": task_id,
                "status": status,
                "checklist": [True, status == "done"],
                "files_changed": [f"src/{task_id}.py"],
                "errors": errors,
                "notes": f"{task_id} notes",
            }
        )
        + "\nEND_DAEDALUS_WORKER_REPORT"
    )


CARD_ID = re.compile(r"^# (t\d+) —", re.MULTILINE)


class ScriptedRunner:
    """Answers planner turns from a script and worker turns from their card."""

    def __init__(self, planner_responses, failing_cards=()):
        self.planner_responses = list(planner_responses)
        self.failing_cards = set(failing_cards)
        self.lock = threading.Lock()
        self.planner_prompts = []
        self.worker_prompts = []
        self.worker_order = []
        self.active_workers = 0
        self.max_active_workers = 0

    def run(self, request, on_event=None):
        prompt = request.prompt
        if "TASK_MODE: orchestrate-plan" in prompt:
            with self.lock:
                self.planner_prompts.append(prompt)
                index = len(self.planner_prompts) - 1
            if on_event is not None:
                on_event(AgentLogEvent("message", "Reading the repository map."))
            response = self.planner_responses[min(index, len(self.planner_responses) - 1)]
            return AgentResult(request.provider, 0, response, tokens_consumed=10, output_streamed=True)
        if "TASK_MODE: integrating" in prompt:
            return AgentResult("claude", 0, "resolved", tokens_consumed=1)
        match = CARD_ID.search(prompt)
        card_id = match.group(1) if match else "?"
        with self.lock:
            self.worker_prompts.append(prompt)
            self.worker_order.append(card_id)
            self.active_workers += 1
            self.max_active_workers = max(self.max_active_workers, self.active_workers)
        time.sleep(0.05)
        card_path = request.directory / ".daedalus-orchestration" / "task.md"
        if card_path.is_file():
            text = card_path.read_text(encoding="utf-8")
            card_path.write_text(text.replace(f"- [ ] {card_id} first item", f"- [x] {card_id} first item"), encoding="utf-8")
        with self.lock:
            self.active_workers -= 1
        if card_id in self.failing_cards:
            return AgentResult("claude", 1, "", error=f"{card_id} crashed")
        return AgentResult("claude", 0, worker_report(card_id), tokens_consumed=5)


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name).resolve()
        self.repository = self.root / "repo"
        self.repository.mkdir()
        self.worktrees = self.root / "worktrees"
        self.worktrees.mkdir()
        self.memory = TaskMemoryStore(self.root / ".daedalus-memory.json")
        self.storage = LocalStorage(self.root / "storage")
        self.events = []

    def tearDown(self):
        self._directory.cleanup()

    def manager(self):
        manager = Mock()

        def create(task_id):
            path = self.worktrees / f"task-{task_id}"
            path.mkdir(parents=True, exist_ok=True)
            return WorktreeContext(self.repository, task_id, "base", f"agent/task-{task_id}", path)

        manager.create.side_effect = create
        manager.head.return_value = "changed"
        manager.has_unmerged_paths.return_value = False
        manager.capture_primary.return_value = "tip"
        return manager

    def build(self, runner, orchestrate=None, orchestration=None):
        orchestration = orchestration or OrchestrationSettings(
            max_concurrent_tasks=4, verification_commands=(("true",),)
        )
        tasks = TaskCoordinator(self.repository, runner, orchestration, memory_path=self.memory.path)
        coordinator = OrchestrateCoordinator(
            tasks,
            runner,
            orchestration,
            orchestrate or OrchestrateSettings(),
            self.storage,
            self.memory,
            lambda record, phase, message, kind: self.events.append((record, phase, message, kind)),
        )
        return tasks, coordinator

    def wait_for(self, session, timeout=15.0):
        deadline = time.time() + timeout
        while session.active and time.time() < deadline:
            time.sleep(0.02)
        return session

    def patches(self, manager, verification=None):
        return (
            patch("tui.orchestrator.GitWorktreeManager", return_value=manager),
            patch("tui.orchestrate_coordinator.GitWorktreeManager", return_value=manager),
            patch("tui.orchestrator.run_verification", side_effect=verification or (lambda *a, **k: VerificationResult(True, ""))),
            patch("tui.orchestrator.migrations_pending", return_value=False),
            patch("tui.orchestrator.load_firebase_status", return_value=FirebaseStatus(False, None)),
        )

    def test_scripted_session_reissues_a_failed_card_and_completes(self):
        runner = ScriptedRunner(
            [
                planner_payload(
                    "Three cards.",
                    [card("t1", "src/t1.py"), card("t2", "src/t2.py"), card("t3", "src/t3.py", depends_on=("t2",))],
                ),
                planner_payload("Re-issue t2 as t4 with a narrower card.", [card("t4", "src/t2.py", reissues="t2")]),
                planner_payload("All cards promoted.", [], done=True),
            ],
            failing_cards={"t2"},
        )
        manager = self.manager()
        tasks, coordinator = self.build(runner)
        patches = self.patches(manager)
        for item in patches:
            item.start()
        try:
            session = coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=2)
            self.wait_for(session)
        finally:
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()

        self.assertEqual(session.status, "completed", session.error)
        self.assertEqual(session.round, 3)
        statuses = {card_id: item.status for card_id, item in session.cards.items()}
        self.assertEqual(statuses, {"t1": "promoted", "t2": "reissued", "t3": "promoted", "t4": "promoted"})
        self.assertEqual(session.cards["t2"].reissued_by, "t4")
        self.assertEqual(session.cards["t2"].reissue_count, 1)
        # Dispatch order: the first wave is t1 and t2; t3 waited for t2's replacement.
        self.assertEqual(set(runner.worker_order[:2]), {"t1", "t2"})
        self.assertEqual(runner.worker_order[2:], ["t4", "t3"])
        self.assertLessEqual(runner.max_active_workers, 2)
        # Every worker was an ordinary coding task with the planner as its resolver.
        records = tasks.tasks()
        self.assertEqual(len(records), 4)
        self.assertTrue(all(record.is_worker for record in records))
        self.assertTrue(all(record.session_id == session.session_id for record in records))
        self.assertTrue(all(record.resolver_selection == PLANNER for record in records))
        self.assertTrue(all(record.model == "claude-opus-5" for record in records))
        # Context minimization: no worker ever saw the operator's prompt.
        self.assertEqual(len(runner.worker_prompts), 4)
        self.assertTrue(all(OPERATOR_PROMPT not in prompt for prompt in runner.worker_prompts))
        self.assertTrue(all("BEGIN_DAEDALUS_TASK_CARD" in prompt for prompt in runner.worker_prompts))
        self.assertTrue(all(item.prompt_chars > 0 for item in session.cards.values()))
        # Planner rounds saw the operator prompt and, later, the digest with t2's failure.
        self.assertEqual(len(runner.planner_prompts), 3)
        self.assertIn(OPERATOR_PROMPT, runner.planner_prompts[0])
        self.assertIn("t2  failed", runner.planner_prompts[1])
        self.assertIn("t2 crashed", runner.planner_prompts[1])
        self.assertIn("t1  promoted   1/2 checklist", runner.planner_prompts[1])
        # Ticks came from the card file (the worker ticked the first item; the
        # report claimed both), reconciled with the card file winning.
        self.assertEqual(session.cards["t1"].ticks, (True, False))
        self.assertEqual(session.cards["t1"].report.files_changed, ("src/t1.py",))
        self.assertEqual(session.tokens_planner, 30)
        self.assertEqual(session.tokens_workers, 15)
        self.assertEqual(session.cards["t1"].promoted_commit, "tip")
        # Session files and memory.
        session_dir = coordinator.store.session_dir(coordinator.project_key, session.session_id)
        self.assertTrue((session_dir / "PLAN.md").is_file())
        self.assertTrue((session_dir / "plan-round-1.json").is_file())
        self.assertTrue((session_dir / "digest-round-2.txt").is_file())
        self.assertTrue((session_dir / "cards" / "t4.md").is_file())
        self.assertTrue((session_dir / "reports" / "t1-1.md").is_file())
        snapshot = self.memory.get_orchestrations()[session.session_id]
        self.assertEqual(snapshot["status"], "completed")
        self.assertEqual(snapshot["schema_version"], 1)
        # Session events rode the task-event callback under the orchestrate phase.
        phases = {phase for _, phase, _, _ in self.events}
        self.assertIn(ORCHESTRATE_PHASE, phases)
        session_events = [record for record, phase, _, _ in self.events if phase == ORCHESTRATE_PHASE]
        self.assertTrue(all(isinstance(record, SessionEventRecord) for record in session_events))
        self.assertEqual(session_events[-1].status, "completed")

    def test_card_file_ticks_win_over_the_report(self):
        """The worker ticked only the first item; its report claims both (t1 partial)."""
        runner = ScriptedRunner(
            [planner_payload("One card.", [card("t1", "src/t1.py")]), planner_payload("Done.", [], done=True)]
        )
        original_run = runner.run

        def run(request, on_event=None):
            result = original_run(request, on_event)
            if "TASK_MODE: coding" in request.prompt:
                return AgentResult("claude", 0, worker_report("t1", "partial", "second item blocked"), tokens_consumed=5)
            return result

        runner.run = run
        manager = self.manager()
        tasks, coordinator = self.build(runner)
        patches = self.patches(manager)
        for item in patches:
            item.start()
        try:
            session = coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=1)
            self.wait_for(session)
        finally:
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()
        self.assertEqual(session.status, "completed", session.error)
        self.assertEqual(session.cards["t1"].ticks, (True, False))
        self.assertEqual(session.cards["t1"].report.status, "partial")

    def test_invalid_payload_gets_one_corrective_round_then_fails(self):
        runner = ScriptedRunner(["no payload here", "still no payload"])
        manager = self.manager()
        tasks, coordinator = self.build(runner)
        patches = self.patches(manager)
        for item in patches:
            item.start()
        try:
            session = coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=2)
            self.wait_for(session)
        finally:
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()
        self.assertEqual(session.status, "failed")
        self.assertIn("did not return a valid plan", session.error)
        self.assertEqual(len(runner.planner_prompts), 2)
        self.assertIn("Your previous reply was rejected", runner.planner_prompts[1])
        self.assertEqual(tasks.tasks(), ())

    def test_planner_decides_how_many_rounds_the_session_takes(self):
        """With no cap the session runs as many rounds as the planner needs, then stops on done."""
        responses = [planner_payload(f"Round {index}.", [card(f"t{index}", f"src/t{index}.py")]) for index in range(1, 9)]
        responses.append(planner_payload("Everything promoted.", [], done=True))
        runner = ScriptedRunner(responses)
        manager = self.manager()
        tasks, coordinator = self.build(runner)
        # The temporary repository is not a Git checkout, so stand in for `git ls-files`.
        patches = (
            *self.patches(manager),
            patch.object(OrchestrateCoordinator, "_repository_map", return_value="tui/app.py\ntests/test_app.py"),
        )
        for item in patches:
            item.start()
        try:
            session = coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=2)
            self.wait_for(session, timeout=30.0)
        finally:
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()
        self.assertEqual(session.status, "completed", session.error)
        self.assertEqual(session.round, 9)
        self.assertEqual(len(runner.planner_prompts), 9)
        self.assertIn("Planner round 1.", session.log)
        self.assertIn("Planner round 9.", session.log)
        self.assertFalse(any(" of " in line and line.startswith("Planner round") for line in session.log))
        # Later rounds are told the choice is theirs rather than counted against a cap.
        self.assertIn("Planner round 2.", runner.planner_prompts[1])
        self.assertNotIn("capped at", runner.planner_prompts[1])
        # The first round carries the repository map; later rounds do not repeat it.
        self.assertIn("BEGIN_DAEDALUS_REPOSITORY_MAP", runner.planner_prompts[0])
        self.assertIn("tui/app.py\ntests/test_app.py", runner.planner_prompts[0])
        self.assertNotIn("BEGIN_DAEDALUS_REPOSITORY_MAP", runner.planner_prompts[1])
        # Streamed planner messages reach the session log while the round runs.
        self.assertTrue(any(line.startswith("planner [") and "Reading the repository map." in line for line in session.log))
        self.assertTrue(any(line.startswith("Planner round 1 finished in") for line in session.log))

    def test_non_claude_roles_reach_the_runner_unchanged(self):
        """A Cursor planner and a Codex worker are launched with their own selections."""
        requests = []

        class RecordingRunner(ScriptedRunner):
            def run(self, request, on_event=None):
                requests.append((request.provider, request.model, request.reasoning, "orchestrate-plan" in request.prompt))
                return super().run(request, on_event)

        runner = RecordingRunner(
            [planner_payload("One card.", [card("t1", "src/t1.py")]), planner_payload("Done.", [], done=True)]
        )
        manager = self.manager()
        tasks, coordinator = self.build(runner)
        patches = self.patches(manager)
        for item in patches:
            item.start()
        try:
            session = coordinator.start(
                OPERATOR_PROMPT, ("cursor", "cursor", ""), ("codex", "gpt-6-astra", "medium"), max_workers=1
            )
            self.wait_for(session)
        finally:
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()
        self.assertEqual(session.status, "completed", session.error)
        self.assertIn(("cursor", "cursor", "", True), requests)
        self.assertIn(("codex", "gpt-6-astra", "medium", False), requests)

    def test_round_limit_ends_the_session_with_the_digest(self):
        """An optional round cap still stops a planner that keeps adding cards."""
        responses = [planner_payload(f"Round {index}.", [card(f"t{index}", f"src/t{index}.py")]) for index in range(1, 10)]
        runner = ScriptedRunner(responses)
        manager = self.manager()
        tasks, coordinator = self.build(runner, orchestrate=OrchestrateSettings(planner_round_limit=2))
        patches = self.patches(manager)
        for item in patches:
            item.start()
        try:
            session = coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=2)
            self.wait_for(session)
        finally:
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()
        self.assertEqual(session.status, "failed")
        self.assertIn("round limit (2)", session.error)
        self.assertIn("SESSION", session.error)
        self.assertEqual(session.round, 2)
        self.assertEqual(len(runner.planner_prompts), 2)

    def test_reissue_limit_refuses_a_third_card(self):
        runner = ScriptedRunner(
            [
                planner_payload("One card.", [card("t1", "src/t1.py")]),
                planner_payload("Retry.", [card("t2", "src/t1.py", reissues="t1")]),
                planner_payload("Retry again.", [card("t3", "src/t1.py", reissues="t1")]),
            ],
            failing_cards={"t1", "t2", "t3"},
        )
        manager = self.manager()
        tasks, coordinator = self.build(runner, orchestrate=OrchestrateSettings(task_reissue_limit=1))
        patches = self.patches(manager)
        for item in patches:
            item.start()
        try:
            session = coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=1)
            self.wait_for(session)
        finally:
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()
        self.assertEqual(session.status, "failed")
        self.assertEqual(set(session.cards), {"t1", "t2"})
        self.assertEqual(session.cards["t1"].reissue_count, 1)
        self.assertTrue(any("Refused t3" in line for line in session.log))

    def test_worker_cap_is_bound_by_max_concurrent_tasks(self):
        runner = ScriptedRunner(
            [
                planner_payload("Three independent cards.", [card(f"t{index}", f"src/t{index}.py") for index in (1, 2, 3)]),
                planner_payload("Done.", [], done=True),
            ]
        )
        manager = self.manager()
        tasks, coordinator = self.build(
            runner,
            orchestration=OrchestrationSettings(max_concurrent_tasks=1, verification_commands=(("true",),)),
        )
        patches = self.patches(manager)
        for item in patches:
            item.start()
        try:
            session = coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=3)
            self.wait_for(session)
        finally:
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()
        self.assertEqual(session.status, "completed", session.error)
        self.assertEqual(runner.max_active_workers, 1)
        self.assertTrue(any("max_concurrent_tasks=1" in line for line in session.log))

    def test_stop_interrupts_workers_and_marks_the_session_stopped(self):
        release = threading.Event()

        class BlockingRunner(ScriptedRunner):
            def run(self, request, on_event=None):
                if "TASK_MODE: coding" in request.prompt:
                    with self.lock:
                        self.worker_prompts.append(request.prompt)
                    while not release.is_set():
                        if request.control is not None and request.control.stop_reason:
                            return AgentResult("claude", None, "", stopped_reason=request.control.stop_reason)
                        time.sleep(0.01)
                    return AgentResult("claude", 0, worker_report("t1"))
                return super().run(request, on_event)

        runner = BlockingRunner([planner_payload("One card.", [card("t1", "src/t1.py")])])
        manager = self.manager()
        tasks, coordinator = self.build(runner)
        patches = self.patches(manager)
        for item in patches:
            item.start()
        try:
            session = coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=1)
            deadline = time.time() + 5
            while not runner.worker_prompts and time.time() < deadline:
                time.sleep(0.01)
            self.assertTrue(coordinator.stop(session.session_id))
            self.wait_for(session)
            worker = tasks.get(session.cards["t1"].worker_task_id)
            deadline = time.time() + 5
            while worker.status not in {"interrupted", "failed"} and time.time() < deadline:
                time.sleep(0.01)
        finally:
            release.set()
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()
        self.assertEqual(session.status, "stopped")
        self.assertEqual(session.cards["t1"].status, "stopped")
        self.assertEqual(worker.status, "interrupted")
        self.assertFalse(coordinator.stop(session.session_id))

    def test_context_file_is_committed_and_pushed_after_each_round_and_at_the_end(self):
        runner = ScriptedRunner(
            [
                planner_payload("One card.", [card("t1", "src/t1.py")]),
                planner_payload("All promoted.", [], done=True),
            ]
        )
        manager = self.manager()
        manager.commit_primary_file.return_value = True
        tasks, coordinator = self.build(
            runner, orchestration=OrchestrationSettings(max_concurrent_tasks=4, verification_commands=(("true",),), promotion_push_enabled=True)
        )
        patches = self.patches(manager)
        for item in patches:
            item.start()
        try:
            session = coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=2)
            self.wait_for(session)
        finally:
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()

        self.assertEqual(session.status, "completed", session.error)
        writes = [item.args for item in manager.commit_primary_file.call_args_list]
        self.assertEqual([path for path, _, _ in writes], ["DAEDALUS_CONTEXT.md", "DAEDALUS_CONTEXT.md"])
        self.assertEqual(
            [message for _, _, message in writes],
            [
                f"Daedalus: update orchestration context ({session.session_id} round 1)",
                f"Daedalus: update orchestration context ({session.session_id} session completed)",
            ],
        )
        first, last = (content for _, content, _ in writes)
        self.assertIn(OPERATOR_PROMPT, first)
        self.assertIn("#### t1 — Do t1", first)
        self.assertIn("| t1 | Do t1 | pending |", first)
        self.assertIn("| t1 | Do t1 | promoted |", last)
        self.assertIn("Status: completed", last)
        # Pushed immediately after each write, with the promotion push setting.
        self.assertEqual(manager.push_primary.call_args_list[-2:], [call(enabled=True), call(enabled=True)])
        self.assertIn("Wrote DAEDALUS_CONTEXT.md to main (round 1).", session.log)
        self.assertIn("Wrote DAEDALUS_CONTEXT.md to main (session completed).", session.log)
        # The round-1 write happened before any worker was dispatched.
        wrote = next(index for index, line in enumerate(session.log) if line.startswith("Wrote DAEDALUS_CONTEXT.md"))
        dispatched = next(index for index, line in enumerate(session.log) if line.startswith("Dispatched t1"))
        self.assertLess(wrote, dispatched)

    def test_context_file_failure_is_logged_and_never_fails_the_session(self):
        runner = ScriptedRunner(
            [planner_payload("One card.", [card("t1", "src/t1.py")]), planner_payload("Done.", [], done=True)]
        )
        manager = self.manager()
        manager.commit_primary_file.side_effect = RuntimeError("disk full")
        tasks, coordinator = self.build(
            runner, orchestration=OrchestrationSettings(max_concurrent_tasks=4, verification_commands=(("true",),), promotion_push_enabled=False)
        )
        patches = self.patches(manager)
        for item in patches:
            item.start()
        try:
            session = coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=1)
            self.wait_for(session)
        finally:
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()

        self.assertEqual(session.status, "completed", session.error)
        self.assertTrue(any(line.startswith("Could not publish DAEDALUS_CONTEXT.md: disk full") for line in session.log))
        self.assertFalse(any(line.startswith("Wrote DAEDALUS_CONTEXT.md") for line in session.log))
        manager.push_primary.assert_not_called()

    def test_context_file_can_be_disabled_with_an_empty_name(self):
        runner = ScriptedRunner([planner_payload("Done already.", [], done=True)])
        manager = self.manager()
        tasks, coordinator = self.build(runner, orchestrate=OrchestrateSettings(context_filename=""))
        patches = self.patches(manager)
        for item in patches:
            item.start()
        try:
            session = coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=1)
            self.wait_for(session)
        finally:
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()

        manager.commit_primary_file.assert_not_called()
        self.assertNotIn("BEGIN_DAEDALUS_PROJECT_CONTEXT", runner.planner_prompts[0])

    def test_a_later_session_planner_receives_the_earlier_sessions_context(self):
        """The orc-005 failure: a new planner saw a bare repository and asked for the old cards."""
        runner = ScriptedRunner(
            [
                planner_payload("First session card.", [card("t1", "src/t1.py")]),
                planner_payload("First session done.", [], done=True),
                planner_payload("Second session card.", [card("t2", "src/t2.py")]),
                planner_payload("Second session done.", [], done=True),
            ]
        )
        manager = self.manager()
        tasks, coordinator = self.build(runner)
        patches = self.patches(manager)
        for item in patches:
            item.start()
        try:
            first = self.wait_for(coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=1))
            second = self.wait_for(coordinator.start("Continue the earlier plan.", PLANNER, WORKER, max_workers=1))
        finally:
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()

        self.assertEqual((first.status, second.status), ("completed", "completed"), (first.error, second.error))
        self.assertNotIn("BEGIN_DAEDALUS_PROJECT_CONTEXT", runner.planner_prompts[0])
        prompt = runner.planner_prompts[2]
        self.assertIn("BEGIN_DAEDALUS_PROJECT_CONTEXT", prompt)
        self.assertIn(f"## Session {first.session_id}", prompt)
        self.assertIn(OPERATOR_PROMPT, prompt)
        self.assertIn("| t1 | Do t1 | promoted |", prompt)
        self.assertIn("`DAEDALUS_CONTEXT.md`", prompt)
        self.assertNotIn(f"## Session {second.session_id}", prompt)
        # The context file itself records both sessions, oldest first.
        content = manager.commit_primary_file.call_args.args[1]
        self.assertLess(content.index(f"## Session {first.session_id}"), content.index(f"## Session {second.session_id}"))

    def test_planner_context_drops_the_oldest_sessions_whole_to_fit_the_budget(self):
        runner = ScriptedRunner([planner_payload("Done.", [], done=True)])
        tasks, coordinator = self.build(runner, orchestrate=OrchestrateSettings(planner_context_chars=1_600))
        try:
            for index in range(1, 4):
                session = coordinator.start(f"Session {index} prompt.", PLANNER, WORKER, max_workers=1)
                session.summary = f"Summary {index}. " + "x" * 600
                session.status = "completed"
                session.started_at = float(index)
            current = coordinator.start("Current.", PLANNER, WORKER, max_workers=1)
            self.wait_for(current)
            context = coordinator._project_context(current)
        finally:
            coordinator.shutdown()
            tasks.shutdown()

        self.assertLessEqual(len(context), 1_600)
        self.assertNotIn("Session 1 prompt.", context)
        self.assertIn("Session 3 prompt.", context)
        self.assertNotIn("Current.", context)

    def test_planner_tool_reference_pattern_targets_tool_usage_not_nouns(self):
        from tui.orchestrate_coordinator import PLANNER_TOOL_REFERENCE

        for text in (
            "Use the Sites building skill and its environment reference to propose a stack.",
            "Skill(sites) returns the supported environments.",
            "Apply the deployment plugin before writing the doc.",
            "Consult the hosting plugin docs.",
        ):
            self.assertTrue(PLANNER_TOOL_REFERENCE.search(text), text)
        for text in (
            "Add a skills section to the profile page.",
            "List the plugins directory contents.",
            "Document the required skill level of operators.",
        ):
            self.assertFalse(PLANNER_TOOL_REFERENCE.search(text), text)

    def test_card_that_needs_a_planner_skill_is_sent_back_for_correction(self):
        """The orc-007 failure: a Codex planner told a Claude worker to use the Sites skill."""
        bad = card("p1", "docs/contracts.md")
        bad["checklist"] = ["Use the Sites building skill and its environment reference to propose a stack."]
        runner = ScriptedRunner(
            [
                planner_payload("First try.", [bad]),
                planner_payload("Plain words.", [card("p1", "docs/contracts.md")]),
                planner_payload("Done.", [], done=True),
            ]
        )
        manager = self.manager()
        tasks, coordinator = self.build(runner)
        patches = self.patches(manager)
        for item in patches:
            item.start()
        try:
            session = coordinator.start(OPERATOR_PROMPT, PLANNER, WORKER, max_workers=1)
            self.wait_for(session)
        finally:
            coordinator.shutdown()
            tasks.shutdown()
            for item in patches:
                item.stop()

        self.assertEqual(session.status, "completed", session.error)
        self.assertEqual(len(runner.planner_prompts), 3)
        rejection = runner.planner_prompts[1]
        self.assertIn("Your previous reply was rejected", rejection)
        self.assertIn("tells its worker to use a skill or plugin", rejection)
        self.assertIn("Sites building skill", rejection)
        self.assertTrue(any(line.startswith("Planner payload rejected:") and "'p1'" in line for line in session.log))
        # Every planner turn spells out what a worker session has.
        for prompt in runner.planner_prompts:
            self.assertIn("Workers run on Claude Code CLI (claude-opus-5)", prompt)
        self.assertEqual([record.card_id for record in tasks.tasks()], ["p1"])

    def test_sessions_restore_as_stopped_after_a_restart(self):
        tasks = TaskCoordinator(self.repository, object(), OrchestrationSettings(), memory_path=self.memory.path)
        coordinator = OrchestrateCoordinator(
            tasks, object(), OrchestrationSettings(), OrchestrateSettings(), self.storage, self.memory
        )
        from tui.orchestrate_session import OrchestrationSession

        snapshot = OrchestrationSession(
            "orc-004-deadbeef", coordinator.project_key, "prompt", PLANNER, WORKER, 2, status="waiting"
        ).to_dict()
        self.memory.record_orchestration(snapshot)
        self.memory.record_orchestration(
            OrchestrationSession("orc-001-00000000", "other-project", "prompt", PLANNER, WORKER, 2).to_dict()
        )
        tasks.shutdown()

        tasks = TaskCoordinator(self.repository, object(), OrchestrationSettings(), memory_path=self.memory.path)
        restored = OrchestrateCoordinator(
            tasks, object(), OrchestrationSettings(), OrchestrateSettings(), self.storage, self.memory
        )
        sessions = restored.sessions()
        tasks.shutdown()
        self.assertEqual([session.session_id for session in sessions], ["orc-004-deadbeef"])
        self.assertEqual(sessions[0].status, "stopped")
        self.assertIn("do not resume", sessions[0].error)
        self.assertEqual(self.memory.get_orchestrations()["orc-004-deadbeef"]["status"], "stopped")
        self.assertEqual(restored._next_sequence, 5)
        self.assertTrue(restored.delete("orc-004-deadbeef"))
        self.assertNotIn("orc-004-deadbeef", self.memory.get_orchestrations())


if __name__ == "__main__":
    unittest.main()
