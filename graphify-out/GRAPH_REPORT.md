# Graph Report - daedalus-tui  (2026-11-04)

## Corpus Check
- 99 files · ~98,324 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1911 nodes · 5318 edges · 106 communities (91 shown, 15 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 614 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `278ebf62`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- PlanQuestion
- DaedalusVimTextArea
- AgentRunner
- DaedalusTuiApp
- app.py
- TokenUsageStore
- GitWorktreeManager
- Daedalus TUI Local Token Usage Memory
- update_repository
- daedalus-tui
- Key
- Path
- Path
- Path
- architecture.md
- coding.md
- planning.md
- Daedalus TUI Project Instructions
- integrating.md
- TaskRecord
- ._shutdown_coordinators
- ._set_status
- update_repository
- Daedalus TUI Coding Statistics
- ._set_status
- .provider_split
- .on_mount
- log_exception
- CodingStatisticsScreen
- calculate_token_usage
- PlanAnswerSelect
- discover_projects
- .emit
- ._render_line_strip
- agent_runner.py
- architecture.md
- integrating.md
- ._set_status
- Daedalus Project Instructions
- README.md
- KeyboardShortcutsScreen
- debug_log.py
- ._rebuild_plan_questions
- CandidateFeatureGroup
- KeyboardShortcutsScreen
- orchestrator.py
- DaedalusTuiApp
- ._persist_task
- ._rebuild_plan_questions
- environment.py
- CompactSettingsSelect
- Daedalus TUI Call Graph Visualization
- b.py
- TranscriptLog
- conftest.py
- cycle_a.py
- DescriptorEmbedder
- __init__.py
- PlanClarification
- trading.py
- CodingStatisticsScreen
- ambiguous_a.py
- ambiguous_b.py
- module_resource.py
- scopes.py
- task_coordinator.py
- __init__.py
- task_coordinator.py
- log_exception
- GitWorktreeError
- _collapse_inner_safe
- render_call_graph_tree.py
- ._on_personal_supabase_activation_progress
- ProjectWorktreeSettings
- CallGraphRunnerTests
- bootstrap_personal_supabase
- push_migrations
- debug_log.py
- test_app.py
- PersonalSupabaseConfirmationScreen
- select_roots
- TranscriptLog
- discover_projects
- RegistrationResult
- ._focus_submitted_task
- CandidateFeatureGroup
- .__init__
- orchestrator.py
- IntegrationCoordinator
- remove_personal_supabase
- ._apply_task_event
- PersonalSupabaseSetupWizardScreen
- ._refresh_push_button
- SyncMergeConflictError
- render_html
- PlanClarificationScreen
- ._on_personal_supabase_activation_progress
- .compose
- ._render_line_strip
- .__init__
- ._on_personal_supabase_activation_progress
- .action_view_topic
- .has_active_sync_recovery
- ._parse_plan_messages
- .nav_word_end

## God Nodes (most connected - your core abstractions)
1. `DaedalusTuiApp` - 185 edges
2. `TuiAppTests` - 125 edges
3. `TaskCoordinator` - 94 edges
4. `OrchestrationSettings` - 77 edges
5. `AgentRunner` - 73 edges
6. `TaskRecord` - 72 edges
7. `FakeCoordinator` - 67 edges
8. `WorktreeContext` - 67 edges
9. `GitWorktreeManager` - 67 edges
10. `DaedalusVimTextArea` - 66 edges

## Surprising Connections (you probably didn't know these)
- `FakeStream` --uses--> `AgentControl`  [INFERRED]
  tests/test_agent_runner.py → tui/agent_runner.py
- `FakeProcess` --uses--> `AgentControl`  [INFERRED]
  tests/test_agent_runner.py → tui/agent_runner.py
- `InterruptibleProcess` --uses--> `AgentControl`  [INFERRED]
  tests/test_agent_runner.py → tui/agent_runner.py
- `AgentRunnerTests` --uses--> `AgentControl`  [INFERRED]
  tests/test_agent_runner.py → tui/agent_runner.py
- `FakeRunner` --uses--> `CodingStatisticsScreen`  [INFERRED]
  tests/test_app.py → tui/app.py

## Import Cycles
- None detected.

## Communities (106 total, 15 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.21
Nodes (21): score_band(), _canonical_tree_name(), _histogram_bars(), _layout_extent_y(), _layout_subtree(), _layout_trees(), _LayoutNode, _layouts_bounds() (+13 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.11
Nodes (12): Path, Apply provider-specific model and reasoning choices to all controls., Avoid posting Select.Changed events when the options are unchanged., Read the current value from the same selectors used for submission., Populate the compact value Select while retaining its active category., Apply a compact value through the existing wide-control state., Memory override for the project, else the parameter-file default., Update the project's coordinator so later submits use ``branch``. (+4 more)

### Community 2 - "AgentRunner"
Cohesion: 0.08
Nodes (30): Binding, Mount, CompactSettingsSelect, _format_codex_usage(), _format_codex_window(), KeyboardShortcutsScreen, _LegacyCompatibleBinding, PlanAnswerSelect (+22 more)

### Community 3 - "DaedalusTuiApp"
Cohesion: 0.07
Nodes (42): AnnAssign, Assign, AsyncFunctionDef, Attribute, AugAssign, Call, ClassDef, comprehension (+34 more)

### Community 4 - "app.py"
Cohesion: 0.22
Nodes (9): CallGraphTreeTests, candidate_feature_id(), group_candidate_features(), Return a stable ID derived solely from a group's sorted member symbols., Group symbols connected by inclusive-threshold relations.      Parent/child dire, ScoredRelation, SimilarityResult, Choose tree roots from configured entry points or orphan graph nodes. (+1 more)

### Community 5 - "TokenUsageStore"
Cohesion: 0.29
Nodes (6): Applying answers, Bridge Agent Profile, Build-loop tasking, cp_doc structure, Hard rules, Purpose

### Community 6 - "GitWorktreeManager"
Cohesion: 0.10
Nodes (15): Resize, Selectable transcript rendering with semantic assistant-message emphasis., Return the width available for transcript text inside the Log., Wrap one logical line at word boundaries when the width permits., Add a file glyph to bracketed paths and filenames in agent text., Split an overlong word with visible hyphens at cell boundaries., A selectable log that can emphasize a task's final assistant message.      ``Log, Return the tone assigned to each rendered transcript line. (+7 more)

### Community 7 - "Daedalus TUI Local Token Usage Memory"
Cohesion: 0.29
Nodes (6): Daedalus TUI Local Persistent Memory, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 8 - "update_repository"
Cohesion: 0.11
Nodes (25): TopicsTests, build_topic_instructions(), build_topic_template(), embed_topic(), list_topic_slugs(), load_topic_settings(), load_topic_text(), Path (+17 more)

### Community 11 - "Key"
Cohesion: 0.09
Nodes (10): CompletedProcess, Stage the current worktree contents for orchestration checks or commit., Remove graphify output changes from an agent worktree.          Graphify refresh, Keep a read-only planning pass from becoming an implementation change., Commit only the generated graph after a successful primary update., Return a directory whose HEAD matches the target branch tip.          When the r, Remove a short-lived primary checkout created for post-promotion work., Remove a cancelled task even when its branch was never integrated. (+2 more)

### Community 12 - "Path"
Cohesion: 0.29
Nodes (6): Daedalus Textual TUI, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 13 - "Path"
Cohesion: 0.29
Nodes (6): Daedalus TUI Local Orchestration, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 15 - "architecture.md"
Cohesion: 0.33
Nodes (5): Architecture Boundaries, Development Lifecycle, Evidence Extraction, Execution Boundaries (CRITICAL), Parameter Files

### Community 16 - "coding.md"
Cohesion: 0.29
Nodes (6): 4-Stage Development Lifecycle, Debugging, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization, Topics (when tagged)

### Community 17 - "planning.md"
Cohesion: 0.29
Nodes (6): Execution Boundaries (CRITICAL), Feature File Context, Graphify, Parameter Files, Planning Boundaries, Topics (when tagged)

### Community 18 - "Daedalus TUI Project Instructions"
Cohesion: 0.40
Nodes (4): Daedalus TUI Project Instructions, graphify, Project boundaries, Task mode

### Community 19 - "integrating.md"
Cohesion: 0.40
Nodes (4): Development Lifecycle, Execution Boundaries (CRITICAL), Integration Boundaries, Parameter Files

### Community 20 - "TaskRecord"
Cohesion: 0.16
Nodes (17): ProgressCallback, ProjectInitializerTests, find_github_url(), initialize_project(), load_initializer_settings(), matching_request_marker(), materialize_templates(), normalize_github_url() (+9 more)

### Community 21 - "._shutdown_coordinators"
Cohesion: 0.12
Nodes (15): Path, Remove the clean, read-only planning worktree after coding is queued., Persist task state, coalescing high-frequency streamed messages., Force-remove leftover sync worktrees from interrupted recoveries for ``branch``., Attach plan-mode recovery to a preserved Sync conflict worktree., Ask a side-channel clarification about one plan question without plan follow-up., Create a new coding task from a confirmed plan review., Auto-start coding in the same conflict worktree after a confirmed sync plan. (+7 more)

### Community 22 - "._set_status"
Cohesion: 0.29
Nodes (6): Daedalus TUI Codex Plan Usage, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 23 - "update_repository"
Cohesion: 0.09
Nodes (33): build_symbol_contexts(), _descriptor_hash(), DescriptorEmbedder, _doc_for_definition(), extract_docs_for_symbols(), format_descriptor(), _format_name_list(), invert_edges() (+25 more)

### Community 24 - "Daedalus TUI Coding Statistics"
Cohesion: 0.29
Nodes (6): Daedalus TUI Coding Statistics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 25 - "._set_status"
Cohesion: 0.12
Nodes (16): AbstractEventLoop, BaseException, Provider-specific subprocess execution with normalized agent messages., Finish Select setup without allowing a stale value to exit the TUI.          Pla, configure_debug_logging(), install_fault_handler(), _install_thread_exception_logging(), log_exception() (+8 more)

### Community 26 - ".provider_split"
Cohesion: 0.20
Nodes (10): AgentControl, Cooperative stop signals shared by a task and its active subprocess., AgentStopped, OrchestrationResult, Path, RuntimeError, Plan or resolve Sync merge conflicts in a preserved sync worktree., Load a repository-owned profile immediately before building a prompt. (+2 more)

### Community 27 - ".on_mount"
Cohesion: 0.10
Nodes (12): TaskEventCallback, IntegrationCoordinator, _nonnegative_int(), _phase_for_status(), Lock, Rehydrate this project's persisted tasks after a TUI restart., Recover review questions from the last persisted plan response., Run ready integration operations one at a time in ready order. (+4 more)

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.29
Nodes (5): ProjectDiscoveryTests, discover_projects(), Path, Discovery of Daedalus-supported repositories beneath a launch root., Find immediate child folders containing a direct ``feature_files`` child.      G

### Community 30 - "calculate_token_usage"
Cohesion: 0.05
Nodes (34): TaskMemoryStoreTests, TokenUsageTests, Path, Small local JSON stores for persistent task history., Remove one project's operating-branch override (absent = use default)., Return the remembered default topic for a project, if any., Remember one project's default topic without losing other entries., Remove one project's topic override (absent = no default topic). (+26 more)

### Community 31 - "PlanAnswerSelect"
Cohesion: 0.29
Nodes (6): Daedalus TUI Project Initialization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 32 - "discover_projects"
Cohesion: 0.25
Nodes (7): 4-Stage Development Lifecycle, Alignment, Debugging, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization, Topics (when tagged)

### Community 33 - ".emit"
Cohesion: 0.09
Nodes (32): PlanTests, Cursor may include prose and omit redundant false confirmation., Resolve a Select value that is legal for the current question options., build_implementation_prompt(), build_plan_clarification_prompt(), build_plan_followup_prompt(), custom_answer_text(), encode_custom_answer() (+24 more)

### Community 34 - "._render_line_strip"
Cohesion: 0.25
Nodes (7): 4-Stage Development Lifecycle, Alignment, Debugging, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization, Topics (when tagged)

### Community 36 - "architecture.md"
Cohesion: 0.33
Nodes (5): 4-Stage Development Lifecycle, Evidence Extraction, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization

### Community 37 - "integrating.md"
Cohesion: 0.40
Nodes (4): 4-Stage Development Lifecycle, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization

### Community 38 - "._set_status"
Cohesion: 0.16
Nodes (24): abort_sync_merge(), _create_isolated_sync_worktree(), _delete_branch_if_present(), finalize_sync_merge(), _force_remove_worktree(), _is_ancestor(), list_local_branches(), list_unmerged_paths() (+16 more)

### Community 39 - "Daedalus Project Instructions"
Cohesion: 0.33
Nodes (5): Daedalus Project Instructions, graphify, Shared personal Supabase, Task mode, Topics

### Community 41 - "KeyboardShortcutsScreen"
Cohesion: 0.11
Nodes (5): Agent plan text must not be parsed as Textual/Rich markup., Follow-up questions must not crash when old option ids linger on widgets., Deferred Select init must not fatal-exit on a leftover option id., Clearing questions after confirmation must keep the TUI alive., PlanOption

### Community 42 - "debug_log.py"
Cohesion: 0.16
Nodes (15): Popen, Protocol, VerificationTests, discover_commands(), format_process_result(), package_has_test_script(), CompletedProcess, Path (+7 more)

### Community 43 - "._rebuild_plan_questions"
Cohesion: 0.12
Nodes (7): FakeCoordinator, FakeRunner, settings(), PersonalSupabaseRemovalResult, Outcome of removing the local personal-Supabase integration artifacts., DaedalusProject, A repository recognized by the presence of a ``feature_files`` folder.

### Community 44 - "CandidateFeatureGroup"
Cohesion: 0.13
Nodes (9): AgentRunnerTests, FakeProcess, FakeStream, InterruptibleProcess, AgentLogEvent, AgentRequest, AgentRunner, Run Codex or Cursor directly and emit only assistant-facing messages. (+1 more)

### Community 45 - "KeyboardShortcutsScreen"
Cohesion: 0.20
Nodes (9): Constraints and Design Principles, Desired End State, Intended Import Workflow, Open Questions, Project Imports to the Daedalus Format, Scope and Durable Context, State Log, Topic Goal (+1 more)

### Community 46 - "orchestrator.py"
Cohesion: 0.25
Nodes (6): CandidateFeatureGroup, A deterministic connected component of qualifying similarity relations., Return the stable identifier using the concise ``id`` spelling., Compatibility alias for callers that refer to group relations directly., _feature_ids_by_member(), Map each grouped symbol to its stable candidate-feature ID.

### Community 47 - "DaedalusTuiApp"
Cohesion: 0.16
Nodes (7): Key, Route visual-line mode and mirror new yanks to the host clipboard., Add Daedalus prompt commands that the dependency does not provide., Select the current line and enter Vim visual-line mode., Select every character in the lines between the start and cursor., Handle movement and operators while whole lines are selected., Expose operator-pending so the caret can become an underline.

### Community 48 - "._persist_task"
Cohesion: 0.17
Nodes (5): FakeOrchestrator, TaskCoordinatorTests, OrchestrationSettings, Submit independent prompts while sharing a serialized integration gate., TaskCoordinator

### Community 49 - "._rebuild_plan_questions"
Cohesion: 0.22
Nodes (5): Changed, CodingStatisticsScreen, _format_count(), _format_tokens(), Show token or task usage history and derived coding statistics.

### Community 50 - "environment.py"
Cohesion: 0.29
Nodes (6): Daedalus TUI Command Menu, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 51 - "CompactSettingsSelect"
Cohesion: 0.21
Nodes (4): PersonalSupabaseTests, Path, Scaffold supabase files, env placeholders, profiles, and a ``.daedalus`` marker., register_personal_supabase()

### Community 52 - "Daedalus TUI Call Graph Visualization"
Cohesion: 0.29
Nodes (6): Daedalus TUI Call Graph Visualization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 53 - "b.py"
Cohesion: 0.10
Nodes (21): alpha(), Entry helper that fans out into order and UI branches., beta(), Continue the sample call chain toward gamma., gamma(), Leaf helper in the sample call chain., make_runner(), create_order() (+13 more)

### Community 54 - "TranscriptLog"
Cohesion: 0.10
Nodes (5): OutputCallback, Thread, Track an inactivity deadline that agent stdout can refresh., Prefer Codex JSONL error events over benign stderr noise., _TimeoutTracker

### Community 55 - "conftest.py"
Cohesion: 0.50
Nodes (3): pytest_configure(), Pytest hooks shared across the test suite., Install pyan3 when call-graph tests run in an environment missing it.

### Community 57 - "DescriptorEmbedder"
Cohesion: 0.08
Nodes (8): Pressed, Submitted, CreateTopicScreen, PersonalSupabaseRemovalConfirmationScreen, ProjectInitializerScreen, Collect the context needed to initialize and populate a topic file., Require an exact project-name confirmation before local cleanup., Collect a project slug and create a Daedalus-compatible directory.

### Community 59 - "PlanClarification"
Cohesion: 0.08
Nodes (49): _allow_list_comment(), _commit_paths(), commit_personal_supabase_scaffold(), _ensure_env_example(), _ensure_profile_guidance(), _ensure_supabase_scaffold(), _env_example_block(), _git_output() (+41 more)

### Community 60 - "trading.py"
Cohesion: 0.32
Nodes (5): calculate(), execute_trade(), Portfolio, Assignment lineage, augassign, attribute mutate, and unique call mapping., run_pipeline()

### Community 61 - "CodingStatisticsScreen"
Cohesion: 0.22
Nodes (7): OrchestratorTests, AgentResult, WorktreeContext, GraphifyResult, LocalOrchestrator, PushResult, VerificationResult

### Community 62 - "ambiguous_a.py"
Cohesion: 0.67
Nodes (3): helper(), Ambiguous same-named callees should not emit PASSED_TO edges., run_local()

### Community 63 - "ambiguous_b.py"
Cohesion: 0.67
Nodes (3): helper(), Second helper with the same simple name as ambiguous_a.helper., run_other()

### Community 66 - "task_coordinator.py"
Cohesion: 0.29
Nodes (6): Daedalus TUI Personal Shared Supabase, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 68 - "task_coordinator.py"
Cohesion: 0.15
Nodes (19): activate_personal_supabase(), bootstrap_personal_supabase(), is_personal_supabase_activated(), is_personal_supabase_registered(), load_personal_supabase_status(), PersonalSupabaseStatus, Phase 1 (if needed) then Phase 2: Git commit, preflight, and migration push., Derive and validate the Postgres schema name from the project directory slug. (+11 more)

### Community 69 - "log_exception"
Cohesion: 0.10
Nodes (12): Exception, Pause active agents before ThreadPoolExecutor joins its workers.      CPython ex, Stop agents before an explicit Textual exit begins., Persist Textual failures that would otherwise only flash on screen., Cover terminal and event-loop exits that bypass Textual unmount., Run before ThreadPoolExecutor's internal interpreter-exit join., Clean up if Textual's run loop returns without its unmount hook., Idempotently detach task callbacks and request child-process shutdown. (+4 more)

### Community 70 - "GitWorktreeError"
Cohesion: 0.31
Nodes (5): GitWorktreeError, push_branch(), RuntimeError, Push a local branch to ``remote``, setting upstream with ``-u`` when needed., Install project resources and link declared shared read-only paths.

### Community 71 - "_collapse_inner_safe"
Cohesion: 0.15
Nodes (12): CallGraphVisitor, _collapse_inner_safe(), _collect_node_names(), discover_source_files(), extract_uses_edges(), Any, Path, Run pyan's collapse_inner while skipping anonymous nodes pyan cannot parent-reso (+4 more)

### Community 72 - "render_call_graph_tree.py"
Cohesion: 0.24
Nodes (14): _flat_parameter_values(), load_config(), _load_parameter_values(), load_runner_parameters(), main(), _project_root_setting(), _project_table(), Path (+6 more)

### Community 73 - "._on_personal_supabase_activation_progress"
Cohesion: 0.14
Nodes (3): GitWorktreeTests, Path, GitWorktreeManager

### Community 74 - "ProjectWorktreeSettings"
Cohesion: 0.25
Nodes (8): ProjectConfigTests, load_project_worktree_settings(), ProjectWorktreeSettings, Path, Configuration supplied by a target project to prepare task worktrees., Install and shared-path settings from a target project's .daedalus file., Load optional worktree provisioning settings from a target repository., _string_array()

### Community 76 - "bootstrap_personal_supabase"
Cohesion: 0.08
Nodes (4): TuiAppTests, DaedalusVimTextArea, VimTextArea with multiline prompt behavior and system clipboard sync., VimTextArea

### Community 77 - "push_migrations"
Cohesion: 0.16
Nodes (11): SupabaseMigrationsTests, _migration_directory_name(), migrations_pending(), MigrationSyncResult, push_migrations(), Path, Orchestration-owned Supabase migration push for target project worktrees., Link the selected project when needed, then run non-interactive `db push`. (+3 more)

### Community 78 - "debug_log.py"
Cohesion: 0.23
Nodes (6): GraphifyTests, Path, Best-effort graph refresh owned by the local orchestration layer., Refresh the primary repository graph without affecting task success., update_repository(), Refresh graph metadata after promotion without blocking the task.

### Community 79 - "test_app.py"
Cohesion: 0.22
Nodes (14): CodexUsageTests, CodexUsageWindow, fetch_codex_usage(), _find_response(), _first_undimensioned_window(), parse_codex_usage(), _parse_reset(), _parse_window() (+6 more)

### Community 80 - "PersonalSupabaseConfirmationScreen"
Cohesion: 0.25
Nodes (8): personal_supabase_managed_env_keys(), project_personal_supabase_env_path(), Return every env key this feature may clean up (preferred + aliases)., Return env text without the configured Supabase assignments., Return the target project's ``.env`` path for client credentials., Append/update the managed project ``.env`` block, preserving other lines., _without_personal_supabase_env_values(), write_project_personal_supabase_environment()

### Community 81 - "select_roots"
Cohesion: 0.15
Nodes (12): EnvironmentTests, apply_process_supabase_overrides(), cursor_environment(), Path, Small, dependency-free environment-file loading for local CLI providers., Return file values with non-empty process ``SUPABASE_*`` overrides applied., Return ``.env`` beside the installed ``tui`` package root., Return the process environment plus local Cursor credentials.      Explicit proc (+4 more)

### Community 82 - "TranscriptLog"
Cohesion: 0.13
Nodes (8): CommandMenuScreen, PersonalSupabaseConfirmationScreen, PersonalSupabaseSetupWizardScreen, Offer low-frequency actions as discoverable buttons., Require an explicit confirmation before scaffolding/Activating a shared schema., Guide scaffold completion and manual project env setup before Activate., ActivationResult, Outcome of Phase 2 Activate (and optional Phase 1 scaffold).

### Community 84 - "RegistrationResult"
Cohesion: 0.07
Nodes (9): DaedalusTuiApp, Run the wide-layout measurement after the next screen refresh., Run a command after the command menu has been removed., Keep a task visible after user activity during this launch., Show animated activity or a concise terminal task outcome., Prefer mounted selector values so clarification refreshes keep choices., Replace question controls after Textual has completed child removal., Show either the full-size transcript or the full-size diagnostics log. (+1 more)

### Community 85 - "._focus_submitted_task"
Cohesion: 0.18
Nodes (14): Path, Unit tests for AST variable-lineage analysis., _sample_files(), CallGraphConfig, Analyze the project at *project_root* and write the HTML call tree., render_call_graph_tree(), analyze_sources(), module_fqn_from_path() (+6 more)

### Community 86 - "CandidateFeatureGroup"
Cohesion: 0.18
Nodes (6): Resize, Apply the viewport-aware layout whenever the terminal changes size., Toggle responsive classes and dimensions after a viewport change.          ``com, Measure wide controls after their current layout pass completes., Switch to compact mode when wide controls extend past their bars., Return whether wide-layout controls are clipped or too narrow.

### Community 87 - ".__init__"
Cohesion: 0.14
Nodes (17): ConfigTests, PersonalSupabaseExposureErrorScreen, Show the specific reason hosted schema exposure failed., CodingStatisticsSettings, CommandMenuSettings, LayoutSettings, load_codex_usage_settings(), load_coding_statistics_settings() (+9 more)

### Community 88 - "orchestrator.py"
Cohesion: 0.16
Nodes (15): PromptTests, Single-run local agent orchestration without daemon or database dependencies., build_migration_repair_prompt(), build_repair_prompt(), build_resolver_prompt(), build_sync_conflict_coding_prompt(), build_sync_conflict_plan_prompt(), build_task_prompt() (+7 more)

### Community 89 - "IntegrationCoordinator"
Cohesion: 0.14
Nodes (4): Paste Vim's register, falling back to the system clipboard., Paste before the cursor, including from the system clipboard., Return bar, underline, or block for the current Vim state., Return to Insert mode after programmatic prompt operations.

### Community 90 - "remove_personal_supabase"
Cohesion: 0.09
Nodes (29): main(), Child-process probe for Daedalus TUI Supabase env key presence.  Invoke as ``pyt, Remove values loaded for a subprocess from a user-facing diagnostic., redact_environment_values(), _direct_database_host_project_ref(), expose_registered_personal_supabase_schema(), _first_filled_env_value(), _key_or_aliases_label() (+21 more)

### Community 91 - "._apply_task_event"
Cohesion: 0.10
Nodes (11): RowSelected, Focus a task from the cross-project update inbox., Apply only the newest event per task to keep the UI responsive., Promote only events that need the user's attention in the inbox., Refresh the account usage line without blocking the TUI event loop., Render actionable history and tasks created during this session., Keep failures, active work, and all tasks submitted in this launch., Keep inbox cells within their fixed width with a visible ellipsis. (+3 more)

### Community 92 - "PersonalSupabaseSetupWizardScreen"
Cohesion: 0.33
Nodes (4): probe_project_personal_supabase_environment(), Return the TUI root ``.env`` that remains the credential source of truth., Check required TUI Supabase keys via a child process exit code.      The parent, tui_personal_supabase_env_path()

### Community 93 - "._refresh_push_button"
Cohesion: 0.12
Nodes (7): Scaffold files, then guide manual project env setup before Activate., Return labels and values for one compact settings category., Return provider metadata from the shared controls for a new task., Queue a coding task that writes and expands the requested topic file., Enable Push only when an origin remote and operating branch are available., Sync the Branch Select value for the active project with origin., Launch plan-mode recovery against the preserved Sync conflict worktree.

### Community 94 - "SyncMergeConflictError"
Cohesion: 0.08
Nodes (12): Key, Remove known credential values before diagnostics reach the UI or log., Add Vim-like navigation without changing TextArea insert behavior., Confirm, then scaffold (if needed) and Activate personal Supabase., Confirm, then remove local personal-Supabase artifacts for the project., Run scaffold+Activate in a background worker so the TUI stays responsive., Surface Sync conflict recovery progress in the status bar., Clear the selected task and unlock a fresh prompt editor. (+4 more)

### Community 95 - "render_html"
Cohesion: 0.15
Nodes (11): parent_child_score_map(), build_tree(), datetime, Build a call tree from *root* with cycle and depth limits., Render candidate features independently from the similarity panel., Render a self-contained HTML page for the call trees., _render_candidate_features_panel(), render_html() (+3 more)

### Community 96 - "PlanClarificationScreen"
Cohesion: 0.13
Nodes (4): ComposeResult, Select, PlanClarificationScreen, Collect a clarification about one plan question.

### Community 97 - "._on_personal_supabase_activation_progress"
Cohesion: 0.18
Nodes (7): PersonalSupabaseActivationProgressScreen, Finish a queued modal update only if its screen is still mounted., Show the durable activation phases while the worker runs., Whether the activation worker still owns this progress surface., Apply worker results that arrived while this modal was mounting., Freeze the progress display and allow the operator to close it., Render a completion state after all modal widgets are mounted.

### Community 98 - ".compose"
Cohesion: 0.18
Nodes (8): Log, Text, _literal_select_options(), Build Select prompts that Rich will not parse as markup., Synchronize registered projects; push migrations only when activated., Return only direct-child projects, or the empty-root fallback., is_direct_child_project(), Return whether ``path`` is an immediate child of ``launch_root``.

### Community 99 - "._render_line_strip"
Cohesion: 0.33
Nodes (4): Strip, Style, Render a line with the final-message color before selection styling., Render the native cursor without a background in visible modes.

### Community 100 - ".__init__"
Cohesion: 0.40
Nodes (3): EventCallback, IntegrationGate, Lock

### Community 101 - "._on_personal_supabase_activation_progress"
Cohesion: 0.40
Nodes (3): Forward worker phases to the modal and the main status line., Mark the current activation phase and retain a readable status line., Update mounted progress widgets for one worker phase.

## Knowledge Gaps
- **117 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+112 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `RegistrationResult` to `DaedalusVimTextArea`, `AgentRunner`, `GitWorktreeManager`, `._shutdown_coordinators`, `._set_status`, `calculate_token_usage`, `.emit`, `._rebuild_plan_questions`, `CandidateFeatureGroup`, `._persist_task`, `log_exception`, `GitWorktreeError`, `bootstrap_personal_supabase`, `test_app.py`, `TranscriptLog`, `CandidateFeatureGroup`, `.__init__`, `._apply_task_event`, `._refresh_push_button`, `SyncMergeConflictError`, `._on_personal_supabase_activation_progress`, `.compose`, `._on_personal_supabase_activation_progress`, `.action_view_topic`?**
  _High betweenness centrality (0.151) - this node is a cross-community bridge._
- **Why does `AgentRunner` connect `CandidateFeatureGroup` to `PlanClarificationScreen`, `._on_personal_supabase_activation_progress`, `AgentRunner`, `.__init__`, `._persist_task`, `._rebuild_plan_questions`, `TranscriptLog`, `RegistrationResult`, `._shutdown_coordinators`, `TranscriptLog`, `.__init__`, `orchestrator.py`, `._set_status`, `.provider_split`, `.on_mount`, `CodingStatisticsScreen`, `DescriptorEmbedder`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `TuiAppTests` connect `bootstrap_personal_supabase` to `PlanClarificationScreen`, `.emit`, `AgentRunner`, `._on_personal_supabase_activation_progress`, `GitWorktreeError`, `KeyboardShortcutsScreen`, `._rebuild_plan_questions`, `test_app.py`, `._rebuild_plan_questions`, `TranscriptLog`, `RegistrationResult`, `._shutdown_coordinators`, `.__init__`, `DescriptorEmbedder`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `CommandMenuScreen`) actually correct?**
  _`TuiAppTests` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 19 INFERRED edges - model-reasoned connections that need verification._