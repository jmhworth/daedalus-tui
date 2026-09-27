"""Single-run local agent orchestration without daemon or database dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
import uuid
from typing import Callable

from .agent_runner import AgentControl, AgentRequest, AgentResult, AgentRunner
from .debug_log import LOGGER, log_exception
from .environment import cursor_environment, redact_environment_values
from .graphify import update_repository
from .git_worktree import (
    GitWorktreeError,
    GitWorktreeManager,
    WorktreeContext,
    abort_sync_merge,
    finalize_sync_merge,
    list_unmerged_paths,
    push_branch,
)
from .project_config import load_project_worktree_settings
from .personal_supabase import (
    is_personal_supabase_registered,
    load_personal_supabase_settings,
    preflight_personal_supabase,
    resolve_project_ref_from_environment,
    temporary_supabase_cli_config,
)
from .prompts import (
    build_migration_repair_prompt,
    build_repair_prompt,
    build_resolver_prompt,
    build_sync_conflict_coding_prompt,
    build_task_prompt,
)
from .supabase_migrations import (
    ROOT_MIGRATION_LOCK,
    TUI_ROOT,
    migrations_pending,
    push_migrations,
    synchronize_personal_migrations,
)
from .topics import load_topic_text, topic_path
from .verification import discover_commands, run_verification, truncate_diagnostic


EventCallback = Callable[[str, str, str], None]
IntegrationGate = Callable[[int, Callable[[], None]], None]
PROFILE_FILENAMES = {
    "coding": "coding.md",
    "plan": "planning.md",
    "integrating": "integrating.md",
}


@dataclass(frozen=True)
class OrchestrationSettings:
    primary_branch: str = "main"
    worktree_root: str = ".daedalus-worktrees"
    verification_commands: tuple[tuple[str, ...], ...] = ()
    task_verification_attempt_limit: int = 3
    resolver_attempt_limit: int = 3
    max_concurrent_tasks: int = 4
    agent_timeout_seconds: float = 450.0
    graphify_update_enabled: bool = True
    graphify_executable: str = "graphify"
    supabase_db_push_enabled: bool = True
    supabase_executable: str = "supabase"
    shutdown_grace_seconds: float = 8.0
    debug_log_filename: str = ".daedalus-debug.log"


@dataclass(frozen=True)
class OrchestrationResult:
    succeeded: bool
    task_id: str
    branch_name: str = ""
    worktree: Path | None = None
    error: str | None = None
    context: WorktreeContext | None = None
    paused: bool = False
    cancelled: bool = False
    tokens_consumed: int = 0
    awaiting_plan: bool = False


class AgentStopped(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class LocalOrchestrator:
    def __init__(
        self,
        repository: Path,
        runner: AgentRunner,
        settings: OrchestrationSettings,
        on_event: EventCallback,
        integration_gate: IntegrationGate | None = None,
        environment_path: Path | None = None,
        launch_environment_path: Path | None = None,
        migration_push_lock: Lock | None = None,
    ):
        self.repository = repository.resolve()
        self.runner = runner
        self.settings = settings
        self.on_event = on_event
        self.integration_gate = integration_gate or (lambda _sequence, operation: operation())
        self.environment_path = environment_path.resolve() if environment_path is not None else None
        self.launch_environment_path = (
            launch_environment_path.resolve() if launch_environment_path is not None else None
        )
        self.migration_push_lock = migration_push_lock
        self._tokens_consumed = 0

    def run(
        self,
        prompt: str,
        provider: str,
        model: str,
        reasoning: str,
        task_id: str | None = None,
        submission_sequence: int = 0,
        mode: str = "coding",
        control: AgentControl | None = None,
        existing_context: WorktreeContext | None = None,
        resume_notes: tuple[str, ...] = (),
        resume_from: str | None = None,
        topic_slug: str | None = None,
        *,
        sync_recovery: bool = False,
        sync_operating_branch: str | None = None,
        sync_remote: str = "origin",
        sync_used_temp_branch: bool = False,
        sync_temp_branch_name: str | None = None,
        sync_conflict_attempt_limit: int = 3,
        sync_plan_text: str = "",
        sync_plan_answers: dict[str, str] | None = None,
        sync_plan_answer_details: dict[str, str] | None = None,
    ) -> OrchestrationResult:
        task_id = task_id or uuid.uuid4().hex[:12]
        LOGGER.info(
            "Orchestration started task=%s mode=%s provider=%s resume_from=%s topic=%s sync_recovery=%s",
            task_id,
            mode,
            provider,
            resume_from or "start",
            topic_slug or "-",
            sync_recovery,
        )
        context: WorktreeContext | None = existing_context
        manager = GitWorktreeManager(
            self.repository,
            self.settings.primary_branch,
            self.settings.worktree_root,
        )
        if sync_recovery:
            return self._run_sync_recovery(
                manager,
                prompt,
                provider,
                model,
                reasoning,
                task_id=task_id,
                submission_sequence=submission_sequence,
                mode=mode,
                control=control,
                existing_context=existing_context,
                resume_notes=resume_notes,
                topic_slug=topic_slug,
                operating_branch=sync_operating_branch or self.settings.primary_branch,
                remote=sync_remote,
                used_temp_branch=sync_used_temp_branch,
                temp_branch_name=sync_temp_branch_name,
                attempt_limit=max(1, sync_conflict_attempt_limit),
                plan_text=sync_plan_text,
                plan_answers=sync_plan_answers or {},
                plan_answer_details=sync_plan_answer_details or {},
            )
        try:
            project_worktree_settings = load_project_worktree_settings(self.repository)
            self.emit("worktree", "Validating the primary Git worktree.")
            # Commit dirty primary files on start/resume so send is not blocked.
            if manager.validate_primary(auto_commit_dirty=True):
                self.emit(
                    "worktree",
                    "Auto-committed dirty primary worktree changes.",
                )
            if context is None:
                context = manager.create(task_id, validate=False)
                self.emit("worktree", f"Created {context.branch_name} at {context.path}.")
            else:
                self.emit("worktree", f"Resuming {context.branch_name} at {context.path}.")
            manager.provision_worktree(context, project_worktree_settings)
            self._raise_if_stopped(control)

            selection = (provider, model, reasoning)
            skip_to_integration = (
                mode not in {"ask", "plan"}
                and resume_from == "integration"
                and existing_context is not None
            )
            if not skip_to_integration:
                self.emit(
                    "planning" if mode == "plan" else "agent",
                    f"Planning with {provider} in the isolated worktree."
                    if mode == "plan"
                    else f"Running {provider} in the isolated worktree.",
                )
                profile_text = self.load_profile(context.path, mode)
                topic_text = self.load_topic(context.path, topic_slug)
                result = self.run_agent(
                    manager,
                    context,
                    selection,
                    build_task_prompt(
                        prompt,
                        mode,
                        resume_notes,
                        resumed=existing_context is not None,
                        profile_text=profile_text,
                        topic_text=topic_text,
                    ),
                    control,
                    event_phase="planning" if mode == "plan" else "agent",
                )
                if not result.succeeded:
                    raise RuntimeError(result.error or "Agent execution failed.")

                if mode in {"ask", "plan"}:
                    manager.discard_graphify_changes(context.path)
                if mode == "plan":
                    manager.reset_task_to_base(context)
                    self.emit("questioning", "Plan ready. Review it, answer questions, or start coding.")
                    return OrchestrationResult(
                        True,
                        task_id,
                        context.branch_name,
                        context.path,
                        context=context,
                        awaiting_plan=True,
                        tokens_consumed=self._completed_tokens(),
                    )
                if mode == "ask":
                    manager.remove_successful(context)
                    self.emit("completed", f"Completed {mode} task.")
                    return OrchestrationResult(
                        True,
                        task_id,
                        context.branch_name,
                        context.path,
                        context=context,
                        tokens_consumed=self._completed_tokens(),
                    )

                manager.discard_graphify_changes(context.path)
                manager.commit_changes(context.path, f"Daedalus task {task_id}")
                if manager.head(context.path) == context.base_commit:
                    raise RuntimeError("Agent finished without creating a commit.")
                self.verify_with_repairs(
                    manager, context, selection, prompt, control, topic_slug=topic_slug
                )
                self.push_migrations_with_repairs(
                    manager, context, selection, prompt, control, topic_slug=topic_slug
                )
            else:
                self.emit("ready", "Coding already complete; retrying from integration.")

            def integrate_and_promote() -> None:
                self._raise_if_stopped(control)
                integration_base = manager.capture_primary()
                self.integrate(
                    manager, context, selection, prompt, control, topic_slug=topic_slug
                )
                manager.promote(context, integration_base)
                self.refresh_graphify(manager, task_id)

            self.emit("ready", "Task is ready for serialized integration.")
            self.integration_gate(submission_sequence, integrate_and_promote)
            manager.remove_successful(context)
            self.emit("completed", f"Promoted {context.branch_name} into {self.settings.primary_branch}.")
            return OrchestrationResult(
                True,
                task_id,
                context.branch_name,
                context.path,
                context=context,
                tokens_consumed=self._completed_tokens(),
            )
        except AgentStopped as stopped:
            LOGGER.info("Orchestration stopped task=%s reason=%s", task_id, stopped.reason)
            if stopped.reason == "cancelled" and context is not None:
                manager.remove_cancelled(context)
                self.emit("cancelled", "Task cancelled and its worktree was removed.")
                return OrchestrationResult(
                    False,
                    task_id,
                    context.branch_name,
                    context.path,
                    "Task cancelled.",
                    cancelled=True,
                    tokens_consumed=self._completed_tokens(False),
                )
            self.emit("paused", "Task paused; its worktree and current progress were preserved.")
            return OrchestrationResult(
                False,
                task_id,
                context.branch_name if context else "",
                context.path if context else None,
                context=context,
                paused=True,
                tokens_consumed=self._completed_tokens(False),
            )
        except (GitWorktreeError, RuntimeError, ValueError) as error:
            log_exception(f"Orchestration failed task={task_id}", error)
            message = str(error)
            self.emit("failed", message, "error")
            return OrchestrationResult(
                False,
                task_id,
                context.branch_name if context else "",
                context.path if context else None,
                message,
                context=context,
                tokens_consumed=self._completed_tokens(False),
            )

    def _run_sync_recovery(
        self,
        manager: GitWorktreeManager,
        prompt: str,
        provider: str,
        model: str,
        reasoning: str,
        *,
        task_id: str,
        submission_sequence: int,
        mode: str,
        control: AgentControl | None,
        existing_context: WorktreeContext | None,
        resume_notes: tuple[str, ...],
        topic_slug: str | None,
        operating_branch: str,
        remote: str,
        used_temp_branch: bool,
        temp_branch_name: str | None,
        attempt_limit: int,
        plan_text: str,
        plan_answers: dict[str, str],
        plan_answer_details: dict[str, str],
    ) -> OrchestrationResult:
        """Plan or resolve Sync merge conflicts in a preserved sync worktree."""
        context = existing_context
        if context is None:
            message = "Sync conflict recovery requires a preserved conflict worktree."
            self.emit("failed", message, "error")
            return OrchestrationResult(False, task_id, error=message)
        try:
            self.emit("worktree", f"Using sync conflict worktree at {context.path}.")
            selection = (provider, model, reasoning)
            self._raise_if_stopped(control)
            if mode == "plan":
                self.emit("planning", f"Planning sync conflict resolution with {provider}.")
                profile_text = self.load_profile(context.path, "plan")
                topic_text = self.load_topic(context.path, topic_slug)
                result = self.run_agent(
                    manager,
                    context,
                    selection,
                    build_task_prompt(
                        prompt,
                        "plan",
                        resume_notes,
                        resumed=True,
                        profile_text=profile_text,
                        topic_text=topic_text,
                    ),
                    control,
                    event_phase="planning",
                )
                if not result.succeeded:
                    raise RuntimeError(result.error or "Sync conflict planning failed.")
                manager.discard_graphify_changes(context.path)
                # Keep conflict markers; never reset_task_to_base for sync recovery.
                self.emit("questioning", "Sync conflict plan ready for review.")
                return OrchestrationResult(
                    True,
                    task_id,
                    context.branch_name,
                    context.path,
                    context=context,
                    awaiting_plan=True,
                    tokens_consumed=self._completed_tokens(),
                )

            # Coding / finalize path for an approved conflict plan.
            leftover: tuple[str, ...] = ()
            for attempt in range(1, attempt_limit + 1):
                self._raise_if_stopped(control)
                self.emit(
                    "agent",
                    f"Resolving sync conflicts (attempt {attempt}/{attempt_limit}).",
                )
                profile_text = self.load_profile(context.path, "coding")
                topic_text = self.load_topic(context.path, topic_slug)
                coding_prompt = build_sync_conflict_coding_prompt(
                    plan_text or prompt,
                    plan_answers,
                    plan_answer_details,
                    attempt=attempt,
                    limit=attempt_limit,
                    leftover_unmerged=leftover,
                )
                result = self.run_agent(
                    manager,
                    context,
                    selection,
                    build_task_prompt(
                        coding_prompt,
                        "coding",
                        resume_notes if attempt == 1 else (),
                        resumed=True,
                        profile_text=profile_text,
                        topic_text=topic_text,
                    ),
                    control,
                    event_phase="agent",
                )
                if not result.succeeded:
                    raise RuntimeError(result.error or "Sync conflict resolution failed.")
                manager.discard_graphify_changes(context.path)
                manager.stage_changes(context.path)
                leftover = list_unmerged_paths(context.path)
                if not leftover:
                    break
                self.emit(
                    "resolving",
                    f"Unmerged paths remain after attempt {attempt}: {', '.join(leftover)}",
                )
            else:
                raise RuntimeError(
                    f"Sync conflict resolution left unmerged paths after {attempt_limit} attempts: "
                    + ", ".join(leftover)
                )

            def finalize_and_push() -> None:
                self._raise_if_stopped(control)
                self.emit("integration", "Finalizing sync merge commit.")
                finalize_sync_merge(
                    self.repository,
                    context.path,
                    operating_branch,
                    used_temp_branch=used_temp_branch,
                    temp_branch_name=temp_branch_name,
                )
                self.emit("integration", f"Pushing resolved {operating_branch} to {remote}.")
                push_branch(self.repository, operating_branch, remote, pull_first=False)

            self.emit("ready", "Sync conflicts resolved; finalizing under the integration gate.")
            self.integration_gate(submission_sequence, finalize_and_push)
            self.emit("completed", f"Synced {operating_branch} to {remote} after conflict resolution.")
            return OrchestrationResult(
                True,
                task_id,
                context.branch_name,
                context.path,
                context=None,
                tokens_consumed=self._completed_tokens(),
            )
        except AgentStopped as stopped:
            LOGGER.info("Sync recovery stopped task=%s reason=%s", task_id, stopped.reason)
            if stopped.reason == "cancelled" and context is not None:
                abort_sync_merge(
                    self.repository,
                    context.path,
                    temp_branch_name=temp_branch_name,
                )
                self.emit("cancelled", "Sync conflict recovery cancelled; merge aborted.")
                return OrchestrationResult(
                    False,
                    task_id,
                    context.branch_name,
                    context.path,
                    "Sync conflict recovery cancelled.",
                    cancelled=True,
                    tokens_consumed=self._completed_tokens(False),
                )
            self.emit("paused", "Sync conflict recovery paused; conflict worktree preserved.")
            return OrchestrationResult(
                False,
                task_id,
                context.branch_name,
                context.path,
                context=context,
                paused=True,
                tokens_consumed=self._completed_tokens(False),
            )
        except (GitWorktreeError, RuntimeError, ValueError) as error:
            log_exception(f"Sync recovery failed task={task_id}", error)
            message = str(error)
            self.emit("failed", message, "error")
            return OrchestrationResult(
                False,
                task_id,
                context.branch_name if context else "",
                context.path if context else None,
                message,
                context=context,
                tokens_consumed=self._completed_tokens(False),
            )

    def run_agent(
        self,
        manager: GitWorktreeManager,
        context: WorktreeContext,
        selection: tuple[str, str, str],
        prompt: str,
        control: AgentControl | None = None,
        event_phase: str = "agent",
    ) -> AgentResult:
        provider, model, reasoning = selection
        request = AgentRequest(
            prompt=prompt,
            directory=context.path,
            provider=provider,
            model=model,
            reasoning=reasoning,
            writable_directories=(context.path,),
            environment_files=(
                (self.repository / ".env", self.environment_path)
                if self.environment_path is not None
                else (self.repository / ".env",)
            ),
            control=control,
            timeout_seconds=self.settings.agent_timeout_seconds,
            credential_files=(
                (self.launch_environment_path,)
                if self.launch_environment_path is not None
                else ()
            ),
        )
        result = self.runner.run(
            request,
            lambda event: self.emit(event_phase, event.text, event.kind),
        )
        if result.tokens_consumed is not None:
            self._tokens_consumed += result.tokens_consumed
        if provider == "cursor" and result.succeeded and result.output:
            if event_phase == "planning":
                # Cursor's stream-json assistant events are useful progress,
                # but may be partial or cumulative. Its terminal ``result`` is
                # the complete response and must remain available to plan
                # parsing even after one or more assistant deltas arrived.
                self.emit("plan_result", result.output, "message")
            elif not result.output_streamed:
                self.emit(event_phase, result.output, "message")
        if result.stopped_reason:
            raise AgentStopped(result.stopped_reason)
        return result

    def verify_with_repairs(
        self,
        manager: GitWorktreeManager,
        context: WorktreeContext,
        selection: tuple[str, str, str],
        original: str,
        control: AgentControl | None = None,
        topic_slug: str | None = None,
    ) -> None:
        commands = discover_commands(
            context.path,
            [list(command) for command in self.settings.verification_commands],
        )
        attempts = 0
        failure_log: list[str] = []
        limit = self.settings.task_verification_attempt_limit
        while True:
            self.emit("verification", "Running verification checks.")
            self._raise_if_stopped(control)
            result = run_verification(context.path, commands, control=control)
            self._raise_if_stopped(control)
            if result.succeeded:
                return
            attempts += 1
            reason = truncate_diagnostic(
                result.output.strip() or "Verification produced no diagnostic output."
            )
            attempt_summary = f"Verification attempt {attempts}/{limit} failed.\n\n{reason}"
            failure_log.append(attempt_summary)
            self.emit("verification", attempt_summary, "error")
            if attempts >= limit:
                raise RuntimeError(
                    f"Verification failed after {limit} attempts.\n\n"
                    + "\n\n".join(failure_log)
                )
            self.emit("repairing", f"Launching task repair attempt {attempts}/{limit}.")
            profile_text = self.load_profile(context.path, "coding")
            topic_text = self.load_topic(context.path, topic_slug)
            repair = self.run_agent(
                manager,
                context,
                selection,
                build_repair_prompt(
                    original,
                    reason,
                    attempts,
                    limit,
                    profile_text=profile_text,
                    topic_text=topic_text,
                ),
                control,
            )
            if not repair.succeeded:
                raise RuntimeError(repair.error or "Task repair agent failed.")
            manager.commit_changes(context.path, f"Daedalus task repair {attempts}")

    def push_migrations_with_repairs(
        self,
        manager: GitWorktreeManager,
        context: WorktreeContext,
        selection: tuple[str, str, str],
        original: str,
        control: AgentControl | None = None,
        topic_slug: str | None = None,
    ) -> None:
        if not self.settings.supabase_db_push_enabled:
            return
        lock = self.migration_push_lock
        if lock is None:
            self._push_migrations_with_repairs(
                manager, context, selection, original, control, topic_slug
            )
            return
        with lock:
            self._push_migrations_with_repairs(
                manager, context, selection, original, control, topic_slug
            )

    def _push_migrations_with_repairs(
        self,
        manager: GitWorktreeManager,
        context: WorktreeContext,
        selection: tuple[str, str, str],
        original: str,
        control: AgentControl | None,
        topic_slug: str | None,
    ) -> None:
        attempts = 0
        failure_log: list[str] = []
        limit = self.settings.task_verification_attempt_limit
        extra_environment = (self.environment_path,) if self.environment_path is not None else ()
        environment = cursor_environment(context.path, (self.repository / ".env", *extra_environment))
        project_ref = resolve_project_ref_from_environment(
            environment,
            load_personal_supabase_settings(),
        )
        personal_registered = is_personal_supabase_registered(context.path)
        while True:
            if not migrations_pending(context.path, context.base_commit):
                return
            database_url: str | None = None
            if personal_registered:
                preflight = preflight_personal_supabase(
                    context.path,
                    executable=self.settings.supabase_executable,
                    environment=environment,
                )
                if not preflight.succeeded:
                    raise RuntimeError(
                        preflight.message or "Personal Supabase connectivity preflight failed."
                    )
                database_url = preflight.database_url
            self.emit("migrations", "Pushing pending Supabase migrations.")
            self._raise_if_stopped(control)
            if personal_registered:
                synced = synchronize_personal_migrations(context.path)
                if not synced.succeeded:
                    raise RuntimeError(synced.output)
                if synced.conflicts:
                    conflicts = "\n\n".join(
                        f"Filename: {name}\nTUI root SQL (authoritative):\n{root_sql}\n"
                        f"Project SQL:\n{project_sql}"
                        for name, root_sql, project_sql in synced.conflicts
                    )
                    reason = (
                        "A project migration matches a TUI-root migration filename but has different SQL. "
                        "Keep the TUI-root SQL as the source of truth and repair the project migration.\n\n"
                        + conflicts
                    )
                    attempts += 1
                    if attempts >= limit:
                        raise RuntimeError(reason)
                    self.emit("repairing", f"Launching migration conflict repair attempt {attempts}/{limit}.")
                    repair = self.run_agent(
                        manager,
                        context,
                        selection,
                        build_migration_repair_prompt(
                            original, reason, attempts, limit,
                            profile_text=self.load_profile(context.path, "coding"),
                            topic_text=self.load_topic(context.path, topic_slug),
                        ),
                        control,
                    )
                    if not repair.succeeded:
                        raise RuntimeError(repair.error or "Migration conflict repair agent failed.")
                    manager.commit_changes(context.path, f"Daedalus migration conflict repair {attempts}")
                    continue
                with ROOT_MIGRATION_LOCK:
                    with temporary_supabase_cli_config(context.path, project_ref):
                        push_options = {
                            "executable": self.settings.supabase_executable,
                            "env": environment,
                        }
                        if database_url:
                            push_options["database_url"] = database_url
                        result = push_migrations(TUI_ROOT, **push_options)
            else:
                result = push_migrations(
                    context.path,
                    executable=self.settings.supabase_executable,
                    env=environment,
                )
            self._raise_if_stopped(control)
            if result.succeeded:
                return
            attempts += 1
            reason = redact_environment_values(
                result.output.strip(), environment
            ) or "Migration push produced no diagnostic output."
            attempt_summary = f"Migration push attempt {attempts}/{limit} failed.\n\n{reason}"
            failure_log.append(attempt_summary)
            self.emit("migrations", attempt_summary, "error")
            if attempts >= limit:
                raise RuntimeError(
                    f"Migration push failed after {limit} attempts.\n\n"
                    + "\n\n".join(failure_log)
                )
            self.emit("repairing", f"Launching migration repair attempt {attempts}/{limit}.")
            profile_text = self.load_profile(context.path, "coding")
            topic_text = self.load_topic(context.path, topic_slug)
            repair = self.run_agent(
                manager,
                context,
                selection,
                build_migration_repair_prompt(
                    original,
                    reason,
                    attempts,
                    limit,
                    profile_text=profile_text,
                    topic_text=topic_text,
                ),
                control,
            )
            if not repair.succeeded:
                raise RuntimeError(repair.error or "Migration repair agent failed.")
            manager.commit_changes(context.path, f"Daedalus migration repair {attempts}")

    def integrate(
        self,
        manager: GitWorktreeManager,
        context: WorktreeContext,
        selection: tuple[str, str, str],
        original: str,
        control: AgentControl | None = None,
        topic_slug: str | None = None,
    ) -> None:
        failure = ""
        try:
            self._raise_if_stopped(control)
            self.emit("integration", f"Merging {self.settings.primary_branch} into {context.branch_name}.")
            manager.merge_primary_into_task(context)
        except GitWorktreeError as error:
            failure = str(error)

        if failure:
            self.resolve_integration(
                manager, context, selection, original, failure, control, topic_slug=topic_slug
            )

        commands = discover_commands(
            context.path,
            [list(command) for command in self.settings.verification_commands],
        )
        result = run_verification(context.path, commands, control=control)
        self._raise_if_stopped(control)
        if not result.succeeded:
            self.resolve_integration(
                manager,
                context,
                selection,
                original,
                result.output,
                control,
                topic_slug=topic_slug,
            )

    def resolve_integration(
        self,
        manager: GitWorktreeManager,
        context: WorktreeContext,
        selection: tuple[str, str, str],
        original: str,
        failure: str,
        control: AgentControl | None = None,
        topic_slug: str | None = None,
    ) -> None:
        for attempt in range(1, self.settings.resolver_attempt_limit + 1):
            self._raise_if_stopped(control)
            self.emit("resolving", f"Launching resolver attempt {attempt}/{self.settings.resolver_attempt_limit}.")
            profile_text = self.load_profile(context.path, "integrating")
            topic_text = self.load_topic(context.path, topic_slug)
            result = self.run_agent(
                manager,
                context,
                selection,
                build_resolver_prompt(
                    original,
                    failure,
                    attempt,
                    self.settings.resolver_attempt_limit,
                    profile_text=profile_text,
                    topic_text=topic_text,
                ),
                control,
            )
            if result.succeeded:
                manager.stage_changes(context.path)
                if manager.has_unmerged_paths(context.path):
                    failure = "Resolver left unmerged Git paths in the task worktree."
                    continue
                manager.discard_graphify_changes(context.path)
                manager.commit_changes(context.path, f"Daedalus resolver attempt {attempt}")
                commands = discover_commands(
                    context.path,
                    [list(command) for command in self.settings.verification_commands],
                )
                verification = run_verification(context.path, commands, control=control)
                self._raise_if_stopped(control)
                if verification.succeeded:
                    return
                failure = verification.output
            else:
                failure = result.error or "Resolver agent failed."
        raise RuntimeError(
            f"Integration failed after {self.settings.resolver_attempt_limit} resolver attempts.\n\n{failure}"
        )

    def load_profile(self, worktree: Path, route: str) -> str | None:
        """Load a repository-owned profile immediately before building a prompt."""
        filename = PROFILE_FILENAMES.get(route)
        if filename is None:
            return None
        profile_path = worktree / ".agents" / "profiles" / filename
        try:
            return profile_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            message = f"Could not load {route} profile from {profile_path}: {error}"
            LOGGER.warning(message)
            self.emit("profile", message, "error")
            return None

    def load_topic(self, worktree: Path, topic_slug: str | None) -> str | None:
        """Load a tagged topic from the task worktree immediately before a prompt."""
        if not topic_slug:
            return None
        text = load_topic_text(worktree, topic_slug)
        if text is not None:
            return text
        path = topic_path(worktree, topic_slug)
        message = f"Could not load topic '{topic_slug}' from {path}"
        LOGGER.warning(message)
        self.emit("topic", message, "error")
        return None

    def refresh_graphify(self, manager: GitWorktreeManager, task_id: str) -> None:
        """Refresh graph metadata after promotion without blocking the task."""
        if not self.settings.graphify_update_enabled:
            return
        if not (self.repository / "graphify-out").exists():
            self.emit("graphify", "Graph refresh skipped because graphify-out is not present.")
            return
        self.emit("graphify", "Refreshing the primary repository graph.")
        checkout: Path | None = None
        temporary: Path | None = None
        try:
            checkout, temporary = manager.prepare_primary_checkout()
        except GitWorktreeError as error:
            self.emit("graphify", f"Graph refresh skipped: could not open target branch checkout: {error}", "error")
            return
        try:
            result = update_repository(checkout, self.settings.graphify_executable)
            if not result.succeeded:
                # A failed or partial refresh must not dirty the primary worktree
                # and must never trigger a resolver attempt for the code task.
                try:
                    manager.discard_graphify_changes(checkout)
                except GitWorktreeError as cleanup_error:
                    self.emit(
                        "graphify",
                        f"Graph refresh failed and cleanup also failed: {cleanup_error}",
                        "error",
                    )
                self.emit("graphify", f"Graph refresh skipped: {result.output or 'unknown error'}")
                return
            try:
                committed = manager.commit_graphify_changes(
                    f"Daedalus graphify update after task {task_id}",
                    checkout,
                )
            except GitWorktreeError as error:
                try:
                    manager.discard_graphify_changes(checkout)
                except GitWorktreeError as cleanup_error:
                    self.emit(
                        "graphify",
                        f"Graph refresh commit failed and cleanup also failed: {cleanup_error}",
                        "error",
                    )
                self.emit("graphify", f"Graph refresh completed but could not be committed: {error}", "error")
                return
            self.emit(
                "graphify",
                "Graph refresh committed." if committed else "Graph refresh completed with no changes.",
            )
        finally:
            try:
                manager.cleanup_temporary_checkout(temporary)
            except GitWorktreeError as cleanup_error:
                self.emit(
                    "graphify",
                    f"Temporary target-branch checkout cleanup failed: {cleanup_error}",
                    "error",
                )

    def emit(self, phase: str, message: str, kind: str = "status") -> None:
        LOGGER.debug("Orchestration event phase=%s kind=%s message_length=%d", phase, kind, len(message))
        self.on_event(phase, message, kind)

    def _completed_tokens(self, completed: bool = True) -> int:
        """Expose usage only after the whole task reaches completion."""
        return self._tokens_consumed if completed else 0

    @staticmethod
    def _raise_if_stopped(control: AgentControl | None) -> None:
        if control is not None and control.stop_reason:
            raise AgentStopped(control.stop_reason)
