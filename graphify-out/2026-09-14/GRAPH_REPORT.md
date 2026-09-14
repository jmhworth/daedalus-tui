# Graph Report - daedalus-tui  (2026-09-14)

## Corpus Check
- 91 files · ~74,765 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1574 nodes · 4120 edges · 79 communities (67 shown, 12 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 407 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `02135417`
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
- .nav_word_end
- .edit_paste_after
- .on_resize

## God Nodes (most connected - your core abstractions)
1. `DaedalusTuiApp` - 159 edges
2. `TuiAppTests` - 102 edges
3. `TaskCoordinator` - 78 edges
4. `OrchestrationSettings` - 66 edges
5. `GitWorktreeManager` - 61 edges
6. `TaskRecord` - 61 edges
7. `DaedalusVimTextArea` - 61 edges
8. `AgentRunner` - 60 edges
9. `WorktreeContext` - 60 edges
10. `TaskMemoryStore` - 58 edges

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

## Communities (79 total, 12 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.18
Nodes (25): score_band(), _canonical_tree_name(), _collapse_inner_safe(), _collect_node_names(), _histogram_bars(), _layout_extent_y(), _layout_subtree(), _layout_trees() (+17 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.13
Nodes (13): PlanClarification, A side-channel clarification about one plan question (not plan follow-up)., Send selected plan answers back to the planning agent for confirmation., Ask a side-channel clarification about one plan question without plan follow-up., Create a new coding task from a confirmed plan review., Run another planning pass while keeping the task in questioning., Promote a reviewed plan into the normal coding and verification route., Retry a failed agent request after connectivity or service recovery. (+5 more)

### Community 2 - "AgentRunner"
Cohesion: 0.06
Nodes (29): OutputCallback, AgentRunnerTests, FakeProcess, FakeStream, InterruptibleProcess, EnvironmentTests, Thread, AgentLogEvent (+21 more)

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
Cohesion: 0.10
Nodes (14): Show either the full-size transcript or the full-size diagnostics log., Resize, Return the width available for transcript text inside the Log., Wrap one logical line at word boundaries when the width permits., A selectable log that can emphasize a task's final assistant message.      ``Log, Split an overlong word with visible hyphens at cell boundaries., Return the tone assigned to each rendered transcript line., Reflow stored messages when the output box changes width. (+6 more)

### Community 7 - "Daedalus TUI Local Token Usage Memory"
Cohesion: 0.29
Nodes (6): Daedalus TUI Local Persistent Memory, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 8 - "update_repository"
Cohesion: 0.14
Nodes (19): TopicsTests, build_topic_instructions(), build_topic_template(), embed_topic(), list_topic_slugs(), load_topic_text(), Path, Topic file discovery, creation, loading, and prompt embedding. (+11 more)

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
Cohesion: 0.08
Nodes (15): AbstractEventLoop, BaseException, RowSelected, Focus a task from the cross-project update inbox., Apply only the newest event per task to keep the UI responsive., Promote only events that need the user's attention in the inbox., Finish Select setup without allowing a stale value to exit the TUI.          Pla, Render actionable history and tasks created during this session. (+7 more)

### Community 21 - "._shutdown_coordinators"
Cohesion: 0.08
Nodes (10): Changed, DaedalusTuiApp, Key, Add Vim-like navigation without changing TextArea insert behavior., Run the wide-layout measurement after the next screen refresh., Keep a task visible after user activity during this launch., Prefer mounted selector values so clarification refreshes keep choices., Replace question controls after Textual has completed child removal. (+2 more)

### Community 22 - "._set_status"
Cohesion: 0.09
Nodes (18): TaskEventCallback, FakeOrchestrator, __getattr__(), Standalone Textual interface and local agent orchestration., OrchestrationResult, IntegrationCoordinator, _nonnegative_int(), _phase_for_status() (+10 more)

### Community 23 - "update_repository"
Cohesion: 0.10
Nodes (31): build_symbol_contexts(), _descriptor_hash(), DescriptorEmbedder, _doc_for_definition(), extract_docs_for_symbols(), format_descriptor(), _format_name_list(), invert_edges() (+23 more)

### Community 24 - "Daedalus TUI Coding Statistics"
Cohesion: 0.29
Nodes (6): Daedalus TUI Coding Statistics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 25 - "._set_status"
Cohesion: 0.14
Nodes (19): PlanTests, Resolve a Select value that is legal for the current question options., build_implementation_prompt(), build_plan_clarification_prompt(), build_plan_followup_prompt(), custom_answer_text(), encode_custom_answer(), is_valid_plan_answer() (+11 more)

### Community 26 - ".provider_split"
Cohesion: 0.21
Nodes (4): TaskCoordinatorTests, OrchestrationSettings, Submit independent prompts while sharing a serialized integration gate., TaskCoordinator

### Community 27 - ".on_mount"
Cohesion: 0.05
Nodes (44): Popen, Protocol, GraphifyTests, PromptTests, SupabaseMigrationsTests, VerificationTests, Remove known credential values before diagnostics reach the UI or log., _redact_supabase_diagnostic() (+36 more)

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.09
Nodes (12): Mount, FakeCoordinator, FakeRunner, settings(), PlanAnswerSelect, Initialize dynamic plan selectors after their nested children mount., Display a topic markdown file without allowing edits., TopicViewerScreen (+4 more)

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
Cohesion: 0.19
Nodes (7): Log, Select, Synchronize and optionally push every registered discovered project., Avoid posting Select.Changed events when the options are unchanged., Return only direct-child projects, or the empty-root fallback., is_direct_child_project(), Return whether ``path`` is an immediate child of ``launch_root``.

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
Cohesion: 0.11
Nodes (12): Path, Apply provider-specific model and reasoning choices to all controls., Return labels and values for one compact settings category., Read the current value from the same selectors used for submission., Populate the compact value Select while retaining its active category., Apply a compact value through the existing wide-control state., Memory override for the project, else the parameter-file default., Update the project's coordinator so later submits use ``branch``. (+4 more)

### Community 39 - "Daedalus Project Instructions"
Cohesion: 0.33
Nodes (5): Daedalus Project Instructions, graphify, Shared personal Supabase, Task mode, Topics

### Community 41 - "KeyboardShortcutsScreen"
Cohesion: 0.06
Nodes (56): ProgressCallback, PersonalSupabaseTests, Path, ProjectInitializerTests, _allow_list_comment(), bootstrap_personal_supabase(), _ensure_env_example(), _ensure_profile_guidance() (+48 more)

### Community 42 - "debug_log.py"
Cohesion: 0.22
Nodes (7): Strip, Style, Text, _literal_select_options(), Build Select prompts that Rich will not parse as markup., Render a line with the final-message color before selection styling., Render the native cursor without a background in visible modes.

### Community 43 - "._rebuild_plan_questions"
Cohesion: 0.15
Nodes (12): CallGraphTreeTests, candidate_feature_id(), group_candidate_features(), Lowercase and split identifiers on `.` / `_` while keeping word tokens., Return a stable ID derived solely from a group's sorted member symbols., Group symbols connected by inclusive-threshold relations.      Parent/child dire, ScoredRelation, SimilarityResult (+4 more)

### Community 44 - "task_coordinator.py"
Cohesion: 0.06
Nodes (11): ComposeResult, Pressed, Submitted, CreateTopicScreen, PersonalSupabaseConfirmationScreen, PlanClarificationScreen, ProjectInitializerScreen, Collect a clarification about one plan question. (+3 more)

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
Cohesion: 0.29
Nodes (5): ProjectDiscoveryTests, discover_projects(), Path, Discovery of Daedalus-supported repositories beneath a launch root., Find immediate child folders containing a direct ``feature_files`` child.      G

### Community 49 - "._render_line_strip"
Cohesion: 0.12
Nodes (8): Ask for confirmation before scaffolding a shared Supabase schema., Open the selected project topic in a read-only modal., Return provider metadata from the shared controls for a new task., Queue a coding task that writes and expands the requested topic file., Enable Push only when an origin remote and operating branch are available., Push the Branch Select value for the active project to origin., Return the selected topic slug, or None for the blank option., Clear the selected task and unlock a fresh prompt editor.

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
Cohesion: 0.15
Nodes (8): Binding, CodingStatisticsScreen, _format_count(), _format_tokens(), _LegacyCompatibleBinding, Expose the former four-item binding shape to local UI tests.      Textual 8 acce, Show token or task usage history and derived coding statistics., CodingStatisticsSettings

### Community 55 - "conftest.py"
Cohesion: 0.50
Nodes (3): pytest_configure(), Pytest hooks shared across the test suite., Install pyan3 when call-graph tests run in an environment missing it.

### Community 57 - "DescriptorEmbedder"
Cohesion: 0.27
Nodes (9): ConfigTests, LayoutSettings, load_coding_statistics_settings(), load_orchestration_settings(), load_tui_settings(), _options(), Path, Read-only configuration for the standalone TUI. (+1 more)

### Community 59 - "render_call_graph_tree"
Cohesion: 0.10
Nodes (23): Path, Unit tests for AST variable-lineage analysis., _sample_files(), build_tree(), CallGraphConfig, datetime, Build a call tree from *root* with cycle and depth limits., Render candidate features independently from the similarity panel. (+15 more)

### Community 60 - "trading.py"
Cohesion: 0.32
Nodes (5): calculate(), execute_trade(), Portfolio, Assignment lineage, augassign, attribute mutate, and unique call mapping., run_pipeline()

### Community 61 - "CodingStatisticsScreen"
Cohesion: 0.14
Nodes (12): EventCallback, IntegrationGate, AgentControl, Cooperative stop signals shared by a task and its active subprocess., AgentStopped, Lock, Path, RuntimeError (+4 more)

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
Cohesion: 0.16
Nodes (8): Agent plan text must not be parsed as Textual/Rich markup., Follow-up questions must not crash when old option ids linger on widgets., Deferred Select init must not fatal-exit on a leftover option id., Clearing questions after confirmation must keep the TUI alive., _parse_question(), PlanOption, PlanQuestion, Any

### Community 69 - "._set_status"
Cohesion: 0.12
Nodes (10): Exception, Stop agents before an explicit Textual exit begins., Persist Textual failures that would otherwise only flash on screen., Cover terminal and event-loop exits that bypass Textual unmount., Run before ThreadPoolExecutor's internal interpreter-exit join., Clean up if Textual's run loop returns without its unmount hook., Idempotently detach task callbacks and request child-process shutdown., Pause active agents before ThreadPoolExecutor joins its workers.      CPython ex (+2 more)

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
Cohesion: 0.29
Nodes (6): load_topic_settings(), Load tunable limits for topic creation from the paired parameter file., Return a display name suitable for an H1 and a filesystem slug., Convert a validated topic name to the filename stem used by the TUI., topic_slug_from_name(), validate_topic_name()

### Community 79 - ".nav_word_end"
Cohesion: 0.20
Nodes (3): Return bar, underline, or block for the current Vim state., Return to Insert mode after programmatic prompt operations., Move to the end of the current word, or the next word when needed.

### Community 80 - ".edit_paste_after"
Cohesion: 0.13
Nodes (11): Textual interface for concurrent local agent tasks., _unregister_app_for_thread_exit(), copy_to_system_clipboard(), paste_from_system_clipboard(), System clipboard helpers for terminals without OSC 52 support., Read clipboard text using the native command available on the host., close_fault_handler(), Selectable transcript rendering with semantic assistant-message emphasis. (+3 more)

### Community 82 - ".on_resize"
Cohesion: 0.32
Nodes (7): configure_debug_logging(), install_fault_handler(), _install_thread_exception_logging(), Path, Persistent diagnostics for failures that occur after the Textual screen closes., Write detailed runtime diagnostics to a rotating local log file., Capture fatal faults and ``SIGUSR1`` thread dumps in the debug log.

## Knowledge Gaps
- **107 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+102 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `._shutdown_coordinators` to `DaedalusVimTextArea`, `AgentRunner`, `GitWorktreeManager`, `Key`, `TaskRecord`, `._set_status`, `._set_status`, `.provider_split`, `CodingStatisticsScreen`, `calculate_token_usage`, `.on_button_pressed`, `._set_status`, `KeyboardShortcutsScreen`, `task_coordinator.py`, `._start_new_task`, `._render_line_strip`, `.test_plan_review_renders_literal_markup_like_agent_text`, `CompactSettingsSelect`, `update_repository`, `PlanQuestion`, `._set_status`, `.edit_paste_after`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Why does `TuiAppTests` connect `.test_plan_review_renders_literal_markup_like_agent_text` to `DaedalusVimTextArea`, `PlanQuestion`, `Key`, `task_coordinator.py`, `CompactSettingsSelect`, `._shutdown_coordinators`, `update_repository`, `DescriptorEmbedder`, `CodingStatisticsScreen`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `DaedalusVimTextArea` connect `.test_plan_review_renders_literal_markup_like_agent_text` to `.on_button_pressed`, `debug_log.py`, `._set_status`, `GitWorktreeManager`, `debug_log.py`, `task_coordinator.py`, `._handle_visual_line_mode`, `._start_new_task`, `.edit_paste_after`, `.nav_word_end`, `CompactSettingsSelect`, `._shutdown_coordinators`, `update_repository`, `CodingStatisticsScreen`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `DaedalusTuiApp`) actually correct?**
  _`TuiAppTests` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 17 INFERRED edges - model-reasoned connections that need verification._