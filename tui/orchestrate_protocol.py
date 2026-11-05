"""Structured payloads exchanged between Orchestrate Mode agents and the TUI.

The planner returns a plan; the TUI — not the agent — turns that plan into task
cards, so a planner cannot silently do worker work. Workers return a report and
tick the checklist in their card file. Both payloads follow the same
marker-plus-JSON pattern as :mod:`tui.plan`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
from typing import Any, Iterable, Sequence


ORCHESTRATION_START = "BEGIN_DAEDALUS_ORCHESTRATION"
ORCHESTRATION_END = "END_DAEDALUS_ORCHESTRATION"
WORKER_REPORT_START = "BEGIN_DAEDALUS_WORKER_REPORT"
WORKER_REPORT_END = "END_DAEDALUS_WORKER_REPORT"

#: Worker outcomes. An unparseable report is reported as ``partial`` so the
#: planner sees unfinished work rather than a silent success.
WORKER_STATUSES: tuple[str, ...] = ("done", "partial", "blocked")

#: Role rules and card template bundled with the TUI.
TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates" / "orchestrate"
ROLE_RULES_PATH = TEMPLATE_ROOT / "AGENTS.md"
CARD_TEMPLATE_PATH = TEMPLATE_ROOT / "task-card.md"

_CHECKLIST_ITEM = re.compile(r"^\s*[-*]\s*\[( |x|X)\]\s*(.*)$")
_HEADING = re.compile(r"^\s*#{1,6}\s+(.*?)\s*$")


@dataclass(frozen=True)
class PlannerTask:
    """One task card as the planner described it."""

    task_id: str
    title: str
    goal: str
    checklist: tuple[str, ...]
    file_scope: tuple[str, ...]
    read_first: tuple[str, ...] = ()
    interfaces: str = ""
    verify: str = ""
    depends_on: tuple[str, ...] = ()
    reissues: str | None = None


@dataclass(frozen=True)
class PlannerPayload:
    """The planner's answer for one round."""

    summary: str
    tasks: tuple[PlannerTask, ...] = ()
    done: bool = False
    valid: bool = True
    error: str | None = None


@dataclass(frozen=True)
class WorkerReport:
    """One worker's account of the card it was given."""

    task_id: str
    status: str
    checklist: tuple[bool, ...] = ()
    files_changed: tuple[str, ...] = ()
    errors: str = ""
    notes: str = ""
    valid: bool = True
    error: str | None = None


def load_role_rules() -> str:
    """Return the bundled role rules the prompt builders embed by heading."""
    return ROLE_RULES_PATH.read_text(encoding="utf-8")


def load_card_template() -> str:
    """Return the bundled task-card template."""
    return CARD_TEMPLATE_PATH.read_text(encoding="utf-8")


def parse_planner_payload(response: str, known_ids: Iterable[str] = ()) -> PlannerPayload:
    """Extract and validate the planner's task list from one agent response.

    ``known_ids`` are cards from earlier rounds: a later round may depend on
    them, but may not reuse their ids.
    """
    payload_text = _payload_text(response, ORCHESTRATION_START, ORCHESTRATION_END)
    if payload_text is None:
        return _invalid_plan("Planner response was not in the required format.")
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as error:
        return _invalid_plan(f"Planner response was not valid JSON: {error.msg}.")
    if not isinstance(payload, dict):
        return _invalid_plan("Planner payload must be a JSON object.")

    summary = payload.get("summary", "")
    done = payload.get("done", False)
    raw_tasks = payload.get("tasks", [])
    if not isinstance(summary, str):
        return _invalid_plan("Planner payload summary must be a string.")
    if not isinstance(done, bool):
        return _invalid_plan("Planner payload done must be true or false.")
    if not isinstance(raw_tasks, list):
        return _invalid_plan("Planner payload tasks must be an array.", summary)

    tasks: list[PlannerTask] = []
    try:
        for raw_task in raw_tasks:
            tasks.append(_parse_task(raw_task))
    except ValueError as error:
        return _invalid_plan(str(error), summary)

    error = _plan_structure_error(tasks, done, set(known_ids))
    if error is not None:
        return _invalid_plan(error, summary)
    return PlannerPayload(summary.strip(), tuple(tasks), done)


