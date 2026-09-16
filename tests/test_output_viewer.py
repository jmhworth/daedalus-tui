"""Output viewer tests: rendering, raw fallback, source switching, scroll retention."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Markdown, Select, TextArea

from tui.output_viewer import LATEST_SOURCE, PLAN_SOURCE, OutputViewer, ViewerSource, response_sources


LONG_MARKDOWN = "\n".join(
    [
        "# Heading",
        "",
        "Some *emphasis* and a [link](https://example.com) with literal [brackets] and 1e-5.",
        "",
        "- item one",
        "- item two",
        "",
        "```python",
        "print('hi')",
        "```",
        "",
        "| a | b |",
        "| - | - |",
        "| 1 | 2 |",
        "",
    ]
    + [f"paragraph {index}" for index in range(60)]
)


class ViewerHarness(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def compose(self) -> ComposeResult:
        yield OutputViewer(id="viewer", render_debounce_ms=0)

    def on_output_viewer_link_activated(self, event: OutputViewer.LinkActivated) -> None:
        self.links.append(event.href)


class OutputViewerTests(unittest.IsolatedAsyncioTestCase):
    async def test_renders_markdown_blocks_and_keeps_raw_text_exact(self):
        app = ViewerHarness()
        async with app.run_test(size=(120, 40)) as pilot:
            viewer = app.query_one("#viewer", OutputViewer)
            viewer.show_sources("task-1", response_sources(LONG_MARKDOWN, [], None, "Task · run 1"))
            await pilot.pause()
            await pilot.pause()
            markdown = viewer.query_one("#viewer-markdown", Markdown)
            self.assertGreater(len(markdown.children), 5)
            self.assertEqual(viewer.query_one("#viewer-raw", TextArea).text, LONG_MARKDOWN)
            self.assertFalse(viewer.render_failed)
            viewer.set_raw_mode(True)
            await pilot.pause()
            self.assertTrue(viewer.has_class("raw-mode"))
            self.assertTrue(viewer.query_one("#viewer-raw", TextArea).read_only)

    async def test_incomplete_fences_render_safely_while_streaming(self):
        app = ViewerHarness()
        async with app.run_test(size=(100, 30)) as pilot:
            viewer = app.query_one("#viewer", OutputViewer)
            partial = "Intro\n\n```python\nprint('unterminated"
            viewer.show_sources("task-1", response_sources(partial, [], None, "streaming"))
            await pilot.pause()
            await pilot.pause()
            self.assertFalse(viewer.render_failed)
            viewer.update_source(LATEST_SOURCE, partial + "')\n```\n\n| a |\n| - |", final=True)
            await pilot.pause()
            await pilot.pause()
            self.assertEqual(viewer.current_text(), partial + "')\n```\n\n| a |\n| - |")
            self.assertFalse(viewer.render_failed)

    async def test_render_failure_falls_back_to_raw_and_logs_once(self):
        app = ViewerHarness()
        async with app.run_test(size=(100, 30)) as pilot:
            viewer = app.query_one("#viewer", OutputViewer)
            with patch.object(Markdown, "update", side_effect=RuntimeError("boom")):
                with patch("tui.output_viewer.log_exception") as logged:
                    viewer.show_sources("task-1", response_sources("# bad", [], None, "identity"))
                    await pilot.pause()
                    await pilot.pause()
                    viewer.update_source(LATEST_SOURCE, "# bad again", final=True)
                    await pilot.pause()
                    await pilot.pause()
                    self.assertEqual(logged.call_count, 1)
            self.assertTrue(viewer.render_failed)
            self.assertTrue(viewer.raw_mode)
            self.assertEqual(viewer.query_one("#viewer-raw", TextArea).text, "# bad again")

    async def test_source_switching_during_updates_and_task_changes_reset_selection(self):
        app = ViewerHarness()
        async with app.run_test(size=(100, 30)) as pilot:
            viewer = app.query_one("#viewer", OutputViewer)
            sources = response_sources("latest text", [("run:1", "Turn 1 response", "earlier text")], "plan body", "id")
            viewer.show_sources("task-1", sources)
            await pilot.pause()
            select = viewer.query_one("#viewer-source-select", Select)
            self.assertEqual([value for _label, value in select._options if isinstance(value, str)], [LATEST_SOURCE, "run:1", PLAN_SOURCE])
            select.value = PLAN_SOURCE
            await pilot.pause()
            await pilot.pause()
            self.assertEqual(viewer.selected_key, PLAN_SOURCE)
            self.assertEqual(viewer.current_text(), "plan body")
            # Streaming updates to the same task keep the chosen source.
            viewer.show_sources("task-1", response_sources("latest text 2", [("run:1", "Turn 1 response", "earlier text")], "plan body", "id"))
            await pilot.pause()
            self.assertEqual(viewer.selected_key, PLAN_SOURCE)
            # A different task returns to the latest response.
            viewer.show_sources("task-2", response_sources("other", [], None, "other id"))
            await pilot.pause()
            self.assertEqual(viewer.selected_key, LATEST_SOURCE)
            self.assertEqual(viewer.current_text(), "other")

    async def test_scroll_position_is_retained_when_reading_older_content(self):
        app = ViewerHarness()
        async with app.run_test(size=(80, 20)) as pilot:
            viewer = app.query_one("#viewer", OutputViewer)
            viewer.show_sources("task-1", response_sources(LONG_MARKDOWN, [], None, "id"))
            await pilot.pause()
            await pilot.pause()
            scroller = viewer.query_one("#viewer-rendered", VerticalScroll)
            scroller.scroll_end(animate=False)
            await pilot.pause()
            at_bottom = scroller.scroll_y
            scroller.scroll_to(y=3, animate=False)
            await pilot.pause()
            viewer.update_source(LATEST_SOURCE, LONG_MARKDOWN + "\n\nmore text\n\nand more", final=True)
            await pilot.pause()
            await pilot.pause()
            self.assertLessEqual(scroller.scroll_y, 5)
            self.assertGreater(at_bottom, 5)

    async def test_links_are_reported_not_opened(self):
        app = ViewerHarness()
        async with app.run_test(size=(100, 30)) as pilot:
            viewer = app.query_one("#viewer", OutputViewer)
            viewer.post_message(Markdown.LinkClicked(viewer.query_one("#viewer-markdown", Markdown), "https://example.com"))
            await pilot.pause()
            await pilot.pause()
            self.assertEqual(app.links, ["https://example.com"])


if __name__ == "__main__":
    unittest.main()
