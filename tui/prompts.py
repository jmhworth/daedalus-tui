"""Prompt wrappers used by task and resolver agents."""

from collections.abc import Sequence
from dataclasses import dataclass

from .topics import embed_topic


CONVERSATION_HEADER = "Conversation so far (earlier turns of this same task, oldest first):"
LATEST_INSTRUCTION_HEADER = "Latest instruction (respond to this one):"
ORIGINAL_GOAL_HEADER = "Original request for this task:"


@dataclass(frozen=True)
class ConversationEntry:
    """One historical exchange piece: ``user``, ``assistant``, or generated ``context``."""

    role: str
    text: str
    label: str = ""


def build_conversation_prompt(
    entries: Sequence[ConversationEntry],
    latest_instruction: str,
    budget_chars: int = 24_000,
) -> str:
    """Compose provider-neutral conversation context for a follow-up turn.

    The original request and the latest instruction are always transmitted.
    Recent history is added newest-first until the character budget is
    spent; anything older is summarized by an explicit omission marker so the
    agent knows history exists that it was not shown. Complete history remains
    on disk regardless of what is transmitted.
    """
    budget = max(1, int(budget_chars))
    original = next((entry for entry in entries if entry.role == "user"), None)
    history = [entry for entry in entries if entry is not original]
    original_block = ""
    if original is not None:
        original_text = _bounded(original.text, max(200, budget // 3))
        original_block = f"{ORIGINAL_GOAL_HEADER}\n{original_text}\n\n"
    latest_block = f"{LATEST_INSTRUCTION_HEADER}\n{latest_instruction}"
    remaining = budget - len(original_block) - len(latest_block) - len(CONVERSATION_HEADER) - 4

    included: list[str] = []
    for index, entry in enumerate(reversed(history)):
        block = _entry_block(entry, len(history) - index)
        if len(block) + 2 > remaining and included:
            break
        if len(block) + 2 > remaining:
            block = _bounded(block, max(80, remaining))
        included.append(block)
        remaining -= len(block) + 2
        if remaining <= 0:
            break
    included.reverse()
    omitted = len(history) - len(included)
    parts = [original_block]
    if history:
        parts.append(f"{CONVERSATION_HEADER}\n\n")
        if omitted:
            parts.append(
                f"[… {omitted} earlier turn{'s' if omitted != 1 else ''} omitted to fit the context budget; "
                "the complete history is stored locally and can be requested …]\n\n"
            )
        parts.append("\n\n".join(included))
        parts.append("\n\n")
    parts.append(latest_block)
    return "".join(parts)


def _entry_block(entry: ConversationEntry, position: int) -> str:
    if entry.role == "assistant":
        label = entry.label or f"Assistant response {position}"
    elif entry.role == "context":
        label = entry.label or f"Generated follow-up {position} (not typed by the user)"
    else:
        label = entry.label or f"User turn {position}"
    return f"[{label}]\n{entry.text.rstrip()}"


def _bounded(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    marker = "\n[… truncated to fit the context budget …]\n"
    keep = max(0, limit - len(marker))
    head = keep * 2 // 3
    tail = keep - head
    return text[:head] + marker + (text[-tail:] if tail else "")


def build_topic_population_prompt(
    topic_name: str,
    topic_slug: str,
    topic_goal: str,
    template: str,
) -> str:
    """Tell a coding agent to create and flesh out a new topic file."""
    return (
        f"Create and populate the new Daedalus topic `{topic_name}`.\n\n"
        f"Write the file `topic_files/{topic_slug}.md` using this initialized template:\n\n"
        "```markdown\n"
        f"{template.rstrip()}\n"
        "```\n\n"
        "The operator's description and desired end state is:\n"
        f"{topic_goal.strip()}\n\n"
        "Expand the template with the durable context an agent needs to work on this topic. "
        "Keep the H1 name and the Topic Goal aligned with the operator's request. "
        "Use `open` for Topic Status unless the requested outcome is already complete. "
        "Replace the initialization placeholder in State Log with a concise first entry that "
        "captures the starting state, important constraints, and the intended end state. "
        "Do not create unrelated files or change application code."
    )


def build_task_prompt(
    prompt: str,
    mode: str = "coding",
    resume_notes: Sequence[str] = (),
    resumed: bool = False,
    profile_text: str | None = None,
    topic_text: str | None = None,
) -> str:
    if mode == "ask":
        instructions = (
            "Answer the user's question using the repository as read-only context. "
            "Do not modify files or create generated artifacts."
        )
    elif mode == "plan":
        instructions = (
            "Inspect the repository and produce a clear implementation plan. Return exactly one "
            "payload between BEGIN_DAEDALUS_PLAN and END_DAEDALUS_PLAN, with no prose outside it. "
            "The payload must be JSON with this shape: {\"plan\": \"...\", "
            "\"questions\": [{\"id\": \"q1\", \"question\": \"...\", "
            "\"required\": true, \"options\": [{\"id\": \"a\", \"label\": \"...\"}, "
            "{\"id\": \"b\", \"label\": \"...\"}]}], "
            "\"no_more_questions\": false}. Use an empty questions array and "
            "no_more_questions=true when no decisions are needed. Set it to false whenever "
            "a required question remains. The plan field contains only the implementation plan; "
            "questions belong in questions and every question must have at least two choices. "
            "For every question, mark exactly one option as the recommended default by appending "
            "\" (Recommended)\" to that option's label (never more than one per question), choosing "
            "the safest reasonable default when the user may not care which answer is picked. "
            "Explicitly include assumptions and decisions in the plan field for the user to review. "
            "Do not modify files or create generated artifacts."
        )
    elif mode == "coding":
        instructions = "Make the requested file changes and leave them in the worktree."
    else:
        raise ValueError(f"Unsupported task mode: {mode}")
    embedded_profile = _embedded_profile(profile_text)
    embedded_topic = _embedded_topic(topic_text, mode)
    extras = "".join(
        part for part in (embedded_profile, embedded_topic) if part
    )
    profile_prefix = f"\n\n{extras}" if extras else ""
    task_prompt = (
        f"TASK_MODE: {mode}\n\n"
        f"{prompt}{profile_prefix}\n\n"
        f"{instructions} Work only in this Git worktree. "
        "Do not run git add, git commit, git merge, git push, or switch branches. "
        "Do not run graphify, `graphify update`, or any graph refresh. "
        "Do not run `supabase db push`, `firebase deploy`, or other database push "
        "and remote deploy commands. "
        "The orchestration layer owns all file staging, commits, merges, graph refreshes, "
        "migration pushes, and cleanup."
    )
    if not resumed:
        return task_prompt

    continuation = (
        "This is a resumption of work already started in this existing worktree. "
        "Do not restart the task or discard work that is already present. "
        "First inspect the current state with git status and git diff, then continue "
        "from the existing implementation and make only the updates still needed."
    )
    cleaned_notes = [note.strip() for note in resume_notes if note.strip()]
    if cleaned_notes:
        continuation += "\n\nAdditional notes from the user:\n" + "\n\n".join(cleaned_notes)
    return f"{task_prompt}\n\n{continuation}"


def build_repair_prompt(
    original: str,
    failure: str,
    attempt: int,
    limit: int,
    profile_text: str | None = None,
    topic_text: str | None = None,
) -> str:
    return (
        "TASK_MODE: coding\n\n"
        f"{_embedded_profile(profile_text)}"
        f"{_embedded_topic(topic_text, 'repair')}"
        "Repair the failing verification suite in this existing isolated Git worktree. "
        "Preserve the original task intent and make the smallest compatible fix. "
        "Do not run git add, git commit, git merge, git push, or switch branches. "
        "Do not run graphify, `graphify update`, or any graph refresh. "
        "Do not run `supabase db push`, `firebase deploy`, or other database push "
        "and remote deploy commands. "
        "Leave file changes in the worktree for the orchestration layer to stage, commit, and refresh.\n\n"
        f"Original task:\n{original}\n\n"
        f"Repair attempt: {attempt}/{limit}\n\n"
        f"Verification failure:\n{failure}"
    )


def build_migration_repair_prompt(
    original: str,
    failure: str,
    attempt: int,
    limit: int,
    profile_text: str | None = None,
    topic_text: str | None = None,
) -> str:
    return (
        "TASK_MODE: coding\n\n"
        f"{_embedded_profile(profile_text)}"
        f"{_embedded_topic(topic_text, 'repair')}"
        "Repair the failing Supabase migration push in this existing isolated Git worktree. "
        "Fix migration SQL and related application code only. "
        "Preserve the original task intent and make the smallest compatible fix. "
        "Do not run git add, git commit, git merge, git push, or switch branches. "
        "Do not run graphify, `graphify update`, or any graph refresh. "
        "Do not run `supabase db push`, `firebase deploy`, or other database push "
        "and remote deploy commands. "
        "Leave file changes in the worktree for the orchestration layer to stage, commit, and push.\n\n"
        f"Original task:\n{original}\n\n"
        f"Migration repair attempt: {attempt}/{limit}\n\n"
        f"Migration push failure:\n{failure}"
    )


def build_firebase_repair_prompt(
    original: str,
    failure: str,
    attempt: int,
    limit: int,
    profile_text: str | None = None,
    topic_text: str | None = None,
) -> str:
    return (
        "TASK_MODE: coding\n\n"
        f"{_embedded_profile(profile_text)}"
        f"{_embedded_topic(topic_text, 'repair')}"
        "Repair the failing Firebase deploy in this existing isolated Git worktree. "
        "Fix Firestore security rules, indexes, `firebase.json`, and related application "
        "code only. Keep rules deny-by-default and never widen them to `if true` to make "
        "a deploy pass. "
        "Preserve the original task intent and make the smallest compatible fix. "
        "Do not run git add, git commit, git merge, git push, or switch branches. "
        "Do not run graphify, `graphify update`, or any graph refresh. "
        "Do not run `firebase deploy` or other remote deploy commands. "
        "Leave file changes in the worktree for the orchestration layer to stage, commit, and deploy.\n\n"
        f"Original task:\n{original}\n\n"
        f"Firebase repair attempt: {attempt}/{limit}\n\n"
        f"Firebase deploy failure:\n{failure}"
    )


def build_resolver_prompt(
    original: str,
    failure: str,
    attempt: int,
    limit: int,
    profile_text: str | None = None,
    topic_text: str | None = None,
) -> str:
    return (
        "TASK_MODE: integrating\n\n"
        f"{_embedded_profile(profile_text)}"
        f"{_embedded_topic(topic_text, 'integrating')}"
        "Resolve the current integration failure in this existing Git worktree. "
        "Preserve the task intent, resolve conflicts or repair the failing checks, and run relevant checks. "
        "Do not run git add, git commit, git merge, git push, or switch branches. "
        "Do not run graphify, `graphify update`, or any graph refresh. "
        "Do not run `supabase db push`, `firebase deploy`, or other database push "
        "and remote deploy commands. "
        "Leave all resolutions in the worktree for the orchestration layer to stage, commit, and refresh.\n\n"
        f"Task goal:\n{original}\n\n"
        f"Resolver attempt: {attempt}/{limit}\n\n"
        f"Failure details:\n{failure}"
    )


def _embedded_profile(profile_text: str | None) -> str:
    if profile_text is None:
        return ""
    return (
        "BEGIN_DAEDALUS_PROFILE\n"
        "The following profile is authoritative and has already been supplied inline. "
        "Apply it directly; do not open the profile file merely to read it again.\n"
        "--- PROFILE CONTENT START ---\n"
        f"{profile_text}\n"
        "--- PROFILE CONTENT END ---\n"
        "END_DAEDALUS_PROFILE\n"
    )


def _embedded_topic(topic_text: str | None, mode: str) -> str:
    if topic_text is None:
        return ""
    return embed_topic(topic_text, mode)
