"""Structured plan review data exchanged between the agent and the TUI."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


PLAN_START = "BEGIN_DAEDALUS_PLAN"
PLAN_END = "END_DAEDALUS_PLAN"
CUSTOM_ANSWER_OPTION_ID = "__daedalus_custom_answer__"
CUSTOM_ANSWER_LABEL = "Custom answer"
_CUSTOM_ANSWER_PREFIX = f"{CUSTOM_ANSWER_OPTION_ID}:"


@dataclass(frozen=True)
class PlanOption:
    option_id: str
    label: str


@dataclass(frozen=True)
class PlanQuestion:
    question_id: str
    text: str
    options: tuple[PlanOption, ...]
    required: bool = True


@dataclass
class PlanClarification:
    """A side-channel clarification about one plan question (not plan follow-up)."""

    clarification_id: str
    question_id: str
    user_question: str
    answer: str = ""
    status: str = "queued"
    error: str | None = None


@dataclass(frozen=True)
class PlanResult:
    plan: str
    questions: tuple[PlanQuestion, ...]
    no_more_questions: bool
    valid: bool = True
    error: str | None = None


def plan_answer_options(question: PlanQuestion) -> tuple[PlanOption, ...]:
    """Return agent choices plus the UI-owned custom-answer choice."""
    if any(option.option_id == CUSTOM_ANSWER_OPTION_ID for option in question.options):
        return question.options
    return question.options + (PlanOption(CUSTOM_ANSWER_OPTION_ID, CUSTOM_ANSWER_LABEL),)


def encode_custom_answer(text: str) -> str:
    """Encode free text without confusing it with an agent option id."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("A custom plan answer cannot be empty.")
    return f"{_CUSTOM_ANSWER_PREFIX}{cleaned}"


def custom_answer_text(answer: str | None) -> str | None:
    """Extract UI-entered text from an encoded custom answer, if present."""
    if not isinstance(answer, str) or not answer.startswith(_CUSTOM_ANSWER_PREFIX):
        return None
    text = answer[len(_CUSTOM_ANSWER_PREFIX) :].strip()
    return text or None


def is_valid_plan_answer(question: PlanQuestion, answer: str | None) -> bool:
    """Validate agent option ids and the software-owned custom answer format."""
    return custom_answer_text(answer) is not None or any(
        option.option_id == answer for option in question.options
    )


def parse_plan_response(response: str) -> PlanResult:
    """Extract the agent's plan payload without exposing protocol text in the UI."""
    candidates = _plan_payload_candidates(response)
    if not candidates:
        return PlanResult(
            response.strip(),
            (),
            False,
            valid=False,
            error="Plan response was not in the required format.",
        )

    # Agents often revise in one turn (prose + multiple BEGIN/END blocks). Prefer
    # the latest valid payload so an earlier broken draft cannot hide questions.
    last_failure: PlanResult | None = None
    for payload_text in reversed(candidates):
        parsed = _parse_plan_payload(payload_text, response)
        if parsed.valid:
            return parsed
        last_failure = parsed
    return last_failure or PlanResult(
        response.strip(),
        (),
        False,
        valid=False,
        error="Plan response was not in the required format.",
    )


def build_plan_clarification_prompt(
    original_prompt: str,
    plan: str,
    question: PlanQuestion,
    clarification: str,
) -> str:
    """Build a read-only ask prompt for one plan question, without other questions."""
    options = "\n".join(f"- {option.option_id}: {option.label}" for option in question.options)
    return (
        "The user is reviewing an implementation plan and needs clarification about one "
        "multiple-choice question before answering it. Explain what the question means and "
        "how the options differ in this context. Do not revise the plan, do not ask new "
        "planning questions, and do not modify files. Answer only the clarification request.\n\n"
        f"Original request:\n{original_prompt}\n\n"
        f"Current plan:\n{plan}\n\n"
        f"Question under review:\n{question.text}\n"
        f"Options:\n{options}\n\n"
        f"User clarification request:\n{clarification.strip()}"
    )


