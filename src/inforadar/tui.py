import sys
import os
import time
import math
import signal
import select
import tty
import termios
from typing import List, Optional, Any, Dict, Callable, Tuple
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.markup import escape
from rich.text import Text
from rich import box
from rich.status import Status
from rich.live import Live
from rich.console import Group
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeRemainingColumn,
    TaskID,
)
from rich.control import Control
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
import threading
from queue import Queue, Empty

from .core import CoreEngine
from .models import Article


class Key:
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    ENTER = "enter"
    ESCAPE = "escape"
    Q = "q"
    S = "s"
    T = "t"
    R = "r"
    F = "f"
    H = "h"
    J = "j"
    K = "k"
    L = "l"
    G = "g"
    SHIFT_G = "G"
    QUESTION = "?"
    SLASH = "/"
    BACKSPACE = "backspace"
    CTRL_D = "ctrl_d"
    CTRL_U = "ctrl_u"
    UNKNOWN = "unknown"
    D = "d"
    V = "v"
    C = "c"
    B = "b"
    # Command Line Keys
    CTRL_B = "ctrl_b"
    CTRL_E = "ctrl_e"
    CTRL_F = "ctrl_f"
    CTRL_H = "ctrl_h"
    CTRL_W = "ctrl_w"
    ALT_B = "alt_b"
    ALT_F = "alt_f"
    DELETE = "delete"
    COLON = ":"
    CTRL_A = "ctrl_a"
    SPACE = "space"


# Keyboard layout mapping: other layouts -> English
LAYOUT_MAP = {
    # Russian layout
    "й": "q",
    "ц": "w",
    "у": "e",
    "к": "r",
    "е": "t",
    "н": "y",
    "г": "u",
    "ш": "i",
    "щ": "o",
    "з": "p",
    "ф": "a",
    "ы": "s",
    "в": "d",
    "а": "f",
    "п": "g",
    "р": "h",
    "о": "j",
    "л": "k",
    "д": "l",
    "я": "z",
    "ч": "x",
    "с": "c",
    "м": "v",
    "и": "b",
    "т": "n",
    "ь": "m",
    ".": "/",
    # Upper case Russian
    "Й": "Q",
    "Ц": "W",
    "У": "E",
    "К": "R",
    "Е": "T",
    "Н": "Y",
    "Г": "U",
    "Ш": "I",
    "Щ": "O",
    "З": "P",
    "Ф": "A",
    "Ы": "S",
    "В": "D",
    "А": "F",
    "П": "G",
    "Р": "H",
    "О": "J",
    "Л": "K",
    "Д": "L",
    "Я": "Z",
    "Ч": "X",
    "С": "C",
    "М": "V",
    "И": "B",
    "Т": "N",
    "Ь": "M",
    "Ж": ":",
}


# Resize handling
class ResizeScreen(Exception):
    pass


resize_needed = False


def handle_winch(signum, frame):
    global resize_needed
    resize_needed = True


def get_key() -> Optional[str]:
    """Reads a key press and decodes escape sequences. Returns None on timeout."""
    global resize_needed

    fd = sys.stdin.fileno()

    if resize_needed:
        resize_needed = False
        raise ResizeScreen()

    try:
        # Wait for input with timeout to allow periodic refresh
        r, _, _ = select.select([fd], [], [], 0.1)
        if not r:
            return None  # Timeout - no input
    except (OSError, InterruptedError):
        return None

    # Read first byte
    try:
        b1 = os.read(fd, 1)
    except OSError:
        return Key.UNKNOWN

    ch = ""
    # Decode UTF-8
    if b1:
        byte1 = ord(b1)
        # Determine sequence length
        seq_len = 1
        if (byte1 & 0x80) == 0:
            seq_len = 1
        elif (byte1 & 0xE0) == 0xC0:
            seq_len = 2
        elif (byte1 & 0xF0) == 0xE0:
            seq_len = 3
        elif (byte1 & 0xF8) == 0xF0:
            seq_len = 4

        # Read remaining bytes if any
        raw_bytes = b1
        if seq_len > 1:
            try:
                raw_bytes += os.read(fd, seq_len - 1)
            except OSError:
                pass

        try:
            ch = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            ch = Key.UNKNOWN

    # Handle CTRL+D (EOT) and CTRL+U (NAK)
    if ch == "\x04":
        return Key.CTRL_D
    if ch == "\x15":
        return Key.CTRL_U
    if ch == "\x02":
        return Key.CTRL_B
    if ch == "\x05":
        return Key.CTRL_E
    if ch == "\x06":
        return Key.CTRL_F
    if ch == "\x08":
        return Key.CTRL_H
    if ch == "\x17":
        return Key.CTRL_W
    if ch == "\x01":
        return Key.CTRL_A

    # Handle Alt+Key (Esc followed by char)
    if ch == "\x1b":
        try:
            ch2 = os.read(fd, 1).decode()
            if ch2 == "b":
                return Key.ALT_B
            if ch2 == "f":
                return Key.ALT_F

            # ANSI sequences check again (merged from above logic to be safe)
            if ch2 == "[":
                try:
                    ch3 = os.read(fd, 1).decode()
                    if ch3 == "A":
                        return Key.UP
                    if ch3 == "B":
                        return Key.DOWN
                    if ch3 == "C":
                        return Key.RIGHT
                    if ch3 == "D":
                        return Key.LEFT
                    if ch3 == "3":  # Delete is usually [3~
                        ch4 = os.read(fd, 1).decode()
                        if ch4 == "~":
                            return Key.DELETE
                except OSError:
                    pass
            elif ch2 == "O":
                try:
                    ch3 = os.read(fd, 1).decode()
                    if ch3 == "A":
                        return Key.UP
                    if ch3 == "B":
                        return Key.DOWN
                    if ch3 == "C":
                        return Key.RIGHT
                    if ch3 == "D":
                        return Key.LEFT
                except OSError:
                    pass

        except (OSError, UnicodeDecodeError):
            pass
        return Key.ESCAPE

    # Convert from other keyboard layouts to English
    if ch in LAYOUT_MAP:
        ch = LAYOUT_MAP[ch]

    if ch == "\r":
        return Key.ENTER
    if ch == "\n":
        return Key.ENTER
    if ch == "\x7f":
        return Key.BACKSPACE

    if ch == "q" or ch == "Q":
        return Key.Q
    if ch == "s" or ch == "S":
        return Key.S
    if ch == "r" or ch == "R":
        return Key.R
    if ch == "f" or ch == "F":
        return Key.F
    if ch == "h" or ch == "H":
        return Key.H
    if ch == "j" or ch == "J":
        return Key.J
    if ch == "k" or ch == "K":
        return Key.K
    if ch == "l" or ch == "L":
        return Key.L
    if ch == "v" or ch == "V":
        return Key.V
    if ch == "c" or ch == "C":
        return Key.C
    if ch == "b" or ch == "B":
        return Key.B
    if ch == "d" or ch == "D":
        return Key.D
    if ch == "g":
        return Key.G
    if ch == "G":
        return Key.SHIFT_G
    if ch == "?":
        return Key.QUESTION
    if ch == ":":
        return Key.COLON
    if ch == ":":
        return Key.COLON
    if ch == ":":
        return Key.COLON
    if ch == "/":
        return Key.SLASH
    if ch == " ":
        return Key.SPACE

    # Return digits as is
    if ch.isdigit():
        return ch

    return ch


