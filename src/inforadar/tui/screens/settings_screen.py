from rich.panel import Panel
from rich.align import Align
from .base import BaseScreen


class SettingsScreen(BaseScreen):
    """A screen to display and edit settings."""

    def render(self):
        """Render the settings screen content."""
        self.app.console.print(
            Align.center(
                Panel("Settings screen coming soon!", title="Settings", border_style="green"),
                vertical="middle",
            )
        )
