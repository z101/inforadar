from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.text import Text

from inforadar.tui.screens.action_screen import ActionScreen
from inforadar.tui.keys import Key

if TYPE_CHECKING:
    from inforadar.tui.app import AppState
    from inforadar.tui.screens.view_screen import ViewScreen


class FilterActionScreen(ActionScreen):
    def __init__(self, app: "AppState", parent_screen: "ViewScreen"):
        super().__init__(app, parent_screen)
        self.input_text = parent_screen.filter_text

    def render(self):
        console = self.app.console

        panel = Panel(
            f"Filter: {self.input_text}_",
            title="Filter Articles",
            border_style="yellow",
        )
        console.print(panel)
        console.print(
            Text.from_markup(
                "\n[[white]Enter[/white]] Apply  [[white]Esc, q[/white]] Cancel"
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
        elif key == Key.ESCAPE or key == Key.Q:
            self.app.pop_screen()
            return True
        elif len(key) == 1 and key.isprintable():
            self.input_text += key
            return True
        return False