class AppState:
    def __init__(self):
        self.engine = CoreEngine()
        self.console = Console()
        self.running = True
        self.screen_stack: List["BaseScreen"] = []

    def push_screen(self, screen: "BaseScreen"):
        self.screen_stack.append(screen)

    def pop_screen(self):
        if self.screen_stack:
            self.screen_stack.pop()
        if not self.screen_stack:
            self.running = False

    @property
    def current_screen(self) -> Optional["BaseScreen"]:
        return self.screen_stack[-1] if self.screen_stack else None

    def run(self):
        # Initial screen: ArticlesViewScreen
        self.push_screen(ArticlesViewScreen(self))

        # Register resize handler
        old_handler = signal.signal(signal.SIGWINCH, handle_winch)

        # Save terminal settings
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setcbreak(fd)
            with self.console.screen():
                self.console.show_cursor(False)
                should_render = True
                while self.running and self.current_screen:
                    if should_render:
                        # Use home() only in command mode dealing with typing to prevent flickering.
                        # Otherwise use clear() to ensure no artifacts (e.g. when changing pages).
                        use_clear = True
                        if (
                            hasattr(self.current_screen, "command_mode")
                            and self.current_screen.command_mode
                        ):
                            use_clear = False
                        elif (
                            hasattr(self.current_screen, "active_mode")
                            and self.current_screen.active_mode
                        ):
                            use_clear = False

                        if use_clear:
                            self.console.clear()
                        else:
                            self.console.control(Control.home())

                        # Ensure we clear the rest of the screen if not using clear() and content shrunk (unlikely here but good practice)
                        # Actually rich's clean screen usage handles full redraw usually.

                        self.current_screen.render()
                        should_render = False

                    try:
                        key = get_key()
                        if key is None:
                            # Timeout - check if screen needs refresh (for animations)
                            if (
                                hasattr(self.current_screen, "needs_refresh")
                                and self.current_screen.needs_refresh()
                            ):
                                should_render = True
                        elif self.current_screen:
                            should_render = self.current_screen.handle_input(key)
                    except ResizeScreen:
                        should_render = True
                        # Update console size explicitly if needed (rich usually handles it)
                        size = self.console.size
        except KeyboardInterrupt:
            pass  # Handle Ctrl+C gracefully
        finally:
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            # Restore signal handler
            signal.signal(signal.SIGWINCH, old_handler)


class BaseScreen:
    def __init__(self, app: AppState):
        self.app = app

    def render(self):
        pass

    def handle_input(self, key: str) -> bool:
        if key == Key.QUESTION:
            self.app.push_screen(HelpScreen(self.app))
            return True
        elif key == Key.Q and len(self.app.screen_stack) == 1:
            self.app.running = False
            return True
        elif key == Key.ESCAPE:
            if len(self.app.screen_stack) > 1:
                self.app.pop_screen()
                return True
        return False


class CommandLine:
    def __init__(self):
        self.text = ""
        self.cursor_pos = 0

    def insert(self, char: str):
        self.text = self.text[: self.cursor_pos] + char + self.text[self.cursor_pos :]
        self.cursor_pos += 1

    def delete_back(self):
        if self.cursor_pos > 0:
            self.text = self.text[: self.cursor_pos - 1] + self.text[self.cursor_pos :]
            self.cursor_pos -= 1

    def delete_forward(self):
        if self.cursor_pos < len(self.text):
            self.text = self.text[: self.cursor_pos] + self.text[self.cursor_pos + 1 :]

    def move_left(self):
        if self.cursor_pos > 0:
            self.cursor_pos -= 1

    def move_right(self):
        if self.cursor_pos < len(self.text):
            self.cursor_pos += 1

    def move_start(self):
        self.cursor_pos = 0

    def move_end(self):
        self.cursor_pos = len(self.text)

    def _is_word_char(self, char):
        return char.isalnum() or char == "_"

    def move_word_left(self):
        # Skip spaces
        while self.cursor_pos > 0 and not self._is_word_char(
            self.text[self.cursor_pos - 1]
        ):
            self.cursor_pos -= 1
        # Skip word
        while self.cursor_pos > 0 and self._is_word_char(
            self.text[self.cursor_pos - 1]
        ):
            self.cursor_pos -= 1

    def move_word_right(self):
        n = len(self.text)
        # Skip word characters
        while self.cursor_pos < n and self._is_word_char(self.text[self.cursor_pos]):
            self.cursor_pos += 1
        # Skip spaces
        while self.cursor_pos < n and not self._is_word_char(
            self.text[self.cursor_pos]
        ):
            self.cursor_pos += 1

    def delete_word_back(self):
        start = self.cursor_pos
        self.move_word_left()
        new_pos = self.cursor_pos
        self.text = self.text[:new_pos] + self.text[start:]
        self.cursor_pos = new_pos

    def delete_to_start(self):
        self.text = self.text[self.cursor_pos :]
        self.cursor_pos = 0

    def clear(self):
        self.text = ""
        self.cursor_pos = 0


