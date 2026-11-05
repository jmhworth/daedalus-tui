"""Turn, run, and title model for one task conversation.

A **task** is the durable conversation. A **turn** is one submitted user
prompt (or, for legacy history, a generated Plan follow-up kept as context). A
**run** is one execution attempt for a turn: retrying an unchanged prompt adds
a run, while submitting edited or additional text adds a turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
import uuid


TASK_SCHEMA_VERSION = 2
USER_TURN = "user"
GENERATED_TURN = "generated"

_MARKDOWN_DECORATION = re.compile(r"^(?:[#>*\-+\s]|\d+[.)]\s|`+|~+)+")
_TRAILING_DECORATION = re.compile(r"[\s#*`_~:;,.\-]+$")


def new_turn_id() -> str:
    return f"turn-{uuid.uuid4().hex[:10]}"


def new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:10]}"


def iso_timestamp(value: float | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_timestamp(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


@dataclass
class TaskTurn:
    """One submitted prompt, immutable once recorded."""

    turn_id: str
    sequence: int
    text: str
    submitted_at: float | None = None
    kind: str = USER_TURN
    revises_turn_id: str | None = None
    provider: str = ""
    model: str = ""
    reasoning: str = ""
    mode: str = "coding"
    topic: str | None = None
    branch: str = ""
    archive_path: str | None = None

    @property
    def is_user(self) -> bool:
        return self.kind == USER_TURN

    def to_dict(self) -> dict[str, object]:
        return {
            "turn_id": self.turn_id,
            "sequence": self.sequence,
            "text": self.text,
            "submitted_at": iso_timestamp(self.submitted_at),
            "kind": self.kind,
            "revises_turn_id": self.revises_turn_id,
            "provider": self.provider,
            "model": self.model,
            "reasoning": self.reasoning,
            "mode": self.mode,
            "topic": self.topic,
            "branch": self.branch,
            "archive_path": self.archive_path,
        }

    @classmethod
    def from_dict(cls, value: object) -> "TaskTurn | None":
        if not isinstance(value, dict):
            return None
        text = value.get("text")
        turn_id = value.get("turn_id")
        if not isinstance(text, str) or not isinstance(turn_id, str) or not turn_id:
            return None
        try:
            sequence = max(1, int(value.get("sequence", 1)))
        except (TypeError, ValueError):
            sequence = 1
        revises = value.get("revises_turn_id")
        topic = value.get("topic")
        archive = value.get("archive_path")
        kind = value.get("kind")
        return cls(
            turn_id=turn_id,
            sequence=sequence,
            text=text,
            submitted_at=parse_timestamp(value.get("submitted_at")),
            kind=kind if kind in (USER_TURN, GENERATED_TURN) else USER_TURN,
            revises_turn_id=revises if isinstance(revises, str) and revises else None,
            provider=str(value.get("provider") or ""),
            model=str(value.get("model") or ""),
            reasoning=str(value.get("reasoning") or ""),
            mode=str(value.get("mode") or "coding"),
            topic=topic if isinstance(topic, str) and topic else None,
            branch=str(value.get("branch") or ""),
            archive_path=archive if isinstance(archive, str) and archive else None,
        )


@dataclass
class TaskRun:
    """One execution attempt for a turn."""

    run_id: str
    turn_id: str
    attempt: int = 1
    status: str = "queued"
    started_at: float | None = None
    finished_at: float | None = None
    message_start: int = 0
    message_end: int | None = None
    error: str | None = None
    diagnostics_path: str | None = None
    tokens: int | None = None
    worktree_path: str | None = None
    branch_name: str | None = None
    execution_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "turn_id": self.turn_id,
            "attempt": self.attempt,
            "status": self.status,
            "started_at": iso_timestamp(self.started_at),
            "finished_at": iso_timestamp(self.finished_at),
            "message_start": self.message_start,
            "message_end": self.message_end,
            "error": self.error,
            "diagnostics_path": self.diagnostics_path,
            "tokens": self.tokens,
            "worktree_path": self.worktree_path,
            "branch_name": self.branch_name,
            "execution_id": self.execution_id,
        }

    @classmethod
    def from_dict(cls, value: object) -> "TaskRun | None":
        if not isinstance(value, dict):
            return None
        run_id = value.get("run_id")
        turn_id = value.get("turn_id")
        if not isinstance(run_id, str) or not run_id or not isinstance(turn_id, str) or not turn_id:
            return None

        def optional_int(key: str) -> int | None:
            raw = value.get(key)
            if isinstance(raw, bool) or not isinstance(raw, int):
                return None
            return raw

        def optional_str(key: str) -> str | None:
            raw = value.get(key)
            return raw if isinstance(raw, str) and raw else None

        return cls(
            run_id=run_id,
            turn_id=turn_id,
            attempt=max(1, optional_int("attempt") or 1),
            status=str(value.get("status") or "queued"),
            started_at=parse_timestamp(value.get("started_at")),
            finished_at=parse_timestamp(value.get("finished_at")),
            message_start=max(0, optional_int("message_start") or 0),
            message_end=optional_int("message_end"),
            error=optional_str("error"),
            diagnostics_path=optional_str("diagnostics_path"),
            tokens=optional_int("tokens"),
            worktree_path=optional_str("worktree_path"),
            branch_name=optional_str("branch_name"),
            execution_id=optional_str("execution_id"),
        )


def generate_task_title(text: str, limit: int = 60, fallback_id: str = "") -> str:
    """Return a readable title from the first meaningful line or sentence.

    Leading Markdown decoration (headings, list markers, quotes, fences) is
    removed, whitespace is collapsed, and the result is shortened at a word
    boundary to ``limit`` characters. Content that yields no readable text
    falls back to ``Task <short-id>``.
    """
    limit = max(1, int(limit))
    for raw_line in text.splitlines():
        line = _MARKDOWN_DECORATION.sub("", raw_line.strip())
        line = " ".join(line.split())
        line = _TRAILING_DECORATION.sub("", line).strip()
        if not line:
            continue
        sentence = re.split(r"(?<=[.!?])\s+", line, maxsplit=1)[0].strip()
        candidate = sentence if len(sentence) >= min(12, len(line)) else line
        if len(candidate) <= limit:
            return candidate
        shortened = candidate[:limit]
        boundary = shortened.rfind(" ")
        if boundary >= max(1, limit // 2):
            shortened = shortened[:boundary]
        shortened = _TRAILING_DECORATION.sub("", shortened).strip()
        if shortened:
            return f"{shortened}…"
    short_id = fallback_id.split("-", 1)[-1][:8] if fallback_id else uuid.uuid4().hex[:8]
    return f"Task {short_id}"


__all__ = [
    "GENERATED_TURN",
    "TASK_SCHEMA_VERSION",
    "TaskRun",
    "TaskTurn",
    "USER_TURN",
    "generate_task_title",
    "iso_timestamp",
    "new_run_id",
    "new_turn_id",
    "parse_timestamp",
]
