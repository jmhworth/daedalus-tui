# Graph Report - daedalus-tui  (2026-09-26)

## Corpus Check
- 96 files · ~92,098 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1861 nodes · 5147 edges · 95 communities (77 shown, 18 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 595 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `41237804`
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
- .on_mount
- ._apply_responsive_layout
- .submit_sync_recovery
- ._update_plan_state

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

## Communities (95 total, 18 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.14
Nodes (32): CandidateFeatureGroup, A deterministic connected component of qualifying similarity relations., Return the stable identifier using the concise ``id`` spelling., score_band(), SimilarityResult, _canonical_tree_name(), _feature_ids_by_member(), _histogram_bars() (+24 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.05
Nodes (26): Exception, DaedalusTuiApp, Key, Remove known credential values before diagnostics reach the UI or log., Synchronize registered projects; push migrations only when activated., Add Vim-like navigation without changing TextArea insert behavior., Run the wide-layout measurement after the next screen refresh., Persist Textual failures that would otherwise only flash on screen. (+18 more)

### Community 2 - "AgentRunner"
Cohesion: 0.07
Nodes (26): Mount, FakeCoordinator, FakeRunner, settings(), PersonalSupabaseActivationProgressScreen, PersonalSupabaseSetupWizardScreen, PlanAnswerSelect, Display a topic markdown file without allowing edits. (+18 more)

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
Cohesion: 0.14
Nodes (17): ProgressCallback, ProjectInitializerTests, find_github_url(), initialize_project(), load_initializer_settings(), matching_request_marker(), materialize_templates(), normalize_github_url() (+9 more)

### Community 21 - "._shutdown_coordinators"
Cohesion: 0.16
Nodes (12): EventCallback, IntegrationGate, AgentControl, Cooperative stop signals shared by a task and its active subprocess., AgentStopped, Lock, Path, RuntimeError (+4 more)

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
Nodes (26): OutputCallback, AgentRunnerTests, FakeProcess, FakeStream, InterruptibleProcess, EnvironmentTests, Thread, AgentLogEvent (+18 more)

### Community 26 - ".provider_split"
Cohesion: 0.17
Nodes (8): Persist task state, coalescing high-frequency streamed messages., Send selected plan answers back to the planning agent for confirmation., Ask a side-channel clarification about one plan question without plan follow-up., Auto-start coding in the same conflict worktree after a confirmed sync plan., Run another planning pass while keeping the task in questioning., Promote a reviewed plan into the normal coding and verification route., Retry a failed agent request after connectivity or service recovery., Abort the preserved sync merge and remove its worktree/temp branch.

### Community 27 - ".on_mount"
Cohesion: 0.14
Nodes (17): Popen, Protocol, VerificationTests, discover_commands(), format_process_result(), package_has_test_script(), CompletedProcess, Path (+9 more)

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.10
Nodes (17): AbstractEventLoop, BaseException, GraphifyTests, Provider-specific subprocess execution with normalized agent messages., log_exception(), Persistent diagnostics for failures that occur after the Textual screen closes., GraphifyResult, Path (+9 more)

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
Cohesion: 0.12
Nodes (26): abort_sync_merge(), _create_isolated_sync_worktree(), _delete_branch_if_present(), finalize_sync_merge(), _force_remove_worktree(), _is_ancestor(), list_local_branches(), list_unmerged_paths() (+18 more)

### Community 39 - "Daedalus Project Instructions"
Cohesion: 0.33
Nodes (5): Daedalus Project Instructions, graphify, Shared personal Supabase, Task mode, Topics

### Community 41 - "KeyboardShortcutsScreen"
Cohesion: 0.15
Nodes (32): activate_personal_supabase(), _allow_list_comment(), bootstrap_personal_supabase(), _commit_paths(), commit_personal_supabase_scaffold(), _ensure_env_example(), _ensure_supabase_scaffold(), _env_example_block() (+24 more)

### Community 42 - "debug_log.py"
Cohesion: 0.18
Nodes (6): Log, Return only direct-child projects, or the empty-root fallback., Selectable transcript rendering with semantic assistant-message emphasis., A selectable log that can emphasize a task's final assistant message.      ``Log, Return the tone assigned to each rendered transcript line., TranscriptLog

### Community 44 - "CandidateFeatureGroup"
Cohesion: 0.07
Nodes (17): Path, Resize, Apply the viewport-aware layout whenever the terminal changes size., Toggle responsive classes and dimensions after a viewport change.          ``com, Measure wide controls after their current layout pass completes., Apply provider-specific model and reasoning choices to all controls., Avoid posting Select.Changed events when the options are unchanged., Return labels and values for one compact settings category. (+9 more)

### Community 45 - "KeyboardShortcutsScreen"
Cohesion: 0.20
Nodes (9): Constraints and Design Principles, Desired End State, Intended Import Workflow, Open Questions, Project Imports to the Daedalus Format, Scope and Durable Context, State Log, Topic Goal (+1 more)

### Community 46 - "._handle_visual_line_mode"
Cohesion: 0.11
Nodes (25): CodexUsageTests, ConfigTests, CodexUsageWindow, fetch_codex_usage(), _find_response(), _first_undimensioned_window(), parse_codex_usage(), _parse_reset() (+17 more)

### Community 47 - "DaedalusTuiApp"
Cohesion: 0.14
Nodes (8): Key, Keep Enter as a newline; Ctrl+Enter remains the app submit key., Route visual-line mode and mirror new yanks to the host clipboard., Add Daedalus prompt commands that the dependency does not provide., Select the current line and enter Vim visual-line mode., Select every character in the lines between the start and cursor., Handle movement and operators while whole lines are selected., Expose operator-pending so the caret can become an underline.

### Community 48 - "._persist_task"
Cohesion: 0.12
Nodes (3): TaskCoordinatorTests, Submit independent prompts while sharing a serialized integration gate., TaskCoordinator

### Community 49 - "._render_line_strip"
Cohesion: 0.17
Nodes (5): Text, _literal_select_options(), Build Select prompts that Rich will not parse as markup., Finish Select setup without allowing a stale value to exit the TUI.          Pla, Replace question controls after Textual has completed child removal.

### Community 50 - "environment.py"
Cohesion: 0.29
Nodes (6): Daedalus TUI Command Menu, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 51 - "CompactSettingsSelect"
Cohesion: 0.23
Nodes (6): PersonalSupabaseTests, Path, Outcome of scaffolding personal-Supabase files into a project tree., Scaffold supabase files, env placeholders, profiles, and a ``.daedalus`` marker., register_personal_supabase(), RegistrationResult

### Community 52 - "Daedalus TUI Call Graph Visualization"
Cohesion: 0.29
Nodes (6): Daedalus TUI Call Graph Visualization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 53 - "b.py"
Cohesion: 0.10
Nodes (21): alpha(), Entry helper that fans out into order and UI branches., beta(), Continue the sample call chain toward gamma., gamma(), Leaf helper in the sample call chain., make_runner(), create_order() (+13 more)

### Community 54 - "update_repository"
Cohesion: 0.22
Nodes (5): FakeOrchestrator, OrchestrationResult, IntegrationCoordinator, Lock, Run ready integration operations one at a time in ready order.

### Community 55 - "conftest.py"
Cohesion: 0.50
Nodes (3): pytest_configure(), Pytest hooks shared across the test suite., Install pyan3 when call-graph tests run in an environment missing it.

### Community 57 - "DescriptorEmbedder"
Cohesion: 0.09
Nodes (28): Agent plan text must not be parsed as Textual/Rich markup., Follow-up questions must not crash when old option ids linger on widgets., Deferred Select init must not fatal-exit on a leftover option id., Clearing questions after confirmation must keep the TUI alive., Resolve a Select value that is legal for the current question options., build_implementation_prompt(), build_plan_clarification_prompt(), build_plan_followup_prompt() (+20 more)

### Community 59 - "PlanClarification"
Cohesion: 0.05
Nodes (36): Binding, ComposeResult, Select, CodingStatisticsScreen, CommandMenuScreen, CompactSettingsSelect, CreateTopicScreen, _format_codex_usage() (+28 more)

### Community 60 - "trading.py"
Cohesion: 0.32
Nodes (5): calculate(), execute_trade(), Portfolio, Assignment lineage, augassign, attribute mutate, and unique call mapping., run_pipeline()

### Community 61 - "CodingStatisticsScreen"
Cohesion: 0.28
Nodes (7): OrchestratorTests, AgentResult, WorktreeContext, LocalOrchestrator, OrchestrationSettings, PushResult, VerificationResult

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
Cohesion: 0.25
Nodes (6): Use Textual's OSC 52 path and a native clipboard fallback., copy_to_system_clipboard(), paste_from_system_clipboard(), System clipboard helpers for terminals without OSC 52 support., Read clipboard text using the native command available on the host., The Daedalus prompt's incremental Vim editing adapter.

### Community 70 - "configure_debug_logging"
Cohesion: 0.33
Nodes (6): configure_debug_logging(), install_fault_handler(), _install_thread_exception_logging(), Path, Write detailed runtime diagnostics to a rotating local log file., Capture fatal faults and ``SIGUSR1`` thread dumps in the debug log.

### Community 71 - "_collapse_inner_safe"
Cohesion: 0.17
Nodes (10): CallGraphVisitor, _collapse_inner_safe(), _collect_node_names(), discover_source_files(), extract_uses_edges(), Any, Path, Run pyan's collapse_inner while skipping anonymous nodes pyan cannot parent-reso (+2 more)

### Community 72 - "render_call_graph_tree.py"
Cohesion: 0.18
Nodes (17): _flat_parameter_values(), load_config(), _load_parameter_values(), load_runner_parameters(), main(), _project_root_setting(), _project_table(), Path (+9 more)

### Community 73 - "._on_personal_supabase_activation_progress"
Cohesion: 0.10
Nodes (9): GitWorktreeTests, Path, GitWorktreeError, push_branch(), RuntimeError, Push a local branch to ``remote``, setting upstream with ``-u`` when needed., Install project resources and link declared shared read-only paths., ProjectWorktreeSettings (+1 more)

### Community 74 - "ProjectWorktreeSettings"
Cohesion: 0.29
Nodes (6): ProjectConfigTests, load_project_worktree_settings(), Path, Configuration supplied by a target project to prepare task worktrees., Load optional worktree provisioning settings from a target repository., _string_array()

### Community 76 - "bootstrap_personal_supabase"
Cohesion: 0.08
Nodes (4): TuiAppTests, DaedalusVimTextArea, VimTextArea with multiline prompt behavior and system clipboard sync., VimTextArea

### Community 77 - "push_migrations"
Cohesion: 0.26
Nodes (6): SupabaseMigrationsTests, migrations_pending(), push_migrations(), Path, Return True when the worktree differs from base under supabase/migrations/., Run non-interactive `supabase db push --yes` in the target worktree.

### Community 80 - ".edit_paste_after"
Cohesion: 0.14
Nodes (18): main(), Child-process probe for project-local Supabase env key presence.  Invoke as ``py, _first_filled_env_value(), _key_or_aliases_label(), load_personal_supabase_settings(), personal_supabase_environment_settings(), personal_supabase_scaffold_relative_paths(), project_ref_from_supabase_url() (+10 more)

### Community 81 - ".enter_insert_mode"
Cohesion: 0.12
Nodes (12): _nonnegative_int(), _phase_for_status(), Path, Parse plan JSON from one turn without letting join separators break it., Rehydrate this project's persisted tasks after a TUI restart., Recover review questions from the last persisted plan response., Run an ask-mode clarification that does not mutate plan conversation state., Construct an orchestrator with the project environment when configured. (+4 more)

### Community 84 - "._handle_visual_line_mode"
Cohesion: 0.08
Nodes (7): Changed, Pressed, Submitted, PersonalSupabaseConfirmationScreen, PersonalSupabaseRemovalConfirmationScreen, Require an explicit confirmation before scaffolding/Activating a shared schema., Require an exact project-name confirmation before local cleanup.

### Community 85 - "._focus_submitted_task"
Cohesion: 0.10
Nodes (13): RowSelected, Focus a task from the cross-project update inbox., Apply only the newest event per task to keep the UI responsive., Surface Sync conflict recovery progress in the status bar., Promote only events that need the user's attention in the inbox., Refresh the account usage line without blocking the TUI event loop., Render actionable history and tasks created during this session., Keep failures, active work, and all tasks submitted in this launch. (+5 more)

### Community 89 - "PersonalSupabaseSetupWizardScreen"
Cohesion: 0.14
Nodes (13): Remove values loaded for a subprocess from a user-facing diagnostic., redact_environment_values(), load_project_personal_supabase_env_values(), preflight_personal_supabase(), PreflightResult, _probe_database_url(), probe_project_personal_supabase_environment(), project_personal_supabase_env_path() (+5 more)

### Community 90 - "remove_personal_supabase"
Cohesion: 0.14
Nodes (18): personal_supabase_managed_env_keys(), Return every env key this feature may clean up (preferred + aliases)., Remove local personal-Supabase artifacts without touching remote state.      The, Remove only the personal-Supabase table from a project marker., Remove one already-resolved file, symlink, or directory., Remove the generated shared-Supabase block from ``.env.example``., Remove synchronized Supabase assignments while preserving other env values., Return env text without the configured Supabase assignments. (+10 more)

### Community 93 - ".on_mount"
Cohesion: 0.12
Nodes (10): Pause active agents before ThreadPoolExecutor joins its workers.      CPython ex, Stop agents before an explicit Textual exit begins., Cover terminal and event-loop exits that bypass Textual unmount., Run before ThreadPoolExecutor's internal interpreter-exit join., Clean up if Textual's run loop returns without its unmount hook., Idempotently detach task callbacks and request child-process shutdown., _register_app_for_thread_exit(), _shutdown_apps_before_thread_join() (+2 more)

### Community 98 - ".submit_sync_recovery"
Cohesion: 0.29
Nodes (3): Return whether a Sync conflict recovery is still in flight for this project., Force-remove leftover sync worktrees from interrupted recoveries for ``branch``., Attach plan-mode recovery to a preserved Sync conflict worktree.

### Community 101 - "._update_plan_state"
Cohesion: 0.19
Nodes (8): PlanTests, Cursor may include prose and omit redundant false confirmation., parse_plan_response(), _payload_text(), _plan_payload_candidates(), Return every BEGIN/END plan blob, then fence/bare-object fallbacks., Compatibility helper: first plan payload candidate, if any., Extract the agent's plan payload without exposing protocol text in the UI.

## Knowledge Gaps
- **117 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+112 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `DaedalusVimTextArea` to `AgentRunner`, `PersonalSupabaseActivationProgressScreen`, `._on_personal_supabase_activation_progress`, `debug_log.py`, `bootstrap_personal_supabase`, `CandidateFeatureGroup`, `._persist_task`, `._render_line_strip`, `CodingStatisticsScreen`, `._focus_submitted_task`, `calculate_token_usage`, `._set_status`, `PlanClarification`, `.on_mount`, `._apply_responsive_layout`, `DescriptorEmbedder`?**
  _High betweenness centrality (0.136) - this node is a cross-community bridge._
- **Why does `AgentRunner` connect `._set_status` to `DaedalusVimTextArea`, `AgentRunner`, `._set_status`, `CandidateFeatureGroup`, `._persist_task`, `CodingStatisticsScreen`, `._handle_visual_line_mode`, `._shutdown_coordinators`, `update_repository`, `._focus_submitted_task`, `PlanClarification`, `CodingStatisticsScreen`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `TaskCoordinator` connect `._persist_task` to `DaedalusVimTextArea`, `AgentRunner`, `Key`, `._shutdown_coordinators`, `._set_status`, `.provider_split`, `CodingStatisticsScreen`, `calculate_token_usage`, `._set_status`, `CandidateFeatureGroup`, `update_repository`, `DescriptorEmbedder`, `PlanClarification`, `CodingStatisticsScreen`, `._on_personal_supabase_activation_progress`, `load_project_worktree_settings`, `.enter_insert_mode`, `paste_from_system_clipboard`, `._handle_visual_line_mode`, `.submit_sync_recovery`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `CommandMenuScreen`) actually correct?**
  _`TuiAppTests` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 19 INFERRED edges - model-reasoned connections that need verification._