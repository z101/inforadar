from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel
from rich.table import Table

from inforadar.tui.screens.action_screen import ActionScreen
from inforadar.tui.keys import Key

if TYPE_CHECKING:
    from inforadar.tui.app import AppState
    from inforadar.tui.screens.view_screen import ViewScreen


class SortActionScreen(ActionScreen):
    def __init__(self, app: "AppState", parent_screen: "ViewScreen"):
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
