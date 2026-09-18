"""Textual interface for concurrent local agent tasks."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Callable
import sys
import threading
import time
import uuid

from rich.cells import cell_len
from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, ContentSwitcher, DataTable, Footer, Header, Input, Log, Select, Static, TextArea
from textual.widgets.select import InvalidSelectValueError
from .agent_runner import AgentRunner
from .clipboard import copy_to_system_clipboard, paste_from_system_clipboard
from .config import (
    CodingStatisticsSettings,
    OrchestrateSettings,
    PromptingSettings,
    TuiSettings,
    load_coding_statistics_settings,
    load_orchestrate_settings,
    load_orchestration_settings,
    load_prompting_settings,
    load_tui_settings,
)
from .debug_log import (
    LOGGER,
    LoggingStatus,
    close_fault_handler,
    configure_debug_logging,
    install_fault_handler,
    log_exception,
)
from .local_storage import LocalStorage
from .output_viewer import LATEST_SOURCE, OutputViewer, ViewerSource, response_sources
from .prompt_store import DraftRecord, PromptStore, PromptStoreError
from .git_worktree import (
    GitWorktreeError,
    list_local_branches,
    parse_push_notice,
    push_branch,
    remote_exists,
)
from .memory import DEFAULT_MEMORY_FILE, TaskMemoryStore
from .orchestrate_coordinator import ORCHESTRATE_PHASE, OrchestrateCoordinator
from .orchestrate_session import OrchestrationSession
from .project_initializer import (
    BACKENDS,
    initialize_project,
    load_initializer_settings,
    validate_project_name,
)
from .personal_supabase import (
    is_personal_supabase_registered,
    register_personal_supabase,
    schema_from_project_root,
)
from .firebase import (
    is_firebase_registered,
    load_firebase_status,
    project_id_from_project_root,
    register_firebase,
)
from .provider_auth import check_provider_auth, sign_in_instructions
from .projects import (
    DaedalusProject,
    discover_projects,
    is_direct_child_project,
    project_from_directory,
)
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
from .task_coordinator import ACTIVE_RUN_STATUSES, TaskCoordinator, TaskRecord
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
from .usage_monitor import ClaudeAccountUsage, ProviderUsage, UsageMonitor, format_usage_bar
from .token_usage import calculate_token_usage, merge_usage_entries, task_usage_entry, usage_entries_from_memory
from .verification import truncate_diagnostic
from .vim_text_area import MODE_LABELS, SUBMIT_KEYS, DaedalusVimTextArea, VimMode as VimModeEnum


def _literal_select_options(options: list[tuple[str, str]]) -> list[tuple[Text, str]]:
    """Build Select prompts that Rich will not parse as markup."""
    return [(Text(label), value) for label, value in options]


_THREAD_EXIT_APPS: dict[int, "DaedalusTuiApp"] = {}
_THREAD_EXIT_APPS_LOCK = threading.Lock()
_THREAD_EXIT_HOOK_REGISTERED = False


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


# The prompt editor owns the submit keys because it must let them through
# instead of inserting a newline; the menu label is derived from them so the
# two can never drift apart.
SUBMIT_SHORTCUT = " / ".join(
    "+".join(part.capitalize() for part in key.split("+")) for key in SUBMIT_KEYS
)

GLOBAL_SHORTCUTS = (
    (SUBMIT_SHORTCUT, "Send prompt (new task or follow-up)", "submit_prompt"),
    ("Tab", "Toggle coding/plan mode", "toggle_plan_mode"),
    ("Ctrl+C", "Stop the run, keep progress, restore prompt", "interrupt_task"),
    ("Ctrl+X", "Same as Ctrl+C (stop the run)", "interrupt_task"),
    ("Ctrl+Alt+S", "Copy selection", "copy_selection"),
    ("Ctrl+P", "Pause task", "pause_task"),
    ("Ctrl+R", "Resume task (Vim redo inside the prompt)", "resume_task"),
    ("Ctrl+N", "New project", "show_new_project"),
    ("Ctrl+Q", "Quit Daedalus", "quit"),
    ("Ctrl+K", "Show keyboard shortcuts", "show_shortcuts"),
    ("Ctrl+T", "Show coding statistics and total Claude usage", "show_statistics"),
    ("Ctrl+H", "Show pushed commit history", "show_push_history"),
    ("Ctrl+O", "Toggle Orchestrate Mode", "toggle_orchestrate_mode"),
)


def binding_keys(shortcut: str) -> str:
    """Turn a displayed shortcut into Textual's comma-separated key list.

    A shortcut may offer several keys for one action, written for the
    shortcuts menu as ``"Shift+Enter / Ctrl+Enter"``. Textual binds the same
    alternatives as ``"shift+enter,ctrl+enter"``.
    """
    return ",".join(part.strip().lower() for part in shortcut.split("/") if part.strip())


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
    "interrupted",
    "awaiting_answers",
}
_SELECT_EMPTY = (Select.BLANK, "", getattr(Select, "NULL", None))

SHORTCUT_SECTIONS = (
    (
        "Global shortcuts",
        tuple((shortcut, description) for shortcut, description, _ in GLOBAL_SHORTCUTS),
    ),
    (
        "Output navigation (transcript, errors, or viewer)",
        (
            ("j / k", "Scroll down / up"),
            ("gg / G", "Scroll to start / end"),
            ("Ctrl+D / Ctrl+U", "Scroll one page down / up"),
            ("y", "Copy selected text"),
            ("p", "Paste clipboard into the prompt"),
            ("i", "Focus the prompt"),
        ),
    ),
    (
        "Task sidebar",
        (("dd", "Delete the task under the sidebar cursor"),),
    ),
    (
        "Prompt (Vim mode)",
        (
            ("Esc", "Normal mode; clears selection and pending keys"),
            ("i / a / I / A / o / O", "Enter Insert mode"),
            ("h / j / k / l", "Move the cursor (counts: 3j)"),
            ("w / b / e / 0 / $", "Move by word or line"),
            ("gg / G", "Move to document start / end"),
            ("v / V", "Select characters / whole lines"),
            ("x / dd / dw / d$", "Cut (2dd cuts two lines)"),
            ("yy / yw / y$", "Copy (2yy copies two lines)"),
            ("visual d / x / y / c", "Cut / copy / change selection"),
            ("p / P", "Paste after / before (lines stay lines)"),
            ("\"+y / \"+p / \"+P", "Copy to / paste from the system clipboard"),
            ("u / Ctrl+R", "Undo / redo"),
            ("Enter", "Insert a newline"),
        ),
    ),
    (
        "Clipboard and storage",
        (
            ("Every cut/yank", "Also copies to the system clipboard"),
            ("p with empty register", "Pastes the system clipboard"),
            ("Drafts", "Saved automatically under prompts/"),
            ("Sent prompts", "Archived exactly as turn-NNNN.md"),
            ("Errors", "Written under errors/ with task and run ids"),
            ("Pushed commits", "Recorded in launch-root memory; Ctrl+H opens the Push log"),
        ),
    ),
)

# Backends a project can register for. Firebase leads because registration is
# the common case for new projects; "none" stays available for front-end-only
# work.
BACKEND_LABELS = {
    "none": "No backend",
    "firebase": "Firebase",
    "supabase": "Personal Supabase",
}
BACKEND_OPTIONS = tuple((BACKEND_LABELS[name], name) for name in ("firebase", "supabase", "none"))


# Trailing project-selector entry. Discovery only walks the launch root, so one
# sentinel keeps a project living anywhere else reachable without listing every
# directory on the machine in the selector.
OPEN_DIRECTORY_VALUE = "__open-project-directory__"
OPEN_DIRECTORY_LABEL = "Open directory…"


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

    _pending_user_value = None

    def _watch_value(self, value) -> None:
        super()._watch_value(value)
        self._latest_value = value
        if self.id == "compact-settings-value":
            # A value assigned outside a programmatic refresh is a user choice
            # that has not been applied yet. Remember it so a refresh queued
            # behind it (for example from a mount-time Select.Changed event)
            # cannot reset the control before the choice is processed.
            try:
                suppressed = self.app._suppress_compact_setting_change
            except Exception:
                suppressed = True
            self._pending_user_value = None if suppressed else value
            return
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


class OpenProjectDirectoryScreen(ModalScreen[str | None]):
    """Collect the path of a project that launch-root discovery cannot see.

    Discovery is deliberately limited to immediate launch-root children, so a
    project created, cloned, or moved elsewhere would otherwise require
    relaunching the TUI from another directory.
    """

    BINDINGS = [
        ("escape", "cancel_open_directory", "Cancel"),
    ]

    def __init__(self, base_directory: Path) -> None:
        super().__init__()
        self.base_directory = base_directory.expanduser().resolve()

    def compose(self) -> ComposeResult:
        with Vertical(id="open-directory-dialog"):
            yield Static("Open project directory", id="open-directory-title")
            yield Static(
                f"Absolute path, ~ path, or a path relative to {self.base_directory}",
                id="open-directory-subtitle",
                markup=False,
            )
            yield Input(placeholder="~/code/my-project", id="open-directory-input")
            yield Static("", id="open-directory-status", markup=False)
            with Horizontal(id="open-directory-actions"):
                yield Button("Open", id="open-directory-button", variant="primary")
                yield Button("Cancel", id="cancel-open-directory-button")

    def on_mount(self) -> None:
        self.query_one("#open-directory-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-open-directory-button":
            self.dismiss(None)
        elif event.button.id == "open-directory-button":
            self._open_directory()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "open-directory-input":
            self._open_directory()

    def action_cancel_open_directory(self) -> None:
        self.dismiss(None)

    def _open_directory(self) -> None:
        status = self.query_one("#open-directory-status", Static)
        directory_input = self.query_one("#open-directory-input", Input)
        entered = directory_input.value.strip()
        if not entered:
            status.update("Enter a directory path.")
            directory_input.focus()
            return
        candidate = Path(entered).expanduser()
        if not candidate.is_absolute():
            candidate = self.base_directory / candidate
        try:
            resolved = candidate.resolve()
            is_directory = resolved.is_dir()
        except OSError as error:
            status.update(str(error))
            directory_input.focus()
            return
        if not is_directory:
            status.update(f"{resolved} is not an existing directory.")
            directory_input.focus()
            return
        self.dismiss(str(resolved))


class ProjectInitializerScreen(ModalScreen[dict | None]):
    """Collect a project slug and create a Daedalus-compatible directory."""

    BINDINGS = [
        ("escape", "cancel_initializer", "Cancel"),
    ]

    def __init__(self, launch_root: Path, default_backend: str = "firebase") -> None:
        super().__init__()
        self.launch_root = launch_root.resolve()
        self.default_backend = default_backend if default_backend in BACKENDS else "none"
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
            yield Static("Backend", id="project-backend-label")
            yield Select(
                list(BACKEND_OPTIONS),
                value=self.default_backend,
                allow_blank=False,
                id="project-backend-select",
            )
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
        backend = str(self.query_one("#project-backend-select", Select).value)
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

        self._busy = True
        status.update(f"Initializing {project_name}…")
        self.query_one("#create-project-button", Button).disabled = True
        try:
            result = initialize_project(
                {
                    "requestId": str(uuid.uuid4()),
                    "projectName": project_name,
                    "createGitHubRepository": create_github,
                    "backend": backend,
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


class ProviderSignInScreen(ModalScreen[None]):
    """Report a provider's sign-in status and hand over the login command.

    The TUI deliberately does not host the login itself: a child CLI that takes
    over this terminal makes the Textual application appear to vanish, which is
    the same reason agent subprocesses run with their stdin detached.
    """

    BINDINGS = [
        ("escape", "close_sign_in", "Close"),
    ]

    def __init__(self, provider: str, settings: TuiSettings) -> None:
        super().__init__()
        self.provider = provider
        self.settings = settings
        self.provider_settings = settings.auth.for_provider(provider)
        self._checking = False

    def compose(self) -> ComposeResult:
        with Vertical(id="sign-in-dialog"):
            yield Static(f"{self.provider_settings.label} sign-in", id="sign-in-title")
            mode = "account" if self.settings.auth.uses_account_login else "API key"
            yield Static(f"Authentication mode: {mode}", id="sign-in-mode")
            yield Static("Checking…", id="sign-in-detail", markup=False)
            with Horizontal(id="sign-in-actions"):
                yield Button("Check again", id="recheck-sign-in-button", variant="primary")
                yield Button("Close", id="close-sign-in-button")

    def on_mount(self) -> None:
        self._check()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-sign-in-button":
            self.dismiss(None)
        elif event.button.id == "recheck-sign-in-button":
            self._check()

    def action_close_sign_in(self) -> None:
        self.dismiss(None)

    def _check(self) -> None:
        if self._checking:
            return
        self._checking = True
        self.query_one("#sign-in-detail", Static).update("Checking…")
        self.query_one("#recheck-sign-in-button", Button).disabled = True

        def work() -> None:
            try:
                status = check_provider_auth(self.provider, self.provider_settings)
            except Exception as error:  # pragma: no cover - defensive UI boundary
                self.app.call_from_thread(self._show_failure, str(error))
            else:
                self.app.call_from_thread(self._show_status, status)

        self.app.run_worker(
            work,
            thread=True,
            exclusive=True,
            group="provider-auth",
            exit_on_error=False,
        )

    def _show_status(self, status) -> None:
        self._checking = False
        if not self.is_running:
            return
        self.query_one("#recheck-sign-in-button", Button).disabled = False
        self.query_one("#sign-in-detail", Static).update(
            f"{status.summary}\n\n"
            + sign_in_instructions(status, self.settings.auth.uses_account_login)
        )

    def _show_failure(self, message: str) -> None:
        self._checking = False
        if not self.is_running:
            return
        self.query_one("#recheck-sign-in-button", Button).disabled = False
        self.query_one("#sign-in-detail", Static).update(
            f"Could not check {self.provider_settings.label} sign-in status.\n\n{message}"
        )


class BackendRegistrationScreen(ModalScreen[str | None]):
    """Choose and scaffold the backend an existing project targets."""

    BINDINGS = [
        ("escape", "cancel_backend", "Cancel"),
    ]

    def __init__(self, project_root: Path, registered: str | None, default_backend: str) -> None:
        super().__init__()
        self.project_root = project_root.resolve()
        self.registered = registered
        self.default_backend = registered or (
            default_backend if default_backend in BACKENDS and default_backend != "none" else "firebase"
        )

    def compose(self) -> ComposeResult:
        with Vertical(id="backend-dialog"):
            yield Static("Project backend", id="backend-title")
            yield Static(f"Scaffolds backend files in {self.project_root}", id="backend-subtitle")
            if self.registered:
                yield Static(
                    f"Already registered for {BACKEND_LABELS[self.registered]}.",
                    id="backend-registered",
                    markup=False,
                )
            yield Select(
                [(label, value) for label, value in BACKEND_OPTIONS if value != "none"],
                value=self.default_backend,
                allow_blank=False,
                id="backend-select",
            )
            yield Static(
                "Registration writes configuration and rules only. Orchestration "
                "applies them remotely after verification passes.",
                id="backend-note",
            )
            yield Static("", id="backend-status", markup=False)
            with Horizontal(id="backend-actions"):
                yield Button("Register", id="register-backend-confirm", variant="primary")
                yield Button("Cancel", id="cancel-backend-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-backend-button":
            self.dismiss(None)
        elif event.button.id == "register-backend-confirm":
            self._register()

    def action_cancel_backend(self) -> None:
        self.dismiss(None)

    def _register(self) -> None:
        backend = str(self.query_one("#backend-select", Select).value)
        status = self.query_one("#backend-status", Static)
        try:
            if backend == "firebase":
                result = register_firebase(
                    self.project_root,
                    project_id=project_id_from_project_root(self.project_root),
                )
            else:
                result = register_personal_supabase(
                    self.project_root,
                    schema=schema_from_project_root(self.project_root),
                )
        except ValueError as error:
            status.update(str(error))
            return
        if result.status != "success":
            status.update(result.message)
            return
        self.dismiss(result.message)


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
        ("ctrl+t", "close_statistics", "Close"),
    ]

    def __init__(
        self,
        entries,
        settings: CodingStatisticsSettings | None = None,
        account_usage_reader: Callable[[], ClaudeAccountUsage] | None = None,
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
        # Reading every Claude Code transcript can take a moment, so the screen
        # opens with the Daedalus figures and fills the account total in later.
        self._account_usage_reader = account_usage_reader
        self.account_usage: ClaudeAccountUsage | None = None
        self._account_error = ""

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
                yield Static(id="claude-account-metric", classes="usage-metric")
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
            yield Static("Press Esc or Ctrl+T to close", id="coding-statistics-footer")

    def on_mount(self) -> None:
        self._refresh_statistics_view()
        self._start_account_usage_read()

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
        self._render_account_metric()

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

    # --- account-wide Claude usage ---------------------------------------------

    def _start_account_usage_read(self) -> None:
        """Read every Claude Code token off the UI thread, then show the total.

        The Daedalus figures above count only tasks this app launched; this
        reads Claude Code's own local records so the operator sees their whole
        Claude spend, including sessions run outside Daedalus.
        """
        reader = self._account_usage_reader
        if reader is None:
            return
        app = self.app

        def work() -> None:
            try:
                usage = reader()
            except Exception as error:  # pragma: no cover - defensive UI boundary
                log_exception("Claude account usage reading failed", error)
                usage, failure = None, str(error)
            else:
                failure = ""
            try:
                app.call_from_thread(self._show_account_usage, usage, failure)
            except RuntimeError:
                # The operator closed the screen, or the app stopped, while the
                # transcripts were still being read.
                return

        self.app.run_worker(
            work,
            thread=True,
            exclusive=True,
            group="claude-account-usage",
            exit_on_error=False,
        )

    def _show_account_usage(self, usage: ClaudeAccountUsage | None, error: str) -> None:
        self.account_usage = usage
        self._account_error = error
        if not self.is_running:
            return
        self._render_account_metric()

    def _render_account_metric(self) -> None:
        """Draw the account-wide Claude total, which is always a token count."""
        try:
            tile = self.query_one("#claude-account-metric", Static)
        except NoMatches:  # pragma: no cover - the tile is part of compose
            return
        usage = self.account_usage
        if usage is None:
            if self._account_error:
                tile.update("All Claude tokens\nunavailable")
                tile.tooltip = self._account_error
            elif self._account_usage_reader is None:
                tile.update("All Claude tokens\n—")
                tile.tooltip = "Usage readings are disabled in the parameter file."
            else:
                tile.update("All Claude tokens\nreading…")
                tile.tooltip = None
            return
        if not usage.ok:
            tile.update("All Claude tokens\nno usage data")
            tile.tooltip = usage.detail or None
            return
        # The tile keeps the same two-line shape as its neighbours; the record's
        # span and sources belong in the tooltip, where they cannot clip.
        tile.update(f"All Claude tokens\n{_format_count(usage.total_tokens)}")
        since = f"recorded since {usage.first_day}\n" if usage.first_day else ""
        tile.tooltip = (
            "Every Claude Code token recorded on this machine, including "
            "sessions run outside Daedalus.\n"
            f"{since}"
            f"today: {_format_count(usage.today_tokens)} tokens\n"
            f"{usage.days_recorded} days recorded · {usage.scanned_files} transcripts\n"
            f"{usage.detail}"
        )

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


class PushedCommitsScreen(ModalScreen[None]):
    """Show the persistent record of commits successfully pushed by Daedalus."""

    BINDINGS = [
        ("escape", "close_push_history", "Close"),
        ("ctrl+h", "close_push_history", "Close"),
    ]

    def __init__(self, records: tuple[dict[str, object], ...], memory_path: Path) -> None:
        super().__init__()
        self.records = records
        self.memory_path = memory_path

    def compose(self) -> ComposeResult:
        with Vertical(id="pushed-commits-dialog"):
            yield Static("Pushed commits", id="pushed-commits-title")
            yield Static(
                f"Successful pushes are recorded in {self.memory_path}",
                id="pushed-commits-subtitle",
                markup=False,
            )
            yield TextArea(self._history_text(), id="pushed-commits-content", read_only=True, soft_wrap=False)
            yield Static("Press Esc or Ctrl+H to close", id="pushed-commits-footer")

    def on_mount(self) -> None:
        self.query_one("#pushed-commits-content", TextArea).focus()

    def action_close_push_history(self) -> None:
        self.dismiss(None)

    def _history_text(self) -> str:
        if not self.records:
            return "No pushed commits recorded yet."
        lines = []
        for record in reversed(self.records):
            timestamp = str(record.get("timestamp", "—"))
            project = str(record.get("project", "—"))
            branch = str(record.get("branch", "—"))
            remote = str(record.get("remote", "—"))
            commit = str(record.get("commit", "—"))
            lines.append(f"{timestamp}  {project}  {remote}/{branch}  {commit}")
        return "\n".join(lines)


def _format_tokens(tokens: int) -> str:
    return f"{tokens:,}"


def _format_count(value: int) -> str:
    return f"{value:,}"


class DaedalusTuiApp(App[None]):
    TITLE = "Daedalus TUI"
    CSS_PATH = "app.tcss"
    # Keep Textual's arbitrary text selection enabled for labels, logs, and
    # other non-editor widgets. TextArea has its own native selection model.
    ALLOW_SELECT = True
    # Ctrl+C and Ctrl+X are priority bindings: they must reach the interrupt
    # action before the Screen's copy binding or TextArea's cut binding can
    # consume them, even when output text is selected.
    BINDINGS = [
        Binding(
            binding_keys(shortcut),
            action,
            description,
            priority=action == "interrupt_task",
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
        prompting_settings: PromptingSettings | None = None,
        usage_monitor: UsageMonitor | None = None,
        orchestrate_settings: OrchestrateSettings | None = None,
        orchestrate_coordinator: object | None = None,
    ) -> None:
        super().__init__()
        self.launch_root = (directory or Path.cwd()).resolve()
        self.memory = TaskMemoryStore(self.launch_root / DEFAULT_MEMORY_FILE)
        self.settings = settings or load_tui_settings()
        self.statistics_settings = statistics_settings or load_coding_statistics_settings()
        self.orchestration_settings = load_orchestration_settings()
        self.orchestrate_settings = orchestrate_settings or self._load_orchestrate_settings()
        self.prompting = prompting_settings or load_prompting_settings()
        # Prompt archives and diagnostics live under the TUI's own storage
        # root, never under the target project or the working directory.
        self.storage = LocalStorage(self.prompting.data_root)
        self.prompt_store = PromptStore(self.storage)
        self.debug_log_path = self.storage.runtime_log_path
        self.fault_log_path = self.storage.fault_log_path
        # Configure the runtime log before anything else can fail, so
        # initialization problems are captured before widgets mount.
        self._logging_status: LoggingStatus = configure_debug_logging(
            self.debug_log_path,
            self.prompting.error_log_max_bytes,
            self.prompting.error_log_backup_count,
        )
        self._fault_log_file = None
        self.runner = runner or AgentRunner(
            auth_policy=self.settings.auth.runner_policy(),
            claude_permission_mode=self.settings.claude.permission_mode,
            claude_allowed_tools=self.settings.claude.allowed_tools,
        )
        try:
            self._opened_directories = list(self.memory.get_opened_project_directories())
        except (OSError, ValueError):
            # Project navigation should remain usable if local memory is unavailable.
            self._opened_directories = []
        discovered = [
            project
            for project in discover_projects(self.launch_root, self.settings.project_discovery)
            if is_direct_child_project(project.path, self.launch_root)
        ]
        if not discovered:
            # Keep the app usable when launched in a new or test directory;
            # orchestration will provide the actionable Git error if needed.
            discovered = [DaedalusProject(self.launch_root, self.launch_root)]
        discovered_paths = {project.path.resolve() for project in discovered}
        for opened in self._opened_project_entries():
            if opened.path not in discovered_paths:
                discovered.append(opened)
                discovered_paths.add(opened.path)
        remembered_project = self._remembered_project()
        if remembered_project in discovered_paths:
            active_project = remembered_project
        else:
            active_project = discovered[0].path.resolve()
        if coordinator is not None and active_project not in discovered_paths:
            discovered.insert(0, DaedalusProject(active_project, self.launch_root))
        self.projects = tuple(discovered)
        self._coordinators: dict[Path, TaskCoordinator] = {}
        self._external_coordinator = coordinator
        # One Orchestrate Mode dispatcher per project, created beside the
        # task coordinator the first time the project's view is used.
        self._orchestrators: dict[Path, OrchestrateCoordinator] = {}
        self._external_orchestrator = orchestrate_coordinator
        self._orchestrate_view_shown = False
        self._selected_session_id: str | None = None
        self._orchestrate_board_rows: list[tuple[str, str | None]] = []
        self._orchestrate_draft_dirty = False
        self._orchestrate_draft_timer = None
        self._suppress_orchestrate_draft_events = False
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
        self._vim_pending_d = False
        self._showing_error_output = False
        self._plan_review_generation = 0
        self._accept_task_events = False
        self._task_event_lock = threading.Lock()
        self._pending_task_events: dict[str, tuple[TaskRecord, str, str, str]] = {}
        self._pending_push_notices: list[tuple[TaskRecord, str]] = []
        self._task_event_flush_scheduled = False
        self._shutdown_lock = threading.Lock()
        self._shutdown_started = False
        self._textual_unmounted = False
        # Set when Textual unwinds from an unhandled exception, so the close
        # hook keeps the composer draft instead of clearing it.
        self._fatal_error = False
        # Set once the close hook has settled the composer draft. Shutdown runs
        # through several entry points that each flush the draft, and one of
        # them follows the close hook, so without this the flush would write
        # back the very prompt the close just cleared.
        self._composer_draft_closed = False
        self._previous_asyncio_exception_handler = None
        self._rendered_plan_question_signature: tuple[object, ...] | None = None
        self._suppress_target_branch_change = False
        self._suppress_topic_change = False
        self._suppress_compact_setting_change = False
        self._compact_setting_category = "provider"
        self._compact_setting_values: dict[str, str] = {}
        self._push_in_flight = False
        self._push_confirmation_branch: str | None = None
        self._compact_mode = False
        self._wrapped_toolbars = False
        self._short_height_mode = False
        self._responsive_measure_pending = False
        self._displayed_error = ""
        # Composer draft state. The composer always holds an editable draft:
        # either the new-task draft (``_composer_task_id`` is None) or the
        # follow-up draft of the selected task.
        self._composer_task_id: str | None = None
        self._composer_project: Path = active_project
        self._composer_revises_turn_id: str | None = None
        self._draft_revision = 0
        self._draft_dirty = False
        self._draft_timer = None
        self._suppress_draft_events = False
        self._submission_in_progress = False
        self._selection_settings: tuple[str, str, str, str] | None = None
        self._suppress_history_select = False
        self._show_all_tasks = False
        self._viewer_visible = False
        self._viewer_full = False
        self._storage_error: str | None = None
        self.usage_monitor = usage_monitor or UsageMonitor(self.settings.usage)
        self._usage_readings: tuple[ProviderUsage, ...] = ()
        self._usage_timer = None
        try:
            self._show_all_tasks = bool(self.memory.get_ui_preference("show_all_tasks", False))
            self._viewer_visible = bool(
                self.memory.get_ui_preference("output_viewer_visible", self.prompting.viewer_visible_by_default)
            )
            self._orchestrate_view_shown = bool(self.memory.get_ui_preference("orchestrate_view", False))
        except (OSError, ValueError):
            pass

    def _load_orchestrate_settings(self) -> OrchestrateSettings:
        """Load the Orchestrate Mode parameter file, falling back to its defaults."""
        try:
            return load_orchestrate_settings(tui_settings=self.settings)
        except (OSError, ValueError) as error:
            LOGGER.warning("Orchestrate Mode settings unavailable, using defaults: %s", error)
            return OrchestrateSettings()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="screen"):
            with Horizontal(id="workspace"):
                with Horizontal(id="main-workspace"):
                    with Vertical(id="task-sidebar"):
                        yield Static("Task updates", id="task-label")
                        yield DataTable(id="task-list", cursor_type="row")
                        yield Button("All tasks", id="history-toggle-button")
                        # Bottom-left usage bar, refreshed every minute.
                        yield Static("Usage: —", id="usage-bar", markup=False)
                    yield from self._compose_project_main()
                yield OutputViewer(
                    id="output-viewer",
                    render_debounce_ms=self.prompting.viewer_render_debounce_ms,
                    hard_line_breaks=self.prompting.viewer_hard_line_breaks,
                    show_action_items=self.prompting.viewer_action_items_by_default,
                    action_item_limit=self.prompting.viewer_action_item_limit,
                )
        yield Footer()

    def _compose_project_main(self) -> ComposeResult:
        with Vertical(id="project-main"):
            yield Static("Local agent orchestration", id="title")
            with Horizontal(id="task-bar"):
                yield Static("Project", id="project-label")
                yield Select(
                    self._project_selector_options(),
                    value=self._project_select_value(),
                    allow_blank=False,
                    id="project-select",
                )
                yield Button("New Project", id="new-project-button")
                yield Button("Create Topic", id="create-topic-button", variant="primary")
                yield Button("Register Backend", id="register-backend-button")
                yield Button("Sign In", id="sign-in-button")
                yield Button("New Task", id="new-task-button", variant="primary")
                yield Button(
                    "Task Mode" if self._orchestrate_view_shown else "Orchestrate Mode",
                    id="orchestrate-mode-button",
                )
            with ContentSwitcher(
                id="view-switcher",
                initial="orchestrate-view" if self._orchestrate_view_shown else "tasks-view",
            ):
                with Vertical(id="tasks-view"):
                    yield from self._compose_tasks_view()
                with Vertical(id="orchestrate-view"):
                    yield from self._compose_orchestrate_view()

    def _compose_tasks_view(self) -> ComposeResult:
        """The ordinary task view: settings, output, plan review, composer."""
        if True:
            # The model and effort lists depend on the default provider: the
            # Claude default model is not a Codex option, so building these
            # controls from the Codex lists would make the initial value
            # illegal and crash on mount before the provider cascade runs.
            default_provider = self.settings.default_provider
            with Horizontal(id="settings"):
                yield Select(
                    [(option.label, option.value) for option in self.settings.providers],
                    value=default_provider,
                    id="provider-select",
                )
                yield Select(
                    self._provider_model_options(default_provider),
                    value=self.settings.default_model_for(default_provider),
                    id="model-select",
                )
                yield Select(
                    self._provider_reasoning_options(default_provider),
                    value=self.settings.default_reasoning_for(default_provider),
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
                yield Button("Push", id="push-branch-button")
                yield Button("Push log", id="push-history-button")
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
            yield Static(self._directory_text(), id="directory")
            yield Static("Phase: Idle", id="phase")
            yield Static("Task branch: —    Worktree: —", id="task-context")
            with Vertical(id="output-panel"):
                with Horizontal(id="output-toolbar"):
                    yield Static("Agent output", id="output-view-label")
                    yield Button("Show errors", id="output-toggle-button")
                    yield Button(
                        "Hide viewer" if self._viewer_visible else "Show viewer",
                        id="viewer-toggle-button",
                    )
                # Keep diagnostics on the same selectable Log surface
                # as the transcript so mouse selection, y, and Ctrl+C
                # all use Textual's screen-selection clipboard path.
                yield Log(id="task-error", auto_scroll=False)
                # Log supports Textual click-drag selection; RichLog does not.
                yield TranscriptLog(id="output", auto_scroll=True)
            with Vertical(id="plan-review"):
                # Agent plan text is literal; brackets and scientific
                # notation must not be parsed as Textual/Rich markup.
                yield Static("", id="plan-display", markup=False)
                with Vertical(id="plan-questions"):
                    yield Static("", id="plan-questions-empty", markup=False)
                with Horizontal(id="plan-actions"):
                    yield Button("Submit Answers", id="answer-plan-button", disabled=True)
                    yield Button("Implement", id="implement-button", disabled=True, variant="primary")
            with Vertical(id="composer"):
                yield Static("New task", id="task-title", markup=False)
                with Horizontal(id="composer-tools"):
                    yield Select(
                        [],
                        prompt="Prompt history…",
                        allow_blank=True,
                        id="prompt-history-select",
                    )
                    yield Static(MODE_LABELS[VimModeEnum.INSERT], id="vim-mode")
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
                with Horizontal(id="actions"):
                    yield Button("Send", id="send-button", variant="primary")
                    yield Button("Continue Plan", id="continue-plan-button", disabled=True)
                    yield Button("Start Coding", id="start-coding-button", disabled=True, variant="primary")
                    yield Button("Pause", id="pause-button", disabled=True)
                    yield Button("Resume", id="resume-button", disabled=True)
                    yield Button("Cancel", id="cancel-button", disabled=True, variant="error")
                    yield Button("Retry", id="retry-button", disabled=True)
                    yield Static("Idle", id="status")

    def _compose_orchestrate_view(self) -> ComposeResult:
        """Orchestrate Mode: role row, prompt, actions, board, planner log, summary."""
        orchestrate = self.orchestrate_settings
        with Horizontal(id="orchestrate-roles"):
            # Each role keeps its provider, model, and effort on one line even
            # when the compact layout stacks the roles vertically.
            for role, provider, model, reasoning in (
                ("planner", orchestrate.planner_provider, orchestrate.planner_model, orchestrate.planner_reasoning),
                ("worker", orchestrate.worker_provider, orchestrate.worker_model, orchestrate.worker_reasoning),
            ):
                with Horizontal(classes="orchestrate-role", id=f"{role}-role"):
                    yield Static(role.capitalize(), classes="orchestrate-role-label")
                    yield Select(
                        self._role_provider_options(provider),
                        value=provider,
                        allow_blank=False,
                        id=f"{role}-provider-select",
                        classes="orchestrate-role-provider",
                    )
                    model_options = self._role_model_options(provider, model)
                    yield Select(
                        model_options,
                        value=model,
                        allow_blank=False,
                        disabled=len(model_options) < 2,
                        id=f"{role}-model-select",
                        classes="orchestrate-role-model",
                    )
                    reasoning_options = self._role_reasoning_options(provider, reasoning)
                    yield Select(
                        reasoning_options,
                        value=reasoning_options[0][1] if not self.settings.reasoning_for(provider) else reasoning,
                        allow_blank=False,
                        disabled=not self.settings.reasoning_for(provider),
                        id=f"{role}-reasoning-select",
                        classes="orchestrate-role-reasoning",
                    )
            with Horizontal(classes="orchestrate-role orchestrate-role-workers", id="workers-role"):
                yield Static("Workers", classes="orchestrate-role-label")
                yield Input(
                    value=str(orchestrate.default_max_workers),
                    type="integer",
                    id="max-workers-input",
                    tooltip=f"1 to {orchestrate.max_workers_limit} workers",
                )
        yield DaedalusVimTextArea(
            id="orchestrate-prompt",
            placeholder="Describe the whole change; the planner splits it into worker cards...",
        )
        with Horizontal(id="orchestrate-actions"):
            yield Button("Start", id="orchestrate-start-button", variant="primary")
            yield Button("Stop", id="orchestrate-stop-button", variant="error", disabled=True)
            yield Select([], prompt="Session…", allow_blank=True, id="orchestrate-session-select")
            yield Static("Idle", id="orchestrate-status", markup=False)
        yield DataTable(id="orchestrate-board", cursor_type="row")
        yield TranscriptLog(id="planner-log", auto_scroll=True)
        yield Static("", id="orchestrate-summary", markup=False)

    def _role_provider_options(self, default_provider: str) -> list[tuple[str, str]]:
        """Provider choices for one Orchestrate role: every provider the settings bar offers."""
        options = [(option.label, option.value) for option in self.settings.providers]
        if default_provider and default_provider not in {value for _, value in options}:
            options.insert(0, (default_provider, default_provider))
        return options

    def _role_model_options(self, provider: str, default_model: str) -> list[tuple[str, str]]:
        """Model choices for one Orchestrate role, always including its default."""
        options = [(option.label, option.value) for option in self.settings.models_for(provider)]
        if default_model and default_model not in {value for _, value in options}:
            options.insert(0, (default_model, default_model))
        return options

    def _role_reasoning_options(self, provider: str, default_reasoning: str) -> list[tuple[str, str]]:
        """Effort choices for one Orchestrate role, or one inert entry for providers without any."""
        options = [(option.label, option.value) for option in self.settings.reasoning_for(provider)]
        if not options:
            return [("Not applicable", "")]
        if default_reasoning and default_reasoning not in {value for _, value in options}:
            options.insert(0, (default_reasoning, default_reasoning))
        return options

    def _role_defaults(self, role: str, provider: str) -> tuple[str, str]:
        """Model and reasoning preselected when ``role`` switches to ``provider``.

        The parameter file's choice wins for its own provider; any other
        provider starts from the settings bar defaults for that provider.
        """
        orchestrate = self.orchestrate_settings
        configured_provider, configured_model, configured_reasoning = (
            orchestrate.planner_selection if role == "planner" else orchestrate.worker_selection
        )
        if provider == configured_provider:
            return configured_model, configured_reasoning
        return self.settings.default_model_for(provider), self.settings.default_reasoning_for(provider)

    def _apply_role_provider(self, role: str, provider: str) -> None:
        """Swap one Orchestrate role's model and effort choices to match its provider."""
        model_select = self.query_one(f"#{role}-model-select", Select)
        reasoning_select = self.query_one(f"#{role}-reasoning-select", Select)
        default_model, default_reasoning = self._role_defaults(role, provider)
        model_options = self._role_model_options(provider, default_model)
        reasoning_options = self._role_reasoning_options(provider, default_reasoning)
        has_reasoning = bool(self.settings.reasoning_for(provider))
        model_select.disabled = len(model_options) < 2
        reasoning_select.disabled = not has_reasoning
        self._set_select_options_if_changed(model_select, model_options)
        if model_select.value != default_model:
            model_select.value = default_model
        self._set_select_options_if_changed(reasoning_select, reasoning_options)
        reasoning_value = default_reasoning if has_reasoning else reasoning_options[0][1]
        if reasoning_select.value != reasoning_value:
            reasoning_select.value = reasoning_value

    def on_mount(self) -> None:
        if not self._logging_status.available:
            self._logging_status = configure_debug_logging(
                self.debug_log_path,
                self.prompting.error_log_max_bytes,
                self.prompting.error_log_backup_count,
            )
        self._fault_log_file = install_fault_handler(self.fault_log_path)
        self._install_exit_diagnostics()
        self._accept_task_events = True
        prompts_status, errors_status = self.storage.ensure_roots()
        storage_problems = [status.error for status in (prompts_status, errors_status) if status.error]
        if not self._logging_status.available and self._logging_status.error:
            storage_problems.append(f"diagnostics log unavailable: {self._logging_status.error}")
        self._storage_error = "; ".join(storage_problems) or None
        self.query_one("#output", TranscriptLog).styles.width = self.settings.output_width
        self._apply_provider_selection(str(self.query_one("#provider-select", Select).value))
        self._refresh_target_branch_select()
        self._refresh_topic_select()
        self._refresh_backend_button()
        self._refresh_push_button()
        self._refresh_task_list()
        self._refresh_compact_setting_value()
        self._refresh_history_toggle_button()
        self._apply_responsive_layout()
        self._apply_viewer_visibility()
        self._refresh_output_viewer(None)
        # Restore any draft still on disk. A deliberate close clears the
        # composer's own draft (``[drafts] clear_on_exit``), so what is left to
        # restore here is a crash's autosave or a deliberately stashed prompt.
        self._load_composer_for_selection(restore_status=False)
        if self._storage_error:
            self._set_error(f"Local prompt/error storage is unavailable: {self._storage_error}")
            self._set_status("Storage unavailable")
        self.query_one("#output", TranscriptLog).set_user_color(self.screen.rich_style.color)
        self._load_orchestrate_draft()
        self._refresh_orchestrate_view()
        self._start_usage_polling()

    # ------------------------------------------------------------------
    # Usage bar
    # ------------------------------------------------------------------

    def _start_usage_polling(self) -> None:
        """Read provider usage now and then on the configured cadence."""
        if not self.settings.usage.enabled:
            self.query_one("#usage-bar", Static).update("Usage: disabled")
            return
        self._poll_usage()
        self._usage_timer = self.set_interval(
            max(1, self.settings.usage.interval_seconds), self._poll_usage
        )

    def _poll_usage(self) -> None:
        """Run the usage readers off the UI thread and update the bar."""
        monitor = self.usage_monitor

        def work() -> None:
            try:
                readings = monitor.poll()
            except Exception as error:  # pragma: no cover - monitor guards itself
                log_exception("Usage polling failed", error)
                return
            try:
                self.call_from_thread(self._show_usage, readings)
            except RuntimeError:
                return

        self.run_worker(work, thread=True, exclusive=True, group="usage", exit_on_error=False)

    def _show_usage(self, readings: tuple[ProviderUsage, ...]) -> None:
        self._usage_readings = readings
        nodes = self.query("#usage-bar")
        if not nodes:
            return
        bar = nodes.first()
        bar.update(format_usage_bar(readings, bar_width=self.settings.usage.bar_width))
        bar.tooltip = "\n\n".join(
            f"{reading.label}: {reading.detail or reading.summary}" + (
                "" if reading.ok else " (unavailable)"
            )
            for reading in readings
        ) or None

    def on_key(self, event: events.Key) -> None:
        """Add Vim-like navigation without changing TextArea insert behavior."""
        if event.key == "tab" and len(self.screen_stack) == 1 and not self._orchestrate_view_shown:
            self.action_toggle_plan_mode()
            event.stop()
            return

        if isinstance(self.focused, TextArea) and not self._focus_in_viewer():
            self._vim_pending_g = False
            self._vim_pending_d = False
            return

        key = event.key
        task_list_focused = isinstance(self.focused, DataTable) and self.focused.id == "task-list"
        if self._vim_pending_d:
            self._vim_pending_d = False
            if key == "d" and task_list_focused:
                self._delete_task_at_cursor()
                event.stop()
                return

        if self._vim_pending_g:
            self._vim_pending_g = False
            if key == "g":
                self._scroll_output("home")
            else:
                self._handle_vim_key(key)
            event.stop()
            return

        if key == "d" and task_list_focused:
            self._vim_pending_d = True
            self._set_status("d-")
            event.stop()
            return

        if key == "g":
            self._vim_pending_g = True
            self._set_status("g-")
            event.stop()
            return
        if key in {"j", "k", "G", "ctrl+d", "ctrl+u", "y", "p", "i"}:
            self._handle_vim_key(key)
            event.stop()

    def on_unmount(self) -> None:
        self._textual_unmounted = True
        self._close_composer_draft()
        self._flush_orchestrate_draft()
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
        wrapped: bool = False,
    ) -> None:
        """Toggle responsive classes and dimensions after a viewport change.

        ``compact_width`` is a lower safety guard, not the primary wide-layout
        breakpoint. Above it, the actual laid-out controls are measured after
        Textual has processed the style change. A clipped toolbar first wraps
        onto two rows (``wrapped``) while the workspace stays side by side;
        only when the wrapped toolbars are still clipped does the whole layout
        switch to compact mode and the compact settings picker.
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
        wrapped = wrapped and not compact
        self._compact_mode = compact
        self._wrapped_toolbars = wrapped
        self._short_height_mode = short
        screen = self.query_one("#screen", Vertical)
        screen.set_class(compact, "compact-width")
        screen.set_class(wrapped, "wrapped-toolbars")
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
        output.styles.width = "1fr" if compact else self.settings.output_width
        self._refresh_compact_setting_value()
        self._apply_viewer_visibility(width)
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
        self.screen.call_after_refresh(self._apply_measured_responsive_layout)

    def _apply_measured_responsive_layout(self) -> None:
        """Wrap the toolbars, then compact, when wide controls are clipped."""
        self._responsive_measure_pending = False
        if not self.query("#screen"):
            return
        width = self.size.width
        height = self.size.height
        compact = width < self.settings.layout.compact_width
        if not compact and self._wide_controls_overflow():
            if not self._wrapped_toolbars:
                # Try the two-row toolbars first; the queued re-measurement
                # falls back to compact mode if they are clipped as well.
                self._apply_responsive_layout(width, height, wrapped=True)
                return
            compact = True
        if compact != self._compact_mode:
            self._apply_responsive_layout(width, height, compact=compact)

    def _wide_controls_overflow(self) -> bool:
        """Return whether wide-layout controls are clipped or too narrow."""
        settings_selector = "#orchestrate-roles" if self._orchestrate_view_shown else "#settings"
        for selector in ("#task-bar", settings_selector):
            containers = self.query(selector)
            if not containers:
                continue
            container = containers.first()
            available = container.content_region
            if available.width <= 0:
                return True
            # The orchestrate role row nests each role's selects in a group,
            # so measure those selects too, not only the direct children.
            nested = (
                [widget for widget in container.query(Select) if widget.parent is not container]
                if selector == "#orchestrate-roles"
                else []
            )
            for child in (*container.children, *nested):
                if not child.display:
                    continue
                region = child.region
                if region.width <= 0 or region.height <= 0:
                    return True
                # A button narrower than its label plus line padding wraps
                # the label onto a second line.
                if isinstance(child, Button) and region.width < cell_len(str(child.label)) + 2:
                    return True
                if (
                    selector == settings_selector
                    and isinstance(child, Select)
                    and region.width < self.settings.layout.wide_control_min_width
                ):
                    return True
                # Controls pushed past the bar, or grown taller than it
                # because their text wrapped, are clipped by the bar.
                if (
                    region.x < available.x
                    or region.x + region.width > available.x + available.width
                    or region.y < available.y
                    or region.y + region.height > available.y + available.height
                ):
                    return True
        return False

    def exit(self, *args, **kwargs) -> None:
        """Stop agents before an explicit Textual exit begins."""
        self._shutdown_coordinators("explicit Textual exit")
        super().exit(*args, **kwargs)

    def _handle_exception(self, error: Exception) -> None:
        """Persist Textual failures that would otherwise only flash on screen."""
        self._fatal_error = True
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
        try:
            self._flush_draft(force=True)
        except Exception as error:
            log_exception("Could not flush the composer draft during shutdown", error)
        try:
            self._flush_orchestrate_draft()
        except Exception as error:
            log_exception("Could not flush the orchestrate draft during shutdown", error)
        shutdown_complete = True
        # Sessions stop first so their loops do not dispatch into a closing
        # task coordinator; the task coordinator then stops the workers.
        for orchestrator in self._orchestrators.values():
            if hasattr(orchestrator, "set_event_callback"):
                orchestrator.set_event_callback(None)
            try:
                orchestrator.shutdown()
            except Exception as error:
                log_exception("Orchestrate coordinator shutdown failed", error)
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
        if len(self.screen_stack) != 1 or self._orchestrate_view_shown:
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

    def action_start_coding(self) -> None:
        self._start_coding()

    def action_cancel_task(self) -> None:
        self._interrupt_task()

    def action_interrupt_task(self) -> None:
        """Stop the selected task's run, keep its progress, restore its prompt."""
        if len(self.screen_stack) != 1:
            # Modal dialogs keep their own cancel/close behavior.
            return
        if self._orchestrate_view_shown:
            # In Orchestrate Mode the interrupt stops the whole session.
            self._stop_orchestration()
            return
        self._interrupt_task()

    def action_toggle_orchestrate_mode(self) -> None:
        if len(self.screen_stack) != 1:
            return
        self._set_orchestrate_view(not self._orchestrate_view_shown)

    def action_toggle_output_viewer(self) -> None:
        self._set_viewer_visible(not self._viewer_visible)

    def action_toggle_task_history(self) -> None:
        self._toggle_task_history()

    def action_retry_task(self) -> None:
        self._retry_task()

    def action_show_shortcuts(self) -> None:
        self.push_screen(KeyboardShortcutsScreen())

    def action_show_statistics(self) -> None:
        # The screen reads the operator's whole Claude Code spend through the
        # usage monitor, so Ctrl+T shows more than the tasks Daedalus launched.
        # Turning usage readings off also turns that reading off, because it is
        # the same local Claude data the usage bar would have polled.
        reader = (
            self.usage_monitor.read_claude_account_usage
            if self.settings.usage.enabled
            else None
        )
        self.push_screen(
            CodingStatisticsScreen(
                self._usage_entries(),
                self.statistics_settings,
                account_usage_reader=reader,
            )
        )

    def action_show_push_history(self) -> None:
        """Show the launch-root record of successful branch pushes."""
        try:
            records = self.memory.get_pushed_commits()
        except (OSError, ValueError) as error:
            self._set_error(f"Could not read pushed commit history: {error}")
            self._set_status("Push history unavailable")
            return
        self.push_screen(PushedCommitsScreen(records, self.memory.path))

    def action_show_new_project(self) -> None:
        self.push_screen(
            ProjectInitializerScreen(self.launch_root, self._default_backend()),
            self._on_project_initialized,
        )

    def _default_backend(self) -> str:
        """Return the backend preselected for new projects."""
        try:
            return str(load_initializer_settings().get("default_backend", "none"))
        except (OSError, ValueError, KeyError):
            return "none"

    def action_show_create_topic(self) -> None:
        self.push_screen(CreateTopicScreen(self._active_project_path), self._on_topic_created)

    def action_register_backend(self) -> None:
        """Choose and scaffold the backend files for the active project."""
        self.push_screen(
            BackendRegistrationScreen(
                self._active_project_path,
                self._registered_backend(),
                self._default_backend(),
            ),
            self._on_backend_registered,
        )

    def _on_backend_registered(self, message: str | None) -> None:
        if message:
            self._set_error("")
            self._set_status(message)
        self._refresh_backend_button()

    def _registered_backend(self) -> str | None:
        """Return the backend the active project is already registered for."""
        project_path = self._active_project_path
        try:
            if is_firebase_registered(project_path):
                return "firebase"
            if is_personal_supabase_registered(project_path):
                return "supabase"
        except (OSError, ValueError):
            return None
        return None

    def action_show_sign_in(self) -> None:
        """Show sign-in status for the provider selected in the settings bar."""
        if not self.query("#provider-select"):
            return
        provider = str(self.query_one("#provider-select", Select).value)
        self.push_screen(ProviderSignInScreen(provider, self.settings))

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
        elif event.button.id == "new-task-button":
            self._start_new_task()
        elif event.button.id == "orchestrate-mode-button":
            self._set_orchestrate_view(not self._orchestrate_view_shown)
        elif event.button.id == "orchestrate-start-button":
            self._start_orchestration()
        elif event.button.id == "orchestrate-stop-button":
            self._stop_orchestration()
        elif event.button.id == "new-project-button":
            self.action_show_new_project()
        elif event.button.id == "create-topic-button":
            self.action_show_create_topic()
        elif event.button.id == "register-backend-button":
            self.action_register_backend()
        elif event.button.id == "sign-in-button":
            self.action_show_sign_in()
        elif event.button.id == "view-topic-button":
            self.action_view_topic()
        elif event.button.id == "push-branch-button":
            self._push_selected_branch()
        elif event.button.id == "push-history-button":
            self.action_show_push_history()
        elif event.button.id == "continue-plan-button":
            self._continue_plan()
        elif event.button.id == "start-coding-button":
            self._start_coding()
        elif event.button.id == "pause-button":
            self._pause_task()
        elif event.button.id == "resume-button":
            self._resume_task()
        elif event.button.id == "cancel-button":
            self._interrupt_task()
        elif event.button.id == "retry-button":
            self._retry_task()
        elif event.button.id == "output-toggle-button":
            self._set_output_view(not self._showing_error_output, focus=True)
        elif event.button.id == "viewer-toggle-button":
            self._set_viewer_visible(not self._viewer_visible)
        elif event.button.id == "history-toggle-button":
            self._toggle_task_history()
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
        if event.select.id == "prompt-history-select":
            if not self._suppress_history_select and event.value not in _SELECT_EMPTY:
                self._load_prompt_history_entry(str(event.value))
            return
        if event.select.id == "orchestrate-session-select":
            if event.value not in _SELECT_EMPTY and str(event.value) != self._selected_session_id:
                self._selected_session_id = str(event.value)
                self._refresh_orchestrate_view()
            return
        if event.select.id in {"planner-provider-select", "worker-provider-select"}:
            if event.value not in _SELECT_EMPTY:
                role = event.select.id.split("-", 1)[0]
                self._apply_role_provider(role, str(event.value))
            return
        if event.select.id in {
            "planner-model-select",
            "planner-reasoning-select",
            "worker-model-select",
            "worker-reasoning-select",
        }:
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
                value_select._pending_user_value = None
                self._apply_compact_setting(str(event.value))
            return
        if event.select.id == "project-select":
            if str(event.value) == OPEN_DIRECTORY_VALUE:
                self._prompt_for_project_directory()
            elif event.value not in (Select.BLANK, ""):
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
        model_options = self._provider_model_options(provider)
        reasoning_options = self._provider_reasoning_options(provider)
        model_value = self.settings.default_model_for(provider)
        reasoning_value = self.settings.default_reasoning_for(provider)
        # A provider with a single fixed model or no effort scale keeps its
        # selector visible but inert rather than removing the control.
        model_select.disabled = len(model_options) < 2
        reasoning_select.disabled = not self.settings.reasoning_for(provider)
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

    def _provider_model_options(self, provider: str) -> list[tuple[str, str]]:
        """Return the model choices for a provider, for both settings layouts."""
        return [(option.label, option.value) for option in self.settings.models_for(provider)]

    def _provider_reasoning_options(self, provider: str) -> list[tuple[str, str]]:
        """Return effort choices, or a single inert entry for providers without one."""
        options = self.settings.reasoning_for(provider)
        if not options:
            return [("Not applicable", "")]
        return [(option.label, option.value) for option in options]

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
            return self._provider_model_options(str(self.query_one("#provider-select", Select).value))
        if category == "reasoning":
            return self._provider_reasoning_options(
                str(self.query_one("#provider-select", Select).value)
            )
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
        pending = getattr(value_select, "_pending_user_value", None)
        if pending is not None and pending in values and pending != effective:
            # Leave the user's not-yet-applied choice in place.
            return
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
            return
        if event.text_area.id == "prompt-input" and not self._suppress_draft_events:
            self._draft_revision += 1
            self._draft_dirty = True
            self._schedule_draft_save()
        if event.text_area.id == "orchestrate-prompt" and not self._suppress_orchestrate_draft_events:
            self._orchestrate_draft_dirty = True
            self._schedule_orchestrate_draft_save()

    def on_vim_text_area_mode_changed(self, event) -> None:
        """Keep the compact Insert/Normal/Visual indicator current."""
        nodes = self.query("#vim-mode")
        if nodes:
            nodes.first().update(MODE_LABELS.get(event.mode, str(event.mode)))

    def on_daedalus_vim_text_area_clipboard_status(self, event: DaedalusVimTextArea.ClipboardStatus) -> None:
        if not event.succeeded:
            self._set_status(event.message)

    # ------------------------------------------------------------------
    # Draft persistence
    # ------------------------------------------------------------------

    def _schedule_draft_save(self) -> None:
        if self._draft_timer is not None:
            return
        delay = self.prompting.draft_autosave_delay_ms / 1000
        if delay <= 0:
            self._flush_draft()
            return
        self._draft_timer = self.set_timer(delay, self._draft_timer_fired)

    def _draft_timer_fired(self) -> None:
        self._draft_timer = None
        self._flush_draft()

    def _flush_draft(self, force: bool = False) -> bool:
        """Write the composer draft to disk; returns False when it could not be saved."""
        if self._composer_draft_closed:
            # The window has already closed the draft; its state on disk is
            # final and a late shutdown flush must not resurrect it.
            return True
        if self._draft_timer is not None:
            self._draft_timer.stop()
            self._draft_timer = None
        if not self._draft_dirty and not force:
            return True
        nodes = self.query("#prompt-input")
        if not nodes:
            return True
        prompt = nodes.first()
        text = prompt.text
        self._draft_dirty = False
        project = self._composer_project
        task_id = self._composer_task_id
        try:
            if not text:
                self.prompt_store.delete_draft(project, task_id)
            else:
                self.prompt_store.save_draft(
                    project,
                    task_id,
                    text,
                    cursor=tuple(prompt.cursor_location),
                    revision=self._draft_revision,
                    revises_turn_id=self._composer_revises_turn_id,
                )
        except (PromptStoreError, OSError) as error:
            # Keep the editor usable; report the exact path that failed and
            # never claim the draft is saved.
            self._draft_dirty = True
            LOGGER.warning("Draft save failed: %s", error)
            self._set_status(f"Draft not saved: {error}")
            return False
        return True

    def _close_composer_draft(self) -> None:
        """Save or clear the composer draft as the Daedalus window closes.

        With ``[drafts] clear_on_exit`` set, closing the window deliberately
        clears the prompt the composer was holding, so the next launch starts
        on an empty composer instead of last session's unsent text. Autosaves
        still protect the draft for as long as the app runs, and a crash never
        reaches this hook, so an unexpected exit still leaves the draft on disk
        to be recovered.
        """
        if not self.prompting.clear_drafts_on_exit or self._fatal_error:
            self._flush_draft(force=True)
        else:
            self._discard_draft()
        self._composer_draft_closed = True

    def _discard_draft(self) -> None:
        """Delete the composer's saved draft without touching stashed drafts.

        Only the draft the composer would reload on the next launch is removed.
        Drafts stashed by an interruption and prompts recovered from an
        archive stay reachable from Prompt history, because those were set
        aside deliberately rather than left in the prompt box.
        """
        if self._draft_timer is not None:
            self._draft_timer.stop()
            self._draft_timer = None
        self._draft_dirty = False
        try:
            self.prompt_store.delete_draft(self._composer_project, self._composer_task_id)
        except (PromptStoreError, OSError) as error:
            LOGGER.warning("Draft discard failed: %s", error)

    def _load_composer(
        self,
        task_id: str | None,
        text: str,
        *,
        revises_turn_id: str | None = None,
        cursor: tuple[int, int] | None = None,
        revision: int = 0,
        focus: bool = True,
    ) -> None:
        """Deliberately replace the composer contents (never from a render path)."""
        prompt = self.query_one("#prompt-input", DaedalusVimTextArea)
        self._composer_task_id = task_id
        self._composer_project = self._active_project_path
        self._composer_revises_turn_id = revises_turn_id
        self._draft_revision = revision
        self._draft_dirty = False
        self._suppress_draft_events = True
        try:
            prompt.read_only = False
            prompt.load_text(text)
        finally:
            self._suppress_draft_events = False
        if cursor is not None:
            row = min(max(0, cursor[0]), max(0, prompt.document.line_count - 1))
            column = min(max(0, cursor[1]), len(str(prompt.get_line(row))))
            prompt.cursor_location = (row, column)
        else:
            prompt.move_cursor_to_end()
        self.query_one("#output", TranscriptLog).invalidate_render_cache()
        prompt.enter_insert_mode()
        if focus:
            prompt.focus()
        self._refresh_send_button()

    def _load_composer_for_selection(self, *, restore_status: bool = True) -> None:
        """Load the saved draft for the selected task (or the new-task draft)."""
        task_id = self._selected_task_id
        record = self.coordinator.get(task_id or "") if task_id else None
        if record is None:
            task_id = None
        try:
            draft = self.prompt_store.load_draft(self._active_project_path, task_id)
        except OSError:
            draft = None
        if draft is not None and draft.text:
            self._load_composer(
                task_id,
                draft.text,
                revises_turn_id=draft.revises_turn_id,
                cursor=draft.cursor,
                revision=draft.revision,
            )
            if restore_status and draft.kind == "recovered":
                self._set_status("Recovered an unsent prompt")
        else:
            self._load_composer(task_id, "")
        self._refresh_task_title(record)
        self._refresh_prompt_history(record)

    def _refresh_task_title(self, record: TaskRecord | None) -> None:
        nodes = self.query("#task-title")
        if not nodes:
            return
        if record is None:
            nodes.first().update("New task")
        else:
            nodes.first().update(f"Task: {record.display_title}")

    def _refresh_send_button(self) -> None:
        nodes = self.query("#send-button")
        if not nodes:
            return
        record = self.coordinator.get(self._selected_task_id or "") if self._selected_task_id else None
        # Composing is always allowed; Send waits until the task's run has
        # stopped or finished so one task never has two executing runs.
        nodes.first().disabled = record is not None and record.status in ACTIVE_RUN_STATUSES

    @staticmethod
    def _record_has_active_run(record: TaskRecord) -> bool:
        """Treat inconsistent task and run metadata as active until it settles."""
        if record.status in ACTIVE_RUN_STATUSES:
            return True
        runs = getattr(record, "runs", None) or ()
        return bool(runs) and getattr(runs[-1], "status", None) in ACTIVE_RUN_STATUSES

    def _refresh_prompt_history(self, record: TaskRecord | None) -> None:
        nodes = self.query("#prompt-history-select")
        if not nodes:
            return
        select = nodes.first()
        options: list[tuple[Text, str]] = []
        if record is not None:
            for turn in getattr(record, "turns", None) or ():
                if not getattr(turn, "is_user", True):
                    continue
                preview = " ".join(turn.text.split())
                if len(preview) > 48:
                    preview = f"{preview[:45]}…"
                options.append((Text(f"Turn {turn.sequence}: {preview}"), f"turn:{turn.turn_id}"))
            if not options and record.prompt:
                preview = " ".join(record.prompt.split())[:45]
                options.append((Text(f"Turn 1: {preview}"), "turn:legacy"))
            try:
                for draft in self.prompt_store.list_drafts(self._active_project_path, record.task_id):
                    if draft.draft_id == "draft":
                        continue
                    preview = " ".join(draft.text.split())
                    if len(preview) > 40:
                        preview = f"{preview[:37]}…"
                    label = "Saved follow-up" if draft.kind == "stashed" else "Saved draft"
                    options.append((Text(f"{label}: {preview}"), f"draft:{draft.draft_id}"))
            except OSError:
                pass
        self._suppress_history_select = True
        try:
            select.set_options(options)
            select.disabled = not options
        finally:
            self._suppress_history_select = False

    def _load_prompt_history_entry(self, value: str) -> None:
        """Load an earlier prompt or saved follow-up into the composer, leaving its file untouched."""
        record = self.coordinator.get(self._selected_task_id or "") if self._selected_task_id else None
        if record is None:
            return
        self._flush_draft(force=True)
        text: str | None = None
        revises: str | None = None
        if value.startswith("turn:"):
            turn_id = value.removeprefix("turn:")
            if turn_id == "legacy":
                text = record.prompt
            else:
                turn = record.turn_by_id(turn_id) if hasattr(record, "turn_by_id") else None
                if turn is not None:
                    text = turn.text
                    revises = turn.turn_id
        elif value.startswith("draft:"):
            draft_id = value.removeprefix("draft:")
            try:
                draft = self.prompt_store.load_draft(self._active_project_path, record.task_id, draft_id)
            except OSError:
                draft = None
            if draft is not None:
                text = draft.text
                revises = draft.revises_turn_id
        select = self.query_one("#prompt-history-select", Select)
        self._suppress_history_select = True
        try:
            # Select.NULL is the blank sentinel; the legacy Select.BLANK is not
            # a legal value in Textual 8.
            select.clear()
        except InvalidSelectValueError:
            pass
        finally:
            self._suppress_history_select = False
        if text is None:
            self._set_status("That prompt is no longer available")
            return
        self._load_composer(record.task_id, text, revises_turn_id=revises)
        self._draft_dirty = True
        self._schedule_draft_save()
        self._set_status("Loaded earlier prompt into the composer")

    def _submit_prompt(self) -> None:
        prompt_widget = self.query_one("#prompt-input", DaedalusVimTextArea)
        if self._submission_in_progress:
            return
        raw_text = prompt_widget.text
        if not raw_text.strip():
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
        # Flush the draft first so nothing is lost if submission fails.
        self._flush_draft(force=True)
        followup_record = (
            self.coordinator.get(self._composer_task_id) if self._composer_task_id else None
        )
        self._submission_in_progress = True
        try:
            if (
                followup_record is not None
                and self._selected_task_id == followup_record.task_id
                and not self._record_has_active_run(followup_record)
            ):
                record = self._submit_followup(followup_record, raw_text, provider, model, reasoning, mode, topic)
            else:
                record = self.coordinator.submit(raw_text, provider, model, reasoning, mode, topic=topic)
        except (RuntimeError, ValueError, OSError) as error:
            self._set_error(str(error))
            self._set_status("Error")
            return
        finally:
            self._submission_in_progress = False
        if record is None:
            self._set_error("The selected task is no longer available.")
            self._set_status("Error")
            return
        # Durable submission succeeded: the sent text is now an immutable turn
        # and the composer becomes a blank follow-up draft for that task.
        try:
            self.prompt_store.delete_draft(self._composer_project, self._composer_task_id)
        except OSError:
            pass
        self._load_composer(record.task_id, "")
        self._focus_submitted_task(record, "prompt submission")

    def _submit_followup(
        self,
        record: TaskRecord,
        text: str,
        provider: str,
        model: str,
        reasoning: str,
        mode: str,
        topic: str | None,
    ) -> TaskRecord | None:
        """Send another turn to the selected task, recording explicit setting changes."""
        submit_followup = getattr(self.coordinator, "submit_followup", None)
        if submit_followup is None:
            raise RuntimeError("This task coordinator does not support follow-up prompts.")
        if record.status in ACTIVE_RUN_STATUSES:
            raise RuntimeError("Wait for the current run to stop before sending another prompt.")
        changes: dict[str, object] = {}
        snapshot = self._selection_settings
        current = (provider, model, reasoning, mode)
        if snapshot is not None and current != snapshot:
            # Only settings the user changed after selecting the task are
            # recorded on the new turn; the rest stay as the task had them.
            for name, before, after in zip(("provider", "model", "reasoning", "mode"), snapshot, current):
                if before != after:
                    changes[name] = after
        if topic != record.topic:
            changes["topic"] = topic or ""
        return submit_followup(
            record.task_id,
            text,
            revises_turn_id=self._composer_revises_turn_id,
            **changes,
        )

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
        if event.data_table.id == "orchestrate-board":
            self._focus_board_row(row_key)
            return
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
                if kind == "pushed" and message:
                    # A later lifecycle event can replace the pending task
                    # event before the UI thread flushes it. Keep push notices
                    # separately so a successful push is never swallowed.
                    self._pending_push_notices.append((record, message))
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
                    self._pending_push_notices = [
                        item for item in self._pending_push_notices if item[0] is not record
                    ]
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
            push_notices = tuple(self._pending_push_notices)
            self._pending_task_events.clear()
            self._pending_push_notices.clear()
            self._task_event_flush_scheduled = False
        for record, phase, message, kind in events_to_apply:
            self._apply_task_event(record, phase, message, kind)
        for record, message in push_notices:
            self._apply_push_confirmation(record, message)

    def _apply_task_event(self, record: TaskRecord, phase: str, message: str, kind: str) -> None:
        try:
            if phase == ORCHESTRATE_PHASE:
                self._apply_session_event(record, message, kind)
                return
            project_path = self._project_for_record(record)
            if project_path is None:
                return
            if getattr(record, "is_worker", False) and kind != "message":
                # A worker settling or advancing changes its card on the board.
                self._refresh_orchestrate_view()
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
            if is_selected:
                self._render_selected_task_safely(f"task event phase={phase}")
            if kind == "pushed" and message:
                self._apply_push_confirmation(record, message)
        except Exception as error:
            log_exception(f"Could not render task event task={record.task_id} phase={phase}", error)
            if not self._accept_task_events:
                return
            try:
                self._set_error(f"Task update could not be rendered: {error}")
                self._set_status("Error")
            except Exception as display_error:
                log_exception("Could not show task rendering error", display_error)

    def _apply_push_confirmation(self, record: TaskRecord, message: str) -> None:
        """Keep an orchestration push visible after task events repaint the UI."""
        project_path = self._project_for_record(record)
        if project_path is None:
            project_path = self._project_for_session_record(record)
        if project_path is None:
            return
        pushed = parse_push_notice(message)
        if pushed is not None:
            self._record_pushed_commit(project_path, *pushed)
            if project_path == self._active_project_path:
                self._push_confirmation_branch = pushed[0]
                self._refresh_push_button()
        self._set_error("")
        self._set_status(message)

    @staticmethod
    def _should_promote_task_update(record: TaskRecord, phase: str) -> bool:
        """Promote only events that need the user's attention in the inbox."""
        normalized_phase = phase.lower()
        if normalized_phase in {"completed", "failed"}:
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
            if hasattr(coordinator, "memory"):
                # Keep injected coordinators on the same launch-root memory as
                # coordinators created by the app, including push history.
                coordinator.memory = self.memory
        else:
            coordinator = TaskCoordinator(
                project_path,
                self.runner,
                settings,
                self._on_task_event,
                memory_path=self.launch_root / DEFAULT_MEMORY_FILE,
                prompt_store=self.prompt_store,
                storage=self.storage,
                title_length=self.prompting.task_title_length,
                context_budget_chars=self.prompting.conversation_context_budget_chars,
                run_log_max_bytes=self.prompting.run_log_max_bytes,
            )
        if hasattr(coordinator, "set_event_callback"):
            coordinator.set_event_callback(self._on_task_event)
        self._coordinators[project_path] = coordinator
        # The Orchestrate Mode dispatcher lives beside the task coordinator so
        # its restored sessions are visible before the operator starts one.
        self._orchestrator_for(project_path)
        return coordinator

    def _orchestrator_for(self, project_path: Path) -> OrchestrateCoordinator | None:
        """Return the project's Orchestrate Mode dispatcher, creating it once."""
        project_path = project_path.resolve()
        if project_path in self._orchestrators:
            return self._orchestrators[project_path]
        task_coordinator = self._coordinator_for(project_path)
        if self._external_orchestrator is not None:
            orchestrator = self._external_orchestrator
            self._external_orchestrator = None
        else:
            try:
                orchestrator = OrchestrateCoordinator(
                    task_coordinator,
                    self.runner,
                    task_coordinator.settings,
                    self.orchestrate_settings,
                    self.storage,
                    self.memory,
                    self._on_task_event,
                )
            except Exception as error:
                log_exception(f"Could not create the Orchestrate coordinator for {project_path}", error)
                return None
        if hasattr(orchestrator, "set_event_callback"):
            orchestrator.set_event_callback(self._on_task_event)
        self._orchestrators[project_path] = orchestrator
        return orchestrator

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
        self._push_confirmation_branch = None
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
        # teardown, before/after #push-branch-button is in the DOM.
        if not self.query("#push-branch-button"):
            return
        button = self.query_one("#push-branch-button", Button)
        if self._push_in_flight:
            button.disabled = True
            return
        branch = self._selected_operating_branch()
        button.label = "Pushed" if branch and branch == self._push_confirmation_branch else "Push"
        button.disabled = not branch or not remote_exists(self._active_project_path)

    def _push_selected_branch(self) -> None:
        """Push the Branch Select value for the active project to origin."""
        if self._push_in_flight:
            return
        branch = self._selected_operating_branch()
        if not branch:
            self._set_error("Select a branch before pushing.")
            self._set_status("Error")
            return
        project_path = self._active_project_path
        self._push_confirmation_branch = None
        if not remote_exists(project_path):
            self._set_error("Remote 'origin' is not configured for this project.")
            self._set_status("Error")
            self._refresh_push_button()
            return

        self._push_in_flight = True
        self._refresh_push_button()
        self._set_error("")
        self._set_status(f"Pushing {branch}…")

        def work() -> None:
            try:
                commit = push_branch(project_path, branch)
            except GitWorktreeError as error:
                self.call_from_thread(self._on_push_finished, False, str(error), branch, "", project_path)
            except Exception as error:  # pragma: no cover - defensive UI boundary
                self.call_from_thread(self._on_push_finished, False, str(error), branch, "", project_path)
            else:
                self.call_from_thread(self._on_push_finished, True, "", branch, commit, project_path)

        self.run_worker(
            work,
            thread=True,
            exclusive=True,
            group="git-push",
            exit_on_error=False,
        )

    def _record_pushed_commit(
        self,
        project_path: Path,
        branch: str,
        remote: str,
        commit: str,
    ) -> Path | None:
        """Persist push history, falling back when a target root is read-only."""
        try:
            self.memory.record_pushed_commit(project_path, branch, remote, commit)
            return self.memory.path
        except (OSError, ValueError) as error:
            primary_error = error

        fallback_path = self.storage.data_root / DEFAULT_MEMORY_FILE
        if fallback_path.resolve() == self.memory.path.resolve():
            LOGGER.warning(
                "Could not persist pushed commit commit=%s error=%s",
                commit,
                primary_error,
            )
            return None
        fallback = TaskMemoryStore(fallback_path)
        try:
            fallback.record_pushed_commit(project_path, branch, remote, commit)
        except (OSError, ValueError) as fallback_error:
            LOGGER.warning(
                "Could not persist pushed commit commit=%s primary_error=%s fallback_error=%s",
                commit,
                primary_error,
                fallback_error,
            )
            return None
        self.memory = fallback
        for coordinator in self._coordinators.values():
            if hasattr(coordinator, "memory"):
                coordinator.memory = fallback
        return fallback.path

    def _on_push_finished(
        self,
        succeeded: bool,
        error: str,
        branch: str,
        commit: str = "",
        project_path: Path | None = None,
    ) -> None:
        self._push_in_flight = False
        if succeeded:
            self._push_confirmation_branch = branch
        self._refresh_push_button()
        if succeeded:
            self._set_error("")
            if isinstance(commit, str) and commit:
                recorded_path = self._record_pushed_commit(
                    project_path or self._active_project_path,
                    branch,
                    "origin",
                    commit,
                )
                if recorded_path is not None:
                    self._set_status(
                        f"Pushed {branch} to origin (commit {commit[:12]}); recorded in {recorded_path}"
                    )
                else:
                    self._set_status(
                        f"Pushed {branch} to origin (commit {commit[:12]}); push history unavailable"
                    )
            else:
                self._set_status(f"Pushed {branch} to origin")
            return
        self._set_error(error or "Push failed.")
        self._set_status("Push failed")

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

    def _refresh_backend_button(self) -> None:
        """Show which backend the active project already registered, if any."""
        if not self.query("#register-backend-button"):
            return
        button = self.query_one("#register-backend-button", Button)
        backend = self._registered_backend()
        button.disabled = backend is not None
        if backend == "firebase":
            try:
                project_id = load_firebase_status(self._active_project_path).project_id
            except (OSError, ValueError):
                project_id = None
            button.tooltip = f"Firebase project {project_id!r} already registered"
        elif backend == "supabase":
            try:
                schema = schema_from_project_root(self._active_project_path)
            except ValueError:
                schema = None
            button.tooltip = f"Supabase schema {schema!r} already registered"
        else:
            button.tooltip = "Scaffold Firebase or personal Supabase files for this project"

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

    def _opened_project_entries(self) -> list[DaedalusProject]:
        """Return by-path projects, forgetting directories that no longer exist."""

        entries: list[DaedalusProject] = []
        remaining: list[Path] = []
        for directory in self._opened_directories:
            try:
                entries.append(project_from_directory(directory, self.launch_root))
            except ValueError:
                # The directory was moved or deleted; stop offering it.
                try:
                    self.memory.remove_opened_project_directory(directory)
                except (OSError, ValueError):
                    pass
                continue
            remaining.append(directory)
        self._opened_directories = remaining
        return entries

    def _project_selector_options(self) -> list[tuple[str, str]]:
        """Return project choices followed by the open-by-path entry.

        The list stays limited to projects actually in use: a directory appears
        only once it has been opened, so the single trailing entry is the whole
        cost of reaching projects outside the launch root.
        """

        options = [
            (project.display_name, str(project.path))
            for project in self._selector_projects()
        ]
        options.append((OPEN_DIRECTORY_LABEL, OPEN_DIRECTORY_VALUE))
        return options

    def _prompt_for_project_directory(self) -> None:
        """Restore the displayed project, then ask which directory to open."""

        project_select = self.query_one("#project-select", Select)
        effective = self._project_select_value()
        if project_select.value != effective:
            # The sentinel is an action, not a project; a queued Changed event
            # for the restored value is a no-op in _switch_project.
            project_select.value = effective
        self.push_screen(
            OpenProjectDirectoryScreen(self.launch_root),
            self._on_project_directory_chosen,
        )

    def _on_project_directory_chosen(self, directory: str | None) -> None:
        if not directory:
            return
        self._open_project_directory(Path(directory))

    def _open_project_directory(self, directory: Path) -> None:
        """List a directory in the project selector and switch onto it."""

        try:
            project = project_from_directory(directory, self.launch_root)
        except ValueError as error:
            self._set_error(str(error))
            self._set_status("Error")
            return
        project_path = project.path
        if not is_direct_child_project(project_path, self.launch_root):
            # Direct children are rediscovered on every refresh and need no
            # remembered entry of their own.
            if project_path not in self._opened_directories:
                self._opened_directories.append(project_path)
            try:
                self.memory.add_opened_project_directory(project_path)
            except (OSError, ValueError):
                # The directory still opens this session without local memory.
                pass
        if project_path not in {known.path.resolve() for known in self.projects}:
            self.projects = (*self.projects, project)
        self._refresh_project_selector()
        if project_path == self._active_project_path:
            self._set_status(f"Opened {project.display_name}")
            return
        self._switch_project(project_path)
        # The switch changes which option is effective, so sync the selector.
        self._refresh_project_selector()

    def _switch_project(self, project_path: Path) -> None:
        project_path = project_path.expanduser().resolve()
        if project_path == self._active_project_path:
            return
        if project_path not in {
            project.path.resolve() for project in self._selector_projects()
        }:
            return
        # Keep an in-progress new-task draft when changing projects so a
        # mis-targeted prompt can be redirected instead of erased. A task
        # follow-up draft stays with its task (flushed to that task's file).
        self._flush_draft(force=True)
        draft: str | None = None
        try:
            prompt_widget = self.query_one("#prompt-input", TextArea)
            if self._composer_task_id is None:
                draft = prompt_widget.text
        except Exception:
            draft = None
        self._active_project_path = project_path
        self.directory = project_path
        self._push_confirmation_branch = None
        # Persist after the active focus changes so the marker mirrors the
        # project that is currently visible in the TUI.
        self._remember_project(project_path)
        self.coordinator = self._coordinator_for(project_path)
        self._selected_task_id = None
        self._new_task_mode = True
        self._updated_task_rows = {
            row_key for row_key in self._updated_task_rows if row_key in self._task_rows
        }
        self.query_one("#directory", Static).update(self._directory_text())
        self._refresh_target_branch_select()
        self._refresh_topic_select()
        self._refresh_backend_button()
        self._refresh_task_list()
        self._render_selected_task_safely("project switch")
        self._flush_orchestrate_draft()
        self._selected_session_id = None
        self._load_orchestrate_draft()
        self._refresh_orchestrate_view()
        if draft:
            self._load_composer(None, draft)
            self._draft_dirty = True
            self._schedule_draft_save()
            self._refresh_task_title(None)
            self._refresh_prompt_history(None)
        else:
            self._load_composer_for_selection(restore_status=False)
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
            for project in discover_projects(self.launch_root, self.settings.project_discovery)
            if is_direct_child_project(project.path, self.launch_root)
        ]
        if not discovered:
            discovered = [DaedalusProject(self.launch_root, self.launch_root)]
        discovered_paths = {project.path.resolve() for project in discovered}
        for opened in self._opened_project_entries():
            if opened.path not in discovered_paths:
                discovered.append(opened)
                discovered_paths.add(opened.path)
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
            else:
                self.query_one("#directory", Static).update(self._directory_text())
                self._refresh_backend_button()
            self.query_one("#project-select", Select).value = self._project_select_value()
        else:
            self._refresh_backend_button()

    def _refresh_project_selector(self) -> None:
        project_select = self.query_one("#project-select", Select)
        options = self._project_selector_options()
        self._set_select_options_if_changed(project_select, options, compare_labels=True)
        effective = self._project_select_value()
        if project_select.value != effective:
            project_select.value = effective

    def _selector_projects(self) -> tuple[DaedalusProject, ...]:
        """Return direct-child and opened-by-path projects, or the root fallback."""

        opened = set(self._opened_directories)
        listed = tuple(
            project
            for project in self.projects
            if is_direct_child_project(project.path, self.launch_root)
            or project.path.resolve() in opened
        )
        if listed:
            return listed
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

    def _directory_text(self) -> str:
        return f"Launch root: {self.launch_root}    Active project: {self.directory}"

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
            project_name = project_names.get(project_path, project_path.name)
            card_id = getattr(record, "card_id", None)
            if getattr(record, "is_worker", False) and card_id:
                # Worker tasks of an Orchestrate session carry their card id.
                project_name = f"⋯ {card_id}"
            project_name = self._fit_task_cell(project_name, project_width)
            summary = " ".join(self._record_title(record).split())
            summary = self._fit_task_cell(summary, task_width)
            marker = "!" if row_key in self._updated_task_rows else ""
            status = self._fit_task_cell(record.status, status_width)
            task_list.add_row(marker, project_name, summary, status, key=row_key)

        if self._selected_task_id:
            selected_key = self._task_row_key(self._active_project_path, self._selected_task_id)
            if selected_key in self._task_rows:
                task_list.move_cursor(row=list(self._task_rows).index(selected_key), column=0)

    def _should_show_task(self, project_path: Path, record: TaskRecord) -> bool:
        """Keep failures, active work, and all tasks submitted in this launch.

        The All tasks toggle also lists completed and interrupted history so
        any earlier conversation can be reopened after a restart.
        """
        if self._show_all_tasks:
            return True
        row_key = self._task_row_key(project_path, record.task_id)
        return (
            row_key in self._session_task_rows
            or record.status == "failed"
            or record.status in _ACTIVE_TASK_STATUSES
        )

    @staticmethod
    def _record_title(record: TaskRecord) -> str:
        title = getattr(record, "display_title", None)
        return title if isinstance(title, str) and title else record.prompt

    def _toggle_task_history(self) -> None:
        self._show_all_tasks = not self._show_all_tasks
        try:
            self.memory.set_ui_preference("show_all_tasks", self._show_all_tasks)
        except (OSError, ValueError):
            pass
        self._refresh_history_toggle_button()
        self._refresh_task_list()
        self._set_status("Showing all tasks" if self._show_all_tasks else "Showing recent tasks")

    def _refresh_history_toggle_button(self) -> None:
        nodes = self.query("#history-toggle-button")
        if nodes:
            nodes.first().label = "Recent tasks" if self._show_all_tasks else "All tasks"

    @staticmethod
    def _task_row_key(project_path: Path, task_id: str) -> str:
        return f"{project_path.resolve()}::{task_id}"

    def _delete_task_at_cursor(self) -> None:
        """Delete the task currently under the focused sidebar cursor."""
        task_list = self.query_one("#task-list", DataTable)
        cursor_row = task_list.cursor_row
        row_keys = tuple(self._task_rows)
        if cursor_row < 0 or cursor_row >= len(row_keys):
            self._set_status("No task selected in the sidebar")
            return

        row_key = row_keys[cursor_row]
        task_target = self._task_rows.get(row_key)
        if task_target is None:
            self._set_status("No task selected in the sidebar")
            return
        project_path, task_id = task_target
        coordinator = self._coordinators.get(project_path)
        if coordinator is None:
            self._set_status("Task coordinator unavailable")
            return
        record = coordinator.get(task_id)
        if record is None:
            self._refresh_task_list()
            self._set_status("Task is no longer available")
            return
        delete_task = getattr(coordinator, "delete_task", None)
        if not callable(delete_task):
            self._set_status("Task deletion unavailable")
            return

        selected = (
            project_path == self._active_project_path
            and task_id == self._selected_task_id
        )
        if selected and not self._flush_draft(force=True):
            self._set_status("Task not deleted: draft could not be saved")
            return
        try:
            deleted = bool(delete_task(task_id))
        except (RuntimeError, OSError, ValueError) as error:
            self._set_status(f"Task not deleted: {error}")
            return
        if not deleted:
            if record.status in ACTIVE_RUN_STATUSES:
                self._set_status("Stop the active task before deleting it")
            else:
                self._set_status("Task could not be deleted")
            return

        if selected:
            try:
                self.prompt_store.delete_draft(project_path, task_id)
            except (PromptStoreError, OSError):
                pass
            self._selected_task_id = None
            self._new_task_mode = True
            self._selection_settings = None
            self._load_composer_for_selection(restore_status=False)
        self._session_task_rows.discard(row_key)
        self._updated_task_rows.discard(row_key)
        self._refresh_task_list()
        if self._task_rows:
            # Rebuilds clear Textual's cursor. Keep the same visual position,
            # clamping only when the deleted row was the last one.
            task_list.move_cursor(row=min(cursor_row, len(self._task_rows) - 1), column=0)
        if selected:
            self._render_selected_task_safely("task deletion")
            task_list.focus()
        self._set_status(f"Deleted task: {self._record_title(record)}")

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
        selection_changed = (
            project_path != self._active_project_path or task_id != self._selected_task_id
        )
        if selection_changed:
            self._flush_draft(force=True)
        self._active_project_path = project_path
        self.directory = project_path
        self._remember_project(project_path)
        self.coordinator = record_coordinator
        self._selected_task_id = task_id
        self._new_task_mode = False
        self._clear_task_update(self._task_row_key(project_path, task_id))
        self.query_one("#project-select", Select).value = self._project_select_value()
        self.query_one("#directory", Static).update(self._directory_text())
        self._refresh_task_list()
        self._render_selected_task_safely("task selection")
        if selection_changed or self._composer_task_id != task_id:
            # Deliberate transition: load this task's follow-up draft.
            self._load_composer_for_selection()
            self._selection_settings = self._current_submission_settings()

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
        """Render the selected task's transcript, header, and controls.

        This is a view refresh: it never touches the composer, so background
        output cannot overwrite a draft, steal focus, or reset the cursor.
        Composer contents change only on deliberate draft/task transitions.
        """
        record = self.coordinator.get(self._selected_task_id or "")
        self._plan_review_generation += 1
        plan_review_generation = self._plan_review_generation
        output = self.query_one("#output", TranscriptLog)
        output.clear()
        self._refresh_send_button()
        if record is None:
            self._rendered_plan_question_signature = None
            self.query_one("#output-panel", Vertical).styles.display = "block"
            self._set_output_view(self._showing_error_output)
            self.query_one("#task-context", Static).update("Task branch: —    Worktree: —")
            self.query_one("#phase", Static).update("Phase: Idle")
            self._set_error("")
            self.query_one("#pause-button", Button).disabled = True
            self.query_one("#resume-button", Button).disabled = True
            self.query_one("#cancel-button", Button).disabled = True
            self.query_one("#retry-button", Button).disabled = True
            self.query_one("#continue-plan-button", Button).disabled = True
            self.query_one("#start-coding-button", Button).disabled = True
            self.query_one("#resume-notes-panel", Vertical).styles.display = "none"
            self.query_one("#plan-review", Vertical).styles.display = "none"
            self._refresh_task_title(None)
            self._refresh_output_viewer(None)
            return
        # Use Textual's resolved Rich color rather than the raw CSS variable:
        # the default `$text` value is CSS syntax (`auto 87%`), not a Rich
        # color string.
        output.set_final_color(self.screen.rich_style.color)
        output.set_user_color(self.screen.rich_style.color)
        plan_review = self.query_one("#plan-review", Vertical)
        plan_review.styles.display = "block" if record.mode == "plan" else "none"
        self.query_one("#output-panel", Vertical).styles.display = (
            "none" if record.mode == "plan" else "block"
        )
        self._set_output_view(self._showing_error_output, visible=record.mode != "plan")
        if record.mode == "plan":
            self._render_plan_review(record, plan_review_generation)
        else:
            self._rendered_plan_question_signature = None
            self._write_conversation(output, record)
        worktree = str(record.worktree_path) if record.worktree_path else "—"
        branch = record.branch_name or "—"
        reasoning = record.reasoning or "not applicable"
        self.query_one("#task-context", Static).update(
            f"Mode: {record.mode} · Provider: {record.provider} · Model: {record.model} · Thinking: {reasoning}\n"
            f"Task branch: {branch}    Worktree: {worktree}"
        )
        self.query_one("#phase", Static).update(f"Phase: {record.phase}")
        self._set_error(record.error or "", record=record)
        self._set_status(record.phase if record.phase == "Stopping" else record.status.capitalize())
        active = record.status in ACTIVE_RUN_STATUSES
        stopping = getattr(record, "stopping", False)
        self.query_one("#pause-button", Button).disabled = not active or stopping
        self.query_one("#resume-button", Button).disabled = record.status not in {"paused", "interrupted"}
        self.query_one("#cancel-button", Button).disabled = not active
        self.query_one("#retry-button", Button).disabled = record.status != "failed"
        self.query_one("#continue-plan-button", Button).disabled = record.status != "questioning"
        self.query_one("#start-coding-button", Button).disabled = record.status != "questioning"
        self.query_one("#resume-notes-panel", Vertical).styles.display = (
            "block" if record.status in {"paused", "interrupted", "questioning"} else "none"
        )
        self.query_one("#resume-notes-label", Static).update(
            "Plan follow-up or question" if record.status == "questioning" else "Optional notes for resuming this task"
        )
        self._refresh_task_title(record)
        self._refresh_output_viewer(record)

    def _write_conversation(self, output: TranscriptLog, record: TaskRecord) -> None:
        """Render user turns and per-run assistant responses in order."""
        turns = list(getattr(record, "turns", None) or ())
        runs = list(getattr(record, "runs", None) or ())
        if not turns:
            # A record without turns (minimal test doubles) renders its
            # messages only; the prompt stays visible in the task title.
            for index, message in enumerate(record.messages):
                output.write_message(
                    message,
                    final=record.status == "completed" and index == len(record.messages) - 1,
                )
            return
        runs_by_turn: dict[str, list] = {}
        for run in runs:
            runs_by_turn.setdefault(run.turn_id, []).append(run)
        last_run = runs[-1] if runs else None
        for turn in turns:
            if turn.is_user:
                output.write_message(f"You · turn {turn.sequence}:\n{turn.text}", tone="user")
            else:
                output.write_message(f"Generated follow-up · turn {turn.sequence} (not typed by you)", tone="user")
            for run in runs_by_turn.get(turn.turn_id, ()):
                messages = record.run_messages(run)
                status_label = "Stopping" if run is last_run and getattr(record, "stopping", False) else run.status
                attempt = f" · attempt {run.attempt}" if run.attempt > 1 else ""
                output.write_message(f"Assistant{attempt} · {status_label}", tone="user")
                for index, message in enumerate(messages):
                    output.write_message(
                        message,
                        final=(
                            run is last_run
                            and record.status == "completed"
                            and index == len(messages) - 1
                        ),
                    )
        covered = sum(len(record.run_messages(run)) for run in runs)
        if covered < len(record.messages) and not runs:
            for message in record.messages:
                output.write_message(message)

    # ------------------------------------------------------------------
    # Output viewer
    # ------------------------------------------------------------------

    def _viewer(self) -> OutputViewer | None:
        nodes = self.query("#output-viewer")
        return nodes.first() if nodes else None

    def _set_viewer_visible(self, visible: bool) -> None:
        self._viewer_visible = visible
        try:
            self.memory.set_ui_preference("output_viewer_visible", visible)
        except (OSError, ValueError):
            pass
        self._apply_viewer_visibility()
        if visible:
            record = self.coordinator.get(self._selected_task_id or "") if self._selected_task_id else None
            self._refresh_output_viewer(record, final=True)
        self._set_status("Viewer shown" if visible else "Viewer hidden")

    def _apply_viewer_visibility(self, width: int | None = None) -> None:
        """Show the viewer as a one-third panel, or full width when too narrow."""
        nodes = self.query("#workspace")
        viewer = self._viewer()
        if not nodes or viewer is None:
            return
        width = self.size.width if width is None else width
        required = self.prompting.viewer_minimum_width + self.prompting.main_minimum_width
        full = self._viewer_visible and (self._compact_mode or width < required)
        self._viewer_full = full
        workspace = nodes.first()
        workspace.set_class(self._viewer_visible and not full, "viewer-visible")
        workspace.set_class(full, "viewer-full")
        viewer.set_full_width(full)
        toggle = self.query("#viewer-toggle-button")
        if toggle:
            toggle.first().label = "Hide viewer" if self._viewer_visible else "Show viewer"

    def _refresh_output_viewer(self, record: TaskRecord | None, *, final: bool = False) -> None:
        viewer = self._viewer()
        if viewer is None:
            return
        if record is None:
            viewer.show_sources(None, [ViewerSource(LATEST_SOURCE, "Latest response", "", "No task selected")])
            return
        title = self._record_title(record)
        runs = list(getattr(record, "runs", None) or ())
        turn_positions = {
            turn.turn_id: turn.sequence for turn in (getattr(record, "turns", None) or ())
        }
        latest_text = ""
        latest_identity = f"{title} · no response yet"
        earlier: list[tuple[str, str, str]] = []
        textual_runs = [run for run in runs if record.response_text(run)]
        if textual_runs:
            latest = textual_runs[-1]
            latest_text = record.response_text(latest)
            latest_identity = (
                f"{title} · turn {turn_positions.get(latest.turn_id, '?')} · run {latest.attempt} · {latest.status}"
            )
            for run in reversed(textual_runs[:-1]):
                earlier.append(
                    (
                        f"run:{run.run_id}",
                        f"Turn {turn_positions.get(run.turn_id, '?')} response (attempt {run.attempt}, {run.status})",
                        record.response_text(run),
                    )
                )
        elif record.messages:
            latest_text = "\n\n".join(message for message in record.messages if message.strip())
            latest_identity = f"{title} · {record.status}"
        if record.mode == "plan" and record.plan_text:
            latest_text = record.plan_text
            latest_identity = f"{title} · plan · {record.status}"
        viewer.show_sources(
            f"{self._active_project_path}::{record.task_id}",
            response_sources(latest_text, earlier, record.plan_text or None, latest_identity),
            final=final or record.status not in ACTIVE_RUN_STATUSES,
        )

    def on_output_viewer_back_requested(self, event: OutputViewer.BackRequested) -> None:
        event.stop()
        self._set_viewer_visible(False)
        self.query_one("#prompt-input", DaedalusVimTextArea).focus()

    def on_output_viewer_link_activated(self, event: OutputViewer.LinkActivated) -> None:
        event.stop()
        # Links are never opened automatically; show the target instead.
        self._set_status(f"Link: {event.href}")

    def _focus_in_viewer(self) -> bool:
        viewer = self._viewer()
        focused = self.focused
        if viewer is None or focused is None:
            return False
        return focused is viewer or viewer in focused.ancestors

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
            and record.status in {"completed", "awaiting_answers"}
            and len(selected) == len(record.plan_questions)
            and all_answered
            and not record.plan_confirmed
        )
        implement_button = implement_nodes.first()
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
        if record is None or record.mode != "plan":
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
        """Save the current draft and open a separate new-task conversation."""
        self._flush_draft(force=True)
        self._selected_task_id = None
        self._new_task_mode = True
        self._selection_settings = None
        self._refresh_topic_select()
        self._refresh_task_list()
        self._render_selected_task_safely("new task")
        self._load_composer_for_selection(restore_status=False)
        self._set_status("New task")

    def _set_prompt_text(self, text: str, *, editable: bool) -> None:
        """Compatibility helper: deliberately replace the composer text."""
        self._load_composer(self._composer_task_id, text)
        prompt = self.query_one("#prompt-input", DaedalusVimTextArea)
        prompt.read_only = not editable

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
        elif key == "ctrl+u":
            self._scroll_output("page_up")
        elif key == "y":
            self._copy_selection()
        elif key == "p":
            self._paste_into_prompt()
        elif key == "i":
            self.query_one("#prompt-input", TextArea).focus()
            self._set_status("Insert")

    def _scroll_output(self, direction: str) -> None:
        if self._focus_in_viewer():
            viewer = self._viewer()
            if viewer is not None:
                viewer.scroll_content(direction)
                self._set_status(f"Viewer {direction.replace('_', ' ')}")
                return
        output = self.query_one("#task-error" if self._showing_error_output else "#output", Log)
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

    def _set_output_view(
        self,
        show_errors: bool,
        *,
        focus: bool = False,
        visible: bool = True,
    ) -> None:
        """Show either the full-size transcript or the full-size diagnostics log."""
        self._showing_error_output = show_errors
        error_widget = self.query_one("#task-error", Log)
        output_widget = self.query_one("#output", TranscriptLog)
        error_widget.styles.display = "block" if visible and show_errors else "none"
        output_widget.styles.display = "block" if visible and not show_errors else "none"
        self.query_one("#output-view-label", Static).update(
            "Error output" if show_errors else "Agent output"
        )
        self.query_one("#output-toggle-button", Button).label = (
            "Show agent output" if show_errors else "Show errors"
        )
        if focus:
            (error_widget if show_errors else output_widget).focus()

    def _paste_into_prompt(self) -> None:
        text = paste_from_system_clipboard()
        if text is None:
            self._set_status("Clipboard unavailable")
            return
        prompt = self.query_one("#prompt-input", TextArea)
        if prompt.read_only:
            prompt.read_only = False
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

    def copy_to_clipboard(self, text: str) -> bool:
        """Use Textual's OSC 52 path and a native clipboard fallback.

        Returns whether the native clipboard accepted the text; OSC 52 has no
        acknowledgement, so a False result means only that the host command
        was unavailable or failed, and the Vim register still holds the text.
        """
        super().copy_to_clipboard(text)
        return bool(copy_to_system_clipboard(text))

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

    def _start_coding(self) -> None:
        record = self.coordinator.get(self._selected_task_id or "")
        notes_widget = self.query_one("#resume-notes", TextArea)
        notes = notes_widget.text.strip()
        if record is not None and self.coordinator.start_coding(record.task_id, notes):
            self._mark_task_current_session(record)
            notes_widget.clear()
            self._set_status("Starting coding")

    def _cancel_task(self) -> None:
        """Compatibility alias: Cancel now interrupts without discarding work."""
        self._interrupt_task()

    def _interrupt_task(self) -> None:
        """Shared interruption for Ctrl+C, Cancel, and Ctrl+X.

        Captures the selected task and its active turn first, saves any
        separately typed follow-up as a recoverable draft, asks the
        coordinator to stop the run non-destructively, and restores the
        interrupted turn's exact text to the composer for editing.
        """
        record = self.coordinator.get(self._selected_task_id or "") if self._selected_task_id else None
        if record is None:
            self._set_status("Nothing is running")
            return
        interrupt = getattr(self.coordinator, "interrupt", None)
        if interrupt is None:
            self._set_status("Interrupt unavailable")
            return
        turn = getattr(record, "latest_user_turn", None)
        turn_text = turn.text if turn is not None else record.prompt
        turn_id = turn.turn_id if turn is not None else None
        # Save whatever is in the composer before anything else changes.
        self._flush_draft(force=True)
        prompt = self.query_one("#prompt-input", DaedalusVimTextArea)
        stashed = False
        current = prompt.text
        if (
            self._composer_task_id == record.task_id
            and current.strip()
            and current != turn_text
        ):
            try:
                self.prompt_store.save_draft(
                    self._active_project_path,
                    record.task_id,
                    current,
                    cursor=tuple(prompt.cursor_location),
                    revision=self._draft_revision,
                    revises_turn_id=self._composer_revises_turn_id,
                    draft_id=f"stash-{int(time.time() * 1000)}",
                    kind="stashed",
                )
                stashed = True
            except (PromptStoreError, OSError) as error:
                self._set_status(f"Follow-up not saved: {error}")
        if not interrupt(record.task_id):
            self._set_status("Nothing is running")
            return
        self._mark_task_current_session(record)
        # Restore the interrupted turn for editing. The recovered prompt may
        # be edited immediately; Send stays disabled until the run has stopped.
        self._load_composer(record.task_id, turn_text, revises_turn_id=turn_id)
        self._draft_dirty = True
        self._flush_draft(force=True)
        self._refresh_prompt_history(record)
        status = "Stopping; the prompt is back in the editor"
        if stashed:
            status += " (your unsent follow-up is saved under Prompt history)"
        self._set_status(status)

    def _retry_task(self) -> None:
        record = self.coordinator.get(self._selected_task_id or "")
        retry = getattr(self.coordinator, "retry", None)
        if record is None or retry is None or not retry(record.task_id):
            self._set_status("Retry unavailable")
            return
        self._mark_task_current_session(record)
        self._set_status("Retrying")

    # ------------------------------------------------------------------
    # Orchestrate Mode view
    # ------------------------------------------------------------------

    def _set_orchestrate_view(self, shown: bool) -> None:
        """Switch between the task view and the orchestrate view."""
        switcher = self.query("#view-switcher")
        if not switcher:
            return
        self._orchestrate_view_shown = shown
        switcher.first().current = "orchestrate-view" if shown else "tasks-view"
        buttons = self.query("#orchestrate-mode-button")
        if buttons:
            buttons.first().label = "Task Mode" if shown else "Orchestrate Mode"
        try:
            self.memory.set_ui_preference("orchestrate_view", shown)
        except (OSError, ValueError):
            pass
        if shown:
            self._refresh_orchestrate_view()
            self.query_one("#orchestrate-prompt", DaedalusVimTextArea).focus()
        else:
            self._render_selected_task_safely("orchestrate view closed")
            self.query_one("#prompt-input", DaedalusVimTextArea).focus()
        # The two views have different toolbars, so start again from the
        # single-row layout and let the measurement wrap or compact it.
        self._apply_responsive_layout()

    def _active_orchestrator(self) -> OrchestrateCoordinator | None:
        return self._orchestrator_for(self._active_project_path)

    def _role_selection(self, role: str) -> tuple[str, str, str]:
        """Read one role's ``(provider, model, reasoning)`` from the role row."""
        provider = str(self.query_one(f"#{role}-provider-select", Select).value)
        model = str(self.query_one(f"#{role}-model-select", Select).value)
        reasoning_value = self.query_one(f"#{role}-reasoning-select", Select).value
        reasoning = "" if reasoning_value in _SELECT_EMPTY else str(reasoning_value)
        return provider, model, reasoning

    def _orchestrate_selections(self) -> tuple[tuple[str, str, str], tuple[str, str, str], int] | None:
        """Read the role row; report the first invalid control and return None."""
        orchestrate = self.orchestrate_settings
        workers_text = self.query_one("#max-workers-input", Input).value.strip()
        try:
            workers = int(workers_text)
        except ValueError:
            workers = 0
        if not 1 <= workers <= orchestrate.max_workers_limit:
            self._set_orchestrate_status(
                f"Workers must be a whole number from 1 to {orchestrate.max_workers_limit}"
            )
            self.query_one("#max-workers-input", Input).focus()
            return None
        return self._role_selection("planner"), self._role_selection("worker"), workers

    def _start_orchestration(self) -> None:
        prompt_widget = self.query_one("#orchestrate-prompt", DaedalusVimTextArea)
        text = prompt_widget.text
        if not text.strip():
            self._set_orchestrate_status("Prompt cannot be empty")
            prompt_widget.focus()
            return
        selections = self._orchestrate_selections()
        if selections is None:
            return
        planner, worker, workers = selections
        orchestrator = self._active_orchestrator()
        if orchestrator is None:
            self._set_orchestrate_status("Orchestrate Mode is unavailable for this project")
            return
        self._flush_orchestrate_draft()
        try:
            session = orchestrator.start(text, planner, worker, workers, topic=self._selected_topic())
        except (RuntimeError, ValueError, OSError) as error:
            self._set_orchestrate_status(f"Could not start: {error}")
            return
        self._selected_session_id = session.session_id
        self._suppress_orchestrate_draft_events = True
        try:
            prompt_widget.load_text("")
        finally:
            self._suppress_orchestrate_draft_events = False
        self._orchestrate_draft_dirty = False
        try:
            self.prompt_store.delete_draft(self._active_project_path, None, draft_id="orchestrate")
        except (PromptStoreError, OSError):
            pass
        self._refresh_orchestrate_view()
        self._set_orchestrate_status(f"Session {session.session_id} started")

    def _stop_orchestration(self) -> None:
        orchestrator = self._active_orchestrator()
        session = self._selected_session()
        if orchestrator is None or session is None:
            self._set_orchestrate_status("No session selected")
            return
        if not orchestrator.stop(session.session_id):
            self._set_orchestrate_status("Session is not running")
            return
        self._refresh_orchestrate_view()
        self._set_orchestrate_status(f"Stopping {session.session_id}")

    def _selected_session(self) -> OrchestrationSession | None:
        orchestrator = self._orchestrators.get(self._active_project_path.resolve())
        if orchestrator is None:
            return None
        sessions = list(orchestrator.sessions())
        if not sessions:
            return None
        if self._selected_session_id is not None:
            for session in sessions:
                if session.session_id == self._selected_session_id:
                    return session
        self._selected_session_id = sessions[-1].session_id
        return sessions[-1]

    def _apply_session_event(self, record, message: str, kind: str) -> None:
        session_id = getattr(record, "session_id", None)
        if session_id and self._selected_session_id is None:
            self._selected_session_id = session_id
        self._refresh_orchestrate_view()
        if message and self._orchestrate_view_shown:
            self._set_orchestrate_status(message)
        if kind == "pushed" and message:
            # The context file push arrives as a session event, not a task
            # event; record it in the push log like any other Daedalus push.
            self._apply_push_confirmation(record, message)

    def _project_for_session_record(self, record) -> Path | None:
        """Project owning an orchestrate session event, or None for task records."""
        session_id = getattr(record, "session_id", None)
        if not session_id:
            return None
        for project_path, orchestrator in self._orchestrators.items():
            if orchestrator.get(session_id) is not None:
                return project_path
        return None

    def _refresh_orchestrate_view(self) -> None:
        """Render the session selector, board, planner log, and summary."""
        if not self.query("#orchestrate-board"):
            return
        orchestrator = self._orchestrators.get(self._active_project_path.resolve())
        sessions = list(orchestrator.sessions()) if orchestrator is not None else []
        session = self._selected_session()
        session_select = self.query_one("#orchestrate-session-select", Select)
        options = [
            (f"{item.session_id} · {item.status}", item.session_id) for item in reversed(sessions)
        ]
        current = tuple(value for _label, value in getattr(session_select, "_options", ()))
        if current != tuple(value for _, value in options):
            session_select.set_options(_literal_select_options(options))
        if session is not None and session_select.value != session.session_id:
            try:
                session_select.value = session.session_id
            except InvalidSelectValueError:
                pass
        board = self.query_one("#orchestrate-board", DataTable)
        board.clear(columns=True)
        title_width = self.orchestrate_settings.board_title_width
        for label, width in (
            ("Card", 5),
            ("Title", title_width),
            ("Status", 11),
            ("Checklist", 9),
            ("Worker task", 13),
            ("Tokens", 7),
        ):
            board.add_column(label, width=width)
        self._orchestrate_board_rows = []
        stop_button = self.query_one("#orchestrate-stop-button", Button)
        log = self.query_one("#planner-log", TranscriptLog)
        log.clear()
        summary = self.query_one("#orchestrate-summary", Static)
        if session is None:
            stop_button.disabled = True
            summary.update("No orchestration session yet.")
            self.query_one("#orchestrate-status", Static).update("Idle")
            return
        for card in session.ordered_cards():
            board.add_row(
                card.card_id,
                self._fit_task_cell(" ".join(card.task.title.split()), title_width),
                card.status,
                card.ticks_text,
                card.worker_task_id or "—",
                str(card.tokens),
                key=card.card_id,
            )
            self._orchestrate_board_rows.append((card.card_id, card.worker_task_id))
        stop_button.disabled = not session.active
        limit = max(1, self.orchestrate_settings.planner_log_lines)
        lines: list[str] = []
        for entry in session.log:
            lines.extend(entry.splitlines() or [""])
        for line in lines[-limit:]:
            log.write_message(line or " ")
        summary.update(
            f"Planner tokens: {session.tokens_planner}    Worker tokens: {session.tokens_workers}    "
            f"Total: {session.tokens_total}    "
            f"Context sent to workers: {session.worker_prompt_chars} chars over {session.dispatched_cards} tasks"
        )
        status_text = f"{session.session_id}: {session.status} (round {session.round})"
        if session.error:
            status_text += f" — {' '.join(session.error.split())[:160]}"
        self.query_one("#orchestrate-status", Static).update(status_text)
        if self._orchestrate_view_shown:
            self._refresh_orchestrate_viewer(session, orchestrator)

    def _refresh_orchestrate_viewer(self, session: OrchestrationSession, orchestrator) -> None:
        """Show the session's PLAN.md in the Markdown viewer."""
        viewer = self._viewer()
        if viewer is None:
            return
        plan_text = getattr(orchestrator, "plan_text", None)
        text = plan_text(session) if callable(plan_text) else session.summary
        identity = f"{session.session_id} · {session.status} · round {session.round}"
        viewer.show_sources(
            f"{self._active_project_path}::{session.session_id}",
            [ViewerSource(LATEST_SOURCE, "Plan", text, identity)],
            final=not session.active,
        )

    def _focus_board_row(self, card_id: str) -> None:
        worker_task_id = next(
            (task_id for item_id, task_id in self._orchestrate_board_rows if item_id == card_id), None
        )
        if not worker_task_id:
            self._set_orchestrate_status(f"{card_id} has no worker task yet")
            return
        self._focus_task(self._active_project_path, worker_task_id)
        self._set_orchestrate_status(f"Selected worker task {worker_task_id} for {card_id}")

    def _set_orchestrate_status(self, status: str) -> None:
        nodes = self.query("#orchestrate-status")
        if nodes:
            nodes.first().update(status)

    def _schedule_orchestrate_draft_save(self) -> None:
        if self._orchestrate_draft_timer is not None:
            return
        delay = self.prompting.draft_autosave_delay_ms / 1000
        if delay <= 0:
            self._flush_orchestrate_draft()
            return
        self._orchestrate_draft_timer = self.set_timer(delay, self._orchestrate_draft_timer_fired)

    def _orchestrate_draft_timer_fired(self) -> None:
        self._orchestrate_draft_timer = None
        self._flush_orchestrate_draft()

    def _flush_orchestrate_draft(self) -> None:
        """Save the orchestrate prompt under its own draft key."""
        if self._orchestrate_draft_timer is not None:
            self._orchestrate_draft_timer.stop()
            self._orchestrate_draft_timer = None
        if not self._orchestrate_draft_dirty:
            return
        nodes = self.query("#orchestrate-prompt")
        if not nodes:
            return
        text = nodes.first().text
        try:
            if text.strip():
                self.prompt_store.save_draft(self._active_project_path, None, text, draft_id="orchestrate")
            else:
                self.prompt_store.delete_draft(self._active_project_path, None, draft_id="orchestrate")
            self._orchestrate_draft_dirty = False
        except (PromptStoreError, OSError) as error:
            self._set_orchestrate_status(f"Draft not saved: {error}")

    def _load_orchestrate_draft(self) -> None:
        nodes = self.query("#orchestrate-prompt")
        if not nodes:
            return
        try:
            draft = self.prompt_store.load_draft(self._active_project_path, None, draft_id="orchestrate")
        except (PromptStoreError, OSError):
            draft = None
        self._suppress_orchestrate_draft_events = True
        try:
            nodes.first().load_text(draft.text if draft is not None else "")
        finally:
            self._suppress_orchestrate_draft_events = False
        self._orchestrate_draft_dirty = False

    def _set_status(self, status: str) -> None:
        self.query_one("#status", Static).update(status)

    def _set_error(self, error: str, record: TaskRecord | None = None) -> None:
        error = truncate_diagnostic(error) if error else ""
        header = self._diagnostics_header(record) if record is not None else ""
        text = f"{header}\n\n{error}" if header and error else (error or header)
        if text == self._displayed_error:
            return
        error_widget = self.query_one("#task-error", Log)
        error_widget.clear()
        if text:
            error_widget.write(text)
        self._displayed_error = text

    def _diagnostics_header(self, record: TaskRecord) -> str:
        """Name the local log files for the selected run so they can be opened."""
        lines = []
        run = getattr(record, "active_run", None)
        path = getattr(run, "diagnostics_path", None) if run is not None else None
        if path:
            lines.append(f"Run diagnostics: {path}")
        elif getattr(record, "diagnostics_dir", None):
            lines.append(f"Task diagnostics: {record.diagnostics_dir}")
        lines.append(f"Runtime log: {self.debug_log_path}")
        return "\n".join(lines)
