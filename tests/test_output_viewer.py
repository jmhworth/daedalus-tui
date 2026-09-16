"""Output viewer tests: rendering, raw fallback, source switching, scroll retention."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Markdown, Select, Static, TextArea

from tui.output_viewer import (
    LATEST_SOURCE,
    PLAN_SOURCE,
    OutputViewer,
    ViewerSource,
    apply_hard_line_breaks,
    extract_action_items,
    response_sources,
)


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

    async def test_action_items_head_the_output_and_carry_the_run_identity(self):
        app = ViewerHarness()
        async with app.run_test(size=(100, 30)) as pilot:
            viewer = app.query_one("#viewer", OutputViewer)
            response = "\n".join(
                [
                    "Done.",
                    "",
                    "## Next steps",
                    "- Rerun the migration",
                    "- [ ] Review the parameter file",
                ]
            )
            viewer.show_sources("task-1", response_sources(response, [], None, "Task · run 1 · completed"))
            await pilot.pause()
            await pilot.pause()
            self.assertEqual(
                viewer.action_items,
                ("Review the parameter file", "Rerun the migration"),
            )
            panel = str(app.query_one("#viewer-action-items", Static).render())
            self.assertIn("Action items · Task · run 1 · completed", panel)
            self.assertIn("1. Review the parameter file", panel)

    async def test_a_response_without_follow_ups_still_names_the_run(self):
        app = ViewerHarness()
        async with app.run_test(size=(100, 30)) as pilot:
            viewer = app.query_one("#viewer", OutputViewer)
            viewer.show_sources("task-1", response_sources("All finished.", [], None, "Task · run 2"))
            await pilot.pause()
            self.assertEqual(viewer.action_items, ())
            self.assertIn("No action items · Task · run 2", str(app.query_one("#viewer-action-items", Static).render()))

    async def test_switching_sources_re_reads_the_action_items(self):
        app = ViewerHarness()
        async with app.run_test(size=(100, 30)) as pilot:
            viewer = app.query_one("#viewer", OutputViewer)
            sources = response_sources(
                "- [ ] latest work",
                [("run:1", "Turn 1 response", "- [ ] earlier work")],
                None,
                "id",
            )
            viewer.show_sources("task-1", sources)
            await pilot.pause()
            self.assertEqual(viewer.action_items, ("latest work",))
            viewer.query_one("#viewer-source-select", Select).value = "run:1"
            await pilot.pause()
            await pilot.pause()
            self.assertEqual(viewer.action_items, ("earlier work",))

    async def test_line_breaks_are_rendered_without_altering_the_raw_source(self):
        app = ViewerHarness()
        async with app.run_test(size=(100, 30)) as pilot:
            viewer = app.query_one("#viewer", OutputViewer)
            wrapped = "first line\nsecond line\n\nnew paragraph"
            rendered: list[str] = []
            original = Markdown.update

            async def capture(self, markdown):
                rendered.append(markdown)
                return await original(self, markdown)

            with patch.object(Markdown, "update", capture):
                viewer.show_sources("task-1", response_sources(wrapped, [], None, "id"))
                await pilot.pause()
                await pilot.pause()
            self.assertEqual(rendered[-1], "first line  \nsecond line\n\nnew paragraph")
            # The Raw tab keeps the response exactly as the agent wrote it.
            self.assertEqual(viewer.query_one("#viewer-raw", TextArea).text, wrapped)
            self.assertEqual(viewer.current_text(), wrapped)


class HardLineBreakTests(unittest.TestCase):
    def test_paragraph_lines_gain_a_hard_break(self):
        self.assertEqual(
            apply_hard_line_breaks("one\ntwo\n\nthree"),
            "one  \ntwo\n\nthree",
        )

    def test_fenced_and_indented_code_stay_byte_exact(self):
        source = "\n".join(
            [
                "intro",
                "",
                "```sh",
                "echo one",
                "echo two",
                "```",
                "",
                "    indented one",
                "    indented two",
            ]
        )
        self.assertEqual(apply_hard_line_breaks(source), source)

    def test_an_unterminated_fence_keeps_its_streamed_content_intact(self):
        source = "intro\n\n```python\nprint('a')\nprint('b')"
        self.assertEqual(apply_hard_line_breaks(source), source)

    def test_existing_hard_breaks_are_not_doubled(self):
        self.assertEqual(apply_hard_line_breaks("one  \ntwo\\\nthree"), "one  \ntwo\\\nthree")


class ActionItemTests(unittest.TestCase):
    def test_unchecked_boxes_outrank_headed_lists_and_done_work_is_skipped(self):
        response = "\n".join(
            [
                "## Follow-ups",
                "- run the tests",
                "",
                "- [x] already done",
                "- [ ] publish the branch",
            ]
        )
        self.assertEqual(
            extract_action_items(response),
            ["publish the branch", "run the tests"],
        )

    def test_a_bold_line_introduces_its_section_like_a_heading(self):
        response = "**Next steps:**\n- restart the daemon\n\n**Changes**\n- renamed a module"
        self.assertEqual(extract_action_items(response), ["restart the daemon"])

    def test_bullets_outside_an_action_heading_are_not_action_items(self):
        response = "## Changes\n- renamed a function\n- deleted a file"
        self.assertEqual(extract_action_items(response), [])

    def test_a_heading_after_the_action_heading_ends_the_section(self):
        response = "## Next steps\n- deploy\n\n## Notes\n- unrelated detail"
        self.assertEqual(extract_action_items(response), ["deploy"])

    def test_checklists_inside_code_blocks_are_ignored(self):
        response = "```md\n- [ ] sample from a template\n```"
        self.assertEqual(extract_action_items(response), [])

    def test_prefixed_lines_are_collected_and_emphasis_is_stripped(self):
        response = "TODO: **tighten** the timeout\nNEXT: tighten the timeout"
        self.assertEqual(extract_action_items(response), ["tighten the timeout"])

    def test_the_limit_bounds_the_list(self):
        response = "\n".join(f"- [ ] item {index}" for index in range(10))
        self.assertEqual(len(extract_action_items(response, limit=3)), 3)


if __name__ == "__main__":
    unittest.main()
