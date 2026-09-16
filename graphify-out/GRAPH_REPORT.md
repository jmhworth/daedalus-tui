# Graph Report - daedalus-tui  (2026-09-16)

## Corpus Check
- 91 files · ~78,804 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1640 nodes · 4369 edges · 80 communities (70 shown, 10 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 448 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0edbed54`
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
- .edit_paste_after

## God Nodes (most connected - your core abstractions)
1. `DaedalusTuiApp` - 166 edges
2. `TuiAppTests` - 110 edges
3. `TaskCoordinator` - 79 edges
4. `OrchestrationSettings` - 66 edges
5. `AgentRunner` - 62 edges
6. `TaskRecord` - 62 edges
7. `DaedalusVimTextArea` - 62 edges
8. `GitWorktreeManager` - 61 edges
9. `WorktreeContext` - 60 edges
10. `TaskMemoryStore` - 59 edges

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

## Communities (80 total, 10 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.18
Nodes (25): score_band(), _canonical_tree_name(), _collapse_inner_safe(), _collect_node_names(), _histogram_bars(), _layout_extent_y(), _layout_subtree(), _layout_trees() (+17 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.19
Nodes (5): FakeOrchestrator, TaskCoordinatorTests, OrchestrationSettings, Submit independent prompts while sharing a serialized integration gate., TaskCoordinator

### Community 2 - "AgentRunner"
Cohesion: 0.08
Nodes (13): OutputCallback, AgentRunnerTests, FakeProcess, FakeStream, InterruptibleProcess, Thread, AgentLogEvent, AgentRequest (+5 more)

### Community 3 - "DaedalusTuiApp"
Cohesion: 0.07
Nodes (43): AnnAssign, Assign, AsyncFunctionDef, Attribute, AugAssign, Call, ClassDef, comprehension (+35 more)

### Community 4 - "app.py"
Cohesion: 0.28
Nodes (5): OrchestratorTests, AgentResult, WorktreeContext, LocalOrchestrator, VerificationResult

### Community 5 - "TokenUsageStore"
Cohesion: 0.29
Nodes (6): Applying answers, Bridge Agent Profile, Build-loop tasking, cp_doc structure, Hard rules, Purpose

### Community 6 - "GitWorktreeManager"
Cohesion: 0.07
Nodes (17): Strip, Style, Text, _literal_select_options(), Build Select prompts that Rich will not parse as markup., Resize, Return the width available for transcript text inside the Log., Wrap one logical line at word boundaries when the width permits. (+9 more)

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
Cohesion: 0.15
Nodes (17): ProgressCallback, ProjectInitializerTests, find_github_url(), initialize_project(), load_initializer_settings(), matching_request_marker(), materialize_templates(), normalize_github_url() (+9 more)

### Community 21 - "._shutdown_coordinators"
Cohesion: 0.09
Nodes (13): Apply provider-specific model and reasoning choices to all controls., Avoid posting Select.Changed events when the options are unchanged., Return labels and values for one compact settings category., Read the current value from the same selectors used for submission., Populate the compact value Select while retaining its active category., Apply a compact value through the existing wide-control state., Update the project's coordinator so later submits use ``branch``., Remember the selected topic as the default for the active project. (+5 more)

### Community 22 - "._set_status"
Cohesion: 0.10
Nodes (23): Path, Unit tests for AST variable-lineage analysis., _sample_files(), build_tree(), CallGraphConfig, datetime, Build a call tree from *root* with cycle and depth limits., Render candidate features independently from the similarity panel. (+15 more)

### Community 23 - "update_repository"
Cohesion: 0.10
Nodes (31): build_symbol_contexts(), _descriptor_hash(), DescriptorEmbedder, _doc_for_definition(), extract_docs_for_symbols(), format_descriptor(), _format_name_list(), invert_edges() (+23 more)

### Community 24 - "Daedalus TUI Coding Statistics"
Cohesion: 0.29
Nodes (6): Daedalus TUI Coding Statistics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 25 - "._set_status"
Cohesion: 0.23
Nodes (6): Agent plan text must not be parsed as Textual/Rich markup., Follow-up questions must not crash when old option ids linger on widgets., Deferred Select init must not fatal-exit on a leftover option id., Clearing questions after confirmation must keep the TUI alive., PlanOption, PlanQuestion

### Community 26 - ".provider_split"
Cohesion: 0.13
Nodes (20): PlanTests, build_implementation_prompt(), build_plan_clarification_prompt(), build_plan_followup_prompt(), custom_answer_text(), encode_custom_answer(), is_valid_plan_answer(), parse_plan_response() (+12 more)

### Community 27 - ".on_mount"
Cohesion: 0.05
Nodes (31): Binding, ComposeResult, Pressed, Select, Submitted, CompactSettingsSelect, CreateTopicScreen, KeyboardShortcutsScreen (+23 more)

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.13
Nodes (13): GraphifyTests, Provider-specific subprocess execution with normalized agent messages., cursor_environment(), Return the process environment plus local Cursor credentials.      Explicit proc, GraphifyResult, Path, Best-effort graph refresh owned by the local orchestration layer., Refresh the primary repository graph without affecting task success. (+5 more)

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
Cohesion: 0.09
Nodes (8): Changed, DaedalusTuiApp, Run the wide-layout measurement after the next screen refresh., Keep a task visible after user activity during this launch., Prefer mounted selector values so clarification refreshes keep choices., Show either the full-size transcript or the full-size diagnostics log., Use Textual's OSC 52 path and a native clipboard fallback., __getattr__()

### Community 39 - "Daedalus Project Instructions"
Cohesion: 0.33
Nodes (5): Daedalus Project Instructions, graphify, Shared personal Supabase, Task mode, Topics

### Community 41 - "KeyboardShortcutsScreen"
Cohesion: 0.06
Nodes (73): EnvironmentTests, PersonalSupabaseTests, Path, _atomic_write(), _env_value(), EnvironmentSyncResult, Path, Small, dependency-free environment-file loading for local CLI providers. (+65 more)

### Community 42 - "debug_log.py"
Cohesion: 0.11
Nodes (22): Popen, Protocol, VerificationTests, Remove known credential values before diagnostics reach the UI or log., _redact_supabase_diagnostic(), Remove values loaded for a subprocess from a user-facing diagnostic., redact_environment_values(), Small local JSON stores for persistent task history. (+14 more)

### Community 43 - "._rebuild_plan_questions"
Cohesion: 0.15
Nodes (12): CallGraphTreeTests, candidate_feature_id(), group_candidate_features(), Lowercase and split identifiers on `.` / `_` while keeping word tokens., Return a stable ID derived solely from a group's sorted member symbols., Group symbols connected by inclusive-threshold relations.      Parent/child dire, ScoredRelation, SimilarityResult (+4 more)

### Community 44 - "CandidateFeatureGroup"
Cohesion: 0.25
Nodes (6): CandidateFeatureGroup, A deterministic connected component of qualifying similarity relations., Return the stable identifier using the concise ``id`` spelling., Compatibility alias for callers that refer to group relations directly., _feature_ids_by_member(), Map each grouped symbol to its stable candidate-feature ID.

### Community 45 - "KeyboardShortcutsScreen"
Cohesion: 0.20
Nodes (9): Constraints and Design Principles, Desired End State, Intended Import Workflow, Open Questions, Project Imports to the Daedalus Format, Scope and Durable Context, State Log, Topic Goal (+1 more)

### Community 46 - "._handle_visual_line_mode"
Cohesion: 0.14
Nodes (8): Key, Keep Enter as a newline; Ctrl+Enter remains the app submit key., Route visual-line mode and mirror new yanks to the host clipboard., Add Daedalus prompt commands that the dependency does not provide., Select the current line and enter Vim visual-line mode., Select every character in the lines between the start and cursor., Handle movement and operators while whole lines are selected., Expose operator-pending so the caret can become an underline.

### Community 47 - "DaedalusTuiApp"
Cohesion: 0.11
Nodes (10): RowSelected, Focus a task from the cross-project update inbox., Apply only the newest event per task to keep the UI responsive., Promote only events that need the user's attention in the inbox., Render actionable history and tasks created during this session., Keep failures, active work, and all tasks submitted in this launch., Keep inbox cells within their fixed width with a visible ellipsis., Switch the project context and focus a row selected in the inbox. (+2 more)

### Community 48 - "._persist_task"
Cohesion: 0.17
Nodes (8): Send selected plan answers back to the planning agent for confirmation., Ask a side-channel clarification about one plan question without plan follow-up., Run another planning pass while keeping the task in questioning., Promote a reviewed plan into the normal coding and verification route., Retry a failed agent request after connectivity or service recovery., Run an ask-mode clarification that does not mutate plan conversation state., Construct an orchestrator with the shared launch environment when configured., Persist task state, coalescing high-frequency streamed messages.

### Community 49 - "._render_line_strip"
Cohesion: 0.18
Nodes (8): Mount, PlanAnswerSelect, Initialize dynamic plan selectors after their nested children mount., Finish Select setup without allowing a stale value to exit the TUI.          Pla, Resolve a Select value that is legal for the current question options., Replace question controls after Textual has completed child removal., PlanClarification, A side-channel clarification about one plan question (not plan follow-up).

### Community 50 - "environment.py"
Cohesion: 0.18
Nodes (6): Resize, Apply the viewport-aware layout whenever the terminal changes size., Toggle responsive classes and dimensions after a viewport change.          ``com, Measure wide controls after their current layout pass completes., Switch to compact mode when wide controls extend past their bars., Return whether wide-layout controls are clipped or too narrow.

### Community 51 - "CompactSettingsSelect"
Cohesion: 0.07
Nodes (7): TuiAppTests, DaedalusVimTextArea, VimTextArea with multiline prompt behavior and system clipboard sync., Return bar, underline, or block for the current Vim state., Return to Insert mode after programmatic prompt operations., Move to the end of the current word, or the next word when needed., VimTextArea

### Community 52 - "Daedalus TUI Call Graph Visualization"
Cohesion: 0.29
Nodes (6): Daedalus TUI Call Graph Visualization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 53 - "b.py"
Cohesion: 0.10
Nodes (21): alpha(), Entry helper that fans out into order and UI branches., beta(), Continue the sample call chain toward gamma., gamma(), Leaf helper in the sample call chain., make_runner(), create_order() (+13 more)

### Community 54 - "update_repository"
Cohesion: 0.33
Nodes (4): CodingStatisticsScreen, _format_count(), _format_tokens(), Show token or task usage history and derived coding statistics.

### Community 55 - "conftest.py"
Cohesion: 0.50
Nodes (3): pytest_configure(), Pytest hooks shared across the test suite., Install pyan3 when call-graph tests run in an environment missing it.

### Community 57 - "DescriptorEmbedder"
Cohesion: 0.11
Nodes (22): ConfigTests, Textual interface for concurrent local agent tasks., Return Textual's event name for a user-facing shortcut label., _shortcut_binding_key(), copy_to_system_clipboard(), paste_from_system_clipboard(), System clipboard helpers for terminals without OSC 52 support., Read clipboard text using the native command available on the host. (+14 more)

### Community 59 - "PlanClarification"
Cohesion: 0.12
Nodes (5): FakeCoordinator, FakeRunner, settings(), DaedalusProject, A repository recognized by the presence of a ``feature_files`` folder.

### Community 60 - "trading.py"
Cohesion: 0.32
Nodes (5): calculate(), execute_trade(), Portfolio, Assignment lineage, augassign, attribute mutate, and unique call mapping., run_pipeline()

### Community 61 - "CodingStatisticsScreen"
Cohesion: 0.20
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

### Community 68 - "task_coordinator.py"
Cohesion: 0.13
Nodes (13): TaskEventCallback, IntegrationCoordinator, _nonnegative_int(), _phase_for_status(), Lock, Path, Concurrent task state and serialized local integration., Run ready integration operations one at a time in ready order. (+5 more)

### Community 69 - "PersonalSupabaseActivationProgressScreen"
Cohesion: 0.19
Nodes (7): PersonalSupabaseActivationProgressScreen, Finish a queued modal update only if its screen is still mounted., Show the durable activation phases while the worker runs., Whether the activation worker still owns this progress surface., Apply worker results that arrived while this modal was mounting., Freeze the progress display and allow the operator to close it., Render a completion state after all modal widgets are mounted.

### Community 70 - "TranscriptLog"
Cohesion: 0.25
Nodes (4): Recover review questions from the last persisted plan response., Create a new coding task from a confirmed plan review., Remove the clean, read-only planning worktree after coding is queued., TaskRecord

### Community 71 - "_collapse_inner_safe"
Cohesion: 0.21
Nodes (8): CallGraphVisitor, discover_source_files(), extract_uses_edges(), Path, CallGraphVisitor with a collapse_inner guard for namespace-less anonymous nodes., Run pyan analysis and return caller→callees edges plus all node names., Collect Python source files matching *source_globs* and not *exclude*., _SafeCallGraphVisitor

### Community 72 - "render_call_graph_tree.py"
Cohesion: 0.24
Nodes (14): _flat_parameter_values(), load_config(), _load_parameter_values(), load_runner_parameters(), main(), _project_root_setting(), _project_table(), Path (+6 more)

### Community 73 - "._on_personal_supabase_activation_progress"
Cohesion: 0.10
Nodes (9): Key, Add Vim-like navigation without changing TextArea insert behavior., Confirm, then scaffold (if needed) and Activate personal Supabase., Run scaffold+Activate in a background worker so the TUI stays responsive., Open the selected project topic in a read-only modal., Queue a coding task that writes and expands the requested topic file., Return the selected topic slug, or None for the blank option., Clear the selected task and unlock a fresh prompt editor. (+1 more)

### Community 74 - "__init__.py"
Cohesion: 0.14
Nodes (5): Log, Path, Return provider metadata from the shared controls for a new task., Memory override for the project, else the parameter-file default., Return only direct-child projects, or the empty-root fallback.

### Community 76 - "bootstrap_personal_supabase"
Cohesion: 0.40
Nodes (3): EventCallback, IntegrationGate, Lock

### Community 77 - "update_repository"
Cohesion: 0.22
Nodes (8): SupabaseMigrationsTests, migrations_pending(), push_migrations(), PushResult, Path, Orchestration-owned Supabase migration push for target project worktrees., Return True when the worktree differs from base under supabase/migrations/., Run non-interactive `supabase db push --yes` in the target worktree.

### Community 78 - "load_project_worktree_settings"
Cohesion: 0.40
Nodes (3): Forward worker phases to the modal and the main status line., Mark the current activation phase and retain a readable status line., Update mounted progress widgets for one worker phase.

### Community 80 - ".edit_paste_after"
Cohesion: 0.07
Nodes (24): AbstractEventLoop, BaseException, Exception, Pause active agents before ThreadPoolExecutor joins its workers.      CPython ex, Synchronize registered projects; push migrations only when activated., Stop agents before an explicit Textual exit begins., Persist Textual failures that would otherwise only flash on screen., Cover terminal and event-loop exits that bypass Textual unmount. (+16 more)

## Knowledge Gaps
- **107 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+102 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `._set_status` to `DaedalusVimTextArea`, `AgentRunner`, `._shutdown_coordinators`, `._set_status`, `.on_mount`, `CodingStatisticsScreen`, `calculate_token_usage`, `DaedalusTuiApp`, `._render_line_strip`, `environment.py`, `CompactSettingsSelect`, `DescriptorEmbedder`, `PlanClarification`, `PersonalSupabaseActivationProgressScreen`, `TranscriptLog`, `._on_personal_supabase_activation_progress`, `__init__.py`, `load_project_worktree_settings`, `.edit_paste_after`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Why does `TuiAppTests` connect `CompactSettingsSelect` to `PersonalSupabaseActivationProgressScreen`, `._set_status`, `TranscriptLog`, `.on_mount`, `._render_line_strip`, `update_repository`, `DescriptorEmbedder`, `PlanClarification`, `._set_status`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `TaskCoordinator` connect `DaedalusVimTextArea` to `AgentRunner`, `task_coordinator.py`, `PersonalSupabaseActivationProgressScreen`, `._set_status`, `app.py`, `TranscriptLog`, `__init__.py`, `Key`, `._persist_task`, `._render_line_strip`, `CodingStatisticsScreen`, `update_repository`, `._set_status`, `DescriptorEmbedder`, `.provider_split`, `.on_mount`, `CodingStatisticsScreen`, `calculate_token_usage`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `CreateTopicScreen`) actually correct?**
  _`TuiAppTests` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 17 INFERRED edges - model-reasoned connections that need verification._