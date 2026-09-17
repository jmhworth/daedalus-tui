# Graph Report - daedalus-tui  (2026-09-16)

## Corpus Check
- 92 files · ~82,170 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1716 nodes · 4627 edges · 95 communities (75 shown, 20 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 525 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6219f1d9`
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
- ProjectWorktreeSettings
- .edit_paste_after
- .enter_insert_mode
- .nav_word_end
- push_branch
- .edit_paste_before
- .__init__
- ._on_topic_created
- CandidateFeatureGroup
- ._render_line_strip
- PersonalSupabaseSetupWizardScreen
- list_local_branches
- _literal_select_options
- .remove_cancelled
- .reset_task_to_base
- .cursor_shape

## God Nodes (most connected - your core abstractions)
1. `DaedalusTuiApp` - 175 edges
2. `TuiAppTests` - 117 edges
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

## Communities (95 total, 20 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.18
Nodes (25): score_band(), _canonical_tree_name(), _collapse_inner_safe(), _collect_node_names(), _histogram_bars(), _layout_extent_y(), _layout_subtree(), _layout_trees() (+17 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.11
Nodes (8): Apply only the newest event per task to keep the UI responsive., Promote only events that need the user's attention in the inbox., Render actionable history and tasks created during this session., Keep failures, active work, and all tasks submitted in this launch., Keep inbox cells within their fixed width with a visible ellipsis., Make a newly submitted task the visible task in every mode., Keep one bad dynamic widget update from closing the entire TUI., Clear the selected task and unlock a fresh prompt editor.

### Community 2 - "AgentRunner"
Cohesion: 0.08
Nodes (18): Select, Resize, Apply the viewport-aware layout whenever the terminal changes size., Toggle responsive classes and dimensions after a viewport change.          ``com, Measure wide controls after their current layout pass completes., Apply provider-specific model and reasoning choices to all controls., Avoid posting Select.Changed events when the options are unchanged., Return labels and values for one compact settings category. (+10 more)

### Community 3 - "DaedalusTuiApp"
Cohesion: 0.07
Nodes (43): AnnAssign, Assign, AsyncFunctionDef, Attribute, AugAssign, Call, ClassDef, comprehension (+35 more)

### Community 4 - "app.py"
Cohesion: 0.29
Nodes (8): OrchestratorTests, AgentResult, WorktreeContext, GraphifyResult, LocalOrchestrator, OrchestrationSettings, PushResult, VerificationResult

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
Cohesion: 0.07
Nodes (33): PromptTests, TopicsTests, build_migration_repair_prompt(), build_repair_prompt(), build_resolver_prompt(), build_task_prompt(), build_topic_population_prompt(), _embedded_profile() (+25 more)

### Community 11 - "Key"
Cohesion: 0.13
Nodes (8): Path, Stage the current worktree contents for orchestration checks or commit., Remove graphify output changes from an agent worktree.          Graphify refresh, Commit only the generated graph after a successful primary update., Return a directory whose HEAD matches the target branch tip.          When the r, Remove a short-lived primary checkout created for post-promotion work., Ensure the configured target branch exists and is safe to integrate into., Compatibility alias for callers that used the original private helper.

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
Nodes (19): ProgressCallback, ProjectInitializerTests, copy_launch_environment(), find_github_url(), initialize_project(), load_initializer_settings(), matching_request_marker(), materialize_templates() (+11 more)

### Community 21 - "._shutdown_coordinators"
Cohesion: 0.10
Nodes (21): Binding, Mount, KeyboardShortcutsScreen, _LegacyCompatibleBinding, PlanAnswerSelect, PlanClarificationScreen, Display a topic markdown file without allowing edits., Expose the former four-item binding shape to local UI tests.      Textual 8 acce (+13 more)

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
Cohesion: 0.08
Nodes (13): OutputCallback, AgentRunnerTests, FakeProcess, FakeStream, InterruptibleProcess, Thread, AgentLogEvent, AgentRequest (+5 more)

### Community 26 - ".provider_split"
Cohesion: 0.11
Nodes (24): Clearing questions after confirmation must keep the TUI alive., PlanTests, Resolve a Select value that is legal for the current question options., build_implementation_prompt(), build_plan_clarification_prompt(), build_plan_followup_prompt(), custom_answer_text(), encode_custom_answer() (+16 more)

### Community 27 - ".on_mount"
Cohesion: 0.10
Nodes (6): Pressed, Submitted, PersonalSupabaseRemovalConfirmationScreen, ProjectInitializerScreen, Require an exact project-name confirmation before local cleanup., Collect a project slug and create a Daedalus-compatible directory.

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.23
Nodes (6): GraphifyTests, Path, Best-effort graph refresh owned by the local orchestration layer., Refresh the primary repository graph without affecting task success., update_repository(), Refresh graph metadata after promotion without blocking the task.

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
Cohesion: 0.29
Nodes (5): ProjectDiscoveryTests, discover_projects(), Path, Discovery of Daedalus-supported repositories beneath a launch root., Find immediate child folders containing a direct ``feature_files`` child.      G

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
Cohesion: 0.07
Nodes (10): AbstractEventLoop, DaedalusTuiApp, Run the wide-layout measurement after the next screen refresh., Run a command after the command menu has been removed., Finish Select setup without allowing a stale value to exit the TUI.          Pla, Keep a task visible after user activity during this launch., Prefer mounted selector values so clarification refreshes keep choices., Replace question controls after Textual has completed child removal. (+2 more)

### Community 39 - "Daedalus Project Instructions"
Cohesion: 0.33
Nodes (5): Daedalus Project Instructions, graphify, Shared personal Supabase, Task mode, Topics

### Community 41 - "KeyboardShortcutsScreen"
Cohesion: 0.05
Nodes (88): PersonalSupabaseTests, Path, activate_personal_supabase(), _allow_list_comment(), bootstrap_personal_supabase(), _commit_paths(), commit_personal_supabase_scaffold(), _ensure_env_example() (+80 more)

### Community 42 - "debug_log.py"
Cohesion: 0.13
Nodes (18): Popen, Protocol, VerificationTests, Small local JSON stores for persistent task history., discover_commands(), format_process_result(), package_has_test_script(), CompletedProcess (+10 more)

### Community 43 - "._rebuild_plan_questions"
Cohesion: 0.15
Nodes (12): CallGraphTreeTests, candidate_feature_id(), group_candidate_features(), Lowercase and split identifiers on `.` / `_` while keeping word tokens., Return a stable ID derived solely from a group's sorted member symbols., Group symbols connected by inclusive-threshold relations.      Parent/child dire, ScoredRelation, SimilarityResult (+4 more)

### Community 44 - "CandidateFeatureGroup"
Cohesion: 0.08
Nodes (12): Key, Synchronize registered projects; push migrations only when activated., Add Vim-like navigation without changing TextArea insert behavior., Confirm, then scaffold (if needed) and Activate personal Supabase., Confirm, then remove local personal-Supabase artifacts for the project., Scaffold files, then guide manual launch-root env setup before Activate., Run scaffold+Activate in a background worker so the TUI stays responsive., Return provider metadata from the shared controls for a new task. (+4 more)

### Community 45 - "KeyboardShortcutsScreen"
Cohesion: 0.20
Nodes (9): Constraints and Design Principles, Desired End State, Intended Import Workflow, Open Questions, Project Imports to the Daedalus Format, Scope and Durable Context, State Log, Topic Goal (+1 more)

### Community 46 - "._handle_visual_line_mode"
Cohesion: 0.14
Nodes (8): Key, Keep Enter as a newline; Ctrl+Enter remains the app submit key., Route visual-line mode and mirror new yanks to the host clipboard., Add Daedalus prompt commands that the dependency does not provide., Select the current line and enter Vim visual-line mode., Select every character in the lines between the start and cursor., Handle movement and operators while whole lines are selected., Expose operator-pending so the caret can become an underline.

### Community 47 - "DaedalusTuiApp"
Cohesion: 0.14
Nodes (3): ComposeResult, CreateTopicScreen, Collect the context needed to initialize and populate a topic file.

### Community 48 - "._persist_task"
Cohesion: 0.07
Nodes (15): TaskEventCallback, TaskCoordinatorTests, Recover review questions from the last persisted plan response., Submit independent prompts while sharing a serialized integration gate., Send selected plan answers back to the planning agent for confirmation., Ask a side-channel clarification about one plan question without plan follow-up., Create a new coding task from a confirmed plan review., Run another planning pass while keeping the task in questioning. (+7 more)

### Community 49 - "._render_line_strip"
Cohesion: 0.12
Nodes (3): Agent plan text must not be parsed as Textual/Rich markup., Follow-up questions must not crash when old option ids linger on widgets., Deferred Select init must not fatal-exit on a leftover option id.

### Community 50 - "environment.py"
Cohesion: 0.29
Nodes (6): Daedalus TUI Command Menu, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 52 - "Daedalus TUI Call Graph Visualization"
Cohesion: 0.29
Nodes (6): Daedalus TUI Call Graph Visualization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 53 - "b.py"
Cohesion: 0.10
Nodes (21): alpha(), Entry helper that fans out into order and UI branches., beta(), Continue the sample call chain toward gamma., gamma(), Leaf helper in the sample call chain., make_runner(), create_order() (+13 more)

### Community 54 - "update_repository"
Cohesion: 0.31
Nodes (4): CodingStatisticsScreen, _format_count(), _format_tokens(), Show token or task usage history and derived coding statistics.

### Community 55 - "conftest.py"
Cohesion: 0.50
Nodes (3): pytest_configure(), Pytest hooks shared across the test suite., Install pyan3 when call-graph tests run in an environment missing it.

### Community 57 - "DescriptorEmbedder"
Cohesion: 0.14
Nodes (19): ConfigTests, CommandMenuScreen, CompactSettingsSelect, Textual interface for concurrent local agent tasks., Return Textual's event name for a user-facing shortcut label., Keep only the latest value-change event for rebuilt compact controls., Offer low-frequency actions as discoverable buttons., _shortcut_binding_key() (+11 more)

### Community 59 - "PlanClarification"
Cohesion: 0.11
Nodes (8): FakeCoordinator, FakeRunner, settings(), ModelOption, PersonalSupabaseRemovalResult, Outcome of removing the local personal-Supabase integration artifacts., DaedalusProject, A repository recognized by the presence of a ``feature_files`` folder.

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
Cohesion: 0.12
Nodes (15): FakeOrchestrator, Local Git worktree lifecycle used by the standalone orchestrator., OrchestrationResult, IntegrationCoordinator, _nonnegative_int(), _phase_for_status(), Lock, Path (+7 more)

### Community 69 - "PersonalSupabaseActivationProgressScreen"
Cohesion: 0.18
Nodes (7): PersonalSupabaseActivationProgressScreen, Finish a queued modal update only if its screen is still mounted., Show the durable activation phases while the worker runs., Whether the activation worker still owns this progress surface., Apply worker results that arrived while this modal was mounting., Freeze the progress display and allow the operator to close it., Render a completion state after all modal widgets are mounted.

### Community 71 - "_collapse_inner_safe"
Cohesion: 0.21
Nodes (8): CallGraphVisitor, discover_source_files(), extract_uses_edges(), Path, CallGraphVisitor with a collapse_inner guard for namespace-less anonymous nodes., Run pyan analysis and return caller→callees edges plus all node names., Collect Python source files matching *source_globs* and not *exclude*., _SafeCallGraphVisitor

### Community 72 - "render_call_graph_tree.py"
Cohesion: 0.24
Nodes (14): _flat_parameter_values(), load_config(), _load_parameter_values(), load_runner_parameters(), main(), _project_root_setting(), _project_table(), Path (+6 more)

### Community 74 - "__init__.py"
Cohesion: 0.10
Nodes (12): Exception, Pause active agents before ThreadPoolExecutor joins its workers.      CPython ex, Stop agents before an explicit Textual exit begins., Persist Textual failures that would otherwise only flash on screen., Cover terminal and event-loop exits that bypass Textual unmount., Run before ThreadPoolExecutor's internal interpreter-exit join., Clean up if Textual's run loop returns without its unmount hook., Idempotently detach task callbacks and request child-process shutdown. (+4 more)

### Community 76 - "bootstrap_personal_supabase"
Cohesion: 0.09
Nodes (4): TuiAppTests, DaedalusVimTextArea, VimTextArea with multiline prompt behavior and system clipboard sync., VimTextArea

### Community 77 - "update_repository"
Cohesion: 0.23
Nodes (7): SupabaseMigrationsTests, migrations_pending(), push_migrations(), Path, Orchestration-owned Supabase migration push for target project worktrees., Return True when the worktree differs from base under supabase/migrations/., Run non-interactive `supabase db push --yes` in the target worktree.

### Community 78 - "load_project_worktree_settings"
Cohesion: 0.40
Nodes (3): Forward worker phases to the modal and the main status line., Mark the current activation phase and retain a readable status line., Update mounted progress widgets for one worker phase.

### Community 79 - "ProjectWorktreeSettings"
Cohesion: 0.24
Nodes (8): ProjectConfigTests, load_project_worktree_settings(), ProjectWorktreeSettings, Path, Configuration supplied by a target project to prepare task worktrees., Install and shared-path settings from a target project's .daedalus file., Load optional worktree provisioning settings from a target repository., _string_array()

### Community 80 - ".edit_paste_after"
Cohesion: 0.09
Nodes (24): BaseException, EnvironmentTests, Provider-specific subprocess execution with normalized agent messages., configure_debug_logging(), install_fault_handler(), _install_thread_exception_logging(), log_exception(), Path (+16 more)

### Community 81 - ".enter_insert_mode"
Cohesion: 0.20
Nodes (7): copy_to_system_clipboard(), paste_from_system_clipboard(), System clipboard helpers for terminals without OSC 52 support., Read clipboard text using the native command available on the host., The Daedalus prompt's incremental Vim editing adapter., Paste Vim's register, falling back to the system clipboard., Paste before the cursor, including from the system clipboard.

### Community 82 - ".nav_word_end"
Cohesion: 0.12
Nodes (10): Log, RowSelected, Path, Focus a task from the cross-project update inbox., Memory override for the project, else the parameter-file default., Update the project's coordinator so later submits use ``branch``., Return only direct-child projects, or the empty-root fallback., Switch the project context and focus a row selected in the inbox. (+2 more)

### Community 83 - "push_branch"
Cohesion: 0.14
Nodes (6): push_branch(), CompletedProcess, Install project resources and link declared shared read-only paths., Return whether ``remote`` is configured for ``repository``., Push a local branch to ``remote``, setting upstream with ``-u`` when needed., remote_exists()

### Community 84 - ".edit_paste_before"
Cohesion: 0.22
Nodes (3): Changed, PersonalSupabaseConfirmationScreen, Require an explicit confirmation before scaffolding/Activating a shared schema.

### Community 87 - "CandidateFeatureGroup"
Cohesion: 0.25
Nodes (6): CandidateFeatureGroup, A deterministic connected component of qualifying similarity relations., Return the stable identifier using the concise ``id`` spelling., Compatibility alias for callers that refer to group relations directly., _feature_ids_by_member(), Map each grouped symbol to its stable candidate-feature ID.

### Community 88 - "._render_line_strip"
Cohesion: 0.33
Nodes (4): Strip, Style, Render a line with the final-message color before selection styling., Render the native cursor without a background in visible modes.

### Community 91 - "_literal_select_options"
Cohesion: 0.67
Nodes (3): Text, _literal_select_options(), Build Select prompts that Rich will not parse as markup.

## Knowledge Gaps
- **112 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+107 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `._set_status` to `DaedalusVimTextArea`, `AgentRunner`, `GitWorktreeManager`, `._shutdown_coordinators`, `._set_status`, `.provider_split`, `calculate_token_usage`, `CandidateFeatureGroup`, `._persist_task`, `CompactSettingsSelect`, `DescriptorEmbedder`, `PlanClarification`, `PersonalSupabaseActivationProgressScreen`, `TranscriptLog`, `__init__.py`, `bootstrap_personal_supabase`, `load_project_worktree_settings`, `.edit_paste_after`, `.nav_word_end`?**
  _High betweenness centrality (0.140) - this node is a cross-community bridge._
- **Why does `TuiAppTests` connect `bootstrap_personal_supabase` to `PersonalSupabaseSetupWizardScreen`, `PersonalSupabaseActivationProgressScreen`, `._set_status`, `.on_mount`, `DaedalusTuiApp`, `._render_line_strip`, `.edit_paste_before`, `._shutdown_coordinators`, `update_repository`, `DescriptorEmbedder`, `.provider_split`, `PlanClarification`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Why does `AgentRunner` connect `._set_status` to `PersonalSupabaseSetupWizardScreen`, `app.py`, `PersonalSupabaseActivationProgressScreen`, `._set_status`, `task_coordinator.py`, `DaedalusTuiApp`, `.edit_paste_after`, `._persist_task`, `.edit_paste_before`, `._shutdown_coordinators`, `update_repository`, `DescriptorEmbedder`, `.on_mount`, `CodingStatisticsScreen`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `CommandMenuScreen`) actually correct?**
  _`TuiAppTests` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 28 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 18 INFERRED edges - model-reasoned connections that need verification._