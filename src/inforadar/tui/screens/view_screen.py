import math
from typing import Any, Dict, List, Tuple, TYPE_CHECKING

from rich import box
from rich.console import Group
from rich.live import Live
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
    Base class for View Screens, now powered by rich.live.Live for a flicker-free UI.
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
        self.current_page_items: List[Any] = []
        self.start_index = 0
        self.filter_text = ""
        self.final_filter_text = ""
        self.sort_key = None
        self.sort_reverse = False
        self.input_buffer = ""
        self.pending_g = False

        self.active_mode = True
        self.active_cursor = 0
        self.cursor_visible = True

        self.command_mode = False
        self.filter_mode = False
        self.command_line = CommandLine()
        self.numerical_input_buffer = ""
        self.status_message = ""
        
        self.available_commands = ["q", "help", "noh"]
        self.autocomplete_index = -1
        self.autocomplete_prefix = None
        
        self._live_started = False
        self.live = Live(
            None,
            console=self.app.console,
            screen=False,
            auto_refresh=False,
            transient=True,
            vertical_overflow="visible"
        )

        self.load_state()

    def _mount(self):
        """Starts the live display if not already running."""
        if not self._live_started:
            self.live.start(refresh=False)
            self._live_started = True
            self.live.update(self._generate_renderable(), refresh=True)

    def on_leave(self):
        """Saves state and stops the live display."""
        self.save_state()
        if self._live_started:
            self.live.stop()
        self._live_started = False
        super().on_leave() if hasattr(super(), 'on_leave') else None
    
    @property
    def is_text_input_mode(self) -> bool:
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

    def execute_command(self) -> bool:
        """
        Executes the command in the command line.
        Returns True if a screen was pushed, False otherwise.
        """
        cmd = self.command_line.text.strip()
        pushed_screen = False
        known_command = True

        if not cmd:
            self.status_message = ""
            return pushed_screen

        if cmd == "q":
            self.app.running = False
        elif cmd == "help" or cmd == "?":
            help_screen_class = getattr(self, "help_screen_class", None)
            if help_screen_class:
                self.app.push_screen(help_screen_class(self.app))
                pushed_screen = True
        elif cmd == "noh":
            self.cursor_visible = False
        else:
            known_command = False

        if not known_command:
            self.status_message = f"command '{cmd}' not found"
        else:
            self.status_message = ""  # Clear status message on known command

        return pushed_screen

    def refresh_data(self):
        pass

    def get_item_for_filter(self, item: Any) -> str:
        return str(item)

    def apply_filter_and_sort(self):
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
                    if pos == -1: return False
                    start_pos = pos + len(part)
                return True
            self.filtered_items = [item for item in self.items if check_pattern(self.get_item_for_filter(item), pattern)]

        if self.sort_key:
            self.filtered_items.sort(key=self.sort_key, reverse=self.sort_reverse)

        self.start_index = 0
        self.active_cursor = 0

    def render_row(self, item: Any, index: int) -> Tuple[List[str], str]:
        return ([str(item)], "")

    def get_columns(self, width: int) -> List[Dict[str, Any]]:
        return [{"header": "Item", "no_wrap": True, "overflow": "ellipsis"}]

    def calculate_visible_range(self, start_idx: int, available_rows: int, width: int) -> List[Any]:
        if start_idx >= len(self.filtered_items):
            return []
        end_idx = min(start_idx + available_rows, len(self.filtered_items))
        return self.filtered_items[start_idx:end_idx]

    def render(self):
        """The render method is now only responsible for ensuring the Live view is active."""
        self._mount()

    def _generate_renderable(self) -> Group:
        """Builds the rich renderable for the entire screen."""
        console = self.app.console
        width, height = console.size

        # Header
        header_text = self.title
        if self.filter_text:
            header_text += f" [white]|[/white] [dim]Filter[/] [yellow]{escape(self.filter_text)}[/]"
        header = Text.from_markup(header_text, justify="center")

        # Table
        available_rows = height - self.RESERVED_ROWS
        if available_rows < 1: available_rows = 1
        
        self.current_page_items = self.calculate_visible_range(self.start_index, available_rows, width)

        table = Table(box=box.SIMPLE_HEAD, padding=0, expand=True, show_footer=False, header_style="bold dim")
        columns = self.get_columns(width)
        for col in columns:
            table.add_column(**col)

        for i, item in enumerate(self.current_page_items):
            row_num = i + 1
            row_data, row_style = self.render_row(item, row_num)
            abs_index = self.start_index + i
            style = row_style
            if self.active_mode and abs_index == self.active_cursor and self.cursor_visible:
                style = "reverse green"
            table.add_row(*row_data, style=style)
        
        # Footer
        total_items = len(self.filtered_items)
        current_page = (self.start_index // available_rows) + 1 if available_rows > 0 else 1
        total_pages = math.ceil(total_items / available_rows) if available_rows > 0 and total_items > 0 else 1
        pager_text = f"Page [green dim]{current_page}[/green dim] of [green dim]{total_pages}[/green dim] | Items [green dim]{total_items}[/green dim]"

        has_left_footer = self.command_mode or self.filter_mode or self.status_message
        if has_left_footer:
            footer_table = Table.grid(expand=True)
            footer_table.add_column()
            footer_table.add_column(justify="right")

            if self.command_mode or self.filter_mode:
                prompt = ":" if self.command_mode else "/"
                txt = self.command_line.text
                cpos = self.command_line.cursor_pos
                pre_cursor = txt[:cpos]
                cursor_char = txt[cpos] if cpos < len(txt) else " "
                post_cursor = txt[cpos + 1:]
                
                cmd_styled = Text(prompt)
                cmd_styled.append(pre_cursor)
                cmd_styled.append(cursor_char, style="reverse")
                cmd_styled.append(post_cursor)
                footer_left = cmd_styled
            else:  # status_message must be true
                footer_left = Text(self.status_message, style="red")

            footer_table.add_row(footer_left, Text.from_markup(pager_text, style="dim"))
            footer = footer_table
        else:
            footer = Text.from_markup(pager_text, style="dim", justify="center")

        return Group(header, table, footer)


    def handle_input(self, key: str) -> bool:
        """Handles key presses and updates the screen state and live view."""
        self._mount()

        from inforadar.tui.screens.filter_action import FilterActionScreen
        from inforadar.tui.screens.sort_action import SortActionScreen
        from inforadar.tui.screens.sync_action import SyncActionScreen

        redraw = False

        console_height = self.app.console.size[1]
        available_rows = max(1, console_height - self.RESERVED_ROWS)

        # Command/Filter mode input
        if self.command_mode or self.filter_mode:
            def _update_filter():
                if self.filter_mode:
                    self.filter_text = self.command_line.text
                    self.apply_filter_and_sort()

            if key == Key.TAB:
                if self.command_mode:
                    current_text = self.command_line.text
                    
                    if self.autocomplete_prefix is None:
                        self.autocomplete_prefix = current_text
                        
                    matching_commands = sorted([
                        cmd for cmd in self.available_commands 
                        if cmd.startswith(self.autocomplete_prefix)
                    ])
                    
                    if matching_commands:
                        self.autocomplete_index = (self.autocomplete_index + 1) % len(matching_commands)
                        self.command_line.set_text(matching_commands[self.autocomplete_index])
            else:
                if self.command_mode:
                    self.autocomplete_prefix = None
                    self.autocomplete_index = -1
                if key == Key.ESCAPE:
                    if self.filter_mode:
                        self.filter_text = self.final_filter_text
                        self.apply_filter_and_sort()
                    self.command_mode = False
                    self.filter_mode = False
                    self.command_line.clear()
                elif key == Key.ENTER:
                    if self.command_mode:
                        pushed_screen = self.execute_command()

                        # Always exit command mode after executing a command.
                        self.command_mode = False
                        self.command_line.clear()

                        if pushed_screen:
                            return True
                    elif self.filter_mode:
                        self.final_filter_text = self.command_line.text
                        self.filter_text = self.final_filter_text
                        self.filter_mode = False
                        self.command_line.clear()

                elif key in (Key.BACKSPACE, Key.CTRL_H):
                    self.command_line.delete_back()
                    _update_filter()
                elif key == Key.DELETE:
                    self.command_line.delete_forward()
                    _update_filter()
                elif key in (Key.LEFT, Key.CTRL_B):
                    self.command_line.move_left()
                elif key in (Key.RIGHT, Key.CTRL_F):
                    self.command_line.move_right()
                elif key == Key.CTRL_A:
                    self.command_line.move_start()
                elif key == Key.CTRL_E:
                    self.command_line.move_end()
                elif key == Key.ALT_B:
                    self.command_line.move_word_left()
                elif key == Key.ALT_F:
                    self.command_line.move_word_right()
                elif key == Key.CTRL_W:
                    self.command_line.delete_word_back()
                    _update_filter()
                elif key == Key.CTRL_U:
                    self.command_line.delete_to_start()
                    _update_filter()
                elif len(key) == 1 and key.isprintable():
                    self.command_line.insert(key)
                    _update_filter()
            
            redraw = True

        # Normal mode input
        else:
            # If a status message is present from a previous command,
            # the next key press in normal mode should clear it before proceeding.
            if self.status_message:
                self.status_message = ""
                redraw = True

            if not key.isdigit():
                self.numerical_input_buffer = "" # Clear buffer if non-digit key is pressed

            if key == Key.COLON:
                self.command_mode = True
                self.command_line.clear()
                self.status_message = "" # Clear status message when re-entering command mode
                redraw = True
            elif key == Key.SLASH:
                self.filter_mode = True
                self.command_line.clear()
                self.command_line.set_text(self.filter_text)
                self.final_filter_text = ""
                redraw = True
            elif key == Key.ESCAPE:
                if self.filter_text or self.final_filter_text:
                    self.filter_text = ""
                    self.final_filter_text = ""
                    self.apply_filter_and_sort()
                    self.save_state()
                    redraw = True
                else: return super().handle_input(key)
            elif key == Key.Q:
                self.save_state()
                return super().handle_input(key)
            elif key.isdigit():
                # Special handling for '1' when currently on the first item and no number in buffer
                # Adjusted to check if active_cursor is the first item on the CURRENT page
                if not self.numerical_input_buffer and key == '1' and self.active_cursor == self.start_index:
                    # Assume user means '11' if they press '1' while on the first item (line 1)
                    # and no number is being typed yet.
                    self.numerical_input_buffer = "11"
                else:
                    self.numerical_input_buffer += key
                
                # Now, apply overflow logic to the potentially updated buffer
                # and then try to select.
                
                # Safely try to get the line number from the current buffer state
                try:
                    attempt_line_num = int(self.numerical_input_buffer)
                except ValueError:
                    # Should not happen with valid digit inputs, but clear if it does
                    self.numerical_input_buffer = ""
                    redraw = False
                    return False # We handled this key
                
                # Check for overflow and reset if necessary - now against current_page_items
                if len(self.current_page_items) > 0 and attempt_line_num > len(self.current_page_items):
                    # If the current buffer value would cause an overflow on the current page,
                    # reset the buffer to just the current key and process that.
                    self.numerical_input_buffer = key
                    line_num = int(key)
                else:
                    line_num = attempt_line_num # Otherwise, use the full number
                
                # Finally, attempt to select the line
                # Validate against current_page_items length
                if 0 < line_num <= len(self.current_page_items):
                    self.active_cursor = self.start_index + (line_num - 1) # Calculate absolute cursor
                    self.active_mode = True
                    redraw = True
                else:
                    # If the number is still invalid (e.g., '0' or > max after reset)
                    self.numerical_input_buffer = "" # Clear buffer
                    redraw = False
            elif key == Key.ENTER:
                self.numerical_input_buffer = "" # Clear buffer when ENTER is pressed
                if self.active_mode and 0 <= self.active_cursor < len(self.filtered_items):
                    self.on_select(self.filtered_items[self.active_cursor])
                redraw = True
            elif key in (Key.DOWN, Key.J):
                self.cursor_visible = True
                self.active_mode = True
                if self.current_page_items:
                    current_relative_index = self.active_cursor - self.start_index
                    self.active_cursor = self.start_index + ((current_relative_index + 1) % len(self.current_page_items))
                redraw = True
            elif key in (Key.UP, Key.K):
                self.cursor_visible = True
                self.active_mode = True
                if self.current_page_items:
                    current_relative_index = self.active_cursor - self.start_index
                    self.active_cursor = self.start_index + ((current_relative_index - 1 + len(self.current_page_items)) % len(self.current_page_items))
                redraw = True
            elif key == Key.G:
                if self.pending_g:
                    if self.start_index != 0:
                        self.start_index = 0
                        self.active_cursor = 0
                        redraw = True
                    self.pending_g = False
                else:
                    self.pending_g = True
            elif key == Key.SHIFT_G:
                total = len(self.filtered_items)
                if total > 0:
                    new_start = ((total - 1) // available_rows) * available_rows
                    if self.start_index != new_start:
                        self.start_index = new_start
                        self.active_cursor = total - 1
                        redraw = True
            elif key == Key.L:
                total = len(self.filtered_items)
                total_pages = math.ceil(total / available_rows) if available_rows > 0 else 1
                if total_pages > 1:
                    self.start_index = (self.start_index + available_rows) % total
                    self.active_cursor = self.start_index
                    redraw = True
            elif key == Key.H:
                total = len(self.filtered_items)
                total_pages = math.ceil(total / available_rows) if available_rows > 0 else 1
                if total_pages > 1:
                    self.start_index -= available_rows
                    if self.start_index < 0:
                        self.start_index = ((total - 1) // available_rows) * available_rows
                    self.active_cursor = self.start_index
                    redraw = True
            elif key == Key.R:
                self.app.push_screen(SyncActionScreen(self.app, self))
                redraw = True
            elif key == Key.F:
                self.app.push_screen(FilterActionScreen(self.app, self))
                redraw = True
            elif key == Key.S:
                self.app.push_screen(SortActionScreen(self.app, self))
                redraw = True
            else:
                if super().handle_input(key):
                    return True
            
            if key != Key.G:
                self.pending_g = False

        if redraw:
            self.live.update(self._generate_renderable(), refresh=True)
            return False # We handled the redraw
        
        return False # No state change, no redraw needed

    def on_select(self, item: Any):
        pass

        