from datetime import datetime, timezone
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tui.orchestrator import OrchestrationResult, OrchestrationSettings
from tui.git_worktree import WorktreeContext
from tui.memory import TaskMemoryStore
from tui.plan import PlanOption, PlanQuestion, encode_custom_answer
from tui.task_coordinator import TASK_STATUSES, IntegrationCoordinator, TaskCoordinator, TaskRecord


class FakeOrchestrator:
    active = 0
    maximum = 0
    lock = threading.Lock()
    starts = []
    release = None

    def __init__(self, _repository, _runner, _settings, on_event, integration_gate=None):
        self.on_event = on_event
        self.integration_gate = integration_gate

    def run(self, prompt, provider, model, reasoning, task_id=None, submission_sequence=0, mode="coding", control=None, existing_context=None, resume_notes=(), resume_from=None, topic_slug=None):
        with self.lock:
            type(self).active += 1
            type(self).maximum = max(type(self).maximum, type(self).active)
            type(self).starts.append((prompt, provider, model, reasoning))
        self.on_event("worktree", f"Created agent/task-{task_id} at /tmp/{task_id}.", "status")
        self.on_event("agent", f"Completed {prompt}", "message")
        if type(self).release is not None:
            type(self).release.wait(timeout=5)

        def integrate():
            self.on_event("integration", "Integrating task.", "status")

        self.on_event("ready", "Ready.", "status")
        self.integration_gate(submission_sequence, integrate)
        with self.lock:
            type(self).active -= 1
        return OrchestrationResult(True, task_id, f"agent/task-{task_id}", Path(f"/tmp/{task_id}"))


