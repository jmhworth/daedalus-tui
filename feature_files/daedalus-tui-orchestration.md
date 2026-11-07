# Daedalus TUI Local Orchestration

## Summary
The standalone TUI orchestration layer creates isolated Git worktrees from a configurable target branch (default `main`), runs a selected local agent, verifies its changes, resolves integration failures, and promotes successful task branches into that target branch.

## Key Points
- **Worktree isolation**: Each task receives an `agent/task-<id>` branch and a sibling `.daedalus-worktrees` directory.
- **Project worktree provisioning**: An optional target-project `.daedalus` file can run one install command inside each task worktree and symlink declared repository-relative shared paths from the primary checkout.
- **Restart recovery**: Persisted failed tasks are restored with Retry available, while tasks active during shutdown are restored as paused tasks with their existing worktree context.
- **Conversation follow-ups**: Completed and failed tasks can start a separately numbered linked task that carries earlier user prompts and assistant outputs as agent context; Retry continues to rerun a failed task independently.
- **Automatic task follow-ups**: A task may include an optional next-task prompt in the composer. It is persisted with the parent and only creates and dispatches the linked task after the parent reaches successful completion; failures leave it unsent.
- **Plan proposal status**: Confirmed plan-mode tasks persist as `proposed`, keeping plan review distinct from completed coding while enabling the Implement handoff.
- **Verification repair**: Failed task checks launch repair attempts in the same worktree up to the configured limit.
- **Verification diagnostics**: When every verification attempt fails, each attempt's failure output is written to the task error panel and included in the final failure message.
- **Supabase migration apply**: After verification succeeds, ordinary projects retain their existing `supabase/migrations/` flow. For registered personal Supabase projects, orchestration detects `daedalus-migrations/` changes, synchronizes SQL into the TUI-root aggregate, and runs Supabase CLI from the TUI root. Same-name SQL conflicts preserve the root version and provide both SQL bodies to a coding-profile repair agent. Launch bootstrap validates the TUI root `.env` against each project's registration and applies pending aggregate migrations only for activated projects.
- **Integration-stage retry**: After coding, verification, and any required migration push succeed, failed integration or resolver retries resume at the integration gate instead of re-running the coding agent.
- **Resolver fallback**: Merge conflicts and post-merge verification failures launch the selected provider as a resolver with the latest failure details.
- **Configurable target branch**: `target_branch` (default `main`, alias
  `primary_branch`) in the orchestration parameter file is only the default
  seed for new projects; each project's Branch Select can override it in
  launch-root memory. New task worktrees are based on that effective local
  branch and successful tasks promote into it; the operator does not need it
  checked out.
- **Safe promotion**: The target branch tip must remain unchanged during integration; when it is checked out the working tree must be clean for merge-based promotion, otherwise promotion fast-forwards the target ref in place; failed worktrees remain available for inspection.
- **Dirty primary commits**: When starting or resuming a task, and again when integration captures its base, orchestration auto-commits dirty target-branch files if that branch is checked out. Capturing after the commit makes those files part of the task's integration base; changes arriving after capture still fail the promotion check so they cannot be omitted from the integrated branch.
- **Concurrent integration**: Up to four task agents and their verification runs execute concurrently, then ready tasks pass through a first-ready serialized integration gate before promotion.
- **Connectivity recovery**: Agent subprocesses have a bounded timeout, report actionable offline/service diagnostics, and failed requests can be retried without losing their task context.
- **Agent Git boundary**: Task, repair, and resolver agents edit files only; the orchestration layer owns staging, commits, merges, migration pushes, and cleanup. Coding tasks that intentionally leave the worktree unchanged (for example an ask-style prompt sent in coding mode) complete successfully without a commit and skip verification and promotion.
- **Sync conflict recovery**: Operator Sync pull/merge conflicts that leave unmerged paths preserve an isolated `.sync-pull-*` / `.sync-resolve-*` worktree (temp `daedalus/sync-resolve-*` branch when the operating branch is already checked out elsewhere). The task transcript explains that plan mode was triggered by unmerged files and that the plan reviews conflict resolutions and operator decisions before coding; questions go to the operator; when `no_more_questions` with an empty questions array, coding auto-starts in the same worktree, then orchestration finalizes the merge under the project integration gate and pushes with `pull_first=False`. Stock `implement_plan` / worktree discard is not used. First cut skips verify→promote→graphify.
- **Profile prompt boundary**: The orchestrator reloads the selected repository profile from the active task worktree and embeds it inline before each task, repair, follow-up planning, or resolver prompt; agents apply supplied profile content directly without reopening the file, while the mode and orchestration constraints that follow remain authoritative.
- **Topic prompt boundary**: When a task carries a topic slug, the orchestrator reloads that topic markdown from the task worktree and embeds it with mode-specific instructions before task, repair, and resolver prompts; missing topics emit a non-fatal diagnostic and omit the embed.
- **Graph refresh boundary**: Graphify runs only after successful primary promotion, and a failed refresh is cleaned up and reported without starting a resolver.
- **Local-only boundary**: No persistence or daemon communications. Agent subprocesses inherit the TUI process environment and may read `CURSOR_API_KEY` from the Daedalus TUI package `.env`; launch-root and target-project `.env` files are not passed to agents. Personal Supabase migration operations read the Daedalus TUI root `.env`; Activate copies only app-facing API settings and the registered schema into each target project's ignored `.env`, which is not passed to task agents. Orchestration may push Supabase migrations via the CLI; agents still do not own DB push. Automated orchestration never pushes Git remotes; an explicit operator Sync in the TUI may pull then push the selected operating branch.
- **Project discovery boundary**: The TUI discovers only immediate launch-root child directories containing `feature_files`; nested paths are excluded, with the launch root used only when no eligible child exists.
- **Project-scoped execution**: The TUI creates one coordinator per discovered `feature_files` project, so task numbering, worktrees, branches, and integration gates stay scoped to the selected repository.
- **Shutdown diagnostics**: A rotating project-local debug log records agent process IDs, task transitions, Textual exceptions, worker shutdown, and on-demand all-thread stack dumps.

