"""Concurrent task state and serialized local integration.

A task is one durable conversation. Each submitted user prompt is a turn, each
execution attempt for a turn is a run, and the coordinator keeps the logical
task identity stable across turns, retries, restarts, and replacement
worktrees.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from pathlib import Path
from threading import Condition, Lock
import time
import uuid
from typing import Callable

from .agent_runner import AgentControl, AgentRunner
from .conversation import (
    GENERATED_TURN,
    TASK_SCHEMA_VERSION,
    TaskRun,
    TaskTurn,
    USER_TURN,
    generate_task_title,
    new_run_id,
    new_turn_id,
)
from .debug_log import LOGGER, append_run_diagnostic, log_event, log_exception
from .git_worktree import GitWorktreeError, GitWorktreeManager, WorktreeContext
from .local_storage import LocalStorage, project_key
from .memory import DEFAULT_MEMORY_FILE, TaskMemoryStore
from .orchestrator import AgentStopped, LocalOrchestrator, OrchestrationResult, OrchestrationSettings
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
from .prompt_store import PromptStore, PromptStoreError
from .prompts import ConversationEntry, build_conversation_prompt


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
    "completed",
    "failed",
    "blocked",
    "paused",
    "cancelled",
    "interrupted",
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
#: Statuses with an executing (or about to execute) run. Only one run per task.
ACTIVE_RUN_STATUSES = frozenset(INTERRUPTIBLE_STATUSES)
#: Statuses from which a follow-up prompt may start another run.
CONTINUABLE_STATUSES = frozenset(
    {
        "completed",
        "failed",
        "blocked",
        "paused",
        "cancelled",
        "interrupted",
        "questioning",
        "awaiting_answers",
    }
)
STOPPING_PHASE = "Stopping"
DEFAULT_TITLE_LENGTH = 60
DEFAULT_CONTEXT_BUDGET = 24_000
DEFAULT_RUN_LOG_MAX_BYTES = 1_000_000


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
        "completed": "Completed",
        "failed": "Failed",
        "paused": "Paused",
        "cancelled": "Cancelled",
        "interrupted": "Interrupted",
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
    plan_answers: dict[str, str] = field(default_factory=dict)
    plan_answer_details: dict[str, str] = field(default_factory=dict)
    plan_clarifications: dict[str, list[PlanClarification]] = field(default_factory=dict)
    plan_confirmed: bool = False
    plan_implemented: bool = False
    plan_error: str | None = None
    prompt_history: list[str] = field(default_factory=list, repr=False, compare=False)
    plan_followup_prompt: str | None = field(default=None, repr=False, compare=False)
    retry_prompt: str | None = field(default=None, repr=False, compare=False)
    retry_output_context: str | None = field(default=None, repr=False, compare=False)
    # When coding and verification already succeeded, retries resume at integration.
    resume_from: str | None = None
    # --- conversation model ---------------------------------------------------
    title: str = ""
    turns: list[TaskTurn] = field(default_factory=list, repr=False, compare=False)
    runs: list[TaskRun] = field(default_factory=list, repr=False, compare=False)
    active_turn_id: str | None = field(default=None, repr=False, compare=False)
    active_run_id: str | None = field(default=None, repr=False, compare=False)
    # Each replacement worktree gets a unique execution suffix; the logical
    # task id (and therefore the title and inbox row) never changes.
    execution_count: int = field(default=1, repr=False, compare=False)
    execution_id: str | None = field(default=None, repr=False, compare=False)
    diagnostics_dir: Path | None = field(default=None, repr=False, compare=False)
    prompts_dir: Path | None = field(default=None, repr=False, compare=False)

    @property
    def display_title(self) -> str:
        return self.title or generate_task_title(self.prompt, fallback_id=self.task_id)

    @property
    def user_turns(self) -> list[TaskTurn]:
        return [turn for turn in self.turns if turn.is_user]

    @property
    def latest_user_turn(self) -> TaskTurn | None:
        user_turns = self.user_turns
        return user_turns[-1] if user_turns else None

    @property
    def active_turn(self) -> TaskTurn | None:
        return self.turn_by_id(self.active_turn_id) or self.latest_user_turn

    @property
    def active_run(self) -> TaskRun | None:
        return self.run_by_id(self.active_run_id)

    @property
    def run_active(self) -> bool:
        return self.status in ACTIVE_RUN_STATUSES

    @property
    def stopping(self) -> bool:
        return self.run_active and self.phase == STOPPING_PHASE

    def turn_by_id(self, turn_id: str | None) -> TaskTurn | None:
        if not turn_id:
            return None
        return next((turn for turn in self.turns if turn.turn_id == turn_id), None)

    def run_by_id(self, run_id: str | None) -> TaskRun | None:
        if not run_id:
            return None
        return next((run for run in self.runs if run.run_id == run_id), None)

    def run_messages(self, run: TaskRun) -> list[str]:
        end = run.message_end if run.message_end is not None else len(self.messages)
        return self.messages[run.message_start : max(run.message_start, end)]

    def response_text(self, run: TaskRun) -> str:
        return "\n\n".join(message for message in self.run_messages(run) if message.strip()).strip()

    def latest_response_text(self) -> str:
        for run in reversed(self.runs):
            text = self.response_text(run)
            if text:
                return text
        return "\n\n".join(message for message in self.messages if message.strip()).strip()


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

    def run_when_ready(
        self,
        sequence: int,
        operation: Callable[[], None],
        stop_check: Callable[[], str | None] | None = None,
    ) -> None:
        """Wait for the gate, then run ``operation``.

        ``stop_check`` returns a stop reason while the operation is still
        waiting. A stopped task leaves the queue immediately instead of
        staying stuck behind another task's integration, and the caller sees
        :class:`AgentStopped` so it can preserve its worktree.
        """
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
                reason = stop_check() if stop_check is not None else None
                if reason:
                    self._ready.remove(entry)
                    self._condition.notify_all()
                    raise AgentStopped(reason)
            if self._closed:
                self._ready.remove(entry)
                self._condition.notify_all()
                raise RuntimeError("Integration coordinator is shut down.")
            reason = stop_check() if stop_check is not None else None
            if reason:
                self._ready.remove(entry)
                self._condition.notify_all()
                raise AgentStopped(reason)
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
        prompt_store: PromptStore | None = None,
        storage: LocalStorage | None = None,
        title_length: int = DEFAULT_TITLE_LENGTH,
        context_budget_chars: int = DEFAULT_CONTEXT_BUDGET,
        run_log_max_bytes: int = DEFAULT_RUN_LOG_MAX_BYTES,
    ) -> None:
        if settings.max_concurrent_tasks < 1:
            raise ValueError("max_concurrent_tasks must be positive")
        self.repository = repository.resolve()
        self.runner = runner
        self.settings = settings
        self.on_event = on_event
        self.integration = IntegrationCoordinator()
        self.executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_tasks)
        self._lock = Lock()
        self._next_sequence = 1
        self._tasks: dict[str, TaskRecord] = {}
        self._closed = False
        self._last_persist_at: dict[str, float] = {}
        self._clarification_controls: dict[str, AgentControl] = {}
        self.prompt_store = prompt_store
        self.storage = storage
        self.project_key = project_key(self.repository)
        self.title_length = max(1, int(title_length))
        self.context_budget_chars = max(1, int(context_budget_chars))
        self.run_log_max_bytes = max(1, int(run_log_max_bytes))
        self.memory = TaskMemoryStore(memory_path or self.repository / DEFAULT_MEMORY_FILE)
        self._restore_tasks()

    def set_event_callback(self, callback: TaskEventCallback | None) -> None:
        self.on_event = callback

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    def submit(
        self,
        prompt: str,
        provider: str,
        model: str,
        reasoning: str,
        mode: str = "coding",
        topic: str | None = None,
    ) -> TaskRecord:
        """Start a new conversation from its first user prompt.

        The exact prompt is archived and the queued turn is persisted before
        the run is dispatched; a storage failure raises and launches nothing.
        """
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
            )
            record.title = generate_task_title(prompt, self.title_length, fallback_id=task_id)
            record.prompt_history = [prompt]
            record.memory_task_id = f"task-{task_id}"
            record.execution_id = task_id
            self._attach_storage_paths(record)
            turn = self._record_turn(record, prompt, USER_TURN)
            self._tasks[task_id] = record
            self._dispatch(record, turn, "Queued", "Task queued.")
        self._notify(record, "queued", "Task queued.", "status")
        return record

    def submit_followup(
        self,
        task_id: str,
        text: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        reasoning: str | None = None,
        mode: str | None = None,
        topic: str | None = None,
        revises_turn_id: str | None = None,
    ) -> TaskRecord | None:
        """Send another user prompt within an existing conversation.

        The task must exist and have no active run. Supported configuration
        changes are recorded on the new turn; the task's base branch never
        changes underneath an existing unmerged worktree. A preserved worktree
        is reused; a cleaned-up one is replaced by a fresh worktree from the
        task's operating branch under a new execution suffix.
        """
        with self._lock:
            if self._closed:
                raise RuntimeError("Task coordinator is shut down.")
            record = self._tasks.get(task_id)
            if record is None:
                return None
            if record.run_active:
                raise RuntimeError("Wait for the current run to stop before sending another prompt.")
            if not self.repository.exists():
                raise RuntimeError(f"Project is no longer available: {self.repository}")
            if provider:
                record.provider = provider
            if model is not None and record.provider != "cursor":
                record.model = model
            if reasoning is not None and record.provider != "cursor":
                record.reasoning = reasoning
            if mode and mode in {"coding", "ask", "plan"}:
                if record.mode == "plan" and mode == "coding":
                    record.plan_implemented = record.plan_implemented or record.plan_confirmed
                record.mode = mode
            if topic is not None:
                cleaned_topic = topic.strip() if topic.strip() else None
                record.topic = cleaned_topic
            # A new instruction invalidates the previous execution stage.
            record.retry_prompt = None
            record.retry_output_context = None
            record.plan_followup_prompt = None
            record.resume_notes = []
            record.resume_from = None
            record.control = AgentControl()
            record.error = None
            record.plan_error = None
            record.finished_at = None
            if record.mode == "plan":
                record.plan_confirmed = False
            self._prepare_execution_context(record)
            turn = self._record_turn(record, text, USER_TURN, revises_turn_id=revises_turn_id)
            record.prompt_history.append(text)
            self._dispatch(record, turn, "Queued (follow-up)", "Follow-up queued.")
        log_event(
            logging.INFO,
            "Follow-up turn queued",
            project=self.project_key,
            task=record.task_id,
            turn=turn.turn_id,
            run=record.active_run_id,
            provider=record.provider,
        )
        self._notify(record, "queued", "Follow-up queued.", "status")
        return record

    def _prepare_execution_context(self, record: TaskRecord, *, replace_missing: bool = True) -> None:
        """Reuse a preserved worktree or arrange a fresh one for the next run.

        ``replace_missing`` is used by follow-ups: a worktree that was cleaned
        up after completion is replaced by a fresh one under a new execution
        suffix. Resume and retry keep the recorded context as-is so the
        orchestrator reports the real state of a missing worktree.
        """
        if replace_missing and record.context is not None and not record.context.path.exists():
            LOGGER.info(
                "Preserved worktree is gone; a fresh worktree will be created task=%s path=%s",
                record.task_id,
                record.context.path,
            )
            record.context = None
            record.worktree_path = None
        if record.context is None and record.runs:
            record.execution_count += 1
            record.execution_id = f"{record.task_id}-r{record.execution_count}"
            record.worktree_path = None
            record.branch_name = ""
        elif record.context is not None:
            record.execution_id = record.context.task_id

    def _record_turn(
        self,
        record: TaskRecord,
        text: str,
        kind: str,
        *,
        revises_turn_id: str | None = None,
    ) -> TaskTurn:
        """Archive the exact text and append the turn. Raises on storage failure."""
        sequence = len(record.turns) + 1
        archive_path: str | None = None
        if self.prompt_store is not None and kind == USER_TURN:
            # PromptStoreError propagates: a prompt that cannot be archived
            # must not launch an unrecorded run.
            archive_path = str(self.prompt_store.archive_turn(self.repository, record.task_id, sequence, text))
        turn = TaskTurn(
            turn_id=new_turn_id(),
            sequence=sequence,
            text=text,
            submitted_at=time.time(),
            kind=kind,
            revises_turn_id=revises_turn_id,
            provider=record.provider,
            model=record.model,
            reasoning=record.reasoning,
            mode=record.mode,
            topic=record.topic,
            branch=self.settings.primary_branch,
            archive_path=archive_path,
        )
        record.turns.append(turn)
        record.active_turn_id = turn.turn_id
        return turn

    def _dispatch(self, record: TaskRecord, turn: TaskTurn | None, phase: str, _message: str) -> TaskRun:
        """Create the run for ``turn``, persist it as queued, then start the worker.

        Must be called with the coordinator lock held.
        """
        turn = turn or record.active_turn
        turn_id = turn.turn_id if turn is not None else (record.active_turn_id or "legacy")
        attempt = sum(1 for run in record.runs if run.turn_id == turn_id) + 1
        run = TaskRun(
            run_id=new_run_id(),
            turn_id=turn_id,
            attempt=attempt,
            status="queued",
            message_start=len(record.messages),
            execution_id=record.execution_id or record.task_id,
        )
        if record.diagnostics_dir is not None:
            sequence = turn.sequence if turn is not None else 1
            run.diagnostics_path = str(record.diagnostics_dir / f"turn-{sequence:04d}-run-{attempt:04d}.log")
        record.runs.append(run)
        record.active_run_id = run.run_id
        record.status = "queued"
        record.phase = phase
        self._persist_task(record)
        record.future = self.executor.submit(self._run, record, run.run_id)
        return run

    def _attach_storage_paths(self, record: TaskRecord) -> None:
        if self.storage is not None:
            record.diagnostics_dir = self.storage.task_errors_dir(self.repository, record.task_id)
            record.prompts_dir = self.storage.task_prompts_dir(self.repository, record.task_id)

    # ------------------------------------------------------------------
    # Plan review
    # ------------------------------------------------------------------

    def answer_plan(self, task_id: str, answers: dict[str, str]) -> bool:
        """Send selected plan answers back to the planning agent for confirmation."""
        with self._lock:
            record = self._tasks.get(task_id)
            if (
                record is None
                or record.mode != "plan"
                or record.plan_confirmed
                or record.status not in {"completed", "awaiting_answers"}
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
            # Generated review requests are recorded separately from user turns.
            turn = self._record_turn(record, record.plan_followup_prompt, GENERATED_TURN)
            record.error = None
            record.plan_error = None
            record.control = AgentControl()
            self._dispatch(record, turn, "Queued (reviewing answers)", "Plan answers queued.")
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
                or record.status not in {"awaiting_answers", "completed", "questioning"}
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
            self._clarification_controls[clarification.clarification_id] = AgentControl()
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
        """Continue a confirmed plan as coding within the same conversation.

        The visible task and its title stay the same; the mode change and the
        generated implementation prompt are recorded as a new execution
        context, and the clean planning worktree is replaced by a fresh one.
        """
        with self._lock:
            record = self._tasks.get(task_id)
            if (
                record is None
                or record.mode != "plan"
                or record.status != "completed"
                or not record.plan_confirmed
                or record.plan_implemented
                or self._closed
            ):
                return None
            if any(question.question_id not in record.plan_answers for question in record.plan_questions):
                return None
            # Claim the one-shot transition before dispatching so concurrent UI
            # events cannot start more than one implementation run.
            record.plan_implemented = True
        self._discard_plan_worktree(record)
        with self._lock:
            implementation_prompt = build_implementation_prompt(
                record.prompt,
                record.plan_text,
                record.plan_answers,
                record.plan_answer_details,
            )
            record.mode = "coding"
            record.retry_prompt = None
            record.retry_output_context = None
            record.plan_followup_prompt = None
            record.resume_notes = []
            record.resume_from = None
            record.control = AgentControl()
            record.error = None
            record.finished_at = None
            record.prompt_history.append(implementation_prompt)
            self._prepare_execution_context(record)
            turn = self._record_turn(record, implementation_prompt, GENERATED_TURN)
            self._dispatch(record, turn, "Queued (implementing plan)", "Implementation queued.")
        self._notify(record, "queued", "Implementation queued from the approved plan.", "status")
        return record

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def tasks(self) -> tuple[TaskRecord, ...]:
        with self._lock:
            return tuple(sorted(self._tasks.values(), key=lambda task: task.submission_sequence))

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._tasks.get(task_id)

    def conversation_entries(self, record: TaskRecord) -> list[ConversationEntry]:
        """Return ordered user turns, generated context, and assistant responses."""
        entries: list[ConversationEntry] = []
        turn_positions = {turn.turn_id: index + 1 for index, turn in enumerate(record.turns)}
        runs_by_turn: dict[str, list[TaskRun]] = {}
        for run in record.runs:
            runs_by_turn.setdefault(run.turn_id, []).append(run)
        for turn in record.turns:
            role = "user" if turn.is_user else "context"
            entries.append(ConversationEntry(role, turn.text))
            for run in runs_by_turn.get(turn.turn_id, ()):
                response = record.response_text(run)
                if response:
                    label = f"Assistant response to turn {turn_positions[turn.turn_id]}"
                    if run.attempt > 1:
                        label += f" (attempt {run.attempt})"
                    if run.status == "interrupted":
                        label += " (stopped early)"
                    entries.append(ConversationEntry("assistant", response, label))
        if not record.turns and record.messages:
            entries.append(ConversationEntry("user", record.prompt))
            entries.append(ConversationEntry("assistant", "\n\n".join(record.messages)))
        return entries

    # ------------------------------------------------------------------
    # Lifecycle controls
    # ------------------------------------------------------------------

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
                    run = record.active_run
                    if run is not None:
                        run.status = "paused"
                        run.finished_at = time.time()
                    self._persist_task(record)
                    record.control.request_pause()
                    LOGGER.info("Shutdown paused task=%s status=%s", record.task_id, record.status)
            for control in self._clarification_controls.values():
                control.request_pause()
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
        if record is None or record.status in {"completed", "failed", "blocked", "paused", "cancelled", "interrupted"}:
            return False
        if record.status == "questioning":
            return False
        if record.status == "queued" and record.future is not None and record.future.cancel():
            record.status = "paused"
            record.phase = "Paused"
            record.finished_at = time.time()
            self._finish_run(record, "paused")
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
            if record is None or record.status not in {"paused", "interrupted"} or self._closed:
                return False
            record.control.clear_pause()
            record.control.clear_interrupt()
            record.error = None
            record.finished_at = None
            if notes.strip():
                record.resume_notes.append(notes.strip())
            self._prepare_execution_context(record, replace_missing=False)
            self._dispatch(record, record.active_turn, "Queued (resuming)", "Task queued to resume.")
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
            record.error = None
            record.control = AgentControl()
            self._dispatch(record, record.active_turn, "Queued (continuing plan)", "Planning pass queued.")
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
            record.error = None
            record.control = AgentControl()
            self._dispatch(record, record.active_turn, "Queued (starting coding)", "Coding queued.")
        self._notify(record, "queued", "Task queued to start coding from its plan.", "status")
        return True

    def retry(self, task_id: str) -> bool:
        """Retry a failed agent request after connectivity or service recovery.

        An unchanged retry is another run of the same turn; it resumes the
        failed stage rather than counting as a new prompt.
        """
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
            record.error = None
            record.finished_at = None
            self._prepare_execution_context(record, replace_missing=False)
            self._dispatch(record, record.active_turn, "Queued (retrying)", "Retry queued.")
        self._notify(record, "queued", "Task queued for retry.", "status")
        return True

    def interrupt(self, task_id: str) -> bool:
        """Stop the selected task's active run without discarding progress.

        Shared by Cancel, ``Ctrl+C``, and the ``Ctrl+X`` alias. A queued run is
        released immediately; a running one is asked to stop and reports
        ``interrupted`` once its worker and subprocesses have exited. Repeated
        calls while stopping are idempotent. Returns ``False`` when nothing is
        running for the task.
        """
        record = self.get(task_id)
        if record is None:
            return False
        with self._lock:
            stopped_clarifications = self._interrupt_clarifications(record)
            if record.status == "queued" and record.future is not None and record.future.cancel():
                record.status = "interrupted"
                record.phase = "Interrupted"
                record.error = None
                record.finished_at = time.time()
                self._finish_run(record, "interrupted")
                self._persist_task(record)
                log_event(
                    logging.INFO,
                    "Queued run interrupted before execution",
                    project=self.project_key,
                    task=record.task_id,
                    turn=record.active_turn_id,
                    run=record.active_run_id,
                )
                notify = ("interrupted", "Run stopped before execution; the task can continue.", "status")
            elif record.status in ACTIVE_RUN_STATUSES:
                if record.stopping:
                    return True
                record.control.request_interrupt()
                record.phase = STOPPING_PHASE
                log_event(
                    logging.INFO,
                    "Interruption requested",
                    project=self.project_key,
                    task=record.task_id,
                    turn=record.active_turn_id,
                    run=record.active_run_id,
                    phase=record.status,
                    provider=record.provider,
                )
                notify = ("stopping", "Stopping the active run; progress is preserved.", "status")
            elif stopped_clarifications:
                notify = ("stopping", "Stopping the running clarification.", "status")
            else:
                return False
        self._notify(record, *notify)
        return True

    def _interrupt_clarifications(self, record: TaskRecord) -> bool:
        stopped = False
        for items in record.plan_clarifications.values():
            for clarification in items:
                if clarification.status in {"queued", "running"}:
                    control = self._clarification_controls.get(clarification.clarification_id)
                    if control is not None:
                        control.request_interrupt()
                        stopped = True
        return stopped

    def cancel(self, task_id: str) -> bool:
        """Discard a stopped task's preserved worktree and branch.

        This is the destructive operation; the Cancel control in the UI uses
        :meth:`interrupt` instead. It remains available for explicit cleanup of
        paused, interrupted, or questioning tasks and for legacy callers.
        """
        record = self.get(task_id)
        if record is None or record.status in {"completed", "failed", "blocked", "cancelled"}:
            return False
        if record.status in {"paused", "interrupted", "questioning"}:
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
                    self._diagnose(record, "error", record.error, phase="cleanup")
                    self._persist_task(record)
                    self._notify(record, "failed", record.error, "error")
                    return False
            record.status = "cancelled"
            record.phase = "Cancelled"
            record.error = "Task cancelled and its worktree was removed."
            record.finished_at = time.time()
            record.context = None
            record.worktree_path = None
            self._persist_task(record)
            self._notify(record, "cancelled", record.error, "error")
            return True
        if record.status == "queued" and record.future is not None and record.future.cancel():
            record.status = "cancelled"
            record.phase = "Cancelled"
            record.error = "Task cancelled before execution."
            record.finished_at = time.time()
            self._finish_run(record, "cancelled")
            self._persist_task(record)
            self._notify(record, "cancelled", record.error, "error")
            return True
        record.control.request_cancel()
        record.phase = "Cancelling"
        self._notify(record, "cancelling", "Stopping the active agent and removing its worktree.", "status")
        return True

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

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
            control = self._clarification_controls.get(clarification_id)
        self._notify(record, "clarification", "Asking for clarification.", "status")

        answer_chunks: list[str] = []

        def on_event(_phase: str, message: str, kind: str = "status") -> None:
            # Clarifications stay off the plan transcript and do not change task status.
            if kind == "message" and message:
                answer_chunks.append(message)

        orchestrator = LocalOrchestrator(
            self.repository,
            self.runner,
            self.settings,
            on_event,
            integration_gate=self.integration.run_when_ready,
        )
        try:
            result = orchestrator.run(
                prompt,
                provider,
                model,
                reasoning,
                task_id=f"{task_id}-clarify-{clarification_id}",
                mode="ask",
                topic_slug=topic_slug,
                control=control,
            )
        except Exception as error:  # Keep clarification failures isolated from the plan task.
            log_exception(
                f"Plan clarification crashed task={task_id} clarification={clarification_id}",
                error,
            )
            with self._lock:
                clarification = self._find_clarification(record, clarification_id)
                self._clarification_controls.pop(clarification_id, None)
                if clarification is None:
                    return
                clarification.status = "failed"
                clarification.error = str(error)
            self._notify(record, "clarification", str(error), "error")
            return

        with self._lock:
            clarification = self._find_clarification(record, clarification_id)
            self._clarification_controls.pop(clarification_id, None)
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
            elif result.interrupted or result.paused:
                clarification.status = "failed"
                clarification.error = "Clarification stopped before it answered."
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

    def _turn_prompt(self, record: TaskRecord) -> str:
        """Return the text sent for the active turn: exact for the first, contextual later."""
        turn = record.active_turn
        if turn is None:
            return record.prompt
        if not turn.is_user:
            # Generated prompts (plan review, implementation) already embed the
            # original request and the plan; do not wrap them again.
            return turn.text
        user_turns = record.user_turns
        if len(record.turns) <= 1 or (user_turns and turn is user_turns[0] and len(user_turns) == 1):
            return turn.text
        history = [
            entry
            for entry in self.conversation_entries(record)
        ]
        # Drop the active turn itself (and anything after it) from history so it
        # appears only as the latest instruction.
        trimmed: list[ConversationEntry] = []
        seen_active = False
        for entry, source in zip(history, self._entry_sources(record)):
            if source == turn.turn_id:
                seen_active = True
                break
            trimmed.append(entry)
        if not seen_active:
            trimmed = history
        return build_conversation_prompt(trimmed, turn.text, self.context_budget_chars)

    def _entry_sources(self, record: TaskRecord) -> list[str]:
        """Parallel list to :meth:`conversation_entries`: the turn id each entry belongs to."""
        sources: list[str] = []
        runs_by_turn: dict[str, list[TaskRun]] = {}
        for run in record.runs:
            runs_by_turn.setdefault(run.turn_id, []).append(run)
        for turn in record.turns:
            sources.append(turn.turn_id)
            for run in runs_by_turn.get(turn.turn_id, ()):
                if record.response_text(run):
                    sources.append(f"{turn.turn_id}:response")
        if not record.turns and record.messages:
            sources.extend(("legacy", "legacy:response"))
        return sources

    def _run(self, record: TaskRecord, run_id: str | None = None) -> None:
        run = record.run_by_id(run_id) if run_id else record.active_run
        run_id = run.run_id if run is not None else run_id
        log_event(
            logging.INFO,
            "Task worker started",
            project=self.project_key,
            task=record.task_id,
            turn=record.active_turn_id,
            run=run_id,
            phase=record.mode,
            provider=record.provider,
        )
        record.started_at = time.time()
        if run is not None:
            run.status = "running"
            run.started_at = record.started_at
            run.message_start = len(record.messages)
        self._persist_task(record)
        message_start = len(record.messages)
        if record.mode == "plan" and record.plan_followup_prompt and record.provider == "cursor":
            # Cursor streams deltas by extending the last stored message. Give a
            # follow-up response its own transcript slot before starting it.
            record.messages.append("")
        prompt = record.plan_followup_prompt or record.retry_prompt or self._turn_prompt(record)
        record.retry_prompt = prompt
        record.plan_followup_prompt = None
        resume_notes = tuple(record.resume_notes)
        if record.retry_output_context:
            resume_notes += (record.retry_output_context,)
        record.retry_output_context = None
        execution_id = record.execution_id or record.task_id
        orchestrator = LocalOrchestrator(
            self.repository,
            self.runner,
            self.settings,
            lambda phase, message, kind="status": self._handle_event(record, run_id, phase, message, kind),
            integration_gate=self.integration.run_when_ready,
        )
        try:
            result = orchestrator.run(
                prompt,
                record.provider,
                record.model,
                record.reasoning,
                task_id=execution_id,
                submission_sequence=record.submission_sequence,
                mode=record.mode,
                control=record.control,
                existing_context=record.context,
                resume_notes=resume_notes,
                resume_from=record.resume_from,
                topic_slug=record.topic,
            )
        except Exception as error:  # Keep one unexpected task failure isolated from the pool.
            log_event(
                logging.ERROR,
                "Task worker crashed",
                error=error,
                project=self.project_key,
                task=record.task_id,
                turn=record.active_turn_id,
                run=run_id,
                provider=record.provider,
            )
            record.finished_at = time.time()
            record.status = "failed"
            record.phase = "Failed"
            record.error = str(error)
            self._diagnose(record, "error", f"Task worker crashed: {error}", phase="worker", run=run)
            self._finish_run(record, "failed", run=run, error=record.error)
            self._persist_task(record)
            self._notify(record, "failed", str(error), "error")
            return
        if record.active_run_id != run_id:
            # A newer run replaced this one while it was finishing; its result
            # must not overwrite the newer run's state.
            LOGGER.info("Late run result ignored task=%s run=%s", record.task_id, run_id)
            return
        record.finished_at = time.time()
        record.branch_name = result.branch_name or record.branch_name
        record.worktree_path = result.worktree or record.worktree_path
        record.context = result.context or record.context
        if run is not None:
            run.branch_name = record.branch_name or None
            run.worktree_path = str(record.worktree_path) if record.worktree_path else None
            run.tokens = result.tokens_consumed if result.succeeded else None
        if result.succeeded:
            record.tokens_consumed += result.tokens_consumed
        if result.awaiting_plan:
            if record.mode == "plan":
                self._update_plan_state(record, record.messages[message_start:])
            if record.plan_confirmed:
                record.status = "completed"
                record.phase = "Completed"
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
            self._finish_run(record, record.status, run=run, error=record.error)
            self._persist_task(record)
            event_phase = {
                "completed": "completed",
                "awaiting_answers": "questions",
            }.get(record.status, "questioning")
            self._notify(
                record,
                event_phase,
                "Plan ready for review." if record.status != "completed" else "Plan confirmed.",
                "status",
            )
            self._log_finished(record, run_id)
            return
        if result.interrupted:
            record.status = "interrupted"
            record.phase = "Interrupted"
            record.error = None
            record.control.clear_interrupt()
            self._finish_run(record, "interrupted", run=run)
            self._persist_task(record)
            self._notify(record, "interrupted", "Run stopped; progress preserved. Edit the prompt and send again to continue.", "status")
            self._log_finished(record, run_id)
            return
        if result.paused:
            record.status = "paused"
            record.phase = "Paused"
            record.error = None
            self._finish_run(record, "paused", run=run)
            self._persist_task(record)
            self._notify(record, "paused", "Task paused; progress preserved.", "status")
            self._log_finished(record, run_id)
            return
        if result.cancelled:
            record.status = "cancelled"
            record.phase = "Cancelled"
            record.error = result.error or "Task cancelled."
            record.context = None
            record.worktree_path = None
            self._finish_run(record, "cancelled", run=run, error=record.error)
            self._persist_task(record)
            self._notify(record, "cancelled", record.error, "error")
            self._log_finished(record, run_id)
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
                record.status = "completed"
                record.phase = "Completed"
                record.resume_from = None
        else:
            record.status = "failed"
            record.phase = "Failed"
            record.error = record.error or result.error or "Task failed."
            self._diagnose(record, "error", record.error, phase="failed", run=run)
        self._finish_run(record, record.status, run=run, error=record.error)
        self._persist_task(record)
        self._notify(
            record,
            "questions" if result.succeeded and record.mode == "plan" and record.plan_questions and not record.plan_confirmed else
            ("completed" if result.succeeded else "failed"),
            "",
            "status",
        )
        self._log_finished(record, run_id)

    def _log_finished(self, record: TaskRecord, run_id: str | None) -> None:
        log_event(
            logging.INFO,
            f"Task worker finished status={record.status}",
            project=self.project_key,
            task=record.task_id,
            turn=record.active_turn_id,
            run=run_id,
            provider=record.provider,
        )

    def _finish_run(
        self,
        record: TaskRecord,
        status: str,
        *,
        run: TaskRun | None = None,
        error: str | None = None,
    ) -> None:
        run = run or record.active_run
        if run is None:
            return
        run.status = status
        run.finished_at = time.time()
        run.message_end = len(record.messages)
        if error is not None:
            run.error = error

    def _update_plan_state(self, record: TaskRecord, new_messages: list[str]) -> bool:
        response = "\n\n".join(new_messages).strip()
        parsed = parse_plan_response(response)
        if not parsed.valid:
            # A protocol error after the user answered questions must not erase
            # the last usable plan or make the choices impossible to resubmit.
            record.plan_confirmed = False
            record.plan_error = parsed.error
            record.error = parsed.error
            LOGGER.warning(
                "Rejected invalid plan payload task=%s response_length=%d error=%s",
                record.task_id,
                len(response),
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
            # The coding run is still queued; a failed cleanup must not
            # prevent it from running or hide the planning result.
            LOGGER.warning("Could not remove plan worktree task=%s error=%s", record.task_id, error)
            self._diagnose(record, "warning", f"Could not remove plan worktree: {error}", phase="cleanup")
            return
        LOGGER.info("Removed clean plan worktree task=%s path=%s", record.task_id, record.context.path)
        record.context = None
        record.worktree_path = None
        self._persist_task(record)

    def _handle_event(self, record: TaskRecord, run_id: str | None, phase: str, message: str, kind: str) -> None:
        if run_id is not None and record.active_run_id != run_id:
            # A late callback from a superseded run must never change the new
            # run's state or append to its response.
            LOGGER.debug("Dropped late event task=%s run=%s phase=%s", record.task_id, run_id, phase)
            return
        run = record.run_by_id(run_id)
        record.phase = phase.replace("_", " ").capitalize()
        status = {
            "worktree": "running",
            "planning": "planning",
            "questioning": "questioning",
            "agent": "running",
            "verification": "verifying",
            "migrations": "verifying",
            "firebase": "verifying",
            "repairing": "verifying",
            "ready": "ready",
            "integration": "integrating",
            "resolving": "resolving",
            "completed": "completed",
            "failed": "failed",
            "paused": "paused",
            "cancelled": "cancelled",
            "interrupted": "interrupted",
        }.get(phase)
        if status:
            record.status = status
        if record.control.interrupt_requested.is_set() and record.status in ACTIVE_RUN_STATUSES:
            # Keep the visible state honest while the worker winds down.
            record.phase = STOPPING_PHASE
        if kind == "message" and message:
            run_has_messages = run is not None and len(record.messages) > run.message_start
            if record.provider == "cursor" and record.messages and (run is None or run_has_messages):
                record.messages[-1] += message
            else:
                record.messages.append(message)
            if run is not None:
                run.message_end = len(record.messages)
        if kind == "error" and message:
            record.error = message
            if run is not None:
                run.error = message
            self._diagnose(record, "error", message, phase=phase, run=run)
        if phase in {"ready", "integration", "resolving"}:
            record.resume_from = "integration"
        if phase == "worktree" and message.startswith("Created "):
            branch, _, worktree = message.removeprefix("Created ").rstrip(".").partition(" at ")
            if branch and worktree:
                record.branch_name = branch
                record.worktree_path = Path(worktree)
        self._persist_task(record, force=kind != "message")
        self._notify(record, phase, message, kind)

    def _diagnose(
        self,
        record: TaskRecord,
        severity: str,
        text: str,
        *,
        phase: str,
        run: TaskRun | None = None,
    ) -> None:
        """Append the complete diagnostic to the run's local log before UI truncation."""
        run = run or record.active_run
        path_text = run.diagnostics_path if run is not None else None
        if path_text is None and record.diagnostics_dir is not None:
            path_text = str(record.diagnostics_dir / "task.log")
        if path_text is None:
            return
        append_run_diagnostic(
            Path(path_text),
            severity,
            text,
            max_bytes=self.run_log_max_bytes,
            project=self.project_key,
            task=record.task_id,
            turn=run.turn_id if run is not None else record.active_turn_id,
            run=run.run_id if run is not None else None,
            phase=phase,
            provider=record.provider,
        )

    def _persist_task(self, record: TaskRecord, *, force: bool = True) -> None:
        """Persist task state, coalescing high-frequency streamed messages."""
        now = time.monotonic()
        if not force and now - self._last_persist_at.get(record.task_id, 0.0) < 0.25:
            return
        task_id = f"task-{record.task_id}"
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
                logical_task_id=record.task_id,
                branch_name=record.context.branch_name if record.context is not None else None,
                worktree_path=record.context.path if record.context is not None else None,
                base_commit=record.context.base_commit if record.context is not None else None,
                submission_sequence=record.submission_sequence,
                resume_from=record.resume_from,
                topic=record.topic,
                title=record.title or None,
                turns=[turn.to_dict() for turn in record.turns] if record.turns else None,
                runs=[run.to_dict() for run in record.runs] if record.runs else None,
                active_turn_id=record.active_turn_id,
                active_run_id=record.active_run_id,
                schema_version=TASK_SCHEMA_VERSION if record.turns else None,
                prompt_count=len(record.user_turns) if record.turns else None,
                project_key=self.project_key if record.turns else None,
                diagnostics_dir=record.diagnostics_dir,
                prompts_dir=record.prompts_dir,
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
            phase = _phase_for_status(status)
            restart_interrupted = False
            if status in INTERRUPTIBLE_STATUSES:
                # The run was active when the previous process ended. It is
                # recoverable, never auto-launched, and not an error.
                status = "interrupted"
                phase = "Interrupted (Daedalus was closed while this run was active)"
                error = None
                restart_interrupted = True
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
                    branch_name.removeprefix("agent/task-") if branch_name.startswith("agent/task-") else task_id,
                    base_commit,
                    branch_name,
                    worktree_path,
                )
            messages = _string_list(snapshot.get("outputs"))
            prompt_history = _string_list(snapshot.get("prompt_history")) or [prompt]
            title_value = snapshot.get("title")
            title = (
                title_value.strip()
                if isinstance(title_value, str) and title_value.strip()
                else generate_task_title(prompt, self.title_length, fallback_id=task_id)
            )
            record = TaskRecord(
                task_id=task_id,
                submission_sequence=sequence,
                prompt=prompt,
                provider=str(snapshot.get("provider") or "codex"),
                model=str(snapshot.get("model") or ""),
                reasoning=str(snapshot.get("reasoning") or ""),
                mode=str(snapshot.get("mode") or "coding"),
                topic=topic,
                status=status,
                phase=phase,
                branch_name=branch_name,
                worktree_path=worktree_path,
                messages=messages,
                error=error,
                tokens_consumed=_nonnegative_int(snapshot.get("tokens")),
                submitted_at=_snapshot_timestamp(snapshot.get("timestamp")),
                context=context,
                memory_task_id=memory_task_id,
                prompt_history=prompt_history,
                resume_from=resume_from,
                title=title,
            )
            self._attach_storage_paths(record)
            self._restore_conversation(record, snapshot, restart_interrupted)
            if record.mode == "plan":
                self._restore_plan_state(record)
            self._tasks[task_id] = record
            self._reconcile_archives(record)
        self._next_sequence = max(self._next_sequence, maximum_sequence + 1)

    def _restore_conversation(self, record: TaskRecord, snapshot: dict[str, object], restart_interrupted: bool) -> None:
        """Round-trip turns and runs, or derive them from a legacy snapshot."""
        turns = [
            turn
            for turn in (TaskTurn.from_dict(item) for item in snapshot.get("turns") or [])
            if turn is not None
        ] if isinstance(snapshot.get("turns"), list) else []
        runs = [
            run
            for run in (TaskRun.from_dict(item) for item in snapshot.get("runs") or [])
            if run is not None
        ] if isinstance(snapshot.get("runs"), list) else []
        if not turns:
            # Legacy snapshot: the original prompt is the first user turn and
            # any generated Plan follow-ups are context, not user submissions.
            turns.append(
                TaskTurn(
                    turn_id=f"turn-legacy-{record.task_id}-1",
                    sequence=1,
                    text=record.prompt,
                    submitted_at=record.submitted_at,
                    kind=USER_TURN,
                    provider=record.provider,
                    model=record.model,
                    reasoning=record.reasoning,
                    mode=record.mode,
                    topic=record.topic,
                )
            )
            for index, generated in enumerate(record.prompt_history[1:], start=2):
                turns.append(
                    TaskTurn(
                        turn_id=f"turn-legacy-{record.task_id}-{index}",
                        sequence=index,
                        text=generated,
                        submitted_at=None,
                        kind=GENERATED_TURN,
                        provider=record.provider,
                        model=record.model,
                        reasoning=record.reasoning,
                        mode=record.mode,
                        topic=record.topic,
                    )
                )
        if not runs and (record.messages or record.status not in {"queued"}):
            runs.append(
                TaskRun(
                    run_id=f"run-legacy-{record.task_id}-1",
                    turn_id=turns[-1].turn_id,
                    attempt=1,
                    status=record.status,
                    started_at=None,
                    finished_at=None,
                    message_start=0,
                    message_end=len(record.messages),
                    error=record.error,
                    execution_id=record.task_id,
                )
            )
        record.turns = turns
        record.runs = runs
        active_turn = snapshot.get("active_turn_id")
        active_run = snapshot.get("active_run_id")
        record.active_turn_id = (
            active_turn if isinstance(active_turn, str) and record.turn_by_id(active_turn) else turns[-1].turn_id
        )
        record.active_run_id = (
            active_run if isinstance(active_run, str) and record.run_by_id(active_run) else (runs[-1].run_id if runs else None)
        )
        execution_ids = [run.execution_id for run in runs if run.execution_id]
        record.execution_id = execution_ids[-1] if execution_ids else record.task_id
        suffixes = [
            int(execution_id.rsplit("-r", 1)[1])
            for execution_id in execution_ids
            if "-r" in execution_id and execution_id.rsplit("-r", 1)[1].isdigit()
        ]
        record.execution_count = max(suffixes) if suffixes else 1
        if restart_interrupted:
            for run in runs:
                if run.status in ACTIVE_RUN_STATUSES:
                    run.status = "interrupted"
                    run.finished_at = run.finished_at or time.time()
                    if run.message_end is None:
                        run.message_end = len(record.messages)
        for run in runs:
            if run.message_end is None and run.status not in ACTIVE_RUN_STATUSES:
                run.message_end = len(record.messages)

    def _reconcile_archives(self, record: TaskRecord) -> None:
        """Regenerate missing prompt archives and expose orphaned ones as drafts."""
        if self.prompt_store is None:
            return
        try:
            indexed = {turn.sequence: turn.text for turn in record.turns if turn.is_user}
            orphans = self.prompt_store.reconcile(self.repository, record.task_id, indexed)
            for turn in record.turns:
                if turn.is_user and turn.archive_path is None:
                    turn.archive_path = str(self.prompt_store.turn_path(self.repository, record.task_id, turn.sequence))
            if orphans and self.prompt_store.load_draft(self.repository, record.task_id) is None:
                text = self.prompt_store.read_turn(orphans[-1].path)
                if text is not None:
                    # Never execute an orphaned archive automatically; offer it back.
                    self.prompt_store.save_draft(
                        self.repository,
                        record.task_id,
                        text,
                        cursor=(0, 0),
                        revision=0,
                        kind="recovered",
                    )
                    LOGGER.info(
                        "Recovered an unindexed prompt archive as a draft task=%s path=%s",
                        record.task_id,
                        orphans[-1].path,
                    )
        except (OSError, PromptStoreError) as error:
            LOGGER.warning("Prompt archive reconciliation failed task=%s error=%s", record.task_id, error)

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
            record.plan_confirmed = parsed.no_more_questions and not parsed.questions
            record.plan_error = None
            return

    def _notify(self, record: TaskRecord, phase: str, message: str, kind: str) -> None:
        if self.on_event is not None:
            self.on_event(record, phase, message, kind)


__all__ = [
    "ACTIVE_RUN_STATUSES",
    "CONTINUABLE_STATUSES",
    "INTERRUPTIBLE_STATUSES",
    "IntegrationCoordinator",
    "STOPPING_PHASE",
    "TASK_STATUSES",
    "TaskCoordinator",
    "TaskRecord",
    "TaskRun",
    "TaskTurn",
]
