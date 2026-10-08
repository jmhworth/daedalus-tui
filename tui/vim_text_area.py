"""The Daedalus prompt's incremental Vim editing adapter."""

from __future__ import annotations

from rich.style import Style
from textual import events
from textual.widgets.text_area import Selection

from vimkeys_input import VimMode, VimTextArea

from .clipboard import paste_from_system_clipboard

# Textual names `$` `dollar_sign`; vimkeys-input looks for `dollar`.
_LINE_END_KEYS = {"dollar", "dollar_sign", "$"}


class DaedalusVimTextArea(VimTextArea):
    """VimTextArea with multiline prompt behavior and system clipboard sync."""

    DEFAULT_CSS = """
    DaedalusVimTextArea.insert-mode .text-area--cursor {
        /* The native cursor styles the character cell itself. Keep that
           character visible instead of replacing it with a caret glyph. */
        color: $text !important;
        background: transparent !important;
        text-style: underline !important;
    }

    DaedalusVimTextArea.operator-pending .text-area--cursor {
        color: $text !important;
        background: transparent !important;
        text-style: underline !important;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        # TextArea's active-line highlight uses the dark `$boost` background.
        # It is applied before the cursor style, so a transparent cursor still
        # leaves a dark cell behind the character it is meant to underline.
        kwargs.setdefault("highlight_cursor_line", False)
        super().__init__(*args, **kwargs)
        # Keep the cursor visible continuously; blinking is distracting while
        # composing a prompt.
        self.cursor_blink = False

    @property
    def cursor_shape(self) -> str:
        """Return bar, underline, or block for the current Vim state."""
        operator_pending = getattr(self, "operator_pending", None)
        if operator_pending is not None and operator_pending.is_pending():
            return "underline"
        vim_mode = getattr(self, "vim_mode", VimMode.INSERT)
        if vim_mode == VimMode.INSERT:
            return "bar"
        return "block"

    @property
    def _draw_cursor(self) -> bool:
        # Let Textual style the actual character at the insertion point. A
        # separate bar glyph replaces that character and makes it unreadable.
        return super()._draw_cursor

    def enter_insert_mode(self) -> None:
        """Return to Insert mode after programmatic prompt operations."""
        self._enter_insert_mode()

    def _enter_insert_mode(self) -> None:
        self.operator_pending.clear()
        super()._enter_insert_mode()

    def _enter_command_mode(self) -> None:
        self.operator_pending.clear()
        super()._enter_command_mode()

    def _update_mode_display(self) -> None:
        super()._update_mode_display()
        self._sync_cursor_classes()

    def _sync_cursor_classes(self) -> None:
        """Expose operator-pending so the caret can become an underline."""
        self.set_class(self.operator_pending.is_pending(), "operator-pending")

    def nav_word_end(self) -> None:
        """Move to the end of the current word, or the next word when needed."""
        lines = [str(self.get_line(row)) for row in range(self.document.line_count)]
        characters: list[tuple[str, tuple[int, int]]] = []
        for row, line in enumerate(lines):
            characters.extend((character, (row, column)) for column, character in enumerate(line))
            if row < len(lines) - 1:
                characters.append(("\n", (row, len(line))))

        row, column = self.cursor_location
        index = sum(len(line) + 1 for line in lines[:row]) + column
        if index >= len(characters):
            return

        def kind(character: str) -> str | None:
            if character.isspace():
                return None
            return "word" if character.isalnum() or character == "_" else "punctuation"

        current_kind = kind(characters[index][0])
        if current_kind is not None:
            end = index
            while end + 1 < len(characters) and kind(characters[end + 1][0]) == current_kind:
                end += 1
            if end > index:
                self.cursor_location = characters[end][1]
                return
            index = end + 1

        while index < len(characters) and kind(characters[index][0]) is None:
            index += 1
        if index >= len(characters):
            return

        target_kind = kind(characters[index][0])
        end = index
        while end + 1 < len(characters) and kind(characters[end + 1][0]) == target_kind:
            end += 1
        self.cursor_location = characters[end][1]

    def on_key(self, event: events.Key) -> None:
        """Route visual-line mode and mirror new yanks to the host clipboard."""
        if event.key == "enter":
            self.app.action_submit_prompt()
            event.stop()
            event.prevent_default()
            return
        if event.key == "shift+enter" and self.vim_mode == VimMode.INSERT:
            self.insert("\n")
            event.stop()
            event.prevent_default()
            return
        if event.key == "ctrl+k":
            # VimTextArea handles several Ctrl keys itself, so route the
            # application's shortcut before its mode-specific processing.
            self.app.action_show_command_menu()
            event.stop()
            return
        if event.key == "tab" and len(self.app.screen_stack) == 1:
            # The prompt owns keyboard events while focused, so route the
            # main-screen mode toggle before VimTextArea treats Tab as input.
            self.app.action_toggle_plan_mode()
            event.stop()
            return
        if self.vim_mode == VimMode.INSERT and event.is_printable:
            # Textual's TextArea._on_key runs after this handler and owns
            # native printable insertion. Do not pass ordinary prompt text
            # through the Vim router first; that router intentionally has no
            # insert-mode implementation for printable keys.
            return
        previous_register = self.yank_register
        if event.key == "escape":
            super().on_key(event)
            # Vim mode transitions do not clear TextArea's native selection.
            # Collapse it so Escape reliably stops all highlighting.
            self.selection = Selection.cursor(self.cursor_location)
        elif self.vim_mode == VimMode.VISUAL_LINE:
            self._handle_visual_line_mode(event)
        else:
            super().on_key(event)
        if self.yank_register and self.yank_register != previous_register:
            self.app.copy_to_clipboard(self.yank_register)

    def edit_paste_after(self) -> None:
        """Paste Vim's register, falling back to the system clipboard."""
        if not self.yank_register:
            clipboard_text = paste_from_system_clipboard()
            if clipboard_text:
                self.yank_register = clipboard_text
        super().edit_paste_after()

    def edit_paste_before(self) -> None:
        """Paste before the cursor, including from the system clipboard."""
        if not self.yank_register:
            clipboard_text = paste_from_system_clipboard()
            if clipboard_text:
                self.yank_register = clipboard_text
        super().edit_paste_before()

    def _handle_command_mode(self, event: events.Key) -> None:
        """Add Daedalus prompt commands that the dependency does not provide."""
        if event.key == "V":
            self._enter_visual_line_mode()
            event.prevent_default()
            return
        if event.key == "space":
            self.nav_right()
            event.prevent_default()
            return
        if event.key in _LINE_END_KEYS:
            # Textual reports `$` as dollar_sign; vimkeys-input listens for dollar.
            event.key = "dollar"
        super()._handle_command_mode(event)
        self._sync_cursor_classes()

    def render_line(self, y: int):
        """Render the native cursor without a background in visible modes."""
        if self.cursor_shape in {"bar", "underline"}:
            # TextArea copies the component CSS into its theme before it
            # renders. Override that copied style here because the built-in
            # dark theme otherwise restores its opaque cursor background.
            # Leaving bgcolor unset is important: Rich's "default" color
            # resets the cell to the terminal default instead of inheriting
            # the prompt's background, which creates a dark box over the
            # character under the caret.
            self._theme.cursor_style = Style(underline=True)
        return super().render_line(y)

    def _enter_visual_line_mode(self) -> None:
        """Select the current line and enter Vim visual-line mode."""
        self.vim_mode = VimMode.VISUAL_LINE
        self.visual_start = self.cursor_location
        self._set_visual_line_selection()
        self._update_mode_display()

    def _set_visual_line_selection(self) -> None:
        """Select every character in the lines between the start and cursor."""
        start_row = self.visual_start[0] if self.visual_start else self.cursor_location[0]
        cursor_row = self.cursor_location[0]
        first_row = min(start_row, cursor_row)
        last_row = max(start_row, cursor_row)
        if last_row < self.document.line_count - 1:
            end = (last_row + 1, 0)
        else:
            end = (last_row, len(str(self.get_line(last_row))))
        self.selection = Selection(start=(first_row, 0), end=end)

    def _handle_visual_line_mode(self, event: events.Key) -> None:
        """Handle movement and operators while whole lines are selected."""
        key = event.key
        if self.pending_command == "g" and key == "g":
            self.nav_document_start()
            self.pending_command = None
        elif key == "j":
            self.nav_down()
        elif key == "k":
            self.nav_up()
        elif key == "G":
            self.nav_document_end()
        elif key == "g":
            self.pending_command = "g"
            event.prevent_default()
            return
        elif key == "y":
            self.visual_yank()
            self._enter_command_mode()
        elif key in {"d", "x"}:
            self.visual_delete()
            self._enter_command_mode()
        elif key == "c":
            self.visual_change()
        elif key == "V":
            self._enter_command_mode()
        else:
            event.prevent_default()
            return
        if self.vim_mode == VimMode.VISUAL_LINE:
            self._set_visual_line_selection()
        event.prevent_default()


__all__ = ["DaedalusVimTextArea", "VimMode"]
