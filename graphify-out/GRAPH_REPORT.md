# Graph Report - daedalus-tui  (2026-09-13)

## Corpus Check
- 90 files · ~71,845 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1531 nodes · 3985 edges · 84 communities (69 shown, 15 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 384 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8700b38b`
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
1. `DaedalusTuiApp` - 157 edges
2. `TuiAppTests` - 102 edges
3. `TaskCoordinator` - 76 edges
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

## Communities (84 total, 15 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.18
Nodes (25): score_band(), _canonical_tree_name(), _histogram_bars(), _layout_extent_y(), _layout_subtree(), _layout_trees(), _LayoutNode, _layouts_bounds() (+17 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.19
Nodes (5): FakeOrchestrator, TaskCoordinatorTests, OrchestrationSettings, Submit independent prompts while sharing a serialized integration gate., TaskCoordinator

### Community 2 - "AgentRunner"
Cohesion: 0.07
Nodes (18): OutputCallback, AgentRunnerTests, FakeProcess, FakeStream, InterruptibleProcess, Thread, AgentLogEvent, AgentRequest (+10 more)

### Community 3 - "DaedalusTuiApp"
Cohesion: 0.07
Nodes (42): AnnAssign, Assign, AsyncFunctionDef, Attribute, AugAssign, Call, ClassDef, comprehension (+34 more)

### Community 4 - "app.py"
Cohesion: 0.28
Nodes (5): OrchestratorTests, AgentResult, WorktreeContext, LocalOrchestrator, VerificationResult

### Community 5 - "TokenUsageStore"
Cohesion: 0.29
Nodes (6): Applying answers, Bridge Agent Profile, Build-loop tasking, cp_doc structure, Hard rules, Purpose

### Community 6 - "GitWorktreeManager"
Cohesion: 0.07
Nodes (21): Strip, Style, Text, _literal_select_options(), Show either the full-size transcript or the full-size diagnostics log., Build Select prompts that Rich will not parse as markup., Resize, Return the width available for transcript text inside the Log. (+13 more)

### Community 7 - "Daedalus TUI Local Token Usage Memory"
Cohesion: 0.29
Nodes (6): Daedalus TUI Local Persistent Memory, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 8 - "update_repository"
Cohesion: 0.07
Nodes (35): PromptTests, TopicsTests, build_migration_repair_prompt(), build_repair_prompt(), build_resolver_prompt(), build_task_prompt(), build_topic_population_prompt(), _embedded_profile() (+27 more)

### Community 11 - "Key"
Cohesion: 0.05
Nodes (31): GitWorktreeTests, ProjectConfigTests, GitWorktreeError, GitWorktreeManager, list_local_branches(), push_branch(), CompletedProcess, Path (+23 more)

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
Nodes (10): RowSelected, Path, Focus a task from the cross-project update inbox., Apply only the newest event per task to keep the UI responsive., Promote only events that need the user's attention in the inbox., Memory override for the project, else the parameter-file default., Render actionable history and tasks created during this session., Keep failures, active work, and all tasks submitted in this launch. (+2 more)

### Community 21 - "._shutdown_coordinators"
Cohesion: 0.08
Nodes (9): DaedalusTuiApp, Key, Add Vim-like navigation without changing TextArea insert behavior., Run the wide-layout measurement after the next screen refresh., Keep a task visible after user activity during this launch., Prefer mounted selector values so clarification refreshes keep choices., Replace question controls after Textual has completed child removal., Return a TextArea selection or the active screen selection. (+1 more)

### Community 22 - "._set_status"
Cohesion: 0.16
Nodes (9): Ask a side-channel clarification about one plan question without plan follow-up., Create a new coding task from a confirmed plan review., Run another planning pass while keeping the task in questioning., Promote a reviewed plan into the normal coding and verification route., Retry a failed agent request after connectivity or service recovery., Run an ask-mode clarification that does not mutate plan conversation state., Remove the clean, read-only planning worktree after coding is queued., Persist task state, coalescing high-frequency streamed messages. (+1 more)

### Community 23 - "update_repository"
Cohesion: 0.08
Nodes (35): build_symbol_contexts(), candidate_feature_id(), _descriptor_hash(), DescriptorEmbedder, _doc_for_definition(), extract_docs_for_symbols(), format_descriptor(), _format_name_list() (+27 more)

### Community 24 - "Daedalus TUI Coding Statistics"
Cohesion: 0.29
Nodes (6): Daedalus TUI Coding Statistics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 25 - "._set_status"
Cohesion: 0.13
Nodes (23): PlanTests, Resolve a Select value that is legal for the current question options., build_implementation_prompt(), build_plan_clarification_prompt(), build_plan_followup_prompt(), custom_answer_text(), encode_custom_answer(), is_valid_plan_answer() (+15 more)

### Community 26 - ".provider_split"
Cohesion: 0.07
Nodes (46): ProgressCallback, PersonalSupabaseTests, Path, ProjectInitializerTests, _allow_list_comment(), _ensure_env_example(), _ensure_profile_guidance(), _ensure_supabase_scaffold() (+38 more)

### Community 27 - ".on_mount"
Cohesion: 0.13
Nodes (18): Popen, Protocol, VerificationTests, Provider-specific subprocess execution with normalized agent messages., discover_commands(), format_process_result(), package_has_test_script(), CompletedProcess (+10 more)

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.12
Nodes (5): FakeCoordinator, FakeRunner, settings(), DaedalusProject, A repository recognized by the presence of a ``feature_files`` folder.

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
Cohesion: 0.22
Nodes (8): SupabaseMigrationsTests, migrations_pending(), push_migrations(), PushResult, Path, Orchestration-owned Supabase migration push for target project worktrees., Return True when the worktree differs from base under supabase/migrations/., Run non-interactive `supabase db push --yes` in the target worktree.

### Community 34 - "._render_line_strip"
Cohesion: 0.25
Nodes (7): 4-Stage Development Lifecycle, Alignment, Debugging, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization, Topics (when tagged)

### Community 35 - "agent_runner.py"
Cohesion: 0.12
Nodes (10): Path, _sample_files(), VariableLineageTests, analyze_sources(), module_fqn_from_path(), Path, Analyze Python sources and return lineage graph, summaries, and stats., Map a project-relative Python path to a dotted module FQN. (+2 more)

### Community 36 - "architecture.md"
Cohesion: 0.33
Nodes (5): 4-Stage Development Lifecycle, Evidence Extraction, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization

### Community 37 - "integrating.md"
Cohesion: 0.40
Nodes (4): 4-Stage Development Lifecycle, Execution Boundaries (CRITICAL), Feature File Automation, Parameter File Centralization

### Community 38 - "._set_status"
Cohesion: 0.09
Nodes (17): Changed, Select, Apply provider-specific model and reasoning choices to all controls., Avoid posting Select.Changed events when the options are unchanged., Return labels and values for one compact settings category., Read the current value from the same selectors used for submission., Populate the compact value Select while retaining its active category., Apply a compact value through the existing wide-control state. (+9 more)

### Community 39 - "Daedalus Project Instructions"
Cohesion: 0.40
Nodes (4): Daedalus Project Instructions, graphify, Task mode, Topics

### Community 41 - "KeyboardShortcutsScreen"
Cohesion: 0.12
Nodes (13): TaskEventCallback, IntegrationCoordinator, _nonnegative_int(), _phase_for_status(), Path, Concurrent task state and serialized local integration., Recover review questions from the last persisted plan response., Run ready integration operations one at a time in ready order. (+5 more)

### Community 42 - "debug_log.py"
Cohesion: 0.19
Nodes (8): GraphifyTests, GraphifyResult, Path, Best-effort graph refresh owned by the local orchestration layer., Refresh the primary repository graph without affecting task success., update_repository(), Single-run local agent orchestration without daemon or database dependencies., Refresh graph metadata after promotion without blocking the task.

### Community 43 - "._rebuild_plan_questions"
Cohesion: 0.26
Nodes (8): CallGraphTreeTests, group_candidate_features(), Group symbols connected by inclusive-threshold relations.      Parent/child dire, ScoredRelation, SimilarityResult, write_similarity_json(), Choose tree roots from configured entry points or orphan graph nodes., select_roots()

### Community 44 - "task_coordinator.py"
Cohesion: 0.12
Nodes (6): Pressed, Submitted, CreateTopicScreen, ProjectInitializerScreen, Collect a project slug and create a Daedalus-compatible directory., Collect the context needed to initialize and populate a topic file.

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
Cohesion: 0.12
Nodes (9): Ask for confirmation before scaffolding a shared Supabase schema., Open the selected project topic in a read-only modal., Return provider metadata from the shared controls for a new task., Queue a coding task that writes and expands the requested topic file., Push the Branch Select value for the active project to origin., Disable registration when the active project already claimed its schema., Make a newly submitted task the visible task in every mode., Keep one bad dynamic widget update from closing the entire TUI. (+1 more)

### Community 50 - ".test_plan_review_renders_literal_markup_like_agent_text"
Cohesion: 0.10
Nodes (4): TuiAppTests, DaedalusVimTextArea, VimTextArea with multiline prompt behavior and system clipboard sync., VimTextArea

### Community 51 - "CompactSettingsSelect"
Cohesion: 0.18
Nodes (3): ComposeResult, KeyboardShortcutsScreen, Modal reference for the app and prompt editor keyboard shortcuts.

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
Cohesion: 0.20
Nodes (13): Mount, ConfigTests, PlanAnswerSelect, Initialize dynamic plan selectors after their nested children mount., LayoutSettings, load_orchestration_settings(), load_tui_settings(), ModelOption (+5 more)

### Community 59 - "render_call_graph_tree"
Cohesion: 0.17
Nodes (8): Unit tests for AST variable-lineage analysis., build_tree(), datetime, Build a call tree from *root* with cycle and depth limits., Render candidate features independently from the similarity panel., Render a self-contained HTML page for the call trees., _render_candidate_features_panel(), render_html()

### Community 60 - "trading.py"
Cohesion: 0.32
Nodes (5): calculate(), execute_trade(), Portfolio, Assignment lineage, augassign, attribute mutate, and unique call mapping., run_pipeline()

### Community 61 - "CodingStatisticsScreen"
Cohesion: 0.21
Nodes (8): AgentControl, Cooperative stop signals shared by a task and its active subprocess., AgentStopped, Path, RuntimeError, Load a repository-owned profile immediately before building a prompt., Load a tagged topic from the task worktree immediately before a prompt., Expose usage only after the whole task reaches completion.

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
Cohesion: 0.11
Nodes (5): Agent plan text must not be parsed as Textual/Rich markup., Follow-up questions must not crash when old option ids linger on widgets., Deferred Select init must not fatal-exit on a leftover option id., Clearing questions after confirmation must keep the TUI alive., PlanOption

### Community 69 - "._set_status"
Cohesion: 0.07
Nodes (22): AbstractEventLoop, BaseException, Exception, Stop agents before an explicit Textual exit begins., Persist Textual failures that would otherwise only flash on screen., Cover terminal and event-loop exits that bypass Textual unmount., Run before ThreadPoolExecutor's internal interpreter-exit join., Clean up if Textual's run loop returns without its unmount hook. (+14 more)

### Community 70 - "debug_log.py"
Cohesion: 0.17
Nodes (6): CompactSettingsSelect, PlanClarificationScreen, Keep only the latest value-change event for rebuilt compact controls., Collect a clarification about one plan question., PlanClarification, A side-channel clarification about one plan question (not plan follow-up).

### Community 71 - "_collapse_inner_safe"
Cohesion: 0.15
Nodes (13): CallGraphVisitor, CallGraphConfig, _collapse_inner_safe(), _collect_node_names(), discover_source_files(), extract_uses_edges(), Any, Path (+5 more)

### Community 72 - "render_call_graph_tree.py"
Cohesion: 0.24
Nodes (14): _flat_parameter_values(), load_config(), _load_parameter_values(), load_runner_parameters(), main(), _project_root_setting(), _project_table(), Path (+6 more)

### Community 73 - "CandidateFeatureGroup"
Cohesion: 0.20
Nodes (8): CandidateFeatureGroup, A deterministic connected component of qualifying similarity relations., Return the stable identifier using the concise ``id`` spelling., Compatibility alias for callers that refer to group relations directly., _feature_ids_by_member(), CallGraphVisitor with a collapse_inner guard for namespace-less anonymous nodes., Map each grouped symbol to its stable candidate-feature ID., _SafeCallGraphVisitor

### Community 76 - ".action_view_topic"
Cohesion: 0.27
Nodes (4): Display a topic markdown file without allowing edits., TopicViewerScreen, CodingStatisticsSettings, load_coding_statistics_settings()

### Community 80 - ".edit_paste_after"
Cohesion: 0.17
Nodes (9): Textual interface for concurrent local agent tasks., copy_to_system_clipboard(), paste_from_system_clipboard(), System clipboard helpers for terminals without OSC 52 support., Read clipboard text using the native command available on the host., Selectable transcript rendering with semantic assistant-message emphasis., The Daedalus prompt's incremental Vim editing adapter., Paste Vim's register, falling back to the system clipboard. (+1 more)

### Community 82 - ".on_resize"
Cohesion: 0.40
Nodes (3): __getattr__(), Standalone Textual interface and local agent orchestration., OrchestrationResult

## Knowledge Gaps
- **106 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+101 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `._shutdown_coordinators` to `DaedalusVimTextArea`, `AgentRunner`, `GitWorktreeManager`, `Key`, `TaskRecord`, `._set_status`, `._set_status`, `CodingStatisticsScreen`, `calculate_token_usage`, `._set_status`, `._start_new_task`, `._render_line_strip`, `.test_plan_review_renders_literal_markup_like_agent_text`, `CompactSettingsSelect`, `update_repository`, `DescriptorEmbedder`, `._set_status`, `debug_log.py`, `.action_view_topic`, `.edit_paste_after`, `.on_data_table_row_selected`, `.on_resize`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Why does `TuiAppTests` connect `.test_plan_review_renders_literal_markup_like_agent_text` to `PlanQuestion`, `debug_log.py`, `Key`, `task_coordinator.py`, `.action_view_topic`, `.enter_insert_mode`, `CompactSettingsSelect`, `._shutdown_coordinators`, `update_repository`, `._set_status`, `DescriptorEmbedder`, `CodingStatisticsScreen`, `._set_status`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `TaskCoordinator` connect `DaedalusVimTextArea` to `AgentRunner`, `app.py`, `Key`, `TaskRecord`, `._shutdown_coordinators`, `._set_status`, `._set_status`, `calculate_token_usage`, `KeyboardShortcutsScreen`, `task_coordinator.py`, `CompactSettingsSelect`, `update_repository`, `DescriptorEmbedder`, `CodingStatisticsScreen`, `debug_log.py`, `.action_view_topic`, `.enter_insert_mode`, `.edit_paste_after`, `.on_resize`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `DaedalusTuiApp`) actually correct?**
  _`TuiAppTests` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 17 INFERRED edges - model-reasoned connections that need verification._