## Relevant Files
- `tui/orchestrator.py`: Single-task lifecycle, verification repair, migration push repair, integration, and resolver loops.
- `tui/task_coordinator.py`: Concurrent task records, executor limit, serialized integration gate, and linked automatic follow-up dispatch after success.
- `tui/transcript.py`: Selectable numbered task turns, italic submitted prompts, and reflowing task dividers.
- `tui/app.py`: Task selection, prompt editing, and Follow Up controls.
- `tui/token_usage.py`: Completed coding and proposed planning task usage records.
- `tui/git_worktree.py`: Git validation, worktree, branch listing, operator pull-then-push sync helper, merge, and cleanup operations.
- `tui/project_config.py`: Target-project `.daedalus` worktree provisioning settings.
- `tui/memory.py`: Atomic task snapshots, worktree identity, restart metadata, automatic follow-up intent, and per-project target branches.
- `tui/topics.py`: Topic discovery and embed helpers used at prompt-build time.
- `tui/verification.py`: Configured and convention-based verification execution.
- `tui/supabase_migrations.py`: Pending migration detection and non-interactive `supabase db push`.
- `tui/environment.py`, `tui/personal_supabase.py`: Canonical project-local environment loading/validation, Cursor operator credential fallbacks, and temporary TUI-root project-ref preparation used by launch and task applies.
- `tui/supabase_migrations.py`: Personal migration synchronization into the root aggregate and migration CLI invocation.
- `parameter_files/daedalus-tui-orchestration.toml`: Default target branch seed, worktree, verification, migration push, and retry settings.

## Dev Mode
HACKING

