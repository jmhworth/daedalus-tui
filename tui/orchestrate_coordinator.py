"""Orchestrate Mode dispatcher: planner rounds, worker scheduling, failure loop.

One :class:`OrchestrateCoordinator` lives beside each project's
:class:`~tui.task_coordinator.TaskCoordinator`. It runs the planner through
:class:`~tui.orchestrator.LocalOrchestrator` in ``orchestrate-plan`` mode,
turns the payload into cards, submits ready cards as ordinary coding tasks,
and feeds a bounded digest of their outcomes back to the planner until the
planner declares the session done or a cap is exhausted.

Each session runs on its own thread, never inside the task executor the
workers need.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import subprocess
from threading import Condition, Lock, Thread
import time
from typing import Callable

from .agent_runner import AgentControl, AgentResult, AgentRunner
from .config import OrchestrateSettings
from .debug_log import LOGGER, log_exception
from .git_worktree import GitWorktreeError, GitWorktreeManager, WorktreeContext
from .local_storage import LocalStorage
from .memory import TaskMemoryStore
from .orchestrate_protocol import (
    PlannerPayload,
    load_role_rules,
    parse_planner_payload,
    parse_worker_report,
    ready_tasks,
)
from .orchestrate_session import (
    OrchestrationSession,
    SessionStore,
    TaskCard,
    cards_from_payload,
    new_session_id,
)
from .orchestrator import BUNDLED_PROFILE_ROOT, LocalOrchestrator, OrchestrationSettings
from .prompts import (
    bounded_digest,
    build_planner_prompt,
    build_planner_round_prompt,
    build_worker_prompt,
    planner_round_label,
)
from .task_coordinator import TaskCoordinator, TaskEventCallback, TaskRecord
from .verification import discover_commands


ORCHESTRATE_PHASE = "orchestrate"
#: Longest planner progress line kept in the session log; the full output is
#: logged once the round ends.
_PLANNER_PROGRESS_CHARS = 400
#: Worker record statuses that end a card one way or another.
_SETTLED_TASK_STATUSES = frozenset({"completed", "failed", "interrupted", "paused", "cancelled"})
_CARD_STATUS_FOR_TASK = {
    "queued": "running",
    "running": "running",
    "verifying": "verifying",
    "ready": "integrating",
    "integrating": "integrating",
    "resolving": "integrating",
}


@dataclass
class SessionEventRecord:
    """The record shape the app's task-event queue reads, for session events.

    Session events ride the existing :data:`TaskEventCallback` under the
    ``orchestrate`` phase family; ``task_id`` carries the session id.
    """

    task_id: str
    session_id: str
    status: str
    phase: str = ORCHESTRATE_PHASE
    mode: str = "orchestrate"
    error: str | None = None
    messages: list[str] = field(default_factory=list)


class OrchestrateCoordinator:
    """Run Orchestrate Mode sessions for one project."""

    def __init__(
        self,
        task_coordinator: TaskCoordinator,
        runner: AgentRunner,
        orchestration_settings: OrchestrationSettings,
        orchestrate_settings: OrchestrateSettings,
        storage: LocalStorage,
        memory: TaskMemoryStore,
        on_event: TaskEventCallback | None = None,
    ) -> None:
        self.task_coordinator = task_coordinator
        self.runner = runner
        self.settings = orchestration_settings
        self.orchestrate = orchestrate_settings
        self.storage = storage
        self.memory = memory
        self.on_event = on_event
        self.repository = task_coordinator.repository
        self.project_key = task_coordinator.project_key
        self.store = SessionStore(storage, orchestrate_settings)
        self._lock = Lock()
        self._wakeup = Condition(self._lock)
        self._sessions: dict[str, OrchestrationSession] = {}
        self._threads: dict[str, Thread] = {}
        self._stop_requested: set[str] = set()
        self._planner_controls: dict[str, AgentControl] = {}
        self._worker_outputs: dict[str, str] = {}
        self._next_sequence = 1
        self._closed = False
        self._role_rules: str | None = None
        add_observer = getattr(task_coordinator, "add_task_observer", None)
        if callable(add_observer):
            add_observer(self._on_worker_event)
        self._restore_sessions()

    def set_event_callback(self, callback: TaskEventCallback | None) -> None:
        self.on_event = callback

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(
        self,
        prompt: str,
        planner_selection: tuple[str, str, str],
        worker_selection: tuple[str, str, str],
        max_workers: int,
        topic: str | None = None,
    ) -> OrchestrationSession:
        """Create a session and start its planner on a dedicated thread."""
        if not prompt.strip():
            raise ValueError("The orchestration prompt cannot be empty.")
        workers = max(1, min(int(max_workers), self.orchestrate.max_workers_limit))
        with self._lock:
            if self._closed:
                raise RuntimeError("Orchestrate coordinator is shut down.")
            session = OrchestrationSession(
                session_id=new_session_id(self._next_sequence),
                project_key=self.project_key,
                prompt=prompt,
                planner_selection=planner_selection,
                worker_selection=worker_selection,
                max_workers=workers,
                topic=topic.strip() if isinstance(topic, str) and topic.strip() else None,
            )
            self._next_sequence += 1
            self._sessions[session.session_id] = session
            thread = Thread(
                target=self._run_session,
                args=(session,),
                name=f"orchestrate-{session.session_id}",
                daemon=True,
            )
            self._threads[session.session_id] = thread
        self._log(session, f"Session {session.session_id} started with up to {workers} workers.")
        self._persist(session)
        self._notify(session, "Session started.")
        thread.start()
        return session

    def stop(self, session_id: str) -> bool:
        """Stop a session: interrupt its planner and worker tasks, keep their progress."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or not session.active:
                return False
            self._stop_requested.add(session_id)
            control = self._planner_controls.get(session_id)
            worker_ids = [card.worker_task_id for card in session.cards.values() if card.active and card.worker_task_id]
            self._wakeup.notify_all()
        if control is not None:
            control.request_interrupt()
        for worker_id in worker_ids:
            try:
                self.task_coordinator.interrupt(worker_id)
            except Exception as error:  # A worker that will not stop must not hide the others.
                log_exception(f"Could not interrupt worker task={worker_id}", error)
        self._log(session, "Stop requested; interrupting the planner and active workers.")
        self._notify(session, "Stopping the session.")
        return True

    def sessions(self) -> tuple[OrchestrationSession, ...]:
        with self._lock:
            return tuple(self._sessions.values())

    def get(self, session_id: str) -> OrchestrationSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        """Forget an inactive session; its worker tasks stay in the inbox."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.active:
                return False
            self._sessions.pop(session_id, None)
            self._threads.pop(session_id, None)
        try:
            self.memory.delete_orchestration(session_id)
        except (OSError, ValueError) as error:
            LOGGER.warning("Could not delete persisted session session=%s error=%s", session_id, error)
            return False
        return True

    def plan_text(self, session: OrchestrationSession) -> str:
        return self.store.read_plan(session)

    def shutdown(self) -> None:
        """Mark running sessions stopped; the task coordinator stops the workers."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            active = [session for session in self._sessions.values() if session.active]
            self._stop_requested.update(session.session_id for session in active)
            controls = list(self._planner_controls.values())
            self._wakeup.notify_all()
        for control in controls:
            control.request_interrupt()
        for session in active:
            session.status = "stopped"
            session.error = "Daedalus was closed while this session was active."
            session.finished_at = time.time()
            for card in session.cards.values():
                if card.active or card.status in {"pending", "waiting"}:
                    card.status = "stopped"
            self._persist(session)
        for thread in list(self._threads.values()):
            if thread.is_alive():
                thread.join(timeout=0.5)

    # ------------------------------------------------------------------
    # Session loop
    # ------------------------------------------------------------------

    def _run_session(self, session: OrchestrationSession) -> None:
        try:
            self._plan(session, first_round=True)
            while session.active:
                if self._stopping(session):
                    break
                self._dispatch(session)
                self._wait_for_workers(session)
                if self._stopping(session):
                    break
                if not session.active:
                    break
                if self._all_promoted(session) or session.cards_with_status("failed"):
                    self._plan(session, first_round=False)
                elif not session.cards_with_status("running", "verifying", "integrating") and not self._ready(session):
                    # Nothing runs, nothing failed, nothing can start: the
                    # planner has to say what happens next.
                    self._plan(session, first_round=False)
            if self._stopping(session) and session.active:
                self._finish(session, "stopped", "Session stopped by the operator.")
        except Exception as error:  # A crashed session must never take the app down.
            log_exception(f"Orchestration session crashed session={session.session_id}", error)
            self._finish(session, "failed", f"Session crashed: {error}")
        finally:
            with self._lock:
                self._planner_controls.pop(session.session_id, None)
                self._stop_requested.discard(session.session_id)
            self._persist(session)

    def _round_cap_reached(self, session: OrchestrationSession) -> bool:
        """True when the optional round cap is set and spent; zero means no cap."""
        limit = self.orchestrate.planner_round_limit
        return limit > 0 and session.round >= limit

    def _plan(self, session: OrchestrationSession, *, first_round: bool) -> None:
        """Run one planner round (with one corrective retry) and apply its payload.

        The planner decides how many rounds the work needs; it ends the session
        by declaring it done. ``planner_round_limit`` is only a safety cap.
        """
        if self._round_cap_reached(session):
            digest = self.store.write_digest(session)
            self._finish(
                session,
                "failed",
                f"Planner round limit ({self.orchestrate.planner_round_limit}) reached.\n\n{digest}",
            )
            return
        correction: str | None = None
        for attempt in (1, 2):
            if self._stopping(session):
                return
            session.round += 1
            session.status = "planning"
            digest = "" if first_round and attempt == 1 else self.store.write_digest(session)
            self._log(
                session,
                planner_round_label(session.round, self.orchestrate.planner_round_limit)
                + (" (corrective retry)" if correction else "") + ".",
            )
            if digest:
                self._log(session, digest)
            self._persist(session)
            self._notify(session, f"Planner round {session.round} running.")
            output, tokens = self._run_planner(session, digest, correction, first_round)
            session.tokens_planner += tokens
            if output is None:
                # Stopped or failed inside the orchestrator; _run_planner
                # already settled the session.
                return
            self._log(session, output)
            payload = parse_planner_payload(output, known_ids=session.cards)
            conflict = self._round_conflict(session, payload) if payload.valid else None
            if payload.valid and conflict is None:
                self.store.write_plan(session, raw_payload=output)
                self._apply_payload(session, payload)
                return
            correction = payload.error or conflict or "Planner payload was rejected."
            self._log(session, f"Planner payload rejected: {correction}")
            if self._round_cap_reached(session):
                break
        self._finish(session, "failed", f"Planner did not return a valid plan: {correction}")

    def _run_planner(
        self,
        session: OrchestrationSession,
        digest: str,
        correction: str | None,
        first_round: bool,
    ) -> tuple[str | None, int]:
        role_rules = self._load_role_rules()
        verification_hint = self._verification_hint()
        rejected = (
            f"\n\nYour previous reply was rejected: {correction} Reply again with one valid payload."
            if correction
            else ""
        )

        def prompt_builder(profile_text: str | None, topic_text: str | None) -> str:
            if first_round and not digest:
                prompt = build_planner_prompt(
                    session.prompt,
                    role_rules,
                    profile_text,
                    topic_text,
                    session.max_workers,
                    verification_hint,
                    repository_map=self._repository_map(),
                )
            else:
                prompt = build_planner_round_prompt(
                    session.prompt,
                    session.summary,
                    digest,
                    role_rules,
                    profile_text,
                    session.round,
                    self.orchestrate.planner_round_limit,
                )
            return prompt + rejected

        control = AgentControl()
        with self._lock:
            self._planner_controls[session.session_id] = control
            if session.session_id in self._stop_requested:
                control.request_interrupt()
        messages: list[str] = []
        started = time.monotonic()

        def on_event(phase: str, message: str, kind: str = "status") -> None:
            if kind == "message" and message:
                messages.append(message)
                # Show the planner thinking as it streams so a long round is
                # visibly alive; the full output is logged when it ends.
                elapsed = int(time.monotonic() - started)
                line = " ".join(message.split())
                if len(line) > _PLANNER_PROGRESS_CHARS:
                    line = line[: _PLANNER_PROGRESS_CHARS - 1] + "…"
                self._log(session, f"planner [{elapsed}s]: {line}")
                self._notify(session, "Planner progress.")
            elif kind == "error" and message:
                self._log(session, f"planner {phase}: {message}")

        orchestrator = LocalOrchestrator(self.repository, self.runner, self.settings, on_event)
        orchestrator.set_task_title(f"Orchestrate {session.session_id} planner round {session.round}")
        provider, model, reasoning = session.planner_selection
        result = orchestrator.run(
            session.prompt,
            provider,
            model,
            reasoning,
            task_id=f"{session.session_id}-plan-{session.round}",
            mode="orchestrate-plan",
            control=control,
            topic_slug=session.topic,
            prompt_builder=prompt_builder,
        )
        with self._lock:
            self._planner_controls.pop(session.session_id, None)
        if result.context is not None:
            self._remove_worktree(result.context)
        if result.interrupted or result.paused or result.cancelled:
            self._finish(session, "stopped", "Session stopped during a planner round.")
            return None, result.tokens_consumed
        if not result.succeeded:
            self._finish(session, "failed", result.error or "Planner run failed.")
            return None, result.tokens_consumed
        output = result.planner_output or "\n\n".join(messages)
        self._log(session, f"Planner round {session.round} finished in {int(time.monotonic() - started)}s.")
        return output, result.tokens_consumed

    def _apply_payload(self, session: OrchestrationSession, payload: PlannerPayload) -> None:
        if payload.summary:
            session.summary = payload.summary
        if payload.done:
            unfinished = [
                card.card_id
                for card in session.cards.values()
                if card.status != "promoted" and not self._replacement_promoted(session, card)
            ]
            abandoned = [card_id for card_id in unfinished if card_id in payload.summary]
            missing = [card_id for card_id in unfinished if card_id not in abandoned]
            if missing:
                self._finish(
                    session,
                    "failed",
                    "Planner declared the session done, but these cards are neither promoted nor "
                    f"abandoned in the summary: {', '.join(missing)}.",
                )
                return
            self._finish(
                session,
                "completed",
                None if not abandoned else f"Completed with abandoned cards: {', '.join(abandoned)}.",
            )
            return
        added: list[str] = []
        for card in cards_from_payload(payload):
            task = card.task
            if task.reissues:
                original = session.cards.get(task.reissues)
                if original is None:
                    self._log(session, f"Ignored {task.task_id}: it re-issues unknown card {task.reissues}.")
                    continue
                if original.reissue_count >= self.orchestrate.task_reissue_limit:
                    self._log(
                        session,
                        f"Refused {task.task_id}: {original.card_id} already re-issued "
                        f"{original.reissue_count} time(s), the limit is {self.orchestrate.task_reissue_limit}.",
                    )
                    continue
                original.reissue_count += 1
                original.status = "reissued"
                original.reissued_by = task.task_id
            session.cards[task.task_id] = card
            self.store.write_card(session, card)
            added.append(task.task_id)
        self._log(session, f"Planner added cards: {', '.join(added) or '(none)'}.")
        if not added and not self._ready(session) and not session.cards_with_status("running", "verifying", "integrating"):
            self._finish(session, "failed", "Planner returned no runnable cards and did not finish the session.")
            return
        session.status = "dispatching"
        self.store.write_plan(session)
        self._persist(session)
        self._notify(session, f"Planner round {session.round} added {len(added)} card(s).")

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    def _dispatch(self, session: OrchestrationSession) -> None:
        if self._stopping(session) or session.cards_with_status("failed"):
            return
        session.status = "dispatching"
        cap = min(session.max_workers, self.settings.max_concurrent_tasks)
        if cap < session.max_workers and not any("max_concurrent_tasks" in line for line in session.log):
            self._log(
                session,
                f"Worker cap {session.max_workers} is bound by max_concurrent_tasks={self.settings.max_concurrent_tasks}.",
            )
        active = len(session.cards_with_status("running", "verifying", "integrating"))
        for task in self._ready(session):
            if active >= cap:
                break
            card = session.cards[task.task_id]
            self._submit_worker(session, card)
            active += 1
        for card in session.cards.values():
            if card.status == "pending" and not all(
                parent in self._promoted_ids(session) for parent in card.task.depends_on
            ):
                card.status = "waiting"
        self._persist(session)

    def _submit_worker(self, session: OrchestrationSession, card: TaskCard) -> None:
        card_markdown = self.store.render_card(card)
        provider, model, reasoning = session.worker_selection
        record = self.task_coordinator.submit(
            f"{card.card_id}: {card.task.title}\n\n{card.task.goal}",
            provider,
            model,
            reasoning,
            mode="coding",
            session_id=session.session_id,
            card_id=card.card_id,
            card_markdown=card_markdown,
            resolver_selection=session.planner_selection,
            before_agent=lambda context, card=card: self.store.place_card_in_worktree(card, context.path),
            after_agent=lambda context, result, card=card: self._capture_worker(session, card, context, result),
        )
        card.worker_task_id = record.task_id
        card.status = "running"
        card.error = ""
        card.prompt_chars = len(build_worker_prompt(card_markdown, self._load_role_rules(), self._coding_profile()))
        self._log(
            session,
            f"Dispatched {card.card_id} ({card.task.title}) as task {record.task_id}; "
            f"{card.prompt_chars} characters of context.",
        )
        self._notify(session, f"Dispatched {card.card_id} as task {record.task_id}.")

    def _capture_worker(
        self,
        session: OrchestrationSession,
        card: TaskCard,
        context: WorktreeContext,
        result: AgentResult,
    ) -> None:
        """Read the worker's report and ticked card before its worktree is committed."""
        try:
            raw = result.output or result.error or ""
            self.store.write_report(session, card, raw)
            report = parse_worker_report(raw)
            card.report = report
            ticks = self.store.read_card_from_worktree(context.path)
            # The card file wins when both are present.
            card.checklist_state = ticks if ticks is not None else tuple(report.checklist)
            self._log(
                session,
                f"{card.card_id} reported {report.status} with {card.ticks_text} checklist items"
                + (f": {report.errors}" if report.errors else "."),
            )
            self._persist(session)
        except Exception as error:  # Never break the worker's own run.
            log_exception(f"Could not capture worker report session={session.session_id} card={card.card_id}", error)

    def _on_worker_event(self, record: TaskRecord, phase: str, message: str, kind: str) -> None:
        session_id = getattr(record, "session_id", None)
        if not session_id:
            return
        with self._lock:
            if session_id in self._sessions:
                self._wakeup.notify_all()

    def _wait_for_workers(self, session: OrchestrationSession) -> None:
        """Block until no card runs and either one failed or nothing else can start."""
        while True:
            self._reconcile_workers(session)
            running = session.cards_with_status("running", "verifying", "integrating")
            if self._stopping(session):
                if not running:
                    return
            elif not running:
                if session.cards_with_status("failed") or not self._ready(session):
                    return
                # Something became ready (a dependency promoted): dispatch it.
                self._dispatch(session)
                continue
            elif self._ready(session) and not session.cards_with_status("failed"):
                cap = min(session.max_workers, self.settings.max_concurrent_tasks)
                if len(running) < cap:
                    self._dispatch(session)
                    continue
            with self._lock:
                self._wakeup.wait(timeout=0.5)

    def _reconcile_workers(self, session: OrchestrationSession) -> None:
        changed = False
        resolving = False
        for card in session.cards.values():
            if not card.active or not card.worker_task_id:
                continue
            record = self.task_coordinator.get(card.worker_task_id)
            if record is None:
                card.status = "failed"
                card.error = "Worker task disappeared from the task coordinator."
                changed = True
                continue
            status = record.status
            if status in _SETTLED_TASK_STATUSES:
                # The orchestrator's final event sets the status before the
                # run returns with its tokens; wait for the worker thread to
                # finish so the record is complete.
                future = getattr(record, "future", None)
                if future is not None and not future.done():
                    try:
                        future.result(timeout=10)
                    except Exception:  # Timed out or cancelled: try again next pass.
                        continue
                if record.status not in _SETTLED_TASK_STATUSES:
                    continue
                self._settle_card(session, card, record)
                changed = True
                continue
            if status == "resolving":
                resolving = True
            mapped = _CARD_STATUS_FOR_TASK.get(status, card.status)
            if mapped != card.status:
                card.status = mapped
                changed = True
        if session.active and session.status != "planning":
            running = session.cards_with_status("running", "verifying", "integrating")
            new_status = "resolving" if resolving else ("waiting" if running else session.status)
            if new_status != session.status:
                session.status = new_status
                changed = True
        if changed:
            self._persist(session)
            self._notify(session, "Worker status changed.")

    def _settle_card(self, session: OrchestrationSession, card: TaskCard, record: TaskRecord) -> None:
        card.tokens = record.tokens_consumed
        card.branch_name = record.branch_name or card.branch_name
        if record.status == "completed":
            card.status = "promoted"
            card.promoted_commit = self._primary_tip()
            if card.report is not None and not card.checklist_state:
                card.checklist_state = tuple(card.report.checklist)
            self._log(session, f"{card.card_id} promoted ({card.ticks_text} checklist).")
        elif record.status == "paused" or (record.status == "interrupted" and self._stopping(session)):
            card.status = "stopped"
            card.error = record.error or "Worker stopped."
            self._log(session, f"{card.card_id} stopped.")
        else:
            card.status = "failed"
            card.error = record.error or f"Worker task {record.status}."
            self._log(session, f"{card.card_id} failed: {' '.join(card.error.split())[:300]}")
        session.tokens_workers = sum(
            item.tokens for item in session.cards.values() if item.worker_task_id
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ready(self, session: OrchestrationSession):
        promoted = self._promoted_ids(session)
        active = [card.card_id for card in session.cards.values() if card.active]
        failed = [
            card.card_id
            for card in session.cards.values()
            if card.status in {"failed", "reissued", "stopped"}
        ]
        return ready_tasks(session.tasks(), promoted, active, failed)

    def _promoted_ids(self, session: OrchestrationSession) -> set[str]:
        """Promoted cards plus re-issued cards whose replacement was promoted."""
        promoted = {card.card_id for card in session.cards.values() if card.status == "promoted"}
        changed = True
        while changed:
            changed = False
            for card in session.cards.values():
                if card.status == "reissued" and card.reissued_by in promoted and card.card_id not in promoted:
                    promoted.add(card.card_id)
                    changed = True
        return promoted

    def _replacement_promoted(self, session: OrchestrationSession, card: TaskCard) -> bool:
        return card.status == "reissued" and card.card_id in self._promoted_ids(session)

    def _all_promoted(self, session: OrchestrationSession) -> bool:
        promoted = self._promoted_ids(session)
        return bool(session.cards) and all(card.card_id in promoted for card in session.cards.values())

    def _round_conflict(self, session: OrchestrationSession, payload: PlannerPayload) -> str | None:
        """Reject new cards whose scope overlaps a card that is still unsettled."""
        live = [card for card in session.cards.values() if not card.settled]
        for task in payload.tasks:
            for card in live:
                if card.card_id in task.depends_on:
                    continue
                shared = sorted(set(task.file_scope) & set(card.task.file_scope))
                if shared:
                    return (
                        f"Planner task {task.task_id!r} shares file scope with unfinished card "
                        f"{card.card_id!r}: {', '.join(shared)}."
                    )
        return None

    def _stopping(self, session: OrchestrationSession) -> bool:
        with self._lock:
            return session.session_id in self._stop_requested or self._closed

    def _finish(self, session: OrchestrationSession, status: str, error: str | None) -> None:
        session.status = status
        session.error = error
        session.finished_at = time.time()
        for card in session.cards.values():
            if card.status in {"pending", "waiting"}:
                card.status = "stopped"
        self._log(session, f"Session {status}." + (f" {error}" if error else ""))
        self.store.write_plan(session)
        self._persist(session)
        self._notify(session, f"Session {status}.", "error" if status == "failed" else "status")

    def _remove_worktree(self, context: WorktreeContext) -> None:
        try:
            GitWorktreeManager(
                self.repository, self.settings.primary_branch, self.settings.worktree_root
            ).remove_successful(context)
        except GitWorktreeError as error:
            LOGGER.warning("Could not remove planner worktree path=%s error=%s", context.path, error)

    def _primary_tip(self) -> str:
        try:
            return GitWorktreeManager(
                self.repository, self.settings.primary_branch, self.settings.worktree_root
            ).capture_primary()
        except (GitWorktreeError, OSError):
            return ""

    def _repository_map(self) -> str:
        """Bounded ``git ls-files`` listing for the first planner turn, or empty."""
        budget = self.orchestrate.planner_repository_map_chars
        if budget <= 0:
            return ""
        try:
            process = subprocess.run(
                ["git", "ls-files"],
                cwd=self.repository,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            LOGGER.warning("Could not list repository files for the planner error=%s", error)
            return ""
        if process.returncode != 0:
            return ""
        return bounded_digest(process.stdout.strip(), budget)

    def _verification_hint(self) -> str:
        configured = [list(command) for command in self.settings.verification_commands]
        try:
            commands = discover_commands(self.repository, configured)
        except OSError:
            commands = configured
        return " && ".join(" ".join(command) for command in commands if command)

    def _coding_profile(self) -> str | None:
        for path in (
            self.repository / ".agents" / "profiles" / "coding.md",
            BUNDLED_PROFILE_ROOT / "coding.md",
        ):
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                continue
        return None

    def _load_role_rules(self) -> str:
        if self._role_rules is None:
            self._role_rules = load_role_rules()
        return self._role_rules

    def _log(self, session: OrchestrationSession, text: str) -> None:
        session.add_line(text)
        LOGGER.info("Orchestrate session=%s %s", session.session_id, " ".join(text.split())[:200])

    def _persist(self, session: OrchestrationSession) -> None:
        try:
            self.memory.record_orchestration(session.to_dict())
        except (OSError, ValueError) as error:
            LOGGER.warning("Could not persist session session=%s error=%s", session.session_id, error)

    def _notify(self, session: OrchestrationSession, message: str, kind: str = "status") -> None:
        if self.on_event is None:
            return
        record = SessionEventRecord(
            task_id=session.session_id,
            session_id=session.session_id,
            status=session.status,
            error=session.error,
        )
        try:
            self.on_event(record, ORCHESTRATE_PHASE, message, kind)
        except Exception as error:  # UI failures must not stop a session.
            log_exception(f"Orchestrate event callback failed session={session.session_id}", error)

    def _restore_sessions(self) -> None:
        try:
            snapshots = self.memory.get_orchestrations()
        except (OSError, ValueError) as error:
            LOGGER.warning("Could not restore sessions for project=%s error=%s", self.repository, error)
            return
        highest = 0
        for snapshot in snapshots.values():
            if snapshot.get("project_key") != self.project_key:
                continue
            session = OrchestrationSession.from_dict(snapshot)
            if session is None:
                continue
            highest = max(highest, _sequence_of(session.session_id))
            if session.mark_stopped_by_restart():
                self._persist(session)
            self._sessions[session.session_id] = session
        self._next_sequence = highest + 1


def _sequence_of(session_id: str) -> int:
    parts = session_id.split("-")
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return 0


__all__ = [
    "ORCHESTRATE_PHASE",
    "OrchestrateCoordinator",
    "SessionEventRecord",
]
