"""The Daedalus prompt's incremental Vim editing adapter.

This extends the installed ``vimkeys_input.VimTextArea`` rather than replacing
it. The dependency already provides Insert/Normal/Visual modes, ``hjkl``,
word and line motions, counts, same-line operator motions, ``x``, ``p``/``P``,
undo/redo, and visual yank/delete/change. This adapter completes the pieces
the prompt needs: a register that remembers whether it holds whole lines,
Vim placement for line-wise paste (including the last line), counted ``dd``
/``yy``/``cc``, visual-line operators, explicit ``"+`` system-register
commands, clipboard mirroring for every cut and yank, and main-screen key
routing for ``Ctrl+C``/``Ctrl+X`` (interrupt) and ``Ctrl+R`` (redo).
"""

from __future__ import annotations

from rich.style import Style
from textual import events
from textual.message import Message
from textual.widgets.text_area import Selection

from vimkeys_input import VimMode, VimTextArea

from .clipboard import paste_from_system_clipboard

# Textual names `$` `dollar_sign`; vimkeys-input looks for `dollar`.
_LINE_END_KEYS = {"dollar", "dollar_sign", "$"}
_REGISTER_PREFIX_KEY = "quotation_mark"
_SYSTEM_REGISTER_KEY = "plus"
_INTERRUPT_KEYS = {"ctrl+c", "ctrl+x"}
# Keys that send the prompt rather than edit it, in the order the shortcuts
# menu lists them. Enter alone always inserts a newline, so a terminal has to
# report Enter's modifiers -- which means the Kitty keyboard protocol -- for
# either of these to arrive at all.
SUBMIT_KEYS = ("shift+enter", "ctrl+enter")

