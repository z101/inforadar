import math
from typing import Any, Dict, List, Tuple, TYPE_CHECKING

from rich import box
from rich.table import Table
from rich.text import Text

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.command_line import CommandLine
from inforadar.tui.keys import Key

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class ViewScreen(BaseScreen):
    """
    Base class for View Screens with variable row height block pagination.
    """

    HEADER_HEIGHT = 2
    TABLE_HEADER_HEIGHT = 2
    FOOTER_HEIGHT = 2
    SAFETY_MARGIN = 1
    RESERVED_ROWS = HEADER_HEIGHT + TABLE_HEADER_HEIGHT + FOOTER_HEIGHT + SAFETY_MARGIN

    def __init__(self, app: "AppState", title: str):
        super().__init__(app)
        self.title = title
        self.items: List[Any] = []
        self.filtered_items: List[Any] = []
        self.start_index = 0
        self.current_page_items: List[Any] = []
        self.filter_text = ""
        self.sort_key = None
        self.sort_reverse = False
        self.input_buffer = ""
        self.pending_g = False

        # Cursor / Active Mode State
        self.active_mode = False
        self.active_cursor = 0  # Absolute index in filtered_items

        # Command Line Support
        self.command_mode = False
        self.command_line = CommandLine()

    def execute_command(self):
        from inforadar.tui.screens.fetch import FetchScreen
        from inforadar.tui.screens.test_popup import TestPopupScreen

        cmd = self.command_line.text.strip()
        if not cmd:
            return

        if cmd == "test":
            self.app.push_screen(TestPopupScreen(self.app))
        elif cmd == "fetch":
            # Pass filters if available (from ArticlesViewScreen)
            sources = getattr(self, "selected_sources", set())
            topics = getattr(self, "selected_topics", set())

            fetch_screen = FetchScreen(self.app, self, sources, topics)
            self.app.push_screen(fetch_screen)
        elif cmd == "q":
            self.app.running = False

        # Clear after execution
        self.command_mode = False
        self.command_line.clear()

    def refresh_data(self):
        """Load items from source."""
        pass

    def apply_filter_and_sort(self):
        """Filter and sort items."""
        if not self.filter_text:
            self.filtered_items = list(self.items)
        else:
            filter_lower = self.filter_text.lower()
            self.filtered_items = [
                item for item in self.items if filter_lower in str(item).lower()
            ]

        if self.sort_key:
            self.filtered_items.sort(key=self.sort_key, reverse=self.sort_reverse)

        # Reset to start
        self.start_index = 0
        self.active_mode = False
        self.active_cursor = 0

    def render_row(self, item: Any, index: int) -> Tuple[List[str], str]:
        """Return list of cell values and style for the row."""
        return ([str(item)], "")

    def get_columns(self, width: int) -> List[Dict[str, Any]]:
        """Return column definitions based on available width."""
        return [{"header": "Item", "no_wrap": True, "overflow": "ellipsis"}]

    def calculate_visible_range(
        self, start_idx: int, available_rows: int, width: int
    ) -> List[Any]:
        """
        Calculates which items fit in the available rows starting from start_idx.
        With no_wrap=True, each row is exactly 1 line high.
        Returns the list of items that fit.
        """
        if start_idx >= len(self.filtered_items):
            return []

        end_idx = min(start_idx + available_rows, len(self.filtered_items))
        return self.filtered_items[start_idx:end_idx]

    def render(self):
        console = self.app.console
        width, height = console.size

        # Header
        header_text = self.title

        console.print(Text.from_markup(header_text), justify="center")

        # Calculate available rows for content
        available_rows = height - self.RESERVED_ROWS
        if available_rows < 1:
            available_rows = 1

        # Adjust start_index if active cursor is out of view (smooth scrolling logic)
        if self.active_mode:
            if self.active_cursor < self.start_index:
                self.start_index = self.active_cursor
            elif self.active_cursor >= self.start_index + available_rows:
                self.start_index = self.active_cursor - available_rows + 1

        # Calculate items for current "page"
        self.current_page_items = self.calculate_visible_range(
            self.start_index, available_rows, width
        )

        # Table with no_wrap to ensure fixed row height
        table = Table(
            box=box.SIMPLE_HEAD,
            padding=0,
            expand=True,
            show_footer=False,
            header_style="bold dim",
        )
        columns = self.get_columns(width)
        for col in columns:
            table.add_column(**col)

        for i, item in enumerate(self.current_page_items):
            # Row number on page starts at 1
            row_num = i + 1
            row_data, row_style = self.render_row(item, row_num)

            # Absolute index of this row
            abs_index = self.start_index + i

            style = row_style
            if self.active_mode and abs_index == self.active_cursor:
                style = "reverse green"
            elif (
                not self.active_mode
                and self.input_buffer
                and self.input_buffer == str(row_num)
            ):
                # Fallback for transient input highlighting if needed,
                # but we switch to active mode on digit input usually.
                style = "reverse green"

            table.add_row(*row_data, style=style)

        console.print(table)

        # Footer
        total_items = len(self.filtered_items)
        current_page = (self.start_index // available_rows) + 1
        total_pages = (
            math.ceil(total_items / available_rows) if available_rows > 0 else 1
        )
        if total_pages < 1:
            total_pages = 1

        if self.command_mode:
            # Render Command Line
            # Layout: ":<text>" with cursor. Right align: Pager | Total

            # Construct command part with cursor
            txt = self.command_line.text
            cpos = self.command_line.cursor_pos

            # Safe slice
            pre_cursor = txt[:cpos]
            cursor_char = txt[cpos] if cpos < len(txt) else " "
            post_cursor = txt[cpos + 1 :]

            # Styled cursor (reverse video)
            cmd_styled = Text(":")
            cmd_styled.append(pre_cursor)
            cmd_styled.append(cursor_char, style="reverse")
            cmd_styled.append(post_cursor)

            # Pager info
            pager_text = f"Page [green dim]{current_page}[/green dim] of [green dim]{total_pages}[/green dim] | Items [green dim]{total_items}[/green dim]"

            # Combine in table or just string formatting
            # Calculate spacing
            # Use a table for layout
            footer_table = Table.grid(expand=True)
            footer_table.add_column()
            footer_table.add_column(justify="right")

            footer_table.add_row(cmd_styled, Text.from_markup(pager_text, style="dim"))
            console.print(footer_table)

        else:
            filter_status = " [FILTERED]" if self.filter_text else ""

            info_status = ""
            if self.active_mode:
                # Show active row number (relative to page or absolute? Prompt says "Active <номер выделенной строки")
                # Usually means visible row number or absolute index + 1?
                # User typed row number which is page-relative.
                # If we scroll, does active row number change?
                # If we show absolute index it's clearer: Item X
                # But user types relative number.
                # Let's show visible row number if visible, else absolute?
                # "Active <row>" usually implies what the user sees.
                # Let's show (active_cursor - start_index + 1) if in view?
                # Or just absolute. Let's use visible row number for consistency with input.
                visible_row = self.active_cursor - self.start_index + 1
                info_status = f" | Active [green dim]{visible_row}[/green dim]"
            elif self.input_buffer:
                info_status = f" | Goto: {self.input_buffer}"

            footer_text = f"Page [green dim]{current_page}[/green dim] of [green dim]{total_pages}[/green dim] | Items [green dim]{total_items}[/green dim]{filter_status}{info_status}"
            console.print(Text.from_markup(footer_text), style="dim", justify="center")

    def handle_input(self, key: str) -> bool:
        from inforadar.tui.screens.filter_action import FilterActionScreen
        from inforadar.tui.screens.sort_action import SortActionScreen
        from inforadar.tui.screens.sync_action import SyncActionScreen

        console_height = self.app.console.size[1]
        available_rows = max(1, console_height - self.RESERVED_ROWS)
        width = self.app.console.size[0]

        if self.command_mode:
            if key == Key.ESCAPE:
                self.command_mode = False
                self.command_line.clear()
                return True
            elif key == Key.ENTER:
                self.execute_command()
                return True
            elif key == Key.BACKSPACE or key == Key.CTRL_H:
                self.command_line.delete_back()
                return True
            elif key == Key.DELETE:
                self.command_line.delete_forward()
                return True
            elif key == Key.LEFT or key == Key.CTRL_B:
                self.command_line.move_left()
                return True
            elif key == Key.RIGHT or key == Key.CTRL_F:
                self.command_line.move_right()
                return True
            elif key == Key.CTRL_A:
                self.command_line.move_start()
                return True
            elif key == Key.CTRL_E:
                self.command_line.move_end()
                return True
            elif key == Key.ALT_B:
                self.command_line.move_word_left()
                return True
            elif key == Key.ALT_F:
                self.command_line.move_word_right()
                return True
            elif key == Key.CTRL_W:
                self.command_line.delete_word_back()
                return True
            elif key == Key.CTRL_U:
                self.command_line.delete_to_start()
                return True
            elif len(key) == 1 and key.isprintable():
                self.command_line.insert(key)
                return True
            return True

        # Normal Mode
        if key == Key.COLON:
            self.command_mode = True
            return True

        # Esc exits Active Mode
        if key == Key.ESCAPE:
            if self.active_mode:
                self.active_mode = False
                self.input_buffer = ""
                return True
            else:
                # If not active, let parent handle it (e.g. pop screen)
                return super().handle_input(key)

        # Digits enter/update Active Mode
        if key.isdigit():
            # If in active mode and user types digits, we assume they are typing a NEW number
            # So we append to buffer and UPADTE active cursor
            new_buffer = self.input_buffer + key

            # Validate if it maps to a row on current page
            # Row numbers are 1-based relative to current page items (visible)
            # Max row = len(current_page_items)
            # BUT we might be at start of typing.

            # If we just switched pages, input_buffer might be stale?
            # We clear input_buffer on navigation below.

            if self.current_page_items:
                try:
                    row_num = int(new_buffer)
                    if 1 <= row_num <= len(self.current_page_items):
                        self.input_buffer = new_buffer
                        self.active_mode = True
                        # Map to absolute cursor
                        self.active_cursor = self.start_index + (row_num - 1)
                        return True
                except ValueError:
                    pass

            # If invalid, consume but don't update? Or update buffer but don't set active?
            # Existing logic just updated buffer if valid.
            if int(new_buffer) <= available_rows:  # Just a sanity check approx
                self.input_buffer = new_buffer
            return True

        if key == Key.BACKSPACE:
            if self.input_buffer:
                self.input_buffer = self.input_buffer[:-1]
                # Update active cursor if buffer is valid
                if self.input_buffer:
                    try:
                        row_num = int(self.input_buffer)
                        if 1 <= row_num <= len(self.current_page_items):
                            self.active_mode = True
                            self.active_cursor = self.start_index + (row_num - 1)
                    except ValueError:
                        pass
                else:
                    # Buffer empty, remain active? or exit active?
                    # Usually Backspace until empty exits specific selection but maybe keeps active mode on 0?
                    # Let's keep active mode but cursor might not move
                    pass
            return True

        if key == Key.ENTER:
            if self.active_mode:
                if 0 <= self.active_cursor < len(self.filtered_items):
                    item = self.filtered_items[self.active_cursor]
                    self.on_select(item)
                return True
            if self.input_buffer:
                # Legacy behavior if for some reason not active
                try:
                    row_num = int(self.input_buffer)
                    if 1 <= row_num <= len(self.current_page_items):
                        item = self.current_page_items[row_num - 1]
                        self.on_select(item)
                except ValueError:
                    pass
                self.input_buffer = ""
                return True

        # Navigation

        # If in Active Mode, J/K move cursor by 1 (Cyclic within page)
        if self.active_mode:
            # Calculate page boundary
            console_height = self.app.console.size[1]
            available_rows = max(1, console_height - self.RESERVED_ROWS)

            # Determine indices for current page
            page_start = self.start_index

            # How many items on this page?
            # It's min(available_rows, total - page_start)
            total = len(self.filtered_items)
            page_items_count = min(available_rows, total - page_start)

            if page_items_count > 0:
                # current relative index
                rel_cursor = self.active_cursor - page_start
                # Safety clamp if for some reason out of sync
                if rel_cursor < 0:
                    rel_cursor = 0
                if rel_cursor >= page_items_count:
                    rel_cursor = page_items_count - 1

                if key == Key.UP or key == Key.K:
                    rel_cursor = (rel_cursor - 1 + page_items_count) % page_items_count
                    self.active_cursor = page_start + rel_cursor
                    self.input_buffer = ""
                    return True
                elif key == Key.DOWN or key == Key.J:
                    rel_cursor = (rel_cursor + 1) % page_items_count
                    self.active_cursor = page_start + rel_cursor
                    self.input_buffer = ""
                    return True

        # Clear buffer on any other navigation key if not caught above
        # (Though we cleared it in active mode branches)

        if self.input_buffer and not self.active_mode:
            self.input_buffer = ""

        if key == Key.UP or key == Key.J:  # Previous Block (J = Backward)
            # Normal mode: Block Scroll
            if self.start_index > 0:
                self.start_index = max(0, self.start_index - available_rows)
                return True

        elif key == Key.DOWN or key == Key.K:  # Next Block (K = Forward)
            # Normal mode: Block Scroll
            if self.start_index + len(self.current_page_items) < len(
                self.filtered_items
            ):
                self.start_index += len(self.current_page_items)
                return True

        elif key == Key.G:  # First page (Double 'g')
            if self.pending_g:
                if self.start_index != 0:
                    self.start_index = 0
                    self.active_cursor = 0  # specific to g
                    if self.active_mode:
                        self.active_cursor = 0
                    self.pending_g = False
                    return True
                self.pending_g = False
            else:
                self.pending_g = True
                return False  # Wait for next key

        elif key == Key.SHIFT_G:  # Last page
            # Calculate the start of the last page
            total = len(self.filtered_items)
            if total > 0:
                last_page_idx = (total - 1) // available_rows
                new_start = last_page_idx * available_rows
                if self.start_index != new_start:
                    self.start_index = new_start
                    # If active mode, move cursor to last item?
                    # Vim G usually moves cursor to last line.
                    if self.active_mode:
                        self.active_cursor = total - 1
                    return True

        elif key == Key.R:  # r - Read/Sync
            self.app.push_screen(SyncActionScreen(self.app, self))
            return True
        elif key == Key.F:  # f - Filter
            self.app.push_screen(FilterActionScreen(self.app, self))
            return True
        elif key == Key.S:  # s - Sort
            self.app.push_screen(SortActionScreen(self.app, self))
            return True
        elif key == Key.L:  # l - Next screen (generic)
            pass
        else:
            if super().handle_input(key):
                return True

        # Reset pending_g if any other key was processed
        if key != Key.G:
            self.pending_g = False

        return False