def parse_worker_report(response: str) -> WorkerReport:
    """Extract a worker's report, degrading to ``partial`` when it is unusable."""
    payload_text = _payload_text(response, WORKER_REPORT_START, WORKER_REPORT_END)
    if payload_text is None:
        return _invalid_report("Worker report was not in the required format.")
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as error:
        return _invalid_report(f"Worker report was not valid JSON: {error.msg}.")
    if not isinstance(payload, dict):
        return _invalid_report("Worker report must be a JSON object.")

    task_id = payload.get("task", "")
    status = payload.get("status", "")
    raw_checklist = payload.get("checklist", [])
    raw_files = payload.get("files_changed", [])
    errors = payload.get("errors", "")
    notes = payload.get("notes", "")
    if not isinstance(task_id, str) or not task_id.strip():
        return _invalid_report("Worker report is missing the task id.")
    if status not in WORKER_STATUSES:
        return _invalid_report(
            f"Worker report status must be one of {', '.join(WORKER_STATUSES)}.", task_id
        )
    if not isinstance(raw_checklist, list) or any(
        not isinstance(item, bool) for item in raw_checklist
    ):
        return _invalid_report("Worker report checklist must be an array of booleans.", task_id)
    if not isinstance(raw_files, list) or any(not isinstance(item, str) for item in raw_files):
        return _invalid_report("Worker report files_changed must be an array of strings.", task_id)
    if not isinstance(errors, str) or not isinstance(notes, str):
        return _invalid_report("Worker report errors and notes must be strings.", task_id)
    return WorkerReport(
        task_id.strip(),
        status,
        tuple(raw_checklist),
        tuple(item.strip() for item in raw_files if item.strip()),
        errors.strip(),
        notes.strip(),
    )


def ready_tasks(
    tasks: Sequence[PlannerTask],
    promoted_ids: Iterable[str],
    active_ids: Iterable[str],
    failed_ids: Iterable[str],
) -> list[PlannerTask]:
    """Return the tasks that can be dispatched now, in payload order.

    A task is ready when it is not already promoted, running, or failed and
    every task it depends on has been promoted — dependencies are ordered by
    promotion so a dependent worker's worktree already contains their changes.
    """
    promoted = set(promoted_ids)
    settled = promoted | set(active_ids) | set(failed_ids)
    return [
        task
        for task in tasks
        if task.task_id not in settled and all(parent in promoted for parent in task.depends_on)
    ]


def render_task_card(task: PlannerTask, template_text: str) -> str:
    """Fill the bundled card template for one task."""
    replacements = {
        "task_id": task.task_id,
        "title": task.title,
        "goal": task.goal.strip(),
        "checklist": "\n".join(f"- [ ] {item}" for item in task.checklist),
        "file_scope": _bullets(task.file_scope),
        "read_first": _bullets(task.read_first, "(nothing beyond your file scope)"),
        "interfaces": task.interfaces.strip() or "(none declared)",
        "verify": task.verify.strip() or "(no verification command was given)",
    }
    card = template_text
    for name, value in replacements.items():
        card = card.replace(f"{{{{{name}}}}}", value)
    return card


def parse_card_ticks(markdown: str) -> tuple[bool, ...]:
    """Return the checklist state a worker left in its card file.

    Only the ``## Checklist`` section counts, so a checkbox a worker wrote
    elsewhere in the card does not shift the answers.
    """
    lines = markdown.splitlines()
    checklist_lines = _checklist_section(lines)
    ticks: list[bool] = []
    for line in checklist_lines:
        match = _CHECKLIST_ITEM.match(line)
        if match:
            ticks.append(match.group(1).lower() == "x")
    return tuple(ticks)


def card_verify_command(markdown: str) -> str:
    """Return the command under a card's ``## Verify`` heading, or ``""``."""
    section = _section(markdown.splitlines(), "verify")
    for line in section:
        text = line.strip()
        if text and not text.startswith("(") and not text.startswith("```"):
            return text
    return ""


def _section(lines: Sequence[str], name: str) -> list[str]:
    section: list[str] = []
    inside = False
    for line in lines:
        heading = _HEADING.match(line)
        if heading:
            inside = heading.group(1).strip().lower() == name
            continue
        if inside:
            section.append(line)
    return section


def _checklist_section(lines: Sequence[str]) -> list[str]:
    section: list[str] = []
    inside = False
    for line in lines:
        heading = _HEADING.match(line)
        if heading:
            inside = heading.group(1).strip().lower() == "checklist"
            continue
        if inside:
            section.append(line)
    return section if section else list(lines)


def _bullets(values: Sequence[str], empty_text: str = "(none)") -> str:
    return "\n".join(f"- {value}" for value in values) or f"- {empty_text}"


def _parse_task(raw_task: Any) -> PlannerTask:
    if not isinstance(raw_task, dict):
        raise ValueError("Each planner task must be an object.")
    task_id = raw_task.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("Each planner task needs an id.")
    task_id = task_id.strip()
    title = _required_text(raw_task.get("title"), task_id, "title")
    goal = _required_text(raw_task.get("goal"), task_id, "goal")
    checklist = _string_list(raw_task.get("checklist"), task_id, "checklist")
    if not checklist:
        raise ValueError(f"Planner task {task_id!r} needs at least one checklist item.")
    file_scope = _string_list(raw_task.get("file_scope"), task_id, "file_scope")
    if not file_scope:
        raise ValueError(f"Planner task {task_id!r} needs a non-empty file_scope.")
    read_first = _string_list(raw_task.get("read_first", []), task_id, "read_first")
    depends_on = _string_list(raw_task.get("depends_on", []), task_id, "depends_on")
    interfaces = raw_task.get("interfaces", "")
    verify = raw_task.get("verify", "")
    reissues = raw_task.get("reissues")
    if not isinstance(interfaces, str) or not isinstance(verify, str):
        raise ValueError(f"Planner task {task_id!r} has invalid interfaces or verify text.")
    if reissues is not None and (not isinstance(reissues, str) or not reissues.strip()):
        raise ValueError(f"Planner task {task_id!r} has an invalid reissues id.")
    return PlannerTask(
        task_id,
        title,
        goal,
        checklist,
        file_scope,
        read_first,
        interfaces.strip(),
        verify.strip(),
        depends_on,
        reissues.strip() if isinstance(reissues, str) else None,
    )


