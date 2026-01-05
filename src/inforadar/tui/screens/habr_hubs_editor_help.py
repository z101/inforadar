from rich.align import Align
from rich.panel import Panel
from rich.text import Text

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.keys import Key


class HabrHubsEditorHelpScreen(BaseScreen):
    """A screen that displays help for the Habr Hubs Editor."""

    def handle_input(self, key: str) -> bool:
        # Any key closes the help
        self.app.pop_screen()
        return True

    def render(self) -> Panel:
        """Render the help panel."""
        self.app.console.clear()
        
        help_text = Text.from_markup(
            """
[bold]Hub Editor Key Bindings[/bold]

[bold]Navigation[/bold]
  [green]j, ↓[/green]     - Move cursor down
  [green]k, ↑[/green]     - Move cursor up
  [green]l[/green]         - Next page
  [green]h[/green]         - Previous page
  [green]gg[/green]        - Go to top of list
  [green]G[/green]         - Go to bottom of list
  [green]1-9[/green]      - Select row on page

[bold]Hub Actions[/bold]
  [green]Enter[/green]     - Edit selected hub's Name
  [green]e[/green]         - Toggle 'enabled' status of hub
  [green]o[/green]         - Open hub page in browser
  [green]f[/green]         - Fetch all hubs from Habr

[bold]Sorting[/bold] (toggles asc/desc)
  [green]r[/green]         - Sort by Rating
  [green]s[/green]         - Sort by Subscribers
  [green]n[/green]         - Sort by Name

[bold]Filtering / Commands[/bold]
  [green]/[/green]         - Filter hubs by ID or Name
  [green]:[/green]         - Enter command mode (no commands implemented)

[bold]Application[/bold]
  [green]q, Esc[/green] - Go back
  [green]?[/green]         - Show this help screen
"""
        )

        panel = Panel(
            Align.center(help_text),
            title="[bold blue]Hub Editor Help[/bold blue]",
            border_style="green",
            width=min(self.app.console.width, 60),
        )
        self.app.console.print(panel)
