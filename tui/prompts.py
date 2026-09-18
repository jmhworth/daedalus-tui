"""Prompt wrappers used by task and resolver agents."""

from collections.abc import Sequence
from dataclasses import dataclass

from .orchestrate_protocol import card_verify_command, load_role_rules
from .topics import embed_topic


CONVERSATION_HEADER = "Conversation so far (earlier turns of this same task, oldest first):"
RESUMPTION_TEXT = (
    "This is a resumption of work already started in this existing worktree. "
    "Do not restart the task or discard work that is already present. "
    "First inspect the current state with git status and git diff, then continue "
    "from the existing implementation and make only the updates still needed."
)
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
    orchestrate_card: str | None = None,
    role_rules: str | None = None,
) -> str:
    """Build the first agent prompt for a task.

    ``orchestrate_card`` marks an Orchestrate Mode worker: the prompt is then
    built by :func:`build_worker_prompt` from the card alone. ``prompt``,
    ``topic_text``, and ``resume_notes`` are deliberately ignored in that case
    so the worker never receives the operator's prompt or any history; only
    the resumption sentence is kept when ``resumed`` is set.
    """
    if orchestrate_card is not None:
        worker_prompt = build_worker_prompt(
            orchestrate_card,
            role_rules if role_rules is not None else load_role_rules(),
            profile_text,
            verify_command=card_verify_command(orchestrate_card),
        )
        if not resumed:
            return worker_prompt
        return f"{worker_prompt}\n\n{RESUMPTION_TEXT}"
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

    continuation = RESUMPTION_TEXT
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


ORCHESTRATE_BOUNDARY = (
    "Work only in this Git worktree. "
    "Do not run git add, git commit, git merge, git push, or switch branches. "
    "Do not run graphify, `graphify update`, or any graph refresh. "
    "Do not run `supabase db push`, `firebase deploy`, or other database push "
    "and remote deploy commands. "
    "The orchestration layer owns all file staging, commits, merges, graph refreshes, "
    "migration pushes, and cleanup."
)

PLANNER_PAYLOAD_INSTRUCTIONS = (
    "Return exactly one payload between BEGIN_DAEDALUS_ORCHESTRATION and "
    "END_DAEDALUS_ORCHESTRATION, with no prose outside it. The payload must be JSON with this "
    "shape: {\"summary\": \"one paragraph describing the approach\", \"tasks\": ["
    "{\"id\": \"t1\", \"title\": \"short imperative title\", "
    "\"goal\": \"what done looks like, in two to five sentences\", "
    "\"checklist\": [\"verifiable item\", \"verifiable item\"], "
    "\"file_scope\": [\"tui/foo.py\", \"tests/test_foo.py\"], "
    "\"read_first\": [\"tui/bar.py:120-180\"], "
    "\"interfaces\": \"signatures or contracts this task must expose or consume\", "
    "\"verify\": \"pytest tests/test_foo.py\", \"depends_on\": []}], \"done\": false}. "
    "Every task needs a unique id, at least one checklist item, and a non-empty file_scope. "
    "depends_on may only name ids in the same payload and must not form a cycle. Two tasks with "
    "no dependency between them run at the same time, so they must not share any path in "
    "file_scope. Set done=true with an empty tasks array to declare the session finished."
)

WORKER_REPORT_INSTRUCTIONS = (
    "Finish your response with exactly one payload between BEGIN_DAEDALUS_WORKER_REPORT and "
    "END_DAEDALUS_WORKER_REPORT. The payload must be JSON with this shape: "
    "{\"task\": \"t2\", \"status\": \"done\", \"checklist\": [true, true, false], "
    "\"files_changed\": [\"tui/bar.py\"], "
    "\"errors\": \"empty string, or what blocked the unfinished items\", "
    "\"notes\": \"anything the planner must know: interface changes, follow-ups\"}. "
    "status is one of done, partial, or blocked, and the checklist array has one boolean per "
    "checklist item of the card, in order. A missing or malformed report is recorded as partial."
)


PLANNER_ROUNDS_TEXT = (
    "You decide how many planning rounds this session takes. After each wave of workers "
    "finishes you are called again with a status digest and may add cards, re-issue failed "
    "ones, or finish. Plan only the tasks that can start now plus those that depend on them; "
    "there is no fixed number of rounds to fill or to save."
)

PLANNER_SPEED_TEXT = (
    "Be quick: read only the files you must open to write accurate read_first lists and "
    "interfaces. Do not run tests, builds, or the verification command yourself; that is the "
    "workers' job."
)
PLANNER_MAP_TEXT = (
    "The repository map above already lists every tracked path, so do not spend tool calls "
    "listing directories."
)


def planner_round_label(round_number: int, round_limit: int = 0) -> str:
    """Return ``Planner round N`` or ``Planner round N of M`` when a cap is set."""
    label = f"Planner round {int(round_number)}"
    if int(round_limit) > 0:
        label += f" of {int(round_limit)}"
    return label