class TestPopupScreen(BaseScreen):
    def __init__(self, app: AppState):
        super().__init__(app)

    def render(self):
        console = self.app.console
        width, height = console.size

        panel = Panel(
            Text("test", justify="center", style="bold green"),
            title="Info",
            border_style="green",
            padding=(1, 5),
        )

        # Center the popup vertically
        # We assume clean screen for now, but in reality we might want overlay.
        # But 'render' clears screen in main loop.
        # To strictly follow requirements "Flash test" or just "popup test"
        # We'll just render it centered.

        ph = 7
        pad_top = max(0, (height - ph) // 2)

        console.print("\n" * pad_top)
        console.print(panel, justify="center")

        # Fill rest
        used = pad_top + ph
        if used < height:
            console.print("\n" * (height - used - 1))

        # console.print("[Enter/Esc] Close", justify="center", style="dim")

    def handle_input(self, key: str) -> bool:
        if key in (Key.ESCAPE, Key.ENTER):
            self.app.pop_screen()
            return True
        return False


class ViewScreen(BaseScreen):
    """
    Base class for View Screens with variable row height block pagination.
    """

    HEADER_HEIGHT = 2
    TABLE_HEADER_HEIGHT = 2
    FOOTER_HEIGHT = 2
    SAFETY_MARGIN = 1
    RESERVED_ROWS = HEADER_HEIGHT + TABLE_HEADER_HEIGHT + FOOTER_HEIGHT + SAFETY_MARGIN

    def __init__(self, app: AppState, title: str):
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
        cmd = self.command_line.text.strip()
        if not cmd:
            return

        if cmd == "test":
            self.app.push_screen(TestPopupScreen(self.app))
        elif cmd == "fetch":
            # Pass filters if available (from ArticlesViewScreen)
            sources = getattr(self, "selected_sources", set())
            topics = getattr(self, "selected_topics", set())

            fetch_screen = FetchScreen(self.app, sources, topics)
            fetch_screen.run()
            self.refresh_data()
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
            # Allow propagate if not active

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


class ArticlesViewScreen(ViewScreen):
    def __init__(self, app: AppState):
        super().__init__(app, "Info Radar [Articles]")

        # Filter State
        self.selected_sources = set()
        self.selected_topics = set()

        # Sort State
        # options: 'date_desc', 'rating_desc', 'rating_asc'
        self.current_sort = "date_desc"

        self.refresh_data()

        self.show_details = True

        self.apply_current_sort()

        # Build hub slug map from config
        self.hub_map = {}
        sources = self.app.engine.config.get("sources", {})
        for source_cfg in sources.values():
            hubs = source_cfg.get("hubs", [])
            for hub in hubs:
                if isinstance(hub, dict) and "id" in hub and "slug" in hub:
                    self.hub_map[hub["id"]] = hub["slug"]

    def apply_current_sort(self):
        if self.current_sort == "date_desc":
            self.sort_key = lambda a: a.published_date
            self.sort_reverse = True
        elif self.current_sort == "rating_desc":
            self.sort_key = lambda a: (a.extra_data.get("rating") or 0)
            self.sort_reverse = True
        elif self.current_sort == "rating_asc":
            self.sort_key = lambda a: (a.extra_data.get("rating") or 0)
            self.sort_reverse = False

        elif self.current_sort == "views_desc":
            self.sort_key = lambda a: self._parse_metric(a.extra_data.get("views"))
            self.sort_reverse = True
        elif self.current_sort == "views_asc":
            self.sort_key = lambda a: self._parse_metric(a.extra_data.get("views"))
            self.sort_reverse = False

        elif self.current_sort == "comments_desc":
            self.sort_key = lambda a: self._parse_metric(a.extra_data.get("comments"))
            self.sort_reverse = True
        elif self.current_sort == "comments_asc":
            self.sort_key = lambda a: self._parse_metric(a.extra_data.get("comments"))
            self.sort_reverse = False

        elif self.current_sort == "bookmarks_desc":
            self.sort_key = lambda a: self._parse_metric(a.extra_data.get("bookmarks"))
            self.sort_reverse = True
        elif self.current_sort == "bookmarks_asc":
            self.sort_key = lambda a: self._parse_metric(a.extra_data.get("bookmarks"))
            self.sort_reverse = False

        self.apply_filter_and_sort()

    def _parse_metric(self, val: Any) -> float:
        if val is None:
            return 0
        if isinstance(val, (int, float)):
            return float(val)

        s = str(val).lower().replace(",", ".").strip()
        try:
            if s.endswith("k"):
                return float(s[:-1]) * 1000
            elif s.endswith("m"):
                return float(s[:-1]) * 1000000
            else:
                return float(s)
        except ValueError:
            return 0

    def handle_input(self, key: str) -> bool:
        if self.command_mode:
            return super().handle_input(key)

        if key == Key.R:
            # Cycle sort modes: date_desc -> rating_desc -> rating_asc -> rating_desc
            if self.current_sort == "date_desc":
                self.current_sort = "rating_desc"
            elif self.current_sort == "rating_desc":
                self.current_sort = "rating_asc"
            else:  # rating_asc or any other
                self.current_sort = "rating_desc"

            self.apply_current_sort()
            return True

        if key == Key.V:
            if self.current_sort == "views_desc":
                self.current_sort = "views_asc"
            else:
                self.current_sort = "views_desc"
            self.apply_current_sort()
            return True

        if key == Key.C:
            if self.current_sort == "comments_desc":
                self.current_sort = "comments_asc"
            else:
                self.current_sort = "comments_desc"
            self.apply_current_sort()
            return True

        if key == Key.B:
            if self.current_sort == "bookmarks_desc":
                self.current_sort = "bookmarks_asc"
            else:
                self.current_sort = "bookmarks_desc"
            self.apply_current_sort()
            return True

        elif key == Key.ESCAPE:
            # If command mode is handled above, this is for normal mode ESC
            if self.current_sort != "date_desc":
                self.current_sort = "date_desc"
                self.apply_current_sort()
                return True
            # Otherwise allow bubbling up (which pops screen)
            return super().handle_input(key)

        if key == Key.S:  # s - Source Filter (Remapped from Sort)
            self.app.push_screen(SourceFilterScreen(self.app, self))
            return True
        elif key == Key.T:  # t - Topic Filter
            self.app.push_screen(TopicFilterScreen(self.app, self))
            return True
        elif key == Key.F:  # f - Fetch
            fetch_screen = FetchScreen(
                self.app, self.selected_sources, self.selected_topics
            )
            fetch_screen.run()
            self.refresh_data()
            return True
        elif (
            key == Key.SHIFT_G and False
        ):  # Disable G for now if needed, but S is Shift+s
            pass

        # Remap Sort to S (Shift+s) check
        # In our key map: 'S' is returned for 's' or 'S'?
        # tui.py:203: if ch == 's' or ch == 'S': return Key.S
        # The key mapping returns Key.S for both 's' and 'S'.
        # We need to distinguish 's' and 'S'.
        # Currently the get_key implementation maps both to Key.S.
        # I cannot distinguish easily without changing get_key or Key constants.
        # But wait, Key.S is just string 's'.
        # If I want Shift+S, I need to know case.
        # The current `get_key` implementation:
        # if ch == 's' or ch == 'S': return Key.S
        # This makes 's' and 'S' indistinguishable.
        # I will rely on the plan: S is Source Filter. Sort is moved or remapped?
        # Plan said: "Remap Sort to S (Shift+s) to preserve it."
        # But I can't if they return same key.
        # I will assume 's' opens Source Filter.
        # I will bind `s` to Source Filter.
        # I will bind `t` to Topic Filter.
        # I will bind `S` (Shift+s) to Sort if I can fix get_key, otherwise I will pick another key, e.g., 'o' (Order).
        # But 'o' is Open.
        # Let's check 'ActionScreen' binding.
        # FilterActionScreen was 'f'. Now 'f' is global fetch.

        if super().handle_input(key):
            return True

        if key == Key.D:
            self.show_details = not self.show_details
            return True
        return False

    def refresh_data(self):
        # Fetch ALL articles
        self.items = self.app.engine.get_articles(read=None)
        self.apply_filter_and_sort()

    def apply_filter_and_sort(self):
        # 1. Filter by Text
        if not self.filter_text:
            filtered = list(self.items)
        else:
            filter_lower = self.filter_text.lower()
            filtered = [
                item for item in self.items if filter_lower in str(item).lower()
            ]

        # 2. Filter by Source
        if self.selected_sources:
            filtered = [
                item for item in filtered if item.source in self.selected_sources
            ]

        # 3. Filter by Topic
        if self.selected_topics:
            filtered = [
                item
                for item in filtered
                if self._get_topic_slug(item) in self.selected_topics
            ]

        self.filtered_items = filtered

        # 4. Sort
        if self.sort_key:
            self.filtered_items.sort(key=self.sort_key, reverse=self.sort_reverse)

        # Update Header Title
        # Update Header Title
        parts = ["[bold green dim]Info Radar[/bold green dim]"]
        if self.selected_sources:
            items = ", ".join(sorted(self.selected_sources))
            parts.append(
                f"[dim]Sources[/dim] [[bold white]{escape(items)}[/bold white]]"
            )
        if self.selected_topics:
            items = ", ".join(sorted(self.selected_topics))
            parts.append(
                f"[dim]Topics[/dim] [[bold white]{escape(items)}[/bold white]]"
            )

        if self.current_sort == "rating_desc":
            parts.append("[dim]Rating[/dim] [bold white]↓[/bold white]")
        elif self.current_sort == "rating_asc":
            parts.append("[dim]Rating[/dim] [bold white]↑[/bold white]")
        elif self.current_sort == "views_desc":
            parts.append("[dim]Views[/dim] [bold white]↓[/bold white]")
        elif self.current_sort == "views_asc":
            parts.append("[dim]Views[/dim] [bold white]↑[/bold white]")
        elif self.current_sort == "comments_desc":
            parts.append("[dim]Comments[/dim] [bold white]↓[/bold white]")
        elif self.current_sort == "comments_asc":
            parts.append("[dim]Comments[/dim] [bold white]↑[/bold white]")
        elif self.current_sort == "bookmarks_desc":
            parts.append("[dim]Bookmarks[/dim] [bold white]↓[/bold white]")
        elif self.current_sort == "bookmarks_asc":
            parts.append("[dim]Bookmarks[/dim] [bold white]↑[/bold white]")

        self.title = " | ".join(parts)

        # Reset to start
        self.start_index = 0

    def _get_topic_slug(self, item: Article) -> str:
        if item.extra_data.get("hub_id") in self.hub_map:
            return self.hub_map[item.extra_data["hub_id"]]
        elif item.extra_data and "tags" in item.extra_data and item.extra_data["tags"]:
            return item.extra_data["tags"][0]
        return ""

    def _format_compact(self, val: Any) -> str:
        """
        Formats numbers to compact string (e.g. '1.2k').
        """
        s_val = ""
        if val is None:
            s_val = "-"
        elif isinstance(val, (int, float)) or (
            isinstance(val, str) and val.replace(".", "", 1).isdigit()
        ):
            try:
                n = float(val)
                if n == 0:
                    s_val = "-"
                elif n < 1000:
                    s_val = f"{int(n)}"
                elif n < 1000000:
                    k = n / 1000
                    if k < 10:
                        s_val = f"{k:.1f}k".replace(".0k", "k")
                    else:
                        s_val = f"{int(k)}k"
                else:
                    m = n / 1000000
                    if m < 10:
                        s_val = f"{m:.1f}M".replace(".0M", "M")
                    else:
                        s_val = f"{int(m)}M"
            except ValueError:
                s_val = str(val)
        else:
            s_val = str(val)

        return s_val

    def render_row(self, item: Article, index: int) -> Tuple[List[str], str]:
        # Columns: #, Article, Source, Topic, Date, R, V, C, B

        idx_str = f"[green dim]{index}[/green dim]"
        title = item.title

        row = [idx_str, title]

        if self.show_details:
            source = f"[dim]{item.source or '?'}[/dim]"

            # Topic resolution
            topic_raw = ""
            if item.extra_data.get("hub_id") in self.hub_map:
                topic_raw = self.hub_map[item.extra_data["hub_id"]]
            elif (
                item.extra_data
                and "tags" in item.extra_data
                and item.extra_data["tags"]
            ):
                topic_raw = item.extra_data["tags"][0]

            topic = f"[dim]{topic_raw}[/dim]"

            d = item.published_date
            date_str = f"[dim]{d.day}-{d.strftime('%b')}-{d.strftime('%y')}[/dim]"

            # Details: Split into R, V, C, B

            # 1. Rating
            r_val = item.extra_data.get("rating", 0) or 0
            if isinstance(r_val, str) and not r_val.replace("-", "").isdigit():
                r_val = 0
            r_val = int(r_val)

            r_str = str(r_val)
            if r_val > 0:
                r_cell = f"[bold green]{r_str}[/bold green]"
            elif r_val < 0:
                r_cell = f"[bold red]{r_str}[/bold red]"
            else:
                r_cell = f"[dim]-[/dim]"  # Default to dash if 0

            # Helper for other metrics
            def fmt_metric(key, icon, fallback="-"):
                val = item.extra_data.get(key)
                # Special handling for comments count
                if key == "comments":
                    if val is None and item.comments_data:
                        val = len(item.comments_data)
                    elif val is None:
                        val = 0

                # Bookmarks fallback
                if key == "bookmarks" and val is None:
                    val = fallback

                if val is None:
                    val = fallback

                s_v = self._format_compact(val)
                return f"[dim]{icon} {s_v}[/dim]"

            v_cell = fmt_metric("views", "👁")
            c_cell = fmt_metric("comments", "💬", "0")
            b_cell = fmt_metric("bookmarks", "🔖", "-")

            row.extend([source, topic, date_str, r_cell, v_cell, c_cell, b_cell])

        style = ""

        return row, style

    def get_columns(self, width: int) -> List[Dict[str, Any]]:
        # Order: #, Article, Source, Topic, Date, Details

        cols = []
        cols.append({"header": "#", "justify": "right", "no_wrap": True})
        cols.append(
            {"header": "Article", "ratio": 1, "no_wrap": True, "overflow": "ellipsis"}
        )

        if self.show_details:
            cols.append({"header": "Source", "justify": "left", "no_wrap": True})
            cols.append({"header": "Topic", "justify": "left", "no_wrap": True})
            cols.append({"header": "Date", "justify": "center", "no_wrap": True})

            # Metric columns
            cols.append({"header": "⭐", "justify": "right", "no_wrap": True})
            cols.append({"header": "👁", "justify": "left", "no_wrap": True})
            cols.append({"header": "💬", "justify": "left", "no_wrap": True})
            cols.append({"header": "🔖", "justify": "left", "no_wrap": True})

        return cols

    def on_select(self, item: Article):
        self.app.push_screen(ArticleDetailScreen(self.app, item))


class MultiSelectScreen(ViewScreen):
    """
    Base screen for multiple selection from a list of items.
    """

    def __init__(
        self,
        app: AppState,
        parent_screen: "ArticlesViewScreen",
        title: str,
        items: List[str],
        selected: set,
    ):
        super().__init__(app, title)
        self.parent_screen = parent_screen
        self.items = sorted(list(set(items)))
        self.selected = set(selected)
        self.cursor_index = 0
        self.apply_filter_and_sort()

    def handle_cursor_input(self, key: str) -> bool:
        # Cursor movement
        console_height = self.app.console.size[1]
        available_rows = max(1, console_height - self.RESERVED_ROWS)

        if key == Key.UP or key == Key.K:
            self.cursor_index = max(0, self.cursor_index - 1)
            # Adjust start_index if cursor moves out of view
            if self.cursor_index < self.start_index:
                self.start_index = self.cursor_index
            return True
        elif key == Key.DOWN or key == Key.J:
            self.cursor_index = min(len(self.filtered_items) - 1, self.cursor_index + 1)
            # Adjust start_index if cursor moves out of view
            if self.cursor_index >= self.start_index + available_rows:
                self.start_index = self.cursor_index - available_rows + 1
            return True
        elif key == Key.SPACE:  # Space = Toggle
            if 0 <= self.cursor_index < len(self.filtered_items):
                item = self.filtered_items[self.cursor_index]
                if item in self.selected:
                    self.selected.remove(item)
                else:
                    self.selected.add(item)
            return True

        elif key == Key.ENTER:  # Enter = Apply
            self.on_apply()
            self.app.pop_screen()
            return True

        elif key == Key.ESCAPE:  # Esc = Cancel (Clear/Reset)
            # "сбрасывает все выделение" - interpreted as reset filter to empty and close?
            # Or reset to empty and apply that (i.e. clear filter)?
            # The prompt says: "Esc ... apply". Now "Esc ... Cancel".
            # If Cancel means "Don't apply changes", that contradicts "сбрасывает все выделение".
            # "сбрасывает все выделение" means Clear Selection.
            # If I clear selection and close, isn't that same as Applying Empty Selection?
            # Yes, effectively clearing the filter.
            # So Esc -> Clear Selection -> Apply (which clears filter) -> Close.
            self.selected.clear()
            self.on_apply()
            self.app.pop_screen()
            return True

        elif key == Key.Q or key == "q":
            # Apply and Close
            self.on_apply()
            self.app.pop_screen()
            return True

        return super().handle_input(key)

    def handle_input(self, key: str) -> bool:
        if self.command_mode:
            return super().handle_input(key)
        return self.handle_cursor_input(key)

    def render_row(self, item: Any, index: int) -> Tuple[List[str], str]:
        return [], ""

    def get_columns(self, width: int) -> List[Dict[str, Any]]:
        return [
            {"header": "", "width": 5, "no_wrap": True},
            {"header": "Name", "ratio": 1},
        ]

    def render(self):
        # Override render to highlight cursor row
        console = self.app.console
        width, height = console.size

        console.print(self.title, style="bold green dim", justify="center")

        available_rows = height - self.RESERVED_ROWS
        if available_rows < 1:
            available_rows = 1

        # Ensure start_index is valid for cursor
        if self.cursor_index < self.start_index:
            self.start_index = self.cursor_index
        if self.cursor_index >= self.start_index + available_rows:
            self.start_index = self.cursor_index - available_rows + 1

        self.current_page_items = self.calculate_visible_range(
            self.start_index, available_rows, width
        )

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
            # i is index relative to page
            # abs_index is index in filtered_items
            abs_index = self.start_index + i

            is_selected = item in self.selected

            # Select column
            sel_char = "[*]" if is_selected else "[ ]"
            name_char = str(item)

            row_data = [sel_char, name_char]

            style = ""

            # Selected logic: No background color
            # Active/Cursor logic: Reverse green

            if abs_index == self.cursor_index:
                # Cursor: Reverse Green
                style = "reverse green"

            table.add_row(*row_data, style=style)

        console.print(table)

        # Footer
        footer_text = f"Page [green dim]{(self.start_index // available_rows) + 1}[/green dim] | [[bold white]Space[/bold white]] Toggle [[bold white]Enter[/bold white]] Apply [[bold white]Esc[/bold white]] Clear"
        console.print(Text.from_markup(footer_text), style="dim", justify="center")

    def on_apply(self):
        pass

    def on_reset(self):
        pass


class SourceFilterScreen(MultiSelectScreen):
    def __init__(self, app: AppState, parent_screen: "ArticlesViewScreen"):
        sources = list(app.engine.config.get("sources", {}).keys())
        super().__init__(
            app,
            parent_screen,
            "Filter Sources",
            sources,
            parent_screen.selected_sources,
        )

    def on_apply(self):
        self.parent_screen.selected_sources = self.selected
        self.parent_screen.apply_filter_and_sort()

    def on_reset(self):
        self.parent_screen.selected_sources = set()
        self.parent_screen.apply_filter_and_sort()


class TopicFilterScreen(MultiSelectScreen):
    def __init__(self, app: AppState, parent_screen: "ArticlesViewScreen"):
        # Gather all hubs/topics from sources
        valid_sources = parent_screen.selected_sources

        topics = set()
        sources_cfg = app.engine.config.get("sources", {})

        for src_name, src_cfg in sources_cfg.items():
            if valid_sources and src_name not in valid_sources:
                continue

            hubs = src_cfg.get("hubs", [])
            for hub in hubs:
                if isinstance(hub, dict):
                    topics.add(hub.get("slug", "unknown"))
                else:
                    topics.add(str(hub))

        super().__init__(
            app,
            parent_screen,
            "Filter Topics",
            list(topics),
            parent_screen.selected_topics,
        )

    def on_apply(self):
        self.parent_screen.selected_topics = self.selected
        self.parent_screen.apply_filter_and_sort()

    def on_reset(self):
        self.parent_screen.selected_topics = set()
        self.parent_screen.apply_filter_and_sort()


class ActionScreen(BaseScreen):
    def __init__(self, app: AppState, parent_screen: ViewScreen):
        super().__init__(app)
        self.parent_screen = parent_screen

    def handle_input(self, key: str) -> bool:
        if key == Key.ESCAPE:
            self.app.pop_screen()
            return True
        else:
            return super().handle_input(key)


class FilterActionScreen(ActionScreen):
    def __init__(self, app: AppState, parent_screen: ViewScreen):
        super().__init__(app, parent_screen)
        self.input_text = parent_screen.filter_text

    def render(self):
        console = self.app.console
        console.clear()

        panel = Panel(
            f"Filter: {self.input_text}_",
            title="Filter Articles",
            border_style="yellow",
        )
        console.print(panel)
        console.print(
            Text.from_markup(
                "\n[[white]Enter[/white]] Apply  [[white]Esc[/white]] Cancel"
            ),
            style="dim",
        )

    def handle_input(self, key: str) -> bool:
        if key == Key.ENTER:
            self.parent_screen.filter_text = self.input_text
            self.parent_screen.apply_filter_and_sort()
            self.app.pop_screen()
            return True
        elif key == Key.BACKSPACE:
            self.input_text = self.input_text[:-1]
            return True
        elif key == Key.ESCAPE:
            self.app.pop_screen()
            return True
        elif len(key) == 1 and key.isprintable():
            self.input_text += key
            return True
        return False


class SortActionScreen(ActionScreen):
    def __init__(self, app: AppState, parent_screen: ViewScreen):
        super().__init__(app, parent_screen)
        self.options = [
            ("Date (Newest)", lambda a: a.published_date, True),
            ("Date (Oldest)", lambda a: a.published_date, False),
            ("Source", lambda a: a.source or "", False),
            ("Title", lambda a: a.title, False),
        ]
        self.selected = 0

    def render(self):
        console = self.app.console
        console.clear()

        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("Option")

        for i, (name, _, _) in enumerate(self.options):
            style = "reverse green" if i == self.selected else ""
            table.add_row(name, style=style)

        panel = Panel(table, title="Sort By", border_style="green")
        console.print(panel)
        console.print("\n[Enter] Select  [Esc] Cancel", style="dim")

    def handle_input(self, key: str) -> bool:
        if key == Key.UP or key == Key.K:
            self.selected = max(0, self.selected - 1)
            return True
        elif key == Key.DOWN or key == Key.J:
            self.selected = min(len(self.options) - 1, self.selected + 1)
            return True
        elif key == Key.ENTER:
            _, sort_key, reverse = self.options[self.selected]
            self.parent_screen.sort_key = sort_key
            self.parent_screen.sort_reverse = reverse
            self.parent_screen.apply_filter_and_sort()
            self.app.pop_screen()
            return True
        else:
            return super().handle_input(key)


class SyncActionScreen(ActionScreen):
    def __init__(self, app: AppState, parent_screen: ViewScreen):
        super().__init__(app, parent_screen)
        self.started = False

    def render(self):
        if not self.started:
            self.started = True
            self.run_sync()

    def run_sync(self):
        console = self.app.console
        console.clear()

        # Setup UI components
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeRemainingColumn(),
        )

        log_text = Text()
        log_panel_height = 15
        all_log_lines = []

        def log_message(msg: str):
            timestamp = datetime.now().strftime("%H:%M:%S")
            all_log_lines.append(f"[{timestamp}] {msg}")
            # Keep only last N lines
            visible_lines = all_log_lines[-log_panel_height + 2 :]
            log_text.plain = "\n".join(visible_lines)

        header = Panel(
            Text("Syncing Articles...", justify="center"), style="bold white on blue"
        )

        layout = Group(
            header,
            Text(""),
            progress,
            Text(""),
            Panel(
                log_text,
                title="Sync Log",
                border_style="green",
                height=log_panel_height,
            ),
        )

        sources = self.app.engine.config.get("sources", {})
        task = progress.add_task("Syncing...", total=len(sources))

        with Live(layout, console=console, refresh_per_second=10):
            for name in sources.keys():
                self.app.engine.run_sync(
                    source_name=name, progress=progress, log_callback=log_message
                )
                progress.advance(task, 1)

            log_message("Sync completed! Press Esc to return.")

        # Wait for Esc
        while True:
            key = get_key()
            if key == Key.ESCAPE:
                break

        self.parent_screen.refresh_data()
        self.app.pop_screen()