MODE_LABELS = {
    VimMode.INSERT: "INSERT",
    VimMode.COMMAND: "NORMAL",
    VimMode.VISUAL: "VISUAL",
    VimMode.VISUAL_LINE: "V-LINE",
}


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

    class ClipboardStatus(Message):
        """Posted when a register update could or could not reach the clipboard."""

        def __init__(self, message: str, succeeded: bool) -> None:
            super().__init__()
            self.message = message
            self.succeeded = succeeded

    def __init__(self, *args, **kwargs) -> None:
        # Register state must exist before VimTextArea.__init__ assigns
        # ``yank_register`` through the property below.
        self._yank_register = ""
        self._register_linewise = False
        self._register_generation = 0
        self._register_prefix_pending = False
        self._selected_register: str | None = None
        self.clipboard_status: str | None = None
        # Visual modes keep their own anchor and cursor: assigning a TextArea
        # selection moves the widget cursor to the selection end, which is
        # one past the highlighted character in Vim's inclusive model.
        self._visual_anchor: tuple[int, int] = (0, 0)
        self._visual_cursor: tuple[int, int] = (0, 0)
        self._visual_line_row = 0
        # TextArea's active-line highlight uses the dark `$boost` background.
        # It is applied before the cursor style, so a transparent cursor still
        # leaves a dark cell behind the character it is meant to underline.
        kwargs.setdefault("highlight_cursor_line", False)
        super().__init__(*args, **kwargs)
        # Keep the cursor visible continuously; blinking is distracting while
        # composing a prompt.
        self.cursor_blink = False

    # ------------------------------------------------------------------
    # Register
    # ------------------------------------------------------------------

    @property
    def yank_register(self) -> str:
        return self._yank_register

    @yank_register.setter
    def yank_register(self, value: str) -> None:
        # Every cut and yank goes through here. The generation counter, not
        # the text, decides whether the clipboard is refreshed, so yanking
        # identical text twice still replaces an externally changed clipboard.
        self._yank_register = value or ""
        self._register_generation += 1
        self._register_linewise = False

    @property
    def register_linewise(self) -> bool:
        """Whether the register holds whole lines (``dd``/``yy``/visual-line)."""
        return self._register_linewise

    @property
    def mode_label(self) -> str:
        """Compact Insert/Normal/Visual label for the status area."""
        return MODE_LABELS.get(self.vim_mode, str(self.vim_mode))

    def _set_register(self, text: str, *, linewise: bool) -> None:
        self.yank_register = text
        self._register_linewise = linewise

    def _load_system_register(self) -> bool:
        """Fill the register from the host clipboard without echoing it back."""
        clipboard_text = paste_from_system_clipboard()
        if not clipboard_text:
            self.clipboard_status = "Clipboard unavailable or empty"
            return False
        # Bypass the property so the generation counter does not mirror the
        # freshly pasted clipboard back onto itself.
        self._yank_register = clipboard_text
        self._register_linewise = clipboard_text.endswith("\n")
        return True

    def _mirror_register(self) -> None:
        text = self._yank_register
        if not text:
            return
        app = getattr(self, "app", None)
        copier = getattr(app, "copy_to_clipboard", None)
        if copier is None:
            return
        try:
            succeeded = copier(text)
        except Exception:
            succeeded = False
        if succeeded is False:
            self.clipboard_status = "Clipboard unavailable; text kept in the Vim register"
            self.post_message(self.ClipboardStatus(self.clipboard_status, False))
        else:
            self.clipboard_status = None
            self.post_message(self.ClipboardStatus("Copied", True))

    # ------------------------------------------------------------------
    # Cursor appearance
    # ------------------------------------------------------------------

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
        self._clear_register_selection()
        super()._enter_insert_mode()

    def _enter_command_mode(self) -> None:
        self.operator_pending.clear()
        self._clear_register_selection()
        super()._enter_command_mode()

    def _clear_register_selection(self) -> None:
        self._register_prefix_pending = False
        self._selected_register = None

    def _update_mode_display(self) -> None:
        super()._update_mode_display()
        self._sync_cursor_classes()

    def _sync_cursor_classes(self) -> None:
        """Expose operator-pending so the caret can become an underline."""
        self.set_class(self.operator_pending.is_pending(), "operator-pending")

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

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

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

    def _document_characters(self) -> list[tuple[str, tuple[int, int]]]:
        lines = [str(self.get_line(row)) for row in range(self.document.line_count)]
        characters: list[tuple[str, tuple[int, int]]] = []
        for row, line in enumerate(lines):
            characters.extend((character, (row, column)) for column, character in enumerate(line))
            if row < len(lines) - 1:
                characters.append(("\n", (row, len(line))))
        return characters

    @staticmethod
    def _character_kind(character: str) -> str | None:
        if character.isspace():
            return None
        return "word" if character.isalnum() or character == "_" else "punctuation"

    def _word_forward_location(self, start: tuple[int, int]) -> tuple[int, int]:
        """Return where Vim's ``w`` lands from ``start``: the next word's first character."""
        characters = self._document_characters()
        lines_count = self.document.line_count
        index = sum(len(str(self.get_line(row))) + 1 for row in range(start[0])) + start[1]
        if index >= len(characters):
            last_row = lines_count - 1
            return (last_row, len(str(self.get_line(last_row))))
        current_kind = self._character_kind(characters[index][0])
        if current_kind is not None:
            while index < len(characters) and self._character_kind(characters[index][0]) == current_kind:
                index += 1
        while index < len(characters) and self._character_kind(characters[index][0]) is None:
            index += 1
        if index >= len(characters):
            last_row = lines_count - 1
            return (last_row, len(str(self.get_line(last_row))))
        return characters[index][1]

    def nav_word_forward(self) -> None:
        """Move to the start of the next word (``w``), crossing lines."""
        self.cursor_location = self._word_forward_location(self.cursor_location)

    def move_cursor_to_end(self) -> None:
        """Place the cursor after the last character so text can be appended."""
        last_row = max(0, self.document.line_count - 1)
        self.cursor_location = (last_row, len(str(self.get_line(last_row))))

    # ------------------------------------------------------------------
    # Key routing
    # ------------------------------------------------------------------

    def _handle_insert_mode(self, event: events.Key) -> None:
        """Keep Enter as a newline; the modified Enters remain the submit keys."""
        if event.key == "enter":
            return
        super()._handle_insert_mode(event)

    def on_key(self, event: events.Key) -> None:
        """Route app shortcuts first, then Vim commands, then mirror the register."""
        app = self.app
        if event.key in SUBMIT_KEYS:
            # Send from any Vim mode. The app also binds these keys, but the
            # focused prompt sees them first, and the Vim router has no reason
            # to hold a key it does not implement.
            submit = getattr(app, "action_submit_prompt", None)
            if submit is not None:
                submit()
            event.stop()
            event.prevent_default()
            return
        if event.key == "ctrl+k":
            # VimTextArea handles several Ctrl keys itself, so route the
            # application's shortcut before its mode-specific processing.
            app.action_show_shortcuts()
            event.stop()
            return
        if event.key in _INTERRUPT_KEYS and len(app.screen_stack) == 1:
            # Ctrl+C never copies or quits on the main screen: it interrupts
            # the selected task's run. Stop the event here so TextArea's own
            # copy/cut bindings cannot consume it.
            interrupt = getattr(app, "action_interrupt_task", None)
            if interrupt is not None:
                interrupt()
            event.stop()
            return
        if event.key == "ctrl+r" and not self.read_only:
            # A focused editable prompt means Vim redo; Resume stays reachable
            # through its button and the app binding outside the editor.
            self.edit_redo()
            event.stop()
            return
        if event.key == "tab" and len(app.screen_stack) == 1:
            # The prompt owns keyboard events while focused, so route the
            # main-screen mode toggle before VimTextArea treats Tab as input.
            app.action_toggle_plan_mode()
            event.stop()
            return
        if self.vim_mode == VimMode.INSERT and event.is_printable:
            # Textual's TextArea._on_key runs after this handler and owns
            # native printable insertion. Do not pass ordinary prompt text
            # through the Vim router first; that router intentionally has no
            # insert-mode implementation for printable keys.
            return
        previous_generation = self._register_generation
        if event.key == "escape":
            super().on_key(event)
            # Vim mode transitions do not clear TextArea's native selection.
            # Collapse it so Escape reliably stops all highlighting.
            self.selection = Selection.cursor(self.cursor_location)
            self.count_handler.clear()
        elif self.vim_mode == VimMode.VISUAL_LINE:
            self._handle_visual_line_mode(event)
        else:
            super().on_key(event)
        if self._register_generation != previous_generation and self._yank_register:
            self._mirror_register()

    def _handle_register_prefix(self, event: events.Key) -> bool:
        """Consume ``"`` and the register name that follows it (only ``+`` is special)."""
        if self._register_prefix_pending:
            self._register_prefix_pending = False
            self._selected_register = "+" if event.key == _SYSTEM_REGISTER_KEY else None
            event.prevent_default()
            return True
        if event.key == _REGISTER_PREFIX_KEY:
            self._register_prefix_pending = True
            event.prevent_default()
            return True
        return False

    def _handle_command_mode(self, event: events.Key) -> None:
        """Add Daedalus prompt commands that the dependency does not provide."""
        if self._handle_register_prefix(event):
            return
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
        if event.key in {"p", "P"}:
            self._paste_from_selected_register(after=event.key == "p")
            event.prevent_default()
            self._sync_cursor_classes()
            return
        super()._handle_command_mode(event)
        if not self.operator_pending.is_pending() and self.pending_command is None:
            # A completed command consumes the `"+` prefix.
            self._selected_register = None
        self._sync_cursor_classes()

    def _enter_visual_mode(self) -> None:
        self.vim_mode = VimMode.VISUAL
        self._visual_anchor = self.cursor_location
        self._visual_cursor = self.cursor_location
        self.visual_start = self._visual_anchor
        self._apply_visual_selection()
        self._update_mode_display()

    def _apply_visual_selection(self) -> None:
        """Highlight anchor..cursor inclusively, whichever order they are in."""
        anchor, cursor = self._visual_anchor, self._visual_cursor
        start, end = (anchor, cursor) if anchor <= cursor else (cursor, anchor)
        line = str(self.get_line(end[0]))
        end = (end[0], min(len(line), end[1] + 1))
        self.selection = Selection(start=start, end=end)

    def _visual_move(self, mover, count: int = 1) -> None:
        self.selection = Selection.cursor(self._visual_cursor)
        for _ in range(max(1, count)):
            mover()
        self._visual_cursor = self.cursor_location
        self._apply_visual_selection()

    def _handle_visual_mode(self, event: events.Key) -> None:
        if self._handle_register_prefix(event):
            return
        key = "dollar" if event.key in _LINE_END_KEYS else event.key
        if key.isdigit() and (key != "0" or self.count_handler.has_count()):
            self.count_handler.add_digit(key)
            event.prevent_default()
            return
        count = self.count_handler.get_count()
        movers = {
            "h": self.nav_left,
            "j": self.nav_down,
            "k": self.nav_up,
            "l": self.nav_right,
            "w": self.nav_word_forward,
            "b": self.nav_word_backward,
            "e": self.nav_word_end,
            "0": self.nav_line_start,
            "dollar": self.nav_line_end,
            "G": self.nav_document_end,
        }
        if self.pending_command == "g":
            self.pending_command = None
            if key == "g":
                self._visual_move(self.nav_document_start)
            event.prevent_default()
            return
        if key == "g":
            self.pending_command = "g"
            event.prevent_default()
            return
        if key in movers:
            self._visual_move(movers[key], count)
            self.count_handler.clear()
            event.prevent_default()
            return
        selection = self.selection
        start, end = selection.start, selection.end
        if start > end:
            start, end = end, start
        if key == "y":
            self._set_register(self.get_text_range(start, end), linewise=False)
            self._enter_command_mode()
            self.cursor_location = start
        elif key in {"d", "x", "c"}:
            self._set_register(self.get_text_range(start, end), linewise=False)
            self.replace("", start, end)
            self.cursor_location = start
            if key == "c":
                self._enter_insert_mode()
            else:
                self._enter_command_mode()
        elif key in {"v", "escape"}:
            self._enter_command_mode()
            self.cursor_location = self._visual_cursor
        else:
            self.count_handler.clear()
            event.prevent_default()
            return
        self.count_handler.clear()
        self._selected_register = None
        event.prevent_default()

    # ------------------------------------------------------------------
    # Operators
    # ------------------------------------------------------------------

    def _handle_operator_motion(self, event: events.Key) -> bool:
        """Line-wise operators with counts and multi-line ``j``/``k`` motions."""
        key = event.key
        if key in _LINE_END_KEYS:
            key = "dollar"
            event.key = "dollar"
        operator = self.operator_pending.get_operator()
        if key == operator and operator in {"d", "y", "c"}:
            count = self.operator_pending.get_total_count()
            self.operator_pending.clear()
            return self._execute_line_operator(operator, count)
        if key == "w" and operator in {"d", "y", "c"}:
            count = self.operator_pending.get_total_count()
            self.operator_pending.clear()
            start = self.cursor_location
            end = start
            for _ in range(max(1, count)):
                end = self._word_forward_location(end)
            if end[0] != start[0]:
                # Vim's dw/cw/yw never cross the line break.
                end = (start[0], len(str(self.get_line(start[0]))))
            if end == start:
                return False
            text = self.get_text_range(start, end)
            self._set_register(text, linewise=False)
            if operator == "y":
                self.cursor_location = start
                return True
            self.replace("", start, end)
            self.cursor_location = start
            if operator == "c":
                self._enter_insert_mode()
            return True
        if key in {"j", "k"} and operator in {"d", "y", "c"}:
            count = self.operator_pending.get_total_count()
            self.operator_pending.clear()
            row = self.cursor_location[0]
            if key == "j":
                start_row, end_row = row, min(self.document.line_count - 1, row + count)
            else:
                start_row, end_row = max(0, row - count), row
            self.cursor_location = (start_row, 0)
            return self._execute_line_operator(operator, end_row - start_row + 1)
        return super()._handle_operator_motion(event)

    def _execute_line_operator(self, operator: str, count: int) -> bool:
        """Apply ``dd``/``yy``/``cc`` to ``count`` lines from the cursor line."""
        row, column = self.cursor_location
        line_count = self.document.line_count
        last_row = min(line_count - 1, row + max(1, count) - 1)
        lines = [str(self.get_line(index)) for index in range(row, last_row + 1)]
        text = "\n".join(lines) + "\n"
        if operator == "y":
            self._set_register(text, linewise=True)
            self.cursor_location = (row, column)
            return True
        self._set_register(text, linewise=True)
        self._delete_line_range(row, last_row)
        if operator == "c":
            self._open_empty_line_at(row)
            self._enter_insert_mode()
        return True

    def _open_empty_line_at(self, row: int) -> None:
        """After deleting lines at ``row``, leave one empty line there to type into."""
        line_count = self.document.line_count
        if line_count == 1 and not str(self.get_line(0)):
            self.cursor_location = (0, 0)
            return
        if row >= line_count:
            # The deleted lines were at the end: open the new line below the
            # last remaining one instead of above it.
            last_row = line_count - 1
            self.cursor_location = (last_row, len(str(self.get_line(last_row))))
            self.insert("\n")
            self.cursor_location = (last_row + 1, 0)
            return
        self.cursor_location = (row, 0)
        self.insert("\n")
        self.cursor_location = (row, 0)

    def _delete_line_range(self, first_row: int, last_row: int) -> None:
        """Delete whole lines including their line breaks, Vim style."""
        line_count = self.document.line_count
        if last_row < line_count - 1:
            start = (first_row, 0)
            end = (last_row + 1, 0)
        elif first_row > 0:
            start = (first_row - 1, len(str(self.get_line(first_row - 1))))
            end = (last_row, len(str(self.get_line(last_row))))
        else:
            start = (0, 0)
            end = (last_row, len(str(self.get_line(last_row))))
        self.replace("", start, end)
        target_row = min(first_row, max(0, self.document.line_count - 1))
        self.cursor_location = (target_row, 0)

    def edit_delete_line(self) -> None:
        """``dd`` for one line, keeping the register line-wise."""
        self._execute_line_operator("d", 1)

    def edit_yank_line(self) -> None:
        """``yy`` for one line, keeping the register line-wise."""
        self._execute_line_operator("y", 1)

    def edit_change_line(self) -> None:
        self._execute_line_operator("c", 1)

    # ------------------------------------------------------------------
    # Paste
    # ------------------------------------------------------------------

    def _paste_from_selected_register(self, *, after: bool) -> None:
        if self._selected_register == "+":
            self._selected_register = None
            if not self._load_system_register():
                return
        elif not self._yank_register and not self._load_system_register():
            return
        text = self._yank_register
        if not text:
            return
        if self._register_linewise:
            self._paste_lines(text, after=after)
        elif after:
            row, column = self.cursor_location
            line = str(self.get_line(row))
            location = (row, min(len(line), column + 1)) if line else (row, 0)
            self.insert(text, location)
        else:
            self.insert(text, self.cursor_location)

    def _paste_lines(self, text: str, *, after: bool) -> None:
        body = text.rstrip("\n")
        row, _ = self.cursor_location
        if after:
            line_end = (row, len(str(self.get_line(row))))
            self.insert("\n" + body, line_end)
            self.cursor_location = (row + 1, 0)
        else:
            self.insert(body + "\n", (row, 0))
            self.cursor_location = (row, 0)

    def edit_paste_after(self) -> None:
        """Paste Vim's register after the cursor, falling back to the system clipboard."""
        self._paste_from_selected_register(after=True)

    def edit_paste_before(self) -> None:
        """Paste before the cursor, including from the system clipboard."""
        self._paste_from_selected_register(after=False)

    # ------------------------------------------------------------------
    # Visual-line mode
    # ------------------------------------------------------------------

    def _enter_visual_line_mode(self) -> None:
        """Select the current line and enter Vim visual-line mode."""
        self.vim_mode = VimMode.VISUAL_LINE
        row = self.cursor_location[0]
        self.visual_start = (row, 0)
        self._visual_line_row = row
        self._set_visual_line_selection()
        self._update_mode_display()

    def _visual_line_rows(self) -> tuple[int, int]:
        start_row = self.visual_start[0] if self.visual_start else self._visual_line_row
        return min(start_row, self._visual_line_row), max(start_row, self._visual_line_row)

    def _set_visual_line_selection(self) -> None:
        """Select every character in the lines between the start and cursor."""
        first_row, last_row = self._visual_line_rows()
        if last_row < self.document.line_count - 1:
            end = (last_row + 1, 0)
        else:
            end = (last_row, len(str(self.get_line(last_row))))
        self.selection = Selection(start=(first_row, 0), end=end)

    def _visual_line_text(self) -> str:
        first_row, last_row = self._visual_line_rows()
        return "\n".join(str(self.get_line(row)) for row in range(first_row, last_row + 1)) + "\n"

    def _handle_visual_line_mode(self, event: events.Key) -> None:
        """Handle movement and operators while whole lines are selected."""
        if self._handle_register_prefix(event):
            return
        key = event.key
        if key.isdigit() and (key != "0" or self.count_handler.has_count()):
            self.count_handler.add_digit(key)
            event.prevent_default()
            return
        count = self.count_handler.get_count()
        last_row = self.document.line_count - 1
        if self.pending_command == "g" and key == "g":
            self._visual_line_row = 0
            self.pending_command = None
        elif key == "j":
            self._visual_line_row = min(last_row, self._visual_line_row + count)
        elif key == "k":
            self._visual_line_row = max(0, self._visual_line_row - count)
        elif key == "G":
            self._visual_line_row = last_row
        elif key == "g":
            self.pending_command = "g"
            event.prevent_default()
            return
        elif key == "y":
            self._set_register(self._visual_line_text(), linewise=True)
            self.cursor_location = (self._visual_line_rows()[0], 0)
            self._enter_command_mode()
        elif key in {"d", "x"}:
            first_row, last_row = self._visual_line_rows()
            self._set_register(self._visual_line_text(), linewise=True)
            self._delete_line_range(first_row, last_row)
            self._enter_command_mode()
        elif key == "c":
            first_row, last_row = self._visual_line_rows()
            self._set_register(self._visual_line_text(), linewise=True)
            self._delete_line_range(first_row, last_row)
            self._open_empty_line_at(first_row)
            self._enter_insert_mode()
        elif key in {"V", "escape"}:
            self._enter_command_mode()
        else:
            event.prevent_default()
            return
        self.count_handler.clear()
        if self.vim_mode == VimMode.VISUAL_LINE:
            self._set_visual_line_selection()
        event.prevent_default()


__all__ = ["DaedalusVimTextArea", "MODE_LABELS", "SUBMIT_KEYS", "VimMode"]
