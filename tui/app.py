"""Textual interface for concurrent local agent tasks."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import threading
import uuid

from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Log,
    LoadingIndicator,
    ProgressBar,
    Select,
    Static,
    TextArea,
)
from textual.theme import Theme
from textual.widgets import TabbedContent, TabPane
from textual.widgets.select import InvalidSelectValueError
from .agent_runner import AgentRunner
from .clipboard import copy_to_system_clipboard, paste_from_system_clipboard
from .codex_usage import CodexUsageSnapshot, fetch_codex_usage
from .config import (
    CodingStatisticsSettings,
    CommandMenuSettings,
    CodexUsageSettings,
    TuiSettings,
    load_command_menu_settings,
    load_codex_usage_settings,
    load_coding_statistics_settings,
    load_orchestration_settings,
    load_tui_settings,
)
from .debug_log import LOGGER, close_fault_handler, configure_debug_logging, install_fault_handler, log_exception
from .environment import cursor_environment, redact_environment_values
from .git_worktree import (
    GitWorktreeError,
    SyncMergeConflictError,
    list_local_branches,
    push_branch,
    remote_exists,
)
from .memory import DEFAULT_MEMORY_FILE, TaskMemoryStore
from .project_initializer import initialize_project, load_initializer_settings, validate_project_name
from .personal_supabase import (
    ActivationResult,
    PersonalSupabaseBootstrapResult,
    activate_personal_supabase,
    expose_registered_personal_supabase_schema,
    bootstrap_personal_supabase,
    is_personal_supabase_activated,
    preflight_personal_supabase,
    load_personal_supabase_settings,
    load_personal_supabase_status,
    register_personal_supabase,
    remove_personal_supabase,
    resolve_project_ref_from_environment,
    schema_from_project_root,
    temporary_supabase_cli_config,
    tui_personal_supabase_env_path,
    probe_project_personal_supabase_environment,
)
from .projects import DaedalusProject, discover_projects, is_direct_child_project
from .plan import (
    CUSTOM_ANSWER_OPTION_ID,
    PlanClarification,
    PlanQuestion,
    custom_answer_text,
    encode_custom_answer,
    is_valid_plan_answer,
    plan_answer_options,
)
from .prompts import build_topic_population_prompt
from .task_coordinator import TaskCoordinator, TaskRecord
from .supabase_migrations import ROOT_MIGRATION_LOCK, TUI_ROOT, push_migrations, synchronize_personal_migrations
from .topics import (
    TOPIC_NONE_VALUE,
    build_topic_template,
    load_topic_settings,
    load_topic_text,
    topic_path,
    topic_select_options,
    topic_slug_from_name,
    validate_topic_name,
)
from .transcript import TranscriptLog
from .token_usage import calculate_token_usage, merge_usage_entries, task_usage_entry, usage_entries_from_memory
from .verification import truncate_diagnostic
from .vim_text_area import DaedalusVimTextArea


def _literal_select_options(options: list[tuple[str, str]]) -> list[tuple[Text, str]]:
    """Build Select prompts that Rich will not parse as markup."""
    return [(Text(label), value) for label, value in options]


def _redact_supabase_diagnostic(message: str, environment: dict[str, str] | None = None) -> str:
    """Remove known credential values before diagnostics reach the UI or log."""
    return truncate_diagnostic(redact_environment_values(message, environment))


_THREAD_EXIT_APPS: dict[int, "DaedalusTuiApp"] = {}
_THREAD_EXIT_APPS_LOCK = threading.Lock()
_THREAD_EXIT_HOOK_REGISTERED = False


THEMES: dict[str, dict[str, str | bool]] = {
    "rainbow": {
        "label": "Rainbow",
        "primary": "#ff4fa3", "secondary": "#ff9f1c", "accent": "#ffe14a",
        "success": "#42e695", "warning": "#48d8ff", "error": "#ff5263",
        "foreground": "#fff6fb", "background": "#17111c", "surface": "#24182a",
        "panel": "#312039", "boost": "#452b4d", "dark": True,
        "text-muted": "#c8aacb", "text-accent": "#ffe14a",
    },
    "jet_blue": {
        "label": "Jet Black & Light Blue",
        "primary": "#59c7ff", "secondary": "#9ae1ff", "accent": "#b9eaff",
        "success": "#54d6a0", "warning": "#ffc857", "error": "#ff6b72",
        "foreground": "#d8f3ff", "background": "#05090f", "surface": "#0b1420",
        "panel": "#111e2c", "boost": "#1a2d40", "dark": True,
        "text-muted": "#79a9c4", "text-accent": "#9ae1ff",
    },
    "ember": {
        "label": "Ember",
        "primary": "#ff7043", "secondary": "#f4a261", "accent": "#ffd166",
        "success": "#8bd450", "warning": "#ffd166", "error": "#ff4d5a",
        "foreground": "#fff0df", "background": "#1c1110", "surface": "#2a1916",
        "panel": "#38211c", "boost": "#4a2b22", "dark": True,
        "text-muted": "#c49a85", "text-accent": "#ffd166",
    },
    "forest": {
        "label": "Forest",
        "primary": "#45c486", "secondary": "#82d9a6", "accent": "#c6e86b",
        "success": "#82d9a6", "warning": "#f0c75e", "error": "#f36f6f",
        "foreground": "#e4f6e9", "background": "#0d1712", "surface": "#14231a",
        "panel": "#1d3023", "boost": "#294332", "dark": True,
        "text-muted": "#91b69b", "text-accent": "#c6e86b",
    },
    "violet": {
        "label": "Violet",
        "primary": "#b58cff", "secondary": "#dbb5ff", "accent": "#ff9ed8",
        "success": "#69d5b1", "warning": "#ffd166", "error": "#ff6b89",
        "foreground": "#f1e9ff", "background": "#130f1c", "surface": "#20182d",
        "panel": "#2b2040", "boost": "#392a55", "dark": True,
        "text-muted": "#b4a1ce", "text-accent": "#dbb5ff",
    },
}


def _theme_preferences_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "daedalus-tui" / "preferences.json"


def _load_saved_theme(path: Path) -> str:
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("theme")
    except (OSError, ValueError, AttributeError):
        return "violet"
    return value if isinstance(value, str) and value in THEMES else "violet"


def _save_theme(path: Path, theme_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".preferences-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            json.dump({"theme": theme_name}, destination)
            destination.write("\n")
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _textual_theme(name: str) -> Theme:
    values = THEMES[name]
    color_names = (
        "primary", "secondary", "warning", "error", "success", "accent",
        "foreground", "background", "surface", "panel", "boost",
    )
    variables = {key: str(value) for key, value in values.items() if key.startswith("text-")}
    return Theme(
        name=f"daedalus-{name}",
        dark=bool(values["dark"]),
        **{key: str(values[key]) for key in color_names},
        variables=variables,
    )


def _shutdown_apps_before_thread_join() -> None:
    """Pause active agents before ThreadPoolExecutor joins its workers.

    CPython executes ``threading._register_atexit`` callbacks before the
    executor's own thread join. Ordinary ``atexit`` callbacks are too late:
    the executor is already waiting for an agent process by then.
    """
    with _THREAD_EXIT_APPS_LOCK:
        apps = tuple(_THREAD_EXIT_APPS.values())
    for app in apps:
        try:
            app._shutdown_before_thread_join()
        except BaseException as error:
            log_exception("Pre-thread-shutdown coordinator cleanup failed", error)


def _register_app_for_thread_exit(app: "DaedalusTuiApp") -> None:
    global _THREAD_EXIT_HOOK_REGISTERED
    with _THREAD_EXIT_APPS_LOCK:
        _THREAD_EXIT_APPS[id(app)] = app
        if _THREAD_EXIT_HOOK_REGISTERED:
            return
        register = getattr(threading, "_register_atexit", None)
        if not callable(register):
            LOGGER.warning("Python does not provide a pre-thread-shutdown hook.")
            return
        register(_shutdown_apps_before_thread_join)
        _THREAD_EXIT_HOOK_REGISTERED = True


def _unregister_app_for_thread_exit(app: "DaedalusTuiApp") -> None:
    with _THREAD_EXIT_APPS_LOCK:
        _THREAD_EXIT_APPS.pop(id(app), None)


GLOBAL_SHORTCUTS = (
    ("Ctrl+Enter", "Send prompt", "submit_prompt"),
    ("Tab", "Toggle coding/plan mode", "toggle_plan_mode"),
    ("Ctrl+C", "Copy selected text", "copy_selection"),
    ("Ctrl+Alt+S", "Copy selection", "copy_selection"),
    ("Ctrl+P", "Pause task", "pause_task"),
    ("Ctrl+R", "Resume task", "resume_task"),
    ("Ctrl+X", "Cancel task", "cancel_task"),
    ("Ctrl+T", "New task", "new_task"),
    # New Task and New Project remain direct shortcuts; the other low-frequency
    # actions are discoverable from the Command Menu opened with Ctrl+K.
    ("Ctrl+Shift+N", "New project", "show_new_project"),
    ("Ctrl+Q", "Quit", "quit"),
    ("Ctrl+K", "Open command menu", "show_command_menu"),
    ("Ctrl+U", "Show coding statistics", "show_statistics"),
)


def _shortcut_binding_key(shortcut: str) -> str:
    """Return Textual's event name for a user-facing shortcut label."""
    return shortcut.lower()


class _LegacyCompatibleBinding(Binding):
    """Expose the former four-item binding shape to local UI tests.

    Textual 8 accepts footer visibility through ``Binding.show`` rather than
    through a fourth tuple item.  The sequence methods retain the old shape
    for callers that inspect ``BINDINGS`` directly while Textual receives the
    supported Binding object.
    """

    def __len__(self) -> int:
        return 4 if self.show else 3

    def __getitem__(self, index: int) -> str | bool:
        values: tuple[str, str, str, bool] = (
            self.key,
            self.action,
            self.description,
            self.show,
        )
        return values[index]

_ACTIVE_TASK_STATUSES = {
    "queued",
    "planning",
    "questioning",
    "running",
    "verifying",
    "ready",
    "integrating",
    "resolving",
    "paused",
    "awaiting_answers",
}

SHORTCUT_SECTIONS = (
    (
        "Global shortcuts",
        tuple((shortcut, description) for shortcut, description, _ in GLOBAL_SHORTCUTS),
    ),
    (
        "Output navigation",
        (
            ("j / k", "Scroll output down / up"),
            ("gg / G", "Scroll to output start / end"),
            ("Ctrl+D / PageUp", "Scroll one page down / up"),
            ("y", "Copy selected text"),
            ("p", "Paste into the prompt"),
            ("i", "Focus the prompt"),
        ),
    ),
    (
        "Prompt (Vim mode)",
        (
            ("Enter", "Send prompt"),
            ("Shift+Enter", "Insert a new line"),
            ("Esc", "Enter Normal mode"),
            ("i / a / o", "Enter Insert mode"),
            ("h / j / k / l", "Move the cursor"),
            ("w / e / 0 / $", "Move by word or line"),
            ("gg / G", "Move to document start / end"),
            ("d / u", "Delete / undo"),
            ("y / p", "Yank / paste"),
            ("V", "Select whole lines"),
        ),
    ),
)

COMPACT_SETTING_CATEGORIES = (
    ("Model provider", "provider"),
    ("Model", "model"),
    ("Reasoning", "reasoning"),
    ("Mode", "mode"),
    ("Topic", "topic"),
    ("Operating branch", "branch"),
)


class PlanAnswerSelect(Select):
    """Initialize dynamic plan selectors after their nested children mount."""

    @on(events.Mount)
    def _on_plan_answer_mount(self, event: events.Mount) -> None:
        # Textual 8.2.x can dispatch a dynamically mounted Select's mount
        # handler before SelectCurrent has mounted its internal ``#label``.
        # The base Select handler is a naming-convention handler and would
        # otherwise also run after this method, so prevent its default action.
        event.prevent_default()
        self.call_after_refresh(self._initialize_after_mount)

    def _initialize_after_mount(self) -> None:
        """Finish Select setup without allowing a stale value to exit the TUI.

        Plan follow-up rounds remount these widgets while a prior
        ``call_after_refresh`` may still be queued. An illegal constructor
        hint or a half-removed overlay must not reach Textual's fatal handler
        (seen in production as ``InvalidSelectValueError: Illegal select value
        'replace'`` right after a plan returned ``awaiting_answers``).
        """
        if not self.is_attached or self._closing:
            return
        try:
            self._setup_options_renderables()
            hint = self._value if self._value in self._legal_values else self.NULL
            self._init_selected_option(hint)
        except (InvalidSelectValueError, NoMatches, Exception) as error:
            # call_after_refresh is outside the plan-questions worker, so an
            # uncaught error here is a hard TUI exit with no on-screen message.
            log_exception(
                f"Plan answer Select init failed id={self.id!r} value={self._value!r}",
                error,
            )
            try:
                if self.is_attached and not self._closing and self.NULL in self._legal_values:
                    self.value = self.NULL
            except Exception as recovery_error:
                log_exception("Plan answer Select recovery failed", recovery_error)
                self._value = self.NULL


class CompactSettingsSelect(Select):
    """Keep only the latest value-change event for rebuilt compact controls."""

    def _watch_value(self, value) -> None:
        super()._watch_value(value)
        self._latest_value = value
        if self.id != "compact-settings-category" or value not in dict(COMPACT_SETTING_CATEGORIES).values():
            return
        try:
            app = self.app
            if app is not None and not app._suppress_compact_setting_change:
                app._compact_setting_category = str(value)
                app._refresh_compact_setting_value(str(value), sync_category=False)
        except Exception:
            # The category watcher also runs while the app is mounting, before
            # the sibling value control is available.
            return

    def _validate_value(self, value):
        if self.id == "compact-settings-value" and isinstance(value, str):
            return value
        return super()._validate_value(value)


