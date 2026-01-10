from typing import Any, List, Dict, TYPE_CHECKING, Callable, Optional
import math
import json
from rich import box
from rich.table import Table
from rich.text import Text
from rich.markup import escape # Import escape for header rendering

from inforadar.tui.screens.view_screen import ViewScreen
from inforadar.tui.keys import Key
from inforadar.tui.schemas import CUSTOM_TYPE_SCHEMAS
from inforadar.tui.screens.item_editor import ItemEditorScreen
from inforadar.tui.screens.confirmation_screen import ConfirmationScreen

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class CustomListEditorScreen(ViewScreen):
    """
    A generic screen for editing a list of custom items (dictionaries).
    It displays items in a table and uses ItemEditorScreen for editing/creation.
    """

    def __init__(
        self,
        app: "AppState",
        setting_key: str,
        current_value: List[Dict[str, str]],
        description: str,
        on_save: Callable[[List[Dict[str, str]]], None]
    ):
        super().__init__(app, f"[green bold dim]Info Radar Settings Edit[/green bold dim] | {setting_key}")

        self.setting_key = setting_key
        self.schema = CUSTOM_TYPE_SCHEMAS.get(setting_key)
        if not self.schema:
            raise ValueError(f"No schema found for custom setting: {setting_key}")

        # Sanitize legacy data (list of strings) into the expected list of dicts
        safe_value = self._ensure_list_of_dicts(current_value)

        # Deep copy to avoid mutating original list until save
        self.items_list = [item.copy() for item in (safe_value or [])]
        self.description = description
        self.on_save = on_save

        self.fields = self.schema["fields"]
        self.item_name = self.schema.get("item_name", "Item")
        self.id_column_width = 20 # Default width
        self.num_column_width = 4 # Default width for '#'

        self._edited_item = None  # Track item being edited for cursor restoration

        self.refresh_data()

    def _ensure_list_of_dicts(self, value: Any) -> List[Dict[str, str]]:
        """
        Leniently converts a list containing strings or dicts into a uniform list of dicts.
        """
        if not isinstance(value, list):
            return []
        
        sanitized_list = []
        id_field = self.schema["fields"][0]["name"] if (self.schema and self.schema["fields"]) else "id"

        for item in value:
            if isinstance(item, dict):
                sanitized_list.append(item)
            elif isinstance(item, str):
                sanitized_list.append({id_field: item})
        
        return sanitized_list



    def get_columns(self, width: int) -> List[Dict[str, Any]]:
        columns = [{"header": "#", "justify": "right", "width": self.num_column_width}]
        
        # First column (ID) with calculated width
        columns.append({"header": self.fields[0]["label"], "width": self.id_column_width})
        
        # Remaining columns with ratio
        for field in self.fields[1:]:
            columns.append({"header": field["label"], "ratio": 1})
            
        return columns

    def render_row(self, item: Dict[str, str], index: int) -> tuple[list[str], str]:
        # Change: Use index directly for display, it's already 1-based
        row_values = [f"[dim green]{index}[/dim green]"]
        for field in self.fields:
            row_values.append(item.get(field["name"], ""))
        return row_values, ""

    def handle_input(self, key: str) -> bool:
        # First, check for screen-specific keys
        if key == 'a':  # Add
            self._open_form({})
            return True
        elif key == 'd':  # Delete
            if self.items_list and 0 <= self.active_cursor < len(self.filtered_items):
                item_to_delete = self.filtered_items[self.active_cursor]
                
                def do_delete():
                    self.items_list.remove(item_to_delete)
                    if self.active_cursor >= len(self.items_list):
                        self.active_cursor = max(0, len(self.items_list) - 1)
                    self.refresh_data()
                    self._save()
                    # After deletion, trigger a redraw in the app loop
                    # This is handled by returning True from the outer handle_input
                
                display_name = item_to_delete.get(self.fields[0]['name'], f"item #{self.active_cursor}")
                confirm_screen = ConfirmationScreen(
                    self.app,
                    f"Are you sure you want to delete {self.item_name.lower()} '{display_name}'?",
                    on_confirm=do_delete
                )
                self.app.push_screen(confirm_screen)
            return True
        
        # If no specific key was handled, pass to the parent ViewScreen
        return super().handle_input(key)

    def on_select(self, item: Dict[str, str]):
        """Called when Enter is pressed on an item."""
        self._open_form(item)

    def _open_form(self, item_data: Dict[str, str]):
        is_new = not item_data

        def on_form_save(new_data: Dict[str, str]):
            if is_new:
                self.items_list.append(new_data)
            else:
                item_data.update(new_data)

            self.refresh_data()

        def on_form_close():
            self.active_mode = True
            if is_new:
                self.active_cursor = len(self.items_list) - 1
            else:
                try:
                    self.active_cursor = self.items_list.index(item_data)
                except ValueError:
                    pass
            # Force a redraw when returning
            self.live.update(self._generate_renderable(), refresh=True)

        form_screen = ItemEditorScreen(
            app=self.app,
            schema=self.schema,
            item_data=item_data,
            on_save=on_form_save,
            on_close=on_form_close,
        )
        self.app.push_screen(form_screen)

    def _save(self):
        if self.on_save:
            self.on_save(self.items_list)

    def refresh_data(self):
        # Calculate column widths before filtering
        if self.items_list:
            id_field_name = self.fields[0]["name"]
            # Get max width of the label and the values
            max_id_len = max((len(str(item.get(id_field_name, ''))) for item in self.items_list), default=0)
            self.id_column_width = max(max_id_len, len(self.fields[0]["label"])) + 2
            
            total_items = len(self.items_list)
            self.num_column_width = max(len(str(total_items)), len("#")) + 1

        else:
            self.id_column_width = len(self.fields[0]["label"]) + 2
            self.num_column_width = len("#") + 1

        # Base the main items list on our local copy
        self.items = self.items_list
        self.apply_filter_and_sort()

    def _get_shortcuts_text(self) -> str:
        """Returns the footer text with key bindings."""
        return ""

    def on_leave(self):
        """Called when leaving this screen - ensure proper cleanup."""
        # Save state when leaving the screen
        self.save_state()
        # Call parent implementation if exists
        super().on_leave() if hasattr(super(), 'on_leave') else None
