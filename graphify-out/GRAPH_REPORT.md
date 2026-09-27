# Graph Report - daedalus-tui  (2026-09-27)

## Corpus Check
- 96 files · ~95,037 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1877 nodes · 5199 edges · 94 communities (75 shown, 19 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 595 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `facd6343`
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
- agent_runner.py
- push_branch
- .edit_paste_after
- debug_log.py
- paste_from_system_clipboard
- .cursor_shape
- .__init__
- ._on_command_menu_action
- ._schedule_responsive_measurement
- .cursor_shape
- .edit_paste_after
- PersonalSupabaseSetupWizardScreen
- remove_personal_supabase
- ._finish_personal_supabase_progress
- .on_mount
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

## Communities (94 total, 19 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.14
Nodes (32): CandidateFeatureGroup, A deterministic connected component of qualifying similarity relations., Return the stable identifier using the concise ``id`` spelling., score_band(), SimilarityResult, _canonical_tree_name(), _feature_ids_by_member(), _histogram_bars() (+24 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.04
Nodes (46): DaedalusTuiApp, Path, Remove known credential values before diagnostics reach the UI or log., Synchronize registered projects; push migrations only when activated., Toggle responsive classes and dimensions after a viewport change.          ``com, Measure wide controls after their current layout pass completes., Switch to compact mode when wide controls extend past their bars., Return whether wide-layout controls are clipped or too narrow. (+38 more)

### Community 2 - "AgentRunner"
Cohesion: 0.11
Nodes (7): FakeCoordinator, FakeRunner, settings(), PersonalSupabaseRemovalResult, Outcome of removing the local personal-Supabase integration artifacts., DaedalusProject, A repository recognized by the presence of a ``feature_files`` folder.

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
Cohesion: 0.08
Nodes (14): Strip, Style, Resize, Return the width available for transcript text inside the Log., Wrap one logical line at word boundaries when the width permits., Split an overlong word with visible hyphens at cell boundaries., Render a line with the final-message color before selection styling., Reflow stored messages when the output box changes width. (+6 more)

### Community 7 - "Daedalus TUI Local Token Usage Memory"
Cohesion: 0.29
Nodes (6): Daedalus TUI Local Persistent Memory, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 8 - "update_repository"
Cohesion: 0.07
Nodes (39): PromptTests, TopicsTests, build_migration_repair_prompt(), build_repair_prompt(), build_resolver_prompt(), build_sync_conflict_coding_prompt(), build_sync_conflict_plan_prompt(), build_task_prompt() (+31 more)

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
Cohesion: 0.08
Nodes (19): Pressed, ProgressCallback, Submitted, ProjectInitializerTests, find_github_url(), initialize_project(), load_initializer_settings(), matching_request_marker() (+11 more)

### Community 21 - "._shutdown_coordinators"
Cohesion: 0.16
Nodes (3): ComposeResult, Select, Return only direct-child projects, or the empty-root fallback.

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
Cohesion: 0.10
Nodes (13): AgentRunnerTests, FakeProcess, FakeStream, InterruptibleProcess, AgentLogEvent, AgentRequest, AgentRunner, Provider-specific subprocess execution with normalized agent messages. (+5 more)

### Community 26 - ".provider_split"
Cohesion: 0.17
Nodes (5): Text, _literal_select_options(), Build Select prompts that Rich will not parse as markup., Finish Select setup without allowing a stale value to exit the TUI.          Pla, Replace question controls after Textual has completed child removal.

### Community 27 - ".on_mount"
Cohesion: 0.20
Nodes (10): AgentControl, Cooperative stop signals shared by a task and its active subprocess., AgentStopped, OrchestrationResult, Path, RuntimeError, Plan or resolve Sync merge conflicts in a preserved sync worktree., Load a repository-owned profile immediately before building a prompt. (+2 more)

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.14
Nodes (17): Popen, Protocol, VerificationTests, discover_commands(), format_process_result(), package_has_test_script(), CompletedProcess, Path (+9 more)

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
Cohesion: 0.11
Nodes (7): AbstractEventLoop, BaseException, OutputCallback, Thread, Track an inactivity deadline that agent stdout can refresh., _TimeoutTracker, log_exception()

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
Cohesion: 0.15
Nodes (19): abort_sync_merge(), _create_isolated_sync_worktree(), _delete_branch_if_present(), finalize_sync_merge(), _force_remove_worktree(), _is_ancestor(), list_unmerged_paths(), pull_branch() (+11 more)

### Community 39 - "Daedalus Project Instructions"
Cohesion: 0.33
Nodes (5): Daedalus Project Instructions, graphify, Shared personal Supabase, Task mode, Topics

### Community 41 - "KeyboardShortcutsScreen"
Cohesion: 0.08
Nodes (47): _allow_list_comment(), _commit_paths(), commit_personal_supabase_scaffold(), _ensure_env_example(), _ensure_profile_guidance(), _ensure_supabase_scaffold(), _env_example_block(), _git_output() (+39 more)

### Community 42 - "debug_log.py"
Cohesion: 0.20
Nodes (13): CodexUsageTests, CodexUsageWindow, fetch_codex_usage(), _find_response(), _first_undimensioned_window(), parse_codex_usage(), _parse_reset(), _parse_window() (+5 more)

### Community 43 - "._rebuild_plan_questions"
Cohesion: 0.19
Nodes (8): PlanTests, Cursor may include prose and omit redundant false confirmation., parse_plan_response(), _payload_text(), _plan_payload_candidates(), Return every BEGIN/END plan blob, then fence/bare-object fallbacks., Compatibility helper: first plan payload candidate, if any., Extract the agent's plan payload without exposing protocol text in the UI.

### Community 44 - "CandidateFeatureGroup"
Cohesion: 0.26
Nodes (7): ProjectDiscoveryTests, discover_projects(), is_direct_child_project(), Path, Discovery of Daedalus-supported repositories beneath a launch root., Return whether ``path`` is an immediate child of ``launch_root``., Find immediate child folders containing a direct ``feature_files`` child.      G

### Community 45 - "KeyboardShortcutsScreen"
Cohesion: 0.20
Nodes (9): Constraints and Design Principles, Desired End State, Intended Import Workflow, Open Questions, Project Imports to the Daedalus Format, Scope and Durable Context, State Log, Topic Goal (+1 more)

### Community 46 - "._handle_visual_line_mode"
Cohesion: 0.14
Nodes (14): EnvironmentTests, apply_process_supabase_overrides(), cursor_environment(), Path, Small, dependency-free environment-file loading for local CLI providers., Return file values with non-empty process ``SUPABASE_*`` overrides applied., Remove values loaded for a subprocess from a user-facing diagnostic., Return ``.env`` beside the installed ``tui`` package root. (+6 more)

### Community 47 - "DaedalusTuiApp"
Cohesion: 0.14
Nodes (8): Key, Keep Enter as a newline; Ctrl+Enter remains the app submit key., Route visual-line mode and mirror new yanks to the host clipboard., Add Daedalus prompt commands that the dependency does not provide., Select the current line and enter Vim visual-line mode., Select every character in the lines between the start and cursor., Handle movement and operators while whole lines are selected., Expose operator-pending so the caret can become an underline.

### Community 48 - "._persist_task"
Cohesion: 0.05
Nodes (36): TaskEventCallback, FakeOrchestrator, TaskCoordinatorTests, OrchestrationSettings, IntegrationCoordinator, _nonnegative_int(), _phase_for_status(), Lock (+28 more)

### Community 49 - "._render_line_strip"
Cohesion: 0.32
Nodes (7): configure_debug_logging(), install_fault_handler(), _install_thread_exception_logging(), Path, Persistent diagnostics for failures that occur after the Textual screen closes., Write detailed runtime diagnostics to a rotating local log file., Capture fatal faults and ``SIGUSR1`` thread dumps in the debug log.

### Community 50 - "environment.py"
Cohesion: 0.29
Nodes (6): Daedalus TUI Command Menu, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 51 - "CompactSettingsSelect"
Cohesion: 0.22
Nodes (4): PersonalSupabaseTests, Path, Scaffold supabase files, env placeholders, profiles, and a ``.daedalus`` marker., register_personal_supabase()

### Community 52 - "Daedalus TUI Call Graph Visualization"
Cohesion: 0.29
Nodes (6): Daedalus TUI Call Graph Visualization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 53 - "b.py"
Cohesion: 0.10
Nodes (21): alpha(), Entry helper that fans out into order and UI branches., beta(), Continue the sample call chain toward gamma., gamma(), Leaf helper in the sample call chain., make_runner(), create_order() (+13 more)

### Community 55 - "conftest.py"
Cohesion: 0.50
Nodes (3): pytest_configure(), Pytest hooks shared across the test suite., Install pyan3 when call-graph tests run in an environment missing it.

### Community 57 - "DescriptorEmbedder"
Cohesion: 0.09
Nodes (28): Agent plan text must not be parsed as Textual/Rich markup., Follow-up questions must not crash when old option ids linger on widgets., Deferred Select init must not fatal-exit on a leftover option id., Clearing questions after confirmation must keep the TUI alive., Resolve a Select value that is legal for the current question options., build_implementation_prompt(), build_plan_clarification_prompt(), build_plan_followup_prompt() (+20 more)

### Community 59 - "PlanClarification"
Cohesion: 0.05
Nodes (63): Binding, Log, Mount, ConfigTests, CodingStatisticsScreen, CommandMenuScreen, CompactSettingsSelect, CreateTopicScreen (+55 more)

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
Cohesion: 0.25
Nodes (8): is_personal_supabase_activated(), is_personal_supabase_registered(), load_personal_supabase_status(), PersonalSupabaseStatus, Return the ``[personal_supabase]`` marker, or an unregistered default., Registration / activation marker loaded from a target project's ``.daedalus``., True when the project is marked registered for ``schema`` (or any schema if omit, True when the project is registered and activated for ``schema`` (or any).

### Community 69 - "log_exception"
Cohesion: 0.40
Nodes (3): EventCallback, IntegrationGate, Lock

### Community 70 - "GitWorktreeError"
Cohesion: 0.21
Nodes (8): GitWorktreeError, push_branch(), CompletedProcess, RuntimeError, Push a local branch to ``remote``, setting upstream with ``-u`` when needed., Install project resources and link declared shared read-only paths., Return whether ``remote`` is configured for ``repository``., remote_exists()

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
Cohesion: 0.16
Nodes (11): SupabaseMigrationsTests, _migration_directory_name(), migrations_pending(), MigrationSyncResult, push_migrations(), Path, Orchestration-owned Supabase migration push for target project worktrees., Link the selected project when needed, then run non-interactive `db push`. (+3 more)

### Community 80 - ".edit_paste_after"
Cohesion: 0.10
Nodes (33): main(), Child-process probe for project-local Supabase env key presence.  Invoke as ``py, activate_personal_supabase(), bootstrap_personal_supabase(), _direct_database_host_project_ref(), _first_filled_env_value(), _key_or_aliases_label(), load_personal_supabase_settings() (+25 more)

### Community 82 - "paste_from_system_clipboard"
Cohesion: 0.14
Nodes (4): Changed, _format_count(), _format_tokens(), Prefer mounted selector values so clarification refreshes keep choices.

### Community 83 - ".cursor_shape"
Cohesion: 0.20
Nodes (7): GraphifyTests, Path, Best-effort graph refresh owned by the local orchestration layer., Refresh the primary repository graph without affecting task success., update_repository(), Single-run local agent orchestration without daemon or database dependencies., Refresh graph metadata after promotion without blocking the task.

### Community 89 - "PersonalSupabaseSetupWizardScreen"
Cohesion: 0.25
Nodes (6): load_project_personal_supabase_env_values(), probe_project_personal_supabase_environment(), project_personal_supabase_env_path(), Return the project-local ``.env`` path operators must edit., Load values from the project ``.env`` only (no process overrides).      Wizard C, Check required project Supabase keys via a child process exit code.      The par

### Community 91 - "._finish_personal_supabase_progress"
Cohesion: 0.12
Nodes (10): PersonalSupabaseActivationProgressScreen, Forward worker phases to the modal and the main status line., Finish a queued modal update only if its screen is still mounted., Show the durable activation phases while the worker runs., Whether the activation worker still owns this progress surface., Apply worker results that arrived while this modal was mounting., Mark the current activation phase and retain a readable status line., Update mounted progress widgets for one worker phase. (+2 more)

### Community 93 - ".on_mount"
Cohesion: 0.10
Nodes (12): Exception, Pause active agents before ThreadPoolExecutor joins its workers.      CPython ex, Stop agents before an explicit Textual exit begins., Persist Textual failures that would otherwise only flash on screen., Cover terminal and event-loop exits that bypass Textual unmount., Run before ThreadPoolExecutor's internal interpreter-exit join., Clean up if Textual's run loop returns without its unmount hook., Idempotently detach task callbacks and request child-process shutdown. (+4 more)

### Community 99 - ".edit_paste_after"
Cohesion: 0.11
Nodes (9): Key, Add Vim-like navigation without changing TextArea insert behavior., Return a TextArea selection or the active screen selection., Use Textual's OSC 52 path and a native clipboard fallback., copy_to_system_clipboard(), paste_from_system_clipboard(), System clipboard helpers for terminals without OSC 52 support., Read clipboard text using the native command available on the host. (+1 more)

## Knowledge Gaps
- **117 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+112 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `DaedalusVimTextArea` to `AgentRunner`, `._shutdown_coordinators`, `._set_status`, `.provider_split`, `calculate_token_usage`, `.on_button_pressed`, `._persist_task`, `DescriptorEmbedder`, `PlanClarification`, `GitWorktreeError`, `bootstrap_personal_supabase`, `debug_log.py`, `paste_from_system_clipboard`, `.__init__`, `._on_command_menu_action`, `._schedule_responsive_measurement`, `._finish_personal_supabase_progress`, `.on_mount`, `.edit_paste_after`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Why does `AgentRunner` connect `._set_status` to `.on_button_pressed`, `DaedalusVimTextArea`, `log_exception`, `.on_mount`, `PlanClarification`, `._persist_task`, `.cursor_shape`, `._finish_personal_supabase_progress`, `CodingStatisticsScreen`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `TuiAppTests` connect `bootstrap_personal_supabase` to `DaedalusVimTextArea`, `AgentRunner`, `GitWorktreeError`, `PlanClarification`, `debug_log.py`, `._persist_task`, `DescriptorEmbedder`, `._finish_personal_supabase_progress`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `CommandMenuScreen`) actually correct?**
  _`TuiAppTests` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 19 INFERRED edges - model-reasoned connections that need verification._