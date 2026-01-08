from typing import Any, Dict, List, Tuple, TYPE_CHECKING
import json
from .view_screen import ViewScreen
from ..keys import Key
from ..schemas import CUSTOM_TYPE_SCHEMAS

if TYPE_CHECKING:
    from inforadar.tui.app import AppState

# Import the new editor screens
from .simple_setting_editor import SimpleSettingEditor
from .list_setting_editor import ListSettingEditor
from .custom_list_editor import CustomListEditorScreen
from .habr_hubs_editor import HabrHubsEditorScreen

# The registry is no longer needed for custom types
EDITOR_REGISTRY = {}


class SettingsScreen(ViewScreen):
    """A screen to display and edit settings in a table view."""

    def __init__(self, app: "AppState"):
        """Initialise the screen."""
        super().__init__(app, "[green dim bold]Info Radar Settings[/green dim bold]")
        self.index_column_width = 0
        self.name_column_width = 0
        self.current_sort = "name_asc"
        self.error_message = "" # Added this line
        self.refresh_data()

    def _flatten_settings(self, settings: Dict[str, Any], prefix: str = "") -> List[Tuple[str, Any, str]]:
        """Recursively flattens a nested settings dictionary and includes type info."""
        flat_list = []
        for key, value in settings.items():
            new_prefix = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                flat_list.extend(self._flatten_settings(value, new_prefix))
            else:
                # Get the type of the setting from the database
                setting_type = self._get_setting_type(new_prefix)
                flat_list.append((new_prefix, value, setting_type))
        return flat_list

    def _get_setting_type(self, key: str) -> str:
        """Get the type of a setting from the database."""
        # Query the database to get the type of the setting
        with self.app.engine.storage.Session() as session:
            from inforadar.models import Setting
            setting = session.query(Setting).filter_by(key=key).first()
            if setting:
                # Normalize legacy type
                if setting.type == 'habr_hubs':
                    return 'custom'
                return setting.type
            else:
                # Default to 'string' if type is not found
                return 'string'

    def refresh_data(self):
        """Load settings from the engine and calculate max name width."""
        all_settings = self.app.engine.settings.all_settings
        self.items = self._flatten_settings(all_settings)

        if self.items:
            max_key_len = max(len(key) for key, _, _ in self.items)
            self.name_column_width = max_key_len + 1  # Minimal padding
            
            # Calculate index width based on total items count
            self.index_column_width = len(str(len(self.items))) + 1
        else:
            self.name_column_width = 20  # Default width
            self.index_column_width = 3

        self.apply_current_sort()

    def apply_current_sort(self):
        """Apply the current sort order."""
        if self.current_sort == "name_asc":
            self.sort_key = lambda item: item[0]
            self.sort_reverse = False
        elif self.current_sort == "name_desc":
            self.sort_key = lambda item: item[0]
            self.sort_reverse = True
        
        self.apply_filter_and_sort()

    def get_columns(self, width: int) -> List[Dict[str, Any]]:
        """Return the column definitions for the settings table."""
        return [
            {"header": "#", "justify": "right", "width": self.index_column_width, "no_wrap": True},
            {"header": "Name" + (" ↓" if self.current_sort == "name_desc" else " ↑"), "width": self.name_column_width, "no_wrap": True},
            {"header": "Value", "ratio": 1, "no_wrap": True, "overflow": "ellipsis"},
        ]

    def render_row(self, item: Tuple[str, Any, str], index: int) -> Tuple[List[str], str]:
        """Render a single setting item into a row."""
        key, value, setting_type = item
        index_str = f"[green dim]{index}[/dim green]"
        key_str = f"{key}"
        
        value_str = str(value)

        # Handle display for custom types (now parsed in config.py)
        if setting_type == 'custom':
            items = value # Value is already a list of dicts from config.py
            if isinstance(items, list) and items:
                # Format as ID: Slug, ...
                schema = CUSTOM_TYPE_SCHEMAS.get(key)
                if schema and len(schema['fields']) >= 2:
                    id_field = schema["fields"][0]["name"]
                    name_field = schema["fields"][1]["name"]
                    value_str = ", ".join([f"{h.get(id_field, '')}: {h.get(name_field, '')}" for h in items])
                else:
                    value_str = f"[{len(items)} item(s)]"
            elif isinstance(items, list):
                value_str = "[No items]"

        return [index_str, key_str, f"[dim]{value_str}[/dim]"], ""


    def get_item_for_filter(self, item: Tuple[str, Any, str]) -> str:
        """Return the setting name for filtering."""
        return item[0]

    def on_select(self, item: Tuple[str, Any, str]):
        """Handle setting selection - open appropriate editor based on type."""
        key, value, setting_type = item
        self.error_message = "" # Clear error message on new selection

        # Special case for Habr Hubs to use the specialized editor
        if key == 'sources.habr.hubs':
            editor = HabrHubsEditorScreen(
                app=self.app,
                setting_key=key,
                current_value=value,
                description=self._get_setting_description(key),
                on_save=lambda new_value: self._save_setting(key, new_value, 'custom')
            )
            self.app.push_screen(editor)
            return

        # Check registry first
        if setting_type in EDITOR_REGISTRY:
             editor_cls = EDITOR_REGISTRY[setting_type]
             editor = editor_cls(
                 app=self.app,
                 setting_key=key,
                 current_value=value,
                 description=self._get_setting_description(key),
                 on_save=lambda new_value: self._save_setting(key, new_value, setting_type)
             )
             self.app.push_screen(editor)
        elif setting_type in ['string', 'integer', 'date', 'datetime', 'boolean', 'json']:
            # Open simple editor for basic types (including json, which is now handled as a string for editing)
            editor = SimpleSettingEditor(
                app=self.app,
                setting_key=key,
                current_value=json.dumps(value) if setting_type == 'json' and isinstance(value, (dict, list)) else value,
                setting_type=setting_type,
                description=self._get_setting_description(key),
                on_save=lambda new_value: self._save_setting(key, new_value, setting_type)
            )
            self.app.push_screen(editor)
        elif setting_type == 'list':
            # Open list editor for list types
            editor = ListSettingEditor(
                app=self.app,
                setting_key=key,
                current_value=value,
                description=self._get_setting_description(key),
                on_save=lambda new_value: self._save_setting(key, new_value, setting_type)
            )
            self.app.push_screen(editor)
        elif setting_type == 'custom':
            # Use the new generic CustomListEditorScreen
            if key not in CUSTOM_TYPE_SCHEMAS:
                self.error_message = f"No schema for '{key}'"
                return

            editor = CustomListEditorScreen(
                app=self.app,
                setting_key=key,
                current_value=value, # Value is already a list of dicts from config.py
                description=self._get_setting_description(key),
                on_save=lambda new_value: self._save_setting(key, new_value, 'custom') # Always save as 'custom'
            )
            self.app.push_screen(editor)
        else:
            # Fallback for any other unknown types
            self.error_message = f"No editor for type '{setting_type}'"



    def handle_input(self, key: str) -> bool:
        """Handle input."""
        if self.command_mode or self.filter_mode:
            return super().handle_input(key)

        if key == Key.ESCAPE:
            # If filter is active (but not in filter mode), clear it first
            if self.filter_text or self.final_filter_text:
                self.filter_text = ""
                self.final_filter_text = ""
                self.apply_filter_and_sort()
                self.save_state()
                return True
            
            # If no filter, pop screen
            self.app.pop_screen()
            return True

        if key == Key.ENTER and len(self.filtered_items) == 1:
            # If only one item is filtered, select it directly
            self.on_select(self.filtered_items[0])
            return True

        if key == Key.N:
            if self.current_sort == "name_asc":
                self.current_sort = "name_desc"
            else:
                self.current_sort = "name_asc"
            self.apply_current_sort()
            return True

        return super().handle_input(key)

    def _get_setting_description(self, key: str) -> str:
        """Get the description of a setting from the database."""
        with self.app.engine.storage.Session() as session:
            from inforadar.models import Setting
            setting = session.query(Setting).filter_by(key=key).first()
            if setting:
                return setting.description
            return f"Setting: {key}"

    def _save_setting(self, key: str, value: Any, setting_type: str):
        """Save a setting to the database."""
        # Backup state to restore after refresh
        was_active = self.active_mode
        prev_cursor = self.active_cursor

        self.app.engine.settings.set(key, value, setting_type)
        
        # Refresh the settings display
        self.refresh_data()

        # Restore state
        self.input_buffer = ""  # Clear any partial input that might cause "Goto"
        if was_active:
             self.active_mode = True
             # Ensure cursor is still within bounds
             if self.filtered_items:
                 self.active_cursor = min(prev_cursor, len(self.filtered_items) - 1)
             else:
                 self.active_cursor = 0

    def on_leave(self):
        """Called when leaving this screen - ensure proper cleanup."""
        # Make sure the screen is properly refreshed when returning to it
        pass