"""Selectable transcript rendering with semantic assistant-message emphasis."""

from __future__ import annotations

import re

from rich.style import Style
from rich.text import Text
from rich.cells import cell_len, chop_cells
from textual import events
from textual.strip import Strip
from textual.widgets import Log


class TranscriptLog(Log):
    """A selectable log that can emphasize a task's final assistant message.

    ``Log`` deliberately stores plain strings, so its normal CSS color applies
    to every line. Keeping the line tone separately lets the transcript retain
    Log's native selection behavior while giving the final task summary a
    brighter color.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._line_tones: dict[int, str] = {}
        self._final_color = None
        self._user_color = None
        self._messages: list[tuple[str, bool, str | None]] = []
        self._wrapped_width: int | None = None

    @property
    def line_tones(self) -> tuple[str, ...]:
        """Return the tone assigned to each rendered transcript line."""
        return tuple(self._line_tones.get(index, "generic") for index in range(len(self._lines)))

    def clear(self) -> "TranscriptLog":
        self._line_tones.clear()
        self._messages.clear()
        self._wrapped_width = None
        return super().clear()

    def on_resize(self, event: events.Resize) -> None:
        """Reflow stored messages when the output box changes width."""
        if self._messages:
            self._rebuild_lines(scroll_end=self.auto_scroll)

    def render(self):
        """Reflow when styling changes the width without sending Resize."""
        if self._messages and self._content_width() != self._wrapped_width:
            self._rebuild_lines(scroll_end=self.auto_scroll)
        return super().render()

    def set_final_color(self, color) -> None:
        """Use the prompt's normal text color for the final transcript tone."""
        self._final_color = color
        self.invalidate_render_cache()

    def set_user_color(self, color) -> None:
        """Color used for the user's own submitted turns and separators."""
        self._user_color = color
        self.invalidate_render_cache()

    def invalidate_render_cache(self) -> None:
        """Re-render lines after a surrounding widget's color state changes."""
        self._render_line_cache.clear()
        self.refresh()

    def write_message(
        self, message: str, *, final: bool = False, tone: str | None = None
    ) -> "TranscriptLog":
        """Append one message and assign its semantic tone.

        ``tone`` may be ``"user"`` for the user's own submitted turns and
        separators; otherwise ``final`` selects the brighter final tone.
        """
        if not message:
            return self
        self._messages.append((message, final, tone))
        self._rebuild_lines(scroll_end=self.auto_scroll)
        return self

    @property
    def messages(self) -> tuple[str, ...]:
        """Return the logical (unwrapped) messages in order."""
        return tuple(message for message, _final, _tone in self._messages)

    def _rebuild_lines(self, *, scroll_end: bool) -> None:
        """Render logical messages as wrapped, selectable Log lines."""
        content_width = self._content_width()
        # Keep one cell clear at the right edge so the last visible glyph does
        # not sit against the border or trigger a horizontal scroll.
        width = max(0, content_width - 1)
        rendered_lines: list[str] = []
        tones: list[str] = []
        for message_index, (message, final, explicit_tone) in enumerate(self._messages):
            if message_index:
                # Keep one complete blank line between streamed messages.
                rendered_lines.append("")
                tones.append("generic")

            tone = explicit_tone or ("final" if final else "generic")
            for source_line in message.split("\n"):
                wrapped_lines = self._wrap_line(
                    source_line, width, allow_right_edge_buffer=False
                )
                rendered_lines.extend(wrapped_lines)
                tones.extend([tone] * len(wrapped_lines))

        block = "\n".join(rendered_lines)
        if block:
            # Log keeps a trailing empty entry as the insertion point for its
            # next write; it is not included in line_count.
            block += "\n"
        super().clear()
        super().write(block, scroll_end=scroll_end)
        self._line_tones = {
            line_number: tone for line_number, tone in enumerate(tones)
        }
        self._wrapped_width = content_width
        self._render_line_cache.clear()

    def _content_width(self) -> int:
        """Return the width available for transcript text inside the Log."""
        # An explicit cell width is available as soon as the style changes,
        # while ``content_region`` may still describe the previous layout
        # until Textual processes the pending layout pass. Use that value so
        # cached lines reflow during the same render cycle as a direct width
        # update.
        style_width = self.styles.width
        if style_width is not None and style_width.is_cells:
            width = style_width.cells or 0
            if self.styles.box_sizing == "border-box":
                width -= self.styles.gutter.width
            return max(0, width)

        # ``size.width`` includes the output border and padding. Wrapping to
        # that outer width lets the final characters run into the box chrome,
        # so use Textual's content region for the actual text width.
        content_region = self.content_region
        width = content_region.width
        if width <= 0:
            # Messages can arrive before the first layout pass. Keep them
            # temporarily unwrapped; the first resize/layout event will
            # rebuild them using the content region.
            width = self.size.width - self.styles.gutter.width
        return max(0, width)

    def _wrap_line(
        self, line: str, width: int, *, allow_right_edge_buffer: bool = True
    ) -> list[str]:
        """Wrap one logical line at word boundaries when the width permits."""
        processed_line = self._process_line(line)
        if not processed_line or width <= 0 or cell_len(processed_line) <= width:
            return [processed_line]
        if not processed_line.strip():
            return chop_cells(processed_line, width) or [""]

        wrapped: list[str] = []
        current = ""
        tokens = re.findall(r"\s+|\S+", processed_line)
        for token_index, token in enumerate(tokens):
            if token.isspace():
                current += token
                continue

            candidate = current + token
            is_last_word = not any(
                not following.isspace() for following in tokens[token_index + 1:]
            )
            word_width = width + 1 if allow_right_edge_buffer and is_last_word else width
            if current and cell_len(candidate.rstrip()) > word_width:
                if current.strip():
                    wrapped.append(current.rstrip())
                current = ""

            if cell_len(token) > width:
                pieces = self._hyphenate_word(token, width)
                wrapped.extend(pieces[:-1])
                current = pieces[-1]
            else:
                current += token

        if current or not wrapped:
            wrapped.append(current.rstrip())
        return wrapped

    @staticmethod
    def _hyphenate_word(word: str, width: int) -> list[str]:
        """Split an overlong word with visible hyphens at cell boundaries."""
        if width <= 1:
            return chop_cells(word, width) or [""]

        pieces = chop_cells(word, width - 1) or [word]
        if any(cell_len(piece) + 1 > width for piece in pieces[:-1]):
            # A wide glyph may fill the whole line by itself, leaving no room
            # for a hyphen. Preserve that glyph rather than overflowing it.
            return chop_cells(word, width) or [word]
        return [f"{piece}-" for piece in pieces[:-1]] + [pieces[-1]]

    def _render_line_strip(self, y: int, rich_style: Style) -> Strip:
        """Render a line with the final-message color before selection styling."""
        selection = self.text_selection
        if y in self._render_line_cache and selection is None:
            return self._render_line_cache[y]

        line = self._process_line(self._lines[y])
        line_text = Text(line, no_wrap=True)
        line_text.stylize(rich_style)
        line_tone = self._line_tones.get(y)
        if line_tone == "final" and self._final_color is not None:
            line_text.stylize(Style(color=self._final_color))
        elif line_tone == "user" and self._user_color is not None:
            line_text.stylize(Style(color=self._user_color, bold=True))

        if self.highlight:
            line_text = self.highlighter(line_text)
        if selection is not None:
            if (select_span := selection.get_span(y - self._clear_y)) is not None:
                start, end = select_span
                if end == -1:
                    end = len(line_text)
                selection_style = self.screen.get_component_rich_style("screen--selection")
                line_text.stylize(selection_style, start, end)

        rendered_line = Strip(line_text.render(self.app.console), cell_len(line))
        if selection is not None:
            self._render_line_cache[y] = rendered_line
        return rendered_line
