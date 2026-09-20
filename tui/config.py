"""Read-only configuration for the standalone TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib

from .agent_runner import ProviderAuthPolicy
from .git_worktree import DIRTY_PRIMARY_COMMIT_MESSAGE
from .local_storage import GENERATED_DIRECTORY_NAMES, tui_project_root
from .orchestrator import OrchestrationSettings
from .usage_monitor import UsageProviderSettings, UsageSettings


AUTH_MODES = frozenset({"account", "api-key"})
CLAUDE_PERMISSION_MODES = frozenset(
    {"acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan"}
)
CLAUDE_DEFAULT_ALLOWED_TOOLS: tuple[str, ...] = (
    "Bash(npm test:*)",
    "Bash(npm run:*)",
    "Bash(npx vitest:*)",
    "Bash(npx tsc:*)",
    "Bash(npx eslint:*)",
    "Bash(pytest:*)",
    "Bash(python -m pytest:*)",
    "Bash(python3 -m pytest:*)",
    "Bash(git status:*)",
    "Bash(git diff:*)",
    "Bash(git log:*)",
    "Bash(git show:*)",
    "Bash(ls:*)",
)

PARAMETER_DIRECTORY = "parameter_files"
TUI_PARAMETER_FILE = "daedalus-tui.toml"
ORCHESTRATION_PARAMETER_FILE = "daedalus-tui-orchestration.toml"
ORCHESTRATE_MODE_PARAMETER_FILE = "daedalus-tui-orchestrate-mode.toml"
CODING_STATISTICS_PARAMETER_FILE = "daedalus-tui-coding-statistics.toml"
PROMPTING_PARAMETER_FILE = "daedalus-tui-prompting.toml"


@dataclass(frozen=True)
class ModelOption:
    label: str
    value: str


@dataclass(frozen=True)
class ClaudeSettings:
    """Non-interactive execution settings for the Claude Code provider."""

    permission_mode: str = "acceptEdits"
    # Bash rules Claude may run without a prompt. `claude --print` has nobody
    # to answer a permission prompt, so anything outside this list (plus the
    # verification commands orchestration adds per task) is denied outright.
    allowed_tools: tuple[str, ...] = CLAUDE_DEFAULT_ALLOWED_TOOLS


@dataclass(frozen=True)
class ProviderAuthSettings:
    """Sign-in metadata for one provider CLI.

    ``api_key_variables`` names the environment variables that make the CLI bill
    API credit instead of the operator's plan; account mode removes them from the
    agent subprocess environment. Only variable names live here, never keys.
    """

    label: str
    api_key_variables: tuple[str, ...] = ()
    status_command: tuple[str, ...] = ()
    sign_in_command: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthSettings:
    """Whether agents run from a signed-in account or from API keys."""

    mode: str = "account"
    providers: dict[str, ProviderAuthSettings] = field(default_factory=dict)

    @property
    def uses_account_login(self) -> bool:
        return self.mode == "account"

    def for_provider(self, provider: str) -> ProviderAuthSettings:
        return self.providers.get(provider, ProviderAuthSettings(provider))

    def runner_policy(self) -> ProviderAuthPolicy:
        """Return the API-key stripping policy the agent runner applies."""
        return ProviderAuthPolicy(
            account_login=self.uses_account_login,
            api_key_variables={
                name: settings.api_key_variables for name, settings in self.providers.items()
            },
        )


@dataclass(frozen=True)
class ProjectDiscoverySettings:
    """Which immediate launch-root children appear in the project selector."""

    include_git_repositories: bool = True
    include_all_directories: bool = False
    skipped_directory_names: frozenset[str] = frozenset(
        {".git", ".daedalus-worktrees", ".venv", "__pycache__", "node_modules"}
        | GENERATED_DIRECTORY_NAMES
    )


@dataclass(frozen=True)
class LayoutSettings:
    """Safety guard and dimensions used by the responsive TUI.

    The wide controls are measured against their laid-out regions above this
    width: clipped toolbars wrap onto two rows first and compact mode is the
    last resort. The guard keeps very narrow terminals in compact mode while
    those regions are not usable yet. Settings selectors below ``wide_control_min_width``
    use the compact category/value picker instead of shrinking into unreadable
    controls.
    """

    compact_width: int = 100
    short_height: int = 32
    compact_task_sidebar_height: int = 8
    compact_prompt_height: int = 4
    wide_control_min_width: int = 13


@dataclass(frozen=True)
class TuiSettings:
    default_provider: str
    default_model: str
    default_reasoning: str
    providers: tuple[ModelOption, ...]
    codex_models: tuple[ModelOption, ...]
    codex_reasoning: tuple[ModelOption, ...]
    cursor_model: ModelOption
    claude_models: tuple[ModelOption, ...] = ()
    claude_reasoning: tuple[ModelOption, ...] = ()
    modes: tuple[ModelOption, ...] = (
        ModelOption("Coding", "coding"),
        ModelOption("Ask", "ask"),
        ModelOption("Plan", "plan"),
    )
    output_width: str = "95%"
    # Content widths for the four task-inbox columns, excluding DataTable
    # cell padding. The defaults leave a cell for the sidebar scrollbar.
    task_inbox_widths: tuple[int, int, int, int] = (1, 9, 14, 7)
    layout: LayoutSettings = LayoutSettings()
    claude: ClaudeSettings = ClaudeSettings()
    auth: AuthSettings = AuthSettings()
    project_discovery: ProjectDiscoverySettings = ProjectDiscoverySettings()
    usage: UsageSettings = UsageSettings()

    def models_for(self, provider: str) -> tuple[ModelOption, ...]:
        """Return the model choices a provider exposes in the settings bar."""
        if provider == "cursor":
            return (self.cursor_model,)
        if provider == "claude":
            return self.claude_models
        return self.codex_models

    def reasoning_for(self, provider: str) -> tuple[ModelOption, ...]:
        """Return the reasoning/effort choices a provider exposes, if any."""
        if provider == "cursor":
            return ()
        if provider == "claude":
            return self.claude_reasoning
        return self.codex_reasoning

    def default_model_for(self, provider: str) -> str:
        """Return the model preselected when switching to ``provider``."""
        options = self.models_for(provider)
        if any(option.value == self.default_model for option in options):
            return self.default_model
        return options[0].value if options else ""

    def default_reasoning_for(self, provider: str) -> str:
        """Return the reasoning preselected when switching to ``provider``."""
        options = self.reasoning_for(provider)
        if any(option.value == self.default_reasoning for option in options):
            return self.default_reasoning
        return options[0].value if options else ""


@dataclass(frozen=True)
class PromptingSettings:
    """Prompt archive, draft, naming, viewer, and error-folder settings.

    ``data_root`` is already resolved: a relative value in the parameter file
    is anchored to the TUI project directory that owns that file, so the
    storage location does not depend on the working directory or on which
    target repository a task runs against.
    """

    data_root: Path = field(default_factory=tui_project_root)
    draft_autosave_delay_ms: int = 300
    clear_drafts_on_exit: bool = True
    task_title_length: int = 60
    viewer_visible_by_default: bool = False
    viewer_minimum_width: int = 40
    main_minimum_width: int = 80
    viewer_render_debounce_ms: int = 150
    viewer_hard_line_breaks: bool = True
    viewer_action_items_by_default: bool = True
    viewer_action_item_limit: int = 6
    conversation_context_budget_chars: int = 24_000
    error_log_max_bytes: int = 2_000_000
    error_log_backup_count: int = 3
    run_log_max_bytes: int = 1_000_000


@dataclass(frozen=True)
class OrchestrateSettings:
    """Roles, caps, context budgets, and view sizes for Orchestrate Mode.

    The defaults mirror ``parameter_files/daedalus-tui-orchestrate-mode.toml``
    so a missing key falls back to the documented value instead of failing the
    session. The character budgets are the mechanism that keeps a worker's
    context small, so they are settings rather than constants.
    """

    planner_provider: str = "claude"
    planner_model: str = "claude-fable-5-1"
    planner_reasoning: str = "medium"
    worker_provider: str = "claude"
    worker_model: str = "claude-opus-5"
    worker_reasoning: str = "high"
    default_max_workers: int = 3
    max_workers_limit: int = 8
    #: Optional safety cap on planner rounds per session. Zero, the default,
    #: means no cap: the planner decides how many rounds the work needs and
    #: ends the session by declaring it done.
    planner_round_limit: int = 0
    #: Characters of repository file listing handed to the first planner turn
    #: so it can name ``read_first`` paths without exploring the tree itself.
    planner_repository_map_chars: int = 8_000
    #: Characters of the committed orchestration context file (earlier
    #: sessions' prompts, plans, and card outcomes) embedded in the first
    #: planner turn so a new session continues from what was already planned.
    planner_context_chars: int = 12_000
    task_reissue_limit: int = 2
    planner_digest_budget_chars: int = 12_000
    worker_report_budget_chars: int = 4_000
    worker_card_budget_chars: int = 6_000
    session_dirname: str = "orchestrate"
    card_filename: str = "task.md"
    runtime_artifact_dirname: str = ".daedalus-orchestration"
    #: Repository-relative path of the orchestration context file Daedalus
    #: commits and pushes onto the operating branch after every planner round.
    #: An empty string disables the file.
    context_filename: str = "DAEDALUS_CONTEXT.md"
    board_title_width: int = 28
    planner_log_lines: int = 400

    @property
    def planner_selection(self) -> tuple[str, str, str]:
        """Return the planner's ``(provider, model, reasoning)`` selection."""
        return (self.planner_provider, self.planner_model, self.planner_reasoning)

    @property
    def worker_selection(self) -> tuple[str, str, str]:
        """Return the worker's ``(provider, model, reasoning)`` selection."""
        return (self.worker_provider, self.worker_model, self.worker_reasoning)


