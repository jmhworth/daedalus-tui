"""Focused editor tests: cut, copy, paste, registers, undo/redo, read-only."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from textual.app import App, ComposeResult
from textual.widgets import TextArea
from vimkeys_input import VimMode

from tui.vim_text_area import DaedalusVimTextArea


class EditorHarness(App[None]):
    """Minimal host app exposing the same hooks the real TUI provides."""

    def __init__(self) -> None:
        super().__init__()
        self.copied: list[str] = []
        self.copy_ok = True
        self.interrupts = 0
        self.statuses: list[str] = []

    def compose(self) -> ComposeResult:
        yield DaedalusVimTextArea(id="prompt-input")
        yield TextArea("read only text", id="history", read_only=True)

    def on_mount(self) -> None:
        editor = self.query_one("#prompt-input", DaedalusVimTextArea)
        editor.enter_insert_mode()
        editor.focus()

    def copy_to_clipboard(self, text: str) -> bool:
        self.copied.append(text)
        return self.copy_ok

    def action_interrupt_task(self) -> None:
        self.interrupts += 1

    def action_show_shortcuts(self) -> None:
        pass

    def action_toggle_plan_mode(self) -> None:
        pass

    def on_daedalus_vim_text_area_clipboard_status(self, event) -> None:
        self.statuses.append(event.message)


class VimTextAreaTests(unittest.IsolatedAsyncioTestCase):
    async def load(self, app: EditorHarness, text: str, cursor=(0, 0)) -> DaedalusVimTextArea:
        editor = app.query_one("#prompt-input", DaedalusVimTextArea)
        editor.load_text(text)
        editor.cursor_location = cursor
        return editor

    async def test_dd_cuts_a_whole_line_and_p_pastes_it_below(self):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "one\ntwo\nthree", (0, 1))
            await pilot.press("escape", "d", "d")
            self.assertEqual(editor.text, "two\nthree")
            self.assertEqual(editor.yank_register, "one\n")
            self.assertTrue(editor.register_linewise)
            await pilot.press("j", "p")
            self.assertEqual(editor.text, "two\nthree\none")
            self.assertEqual(editor.cursor_location, (2, 0))
            # Every cut mirrors to the clipboard.
            self.assertEqual(app.copied, ["one\n"])

    async def test_capital_p_pastes_a_line_above_and_the_last_line_keeps_vim_placement(self):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "alpha\nbeta", (1, 0))
            await pilot.press("escape", "y", "y")
            self.assertEqual(editor.yank_register, "beta\n")
            await pilot.press("k", "P")
            self.assertEqual(editor.text, "beta\nalpha\nbeta")
            self.assertEqual(editor.cursor_location, (0, 0))
            # dd on the last line removes the preceding newline too.
            editor.cursor_location = (2, 0)
            await pilot.press("d", "d")
            self.assertEqual(editor.text, "beta\nalpha")
            await pilot.press("p")
            self.assertEqual(editor.text, "beta\nalpha\nbeta")

    async def test_counts_apply_to_line_operators_and_motions(self):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "a\nb\nc\nd", (0, 0))
            await pilot.press("escape", "2", "y", "y")
            self.assertEqual(editor.yank_register, "a\nb\n")
            await pilot.press("3", "j")
            self.assertEqual(editor.cursor_location[0], 3)
            await pilot.press("g", "g", "2", "d", "d")
            self.assertEqual(editor.text, "c\nd")
            self.assertEqual(editor.yank_register, "a\nb\n")

    async def test_character_operators_keep_a_charwise_register(self):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "hello brave world", (0, 6))
            await pilot.press("escape", "d", "w")
            self.assertEqual(editor.text, "hello world")
            self.assertEqual(editor.yank_register, "brave ")
            self.assertFalse(editor.register_linewise)
            editor.cursor_location = (0, 0)
            await pilot.press("y", "$")
            self.assertEqual(editor.yank_register, "hello world")
            await pilot.press("x")
            self.assertEqual(editor.text, "ello world")
            editor.cursor_location = (0, 4)
            await pilot.press("d", "$")
            self.assertEqual(editor.text, "ello")

    async def test_visual_line_operations_cut_copy_and_change_whole_lines(self):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "one\ntwo\nthree", (1, 1))
            await pilot.press("escape", "V", "j", "y")
            self.assertEqual(editor.yank_register, "two\nthree\n")
            self.assertTrue(editor.register_linewise)
            self.assertEqual(editor.vim_mode, VimMode.COMMAND)
            await pilot.press("V", "d")
            self.assertEqual(editor.text, "one\nthree")
            await pilot.press("V", "c")
            self.assertEqual(editor.vim_mode, VimMode.INSERT)
            self.assertEqual(editor.text, "one\n")
            editor.insert("new")
            self.assertEqual(editor.text, "one\nnew")

    async def test_visual_character_change_cuts_and_enters_insert_mode(self):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "keep drop end", (0, 5))
            await pilot.press("escape", "v", "l", "l", "l", "c")
            self.assertEqual(editor.vim_mode, VimMode.INSERT)
            self.assertEqual(editor.yank_register, "drop")
            self.assertEqual(editor.text, "keep  end")

    async def test_identical_yanks_refresh_an_externally_changed_clipboard(self):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "same line", (0, 0))
            await pilot.press("escape", "y", "y")
            await pilot.press("y", "y")
            self.assertEqual(app.copied, ["same line\n", "same line\n"])
            self.assertEqual(editor.yank_register, "same line\n")

    @patch("tui.vim_text_area.paste_from_system_clipboard", return_value="fresh clipboard")
    async def test_system_register_paste_reads_new_external_text_after_a_vim_yank(self, _clipboard):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "abc", (0, 0))
            await pilot.press("escape", "y", "y")
            self.assertEqual(editor.yank_register, "abc\n")
            await pilot.press("quotation_mark", "plus", "P")
            self.assertEqual(editor.text, "fresh clipboardabc")
            # A plain p afterwards uses the register just loaded from outside.
            await pilot.press("$", "p")
            self.assertIn("fresh clipboard", editor.text[-16:])

    @patch("tui.vim_text_area.paste_from_system_clipboard", return_value="from host\n")
    async def test_empty_register_falls_back_to_the_system_clipboard_as_lines(self, _clipboard):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "first", (0, 0))
            await pilot.press("escape", "p")
            self.assertEqual(editor.text, "first\nfrom host")

    async def test_failed_native_clipboard_keeps_the_register_and_reports_status(self):
        app = EditorHarness()
        app.copy_ok = False
        async with app.run_test() as pilot:
            editor = await self.load(app, "kept", (0, 0))
            await pilot.press("escape", "d", "d")
            self.assertEqual(editor.yank_register, "kept\n")
            self.assertEqual(editor.text, "")
            self.assertTrue(any("register" in status for status in app.statuses))
            await pilot.press("p")
            self.assertEqual(editor.text, "\nkept")

    async def test_unicode_text_cuts_and_pastes_intact(self):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "héllo wörld ✓\n日本語", (0, 0))
            await pilot.press("escape", "d", "d")
            self.assertEqual(editor.yank_register, "héllo wörld ✓\n")
            await pilot.press("p")
            self.assertEqual(editor.text, "日本語\nhéllo wörld ✓")

    async def test_undo_and_redo_work_in_normal_mode_and_ctrl_r_is_redo(self):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "one\ntwo", (0, 0))
            await pilot.press("escape", "d", "d")
            self.assertEqual(editor.text, "two")
            await pilot.press("u")
            self.assertEqual(editor.text, "one\ntwo")
            await pilot.press("ctrl+r")
            self.assertEqual(editor.text, "two")

    async def test_ctrl_c_and_ctrl_x_interrupt_instead_of_copying_or_cutting(self):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "do not cut", (0, 0))
            editor.select_all()
            await pilot.press("ctrl+c")
            await pilot.press("ctrl+x")
            self.assertEqual(app.interrupts, 2)
            self.assertEqual(editor.text, "do not cut")
            self.assertEqual(app.copied, [])

    async def test_escape_clears_pending_operator_register_prefix_and_count(self):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "abc", (0, 0))
            await pilot.press("escape", "3", "d", "quotation_mark", "escape")
            self.assertFalse(editor.operator_pending.is_pending())
            self.assertFalse(editor.count_handler.has_count())
            self.assertFalse(editor._register_prefix_pending)
            await pilot.press("x")
            self.assertEqual(editor.text, "bc")

    async def test_read_only_surface_cannot_be_edited_by_vim_keys(self):
        app = EditorHarness()
        async with app.run_test() as pilot:
            history = app.query_one("#history", TextArea)
            history.focus()
            await pilot.press("d", "d", "p", "c", "u")
            self.assertEqual(history.text, "read only text")

    async def test_mode_label_tracks_insert_normal_visual_and_line_modes(self):
        app = EditorHarness()
        async with app.run_test() as pilot:
            editor = await self.load(app, "abc", (0, 0))
            self.assertEqual(editor.mode_label, "INSERT")
            await pilot.press("escape")
            self.assertEqual(editor.mode_label, "NORMAL")
            await pilot.press("v")
            self.assertEqual(editor.mode_label, "VISUAL")
            await pilot.press("escape", "V")
            self.assertEqual(editor.mode_label, "V-LINE")


if __name__ == "__main__":
    unittest.main()
