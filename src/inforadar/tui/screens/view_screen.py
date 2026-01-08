import math
import fnmatch
from typing import Any, Dict, List, Tuple, TYPE_CHECKING

from rich import box
from rich.table import Table
from rich.text import Text
from rich.markup import escape

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
        self.final_filter_text = ""
        self.sort_key = None
        self.sort_reverse = False
        self.input_buffer = ""
        self.pending_g = False

        # Cursor / Active Mode State
        self.active_mode = True
        self.active_cursor = 0  # Absolute index in filtered_items
        self.cursor_visible = True

        # Command Line Support
        self.command_mode = False
        self.filter_mode = False
        self.command_line = CommandLine()

        self.load_state()

    @property
    def is_text_input_mode(self) -> bool:
        """Returns True if the screen is in a mode that expects direct text input."""
        return self.command_mode or self.filter_mode

    def get_state_key(self) -> str:
        return self.__class__.__name__

    def load_state(self):
        state = self.app.screen_states.get(self.get_state_key(), {})
        self.filter_text = state.get("filter_text", "")
        self.final_filter_text = state.get("final_filter_text", "")
        if self.filter_text or self.final_filter_text:
             self.apply_filter_and_sort()

    def save_state(self):
        state = {
            "filter_text": self.filter_text,
            "final_filter_text": self.final_filter_text
        }
        self.app.screen_states[self.get_state_key()] = state

    def execute_command(self):
        from inforadar.tui.screens.fetch import FetchScreen
        from inforadar.tui.screens.test_popup import TestPopupScreen
        from inforadar.tui.screens.articles_help import ArticlesHelpScreen

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
        elif cmd == "help" or cmd == "?":
            self.app.push_screen(ArticlesHelpScreen(self.app))

        # Clear after execution
        self.command_mode = False
        self.command_line.clear()

    def refresh_data(self):
        """Load items from source."""
        pass

    def get_item_for_filter(self, item: Any) -> str:
        # Default implementation, subclasses should override
        return str(item)

    def apply_filter_and_sort(self):
        """Filter and sort items."""
        old_count = len(self.filtered_items)

        if not self.filter_text:
            self.filtered_items = list(self.items)
        else:
            pattern = self.filter_text.lower()

            def check_pattern(text, pat):
                text = text.lower()
                parts = pat.split('*')
                start_pos = 0
                for part in parts:
                    pos = text.find(part, start_pos)
                    if pos == -1:
                        return False
                    start_pos = pos + len(part)
                return True

            self.filtered_items = [
                item for item in self.items if check_pattern(self.get_item_for_filter(item), pattern)
            ]

        if old_count != len(self.filtered_items):
            self.need_clear = True

        if self.sort_key:
            self.filtered_items.sort(key=self.sort_key, reverse=self.sort_reverse)

        # Reset to start
        self.start_index = 0
        self.active_mode = True
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
        if self.filter_text:
            header_text += f" [white]|[/white] [dim]Filter[/] [yellow]{escape(self.filter_text)}[/]"

        console.print(Text.from_markup(header_text), justify="center")

        # Calculate available rows for content
        available_rows = height - self.RESERVED_ROWS
        if available_rows < 1:
            available_rows = 1

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
            if self.active_mode and abs_index == self.active_cursor and self.cursor_visible:
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
        current_page = (self.start_index // available_rows) + 1 if available_rows > 0 else 1
        total_pages = (
            math.ceil(total_items / available_rows) if available_rows > 0 else 1
        )
        if total_pages < 1:
            total_pages = 1

        if self.command_mode or self.filter_mode:
            # Render Command Line
            # Layout: ":<text>" with cursor. Right align: Pager | Total
            prompt = ":" if self.command_mode else "/"

            # Construct command part with cursor
            txt = self.command_line.text
            cpos = self.command_line.cursor_pos

            # Safe slice
            pre_cursor = txt[:cpos]
            cursor_char = txt[cpos] if cpos < len(txt) else " "
            post_cursor = txt[cpos + 1 :]

            # Styled cursor (reverse video)
            cmd_styled = Text(prompt)
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
            filter_status = ""
            info_status = ""
            if self.active_mode:
                visible_row = self.active_cursor - self.start_index + 1
                # info_status = f" | Active [green dim]{visible_row}[/green dim]"  <-- Removed per request
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

        if self.command_mode or self.filter_mode:
            def _update_filter():
                if self.filter_mode:
                    self.filter_text = self.command_line.text
                    self.apply_filter_and_sort()

            if key == Key.ESCAPE:
                if self.filter_mode:
                    self.filter_text = self.final_filter_text
                    self.apply_filter_and_sort()
                self.command_mode = False
                self.filter_mode = False
                self.command_line.clear()
                return True
            elif key == Key.ENTER:
                if self.command_mode:
                    self.execute_command()
                elif self.filter_mode:
                    self.final_filter_text = self.command_line.text
                    self.filter_text = self.final_filter_text

                self.command_mode = False
                self.filter_mode = False
                self.command_line.clear()
                return True
            elif key == Key.BACKSPACE or key == Key.CTRL_H:
                self.command_line.delete_back()
                _update_filter()
                return True
            elif key == Key.DELETE:
                self.command_line.delete_forward()
                _update_filter()
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
                _update_filter()
                return True
            elif key == Key.CTRL_U:
                self.command_line.delete_to_start()
                _update_filter()
                return True
            elif len(key) == 1 and key.isprintable():
                self.command_line.insert(key)
                _update_filter()
                return True
            return True

        # Normal Mode
        if key == Key.COLON:
            self.command_mode = True
            self.command_line.clear()
            return True

        if key == Key.SLASH:
            self.filter_mode = True
            self.command_mode = False
            self.command_line.clear()
            self.command_line.set_text(self.filter_text)
            self.final_filter_text = ""
            return True

        if key == Key.ESCAPE:
            if self.active_mode:
                # self.active_mode = False  <-- Removed: Active mode is now default
                self.input_buffer = ""
                return True
            if self.filter_text or self.final_filter_text:
                self.filter_text = ""
                self.final_filter_text = ""
                self.apply_filter_and_sort()
                self.save_state()
                return True
            return super().handle_input(key)

        if key == Key.Q:
             self.save_state()
             return super().handle_input(key)

        # Digits enter/update Active Mode
        if key.isdigit():
            new_buffer = self.input_buffer + key
            if self.current_page_items:
                try:
                    row_num = int(new_buffer)
                    if 1 <= row_num <= len(self.current_page_items):
                        self.input_buffer = ""  # Clear buffer after successful activation
                        self.active_mode = True
                        self.cursor_visible = True
                        self.active_cursor = self.start_index + (row_num - 1)
                        return True
                    else:
                        # Number is out of range, don't update buffer
                        return True
                except ValueError:
                    pass

            # Fallback: allow building buffer if within available rows
            if int(new_buffer) <= available_rows:
                self.input_buffer = new_buffer
            return True

        if key == Key.BACKSPACE:
            if self.input_buffer:
                self.input_buffer = self.input_buffer[:-1]
                if self.input_buffer:
                    try:
                        row_num = int(self.input_buffer)
                        if 1 <= row_num <= len(self.current_page_items):
                            self.active_mode = True
                            self.cursor_visible = True
                            self.active_cursor = self.start_index + (row_num - 1)
                    except ValueError:
                        pass
            return True

        if key == Key.ENTER:
            if self.active_mode:
                if 0 <= self.active_cursor < len(self.filtered_items):
                    item = self.filtered_items[self.active_cursor]
                    self.on_select(item)
                return True
            if self.input_buffer:
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
        if self.input_buffer and key not in [Key.J, Key.K, Key.UP, Key.DOWN]:
            self.input_buffer = ""

        # J/K and Arrow keys for cursor movement (activates active_mode)
        if key == Key.DOWN or key == Key.J:
            self.cursor_visible = True
            if not self.active_mode:
                self.active_mode = True
                self.active_cursor = self.start_index
            elif self.current_page_items:
                current_relative_index = self.active_cursor - self.start_index
                new_relative_index = (current_relative_index + 1) % len(self.current_page_items)
                self.active_cursor = self.start_index + new_relative_index
            self.input_buffer = ""
            return True

        if key == Key.UP or key == Key.K:
            self.cursor_visible = True
            if not self.active_mode:
                self.active_mode = True
                self.active_cursor = self.start_index + len(self.current_page_items) - 1
            elif self.current_page_items:
                current_relative_index = self.active_cursor - self.start_index
                new_relative_index = (current_relative_index - 1 + len(self.current_page_items)) % len(self.current_page_items)
                self.active_cursor = self.start_index + new_relative_index
            self.input_buffer = ""
            return True

        elif key == Key.G:  # First page (Double 'g')
            if self.pending_g:
                if self.start_index != 0:
                    self.start_index = 0
                    self.active_cursor = 0
                    self.pending_g = False
                    self.need_clear = True
                    return True
                self.pending_g = False
            else:
                self.pending_g = True
                return False

        elif key == Key.SHIFT_G:  # Last page
            total = len(self.filtered_items)
            if total > 0:
                last_page_idx = (total - 1) // available_rows
                new_start = last_page_idx * available_rows
                if self.start_index != new_start:
                    self.start_index = new_start
                    self.active_cursor = total - 1
                    self.need_clear = True
                    return True
        
        elif key == Key.L: # Next page
            total = len(self.filtered_items)
            if total > 0:
                total_pages = math.ceil(total / available_rows) if available_rows > 0 else 1
                if total_pages <= 1:
                    return False  # Disabled when only one page
                new_start = self.start_index + available_rows
                if new_start >= total:
                    new_start = 0 # Wrap around
                self.start_index = new_start
                self.active_cursor = self.start_index
                if not self.active_mode: self.active_mode = True
                self.need_clear = True
                return True
        
        elif key == Key.H: # Previous page
            total = len(self.filtered_items)
            if total > 0:
                total_pages = math.ceil(total / available_rows) if available_rows > 0 else 1
                if total_pages <= 1:
                    return False  # Disabled when only one page
                new_start = self.start_index - available_rows
                if new_start < 0:
                    last_page_idx = (total - 1) // available_rows
                    new_start = last_page_idx * available_rows
                self.start_index = new_start
                self.active_cursor = self.start_index
                if not self.active_mode: self.active_mode = True
                self.need_clear = True
                return True

        elif key == Key.R:
            self.app.push_screen(SyncActionScreen(self.app, self))
            return True
        elif key == Key.F:
            self.app.push_screen(FilterActionScreen(self.app, self))
            return True
        elif key == Key.S:
            self.app.push_screen(SortActionScreen(self.app, self))
            return True
        
        elif key == Key.C:
             self.cursor_visible = not self.cursor_visible
             return True
        
        else:
            if super().handle_input(key):
                return True

        if key != Key.G:
            self.pending_g = False

        return False

    def on_leave(self):
        """Called when leaving this screen - ensure proper cleanup."""
        # Save state when leaving the screen
        self.save_state()
        # Call parent implementation if exists
        super().on_leave() if hasattr(super(), 'on_leave') else None