# Graph Report - daedalus-tui  (2026-09-19)

## Corpus Check
- 93 files · ~83,801 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1738 nodes · 4686 edges · 95 communities (78 shown, 17 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 526 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `46c40e07`
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
- WorktreeContext
- _collapse_inner_safe
- render_call_graph_tree.py
- ._on_personal_supabase_activation_progress
- PersonalSupabaseConfirmationScreen
- CallGraphRunnerTests
- bootstrap_personal_supabase
- verification.py
- load_project_worktree_settings
- ._set_status
- .edit_paste_after
- .enter_insert_mode
- GitWorktreeManager
- ._set_error
- git_worktree.py
- ProjectWorktreeSettings
- debug_log.py
- GitWorktreeError
- ProjectInitializerScreen
- PersonalSupabaseSetupWizardScreen
- PlanClarificationScreen
- ._apply_measured_responsive_layout
- ._on_topic_created
- .cursor_shape
- .edit_paste_before

## God Nodes (most connected - your core abstractions)
1. `DaedalusTuiApp` - 175 edges
2. `TuiAppTests` - 118 edges
3. `TaskCoordinator` - 82 edges
4. `OrchestrationSettings` - 67 edges
5. `DaedalusVimTextArea` - 66 edges
6. `AgentRunner` - 65 edges
7. `TaskRecord` - 65 edges
8. `GitWorktreeManager` - 64 edges
9. `FakeCoordinator` - 62 edges
10. `TaskMemoryStore` - 62 edges

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

## Communities (95 total, 17 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.18
Nodes (25): score_band(), _canonical_tree_name(), _collapse_inner_safe(), _collect_node_names(), _histogram_bars(), _layout_extent_y(), _layout_subtree(), _layout_trees() (+17 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.10
Nodes (16): Binding, Mount, Select, CompactSettingsSelect, _LegacyCompatibleBinding, PlanAnswerSelect, Expose the former four-item binding shape to local UI tests.      Textual 8 acce, Initialize dynamic plan selectors after their nested children mount. (+8 more)

### Community 2 - "AgentRunner"
Cohesion: 0.08
Nodes (15): Resize, Apply the viewport-aware layout whenever the terminal changes size., Toggle responsive classes and dimensions after a viewport change.          ``com, Measure wide controls after their current layout pass completes., Open the selected project topic in a read-only modal., Apply provider-specific model and reasoning choices to all controls., Avoid posting Select.Changed events when the options are unchanged., Return labels and values for one compact settings category. (+7 more)

### Community 3 - "DaedalusTuiApp"
Cohesion: 0.07
Nodes (43): AnnAssign, Assign, AsyncFunctionDef, Attribute, AugAssign, Call, ClassDef, comprehension (+35 more)

### Community 4 - "app.py"
Cohesion: 0.10
Nodes (23): Path, Unit tests for AST variable-lineage analysis., _sample_files(), build_tree(), CallGraphConfig, datetime, Build a call tree from *root* with cycle and depth limits., Render candidate features independently from the similarity panel. (+15 more)

### Community 5 - "TokenUsageStore"
Cohesion: 0.29
Nodes (6): Applying answers, Bridge Agent Profile, Build-loop tasking, cp_doc structure, Hard rules, Purpose

### Community 6 - "GitWorktreeManager"
Cohesion: 0.07
Nodes (22): Log, Strip, Style, Text, _literal_select_options(), Build Select prompts that Rich will not parse as markup., Resize, Selectable transcript rendering with semantic assistant-message emphasis. (+14 more)

### Community 7 - "Daedalus TUI Local Token Usage Memory"
Cohesion: 0.29
Nodes (6): Daedalus TUI Local Persistent Memory, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 8 - "update_repository"
Cohesion: 0.07
Nodes (35): PromptTests, TopicsTests, build_migration_repair_prompt(), build_repair_prompt(), build_resolver_prompt(), build_task_prompt(), build_topic_population_prompt(), _embedded_profile() (+27 more)

### Community 11 - "Key"
Cohesion: 0.15
Nodes (10): Path, Send selected plan answers back to the planning agent for confirmation., Ask a side-channel clarification about one plan question without plan follow-up., Run another planning pass while keeping the task in questioning., Promote a reviewed plan into the normal coding and verification route., Retry a failed agent request after connectivity or service recovery., Run an ask-mode clarification that does not mutate plan conversation state., Construct an orchestrator with the project environment when configured. (+2 more)

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
Cohesion: 0.08
Nodes (15): ComposeResult, CommandMenuScreen, CreateTopicScreen, KeyboardShortcutsScreen, PersonalSupabaseSetupWizardScreen, Display a topic markdown file without allowing edits., Modal reference for the app and prompt editor keyboard shortcuts., Offer low-frequency actions as discoverable buttons. (+7 more)

### Community 22 - "._set_status"
Cohesion: 0.10
Nodes (12): RowSelected, Path, Focus a task from the cross-project update inbox., Memory override for the project, else the parameter-file default., Update the project's coordinator so later submits use ``branch``., Refresh Branch Select options for the active project and sync coordinator., Return only direct-child projects, or the empty-root fallback., Render actionable history and tasks created during this session. (+4 more)

### Community 23 - "update_repository"
Cohesion: 0.10
Nodes (31): build_symbol_contexts(), _descriptor_hash(), DescriptorEmbedder, _doc_for_definition(), extract_docs_for_symbols(), format_descriptor(), _format_name_list(), invert_edges() (+23 more)

### Community 24 - "Daedalus TUI Coding Statistics"
Cohesion: 0.29
Nodes (6): Daedalus TUI Coding Statistics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 25 - "._set_status"
Cohesion: 0.08
Nodes (13): OutputCallback, AgentRunnerTests, FakeProcess, FakeStream, InterruptibleProcess, Thread, AgentLogEvent, AgentRequest (+5 more)

### Community 26 - ".provider_split"
Cohesion: 0.10
Nodes (30): PlanTests, Resolve a Select value that is legal for the current question options., build_implementation_prompt(), build_plan_clarification_prompt(), build_plan_followup_prompt(), custom_answer_text(), encode_custom_answer(), is_valid_plan_answer() (+22 more)

### Community 27 - ".on_mount"
Cohesion: 0.16
Nodes (11): EventCallback, IntegrationGate, AgentControl, Cooperative stop signals shared by a task and its active subprocess., AgentStopped, Lock, Path, RuntimeError (+3 more)

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.08
Nodes (17): AbstractEventLoop, BaseException, Exception, Pause active agents before ThreadPoolExecutor joins its workers.      CPython ex, Stop agents before an explicit Textual exit begins., Persist Textual failures that would otherwise only flash on screen., Cover terminal and event-loop exits that bypass Textual unmount., Run before ThreadPoolExecutor's internal interpreter-exit join. (+9 more)

### Community 30 - "calculate_token_usage"
Cohesion: 0.05
Nodes (34): TaskMemoryStoreTests, TokenUsageTests, Path, Small local JSON stores for persistent task history., Remove one project's operating-branch override (absent = use default)., Return the remembered default topic for a project, if any., Remember one project's default topic without losing other entries., Remove one project's topic override (absent = no default topic). (+26 more)

### Community 31 - "PlanAnswerSelect"
Cohesion: 0.29
Nodes (6): Daedalus TUI Project Initialization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 32 - "discover_projects"
Cohesion: 0.25
Nodes (7): 4-Stage Development Lifecycle, Alignment, Debugging, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization, Topics (when tagged)

### Community 33 - ".on_button_pressed"
Cohesion: 0.26
Nodes (7): ProjectDiscoveryTests, discover_projects(), is_direct_child_project(), Path, Discovery of Daedalus-supported repositories beneath a launch root., Return whether ``path`` is an immediate child of ``launch_root``., Find immediate child folders containing a direct ``feature_files`` child.      G

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
Cohesion: 0.20
Nodes (10): EnvironmentTests, apply_process_supabase_overrides(), cursor_environment(), Path, Small, dependency-free environment-file loading for local CLI providers., Return the process environment plus local Cursor credentials.      Explicit proc, Return file values with non-empty process ``SUPABASE_*`` overrides applied., Remove values loaded for a subprocess from a user-facing diagnostic. (+2 more)

### Community 39 - "Daedalus Project Instructions"
Cohesion: 0.33
Nodes (5): Daedalus Project Instructions, graphify, Shared personal Supabase, Task mode, Topics

### Community 41 - "KeyboardShortcutsScreen"
Cohesion: 0.12
Nodes (36): activate_personal_supabase(), _allow_list_comment(), _commit_paths(), commit_personal_supabase_scaffold(), _ensure_env_example(), _ensure_supabase_scaffold(), _env_example_block(), _git_output() (+28 more)

### Community 42 - "debug_log.py"
Cohesion: 0.25
Nodes (6): CandidateFeatureGroup, A deterministic connected component of qualifying similarity relations., Return the stable identifier using the concise ``id`` spelling., Compatibility alias for callers that refer to group relations directly., _feature_ids_by_member(), Map each grouped symbol to its stable candidate-feature ID.

### Community 43 - "._rebuild_plan_questions"
Cohesion: 0.15
Nodes (12): CallGraphTreeTests, candidate_feature_id(), group_candidate_features(), Lowercase and split identifiers on `.` / `_` while keeping word tokens., Return a stable ID derived solely from a group's sorted member symbols., Group symbols connected by inclusive-threshold relations.      Parent/child dire, ScoredRelation, SimilarityResult (+4 more)

### Community 44 - "CandidateFeatureGroup"
Cohesion: 0.09
Nodes (7): DaedalusTuiApp, Run the wide-layout measurement after the next screen refresh., Run a command after the command menu has been removed., Keep a task visible after user activity during this launch., Prefer mounted selector values so clarification refreshes keep choices., Show either the full-size transcript or the full-size diagnostics log., Use Textual's OSC 52 path and a native clipboard fallback.

### Community 45 - "KeyboardShortcutsScreen"
Cohesion: 0.20
Nodes (9): Constraints and Design Principles, Desired End State, Intended Import Workflow, Open Questions, Project Imports to the Daedalus Format, Scope and Durable Context, State Log, Topic Goal (+1 more)

### Community 46 - "._handle_visual_line_mode"
Cohesion: 0.14
Nodes (8): Key, Keep Enter as a newline; Ctrl+Enter remains the app submit key., Route visual-line mode and mirror new yanks to the host clipboard., Add Daedalus prompt commands that the dependency does not provide., Select the current line and enter Vim visual-line mode., Select every character in the lines between the start and cursor., Handle movement and operators while whole lines are selected., Expose operator-pending so the caret can become an underline.

### Community 47 - "DaedalusTuiApp"
Cohesion: 0.20
Nodes (3): Paste Vim's register, falling back to the system clipboard., Return to Insert mode after programmatic prompt operations., Move to the end of the current word, or the next word when needed.

### Community 48 - "._persist_task"
Cohesion: 0.12
Nodes (10): TaskEventCallback, FakeOrchestrator, TaskCoordinatorTests, OrchestrationResult, OrchestrationSettings, IntegrationCoordinator, Lock, Run ready integration operations one at a time in ready order. (+2 more)

### Community 49 - "._render_line_strip"
Cohesion: 0.11
Nodes (5): Agent plan text must not be parsed as Textual/Rich markup., Follow-up questions must not crash when old option ids linger on widgets., Deferred Select init must not fatal-exit on a leftover option id., Clearing questions after confirmation must keep the TUI alive., PlanOption

### Community 50 - "environment.py"
Cohesion: 0.29
Nodes (6): Daedalus TUI Command Menu, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 51 - "CompactSettingsSelect"
Cohesion: 0.24
Nodes (6): PersonalSupabaseTests, Path, bootstrap_personal_supabase(), Validate registration and the project-local shared environment.      This helper, Scaffold supabase files, env placeholders, profiles, and a ``.daedalus`` marker., register_personal_supabase()

### Community 52 - "Daedalus TUI Call Graph Visualization"
Cohesion: 0.29
Nodes (6): Daedalus TUI Call Graph Visualization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 53 - "b.py"
Cohesion: 0.10
Nodes (21): alpha(), Entry helper that fans out into order and UI branches., beta(), Continue the sample call chain toward gamma., gamma(), Leaf helper in the sample call chain., make_runner(), create_order() (+13 more)

### Community 54 - "update_repository"
Cohesion: 0.15
Nodes (12): CodingStatisticsScreen, _format_count(), _format_tokens(), Textual interface for concurrent local agent tasks., Show token or task usage history and derived coding statistics., Return Textual's event name for a user-facing shortcut label., _shortcut_binding_key(), copy_to_system_clipboard() (+4 more)

### Community 55 - "conftest.py"
Cohesion: 0.50
Nodes (3): pytest_configure(), Pytest hooks shared across the test suite., Install pyan3 when call-graph tests run in an environment missing it.

### Community 57 - "DescriptorEmbedder"
Cohesion: 0.19
Nodes (14): ConfigTests, CodingStatisticsSettings, CommandMenuSettings, LayoutSettings, load_coding_statistics_settings(), load_command_menu_settings(), load_orchestration_settings(), load_tui_settings() (+6 more)

### Community 59 - "PlanClarification"
Cohesion: 0.11
Nodes (7): FakeCoordinator, FakeRunner, settings(), PersonalSupabaseRemovalResult, Outcome of removing the local personal-Supabase integration artifacts., DaedalusProject, A repository recognized by the presence of a ``feature_files`` folder.

### Community 60 - "trading.py"
Cohesion: 0.32
Nodes (5): calculate(), execute_trade(), Portfolio, Assignment lineage, augassign, attribute mutate, and unique call mapping., run_pipeline()

### Community 61 - "CodingStatisticsScreen"
Cohesion: 0.09
Nodes (19): GraphifyTests, SupabaseMigrationsTests, Provider-specific subprocess execution with normalized agent messages., GraphifyResult, Path, Best-effort graph refresh owned by the local orchestration layer., Refresh the primary repository graph without affecting task success., update_repository() (+11 more)

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
Cohesion: 0.19
Nodes (11): _ensure_profile_guidance(), is_personal_supabase_activated(), is_personal_supabase_registered(), load_personal_supabase_status(), PersonalSupabaseStatus, profile_guidance_section(), Return the markdown section appended to coding/architecture profiles., Registration / activation marker loaded from a target project's ``.daedalus``. (+3 more)

### Community 69 - "PersonalSupabaseActivationProgressScreen"
Cohesion: 0.18
Nodes (7): PersonalSupabaseActivationProgressScreen, Finish a queued modal update only if its screen is still mounted., Show the durable activation phases while the worker runs., Whether the activation worker still owns this progress surface., Apply worker results that arrived while this modal was mounting., Freeze the progress display and allow the operator to close it., Render a completion state after all modal widgets are mounted.

### Community 70 - "WorktreeContext"
Cohesion: 0.28
Nodes (5): OrchestratorTests, AgentResult, WorktreeContext, LocalOrchestrator, VerificationResult

### Community 71 - "_collapse_inner_safe"
Cohesion: 0.21
Nodes (8): CallGraphVisitor, discover_source_files(), extract_uses_edges(), Path, CallGraphVisitor with a collapse_inner guard for namespace-less anonymous nodes., Run pyan analysis and return caller→callees edges plus all node names., Collect Python source files matching *source_globs* and not *exclude*., _SafeCallGraphVisitor

### Community 72 - "render_call_graph_tree.py"
Cohesion: 0.24
Nodes (14): _flat_parameter_values(), load_config(), _load_parameter_values(), load_runner_parameters(), main(), _project_root_setting(), _project_table(), Path (+6 more)

### Community 73 - "._on_personal_supabase_activation_progress"
Cohesion: 0.10
Nodes (11): CompletedProcess, Path, Stage the current worktree contents for orchestration checks or commit., Remove graphify output changes from an agent worktree.          Graphify refresh, Keep a read-only planning pass from becoming an implementation change., Commit only the generated graph after a successful primary update., Return a directory whose HEAD matches the target branch tip.          When the r, Remove a short-lived primary checkout created for post-promotion work. (+3 more)

### Community 74 - "PersonalSupabaseConfirmationScreen"
Cohesion: 0.10
Nodes (7): Changed, Pressed, Submitted, PersonalSupabaseConfirmationScreen, PersonalSupabaseRemovalConfirmationScreen, Require an explicit confirmation before scaffolding/Activating a shared schema., Require an exact project-name confirmation before local cleanup.

### Community 76 - "bootstrap_personal_supabase"
Cohesion: 0.10
Nodes (4): TuiAppTests, DaedalusVimTextArea, VimTextArea with multiline prompt behavior and system clipboard sync., VimTextArea

### Community 77 - "verification.py"
Cohesion: 0.14
Nodes (17): Popen, Protocol, VerificationTests, discover_commands(), format_process_result(), package_has_test_script(), CompletedProcess, Path (+9 more)

### Community 78 - "load_project_worktree_settings"
Cohesion: 0.40
Nodes (3): Forward worker phases to the modal and the main status line., Mark the current activation phase and retain a readable status line., Update mounted progress widgets for one worker phase.

### Community 79 - "._set_status"
Cohesion: 0.13
Nodes (6): Key, Synchronize registered projects; push migrations only when activated., Add Vim-like navigation without changing TextArea insert behavior., Confirm, then scaffold (if needed) and Activate personal Supabase., Clear the selected task and unlock a fresh prompt editor., Return a TextArea selection or the active screen selection.

### Community 80 - ".edit_paste_after"
Cohesion: 0.16
Nodes (16): main(), Child-process probe for project-local Supabase env key presence.  Invoke as ``py, _first_filled_env_value(), _key_or_aliases_label(), load_personal_supabase_settings(), personal_supabase_environment_settings(), project_ref_from_supabase_url(), Return canonical and required environment keys from the feature parameters. (+8 more)

### Community 81 - ".enter_insert_mode"
Cohesion: 0.16
Nodes (16): personal_supabase_managed_env_keys(), Return every env key this feature may clean up (preferred + aliases)., Remove local personal-Supabase artifacts without touching remote state.      The, Remove only the personal-Supabase table from a project marker., Remove the generated shared-Supabase block from ``.env.example``., Remove synchronized Supabase assignments while preserving other env values., Return env text without the configured Supabase assignments., Remove the generated Personal Supabase section from one profile. (+8 more)

### Community 83 - "._set_error"
Cohesion: 0.13
Nodes (7): Remove known credential values before diagnostics reach the UI or log., Confirm, then remove local personal-Supabase artifacts for the project., Scaffold files, then guide manual project env setup before Activate., Run scaffold+Activate in a background worker so the TUI stays responsive., Enable Push only when an origin remote and operating branch are available., Sync the Branch Select value for the active project with origin., _redact_supabase_diagnostic()

### Community 84 - "git_worktree.py"
Cohesion: 0.14
Nodes (11): _is_ancestor(), list_local_branches(), pull_branch(), Local Git worktree lifecycle used by the standalone orchestrator., Return local branch names under ``refs/heads`` without checking anything out., Return whether ``remote`` is configured for ``repository``., Return the worktree path that has ``branch`` checked out, if any., Integrate ``remote/branch`` into the local branch without switching checkout. (+3 more)

### Community 85 - "ProjectWorktreeSettings"
Cohesion: 0.25
Nodes (8): ProjectConfigTests, load_project_worktree_settings(), ProjectWorktreeSettings, Path, Configuration supplied by a target project to prepare task worktrees., Install and shared-path settings from a target project's .daedalus file., Load optional worktree provisioning settings from a target repository., _string_array()

### Community 86 - "debug_log.py"
Cohesion: 0.20
Nodes (9): _unregister_app_for_thread_exit(), close_fault_handler(), configure_debug_logging(), install_fault_handler(), _install_thread_exception_logging(), Path, Persistent diagnostics for failures that occur after the Textual screen closes., Write detailed runtime diagnostics to a rotating local log file. (+1 more)

### Community 87 - "GitWorktreeError"
Cohesion: 0.24
Nodes (5): GitWorktreeError, push_branch(), RuntimeError, Push a local branch to ``remote``, setting upstream with ``-u`` when needed., Install project resources and link declared shared read-only paths.

### Community 89 - "PersonalSupabaseSetupWizardScreen"
Cohesion: 0.17
Nodes (11): load_project_personal_supabase_env_values(), preflight_personal_supabase(), PreflightResult, _probe_database_url(), probe_project_personal_supabase_environment(), project_personal_supabase_env_path(), Run access-method-aware live connectivity checks; never mutates schema., Return the project-local ``.env`` path operators must edit. (+3 more)

## Knowledge Gaps
- **112 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+107 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `CandidateFeatureGroup` to `DaedalusVimTextArea`, `AgentRunner`, `GitWorktreeManager`, `._shutdown_coordinators`, `._set_status`, `._set_status`, `.provider_split`, `CodingStatisticsScreen`, `calculate_token_usage`, `._persist_task`, `update_repository`, `DescriptorEmbedder`, `PlanClarification`, `CodingStatisticsScreen`, `PersonalSupabaseActivationProgressScreen`, `bootstrap_personal_supabase`, `load_project_worktree_settings`, `._set_status`, `._set_error`, `debug_log.py`, `GitWorktreeError`, `._apply_measured_responsive_layout`, `._on_topic_created`?**
  _High betweenness centrality (0.140) - this node is a cross-community bridge._
- **Why does `TuiAppTests` connect `bootstrap_personal_supabase` to `DaedalusVimTextArea`, `.provider_split`, `PersonalSupabaseActivationProgressScreen`, `PersonalSupabaseConfirmationScreen`, `CandidateFeatureGroup`, `._render_line_strip`, `._shutdown_coordinators`, `update_repository`, `GitWorktreeError`, `ProjectInitializerScreen`, `DescriptorEmbedder`, `PlanClarificationScreen`, `PlanClarification`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `TaskMemoryStore` connect `calculate_token_usage` to `DaedalusVimTextArea`, `.provider_split`, `PersonalSupabaseActivationProgressScreen`, `PersonalSupabaseConfirmationScreen`, `CandidateFeatureGroup`, `._persist_task`, `._shutdown_coordinators`, `update_repository`, `ProjectInitializerScreen`, `DescriptorEmbedder`, `PlanClarificationScreen`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `CommandMenuScreen`) actually correct?**
  _`TuiAppTests` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 28 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 18 INFERRED edges - model-reasoned connections that need verification._