@dataclass(frozen=True)
class CodingStatisticsSettings:
    recent_window_hours: int = 1
    forecast_days: int = 7
    thirty_day_forecast_days: int = 30


def load_tui_settings(parameter_path: Path | None = None) -> TuiSettings:
    path = parameter_path or (Path(__file__).resolve().parents[1] / PARAMETER_DIRECTORY / TUI_PARAMETER_FILE)
    with path.open("rb") as source:
        values = tomllib.load(source)

    defaults = values.get("defaults", {})
    providers = tuple(_options(values.get("providers", []), "provider"))
    codex_models = tuple(_options(values.get("codex_models", []), "model"))
    codex_reasoning = tuple(_options(values.get("codex_reasoning", []), "reasoning"))
    cursor_values = values.get("cursor", {})
    cursor_model = ModelOption(str(cursor_values.get("label", "Cursor CLI")), str(cursor_values.get("value", "cursor")))
    claude_models = tuple(_options(values.get("claude_models", []), "model"))
    claude_reasoning = tuple(_options(values.get("claude_reasoning", []), "reasoning"))
    modes = tuple(_options(values.get("modes", []), "mode")) or TuiSettings.modes
    output = values.get("output", {})
    output_width = str(output.get("width", "95%"))
    task_inbox = values.get("task_inbox", {})
    task_inbox_widths = tuple(
        int(task_inbox.get(name, default))
        for name, default in (
            ("marker_width", 1),
            ("project_width", 9),
            ("task_width", 14),
            ("status_width", 7),
        )
    )
    if any(width < 1 for width in task_inbox_widths):
        raise ValueError(f"{path} task_inbox widths must be positive.")

    layout_values = values.get("layout", {})
    layout = LayoutSettings(
        compact_width=int(layout_values.get("compact_width", 100)),
        short_height=int(layout_values.get("short_height", 32)),
        compact_task_sidebar_height=int(layout_values.get("compact_task_sidebar_height", 8)),
        compact_prompt_height=int(layout_values.get("compact_prompt_height", 4)),
        wide_control_min_width=int(layout_values.get("wide_control_min_width", 14)),
    )
    if any(value < 1 for value in (
        layout.compact_width,
        layout.wide_control_min_width,
        layout.short_height,
        layout.compact_task_sidebar_height,
        layout.compact_prompt_height,
    )):
        raise ValueError(f"{path} layout values must be positive.")

    default_provider = str(defaults.get("provider", "claude"))
    default_model = str(defaults.get("model", "claude-opus-5"))
    default_reasoning = str(defaults.get("reasoning", "high"))
    if not providers or not codex_models or not codex_reasoning:
        raise ValueError(f"{path} must define providers, codex_models, and codex_reasoning.")
    if any(option.value == "claude" for option in providers) and not claude_models:
        raise ValueError(f"{path} lists the claude provider but defines no claude_models.")

    claude_values = values.get("claude", {})
    if not isinstance(claude_values, dict):
        raise ValueError(f"{path} claude must be a table.")
    claude = ClaudeSettings(
        permission_mode=str(claude_values.get("permission_mode", "acceptEdits")),
        allowed_tools=(
            _string_tuple(claude_values["allowed_tools"], path, "claude.allowed_tools")
            if "allowed_tools" in claude_values
            else CLAUDE_DEFAULT_ALLOWED_TOOLS
        ),
    )
    if claude.permission_mode not in CLAUDE_PERMISSION_MODES:
        raise ValueError(
            f"{path} claude.permission_mode must be one of {sorted(CLAUDE_PERMISSION_MODES)}."
        )

    auth = _auth_settings(values.get("auth", {}), path)
    project_discovery = _project_discovery_settings(values.get("projects", {}), path)
    usage = _usage_settings(values.get("usage", {}), path)
    return TuiSettings(
        default_provider,
        default_model,
        default_reasoning,
        providers,
        codex_models,
        codex_reasoning,
        cursor_model,
        claude_models,
        claude_reasoning,
        modes,
        output_width,
        task_inbox_widths,
        layout,
        claude,
        auth,
        project_discovery,
        usage,
    )