def build_plan_followup_prompt(
    original_prompt: str,
    plan: str,
    questions: tuple[PlanQuestion, ...],
    answers: dict[str, str],
) -> str:
    answer_lines = []
    question_by_id = {question.question_id: question for question in questions}
    for question_id, answer_id in answers.items():
        question = question_by_id.get(question_id)
        if question is None:
            continue
        option = next((option for option in question.options if option.option_id == answer_id), None)
        custom_text = custom_answer_text(answer_id)
        answer_label = (
            f"{CUSTOM_ANSWER_LABEL}: {custom_text}"
            if custom_text
            else (option.label if option else answer_id)
        )
        answer_lines.append(f"- {question.text}: {answer_label}")
    answers_text = "\n".join(answer_lines) or "(No answers were supplied.)"
    return (
        "Re-evaluate the plan using the user's answers below. Preserve the original request and "
        "return the exact structured plan format from your planning instructions. Ask another "
        "multiple-choice question if any decision is still required. Every question must still mark "
        "exactly one option with \" (Recommended)\" as the suggested default. Set no_more_questions "
        "to true only when you have no remaining questions that could change the implementation. "
        "Do not modify files.\n\n"
        f"Original request:\n{original_prompt}\n\n"
        f"Current plan:\n{plan}\n\n"
        f"User answers:\n{answers_text}"
    )


def build_implementation_prompt(
    original_prompt: str,
    plan: str,
    answers: dict[str, str],
    answer_details: dict[str, str] | None = None,
) -> str:
    answer_details = answer_details or {}
    answer_text = "\n".join(
        f"- {question_id}: {custom_answer_text(answer) or answer}"
        + (f" ({answer_details[question_id]})" if question_id in answer_details else "")
        for question_id, answer in answers.items()
    )
    return (
        f"Original user request:\n{original_prompt}\n\n"
        f"Approved implementation plan:\n{plan}\n\n"
        "Decisions confirmed during plan review:\n"
        f"{answer_text or '- No additional decisions were required.'}\n\n"
        "Implement the approved plan in this worktree. Do not reopen plan review unless a blocking "
        "technical problem makes the plan impossible; in that case explain the problem clearly."
    )


def _parse_plan_payload(payload_text: str, raw_response: str) -> PlanResult:
    try:
        payload = _loads_plan_json(payload_text)
    except json.JSONDecodeError as error:
        return PlanResult(
            raw_response.strip(),
            (),
            False,
            valid=False,
            error=f"Plan response was not valid JSON: {error.msg}.",
        )
    if not isinstance(payload, dict):
        return PlanResult(
            raw_response.strip(),
            (),
            False,
            valid=False,
            error="Plan payload must be a JSON object.",
        )

    plan = payload.get("plan")
    raw_questions = payload.get("questions", [])
    no_more_questions = payload.get("no_more_questions")
    if not isinstance(plan, str) or not plan.strip():
        return PlanResult(
            raw_response.strip(),
            (),
            False,
            valid=False,
            error="Plan payload is missing a plan.",
        )
    if not isinstance(raw_questions, list) or not isinstance(no_more_questions, bool):
        return PlanResult(
            plan.strip(),
            (),
            False,
            valid=False,
            error="Plan payload must include questions and no_more_questions.",
        )

    questions: list[PlanQuestion] = []
    try:
        for raw_question in raw_questions:
            questions.append(_parse_question(raw_question))
    except ValueError as error:
        return PlanResult(plan.strip(), (), False, valid=False, error=str(error))
    question_ids = [question.question_id for question in questions]
    if len(question_ids) != len(set(question_ids)):
        return PlanResult(
            plan.strip(),
            (),
            False,
            valid=False,
            error="Plan questions must use unique ids.",
        )
    if no_more_questions and questions:
        return PlanResult(
            plan.strip(),
            (),
            False,
            valid=False,
            error="A confirmed plan cannot include unanswered questions.",
        )
    return PlanResult(plan.strip(), tuple(questions), no_more_questions)


