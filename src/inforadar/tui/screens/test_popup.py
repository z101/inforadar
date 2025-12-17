from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.text import Text

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.keys import Key

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class TestPopupScreen(BaseScreen):
    def __init__(self, app: "AppState"):
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