def _auth_settings(values: object, path: Path) -> AuthSettings:
    """Build provider sign-in settings, rejecting literal keys in the file."""
    if not isinstance(values, dict):
        raise ValueError(f"{path} auth must be a table.")
    mode = str(values.get("mode", "account"))
    if mode not in AUTH_MODES:
        raise ValueError(f"{path} auth.mode must be one of {sorted(AUTH_MODES)}.")

    providers: dict[str, ProviderAuthSettings] = {}
    for name, table in values.items():
        if name == "mode":
            continue
        if not isinstance(table, dict):
            raise ValueError(f"{path} auth.{name} must be a table.")
        variables = _string_tuple(table.get("api_key_variables", []), path, f"auth.{name}.api_key_variables")
        for variable in variables:
            # The parameter file names variables; a value here would be a key.
            if "=" in variable or len(variable) > 64:
                raise ValueError(
                    f"{path} auth.{name}.api_key_variables must contain variable names, not values."
                )
        providers[name] = ProviderAuthSettings(
            label=str(table.get("label", name)),
            api_key_variables=variables,
            status_command=_string_tuple(table.get("status_command", []), path, f"auth.{name}.status_command"),
            sign_in_command=_string_tuple(table.get("sign_in_command", []), path, f"auth.{name}.sign_in_command"),
        )
    return AuthSettings(mode=mode, providers=providers)