class ArticleDetailScreen(BaseScreen):
    def __init__(self, app: AppState, article: Article):
        super().__init__(app)
        self.article = article
        self.scroll_offset = 0
        self.total_lines = 0
        self.visible_height = 0

    def render(self):
        console = self.app.console
        width, height = console.size

        # Header
        header = Panel(
            Text(
                f"Article: {self.article.title}", justify="center", style="bold white"
            ),
            style="blue",
        )
        console.print(header)

        # Content
        content_height = height - 6

        md_content = self.article.content_md or "*No content available*"

        with console.capture() as capture:
            console.print(Markdown(md_content))
        full_text = capture.get()
        lines = full_text.splitlines()
        self.total_lines = len(lines)
        self.visible_height = content_height

        # Slice lines
        visible_lines = lines[self.scroll_offset : self.scroll_offset + content_height]

        for line in visible_lines:
            console.print(line)

        # Fill empty space
        for _ in range(content_height - len(visible_lines)):
            console.print("")

        # Footer
        footer_text = f"Lines {self.scroll_offset}-{self.scroll_offset+len(visible_lines)}/{len(lines)} | [Esc]Back [Up/Down]Scroll"
        console.print(Panel(footer_text, style="grey50"))

        # Mark as read
        if not self.article.status_read:
            self.article.status_read = True
            self.app.engine.update_article_status(self.article.id, read=True)

    def handle_input(self, key: str) -> bool:
        if key == Key.UP or key == Key.K:
            self.scroll_offset = max(0, self.scroll_offset - 1)
            return True
        elif key == Key.DOWN or key == Key.J:
            self.scroll_offset = min(
                self.total_lines - self.visible_height, self.scroll_offset + 1
            )
            return True
        elif key == Key.CTRL_D:
            self.scroll_offset = min(
                self.total_lines - self.visible_height,
                self.scroll_offset + self.visible_height,
            )
            return True
        elif key == Key.CTRL_U:
            self.scroll_offset = max(0, self.scroll_offset - self.visible_height)
            return True
        else:
            return super().handle_input(key)


