import sys
import os
import click
import math
import textwrap
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
from rich.text import Text
from rich import box
from rich.status import Status
from rich.live import Live
from rich.console import Group
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

from .core import CoreEngine
from .models import Article

class Key:
    UP = 'up'
    DOWN = 'down'
    LEFT = 'left'
    RIGHT = 'right'
    ENTER = 'enter'
    ESCAPE = 'escape'
    Q = 'q'
    S = 's'
    R = 'r'
    F = 'f'
    H = 'h'
    J = 'j'
    K = 'k'
    L = 'l'
    G = 'g'
    SHIFT_G = 'G'
    QUESTION = '?'
    SLASH = '/'
    BACKSPACE = 'backspace'
    CTRL_D = 'ctrl_d'
    CTRL_U = 'ctrl_u'
    UNKNOWN = 'unknown'
    D = 'd'

# Keyboard layout mapping: other layouts -> English
LAYOUT_MAP = {
    # Russian layout
    'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p',
    'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k', 'д': 'l',
    'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm',
    '.': '/',
    # Upper case Russian
    'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y', 'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P',
    'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F', 'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L',
    'Я': 'Z', 'Ч': 'X', 'С': 'C', 'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M',
}

# Resize handling
class ResizeScreen(Exception):
    pass

resize_needed = False

def handle_winch(signum, frame):
    global resize_needed
    resize_needed = True

def get_key() -> str:
    """Reads a key press and decodes escape sequences."""
    global resize_needed

    fd = sys.stdin.fileno()
    while True:
        if resize_needed:
            resize_needed = False
            raise ResizeScreen()
            
        try:
            # Wait for input with timeout to check resize flag
            # Also select should be interrupted by signal (EINTR)
            r, _, _ = select.select([fd], [], [], 0.1)
            if r:
                break
        except (OSError, InterruptedError):
            pass
            
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
            ch = raw_bytes.decode('utf-8')
        except UnicodeDecodeError:
            ch = Key.UNKNOWN
    
    # Handle Escape Sequences (if it was just ESC)
    if ch == '\x1b':
        # Potential escape sequence - check for more data
        if fd in select.select([fd], [], [], 0.01)[0]:
            try:
                ch2 = os.read(fd, 1).decode()
            except OSError:
                return Key.ESCAPE
                
            if ch2 == '[':
                if fd in select.select([fd], [], [], 0.01)[0]:
                    try:
                        ch3 = os.read(fd, 1).decode()
                    except OSError:
                        return Key.ESCAPE
                        
                    if ch3 == 'A': return Key.UP
                    if ch3 == 'B': return Key.DOWN
                    if ch3 == 'C': return Key.RIGHT
                    if ch3 == 'D': return Key.LEFT
            elif ch2 == 'O': # SS3
                 if fd in select.select([fd], [], [], 0.01)[0]:
                    try:
                        ch3 = os.read(fd, 1).decode()
                    except OSError:
                        return Key.ESCAPE
                        
                    if ch3 == 'A': return Key.UP
                    if ch3 == 'B': return Key.DOWN
                    if ch3 == 'C': return Key.RIGHT
                    if ch3 == 'D': return Key.LEFT
        return Key.ESCAPE

    # Handle CTRL+D (EOT) and CTRL+U (NAK)
    if ch == '\x04': return Key.CTRL_D
    if ch == '\x15': return Key.CTRL_U

    # Convert from other keyboard layouts to English
    if ch in LAYOUT_MAP:
        ch = LAYOUT_MAP[ch]

    if ch == '\r': return Key.ENTER
    if ch == '\n': return Key.ENTER
    if ch == '\x7f': return Key.BACKSPACE
    
    if ch == 'q' or ch == 'Q': return Key.Q
    if ch == 's' or ch == 'S': return Key.S
    if ch == 'r' or ch == 'R': return Key.R
    if ch == 'f' or ch == 'F': return Key.F
    if ch == 'h' or ch == 'H': return Key.H
    if ch == 'j' or ch == 'J': return Key.J
    if ch == 'k' or ch == 'K': return Key.K
    if ch == 'l' or ch == 'L': return Key.L
    if ch == 'g': return Key.G
    if ch == 'G': return Key.SHIFT_G
    if ch == '?': return Key.QUESTION
    if ch == '/': return Key.SLASH
    
    # Return digits as is
    if ch.isdigit():
        return ch
        
    return ch

