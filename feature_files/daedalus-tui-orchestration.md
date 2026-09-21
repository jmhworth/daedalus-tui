# Daedalus TUI Local Orchestration

## Summary
The standalone TUI orchestration layer creates isolated Git worktrees from a configurable target branch (default `main`), runs a selected local agent, verifies its changes, resolves integration failures, and promotes successful task branches into that target branch.

## Key Points
- **Worktree isolation**: Each task receives an `agent/task-<id>` branch and a sibling `.daedalus-worktrees` directory.
- **Project worktree provisioning**: An optional target-project `.daedalus` file can run one install command inside each task worktree and symlink declared repository-relative shared paths from the primary checkout.
- **Restart recovery**: Persisted failed tasks are restored with Retry available; tasks paused by a clean shutdown are restored as paused, and runs that were still active when the process ended are restored as `interrupted`, both with their existing worktree context and never auto-launched.
- **Non-destructive interruption**: `AgentControl.request_interrupt` stops the agent or verification subprocess group, releases a task waiting at the integration gate, and is checked immediately before promotion; the orchestrator returns `interrupted` with the worktree, branch, and uncommitted files preserved. Only the explicit discard path removes a worktree.
- **Follow-up execution**: A later turn reuses a preserved worktree (the agent is told to inspect existing work) or, after cleanup, runs under a new execution id (`<task>-r2`, …) in a fresh worktree from the operating branch while the logical task stays the same.
- **Verification repair**: Failed task checks launch repair attempts in the same worktree up to the configured limit.
- **Descriptive task commits**: Task, verification-repair, Supabase-repair, Firebase-repair, resolver, and post-promotion graph commits use the stable readable task title generated from the user's goal, with the orchestration stage appended only when needed. This keeps follow-up and retry commits tied to the task they completed; the separate dirty-primary bootstrap commit continues to use its parameterized pre-task message.
- **Interpreter discovery**: Convention-based pytest commands run the orchestrator's own interpreter by absolute path (`sys.executable`), falling back to `python3` then `python` on `PATH` only when that path is unknown. A bare `python` is never emitted: it would be resolved against the orchestrator's `PATH` at discovery time but executed later in the worktree with the child process's `PATH`, and it can resolve to a version-manager shim that is executable yet fails to exec.
- **Verification diagnostics**: When every verification attempt fails, each attempt's failure output is written to the task error panel and included in the final failure message.
- **Supabase migration push**: After verification succeeds, orchestration runs `supabase db push --yes` only when the task changed `supabase/migrations/` relative to the worktree base commit; failures emit diagnostics and launch coding-profile repairs up to the verification attempt limit before blocking integration. Personal schema registration (separate feature) only scaffolds those migration files; this feature remains the sole remote push owner.
- **Firebase deploy**: After verification and any Supabase migration push succeed, orchestration runs `firebase deploy --only firestore:rules,firestore:indexes --non-interactive` only for projects whose `.daedalus` marks them Firebase-registered and only when the task changed the parameterized Firebase watched paths; failures emit diagnostics and launch coding-profile repairs up to the verification attempt limit before blocking integration. Registration (separate feature) only scaffolds those files; this feature remains the sole remote deploy owner.
- **Integration-stage retry**: After coding, verification, and any required migration push succeed, failed integration or resolver retries resume at the integration gate instead of re-running the coding agent.
- **Resolver fallback**: Merge conflicts and post-merge verification failures launch the selected provider as a resolver with the latest failure details.
- **Configurable target branch**: `target_branch` (default `main`, alias
  `primary_branch`) in the orchestration parameter file is only the default
  seed for new projects; each project's Branch Select can override it in
  launch-root memory. New task worktrees are based on that effective local
  branch and successful tasks promote into it; the operator does not need it
  checked out.