class HelpScreen(BaseScreen):
    def __init__(self, app: AppState):
        super().__init__(app)

    def render(self):
        console = self.app.console

        console.print("Help", style="bold cyan", justify="center")
        console.print()

        nav_content = """[bold cyan]j / k[/bold cyan] - Next / Previous block
[bold cyan]g / G[/bold cyan] - First / Last page
[bold cyan]0-9 + Enter[/bold cyan] - Open article by number
[bold cyan]Ctrl+D / U[/bold cyan] - Scroll content (in article)"""

        nav_panel = Panel(
            nav_content, title="Navigation", border_style="blue", expand=False
        )
        console.print(nav_panel)
        console.print()

        action_content = """[bold green]r[/bold green] - Sort by Rating
[bold green]v[/bold green] - Sort by Views
[bold green]c[/bold green] - Sort by Comments
[bold green]b[/bold green] - Sort by Bookmarks
[bold green]s[/bold green] - Filter by Source
[bold green]t[/bold green] - Filter by Topic
[bold green]f[/bold green] - Filter by Text
[bold green]?[/bold green] - Show this help screen"""

        action_panel = Panel(
            action_content, title="Actions", border_style="green", expand=False
        )
        console.print(action_panel)
        console.print()

        exit_content = """[bold red]Esc[/bold red] - Go back
[bold red]q[/bold red] - Quit application"""

        exit_panel = Panel(exit_content, title="Exit", border_style="red", expand=False)
        console.print(exit_panel)
        console.print()

        console.print(
            "Press [bold]Esc[/bold] to close help", style="dim", justify="center"
        )

    def handle_input(self, key: str) -> bool:
        if key == Key.ESCAPE:
            self.app.pop_screen()
            return True
        else:
            return super().handle_input(key)


