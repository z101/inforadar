from typing import Any, Dict, List, Tuple, TYPE_CHECKING

from rich import box
from rich.table import Table
from rich.text import Text

from inforadar.tui.screens.view_screen import ViewScreen
from inforadar.tui.keys import Key

if TYPE_CHECKING:
    from inforadar.tui.app import AppState
    from inforadar.tui.screens.articles_view import ArticlesViewScreen


class MultiSelectScreen(ViewScreen):
    """
    Base screen for multiple selection from a list of items.
    """

    def __init__(
        self,
        app: "AppState",
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
        
        elif key == Key.BACKSPACE: # Clear selection
            self.selected.clear()
            return True

        elif key == Key.ESCAPE or key == Key.Q or key == "q":  # Esc/q = Cancel/Close
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
        footer_text = f"Page [green dim]{(self.start_index // available_rows) + 1}[/green dim] | [[bold white]Space[/bold white]] Toggle [[bold white]Enter[/bold white]] Apply [[bold white]Backspace[/bold white]] Clear [[bold white]Esc, q[/bold white]] Close"
        console.print(Text.from_markup(footer_text), style="dim", justify="center")

    def on_apply(self):
        pass

    def on_reset(self):
        pass
