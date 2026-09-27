"""Prompt wrappers used by task and resolver agents."""

from collections.abc import Sequence

from .plan import custom_answer_text
from .topics import embed_topic


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
        "Do not run `supabase db push` or other database push commands. "
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
        "Do not run `supabase db push` or other database push commands. "
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
        "For registered personal Supabase projects, put SQL only in daedalus-migrations/ "
        "using <YYYYMMDDHHMM>_<schema>_<description>.sql filenames. If the failure reports "
        "a same-name conflict, the Daedalus TUI root SQL is authoritative; inspect both "
        "bodies in the failure and edit the project migration to match it or create a new "
        "correctly named migration. Fix migration SQL and related application code only. "
        "Preserve the original task intent and make the smallest compatible fix. "
        "Do not run git add, git commit, git merge, git push, or switch branches. "
        "Do not run graphify, `graphify update`, or any graph refresh. "
        "Do not run `supabase db push` or other database push commands. "
        "Leave file changes in the worktree for the orchestration layer to stage, commit, and push.\n\n"
        f"Original task:\n{original}\n\n"
        f"Migration repair attempt: {attempt}/{limit}\n\n"
        f"Migration push failure:\n{failure}"
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
        "Do not run `supabase db push` or other database push commands. "
        "Leave all resolutions in the worktree for the orchestration layer to stage, commit, and refresh.\n\n"
        f"Task goal:\n{original}\n\n"
        f"Resolver attempt: {attempt}/{limit}\n\n"
        f"Failure details:\n{failure}"
    )


def build_sync_conflict_plan_prompt(
    operating_branch: str,
    conflicted_paths: Sequence[str],
    merge_failure: str,
) -> str:
    """Ask a plan-mode agent to propose resolutions for Sync merge conflicts."""
    paths = "\n".join(f"- {path}" for path in conflicted_paths) or "- (none listed)"
    excerpt = merge_failure.strip() or "(no merge failure text)"
    return (
        f"Operator Sync to GitHub hit merge conflicts while integrating origin into "
        f"`{operating_branch}`.\n\n"
        "Conflicted files:\n"
        f"{paths}\n\n"
        "Merge failure excerpt:\n"
        f"{excerpt}\n\n"
        "Inspect the conflict markers in this preserved sync worktree and produce a clear "
        "resolution plan. Ask the human operator only for decisions that materially change "
        "how conflicts should be resolved. Prefer a complete plan with "
        "no_more_questions=true and an empty questions array when the safe resolution is clear."
    )


def build_sync_conflict_coding_prompt(
    plan: str,
    answers: dict[str, str] | None = None,
    answer_details: dict[str, str] | None = None,
    *,
    attempt: int = 1,
    limit: int = 1,
    leftover_unmerged: Sequence[str] = (),
) -> str:
    """Ask a coding agent to apply an approved Sync conflict resolution plan."""
    answers = answers or {}
    answer_details = answer_details or {}
    answer_text = "\n".join(
        f"- {question_id}: {custom_answer_text(answer) or answer}"
        + (f" ({answer_details[question_id]})" if question_id in answer_details else "")
        for question_id, answer in answers.items()
    )
    leftover = "\n".join(f"- {path}" for path in leftover_unmerged)
    retry_note = ""
    if leftover:
        retry_note = (
            f"\n\nPrevious attempt left unmerged paths (attempt {attempt}/{limit}):\n"
            f"{leftover}\n"
            "Finish resolving every conflict marker and leave clean file contents."
        )
    return (
        "Implement the approved Sync conflict resolution plan in this preserved conflicted "
        "worktree. Resolve every conflict marker. Leave resolutions unstaged for the "
        "orchestration layer to stage, finalize the merge commit, and push.\n\n"
        f"Approved conflict plan:\n{plan}\n\n"
        "Decisions confirmed during plan review:\n"
        f"{answer_text or '- No additional decisions were required.'}"
        f"{retry_note}"
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