def _loads_plan_json(payload_text: str) -> Any:
    """Parse plan JSON, tolerating raw control characters inside string values."""
    try:
        return json.loads(payload_text)
    except json.JSONDecodeError:
        return json.loads(_escape_unescaped_controls_in_json_strings(payload_text))


def _escape_unescaped_controls_in_json_strings(text: str) -> str:
    """Escape raw newlines/tabs inside JSON strings (common LLM soft-wrap damage)."""
    result: list[str] = []
    in_string = False
    escape = False
    for character in text:
        if in_string:
            if escape:
                result.append(character)
                escape = False
                continue
            if character == "\\":
                result.append(character)
                escape = True
                continue
            if character == '"':
                result.append(character)
                in_string = False
                continue
            if character == "\n":
                result.append("\\n")
                continue
            if character == "\r":
                result.append("\\r")
                continue
            if character == "\t":
                result.append("\\t")
                continue
            if ord(character) < 0x20:
                result.append(f"\\u{ord(character):04x}")
                continue
            result.append(character)
            continue
        if character == '"':
            in_string = True
        result.append(character)
    return "".join(result)


def _plan_payload_candidates(response: str) -> list[str]:
    """Return every BEGIN/END plan blob, then fence/bare-object fallbacks."""
    payloads: list[str] = []
    search_from = 0
    while True:
        start = response.find(PLAN_START, search_from)
        if start < 0:
            break
        content_start = start + len(PLAN_START)
        end = response.find(PLAN_END, content_start)
        if end < 0:
            payloads.append(response[content_start:].strip())
            break
        payloads.append(response[content_start:end].strip())
        search_from = end + len(PLAN_END)
    if payloads:
        return payloads

    fenced_start = response.find("```")
    if fenced_start >= 0:
        content_start = response.find("\n", fenced_start)
        fenced_end = response.find("```", content_start + 1) if content_start >= 0 else -1
        if content_start >= 0 and fenced_end >= 0:
            return [response[content_start + 1 : fenced_end].strip()]

    object_start = response.find("{")
    object_end = response.rfind("}")
    if object_start >= 0 and object_end > object_start:
        return [response[object_start : object_end + 1].strip()]
    return []


def _payload_text(response: str) -> str | None:
    """Compatibility helper: first plan payload candidate, if any."""
    candidates = _plan_payload_candidates(response)
    return candidates[0] if candidates else None


def _parse_question(raw_question: Any) -> PlanQuestion:
    if not isinstance(raw_question, dict):
        raise ValueError("Each plan question must be an object.")
    question_id = raw_question.get("id")
    text = raw_question.get("question")
    raw_options = raw_question.get("options")
    if not isinstance(question_id, str) or not question_id.strip():
        raise ValueError("Each plan question needs an id.")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Plan question {question_id!r} needs question text.")
    if not isinstance(raw_options, list) or len(raw_options) < 2:
        raise ValueError(f"Plan question {question_id!r} needs at least two options.")
    options = []
    for raw_option in raw_options:
        if not isinstance(raw_option, dict):
            raise ValueError(f"Plan question {question_id!r} has an invalid option.")
        option_id = raw_option.get("id")
        label = raw_option.get("label")
        if not isinstance(option_id, str) or not option_id.strip() or not isinstance(label, str) or not label.strip():
            raise ValueError(f"Plan question {question_id!r} has an invalid option.")
        options.append(PlanOption(option_id.strip(), label.strip()))
    option_ids = [option.option_id for option in options]
    if len(option_ids) != len(set(option_ids)):
        raise ValueError(f"Plan question {question_id!r} must use unique option ids.")
    required = raw_question.get("required", True)
    if not isinstance(required, bool):
        raise ValueError(f"Plan question {question_id!r} has an invalid required value.")
    return PlanQuestion(question_id.strip(), text.strip(), tuple(options), required)