def _usage_settings(values: object, path: Path) -> UsageSettings:
    """Build the usage-bar settings: cadence plus a per-provider source."""
    if not isinstance(values, dict):
        raise ValueError(f"{path} usage must be a table.")
    interval = int(values.get("interval_seconds", 60))
    timeout = float(values.get("command_timeout_seconds", 20))
    if interval < 1 or timeout <= 0:
        raise ValueError(f"{path} usage.interval_seconds and usage.command_timeout_seconds must be positive.")
    defaults = UsageSettings()
    scan_limit = int(values.get("session_scan_limit", defaults.session_scan_limit))
    tail_bytes = int(values.get("session_tail_bytes", defaults.session_tail_bytes))
    bar_width = int(values.get("bar_width", defaults.bar_width))
    transcript_days = int(values.get("claude_transcript_days", defaults.claude_transcript_days))
    account_scan_days = int(
        values.get("claude_account_scan_days", defaults.claude_account_scan_days)
    )
    if scan_limit < 1 or tail_bytes < 1 or bar_width < 1 or transcript_days < 1 or account_scan_days < 1:
        raise ValueError(
            f"{path} usage.session_scan_limit, usage.session_tail_bytes, usage.bar_width, "
            "usage.claude_transcript_days, and usage.claude_account_scan_days must be positive."
        )
    pty_columns = int(values.get("pty_columns", defaults.pty_columns))
    pty_lines = int(values.get("pty_lines", defaults.pty_lines))
    input_delay = float(values.get("input_delay_seconds", defaults.input_delay_seconds))
    command_interval = float(values.get("command_interval_seconds", defaults.command_interval_seconds))
    if pty_columns < 1 or pty_lines < 1 or input_delay < 0 or command_interval < 0:
        raise ValueError(
            f"{path} usage.pty_columns and usage.pty_lines must be positive and "
            "usage.input_delay_seconds and usage.command_interval_seconds must not be negative."
        )
    # 0 keeps the Claude progress bars calibrated against the operator's own
    # busiest window; a negative budget would silently invert them.
    five_hour_limit = int(values.get("claude_five_hour_token_limit", defaults.claude_five_hour_token_limit))
    weekly_limit = int(values.get("claude_weekly_token_limit", defaults.claude_weekly_token_limit))
    if five_hour_limit < 0 or weekly_limit < 0:
        raise ValueError(
            f"{path} usage.claude_five_hour_token_limit and usage.claude_weekly_token_limit "
            "must not be negative (0 calibrates against the busiest recorded window)."
        )
    providers: dict[str, UsageProviderSettings] = {}
    provider_tables = {
        name: table for name, table in values.items() if isinstance(table, dict)
    } or {name: {} for name in defaults.providers}
    for name, table in provider_tables.items():
        default = defaults.providers.get(name, UsageProviderSettings(name.capitalize()))
        providers[name] = UsageProviderSettings(
            label=str(table.get("label", default.label)),
            command=_string_tuple(table.get("command", list(default.command)), path, f"usage.{name}.command"),
            commands=_usage_commands(table, default, path, name),
            use_pty=bool(table.get("use_pty", default.use_pty)),
            input_text=str(table.get("input_text", default.input_text)),
            env=_usage_command_env(table.get("env", dict(default.env)), path, name),
            fallback_to_local=bool(table.get("fallback_to_local", default.fallback_to_local)),
        )
    return UsageSettings(
        enabled=bool(values.get("enabled", True)),
        interval_seconds=interval,
        command_timeout_seconds=timeout,
        command_interval_seconds=command_interval,
        codex_sessions_dir=str(values.get("codex_sessions_dir", defaults.codex_sessions_dir)),
        claude_stats_file=str(values.get("claude_stats_file", defaults.claude_stats_file)),
        claude_projects_dir=str(values.get("claude_projects_dir", defaults.claude_projects_dir)),
        claude_transcript_days=transcript_days,
        claude_account_scan_days=account_scan_days,
        claude_five_hour_token_limit=five_hour_limit,
        claude_weekly_token_limit=weekly_limit,
        session_scan_limit=scan_limit,
        session_tail_bytes=tail_bytes,
        bar_width=bar_width,
        pty_columns=pty_columns,
        pty_lines=pty_lines,
        input_delay_seconds=input_delay,
        providers=providers,
    )