PROVIDER_ENVIRONMENTS: dict[str, str] = {
    "claude": "Claude Code CLI",
    "codex": "Codex CLI",
    "cursor": "Cursor CLI",
}


def describe_worker_environment(worker_selection: tuple[str, str, str] | None) -> str:
    """One paragraph telling the planner what a worker session does and does not have.

    The planner and its workers can run on different CLIs. A card that says
    "use the Sites skill" because the planner's CLI ships one sends a worker
    after a tool it does not have, so the planner is told, in the prompt and
    not only in the rules, that workers see the repository worktree, their
    own standard tools, and the card, and nothing from the planner's session.
    """
    if not worker_selection:
        return ""
    provider, model, _reasoning = worker_selection
    cli = PROVIDER_ENVIRONMENTS.get(str(provider).strip().lower(), str(provider))
    return (
        f"Workers run on {cli} ({model}) in their own agent sessions, each with only its Git "
        "worktree, that CLI's standard file and shell tools, and its card. They have none of "
        "your skills, plugins, MCP servers, or files outside the worktree, so a card must never "
        "tell a worker to invoke a skill or plugin or to read a reference from your session; "
        "write the requirement itself, in plain words, into the card."
    )


def build_planner_prompt(
    user_prompt: str,
    role_rules: str | None = None,
    profile_text: str | None = None,
    topic_text: str | None = None,
    max_workers: int = 3,
    verification_hint: str = "",
    repository_map: str = "",
    project_context: str = "",
    context_filename: str = "",
    worker_environment: str = "",
) -> str:
    """Build the first planner turn: decompose one operator prompt into cards.

    The planner reads the repository and answers with JSON; it never edits
    files, so this prompt carries the read-only boundary Plan mode uses.
    ``repository_map`` is a bounded path listing so the planner can name
    ``read_first`` entries without spending tool calls on discovering the tree.
    ``project_context`` is the bounded orchestration context file (earlier
    sessions' prompts, plans, and card outcomes) so a new session continues
    from what was already planned; ``context_filename`` names where it lives.
    """
    hint = (
        f"\n\nThe project's verification command is: {verification_hint.strip()}"
        if verification_hint.strip()
        else ""
    )
    return (
        "TASK_MODE: orchestrate-plan\n\n"
        f"{user_prompt.strip()}\n\n"
        f"{_embedded_profile(profile_text)}"
        f"{_embedded_topic(topic_text, 'plan')}"
        f"{_embedded_role_rules(role_rules, 'Planner')}"
        f"{_embedded_repository_map(repository_map)}"
        f"{_embedded_project_context(project_context, context_filename)}"
        "Decompose the request above into small, self-contained tasks. Each task is handed to a "
        "separate worker agent that sees only its own card: the goal, checklist, file scope, "
        "read_first list, interfaces, and verify command you write. A worker that has to explore "
        "the repository to understand its card costs the tokens this mode exists to save, so make "
        "every card startable from read_first alone.\n\n"
        f"At most {max(1, int(max_workers))} workers run at a time, and tasks with no dependency "
        "between them are dispatched together; size and order the waves accordingly. A task that "
        "declares depends_on is dispatched only after those tasks are promoted, so its worktree "
        f"already contains their changes.{hint}\n\n"
        f"{_paragraph(worker_environment)}"
        f"{PLANNER_ROUNDS_TEXT}\n\n"
        f"{PLANNER_SPEED_TEXT}{(' ' + PLANNER_MAP_TEXT) if repository_map.strip() else ''}\n\n"
        f"{PLANNER_PAYLOAD_INSTRUCTIONS}\n\n"
        "Inspect the repository as read-only context. Do not modify files or create generated "
        f"artifacts. {ORCHESTRATE_BOUNDARY}"
    )


def build_planner_round_prompt(
    user_prompt: str,
    summary: str,
    digest: str,
    role_rules: str | None = None,
    profile_text: str | None = None,
    round_number: int = 2,
    round_limit: int = 0,
    worker_environment: str = "",
) -> str:
    """Build a later planner turn from a bounded status digest, not transcripts.

    ``round_limit`` is the optional safety cap; zero means the planner alone
    decides when the session is finished.
    """
    remaining = ""
    if int(round_limit) > 0:
        remaining = (
            f" This session is capped at {int(round_limit)} rounds, after which it fails; "
            "finish before then."
        )
    return (
        "TASK_MODE: orchestrate-plan\n\n"
        f"{user_prompt.strip()}\n\n"
        f"{_embedded_profile(profile_text)}"
        f"{_embedded_role_rules(role_rules, 'Planner')}"
        f"{planner_round_label(round_number, round_limit)}.{remaining}\n\n"
        f"Your current plan summary:\n{summary.strip() or '(none recorded)'}\n\n"
        f"Status of the tasks you dispatched:\n{digest.strip()}\n\n"
        "Decide what happens next. You may add tasks, re-issue a failed task under a new id with "
        "a revised card (set \"reissues\" to the failed id), or finish the session. Re-issue only "
        "when a different card would succeed; a task that is failing for a reason no card can fix "
        "should be abandoned and explained in summary. Send done=true with an empty tasks array "
        "once the request is satisfied. Include only tasks that still need to run — tasks already "
        "promoted must not be repeated. You decide how many more rounds the work needs; do not "
        "add cards merely to use another round.\n\n"
        "Promoted cards are already merged into the branch this worktree was cut from, so read "
        "only what a new card needs and answer promptly.\n\n"
        f"{_paragraph(worker_environment)}"
        f"{PLANNER_PAYLOAD_INSTRUCTIONS}\n\n"
        "Inspect the repository as read-only context. Do not modify files or create generated "
        f"artifacts. {ORCHESTRATE_BOUNDARY}"
    )


