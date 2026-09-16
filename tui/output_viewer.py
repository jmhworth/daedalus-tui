"""Optional right-side viewer that renders a task's Markdown responses.

The viewer is read-only display data: it never executes code blocks, HTML, or
commands, never fetches remote images, and only reports link targets when the
user activates one. It is fed from stored response text (never from the
transcript's wrapped display lines), debounces live re-rendering, discards
outdated render results, and keeps the exact source available in a Raw tab.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Markdown, Select, Static, TextArea

from .debug_log import LOGGER, log_exception


LATEST_SOURCE = "latest"
PLAN_SOURCE = "plan"


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
    OutputViewer #viewer-identity {
        height: 1;
        color: $text-muted;
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

    def __init__(self, *, render_debounce_ms: int = 150, id: str | None = None) -> None:
        super().__init__(id=id)
        self.render_debounce_ms = max(0, int(render_debounce_ms))
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
        yield Static("", id="viewer-identity", markup=False)
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
        self._update_identity()
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
            self._update_identity()
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
        self._update_identity()
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

    def _update_identity(self) -> None:
        source = self._sources.get(self._selected_key or "")
        self.query_one("#viewer-identity", Static).update(source.identity if source is not None else "")

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
        try:
            await markdown.update(text)
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


__all__ = ["LATEST_SOURCE", "OutputViewer", "PLAN_SOURCE", "ViewerSource", "response_sources"]