def _usage_commands(
    table: dict,
    default: UsageProviderSettings,
    path: Path,
    name: str,
) -> tuple[tuple[str, ...], ...]:
    """Read a provider's candidate usage commands, each an argv list."""
    values = table.get("commands")
    if values is None:
        return default.commands
    if not isinstance(values, list):
        raise ValueError(f"{path} usage.{name}.commands must be a list of argument lists.")
    return tuple(
        _string_tuple(entry, path, f"usage.{name}.commands[{index}]")
        for index, entry in enumerate(values)
    )


def _usage_command_env(values: object, path: Path, name: str) -> dict[str, str]:
    """Read the extra environment a provider's usage commands run with."""
    if not isinstance(values, dict):
        raise ValueError(f"{path} usage.{name}.env must be a table of strings.")
    return {str(key): str(value) for key, value in values.items()}


def _project_discovery_settings(values: object, path: Path) -> ProjectDiscoverySettings:
    if not isinstance(values, dict):
        raise ValueError(f"{path} projects must be a table.")
    skipped = _string_tuple(
        values.get("skipped_directory_names", list(ProjectDiscoverySettings().skipped_directory_names)),
        path,
        "projects.skipped_directory_names",
    )
    return ProjectDiscoverySettings(
        include_git_repositories=bool(values.get("include_git_repositories", True)),
        include_all_directories=bool(values.get("include_all_directories", False)),
        skipped_directory_names=frozenset(skipped),
    )