class TaskCoordinatorTests(unittest.TestCase):
    def setUp(self):
        FakeOrchestrator.active = 0
        FakeOrchestrator.maximum = 0
        FakeOrchestrator.starts = []
        FakeOrchestrator.release = threading.Event()

    def test_executor_limits_concurrent_agent_tasks_and_snapshots_settings(self):
        self.assertIn("blocked", TASK_STATUSES)
        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(
                Path(directory),
                object(),
                OrchestrationSettings(max_concurrent_tasks=2),
            )
            with patch("tui.task_coordinator.LocalOrchestrator", FakeOrchestrator):
                records = [
                    coordinator.submit(f"Task {index}", "codex", f"model-{index}", "medium")
                    for index in range(5)
                ]
                deadline = time.time() + 2
                while len(FakeOrchestrator.starts) < 2 and time.time() < deadline:
                    time.sleep(0.01)
                self.assertEqual(len(FakeOrchestrator.starts), 2)
                self.assertLessEqual(FakeOrchestrator.maximum, 2)
                self.assertEqual(records[0].status, "running")
                self.assertEqual(records[2].status, "queued")
                FakeOrchestrator.release.set()
                for record in records:
                    record.future.result(timeout=5)
            self.assertLessEqual(FakeOrchestrator.maximum, 2)
            self.assertEqual(
                [(record.model, record.reasoning) for record in records[:2]],
                [("model-0", "medium"), ("model-1", "medium")],
            )
            coordinator.shutdown()

    def test_plan_task_stays_questioning_until_started_as_coding(self):
        class PlanningOrchestrator:
            calls = []

            def __init__(self, *_args, **_kwargs):
                pass

            def run(self, prompt, _provider, _model, _reasoning, task_id=None, mode="coding", **kwargs):
                type(self).calls.append((mode, kwargs.get("existing_context"), kwargs.get("resume_notes", ())))
                context = kwargs.get("existing_context") or WorktreeContext(
                    Path(directory), task_id, "base", f"agent/task-{task_id}", Path(directory) / "worktree"
                )
                return OrchestrationResult(
                    True,
                    task_id,
                    context.branch_name,
                    context.path,
                    context=context,
                    awaiting_plan=mode == "plan",
                )

        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", PlanningOrchestrator):
                record = coordinator.submit("plan this", "codex", "luna", "medium", mode="plan")
                record.future.result(timeout=5)

                self.assertEqual(record.status, "questioning")
                self.assertEqual(record.phase, "Questioning")
                self.assertTrue(coordinator.continue_plan(record.task_id, "What about the API boundary?"))
                record.future.result(timeout=5)
                self.assertEqual(record.status, "questioning")

                self.assertTrue(coordinator.start_coding(record.task_id, "Proceed with the minimal design."))
                record.future.result(timeout=5)

            self.assertEqual(record.mode, "coding")
            self.assertEqual(record.status, "completed")
            self.assertEqual([call[0] for call in PlanningOrchestrator.calls], ["plan", "plan", "coding"])
            self.assertIs(PlanningOrchestrator.calls[1][1], record.context)
            self.assertIn("What about the API boundary?", PlanningOrchestrator.calls[1][2])
            coordinator.shutdown()

    def test_multi_block_soft_wrapped_plan_reaches_awaiting_answers(self):
        class PlanOrchestrator:
            def __init__(self, _repository, _runner, _settings, on_event, integration_gate=None):
                self.on_event = on_event

            def run(self, _prompt, _provider, _model, _reasoning, task_id=None, **_kwargs):
                # Mimic a planning agent that streams prose, a soft-wrapped first
                # draft, then a revised second BEGIN/END payload in one turn.
                self.on_event("agent", "I'll inspect the repo first.", "message")
                self.on_event(
                    "agent",
                    'BEGIN_DAEDALUS_PLAN\n{"plan":"Draft one.","questions":[{"id":"q1",'
                    '"question":"Which universe?","options":[{"id":"a","label":"All\n'
                    'Climate series"},{"id":"b","label":"One"}]}],'
                    '"no_more_questions":false}\nEND_DAEDALUS_PLAN',
                    "message",
                )
                self.on_event(
                    "agent",
                    'BEGIN_DAEDALUS_PLAN\n{"plan":"Draft two with regimes.","questions":['
                    '{"id":"q1","question":"Which universe?","required":true,"options":['
                    '{"id":"a","label":"KXHIGHLAX only (Recommended)"},'
                    '{"id":"b","label":"All Climate and Weather series"}]}],'
                    '"no_more_questions":false}\nEND_DAEDALUS_PLAN'
                    "Resuming with recommended answers.",
                    "message",
                )
                return OrchestrationResult(True, task_id, awaiting_plan=True)

        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", PlanOrchestrator):
                record = coordinator.submit("Kalshi ACF plan", "codex", "luna", "medium", mode="plan")
                record.future.result(timeout=5)

            self.assertEqual(record.status, "awaiting_answers")
            self.assertEqual(record.plan_text, "Draft two with regimes.")
            self.assertEqual(len(record.plan_questions), 1)
            self.assertEqual(record.plan_questions[0].options[0].option_id, "a")
            self.assertIsNone(record.plan_error)
            coordinator.shutdown()

    def test_first_ready_integration_is_serialized(self):
        coordinator = IntegrationCoordinator()
        started = threading.Event()
        release = threading.Event()
        order = []

        def first_operation():
            order.append(2)
            started.set()
            release.wait(timeout=5)

        thread_two = threading.Thread(target=coordinator.run_when_ready, args=(2, first_operation))
        thread_two.start()
        self.assertTrue(started.wait(timeout=2))

        thread_one = threading.Thread(
            target=coordinator.run_when_ready,
            args=(1, lambda: order.append(1)),
        )
        thread_one.start()
        time.sleep(0.05)
        self.assertEqual(order, [2])
        release.set()
        thread_two.join(timeout=2)
        thread_one.join(timeout=2)
        self.assertEqual(order, [2, 1])

    def test_shutdown_pauses_an_active_worker_without_waiting_indefinitely(self):
        class PausableOrchestrator:
            started = threading.Event()

            def __init__(self, *_args, **_kwargs):
                pass

            def run(self, _prompt, _provider, _model, _reasoning, task_id=None, control=None, **_kwargs):
                type(self).started.set()
                control.pause_requested.wait(timeout=1)
                return OrchestrationResult(False, task_id, paused=True)

        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(
                Path(directory),
                object(),
                OrchestrationSettings(max_concurrent_tasks=1, shutdown_grace_seconds=0.5),
            )
            with patch("tui.task_coordinator.LocalOrchestrator", PausableOrchestrator):
                record = coordinator.submit("stop", "codex", "luna", "medium")
                self.assertTrue(PausableOrchestrator.started.wait(timeout=1))
                self.assertTrue(coordinator.shutdown())

            self.assertTrue(record.future.done())
            self.assertEqual(record.status, "paused")

    def test_failed_task_does_not_block_later_task(self):
        class FailingOrchestrator(FakeOrchestrator):
            def run(self, prompt, provider, model, reasoning, task_id=None, submission_sequence=0, mode="coding", control=None, existing_context=None, resume_notes=(), resume_from=None, topic_slug=None):
                if prompt == "bad":
                    self.on_event("failed", "Task failed but worktree is preserved.", "error")
                    return OrchestrationResult(False, task_id, f"agent/task-{task_id}", Path(f"/tmp/{task_id}"), "preserved")
                return OrchestrationResult(True, task_id, f"agent/task-{task_id}", Path(f"/tmp/{task_id}"))

        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=2))
            with patch("tui.task_coordinator.LocalOrchestrator", FailingOrchestrator):
                failed = coordinator.submit("bad", "codex", "luna", "medium")
                succeeded = coordinator.submit("good", "codex", "terra", "high")
                failed.future.result(timeout=5)
                succeeded.future.result(timeout=5)
            self.assertEqual(failed.status, "failed")
            self.assertEqual(failed.error, "Task failed but worktree is preserved.")
            self.assertEqual(succeeded.status, "completed")
            tasks = next(
                item["tasks"]
                for item in json.loads(coordinator.memory.path.read_text(encoding="utf-8"))
                if "tasks" in item
            )
            self.assertEqual(tasks[failed.worktree_path.name]["state"], "failed")
            self.assertEqual(tasks[failed.worktree_path.name]["error"], failed.error)
            coordinator.shutdown()

    def test_persists_task_details_for_failed_and_completed_tasks(self):
        class TokenReportingOrchestrator:
            def __init__(self, *_args, **_kwargs):
                pass

            def run(self, prompt, _provider, _model, _reasoning, task_id=None, **_kwargs):
                if prompt == "bad":
                    return OrchestrationResult(False, task_id, error="failed", tokens_consumed=99)
                return OrchestrationResult(True, task_id, tokens_consumed=42)

        with tempfile.TemporaryDirectory() as directory:
            memory_path = Path(directory) / ".daedalus-memory.json"
            coordinator = TaskCoordinator(
                Path(directory),
                object(),
                OrchestrationSettings(max_concurrent_tasks=2),
                memory_path=memory_path,
            )
            with patch("tui.task_coordinator.LocalOrchestrator", TokenReportingOrchestrator):
                failed = coordinator.submit("bad", "codex", "luna", "medium")
                succeeded = coordinator.submit("good", "codex", "luna", "medium")
                failed.future.result(timeout=5)
                succeeded.future.result(timeout=5)
            coordinator.shutdown()

            self.assertEqual(failed.status, "failed")
            self.assertEqual(succeeded.status, "completed")
            entries = json.loads(memory_path.read_text(encoding="utf-8"))
            tasks = next(entry["tasks"] for entry in entries if "tasks" in entry)
            failed_task = tasks[f"task-{failed.task_id}"]
            succeeded_task = tasks[f"task-{succeeded.task_id}"]
            self.assertEqual(failed_task["state"], "failed")
            self.assertEqual(succeeded_task["state"], "completed")
            self.assertEqual(failed_task["prompt"], "bad")
            self.assertEqual(succeeded_task["prompt"], "good")
            self.assertEqual(
                succeeded_task["timestamp"],
                datetime.fromtimestamp(succeeded.submitted_at, timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            )
            self.assertEqual(
                {key: succeeded_task[key] for key in ("provider", "model", "reasoning", "mode")},
                {"provider": "codex", "model": "luna", "reasoning": "medium", "mode": "coding"},
            )
            self.assertEqual(succeeded_task["tokens"], 42)
            self.assertEqual(succeeded_task["project"], str(Path(directory).resolve()))
            self.assertEqual(failed_task["tokens"], 0)
            self.assertEqual(failed_task["project"], str(Path(directory).resolve()))

    def test_rehydrates_failed_and_interrupted_tasks_with_worktree_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            worktree = root / ".daedalus-worktrees" / "project" / "task-003-rehydrated"
            project.mkdir()
            worktree.mkdir(parents=True)
            memory_path = root / ".daedalus-memory.json"
            memory = TaskMemoryStore(memory_path)
            memory.record_task(
                "task-003-rehydrated",
                "Recover the task",
                "codex",
                "luna",
                "medium",
                "coding",
                "failed",
                ["The implementation was written."],
                "Verification failed.",
                project=project,
                branch_name="agent/task-003-rehydrated",
                worktree_path=worktree,
                base_commit="base",
            )
            memory.record_task(
                "task-004-running",
                "Keep the task",
                "codex",
                "luna",
                "medium",
                "coding",
                "running",
                project=project,
                branch_name="agent/task-004-running",
                worktree_path=worktree.parent / "task-004-running",
                base_commit="base",
            )
            (worktree.parent / "task-004-running").mkdir()
            legacy_worktree = worktree.parent / "task-005-legacy"
            legacy_worktree.mkdir()
            memory.record_task(
                "task-005-legacy",
                "Recover an older snapshot",
                "codex",
                "luna",
                "medium",
                "coding",
                "failed",
                project=project,
            )

            coordinator = TaskCoordinator(project, object(), OrchestrationSettings(), memory_path=memory_path)
            failed = coordinator.get("003-rehydrated")
            interrupted = coordinator.get("004-running")

            self.assertIsNotNone(failed)
            self.assertEqual(failed.status, "failed")
            self.assertIsNotNone(failed.context)
            self.assertEqual(failed.context.branch_name, "agent/task-003-rehydrated")
            self.assertEqual(failed.messages, ["The implementation was written."])
            self.assertIsNotNone(interrupted)
            self.assertEqual(interrupted.status, "paused")
            self.assertIn("resume", interrupted.error.lower())
            self.assertIsNotNone(interrupted.context)
            legacy = coordinator.get("005-legacy")
            self.assertIsNotNone(legacy)
            self.assertIsNotNone(legacy.context)
            self.assertEqual(legacy.context.branch_name, "agent/task-005-legacy")
            coordinator.shutdown()

    def test_rehydrates_plan_review_from_last_persisted_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            memory_path = root / ".daedalus-memory.json"
            response = (
                '{"plan":"Add the selected store.","questions":[{"id":"q1",'
                '"question":"Which store?","options":[{"id":"a","label":"SQLite"},'
                '{"id":"b","label":"JSON"}]}],"no_more_questions":false}'
            )
            memory = TaskMemoryStore(memory_path)
            memory.record_task(
                "task-plan-rehydrated",
                "Choose a store",
                "codex",
                "luna",
                "medium",
                "plan",
                "awaiting_answers",
                [response],
                project=project,
            )

            coordinator = TaskCoordinator(
                project,
                object(),
                OrchestrationSettings(max_concurrent_tasks=1),
                memory_path=memory_path,
            )
            record = coordinator.get("plan-rehydrated")

            self.assertIsNotNone(record)
            self.assertEqual(record.status, "awaiting_answers")
            self.assertEqual(record.plan_text, "Add the selected store.")
            self.assertEqual(record.plan_questions[0].question_id, "q1")
            self.assertFalse(record.plan_confirmed)
            coordinator.shutdown()

    def test_failed_agent_can_be_retried_with_the_same_request(self):
        class RetryOrchestrator:
            calls = []
            attempts = 0

            def __init__(self, _repository, _runner, _settings, on_event, integration_gate=None):
                self.on_event = on_event

            def run(self, prompt, _provider, _model, _reasoning, task_id=None, resume_notes=(), **_kwargs):
                type(self).calls.append((prompt, resume_notes))
                type(self).attempts += 1
                if type(self).attempts == 1:
                    self.on_event("agent", "I was inspecting the existing implementation.", "message")
                    return OrchestrationResult(False, task_id, error="Agent timed out; retry later.")
                return OrchestrationResult(True, task_id, awaiting_plan=True)

        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", RetryOrchestrator):
                record = coordinator.submit("retryable plan", "codex", "luna", "medium", mode="plan")
                record.future.result(timeout=5)
                self.assertEqual(record.status, "failed")
                self.assertIn("timed out", record.error)

                self.assertTrue(coordinator.retry(record.task_id))
                record.future.result(timeout=5)

            self.assertEqual(record.status, "questioning")
            self.assertEqual(RetryOrchestrator.calls[0], ("retryable plan", ()))
            self.assertEqual(RetryOrchestrator.calls[1][0], "retryable plan")
            self.assertEqual(
                RetryOrchestrator.calls[1][1],
                ("Previous visible AI output from the failed attempt:\n"
                 "I was inspecting the existing implementation.",),
            )
            coordinator.shutdown()

    def test_repeated_retries_replace_previous_output_context_instead_of_duplicating_it(self):
        class RetryOrchestrator:
            attempts = 0
            resume_notes = []

            def __init__(self, _repository, _runner, _settings, on_event, integration_gate=None):
                self.on_event = on_event

            def run(self, _prompt, _provider, _model, _reasoning, task_id=None, resume_notes=(), **_kwargs):
                type(self).resume_notes.append(resume_notes)
                type(self).attempts += 1
                self.on_event("agent", f"Attempt {type(self).attempts} output.", "message")
                if type(self).attempts < 3:
                    return OrchestrationResult(False, task_id, error="Agent failed; retry later.")
                return OrchestrationResult(True, task_id)

        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", RetryOrchestrator):
                record = coordinator.submit("retry this", "codex", "luna", "medium")
                record.future.result(timeout=5)
                self.assertTrue(coordinator.retry(record.task_id))
                record.future.result(timeout=5)
                self.assertTrue(coordinator.retry(record.task_id))
                record.future.result(timeout=5)

            self.assertEqual(RetryOrchestrator.resume_notes[0], ())
            self.assertEqual(
                RetryOrchestrator.resume_notes[1],
                ("Previous visible AI output from the failed attempt:\nAttempt 1 output.",),
            )
            self.assertEqual(
                RetryOrchestrator.resume_notes[2],
                ("Previous visible AI output from the failed attempt:\n"
                 "Attempt 1 output.\n\nAttempt 2 output.",),
            )
            coordinator.shutdown()

    def test_persists_null_model_and_reasoning_for_cursor_task(self):
        class CursorOrchestrator:
            def __init__(self, *_args, **_kwargs):
                pass

            def run(self, prompt, _provider, _model, _reasoning, task_id=None, **_kwargs):
                return OrchestrationResult(True, task_id, tokens_consumed=17)

        with tempfile.TemporaryDirectory() as directory:
            memory_path = Path(directory) / ".daedalus-memory.json"
            coordinator = TaskCoordinator(
                Path(directory),
                object(),
                OrchestrationSettings(max_concurrent_tasks=1),
                memory_path=memory_path,
            )
            with patch("tui.task_coordinator.LocalOrchestrator", CursorOrchestrator):
                record = coordinator.submit("cursor task", "cursor", "cursor", "")
                record.future.result(timeout=5)
            coordinator.shutdown()

            entries = json.loads(memory_path.read_text(encoding="utf-8"))
            tasks = next(entry["tasks"] for entry in entries if "tasks" in entry)
            self.assertEqual(
                tasks[f"task-{record.task_id}"],
                {
                    "timestamp": datetime.fromtimestamp(record.submitted_at, timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z"),
                    "prompt": "cursor task",
                    "provider": "cursor",
                    "model": None,
                    "reasoning": None,
                    "mode": "coding",
                    "state": "completed",
                    "outputs": [],
                    "error": None,
                    "tokens": 17,
                    "project": str(Path(directory).resolve()),
                },
            )

    def test_pause_preserves_context_and_resume_reuses_same_worktree(self):
        class PausableOrchestrator:
            started = threading.Event()
            calls = []

            def __init__(self, repository, _runner, _settings, _on_event, integration_gate=None):
                self.repository = repository

            def run(self, prompt, provider, model, reasoning, task_id=None, submission_sequence=0, mode="coding", control=None, existing_context=None, resume_notes=(), resume_from=None, topic_slug=None):
                type(self).calls.append((existing_context, resume_notes, resume_from))
                type(self).started.set()
                context = existing_context or WorktreeContext(
                    self.repository,
                    task_id,
                    "base",
                    f"agent/task-{task_id}",
                    self.repository / "worktree",
                )
                if existing_context is None:
                    control.pause_requested.wait(timeout=2)
                    return OrchestrationResult(False, task_id, context.branch_name, context.path, context=context, paused=True)
                return OrchestrationResult(True, task_id, context.branch_name, context.path, context=context)

        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", PausableOrchestrator):
                record = coordinator.submit("continue", "codex", "luna", "medium")
                self.assertTrue(PausableOrchestrator.started.wait(timeout=2))
                self.assertTrue(coordinator.pause(record.task_id))
                record.future.result(timeout=5)
                self.assertEqual(record.status, "paused")
                preserved_context = record.context
                self.assertIsNotNone(preserved_context)

                PausableOrchestrator.started.clear()
                self.assertTrue(coordinator.resume(record.task_id, "The API already exists here."))
                record.future.result(timeout=5)

            self.assertEqual(record.status, "completed")
            self.assertIs(PausableOrchestrator.calls[1][0], preserved_context)
            self.assertEqual(PausableOrchestrator.calls[1][1], ("The API already exists here.",))
            self.assertIsNone(PausableOrchestrator.calls[1][2])
            coordinator.shutdown()

    def test_retry_after_integration_failure_resumes_from_integration(self):
        class IntegrationRetryOrchestrator:
            calls = []
            attempts = 0

            def __init__(self, repository, _runner, _settings, on_event, integration_gate=None):
                self.repository = repository
                self.on_event = on_event

            def run(
                self,
                prompt,
                _provider,
                _model,
                _reasoning,
                task_id=None,
                existing_context=None,
                resume_from=None,
                **_kwargs,
            ):
                type(self).attempts += 1
                type(self).calls.append(resume_from)
                context = existing_context or WorktreeContext(
                    self.repository,
                    task_id,
                    "base",
                    f"agent/task-{task_id}",
                    self.repository / "worktree",
                )
                if type(self).attempts == 1:
                    self.on_event("ready", "Task is ready for serialized integration.", "status")
                    self.on_event("failed", "Integration failed after 3 resolver attempts.\n\nmerge conflict", "error")
                    return OrchestrationResult(
                        False,
                        task_id,
                        context.branch_name,
                        context.path,
                        "Integration failed after 3 resolver attempts.\n\nmerge conflict",
                        context=context,
                    )
                return OrchestrationResult(True, task_id, context.branch_name, context.path, context=context)

        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", IntegrationRetryOrchestrator):
                record = coordinator.submit("promote me", "codex", "luna", "medium")
                record.future.result(timeout=5)
                self.assertEqual(record.status, "failed")
                self.assertEqual(record.resume_from, "integration")
                self.assertIn("merge conflict", record.error)

                self.assertTrue(coordinator.retry(record.task_id))
                record.future.result(timeout=5)

            self.assertEqual(record.status, "completed")
            self.assertEqual(IntegrationRetryOrchestrator.calls, [None, "integration"])
            self.assertIsNone(record.resume_from)
            coordinator.shutdown()

    def test_cancel_paused_task_removes_preserved_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            record = TaskRecord("paused-task", 1, "pause me", "codex", "luna", "medium", status="paused")
            record.context = WorktreeContext(
                Path(directory), record.task_id, "base", "agent/task-paused", Path(directory) / "worktree"
            )
            with coordinator._lock:
                coordinator._tasks[record.task_id] = record
            with patch("tui.task_coordinator.GitWorktreeManager") as manager_class:
                self.assertTrue(coordinator.cancel(record.task_id))
                manager_class.return_value.remove_cancelled.assert_called_once_with(record.context)
            self.assertEqual(record.status, "cancelled")
            coordinator.shutdown()

    def test_plan_answers_require_agent_confirmation_before_implementation(self):
        class PlanOrchestrator:
            responses = [
                '{"plan":"Add the selected store.","questions":[{"id":"q1",'
                '"question":"Which store?","options":[{"id":"a","label":"SQLite"},'
                '{"id":"b","label":"JSON"}]}],"no_more_questions":false}',
                '{"plan":"Add the JSON store.","questions":[],"no_more_questions":true}',
                "Implemented the approved plan.",
            ]
            prompts = []

            def __init__(self, _repository, _runner, _settings, on_event, integration_gate=None):
                self.on_event = on_event

            def run(self, prompt, _provider, _model, _reasoning, task_id=None, **_kwargs):
                type(self).prompts.append(prompt)
                response = type(self).responses.pop(0)
                self.on_event("agent", response, "message")
                return OrchestrationResult(True, task_id)

        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", PlanOrchestrator):
                plan_record = coordinator.submit("Choose a store", "codex", "luna", "medium", mode="plan")
                plan_record.future.result(timeout=5)

                self.assertEqual(plan_record.status, "awaiting_answers")
                self.assertFalse(plan_record.plan_confirmed)
                self.assertFalse(
                    coordinator.implement_plan(plan_record.task_id)
                )
                self.assertTrue(coordinator.answer_plan(plan_record.task_id, {"q1": "b"}))
                plan_record.future.result(timeout=5)

                self.assertTrue(plan_record.plan_confirmed)
                self.assertEqual(plan_record.plan_questions, ())
                persisted = coordinator.memory.get_tasks()[plan_record.memory_task_id]
                self.assertEqual(persisted["prompt_history"][0], "Choose a store")
                self.assertIn("User answers:", persisted["prompt_history"][1])
                coding_record = coordinator.implement_plan(plan_record.task_id)
                self.assertIsNotNone(coding_record)
                coding_record.future.result(timeout=5)
                self.assertTrue(plan_record.plan_implemented)
                self.assertIsNone(coordinator.implement_plan(plan_record.task_id))

            self.assertEqual(coding_record.mode, "coding")
            self.assertIn("Add the JSON store", coding_record.prompt)
            self.assertIn("Original user request", coding_record.prompt)
            self.assertIn("q1: b (Which store?: JSON)", coding_record.prompt)
            coordinator.shutdown()

    def test_plan_answers_accept_ui_owned_custom_text(self):
        class PlanOrchestrator:
            prompts = []
            responses = [
                '{"plan":"Choose the store.","questions":[{"id":"q1",'
                '"question":"Which store?","options":[{"id":"a","label":"SQLite"},'
                '{"id":"b","label":"JSON"}]}],"no_more_questions":false}',
                '{"plan":"Use the custom store.","questions":[],"no_more_questions":true}',
            ]

            def __init__(self, _repository, _runner, _settings, on_event, integration_gate=None):
                self.on_event = on_event

            def run(self, prompt, _provider, _model, _reasoning, task_id=None, **_kwargs):
                type(self).prompts.append(prompt)
                self.on_event("agent", type(self).responses.pop(0), "message")
                return OrchestrationResult(True, task_id)

        custom_answer = encode_custom_answer("A user-defined store")
        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", PlanOrchestrator):
                record = coordinator.submit("Choose a store", "codex", "luna", "medium", mode="plan")
                record.future.result(timeout=5)

                self.assertTrue(coordinator.answer_plan(record.task_id, {"q1": custom_answer}))
                record.future.result(timeout=5)

            self.assertTrue(record.plan_confirmed)
            self.assertIn("Custom answer: A user-defined store", PlanOrchestrator.prompts[1])
            self.assertEqual(
                record.plan_answer_details["q1"],
                "Which store?: Custom answer: A user-defined store",
            )
            coordinator.shutdown()

    def test_invalid_confirmation_preserves_answers_for_a_safe_retry(self):
        class PlanOrchestrator:
            responses = [
                '{"plan":"Add the selected store.","questions":[{"id":"q1",'
                '"question":"Which store?","options":[{"id":"a","label":"SQLite"},'
                '{"id":"b","label":"JSON"}]}],"no_more_questions":false}',
                "The final plan is JSON somewhere else.",
                '{"plan":"Add the JSON store.","questions":[],"no_more_questions":true}',
            ]

            def __init__(self, _repository, _runner, _settings, on_event, integration_gate=None):
                self.on_event = on_event

            def run(self, _prompt, _provider, _model, _reasoning, task_id=None, **_kwargs):
                self.on_event("agent", type(self).responses.pop(0), "message")
                return OrchestrationResult(True, task_id)

        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", PlanOrchestrator):
                record = coordinator.submit("Choose a store", "codex", "luna", "medium", mode="plan")
                record.future.result(timeout=5)
                self.assertTrue(coordinator.answer_plan(record.task_id, {"q1": "b"}))
                record.future.result(timeout=5)

                self.assertEqual(record.status, "awaiting_answers")
                self.assertEqual(record.plan_text, "Add the selected store.")
                self.assertEqual(record.plan_answers, {"q1": "b"})
                self.assertIn("required format", record.error)

                self.assertTrue(coordinator.answer_plan(record.task_id, {"q1": "b"}))
                record.future.result(timeout=5)

            self.assertTrue(record.plan_confirmed)
            coordinator.shutdown()

    def test_revised_question_drops_only_its_invalid_saved_answer(self):
        class PlanOrchestrator:
            responses = [
                '{"plan":"Choose storage.","questions":[{"id":"q1","question":"Which store?",'
                '"options":[{"id":"a","label":"SQLite"},{"id":"b","label":"JSON"}]}],'
                '"no_more_questions":false}',
                '{"plan":"Choose hosting.","questions":[{"id":"q1","question":"Which host?",'
                '"options":[{"id":"cloud","label":"Cloud"},{"id":"local","label":"Local"}]}],'
                '"no_more_questions":false}',
            ]

            def __init__(self, _repository, _runner, _settings, on_event, integration_gate=None):
                self.on_event = on_event

            def run(self, _prompt, _provider, _model, _reasoning, task_id=None, **_kwargs):
                self.on_event("agent", type(self).responses.pop(0), "message")
                return OrchestrationResult(True, task_id)

        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", PlanOrchestrator):
                record = coordinator.submit("Choose deployment", "codex", "luna", "medium", mode="plan")
                record.future.result(timeout=5)
                self.assertTrue(coordinator.answer_plan(record.task_id, {"q1": "b"}))
                record.future.result(timeout=5)

            self.assertEqual(record.status, "awaiting_answers")
            self.assertEqual(record.plan_answers, {})
            coordinator.shutdown()

    def test_implementation_discards_the_clean_planning_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            record = TaskRecord("plan-task", 1, "Plan it", "codex", "luna", "medium", mode="plan")
            record.status = "completed"
            record.plan_confirmed = True
            record.context = WorktreeContext(
                Path(directory), record.task_id, "base", "agent/task-plan-task", Path(directory) / "plan-worktree"
            )
            record.worktree_path = record.context.path
            with coordinator._lock:
                coordinator._tasks[record.task_id] = record
            with patch("tui.task_coordinator.GitWorktreeManager") as manager_class:
                coding_record = coordinator.implement_plan(record.task_id)

            self.assertIsNotNone(coding_record)
            manager_class.return_value.remove_successful.assert_called_once_with(
                WorktreeContext(Path(directory), record.task_id, "base", "agent/task-plan-task", Path(directory) / "plan-worktree")
            )
            self.assertIsNone(record.context)
            self.assertIsNone(record.worktree_path)
            coordinator.shutdown()

    def test_plan_clarification_is_separate_from_plan_conversation(self):
        class ClarificationOrchestrator:
            prompts = []
            modes = []

            def __init__(self, _repository, _runner, _settings, on_event, integration_gate=None):
                self.on_event = on_event

            def run(self, prompt, _provider, _model, _reasoning, task_id=None, mode="coding", **_kwargs):
                type(self).prompts.append(prompt)
                type(self).modes.append(mode)
                if mode == "ask":
                    self.on_event("agent", "SQLite means a local file-backed store.", "message")
                    return OrchestrationResult(True, task_id, tokens_consumed=12)
                self.on_event(
                    "agent",
                    '{"plan":"Add the selected store.","questions":[{"id":"q1",'
                    '"question":"Which store?","options":[{"id":"a","label":"SQLite"},'
                    '{"id":"b","label":"JSON"}]}],"no_more_questions":false}',
                    "message",
                )
                return OrchestrationResult(True, task_id, awaiting_plan=True)

        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", ClarificationOrchestrator):
                record = coordinator.submit("Choose a store", "codex", "luna", "medium", mode="plan")
                record.future.result(timeout=5)
                plan_messages = list(record.messages)
                plan_status = record.status

                self.assertTrue(
                    coordinator.clarify_plan_question(record.task_id, "q1", "What does store mean?")
                )
                deadline = time.time() + 2
                while time.time() < deadline:
                    clarifications = record.plan_clarifications.get("q1", [])
                    if clarifications and clarifications[-1].status == "completed":
                        break
                    time.sleep(0.01)

            clarification = record.plan_clarifications["q1"][-1]
            self.assertEqual(clarification.status, "completed")
            self.assertEqual(clarification.answer, "SQLite means a local file-backed store.")
            self.assertEqual(record.status, plan_status)
            self.assertEqual(record.messages, plan_messages)
            self.assertEqual(ClarificationOrchestrator.modes[-1], "ask")
            self.assertIn("What does store mean?", ClarificationOrchestrator.prompts[-1])
            self.assertIn("Which store?", ClarificationOrchestrator.prompts[-1])
            self.assertIn("Add the selected store.", ClarificationOrchestrator.prompts[-1])
            self.assertEqual(record.tokens_consumed, 12)
            coordinator.shutdown()

    def test_submit_persists_and_restores_topic(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            memory_path = repository / ".daedalus-memory.json"
            coordinator = TaskCoordinator(
                repository,
                object(),
                OrchestrationSettings(max_concurrent_tasks=1),
                memory_path=memory_path,
            )
            with patch("tui.task_coordinator.LocalOrchestrator", FakeOrchestrator):
                FakeOrchestrator.release.set()
                record = coordinator.submit(
                    "Build MVP piece",
                    "codex",
                    "luna",
                    "medium",
                    topic="mvp",
                )
                record.future.result(timeout=5)
            self.assertEqual(record.topic, "mvp")
            snapshot = coordinator.memory.get_tasks()[record.memory_task_id]
            self.assertEqual(snapshot["topic"], "mvp")
            coordinator.shutdown()

            restored = TaskCoordinator(
                repository,
                object(),
                OrchestrationSettings(max_concurrent_tasks=1),
                memory_path=memory_path,
            )
            rehydrated = restored.get(record.task_id)
            self.assertIsNotNone(rehydrated)
            self.assertEqual(rehydrated.topic, "mvp")
            restored.shutdown()

    def test_implement_plan_and_clarification_inherit_topic(self):
        class TrackingOrchestrator:
            topic_slugs = []

            def __init__(self, _repository, _runner, _settings, on_event, integration_gate=None):
                self.on_event = on_event

            def run(self, prompt, _provider, _model, _reasoning, task_id=None, mode="coding", **kwargs):
                type(self).topic_slugs.append(kwargs.get("topic_slug"))
                if mode == "ask":
                    self.on_event("agent", "Clarification answer.", "message")
                    return OrchestrationResult(True, task_id, tokens_consumed=3)
                if mode == "plan":
                    self.on_event(
                        "agent",
                        '{"plan":"Ship the MVP.","questions":[{"id":"q1",'
                        '"question":"Scope?","options":[{"id":"a","label":"Small"},'
                        '{"id":"b","label":"Large"}]}],"no_more_questions":false}',
                        "message",
                    )
                    return OrchestrationResult(True, task_id, awaiting_plan=True)
                self.on_event("agent", "Implemented.", "message")
                return OrchestrationResult(True, task_id)

        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", TrackingOrchestrator):
                plan_record = coordinator.submit(
                    "Plan the MVP",
                    "codex",
                    "luna",
                    "medium",
                    mode="plan",
                    topic="mvp",
                )
                plan_record.future.result(timeout=5)
                self.assertEqual(plan_record.topic, "mvp")
                self.assertEqual(TrackingOrchestrator.topic_slugs[-1], "mvp")

                self.assertTrue(
                    coordinator.clarify_plan_question(plan_record.task_id, "q1", "What is Small?")
                )
                deadline = time.time() + 2
                while time.time() < deadline:
                    clarifications = plan_record.plan_clarifications.get("q1", [])
                    if clarifications and clarifications[-1].status == "completed":
                        break
                    time.sleep(0.01)
                self.assertEqual(TrackingOrchestrator.topic_slugs[-1], "mvp")

                plan_record.plan_confirmed = True
                plan_record.plan_questions = ()
                plan_record.plan_answers = {"q1": "a"}
                plan_record.plan_answer_details = {"q1": "Scope?: Small"}
                plan_record.plan_text = "Ship the MVP."
                plan_record.status = "completed"
                plan_record.plan_implemented = False
                coding_record = coordinator.implement_plan(plan_record.task_id)
                self.assertIsNotNone(coding_record)
                self.assertEqual(coding_record.topic, "mvp")
                coding_record.future.result(timeout=5)
                self.assertEqual(TrackingOrchestrator.topic_slugs[-1], "mvp")
            coordinator.shutdown()

    def test_sync_recovery_plan_auto_implements_without_reset_or_stock_implement(self):
        from tui.git_worktree import WorktreeContext
        from tui.orchestrator import OrchestrationResult
        from tui.plan import PLAN_END, PLAN_START

        class SyncOrchestrator:
            calls = []
            gates = []

            def __init__(self, repository, _runner, _settings, on_event, integration_gate=None, **_kwargs):
                self.repository = repository
                self.on_event = on_event
                self.integration_gate = integration_gate or (lambda _seq, op: op())

            def run(self, prompt, provider, model, reasoning, task_id=None, mode="coding",
                    existing_context=None, sync_recovery=False, **kwargs):
                type(self).calls.append(
                    {
                        "mode": mode,
                        "sync_recovery": sync_recovery,
                        "existing_context": existing_context,
                        "kwargs": kwargs,
                    }
                )
                context = existing_context or WorktreeContext(
                    self.repository, task_id, "base", "main", self.repository / "sync-wt"
                )
                if mode == "plan":
                    payload = (
                        f"{PLAN_START}\n"
                        '{"plan": "Keep both sides carefully.", "questions": [], "no_more_questions": true}\n'
                        f"{PLAN_END}"
                    )
                    self.on_event("planning", payload, "message")
                    return OrchestrationResult(
                        True,
                        task_id,
                        context.branch_name,
                        context.path,
                        context=context,
                        awaiting_plan=True,
                    )

                def finalize() -> None:
                    type(self).gates.append("finalize")

                self.integration_gate(kwargs.get("submission_sequence", 0), finalize)
                return OrchestrationResult(True, task_id, context.branch_name, context.path, context=None)

        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory) / "sync-wt"
            worktree.mkdir()
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", SyncOrchestrator), patch.object(
                TaskCoordinator, "_cleanup_orphaned_sync_recoveries_locked"
            ):
                record = coordinator.submit_sync_recovery(
                    provider="codex",
                    model="luna",
                    reasoning="medium",
                    operating_branch="main",
                    remote="origin",
                    worktree_path=worktree,
                    conflicted_paths=("shared.txt",),
                    used_temp_branch=True,
                    temp_branch_name="daedalus/sync-resolve-main-1",
                    merge_failure="CONFLICT",
                    attempt_limit=2,
                    base_commit="abc",
                )
                # Wait for plan + auto coding.
                deadline = time.time() + 5
                while time.time() < deadline and record.status not in {"completed", "failed"}:
                    if record.future is not None and not record.future.done():
                        try:
                            record.future.result(timeout=0.2)
                        except Exception:
                            pass
                    time.sleep(0.05)
                # Coding future may replace plan future.
                if record.future is not None and not record.future.done():
                    record.future.result(timeout=5)

            self.assertTrue(record.sync_recovery)
            self.assertEqual(record.status, "completed")
            self.assertTrue(record.plan_implemented)
            self.assertEqual(len(SyncOrchestrator.calls), 2)
            self.assertEqual(SyncOrchestrator.calls[0]["mode"], "plan")
            self.assertTrue(SyncOrchestrator.calls[0]["sync_recovery"])
            self.assertIsNotNone(SyncOrchestrator.calls[0]["existing_context"])
            self.assertEqual(SyncOrchestrator.calls[1]["mode"], "coding")
            self.assertTrue(SyncOrchestrator.calls[1]["sync_recovery"])
            self.assertIs(
                SyncOrchestrator.calls[1]["existing_context"],
                SyncOrchestrator.calls[0]["existing_context"],
            )
            self.assertEqual(SyncOrchestrator.gates, ["finalize"])
            self.assertIsNone(coordinator.implement_plan(record.task_id))
            coordinator.shutdown()

    def test_sync_recovery_questions_pause_then_auto_continue(self):
        from tui.git_worktree import WorktreeContext
        from tui.orchestrator import OrchestrationResult
        from tui.plan import PLAN_END, PLAN_START

        class QuestionThenConfirmOrchestrator:
            stage = 0

            def __init__(self, repository, _runner, _settings, on_event, integration_gate=None, **_kwargs):
                self.repository = repository
                self.on_event = on_event
                self.integration_gate = integration_gate or (lambda _seq, op: op())

            def run(self, prompt, provider, model, reasoning, task_id=None, mode="coding",
                    existing_context=None, sync_recovery=False, **kwargs):
                context = existing_context or WorktreeContext(
                    self.repository, task_id, "base", "main", self.repository / "sync-wt"
                )
                if mode == "plan":
                    type(self).stage += 1
                    if type(self).stage == 1:
                        payload = (
                            f"{PLAN_START}\n"
                            '{"plan": "Need a decision.", "questions": [{"id": "q1", "question": "Keep?", '
                            '"required": true, "options": [{"id": "a", "label": "Yes (Recommended)"}, '
                            '{"id": "b", "label": "No"}]}], "no_more_questions": false}\n'
                            f"{PLAN_END}"
                        )
                    else:
                        payload = (
                            f"{PLAN_START}\n"
                            '{"plan": "Keep remote.", "questions": [], "no_more_questions": true}\n'
                            f"{PLAN_END}"
                        )
                    self.on_event("planning", payload, "message")
                    return OrchestrationResult(
                        True,
                        task_id,
                        context.branch_name,
                        context.path,
                        context=context,
                        awaiting_plan=True,
                    )
                self.integration_gate(0, lambda: None)
                return OrchestrationResult(True, task_id, context.branch_name, context.path, context=None)

        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory) / "sync-wt"
            worktree.mkdir()
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", QuestionThenConfirmOrchestrator), patch.object(
                TaskCoordinator, "_cleanup_orphaned_sync_recoveries_locked"
            ):
                record = coordinator.submit_sync_recovery(
                    provider="codex",
                    model="luna",
                    reasoning="medium",
                    operating_branch="main",
                    remote="origin",
                    worktree_path=worktree,
                    conflicted_paths=("shared.txt",),
                    used_temp_branch=False,
                    temp_branch_name=None,
                    merge_failure="CONFLICT",
                    base_commit="abc",
                )
                record.future.result(timeout=5)
                self.assertEqual(record.status, "awaiting_answers")
                preserved = record.context
                self.assertIsNotNone(preserved)
                self.assertTrue(coordinator.answer_plan(record.task_id, {"q1": "a"}))
                deadline = time.time() + 5
                while time.time() < deadline and record.status not in {"completed", "failed"}:
                    if record.future is not None and not record.future.done():
                        try:
                            record.future.result(timeout=0.2)
                        except Exception:
                            pass
                    time.sleep(0.05)
                if record.future is not None and not record.future.done():
                    record.future.result(timeout=5)
            self.assertEqual(record.status, "completed")
            self.assertTrue(record.plan_implemented)
            coordinator.shutdown()


if __name__ == "__main__":
    unittest.main()
