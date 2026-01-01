from typing import Any, Dict, List, Tuple, TYPE_CHECKING
from .view_screen import ViewScreen

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class SettingsScreen(ViewScreen):
    """A screen to display and edit settings in a table view."""

    def __init__(self, app: "AppState"):
        """Initialise the screen."""
        super().__init__(app, "[green dim bold]Info Radar Settings[/green dim bold]")
        self.name_column_width = 0
        self.refresh_data()

    def _flatten_settings(self, settings: Dict[str, Any], prefix: str = "") -> List[Tuple[str, Any]]:
        """Recursively flattens a nested settings dictionary."""
        flat_list = []
        for key, value in settings.items():
            new_prefix = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                flat_list.extend(self._flatten_settings(value, new_prefix))
            else:
                flat_list.append((new_prefix, value))
        return flat_list

    def refresh_data(self):
        """Load settings from the engine and calculate max name width."""
        all_settings = self.app.engine.settings.all_settings
        self.items = self._flatten_settings(all_settings)
        
        if self.items:
            max_key_len = max(len(key) for key, _ in self.items)
            self.name_column_width = max_key_len + 2  # Add padding
        else:
            self.name_column_width = 20  # Default width

        self.apply_filter_and_sort()

    def get_columns(self, width: int) -> List[Dict[str, Any]]:
        """Return the column definitions for the settings table."""
        return [
            {"header": "#", "justify": "right", "no_wrap": True},
            {"header": "Name", "width": self.name_column_width, "no_wrap": True},
            {"header": "Value", "ratio": 1, "no_wrap": True, "overflow": "ellipsis"},
        ]

    def render_row(self, item: Tuple[str, Any], index: int) -> Tuple[List[str], str]:
        """Render a single setting item into a row."""
        key, value = item
        index_str = f"[green dim]{index}[/green dim]"
        key_str = f"[green]{key}[/green]"
        value_str = str(value)
        
        return [index_str, key_str, value_str], ""

    def get_item_for_filter(self, item: Tuple[str, Any]) -> str:
        """Return the setting name for filtering."""
        return item[0]

    def on_select(self, item: Any):
        """Handle setting selection."""
        # TODO: Implement setting editing in a future step
        pass
