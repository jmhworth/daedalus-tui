# Graph Report - daedalus-tui  (2026-09-16)

## Corpus Check
- 92 files · ~81,775 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1708 nodes · 4584 edges · 87 communities (72 shown, 15 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 504 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7ab74968`
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
- TranscriptLog
- _collapse_inner_safe
- render_call_graph_tree.py
- ._on_personal_supabase_activation_progress
- __init__.py
- CallGraphRunnerTests
- bootstrap_personal_supabase
- update_repository
- load_project_worktree_settings
- .edit_paste_before
- .edit_paste_after
- .enter_insert_mode
- .nav_word_end
- ProjectInitializerScreen
- .edit_paste_before
- .__init__
- ._on_topic_created

## God Nodes (most connected - your core abstractions)
1. `DaedalusTuiApp` - 172 edges
2. `TuiAppTests` - 115 edges
3. `TaskCoordinator` - 81 edges
4. `OrchestrationSettings` - 67 edges
5. `DaedalusVimTextArea` - 65 edges
6. `AgentRunner` - 64 edges
7. `TaskRecord` - 64 edges
8. `GitWorktreeManager` - 61 edges
9. `TaskMemoryStore` - 61 edges
10. `FakeCoordinator` - 60 edges

## Surprising Connections (you probably didn't know these)
- `FakeStream` --uses--> `AgentControl`  [INFERRED]
  tests/test_agent_runner.py → tui/agent_runner.py
- `FakeStream` --uses--> `AgentRequest`  [INFERRED]
  tests/test_agent_runner.py → tui/agent_runner.py
- `FakeStream` --uses--> `AgentRunner`  [INFERRED]
  tests/test_agent_runner.py → tui/agent_runner.py
- `FakeProcess` --uses--> `AgentControl`  [INFERRED]
  tests/test_agent_runner.py → tui/agent_runner.py
- `FakeProcess` --uses--> `AgentLogEvent`  [INFERRED]
  tests/test_agent_runner.py → tui/agent_runner.py

## Import Cycles
- None detected.

## Communities (87 total, 15 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.18
Nodes (25): score_band(), _canonical_tree_name(), _histogram_bars(), _layout_extent_y(), _layout_subtree(), _layout_trees(), _LayoutNode, _layouts_bounds() (+17 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.21
Nodes (4): TaskCoordinatorTests, OrchestrationSettings, Submit independent prompts while sharing a serialized integration gate., TaskCoordinator

### Community 2 - "AgentRunner"
Cohesion: 0.13
Nodes (4): OutputCallback, Thread, Track an inactivity deadline that agent stdout can refresh., _TimeoutTracker

### Community 3 - "DaedalusTuiApp"
Cohesion: 0.16
Nodes (14): Attribute, AugAssign, Call, Lambda, Name, _attr_dotted(), make_scoped_id(), Return dotted attribute path for Attribute/Name chains, else None. (+6 more)

### Community 4 - "app.py"
Cohesion: 0.26
Nodes (7): OrchestratorTests, AgentResult, WorktreeContext, GraphifyResult, LocalOrchestrator, PushResult, VerificationResult

### Community 5 - "TokenUsageStore"
Cohesion: 0.29
Nodes (6): Applying answers, Bridge Agent Profile, Build-loop tasking, cp_doc structure, Hard rules, Purpose

### Community 6 - "GitWorktreeManager"
Cohesion: 0.08
Nodes (14): Strip, Style, Resize, Return the width available for transcript text inside the Log., Wrap one logical line at word boundaries when the width permits., Split an overlong word with visible hyphens at cell boundaries., Render a line with the final-message color before selection styling., Reflow stored messages when the output box changes width. (+6 more)

### Community 7 - "Daedalus TUI Local Token Usage Memory"
Cohesion: 0.29
Nodes (6): Daedalus TUI Local Persistent Memory, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 8 - "update_repository"
Cohesion: 0.07
Nodes (35): PromptTests, TopicsTests, build_migration_repair_prompt(), build_repair_prompt(), build_resolver_prompt(), build_task_prompt(), build_topic_population_prompt(), _embedded_profile() (+27 more)

### Community 11 - "Key"
Cohesion: 0.05
Nodes (29): GitWorktreeTests, ProjectConfigTests, GitWorktreeManager, list_local_branches(), push_branch(), CompletedProcess, Path, Local Git worktree lifecycle used by the standalone orchestrator. (+21 more)

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
Cohesion: 0.08
Nodes (19): Pressed, ProgressCallback, Submitted, ProjectInitializerTests, find_github_url(), initialize_project(), load_initializer_settings(), matching_request_marker() (+11 more)

### Community 21 - "._shutdown_coordinators"
Cohesion: 0.05
Nodes (52): Binding, ComposeResult, Mount, CommandMenuScreen, CompactSettingsSelect, CreateTopicScreen, KeyboardShortcutsScreen, _LegacyCompatibleBinding (+44 more)

### Community 22 - "._set_status"
Cohesion: 0.19
Nodes (20): Unit tests for AST variable-lineage analysis., analyze_sources(), compute_variable_stats(), _FunctionInfo, FunctionSummary, GraphEdge, GraphNode, module_fqn_from_path() (+12 more)

### Community 23 - "update_repository"
Cohesion: 0.10
Nodes (30): build_symbol_contexts(), _descriptor_hash(), DescriptorEmbedder, _doc_for_definition(), extract_docs_for_symbols(), format_descriptor(), _format_name_list(), invert_edges() (+22 more)

### Community 24 - "Daedalus TUI Coding Statistics"
Cohesion: 0.29
Nodes (6): Daedalus TUI Coding Statistics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 25 - "._set_status"
Cohesion: 0.24
Nodes (5): AgentRunnerTests, FakeProcess, AgentRequest, AgentRunner, Run Codex or Cursor directly and emit only assistant-facing messages.

### Community 26 - ".provider_split"
Cohesion: 0.12
Nodes (23): PlanTests, Resolve a Select value that is legal for the current question options., build_implementation_prompt(), build_plan_clarification_prompt(), build_plan_followup_prompt(), custom_answer_text(), encode_custom_answer(), is_valid_plan_answer() (+15 more)

### Community 27 - ".on_mount"
Cohesion: 0.13
Nodes (8): AsyncFunctionDef, ClassDef, FunctionDef, Global, Module, Nonlocal, Qualname used for Store binding identity in the current scope., _ScopeFrame

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.23
Nodes (6): GraphifyTests, Path, Best-effort graph refresh owned by the local orchestration layer., Refresh the primary repository graph without affecting task success., update_repository(), Refresh graph metadata after promotion without blocking the task.

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

### Community 35 - "agent_runner.py"
Cohesion: 0.17
Nodes (3): Path, _sample_files(), VariableLineageTests

### Community 36 - "architecture.md"
Cohesion: 0.33
Nodes (5): 4-Stage Development Lifecycle, Evidence Extraction, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization

### Community 37 - "integrating.md"
Cohesion: 0.40
Nodes (4): 4-Stage Development Lifecycle, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization

### Community 38 - "._set_status"
Cohesion: 0.04
Nodes (32): DaedalusTuiApp, Key, Resize, Synchronize registered projects; push migrations only when activated., Add Vim-like navigation without changing TextArea insert behavior., Apply the viewport-aware layout whenever the terminal changes size., Toggle responsive classes and dimensions after a viewport change.          ``com, Measure wide controls after their current layout pass completes. (+24 more)

### Community 39 - "Daedalus Project Instructions"
Cohesion: 0.33
Nodes (5): Daedalus Project Instructions, graphify, Shared personal Supabase, Task mode, Topics

### Community 41 - "KeyboardShortcutsScreen"
Cohesion: 0.05
Nodes (88): PersonalSupabaseTests, Path, Remove values loaded for a subprocess from a user-facing diagnostic., redact_environment_values(), activate_personal_supabase(), _allow_list_comment(), bootstrap_personal_supabase(), _commit_paths() (+80 more)

### Community 42 - "debug_log.py"
Cohesion: 0.16
Nodes (15): Popen, Protocol, VerificationTests, discover_commands(), format_process_result(), package_has_test_script(), CompletedProcess, Path (+7 more)

### Community 43 - "._rebuild_plan_questions"
Cohesion: 0.16
Nodes (12): CallGraphTreeTests, candidate_feature_id(), group_candidate_features(), parent_child_score_map(), Return a stable ID derived solely from a group's sorted member symbols., Group symbols connected by inclusive-threshold relations.      Parent/child dire, ScoredRelation, build_tree() (+4 more)

### Community 44 - "CandidateFeatureGroup"
Cohesion: 0.16
Nodes (6): FakeStream, InterruptibleProcess, AgentLogEvent, Provider-specific subprocess execution with normalized agent messages., __getattr__(), Standalone Textual interface and local agent orchestration.

### Community 45 - "KeyboardShortcutsScreen"
Cohesion: 0.20
Nodes (9): Constraints and Design Principles, Desired End State, Intended Import Workflow, Open Questions, Project Imports to the Daedalus Format, Scope and Durable Context, State Log, Topic Goal (+1 more)

### Community 46 - "._handle_visual_line_mode"
Cohesion: 0.14
Nodes (8): Key, Keep Enter as a newline; Ctrl+Enter remains the app submit key., Route visual-line mode and mirror new yanks to the host clipboard., Add Daedalus prompt commands that the dependency does not provide., Select the current line and enter Vim visual-line mode., Select every character in the lines between the start and cursor., Handle movement and operators while whole lines are selected., Expose operator-pending so the caret can become an underline.

### Community 47 - "DaedalusTuiApp"
Cohesion: 0.17
Nodes (15): EnvironmentTests, _atomic_write(), cursor_environment(), _env_value(), EnvironmentSyncResult, Path, Small, dependency-free environment-file loading for local CLI providers., Return the process environment plus local Cursor credentials.      Explicit proc (+7 more)

### Community 48 - "._persist_task"
Cohesion: 0.14
Nodes (11): Send selected plan answers back to the planning agent for confirmation., Ask a side-channel clarification about one plan question without plan follow-up., Create a new coding task from a confirmed plan review., Run another planning pass while keeping the task in questioning., Promote a reviewed plan into the normal coding and verification route., Retry a failed agent request after connectivity or service recovery., Run an ask-mode clarification that does not mutate plan conversation state., Construct an orchestrator with the shared launch environment when configured. (+3 more)

### Community 49 - "._render_line_strip"
Cohesion: 0.11
Nodes (4): Agent plan text must not be parsed as Textual/Rich markup., Follow-up questions must not crash when old option ids linger on widgets., Deferred Select init must not fatal-exit on a leftover option id., Clearing questions after confirmation must keep the TUI alive.

### Community 50 - "environment.py"
Cohesion: 0.29
Nodes (6): Daedalus TUI Command Menu, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 51 - "CompactSettingsSelect"
Cohesion: 0.21
Nodes (8): AnnAssign, Assign, comprehension, Return, AST, Collect scoped variable/attribute lineage for one module., Visit nested function/class/call constructs inside expressions., VariableLineageVisitor

### Community 52 - "Daedalus TUI Call Graph Visualization"
Cohesion: 0.29
Nodes (6): Daedalus TUI Call Graph Visualization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 53 - "b.py"
Cohesion: 0.10
Nodes (21): alpha(), Entry helper that fans out into order and UI branches., beta(), Continue the sample call chain toward gamma., gamma(), Leaf helper in the sample call chain., make_runner(), create_order() (+13 more)

### Community 54 - "update_repository"
Cohesion: 0.13
Nodes (7): Changed, Select, CodingStatisticsScreen, _format_count(), _format_tokens(), Avoid posting Select.Changed events when the options are unchanged., Show token or task usage history and derived coding statistics.

### Community 55 - "conftest.py"
Cohesion: 0.50
Nodes (3): pytest_configure(), Pytest hooks shared across the test suite., Install pyan3 when call-graph tests run in an environment missing it.

### Community 57 - "DescriptorEmbedder"
Cohesion: 0.15
Nodes (11): ConfigTests, LayoutSettings, load_coding_statistics_settings(), load_command_menu_settings(), load_orchestration_settings(), load_tui_settings(), ModelOption, _options() (+3 more)

### Community 59 - "PlanClarification"
Cohesion: 0.12
Nodes (7): FakeCoordinator, FakeRunner, settings(), PersonalSupabaseRemovalResult, Outcome of removing the local personal-Supabase integration artifacts., DaedalusProject, A repository recognized by the presence of a ``feature_files`` folder.

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

### Community 68 - "task_coordinator.py"
Cohesion: 0.11
Nodes (16): TaskEventCallback, FakeOrchestrator, OrchestrationResult, IntegrationCoordinator, _nonnegative_int(), _phase_for_status(), Lock, Path (+8 more)

### Community 69 - "PersonalSupabaseActivationProgressScreen"
Cohesion: 0.25
Nodes (4): Finish a queued modal update only if its screen is still mounted., Apply worker results that arrived while this modal was mounting., Freeze the progress display and allow the operator to close it., Render a completion state after all modal widgets are mounted.

### Community 70 - "TranscriptLog"
Cohesion: 0.16
Nodes (11): Lowercase and split identifiers on `.` / `_` while keeping word tokens., SimilarityResult, tokenize_descriptor(), write_similarity_json(), CallGraphConfig, Choose tree roots from configured entry points or orphan graph nodes., Render candidate features independently from the similarity panel., Analyze the project at *project_root* and write the HTML call tree. (+3 more)

### Community 71 - "_collapse_inner_safe"
Cohesion: 0.15
Nodes (12): CallGraphVisitor, _collapse_inner_safe(), _collect_node_names(), discover_source_files(), extract_uses_edges(), Any, Path, Run pyan's collapse_inner while skipping anonymous nodes pyan cannot parent-reso (+4 more)

### Community 72 - "render_call_graph_tree.py"
Cohesion: 0.24
Nodes (14): _flat_parameter_values(), load_config(), _load_parameter_values(), load_runner_parameters(), main(), _project_root_setting(), _project_table(), Path (+6 more)

### Community 73 - "._on_personal_supabase_activation_progress"
Cohesion: 0.25
Nodes (6): CandidateFeatureGroup, A deterministic connected component of qualifying similarity relations., Return the stable identifier using the concise ``id`` spelling., Compatibility alias for callers that refer to group relations directly., _feature_ids_by_member(), Map each grouped symbol to its stable candidate-feature ID.

### Community 74 - "__init__.py"
Cohesion: 0.10
Nodes (12): Exception, Pause active agents before ThreadPoolExecutor joins its workers.      CPython ex, Stop agents before an explicit Textual exit begins., Persist Textual failures that would otherwise only flash on screen., Cover terminal and event-loop exits that bypass Textual unmount., Run before ThreadPoolExecutor's internal interpreter-exit join., Clean up if Textual's run loop returns without its unmount hook., Idempotently detach task callbacks and request child-process shutdown. (+4 more)

### Community 76 - "bootstrap_personal_supabase"
Cohesion: 0.09
Nodes (4): TuiAppTests, DaedalusVimTextArea, VimTextArea with multiline prompt behavior and system clipboard sync., VimTextArea

### Community 77 - "update_repository"
Cohesion: 0.23
Nodes (7): SupabaseMigrationsTests, migrations_pending(), push_migrations(), Path, Orchestration-owned Supabase migration push for target project worktrees., Return True when the worktree differs from base under supabase/migrations/., Run non-interactive `supabase db push --yes` in the target worktree.

### Community 80 - ".edit_paste_after"
Cohesion: 0.15
Nodes (12): AbstractEventLoop, BaseException, configure_debug_logging(), install_fault_handler(), _install_thread_exception_logging(), log_exception(), Path, Persistent diagnostics for failures that occur after the Textual screen closes. (+4 more)

### Community 82 - ".nav_word_end"
Cohesion: 0.05
Nodes (25): Log, RowSelected, Path, Confirm, then remove local personal-Supabase artifacts for the project., Run scaffold+Activate in a background worker so the TUI stays responsive., Return provider metadata from the shared controls for a new task., Queue a coding task that writes and expands the requested topic file., Focus a task from the cross-project update inbox. (+17 more)

### Community 83 - "ProjectInitializerScreen"
Cohesion: 0.67
Nodes (3): Text, _literal_select_options(), Build Select prompts that Rich will not parse as markup.

## Knowledge Gaps
- **112 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+107 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `._set_status` to `DaedalusVimTextArea`, `PersonalSupabaseActivationProgressScreen`, `__init__.py`, `bootstrap_personal_supabase`, `CandidateFeatureGroup`, `.edit_paste_after`, `._persist_task`, `.nav_word_end`, `._shutdown_coordinators`, `update_repository`, `._set_status`, `.provider_split`, `PlanClarification`, `calculate_token_usage`, `DescriptorEmbedder`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
- **Why does `TuiAppTests` connect `bootstrap_personal_supabase` to `._set_status`, `._persist_task`, `._render_line_strip`, `._shutdown_coordinators`, `update_repository`, `DescriptorEmbedder`, `.provider_split`, `PlanClarification`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `TaskCoordinator` connect `DaedalusVimTextArea` to `task_coordinator.py`, `app.py`, `._set_status`, `Key`, `CandidateFeatureGroup`, `._persist_task`, `.nav_word_end`, `._shutdown_coordinators`, `update_repository`, `calculate_token_usage`, `DescriptorEmbedder`, `.provider_split`, `CodingStatisticsScreen`, `._set_status`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `CommandMenuScreen`) actually correct?**
  _`TuiAppTests` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 18 INFERRED edges - model-reasoned connections that need verification._