class AppState:
    def __init__(self):
        self.engine = CoreEngine()
        self.console = Console()
        self.running = True
        self.screen_stack: List['BaseScreen'] = []

    def push_screen(self, screen: 'BaseScreen'):
        self.screen_stack.append(screen)

    def pop_screen(self):
        if self.screen_stack:
            self.screen_stack.pop()
        if not self.screen_stack:
            self.running = False

    @property
    def current_screen(self) -> Optional['BaseScreen']:
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
                        self.console.clear()
                        self.current_screen.render()
                        should_render = False
                    
                    try:
                        key = get_key()
                        if self.current_screen:
                            should_render = self.current_screen.handle_input(key)
                    except ResizeScreen:
                        should_render = True
                        # Update console size explicitly if needed (rich usually handles it)
                        size = self.console.size
        except KeyboardInterrupt:
            pass # Handle Ctrl+C gracefully
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
                item for item in self.items 
                if filter_lower in str(item).lower()
            ]
            
        if self.sort_key:
            self.filtered_items.sort(key=self.sort_key, reverse=self.sort_reverse)
            
        # Reset to start
        self.start_index = 0
            
    def render_row(self, item: Any, index: int) -> Tuple[List[str], str]:
        """Return list of cell values and style for the row."""
        return ([str(item)], "")
        
    def get_columns(self, width: int) -> List[Dict[str, Any]]:
        """Return column definitions based on available width."""
        return [{"header": "Item", "no_wrap": True, "overflow": "ellipsis"}]

    def calculate_visible_range(self, start_idx: int, available_rows: int, width: int) -> List[Any]:
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
        console.print(self.title, style="bold green dim", justify="center")
        
        # Calculate available rows for content
        available_rows = height - self.RESERVED_ROWS
        if available_rows < 1: available_rows = 1
        
        # Calculate items for current "page"
        self.current_page_items = self.calculate_visible_range(self.start_index, available_rows, width)
        
        # Table with no_wrap to ensure fixed row height
        table = Table(box=box.SIMPLE_HEAD, padding=0, expand=True, show_footer=False, header_style="bold dim")
        columns = self.get_columns(width)
        for col in columns:
            table.add_column(**col)
            
        for i, item in enumerate(self.current_page_items):
            # Row number on page starts at 1
            row_num = i + 1
            row_data, row_style = self.render_row(item, row_num)
            
            # Highlight if input buffer matches row number
            style = row_style
            if self.input_buffer and self.input_buffer == str(row_num):
                style = "reverse green"
                # Exclude first column from highlighting (reset style to ignore row style)
                # if row_data:
                #     row_data[0] = f"[reset]{row_data[0]}[/reset]"
                
            table.add_row(*row_data, style=style)
        
        console.print(table)
        
        # Footer
        total_items = len(self.filtered_items)
        current_page = (self.start_index // available_rows) + 1
        total_pages = math.ceil(total_items / available_rows) if available_rows > 0 else 1
        if total_pages < 1: total_pages = 1
        
        filter_status = " [FILTERED]" if self.filter_text else ""
        input_status = f" | Goto: {self.input_buffer}" if self.input_buffer else ""
        footer_text = f"Page {current_page} of {total_pages} | Total Articles: {total_items}{filter_status}{input_status}"
        console.print(footer_text, style="dim", justify="center")

    def handle_input(self, key: str) -> bool:
        console_height = self.app.console.size[1]
        available_rows = max(1, console_height - self.RESERVED_ROWS)
        width = self.app.console.size[0]
        
        if key.isdigit():
            # Validate input: must be within 1..len(current_page_items)
            new_buffer = self.input_buffer + key
            if int(new_buffer) <= len(self.current_page_items):
                self.input_buffer = new_buffer
            return True
            
        if key == Key.BACKSPACE:
            if self.input_buffer:
                self.input_buffer = self.input_buffer[:-1]
            return True
            
        if key == Key.ENTER:
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
        
        # Clear buffer on any other navigation key
        buffer_cleared = False
        if self.input_buffer:
            self.input_buffer = ""
            buffer_cleared = True
            
        if key == Key.UP or key == Key.J: # Previous Block (J = Backward)
            if self.start_index > 0:
                # With fixed row height, just go back by available_rows
                self.start_index = max(0, self.start_index - available_rows)
                return True
                
        elif key == Key.DOWN or key == Key.K: # Next Block (K = Forward)
            if self.start_index + len(self.current_page_items) < len(self.filtered_items):
                self.start_index += len(self.current_page_items)
                return True
                
        elif key == Key.G: # First page (Double 'g')
            if self.pending_g:
                if self.start_index != 0:
                    self.start_index = 0
                    self.pending_g = False
                    return True
                self.pending_g = False
            else:
                self.pending_g = True
                return False # Wait for next key
                
        elif key == Key.SHIFT_G: # Last page
            # Calculate the start of the last page
            total = len(self.filtered_items)
            if total > 0:
                # Last page starts at the last block multiple
                last_page_idx = (total - 1) // available_rows
                new_start = last_page_idx * available_rows
                if self.start_index != new_start:
                    self.start_index = new_start
                    return True
                
        elif key == Key.R: # r - Read/Sync
            self.app.push_screen(SyncActionScreen(self.app, self))
            return True
        elif key == Key.F: # f - Filter
            self.app.push_screen(FilterActionScreen(self.app, self))
            return True
        elif key == Key.S: # s - Sort
            self.app.push_screen(SortActionScreen(self.app, self))
            return True
        elif key == Key.L: # l - Next screen (generic)
             pass 
        else:
            if super().handle_input(key):
                return True
                
        if buffer_cleared:
            return True
            
        # Reset pending_g if any other key was processed
        if key != Key.G:
            self.pending_g = False
            
        return False

class ArticlesViewScreen(ViewScreen):
    def __init__(self, app: AppState):
        super().__init__(app, "Info Radar [Articles]")
        self.refresh_data()
        # Default sort: Date descending
        self.sort_key = lambda a: a.published_date
        self.sort_reverse = True
        self.show_details = True
        self.apply_filter_and_sort()
        
        # Build hub slug map from config
        self.hub_map = {}
        sources = self.app.engine.config.get('sources', {})
        for source_cfg in sources.values():
            hubs = source_cfg.get('hubs', [])
            for hub in hubs:
                if isinstance(hub, dict) and 'id' in hub and 'slug' in hub:
                    self.hub_map[hub['id']] = hub['slug']

    def handle_input(self, key: str) -> bool:
        if key == Key.D:
            self.show_details = not self.show_details
            return True
        return super().handle_input(key)

    def refresh_data(self):
        # Fetch ALL articles
        self.items = self.app.engine.get_articles(read=None)
        self.apply_filter_and_sort()

    def _format_compact(self, val: Any) -> str:
        """
        Formats numbers to compact string (e.g. '1.2k').
        """
        s_val = ""
        if val is None:
             s_val = "-"
        elif isinstance(val, (int, float)) or (isinstance(val, str) and val.replace('.','',1).isdigit()):
            try:
                n = float(val)
                if n == 0:
                    s_val = "-"
                elif n < 1000:
                    s_val = f"{int(n)}"
                elif n < 1000000:
                    k = n / 1000
                    if k < 10:
                        s_val = f"{k:.1f}k".replace('.0k', 'k')
                    else:
                        s_val = f"{int(k)}k"
                else:
                    m = n / 1000000
                    if m < 10:
                        s_val = f"{m:.1f}M".replace('.0M', 'M')
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
            if item.extra_data.get('hub_id') in self.hub_map:
                topic_raw = self.hub_map[item.extra_data['hub_id']]
            elif item.extra_data and 'tags' in item.extra_data and item.extra_data['tags']:
                topic_raw = item.extra_data['tags'][0]
            
            topic = f"[dim]{topic_raw}[/dim]"
            
            d = item.published_date
            date_str = f"[dim]{d.day}-{d.strftime('%b')}-{d.strftime('%y')}[/dim]"
            
            # Details: Split into R, V, C, B
            
            # 1. Rating
            r_val = item.extra_data.get('rating', 0) or 0
            if isinstance(r_val, str) and not r_val.replace('-','').isdigit(): r_val = 0
            r_val = int(r_val)
            
            r_str = str(r_val)
            if r_val > 0:
                r_cell = f"[bold green]{r_str}[/bold green]"
            elif r_val < 0:
                r_cell = f"[bold red]{r_str}[/bold red]"
            else:
                r_cell = f"[dim]-[/dim]" # Default to dash if 0
                
            # Helper for other metrics
            def fmt_metric(key, icon, fallback='-'):
                val = item.extra_data.get(key)
                # Special handling for comments count
                if key == 'comments':
                    if val is None and item.comments_data:
                         val = len(item.comments_data)
                    elif val is None:
                         val = 0
                
                # Bookmarks fallback
                if key == 'bookmarks' and val is None:
                     val = fallback

                if val is None: val = fallback
                
                s_v = self._format_compact(val)
                return f"[dim]{icon} {s_v}[/dim]"

            v_cell = fmt_metric('views', '👁')
            c_cell = fmt_metric('comments', '💬', '0')
            b_cell = fmt_metric('bookmarks', '🔖', '-')
            
            row.extend([source, topic, date_str, r_cell, v_cell, c_cell, b_cell])
            
        style = ""
            
        return row, style

    def get_columns(self, width: int) -> List[Dict[str, Any]]:
        # Order: #, Article, Source, Topic, Date, Details
        
        cols = []
        cols.append({"header": "#", "justify": "right", "no_wrap": True})
        cols.append({"header": "Article", "ratio": 1, "no_wrap": True, "overflow": "ellipsis"})

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
            border_style="yellow"
        )
        console.print(panel)
        console.print("\n[Enter] Apply  [Esc] Cancel", style="dim")

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
            visible_lines = all_log_lines[-log_panel_height+2:]
            log_text.plain = "\n".join(visible_lines)

        header = Panel(Text("Syncing Articles...", justify="center"), style="bold white on blue")
        
        layout = Group(
            header,
            Text(""),
            progress,
            Text(""),
            Panel(log_text, title="Sync Log", border_style="green", height=log_panel_height)
        )
        
        sources = self.app.engine.config.get('sources', {})
        task = progress.add_task("Syncing...", total=len(sources))

        with Live(layout, console=console, refresh_per_second=10):
            for name in sources.keys():
                self.app.engine.run_sync(
                    source_name=name, 
                    progress=progress,
                    log_callback=log_message
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
        header = Panel(Text(f"Article: {self.article.title}", justify="center", style="bold white"), style="blue")
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
            self.scroll_offset = min(self.total_lines - self.visible_height, self.scroll_offset + 1)
            return True
        elif key == Key.CTRL_D:
            self.scroll_offset = min(self.total_lines - self.visible_height, self.scroll_offset + self.visible_height)
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
        
        nav_panel = Panel(nav_content, title="Navigation", border_style="blue", expand=False)
        console.print(nav_panel)
        console.print()
        
        action_content = """[bold green]r[/bold green] - Sync articles (Read from internet)
[bold green]f[/bold green] - Filter articles
[bold green]s[/bold green] - Sort articles
[bold green]?[/bold green] - Show this help screen"""
        
        action_panel = Panel(action_content, title="Actions", border_style="green", expand=False)
        console.print(action_panel)
        console.print()
        
        exit_content = """[bold red]Esc[/bold red] - Go back
[bold red]q[/bold red] - Quit application"""
        
        exit_panel = Panel(exit_content, title="Exit", border_style="red", expand=False)
        console.print(exit_panel)
        console.print()
        
        console.print("Press [bold]Esc[/bold] to close help", style="dim", justify="center")

    def handle_input(self, key: str) -> bool:
        if key == Key.ESCAPE:
            self.app.pop_screen()
            return True
        else:
            return super().handle_input(key)

if __name__ == "__main__":
    app = AppState()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
