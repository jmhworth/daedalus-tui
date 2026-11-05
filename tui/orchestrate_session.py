"""Orchestrate Mode session state, its task cards, and the files they leave behind.

A session is one operator prompt handed to a planner. Each card the planner
returns becomes a :class:`TaskCard`, which tracks the worker task that runs
it, the checklist ticks it left in its card file, and the report it sent
back. :class:`SessionStore` owns everything written to disk: the plan, the
cards, the reports, the digests, and the card placed inside a worker's
worktree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid
from typing import Iterable

from .config import OrchestrateSettings
from .local_storage import LocalStorage, safe_component
from .orchestrate_protocol import (
    PlannerPayload,
    PlannerTask,
    WorkerReport,
    load_card_template,
    parse_card_ticks,
    render_task_card,
)
from .prompts import bounded_digest


SESSION_STATUSES: tuple[str, ...] = (
    "planning",
    "dispatching",
    "waiting",
    "resolving",
    "completed",
    "failed",
    "stopped",
)
#: Session statuses with work still in flight.
ACTIVE_SESSION_STATUSES = frozenset({"planning", "dispatching", "waiting", "resolving"})
CARD_STATUSES: tuple[str, ...] = (
    "pending",
    "waiting",
    "running",
    "verifying",
    "integrating",
    "promoted",
    "failed",
    "reissued",
    "stopped",
)
#: Card statuses with a worker task still running for the card.
ACTIVE_CARD_STATUSES = frozenset({"running", "verifying", "integrating"})
#: Card statuses that will never change again.
SETTLED_CARD_STATUSES = frozenset({"promoted", "failed", "reissued", "stopped"})
ORCHESTRATION_SCHEMA_VERSION = 1
PLAN_FILENAME = "PLAN.md"
CARDS_DIRNAME = "cards"
REPORTS_DIRNAME = "reports"
RESTART_MESSAGE = (
    "Daedalus was closed while this session was active. Sessions do not resume; "
    "its worker tasks were restored as interrupted and can be continued from the task inbox."
)


def new_session_id(sequence: int) -> str:
    """Return ``orc-<sequence:03d>-<8 hex>`` for the next session of a project."""
    return f"orc-{max(1, int(sequence)):03d}-{uuid.uuid4().hex[:8]}"


@dataclass
class TaskCard:
    """One planner task plus everything the session learned while running it."""

    task: PlannerTask
    status: str = "pending"
    worker_task_id: str | None = None
    checklist_state: tuple[bool, ...] = ()
    report: WorkerReport | None = None
    reissue_count: int = 0
    branch_name: str = ""
    promoted_commit: str = ""
    error: str = ""
    tokens: int = 0
    # Characters of prompt sent to the worker, so the UI can show what the
    # card-only context cost compared with the operator's prompt.
    prompt_chars: int = 0
    reissued_by: str | None = None

    @property
    def card_id(self) -> str:
        return self.task.task_id

    @property
    def active(self) -> bool:
        return self.status in ACTIVE_CARD_STATUSES

    @property
    def settled(self) -> bool:
        return self.status in SETTLED_CARD_STATUSES

    @property
    def ticks(self) -> tuple[bool, ...]:
        """Checklist state padded or trimmed to the card's checklist length."""
        length = len(self.task.checklist)
        state = tuple(self.checklist_state[:length])
        return state + (False,) * (length - len(state))

    @property
    def ticks_text(self) -> str:
        return f"{sum(1 for tick in self.ticks if tick)}/{len(self.task.checklist)}"

    def to_dict(self) -> dict[str, object]:
        task = self.task
        return {
            "id": task.task_id,
            "title": task.title,
            "goal": task.goal,
            "checklist": list(task.checklist),
            "file_scope": list(task.file_scope),
            "read_first": list(task.read_first),
            "interfaces": task.interfaces,
            "verify": task.verify,
            "depends_on": list(task.depends_on),
            "reissues": task.reissues,
            "status": self.status,
            "worker_task_id": self.worker_task_id,
            "checklist_state": list(self.checklist_state),
            "report": _report_to_dict(self.report),
            "reissue_count": self.reissue_count,
            "branch_name": self.branch_name,
            "promoted_commit": self.promoted_commit,
            "error": self.error,
            "tokens": self.tokens,
            "prompt_chars": self.prompt_chars,
            "reissued_by": self.reissued_by,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "TaskCard | None":
        task_id = value.get("id")
        if not isinstance(task_id, str) or not task_id:
            return None
        task = PlannerTask(
            task_id,
            str(value.get("title") or task_id),
            str(value.get("goal") or ""),
            tuple(_strings(value.get("checklist"))),
            tuple(_strings(value.get("file_scope"))),
            tuple(_strings(value.get("read_first"))),
            str(value.get("interfaces") or ""),
            str(value.get("verify") or ""),
            tuple(_strings(value.get("depends_on"))),
            value.get("reissues") if isinstance(value.get("reissues"), str) else None,
        )
        status = value.get("status")
        report_value = value.get("report")
        return cls(
            task,
            status=status if status in CARD_STATUSES else "pending",
            worker_task_id=value.get("worker_task_id") if isinstance(value.get("worker_task_id"), str) else None,
            checklist_state=tuple(bool(item) for item in value.get("checklist_state") or [] if isinstance(item, bool)),
            report=_report_from_dict(report_value) if isinstance(report_value, dict) else None,
            reissue_count=_int(value.get("reissue_count")),
            branch_name=str(value.get("branch_name") or ""),
            promoted_commit=str(value.get("promoted_commit") or ""),
            error=str(value.get("error") or ""),
            tokens=_int(value.get("tokens")),
            prompt_chars=_int(value.get("prompt_chars")),
            reissued_by=value.get("reissued_by") if isinstance(value.get("reissued_by"), str) else None,
        )


@dataclass
class OrchestrationSession:
    """One operator prompt, its planner rounds, and the cards they produced."""

    session_id: str
    project_key: str
    prompt: str
    planner_selection: tuple[str, str, str]
    worker_selection: tuple[str, str, str]
    max_workers: int
    status: str = "planning"
    round: int = 0
    summary: str = ""
    cards: dict[str, TaskCard] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    tokens_planner: int = 0
    tokens_workers: int = 0
    error: str | None = None
    topic: str | None = None
    # Planner output, digests, and dispatch decisions, newest last. The UI
    # bounds what it shows; the complete session files live on disk.
    log: list[str] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return self.status in ACTIVE_SESSION_STATUSES

    @property
    def tokens_total(self) -> int:
        return self.tokens_planner + self.tokens_workers

    @property
    def worker_prompt_chars(self) -> int:
        return sum(card.prompt_chars for card in self.cards.values())

    @property
    def dispatched_cards(self) -> int:
        return sum(1 for card in self.cards.values() if card.worker_task_id)

    def cards_with_status(self, *statuses: str) -> list[TaskCard]:
        wanted = set(statuses)
        return [card for card in self.cards.values() if card.status in wanted]

    def ordered_cards(self) -> list[TaskCard]:
        return list(self.cards.values())

    def tasks(self) -> list[PlannerTask]:
        return [card.task for card in self.cards.values()]

    def card_for_worker(self, worker_task_id: str) -> TaskCard | None:
        for card in self.cards.values():
            if card.worker_task_id == worker_task_id:
                return card
        return None

    def add_line(self, text: str) -> None:
        self.log.append(text)

    def mark_stopped_by_restart(self) -> bool:
        """Settle a session restored mid-flight; nothing resumes on its own."""
        if not self.active:
            return False
        for card in self.cards.values():
            if card.active or card.status in {"pending", "waiting"}:
                card.status = "stopped"
        self.status = "stopped"
        self.error = RESTART_MESSAGE
        self.finished_at = self.finished_at or time.time()
        self.add_line(RESTART_MESSAGE)
        return True

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": ORCHESTRATION_SCHEMA_VERSION,
            "session_id": self.session_id,
            "project_key": self.project_key,
            "prompt": self.prompt,
            "planner_selection": list(self.planner_selection),
            "worker_selection": list(self.worker_selection),
            "max_workers": self.max_workers,
            "status": self.status,
            "round": self.round,
            "summary": self.summary,
            "cards": [card.to_dict() for card in self.cards.values()],
            "started_at": _timestamp(self.started_at),
            "finished_at": _timestamp(self.finished_at) if self.finished_at is not None else None,
            "tokens_planner": self.tokens_planner,
            "tokens_workers": self.tokens_workers,
            "error": self.error,
            "topic": self.topic,
            "log": list(self.log),
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "OrchestrationSession | None":
        session_id = value.get("session_id")
        prompt = value.get("prompt")
        if not isinstance(session_id, str) or not session_id or not isinstance(prompt, str):
            return None
        cards: dict[str, TaskCard] = {}
        for item in value.get("cards") or []:
            if isinstance(item, dict):
                card = TaskCard.from_dict(item)
                if card is not None:
                    cards[card.card_id] = card
        status = value.get("status")
        return cls(
            session_id=session_id,
            project_key=str(value.get("project_key") or ""),
            prompt=prompt,
            planner_selection=_selection(value.get("planner_selection")),
            worker_selection=_selection(value.get("worker_selection")),
            max_workers=max(1, _int(value.get("max_workers")) or 1),
            status=status if status in SESSION_STATUSES else "stopped",
            round=_int(value.get("round")),
            summary=str(value.get("summary") or ""),
            cards=cards,
            started_at=_parse_timestamp(value.get("started_at")),
            finished_at=(
                _parse_timestamp(value.get("finished_at"))
                if isinstance(value.get("finished_at"), str)
                else None
            ),
            tokens_planner=_int(value.get("tokens_planner")),
            tokens_workers=_int(value.get("tokens_workers")),
            error=value.get("error") if isinstance(value.get("error"), str) else None,
            topic=value.get("topic") if isinstance(value.get("topic"), str) else None,
            log=_strings(value.get("log")),
        )


def cards_from_payload(payload: PlannerPayload) -> list[TaskCard]:
    """Turn a valid planner payload into fresh pending cards."""
    return [TaskCard(task) for task in payload.tasks]


class SessionStore:
    """Write and read the files of one session under the TUI storage root."""

    def __init__(self, storage: LocalStorage, settings: OrchestrateSettings):
        self.storage = storage
        self.settings = settings
        self._card_template: str | None = None

    # --- layout -----------------------------------------------------------

    def session_dir(self, project_key: str, session_id: str) -> Path:
        return (
            self.storage.prompts_root
            / safe_component(project_key)
            / self.settings.session_dirname
            / safe_component(session_id)
        )

    def cards_dir(self, session: OrchestrationSession) -> Path:
        return self.session_dir(session.project_key, session.session_id) / CARDS_DIRNAME

    def reports_dir(self, session: OrchestrationSession) -> Path:
        return self.session_dir(session.project_key, session.session_id) / REPORTS_DIRNAME

    def plan_path(self, session: OrchestrationSession) -> Path:
        return self.session_dir(session.project_key, session.session_id) / PLAN_FILENAME

    # --- session files ----------------------------------------------------

    def write_plan(self, session: OrchestrationSession, raw_payload: str | None = None) -> Path:
        """Write ``PLAN.md`` and, when given, the round's raw planner payload."""
        directory = self.session_dir(session.project_key, session.session_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / PLAN_FILENAME
        path.write_text(render_plan(session), encoding="utf-8")
        if raw_payload is not None:
            (directory / f"plan-round-{session.round}.json").write_text(raw_payload, encoding="utf-8")
        return path

    def read_plan(self, session: OrchestrationSession) -> str:
        path = self.plan_path(session)
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return render_plan(session)

    def write_card(self, session: OrchestrationSession, card: TaskCard) -> Path:
        directory = self.cards_dir(session)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{safe_component(card.card_id)}.md"
        path.write_text(self.render_card(card), encoding="utf-8")
        return path

    def write_report(self, session: OrchestrationSession, card: TaskCard, raw_text: str) -> Path:
        directory = self.reports_dir(session)
        directory.mkdir(parents=True, exist_ok=True)
        prefix = f"{safe_component(card.card_id)}-"
        existing = [entry for entry in directory.glob(f"{prefix}*.md")]
        path = directory / f"{prefix}{len(existing) + 1}.md"
        path.write_text(raw_text, encoding="utf-8")
        return path

    def write_digest(self, session: OrchestrationSession) -> str:
        """Render the bounded planner digest and keep a copy for the round."""
        text = bounded_digest(self.render_digest(session), self.settings.planner_digest_budget_chars)
        directory = self.session_dir(session.project_key, session.session_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"digest-round-{session.round}.txt").write_text(text, encoding="utf-8")
        return text

    # --- worktree card ----------------------------------------------------

    def worktree_card_path(self, worktree: Path) -> Path:
        return worktree / self.settings.runtime_artifact_dirname / self.settings.card_filename

    def place_card_in_worktree(self, card: TaskCard, worktree: Path) -> Path:
        """Write the card the worker ticks; the directory is a runtime artifact."""
        path = self.worktree_card_path(worktree)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render_card(card), encoding="utf-8")
        return path

    def read_card_from_worktree(self, worktree: Path) -> tuple[bool, ...] | None:
        path = self.worktree_card_path(worktree)
        try:
            return parse_card_ticks(path.read_text(encoding="utf-8"))
        except OSError:
            return None

    # --- rendering --------------------------------------------------------

    def render_card(self, card: TaskCard) -> str:
        if self._card_template is None:
            self._card_template = load_card_template()
        return render_task_card(card.task, self._card_template)

    def render_digest(self, session: OrchestrationSession) -> str:
        return render_digest(
            session,
            self.settings.planner_round_limit,
            self.settings.worker_report_budget_chars,
        )


def render_plan(session: OrchestrationSession) -> str:
    """Markdown summary of the session and a table of its cards."""
    lines = [
        f"# Orchestration {session.session_id}",
        "",
        f"Status: {session.status}    Round: {session.round}    "
        f"Workers: {session.max_workers}    "
        f"Tokens: planner {session.tokens_planner}, workers {session.tokens_workers}",
        "",
        "## Prompt",
        "",
        session.prompt.strip(),
        "",
        "## Summary",
        "",
        session.summary.strip() or "(no plan yet)",
        "",
        "## Cards",
        "",
        "| Card | Title | Status | Checklist | Depends on | Worker task |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for card in session.cards.values():
        lines.append(
            f"| {card.card_id} | {_cell(card.task.title)} | {card.status} | {card.ticks_text} | "
            f"{', '.join(card.task.depends_on) or '—'} | {card.worker_task_id or '—'} |"
        )
    if session.error:
        lines.extend(["", "## Error", "", session.error])
    return "\n".join(lines) + "\n"


CONTEXT_HEADER = (
    "# Daedalus orchestration context\n"
    "\n"
    "Daedalus writes this file after every Orchestrate Mode planner round and when a "
    "session ends, then pushes it with the operating branch. It records each session's "
    "prompt, plan, and card outcomes so a later planner (in another session, after a "
    "restart, or on another machine) continues from what was already planned instead of "
    "starting over. Promoted cards are merged into this branch; stopped, failed, and "
    "never-dispatched cards may be re-issued. Do not edit this file by hand: Daedalus "
    "overwrites it.\n"
)


def render_context(sessions: Iterable[OrchestrationSession]) -> str:
    """Markdown record of every session, written for readers without Daedalus.

    The newest session comes last. Each card carries its full text (goal,
    checklist with ticks, scope, interfaces, verify command) because a planner
    reading this in a fresh worktree has nothing else to re-issue it from.
    """
    ordered = sorted(sessions, key=lambda item: (item.started_at, item.session_id))
    lines = [CONTEXT_HEADER]
    if not ordered:
        lines.append("No sessions recorded yet.\n")
    for session in ordered:
        header = (
            f"Status: {session.status}    Round: {session.round}    "
            f"Workers: {session.max_workers}    Started: {_timestamp(session.started_at)}"
        )
        if session.finished_at:
            header += f"    Finished: {_timestamp(session.finished_at)}"
        lines.extend(
            [
                f"## Session {session.session_id}",
                "",
                header,
                "",
                "### Prompt",
                "",
                session.prompt.strip(),
                "",
                "### Summary",
                "",
                session.summary.strip() or "(no plan recorded)",
                "",
            ]
        )
        if session.cards:
            lines.extend(
                [
                    "### Cards",
                    "",
                    "| Card | Title | Status | Checklist | Depends on | Promoted commit |",
                    "| --- | --- | --- | --- | --- | --- |",
                ]
            )
            for card in session.cards.values():
                lines.append(
                    f"| {card.card_id} | {_cell(card.task.title)} | {card.status} | {card.ticks_text} | "
                    f"{', '.join(card.task.depends_on) or '—'} | "
                    f"{card.promoted_commit[:12] if card.promoted_commit else '—'} |"
                )
            lines.append("")
            for card in session.cards.values():
                lines.extend(_context_card(card))
        if session.error:
            lines.extend(["### Outcome", "", session.error.strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def _context_card(card: TaskCard) -> list[str]:
    task = card.task
    lines = [f"#### {card.card_id} — {task.title}", "", f"Status: {card.status}", "", task.goal.strip(), ""]
    if task.checklist:
        lines.append("Checklist:")
        lines.extend(
            f"- [{'x' if tick else ' '}] {item}" for item, tick in zip(task.checklist, card.ticks)
        )
        lines.append("")
    details = [
        ("File scope", ", ".join(task.file_scope)),
        ("Read first", ", ".join(task.read_first)),
        ("Interfaces", task.interfaces.strip()),
        ("Verify", task.verify.strip()),
        ("Re-issues", task.reissues or ""),
        ("Re-issued as", card.reissued_by or ""),
        ("Worker notes", card.report.notes.strip() if card.report is not None else ""),
        ("Worker errors", card.report.errors.strip() if card.report is not None else ""),
        ("Error", " ".join(card.error.split())),
    ]
    for label, value in details:
        if value:
            lines.append(f"- {label}: {value}")
    lines.append("")
    return lines


def render_digest(session: OrchestrationSession, round_limit: int, report_budget: int) -> str:
    """Render the planner-facing status digest described by the protocol.

    ``round_limit`` is the optional safety cap; zero leaves the round uncapped
    in the header because the planner decides when the session ends.
    """
    busy = sum(1 for card in session.cards.values() if card.active)
    round_text = f"round {session.round}"
    if int(round_limit) > 0:
        round_text += f" of {int(round_limit)}"
    lines = [
        f"SESSION {session.session_id}  {round_text}  "
        f"workers {busy}/{session.max_workers} busy"
    ]
    for card in session.cards.values():
        detail = _card_detail(card)
        lines.append(f"{card.card_id}  {card.status:<10} {detail}")
        if card.status in {"failed", "reissued", "stopped"} or (card.report and card.report.status != "done"):
            report_text = _report_text(card)
            if report_text:
                lines.append(f"    report: {_one_line(report_text, report_budget)}")
    return "\n".join(lines)


def _one_line(text: str, limit: int) -> str:
    """Keep a report on one digest line, marking what the budget cut off."""
    flattened = " ".join(text.split())
    if len(flattened) <= limit:
        return flattened
    marker = " […truncated…]"
    return flattened[: max(0, limit - len(marker))].rstrip() + marker


def _card_detail(card: TaskCard) -> str:
    if card.status in {"pending", "waiting"}:
        parents = ", ".join(card.task.depends_on)
        return f"depends_on {parents}" if parents else "ready"
    parts = [f"{card.ticks_text} checklist"]
    files = list(card.report.files_changed) if card.report is not None else []
    if files:
        parts.append(f"files: {', '.join(files)}")
    if card.error and card.status in {"failed", "stopped"}:
        parts.append(f"error: {' '.join(card.error.split())}")
    if card.reissued_by:
        parts.append(f"reissued as {card.reissued_by}")
    return "  ".join(parts)


def _report_text(card: TaskCard) -> str:
    report = card.report
    if report is None:
        return ""
    pieces = [f"status={report.status}"]
    if report.errors:
        pieces.append(f"errors: {report.errors}")
    if report.notes:
        pieces.append(f"notes: {report.notes}")
    if not report.valid and report.error and report.error != report.errors:
        pieces.append(f"parse: {report.error}")
    return " | ".join(pieces)


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def _report_to_dict(report: WorkerReport | None) -> dict[str, object] | None:
    if report is None:
        return None
    return {
        "task": report.task_id,
        "status": report.status,
        "checklist": list(report.checklist),
        "files_changed": list(report.files_changed),
        "errors": report.errors,
        "notes": report.notes,
        "valid": report.valid,
        "error": report.error,
    }


def _report_from_dict(value: dict[str, object]) -> WorkerReport:
    status = value.get("status")
    return WorkerReport(
        str(value.get("task") or ""),
        status if status in ("done", "partial", "blocked") else "partial",
        tuple(bool(item) for item in value.get("checklist") or [] if isinstance(item, bool)),
        tuple(_strings(value.get("files_changed"))),
        str(value.get("errors") or ""),
        str(value.get("notes") or ""),
        bool(value.get("valid", True)),
        value.get("error") if isinstance(value.get("error"), str) else None,
    )


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _int(value: object) -> int:
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _selection(value: object) -> tuple[str, str, str]:
    items = _strings(value)
    while len(items) < 3:
        items.append("")
    return (items[0], items[1], items[2])


def _timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: object) -> float:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return time.time()


__all__ = [
    "ACTIVE_CARD_STATUSES",
    "ACTIVE_SESSION_STATUSES",
    "CARD_STATUSES",
    "ORCHESTRATION_SCHEMA_VERSION",
    "OrchestrationSession",
    "RESTART_MESSAGE",
    "SESSION_STATUSES",
    "SETTLED_CARD_STATUSES",
    "SessionStore",
    "TaskCard",
    "cards_from_payload",
    "new_session_id",
    "render_digest",
    "render_plan",
]