class PlanClarificationScreen(ModalScreen[str | None]):
    """Collect a clarification about one plan question."""

    BINDINGS = [
        ("escape", "cancel_clarification", "Cancel"),
    ]

    def __init__(self, question_text: str) -> None:
        super().__init__()
        self.question_text = question_text

    def compose(self) -> ComposeResult:
        with Vertical(id="plan-clarification-dialog"):
            yield Static("Clarify this plan question", id="plan-clarification-title")
            yield Static(self.question_text, id="plan-clarification-question", markup=False)
            yield Static(
                "Ask what the agent means. This stays separate from plan answers.",
                id="plan-clarification-subtitle",
            )
            yield TextArea(
                id="plan-clarification-input",
                placeholder="What do you mean by this question?",
            )
            with Horizontal(id="plan-clarification-actions"):
                yield Button("Ask", id="ask-clarification-button", variant="primary")
                yield Button("Cancel", id="cancel-clarification-button")

    def on_mount(self) -> None:
        self.query_one("#plan-clarification-input", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ask-clarification-button":
            text = self.query_one("#plan-clarification-input", TextArea).text.strip()
            if not text:
                return
            self.dismiss(text)
        elif event.button.id == "cancel-clarification-button":
            self.dismiss(None)

    def action_cancel_clarification(self) -> None:
        self.dismiss(None)


class KeyboardShortcutsScreen(ModalScreen[None]):
    """Modal reference for the app and prompt editor keyboard shortcuts."""

    BINDINGS = [
        ("escape", "close_shortcuts", "Close"),
        ("ctrl+k", "close_shortcuts", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="shortcuts-dialog"):
            yield Static("Keyboard shortcuts", id="shortcuts-title")
            yield Static("Press Esc or Ctrl+K to close", id="shortcuts-subtitle")
            for heading, shortcuts in SHORTCUT_SECTIONS:
                yield Static(heading, classes="shortcut-section")
                for shortcut, description in shortcuts:
                    yield Static(f"{shortcut:<18}{description}", classes="shortcut-row")

    def action_close_shortcuts(self) -> None:
        self.dismiss(None)


class CommandMenuScreen(ModalScreen[str | None]):
    """Offer low-frequency actions as discoverable buttons."""

    BINDINGS = [
        ("escape", "close_command_menu", "Close"),
        ("ctrl+k", "close_command_menu", "Close"),
    ]

    def __init__(self, settings: CommandMenuSettings | None = None) -> None:
        super().__init__()
        self.settings = settings or load_command_menu_settings()

    def compose(self) -> ComposeResult:
        with Vertical(id="command-menu-dialog"):
            yield Static(self.settings.title, id="command-menu-title")
            yield Static(
                self.settings.subtitle,
                id="command-menu-subtitle",
            )
            with TabbedContent(initial="technical-tab", id="command-menu-tabs"):
                with TabPane("Technical", id="technical-tab"):
                    with VerticalScroll(classes="command-actions"):
                        yield Button(
                            self.settings.new_task_label,
                            id="command-new-task-button",
                            variant="primary",
                        )
                        yield Button(self.settings.new_project_label, id="command-new-project-button")
                        yield Button(self.settings.create_topic_label, id="command-create-topic-button")
                        yield Button(
                            self.settings.personal_supabase_label,
                            id="command-register-supabase-button",
                        )
                        yield Button(
                            self.settings.remove_personal_supabase_label,
                            id="command-remove-supabase-button",
                            variant="error",
                        )
                        yield Button(self.settings.push_branch_label, id="command-push-branch-button")
                        yield Button(self._auto_sync_label(), id="command-auto-sync-button")
                        yield Button(
                            self.settings.keyboard_shortcuts_label,
                            id="command-show-shortcuts-button",
                        )
                with TabPane("Appearance", id="appearance-tab"):
                    yield Static("Make every screen feel like yours.", classes="appearance-copy")
                    yield Button("Pick Theme", id="command-pick-theme-button", variant="primary")

    def on_mount(self) -> None:
        self.app._refresh_push_button()
        self.query_one("#command-new-task-button", Button).focus()

    def _auto_sync_label(self) -> str:
        state = "On" if self.app.auto_sync_after_completed_tasks else "Off"
        return f"{self.settings.auto_sync_label}: {state}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "command-new-task-button": "new_task",
            "command-new-project-button": "show_new_project",
            "command-create-topic-button": "show_create_topic",
            "command-register-supabase-button": "register_personal_supabase",
            "command-remove-supabase-button": "remove_personal_supabase",
            "command-push-branch-button": "push_branch",
            "command-auto-sync-button": "toggle_auto_sync",
            "command-show-shortcuts-button": "show_shortcuts",
            "command-pick-theme-button": "pick_theme",
        }
        action = actions.get(event.button.id)
        if action is not None:
            if action == "toggle_auto_sync":
                self.app._toggle_auto_sync_after_tasks()
                event.button.label = self._auto_sync_label()
                return
            self.dismiss(action)

    def action_close_command_menu(self) -> None:
        self.dismiss(None)


class ThemePickerScreen(ModalScreen[str | None]):
    """Choose a built-in app-wide color theme."""

    BINDINGS = [
        ("escape", "close_theme_picker", "Back"),
        ("ctrl+k", "close_theme_picker", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-picker-dialog"):
            yield Static("Pick Theme", id="theme-picker-title")
            yield Static("Color across every screen", id="theme-picker-subtitle")
            for theme_name, values in THEMES.items():
                yield Button(str(values["label"]), id=f"theme-{theme_name}-button")

    def on_mount(self) -> None:
        self.query_one(f"#theme-{self.app.selected_theme}-button", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("theme-"):
            self.dismiss(event.button.id.removeprefix("theme-").removesuffix("-button"))

    def action_close_theme_picker(self) -> None:
        self.dismiss(None)


class PersonalSupabaseConfirmationScreen(ModalScreen[bool]):
    """Require an explicit confirmation before scaffolding/Activating a shared schema."""

    BINDINGS = [
        ("escape", "cancel_registration", "Cancel"),
    ]

    def __init__(self, project_name: str) -> None:
        super().__init__()
        self.project_name = project_name
        self.settings = load_personal_supabase_settings()

    def compose(self) -> ComposeResult:
        with Vertical(id="personal-supabase-confirmation-dialog"):
            yield Static(
                str(self.settings["confirmation_title"]),
                id="personal-supabase-confirmation-title",
            )
            yield Static(
                str(self.settings["confirmation_warning"]),
                id="personal-supabase-confirmation-warning",
                markup=False,
            )
            yield Static(
                f"{self.settings['confirmation_name_prompt']}\n{self.project_name}",
                id="personal-supabase-confirmation-prompt",
                markup=False,
            )
            yield Input(
                id="personal-supabase-confirmation-input",
                placeholder=self.project_name,
            )
            yield Static("", id="personal-supabase-confirmation-status")
            with Horizontal(id="personal-supabase-confirmation-actions"):
                yield Button(
                    str(self.settings["confirmation_button_label"]),
                    id="confirm-personal-supabase-button",
                    variant="error",
                    disabled=True,
                )
                yield Button("Cancel", id="cancel-personal-supabase-button")

    def on_mount(self) -> None:
        self.query_one("#personal-supabase-confirmation-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "personal-supabase-confirmation-input":
            return
        matches = event.value == self.project_name
        self.query_one("#confirm-personal-supabase-button", Button).disabled = not matches
        if matches:
            self.query_one("#personal-supabase-confirmation-status", Static).update("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "personal-supabase-confirmation-input":
            self._confirm()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-personal-supabase-button":
            self.dismiss(False)
        elif event.button.id == "confirm-personal-supabase-button":
            self._confirm()

    def action_cancel_registration(self) -> None:
        self.dismiss(False)

    def _confirm(self) -> None:
        entered = self.query_one("#personal-supabase-confirmation-input", Input).value
        if entered != self.project_name:
            self.query_one("#personal-supabase-confirmation-status", Static).update(
                "Type the project name exactly to enable Activate."
            )
            self.query_one("#personal-supabase-confirmation-input", Input).focus()
            return
        self.dismiss(True)


class PersonalSupabaseSetupWizardScreen(ModalScreen[bool]):
    """Guide scaffold completion and manual project env setup before Activate."""

    BINDINGS = [
        ("escape", "cancel_wizard", "Cancel"),
    ]

    def __init__(self, project_path: Path, schema: str) -> None:
        super().__init__()
        self.project_path = project_path.resolve()
        self.schema = schema
        self.settings = load_personal_supabase_settings()
        self._scaffold_ready = False

    def compose(self) -> ComposeResult:
        with Vertical(id="personal-supabase-wizard-dialog"):
            yield Static(
                str(self.settings["wizard_title"]),
                id="personal-supabase-wizard-title",
            )
            yield Static(
                "Preparing scaffold…",
                id="personal-supabase-wizard-scaffold",
                markup=False,
            )
            yield Static(
                "",
                id="personal-supabase-wizard-instructions",
                markup=False,
            )
            yield Static("", id="personal-supabase-wizard-status", markup=False)
            with Horizontal(id="personal-supabase-wizard-actions"):
                yield Button(
                    str(self.settings["wizard_continue_label"]),
                    id="continue-personal-supabase-wizard-button",
                    variant="primary",
                    disabled=True,
                )
                yield Button(
                    str(self.settings["wizard_cancel_label"]),
                    id="cancel-personal-supabase-wizard-button",
                )

    def on_mount(self) -> None:
        result = register_personal_supabase(self.project_path, schema=self.schema)
        scaffold = self.query_one("#personal-supabase-wizard-scaffold", Static)
        instructions = self.query_one("#personal-supabase-wizard-instructions", Static)
        status = self.query_one("#personal-supabase-wizard-status", Static)
        continue_button = self.query_one("#continue-personal-supabase-wizard-button", Button)
        if result.status != "success":
            scaffold.update(result.message or "Scaffold failed.")
            status.update(result.message or "Scaffold failed.")
            continue_button.disabled = True
            self._scaffold_ready = False
            return
        self._scaffold_ready = True
        scaffold.update(
            str(self.settings["wizard_scaffold_done"]).format(schema=self.schema)
        )
        env_path = tui_personal_supabase_env_path()
        instructions.update(
            str(self.settings["wizard_env_instructions"]).format(
                env_path=env_path,
                schema=self.schema,
            )
        )
        status.update("")
        continue_button.disabled = False
        continue_button.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-personal-supabase-wizard-button":
            self.dismiss(False)
        elif event.button.id == "continue-personal-supabase-wizard-button":
            self._continue()

    def action_cancel_wizard(self) -> None:
        self.dismiss(False)

    def _continue(self) -> None:
        if not self._scaffold_ready:
            return
        status = self.query_one("#personal-supabase-wizard-status", Static)
        # Presence only: child process exit code, never load secret values here.
        present, error = probe_project_personal_supabase_environment(
            self.project_path,
            require_database_access=True,
        )
        if not present:
            missing_prefix = str(self.settings["wizard_env_missing"])
            env_path = tui_personal_supabase_env_path()
            detail = error or "required Supabase settings are missing."
            status.update(f"{missing_prefix} Checked {env_path}. {detail}")
            return
        status.update("")
        self.dismiss(True)


class PersonalSupabaseRemovalConfirmationScreen(ModalScreen[bool]):
    """Require an exact project-name confirmation before local cleanup."""

    BINDINGS = [
        ("escape", "cancel_removal", "Cancel"),
    ]

    def __init__(self, project_name: str) -> None:
        super().__init__()
        self.project_name = project_name

    def compose(self) -> ComposeResult:
        with Vertical(id="personal-supabase-removal-dialog"):
            yield Static("Remove personal Supabase", id="personal-supabase-removal-title")
            yield Static(
                "This removes daedalus-migrations/, generated Supabase entries from .env.example and agent profiles, the managed credential block from the project .env, and the personal_supabase entry in .daedalus. Empty generated agent directories are removed; directories with other files are kept. The remote database is left untouched.",
                id="personal-supabase-removal-warning",
                markup=False,
            )
            yield Static(
                f"Type the project name exactly to confirm:\n{self.project_name}",
                id="personal-supabase-removal-prompt",
                markup=False,
            )
            yield Input(
                id="personal-supabase-removal-input",
                placeholder=self.project_name,
            )
            yield Static("", id="personal-supabase-removal-status")
            with Horizontal(id="personal-supabase-removal-actions"):
                yield Button(
                    "Remove",
                    id="confirm-personal-supabase-removal-button",
                    variant="error",
                    disabled=True,
                )
                yield Button("Cancel", id="cancel-personal-supabase-removal-button")

    def on_mount(self) -> None:
        self.query_one("#personal-supabase-removal-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "personal-supabase-removal-input":
            return
        matches = event.value == self.project_name
        self.query_one("#confirm-personal-supabase-removal-button", Button).disabled = not matches
        if matches:
            self.query_one("#personal-supabase-removal-status", Static).update("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "personal-supabase-removal-input":
            self._confirm()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-personal-supabase-removal-button":
            self.dismiss(False)
        elif event.button.id == "confirm-personal-supabase-removal-button":
            self._confirm()

    def action_cancel_removal(self) -> None:
        self.dismiss(False)

    def _confirm(self) -> None:
        entered = self.query_one("#personal-supabase-removal-input", Input).value
        if entered != self.project_name:
            self.query_one("#personal-supabase-removal-status", Static).update(
                "Type the project name exactly to enable removal."
            )
            self.query_one("#personal-supabase-removal-input", Input).focus()
            return
        self.dismiss(True)


class PersonalSupabaseActivationProgressScreen(ModalScreen[str | None]):
    """Show the durable activation phases while the worker runs."""

    BINDINGS = [
        ("escape", "close_activation_progress", "Close"),
    ]

    _STAGE_MESSAGES = {
        "Scaffolding project files": 0,
        "Using existing scaffold": 0,
        "Validating scaffold": 1,
        "Committing scaffold changes": 2,
        "Validating environment": 3,
        "Checking Supabase connection": 4,
        "Synchronize and apply migrations from the Daedalus TUI root": 5,
    }

    def __init__(self, project_name: str, schema: str) -> None:
        super().__init__()
        self.project_name = project_name
        self.schema = schema
        self.settings = load_personal_supabase_settings()
        self.stages = tuple(str(stage) for stage in self.settings["activation_progress_stages"])
        self._activation_running = True
        self._current_stage_index = -1
        self._pending_progress: str | None = None
        self._pending_finish: tuple[bool, str] | None = None

    @property
    def running(self) -> bool:
        """Whether the activation worker still owns this progress surface."""
        return self._activation_running

    def compose(self) -> ComposeResult:
        with Vertical(id="personal-supabase-progress-dialog"):
            yield Static(
                str(self.settings["activation_progress_title"]),
                id="personal-supabase-progress-title",
            )
            yield Static(
                f"{self.settings['activation_progress_subtitle']}\n"
                f"Project: {self.project_name}  ·  Schema: {self.schema}",
                id="personal-supabase-progress-subtitle",
                markup=False,
            )
            yield ProgressBar(
                total=len(self.stages),
                show_eta=False,
                id="personal-supabase-progress-bar",
            )
            yield Static(
                "Checking registration…",
                id="personal-supabase-progress-status",
                markup=False,
            )
            with Vertical(id="personal-supabase-progress-steps"):
                for index, stage in enumerate(self.stages):
                    yield Static(
                        f"○ {stage}",
                        id=f"personal-supabase-progress-step-{index}",
                        markup=False,
                    )
            with Horizontal(id="personal-supabase-progress-actions"):
                yield Button(
                    str(self.settings["activation_progress_close_label"]),
                    id="close-personal-supabase-progress-button",
                    disabled=True,
                )
                yield Button(
                    "Expose schema",
                    id="expose-personal-supabase-schema-button",
                    disabled=True,
                )

    def on_mount(self) -> None:
        """Apply worker results that arrived while this modal was mounting."""
        if self._pending_progress is not None:
            message = self._pending_progress
            self._pending_progress = None
            self._update_progress(message)
        if self._pending_finish is not None:
            succeeded, detail = self._pending_finish
            self._pending_finish = None
            self._apply_finish(succeeded, detail)

    def update_progress(self, message: str) -> None:
        """Mark the current activation phase and retain a readable status line."""
        if not self._is_mounted:
            self._pending_progress = message
            return
        self._update_progress(message)

    def _update_progress(self, message: str) -> None:
        """Update mounted progress widgets for one worker phase."""
        self.query_one("#personal-supabase-progress-status", Static).update(message)
        stage_index = self._STAGE_MESSAGES.get(message)
        if stage_index is None:
            stage_index = next(
                (index for index, stage in enumerate(self.stages) if stage == message),
                None,
            )
        if stage_index is None:
            return
        self._current_stage_index = stage_index
        for index, _stage in enumerate(self.stages):
            if index < stage_index:
                marker = "✓"
            elif index == stage_index:
                marker = "⟳"
            else:
                marker = "○"
            self.query_one(f"#personal-supabase-progress-step-{index}", Static).update(
                f"{marker} {self.stages[index]}"
            )
        self.query_one("#personal-supabase-progress-bar", ProgressBar).update(
            progress=stage_index
        )

    def finish(self, succeeded: bool, detail: str) -> None:
        """Freeze the progress display and allow the operator to close it."""
        self._activation_running = False
        if not self._is_mounted:
            self._pending_finish = (succeeded, detail)
            return
        self._apply_finish(succeeded, detail)

    def _apply_finish(self, succeeded: bool, detail: str) -> None:
        """Render a completion state after all modal widgets are mounted."""
        if succeeded:
            for index, _stage in enumerate(self.stages):
                self.query_one(f"#personal-supabase-progress-step-{index}", Static).update(
                    f"✓ {self.stages[index]}"
                )
            self.query_one("#personal-supabase-progress-bar", ProgressBar).update(
                progress=len(self.stages)
            )
            status = detail or "Personal Supabase is activated."
            self.query_one("#expose-personal-supabase-schema-button", Button).disabled = False
        else:
            if 0 <= self._current_stage_index < len(self.stages):
                self.query_one(
                    f"#personal-supabase-progress-step-{self._current_stage_index}",
                    Static,
                ).update(f"✗ {self.stages[self._current_stage_index]}")
            status = f"Activation blocked: {detail or 'Activation failed.'}"
        self.query_one("#personal-supabase-progress-status", Static).update(status)
        self.query_one("#close-personal-supabase-progress-button", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "expose-personal-supabase-schema-button" and not self._activation_running:
            self.dismiss("expose")
        elif event.button.id == "close-personal-supabase-progress-button" and not self._activation_running:
            self.dismiss(None)

    def action_close_activation_progress(self) -> None:
        if not self._activation_running:
            self.dismiss(None)


class PersonalSupabaseExposureErrorScreen(ModalScreen[None]):
    """Show the specific reason hosted schema exposure failed."""

    BINDINGS = [
        ("escape", "close_error", "Close"),
    ]

    def __init__(self, detail: str) -> None:
        super().__init__()
        self.detail = detail
        self.settings = load_personal_supabase_settings()

    def compose(self) -> ComposeResult:
        with Vertical(id="personal-supabase-exposure-error-dialog"):
            yield Static(
                str(self.settings["exposure_error_title"]),
                id="personal-supabase-exposure-error-title",
            )
            yield Static(
                str(self.settings["exposure_error_intro"]),
                id="personal-supabase-exposure-error-intro",
                markup=False,
            )
            with VerticalScroll(id="personal-supabase-exposure-error-scroll"):
                yield Static(
                    self.detail,
                    id="personal-supabase-exposure-error-detail",
                    markup=False,
                )
            with Horizontal(id="personal-supabase-exposure-error-actions"):
                yield Button("Close", id="close-personal-supabase-exposure-error-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-personal-supabase-exposure-error-button":
            self.dismiss(None)

    def action_close_error(self) -> None:
        self.dismiss(None)


class ProjectInitializerScreen(ModalScreen[dict | None]):
    """Collect a project slug and create a Daedalus-compatible directory."""

    BINDINGS = [
        ("escape", "cancel_initializer", "Cancel"),
    ]

    def __init__(self, launch_root: Path) -> None:
        super().__init__()
        self.launch_root = launch_root.resolve()
        self._busy = False

    def compose(self) -> ComposeResult:
        with Vertical(id="project-initializer-dialog"):
            yield Static("New Daedalus project", id="project-initializer-title")
            yield Static(
                f"Creates a folder under {self.launch_root}",
                id="project-initializer-subtitle",
            )
            yield Static("Project name (lowercase, digits, hyphens)", id="project-name-label")
            yield Input(placeholder="example-project", id="project-name-input")
            yield Checkbox("Also create a private GitHub repository", id="project-github-checkbox")
            yield Static("", id="project-initializer-status")
            with Horizontal(id="project-initializer-actions"):
                yield Button("Create", id="create-project-button", variant="primary")
                yield Button("Cancel", id="cancel-project-button")

    def on_mount(self) -> None:
        self.query_one("#project-name-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-project-button":
            self.dismiss(None)
        elif event.button.id == "create-project-button":
            self._create_project()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "project-name-input":
            self._create_project()

    def action_cancel_initializer(self) -> None:
        if not self._busy:
            self.dismiss(None)

    def _create_project(self) -> None:
        if self._busy:
            return
        status = self.query_one("#project-initializer-status", Static)
        name_input = self.query_one("#project-name-input", Input)
        create_github = self.query_one("#project-github-checkbox", Checkbox).value
        try:
            settings = load_initializer_settings()
            project_name = validate_project_name(
                name_input.value,
                int(settings["maximum_project_name_length"]),
            )
        except ValueError as error:
            status.update(str(error))
            name_input.focus()
            return

        self._initialize_project(project_name, create_github)

    def _initialize_project(
        self,
        project_name: str,
        create_github: bool,
    ) -> None:
        status = self.query_one("#project-initializer-status", Static)
        self._busy = True
        status.update(f"Initializing {project_name}…")
        self.query_one("#create-project-button", Button).disabled = True
        try:
            result = initialize_project(
                {
                    "requestId": str(uuid.uuid4()),
                    "projectName": project_name,
                    "createGitHubRepository": create_github,
                },
                execution_root=self.launch_root,
            )
        except ValueError as error:
            self._busy = False
            self.query_one("#create-project-button", Button).disabled = False
            status.update(str(error))
            return

        if result["status"] in {"success", "partial_success"}:
            self.dismiss(result)
            return

        self._busy = False
        self.query_one("#create-project-button", Button).disabled = False
        status.update(str(result.get("error") or "Initialization failed."))


class CreateTopicScreen(ModalScreen[dict | None]):
    """Collect the context needed to initialize and populate a topic file."""

    BINDINGS = [
        ("escape", "cancel_topic_creation", "Cancel"),
    ]

    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root.resolve()

    def compose(self) -> ComposeResult:
        with Vertical(id="create-topic-dialog"):
            yield Static("Create Topic", id="create-topic-title")
            yield Static(
                "Describe the shared context and desired end state; a coding agent will finish the markdown.",
                id="create-topic-subtitle",
            )
            yield Static("Topic name", id="topic-name-label")
            yield Input(placeholder="Example: Trading strategy MVP", id="topic-name-input")
            yield Static("Topic context and desired end state", id="topic-goal-label")
            yield TextArea(
                id="topic-goal-input",
                placeholder=(
                    "What is this topic about? What should be true when it is complete? "
                    "Include constraints, decisions, and useful starting context."
                ),
            )
            yield Static("", id="create-topic-status")
            with Horizontal(id="create-topic-actions"):
                yield Button("Create and Populate", id="create-topic-button", variant="primary")
                yield Button("Cancel", id="cancel-topic-button")

    def on_mount(self) -> None:
        self.query_one("#topic-name-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-topic-button":
            self.dismiss(None)
        elif event.button.id == "create-topic-button":
            self._create_topic()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "topic-name-input":
            self.query_one("#topic-goal-input", TextArea).focus()

    def action_cancel_topic_creation(self) -> None:
        self.dismiss(None)

    def _create_topic(self) -> None:
        name_input = self.query_one("#topic-name-input", Input)
        goal_input = self.query_one("#topic-goal-input", TextArea)
        status = self.query_one("#create-topic-status", Static)
        try:
            settings = load_topic_settings()
            name = validate_topic_name(
                name_input.value,
                int(settings["maximum_topic_name_length"]),
            )
            goal = goal_input.text.strip()
            if not goal:
                raise ValueError("Topic context and desired end state are required.")
            if len(goal) > int(settings["maximum_topic_goal_length"]):
                raise ValueError(
                    "Topic context and desired end state must be at most "
                    f"{settings['maximum_topic_goal_length']} characters."
                )
            slug = topic_slug_from_name(name, int(settings["maximum_topic_slug_length"]))
            if topic_path(self.project_root, slug).exists():
                raise ValueError(f"Topic already exists: {slug}")
        except (KeyError, TypeError, ValueError) as error:
            status.update(str(error))
            name_input.focus()
            return

        self.dismiss(
            {
                "name": name,
                "slug": slug,
                "goal": goal,
                "template": build_topic_template(name, goal),
            }
        )


class TopicViewerScreen(ModalScreen[None]):
    """Display a topic markdown file without allowing edits."""

    BINDINGS = [
        ("escape", "close_topic_viewer", "Close"),
    ]

    def __init__(self, topic_slug: str, topic_text: str) -> None:
        super().__init__()
        self.topic_slug = topic_slug
        self.topic_text = topic_text

    def compose(self) -> ComposeResult:
        with Vertical(id="topic-view-dialog"):
            yield Static(f"Topic: {self.topic_slug}", id="topic-view-title")
            yield Static(
                "Read-only view · Select text to copy · Press Esc to close",
                id="topic-view-subtitle",
            )
            yield TextArea(
                self.topic_text,
                id="topic-view-content",
                read_only=True,
                soft_wrap=False,
            )
            with Horizontal(id="topic-view-actions"):
                yield Button("Close", id="close-topic-view-button")

    def on_mount(self) -> None:
        self.query_one("#topic-view-content", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-topic-view-button":
            self.dismiss(None)

    def action_close_topic_viewer(self) -> None:
        self.dismiss(None)


class CodingStatisticsScreen(ModalScreen[None]):
    """Show token or task usage history and derived coding statistics."""

    BINDINGS = [
        ("escape", "close_statistics", "Close"),
        ("ctrl+u", "close_statistics", "Close"),
    ]

    def __init__(
        self,
        entries,
        settings: CodingStatisticsSettings | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings or CodingStatisticsSettings()
        self.stats = calculate_token_usage(
            entries,
            recent_window_hours=self.settings.recent_window_hours,
            forecast_days=self.settings.forecast_days,
            thirty_day_forecast_days=self.settings.thirty_day_forecast_days,
        )
        self.unit = "tokens"

    def compose(self) -> ComposeResult:
        with Vertical(id="coding-statistics-dialog"):
            yield Static("Coding statistics", id="coding-statistics-title")
            with Horizontal(id="coding-statistics-controls"):
                yield Static("Measure", id="statistics-unit-label")
                yield Select(
                    [("Tokens", "tokens"), ("Tasks", "tasks")],
                    value="tokens",
                    allow_blank=False,
                    id="statistics-unit-select",
                )
            yield Static("Token usage from recorded local tasks", id="coding-statistics-subtitle")
            with Horizontal(id="coding-statistics-summary"):
                yield Static(id="cumulative-metric", classes="usage-metric")
                yield Static(id="daily-metric", classes="usage-metric")
                yield Static(id="thirty-day-metric", classes="usage-metric")
            with Horizontal(id="coding-statistics-body"):
                with Vertical(id="usage-history-panel"):
                    yield Static("Task usage", classes="statistics-heading")
                    yield DataTable(id="usage-table", cursor_type="row")
                with Vertical(id="usage-breakdown-panel"):
                    yield Static("Statistics", classes="statistics-heading")
                    yield Static(id="average-metric", classes="statistics-value")
                    yield Static(id="recent-metric", classes="statistics-value")
                    yield Static(id="seven-day-metric", classes="statistics-value")
                    yield Static(id="thirty-day-statistic", classes="statistics-value")
                    yield Static(id="provider-split", classes="statistics-value")
            yield Static("Press Esc or Ctrl+U to close", id="coding-statistics-footer")

    def on_mount(self) -> None:
        self._refresh_statistics_view()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "statistics-unit-select" or event.value in (Select.BLANK, ""):
            return
        self.unit = str(event.value)
        self._refresh_statistics_view()

    def _refresh_statistics_view(self) -> None:
        unit = self.unit
        is_tasks = unit == "tasks"
        suffix = "tasks" if is_tasks else "tokens"
        cumulative = self.stats.cumulative_tasks if is_tasks else self.stats.cumulative_tokens
        daily = self.stats.daily_tasks if is_tasks else self.stats.daily_tokens
        recent = self.stats.last_hour_tasks if is_tasks else self.stats.last_hour_tokens
        seven_day = self.stats.seven_day_expected_tasks if is_tasks else self.stats.seven_day_expected_tokens
        thirty_day = self.stats.thirty_day_expected_tasks if is_tasks else self.stats.thirty_day_expected_tokens
        self.query_one("#coding-statistics-subtitle", Static).update(
            f"{suffix.capitalize()} from recorded local tasks"
        )
        self.query_one("#cumulative-metric", Static).update(
            f"Cumulative {suffix}\n{_format_count(cumulative)}"
        )
        self.query_one("#daily-metric", Static).update(
            f"Today's {suffix}\n{_format_count(daily)}"
        )
        self.query_one("#thirty-day-metric", Static).update(
            f"Monthly projected {suffix}\n{_format_count(thirty_day)}"
        )
        self.query_one("#average-metric", Static).update(self._average_per_prompt_text())
        self.query_one("#recent-metric", Static).update(
            f"Last hour {suffix} usage\n{_format_count(recent)}"
        )
        self.query_one("#seven-day-metric", Static).update(
            f"Weekly projected {suffix}\n{_format_count(seven_day)}"
        )
        self.query_one("#thirty-day-statistic", Static).update(
            f"Monthly projected {suffix}\n{_format_count(thirty_day)}"
        )
        self.query_one("#provider-split", Static).update(self._provider_split_text())

        table = self.query_one("#usage-table", DataTable)
        table.clear(columns=True)
        rows = [
            (
                entry.timestamp.astimezone().strftime("%Y-%m-%d %H:%M"),
                entry.provider,
                "1" if is_tasks else _format_tokens(entry.tokens),
            )
            for entry in self.stats.entries
        ]
        if not rows:
            rows = [("—", "No recorded tasks", "0")]

        # Set widths before adding rows so DataTable doesn't render once with
        # header-only auto widths and cache clipped cell content.
        table.add_column(
            "Timestamp", width=max(len("Timestamp"), *(len(row[0]) for row in rows))
        )
        table.add_column(
            "Provider", width=max(len("Provider"), *(len(row[1]) for row in rows))
        )
        table.add_column(
            suffix.capitalize(), width=max(len(suffix), *(len(row[2]) for row in rows))
        )
        for row in rows:
            table.add_row(*row)

    def action_close_statistics(self) -> None:
        self.dismiss(None)

    def _average_per_prompt_text(self) -> str:
        suffix = "tasks" if self.unit == "tasks" else "tokens"
        lines = [f"Average {suffix} per prompt"]
        averages = self.stats.average_per_prompt(self.unit)
        if not averages:
            lines.append(f"No {suffix} recorded")
        else:
            lines.extend(
                f"{provider}: {average:,.0f}"
                for provider, average in averages
            )
        return "\n".join(lines)

    def _provider_split_text(self) -> str:
        lines = ["Provider usage"]
        split = self.stats.provider_split(self.unit)
        suffix = "tasks" if self.unit == "tasks" else "tokens"
        if not split:
            lines.append(f"No {suffix} recorded")
        else:
            lines.extend(
                f"{provider}: {_format_count(count)} {suffix}"
                for provider, count in split
            )
        return "\n".join(lines)


def _format_tokens(tokens: int) -> str:
    return f"{tokens:,}"


def _format_count(value: int) -> str:
    return f"{value:,}"


def _format_codex_usage(snapshot: CodexUsageSnapshot) -> str:
    if snapshot.error:
        return f"Codex plan usage: unavailable — {snapshot.error}"
    plan = f" ({snapshot.plan_type.title()})" if snapshot.plan_type else ""
    return (
        f"Codex plan usage{plan}: "
        f"5-hour {_format_codex_window(snapshot.five_hour)} · "
        f"Weekly {_format_codex_window(snapshot.weekly)}"
    )


def _format_codex_window(window) -> str:
    if window is None:
        return "unavailable"
    reset = ""
    if window.resets_at is not None:
        local_reset = window.resets_at.astimezone()
        reset_date = local_reset.strftime("%b %d").replace(" 0", " ")
        reset_time = local_reset.strftime("%I:%M %p").lstrip("0")
        reset = f" (resets {reset_date}, {reset_time})"
    return f"{window.remaining_percent}% left{reset}"


class DaedalusTuiApp(App[None]):
    TITLE = "Daedalus TUI"
    CSS_PATH = "app.tcss"
    # Keep Textual's arbitrary text selection enabled for labels, logs, and
    # other non-editor widgets. TextArea has its own native selection model.
    ALLOW_SELECT = True
    BINDINGS = [
        _LegacyCompatibleBinding(
            _shortcut_binding_key(shortcut),
            action,
            description,
            show=shortcut == "Ctrl+K",
            priority=True,
        )
        for shortcut, description, action in GLOBAL_SHORTCUTS
    ]

    def __init__(
        self,
        runner: AgentRunner | None = None,
        directory: Path | None = None,
        settings: TuiSettings | None = None,
        coordinator: TaskCoordinator | None = None,
        statistics_settings: CodingStatisticsSettings | None = None,
        codex_usage_settings: CodexUsageSettings | None = None,
        codex_usage_reader=None,
        theme_preferences_path: Path | None = None,
    ) -> None:
        super().__init__()
        self._theme_preferences_path = theme_preferences_path or _theme_preferences_path()
        for theme_name in THEMES:
            self.register_theme(_textual_theme(theme_name))
        self.selected_theme = _load_saved_theme(self._theme_preferences_path)
        self.theme = f"daedalus-{self.selected_theme}"
        self._initial_directory_path = (
            directory.expanduser().absolute() if directory is not None else None
        )
        self.launch_root = (directory or Path.cwd()).resolve()
        self.memory = TaskMemoryStore(self.launch_root / DEFAULT_MEMORY_FILE)
        self.settings = settings or load_tui_settings()
        self.command_menu_settings = load_command_menu_settings()
        self.auto_sync_after_completed_tasks = (
            self.command_menu_settings.auto_sync_after_completed_tasks
        )
        self._auto_synced_task_ids: set[tuple[Path, str]] = set()
        self.statistics_settings = statistics_settings or load_coding_statistics_settings()
        self.codex_usage_settings = codex_usage_settings or load_codex_usage_settings()
        self._codex_usage_reader = codex_usage_reader or fetch_codex_usage
        self.orchestration_settings = load_orchestration_settings()
        self.debug_log_path = self.launch_root / self.orchestration_settings.debug_log_filename
        self._fault_log_file = None
        self.runner = runner or AgentRunner()
        discovered = [
            project
            for project in discover_projects(self.launch_root)
            if is_direct_child_project(project.path, self.launch_root)
        ]
        if not discovered:
            # Keep the app usable when launched in a new or test directory;
            # orchestration will provide the actionable Git error if needed.
            discovered = [DaedalusProject(self.launch_root, self.launch_root)]
        discovered_paths = {project.path.resolve() for project in discovered}
        remembered_project = self._remembered_project()
        if remembered_project in discovered_paths:
            active_project = remembered_project
        else:
            active_project = discovered[0].path.resolve()
        if coordinator is not None and active_project not in discovered_paths:
            discovered.insert(0, DaedalusProject(active_project, self.launch_root))
        self.projects = tuple(discovered)
        self._coordinators: dict[Path, TaskCoordinator] = {}
        self._migration_push_locks: dict[Path, threading.Lock] = {}
        self._external_coordinator = coordinator
        self._active_project_path = active_project
        self.directory = active_project
        self._remember_project(active_project)
        self.coordinator = self._coordinator_for(active_project)
        self._selected_task_id: str | None = None
        # The task inbox spans all discovered projects. Row keys include the
        # project path because task IDs are only unique within a coordinator.
        self._task_rows: dict[str, tuple[Path, str]] = {}
        self._session_task_rows: set[str] = set()
        self._updated_task_rows: set[str] = set()
        self._new_task_mode = True
        self._vim_pending_g = False
        self._plan_review_generation = 0
        self._accept_task_events = False
        self._task_event_lock = threading.Lock()
        self._pending_task_events: dict[str, tuple[TaskRecord, str, str, str]] = {}
        self._task_event_flush_scheduled = False
        self._shutdown_lock = threading.Lock()
        self._shutdown_started = False
        self._textual_unmounted = False
        self._previous_asyncio_exception_handler = None
        self._rendered_plan_question_signature: tuple[object, ...] | None = None
        self._suppress_target_branch_change = False
        self._suppress_topic_change = False
        self._suppress_compact_setting_change = False
        self._compact_setting_category = "provider"
        self._compact_setting_values: dict[str, str] = {}
        self._push_in_flight = False
        self._compact_mode = False
        self._short_height_mode = False
        self._responsive_measure_pending = False
        self._displayed_error = ""
        self._supabase_bootstrap_started = False
        self._personal_supabase_progress_screen: (
            PersonalSupabaseActivationProgressScreen | None
        ) = None
        self._codex_usage_refresh_lock = threading.Lock()
        self._codex_usage_stop = threading.Event()

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="screen"):
            with Horizontal(id="workspace"):
                with Vertical(id="task-sidebar"):
                    yield Static("Task updates", id="task-label")
                    yield DataTable(id="task-list", cursor_type="row")
                with Vertical(id="project-main"):
                    yield Static("Local agent orchestration", id="title")
                    with Horizontal(id="task-bar"):
                        yield Static("Project", id="project-label")
                        yield Select(
                            [
                                (project.display_name, str(project.path))
                                for project in self._selector_projects()
                            ],
                            value=self._project_select_value(),
                            allow_blank=False,
                            id="project-select",
                        )
                    yield Static("Codex plan usage: Loading…", id="codex-usage")
                    yield Static("Task branch: —    Worktree: —", id="task-context")
                    with Horizontal(id="agent-state-row"):
                        yield LoadingIndicator(id="agent-spinner")
                        yield Static("", id="agent-outcome", markup=False)
                    with Vertical(id="output-panel"):
                        with Horizontal(id="output-toolbar"):
                            yield Static("Agent output", id="output-view-label")
                        # Log supports Textual click-drag selection; RichLog does not.
                        yield TranscriptLog(id="output", auto_scroll=True)
                    with Horizontal(id="settings"):
                        yield Select(
                            [(option.label, option.value) for option in self.settings.providers],
                            value=self.settings.default_provider,
                            id="provider-select",
                        )
                        yield Select(
                            [(option.label, option.value) for option in self.settings.codex_models],
                            value=self.settings.default_model,
                            id="model-select",
                        )
                        yield Select(
                            [(option.label, option.value) for option in self.settings.codex_reasoning],
                            value=self.settings.default_reasoning,
                            id="reasoning-select",
                        )
                        yield Select(
                            [(option.label, option.value) for option in self.settings.modes],
                            value="coding",
                            id="mode-select",
                        )
                        yield Select(
                            [("(None)", TOPIC_NONE_VALUE)],
                            value=TOPIC_NONE_VALUE,
                            id="topic-select",
                        )
                        yield Button("View Topic", id="view-topic-button", disabled=True)
                        yield Select(
                            [
                                (
                                    self.orchestration_settings.primary_branch,
                                    self.orchestration_settings.primary_branch,
                                )
                            ],
                            value=self.orchestration_settings.primary_branch,
                            id="target-branch-select",
                        )
                    with Vertical(id="compact-settings"):
                        yield CompactSettingsSelect(
                            _literal_select_options(list(COMPACT_SETTING_CATEGORIES)),
                            value="provider",
                            allow_blank=False,
                            id="compact-settings-category",
                        )
                        yield CompactSettingsSelect(
                            [(option.label, option.value) for option in self.settings.providers],
                            value=self.settings.default_provider,
                            allow_blank=False,
                            id="compact-settings-value",
                        )
                    with Vertical(id="composer"):
                        yield DaedalusVimTextArea(
                            id="prompt-input",
                            placeholder="Describe the change for the local agent...",
                        )
                        with Vertical(id="resume-notes-panel"):
                            yield Static("Optional notes for resuming this task", id="resume-notes-label")
                            yield TextArea(
                                id="resume-notes",
                                placeholder="Tell the agent what it missed or what to update next...",
                            )
                    with Vertical(id="plan-review"):
                        # Agent plan text is literal; brackets and scientific
                        # notation must not be parsed as Textual/Rich markup.
                        yield Static("", id="plan-display", markup=False)
                        with Vertical(id="plan-questions"):
                            yield Static("", id="plan-questions-empty", markup=False)
                        with Horizontal(id="plan-actions"):
                            yield Button("Submit Answers", id="answer-plan-button", disabled=True)
                            yield Button("Implement", id="implement-button", disabled=True, variant="primary")
                    with Horizontal(id="actions"):
                        yield Button("Send", id="send-button", variant="primary")
                        yield Button("Continue Plan", id="continue-plan-button", disabled=True)
                        yield Button("Pause", id="pause-button", disabled=True)
                        yield Button("Resume", id="resume-button", disabled=True)
                        yield Button("Cancel", id="cancel-button", disabled=True, variant="error")
                        yield Button("Retry", id="retry-button", disabled=True)
                        yield Button("Follow Up", id="follow-up-button", disabled=True)
                        yield Static("Idle", id="status")
        yield Footer()

    def _start_personal_supabase_bootstrap(self) -> None:
        """Synchronize registered projects; push migrations only when activated."""
        if self._supabase_bootstrap_started:
            return
        self._supabase_bootstrap_started = True
        projects = tuple(
            project.path.resolve()
            for project in self.projects
            if is_direct_child_project(project.path, self.launch_root)
        )
        if not projects:
            return
        self._set_status("Preparing personal Supabase…")

        def work() -> None:
            results: list[tuple[Path, PersonalSupabaseBootstrapResult, str]] = []
            for project_path in projects:
                lock = self._migration_push_locks.setdefault(project_path, threading.Lock())
                prepared: PersonalSupabaseBootstrapResult | None = None
                try:
                    with lock:
                        prepared = bootstrap_personal_supabase(
                            project_path,
                            require_database_access=self.orchestration_settings.supabase_db_push_enabled,
                        )
                        push_message = ""
                        should_push = (
                            prepared.status == "success"
                            and self.orchestration_settings.supabase_db_push_enabled
                            and is_personal_supabase_activated(project_path)
                        )
                        if should_push:
                            runtime_environment = cursor_environment(
                                project_path,
                                (TUI_ROOT / ".env",),
                                include_directory_env=False,
                            )
                            project_ref = resolve_project_ref_from_environment(
                                runtime_environment,
                                load_personal_supabase_settings(),
                            )
                            preflight = preflight_personal_supabase(
                                project_path,
                                executable=self.orchestration_settings.supabase_executable,
                                environment=runtime_environment,
                            )
                            if not preflight.succeeded:
                                push_message = _redact_supabase_diagnostic(
                                    preflight.message, runtime_environment
                                ) or "Supabase connectivity preflight failed."
                            else:
                                push_options = {
                                    "executable": self.orchestration_settings.supabase_executable,
                                    "env": runtime_environment,
                                    "project_ref": project_ref,
                                }
                                if preflight.database_url:
                                    push_options["database_url"] = preflight.database_url
                                with ROOT_MIGRATION_LOCK:
                                    synced = synchronize_personal_migrations(project_path)
                                    if synced.succeeded and not synced.conflicts:
                                        with temporary_supabase_cli_config(project_path, project_ref):
                                            pushed = push_migrations(TUI_ROOT, **push_options)
                                if not synced.succeeded:
                                    push_message = synced.output
                                elif synced.conflicts:
                                    details = "\n\n".join(
                                        f"{name}: root migration is authoritative.\nRoot SQL:\n{root_sql}\nProject SQL:\n{project_sql}"
                                        for name, root_sql, project_sql in synced.conflicts
                                    )
                                    push_message = "Personal migration filename conflict requires repair:\n" + details
                                elif not pushed.succeeded:
                                    push_message = _redact_supabase_diagnostic(
                                        pushed.output, runtime_environment
                                    ) or "Supabase migration push failed."
                        results.append((project_path, prepared, push_message))
                except Exception as error:  # Keep one project from blocking other projects.
                    log_exception(
                        f"Personal Supabase bootstrap failed project={project_path.name}",
                        error,
                    )
                    results.append(
                        (
                            project_path,
                            PersonalSupabaseBootstrapResult(
                                "failed",
                                project_path,
                                message=_redact_supabase_diagnostic(
                                    str(error),
                                    prepared.environment if prepared is not None else None,
                                ),
                            ),
                            "",
                        )
                    )
            self.call_from_thread(self._on_personal_supabase_bootstrap_finished, results)

        self.run_worker(
            work,
            thread=True,
            exclusive=True,
            group="personal-supabase-bootstrap",
            exit_on_error=False,
        )

    def _on_personal_supabase_bootstrap_finished(
        self,
        results: list[tuple[Path, PersonalSupabaseBootstrapResult, str]],
    ) -> None:
        registered = [item for item in results if item[1].status != "skipped"]
        failures = [
            (path, result, push_message)
            for path, result, push_message in results
            if result.status == "failed" or push_message
        ]
        if failures:
            diagnostics = []
            for path, result, push_message in failures:
                detail = push_message or result.message or "Bootstrap failed."
                diagnostics.append(f"{path.name}: {_redact_supabase_diagnostic(detail)}")
            self._set_error("\n".join(diagnostics))
            self._set_status(f"Supabase bootstrap incomplete ({len(failures)} project(s))")
            return
        if registered:
            action = "project environment validated"
            if self.orchestration_settings.supabase_db_push_enabled:
                action = "bootstrap complete"
            self._set_status(f"Supabase {action} ({len(registered)} project(s))")
        else:
            self._set_status(f"Supabase bootstrap skipped ({len(results)} unregistered project(s))")


    def on_mount(self) -> None:
        self.debug_log_path = configure_debug_logging(self.debug_log_path)
        self._fault_log_file = install_fault_handler(self.debug_log_path)
        self._install_exit_diagnostics()
        self._accept_task_events = True
        self.query_one("#output", TranscriptLog).styles.width = self.settings.output_width
        self._apply_provider_selection(str(self.query_one("#provider-select", Select).value))
        self._refresh_target_branch_select()
        self._refresh_topic_select()
        self._refresh_push_button()
        self._refresh_task_list()
        self._refresh_compact_setting_value()
        self._apply_responsive_layout()
        self._start_codex_usage_refresh()
        self.set_interval(
            self.codex_usage_settings.refresh_interval_seconds,
            self._start_codex_usage_refresh,
        )
        self._start_personal_supabase_bootstrap()
        prompt = self.query_one("#prompt-input", DaedalusVimTextArea)
        prompt.enter_insert_mode()
        prompt.focus()

    def on_key(self, event: events.Key) -> None:
        """Add Vim-like navigation without changing TextArea insert behavior."""
        if event.key == "tab" and len(self.screen_stack) == 1:
            self.action_toggle_plan_mode()
            event.stop()
            return

        if isinstance(self.focused, TextArea):
            self._vim_pending_g = False
            return

        key = event.key
        if self._vim_pending_g:
            self._vim_pending_g = False
            if key == "g":
                self._scroll_output("home")
            else:
                self._handle_vim_key(key)
            event.stop()
            return

        if key == "g":
            self._vim_pending_g = True
            self._set_status("g-")
            event.stop()
            return
        if key in {"j", "k", "G", "ctrl+d", "pageup", "y", "p", "i"}:
            self._handle_vim_key(key)
            event.stop()

    def on_unmount(self) -> None:
        self._textual_unmounted = True
        self._codex_usage_stop.set()
        _unregister_app_for_thread_exit(self)
        shutdown_complete = self._shutdown_coordinators("Textual app unmount")
        if shutdown_complete:
            close_fault_handler(self._fault_log_file)
        self._remove_exit_diagnostics()

    def on_resize(self, event: events.Resize) -> None:
        """Apply the viewport-aware layout whenever the terminal changes size."""
        self._apply_responsive_layout(event.size.width, event.size.height)

    def _apply_responsive_layout(
        self,
        width: int | None = None,
        height: int | None = None,
        compact: bool | None = None,
    ) -> None:
        """Toggle responsive classes and dimensions after a viewport change.

        ``compact_width`` is a lower safety guard, not the primary wide-layout
        breakpoint. Above it, the actual laid-out controls are measured after
        Textual has processed the style change so a clipped toolbar switches
        to the compact settings picker immediately.
        """
        if not all(
            self.query(selector)
            for selector in ("#screen", "#task-sidebar", "#prompt-input", "#output")
        ):
            return
        width = self.size.width if width is None else width
        height = self.size.height if height is None else height
        compact = width < self.settings.layout.compact_width if compact is None else compact
        short = height < self.settings.layout.short_height
        self._compact_mode = compact
        self._short_height_mode = short
        screen = self.query_one("#screen", VerticalScroll)
        screen.set_class(compact, "compact-width")
        screen.set_class(short, "short-height")
        task_sidebar = self.query_one("#task-sidebar", Vertical)
        prompt = self.query_one("#prompt-input", DaedalusVimTextArea)
        output = self.query_one("#output", TranscriptLog)
        task_sidebar.styles.height = (
            self.settings.layout.compact_task_sidebar_height if compact else "1fr"
        )
        prompt.styles.height = (
            self.settings.layout.compact_prompt_height
            if compact or short
            else 7
        )
        output_panel = self.query_one("#output-panel", Vertical)
        output_panel.styles.height = (
            self.settings.layout.compact_output_height if compact else "1fr"
        )
        output.styles.width = "1fr" if compact else self.settings.output_width
        self._refresh_compact_setting_value()
        if not compact:
            self._queue_responsive_measurement()

    def _queue_responsive_measurement(self) -> None:
        """Measure wide controls after their current layout pass completes."""
        if self._responsive_measure_pending:
            return
        self._responsive_measure_pending = True
        self.set_timer(1 / 120, self._schedule_responsive_measurement)

    def _schedule_responsive_measurement(self) -> None:
        """Run the wide-layout measurement after the next screen refresh."""
        # App.on_resize runs before Textual forwards the resize event to the
        # default screen. Defer once more after the first refresh so the
        # measurement cannot inspect the previous compact layout and switch
        # back to compact mode during a resize to a wide terminal.
        self.screen.call_after_refresh(
            self.screen.call_after_refresh,
            self._apply_measured_responsive_layout,
        )

    def _apply_measured_responsive_layout(self) -> None:
        """Switch to compact mode when wide controls extend past their bars."""
        self._responsive_measure_pending = False
        if not self.query("#screen"):
            return
        width = self.size.width
        height = self.size.height
        compact = width < self.settings.layout.compact_width or self._wide_controls_overflow()
        if compact != self._compact_mode:
            self._apply_responsive_layout(width, height, compact=compact)

    def _wide_controls_overflow(self) -> bool:
        """Return whether wide-layout controls are clipped or too narrow."""
        for selector in ("#task-bar", "#settings"):
            containers = self.query(selector)
            if not containers:
                continue
            container = containers.first()
            available = container.content_region
            if available.width <= 0:
                return True
            for child in container.children:
                region = child.region
                if region.width <= 0 or region.height <= 0:
                    return True
                if (
                    selector == "#settings"
                    and isinstance(child, Select)
                    and region.width < self.settings.layout.wide_control_min_width
                ):
                    return True
                if (
                    region.x < available.x
                    or region.x + region.width > available.x + available.width
                ):
                    return True
        return False

    def exit(self, *args, **kwargs) -> None:
        """Stop agents before an explicit Textual exit begins."""
        self._shutdown_coordinators("explicit Textual exit")
        super().exit(*args, **kwargs)

    def _handle_exception(self, error: Exception) -> None:
        """Persist Textual failures that would otherwise only flash on screen."""
        log_exception("Unhandled Textual application exception", error)
        debug_path = getattr(self, "debug_log_path", None)
        message = (
            f"Daedalus TUI fatal error: {type(error).__name__}: {error}\n"
            f"Details were written to {debug_path or '(debug log unavailable)'}."
        )
        try:
            print(message, file=sys.stderr, flush=True)
        except Exception:
            pass
        try:
            if self.is_running and self._accept_task_events:
                self._set_error(message)
                self._set_status("Fatal error — see diagnostics / debug log")
        except Exception as display_error:
            log_exception("Could not surface fatal error in the TUI", display_error)
        self._shutdown_coordinators("unhandled Textual application exception")
        super()._handle_exception(error)

    def _install_exit_diagnostics(self) -> None:
        """Cover terminal and event-loop exits that bypass Textual unmount."""
        _register_app_for_thread_exit(self)
        loop = asyncio.get_running_loop()
        self._previous_asyncio_exception_handler = loop.get_exception_handler()
        loop.set_exception_handler(self._log_asyncio_exception)
        LOGGER.info("Installed pre-thread-shutdown and asyncio diagnostics for Textual lifecycle.")

    def _remove_exit_diagnostics(self) -> None:
        try:
            asyncio.get_running_loop().set_exception_handler(self._previous_asyncio_exception_handler)
        except RuntimeError:
            pass
        self._previous_asyncio_exception_handler = None

    def _log_asyncio_exception(self, loop: asyncio.AbstractEventLoop, context: dict) -> None:
        error = context.get("exception")
        if isinstance(error, BaseException):
            log_exception("Unhandled asyncio exception in the Textual loop", error)
        else:
            LOGGER.error("Unhandled asyncio exception in the Textual loop: %s", context.get("message", context))
        if self._previous_asyncio_exception_handler is not None:
            self._previous_asyncio_exception_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    def _shutdown_before_thread_join(self) -> None:
        """Run before ThreadPoolExecutor's internal interpreter-exit join."""
        if self._textual_unmounted:
            return
        LOGGER.error("Python is exiting while the Textual unmount hook was not observed.")
        self._shutdown_coordinators("Python pre-thread shutdown")

    def shutdown_after_run(self) -> None:
        """Clean up if Textual's run loop returns without its unmount hook."""
        if self._textual_unmounted:
            return
        LOGGER.error("Textual run loop returned without the unmount hook.")
        self._shutdown_coordinators("Textual run loop returned")

    def _shutdown_coordinators(self, reason: str) -> bool:
        """Idempotently detach task callbacks and request child-process shutdown."""
        with self._shutdown_lock:
            if self._shutdown_started:
                return True
            self._shutdown_started = True
        LOGGER.info("%s; requesting coordinator shutdown.", reason)
        self._accept_task_events = False
        shutdown_complete = True
        for coordinator in self._coordinators.values():
            if hasattr(coordinator, "set_event_callback"):
                coordinator.set_event_callback(None)
            try:
                shutdown_complete = coordinator.shutdown() is not False and shutdown_complete
            except Exception as error:
                shutdown_complete = False
                log_exception("Coordinator shutdown failed", error)
        if not shutdown_complete:
            LOGGER.error("Leaving fault handler active because a task worker is still running.")
        return shutdown_complete

    def action_submit_prompt(self) -> None:
        self._submit_prompt()

    def action_toggle_plan_mode(self) -> None:
        if len(self.screen_stack) != 1:
            return
        self._toggle_plan_mode()

    def action_new_task(self) -> None:
        self._start_new_task()

    def action_copy_selection(self) -> None:
        self._copy_selection()

    def action_pause_task(self) -> None:
        self._pause_task()

    def action_resume_task(self) -> None:
        self._resume_task()

    def action_continue_plan(self) -> None:
        self._continue_plan()

    def action_cancel_task(self) -> None:
        self._cancel_task()

    def action_retry_task(self) -> None:
        self._retry_task()

    def action_follow_up_task(self) -> None:
        self._follow_up_task()

    def action_show_shortcuts(self) -> None:
        self.push_screen(KeyboardShortcutsScreen())

    def action_show_command_menu(self) -> None:
        if len(self.screen_stack) != 1:
            return
        self.push_screen(
            CommandMenuScreen(self.command_menu_settings),
            self._on_command_menu_action,
        )

    def _on_command_menu_action(self, action: str | None) -> None:
        """Run a command after the command menu has been removed."""
        handlers = {
            "new_task": self.action_new_task,
            "show_new_project": self.action_show_new_project,
            "show_create_topic": self.action_show_create_topic,
            "register_personal_supabase": self.action_register_personal_supabase,
            "remove_personal_supabase": self.action_remove_personal_supabase,
            "push_branch": self._push_selected_branch,
            "show_shortcuts": self.action_show_shortcuts,
            "pick_theme": self.action_pick_theme,
        }
        handler = handlers.get(action)
        if handler is not None:
            self.call_after_refresh(handler)

    def action_pick_theme(self) -> None:
        self.push_screen(ThemePickerScreen(), self._on_theme_picked)

    def _on_theme_picked(self, theme_name: str | None) -> None:
        if theme_name not in THEMES:
            return
        self.selected_theme = theme_name
        self.theme = f"daedalus-{theme_name}"
        try:
            _save_theme(self._theme_preferences_path, theme_name)
        except OSError as error:
            LOGGER.warning("Could not save selected theme preference: %s", error)
        self._set_status(f"Theme changed to {THEMES[theme_name]['label']}")

    def _toggle_auto_sync_after_tasks(self) -> None:
        self.auto_sync_after_completed_tasks = not self.auto_sync_after_completed_tasks
        state = "on" if self.auto_sync_after_completed_tasks else "off"
        self._set_status(f"Auto-sync after completed tasks {state}")

    def action_show_statistics(self) -> None:
        self.push_screen(CodingStatisticsScreen(self._usage_entries(), self.statistics_settings))

    def action_show_new_project(self) -> None:
        self.push_screen(ProjectInitializerScreen(self.launch_root), self._on_project_initialized)

    def action_show_create_topic(self) -> None:
        self.push_screen(CreateTopicScreen(self._active_project_path), self._on_topic_created)

    def action_register_personal_supabase(self) -> None:
        """Confirm, then scaffold (if needed) and Activate personal Supabase."""
        progress = self._personal_supabase_progress_screen
        if progress is not None and progress.running and progress.is_attached:
            self._set_status("Personal Supabase Activate is already running…")
            return
        project_path = self._active_project_path
        try:
            schema = schema_from_project_root(project_path)
            status = load_personal_supabase_status(project_path)
        except ValueError as error:
            self._set_error(str(error))
            self._set_status("Personal Supabase Activate failed")
            return
        if status.registered and status.activated and status.schema == schema:
            progress = PersonalSupabaseActivationProgressScreen(project_path.name, schema)
            self._personal_supabase_progress_screen = progress
            self.push_screen(progress, self._on_personal_supabase_progress_action)
            self.call_after_refresh(
                progress.finish,
                True,
                f"Schema {schema!r} is already activated.",
            )
            self._set_status(f"Schema {schema!r} already activated")
            return
        if status.registered and not status.activated:
            self._set_status("Confirm personal Supabase Activate retry…")
        else:
            self._set_status("Confirm personal Supabase Activate…")
        self.push_screen(
            PersonalSupabaseConfirmationScreen(schema),
            lambda confirmed: self._on_personal_supabase_confirmation(
                confirmed,
                project_path,
                schema,
            ),
        )

    def action_remove_personal_supabase(self) -> None:
        """Confirm, then remove local personal-Supabase artifacts for the project."""
        project_path = self._active_project_path
        if (
            self._initial_directory_path is not None
            and project_path == self._initial_directory_path.resolve()
        ):
            # Keep the caller's spelling at this boundary. The cleanup helper
            # resolves it before touching files, while preserving this path
            # avoids changing an operator-supplied project path via symlinks.
            project_path = self._initial_directory_path
        self.push_screen(
            PersonalSupabaseRemovalConfirmationScreen(project_path.name),
            lambda confirmed: self._on_personal_supabase_removal_confirmation(
                confirmed,
                project_path,
            ),
        )

    def _on_personal_supabase_removal_confirmation(
        self,
        confirmed: bool,
        project_path: Path,
    ) -> None:
        if not confirmed:
            self._set_status("Personal Supabase removal cancelled")
            return
        result = remove_personal_supabase(project_path)
        if result.succeeded:
            self._set_error("")
            self._set_status("Personal Supabase local artifacts removed")
        else:
            self._set_error(_redact_supabase_diagnostic(result.message))
            self._set_status("Personal Supabase removal incomplete")

    def _on_personal_supabase_confirmation(
        self,
        confirmed: bool,
        project_path: Path,
        schema: str,
    ) -> None:
        if not confirmed:
            self._set_status("Personal Supabase Activate cancelled")
            return
        # Screen.dismiss invokes this callback before it pops the confirmation
        # screen. Defer the push so the setup wizard remains on top.
        self.call_after_refresh(
            self._open_personal_supabase_setup_wizard,
            project_path,
            schema,
        )

    def _open_personal_supabase_setup_wizard(
        self,
        project_path: Path,
        schema: str,
    ) -> None:
        """Scaffold files, then guide manual project env setup before Activate."""
        self._set_status("Personal Supabase setup…")
        self.push_screen(
            PersonalSupabaseSetupWizardScreen(project_path, schema),
            lambda ready: self._on_personal_supabase_wizard_finished(
                ready,
                project_path,
                schema,
            ),
        )

    def _on_personal_supabase_wizard_finished(
        self,
        ready: bool,
        project_path: Path,
        schema: str,
    ) -> None:
        if not ready:
            self._set_status("Personal Supabase setup cancelled")
            return
        operating_branch = self._selected_operating_branch()
        if not operating_branch:
            self._set_error("Select an operating/target branch before Activate.")
            self._set_status("Personal Supabase Activate blocked")
            return
        # Screen.dismiss invokes this callback before it pops the wizard.
        # Defer the push so the progress screen remains on top.
        self.call_after_refresh(
            self._start_personal_supabase_activate,
            project_path,
            schema,
            operating_branch,
        )

    def _start_personal_supabase_activate(
        self,
        project_path: Path,
        schema: str,
        operating_branch: str,
    ) -> None:
        """Run scaffold+Activate in a background worker so the TUI stays responsive."""
        self._set_error("")
        progress = PersonalSupabaseActivationProgressScreen(project_path.name, schema)
        self._personal_supabase_progress_screen = progress
        self.push_screen(progress, self._on_personal_supabase_progress_action)
        self._set_status(f"Activating personal Supabase schema {schema!r}…")
        root = project_path.resolve()
        lock = self._migration_push_locks.setdefault(root, threading.Lock())

        def work() -> None:
            try:
                with lock:
                    result = activate_personal_supabase(
                        root,
                        operating_branch,
                        schema=schema,
                        executable=self.orchestration_settings.supabase_executable,
                        progress_callback=lambda message: self.call_from_thread(
                            self._on_personal_supabase_activation_progress,
                            message,
                        ),
                    )
            except Exception as error:
                log_exception(
                    f"Personal Supabase Activate failed project={root.name}",
                    error,
                )
                result = ActivationResult(
                    "failed",
                    schema,
                    _redact_supabase_diagnostic(str(error)),
                    root,
                )
            self.call_from_thread(self._on_personal_supabase_activate_finished, result)

        self.run_worker(
            work,
            thread=True,
            exclusive=False,
            group="personal-supabase-activate",
            exit_on_error=False,
        )

    def _on_personal_supabase_activation_progress(self, message: str) -> None:
        """Forward worker phases to the modal and the main status line."""
        progress = self._personal_supabase_progress_screen
        if progress is not None and progress.is_attached:
            progress.update_progress(message)
        self._set_status(f"Supabase: {message}")

    def _on_personal_supabase_activate_finished(self, result: ActivationResult) -> None:
        detail = _redact_supabase_diagnostic(result.message)
        progress = self._personal_supabase_progress_screen
        if result.status == "success" and result.activated:
            self._set_error("")
            self._set_status(f"Activated Supabase schema {result.schema!r}")
            self.call_after_refresh(
                self._finish_personal_supabase_progress,
                progress,
                True,
                detail,
            )
            return
        if result.status == "blocked":
            reason = result.blocked_reason or "blocked"
            self._set_error(detail)
            self._set_status(
                f"Activate blocked ({reason}) for schema {result.schema!r}; retry in the Command Menu (Ctrl+K)"
            )
            self.call_after_refresh(
                self._finish_personal_supabase_progress,
                progress,
                False,
                detail,
            )
            return
        self._set_error(detail or "Personal Supabase Activate failed.")
        self._set_status("Personal Supabase Activate failed")
        self.call_after_refresh(
            self._finish_personal_supabase_progress,
            progress,
            False,
            detail,
        )

    def _on_personal_supabase_progress_action(self, action: str | None) -> None:
        if action == "expose":
            self._start_personal_supabase_exposure(self._active_project_path)

    def _start_personal_supabase_exposure(self, project_path: Path) -> None:
        self._set_error("")
        self._set_status("Exposing personal Supabase schema through the Data API…")

        def work() -> None:
            result = expose_registered_personal_supabase_schema(project_path)
            self.call_from_thread(self._on_personal_supabase_exposure_finished, result)

        self.run_worker(
            work,
            thread=True,
            exclusive=False,
            group="personal-supabase-expose",
            exit_on_error=False,
        )

    def _on_personal_supabase_exposure_finished(self, result: ActivationResult) -> None:
        if result.status == "success":
            self._set_error("")
            self._set_status(result.message)
        else:
            detail = _redact_supabase_diagnostic(result.message)
            self._set_error(detail)
            self._set_status("Personal Supabase schema exposure failed")
            self.push_screen(PersonalSupabaseExposureErrorScreen(detail))

    @staticmethod
    def _finish_personal_supabase_progress(
        progress: PersonalSupabaseActivationProgressScreen | None,
        succeeded: bool,
        detail: str,
    ) -> None:
        """Finish a queued modal update only if its screen is still mounted."""
        if progress is not None and progress.is_attached:
            progress.finish(succeeded, detail)

    def action_view_topic(self) -> None:
        """Open the selected project topic in a read-only modal."""
        topic = self._selected_topic()
        if topic is None:
            self._set_status("Select a topic first")
            return
        topic_text = load_topic_text(self._active_project_path, topic)
        if topic_text is None:
            self._set_error(f"Could not load topic: {topic}")
            self._set_status("Topic unavailable")
            self._refresh_topic_view_button()
            return
        self.push_screen(TopicViewerScreen(topic, topic_text))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-button":
            self._submit_prompt()
        elif event.button.id == "view-topic-button":
            self.action_view_topic()
        elif event.button.id == "continue-plan-button":
            self._continue_plan()
        elif event.button.id == "pause-button":
            self._pause_task()
        elif event.button.id == "resume-button":
            self._resume_task()
        elif event.button.id == "cancel-button":
            self._cancel_task()
        elif event.button.id == "retry-button":
            self._retry_task()
        elif event.button.id == "follow-up-button":
            self._follow_up_task()
        elif event.button.id == "output-toggle-button":
            self._set_output_view(not self._showing_error_output, focus=True)
        elif event.button.id == "answer-plan-button":
            self._answer_plan()
        elif event.button.id == "implement-button":
            self._implement_plan()
        elif event.button.id and event.button.id.startswith("plan-clarify-"):
            index_text = event.button.id.removeprefix("plan-clarify-")
            if index_text.isdigit():
                self._open_plan_clarification(int(index_text))

    def on_select_changed(self, event: Select.Changed) -> None:
        # Select.Changed is posted by the reactive watcher and may be
        # delivered after another refresh has already changed the control.
        # Such an event describes stale state and must not re-enter a refresh
        # or switch projects/providers behind the user's back.
        if event.value != event.select.value:
            return
        if event.select.id == "compact-settings-category":
            if event.value != getattr(event.select, "_latest_value", event.value):
                return
            category = str(event.value)
            if category not in dict(COMPACT_SETTING_CATEGORIES).values():
                return
            self._compact_setting_category = category
            if not self._suppress_compact_setting_change:
                self._refresh_compact_setting_value(category)
            return
        if event.select.id == "compact-settings-value":
            if event.value != getattr(event.select, "_latest_value", event.value):
                return
            if event.value in (Select.BLANK, "", getattr(Select, "NULL", None)):
                return
            value_select = self.query_one("#compact-settings-value", Select)
            if event.value not in value_select._legal_values:
                categories = [
                    self._compact_setting_category,
                    *[setting for _label, setting in COMPACT_SETTING_CATEGORIES],
                ]
                for category in dict.fromkeys(categories):
                    if str(event.value) in {
                        option_value for _label, option_value in self._compact_setting_options(category)
                    }:
                        self._compact_setting_category = category
                        break
                else:
                    return
            if not self._suppress_compact_setting_change:
                self._apply_compact_setting(str(event.value))
            return
        if event.select.id == "project-select":
            if event.value not in (Select.BLANK, ""):
                self._switch_project(Path(str(event.value)))
            return
        if event.select.id == "target-branch-select":
            if self._suppress_target_branch_change:
                return
            if event.value not in (Select.BLANK, ""):
                self._on_target_branch_selected(str(event.value))
            self._refresh_push_button()
            self._refresh_compact_setting_value()
            return
        if event.select.id == "topic-select":
            if self._suppress_topic_change:
                return
            value = event.value
            if value in (Select.BLANK, "", TOPIC_NONE_VALUE, getattr(Select, "NULL", None)):
                self._on_topic_selected(None)
            else:
                self._on_topic_selected(str(value))
            self._refresh_topic_view_button()
            self._refresh_compact_setting_value()
            return
        if event.select.id and event.select.id.startswith("plan-question-"):
            try:
                self._update_plan_custom_answer_visibility(event.select.id, event.value)
                self._update_plan_action_buttons()
            except Exception as error:
                log_exception(
                    f"Plan answer Select change failed id={event.select.id!r}",
                    error,
                )
            return
        if event.select.id and event.select.id.startswith("plan-clarification-select-"):
            try:
                self._update_plan_clarification_answer(event.select.id, event.value)
            except Exception as error:
                log_exception(
                    f"Plan clarification Select change failed id={event.select.id!r}",
                    error,
                )
            return
        if event.select.id != "provider-select":
            return
        self._apply_provider_selection(str(event.value))

    def _apply_provider_selection(self, provider: str) -> None:
        """Apply provider-specific model and reasoning choices to all controls."""
        provider_select = self.query_one("#provider-select", Select)
        if provider_select.value != provider:
            provider_select.value = provider
        model_select = self.query_one("#model-select", Select)
        reasoning_select = self.query_one("#reasoning-select", Select)
        is_cursor = provider == "cursor"
        if is_cursor:
            model_options = [(self.settings.cursor_model.label, self.settings.cursor_model.value)]
            reasoning_options = [("Not applicable", "")]
            model_value = self.settings.cursor_model.value
            reasoning_value = ""
            model_select.disabled = True
            reasoning_select.disabled = True
        else:
            model_options = [(option.label, option.value) for option in self.settings.codex_models]
            reasoning_options = [(option.label, option.value) for option in self.settings.codex_reasoning]
            model_value = self.settings.default_model
            reasoning_value = self.settings.default_reasoning
            model_select.disabled = False
            reasoning_select.disabled = False
        self._set_select_options_if_changed(model_select, model_options)
        if model_select.value != model_value:
            model_select.value = model_value
        self._set_select_options_if_changed(reasoning_select, reasoning_options)
        if reasoning_select.value != reasoning_value:
            reasoning_select.value = reasoning_value
        # The wide provider selector is the source of truth even when the
        # compact controls were used earlier in the session.
        self._compact_setting_values["provider"] = provider
        self._compact_setting_values.pop("model", None)
        self._compact_setting_values.pop("reasoning", None)
        if self.query("#compact-settings-category"):
            self._refresh_compact_setting_value()

    @staticmethod
    def _set_select_options_if_changed(
        select: Select,
        options: list[tuple[str, str]],
        *,
        compare_labels: bool = False,
    ) -> None:
        """Avoid posting Select.Changed events when the options are unchanged."""
        current_options = tuple(getattr(select, "_options", ()))
        next_options = tuple(options)
        if compare_labels:
            unchanged = current_options == next_options
        else:
            unchanged = tuple(value for _label, value in current_options) == tuple(
                value for _label, value in next_options
            )
        if not unchanged:
            select.set_options(options)

    def _compact_setting_options(self, category: str) -> list[tuple[str, str]]:
        """Return labels and values for one compact settings category."""
        if category == "provider":
            return [(option.label, option.value) for option in self.settings.providers]
        if category == "model":
            provider = str(self.query_one("#provider-select", Select).value)
            if provider == "cursor":
                return [(self.settings.cursor_model.label, self.settings.cursor_model.value)]
            return [(option.label, option.value) for option in self.settings.codex_models]
        if category == "reasoning":
            provider = str(self.query_one("#provider-select", Select).value)
            if provider == "cursor":
                return [("Not applicable", "")]
            return [(option.label, option.value) for option in self.settings.codex_reasoning]
        if category == "mode":
            return [(option.label, option.value) for option in self.settings.modes]
        if category == "topic":
            return [(str(label), str(value)) for label, value in topic_select_options(self._active_project_path)]
        if category == "branch":
            options = list_local_branches(self._active_project_path)
            default = self.orchestration_settings.primary_branch
            if default not in options:
                options.insert(0, default)
            effective = self._selected_operating_branch() or default
            if effective not in options:
                options.insert(0, effective)
            return [(name, name) for name in options]
        return []

    def _compact_setting_current_value(self, category: str) -> str:
        """Read the current value from the same selectors used for submission."""
        ids = {
            "provider": "provider-select",
            "model": "model-select",
            "reasoning": "reasoning-select",
            "mode": "mode-select",
            "topic": "topic-select",
            "branch": "target-branch-select",
        }
        value = self.query_one(f"#{ids[category]}", Select).value
        return "" if value in (Select.BLANK, getattr(Select, "NULL", None)) else str(value)

    def _refresh_compact_setting_value(
        self,
        category: str | None = None,
        *,
        sync_category: bool = True,
    ) -> None:
        """Populate the compact value Select while retaining its active category."""
        if not self.query("#compact-settings-category"):
            return
        category_select = self.query_one("#compact-settings-category", Select)
        if category is None:
            category = self._compact_setting_category
        if category not in dict(COMPACT_SETTING_CATEGORIES).values():
            category = "provider"
        self._compact_setting_category = category
        value_select = self.query_one("#compact-settings-value", Select)
        options = self._compact_setting_options(category)
        if not options:
            return
        current = self._compact_setting_current_value(category)
        values = {value for _, value in options}
        effective = current if current in values else options[0][1]
        self._suppress_compact_setting_change = True
        try:
            if sync_category and category_select.value != category:
                category_select.value = category
            current_values = tuple(value for _label, value in getattr(value_select, "_options", ()))
            next_values = tuple(value for _label, value in options)
            if current_values != next_values:
                value_select.set_options(_literal_select_options(options))
            if value_select.value != effective:
                value_select.value = effective
        finally:
            self._suppress_compact_setting_change = False

    def _apply_compact_setting(self, value: str) -> None:
        """Apply a compact value through the existing wide-control state."""
        category = self._compact_setting_category
        self._compact_setting_values[category] = value
        if category == "provider":
            self._apply_provider_selection(value)
        elif category == "model":
            model_select = self.query_one("#model-select", Select)
            if value not in model_select._legal_values:
                self._apply_provider_selection(str(self.query_one("#provider-select", Select).value))
            model_select.value = value
        elif category == "reasoning":
            reasoning_select = self.query_one("#reasoning-select", Select)
            if value not in reasoning_select._legal_values:
                self._apply_provider_selection(str(self.query_one("#provider-select", Select).value))
            reasoning_select.value = value
        elif category == "mode":
            self.query_one("#mode-select", Select).value = value
        elif category == "topic":
            topic = None if value in ("", TOPIC_NONE_VALUE) else value
            self.query_one("#topic-select", Select).value = value
            self._on_topic_selected(topic)
            self._refresh_topic_view_button()
        elif category == "branch":
            self.query_one("#target-branch-select", Select).value = value
            self._on_target_branch_selected(value)
            self._refresh_push_button()
        self._refresh_compact_setting_value()

    def _current_submission_settings(self) -> tuple[str, str, str, str]:
        """Return provider metadata from the shared controls for a new task."""
        provider = self._compact_setting_values.get(
            "provider", str(self.query_one("#provider-select", Select).value)
        )
        model = self._compact_setting_values.get(
            "model", str(self.query_one("#model-select", Select).value)
        )
        reasoning_value = self.query_one("#reasoning-select", Select).value
        reasoning = self._compact_setting_values.get(
            "reasoning",
            "" if reasoning_value in (Select.BLANK, getattr(Select, "NULL", None)) else str(reasoning_value),
        )
        mode = self._compact_setting_values.get(
            "mode", str(self.query_one("#mode-select", Select).value)
        )
        return provider, model, reasoning, mode

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id and event.text_area.id.startswith("plan-custom-answer-"):
            self._update_plan_action_buttons()

    def _submit_prompt(self) -> None:
        prompt_widget = self.query_one("#prompt-input", TextArea)
        if prompt_widget.read_only:
            self._set_status("Press New Task first")
            return
        prompt = prompt_widget.text.strip()
        if not prompt:
            self._set_error("Prompt cannot be empty.")
            self._set_status("Error")
            prompt_widget.focus()
            return

        project_value = self.query_one("#project-select", Select).value
        if project_value in (Select.BLANK, "", getattr(Select, "NULL", None)):
            self._set_error("Select a project before sending.")
            self._set_status("Error")
            return
        selected_project = Path(str(project_value)).expanduser().resolve()
        if selected_project not in {
            project.path.resolve() for project in self._selector_projects()
        }:
            self._set_error("The selected project is no longer available.")
            self._set_status("Error")
            return
        if selected_project != self._active_project_path:
            # _switch_project preserves editable drafts; call it so Send uses
            # the toolbar project even before its Select.Changed event runs.
            self._switch_project(selected_project)

        provider, model, reasoning, mode = self._current_submission_settings()
        topic_value = self.query_one("#topic-select", Select).value
        topic: str | None = None
        if topic_value not in (Select.BLANK, "", TOPIC_NONE_VALUE, getattr(Select, "NULL", None)):
            topic = str(topic_value)
        # Persist the value read from the Select before submitting so a fresh
        # task can restore it even if Select.Changed is still queued.
        self._on_topic_selected(topic)
        try:
            record = self.coordinator.submit(prompt, provider, model, reasoning, mode, topic=topic)
        except (RuntimeError, ValueError) as error:
            self._set_error(str(error))
            self._set_status("Error")
            return
        self._focus_submitted_task(record, "prompt submission")

    def _toggle_plan_mode(self) -> None:
        mode_select = self.query_one("#mode-select", Select)
        current_mode = str(mode_select.value)
        if current_mode == "coding":
            target_mode = "plan"
        elif current_mode == "plan":
            target_mode = "coding"
        else:
            return
        available_modes = {option.value for option in self.settings.modes}
        if target_mode not in available_modes:
            self._set_status(f"{target_mode.capitalize()} mode unavailable")
            return
        mode_select.value = target_mode
        self._refresh_compact_setting_value()
        self._set_status(f"{target_mode.capitalize()} mode")

    def _on_topic_created(self, topic: dict | None) -> None:
        """Queue a coding task that writes and expands the requested topic file."""
        if topic is None:
            return
        try:
            provider, model, reasoning, _mode = self._current_submission_settings()
            prompt = build_topic_population_prompt(
                topic["name"],
                topic["slug"],
                topic["goal"],
                topic["template"],
            )
            record = self.coordinator.submit(
                prompt,
                provider,
                model,
                reasoning,
                "coding",
            )
        except (KeyError, RuntimeError, ValueError) as error:
            self._set_error(str(error))
            self._set_status("Error")
            return
        self._focus_submitted_task(record, "topic creation submission")
        self._set_status(f"Creating topic: {topic['slug']}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Focus a task from the cross-project update inbox."""
        row_key = str(event.row_key.value)
        task_target = self._task_rows.get(row_key)
        if task_target is None:
            return
        project_path, task_id = task_target
        self._focus_task(project_path, task_id)

    def _on_task_event(self, record: TaskRecord, phase: str, message: str, kind: str) -> None:
        LOGGER.debug(
            "Task event task=%s phase=%s kind=%s message_length=%d",
            record.task_id,
            phase,
            kind,
            len(message),
        )
        if not self._accept_task_events:
            LOGGER.debug("Dropped late task event because the app is closing.")
            return
        if threading.current_thread() is threading.main_thread():
            self._apply_task_event(record, phase, message, kind)
        else:
            with self._task_event_lock:
                self._pending_task_events[record.task_id] = (record, phase, message, kind)
                if self._task_event_flush_scheduled:
                    return
                self._task_event_flush_scheduled = True
            try:
                self.call_from_thread(self._flush_task_events)
            except RuntimeError as error:
                with self._task_event_lock:
                    self._task_event_flush_scheduled = False
                    self._pending_task_events.pop(record.task_id, None)
                # A worker can race with Textual's final shutdown transition.
                # Do not let a late event print an exception after the UI closes.
                if "App is not running" not in str(error):
                    log_exception("Could not forward task event into Textual", error)
                    raise
                LOGGER.info("Dropped task event after Textual stopped task=%s", record.task_id)

    def _flush_task_events(self) -> None:
        """Apply only the newest event per task to keep the UI responsive."""
        with self._task_event_lock:
            events_to_apply = tuple(self._pending_task_events.values())
            self._pending_task_events.clear()
            self._task_event_flush_scheduled = False
        for record, phase, message, kind in events_to_apply:
            self._apply_task_event(record, phase, message, kind)

    def _apply_task_event(self, record: TaskRecord, phase: str, message: str, kind: str) -> None:
        try:
            project_path = self._project_for_record(record)
            if project_path is None:
                return
            if (
                phase.lower() == "completed"
                and record.status == "completed"
                and record.mode == "coding"
                and not record.sync_recovery
                and self.auto_sync_after_completed_tasks
            ):
                sync_key = (project_path.resolve(), record.task_id)
                if sync_key not in self._auto_synced_task_ids:
                    self._auto_synced_task_ids.add(sync_key)
                    if project_path.resolve() == self._active_project_path.resolve():
                        self._push_selected_branch()
                    else:
                        LOGGER.info(
                            "Skipped auto-sync for completed task in inactive project task=%s project=%s",
                            record.task_id,
                            project_path,
                        )
            row_key = self._task_row_key(project_path, record.task_id)
            is_selected = (
                project_path == self._active_project_path
                and self._selected_task_id == record.task_id
            )
            if not is_selected and self._should_promote_task_update(record, phase):
                self._updated_task_rows.add(row_key)
            elif is_selected:
                self._updated_task_rows.discard(row_key)
            if kind != "message":
                self._refresh_project_selector()
                self._refresh_task_list()
                if record.sync_recovery:
                    self._refresh_push_button()
                    self._update_sync_recovery_status(record, phase)
            if is_selected:
                self._render_selected_task_safely(f"task event phase={phase}")
            if phase.lower() in {"proposed", "completed"} and record.provider == "codex":
                self._start_codex_usage_refresh()
        except Exception as error:
            log_exception(f"Could not render task event task={record.task_id} phase={phase}", error)
            if not self._accept_task_events:
                return
            try:
                self._set_error(f"Task update could not be rendered: {error}")
                self._set_status("Error")
            except Exception as display_error:
                log_exception("Could not show task rendering error", display_error)

    def _update_sync_recovery_status(self, record: TaskRecord, phase: str) -> None:
        """Surface Sync conflict recovery progress in the status bar."""
        normalized = phase.lower()
        branch = record.sync_operating_branch or "branch"
        if normalized in {"planning", "queued"} and record.mode == "plan":
            self._set_status("Sync conflict — planning…")
            return
        if normalized in {"questions", "questioning"}:
            self._set_status("Awaiting conflict decisions")
            return
        if normalized in {"agent", "resolving", "running"} or (
            normalized == "queued" and record.mode == "coding"
        ):
            self._set_status("Resolving sync conflicts…")
            return
        if normalized in {"ready", "integration"}:
            self._set_status(f"Syncing {branch}…")
            return
        if normalized == "completed":
            self._set_error("")
            self._set_status(f"Synced {branch} to origin")
            return
        if normalized == "failed":
            self._set_status("Sync conflict recovery failed")
            if record.error:
                self._set_error(record.error)
            return
        if normalized == "cancelled":
            self._set_status("Sync conflict recovery cancelled")

    @staticmethod
    def _should_promote_task_update(record: TaskRecord, phase: str) -> bool:
        """Promote only events that need the user's attention in the inbox."""
        normalized_phase = phase.lower()
        if normalized_phase in {"proposed", "completed", "failed"}:
            return True
        return record.mode == "plan" and normalized_phase in {"questions", "clarification"}

    def _coordinator_for(self, project_path: Path) -> TaskCoordinator:
        project_path = project_path.resolve()
        if project_path in self._coordinators:
            return self._coordinators[project_path]
        settings = replace(
            self.orchestration_settings,
            primary_branch=self._effective_primary_branch(project_path),
        )
        if self._external_coordinator is not None:
            coordinator = self._external_coordinator
            self._external_coordinator = None
            coordinator.settings = settings
            coordinator.environment_path = project_path / ".env"
            coordinator.migration_push_lock = self._migration_push_locks.setdefault(
                project_path, threading.Lock()
            )
        else:
            coordinator = TaskCoordinator(
                project_path,
                self.runner,
                settings,
                self._on_task_event,
                memory_path=self.launch_root / DEFAULT_MEMORY_FILE,
                environment_path=project_path / ".env",
                migration_push_lock=self._migration_push_locks.setdefault(
                    project_path, threading.Lock()
                ),
            )
        if hasattr(coordinator, "set_event_callback"):
            coordinator.set_event_callback(self._on_task_event)
        self._coordinators[project_path] = coordinator
        return coordinator

    def _effective_primary_branch(self, project_path: Path) -> str:
        """Memory override for the project, else the parameter-file default."""
        try:
            remembered = self.memory.get_project_target_branch(project_path)
        except (OSError, ValueError):
            remembered = None
        if remembered:
            return remembered
        return self.orchestration_settings.primary_branch

    def _apply_primary_branch(self, project_path: Path, branch: str) -> None:
        """Update the project's coordinator so later submits use ``branch``."""
        coordinator = self._coordinator_for(project_path)
        base = getattr(coordinator, "settings", self.orchestration_settings)
        try:
            coordinator.settings = replace(base, primary_branch=branch)
        except TypeError:
            coordinator.settings = replace(
                self.orchestration_settings,
                primary_branch=branch,
            )

    def _on_target_branch_selected(self, branch: str) -> None:
        project_path = self._active_project_path
        default_branch = self.orchestration_settings.primary_branch
        try:
            if branch == default_branch:
                # Absent key means parameter default; do not store the seed.
                self.memory.clear_project_target_branch(project_path)
            else:
                self.memory.set_project_target_branch(project_path, branch)
        except (OSError, ValueError):
            pass
        self._apply_primary_branch(project_path, branch)

    def _on_topic_selected(self, topic: str | None) -> None:
        """Remember the selected topic as the default for the active project."""
        try:
            if topic is None:
                self.memory.clear_project_topic(self._active_project_path)
            else:
                self.memory.set_project_topic(self._active_project_path, topic)
        except (OSError, ValueError):
            pass

    def _refresh_target_branch_select(self) -> None:
        """Refresh Branch Select options for the active project and sync coordinator."""
        project_path = self._active_project_path
        default_branch = self.orchestration_settings.primary_branch
        branches = list_local_branches(project_path)
        try:
            remembered = self.memory.get_project_target_branch(project_path)
        except (OSError, ValueError):
            remembered = None
        if remembered is not None and remembered not in branches:
            try:
                self.memory.clear_project_target_branch(project_path)
            except (OSError, ValueError):
                pass
            remembered = None
        effective = remembered if remembered is not None else default_branch
        options = list(branches)
        if default_branch not in options:
            options.insert(0, default_branch)
        if effective not in options:
            options.insert(0, effective)
        branch_select = self.query_one("#target-branch-select", Select)
        self._suppress_target_branch_change = True
        try:
            branch_options = [(name, name) for name in options]
            self._set_select_options_if_changed(branch_select, branch_options)
            if branch_select.value != effective:
                branch_select.value = effective
        finally:
            self._suppress_target_branch_change = False
        self._apply_primary_branch(project_path, effective)
        self._refresh_push_button()
        self._refresh_compact_setting_value()

    def _selected_operating_branch(self) -> str:
        value = self.query_one("#target-branch-select", Select).value
        if value in (Select.BLANK, "", getattr(Select, "NULL", None)):
            return ""
        return str(value).strip()

    def _refresh_push_button(self) -> None:
        """Enable Push only when an origin remote and operating branch are available."""
        # Select.Changed can fire while siblings are still mounting or during
        # teardown, before/after the command-menu Push button is in the DOM.
        if not self.screen.query("#command-push-branch-button"):
            return
        button = self.screen.query_one("#command-push-branch-button", Button)
        if self._push_in_flight:
            button.disabled = True
            return
        branch = self._selected_operating_branch()
        if not branch or not remote_exists(self._active_project_path):
            button.disabled = True
            return
        if self.coordinator.has_active_sync_recovery(branch):
            button.disabled = True
            return
        button.disabled = False

    def _push_selected_branch(self) -> None:
        """Sync the Branch Select value for the active project with origin."""
        if self._push_in_flight:
            return
        branch = self._selected_operating_branch()
        if not branch:
            self._set_error("Select a branch before syncing.")
            self._set_status("Error")
            return
        project_path = self._active_project_path
        if not remote_exists(project_path):
            self._set_error("Remote 'origin' is not configured for this project.")
            self._set_status("Error")
            self._refresh_push_button()
            return
        if self.coordinator.has_active_sync_recovery(branch):
            self._set_error("Sync conflict recovery is already active for this branch.")
            self._set_status("Sync recovery in progress")
            self._refresh_push_button()
            return

        pull_first = self.command_menu_settings.pull_before_push
        self._push_in_flight = True
        self._refresh_push_button()
        self._set_error("")
        self._set_status(f"{'Syncing' if pull_first else 'Pushing'} {branch}…")

        def work() -> None:
            try:
                push_branch(project_path, branch, pull_first=pull_first)
            except SyncMergeConflictError as error:
                self.call_from_thread(self._on_push_finished, False, error, branch)
            except GitWorktreeError as error:
                self.call_from_thread(self._on_push_finished, False, str(error), branch)
            except Exception as error:  # pragma: no cover - defensive UI boundary
                self.call_from_thread(self._on_push_finished, False, str(error), branch)
            else:
                self.call_from_thread(self._on_push_finished, True, "", branch)

        self.run_worker(
            work,
            thread=True,
            exclusive=True,
            group="git-push",
            exit_on_error=False,
        )

    def _on_push_finished(
        self,
        succeeded: bool,
        error: str | SyncMergeConflictError,
        branch: str,
    ) -> None:
        self._push_in_flight = False
        pull_first = self.command_menu_settings.pull_before_push
        if succeeded:
            self._refresh_push_button()
            self._set_error("")
            verb = "Synced" if pull_first else "Pushed"
            self._set_status(f"{verb} {branch} to origin")
            return
        if (
            isinstance(error, SyncMergeConflictError)
            and self.command_menu_settings.sync_conflict_recovery_enabled
        ):
            self._start_sync_conflict_recovery(error)
            return
        self._refresh_push_button()
        message = str(error) if error else ("Sync failed." if pull_first else "Push failed.")
        self._set_error(message)
        self._set_status("Sync failed" if pull_first else "Push failed")

    def _start_sync_conflict_recovery(self, conflict: SyncMergeConflictError) -> None:
        """Launch plan-mode recovery against the preserved Sync conflict worktree."""
        try:
            provider, model, reasoning, _mode = self._current_submission_settings()
            record = self.coordinator.submit_sync_recovery(
                provider=provider,
                model=model,
                reasoning=reasoning,
                operating_branch=conflict.branch,
                remote=conflict.remote,
                worktree_path=conflict.worktree_path,
                conflicted_paths=conflict.conflicted_paths,
                used_temp_branch=conflict.used_temp_branch,
                temp_branch_name=conflict.temp_branch_name,
                merge_failure=conflict.merge_failure,
                attempt_limit=self.command_menu_settings.sync_conflict_attempt_limit,
            )
        except (RuntimeError, ValueError, GitWorktreeError) as launch_error:
            self._refresh_push_button()
            self._set_error(str(launch_error))
            self._set_status("Sync conflict recovery failed to start")
            return
        self._focus_submitted_task(record, "sync conflict recovery")
        self._refresh_push_button()
        self._set_error("")
        self._set_status("Sync conflict — planning…")

    def _refresh_topic_select(self) -> None:
        """Refresh topics and restore the active project's remembered default."""
        options = topic_select_options(self._active_project_path)
        valid_values = {value for _, value in options}
        try:
            remembered = self.memory.get_project_topic(self._active_project_path)
        except (OSError, ValueError):
            remembered = None
        if remembered is not None and remembered not in valid_values:
            try:
                self.memory.clear_project_topic(self._active_project_path)
            except (OSError, ValueError):
                pass
            remembered = None
        effective = remembered if remembered is not None else TOPIC_NONE_VALUE
        topic_select = self.query_one("#topic-select", Select)
        self._suppress_topic_change = True
        try:
            self._set_select_options_if_changed(topic_select, options)
            if topic_select.value != effective:
                topic_select.value = effective
        finally:
            self._suppress_topic_change = False
        self._refresh_topic_view_button()
        self._refresh_compact_setting_value()

    def _selected_topic(self) -> str | None:
        """Return the selected topic slug, or None for the blank option."""
        value = self.query_one("#topic-select", Select).value
        if value in (Select.BLANK, "", TOPIC_NONE_VALUE, getattr(Select, "NULL", None)):
            return None
        return str(value)

    def _refresh_topic_view_button(self) -> None:
        """Enable topic viewing only when the selector has a real topic."""
        if not self.query("#view-topic-button"):
            return
        self.query_one("#view-topic-button", Button).disabled = self._selected_topic() is None

    def _usage_entries(self):
        try:
            persisted = usage_entries_from_memory(self.memory)
        except (OSError, ValueError):
            persisted = ()
        live = tuple(
            entry
            for coordinator in self._coordinators.values()
            for record in coordinator.tasks()
            for entry in (task_usage_entry(record),)
            if entry is not None
        )
        return merge_usage_entries(persisted, live)

    def _remembered_project(self) -> Path | None:
        try:
            return self.memory.get_last_opened_project()
        except (OSError, ValueError):
            return None

    def _remember_project(self, project_path: Path) -> None:
        try:
            self.memory.set_last_opened_project(project_path)
        except (OSError, ValueError):
            # Project navigation should remain usable if local memory is unavailable.
            pass

    def _switch_project(self, project_path: Path) -> None:
        project_path = project_path.expanduser().resolve()
        if project_path == self._active_project_path:
            return
        if project_path not in {
            project.path.resolve() for project in self._selector_projects()
        }:
            return
        # Keep in-progress editable drafts when changing projects so a
        # mis-targeted prompt can be redirected instead of erased.
        draft: str | None = None
        try:
            prompt_widget = self.query_one("#prompt-input", TextArea)
            if not prompt_widget.read_only:
                draft = prompt_widget.text
        except Exception:
            draft = None
        self._active_project_path = project_path
        self.directory = project_path
        # Persist after the active focus changes so the marker mirrors the
        # project that is currently visible in the TUI.
        self._remember_project(project_path)
        self.coordinator = self._coordinator_for(project_path)
        self._selected_task_id = None
        self._new_task_mode = draft is not None
        self._updated_task_rows = {
            row_key for row_key in self._updated_task_rows if row_key in self._task_rows
        }
        self._refresh_target_branch_select()
        self._refresh_topic_select()
        self._refresh_task_list()
        self._render_selected_task_safely("project switch")
        if draft is not None:
            self._set_prompt_text(draft, editable=True)
        self._set_status("Project switched")

    def _on_project_initialized(self, result: dict | None) -> None:
        if result is None:
            return
        destination = Path(str(result["projectDirectory"])).resolve()
        self._reload_projects(preferred=destination)
        if result["status"] == "partial_success" and result.get("error"):
            self._set_error(str(result["error"]))
            self._set_status("Project created with GitHub warning")
        else:
            self._set_status(f"Initialized {destination.name}")
        self._start_new_task()

    def _reload_projects(self, preferred: Path | None = None) -> None:
        discovered = [
            project
            for project in discover_projects(self.launch_root)
            if is_direct_child_project(project.path, self.launch_root)
        ]
        if not discovered:
            discovered = [DaedalusProject(self.launch_root, self.launch_root)]
        discovered_paths = {project.path.resolve() for project in discovered}
        for known in self.projects:
            path = known.path.resolve()
            if (
                path not in discovered_paths
                and path in self._coordinators
                and is_direct_child_project(path, self.launch_root)
            ):
                discovered.append(known)
                discovered_paths.add(path)
        self.projects = tuple(
            sorted(
                discovered,
                key=lambda project: (project.path.resolve() != self.launch_root, project.display_name),
            )
        )
        self._refresh_project_selector()
        if preferred is not None and preferred.resolve() in discovered_paths:
            target = preferred.resolve()
            if target != self._active_project_path:
                self._switch_project(target)
            self.query_one("#project-select", Select).value = self._project_select_value()

    def _refresh_project_selector(self) -> None:
        project_select = self.query_one("#project-select", Select)
        options = [
            (project.display_name, str(project.path))
            for project in self._selector_projects()
        ]
        self._set_select_options_if_changed(project_select, options, compare_labels=True)
        effective = self._project_select_value()
        if project_select.value != effective:
            project_select.value = effective

    def _selector_projects(self) -> tuple[DaedalusProject, ...]:
        """Return only direct-child projects, or the empty-root fallback."""

        direct_children = tuple(
            project
            for project in self.projects
            if is_direct_child_project(project.path, self.launch_root)
        )
        if direct_children:
            return direct_children
        return tuple(
            project
            for project in self.projects
            if project.path.resolve() == self.launch_root
        )[:1]

    def _project_select_value(self) -> str:
        selector_projects = self._selector_projects()
        for project in selector_projects:
            if project.path.resolve() == self._active_project_path:
                return str(project.path)
        if selector_projects:
            return str(selector_projects[0].path)
        return str(self._active_project_path)

    def _start_codex_usage_refresh(self) -> None:
        """Refresh the account usage line without blocking the TUI event loop."""
        if not self._accept_task_events or self._codex_usage_stop.is_set():
            return
        if not self._codex_usage_refresh_lock.acquire(blocking=False):
            return

        def work() -> None:
            try:
                snapshot = self._codex_usage_reader(self.codex_usage_settings)
            except Exception as error:
                log_exception("Codex usage refresh failed", error)
                snapshot = CodexUsageSnapshot(error="Codex usage data unavailable")
            finally:
                self._codex_usage_refresh_lock.release()
            if self._codex_usage_stop.is_set() or not self._accept_task_events:
                return
            try:
                self.call_from_thread(self._apply_codex_usage_snapshot, snapshot)
            except RuntimeError as error:
                if "App is not running" not in str(error):
                    log_exception("Could not render Codex usage refresh", error)

        threading.Thread(target=work, name="codex-usage-refresh", daemon=True).start()

    def _apply_codex_usage_snapshot(self, snapshot: CodexUsageSnapshot) -> None:
        try:
            self.query_one("#codex-usage", Static).update(_format_codex_usage(snapshot))
        except NoMatches:
            # The refresh can finish while Textual is unmounting.
            return

    def _refresh_task_list(self) -> None:
        """Render actionable history and tasks created during this session."""
        task_list = self.query_one("#task-list", DataTable)
        task_list.clear(columns=True)
        marker_width, project_width, task_width, status_width = self.settings.task_inbox_widths
        for label, width in (
            ("", marker_width),
            ("Project", project_width),
            ("Task", task_width),
            ("Status", status_width),
        ):
            # Explicit widths keep a new update marker from changing the
            # table's virtual width and moving the visible horizontal slice.
            task_list.add_column(label, width=width)
        self._task_rows.clear()

        project_names = {
            project.path.resolve(): project.display_name
            for project in self.projects
        }
        rows: list[tuple[Path, TaskRecord]] = []
        for project_path in project_names:
            coordinator = self._coordinators.get(project_path)
            if coordinator is None:
                continue
            rows.extend(
                (project_path, record)
                for record in coordinator.tasks()
                if self._should_show_task(project_path, record)
            )
        rows.sort(
            key=lambda item: (
                self._task_row_key(item[0], item[1].task_id) not in self._updated_task_rows,
                -item[1].submission_sequence,
            )
        )

        current_row_keys = {
            self._task_row_key(project_path, record.task_id)
            for project_path, record in rows
        }
        self._updated_task_rows.intersection_update(current_row_keys)
        for project_path, record in rows:
            row_key = self._task_row_key(project_path, record.task_id)
            self._task_rows[row_key] = (project_path, record.task_id)
            project_name = self._fit_task_cell(
                project_names.get(project_path, project_path.name), project_width
            )
            summary = " ".join(record.prompt.split())
            summary = self._fit_task_cell(summary, task_width)
            if record.status == "failed":
                marker = Text("✗", style="bold red")
            elif record.mode == "plan" and record.status in {"completed", "awaiting_answers"}:
                marker = Text("●", style="bold orange1")
            elif record.status == "completed":
                marker = Text("✓", style="bold green")
            else:
                marker = "!" if row_key in self._updated_task_rows else ""
            status = self._fit_task_cell(record.status, status_width)
            task_list.add_row(marker, project_name, summary, status, key=row_key)

        if self._selected_task_id:
            selected_key = self._task_row_key(self._active_project_path, self._selected_task_id)
            if selected_key in self._task_rows:
                task_list.move_cursor(row=list(self._task_rows).index(selected_key), column=0)

    def _should_show_task(self, project_path: Path, record: TaskRecord) -> bool:
        """Keep failures, active work, and all tasks submitted in this launch."""
        row_key = self._task_row_key(project_path, record.task_id)
        return (
            row_key in self._session_task_rows
            or record.status == "failed"
            or record.status in _ACTIVE_TASK_STATUSES
        )

    @staticmethod
    def _task_row_key(project_path: Path, task_id: str) -> str:
        return f"{project_path.resolve()}::{task_id}"

    @staticmethod
    def _fit_task_cell(value: str, width: int) -> str:
        """Keep inbox cells within their fixed width with a visible ellipsis."""
        if len(value) <= width:
            return value
        if width == 1:
            return "…"
        return f"{value[: width - 1]}…"

    def _project_for_record(self, record: TaskRecord) -> Path | None:
        for project_path, coordinator in self._coordinators.items():
            if coordinator.get(record.task_id) is record:
                return project_path
        return None

    def _clear_task_update(self, row_key: str) -> None:
        self._updated_task_rows.discard(row_key)

    def _mark_task_current_session(self, record: TaskRecord) -> None:
        """Keep a task visible after user activity during this launch."""
        self._session_task_rows.add(self._task_row_key(self._active_project_path, record.task_id))

    def _focus_task(self, project_path: Path, task_id: str) -> None:
        """Switch the project context and focus a row selected in the inbox."""
        project_path = project_path.resolve()
        record_coordinator = self._coordinators.get(project_path)
        if record_coordinator is None or record_coordinator.get(task_id) is None:
            return
        self._active_project_path = project_path
        self.directory = project_path
        self._remember_project(project_path)
        self.coordinator = record_coordinator
        self._selected_task_id = task_id
        self._new_task_mode = False
        self._clear_task_update(self._task_row_key(project_path, task_id))
        self.query_one("#project-select", Select).value = self._project_select_value()
        self._refresh_task_list()
        self._render_selected_task_safely("task selection")

    def _focus_submitted_task(self, record: TaskRecord, source: str) -> None:
        """Make a newly submitted task the visible task in every mode."""
        self._mark_task_current_session(record)
        project_path = self._project_for_record(record)
        if project_path is None:
            # Submission normally comes from the active coordinator, but keep
            # the UI recoverable if a custom coordinator returns an unknown
            # record instead of silently leaving the previous task selected.
            self._selected_task_id = record.task_id
            self._new_task_mode = False
            self._refresh_task_list()
            self._render_selected_task_safely(source)
            return
        self._focus_task(project_path, record.task_id)

    def _render_selected_task_safely(self, source: str) -> None:
        """Keep one bad dynamic widget update from closing the entire TUI."""
        try:
            self._render_selected_task()
        except Exception as error:
            log_exception(f"Could not render selected task during {source}", error)
            try:
                self._set_error(f"Task view could not be rendered: {error}")
                self._set_status("Error")
            except Exception as display_error:
                log_exception("Could not show selected-task rendering error", display_error)

    def _render_selected_task(self) -> None:
        record = self.coordinator.get(self._selected_task_id or "")
        self._plan_review_generation += 1
        plan_review_generation = self._plan_review_generation
        output = self.query_one("#output", TranscriptLog)
        output.clear()
        self._displayed_error = ""
        if record is None:
            self._rendered_plan_question_signature = None
            self._set_prompt_text("", editable=True)
            self.query_one("#output-panel", Vertical).styles.display = "block"
            self.query_one("#task-context", Static).update("Task branch: —    Worktree: —")
            self._update_agent_outcome(None)
            self._set_error("")
            self.query_one("#pause-button", Button).disabled = True
            self.query_one("#resume-button", Button).disabled = True
            self.query_one("#cancel-button", Button).disabled = True
            self.query_one("#retry-button", Button).disabled = True
            self.query_one("#follow-up-button", Button).disabled = True
            self.query_one("#continue-plan-button", Button).disabled = True
            self.query_one("#resume-notes-panel", Vertical).styles.display = "none"
            self.query_one("#plan-review", Vertical).styles.display = "none"
            return
        # Use Textual's resolved Rich color rather than the raw CSS variable:
        # the default `$text` value is CSS syntax (`auto 87%`), not a Rich
        # color string, and selecting an existing task has made the prompt
        # read-only by this point.
        output.set_final_color(self.screen.rich_style.color)
        self._set_prompt_text("", editable=True)
        plan_review = self.query_one("#plan-review", Vertical)
        plan_review.styles.display = "block" if record.mode == "plan" else "none"
        self.query_one("#output-panel", Vertical).styles.display = (
            "none" if record.mode == "plan" else "block"
        )
        output.styles.display = "block" if record.mode != "plan" else "none"
        if record.mode == "plan":
            self._render_plan_review(record, plan_review_generation)
        else:
            self._rendered_plan_question_signature = None
            chain_id = record.chain_id or record.task_id
            chain_records = sorted(
                (
                    item for item in self.coordinator.tasks()
                    if (item.chain_id or item.task_id) == chain_id
                    and item.submission_sequence <= record.submission_sequence
                ),
                key=lambda item: item.submission_sequence,
            ) or [record]
            for turn in chain_records:
                output.write_task_turn(
                    turn.submission_sequence,
                    turn.prompt,
                    turn.messages,
                    final=turn.status in {"proposed", "completed"},
                )
        worktree = str(record.worktree_path) if record.worktree_path else "—"
        branch = record.branch_name or "—"
        self.query_one("#task-context", Static).update(
            f"Task branch: {branch}    Worktree: {worktree}"
        )
        self._update_agent_outcome(record)
        self._set_error(record.error or "")
        self._set_status(record.status.capitalize())
        active = record.status in {
            "queued",
            "planning",
            "running",
            "verifying",
            "ready",
            "integrating",
            "resolving",
        }
        self.query_one("#pause-button", Button).disabled = not active
        self.query_one("#resume-button", Button).disabled = record.status != "paused"
        self.query_one("#cancel-button", Button).disabled = not active and record.status != "questioning"
        self.query_one("#retry-button", Button).disabled = record.status != "failed"
        self.query_one("#follow-up-button", Button).disabled = record.status not in {"completed", "failed"}
        self.query_one("#continue-plan-button", Button).disabled = record.status != "questioning"
        self.query_one("#resume-notes-panel", Vertical).styles.display = (
            "block" if record.status in {"paused", "questioning"} else "none"
        )
        self.query_one("#resume-notes-label", Static).update(
            "Plan follow-up or question" if record.status == "questioning" else "Optional notes for resuming this task"
        )

    def _update_agent_outcome(self, record: TaskRecord | None) -> None:
        """Show animated activity or a concise terminal task outcome."""
        spinner = self.query_one("#agent-spinner", LoadingIndicator)
        outcome = self.query_one("#agent-outcome", Static)
        outcome.remove_class("outcome-success", "outcome-failure", "outcome-input")
        if record is None:
            spinner.styles.display = "none"
            outcome.update("")
        elif record.status in {"queued", "planning", "running", "verifying", "ready", "integrating", "resolving"}:
            spinner.styles.display = "block"
            activity = {
                "queued": "Queued…",
                "planning": "Planning…",
                "running": "Thinking…",
                "verifying": "Verifying…",
                "ready": "Ready to integrate…",
                "integrating": "Integrating…",
                "resolving": "Resolving…",
            }[record.status]
            outcome.update(activity)
        elif record.status == "proposed":
            spinner.styles.display = "none"
            outcome.add_class("outcome-success")
            outcome.update("✓ Plan proposed")
        elif record.status == "completed":
            spinner.styles.display = "none"
            outcome.add_class("outcome-success")
            outcome.update("✓ Completed!")
        elif record.status == "failed":
            spinner.styles.display = "none"
            outcome.add_class("outcome-failure")
            outcome.update("✕ Failed")
        elif record.status in {"questioning", "awaiting_answers"}:
            spinner.styles.display = "none"
            outcome.add_class("outcome-input")
            outcome.update("✎ Input needed")
        else:
            spinner.styles.display = "none"
            outcome.update(record.status.capitalize())

    def _render_plan_review(self, record: TaskRecord, generation: int) -> None:
        plan_display = self.query_one("#plan-display", Static)
        plan_display.update(
            record.plan_text
            or (record.messages[-1] if record.messages else "")
            or "Waiting for the agent to return a structured plan."
        )
        questions = tuple(record.plan_questions)
        answers = self._live_plan_answers(record, dict(record.plan_answers))
        clarifications = {
            question_id: tuple(
                (
                    item.clarification_id,
                    item.user_question,
                    item.status,
                    item.answer,
                    item.error,
                )
                for item in items
            )
            for question_id, items in record.plan_clarifications.items()
        }
        question_signature = (
            record.task_id,
            tuple(
                (
                    question.question_id,
                    question.text,
                    tuple((option.option_id, option.label) for option in question.options),
                    clarifications.get(question.question_id, ()),
                )
                for question in questions
            ),
        )

        async def rebuild_questions() -> None:
            try:
                await self._rebuild_plan_questions(record, questions, answers, generation, question_signature)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                # A stale dynamic widget must never terminate the whole TUI.
                # Textual workers exit the app on uncaught errors by default.
                if generation == self._plan_review_generation:
                    self._set_error(f"Plan review could not be rendered: {error}")
                    self._set_status("Error")

        if self._rendered_plan_question_signature != question_signature:
            self.run_worker(
                rebuild_questions,
                exclusive=True,
                group="plan-questions",
                exit_on_error=False,
            )
        answer_button = self.query_one("#answer-plan-button", Button)
        # The button stays disabled until the asynchronous controls have been
        # mounted, so a fast click cannot query widgets that do not exist yet.
        answer_button.disabled = True
        self._update_plan_action_buttons()

    def _live_plan_answers(self, record: TaskRecord, fallback: dict[str, str]) -> dict[str, str]:
        """Prefer mounted selector values so clarification refreshes keep choices."""
        answers = dict(fallback)
        for index, question in enumerate(record.plan_questions):
            nodes = self.query(f"#plan-question-{index}").nodes
            if not nodes:
                continue
            selection = nodes[0].value
            custom_text = self._plan_custom_answer_text(index)
            if not self._has_plan_answer(selection, custom_text):
                continue
            if selection == CUSTOM_ANSWER_OPTION_ID:
                answers[question.question_id] = encode_custom_answer(custom_text)
                continue
            # Old widgets may still hold option ids from a prior question round.
            # Never map those onto revised questions with different option ids.
            answer_id = str(selection)
            if is_valid_plan_answer(question, answer_id):
                answers[question.question_id] = answer_id
            else:
                answers.pop(question.question_id, None)
        return answers

    def _update_plan_action_buttons(self) -> None:
        record = self.coordinator.get(self._selected_task_id or "")
        if record is None or record.mode != "plan":
            return
        answer_nodes = self.query("#answer-plan-button")
        implement_nodes = self.query("#implement-button")
        if not answer_nodes.nodes or not implement_nodes.nodes:
            return
        selected = {
            index: self.query_one(f"#plan-question-{index}", Select).value
            for index, question in enumerate(record.plan_questions)
            if self.query(f"#plan-question-{index}").nodes
        }
        all_answered = all(
            self._has_plan_answer(selected.get(index), self._plan_custom_answer_text(index))
            for index in range(len(record.plan_questions))
        )
        answer_nodes.first().disabled = not (
            bool(record.plan_questions)
            and record.status in {"proposed", "completed", "awaiting_answers"}
            and len(selected) == len(record.plan_questions)
            and all_answered
            and not record.plan_confirmed
        )
        implement_button = implement_nodes.first()
        if record.sync_recovery:
            # Orchestration owns coding→finalize→push for Sync recovery.
            implement_button.disabled = True
            implement_button.add_class("implemented")
            implement_button.label = "Auto-resolving"
            return
        implemented = record.plan_implemented
        implement_button.disabled = implemented or not (
            record.plan_confirmed
            and all(not question.required or question.question_id in record.plan_answers for question in record.plan_questions)
        )
        implement_button.set_class(implemented, "implemented")
        implement_button.label = "Implemented" if implemented else "Implement"

    @staticmethod
    def _has_plan_answer(value, custom_text: str = "") -> bool:
        if value in (Select.BLANK, "", getattr(Select, "NULL", object())):
            return False
        return value != CUSTOM_ANSWER_OPTION_ID or bool(custom_text.strip())

    @staticmethod
    def _plan_answer_select_value(
        question: PlanQuestion, saved_answer: str | None
    ) -> tuple[object, str | None]:
        """Resolve a Select value that is legal for the current question options."""
        saved_custom_text = custom_answer_text(saved_answer)
        if saved_custom_text:
            return CUSTOM_ANSWER_OPTION_ID, saved_custom_text
        if saved_answer and is_valid_plan_answer(question, saved_answer):
            return saved_answer, None
        return Select.NULL, None

    def _plan_custom_answer_text(self, index: int) -> str:
        nodes = self.query(f"#plan-custom-answer-{index}").nodes
        return nodes[0].text if nodes else ""

    def _update_plan_custom_answer_visibility(self, select_id: str, value) -> None:
        index = select_id.removeprefix("plan-question-")
        nodes = self.query(f"#plan-custom-answer-{index}").nodes
        if nodes:
            nodes[0].styles.display = "block" if value == CUSTOM_ANSWER_OPTION_ID else "none"

    def _update_plan_clarification_answer(self, select_id: str, value) -> None:
        index = select_id.removeprefix("plan-clarification-select-")
        answer_nodes = self.query(f"#plan-clarification-answer-{index}").nodes
        if not answer_nodes:
            return
        record = self.coordinator.get(self._selected_task_id or "")
        if record is None or not index.isdigit():
            answer_nodes[0].update("")
            return
        question_index = int(index)
        if question_index < 0 or question_index >= len(record.plan_questions):
            answer_nodes[0].update("")
            return
        question = record.plan_questions[question_index]
        clarifications = record.plan_clarifications.get(question.question_id, [])
        selected = next(
            (item for item in clarifications if item.clarification_id == value),
            None,
        )
        answer_nodes[0].update(self._clarification_display_text(selected) if selected else "")

    @staticmethod
    def _clarification_display_text(clarification: PlanClarification | None) -> str:
        if clarification is None:
            return ""
        if clarification.status in {"queued", "running"}:
            return f"Q: {clarification.user_question}\n\nAsking…"
        if clarification.status == "failed":
            return (
                f"Q: {clarification.user_question}\n\n"
                f"Clarification failed: {clarification.error or 'Unknown error.'}"
            )
        return f"Q: {clarification.user_question}\n\n{clarification.answer or '(No answer returned.)'}"

    @staticmethod
    def _clarification_option_label(clarification: PlanClarification) -> str:
        preview = clarification.user_question.replace("\n", " ").strip()
        if len(preview) > 48:
            preview = f"{preview[:45]}..."
        if clarification.status in {"queued", "running"}:
            return f"Asking: {preview}"
        if clarification.status == "failed":
            return f"Failed: {preview}"
        return preview

    def _open_plan_clarification(self, index: int) -> None:
        record = self.coordinator.get(self._selected_task_id or "")
        if record is None or record.mode != "plan":
            return
        if index < 0 or index >= len(record.plan_questions):
            return
        question = record.plan_questions[index]

        def on_dismiss(user_question: str | None) -> None:
            if not user_question:
                return
            clarify = getattr(self.coordinator, "clarify_plan_question", None)
            if clarify is None or not clarify(record.task_id, question.question_id, user_question):
                self._set_status("Clarification could not be sent")
                return
            self._mark_task_current_session(record)
            self._set_status("Asking clarification")

        self.push_screen(PlanClarificationScreen(question.text), on_dismiss)

    async def _rebuild_plan_questions(
        self,
        record: TaskRecord,
        questions: tuple[PlanQuestion, ...],
        answers: dict[str, str],
        generation: int,
        question_signature: tuple[object, ...],
    ) -> None:
        """Replace question controls after Textual has completed child removal."""
        if not self._is_current_plan_review(record, generation):
            return
        question_container = self.query_one("#plan-questions", Vertical)
        await question_container.remove_children()
        if not self._is_current_plan_review(record, generation):
            return
        if not questions:
            await question_container.mount(Static("No questions from the agent.", markup=False))
        else:
            widgets = [Static("Questions", classes="plan-questions-heading", markup=False)]
            for index, question in enumerate(questions):
                saved_answer = answers.get(question.question_id)
                selected_value, saved_custom_text = self._plan_answer_select_value(
                    question, saved_answer
                )
                clarifications = list(record.plan_clarifications.get(question.question_id, []))
                widgets.extend(
                    (
                        Static(question.text, classes="plan-question", markup=False),
                        Horizontal(
                            PlanAnswerSelect(
                                _literal_select_options(
                                    [
                                        (option.label, option.option_id)
                                        for option in plan_answer_options(question)
                                    ]
                                ),
                                value=selected_value,
                                allow_blank=True,
                                id=f"plan-question-{index}",
                                classes="plan-answer-select",
                            ),
                            Button("?", id=f"plan-clarify-{index}", classes="plan-clarify-button"),
                            classes="plan-answer-row",
                        ),
                        TextArea(
                            saved_custom_text or "",
                            id=f"plan-custom-answer-{index}",
                            classes="plan-custom-answer",
                        ),
                    )
                )
                if clarifications:
                    latest = clarifications[-1]
                    widgets.extend(
                        (
                            PlanAnswerSelect(
                                _literal_select_options(
                                    [
                                        (self._clarification_option_label(item), item.clarification_id)
                                        for item in clarifications
                                    ]
                                ),
                                value=latest.clarification_id,
                                allow_blank=False,
                                id=f"plan-clarification-select-{index}",
                                classes="plan-clarification-select",
                            ),
                            Static(
                                self._clarification_display_text(latest),
                                id=f"plan-clarification-answer-{index}",
                                classes="plan-clarification-answer",
                                markup=False,
                            ),
                        )
                    )
            await question_container.mount(*widgets)
            for index, question in enumerate(questions):
                selected_value, _saved_custom_text = self._plan_answer_select_value(
                    question, answers.get(question.question_id)
                )
                # ``mount`` waits for the selector itself to attach, while
                # the selector's deferred mount callback may still be queued
                # behind the current refresh. Initialize it here as well so
                # restored answers are visible immediately after a rebuild.
                select = self.query_one(f"#plan-question-{index}", PlanAnswerSelect)
                select._initialize_after_mount()
                self._update_plan_custom_answer_visibility(
                    f"plan-question-{index}",
                    selected_value,
                )
        if self._is_current_plan_review(record, generation):
            self._rendered_plan_question_signature = question_signature
            self._update_plan_action_buttons()

    def _is_current_plan_review(self, record: TaskRecord, generation: int) -> bool:
        return (
            generation == self._plan_review_generation
            and self.coordinator.get(record.task_id) is record
            and self._selected_task_id == record.task_id
        )

    def _answer_plan(self) -> None:
        record = self.coordinator.get(self._selected_task_id or "")
        if record is None or record.mode != "plan":
            return
        answers: dict[str, str] = {}
        for index, question in enumerate(record.plan_questions):
            selection = self.query_one(f"#plan-question-{index}", Select).value
            custom_text = self._plan_custom_answer_text(index)
            if self._has_plan_answer(selection, custom_text):
                answers[question.question_id] = (
                    encode_custom_answer(custom_text)
                    if selection == CUSTOM_ANSWER_OPTION_ID
                    else str(selection)
                )
        if len(answers) != len(record.plan_questions):
            self._set_status("Answer every question first")
            return
        LOGGER.info(
            "Submitting plan answers task=%s answer_ids=%s",
            record.task_id,
            sorted(CUSTOM_ANSWER_OPTION_ID if custom_answer_text(answer) else answer for answer in answers.values()),
        )
        answer_plan = getattr(self.coordinator, "answer_plan", None)
        if answer_plan is None or not answer_plan(record.task_id, answers):
            self._set_status("Plan answers could not be submitted")
            return
        self._mark_task_current_session(record)
        self._set_status("Reviewing answers")

    def _implement_plan(self) -> None:
        record = self.coordinator.get(self._selected_task_id or "")
        if record is None or record.mode != "plan" or record.sync_recovery:
            return
        implement_plan = getattr(self.coordinator, "implement_plan", None)
        coding_record = implement_plan(record.task_id) if implement_plan is not None else None
        if coding_record is None:
            self._set_status("The agent must confirm no more questions")
            return
        implement_button = self.query_one("#implement-button", Button)
        implement_button.disabled = True
        implement_button.add_class("implemented")
        implement_button.label = "Implemented"
        self._focus_submitted_task(coding_record, "plan implementation")
        self._set_status("Implementation queued")

    def _start_new_task(self) -> None:
        """Clear the selected task and unlock a fresh prompt editor."""
        self._selected_task_id = None
        self._new_task_mode = True
        self._refresh_topic_select()
        self._refresh_task_list()
        self._render_selected_task_safely("new task")
        self._set_status("New task")

    def _set_prompt_text(self, text: str, *, editable: bool) -> None:
        prompt = self.query_one("#prompt-input", DaedalusVimTextArea)
        # Loading text is a programmatic operation, so temporarily make the
        # widget writable even when replacing a submitted task's immutable
        # prompt.
        prompt.read_only = False
        prompt.load_text(text)
        prompt.read_only = not editable
        self.query_one("#output", TranscriptLog).invalidate_render_cache()
        send_button = self.query_one("#send-button", Button)
        send_button.disabled = not editable
        if editable:
            prompt.enter_insert_mode()
            prompt.focus()

    def _copy_selection(self) -> None:
        selection = self._get_selected_text()
        if not selection:
            self._set_status("Select text first")
            return
        self._copy_text(selection)
        self._set_status("Selection copied")

    def _handle_vim_key(self, key: str) -> None:
        if key == "j":
            self._scroll_output("down")
        elif key == "k":
            self._scroll_output("up")
        elif key == "G":
            self._scroll_output("end")
        elif key == "ctrl+d":
            self._scroll_output("page_down")
        elif key == "pageup":
            self._scroll_output("page_up")
        elif key == "y":
            self._copy_selection()
        elif key == "p":
            self._paste_into_prompt()
        elif key == "i":
            self.query_one("#prompt-input", TextArea).focus()
            self._set_status("Insert")

    def _scroll_output(self, direction: str) -> None:
        output = self.query_one("#output", TranscriptLog)
        output.focus()
        scroll_methods = {
            "up": output.scroll_up,
            "down": output.scroll_down,
            "home": output.scroll_home,
            "end": output.scroll_end,
            "page_up": output.scroll_page_up,
            "page_down": output.scroll_page_down,
        }
        if direction in {"page_up", "page_down"}:
            scroll_methods[direction](animate=False)
        else:
            scroll_methods[direction](animate=False, immediate=True)
        self._set_status(f"Output {direction.replace('_', ' ')}")

    def _paste_into_prompt(self) -> None:
        text = paste_from_system_clipboard()
        if text is None:
            self._set_status("Clipboard unavailable")
            return
        prompt = self.query_one("#prompt-input", TextArea)
        if prompt.read_only:
            self._set_status("Press New Task first")
            return
        if isinstance(prompt, DaedalusVimTextArea):
            prompt.enter_insert_mode()
        prompt.focus()
        prompt.insert(text)
        self._set_status("Pasted")

    def _get_selected_text(self) -> str | None:
        """Return a TextArea selection or the active screen selection."""
        focused = self.focused
        if isinstance(focused, TextArea):
            selected_text = focused.selected_text
            if selected_text:
                return selected_text
        # A read-only diagnostic TextArea may retain its selection while focus
        # is returned to the prompt. Check the other editors before falling
        # back to Textual's arbitrary widget-selection model.
        for text_area in self.query(TextArea):
            if text_area is focused:
                continue
            selected_text = text_area.selected_text
            if selected_text:
                return selected_text
        return self.screen.get_selected_text()

    def copy_to_clipboard(self, text: str) -> None:
        """Use Textual's OSC 52 path and a native clipboard fallback."""
        super().copy_to_clipboard(text)
        copy_to_system_clipboard(text)

    def _copy_text(self, text: str) -> None:
        self.copy_to_clipboard(text)

    def _pause_task(self) -> None:
        record = self.coordinator.get(self._selected_task_id or "")
        if record is not None and self.coordinator.pause(record.task_id):
            self._mark_task_current_session(record)
            self._set_status("Pausing")

    def _resume_task(self) -> None:
        record = self.coordinator.get(self._selected_task_id or "")
        notes_widget = self.query_one("#resume-notes", TextArea)
        notes = notes_widget.text.strip()
        if record is not None and self.coordinator.resume(record.task_id, notes):
            self._mark_task_current_session(record)
            notes_widget.clear()
            self._set_status("Resuming")

    def _continue_plan(self) -> None:
        record = self.coordinator.get(self._selected_task_id or "")
        notes_widget = self.query_one("#resume-notes", TextArea)
        notes = notes_widget.text.strip()
        if record is not None and self.coordinator.continue_plan(record.task_id, notes):
            self._mark_task_current_session(record)
            notes_widget.clear()
            self._set_status("Continuing plan")

    def _cancel_task(self) -> None:
        record = self.coordinator.get(self._selected_task_id or "")
        if record is not None and self.coordinator.cancel(record.task_id):
            if record.sync_recovery:
                self._refresh_push_button()
                self._set_status("Sync conflict recovery cancelled")
            else:
                self._set_status("Cancelling")

    def _retry_task(self) -> None:
        record = self.coordinator.get(self._selected_task_id or "")
        retry = getattr(self.coordinator, "retry", None)
        if record is None or retry is None or not retry(record.task_id):
            self._set_status("Retry unavailable")
            return
        self._mark_task_current_session(record)
        self._set_status("Retrying")

    def _follow_up_task(self) -> None:
        record = self.coordinator.get(self._selected_task_id or "")
        follow_up = getattr(self.coordinator, "follow_up", None)
        prompt = self.query_one("#prompt-input", TextArea).text.strip()
        if record is None or follow_up is None or not prompt:
            self._set_status("Enter a follow-up prompt")
            return
        try:
            next_record = follow_up(record.task_id, prompt)
        except (RuntimeError, ValueError) as error:
            self._set_error(str(error))
            self._set_status("Error")
            return
        if next_record is None:
            self._set_status("Follow Up unavailable")
            return
        self._focus_submitted_task(next_record, "task follow-up")

    def _set_status(self, status: str) -> None:
        self.query_one("#status", Static).update(status)

    def _set_error(self, error: str) -> None:
        error = truncate_diagnostic(error) if error else ""
        if error == self._displayed_error:
            return
        output = self.query_one("#output", TranscriptLog)
        output.clear_errors()
        if error:
            output.write_error(error)
        self._displayed_error = error
