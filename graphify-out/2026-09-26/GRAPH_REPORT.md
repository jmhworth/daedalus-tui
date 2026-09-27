# Graph Report - daedalus-tui  (2026-09-26)

## Corpus Check
- 96 files · ~93,014 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1865 nodes · 5158 edges · 104 communities (82 shown, 22 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 595 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ff7d9b90`
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
- ._finish_personal_supabase_progress
- .__init__
- .on_mount
- ._run_clarification
- .on_unmount
- RegistrationResult
- .submit_sync_recovery
- .nav_word_end
- .edit_paste_after
- .edit_paste_before
- .enter_insert_mode
- RegistrationResult

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
- `FakeStream` --uses--> `AgentRunner`  [INFERRED]
  tests/test_agent_runner.py → tui/agent_runner.py
- `FakeProcess` --uses--> `AgentControl`  [INFERRED]
  tests/test_agent_runner.py → tui/agent_runner.py
- `FakeProcess` --uses--> `AgentLogEvent`  [INFERRED]
  tests/test_agent_runner.py → tui/agent_runner.py
- `FakeProcess` --uses--> `AgentRequest`  [INFERRED]
  tests/test_agent_runner.py → tui/agent_runner.py

## Import Cycles
- None detected.

## Communities (104 total, 22 thin omitted)

### Community 0 - "PlanQuestion"
Cohesion: 0.14
Nodes (32): CandidateFeatureGroup, A deterministic connected component of qualifying similarity relations., Return the stable identifier using the concise ``id`` spelling., score_band(), SimilarityResult, _canonical_tree_name(), _feature_ids_by_member(), _histogram_bars() (+24 more)

### Community 1 - "DaedalusVimTextArea"
Cohesion: 0.03
Nodes (46): DaedalusTuiApp, Key, Resize, Remove known credential values before diagnostics reach the UI or log., Synchronize registered projects; push migrations only when activated., Add Vim-like navigation without changing TextArea insert behavior., Apply the viewport-aware layout whenever the terminal changes size., Toggle responsive classes and dimensions after a viewport change.          ``com (+38 more)

### Community 2 - "AgentRunner"
Cohesion: 0.12
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
Cohesion: 0.07
Nodes (19): Strip, Style, Show either the full-size transcript or the full-size diagnostics log., Resize, Selectable transcript rendering with semantic assistant-message emphasis., Return the width available for transcript text inside the Log., Wrap one logical line at word boundaries when the width permits., A selectable log that can emphasize a task's final assistant message.      ``Log (+11 more)

### Community 7 - "Daedalus TUI Local Token Usage Memory"
Cohesion: 0.29
Nodes (6): Daedalus TUI Local Persistent Memory, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 8 - "update_repository"
Cohesion: 0.11
Nodes (25): TopicsTests, build_topic_instructions(), build_topic_template(), embed_topic(), list_topic_slugs(), load_topic_settings(), load_topic_text(), Path (+17 more)

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
Cohesion: 0.19
Nodes (10): AgentControl, Cooperative stop signals shared by a task and its active subprocess., AgentStopped, OrchestrationResult, Path, RuntimeError, Plan or resolve Sync merge conflicts in a preserved sync worktree., Load a repository-owned profile immediately before building a prompt. (+2 more)

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
Cohesion: 0.15
Nodes (6): OutputCallback, Thread, AgentRunner, Run Codex or Cursor directly and emit only assistant-facing messages., Return assistant text deltas from Cursor's stream-json events., Prefer Codex JSONL error events over benign stderr noise.

### Community 26 - ".provider_split"
Cohesion: 0.16
Nodes (10): Persist task state, coalescing high-frequency streamed messages., Force-remove leftover sync worktrees from interrupted recoveries for ``branch``., Attach plan-mode recovery to a preserved Sync conflict worktree., Send selected plan answers back to the planning agent for confirmation., Ask a side-channel clarification about one plan question without plan follow-up., Auto-start coding in the same conflict worktree after a confirmed sync plan., Run another planning pass while keeping the task in questioning., Promote a reviewed plan into the normal coding and verification route. (+2 more)

### Community 27 - ".on_mount"
Cohesion: 0.17
Nodes (15): Popen, Protocol, VerificationTests, discover_commands(), format_process_result(), package_has_test_script(), CompletedProcess, Path (+7 more)

### Community 28 - "log_exception"
Cohesion: 0.29
Nodes (6): Daedalus TUI Topics, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 29 - "CodingStatisticsScreen"
Cohesion: 0.23
Nodes (6): GraphifyTests, Path, Best-effort graph refresh owned by the local orchestration layer., Refresh the primary repository graph without affecting task success., update_repository(), Refresh graph metadata after promotion without blocking the task.

### Community 30 - "calculate_token_usage"
Cohesion: 0.05
Nodes (32): TaskMemoryStoreTests, TokenUsageTests, Path, Small local JSON stores for persistent task history., Remove one project's operating-branch override (absent = use default)., Return the remembered default topic for a project, if any., Remember one project's default topic without losing other entries., Remove one project's topic override (absent = no default topic). (+24 more)

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
Cohesion: 0.15
Nodes (19): abort_sync_merge(), _create_isolated_sync_worktree(), _delete_branch_if_present(), finalize_sync_merge(), _force_remove_worktree(), _is_ancestor(), list_unmerged_paths(), pull_branch() (+11 more)

### Community 39 - "Daedalus Project Instructions"
Cohesion: 0.33
Nodes (5): Daedalus Project Instructions, graphify, Shared personal Supabase, Task mode, Topics

### Community 41 - "KeyboardShortcutsScreen"
Cohesion: 0.13
Nodes (27): activate_personal_supabase(), bootstrap_personal_supabase(), _commit_paths(), commit_personal_supabase_scaffold(), _ensure_supabase_scaffold(), _git_output(), _git_porcelain_paths(), _GitCommandResult (+19 more)

### Community 42 - "debug_log.py"
Cohesion: 0.16
Nodes (15): PromptTests, Single-run local agent orchestration without daemon or database dependencies., build_migration_repair_prompt(), build_repair_prompt(), build_resolver_prompt(), build_sync_conflict_coding_prompt(), build_sync_conflict_plan_prompt(), build_task_prompt() (+7 more)

### Community 44 - "CandidateFeatureGroup"
Cohesion: 0.15
Nodes (12): EnvironmentTests, apply_process_supabase_overrides(), cursor_environment(), Path, Small, dependency-free environment-file loading for local CLI providers., Return file values with non-empty process ``SUPABASE_*`` overrides applied., Return ``.env`` beside the installed ``tui`` package root., Return the process environment plus local Cursor credentials.      Explicit proc (+4 more)

### Community 45 - "KeyboardShortcutsScreen"
Cohesion: 0.20
Nodes (9): Constraints and Design Principles, Desired End State, Intended Import Workflow, Open Questions, Project Imports to the Daedalus Format, Scope and Durable Context, State Log, Topic Goal (+1 more)

### Community 46 - "._handle_visual_line_mode"
Cohesion: 0.21
Nodes (12): ConfigTests, LayoutSettings, load_codex_usage_settings(), load_coding_statistics_settings(), load_command_menu_settings(), load_orchestration_settings(), load_tui_settings(), ModelOption (+4 more)

### Community 47 - "DaedalusTuiApp"
Cohesion: 0.14
Nodes (8): Key, Keep Enter as a newline; Ctrl+Enter remains the app submit key., Route visual-line mode and mirror new yanks to the host clipboard., Add Daedalus prompt commands that the dependency does not provide., Select the current line and enter Vim visual-line mode., Select every character in the lines between the start and cursor., Handle movement and operators while whole lines are selected., Expose operator-pending so the caret can become an underline.

### Community 48 - "._persist_task"
Cohesion: 0.18
Nodes (4): TaskCoordinatorTests, OrchestrationSettings, Submit independent prompts while sharing a serialized integration gate., TaskCoordinator

### Community 49 - "._render_line_strip"
Cohesion: 0.19
Nodes (8): Agent plan text must not be parsed as Textual/Rich markup., Follow-up questions must not crash when old option ids linger on widgets., Deferred Select init must not fatal-exit on a leftover option id., Clearing questions after confirmation must keep the TUI alive., build_plan_clarification_prompt(), PlanOption, PlanQuestion, Build a read-only ask prompt for one plan question, without other questions.

### Community 50 - "environment.py"
Cohesion: 0.29
Nodes (6): Daedalus TUI Command Menu, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 51 - "CompactSettingsSelect"
Cohesion: 0.21
Nodes (6): PersonalSupabaseTests, Path, is_personal_supabase_activated(), True when the project is registered and activated for ``schema`` (or any)., Scaffold supabase files, env placeholders, profiles, and a ``.daedalus`` marker., register_personal_supabase()

### Community 52 - "Daedalus TUI Call Graph Visualization"
Cohesion: 0.29
Nodes (6): Daedalus TUI Call Graph Visualization, Dev Mode, Key Points, Relevant Files, State Log, Summary

### Community 53 - "b.py"
Cohesion: 0.10
Nodes (21): alpha(), Entry helper that fans out into order and UI branches., beta(), Continue the sample call chain toward gamma., gamma(), Leaf helper in the sample call chain., make_runner(), create_order() (+13 more)

### Community 54 - "update_repository"
Cohesion: 0.16
Nodes (7): FakeStream, InterruptibleProcess, AgentLogEvent, AgentRequest, Provider-specific subprocess execution with normalized agent messages., __getattr__(), Standalone Textual interface and local agent orchestration.

### Community 55 - "conftest.py"
Cohesion: 0.50
Nodes (3): pytest_configure(), Pytest hooks shared across the test suite., Install pyan3 when call-graph tests run in an environment missing it.

### Community 57 - "DescriptorEmbedder"
Cohesion: 0.10
Nodes (24): PlanTests, Cursor may include prose and omit redundant false confirmation., Resolve a Select value that is legal for the current question options., build_implementation_prompt(), build_plan_followup_prompt(), custom_answer_text(), _escape_unescaped_controls_in_json_strings(), _loads_plan_json() (+16 more)

### Community 59 - "PlanClarification"
Cohesion: 0.06
Nodes (48): Binding, ComposeResult, Mount, Select, CommandMenuScreen, CompactSettingsSelect, CreateTopicScreen, _format_codex_usage() (+40 more)

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
Cohesion: 0.21
Nodes (10): is_personal_supabase_registered(), load_personal_supabase_status(), PersonalSupabaseStatus, project_ref_from_supabase_url(), Derive the project ref from a standard ``https://<ref>.supabase.co`` URL., Return an explicit or URL-derived project ref (empty when neither is usable)., Registration / activation marker loaded from a target project's ``.daedalus``., Return the ``[personal_supabase]`` marker, or an unregistered default. (+2 more)

### Community 69 - "PersonalSupabaseActivationProgressScreen"
Cohesion: 0.22
Nodes (6): Use Textual's OSC 52 path and a native clipboard fallback., copy_to_system_clipboard(), paste_from_system_clipboard(), System clipboard helpers for terminals without OSC 52 support., Read clipboard text using the native command available on the host., The Daedalus prompt's incremental Vim editing adapter.

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
Cohesion: 0.23
Nodes (7): SupabaseMigrationsTests, migrations_pending(), push_migrations(), Path, Orchestration-owned Supabase migration push for target project worktrees., Return True when the worktree differs from base under supabase/migrations/., Run non-interactive `supabase db push --yes` in the target worktree.

### Community 78 - "load_project_worktree_settings"
Cohesion: 0.13
Nodes (10): FakeOrchestrator, Prefer mounted selector values so clarification refreshes keep choices., encode_custom_answer(), is_valid_plan_answer(), Encode free text without confusing it with an agent option id., Validate agent option ids and the software-owned custom answer format., Parse plan JSON from one turn without letting join separators break it., Remove the clean, read-only planning worktree after coding is queued. (+2 more)

### Community 80 - ".edit_paste_after"
Cohesion: 0.09
Nodes (36): main(), Child-process probe for project-local Supabase env key presence.  Invoke as ``py, Remove values loaded for a subprocess from a user-facing diagnostic., redact_environment_values(), _allow_list_comment(), _direct_database_host_project_ref(), _ensure_env_example(), _env_example_block() (+28 more)

### Community 81 - ".enter_insert_mode"
Cohesion: 0.11
Nodes (14): TaskEventCallback, IntegrationCoordinator, _nonnegative_int(), _phase_for_status(), Lock, Path, Concurrent task state and serialized local integration., Rehydrate this project's persisted tasks after a TUI restart. (+6 more)

### Community 82 - "paste_from_system_clipboard"
Cohesion: 0.14
Nodes (7): Changed, CodingStatisticsScreen, _format_count(), _format_tokens(), Show token or task usage history and derived coding statistics., merge_usage_entries(), Merge snapshots by task ID, allowing live records to replace history.

### Community 83 - ".cursor_shape"
Cohesion: 0.20
Nodes (13): CodexUsageTests, CodexUsageWindow, fetch_codex_usage(), _find_response(), _first_undimensioned_window(), parse_codex_usage(), _parse_reset(), _parse_window() (+5 more)

### Community 84 - "._handle_visual_line_mode"
Cohesion: 0.11
Nodes (4): Pressed, Submitted, PersonalSupabaseRemovalConfirmationScreen, Require an exact project-name confirmation before local cleanup.

### Community 85 - "._focus_submitted_task"
Cohesion: 0.06
Nodes (18): Log, RowSelected, Text, _literal_select_options(), Path, Build Select prompts that Rich will not parse as markup., Focus a task from the cross-project update inbox., Apply only the newest event per task to keep the UI responsive. (+10 more)

### Community 86 - "._set_status"
Cohesion: 0.21
Nodes (8): GitWorktreeError, push_branch(), CompletedProcess, RuntimeError, Push a local branch to ``remote``, setting upstream with ``-u`` when needed., Install project resources and link declared shared read-only paths., Return whether ``remote`` is configured for ``repository``., remote_exists()

### Community 89 - "PersonalSupabaseSetupWizardScreen"
Cohesion: 0.33
Nodes (4): probe_project_personal_supabase_environment(), project_personal_supabase_env_path(), Return the project-local ``.env`` path operators must edit., Check required project Supabase keys via a child process exit code.      The par

### Community 90 - "remove_personal_supabase"
Cohesion: 0.20
Nodes (12): Remove local personal-Supabase artifacts without touching remote state.      The, Remove only the personal-Supabase table from a project marker., Remove one already-resolved file, symlink, or directory., Remove the generated shared-Supabase block from ``.env.example``., Remove the generated Personal Supabase section from one profile., Remove a generated block and normalize the blank lines around it., _remove_path(), remove_personal_supabase() (+4 more)

### Community 91 - "._finish_personal_supabase_progress"
Cohesion: 0.25
Nodes (4): Finish a queued modal update only if its screen is still mounted., Apply worker results that arrived while this modal was mounting., Freeze the progress display and allow the operator to close it., Render a completion state after all modal widgets are mounted.

### Community 92 - ".__init__"
Cohesion: 0.40
Nodes (3): EventCallback, IntegrationGate, Lock

### Community 93 - ".on_mount"
Cohesion: 0.08
Nodes (20): AbstractEventLoop, BaseException, Exception, Pause active agents before ThreadPoolExecutor joins its workers.      CPython ex, Stop agents before an explicit Textual exit begins., Persist Textual failures that would otherwise only flash on screen., Run before ThreadPoolExecutor's internal interpreter-exit join., Clean up if Textual's run loop returns without its unmount hook. (+12 more)

### Community 97 - "RegistrationResult"
Cohesion: 0.50
Nodes (3): _ensure_profile_guidance(), profile_guidance_section(), Return the markdown section appended to coding/architecture profiles.

## Knowledge Gaps
- **117 isolated node(s):** `daedalus-tui`, `Execution Boundaries (CRITICAL)`, `Evidence Extraction`, `Architecture Boundaries`, `Parameter Files` (+112 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaedalusTuiApp` connect `DaedalusVimTextArea` to `.on_unmount`, `AgentRunner`, `PersonalSupabaseActivationProgressScreen`, `GitWorktreeManager`, `._finish_personal_supabase_progress`, `bootstrap_personal_supabase`, `load_project_worktree_settings`, `._persist_task`, `._render_line_strip`, `paste_from_system_clipboard`, `._focus_submitted_task`, `._set_status`, `update_repository`, `._set_status`, `PlanClarification`, `.on_mount`, `calculate_token_usage`, `DescriptorEmbedder`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Why does `AgentRunner` connect `._set_status` to `DaedalusVimTextArea`, `configure_debug_logging`, `debug_log.py`, `load_project_worktree_settings`, `._persist_task`, `.enter_insert_mode`, `paste_from_system_clipboard`, `._handle_visual_line_mode`, `._focus_submitted_task`, `update_repository`, `._shutdown_coordinators`, `Path`, `PlanClarification`, `.__init__`, `CodingStatisticsScreen`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `TuiAppTests` connect `bootstrap_personal_supabase` to `DaedalusVimTextArea`, `AgentRunner`, `.finish`, `._handle_visual_line_mode`, `load_project_worktree_settings`, `._render_line_strip`, `paste_from_system_clipboard`, `.cursor_shape`, `._handle_visual_line_mode`, `._set_status`, `PlanClarification`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `DaedalusTuiApp` (e.g. with `FakeCoordinator` and `FakeRunner`) actually correct?**
  _`DaedalusTuiApp` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `TuiAppTests` (e.g. with `CodingStatisticsScreen` and `CommandMenuScreen`) actually correct?**
  _`TuiAppTests` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `TaskCoordinator` (e.g. with `FakeOrchestrator` and `TaskCoordinatorTests`) actually correct?**
  _`TaskCoordinator` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `OrchestrationSettings` (e.g. with `OrchestratorTests` and `FakeOrchestrator`) actually correct?**
  _`OrchestrationSettings` has 19 INFERRED edges - model-reasoned connections that need verification._