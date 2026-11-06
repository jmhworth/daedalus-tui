# Graph Report - daedalus-tui  (2026-11-06)

## Corpus Check
- 104 files · ~101,940 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1957 nodes · 5469 edges · 101 communities (83 shown, 18 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 653 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fdb85b2b`
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
- ._set_status
- environment.py
- CompactSettingsSelect
- Daedalus TUI Call Graph Visualization
- b.py
- .edit_paste_after
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
- .enter_insert_mode
- select_roots
- TranscriptLog
- IntegrationCoordinator
- RegistrationResult
- expose_personal_supabase_schema
- expose_personal_supabase_schema
- .__init__
- .__init__
- .implement_plan
- remove_personal_supabase
- ._apply_task_event
- PersonalSupabaseSetupWizardScreen
- ProjectInitializerScreen
- ._render_line_strip
- ._on_personal_supabase_activation_progress
- ._resize_workspace_section
- ._apply_measured_responsive_layout
- .edit_paste_after
- .edit_paste_before
- .enter_insert_mode

## God Nodes (most connected - your core abstractions)
1. `DaedalusTuiApp` - 191 edges
2. `TuiAppTests` - 128 edges
3. `TaskCoordinator` - 98 edges
4. `OrchestrationSettings` - 78 edges
5. `TaskRecord` - 76 edges
6. `AgentRunner` - 75 edges
7. `FakeCoordinator` - 70 edges
8. `DaedalusVimTextArea` - 70 edges
9. `WorktreeContext` - 67 edges
10. `GitWorktreeManager` - 67 edges

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

## Communities (101 total, 18 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.14
Nodes (32): CandidateFeatureGroup, A deterministic connected component of qualifying similarity relations., Return the stable identifier using the concise ``id`` spelling., score_band(), SimilarityResult, _canonical_tree_name(), _feature_ids_by_member(), _histogram_bars() (+24 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.08
Nodes (8): DaedalusTuiApp, Run the wide-layout measurement after the next screen refresh., Run a command after the command menu has been removed., Keep a task visible after user activity during this launch., Make a newly submitted task the visible task in every mode., Show animated activity or a concise terminal task outcome., Prefer mounted selector values so clarification refreshes keep choices., Use Textual's OSC 52 path and a native clipboard fallback.

### Community 2 - "AgentRunner"
Cohesion: 0.10
Nodes (10): TaskEventCallback, FakeOrchestrator, TaskCoordinatorTests, OrchestrationSettings, IntegrationCoordinator, Lock, Run ready integration operations one at a time in ready order., Submit independent prompts while sharing a serialized integration gate. (+2 more)

### Community 3 - "DaedalusTuiApp"
Cohesion: 0.06
Nodes (49): AnnAssign, Assign, AsyncFunctionDef, Attribute, AugAssign, Call, ClassDef, comprehension (+41 more)

### Community 4 - "app.py"
Cohesion: 0.13
Nodes (15): CallGraphTreeTests, candidate_feature_id(), group_candidate_features(), parent_child_score_map(), Return a stable ID derived solely from a group's sorted member symbols., Group symbols connected by inclusive-threshold relations.      Parent/child dire, Compatibility alias for callers that refer to group relations directly., ScoredRelation (+7 more)

### Community 5 - "TokenUsageStore"
Cohesion: 0.29
Nodes (6): Applying answers, Bridge Agent Profile, Build-loop tasking, cp_doc structure, Hard rules, Purpose

### Community 6 - "GitWorktreeManager"
Cohesion: 0.07
Nodes (23): Log, _file_name_and_line(), _looks_like_file(), Resize, Selectable transcript rendering with semantic assistant-message emphasis., Remove rendered errors while preserving the agent transcript., Append a numbered task turn with a selectable italic prompt., Render logical messages as wrapped, selectable Log lines. (+15 more)

### Community 7 - "Daedalus TUI Local Token Usage Memory"
Cohesion: 0.29
Nodes (6): Daedalus TUI Local Persistent Memory, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 8 - "update_repository"
Cohesion: 0.15
Nodes (16): PromptTests, build_migration_repair_prompt(), build_repair_prompt(), build_resolver_prompt(), build_sync_conflict_coding_prompt(), build_sync_conflict_plan_prompt(), build_task_prompt(), build_topic_population_prompt() (+8 more)

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
Cohesion: 0.09
Nodes (20): is_valid_plan_answer(), Validate agent option ids and the software-owned custom answer format., Path, Parse plan JSON from one turn without letting join separators break it., Remove the clean, read-only planning worktree after coding is queued., Persist task state, coalescing high-frequency streamed messages., Force-remove leftover sync worktrees from interrupted recoveries for ``branch``., Attach plan-mode recovery to a preserved Sync conflict worktree. (+12 more)

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
Cohesion: 0.18
Nodes (3): Resolve a Select value that is legal for the current question options., Finish Select setup without allowing a stale value to exit the TUI.          Pla, Replace question controls after Textual has completed child removal.

### Community 26 - ".provider_split"
Cohesion: 0.15
Nodes (13): EventCallback, IntegrationGate, AgentControl, Cooperative stop signals shared by a task and its active subprocess., AgentStopped, OrchestrationResult, Lock, Path (+5 more)

### Community 27 - ".on_mount"
Cohesion: 0.13
Nodes (14): Theme, CodingStatisticsScreen, _format_count(), _format_tokens(), Textual interface for concurrent local agent tasks., Show token or task usage history and derived coding statistics., Return Textual's event name for a user-facing shortcut label., _shortcut_binding_key() (+6 more)

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.18
Nodes (11): __getattr__(), Standalone Textual interface and local agent orchestration., _nonnegative_int(), _phase_for_status(), Concurrent task state and serialized local integration., Rehydrate this project's persisted tasks after a TUI restart., Recover review questions from the last persisted plan response., _snapshot_path() (+3 more)

### Community 30 - "calculate_token_usage"
Cohesion: 0.05
Nodes (33): TaskMemoryStoreTests, TokenUsageTests, Path, Remove one project's operating-branch override (absent = use default)., Return the remembered default topic for a project, if any., Remember one project's default topic without losing other entries., Remove one project's topic override (absent = no default topic)., Return persisted task snapshots keyed by their stable task ID. (+25 more)

### Community 31 - "PlanAnswerSelect"
Cohesion: 0.29
Nodes (6): Daedalus TUI Project Initialization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 32 - "discover_projects"
Cohesion: 0.25
Nodes (7): 4-Stage Development Lifecycle, Alignment, Debugging, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization, Topics (when tagged)

### Community 34 - "._render_line_strip"
Cohesion: 0.25
Nodes (7): 4-Stage Development Lifecycle, Alignment, Debugging, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization, Topics (when tagged)

### Community 35 - "agent_runner.py"
Cohesion: 0.15
Nodes (5): Path, Unit tests for AST variable-lineage analysis., _sample_files(), VariableLineageTests, write_variable_lineage_json()

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
Cohesion: 0.12
Nodes (23): build_implementation_prompt(), build_plan_clarification_prompt(), build_plan_followup_prompt(), custom_answer_text(), encode_custom_answer(), _escape_unescaped_controls_in_json_strings(), _loads_plan_json(), _parse_plan_payload() (+15 more)

### Community 42 - "debug_log.py"
Cohesion: 0.08
Nodes (26): Popen, Protocol, GraphifyTests, VerificationTests, Provider-specific subprocess execution with normalized agent messages., Path, Best-effort graph refresh owned by the local orchestration layer., Refresh the primary repository graph without affecting task success. (+18 more)

### Community 43 - "._rebuild_plan_questions"
Cohesion: 0.10
Nodes (9): FakeCoordinator, FakeRunner, settings(), LayoutSettings, Safety guard and dimensions used by the responsive TUI.      The wide controls a, PersonalSupabaseRemovalResult, Outcome of removing the local personal-Supabase integration artifacts., DaedalusProject (+1 more)

### Community 44 - "CandidateFeatureGroup"
Cohesion: 0.05
Nodes (26): OutputCallback, AgentRunnerTests, FakeProcess, FakeStream, InterruptibleProcess, EnvironmentTests, Thread, AgentLogEvent (+18 more)

### Community 45 - "KeyboardShortcutsScreen"
Cohesion: 0.20
Nodes (9): Constraints and Design Principles, Desired End State, Intended Import Workflow, Open Questions, Project Imports to the Daedalus Format, Scope and Durable Context, State Log, Topic Goal (+1 more)

### Community 46 - "orchestrator.py"
Cohesion: 0.29
Nodes (4): PlanTests, Cursor may include prose and omit redundant false confirmation., parse_plan_response(), Extract the agent's plan payload without exposing protocol text in the UI.

### Community 47 - "DaedalusTuiApp"
Cohesion: 0.16
Nodes (7): Key, Route visual-line mode and mirror new yanks to the host clipboard., Add Daedalus prompt commands that the dependency does not provide., Select the current line and enter Vim visual-line mode., Select every character in the lines between the start and cursor., Handle movement and operators while whole lines are selected., Expose operator-pending so the caret can become an underline.

### Community 48 - "._persist_task"
Cohesion: 0.31
Nodes (5): GitWorktreeError, push_branch(), RuntimeError, Push a local branch to ``remote``, setting upstream with ``-u`` when needed., Install project resources and link declared shared read-only paths.

### Community 49 - "._set_status"
Cohesion: 0.08
Nodes (13): Key, Remove known credential values before diagnostics reach the UI or log., Add Vim-like navigation without changing TextArea insert behavior., Confirm, then scaffold (if needed) and Activate personal Supabase., Confirm, then remove local personal-Supabase artifacts for the project., Scaffold files, then guide manual project env setup before Activate., Run scaffold+Activate in a background worker so the TUI stays responsive., Return provider metadata from the shared controls for a new task. (+5 more)

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

### Community 54 - ".edit_paste_after"
Cohesion: 0.07
Nodes (18): Resize, Apply the viewport-aware layout whenever the terminal changes size., Toggle responsive classes and dimensions after a viewport change.          ``com, Measure wide controls after their current layout pass completes., Open the selected project topic in a read-only modal., Apply provider-specific model and reasoning choices to all controls., Avoid posting Select.Changed events when the options are unchanged., Return labels and values for one compact settings category. (+10 more)

### Community 55 - "conftest.py"
Cohesion: 0.50
Nodes (3): pytest_configure(), Pytest hooks shared across the test suite., Install pyan3 when call-graph tests run in an environment missing it.

### Community 57 - "DescriptorEmbedder"
Cohesion: 0.08
Nodes (9): Changed, Pressed, Submitted, CreateTopicScreen, PersonalSupabaseConfirmationScreen, PersonalSupabaseRemovalConfirmationScreen, Collect the context needed to initialize and populate a topic file., Require an explicit confirmation before scaffolding/Activating a shared schema. (+1 more)

### Community 59 - "PlanClarification"
Cohesion: 0.07
Nodes (55): _allow_list_comment(), _commit_paths(), commit_personal_supabase_scaffold(), _ensure_env_example(), _ensure_supabase_scaffold(), _env_example_block(), _git_output(), _git_porcelain_paths() (+47 more)

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
Nodes (16): expose_personal_supabase_schema(), expose_registered_personal_supabase_schema(), is_personal_supabase_activated(), is_personal_supabase_registered(), load_personal_supabase_status(), PersonalSupabaseStatus, project_ref_from_supabase_url(), Expose an activated project's schema through hosted PostgREST on request. (+8 more)

### Community 69 - "log_exception"
Cohesion: 0.05
Nodes (27): AbstractEventLoop, BaseException, Exception, Stop agents before an explicit Textual exit begins., Persist Textual failures that would otherwise only flash on screen., Cover terminal and event-loop exits that bypass Textual unmount., Run before ThreadPoolExecutor's internal interpreter-exit join., Clean up if Textual's run loop returns without its unmount hook. (+19 more)

### Community 70 - "GitWorktreeError"
Cohesion: 0.18
Nodes (7): PersonalSupabaseActivationProgressScreen, Finish a queued modal update only if its screen is still mounted., Show the durable activation phases while the worker runs., Whether the activation worker still owns this progress surface., Apply worker results that arrived while this modal was mounting., Freeze the progress display and allow the operator to close it., Render a completion state after all modal widgets are mounted.

### Community 71 - "_collapse_inner_safe"
Cohesion: 0.17
Nodes (10): CallGraphVisitor, _collapse_inner_safe(), _collect_node_names(), discover_source_files(), extract_uses_edges(), Any, Path, Run pyan's collapse_inner while skipping anonymous nodes pyan cannot parent-reso (+2 more)

### Community 72 - "render_call_graph_tree.py"
Cohesion: 0.18
Nodes (17): _flat_parameter_values(), load_config(), _load_parameter_values(), load_runner_parameters(), main(), _project_root_setting(), _project_table(), Path (+9 more)

### Community 73 - "._on_personal_supabase_activation_progress"
Cohesion: 0.14
Nodes (3): GitWorktreeTests, Path, GitWorktreeManager

### Community 74 - "ProjectWorktreeSettings"
Cohesion: 0.25
Nodes (8): ProjectConfigTests, load_project_worktree_settings(), ProjectWorktreeSettings, Path, Configuration supplied by a target project to prepare task worktrees., Install and shared-path settings from a target project's .daedalus file., Load optional worktree provisioning settings from a target repository., _string_array()

### Community 76 - "bootstrap_personal_supabase"
Cohesion: 0.09
Nodes (4): TuiAppTests, DaedalusVimTextArea, VimTextArea with multiline prompt behavior and system clipboard sync., VimTextArea

### Community 77 - "push_migrations"
Cohesion: 0.16
Nodes (11): SupabaseMigrationsTests, _migration_directory_name(), migrations_pending(), MigrationSyncResult, push_migrations(), Path, Orchestration-owned Supabase migration push for target project worktrees., Link the selected project when needed, then run non-interactive `db push`. (+3 more)

### Community 78 - "debug_log.py"
Cohesion: 0.11
Nodes (23): TopicsTests, build_topic_instructions(), build_topic_template(), list_topic_slugs(), load_topic_settings(), load_topic_text(), Path, Topic file discovery, creation, loading, and prompt embedding. (+15 more)

### Community 80 - ".enter_insert_mode"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: what is the "ready" status, and is it possible for tasks to get stuck in it?, Source Nodes

### Community 81 - "select_roots"
Cohesion: 0.25
Nodes (9): Remove values loaded for a subprocess from a user-facing diagnostic., redact_environment_values(), _direct_database_host_project_ref(), preflight_personal_supabase(), PreflightResult, _probe_database_url(), Outcome of the access-method-aware live Supabase connectivity probe., Run access-method-aware live connectivity checks; never mutates schema. (+1 more)

### Community 82 - "TranscriptLog"
Cohesion: 0.08
Nodes (27): Binding, Mount, CommandMenuScreen, CompactSettingsSelect, KeyboardShortcutsScreen, _LegacyCompatibleBinding, PersonalSupabaseSetupWizardScreen, PlanAnswerSelect (+19 more)

### Community 83 - "IntegrationCoordinator"
Cohesion: 0.11
Nodes (5): Agent plan text must not be parsed as Textual/Rich markup., Follow-up questions must not crash when old option ids linger on widgets., Deferred Select init must not fatal-exit on a leftover option id., Clearing questions after confirmation must keep the TUI alive., PlanOption

### Community 84 - "RegistrationResult"
Cohesion: 0.11
Nodes (13): MouseDown, MouseUp, _load_saved_theme(), PersonalSupabaseExposureErrorScreen, Show the specific reason hosted schema exposure failed., Mouse-draggable boundary for one of the main workspace sections., Display a topic markdown file without allowing edits., ResizeHandle (+5 more)

### Community 85 - "expose_personal_supabase_schema"
Cohesion: 0.21
Nodes (11): ConfigTests, CodexUsageSettings, load_codex_usage_settings(), load_coding_statistics_settings(), load_orchestration_settings(), load_tui_settings(), ModelOption, _options() (+3 more)

### Community 87 - ".__init__"
Cohesion: 0.15
Nodes (17): CodexUsageTests, _format_codex_usage(), _format_codex_window(), CodexUsageSnapshot, CodexUsageWindow, fetch_codex_usage(), _find_response(), _first_undimensioned_window() (+9 more)

### Community 88 - ".__init__"
Cohesion: 0.21
Nodes (8): ProjectDiscoveryTests, Synchronize registered projects; push migrations only when activated., discover_projects(), is_direct_child_project(), Path, Discovery of Daedalus-supported repositories beneath a launch root., Return whether ``path`` is an immediate child of ``launch_root``., Find immediate child folders containing a direct ``feature_files`` child.      G

### Community 89 - ".implement_plan"
Cohesion: 0.24
Nodes (10): activate_personal_supabase(), bootstrap_personal_supabase(), Phase 1 (if needed) then Phase 2: Git commit, preflight, and migration push., Derive and validate the Postgres schema name from the project directory slug., Validate registration and the TUI-owned shared Supabase environment.      This h, Expose the target project's ref through the TUI-root CLI configuration., schema_from_project_root(), _short_error() (+2 more)

### Community 90 - "remove_personal_supabase"
Cohesion: 0.14
Nodes (15): main(), Child-process probe for Daedalus TUI Supabase env key presence.  Invoke as ``pyt, _ensure_profile_guidance(), _first_filled_env_value(), _key_or_aliases_label(), load_personal_supabase_settings(), personal_supabase_environment_settings(), profile_guidance_section() (+7 more)

### Community 91 - "._apply_task_event"
Cohesion: 0.08
Nodes (16): RowSelected, Select, Text, _literal_select_options(), Path, Build Select prompts that Rich will not parse as markup., Open a fresh project task or focus a task from the update inbox., Memory override for the project, else the parameter-file default. (+8 more)

### Community 92 - "PersonalSupabaseSetupWizardScreen"
Cohesion: 0.25
Nodes (6): load_project_personal_supabase_env_values(), probe_project_personal_supabase_environment(), Return the TUI root ``.env`` that remains the credential source of truth., Load canonical Supabase values from the Daedalus TUI ``.env``., Check required TUI Supabase keys via a child process exit code.      The parent, tui_personal_supabase_env_path()

### Community 94 - "._render_line_strip"
Cohesion: 0.33
Nodes (4): Strip, Style, Render a line with the final-message color before selection styling., Render the native cursor without a background in visible modes.

### Community 95 - "._on_personal_supabase_activation_progress"
Cohesion: 0.40
Nodes (3): Forward worker phases to the modal and the main status line., Mark the current activation phase and retain a readable status line., Update mounted progress widgets for one worker phase.

## Knowledge Gaps
- **120 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+115 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `DaedalusVimTextArea` to `AgentRunner`, `GitWorktreeManager`, `._shutdown_coordinators`, `._set_status`, `.on_mount`, `CodingStatisticsScreen`, `calculate_token_usage`, `._rebuild_plan_questions`, `CandidateFeatureGroup`, `._persist_task`, `._set_status`, `.edit_paste_after`, `log_exception`, `GitWorktreeError`, `bootstrap_personal_supabase`, `TranscriptLog`, `RegistrationResult`, `expose_personal_supabase_schema`, `.__init__`, `.__init__`, `._apply_task_event`, `._on_personal_supabase_activation_progress`, `._resize_workspace_section`, `._apply_measured_responsive_layout`?**
  _High betweenness centrality (0.133) - this node is a cross-community bridge._
- **Why does `AgentRunner` connect `CandidateFeatureGroup` to `DaedalusVimTextArea`, `AgentRunner`, `GitWorktreeError`, `debug_log.py`, `TranscriptLog`, `CodingStatisticsScreen`, `RegistrationResult`, `CodingStatisticsScreen`, `._shutdown_coordinators`, `DescriptorEmbedder`, `.provider_split`, `.on_mount`, `ProjectInitializerScreen`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `TaskCoordinator` connect `AgentRunner` to `DaedalusVimTextArea`, `GitWorktreeError`, `.on_mount`, `._on_personal_supabase_activation_progress`, `CandidateFeatureGroup`, `._persist_task`, `TranscriptLog`, `CodingStatisticsScreen`, `RegistrationResult`, `CodingStatisticsScreen`, `._shutdown_coordinators`, `DescriptorEmbedder`, `.provider_split`, `._apply_task_event`, `ProjectInitializerScreen`, `calculate_token_usage`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `CommandMenuScreen`) actually correct?**
  _`TuiAppTests` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 33 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 19 INFERRED edges - model-reasoned connections that need verification._