class FetchScreen(BaseScreen):
    """Screen for fetching articles with progress and logs."""

    def __init__(
        self, app: "AppState", selected_sources: set = None, selected_topics: set = None
    ):
        super().__init__(app)
        self.selected_sources = selected_sources or set()
        self.selected_topics = selected_topics or set()

        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TimeRemainingColumn(),
            expand=True,
        )
        self.logs: List[str] = []
        self.cancel_event = threading.Event()
        self.worker_thread = None
        self.lock = threading.Lock()

        self.state = "init"  # "init", "running", "cancelled", "finished"

    def work(self):
        """The actual fetch logic that runs in a background thread."""

        def log_cb(msg):
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.logs.append(f"[{timestamp}] {msg}")

        try:
            self.app.engine.run_sync(
                source_names=(
                    list(self.selected_sources) if self.selected_sources else None
                ),
                log_callback=log_cb,
                progress=self.progress,
                cancel_event=self.cancel_event,
            )
            with self.lock:
                self.logs.append("[green]Fetch completed.[/green]")
                self.state = "finished"
        except Exception as e:
            with self.lock:
                self.logs.append(f"[red]Error: {str(e)}[/red]")
                self.state = "finished"
        finally:
            if self.cancel_event.is_set() and self.state != "finished":
                with self.lock:
                    self.logs.append("[yellow]Fetch cancelled by user.[/yellow]")
                    self.state = "cancelled"

    def start_fetch(self):
        if self.state == "init":
            self.state = "running"
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.logs.append(f"[{timestamp}] [cyan]Starting fetch...[/cyan]")
            self.worker_thread = threading.Thread(target=self.work, daemon=True)
            self.worker_thread.start()

    def cancel_fetch(self):
        if self.state == "running":
            self.cancel_event.set()
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.logs.append(f"[{timestamp}] [yellow]Cancelling...[/yellow]")
            # The worker thread will see the event and stop

    def _build_header_text(self) -> str:
        """Builds header text matching the main screen's styling."""
        parts = ["[bold green dim]Fetch[/bold green dim]"]

        sources_config = self.app.engine.config.get("sources", {})
        cutoff_dates = [
            cfg.get("initial_fetch_date", "").split()[0]
            for cfg in sources_config.values()
            if "initial_fetch_date" in cfg
        ]
        if cutoff_dates:
            parts.append(
                f"[dim]Cutoff[/dim] [bold white]{min(cutoff_dates)}[/bold white]"
            )

        if self.selected_sources:
            items = ", ".join(sorted(self.selected_sources))
            parts.append(
                f"[dim]Sources[/dim] [[bold white]{escape(items)}[/bold white]]"
            )

        if self.selected_topics:
            items = ", ".join(sorted(self.selected_topics))
            parts.append(
                f"[dim]Topics[/dim] [[bold white]{escape(items)}[/bold white]]"
            )

        return " | ".join(parts)

    def _build_layout(self) -> Group:
        """Assembles the renderable layout for the Live display."""
        header = self._build_header_text()
        log_panel_height = max(5, self.app.console.height - 8)
        log_content_height = log_panel_height - 2

        with self.lock:
            visible_logs = (
                self.logs[-log_content_height:] if log_content_height > 0 else []
            )
            log_content = "\n".join(visible_logs)

        logs_panel = Panel(
            Text.from_markup(log_content),
            title="Logs",
            border_style="green",
            height=log_panel_height,
            expand=True,
        )

        footer_text = ""
        if self.state == "init":
            footer_text = (
                "[[bold white]s[/bold white]] Start [[bold white]q[/bold white]] Exit"
            )
        elif self.state == "running":
            footer_text = "[[bold white]q[/bold white]] Cancel"
        else:  # "finished" or "cancelled"
            footer_text = "[[bold white]q[/bold white]] Close"

        return Group(
            Text.from_markup(header, justify="center"),
            "",
            self.progress,
            logs_panel,
            Text.from_markup(footer_text, style="dim", justify="center"),
        )

    def run(self):
        """Blocking method that runs the fetch process within a Live context."""
        with Live(
            self._build_layout(),
            console=self.app.console,
            screen=True,
            refresh_per_second=10,
        ) as live:
            while not self.cancel_event.is_set():
                live.update(self._build_layout())
                key = get_key()
                if key:
                    if key in (Key.Q, Key.ESCAPE):
                        if self.state == "running":
                            self.cancel_fetch()
                        else:
                            break  # Exit the loop and screen
                    elif key == Key.S and self.state == "init":
                        self.start_fetch()

                # Check if worker is done
                if (
                    self.state in ("finished", "cancelled")
                    and self.worker_thread
                    and not self.worker_thread.is_alive()
                ):
                    # Just wait for final 'q'
                    pass

                # Exit loop if worker finished and we are not in running state
                if (
                    self.state != "running"
                    and self.worker_thread
                    and not self.worker_thread.is_alive()
                ):
                    # Final render, then wait for q
                    live.update(self._build_layout())
                    while get_key() not in (Key.Q, Key.ESCAPE):
                        time.sleep(0.1)
                    break

                time.sleep(0.05)


if __name__ == "__main__":
    app = AppState()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