- **Dirty operating branch auto-commit**: When the target branch is checked out with uncommitted work, validation stages those paths (Daedalus' own runtime files stay untracked), commits them with the parameterized message, and pushes the branch to the configured remote before the task worktree is created, so a dirty checkout starts the task instead of failing it. A successful push emits the pushed commit SHA as a durable notice in the TUI and records it in the shared launch-root memory; the Push log view makes the record browsable. A missing remote or a failed push is reported as a warning and never blocks the run; `dirty_primary_autocommit_enabled = false` restores the original clean-worktree error.
- **Safe promotion**: The target branch tip must remain unchanged during integration; when it is checked out the working tree must stay clean for merge-based promotion, otherwise promotion fast-forwards the target ref in place; failed worktrees remain available for inspection.
- **Concurrent integration**: Up to four task agents and their verification runs execute concurrently, then ready tasks pass through a first-ready serialized integration gate before promotion.
- **Connectivity recovery**: Agent subprocesses have a bounded timeout, report actionable offline/service diagnostics, and failed requests can be retried without losing their task context.
- **Agent Git boundary**: Task, repair, and resolver agents edit files only; the orchestration layer owns staging, commits, merges, migration pushes, and cleanup.
- **Post-promotion push**: Inside the integration gate, after `promote` and the graph refresh commit, `LocalOrchestrator.publish_promotion` pushes the target branch to `git_remote` through `GitWorktreeManager.push_primary(enabled=True)` when `promotion_push_enabled` is on, so a promotion whose merge conflicts were resolved is published before the task is reported complete. The pushed-commit notice feeds the same Push log as the dirty-branch auto-commit; a missing remote or failed push is a warning, never a task failure. `GitWorktreeManager.commit_primary_file` commits one Daedalus-owned file onto the target branch (through a temporary checkout when the branch is not checked out) without sweeping in anything else the operator staged; Orchestrate Mode uses it for its context file.
- **Profile prompt boundary**: The orchestrator reloads the selected repository profile from the active task worktree and embeds it inline before each task, repair, follow-up planning, or resolver prompt; agents apply supplied profile content directly without reopening the file, while the mode and orchestration constraints that follow remain authoritative. Projects without `.agents/profiles/` (opened by path rather than initialized by Daedalus) fall back to the profiles bundled under `tui/templates/project-initializer/.agents/profiles/`, reported as a status rather than an error.
- **Claude command allowlist**: `claude --print` cannot answer permission prompts, so every agent request carries `Bash(<command>:*)` rules for the worktree's discovered verification commands (both the resolved interpreter path and its basename), merged by the agent runner with the configured `[claude] allowed_tools`; without this, Claude agents were denied `pytest`/`npm test` and gave up before making changes.
- **Topic prompt boundary**: When a task carries a topic slug, the orchestrator reloads that topic markdown from the task worktree and embeds it with mode-specific instructions before task, repair, and resolver prompts; missing topics emit a non-fatal diagnostic and omit the embed.
- **Graph refresh boundary**: Graphify runs only after successful primary promotion, and a failed refresh is cleaned up and reported without starting a resolver.
- **Local-only boundary**: No persistence or daemon communications. Orchestration may push pending Supabase migrations for target projects via the Supabase CLI; agents still do not own DB push. The only Git remote push orchestration performs is publishing the operating branch after auto-committing a dirty primary worktree; otherwise an explicit operator Push in the TUI publishes the selected operating branch.
- **Project discovery boundary**: The TUI discovers only immediate launch-root child directories; nested paths are excluded, with the launch root used only when no eligible child exists. Daedalus-formatted children (those with `feature_files`) always qualify, and the `[projects]` parameter table decides whether plain Git checkouts and other directories are listed alongside them.
- **Project-scoped execution**: The TUI creates one coordinator per discovered `feature_files` project, so task numbering, worktrees, branches, and integration gates stay scoped to the selected repository.
- **Shutdown diagnostics**: A rotating project-local debug log records agent process IDs, task transitions, Textual exceptions, worker shutdown, and on-demand all-thread stack dumps.

## Relevant Files
- `tui/orchestrator.py`: Single-task lifecycle, verification repair, migration push repair, Firebase deploy repair, integration, and resolver loops.
- `tui/firebase.py`: Firebase change detection and the non-interactive deploy wrapper.
- `tui/task_coordinator.py`: Concurrent task records, executor limit, and serialized integration gate.
- `tui/git_worktree.py`: Git validation, dirty-primary auto-commit and push, worktree, branch listing, operator push helper, merge, and cleanup operations.
- `tui/project_config.py`: Target-project `.daedalus` worktree provisioning settings.
- `tui/memory.py`: Atomic task snapshots, worktree identity, restart metadata,
  per-project target branches, and pushed-commit history.
- `tui/app.py`: Operator Push feedback and the browsable Push log view.
- `tui/topics.py`: Topic discovery and embed helpers used at prompt-build time.
- `tui/verification.py`: Configured and convention-based verification execution.
- `tui/supabase_migrations.py`: Pending migration detection and non-interactive `supabase db push`.
- `parameter_files/daedalus-tui-orchestration.toml`: Default target branch seed, worktree, dirty-primary auto-commit and push, verification, migration push, and retry settings.

## Dev Mode
HACKING

## State Log
- 2026-09-21: Added optional project-specific Claude settings and tool rules, environment-file injection without worktree secret copies, excluded atomic memory temp files from Git staging, and skipped empty repair commits after staging.
- 2026-09-18: Pushed the target branch after every successful promotion (`promotion_push_enabled`, inside the integration gate after the graph refresh commit) and added `commit_primary_file` plus a `push_primary(enabled=...)` override so Orchestrate Mode can commit and push its context file the moment it is written.
- 2026-09-16: Pre-approved discovered verification commands for non-interactive Claude runs and fell back to Daedalus' bundled profiles when a project has no `.agents/profiles/`, after msb and tex-manager tasks logged missing-profile warnings and Claude agents were denied `pytest`/`npm test`.
- 2026-09-16: Replaced the dirty-primary start-up error with an auto-commit of the operator's pending changes plus a best-effort push of the operating branch, so a dirty checkout starts the task instead of failing it.
- 2026-09-16: Added pushed commit SHAs to success notices and shared memory,
  kept background push confirmations visible in the status line, and exposed a
  Push log view through the settings bar and Ctrl+H.
- 2026-09-16: Hardened interpreter discovery after the `PATH`-lookup fix still emitted a bare `python`, making `python_executable` accept the roots of the code under test and resolve, in order, a `.venv`/`venv` interpreter belonging to those roots, the active `VIRTUAL_ENV`, a `PATH` lookup, and finally the already-running `sys.executable`, so every discovered command names a real interpreter file rather than a name the child process must resolve itself.
- 2026-09-16: Fixed convention-based verification failing with `[Errno 2] No such file or directory: 'python'` on hosts that only provide `python3` by resolving the interpreter in `discover_commands` instead of hardcoding `python`.
- 2026-09-15: Added non-destructive interruption (`interrupted` results, a stop-aware integration gate, and a pre-promotion stop check), execution suffixes for follow-up worktrees, and per-run diagnostics files under `errors/`.
- 2026-09-15: Added an orchestration-owned Firebase deploy step that applies changed Firestore rules and indexes after verification and repairs failures with the coding profile before blocking integration.
- 2026-09-13: Noted that personal shared-Supabase schema registration scaffolds migrations only; orchestration remains the sole `supabase db push` owner.
- 2026-08-25: Added post-verification Supabase migration push with a verify→repair loop when `supabase/migrations/` changed, gated by `supabase_db_push_enabled`.
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
- 2026-09-16: Replaced task-id-only, repair-only, and resolver-only commit subjects with the stable readable task title plus an explicit orchestration-stage suffix, and carried that subject into post-promotion graph commits.
- 2026-09-17: Exposed a `resolver_selection` override and `before_agent`/`after_agent` hooks on `LocalOrchestrator` (plus task observers on `TaskCoordinator`) so Orchestrate Mode can resolve conflicts with the planner's model and place and read a task card in the worktree; ordinary tasks are unaffected.
