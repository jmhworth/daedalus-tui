# Graph Report - daedalus-tui  (2026-11-04)

## Corpus Check
- 100 files · ~100,063 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1934 nodes · 5391 edges · 92 communities (74 shown, 18 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 633 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0f92dd94`
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
- ._rebuild_plan_questions
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
- .nav_word_end
- RegistrationResult
- expose_personal_supabase_schema
- .__init__
- IntegrationCoordinator
- remove_personal_supabase
- ._apply_task_event
- PersonalSupabaseSetupWizardScreen
- ._on_personal_supabase_activation_progress

## God Nodes (most connected - your core abstractions)
1. `DaedalusTuiApp` - 188 edges
2. `TuiAppTests` - 126 edges
3. `TaskCoordinator` - 97 edges
4. `OrchestrationSettings` - 78 edges
5. `TaskRecord` - 75 edges
6. `AgentRunner` - 74 edges
7. `FakeCoordinator` - 68 edges
8. `WorktreeContext` - 67 edges
9. `GitWorktreeManager` - 67 edges
10. `DaedalusVimTextArea` - 67 edges

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

## Communities (92 total, 18 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.14
Nodes (32): CandidateFeatureGroup, A deterministic connected component of qualifying similarity relations., Return the stable identifier using the concise ``id`` spelling., score_band(), SimilarityResult, _canonical_tree_name(), _feature_ids_by_member(), _histogram_bars() (+24 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.05
Nodes (33): DaedalusTuiApp, _literal_select_options(), Path, Resize, Build Select prompts that Rich will not parse as markup., Synchronize registered projects; push migrations only when activated., Apply the viewport-aware layout whenever the terminal changes size., Toggle responsive classes and dimensions after a viewport change.          ``com (+25 more)

### Community 2 - "AgentRunner"
Cohesion: 0.10
Nodes (11): TaskEventCallback, FakeOrchestrator, TaskCoordinatorTests, OrchestrationResult, OrchestrationSettings, IntegrationCoordinator, Lock, Run ready integration operations one at a time in ready order. (+3 more)

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
Cohesion: 0.06
Nodes (19): Strip, Style, Text, Resize, Render logical messages as wrapped, selectable Log lines., Return the width available for transcript text inside the Log., Wrap one logical line at word boundaries when the width permits., Add a file glyph to bracketed paths and filenames in agent text. (+11 more)

### Community 7 - "Daedalus TUI Local Token Usage Memory"
Cohesion: 0.29
Nodes (6): Daedalus TUI Local Persistent Memory, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 8 - "update_repository"
Cohesion: 0.07
Nodes (39): PromptTests, TopicsTests, build_migration_repair_prompt(), build_repair_prompt(), build_resolver_prompt(), build_sync_conflict_coding_prompt(), build_sync_conflict_plan_prompt(), build_task_prompt() (+31 more)

### Community 11 - "Key"
Cohesion: 0.11
Nodes (10): Path, Stage the current worktree contents for orchestration checks or commit., Remove graphify output changes from an agent worktree.          Graphify refresh, Keep a read-only planning pass from becoming an implementation change., Commit only the generated graph after a successful primary update., Return a directory whose HEAD matches the target branch tip.          When the r, Remove a short-lived primary checkout created for post-promotion work., Remove a cancelled task even when its branch was never integrated. (+2 more)

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
Cohesion: 0.09
Nodes (17): Path, Parse plan JSON from one turn without letting join separators break it., Remove the clean, read-only planning worktree after coding is queued., Persist task state, coalescing high-frequency streamed messages., Force-remove leftover sync worktrees from interrupted recoveries for ``branch``., Attach plan-mode recovery to a preserved Sync conflict worktree., Send selected plan answers back to the planning agent for confirmation., Ask a side-channel clarification about one plan question without plan follow-up. (+9 more)

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
Cohesion: 0.11
Nodes (5): Agent plan text must not be parsed as Textual/Rich markup., Follow-up questions must not crash when old option ids linger on widgets., Deferred Select init must not fatal-exit on a leftover option id., Clearing questions after confirmation must keep the TUI alive., PlanOption

### Community 26 - ".provider_split"
Cohesion: 0.15
Nodes (13): EventCallback, IntegrationGate, AgentControl, Cooperative stop signals shared by a task and its active subprocess., AgentStopped, Lock, Path, RuntimeError (+5 more)

### Community 27 - ".on_mount"
Cohesion: 0.22
Nodes (6): Use Textual's OSC 52 path and a native clipboard fallback., copy_to_system_clipboard(), paste_from_system_clipboard(), System clipboard helpers for terminals without OSC 52 support., Read clipboard text using the native command available on the host., The Daedalus prompt's incremental Vim editing adapter.

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.20
Nodes (8): _nonnegative_int(), _phase_for_status(), Rehydrate this project's persisted tasks after a TUI restart., Recover review questions from the last persisted plan response., _snapshot_path(), _snapshot_sequence(), _snapshot_timestamp(), _string_list()

### Community 30 - "calculate_token_usage"
Cohesion: 0.05
Nodes (34): TaskMemoryStoreTests, TokenUsageTests, Path, Small local JSON stores for persistent task history., Remove one project's operating-branch override (absent = use default)., Return the remembered default topic for a project, if any., Remember one project's default topic without losing other entries., Remove one project's topic override (absent = no default topic). (+26 more)

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
Cohesion: 0.14
Nodes (21): abort_sync_merge(), _create_isolated_sync_worktree(), _delete_branch_if_present(), finalize_sync_merge(), _force_remove_worktree(), _is_ancestor(), list_unmerged_paths(), pull_branch() (+13 more)

### Community 39 - "Daedalus Project Instructions"
Cohesion: 0.33
Nodes (5): Daedalus Project Instructions, graphify, Shared personal Supabase, Task mode, Topics

### Community 41 - "KeyboardShortcutsScreen"
Cohesion: 0.09
Nodes (32): PlanTests, Cursor may include prose and omit redundant false confirmation., Resolve a Select value that is legal for the current question options., build_implementation_prompt(), build_plan_clarification_prompt(), build_plan_followup_prompt(), custom_answer_text(), encode_custom_answer() (+24 more)

### Community 42 - "debug_log.py"
Cohesion: 0.14
Nodes (17): Popen, Protocol, VerificationTests, discover_commands(), format_process_result(), package_has_test_script(), CompletedProcess, Path (+9 more)

### Community 43 - "._rebuild_plan_questions"
Cohesion: 0.07
Nodes (21): FakeCoordinator, FakeRunner, settings(), KeyboardShortcutsScreen, PersonalSupabaseActivationProgressScreen, PersonalSupabaseSetupWizardScreen, Finish a queued modal update only if its screen is still mounted., Modal reference for the app and prompt editor keyboard shortcuts. (+13 more)

### Community 44 - "CandidateFeatureGroup"
Cohesion: 0.05
Nodes (24): OutputCallback, AgentRunnerTests, FakeProcess, FakeStream, InterruptibleProcess, ProjectDiscoveryTests, Thread, AgentLogEvent (+16 more)

### Community 45 - "KeyboardShortcutsScreen"
Cohesion: 0.20
Nodes (9): Constraints and Design Principles, Desired End State, Intended Import Workflow, Open Questions, Project Imports to the Daedalus Format, Scope and Durable Context, State Log, Topic Goal (+1 more)

### Community 47 - "DaedalusTuiApp"
Cohesion: 0.16
Nodes (7): Key, Route visual-line mode and mirror new yanks to the host clipboard., Add Daedalus prompt commands that the dependency does not provide., Select the current line and enter Vim visual-line mode., Select every character in the lines between the start and cursor., Handle movement and operators while whole lines are selected., Expose operator-pending so the caret can become an underline.

### Community 48 - "._persist_task"
Cohesion: 0.14
Nodes (9): Enable Push only when an origin remote and operating branch are available., Sync the Branch Select value for the active project with origin., Launch plan-mode recovery against the preserved Sync conflict worktree., Choose a built-in app-wide color theme., ThemePickerScreen, GitWorktreeError, RuntimeError, Raised when an operator Sync pull/merge leaves unmerged paths.      The conflict (+1 more)

### Community 49 - "._rebuild_plan_questions"
Cohesion: 0.83
Nodes (4): _allow_list_comment(), _ensure_env_example(), _env_example_block(), _shared_env_example_block()

### Community 50 - "environment.py"
Cohesion: 0.29
Nodes (6): Daedalus TUI Command Menu, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 51 - "CompactSettingsSelect"
Cohesion: 0.20
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
Cohesion: 0.05
Nodes (11): Changed, ComposeResult, Pressed, Submitted, CreateTopicScreen, PersonalSupabaseConfirmationScreen, PersonalSupabaseRemovalConfirmationScreen, Collect the context needed to initialize and populate a topic file. (+3 more)

### Community 59 - "PlanClarification"
Cohesion: 0.09
Nodes (25): personal_supabase_managed_env_keys(), project_personal_supabase_env_path(), Return every env key this feature may clean up (preferred + aliases)., Remove local personal-Supabase artifacts without touching remote state.      The, Remove only the personal-Supabase table from a project marker., Remove one already-resolved file, symlink, or directory., Remove a directory only when no unrelated files remain inside it., Remove the generated shared-Supabase block from ``.env.example``. (+17 more)

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
Cohesion: 0.10
Nodes (46): activate_personal_supabase(), bootstrap_personal_supabase(), _commit_paths(), commit_personal_supabase_scaffold(), _ensure_supabase_scaffold(), expose_personal_supabase_schema(), expose_registered_personal_supabase_schema(), _git_output() (+38 more)

### Community 69 - "log_exception"
Cohesion: 0.07
Nodes (23): AbstractEventLoop, BaseException, Exception, Stop agents before an explicit Textual exit begins., Persist Textual failures that would otherwise only flash on screen., Cover terminal and event-loop exits that bypass Textual unmount., Run before ThreadPoolExecutor's internal interpreter-exit join., Clean up if Textual's run loop returns without its unmount hook. (+15 more)

### Community 71 - "_collapse_inner_safe"
Cohesion: 0.17
Nodes (10): CallGraphVisitor, _collapse_inner_safe(), _collect_node_names(), discover_source_files(), extract_uses_edges(), Any, Path, Run pyan's collapse_inner while skipping anonymous nodes pyan cannot parent-reso (+2 more)

### Community 72 - "render_call_graph_tree.py"
Cohesion: 0.18
Nodes (17): _flat_parameter_values(), load_config(), _load_parameter_values(), load_runner_parameters(), main(), _project_root_setting(), _project_table(), Path (+9 more)

### Community 73 - "._on_personal_supabase_activation_progress"
Cohesion: 0.14
Nodes (7): GitWorktreeTests, Path, GitWorktreeManager, push_branch(), Push a local branch to ``remote``, setting upstream with ``-u`` when needed., Return whether ``remote`` is configured for ``repository``., remote_exists()

### Community 74 - "ProjectWorktreeSettings"
Cohesion: 0.27
Nodes (7): ProjectConfigTests, load_project_worktree_settings(), ProjectWorktreeSettings, Path, Install and shared-path settings from a target project's .daedalus file., Load optional worktree provisioning settings from a target repository., _string_array()

### Community 76 - "bootstrap_personal_supabase"
Cohesion: 0.08
Nodes (4): TuiAppTests, DaedalusVimTextArea, VimTextArea with multiline prompt behavior and system clipboard sync., VimTextArea

### Community 77 - "push_migrations"
Cohesion: 0.16
Nodes (11): SupabaseMigrationsTests, _migration_directory_name(), migrations_pending(), MigrationSyncResult, push_migrations(), Path, Orchestration-owned Supabase migration push for target project worktrees., Link the selected project when needed, then run non-interactive `db push`. (+3 more)

### Community 78 - "debug_log.py"
Cohesion: 0.29
Nodes (5): GraphifyTests, Path, Best-effort graph refresh owned by the local orchestration layer., Refresh the primary repository graph without affecting task success., update_repository()

### Community 81 - "select_roots"
Cohesion: 0.15
Nodes (14): EnvironmentTests, apply_process_supabase_overrides(), cursor_environment(), Path, Small, dependency-free environment-file loading for local CLI providers., Return file values with non-empty process ``SUPABASE_*`` overrides applied., Remove values loaded for a subprocess from a user-facing diagnostic., Return ``.env`` beside the installed ``tui`` package root. (+6 more)

### Community 82 - "TranscriptLog"
Cohesion: 0.04
Nodes (45): Binding, Log, Mount, Select, Theme, CodingStatisticsScreen, CommandMenuScreen, CompactSettingsSelect (+37 more)

### Community 84 - "RegistrationResult"
Cohesion: 0.07
Nodes (11): Key, Remove known credential values before diagnostics reach the UI or log., Add Vim-like navigation without changing TextArea insert behavior., Confirm, then scaffold (if needed) and Activate personal Supabase., Scaffold files, then guide manual project env setup before Activate., Run scaffold+Activate in a background worker so the TUI stays responsive., Queue a coding task that writes and expands the requested topic file., Return a TextArea selection or the active screen selection. (+3 more)

### Community 87 - ".__init__"
Cohesion: 0.11
Nodes (25): CodexUsageTests, ConfigTests, CodexUsageWindow, fetch_codex_usage(), _find_response(), _first_undimensioned_window(), parse_codex_usage(), _parse_reset() (+17 more)

### Community 90 - "remove_personal_supabase"
Cohesion: 0.11
Nodes (19): main(), Child-process probe for Daedalus TUI Supabase env key presence.  Invoke as ``pyt, _ensure_profile_guidance(), _first_filled_env_value(), _key_or_aliases_label(), load_personal_supabase_settings(), personal_supabase_environment_settings(), personal_supabase_scaffold_relative_paths() (+11 more)

### Community 91 - "._apply_task_event"
Cohesion: 0.08
Nodes (15): RowSelected, Focus a task from the cross-project update inbox., Apply only the newest event per task to keep the UI responsive., Surface Sync conflict recovery progress in the status bar., Promote only events that need the user's attention in the inbox., Render actionable history and tasks created during this session., Keep failures, active work, and all tasks submitted in this launch., Keep inbox cells within their fixed width with a visible ellipsis. (+7 more)

### Community 92 - "PersonalSupabaseSetupWizardScreen"
Cohesion: 0.14
Nodes (13): _direct_database_host_project_ref(), load_project_personal_supabase_env_values(), preflight_personal_supabase(), PreflightResult, _probe_database_url(), probe_project_personal_supabase_environment(), Outcome of the access-method-aware live Supabase connectivity probe., Run access-method-aware live connectivity checks; never mutates schema. (+5 more)

### Community 101 - "._on_personal_supabase_activation_progress"
Cohesion: 0.40
Nodes (3): Forward worker phases to the modal and the main status line., Mark the current activation phase and retain a readable status line., Update mounted progress widgets for one worker phase.

## Knowledge Gaps
- **117 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+112 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `DaedalusVimTextArea` to `AgentRunner`, `log_exception`, `._on_personal_supabase_activation_progress`, `.on_mount`, `KeyboardShortcutsScreen`, `._rebuild_plan_questions`, `bootstrap_personal_supabase`, `CandidateFeatureGroup`, `._persist_task`, `TranscriptLog`, `RegistrationResult`, `DescriptorEmbedder`, `._apply_task_event`, `calculate_token_usage`?**
  _High betweenness centrality (0.137) - this node is a cross-community bridge._
- **Why does `TaskCoordinator` connect `AgentRunner` to `DaedalusVimTextArea`, `KeyboardShortcutsScreen`, `._on_personal_supabase_activation_progress`, `._rebuild_plan_questions`, `CandidateFeatureGroup`, `._persist_task`, `TranscriptLog`, `CodingStatisticsScreen`, `._shutdown_coordinators`, `DescriptorEmbedder`, `.provider_split`, `CodingStatisticsScreen`, `calculate_token_usage`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `AgentRunner` connect `CandidateFeatureGroup` to `DaedalusVimTextArea`, `AgentRunner`, `._set_status`, `KeyboardShortcutsScreen`, `._rebuild_plan_questions`, `._persist_task`, `TranscriptLog`, `DescriptorEmbedder`, `.provider_split`, `._apply_task_event`, `CodingStatisticsScreen`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `CommandMenuScreen`) actually correct?**
  _`TuiAppTests` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 19 INFERRED edges - model-reasoned connections that need verification._