def _plan_structure_error(
    tasks: Sequence[PlannerTask], done: bool, known_ids: set[str] | None = None
) -> str | None:
    """Return the first rule the plan as a whole breaks, if any."""
    ids = [task.task_id for task in tasks]
    if len(ids) != len(set(ids)):
        return "Planner tasks must use unique ids."
    if done and tasks:
        return "A finished plan cannot include new tasks."
    earlier = known_ids or set()
    reused = sorted(set(ids) & earlier)
    if reused:
        return f"Planner tasks reuse ids from an earlier round: {', '.join(reused)}."
    known = set(ids) | earlier
    for task in tasks:
        for parent in task.depends_on:
            if parent == task.task_id:
                return f"Planner task {task.task_id!r} cannot depend on itself."
            if parent not in known:
                return f"Planner task {task.task_id!r} depends on unknown task {parent!r}."
    cycle = _first_cycle(tasks)
    if cycle:
        return f"Planner tasks form a dependency cycle: {' -> '.join(cycle)}."
    return _shared_scope_error(tasks)


def _first_cycle(tasks: Sequence[PlannerTask]) -> list[str]:
    parents = {task.task_id: task.depends_on for task in tasks}
    visiting: set[str] = set()
    done: set[str] = set()

    def walk(task_id: str, trail: list[str]) -> list[str]:
        if task_id in visiting:
            start = trail.index(task_id) if task_id in trail else 0
            return trail[start:] + [task_id]
        if task_id in done:
            return []
        visiting.add(task_id)
        for parent in parents.get(task_id, ()):  # parent must finish first
            cycle = walk(parent, trail + [task_id])
            if cycle:
                return cycle
        visiting.discard(task_id)
        done.add(task_id)
        return []

    for task in tasks:
        cycle = walk(task.task_id, [])
        if cycle:
            return cycle
    return []


def _shared_scope_error(tasks: Sequence[PlannerTask]) -> str | None:
    """Reject overlapping file scopes between tasks that may run concurrently."""
    reachable = _reachable(tasks)
    for index, task in enumerate(tasks):
        for other in tasks[index + 1 :]:
            if other.task_id in reachable.get(task.task_id, set()):
                continue
            if task.task_id in reachable.get(other.task_id, set()):
                continue
            shared = sorted(set(task.file_scope) & set(other.file_scope))
            if shared:
                return (
                    f"Planner tasks {task.task_id!r} and {other.task_id!r} run concurrently but "
                    f"share file scope: {', '.join(shared)}."
                )
    return None


def _reachable(tasks: Sequence[PlannerTask]) -> dict[str, set[str]]:
    """Map every task id to the ids it transitively depends on."""
    parents = {task.task_id: set(task.depends_on) for task in tasks}
    resolved: dict[str, set[str]] = {}

    def walk(task_id: str) -> set[str]:
        if task_id in resolved:
            return resolved[task_id]
        resolved[task_id] = set()  # guards against cycles found separately
        collected: set[str] = set()
        for parent in parents.get(task_id, set()):
            collected.add(parent)
            collected |= walk(parent)
        resolved[task_id] = collected
        return collected

    for task in tasks:
        walk(task.task_id)
    return resolved


def _required_text(value: Any, task_id: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Planner task {task_id!r} needs {field} text.")
    return value.strip()


def _string_list(value: Any, task_id: str, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"Planner task {task_id!r} {field} must be an array of strings.")
    return tuple(item.strip() for item in value if item.strip())


def _invalid_plan(error: str, summary: str = "") -> PlannerPayload:
    return PlannerPayload(summary.strip(), (), False, valid=False, error=error)


def _invalid_report(error: str, task_id: str = "") -> WorkerReport:
    return WorkerReport(task_id.strip(), "partial", (), (), error, "", valid=False, error=error)


def _payload_text(response: str, start_marker: str, end_marker: str) -> str | None:
    """Extract the JSON body between markers, tolerating a fence or bare object."""
    start = response.find(start_marker)
    if start >= 0:
        start += len(start_marker)
        end = response.find(end_marker, start)
        return response[start : end if end >= 0 else len(response)].strip()
    fenced_start = response.find("```")
    if fenced_start >= 0:
        content_start = response.find("\n", fenced_start)
        fenced_end = response.find("```", content_start + 1) if content_start >= 0 else -1
        if content_start >= 0 and fenced_end >= 0:
            return response[content_start + 1 : fenced_end].strip()
    object_start = response.find("{")
    object_end = response.rfind("}")
    if object_start >= 0 and object_end > object_start:
        return response[object_start : object_end + 1].strip()
    return None