def _string_tuple(value: object, path: Path, key: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{path} {key} must be an array of non-empty strings.")
    return tuple(value)


def load_orchestration_settings(parameter_path: Path | None = None) -> OrchestrationSettings:
    path = parameter_path or (Path(__file__).resolve().parents[1] / PARAMETER_DIRECTORY / ORCHESTRATION_PARAMETER_FILE)
    with path.open("rb") as source:
        values = tomllib.load(source)
    commands = values.get("verification_commands", [])
    if not isinstance(commands, list):
        raise ValueError(f"{path} verification_commands must be an array.")
    normalized = []
    for command in commands:
        if not isinstance(command, list) or not command or any(not isinstance(item, str) for item in command):
            raise ValueError(f"{path} verification_commands must contain non-empty string arrays.")
        normalized.append(tuple(command))
    max_concurrent_tasks = int(values.get("max_concurrent_tasks", 4))
    if max_concurrent_tasks < 1:
        raise ValueError(f"{path} max_concurrent_tasks must be positive.")
    agent_timeout_seconds = float(values.get("agent_timeout_seconds", 450))
    if agent_timeout_seconds <= 0:
        raise ValueError(f"{path} agent_timeout_seconds must be positive.")
    shutdown_grace_seconds = float(values.get("shutdown_grace_seconds", 8))
    if shutdown_grace_seconds <= 0:
        raise ValueError(f"{path} shutdown_grace_seconds must be positive.")
    # target_branch is preferred; primary_branch remains as a compatibility alias.
    target_branch = values.get("target_branch", values.get("primary_branch", "main"))
    return OrchestrationSettings(
        primary_branch=str(target_branch),
        worktree_root=str(values.get("worktree_root", ".daedalus-worktrees")),

        verification_commands=tuple(normalized),
        task_verification_attempt_limit=int(values.get("task_verification_attempt_limit", 3)),
        resolver_attempt_limit=int(values.get("resolver_attempt_limit", 3)),
        max_concurrent_tasks=max_concurrent_tasks,
        agent_timeout_seconds=agent_timeout_seconds,
        graphify_update_enabled=bool(values.get("graphify_update_enabled", True)),
        graphify_executable=str(values.get("graphify_executable", "graphify")),
        supabase_db_push_enabled=bool(values.get("supabase_db_push_enabled", True)),
        supabase_executable=str(values.get("supabase_executable", "supabase")),
        firebase_deploy_enabled=bool(values.get("firebase_deploy_enabled", True)),
        firebase_executable=str(values.get("firebase_executable", "firebase")),
        shutdown_grace_seconds=shutdown_grace_seconds,
        debug_log_filename=str(values.get("debug_log_filename", ".daedalus-debug.log")),
        dirty_primary_autocommit_enabled=bool(
            values.get("dirty_primary_autocommit_enabled", True)
        ),
        dirty_primary_commit_message=str(
            values.get("dirty_primary_commit_message", DIRTY_PRIMARY_COMMIT_MESSAGE)
        ).strip()
        or DIRTY_PRIMARY_COMMIT_MESSAGE,
        dirty_primary_push_enabled=bool(values.get("dirty_primary_push_enabled", True)),
        promotion_push_enabled=bool(values.get("promotion_push_enabled", True)),
        git_remote=str(values.get("git_remote", "origin")).strip() or "origin",
    )


def load_orchestrate_settings(
    parameter_path: Path | None = None,
    tui_settings: TuiSettings | None = None,
) -> OrchestrateSettings:
    """Load Orchestrate Mode roles, caps, budgets, and view sizes.

    ``tui_settings`` supplies the model catalogue the role models are checked
    against; it is loaded from the TUI parameter file when not given, so a
    typo in a role model fails at load time rather than when the first agent
    is launched.
    """
    path = parameter_path or (
        Path(__file__).resolve().parents[1] / PARAMETER_DIRECTORY / ORCHESTRATE_MODE_PARAMETER_FILE
    )
    try:
        with path.open("rb") as source:
            values = tomllib.load(source)
    except FileNotFoundError:
        values = {}
    roles = values.get("roles", {})
    limits = values.get("limits", {})
    files = values.get("files", {})
    ui = values.get("ui", {})
    for name, table in (("roles", roles), ("limits", limits), ("files", files), ("ui", ui)):
        if not isinstance(table, dict):
            raise ValueError(f"{path} {name} must be a table.")

    defaults = OrchestrateSettings()
    settings = OrchestrateSettings(
        planner_provider=str(roles.get("planner_provider", defaults.planner_provider)),
        planner_model=str(roles.get("planner_model", defaults.planner_model)),
        planner_reasoning=str(roles.get("planner_reasoning", defaults.planner_reasoning)),
        worker_provider=str(roles.get("worker_provider", defaults.worker_provider)),
        worker_model=str(roles.get("worker_model", defaults.worker_model)),
        worker_reasoning=str(roles.get("worker_reasoning", defaults.worker_reasoning)),
        default_max_workers=int(limits.get("default_max_workers", defaults.default_max_workers)),
        max_workers_limit=int(limits.get("max_workers_limit", defaults.max_workers_limit)),
        planner_round_limit=int(limits.get("planner_round_limit", defaults.planner_round_limit)),
        planner_repository_map_chars=int(
            limits.get("planner_repository_map_chars", defaults.planner_repository_map_chars)
        ),
        planner_context_chars=int(
            limits.get("planner_context_chars", defaults.planner_context_chars)
        ),
        task_reissue_limit=int(limits.get("task_reissue_limit", defaults.task_reissue_limit)),
        planner_digest_budget_chars=int(
            limits.get("planner_digest_budget_chars", defaults.planner_digest_budget_chars)
        ),
        worker_report_budget_chars=int(
            limits.get("worker_report_budget_chars", defaults.worker_report_budget_chars)
        ),
        worker_card_budget_chars=int(
            limits.get("worker_card_budget_chars", defaults.worker_card_budget_chars)
        ),
        session_dirname=str(files.get("session_dirname", defaults.session_dirname)),
        card_filename=str(files.get("card_filename", defaults.card_filename)),
        runtime_artifact_dirname=str(
            files.get("runtime_artifact_dirname", defaults.runtime_artifact_dirname)
        ),
        context_filename=str(files.get("context_filename", defaults.context_filename)).strip(),
        board_title_width=int(ui.get("board_title_width", defaults.board_title_width)),
        planner_log_lines=int(ui.get("planner_log_lines", defaults.planner_log_lines)),
    )

    if any(
        value < 1
        for value in (
            settings.default_max_workers,
            settings.max_workers_limit,
            settings.planner_digest_budget_chars,
            settings.worker_report_budget_chars,
            settings.worker_card_budget_chars,
            settings.board_title_width,
            settings.planner_log_lines,
        )
    ):
        raise ValueError(f"{path} limits and ui values must be positive.")
    # A card may legitimately be forbidden from re-issue, so zero is allowed.
    if settings.task_reissue_limit < 0:
        raise ValueError(f"{path} limits.task_reissue_limit must not be negative.")
    # Zero rounds means "no cap": the planner decides how many rounds it needs.
    if settings.planner_round_limit < 0:
        raise ValueError(f"{path} limits.planner_round_limit must not be negative.")
    if settings.planner_repository_map_chars < 0:
        raise ValueError(f"{path} limits.planner_repository_map_chars must not be negative.")
    if settings.planner_context_chars < 0:
        raise ValueError(f"{path} limits.planner_context_chars must not be negative.")
    if settings.context_filename.startswith("/") or ".." in Path(settings.context_filename).parts:
        raise ValueError(f"{path} files.context_filename must be a path inside the repository.")
    if settings.default_max_workers > settings.max_workers_limit:
        raise ValueError(
            f"{path} limits.default_max_workers must not exceed limits.max_workers_limit."
        )
    if not all((settings.session_dirname, settings.card_filename, settings.runtime_artifact_dirname)):
        raise ValueError(f"{path} files names must not be empty.")

    catalogue = tui_settings or load_tui_settings()
    for role, provider, model, reasoning in (
        ("planner", settings.planner_provider, settings.planner_model, settings.planner_reasoning),
        ("worker", settings.worker_provider, settings.worker_model, settings.worker_reasoning),
    ):
        validate_role_selection(catalogue, role, provider, model, reasoning, source=str(path))
    return settings


def validate_role_selection(
    catalogue: TuiSettings,
    role: str,
    provider: str,
    model: str,
    reasoning: str,
    source: str = "orchestrate settings",
) -> None:
    """Reject an Orchestrate role whose provider, model, or reasoning is not in the catalogue.

    Every provider the settings bar offers (Claude Code, Codex, Cursor CLI) may
    play either role. A provider without an effort scale, such as Cursor,
    accepts any reasoning value because the runner ignores it.
    """
    if not any(option.value == provider for option in catalogue.providers):
        known = ", ".join(option.value for option in catalogue.providers)
        raise ValueError(f"{source} roles.{role}_provider {provider!r} is not one of: {known}.")
    if not any(option.value == model for option in catalogue.models_for(provider)):
        raise ValueError(f"{source} roles.{role}_model {model!r} is not a {provider} model.")
    reasoning_options = catalogue.reasoning_for(provider)
    if reasoning_options and not any(option.value == reasoning for option in reasoning_options):
        raise ValueError(
            f"{source} roles.{role}_reasoning {reasoning!r} is not a {provider} reasoning level."
        )


def load_prompting_settings(parameter_path: Path | None = None) -> PromptingSettings:
    """Load prompt/error storage settings, anchoring a relative root to the TUI project."""
    path = parameter_path or (
        Path(__file__).resolve().parents[1] / PARAMETER_DIRECTORY / PROMPTING_PARAMETER_FILE
    )
    try:
        with path.open("rb") as source:
            values = tomllib.load(source)
    except FileNotFoundError:
        values = {}
    storage = values.get("storage", {})
    drafts = values.get("drafts", {})
    titles = values.get("titles", {})
    viewer = values.get("viewer", {})
    conversation = values.get("conversation", {})
    errors = values.get("errors", {})
    for name, table in (
        ("storage", storage),
        ("drafts", drafts),
        ("titles", titles),
        ("viewer", viewer),
        ("conversation", conversation),
        ("errors", errors),
    ):
        if not isinstance(table, dict):
            raise ValueError(f"{path} {name} must be a table.")

    # The loader convention resolves relative paths against the project that
    # owns the parameter file (parameter_files/<file> -> project root).
    project_root = path.resolve().parents[1] if path.resolve().parent.name == PARAMETER_DIRECTORY else tui_project_root()
    raw_root = str(storage.get("data_root", "."))
    data_root = Path(raw_root).expanduser()
    if not data_root.is_absolute():
        data_root = project_root / data_root
    settings = PromptingSettings(
        data_root=data_root.resolve(),
        draft_autosave_delay_ms=int(drafts.get("autosave_delay_ms", 300)),
        clear_drafts_on_exit=bool(drafts.get("clear_on_exit", True)),
        task_title_length=int(titles.get("maximum_length", 60)),
        viewer_visible_by_default=bool(viewer.get("visible_by_default", False)),
        viewer_minimum_width=int(viewer.get("minimum_width", 40)),
        main_minimum_width=int(viewer.get("main_minimum_width", 80)),
        viewer_render_debounce_ms=int(viewer.get("render_debounce_ms", 150)),
        viewer_hard_line_breaks=bool(viewer.get("hard_line_breaks", True)),
        viewer_action_items_by_default=bool(viewer.get("action_items_by_default", True)),
        viewer_action_item_limit=int(viewer.get("action_item_limit", 6)),
        conversation_context_budget_chars=int(conversation.get("context_budget_chars", 24_000)),
        error_log_max_bytes=int(errors.get("log_max_bytes", 2_000_000)),
        error_log_backup_count=int(errors.get("log_backup_count", 3)),
        run_log_max_bytes=int(errors.get("run_log_max_bytes", 1_000_000)),
    )
    if settings.draft_autosave_delay_ms < 0 or settings.viewer_render_debounce_ms < 0:
        raise ValueError(f"{path} autosave and render delays must not be negative.")
    if any(
        value < 1
        for value in (
            settings.task_title_length,
            settings.viewer_minimum_width,
            settings.viewer_action_item_limit,
            settings.main_minimum_width,
            settings.conversation_context_budget_chars,
            settings.error_log_max_bytes,
            settings.run_log_max_bytes,
        )
    ):
        raise ValueError(f"{path} sizes and widths must be positive.")
    if settings.error_log_backup_count < 0:
        raise ValueError(f"{path} errors.log_backup_count must not be negative.")
    return settings


def load_coding_statistics_settings(parameter_path: Path | None = None) -> CodingStatisticsSettings:
    path = parameter_path or (
        Path(__file__).resolve().parents[1] / PARAMETER_DIRECTORY / CODING_STATISTICS_PARAMETER_FILE
    )
    with path.open("rb") as source:
        values = tomllib.load(source)
    recent_window_hours = int(values.get("recent_window_hours", 1))
    forecast_days = int(values.get("forecast_days", 7))
    thirty_day_forecast_days = int(values.get("thirty_day_forecast_days", 30))
    if recent_window_hours < 1 or forecast_days < 1 or thirty_day_forecast_days < 1:
        raise ValueError(
            f"{path} recent_window_hours, forecast_days, and thirty_day_forecast_days must be positive."
        )
    return CodingStatisticsSettings(recent_window_hours, forecast_days, thirty_day_forecast_days)


def _options(items, kind: str) -> list[ModelOption]:
    options = []
    for item in items:
        if not isinstance(item, dict):
            continue
        options.append(ModelOption(str(item.get("label", item.get("value", ""))), str(item.get("value", ""))))
    return [option for option in options if option.value]
