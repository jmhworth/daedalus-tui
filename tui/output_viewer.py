"""Optional right-side viewer that renders a task's Markdown responses.

The viewer is read-only display data: it never executes code blocks, HTML, or
commands, never fetches remote images, and only reports link targets when the
user activates one. It is fed from stored response text (never from the
transcript's wrapped display lines), debounces live re-rendering, discards
outdated render results, and keeps the exact source available in a Raw tab.

Two presentation rules sit on top of that. Single newlines inside a paragraph
become real line breaks, because agents hard-wrap prose and write one line per
thought while CommonMark would join those lines into one block. And the action
items found in the response are summarized above the rendered output, so the
first thing visible is what the agent wants done next.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial
import re

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Markdown, Select, Static, TextArea

from .debug_log import LOGGER, log_exception


LATEST_SOURCE = "latest"
PLAN_SOURCE = "plan"
DEFAULT_ACTION_ITEM_LIMIT = 6

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_INDENTED_CODE = re.compile(r"^(?: {4,}|\t)")
_ALREADY_BROKEN = re.compile(r"(?:  |\\)$")

_HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.*?)\s*#*\s*$")
# Agents frequently label a section with a bold line rather than an ATX
# heading, and that line introduces its list exactly the same way.
_BOLD_HEADING = re.compile(r"^\s*\*\*(.+?)\*\*:?\s*$")
_CHECKBOX_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[([ xX])\]\s+(.*\S)\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")
_PREFIXED_ITEM = re.compile(r"^\s*(?:TODO|NEXT|ACTION)\b\s*[:\-]\s*(.*\S)\s*$", re.IGNORECASE)
# Only bold markers are stripped: single `*` and `_` also appear in globs and
# identifiers an action item may legitimately name.
_EMPHASIS = re.compile(r"\*\*")
# Headings that introduce work the agent expects someone to pick up.
_ACTION_HEADINGS = (
    "action item",
    "next step",
    "follow-up",
    "follow up",
    "todo",
    "to do",
    "remaining work",
    "recommend",
    "suggested",
    "what's left",
    "whats left",
)


def apply_hard_line_breaks(text: str) -> str:
    """Turn every single newline inside a paragraph into a visible line break.

    CommonMark joins consecutive prose lines into one paragraph, so an agent's
    hard-wrapped summary renders as a wall of text that looks nothing like the
    response it wrote. Appending the two-space hard break preserves the
    author's line structure. Fenced and indented code are left byte-exact,
    since their content is the point.
    """
    lines = text.split("\n")
    fence: tuple[str, int] | None = None
    result: list[str] = []
    for index, line in enumerate(lines):
        match = _FENCE.match(line)
        if fence is not None:
            result.append(line)
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= fence[1]:
                fence = None
            continue
        if match:
            fence = (match.group(1)[0], len(match.group(1)))
            result.append(line)
            continue
        following = lines[index + 1] if index + 1 < len(lines) else ""
        breakable = (
            line.strip()
            and following.strip()
            and not _INDENTED_CODE.match(line)
            and not _ALREADY_BROKEN.search(line)
        )
        result.append(f"{line}  " if breakable else line)
    return "\n".join(result)


def _clean_item(text: str) -> str:
    """Strip list emphasis so items read as plain sentences in the panel."""
    return " ".join(_EMPHASIS.sub("", text).split())


def extract_action_items(text: str, limit: int = DEFAULT_ACTION_ITEM_LIMIT) -> list[str]:
    """Return the actionable follow-ups an agent response states.

    Three signals are read, strongest first: unchecked task-list boxes, list
    items beneath a heading that names follow-up work, and lines prefixed with
    ``TODO``/``NEXT``/``ACTION``. Code blocks are ignored so a sample snippet
    containing a checklist cannot be mistaken for real work.
    """
    if not text.strip():
        return []
    fence: tuple[str, int] | None = None
    under_action_heading = False
    collected: list[tuple[int, str]] = []
    for line in text.split("\n"):
        match = _FENCE.match(line)
        if fence is not None:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= fence[1]:
                fence = None
            continue
        if match:
            fence = (match.group(1)[0], len(match.group(1)))
            continue
        heading = _HEADING.match(line) or _BOLD_HEADING.match(line)
        if heading:
            lowered = heading.group(1).lower()
            under_action_heading = any(word in lowered for word in _ACTION_HEADINGS)
            continue
        checkbox = _CHECKBOX_ITEM.match(line)
        if checkbox:
            if checkbox.group(1) == " ":
                collected.append((0, _clean_item(checkbox.group(2))))
            continue
        prefixed = _PREFIXED_ITEM.match(line)
        if prefixed:
            collected.append((2, _clean_item(prefixed.group(1))))
            continue
        item = _LIST_ITEM.match(line)
        if item and under_action_heading:
            collected.append((1, _clean_item(item.group(1))))

    ordered = sorted(
        ((priority, order, item) for order, (priority, item) in enumerate(collected) if item),
        key=lambda entry: (entry[0], entry[1]),
    )
    items: list[str] = []
    seen: set[str] = set()
    for _priority, _order, item in ordered:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
        if len(items) >= max(1, limit):
            break
    return items


@dataclass(frozen=True)
class ViewerSource:
    """One selectable content source: latest response, an earlier one, or the plan."""

    key: str
    label: str
    text: str
    identity: str = ""


class OutputViewer(Vertical):
    """Rendered/Raw Markdown viewer for the selected task's output."""

    DEFAULT_CSS = """
    OutputViewer {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    OutputViewer #viewer-toolbar {
        height: 3;
        align: left middle;
    }
    OutputViewer #viewer-source-select {
        width: 1fr;
        margin-right: 1;
    }
    OutputViewer #viewer-mode-button {
        width: 10;
        min-width: 10;
    }
    OutputViewer #viewer-back-button {
        width: 8;
        min-width: 8;
        margin-left: 1;
        display: none;
    }
    OutputViewer.full-width #viewer-back-button {
        display: block;
    }
    OutputViewer #viewer-action-items {
        height: auto;
        max-height: 10;
        padding: 0 1;
        margin-bottom: 1;
        background: $boost;
        color: $text;
    }
    OutputViewer.no-action-panel #viewer-action-items {
        display: none;
    }
    OutputViewer #viewer-rendered {
        height: 1fr;
        overflow-x: auto;
    }
    OutputViewer #viewer-markdown {
        width: auto;
        min-width: 100%;
    }
    OutputViewer #viewer-raw {
        height: 1fr;
        display: none;
        border: none;
    }
    OutputViewer.raw-mode #viewer-rendered {
        display: none;
    }
    OutputViewer.raw-mode #viewer-raw {
        display: block;
    }
    OutputViewer #viewer-note {
        height: auto;
        display: none;
        color: $warning;
    }
    OutputViewer.render-failed #viewer-note {
        display: block;
    }
    """

    class BackRequested(Message):
        """The user asked to leave the full-width viewer."""

    class LinkActivated(Message):
        def __init__(self, href: str) -> None:
            super().__init__()
            self.href = href

    def __init__(
        self,
        *,
        render_debounce_ms: int = 150,
        hard_line_breaks: bool = True,
        show_action_items: bool = True,
        action_item_limit: int = DEFAULT_ACTION_ITEM_LIMIT,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.render_debounce_ms = max(0, int(render_debounce_ms))
        self.hard_line_breaks = bool(hard_line_breaks)
        self.show_action_items = bool(show_action_items)
        self.action_item_limit = max(1, int(action_item_limit))
        self._sources: dict[str, ViewerSource] = {}
        self._order: list[str] = []
        self._selected_key: str | None = None
        self._task_key: str | None = None
        self._raw_mode = False
        self._render_generation = 0
        self._rendered_generation = 0
        self._render_timer = None
        self._render_pending = False
        self._last_rendered_text: str | None = None
        self._render_failure_logged = False
        self.render_failed = False
        self._suppress_select = False
        self._action_items: tuple[str, ...] = ()
        self._action_signature: tuple[str, str] | None = None

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal(id="viewer-toolbar"):
            yield Select(
                [(Text("Latest response"), LATEST_SOURCE)],
                value=LATEST_SOURCE,
                allow_blank=False,
                id="viewer-source-select",
            )
            yield Button("Raw", id="viewer-mode-button")
            yield Button("Back", id="viewer-back-button")
        # The response's action items head the output; the run's identity rides
        # along on the same header rather than as a separate muted line.
        yield Static("", id="viewer-action-items", markup=False)
        yield Static("", id="viewer-note", markup=False)
        with VerticalScroll(id="viewer-rendered"):
            yield Markdown("", id="viewer-markdown", open_links=False)
        yield TextArea("", id="viewer-raw", read_only=True, soft_wrap=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def raw_mode(self) -> bool:
        return self._raw_mode

    @property
    def selected_key(self) -> str | None:
        return self._selected_key

    @property
    def task_key(self) -> str | None:
        return self._task_key

    def current_text(self) -> str:
        source = self._sources.get(self._selected_key or "")
        return source.text if source is not None else ""

    def show_sources(
        self,
        task_key: str | None,
        sources: list[ViewerSource],
        *,
        select_key: str | None = None,
        final: bool = False,
    ) -> None:
        """Replace the available sources for the selected task.

        Switching tasks resets the selection to the latest response; updating
        the same task keeps the user's chosen source and scroll position.
        """
        task_changed = task_key != self._task_key
        self._task_key = task_key
        self._sources = {source.key: source for source in sources}
        self._order = [source.key for source in sources]
        if select_key is not None and select_key in self._sources:
            self._selected_key = select_key
        elif task_changed or self._selected_key not in self._sources:
            self._selected_key = LATEST_SOURCE if LATEST_SOURCE in self._sources else (self._order[0] if self._order else None)
        self._sync_select()
        self._update_action_header()
        if task_changed:
            self._render_generation += 1
            self._last_rendered_text = None
            self.render_failed = False
            self.set_class(False, "render-failed")
        self._schedule_render(immediate=final or task_changed)

    def update_source(self, key: str, text: str, identity: str | None = None, *, final: bool = False) -> None:
        """Update one source's text while a response streams in."""
        source = self._sources.get(key)
        if source is None:
            return
        self._sources[key] = ViewerSource(key, source.label, text, identity if identity is not None else source.identity)
        if key == self._selected_key:
            self._update_action_header()
            self._schedule_render(immediate=final)

    def set_raw_mode(self, raw: bool) -> None:
        self._raw_mode = raw
        self.set_class(raw, "raw-mode")
        self.query_one("#viewer-mode-button", Button).label = "Rendered" if raw else "Raw"
        self._schedule_render(immediate=True)

    def set_full_width(self, full: bool) -> None:
        self.set_class(full, "full-width")

    def flush(self) -> None:
        """Render any pending text immediately (used when a run ends)."""
        self._schedule_render(immediate=True)

    def focus_content(self) -> None:
        if self._raw_mode:
            self.query_one("#viewer-raw", TextArea).focus()
        else:
            self.query_one("#viewer-rendered", VerticalScroll).focus()

    def scroll_content(self, direction: str) -> None:
        """Vim-style scrolling for whichever surface is visible."""
        target = self.query_one("#viewer-raw", TextArea) if self._raw_mode else self.query_one("#viewer-rendered", VerticalScroll)
        methods = {
            "up": target.scroll_up,
            "down": target.scroll_down,
            "home": target.scroll_home,
            "end": target.scroll_end,
            "page_up": target.scroll_page_up,
            "page_down": target.scroll_page_down,
        }
        method = methods.get(direction)
        if method is None:
            return
        try:
            method(animate=False)
        except TypeError:
            method()

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#viewer-mode-button")
    def _toggle_mode(self, event: Button.Pressed) -> None:
        event.stop()
        self.set_raw_mode(not self._raw_mode)

    @on(Button.Pressed, "#viewer-back-button")
    def _back(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(self.BackRequested())

    @on(Select.Changed, "#viewer-source-select")
    def _source_changed(self, event: Select.Changed) -> None:
        event.stop()
        if self._suppress_select or event.value in (Select.BLANK, "", None):
            return
        key = str(event.value)
        if key not in self._sources or key == self._selected_key:
            return
        self._selected_key = key
        self._update_action_header()
        self._schedule_render(immediate=True, reset_scroll=True)

    @on(Markdown.LinkClicked)
    def _link_clicked(self, event: Markdown.LinkClicked) -> None:
        # Links are reported, never opened automatically.
        event.stop()
        self.post_message(self.LinkActivated(event.href))

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _sync_select(self) -> None:
        select = self.query_one("#viewer-source-select", Select)
        options = [(Text(self._sources[key].label), key) for key in self._order]
        if not options:
            options = [(Text("Latest response"), LATEST_SOURCE)]
        current = tuple(value for _label, value in getattr(select, "_options", ()) if isinstance(value, str))
        self._suppress_select = True
        try:
            if current != tuple(value for _label, value in options):
                select.set_options(options)
            target = self._selected_key if self._selected_key in {value for _label, value in options} else options[0][1]
            if select.value != target:
                select.value = target
        finally:
            self._suppress_select = False

    def _update_action_header(self) -> None:
        """Refresh the action-item header above the rendered output."""
        self.set_class(not self.show_action_items, "no-action-panel")
        if not self.show_action_items:
            self._action_items = ()
            return
        source = self._sources.get(self._selected_key or "")
        identity = source.identity if source is not None else ""
        text = source.text if source is not None else ""
        signature = (identity, text)
        if signature == self._action_signature:
            # Streaming calls this on every chunk; re-scanning an unchanged
            # response would walk the whole text for no visible change.
            return
        self._action_signature = signature
        items = extract_action_items(text, self.action_item_limit)
        self._action_items = tuple(items)

        # A Text renderable, not markup: an action item may contain brackets or
        # scientific notation that Textual markup would try to interpret.
        panel = Text()
        panel.append("Action items" if items else "No action items", style="bold")
        if identity:
            panel.append(f" · {identity}")
        for position, item in enumerate(items, start=1):
            panel.append(f"\n{position}. {item}")
        self.query_one("#viewer-action-items", Static).update(panel)

    @property
    def action_items(self) -> tuple[str, ...]:
        """Action items extracted from the source currently on screen."""
        return self._action_items

    def _schedule_render(self, *, immediate: bool = False, reset_scroll: bool = False) -> None:
        if not self.is_mounted:
            return
        if reset_scroll:
            self._last_rendered_text = None
        if immediate or self.render_debounce_ms == 0:
            if self._render_timer is not None:
                self._render_timer.stop()
                self._render_timer = None
            self._render_pending = False
            self._render_now()
            return
        if self._render_timer is not None:
            self._render_pending = True
            return
        self._render_pending = True
        self._render_timer = self.set_timer(self.render_debounce_ms / 1000, self._render_from_timer)

    def _render_from_timer(self) -> None:
        self._render_timer = None
        if self._render_pending:
            self._render_pending = False
            self._render_now()

    def _render_now(self) -> None:
        text = self.current_text()
        self._render_generation += 1
        generation = self._render_generation
        if self._raw_mode or self.render_failed:
            self._render_raw(text)
            self._rendered_generation = generation
            return
        if text == self._last_rendered_text:
            return
        # Pass a callable, not a coroutine object: an exclusive worker that
        # is superseded before it starts must not leave an un-awaited coroutine.
        self.run_worker(
            partial(self._render_markdown, text, generation),
            exclusive=True,
            group="viewer-render",
            exit_on_error=False,
        )

    def _render_raw(self, text: str) -> None:
        raw = self.query_one("#viewer-raw", TextArea)
        if raw.text == text:
            return
        follow = self._at_bottom(raw)
        raw.load_text(text)
        if follow:
            raw.scroll_end(animate=False)
        self._last_rendered_text = text

    async def _render_markdown(self, text: str, generation: int) -> None:
        if generation != self._render_generation:
            return
        scroller = self.query_one("#viewer-rendered", VerticalScroll)
        follow = self._at_bottom(scroller) or self._last_rendered_text is None
        markdown = self.query_one("#viewer-markdown", Markdown)
        # Only the rendered surface gets the hard breaks; Raw stays byte-exact.
        rendered_text = apply_hard_line_breaks(text) if self.hard_line_breaks else text
        try:
            await markdown.update(rendered_text)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not self._render_failure_logged:
                log_exception("Markdown rendering failed; showing the raw response instead", error)
                self._render_failure_logged = True
            self.render_failed = True
            self.set_class(True, "render-failed")
            self.query_one("#viewer-note", Static).update(
                "Rendering failed; the exact response is shown as raw text."
            )
            self.set_raw_mode(True)
            return
        if generation != self._render_generation:
            # A newer render replaced this one while it was mounting.
            return
        self._last_rendered_text = text
        self._rendered_generation = generation
        # The Raw surface stays current so switching tabs is instant.
        self.query_one("#viewer-raw", TextArea).load_text(text)
        if follow:
            scroller.scroll_end(animate=False)

    @staticmethod
    def _at_bottom(widget) -> bool:
        try:
            max_scroll = widget.max_scroll_y
            return widget.scroll_y >= max_scroll - 1
        except Exception:
            return True

    @property
    def rendered_generation(self) -> int:
        return self._rendered_generation


def response_sources(
    latest_text: str,
    earlier: list[tuple[str, str, str]],
    plan_text: str | None,
    latest_identity: str,
) -> list[ViewerSource]:
    """Build the source list: latest response, earlier responses, then the plan."""
    sources = [ViewerSource(LATEST_SOURCE, "Latest response", latest_text, latest_identity)]
    for key, label, text in earlier:
        sources.append(ViewerSource(key, label, text, label))
    if plan_text:
        sources.append(ViewerSource(PLAN_SOURCE, "Current plan", plan_text, "Plan text"))
    return sources


__all__ = [
    "DEFAULT_ACTION_ITEM_LIMIT",
    "LATEST_SOURCE",
    "OutputViewer",
    "PLAN_SOURCE",
    "ViewerSource",
    "apply_hard_line_breaks",
    "extract_action_items",
    "response_sources",
]