def build_worker_prompt(
    card_markdown: str,
    role_rules: str | None = None,
    profile_text: str | None = None,
    verify_command: str = "",
) -> str:
    """Build a worker turn from one task card and nothing else.

    This builder deliberately has no parameter for the operator's prompt, the
    other cards, the planner's reasoning, or conversation history: context is
    minimized by construction rather than by asking an agent to ignore what it
    was sent. Do not add one.
    """
    verify = verify_command.strip()
    verify_line = (
        f"Run this verification before reporting: {verify}\n\n" if verify else ""
    )
    return (
        "TASK_MODE: coding\n\n"
        f"{_embedded_profile(profile_text)}"
        f"{_embedded_role_rules(role_rules, 'Worker')}"
        "You are a worker agent. Complete exactly the task card below and nothing else. The same "
        "card is written to `.daedalus-orchestration/task.md` in this worktree; tick its checklist "
        "items there (`- [x]`) as you finish them and leave unfinished items unticked.\n\n"
        "BEGIN_DAEDALUS_TASK_CARD\n"
        f"{card_markdown.strip()}\n"
        "END_DAEDALUS_TASK_CARD\n\n"
        f"{verify_line}"
        f"Make the requested file changes and leave them in the worktree. {ORCHESTRATE_BOUNDARY}\n\n"
        f"{WORKER_REPORT_INSTRUCTIONS}"
    )


def bounded_digest(text: str, limit: int) -> str:
    """Bound planner-facing text to its character budget, marking the omission."""
    return _bounded(text, max(1, int(limit)))


def role_block(role_rules: str | None, heading: str) -> str:
    """Return one ``## <heading>`` block of the bundled role rules."""
    if not role_rules:
        return ""
    lines = role_rules.splitlines()
    collected: list[str] = []
    inside = False
    for line in lines:
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip().lower() == heading.strip().lower()
            if inside:
                collected.append(line)
            continue
        if inside:
            collected.append(line)
    return "\n".join(collected).strip()


def _embedded_role_rules(role_rules: str | None, role: str) -> str:
    """Embed the shared rules plus one role's block, and nothing else."""
    blocks = [block for block in (role_block(role_rules, "Shared"), role_block(role_rules, role)) if block]
    if not blocks:
        return ""
    body = "\n\n".join(blocks)
    return (
        "BEGIN_DAEDALUS_ROLE_RULES\n"
        "These rules govern your role in this orchestration session and are already supplied "
        "inline; do not go looking for them on disk.\n"
        f"{body}\n"
        "END_DAEDALUS_ROLE_RULES\n\n"
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


def _paragraph(text: str) -> str:
    """Return ``text`` as one prompt paragraph, or nothing when it is empty."""
    return f"{text.strip()}\n\n" if text.strip() else ""


def _embedded_project_context(project_context: str, context_filename: str = "") -> str:
    """Embed the orchestration context file so earlier sessions are not re-planned."""
    if not project_context.strip():
        return ""
    location = (
        f" Daedalus commits it at `{context_filename.strip()}` in this repository and rewrites "
        "it after every planner round; do not edit it."
        if context_filename.strip()
        else ""
    )
    return (
        "BEGIN_DAEDALUS_PROJECT_CONTEXT\n"
        "The record below covers the earlier Orchestrate Mode sessions for this repository: "
        "their prompts, plans, cards, and outcomes. It is supplied inline so you continue from "
        "what was already planned instead of starting over. Cards marked promoted are already "
        "merged into the branch this worktree was cut from; cards that were stopped, failed, or "
        f"never dispatched may be re-issued under new ids when the request still needs them.{location}\n"
        f"{project_context.strip()}\n"
        "END_DAEDALUS_PROJECT_CONTEXT\n\n"
    )


def _embedded_repository_map(repository_map: str) -> str:
    if not repository_map.strip():
        return ""
    return (
        "BEGIN_DAEDALUS_REPOSITORY_MAP\n"
        "Tracked paths in this repository, one per line, already supplied so you need not list "
        "directories yourself:\n"
        f"{repository_map.strip()}\n"
        "END_DAEDALUS_REPOSITORY_MAP\n\n"
    )
