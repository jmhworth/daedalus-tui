"""Read-only configuration for the standalone TUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

from .orchestrator import OrchestrationSettings


PARAMETER_DIRECTORY = "parameter_files"
TUI_PARAMETER_FILE = "daedalus-tui.toml"
ORCHESTRATION_PARAMETER_FILE = "daedalus-tui-orchestration.toml"
CODING_STATISTICS_PARAMETER_FILE = "daedalus-tui-coding-statistics.toml"
CODEX_USAGE_PARAMETER_FILE = "daedalus-tui-codex-usage.toml"
COMMAND_MENU_PARAMETER_FILE = "daedalus-tui-command-menu.toml"


@dataclass(frozen=True)
class ModelOption:
    label: str
    value: str


@dataclass(frozen=True)
class LayoutSettings:
    """Safety guard and dimensions used by the responsive TUI.

    The wide controls are measured against their laid-out regions above this
    width; the guard keeps very narrow terminals in compact mode while those
    regions are not usable yet. Compact mode moves the settings into a
    three-column grid instead of shrinking them into unreadable controls and
    uses the output and prompt heights as initial scrollable workspace sizes.
    """

    compact_width: int = 100
    short_height: int = 32
    compact_task_sidebar_height: int = 14
    compact_prompt_height: int = 8
    wide_control_min_width: int = 13
    compact_output_height: int = 16


@dataclass(frozen=True)
class TuiSettings:
    default_provider: str
    default_model: str
    default_reasoning: str
    providers: tuple[ModelOption, ...]
    codex_models: tuple[ModelOption, ...]
    codex_reasoning: tuple[ModelOption, ...]
    cursor_model: ModelOption
    modes: tuple[ModelOption, ...] = (
        ModelOption("Coding", "coding"),
        ModelOption("Ask", "ask"),
        ModelOption("Plan", "plan"),
    )
    output_width: str = "95%"
    # Content widths for task IDs and statuses, excluding DataTable padding.
    task_inbox_widths: tuple[int, int] = (12, 5)
    layout: LayoutSettings = LayoutSettings()


@dataclass(frozen=True)
class CodingStatisticsSettings:
    recent_window_hours: int = 1
    forecast_days: int = 7
    thirty_day_forecast_days: int = 30


@dataclass(frozen=True)
class CodexUsageSettings:
    executable: str = "codex"
    timeout_seconds: float = 10.0
    refresh_interval_seconds: float = 300.0


@dataclass(frozen=True)
class CommandMenuSettings:
    title: str = "Command Menu"
    subtitle: str = "Choose an action, or press Esc / Ctrl+K to close"
    new_task_label: str = "New Task"
    new_project_label: str = "New Project"
    create_topic_label: str = "Create Topic"
    personal_supabase_label: str = "Activate personal Supabase"
    remove_personal_supabase_label: str = "Remove personal Supabase"
    push_branch_label: str = "Sync to GitHub"
    auto_sync_label: str = "Auto-sync after completed tasks"
    keyboard_shortcuts_label: str = "Keyboard Shortcuts"
    pull_before_push: bool = True
    auto_sync_after_completed_tasks: bool = False
    sync_conflict_recovery_enabled: bool = True
    sync_conflict_attempt_limit: int = 3


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
    modes = tuple(_options(values.get("modes", []), "mode")) or TuiSettings.modes
    output = values.get("output", {})
    output_width = str(output.get("width", "95%"))
    task_inbox = values.get("task_inbox", {})
    task_inbox_widths = tuple(
        int(task_inbox.get(name, default))
        for name, default in (
            ("task_width", 12),
            ("status_width", 5),
        )
    )
    if any(width < 1 for width in task_inbox_widths):
        raise ValueError(f"{path} task_inbox widths must be positive.")

    layout_values = values.get("layout", {})
    layout = LayoutSettings(
        compact_width=int(layout_values.get("compact_width", 100)),
        short_height=int(layout_values.get("short_height", 32)),
        compact_task_sidebar_height=int(layout_values.get("compact_task_sidebar_height", 14)),
        compact_prompt_height=int(layout_values.get("compact_prompt_height", 8)),
        wide_control_min_width=int(layout_values.get("wide_control_min_width", 14)),
        compact_output_height=int(layout_values.get("compact_output_height", 16)),
    )
    if any(value < 1 for value in (
        layout.compact_width,
        layout.wide_control_min_width,
        layout.short_height,
        layout.compact_task_sidebar_height,
        layout.compact_prompt_height,
        layout.compact_output_height,
    )):
        raise ValueError(f"{path} layout values must be positive.")

    default_provider = str(defaults.get("provider", "codex"))
    default_model = str(defaults.get("model", "gpt-6-luna"))
    default_reasoning = str(defaults.get("reasoning", "high"))
    if not providers or not codex_models or not codex_reasoning:
        raise ValueError(f"{path} must define providers, codex_models, and codex_reasoning.")
    return TuiSettings(
        default_provider,
        default_model,
        default_reasoning,
        providers,
        codex_models,
        codex_reasoning,
        cursor_model,
        modes,
        output_width,
        task_inbox_widths,
        layout,
    )


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
        shutdown_grace_seconds=shutdown_grace_seconds,
        debug_log_filename=str(values.get("debug_log_filename", ".daedalus-debug.log")),
    )


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


def load_codex_usage_settings(parameter_path: Path | None = None) -> CodexUsageSettings:
    path = parameter_path or (
        Path(__file__).resolve().parents[1] / PARAMETER_DIRECTORY / CODEX_USAGE_PARAMETER_FILE
    )
    with path.open("rb") as source:
        values = tomllib.load(source)
    executable = str(values.get("executable", "codex")).strip()
    timeout_seconds = float(values.get("timeout_seconds", 10.0))
    refresh_interval_seconds = float(values.get("refresh_interval_seconds", 300.0))
    if not executable or timeout_seconds <= 0 or refresh_interval_seconds <= 0:
        raise ValueError(
            f"{path} executable must be non-empty and timeout/refresh intervals must be positive."
        )
    return CodexUsageSettings(executable, timeout_seconds, refresh_interval_seconds)


def load_command_menu_settings(parameter_path: Path | None = None) -> CommandMenuSettings:
    path = parameter_path or (
        Path(__file__).resolve().parents[1] / PARAMETER_DIRECTORY / COMMAND_MENU_PARAMETER_FILE
    )
    with path.open("rb") as source:
        values = tomllib.load(source)
    labels = values.get("labels", {})
    attempt_limit = int(values.get("sync_conflict_attempt_limit", 3))
    if attempt_limit < 1:
        raise ValueError(f"{path} sync_conflict_attempt_limit must be positive.")
    return CommandMenuSettings(
        title=str(values.get("title", "Command Menu")),
        subtitle=str(
            values.get("subtitle", "Choose an action, or press Esc / Ctrl+K to close")
        ),
        new_task_label=str(labels.get("new_task", "New Task")),
        new_project_label=str(labels.get("new_project", "New Project")),
        create_topic_label=str(labels.get("create_topic", "Create Topic")),
        personal_supabase_label=str(
            labels.get("personal_supabase", "Activate personal Supabase")
        ),
        remove_personal_supabase_label=str(
            labels.get("remove_personal_supabase", "Remove personal Supabase")
        ),
        push_branch_label=str(labels.get("push_branch", "Sync to GitHub")),
        auto_sync_label=str(labels.get("auto_sync", "Auto-sync after completed tasks")),
        keyboard_shortcuts_label=str(labels.get("keyboard_shortcuts", "Keyboard Shortcuts")),
        pull_before_push=bool(values.get("pull_before_push", True)),
        auto_sync_after_completed_tasks=bool(values.get("auto_sync_after_completed_tasks", False)),
        sync_conflict_recovery_enabled=bool(values.get("sync_conflict_recovery_enabled", True)),
        sync_conflict_attempt_limit=attempt_limit,
    )


def _options(items, kind: str) -> list[ModelOption]:
    options = []
    for item in items:
        if not isinstance(item, dict):
            continue
        options.append(ModelOption(str(item.get("label", item.get("value", ""))), str(item.get("value", ""))))
    return [option for option in options if option.value]