## State Log
- 2026-11-06: Added an optional persisted next-task prompt that is dispatched as a linked follow-up only after successful task completion.
- 2026-11-05: Explain in the Sync recovery transcript that plan mode follows pull conflicts and precedes conflict resolution and push.
- 2026-11-04: Corrected selectable transcript regression coordinates to target the assistant row after numbered task headers were added.
- 2026-11-04: Updated app regression expectations for numbered transcript turns and blank editable prompts on selected tasks.
- 2026-11-04: Added linked task follow-ups with persisted conversation context and numbered selectable transcript turns.
- 2026-11-04: Confirmed plan tasks now persist as `proposed`, with task review, implementation handoff, and token usage recognizing the new state.
- 2026-10-06: Coding tasks that finish with no worktree commit now complete as a successful no-op instead of failing with "Agent finished without creating a commit."
- 2026-10-03: Repaired regression coverage for dirty target auto-commit at integration capture without weakening the TUI-root Supabase environment contract.
- 2026-10-03: Integration now auto-commits dirty checked-out target-branch files before capturing the integration base, keeping those changes in the task's promotion ancestry.
- 2026-09-19: Updated coordinator test doubles to accept sync-recovery orchestrator kwargs so normal submit paths stay compatible.
- 2026-09-19: Added operator Sync conflict recovery that plans in a preserved isolated sync worktree, auto-implements when questions clear, finalizes under the integration gate, and pushes without stock implement_plan worktree discard.
- 2026-09-26: Agent subprocesses stopped loading launch-root and project `.env` files; Cursor credentials now come from the process environment or the TUI package `.env`, while Supabase operations keep using project-local credentials.
- 2026-09-19: Cursor agent runs now inherit non-empty `CURSOR_API_KEY` from the launch-root and TUI package `.env` when the target project omits it, without sharing Supabase credentials across projects.
- 2026-09-19: Noted that the operator Command Menu Sync action pulls then pushes the operating branch; automated orchestration still never owns Git remotes.
- 2026-09-16: Orchestration now loads each project's ignored `.env` for agent and Supabase subprocesses instead of sharing launch-root credentials.
- 2026-11-04: Documented activation-time app credential sync into project `.env` while keeping DB migration credentials in the TUI root and away from task agents.
- 2026-09-16: Auto-commit dirty primary files on task start/resume so send is not blocked, while promotion still requires a clean primary.
- 2026-09-14: Documented activated-only launch migration push while env-sync still covers all registered personal Supabase projects.
- 2026-09-13: Threaded the launch-root shared environment through task orchestration and serialized launch/task Supabase pushes per project while preserving task verify→push semantics.
- 2026-09-13: Noted that personal shared-Supabase schema registration scaffolds migrations only; orchestration remains the sole `supabase db push` owner.
- 2026-08-25: Added post-verification Supabase migration push with a verify→repair loop when `supabase/migrations/` changed, gated by `supabase_db_push_enabled`.
- 2026-09-26: Added registered-project `daedalus-migrations/` synchronization and root-owned CLI migration application.
- 2026-08-25: Clarified that remote push remains outside automated orchestration while the TUI may offer an operator-owned Push for the selected operating branch.
- 2026-08-24: Tagged tasks embed topic markdown from the worktree into task, repair, and resolver prompts.
- 2026-08-23: Made the orchestration parameter `target_branch` a default seed only, with per-project operating-branch overrides applied through each coordinator's cloned settings.
- 2026-08-23: Logged every exhausted verification failure reason into the task error panel and resumed retries from integration once coding had already succeeded.
- 2026-08-23: Allowed any configured target branch (default main) as the worktree base and promotion destination without requiring that branch to be checked out.
- 2026-08-14: Added independent worktree, verification, merge, and resolver orchestration without daemon or cloud communication dependencies.
- 2026-08-14: Added bounded multi-task execution with first-ready serialized promotion and explicit orchestration ownership of all Git operations.
- 2026-08-14: Hardened successful worktree removal so committed tasks clean up even when agent tooling leaves untracked artifacts behind.
- 2026-08-14: Passed target-repository environment files into isolated Cursor tasks while preserving process-level credential precedence.
- 2026-08-14: Added cooperative subprocess stopping with preserved paused worktrees and force-cleaned cancelled task branches.
- 2026-08-14: Passed accumulated resume notes into continued task runs without changing the independent worktree lifecycle.
- 2026-08-14: Kept orchestration transcripts available for Vim selection yanks without changing task execution or integration behavior.
- 2026-08-17: Staged resolver worktree changes before checking for unmerged paths so file-only conflict resolutions are recognized by the orchestration layer.
- 2026-08-14: Moved graph refreshes into a best-effort post-promotion hook and discarded accidental task-worktree graph output before orchestration commits.
- 2026-08-14: Connected orchestration to launch-root project discovery while preserving independent task state when the sidebar changes projects.
- 2026-08-17: Added bounded agent execution timeouts and retryable failed tasks so network outages do not leave executor threads hanging or discard the plan context.
- 2026-08-17: Made shutdown detach callbacks, wait for cancellable executor work, and bound subprocess pipe-reader joins so closed TUI sessions do not linger in Python thread shutdown.
- 2026-08-17: Terminated complete agent process groups on cancellation, bounded the app shutdown grace period, and added persistent debug logging plus `SIGUSR1` all-thread dumps for stuck workers.
- 2026-08-17: Isolated non-interactive agent stdin from the Textual terminal and added an idempotent atexit shutdown guard plus asyncio failure logging for UI exits that bypass normal unmount.
- 2026-08-17: Preserved mounted plan-answer selectors while answer confirmation is queued, and moved unexpected-exit cleanup ahead of Python's executor-thread join.
- 2026-08-17: Persisted queued task snapshots before worker submission so fast completions cannot be overwritten by stale queued state, including retries.
- 2026-08-17: Hardened plan-confirmation handoff against invalid or revised agent payloads, retained recoverable answers, and removed the clean planning worktree once implementation is queued.
- 2026-08-17: Injected repository-owned coding, planning, and integrating profiles into every applicable agent prompt, with non-fatal diagnostics for missing profiles and direct mode constraints preserved.
- 2026-08-17: Extended agent inactivity timeouts to 450 seconds and refreshed them for every stdout update so long-running tasks remain connected while the agent is making progress.
- 2026-08-20: Added target-project `.daedalus` provisioning so worktrees can install dependencies locally and link declared shared data folders before agents run.
- 2026-08-20: Added restart recovery for failed and interrupted tasks, preserving actionable task records and existing worktree contexts across TUI relaunches.
- 2026-09-05: Restricted orchestration project discovery and refresh retention to immediate launch-root children so nested coordinators cannot reappear in the selector.
