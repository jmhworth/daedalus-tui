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
            # Snapshots are keyed by the stable logical task id, not the
            # worktree name, so later worktrees never duplicate the record.
            self.assertEqual(tasks[f"task-{failed.task_id}"]["state"], "failed")
            self.assertEqual(tasks[f"task-{failed.task_id}"]["error"], failed.error)
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
            # A run that was active when the previous process ended is
            # recoverable, never auto-launched, and not reported as an error.
            self.assertEqual(interrupted.status, "interrupted")
            self.assertIsNone(interrupted.error)
            self.assertIn("closed", interrupted.phase.lower())
            self.assertIsNotNone(interrupted.context)
            self.assertEqual(interrupted.title, "Keep the task")
            self.assertEqual([turn.text for turn in interrupted.turns], ["Keep the task"])
            self.assertEqual(interrupted.runs[-1].status, "interrupted")
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
            snapshot = tasks[f"task-{record.task_id}"]
            legacy_keys = (
                "timestamp", "prompt", "provider", "model", "reasoning", "mode",
                "state", "outputs", "error", "tokens", "project",
            )
            self.assertEqual(
                {key: snapshot[key] for key in legacy_keys},
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
            # The conversation representation carries a version marker.
            self.assertEqual(snapshot["schema_version"], 2)
            self.assertEqual(snapshot["title"], "cursor task")
            self.assertEqual(snapshot["prompt_count"], 1)
            self.assertEqual([turn["text"] for turn in snapshot["turns"]], ["cursor task"])
            self.assertEqual(snapshot["runs"][0]["status"], "completed")

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

    def test_explicit_discard_removes_a_paused_tasks_preserved_worktree(self):
        # ``cancel`` is the explicit destructive route; the UI's Cancel control
        # uses ``interrupt`` and never deletes a worktree.
        with tempfile.TemporaryDirectory() as directory:
            coordinator = TaskCoordinator(Path(directory), object(), OrchestrationSettings(max_concurrent_tasks=1))
            record = TaskRecord("paused-task", 1, "pause me", "codex", "luna", "medium", status="paused")
            context = WorktreeContext(
                Path(directory), record.task_id, "base", "agent/task-paused", Path(directory) / "worktree"
            )
            record.context = context
            with coordinator._lock:
                coordinator._tasks[record.task_id] = record
            with patch("tui.task_coordinator.GitWorktreeManager") as manager_class:
                self.assertTrue(coordinator.cancel(record.task_id))
                manager_class.return_value.remove_cancelled.assert_called_once_with(context)
            self.assertEqual(record.status, "cancelled")
            self.assertIsNone(record.context)
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

            # Implementation continues inside the same conversation: same
            # logical task and title, a recorded mode change, and a generated
            # (not user-typed) implementation turn.
            self.assertIs(coding_record, plan_record)
            self.assertEqual(coding_record.mode, "coding")
            self.assertEqual(coding_record.title, "Choose a store")
            implementation_prompt = PlanOrchestrator.prompts[-1]
            self.assertIn("Add the JSON store", implementation_prompt)
            self.assertIn("Original user request", implementation_prompt)
            self.assertIn("q1: b (Which store?: JSON)", implementation_prompt)
            self.assertEqual([turn.kind for turn in coding_record.turns], ["user", "generated", "generated"])
            self.assertEqual([turn.text for turn in coding_record.user_turns], ["Choose a store"])
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


if __name__ == "__main__":
    unittest.main()


class InterruptionAndFollowUpTests(unittest.TestCase):
    """Non-destructive interruption, late callbacks, and multi-turn conversations."""

    def _coordinator(self, directory, **kwargs):
        from tui.local_storage import LocalStorage
        from tui.prompt_store import PromptStore

        storage = LocalStorage(Path(directory) / "data")
        return TaskCoordinator(
            Path(directory) / "project",
            object(),
            OrchestrationSettings(max_concurrent_tasks=2),
            memory_path=Path(directory) / ".daedalus-memory.json",
            prompt_store=PromptStore(storage),
            storage=storage,
            **kwargs,
        )

    def test_interrupting_a_running_agent_preserves_the_worktree_and_restores_nothing_destructively(self):
        class InterruptibleOrchestrator:
            started = threading.Event()

            def __init__(self, repository, _runner, _settings, on_event, integration_gate=None):
                self.repository = repository
                self.on_event = on_event

            def run(self, prompt, provider, model, reasoning, task_id=None, control=None, existing_context=None, **_kwargs):
                context = existing_context or WorktreeContext(
                    self.repository, task_id, "base", f"agent/task-{task_id}", self.repository / "worktree"
                )
                self.on_event("worktree", f"Created {context.branch_name} at {context.path}.", "status")
                self.on_event("agent", "partial work", "message")
                type(self).started.set()
                control.interrupt_requested.wait(timeout=2)
                self.on_event("interrupted", "Run stopped; progress preserved.", "status")
                return OrchestrationResult(False, task_id, context.branch_name, context.path, context=context, interrupted=True)

        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "project").mkdir()
            coordinator = self._coordinator(directory)
            with patch("tui.task_coordinator.LocalOrchestrator", InterruptibleOrchestrator), patch(
                "tui.task_coordinator.GitWorktreeManager"
            ) as manager_class:
                record = coordinator.submit("Build it\n", "codex", "luna", "medium")
                self.assertTrue(InterruptibleOrchestrator.started.wait(timeout=2))
                self.assertTrue(coordinator.interrupt(record.task_id))
                self.assertEqual(record.phase, "Stopping")
                # Repeated presses are idempotent while stopping.
                self.assertTrue(coordinator.interrupt(record.task_id))
                record.future.result(timeout=5)
            self.assertEqual(record.status, "interrupted")
            self.assertIsNone(record.error)
            self.assertIsNotNone(record.context)
            manager_class.return_value.remove_cancelled.assert_not_called()
            self.assertEqual(record.runs[-1].status, "interrupted")
            self.assertEqual(record.messages, ["partial work"])
            # Nothing is running now, so another interrupt reports False.
            self.assertFalse(coordinator.interrupt(record.task_id))
            # The exact prompt was archived verbatim, trailing newline included.
            archive = Path(record.turns[0].archive_path)
            self.assertEqual(archive.read_text(encoding="utf-8"), "Build it\n")
            coordinator.shutdown()

    def test_queued_run_is_interrupted_without_creating_a_worktree(self):
        class BlockingOrchestrator(FakeOrchestrator):
            pass

        FakeOrchestrator.release = threading.Event()
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "project").mkdir()
            coordinator = TaskCoordinator(Path(directory) / "project", object(), OrchestrationSettings(max_concurrent_tasks=1))
            with patch("tui.task_coordinator.LocalOrchestrator", BlockingOrchestrator):
                first = coordinator.submit("first", "codex", "luna", "medium")
                second = coordinator.submit("second", "codex", "luna", "medium")
                deadline = time.time() + 2
                while first.status != "running" and time.time() < deadline:
                    time.sleep(0.01)
                self.assertEqual(second.status, "queued")
                self.assertTrue(coordinator.interrupt(second.task_id))
                self.assertEqual(second.status, "interrupted")
                self.assertIsNone(second.context)
                self.assertEqual(second.runs[-1].status, "interrupted")
                FakeOrchestrator.release.set()
                first.future.result(timeout=5)
            self.assertEqual(first.status, "completed")
            coordinator.shutdown()

    def test_late_callbacks_from_a_superseded_run_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "project").mkdir()
            coordinator = self._coordinator(directory)
            record = TaskRecord("late-task", 1, "prompt", "codex", "luna", "medium", status="interrupted")
            from tui.conversation import TaskRun, TaskTurn

            record.turns = [TaskTurn("turn-1", 1, "prompt", 0.0)]
            record.runs = [TaskRun("run-old", "turn-1", 1, "interrupted", message_end=0), TaskRun("run-new", "turn-1", 2, "running")]
            record.active_turn_id = "turn-1"
            record.active_run_id = "run-new"
            record.status = "running"
            with coordinator._lock:
                coordinator._tasks[record.task_id] = record
            coordinator._handle_event(record, "run-old", "agent", "stale delta", "message")
            coordinator._handle_event(record, "run-old", "failed", "stale failure", "error")
            self.assertEqual(record.messages, [])
            self.assertEqual(record.status, "running")
            self.assertIsNone(record.error)
            coordinator._handle_event(record, "run-new", "agent", "fresh delta", "message")
            self.assertEqual(record.messages, ["fresh delta"])
            self.assertEqual(record.runs[-1].message_end, 1)
            coordinator.shutdown()

    def test_follow_up_after_cleanup_creates_a_fresh_worktree_under_the_same_task(self):
        class RecordingOrchestrator:
            calls = []

            def __init__(self, repository, _runner, _settings, on_event, integration_gate=None):
                self.repository = repository
                self.on_event = on_event

            def run(self, prompt, provider, model, reasoning, task_id=None, existing_context=None, resume_from=None, resume_notes=(), **_kwargs):
                type(self).calls.append((task_id, prompt, existing_context, resume_from, tuple(resume_notes)))
                self.on_event("agent", f"response to {task_id}", "message")
                # Completed coding runs clean up their worktree.
                return OrchestrationResult(True, task_id, f"agent/task-{task_id}", None, context=None, tokens_consumed=5)

        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "project").mkdir()
            coordinator = self._coordinator(directory, context_budget_chars=4000)
            with patch("tui.task_coordinator.LocalOrchestrator", RecordingOrchestrator):
                record = coordinator.submit("# Fix login validation\nDetails here.", "codex", "luna", "medium")
                record.future.result(timeout=5)
                self.assertEqual(record.status, "completed")
                self.assertEqual(record.title, "Fix login validation")
                record.resume_from = "integration"
                record.retry_prompt = "stale retry prompt"
                same = coordinator.submit_followup(record.task_id, "Also handle empty passwords", reasoning="high")
                self.assertIs(same, record)
                record.future.result(timeout=5)
                third = coordinator.submit_followup(record.task_id, "And add tests")
                third.future.result(timeout=5)
            self.assertEqual(record.status, "completed")
            self.assertEqual(record.title, "Fix login validation")
            self.assertEqual([turn.text for turn in record.user_turns], ["# Fix login validation\nDetails here.", "Also handle empty passwords", "And add tests"])
            self.assertEqual(record.turns[1].reasoning, "high")
            self.assertEqual(record.reasoning, "high")
            self.assertEqual(len(record.runs), 3)
            self.assertEqual(record.tokens_consumed, 15)
            calls = RecordingOrchestrator.calls
            self.assertEqual([call[0] for call in calls], [record.task_id, f"{record.task_id}-r2", f"{record.task_id}-r3"])
            self.assertTrue(all(call[2] is None for call in calls))
            self.assertIsNone(calls[1][3])
            self.assertEqual(calls[1][4], ())
            second_prompt = calls[1][1]
            self.assertIn("Original request for this task:\n# Fix login validation", second_prompt)
            self.assertIn(f"response to {record.task_id}", second_prompt)
            self.assertIn("Latest instruction (respond to this one):\nAlso handle empty passwords", second_prompt)
            self.assertNotIn("stale retry prompt", second_prompt)
            # One logical memory record with three prompts, not three tasks.
            tasks = coordinator.memory.get_tasks()
            self.assertEqual(list(tasks), [f"task-{record.task_id}"])
            self.assertEqual(tasks[f"task-{record.task_id}"]["prompt_count"], 3)
            self.assertEqual(len(tasks[f"task-{record.task_id}"]["runs"]), 3)
            archives = sorted(entry.name for entry in Path(record.turns[0].archive_path).parent.iterdir() if entry.name.startswith("turn-"))
            self.assertEqual(archives, ["turn-0001.md", "turn-0002.md", "turn-0003.md"])
            coordinator.shutdown()

    def test_follow_up_is_refused_while_a_run_is_active_and_without_an_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "project").mkdir()
            coordinator = self._coordinator(directory)
            record = TaskRecord("busy", 1, "prompt", "codex", "luna", "medium", status="running")
            with coordinator._lock:
                coordinator._tasks[record.task_id] = record
            with self.assertRaises(RuntimeError):
                coordinator.submit_followup(record.task_id, "another")
            record.status = "completed"
            with patch.object(coordinator.prompt_store, "archive_turn", side_effect=__import__("tui.prompt_store", fromlist=["PromptStoreError"]).PromptStoreError("Could not save prompt to /x/turn-0001.md: disk full")):
                with self.assertRaises(OSError) as raised:
                    coordinator.submit_followup(record.task_id, "another")
            self.assertIn("/x/turn-0001.md", str(raised.exception))
            self.assertEqual(record.turns, [])
            self.assertIsNone(record.future)
            coordinator.shutdown()

    def test_restart_restores_conversation_and_offers_orphaned_archive_as_a_draft(self):
        from tui.local_storage import LocalStorage
        from tui.prompt_store import PromptStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            storage = LocalStorage(root / "data")
            store = PromptStore(storage)
            memory = TaskMemoryStore(root / ".daedalus-memory.json")
            memory.record_task(
                "task-001-conv",
                "First prompt",
                "codex",
                "luna",
                "medium",
                "coding",
                "running",
                ["answer one"],
                project=project,
                logical_task_id="001-conv",
                title="First prompt",
                turns=[
                    {"turn_id": "t1", "sequence": 1, "text": "First prompt", "kind": "user"},
                    {"turn_id": "t2", "sequence": 2, "text": "Second prompt", "kind": "user"},
                ],
                runs=[
                    {"run_id": "r1", "turn_id": "t1", "attempt": 1, "status": "completed", "message_start": 0, "message_end": 1},
                    {"run_id": "r2", "turn_id": "t2", "attempt": 1, "status": "running", "message_start": 1},
                ],
                active_turn_id="t2",
                active_run_id="r2",
                schema_version=2,
            )
            store.archive_turn(project, "001-conv", 3, "orphaned partial submission")

            coordinator = TaskCoordinator(
                project, object(), OrchestrationSettings(), memory_path=root / ".daedalus-memory.json", prompt_store=store, storage=storage
            )
            record = coordinator.get("001-conv")
            self.assertEqual(record.status, "interrupted")
            self.assertEqual(record.title, "First prompt")
            self.assertEqual([turn.turn_id for turn in record.turns], ["t1", "t2"])
            self.assertEqual(record.runs[1].status, "interrupted")
            self.assertEqual(record.runs[1].message_end, 1)
            self.assertEqual(record.response_text(record.runs[0]), "answer one")
            self.assertIsNone(record.future)
            # Missing archives were regenerated; the orphan became a draft.
            self.assertEqual(store.turn_path(project, "001-conv", 1).read_text(encoding="utf-8"), "First prompt")
            draft = store.load_draft(project, "001-conv")
            self.assertEqual((draft.text, draft.kind), ("orphaned partial submission", "recovered"))
            coordinator.shutdown()

    def test_legacy_snapshot_keeps_generated_plan_prompts_as_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            memory = TaskMemoryStore(root / ".daedalus-memory.json")
            memory.record_task(
                "task-002-legacy",
                "Plan the API",
                "codex",
                "luna",
                "medium",
                "plan",
                "awaiting_answers",
                ["plan output"],
                project=project,
                prompt_history=("Plan the API", "Re-evaluate the plan using the user's answers below."),
            )
            coordinator = TaskCoordinator(project, object(), OrchestrationSettings(), memory_path=root / ".daedalus-memory.json")
            record = coordinator.get("002-legacy")
            self.assertEqual(record.title, "Plan the API")
            self.assertEqual([turn.kind for turn in record.turns], ["user", "generated"])
            self.assertIsNone(record.turns[1].submitted_at)
            self.assertEqual(len(record.user_turns), 1)
            self.assertEqual(record.runs[0].message_end, 1)
            coordinator.shutdown()

    def test_integration_gate_releases_an_interrupted_waiter(self):
        from tui.orchestrator import AgentStopped

        gate = IntegrationCoordinator()
        holder_started = threading.Event()
        release = threading.Event()

        def hold():
            holder_started.set()
            release.wait(timeout=5)

        holder = threading.Thread(target=gate.run_when_ready, args=(1, hold))
        holder.start()
        self.assertTrue(holder_started.wait(timeout=2))
        stop_after = time.monotonic() + 0.2
        with self.assertRaises(AgentStopped):
            gate.run_when_ready(2, lambda: None, lambda: "interrupted" if time.monotonic() > stop_after else None)
        release.set()
        holder.join(timeout=2)
        # The gate is usable afterwards.
        ran = []
        gate.run_when_ready(3, lambda: ran.append(True))
        self.assertEqual(ran, [True])
