# Graph Report - daedalus-tui  (2026-09-26)

## Corpus Check
- 96 files · ~93,666 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1867 nodes · 5166 edges · 98 communities (87 shown, 11 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 595 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f19357ac`
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
- .on_button_pressed
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
- ._handle_visual_line_mode
- DaedalusTuiApp
- ._persist_task
- ._render_line_strip
- environment.py
- CompactSettingsSelect
- Daedalus TUI Call Graph Visualization
- b.py
- update_repository
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
- PersonalSupabaseActivationProgressScreen
- configure_debug_logging
- _collapse_inner_safe
- render_call_graph_tree.py
- ._on_personal_supabase_activation_progress
- ProjectWorktreeSettings
- CallGraphRunnerTests
- bootstrap_personal_supabase
- push_migrations
- load_project_worktree_settings
- push_branch
- .edit_paste_after
- .enter_insert_mode
- paste_from_system_clipboard
- .cursor_shape
- ._handle_visual_line_mode
- ._focus_submitted_task
- ._set_status
- ._switch_project
- Path
- PersonalSupabaseSetupWizardScreen
- remove_personal_supabase
- ._finish_personal_supabase_progress
- .__init__
- .on_mount
- ._run_clarification
- _literal_select_options
- .on_unmount
- .edit_paste_after

## God Nodes (most connected - your core abstractions)
1. `DaedalusTuiApp` - 182 edges
2. `TuiAppTests` - 125 edges
3. `TaskCoordinator` - 93 edges
4. `OrchestrationSettings` - 75 edges
5. `AgentRunner` - 72 edges
6. `TaskRecord` - 70 edges
7. `FakeCoordinator` - 67 edges
8. `GitWorktreeManager` - 66 edges
9. `DaedalusVimTextArea` - 66 edges
10. `WorktreeContext` - 65 edges

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

## Communities (98 total, 11 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.14
Nodes (31): CandidateFeatureGroup, A deterministic connected component of qualifying similarity relations., Return the stable identifier using the concise ``id`` spelling., score_band(), SimilarityResult, _canonical_tree_name(), _feature_ids_by_member(), _histogram_bars() (+23 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.06
Nodes (14): DaedalusTuiApp, Resize, Apply the viewport-aware layout whenever the terminal changes size., Toggle responsive classes and dimensions after a viewport change.          ``com, Measure wide controls after their current layout pass completes., Run the wide-layout measurement after the next screen refresh., Switch to compact mode when wide controls extend past their bars., Return whether wide-layout controls are clipped or too narrow. (+6 more)

### Community 2 - "AgentRunner"
Cohesion: 0.10
Nodes (7): FakeCoordinator, FakeRunner, settings(), PersonalSupabaseRemovalResult, Outcome of removing the local personal-Supabase integration artifacts., DaedalusProject, A repository recognized by the presence of a ``feature_files`` folder.

### Community 3 - "DaedalusTuiApp"
Cohesion: 0.06
Nodes (49): AnnAssign, Assign, AsyncFunctionDef, Attribute, AugAssign, Call, ClassDef, comprehension (+41 more)

### Community 4 - "app.py"
Cohesion: 0.19
Nodes (9): CallGraphTreeTests, candidate_feature_id(), group_candidate_features(), Return a stable ID derived solely from a group's sorted member symbols., Group symbols connected by inclusive-threshold relations.      Parent/child dire, Compatibility alias for callers that refer to group relations directly., ScoredRelation, Choose tree roots from configured entry points or orphan graph nodes. (+1 more)

### Community 5 - "TokenUsageStore"
Cohesion: 0.29
Nodes (6): Applying answers, Bridge Agent Profile, Build-loop tasking, cp_doc structure, Hard rules, Purpose

### Community 6 - "GitWorktreeManager"
Cohesion: 0.10
Nodes (14): Resize, Selectable transcript rendering with semantic assistant-message emphasis., Return the width available for transcript text inside the Log., Wrap one logical line at word boundaries when the width permits., A selectable log that can emphasize a task's final assistant message.      ``Log, Split an overlong word with visible hyphens at cell boundaries., Return the tone assigned to each rendered transcript line., Reflow stored messages when the output box changes width. (+6 more)

### Community 7 - "Daedalus TUI Local Token Usage Memory"
Cohesion: 0.29
Nodes (6): Daedalus TUI Local Persistent Memory, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 8 - "update_repository"
Cohesion: 0.14
Nodes (16): TopicsTests, build_topic_instructions(), build_topic_template(), embed_topic(), load_topic_settings(), Topic file discovery, creation, loading, and prompt embedding., Return missing required headings; empty list means structurally complete., Mode-specific rules for using an embedded topic file. (+8 more)

### Community 11 - "Key"
Cohesion: 0.14
Nodes (11): GitWorktreeManager, Path, Stage the current worktree contents for orchestration checks or commit., Remove graphify output changes from an agent worktree.          Graphify refresh, Keep a read-only planning pass from becoming an implementation change., Commit only the generated graph after a successful primary update., Return a directory whose HEAD matches the target branch tip.          When the r, Remove a short-lived primary checkout created for post-promotion work. (+3 more)

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
Cohesion: 0.17
Nodes (11): AgentControl, Cooperative stop signals shared by a task and its active subprocess., AgentStopped, OrchestrationResult, Path, RuntimeError, Plan or resolve Sync merge conflicts in a preserved sync worktree., Load a repository-owned profile immediately before building a prompt. (+3 more)

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
Cohesion: 0.05
Nodes (29): OutputCallback, AgentRunnerTests, FakeProcess, FakeStream, InterruptibleProcess, EnvironmentTests, Thread, AgentLogEvent (+21 more)

### Community 26 - ".provider_split"
Cohesion: 0.10
Nodes (17): Path, Parse plan JSON from one turn without letting join separators break it., Remove the clean, read-only planning worktree after coding is queued., Persist task state, coalescing high-frequency streamed messages., Force-remove leftover sync worktrees from interrupted recoveries for ``branch``., Attach plan-mode recovery to a preserved Sync conflict worktree., Send selected plan answers back to the planning agent for confirmation., Ask a side-channel clarification about one plan question without plan follow-up. (+9 more)

### Community 27 - ".on_mount"
Cohesion: 0.13
Nodes (18): Popen, Protocol, VerificationTests, Small local JSON stores for persistent task history., discover_commands(), format_process_result(), package_has_test_script(), CompletedProcess (+10 more)

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.29
Nodes (5): GraphifyTests, Path, Best-effort graph refresh owned by the local orchestration layer., Refresh the primary repository graph without affecting task success., update_repository()

### Community 30 - "calculate_token_usage"
Cohesion: 0.15
Nodes (11): Path, Remove one project's operating-branch override (absent = use default)., Return the remembered default topic for a project, if any., Remember one project's default topic without losing other entries., Remove one project's topic override (absent = no default topic)., Upsert a task snapshot keyed by the task worktree's directory name., Return the remembered project path, if the memory contains one., Set the single project marker without losing task records. (+3 more)

### Community 31 - "PlanAnswerSelect"
Cohesion: 0.29
Nodes (6): Daedalus TUI Project Initialization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 32 - "discover_projects"
Cohesion: 0.25
Nodes (7): 4-Stage Development Lifecycle, Alignment, Debugging, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization, Topics (when tagged)

### Community 33 - ".on_button_pressed"
Cohesion: 0.14
Nodes (10): Log, ProjectDiscoveryTests, Synchronize registered projects; push migrations only when activated., Return only direct-child projects, or the empty-root fallback., discover_projects(), is_direct_child_project(), Path, Discovery of Daedalus-supported repositories beneath a launch root. (+2 more)

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
Cohesion: 0.15
Nodes (19): abort_sync_merge(), _create_isolated_sync_worktree(), _delete_branch_if_present(), finalize_sync_merge(), _force_remove_worktree(), _is_ancestor(), list_unmerged_paths(), pull_branch() (+11 more)

### Community 39 - "Daedalus Project Instructions"
Cohesion: 0.33
Nodes (5): Daedalus Project Instructions, graphify, Shared personal Supabase, Task mode, Topics

### Community 41 - "KeyboardShortcutsScreen"
Cohesion: 0.12
Nodes (31): _allow_list_comment(), _commit_paths(), commit_personal_supabase_scaffold(), _ensure_env_example(), _ensure_local_api_schema(), _ensure_profile_guidance(), _ensure_supabase_scaffold(), _env_example_block() (+23 more)

### Community 42 - "debug_log.py"
Cohesion: 0.17
Nodes (14): PromptTests, build_migration_repair_prompt(), build_repair_prompt(), build_resolver_prompt(), build_sync_conflict_coding_prompt(), build_sync_conflict_plan_prompt(), build_task_prompt(), build_topic_population_prompt() (+6 more)

### Community 43 - "._rebuild_plan_questions"
Cohesion: 0.12
Nodes (13): Path, Unit tests for AST variable-lineage analysis., _sample_files(), parent_child_score_map(), build_tree(), datetime, Build a call tree from *root* with cycle and depth limits., Render a self-contained HTML page for the call trees. (+5 more)

### Community 44 - "CandidateFeatureGroup"
Cohesion: 0.07
Nodes (14): Key, Remove known credential values before diagnostics reach the UI or log., Add Vim-like navigation without changing TextArea insert behavior., Confirm, then scaffold (if needed) and Activate personal Supabase., Confirm, then remove local personal-Supabase artifacts for the project., Scaffold files, then guide manual project env setup before Activate., Run scaffold+Activate in a background worker so the TUI stays responsive., Return provider metadata from the shared controls for a new task. (+6 more)

### Community 45 - "KeyboardShortcutsScreen"
Cohesion: 0.20
Nodes (9): Constraints and Design Principles, Desired End State, Intended Import Workflow, Open Questions, Project Imports to the Daedalus Format, Scope and Durable Context, State Log, Topic Goal (+1 more)

### Community 46 - "._handle_visual_line_mode"
Cohesion: 0.20
Nodes (13): ConfigTests, LayoutSettings, load_codex_usage_settings(), load_coding_statistics_settings(), load_command_menu_settings(), load_orchestration_settings(), load_tui_settings(), ModelOption (+5 more)

### Community 47 - "DaedalusTuiApp"
Cohesion: 0.14
Nodes (8): Key, Keep Enter as a newline; Ctrl+Enter remains the app submit key., Route visual-line mode and mirror new yanks to the host clipboard., Add Daedalus prompt commands that the dependency does not provide., Select the current line and enter Vim visual-line mode., Select every character in the lines between the start and cursor., Handle movement and operators while whole lines are selected., Expose operator-pending so the caret can become an underline.

### Community 48 - "._persist_task"
Cohesion: 0.15
Nodes (6): FakeOrchestrator, TaskCoordinatorTests, OrchestrationSettings, Submit independent prompts while sharing a serialized integration gate., Return whether a Sync conflict recovery is still in flight for this project., TaskCoordinator

### Community 49 - "._render_line_strip"
Cohesion: 0.10
Nodes (12): Open the selected project topic in a read-only modal., Apply provider-specific model and reasoning choices to all controls., Return labels and values for one compact settings category., Read the current value from the same selectors used for submission., Populate the compact value Select while retaining its active category., Apply a compact value through the existing wide-control state., Remember the selected topic as the default for the active project., Enable Push only when an origin remote and operating branch are available. (+4 more)

### Community 50 - "environment.py"
Cohesion: 0.29
Nodes (6): Daedalus TUI Command Menu, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 51 - "CompactSettingsSelect"
Cohesion: 0.21
Nodes (6): PersonalSupabaseTests, Path, is_personal_supabase_activated(), True when the project is registered and activated for ``schema`` (or any)., Scaffold supabase files, env placeholders, profiles, and a ``.daedalus`` marker., register_personal_supabase()

### Community 52 - "Daedalus TUI Call Graph Visualization"
Cohesion: 0.29
Nodes (6): Daedalus TUI Call Graph Visualization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 53 - "b.py"
Cohesion: 0.10
Nodes (21): alpha(), Entry helper that fans out into order and UI branches., beta(), Continue the sample call chain toward gamma., gamma(), Leaf helper in the sample call chain., make_runner(), create_order() (+13 more)

### Community 54 - "update_repository"
Cohesion: 0.16
Nodes (14): TokenUsageTests, calculate_token_usage(), merge_usage_entries(), _parse_timestamp(), datetime, Token usage records and derived coding statistics., The token usage attributed to one submitted task., Convert persisted task snapshots into usage records. (+6 more)

### Community 55 - "conftest.py"
Cohesion: 0.50
Nodes (3): pytest_configure(), Pytest hooks shared across the test suite., Install pyan3 when call-graph tests run in an environment missing it.

### Community 57 - "DescriptorEmbedder"
Cohesion: 0.07
Nodes (36): Agent plan text must not be parsed as Textual/Rich markup., Follow-up questions must not crash when old option ids linger on widgets., Deferred Select init must not fatal-exit on a leftover option id., Clearing questions after confirmation must keep the TUI alive., PlanTests, Cursor may include prose and omit redundant false confirmation., Resolve a Select value that is legal for the current question options., build_implementation_prompt() (+28 more)

### Community 59 - "PlanClarification"
Cohesion: 0.08
Nodes (23): Binding, ComposeResult, CommandMenuScreen, KeyboardShortcutsScreen, _LegacyCompatibleBinding, PersonalSupabaseSetupWizardScreen, PlanClarificationScreen, Display a topic markdown file without allowing edits. (+15 more)

### Community 60 - "trading.py"
Cohesion: 0.32
Nodes (5): calculate(), execute_trade(), Portfolio, Assignment lineage, augassign, attribute mutate, and unique call mapping., run_pipeline()

### Community 61 - "CodingStatisticsScreen"
Cohesion: 0.23
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
Cohesion: 0.33
Nodes (6): is_personal_supabase_registered(), load_personal_supabase_status(), PersonalSupabaseStatus, Registration / activation marker loaded from a target project's ``.daedalus``., Return the ``[personal_supabase]`` marker, or an unregistered default., True when the project is marked registered for ``schema`` (or any schema if omit

### Community 69 - "PersonalSupabaseActivationProgressScreen"
Cohesion: 0.17
Nodes (4): TaskMemoryStoreTests, Return persisted task snapshots keyed by their stable task ID., Persist task history, last project, and per-project task defaults., TaskMemoryStore

### Community 70 - "configure_debug_logging"
Cohesion: 0.16
Nodes (4): Path, Memory override for the project, else the parameter-file default., Update the project's coordinator so later submits use ``branch``., Refresh Branch Select options for the active project and sync coordinator.

### Community 71 - "_collapse_inner_safe"
Cohesion: 0.17
Nodes (10): CallGraphVisitor, _collapse_inner_safe(), _collect_node_names(), discover_source_files(), extract_uses_edges(), Any, Path, Run pyan's collapse_inner while skipping anonymous nodes pyan cannot parent-reso (+2 more)

### Community 72 - "render_call_graph_tree.py"
Cohesion: 0.18
Nodes (17): _flat_parameter_values(), load_config(), _load_parameter_values(), load_runner_parameters(), main(), _project_root_setting(), _project_table(), Path (+9 more)

### Community 73 - "._on_personal_supabase_activation_progress"
Cohesion: 0.12
Nodes (4): GitWorktreeTests, Path, list_local_branches(), Return local branch names under ``refs/heads`` without checking anything out.

### Community 74 - "ProjectWorktreeSettings"
Cohesion: 0.25
Nodes (8): ProjectConfigTests, load_project_worktree_settings(), ProjectWorktreeSettings, Path, Configuration supplied by a target project to prepare task worktrees., Install and shared-path settings from a target project's .daedalus file., Load optional worktree provisioning settings from a target repository., _string_array()

### Community 76 - "bootstrap_personal_supabase"
Cohesion: 0.08
Nodes (4): TuiAppTests, DaedalusVimTextArea, VimTextArea with multiline prompt behavior and system clipboard sync., VimTextArea

### Community 77 - "push_migrations"
Cohesion: 0.21
Nodes (8): SupabaseMigrationsTests, Single-run local agent orchestration without daemon or database dependencies., migrations_pending(), push_migrations(), Path, Orchestration-owned Supabase migration push for target project worktrees., Return True when the worktree differs from base under supabase/migrations/., Run non-interactive `supabase db push --yes` in the target worktree.

### Community 78 - "load_project_worktree_settings"
Cohesion: 0.18
Nodes (7): Mount, Select, CompactSettingsSelect, PlanAnswerSelect, Avoid posting Select.Changed events when the options are unchanged., Initialize dynamic plan selectors after their nested children mount., Keep only the latest value-change event for rebuilt compact controls.

### Community 79 - "push_branch"
Cohesion: 0.20
Nodes (3): Return bar, underline, or block for the current Vim state., Return to Insert mode after programmatic prompt operations., Move to the end of the current word, or the next word when needed.

### Community 80 - ".edit_paste_after"
Cohesion: 0.10
Nodes (33): main(), Child-process probe for project-local Supabase env key presence.  Invoke as ``py, activate_personal_supabase(), bootstrap_personal_supabase(), _direct_database_host_project_ref(), _first_filled_env_value(), _key_or_aliases_label(), load_personal_supabase_settings() (+25 more)

### Community 81 - ".enter_insert_mode"
Cohesion: 0.10
Nodes (15): TaskEventCallback, __getattr__(), Standalone Textual interface and local agent orchestration., IntegrationCoordinator, _nonnegative_int(), _phase_for_status(), Lock, Concurrent task state and serialized local integration. (+7 more)

### Community 82 - "paste_from_system_clipboard"
Cohesion: 0.26
Nodes (5): CodingStatisticsScreen, _format_count(), _format_tokens(), Show token or task usage history and derived coding statistics., CodingStatisticsSettings

### Community 83 - ".cursor_shape"
Cohesion: 0.22
Nodes (14): CodexUsageTests, CodexUsageWindow, fetch_codex_usage(), _find_response(), _first_undimensioned_window(), parse_codex_usage(), _parse_reset(), _parse_window() (+6 more)

### Community 84 - "._handle_visual_line_mode"
Cohesion: 0.08
Nodes (9): Changed, Pressed, Submitted, CreateTopicScreen, PersonalSupabaseConfirmationScreen, PersonalSupabaseRemovalConfirmationScreen, Require an explicit confirmation before scaffolding/Activating a shared schema., Require an exact project-name confirmation before local cleanup. (+1 more)

### Community 85 - "._focus_submitted_task"
Cohesion: 0.10
Nodes (11): RowSelected, Focus a task from the cross-project update inbox., Apply only the newest event per task to keep the UI responsive., Promote only events that need the user's attention in the inbox., Refresh the account usage line without blocking the TUI event loop., Render actionable history and tasks created during this session., Keep failures, active work, and all tasks submitted in this launch., Keep inbox cells within their fixed width with a visible ellipsis. (+3 more)

### Community 86 - "._set_status"
Cohesion: 0.21
Nodes (8): GitWorktreeError, push_branch(), CompletedProcess, RuntimeError, Push a local branch to ``remote``, setting upstream with ``-u`` when needed., Install project resources and link declared shared read-only paths., Return whether ``remote`` is configured for ``repository``., remote_exists()

### Community 87 - "._switch_project"
Cohesion: 0.40
Nodes (3): Forward worker phases to the modal and the main status line., Mark the current activation phase and retain a readable status line., Update mounted progress widgets for one worker phase.

### Community 88 - "Path"
Cohesion: 0.27
Nodes (9): list_topic_slugs(), load_topic_text(), Path, Return sorted topic filename stems from ``topic_files/*.md``., Resolve ``topic_files/{slug}.md`` under the project checkout., Load topic markdown for ``slug``, or ``None`` when missing/unreadable., Build Select options: ``(None)`` plus each discovered topic slug., topic_path() (+1 more)

### Community 89 - "PersonalSupabaseSetupWizardScreen"
Cohesion: 0.25
Nodes (6): load_project_personal_supabase_env_values(), probe_project_personal_supabase_environment(), project_personal_supabase_env_path(), Return the project-local ``.env`` path operators must edit., Load values from the project ``.env`` only (no process overrides).      Wizard C, Check required project Supabase keys via a child process exit code.      The par

### Community 90 - "remove_personal_supabase"
Cohesion: 0.14
Nodes (18): personal_supabase_managed_env_keys(), Return every env key this feature may clean up (preferred + aliases)., Remove local personal-Supabase artifacts without touching remote state.      The, Remove only the personal-Supabase table from a project marker., Remove one already-resolved file, symlink, or directory., Remove the generated shared-Supabase block from ``.env.example``., Remove synchronized Supabase assignments while preserving other env values., Return env text without the configured Supabase assignments. (+10 more)

### Community 91 - "._finish_personal_supabase_progress"
Cohesion: 0.19
Nodes (7): PersonalSupabaseActivationProgressScreen, Finish a queued modal update only if its screen is still mounted., Show the durable activation phases while the worker runs., Whether the activation worker still owns this progress surface., Apply worker results that arrived while this modal was mounting., Freeze the progress display and allow the operator to close it., Render a completion state after all modal widgets are mounted.

### Community 92 - ".__init__"
Cohesion: 0.40
Nodes (3): EventCallback, IntegrationGate, Lock

### Community 93 - ".on_mount"
Cohesion: 0.06
Nodes (24): AbstractEventLoop, BaseException, Exception, Pause active agents before ThreadPoolExecutor joins its workers.      CPython ex, Stop agents before an explicit Textual exit begins., Persist Textual failures that would otherwise only flash on screen., Cover terminal and event-loop exits that bypass Textual unmount., Run before ThreadPoolExecutor's internal interpreter-exit join. (+16 more)

### Community 95 - "_literal_select_options"
Cohesion: 0.22
Nodes (7): Strip, Style, Text, _literal_select_options(), Build Select prompts that Rich will not parse as markup., Render a line with the final-message color before selection styling., Render the native cursor without a background in visible modes.

### Community 96 - ".on_unmount"
Cohesion: 0.33
Nodes (4): Aggregates used by the coding statistics screen., Return provider and absolute usage pairs for the selected unit., Return per-provider average usage per prompt for the selected unit., TokenUsageStats

### Community 101 - ".edit_paste_after"
Cohesion: 0.14
Nodes (14): _format_codex_usage(), _format_codex_window(), Textual interface for concurrent local agent tasks., Return Textual's event name for a user-facing shortcut label., _shortcut_binding_key(), copy_to_system_clipboard(), paste_from_system_clipboard(), System clipboard helpers for terminals without OSC 52 support. (+6 more)

## Knowledge Gaps
- **117 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+112 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `DaedalusVimTextArea` to `AgentRunner`, `GitWorktreeManager`, `._set_status`, `.provider_split`, `.on_button_pressed`, `CandidateFeatureGroup`, `._handle_visual_line_mode`, `._persist_task`, `._render_line_strip`, `update_repository`, `DescriptorEmbedder`, `PlanClarification`, `PersonalSupabaseActivationProgressScreen`, `configure_debug_logging`, `bootstrap_personal_supabase`, `load_project_worktree_settings`, `.enter_insert_mode`, `paste_from_system_clipboard`, `.cursor_shape`, `._focus_submitted_task`, `._set_status`, `._switch_project`, `._finish_personal_supabase_progress`, `.on_mount`, `.edit_paste_after`?**
  _High betweenness centrality (0.129) - this node is a cross-community bridge._
- **Why does `AgentRunner` connect `._set_status` to `DaedalusVimTextArea`, `.edit_paste_after`, `configure_debug_logging`, `._finish_personal_supabase_progress`, `push_migrations`, `load_project_worktree_settings`, `._persist_task`, `.enter_insert_mode`, `paste_from_system_clipboard`, `._handle_visual_line_mode`, `._shutdown_coordinators`, `.provider_split`, `PlanClarification`, `.__init__`, `CodingStatisticsScreen`, `._run_clarification`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Why does `TuiAppTests` connect `bootstrap_personal_supabase` to `DaedalusVimTextArea`, `AgentRunner`, `.edit_paste_after`, `._finish_personal_supabase_progress`, `._handle_visual_line_mode`, `load_project_worktree_settings`, `paste_from_system_clipboard`, `.cursor_shape`, `._handle_visual_line_mode`, `._set_status`, `DescriptorEmbedder`, `.provider_split`, `PlanClarification`, `._run_clarification`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `CommandMenuScreen`) actually correct?**
  _`TuiAppTests` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 19 INFERRED edges - model-reasoned connections that need verification._