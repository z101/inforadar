from typing import TYPE_CHECKING

from rich.panel import Panel

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.keys import Key

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class HelpScreen(BaseScreen):
    def __init__(self, app: "AppState"):
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
