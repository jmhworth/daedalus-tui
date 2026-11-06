"""Concurrent task state and serialized local integration."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Condition, Lock
import time
import uuid
from typing import Callable

from .agent_runner import AgentControl, AgentRunner
from .debug_log import LOGGER, log_exception
from .git_worktree import (
    GitWorktreeError,
    GitWorktreeManager,
    WorktreeContext,
    abort_sync_merge,
)
from .memory import DEFAULT_MEMORY_FILE, TaskMemoryStore
from .orchestrator import LocalOrchestrator, OrchestrationResult, OrchestrationSettings
from .plan import (
    PlanClarification,
    PlanQuestion,
    build_implementation_prompt,
    build_plan_clarification_prompt,
    build_plan_followup_prompt,
    custom_answer_text,
    is_valid_plan_answer,
    parse_plan_response,
)
from .prompts import build_sync_conflict_plan_prompt


TaskEventCallback = Callable[["TaskRecord", str, str, str], None]
TASK_STATUSES = (
    "queued",
    "planning",
    "questioning",
    "running",
    "verifying",
    "ready",
    "integrating",
    "resolving",
    "proposed",
    "completed",
    "failed",
    "blocked",
    "paused",
    "cancelled",
    "awaiting_answers",
)
INTERRUPTIBLE_STATUSES = {
    "queued",
    "planning",
    "running",
    "verifying",
    "ready",
    "integrating",
    "resolving",
}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _nonnegative_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _snapshot_timestamp(value: object) -> float:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return time.time()


def _snapshot_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    return Path(value).expanduser().resolve()


def _snapshot_sequence(snapshot: dict[str, object], task_id: str) -> int:
    sequence = snapshot.get("submission_sequence")
    if isinstance(sequence, int) and sequence > 0:
        return sequence
    prefix = task_id.split("-", 1)[0]
    try:
        return max(1, int(prefix))
    except ValueError:
        return 1


def _phase_for_status(status: str) -> str:
    return {
        "awaiting_answers": "Questions",
        "proposed": "Proposed",
        "completed": "Completed",
        "failed": "Failed",
        "paused": "Paused",
        "cancelled": "Cancelled",
        "questioning": "Questioning",
    }.get(status, status.replace("_", " ").capitalize())


@dataclass
class TaskRecord:
    task_id: str
    submission_sequence: int
    prompt: str
    provider: str
    model: str
    reasoning: str
    mode: str = "coding"
    topic: str | None = None
    status: str = "queued"
    phase: str = "Queued"
    branch_name: str = ""
    worktree_path: Path | None = None
    messages: list[str] = field(default_factory=list)
    error: str | None = None
    tokens_consumed: int = 0
    submitted_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    resume_notes: list[str] = field(default_factory=list)
    context: WorktreeContext | None = field(default=None, repr=False, compare=False)
    control: AgentControl = field(default_factory=AgentControl, repr=False, compare=False)
    future: Future | None = field(default=None, repr=False, compare=False)
    memory_task_id: str | None = field(default=None, repr=False, compare=False)
    plan_text: str = ""
    plan_questions: tuple[PlanQuestion, ...] = ()
    # Cursor's terminal result is authoritative for a planning turn. Streamed
    # assistant fragments remain in ``messages`` for progress and fallback.
    plan_final_output: str = field(default="", repr=False, compare=False)
    plan_answers: dict[str, str] = field(default_factory=dict)
    plan_answer_details: dict[str, str] = field(default_factory=dict)
    plan_clarifications: dict[str, list[PlanClarification]] = field(default_factory=dict)
    plan_confirmed: bool = False
    plan_implemented: bool = False
    plan_error: str | None = None
    prompt_history: list[str] = field(default_factory=list, repr=False, compare=False)
    chain_id: str | None = None
    parent_task_id: str | None = None
    automatic_follow_up_prompt: str = ""
    automatic_follow_up_task_id: str | None = None
    conversation_context: str | None = field(default=None, repr=False, compare=False)
    plan_followup_prompt: str | None = field(default=None, repr=False, compare=False)
    retry_prompt: str | None = field(default=None, repr=False, compare=False)
    retry_output_context: str | None = field(default=None, repr=False, compare=False)
    # When coding and verification already succeeded, retries resume at integration.
    resume_from: str | None = None
    # Operator Sync conflict recovery: plan/code in a preserved sync worktree.
    sync_recovery: bool = False
    sync_operating_branch: str = ""
    sync_remote: str = "origin"
    sync_used_temp_branch: bool = False
    sync_temp_branch_name: str | None = None
    sync_conflict_attempt_limit: int = 3
    sync_conflicted_paths: tuple[str, ...] = ()


class IntegrationCoordinator:
    """Run ready integration operations one at a time in ready order."""

    def __init__(self) -> None:
        self._condition = Condition()
        self._ready: list[tuple[int, int, Callable[[], None]]] = []
        self._ready_counter = 0
        self._active = False
        self._closed = False

    def shutdown(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def run_when_ready(self, sequence: int, operation: Callable[[], None]) -> None:
        with self._condition:
            if self._closed:
                raise RuntimeError("Integration coordinator is shut down.")
            self._ready_counter += 1
            entry = (self._ready_counter, sequence, operation)
            self._ready.append(entry)
            self._ready.sort(key=lambda item: (item[0], item[1]))
            while self._active or self._ready[0] is not entry:
                self._condition.wait(timeout=0.1)
                if self._closed:
                    self._ready.remove(entry)
                    self._condition.notify_all()
                    raise RuntimeError("Integration coordinator is shut down.")
            if self._closed:
                self._ready.remove(entry)
                self._condition.notify_all()
                raise RuntimeError("Integration coordinator is shut down.")
            self._ready.pop(0)
            self._active = True

        try:
            operation()
        finally:
            with self._condition:
                self._active = False
                self._condition.notify_all()


class TaskCoordinator:
    """Submit independent prompts while sharing a serialized integration gate."""

    def __init__(
        self,
        repository: Path,
        runner: AgentRunner,
        settings: OrchestrationSettings,
        on_event: TaskEventCallback | None = None,
        memory_path: Path | None = None,
        environment_path: Path | None = None,
        migration_push_lock: Lock | None = None,
    ) -> None:
        if settings.max_concurrent_tasks < 1:
            raise ValueError("max_concurrent_tasks must be positive")
        self.repository = repository.resolve()
        self.runner = runner
        self.settings = settings
        self.on_event = on_event
        self.environment_path = environment_path.resolve() if environment_path is not None else None
        self.migration_push_lock = migration_push_lock
        self.integration = IntegrationCoordinator()
        self.executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_tasks)
        self._lock = Lock()
        self._next_sequence = 1
        self._tasks: dict[str, TaskRecord] = {}
        self._closed = False
        self._last_persist_at: dict[str, float] = {}
        self.memory = TaskMemoryStore(memory_path or self.repository / DEFAULT_MEMORY_FILE)
        self._restore_tasks()

    def set_event_callback(self, callback: TaskEventCallback | None) -> None:
        self.on_event = callback

    def submit(
        self,
        prompt: str,
        provider: str,
        model: str,
        reasoning: str,
        mode: str = "coding",
        topic: str | None = None,
        automatic_follow_up_prompt: str = "",
    ) -> TaskRecord:
        with self._lock:
            if self._closed:
                raise RuntimeError("Task coordinator is shut down.")
            sequence = self._next_sequence
            self._next_sequence += 1
            task_id = f"{sequence:03d}-{uuid.uuid4().hex[:8]}"
            cleaned_topic = topic.strip() if isinstance(topic, str) and topic.strip() else None
            record = TaskRecord(
                task_id,
                sequence,
                prompt,
                provider,
                model,
                reasoning,
                mode=mode,
                topic=cleaned_topic,
                automatic_follow_up_prompt=automatic_follow_up_prompt.strip(),
            )
            record.prompt_history = [prompt]
            record.chain_id = task_id
            record.memory_task_id = f"task-{task_id}"
            self._tasks[task_id] = record
            self._persist_task(record)
            record.future = self.executor.submit(self._run, record)
        self._notify(record, "queued", "Task queued.", "status")
        return record

    def has_active_sync_recovery(self, branch: str | None = None) -> bool:
        """Return whether a Sync conflict recovery is still in flight for this project."""
        with self._lock:
            return self._has_active_sync_recovery_locked(branch)

    def _has_active_sync_recovery_locked(self, branch: str | None = None) -> bool:
        terminal = {"proposed", "completed", "failed", "cancelled", "blocked"}
        for record in self._tasks.values():
            if not record.sync_recovery or record.status in terminal:
                continue
            if branch is not None and record.sync_operating_branch != branch:
                continue
            return True
        return False

    def _cleanup_orphaned_sync_recoveries_locked(self, branch: str) -> None:
        """Force-remove leftover sync worktrees from interrupted recoveries for ``branch``."""
        for record in list(self._tasks.values()):
            if (
                not record.sync_recovery
                or record.sync_operating_branch != branch
                or record.status not in {"failed", "cancelled"}
            ):
                continue
            worktree = record.worktree_path or (record.context.path if record.context else None)
            if worktree is None or not worktree.exists():
                continue
            try:
                abort_sync_merge(
                    self.repository,
                    worktree,
                    temp_branch_name=record.sync_temp_branch_name,
                )
            except Exception as error:
                LOGGER.warning(
                    "Could not clean orphaned sync worktree task=%s error=%s",
                    record.task_id,
                    error,
                )
            record.context = None
            record.worktree_path = None
            self._persist_task(record)

    def submit_sync_recovery(
        self,
        *,
        provider: str,
        model: str,
        reasoning: str,
        operating_branch: str,
        remote: str,
        worktree_path: Path,
        conflicted_paths: tuple[str, ...],
        used_temp_branch: bool,
        temp_branch_name: str | None,
        merge_failure: str,
        attempt_limit: int = 3,
        base_commit: str = "",
    ) -> TaskRecord:
        """Attach plan-mode recovery to a preserved Sync conflict worktree."""
        prompt = build_sync_conflict_plan_prompt(operating_branch, conflicted_paths, merge_failure)
        with self._lock:
            if self._closed:
                raise RuntimeError("Task coordinator is shut down.")
            if self._has_active_sync_recovery_locked(operating_branch):
                raise RuntimeError(
                    f"Sync conflict recovery is already active for {operating_branch}."
                )
            self._cleanup_orphaned_sync_recoveries_locked(operating_branch)
            sequence = self._next_sequence
            self._next_sequence += 1
            task_id = f"{sequence:03d}-{uuid.uuid4().hex[:8]}"
            branch_name = temp_branch_name or operating_branch
            if not base_commit:
                try:
                    base_commit = GitWorktreeManager(
                        self.repository,
                        self.settings.primary_branch,
                        self.settings.worktree_root,
                    ).git_output(["rev-parse", f"refs/heads/{operating_branch}"])
                except GitWorktreeError:
                    base_commit = ""
            context = WorktreeContext(
                self.repository,
                task_id,
                base_commit,
                branch_name,
                worktree_path,
            )
            record = TaskRecord(
                task_id,
                sequence,
                prompt,
                provider,
                model,
                reasoning,
                mode="plan",
                branch_name=branch_name,
                worktree_path=worktree_path,
                context=context,
                sync_recovery=True,
                sync_operating_branch=operating_branch,
                sync_remote=remote,
                sync_used_temp_branch=used_temp_branch,
                sync_temp_branch_name=temp_branch_name,
                sync_conflict_attempt_limit=max(1, attempt_limit),
                sync_conflicted_paths=conflicted_paths,
            )
            record.prompt_history = [prompt]
            record.memory_task_id = worktree_path.name
            self._tasks[task_id] = record
            self._persist_task(record)
            record.future = self.executor.submit(self._run, record)
        self._notify(record, "queued", "Sync conflict recovery queued.", "status")
        return record

    def answer_plan(self, task_id: str, answers: dict[str, str]) -> bool:
        """Send selected plan answers back to the planning agent for confirmation."""
        with self._lock:
            record = self._tasks.get(task_id)
            if (
                record is None
                or record.mode != "plan"
                or record.plan_confirmed
                or record.status not in {"proposed", "completed", "awaiting_answers"}
            ):
                return False
            question_ids = {question.question_id for question in record.plan_questions}
            if not question_ids.issubset(answers):
                return False
            valid_answers = {
                question.question_id: answer
                for question in record.plan_questions
                for answer in [answers.get(question.question_id)]
                if is_valid_plan_answer(question, answer)
            }
            if question_ids - valid_answers.keys():
                return False
            record.plan_answers.update(valid_answers)
            for question in record.plan_questions:
                answer_id = valid_answers.get(question.question_id)
                if answer_id is None:
                    continue
                custom_text = custom_answer_text(answer_id)
                if custom_text is not None:
                    answer_label = f"Custom answer: {custom_text}"
                else:
                    option = next(option for option in question.options if option.option_id == answer_id)
                    answer_label = option.label
                record.plan_answer_details[question.question_id] = f"{question.text}: {answer_label}"
            record.plan_followup_prompt = build_plan_followup_prompt(
                record.prompt, record.plan_text, record.plan_questions, record.plan_answers
            )
            record.prompt_history.append(record.plan_followup_prompt)
            record.status = "queued"
            record.phase = "Queued (reviewing answers)"
            record.error = None
            record.plan_error = None
            self._persist_task(record)
            record.future = self.executor.submit(self._run, record)
            LOGGER.info("Plan answers queued task=%s answer_ids=%s", record.task_id, sorted(valid_answers))
        self._notify(record, "queued", "Plan answers queued for agent confirmation.", "status")
        return True

    def clarify_plan_question(self, task_id: str, question_id: str, user_question: str) -> bool:
        """Ask a side-channel clarification about one plan question without plan follow-up."""
        cleaned = user_question.strip()
        if not cleaned:
            return False
        with self._lock:
            if self._closed:
                return False
            record = self._tasks.get(task_id)
            if (
                record is None
                or record.mode != "plan"
                or record.status not in {"awaiting_answers", "proposed", "completed", "questioning"}
            ):
                return False
            question = next(
                (item for item in record.plan_questions if item.question_id == question_id),
                None,
            )
            if question is None:
                return False
            clarification = PlanClarification(
                clarification_id=uuid.uuid4().hex[:10],
                question_id=question_id,
                user_question=cleaned,
                status="queued",
            )
            record.plan_clarifications.setdefault(question_id, []).append(clarification)
            self.executor.submit(self._run_clarification, record.task_id, clarification.clarification_id)
            LOGGER.info(
                "Plan clarification queued task=%s question=%s clarification=%s",
                record.task_id,
                question_id,
                clarification.clarification_id,
            )
        self._notify(record, "clarification", "Clarification queued.", "status")
        return True

    def implement_plan(self, task_id: str) -> TaskRecord | None:
        """Create a new coding task from a confirmed plan review."""
        with self._lock:
            record = self._tasks.get(task_id)
            if (
                record is None
                or record.mode != "plan"
                or record.status not in {"proposed", "completed"}
                or not record.plan_confirmed
                or record.plan_implemented
                or record.sync_recovery
            ):
                return None
            if any(question.question_id not in record.plan_answers for question in record.plan_questions):
                return None
            # Claim the one-shot transition before submitting so concurrent UI
            # events cannot create more than one coding task.
            record.plan_implemented = True
        try:
            coding_record = self.submit(
                build_implementation_prompt(
                    record.prompt,
                    record.plan_text,
                    record.plan_answers,
                    record.plan_answer_details,
                ),
                record.provider,
                record.model,
                record.reasoning,
                mode="coding",
                topic=record.topic,
            )
        except Exception:
            with self._lock:
                record.plan_implemented = False
            raise
        self._discard_plan_worktree(record)
        return coding_record

    def _queue_sync_conflict_coding(self, record: TaskRecord) -> bool:
        """Auto-start coding in the same conflict worktree after a confirmed sync plan."""
        with self._lock:
            if (
                not record.sync_recovery
                or not record.plan_confirmed
                or record.plan_implemented
                or record.context is None
                or self._closed
            ):
                return False
            record.plan_implemented = True
            record.mode = "coding"
            record.status = "queued"
            record.phase = "Queued (resolving sync conflicts)"
            record.error = None
            record.finished_at = None
            self._persist_task(record)
            record.future = self.executor.submit(self._run, record)
        self._notify(record, "queued", "Sync conflict coding queued in the preserved worktree.", "status")
        return True

    def tasks(self) -> tuple[TaskRecord, ...]:
        with self._lock:
            return tuple(sorted(self._tasks.values(), key=lambda task: task.submission_sequence))

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._tasks.get(task_id)

    def shutdown(self) -> bool:
        with self._lock:
            if self._closed:
                return True
            self._closed = True
            self.integration.shutdown()
            for record in self._tasks.values():
                if record.status in INTERRUPTIBLE_STATUSES:
                    record.status = "paused"
                    record.phase = "Paused"
                    record.error = "Daedalus was closed while this task was active; resume to continue."
                    self._persist_task(record)
                    record.control.request_pause()
                    LOGGER.info("Shutdown paused task=%s status=%s", record.task_id, record.status)
        # Do not hold Textual's unmount path indefinitely. Active agent process
        # groups receive cancellation above and the executor will finish as they
        # return; any survivor is recorded for inspection in the debug log.
        self.executor.shutdown(wait=False, cancel_futures=True)
        deadline = time.monotonic() + self.settings.shutdown_grace_seconds
        pending: list[TaskRecord] = []
        while time.monotonic() < deadline:
            pending = [
                record
                for record in self._tasks.values()
                if record.future is not None and not record.future.done()
            ]
            if not pending:
                LOGGER.info("Coordinator shutdown completed repository=%s", self.repository)
                return True
            time.sleep(0.05)
        pending_ids = ", ".join(record.task_id for record in pending)
        LOGGER.error("Coordinator shutdown grace period expired pending_tasks=%s", pending_ids or "unknown")
        return False

    def pause(self, task_id: str) -> bool:
        record = self.get(task_id)
        if record is None or record.status in {"proposed", "completed", "failed", "blocked", "paused", "cancelled"}:
            return False
        if record.status == "questioning":
            return False
        if record.status == "queued" and record.future is not None and record.future.cancel():
            record.status = "paused"
            record.phase = "Paused"
            record.finished_at = time.time()
            self._persist_task(record)
            self._notify(record, "paused", "Task paused before execution.", "status")
            return True
        record.control.request_pause()
        record.phase = "Pausing"
        self._notify(record, "pausing", "Stopping the active agent and preserving progress.", "status")
        return True

    def resume(self, task_id: str, notes: str = "") -> bool:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None or record.status != "paused" or self._closed:
                return False
            record.control.clear_pause()
            record.status = "queued"
            record.phase = "Queued (resuming)"
            record.error = None
            record.finished_at = None
            if notes.strip():
                record.resume_notes.append(notes.strip())
            self._persist_task(record)
            record.future = self.executor.submit(self._run, record)
        self._notify(record, "queued", "Task queued to resume in its existing worktree.", "status")
        return True

    def continue_plan(self, task_id: str, notes: str = "") -> bool:
        """Run another planning pass while keeping the task in questioning."""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None or record.status != "questioning" or self._closed:
                return False
            planning_output = "\n\n".join(message for message in record.messages if message.strip()).strip()
            if planning_output:
                record.resume_notes.append("Review this previous planning output:\n" + planning_output)
            if notes.strip():
                record.resume_notes.append(notes.strip())
            record.status = "queued"
            record.phase = "Queued (continuing plan)"
            record.error = None
            self._persist_task(record)
            record.future = self.executor.submit(self._run, record)
        self._notify(record, "queued", "Task queued for another planning pass.", "status")
        return True

    def start_coding(self, task_id: str, notes: str = "") -> bool:
        """Promote a reviewed plan into the normal coding and verification route."""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None or record.status != "questioning" or self._closed:
                return False
            planning_output = "\n\n".join(message for message in record.messages if message.strip()).strip()
            if planning_output:
                record.resume_notes.append(
                    "Carry this planning context into implementation:\n" + planning_output
                )
            if notes.strip():
                record.resume_notes.append(notes.strip())
            record.mode = "coding"
            record.status = "queued"
            record.phase = "Queued (starting coding)"
            record.error = None
            self._persist_task(record)
            record.future = self.executor.submit(self._run, record)
        self._notify(record, "queued", "Task queued to start coding from its plan.", "status")
        return True

    def retry(self, task_id: str) -> bool:
        """Retry a failed agent request after connectivity or service recovery."""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None or record.status != "failed" or self._closed:
                return False
            visible_output = "\n\n".join(message.strip() for message in record.messages if message.strip())
            record.retry_output_context = (
                "Previous visible AI output from the failed attempt:\n" + visible_output
                if visible_output
                else None
            )
            record.control = AgentControl()
            record.status = "queued"
            record.phase = "Queued (retrying)"
            record.error = None
            record.finished_at = None
            self._persist_task(record)
            record.future = self.executor.submit(self._run, record)
        self._notify(record, "queued", "Task queued for retry.", "status")
        return True

    def follow_up(self, task_id: str, prompt: str) -> TaskRecord | None:
        """Submit a distinct task that continues a completed or failed chain."""
        source = self.get(task_id)
        if source is None or source.status not in {"completed", "failed"} or not prompt.strip():
            return None
        with self._lock:
            if self._closed:
                return None
            record = self._create_follow_up_locked(source, prompt)
        self._notify(record, "queued", "Follow-up task queued.", "status")
        return record

    def cancel(self, task_id: str) -> bool:
        record = self.get(task_id)
        if record is None or record.status in {"blocked", "cancelled"}:
            return False
        if record.sync_recovery and record.status == "failed":
            return self._cancel_sync_recovery(record)
        if record.status == "failed":
            return False
        if (
            record.sync_recovery
            and record.status in {"proposed", "completed"}
            and not record.plan_implemented
        ):
            return self._cancel_sync_recovery(record)
        if record.status in {"proposed", "completed"}:
            return False
        if record.sync_recovery and record.status in {
            "paused",
            "questioning",
            "awaiting_answers",
            "queued",
        }:
            return self._cancel_sync_recovery(record)
        if record.status == "paused":
            if record.context is not None:
                try:
                    GitWorktreeManager(
                        self.repository,
                        self.settings.primary_branch,
                        self.settings.worktree_root,
                    ).remove_cancelled(record.context)
                except GitWorktreeError as error:
                    record.status = "failed"
                    record.phase = "Failed"
                    record.error = f"Cancelled task cleanup failed: {error}"
                    self._persist_task(record)
                    self._notify(record, "failed", record.error, "error")
                    return False
            record.status = "cancelled"
            record.phase = "Cancelled"
            record.error = "Task cancelled and its worktree was removed."
            record.finished_at = time.time()
            self._persist_task(record)
            self._notify(record, "cancelled", record.error, "error")
            return True
        if record.status == "questioning":
            if record.context is not None:
                try:
                    GitWorktreeManager(
                        self.repository,
                        self.settings.primary_branch,
                        self.settings.worktree_root,
                    ).remove_cancelled(record.context)
                except GitWorktreeError as error:
                    record.status = "failed"
                    record.phase = "Failed"
                    record.error = f"Cancelled plan cleanup failed: {error}"
                    self._persist_task(record)
                    self._notify(record, "failed", record.error, "error")
                    return False
            record.status = "cancelled"
            record.phase = "Cancelled"
            record.error = "Plan cancelled and its worktree was removed."
            record.finished_at = time.time()
            self._persist_task(record)
            self._notify(record, "cancelled", record.error, "error")
            return True
        if record.status == "queued" and record.future is not None and record.future.cancel():
            if record.sync_recovery:
                return self._cancel_sync_recovery(record)
            record.status = "cancelled"
            record.phase = "Cancelled"
            record.error = "Task cancelled before execution."
            record.finished_at = time.time()
            self._persist_task(record)
            self._notify(record, "cancelled", record.error, "error")
            return True
        record.control.request_cancel()
        record.phase = "Cancelling"
        self._notify(record, "cancelling", "Stopping the active agent and removing its worktree.", "status")
        return True

    def _cancel_sync_recovery(self, record: TaskRecord) -> bool:
        """Abort the preserved sync merge and remove its worktree/temp branch."""
        if record.future is not None and not record.future.done():
            record.control.request_cancel()
            if record.status == "queued":
                record.future.cancel()
        worktree = record.worktree_path or (record.context.path if record.context else None)
        if worktree is not None:
            try:
                abort_sync_merge(
                    self.repository,
                    worktree,
                    temp_branch_name=record.sync_temp_branch_name,
                )
            except Exception as error:  # Keep cancel path resilient for inspectable leftovers.
                record.status = "failed"
                record.phase = "Failed"
                record.error = f"Sync recovery cancel cleanup failed: {error}"
                self._persist_task(record)
                self._notify(record, "failed", record.error, "error")
                return False
        record.context = None
        record.worktree_path = None
        record.status = "cancelled"
        record.phase = "Cancelled"
        record.error = "Sync conflict recovery cancelled; merge aborted."
        record.finished_at = time.time()
        self._persist_task(record)
        self._notify(record, "cancelled", record.error, "error")
        return True

    def _run_clarification(self, task_id: str, clarification_id: str) -> None:
        """Run an ask-mode clarification that does not mutate plan conversation state."""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None or self._closed:
                return
            clarification = self._find_clarification(record, clarification_id)
            if clarification is None:
                return
            question = next(
                (item for item in record.plan_questions if item.question_id == clarification.question_id),
                None,
            )
            if question is None:
                clarification.status = "failed"
                clarification.error = "That plan question is no longer available."
                self._notify(record, "clarification", clarification.error, "error")
                return
            clarification.status = "running"
            clarification.error = None
            prompt = build_plan_clarification_prompt(
                record.prompt,
                record.plan_text,
                question,
                clarification.user_question,
            )
            provider = record.provider
            model = record.model
            reasoning = record.reasoning
            topic_slug = record.topic
        self._notify(record, "clarification", "Asking for clarification.", "status")

        answer_chunks: list[str] = []

        def on_event(_phase: str, message: str, kind: str = "status") -> None:
            # Clarifications stay off the plan transcript and do not change task status.
            if kind == "message" and message:
                answer_chunks.append(message)

        orchestrator = self._orchestrator(on_event)
        try:
            result = orchestrator.run(
                prompt,
                provider,
                model,
                reasoning,
                task_id=f"{task_id}-clarify-{clarification_id}",
                mode="ask",
                topic_slug=topic_slug,
            )
        except Exception as error:  # Keep clarification failures isolated from the plan task.
            log_exception(
                f"Plan clarification crashed task={task_id} clarification={clarification_id}",
                error,
            )
            with self._lock:
                clarification = self._find_clarification(record, clarification_id)
                if clarification is None:
                    return
                clarification.status = "failed"
                clarification.error = str(error)
            self._notify(record, "clarification", str(error), "error")
            return

        with self._lock:
            clarification = self._find_clarification(record, clarification_id)
            if clarification is None:
                return
            if result.succeeded:
                clarification.status = "completed"
                clarification.answer = "\n\n".join(
                    chunk.strip() for chunk in answer_chunks if chunk.strip()
                )
                clarification.error = None
                if result.tokens_consumed:
                    record.tokens_consumed += result.tokens_consumed
            else:
                clarification.status = "failed"
                clarification.error = result.error or "Clarification failed."
            self._persist_task(record)
            notify_kind = "status" if clarification.status == "completed" else "error"
            notify_message = (
                clarification.answer
                if clarification.status == "completed"
                else (clarification.error or "")
            )
            clarification_status = clarification.status
        self._notify(record, "clarification", notify_message, notify_kind)
        LOGGER.info(
            "Plan clarification finished task=%s clarification=%s status=%s",
            task_id,
            clarification_id,
            clarification_status,
        )

    @staticmethod
    def _find_clarification(record: TaskRecord, clarification_id: str) -> PlanClarification | None:
        for items in record.plan_clarifications.values():
            for clarification in items:
                if clarification.clarification_id == clarification_id:
                    return clarification
        return None

    def _orchestrator(self, on_event: Callable[..., None]) -> LocalOrchestrator:
        """Construct an orchestrator with the project environment when configured."""
        options: dict[str, object] = {"integration_gate": self.integration.run_when_ready}
        if self.environment_path is not None:
            options["environment_path"] = self.environment_path
        if self.migration_push_lock is not None:
            options["migration_push_lock"] = self.migration_push_lock
        return LocalOrchestrator(
            self.repository,
            self.runner,
            self.settings,
            on_event,
            **options,
        )

    def _run(self, record: TaskRecord) -> None:
        LOGGER.info("Task worker started task=%s mode=%s", record.task_id, record.mode)
        record.started_at = time.time()
        self._persist_task(record)
        message_start = len(record.messages)
        if record.mode == "plan":
            record.plan_final_output = ""
        if record.mode == "plan" and record.plan_followup_prompt and record.provider == "cursor":
            # Cursor streams deltas by extending the last stored message. Give a
            # follow-up response its own transcript slot before starting it.
            record.messages.append("")
        prompt = record.plan_followup_prompt or record.retry_prompt or record.prompt
        record.retry_prompt = prompt
        record.plan_followup_prompt = None
        resume_notes = tuple(record.resume_notes)
        if record.retry_output_context:
            resume_notes += (record.retry_output_context,)
        record.retry_output_context = None
        orchestrator = self._orchestrator(
            lambda phase, message, kind="status": self._handle_event(record, phase, message, kind)
        )
        try:
            result = orchestrator.run(
                prompt,
                record.provider,
                record.model,
                record.reasoning,
                task_id=record.task_id,
                submission_sequence=record.submission_sequence,
                mode=record.mode,
                control=record.control,
                existing_context=record.context,
                resume_notes=resume_notes,
                resume_from=record.resume_from,
                topic_slug=record.topic,
                sync_recovery=record.sync_recovery,
                sync_operating_branch=record.sync_operating_branch or None,
                sync_remote=record.sync_remote,
                sync_used_temp_branch=record.sync_used_temp_branch,
                sync_temp_branch_name=record.sync_temp_branch_name,
                sync_conflict_attempt_limit=record.sync_conflict_attempt_limit,
                sync_plan_text=record.plan_text,
                sync_plan_answers=dict(record.plan_answers),
                sync_plan_answer_details=dict(record.plan_answer_details),
            )
        except Exception as error:  # Keep one unexpected task failure isolated from the pool.
            log_exception(f"Task worker crashed task={record.task_id}", error)
            record.finished_at = time.time()
            record.status = "failed"
            record.phase = "Failed"
            record.error = str(error)
            self._persist_task(record)
            self._notify(record, "failed", str(error), "error")
            return
        record.finished_at = time.time()
        record.branch_name = result.branch_name or record.branch_name
        record.worktree_path = result.worktree or record.worktree_path
        record.context = result.context or record.context
        if result.succeeded:
            record.tokens_consumed += result.tokens_consumed
        if result.awaiting_plan:
            if record.mode == "plan":
                self._update_plan_state(record, record.messages[message_start:])
            if record.plan_confirmed:
                record.status = "proposed"
                record.phase = "Proposed"
            elif record.plan_questions:
                record.status = "awaiting_answers"
                record.phase = "Questions"
            else:
                # Keep malformed or prose-only responses in the selectable
                # planning loop so the user can request another pass.
                record.status = "questioning"
                record.phase = "Questioning"
            record.error = None
            if record.plan_error:
                record.error = record.plan_error
            self._persist_task(record)
            event_phase = {
                "proposed": "proposed",
                "awaiting_answers": "questions",
            }.get(record.status, "questioning")
            self._notify(
                record,
                event_phase,
                "Plan ready for review." if record.status != "proposed" else "Plan proposed.",
                "status",
            )
            LOGGER.info("Task worker finished task=%s status=%s", record.task_id, record.status)
            if record.sync_recovery and record.plan_confirmed and not record.plan_implemented:
                self._queue_sync_conflict_coding(record)
            return
        if result.paused:
            record.status = "paused"
            record.phase = "Paused"
            record.error = None
            self._persist_task(record)
            self._notify(record, "paused", "Task paused; progress preserved.", "status")
            LOGGER.info("Task worker finished task=%s status=%s", record.task_id, record.status)
            return
        if result.cancelled:
            record.status = "cancelled"
            record.phase = "Cancelled"
            record.error = result.error or "Task cancelled."
            if record.sync_recovery:
                record.context = None
                record.worktree_path = None
            self._persist_task(record)
            self._notify(record, "cancelled", record.error, "error")
            LOGGER.info("Task worker finished task=%s status=%s", record.task_id, record.status)
            return
        if result.succeeded:
            if record.mode == "plan":
                self._update_plan_state(record, record.messages[message_start:])
            if record.mode == "plan" and not record.plan_confirmed:
                if record.plan_questions:
                    record.status = "awaiting_answers"
                    record.phase = "Questions"
                else:
                    record.status = "questioning"
                    record.phase = "Questioning"
            else:
                record.status = "proposed" if record.mode == "plan" else "completed"
                record.phase = "Proposed" if record.mode == "plan" else "Completed"
                record.resume_from = None
                if record.sync_recovery and record.mode == "coding":
                    record.context = None
                    record.worktree_path = None
        else:
            record.status = "failed"
            record.phase = "Failed"
            record.error = record.error or result.error or "Task failed."
        self._persist_task(record)
        self._notify(
            record,
            "questions" if result.succeeded and record.mode == "plan" and record.plan_questions and not record.plan_confirmed else
            ("proposed" if result.succeeded and record.mode == "plan" else "completed" if result.succeeded else "failed"),
            "",
            "status",
        )
        LOGGER.info("Task worker finished task=%s status=%s", record.task_id, record.status)
        if (
            result.succeeded
            and record.sync_recovery
            and record.mode == "plan"
            and record.plan_confirmed
            and not record.plan_implemented
        ):
            self._queue_sync_conflict_coding(record)
        elif result.succeeded and record.status == "completed" and record.automatic_follow_up_prompt:
            self._queue_automatic_follow_up(record)

    def _queue_automatic_follow_up(self, source: TaskRecord) -> TaskRecord | None:
        """Create a prepared successor only after its parent completes successfully."""
        prompt = source.automatic_follow_up_prompt.strip()
        if not prompt or source.status != "completed" or source.automatic_follow_up_task_id:
            return None
        with self._lock:
            if self._closed or source.automatic_follow_up_task_id:
                return None
            existing = next(
                (item for item in self._tasks.values() if item.parent_task_id == source.task_id),
                None,
            )
            if existing is not None:
                source.automatic_follow_up_task_id = existing.task_id
                self._persist_task(source)
                return existing
            next_record = self._create_follow_up_locked(source, prompt)
            source.automatic_follow_up_task_id = next_record.task_id
            self._persist_task(source)
        self._notify(next_record, "queued", "Automatic follow-up task queued after successful completion.", "status")
        return next_record

    def _create_follow_up_locked(self, source: TaskRecord, prompt: str) -> TaskRecord:
        chain_id = source.chain_id or source.task_id
        chain = sorted(
            (
                item for item in self._tasks.values()
                if (item.chain_id or item.task_id) == chain_id
                and item.submission_sequence <= source.submission_sequence
            ),
            key=lambda item: item.submission_sequence,
        )
        turns: list[str] = []
        for item in chain:
            turns.append(f"User: {item.prompt}")
            response = "\n\n".join(message.strip() for message in item.messages if message.strip())
            if response:
                turns.append(f"Assistant: {response}")
        context = "Conversation so far:\n" + "\n\n".join(turns)
        sequence = self._next_sequence
        self._next_sequence += 1
        new_id = f"{sequence:03d}-{uuid.uuid4().hex[:8]}"
        record = TaskRecord(
            new_id, sequence, prompt.strip(), source.provider, source.model,
            source.reasoning, mode=source.mode, topic=source.topic,
            chain_id=chain_id, parent_task_id=source.task_id,
        )
        record.prompt_history = [record.prompt]
        record.resume_notes.append(context)
        record.conversation_context = context
        record.memory_task_id = f"task-{new_id}"
        self._tasks[new_id] = record
        self._persist_task(record)
        record.future = self.executor.submit(self._run, record)
        return record

    def _update_plan_state(self, record: TaskRecord, new_messages: list[str]) -> bool:
        parsed = self._parse_plan_messages(new_messages, record.plan_final_output)
        if not parsed.valid:
            # A protocol error after the user answered questions must not erase
            # the last usable plan or make the choices impossible to resubmit.
            record.plan_confirmed = False
            record.plan_error = parsed.error
            record.error = parsed.error
            LOGGER.warning(
                "Rejected invalid plan payload task=%s message_count=%d error=%s",
                record.task_id,
                len(new_messages),
                parsed.error,
            )
            return False
        record.plan_text = parsed.plan
        record.plan_questions = parsed.questions
        record.plan_confirmed = parsed.valid and parsed.no_more_questions and not parsed.questions
        record.plan_error = None
        record.error = None
        # An agent may revise a question while retaining its id. Do not mount a
        # Select with the now-invalid old value; retain decisions for questions
        # that disappeared because they remain useful implementation context.
        for question in parsed.questions:
            answer_id = record.plan_answers.get(question.question_id)
            if answer_id is not None and not is_valid_plan_answer(question, answer_id):
                record.plan_answers.pop(question.question_id, None)
                record.plan_answer_details.pop(question.question_id, None)
        valid_question_ids = {question.question_id for question in parsed.questions}
        record.plan_clarifications = {
            question_id: clarifications
            for question_id, clarifications in record.plan_clarifications.items()
            if question_id in valid_question_ids
        }
        return True

    @staticmethod
    def _parse_plan_messages(new_messages: list[str], final_output: str = ""):
        """Parse plan JSON from one turn without letting join separators break it.

        Cursor's final result is complete and authoritative for plan-mode
        requests, so parse it before the streamed fragments. All providers
        retain the existing join-and-chunk fallback for versions that omit a
        terminal result or split a payload across messages.
        """
        last_failure = None
        if final_output.strip():
            parsed = parse_plan_response(final_output)
            if parsed.valid:
                return parsed
            last_failure = parsed

        candidates: list[str] = []
        blank_joined = "\n\n".join(new_messages).strip()
        contiguous = "".join(new_messages).strip()
        if blank_joined:
            candidates.append(blank_joined)
        if contiguous and contiguous not in candidates:
            candidates.append(contiguous)
        for message in reversed(new_messages):
            cleaned = message.strip()
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)

        for response in candidates:
            parsed = parse_plan_response(response)
            if parsed.valid:
                return parsed
            last_failure = parsed
        return last_failure or parse_plan_response("")

    def _discard_plan_worktree(self, record: TaskRecord) -> None:
        """Remove the clean, read-only planning worktree after coding is queued."""
        if record.context is None:
            return
        try:
            manager = GitWorktreeManager(
                self.repository,
                self.settings.primary_branch,
                self.settings.worktree_root,
            )
            manager.remove_successful(record.context)
        except GitWorktreeError as error:
            # The coding task is already queued; a failed cleanup must not
            # prevent it from running or hide the planning result.
            LOGGER.warning("Could not remove plan worktree task=%s error=%s", record.task_id, error)
            return
        LOGGER.info("Removed clean plan worktree task=%s path=%s", record.task_id, record.context.path)
        record.context = None
        record.worktree_path = None
        self._persist_task(record)

    def _handle_event(self, record: TaskRecord, phase: str, message: str, kind: str) -> None:
        if phase != "plan_result":
            record.phase = phase.replace("_", " ").capitalize()
        status = {
            "worktree": "running",
            "planning": "planning",
            "questioning": "questioning",
            "agent": "running",
            "verification": "verifying",
            "migrations": "verifying",
            "repairing": "verifying",
            "ready": "ready",
            "integration": "integrating",
            "resolving": "resolving",
            "proposed": "proposed",
            "completed": "completed",
            "failed": "failed",
            "paused": "paused",
            "cancelled": "cancelled",
        }.get(phase)
        if status:
            record.status = status
        if kind == "message" and message:
            if phase == "plan_result":
                # Keep the complete terminal result as its own durable
                # transcript entry; never append it to Cursor stream deltas.
                record.messages.append(message)
                record.plan_final_output = message
            elif record.provider == "cursor" and record.messages:
                record.messages[-1] += message
            else:
                record.messages.append(message)
        if kind == "error" and message:
            record.error = message
        if phase in {"ready", "integration", "resolving"}:
            record.resume_from = "integration"
        if phase == "worktree" and message.startswith("Created "):
            branch, _, worktree = message.removeprefix("Created ").rstrip(".").partition(" at ")
            if branch and worktree:
                record.branch_name = branch
                record.worktree_path = Path(worktree)
        self._persist_task(record, force=kind != "message")
        self._notify(record, phase, message, kind)

    def _persist_task(self, record: TaskRecord, *, force: bool = True) -> None:
        """Persist task state, coalescing high-frequency streamed messages."""
        now = time.monotonic()
        if not force and now - self._last_persist_at.get(record.task_id, 0.0) < 0.25:
            return
        task_id = record.worktree_path.name if record.worktree_path is not None else f"task-{record.task_id}"
        previous_task_id = record.memory_task_id
        try:
            self.memory.record_task(
                task_id,
                record.prompt,
                record.provider,
                None if record.provider == "cursor" else record.model or None,
                None if record.provider == "cursor" else record.reasoning or None,
                record.mode,
                record.status,
                record.messages,
                record.error,
                previous_task_id=previous_task_id,
                submitted_at=record.submitted_at,
                tokens=record.tokens_consumed,
                project=self.repository,
                prompt_history=tuple(record.prompt_history or (record.prompt,)),
                chain_id=record.chain_id,
                parent_task_id=record.parent_task_id,
                automatic_follow_up_prompt=record.automatic_follow_up_prompt or None,
                automatic_follow_up_task_id=record.automatic_follow_up_task_id,
                branch_name=record.context.branch_name if record.context is not None else None,
                worktree_path=record.context.path if record.context is not None else None,
                base_commit=record.context.base_commit if record.context is not None else None,
                resume_from=record.resume_from,
                topic=record.topic,
                sync_recovery=record.sync_recovery,
                sync_operating_branch=record.sync_operating_branch or None,
                sync_remote=record.sync_remote or None,
                sync_used_temp_branch=record.sync_used_temp_branch,
                sync_temp_branch_name=record.sync_temp_branch_name,
                sync_conflict_attempt_limit=record.sync_conflict_attempt_limit,
            )
        except (OSError, ValueError) as error:
            # Persistent task history must never change orchestration behavior.
            LOGGER.warning("Could not persist task task=%s error=%s", record.task_id, error)
            return
        record.memory_task_id = task_id
        self._last_persist_at[record.task_id] = now

    def _restore_tasks(self) -> None:
        """Rehydrate this project's persisted tasks after a TUI restart."""
        try:
            snapshots = self.memory.get_tasks()
        except (OSError, ValueError) as error:
            LOGGER.warning("Could not restore persisted tasks for project=%s error=%s", self.repository, error)
            return

        maximum_sequence = 0
        for memory_task_id, snapshot in snapshots.items():
            if snapshot.get("project") != str(self.repository):
                continue
            prompt = snapshot.get("prompt")
            if not isinstance(prompt, str) or not prompt:
                continue
            task_id = snapshot.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                task_id = memory_task_id.removeprefix("task-")
            sequence = _snapshot_sequence(snapshot, task_id)
            maximum_sequence = max(maximum_sequence, sequence)
            state = snapshot.get("state")
            if state not in TASK_STATUSES:
                continue
            status = str(state)
            error = snapshot.get("error") if isinstance(snapshot.get("error"), str) else None
            resume_from = snapshot.get("resume_from") if isinstance(snapshot.get("resume_from"), str) else None
            if resume_from not in {None, "integration"}:
                resume_from = None
            if status in {"ready", "integrating", "resolving"}:
                resume_from = "integration"
            if status in INTERRUPTIBLE_STATUSES:
                status = "paused"
                error = error or "Daedalus was closed while this task was active; resume to continue."
            sync_recovery = bool(snapshot.get("sync_recovery"))
            if sync_recovery and status not in {"proposed", "completed", "failed", "cancelled", "blocked"}:
                # Cross-session auto-resume of mid-merge sync worktrees is out of scope.
                status = "failed"
                error = (
                    error
                    or "Sync conflict recovery was interrupted; cancel or start Sync again to clean up."
                )
            topic_value = snapshot.get("topic")
            topic = topic_value.strip() if isinstance(topic_value, str) and topic_value.strip() else None
            branch_name = snapshot.get("branch_name")
            if not isinstance(branch_name, str) or not branch_name:
                branch_name = f"agent/task-{task_id}"
            worktree_path = _snapshot_path(snapshot.get("worktree_path"))
            if worktree_path is None:
                candidate = (
                    self.repository.parent
                    / self.settings.worktree_root
                    / self.repository.name
                    / f"task-{task_id}"
                )
                if candidate.exists():
                    worktree_path = candidate
            base_commit = snapshot.get("base_commit")
            if not isinstance(base_commit, str):
                base_commit = ""
            context = None
            if worktree_path is not None and worktree_path.exists():
                context = WorktreeContext(
                    self.repository,
                    task_id,
                    base_commit,
                    branch_name,
                    worktree_path,
                )
            sync_operating_branch = snapshot.get("sync_operating_branch")
            if not isinstance(sync_operating_branch, str):
                sync_operating_branch = ""
            sync_remote = snapshot.get("sync_remote")
            if not isinstance(sync_remote, str) or not sync_remote:
                sync_remote = "origin"
            sync_temp_branch_name = snapshot.get("sync_temp_branch_name")
            if not isinstance(sync_temp_branch_name, str) or not sync_temp_branch_name:
                sync_temp_branch_name = None
            attempt_limit = snapshot.get("sync_conflict_attempt_limit")
            try:
                sync_attempt_limit = max(1, int(attempt_limit)) if attempt_limit is not None else 3
            except (TypeError, ValueError):
                sync_attempt_limit = 3
            record = TaskRecord(
                task_id=task_id,
                submission_sequence=sequence,
                prompt=prompt,
                automatic_follow_up_prompt=(
                    snapshot.get("automatic_follow_up_prompt")
                    if isinstance(snapshot.get("automatic_follow_up_prompt"), str) else ""
                ),
                provider=str(snapshot.get("provider") or "codex"),
                model=str(snapshot.get("model") or ""),
                reasoning=str(snapshot.get("reasoning") or ""),
                mode=str(snapshot.get("mode") or "coding"),
                topic=topic,
                status=status,
                phase=_phase_for_status(status),
                branch_name=branch_name,
                worktree_path=worktree_path,
                messages=_string_list(snapshot.get("outputs")),
                error=error,
                tokens_consumed=_nonnegative_int(snapshot.get("tokens")),
                submitted_at=_snapshot_timestamp(snapshot.get("timestamp")),
                context=context,
                memory_task_id=memory_task_id,
                prompt_history=_string_list(snapshot.get("prompt_history")) or [prompt],
                chain_id=snapshot.get("chain_id") if isinstance(snapshot.get("chain_id"), str) else task_id,
                parent_task_id=snapshot.get("parent_task_id") if isinstance(snapshot.get("parent_task_id"), str) else None,
                automatic_follow_up_task_id=(
                    snapshot.get("automatic_follow_up_task_id")
                    if isinstance(snapshot.get("automatic_follow_up_task_id"), str) else None
                ),
                resume_from=resume_from,
                sync_recovery=sync_recovery,
                sync_operating_branch=sync_operating_branch,
                sync_remote=sync_remote,
                sync_used_temp_branch=bool(snapshot.get("sync_used_temp_branch")),
                sync_temp_branch_name=sync_temp_branch_name,
                sync_conflict_attempt_limit=sync_attempt_limit,
            )
            if record.mode == "plan":
                self._restore_plan_state(record)
            self._tasks[task_id] = record
        self._next_sequence = max(self._next_sequence, maximum_sequence + 1)

    @staticmethod
    def _restore_plan_state(record: TaskRecord) -> None:
        """Recover review questions from the last persisted plan response."""
        # Plan review state predates the persisted task snapshot schema. The
        # assistant output is still durable, so use the newest response that
        # can be parsed instead of leaving an awaiting-answers task unusable
        # after the TUI is restarted.
        for message in reversed(record.messages):
            parsed = parse_plan_response(message)
            if not parsed.valid:
                continue
            record.plan_text = parsed.plan
            record.plan_questions = parsed.questions
            record.plan_final_output = message
            record.plan_confirmed = parsed.no_more_questions and not parsed.questions
            record.plan_error = None
            return

    def _notify(self, record: TaskRecord, phase: str, message: str, kind: str) -> None:
        if self.on_event is not None:
            self.on_event(record, phase, message, kind)
