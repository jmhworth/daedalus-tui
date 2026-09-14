# Graph Report - daedalus-tui  (2026-09-13)

## Corpus Check
- 91 files · ~74,597 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1571 nodes · 4115 edges · 84 communities (71 shown, 13 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 394 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1cf5f847`
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
- task_coordinator.py
- KeyboardShortcutsScreen
- ._handle_visual_line_mode
- ._start_new_task
- discover_projects
- ._render_line_strip
- .test_plan_review_renders_literal_markup_like_agent_text
- CompactSettingsSelect
- Daedalus TUI Call Graph Visualization
- b.py
- update_repository
- conftest.py
- cycle_a.py
- DescriptorEmbedder
- __init__.py
- render_call_graph_tree
- trading.py
- CodingStatisticsScreen
- ambiguous_a.py
- ambiguous_b.py
- module_resource.py
- scopes.py
- task_coordinator.py
- __init__.py
- PlanQuestion
- ._set_status
- debug_log.py
- _collapse_inner_safe
- render_call_graph_tree.py
- CandidateFeatureGroup
- __init__.py
- CallGraphRunnerTests
- .action_view_topic
- .cursor_shape
- .enter_insert_mode
- .nav_word_end
- .edit_paste_after
- .on_data_table_row_selected
- .on_resize
- .edit_paste_before

## God Nodes (most connected - your core abstractions)
1. `DaedalusTuiApp` - 160 edges
2. `TuiAppTests` - 102 edges
3. `TaskCoordinator` - 77 edges
4. `OrchestrationSettings` - 66 edges
5. `GitWorktreeManager` - 61 edges
6. `WorktreeContext` - 60 edges
7. `TaskRecord` - 60 edges
8. `DaedalusVimTextArea` - 60 edges
9. `AgentRunner` - 59 edges
10. `TaskMemoryStore` - 57 edges

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

## Communities (84 total, 13 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.18
Nodes (25): score_band(), _canonical_tree_name(), _collapse_inner_safe(), _collect_node_names(), _histogram_bars(), _layout_extent_y(), _layout_subtree(), _layout_trees() (+17 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.07
Nodes (27): TaskEventCallback, FakeOrchestrator, TaskCoordinatorTests, OrchestrationSettings, _nonnegative_int(), _phase_for_status(), Lock, Path (+19 more)

### Community 2 - "AgentRunner"
Cohesion: 0.09
Nodes (13): OutputCallback, AgentRunnerTests, FakeProcess, FakeStream, InterruptibleProcess, Thread, AgentLogEvent, AgentRequest (+5 more)

### Community 3 - "DaedalusTuiApp"
Cohesion: 0.07
Nodes (43): AnnAssign, Assign, AsyncFunctionDef, Attribute, AugAssign, Call, ClassDef, comprehension (+35 more)

### Community 4 - "app.py"
Cohesion: 0.26
Nodes (7): OrchestratorTests, AgentResult, WorktreeContext, GraphifyResult, LocalOrchestrator, PushResult, VerificationResult

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
Cohesion: 0.08
Nodes (14): GitWorktreeTests, GitWorktreeError, list_local_branches(), push_branch(), CompletedProcess, RuntimeError, Local Git worktree lifecycle used by the standalone orchestrator., Install project resources and link declared shared read-only paths. (+6 more)

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
Cohesion: 0.10
Nodes (10): RowSelected, Path, Focus a task from the cross-project update inbox., Memory override for the project, else the parameter-file default., Return only direct-child projects, or the empty-root fallback., Render actionable history and tasks created during this session., Keep failures, active work, and all tasks submitted in this launch., Keep inbox cells within their fixed width with a visible ellipsis. (+2 more)

### Community 21 - "._shutdown_coordinators"
Cohesion: 0.10
Nodes (8): Changed, DaedalusTuiApp, Run the wide-layout measurement after the next screen refresh., Keep a task visible after user activity during this launch., Prefer mounted selector values so clarification refreshes keep choices., Show either the full-size transcript or the full-size diagnostics log., Use Textual's OSC 52 path and a native clipboard fallback., __getattr__()

### Community 22 - "._set_status"
Cohesion: 0.14
Nodes (11): GitWorktreeManager, Path, Stage the current worktree contents for orchestration checks or commit., Remove graphify output changes from an agent worktree.          Graphify refresh, Keep a read-only planning pass from becoming an implementation change., Commit only the generated graph after a successful primary update., Return a directory whose HEAD matches the target branch tip.          When the r, Remove a short-lived primary checkout created for post-promotion work. (+3 more)

### Community 23 - "update_repository"
Cohesion: 0.10
Nodes (31): build_symbol_contexts(), _descriptor_hash(), DescriptorEmbedder, _doc_for_definition(), extract_docs_for_symbols(), format_descriptor(), _format_name_list(), invert_edges() (+23 more)

### Community 24 - "Daedalus TUI Coding Statistics"
Cohesion: 0.29
Nodes (6): Daedalus TUI Coding Statistics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 25 - "._set_status"
Cohesion: 0.11
Nodes (24): Follow-up questions must not crash when old option ids linger on widgets., PlanTests, Resolve a Select value that is legal for the current question options., build_implementation_prompt(), build_plan_clarification_prompt(), build_plan_followup_prompt(), custom_answer_text(), encode_custom_answer() (+16 more)

### Community 26 - ".provider_split"
Cohesion: 0.16
Nodes (17): ProgressCallback, ProjectInitializerTests, find_github_url(), initialize_project(), load_initializer_settings(), matching_request_marker(), materialize_templates(), normalize_github_url() (+9 more)

### Community 27 - ".on_mount"
Cohesion: 0.08
Nodes (29): Popen, Protocol, VerificationTests, Provider-specific subprocess execution with normalized agent messages., Remove known credential values before diagnostics reach the UI or log., _redact_supabase_diagnostic(), Remove values loaded for a subprocess from a user-facing diagnostic., redact_environment_values() (+21 more)

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.13
Nodes (5): FakeCoordinator, FakeRunner, settings(), DaedalusProject, A repository recognized by the presence of a ``feature_files`` folder.

### Community 30 - "calculate_token_usage"
Cohesion: 0.05
Nodes (33): TaskMemoryStoreTests, TokenUsageTests, Path, Remove one project's operating-branch override (absent = use default)., Return the remembered default topic for a project, if any., Remember one project's default topic without losing other entries., Remove one project's topic override (absent = no default topic)., Return persisted task snapshots keyed by their stable task ID. (+25 more)

### Community 31 - "PlanAnswerSelect"
Cohesion: 0.29
Nodes (6): Daedalus TUI Project Initialization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 32 - "discover_projects"
Cohesion: 0.25
Nodes (7): 4-Stage Development Lifecycle, Alignment, Debugging, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization, Topics (when tagged)

### Community 33 - ".on_button_pressed"
Cohesion: 0.23
Nodes (7): SupabaseMigrationsTests, migrations_pending(), push_migrations(), Path, Orchestration-owned Supabase migration push for target project worktrees., Return True when the worktree differs from base under supabase/migrations/., Run non-interactive `supabase db push --yes` in the target worktree.

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
Cohesion: 0.09
Nodes (13): Synchronize and optionally push every registered discovered project., Open the selected project topic in a read-only modal., Apply provider-specific model and reasoning choices to all controls., Avoid posting Select.Changed events when the options are unchanged., Read the current value from the same selectors used for submission., Populate the compact value Select while retaining its active category., Apply a compact value through the existing wide-control state., Update the project's coordinator so later submits use ``branch``. (+5 more)

### Community 39 - "Daedalus Project Instructions"
Cohesion: 0.33
Nodes (5): Daedalus Project Instructions, graphify, Shared personal Supabase, Task mode, Topics

### Community 41 - "KeyboardShortcutsScreen"
Cohesion: 0.13
Nodes (28): _allow_list_comment(), _ensure_env_example(), _ensure_profile_guidance(), _ensure_supabase_scaffold(), _env_example_block(), is_personal_supabase_registered(), load_personal_supabase_settings(), load_personal_supabase_status() (+20 more)

### Community 42 - "debug_log.py"
Cohesion: 0.23
Nodes (6): GraphifyTests, Path, Best-effort graph refresh owned by the local orchestration layer., Refresh the primary repository graph without affecting task success., update_repository(), Refresh graph metadata after promotion without blocking the task.

### Community 43 - "._rebuild_plan_questions"
Cohesion: 0.15
Nodes (12): CallGraphTreeTests, candidate_feature_id(), group_candidate_features(), Lowercase and split identifiers on `.` / `_` while keeping word tokens., Return a stable ID derived solely from a group's sorted member symbols., Group symbols connected by inclusive-threshold relations.      Parent/child dire, ScoredRelation, SimilarityResult (+4 more)

### Community 44 - "task_coordinator.py"
Cohesion: 0.14
Nodes (6): Pressed, Submitted, PersonalSupabaseConfirmationScreen, ProjectInitializerScreen, Require an explicit confirmation before claiming a shared schema., Collect a project slug and create a Daedalus-compatible directory.

### Community 45 - "KeyboardShortcutsScreen"
Cohesion: 0.20
Nodes (9): Constraints and Design Principles, Desired End State, Intended Import Workflow, Open Questions, Project Imports to the Daedalus Format, Scope and Durable Context, State Log, Topic Goal (+1 more)

### Community 46 - "._handle_visual_line_mode"
Cohesion: 0.14
Nodes (8): Key, Keep Enter as a newline; Ctrl+Enter remains the app submit key., Route visual-line mode and mirror new yanks to the host clipboard., Add Daedalus prompt commands that the dependency does not provide., Select the current line and enter Vim visual-line mode., Select every character in the lines between the start and cursor., Handle movement and operators while whole lines are selected., Expose operator-pending so the caret can become an underline.

### Community 47 - "._start_new_task"
Cohesion: 0.18
Nodes (6): Resize, Apply the viewport-aware layout whenever the terminal changes size., Toggle responsive classes and dimensions after a viewport change.          ``com, Measure wide controls after their current layout pass completes., Switch to compact mode when wide controls extend past their bars., Return whether wide-layout controls are clipped or too narrow.

### Community 48 - "discover_projects"
Cohesion: 0.26
Nodes (7): ProjectDiscoveryTests, discover_projects(), is_direct_child_project(), Path, Discovery of Daedalus-supported repositories beneath a launch root., Return whether ``path`` is an immediate child of ``launch_root``., Find immediate child folders containing a direct ``feature_files`` child.      G

### Community 49 - "._render_line_strip"
Cohesion: 0.13
Nodes (7): Ask for confirmation before scaffolding a shared Supabase schema., Return labels and values for one compact settings category., Return provider metadata from the shared controls for a new task., Queue a coding task that writes and expands the requested topic file., Enable Push only when an origin remote and operating branch are available., Push the Branch Select value for the active project to origin., Disable registration when the active project already claimed its schema.

### Community 50 - ".test_plan_review_renders_literal_markup_like_agent_text"
Cohesion: 0.10
Nodes (4): TuiAppTests, DaedalusVimTextArea, VimTextArea with multiline prompt behavior and system clipboard sync., VimTextArea

### Community 52 - "Daedalus TUI Call Graph Visualization"
Cohesion: 0.29
Nodes (6): Daedalus TUI Call Graph Visualization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 53 - "b.py"
Cohesion: 0.10
Nodes (21): alpha(), Entry helper that fans out into order and UI branches., beta(), Continue the sample call chain toward gamma., gamma(), Leaf helper in the sample call chain., make_runner(), create_order() (+13 more)

### Community 54 - "update_repository"
Cohesion: 0.27
Nodes (4): CodingStatisticsScreen, _format_count(), _format_tokens(), Show token or task usage history and derived coding statistics.

### Community 55 - "conftest.py"
Cohesion: 0.50
Nodes (3): pytest_configure(), Pytest hooks shared across the test suite., Install pyan3 when call-graph tests run in an environment missing it.

### Community 57 - "DescriptorEmbedder"
Cohesion: 0.24
Nodes (11): ConfigTests, LayoutSettings, load_coding_statistics_settings(), load_orchestration_settings(), load_tui_settings(), ModelOption, _options(), Path (+3 more)

### Community 59 - "render_call_graph_tree"
Cohesion: 0.10
Nodes (23): Path, Unit tests for AST variable-lineage analysis., _sample_files(), build_tree(), CallGraphConfig, datetime, Build a call tree from *root* with cycle and depth limits., Render candidate features independently from the similarity panel. (+15 more)

### Community 60 - "trading.py"
Cohesion: 0.32
Nodes (5): calculate(), execute_trade(), Portfolio, Assignment lineage, augassign, attribute mutate, and unique call mapping., run_pipeline()

### Community 61 - "CodingStatisticsScreen"
Cohesion: 0.16
Nodes (11): EventCallback, IntegrationGate, AgentControl, Cooperative stop signals shared by a task and its active subprocess., AgentStopped, Lock, Path, RuntimeError (+3 more)

### Community 62 - "ambiguous_a.py"
Cohesion: 0.67
Nodes (3): helper(), Ambiguous same-named callees should not emit PASSED_TO edges., run_local()

### Community 63 - "ambiguous_b.py"
Cohesion: 0.67
Nodes (3): helper(), Second helper with the same simple name as ambiguous_a.helper., run_other()

### Community 66 - "task_coordinator.py"
Cohesion: 0.29
Nodes (6): Daedalus TUI Personal Shared Supabase, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 68 - "PlanQuestion"
Cohesion: 0.12
Nodes (3): Agent plan text must not be parsed as Textual/Rich markup., Deferred Select init must not fatal-exit on a leftover option id., Clearing questions after confirmation must keep the TUI alive.

### Community 69 - "._set_status"
Cohesion: 0.08
Nodes (17): AbstractEventLoop, BaseException, Exception, Stop agents before an explicit Textual exit begins., Persist Textual failures that would otherwise only flash on screen., Cover terminal and event-loop exits that bypass Textual unmount., Run before ThreadPoolExecutor's internal interpreter-exit join., Clean up if Textual's run loop returns without its unmount hook. (+9 more)

### Community 70 - "debug_log.py"
Cohesion: 0.14
Nodes (10): Mount, Select, CompactSettingsSelect, PlanAnswerSelect, Initialize dynamic plan selectors after their nested children mount., Finish Select setup without allowing a stale value to exit the TUI.          Pla, Keep only the latest value-change event for rebuilt compact controls., Replace question controls after Textual has completed child removal. (+2 more)

### Community 71 - "_collapse_inner_safe"
Cohesion: 0.21
Nodes (8): CallGraphVisitor, discover_source_files(), extract_uses_edges(), Path, CallGraphVisitor with a collapse_inner guard for namespace-less anonymous nodes., Run pyan analysis and return caller→callees edges plus all node names., Collect Python source files matching *source_globs* and not *exclude*., _SafeCallGraphVisitor

### Community 72 - "render_call_graph_tree.py"
Cohesion: 0.24
Nodes (14): _flat_parameter_values(), load_config(), _load_parameter_values(), load_runner_parameters(), main(), _project_root_setting(), _project_table(), Path (+6 more)

### Community 73 - "CandidateFeatureGroup"
Cohesion: 0.25
Nodes (6): CandidateFeatureGroup, A deterministic connected component of qualifying similarity relations., Return the stable identifier using the concise ``id`` spelling., Compatibility alias for callers that refer to group relations directly., _feature_ids_by_member(), Map each grouped symbol to its stable candidate-feature ID.

### Community 74 - "__init__.py"
Cohesion: 0.17
Nodes (15): EnvironmentTests, _atomic_write(), cursor_environment(), _env_value(), EnvironmentSyncResult, Path, Small, dependency-free environment-file loading for local CLI providers., Return the process environment plus local Cursor credentials.      Explicit proc (+7 more)

### Community 76 - ".action_view_topic"
Cohesion: 0.09
Nodes (10): ComposeResult, CreateTopicScreen, PlanClarificationScreen, Collect a clarification about one plan question., Collect the context needed to initialize and populate a topic file., Display a topic markdown file without allowing edits., TopicViewerScreen, CodingStatisticsSettings (+2 more)

### Community 78 - ".enter_insert_mode"
Cohesion: 0.24
Nodes (9): PersonalSupabaseTests, Path, bootstrap_personal_supabase(), Validate registration and synchronize the launch-root shared environment.      T, Scaffold supabase files, env placeholders, profiles, and a ``.daedalus`` marker., Outcome of scaffolding personal-Supabase files into a project tree., register_personal_supabase(), RegistrationResult (+1 more)

### Community 80 - ".edit_paste_after"
Cohesion: 0.21
Nodes (8): Textual interface for concurrent local agent tasks., copy_to_system_clipboard(), paste_from_system_clipboard(), System clipboard helpers for terminals without OSC 52 support., Read clipboard text using the native command available on the host., The Daedalus prompt's incremental Vim editing adapter., Paste Vim's register, falling back to the system clipboard., Paste before the cursor, including from the system clipboard.

### Community 81 - ".on_data_table_row_selected"
Cohesion: 0.17
Nodes (4): Key, Add Vim-like navigation without changing TextArea insert behavior., Clear the selected task and unlock a fresh prompt editor., Return a TextArea selection or the active screen selection.

### Community 82 - ".on_resize"
Cohesion: 0.20
Nodes (9): _unregister_app_for_thread_exit(), close_fault_handler(), configure_debug_logging(), install_fault_handler(), _install_thread_exception_logging(), Path, Persistent diagnostics for failures that occur after the Textual screen closes., Write detailed runtime diagnostics to a rotating local log file. (+1 more)

### Community 83 - ".edit_paste_before"
Cohesion: 0.29
Nodes (6): ProjectConfigTests, load_project_worktree_settings(), Path, Configuration supplied by a target project to prepare task worktrees., Load optional worktree provisioning settings from a target repository., _string_array()

## Knowledge Gaps
- **107 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+102 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `._shutdown_coordinators` to `DaedalusVimTextArea`, `AgentRunner`, `GitWorktreeManager`, `Key`, `TaskRecord`, `._set_status`, `.on_mount`, `CodingStatisticsScreen`, `calculate_token_usage`, `._set_status`, `._start_new_task`, `._render_line_strip`, `.test_plan_review_renders_literal_markup_like_agent_text`, `CompactSettingsSelect`, `update_repository`, `DescriptorEmbedder`, `._set_status`, `debug_log.py`, `.action_view_topic`, `.edit_paste_after`, `.on_data_table_row_selected`, `.on_resize`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Why does `DaedalusVimTextArea` connect `.test_plan_review_renders_literal_markup_like_agent_text` to `debug_log.py`, `._set_status`, `GitWorktreeManager`, `.action_view_topic`, `task_coordinator.py`, `.cursor_shape`, `._start_new_task`, `.edit_paste_after`, `.on_data_table_row_selected`, `._handle_visual_line_mode`, `CompactSettingsSelect`, `TaskRecord`, `._shutdown_coordinators`, `update_repository`, `.nav_word_end`, `DescriptorEmbedder`, `CodingStatisticsScreen`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `TuiAppTests` connect `.test_plan_review_renders_literal_markup_like_agent_text` to `DaedalusVimTextArea`, `PlanQuestion`, `debug_log.py`, `Key`, `task_coordinator.py`, `.action_view_topic`, `CompactSettingsSelect`, `._shutdown_coordinators`, `update_repository`, `DescriptorEmbedder`, `CodingStatisticsScreen`, `._set_status`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `DaedalusTuiApp`) actually correct?**
  _`TuiAppTests` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 17 INFERRED edges - model-reasoned connections that need verification._