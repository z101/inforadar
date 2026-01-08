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
                    self.need_clear = True
                
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
    # --- End Logic copied from ViewScreen.handle_input() ---

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
            self.need_clear = True
            if is_new:
                self.active_cursor = len(self.items_list) - 1
            else:
                try:
                    self.active_cursor = self.items_list.index(item_data)
                except ValueError:
                    pass

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
        # Calculate ID column width before filtering
        if self.items_list:
            id_field_name = self.fields[0]["name"]
            # Get max width of the label and the values
            max_id_len = max(len(str(item.get(id_field_name, ''))) for item in self.items_list)
            self.id_column_width = max(max_id_len, len(self.fields[0]["label"])) + 2
        else:
            self.id_column_width = len(self.fields[0]["label"]) + 2

        # Base the main items list on our local copy
        self.items = self.items_list
        self.apply_filter_and_sort()

    def _get_shortcuts_text(self) -> str:
        """Returns the footer text with key bindings."""
        return ""

    def render(self):
        """Custom render method to combine pagination and shortcuts."""
        console = self.app.console
        width, height = console.size

        # --- Copied from ViewScreen.render() ---
        # Header
        header_text = self.title
        if self.final_filter_text:
            header_text += f" [white]|[/white] [yellow]{escape(self.final_filter_text)}[/yellow]"
        elif self.filter_text:
            header_text += " [white]|[/white] [yellow]FILTERED[/yellow]"
        console.print(Text.from_markup(header_text), justify="center")

        available_rows = height - self.RESERVED_ROWS
        if available_rows < 1:
            available_rows = 1
            
        if self.active_mode:
            if self.active_cursor < self.start_index:
                self.start_index = self.active_cursor
            elif self.active_cursor >= self.start_index + available_rows:
                self.start_index = self.active_cursor - available_rows + 1
                
        self.current_page_items = self.calculate_visible_range(
            self.start_index, available_rows, width
        )
        
        # Calculate num_column_width based on filtered items
        total_filtered_items = len(self.filtered_items)
        if total_filtered_items > 0:
            self.num_column_width = max(len(str(total_filtered_items)), len("#"))
        else:
            self.num_column_width = len("#")

        table = Table(
            box=box.SIMPLE_HEAD, padding=0, expand=True, show_footer=False, header_style="bold dim"
        )
        columns = self.get_columns(width)
        for col in columns:
            table.add_column(**col)

        for i, item in enumerate(self.current_page_items):
            row_num = i + 1
            row_data, row_style = self.render_row(item, row_num)
            abs_index = self.start_index + i
            style = row_style
            if self.active_mode and abs_index == self.active_cursor:
                style = "reverse green"
            elif (
                not self.active_mode
                and self.input_buffer
                and self.input_buffer == str(row_num)
            ):
                style = "reverse green"
            table.add_row(*row_data, style=style)
        console.print(table)
        # --- End of copied table rendering logic ---

        # --- Footer Logic Copied from ViewScreen.render() ---
        total_items = len(self.filtered_items)
        current_page = (self.start_index // available_rows) + 1 if available_rows > 0 else 1
        total_pages = math.ceil(total_items / available_rows) if available_rows > 0 else 1
        if total_pages < 1:
            total_pages = 1

        if self.command_mode or self.filter_mode:
            # Render Command Line
            prompt = ":" if self.command_mode else "/"
            txt = self.command_line.text
            cpos = self.command_line.cursor_pos

            pre_cursor = txt[:cpos]
            cursor_char = txt[cpos] if cpos < len(txt) else " "
            post_cursor = txt[cpos + 1 :]

            cmd_styled = Text(prompt)
            cmd_styled.append(pre_cursor)
            cmd_styled.append(cursor_char, style="reverse")
            cmd_styled.append(post_cursor)

            pager_text = f"Page [dim green]{current_page}[/dim green] of [dim green]{total_pages}[/dim green] | Items [dim green]{total_items}[/dim green]"

            footer_table = Table.grid(expand=True)
            footer_table.add_column()
            footer_table.add_column(justify="right")

            footer_table.add_row(cmd_styled, Text.from_markup(pager_text, style="dim"))
            console.print(footer_table)

        else: # Normal Mode Footer
            filter_status = " [FILTERED]" if self.filter_text or self.final_filter_text else ""
            info_status = ""
            if self.active_mode:
                visible_row = self.active_cursor - self.start_index + 1
                # info_status = f" | Active [dim green]{visible_row}[/dim green]" <-- Removed per request
            elif self.input_buffer:
                info_status = f" | Goto: {self.input_buffer}"

            # Only show pagination and status
            view_footer_text = f"Page [dim green]{current_page}[/dim green] of [dim green]{total_pages}[/dim green] | Items [dim green]{total_items}[/dim green]{filter_status}{info_status}"
            console.print(Text.from_markup(view_footer_text), style="dim", justify="center")

    def execute_command(self):
        # CustomListEditorScreen doesn't have specific commands like fetch/test
        # for now, if command mode is active and enter is pressed, clear the command.
        # Could add specific commands later.
        cmd = self.command_line.text.strip()
        if cmd:
            self.app.show_toast(f"Command '{cmd}' not recognized for this screen.", "warning")
        
        self.command_mode = False
        self.command_line.clear()

    def on_leave(self):
        """Called when leaving this screen - ensure proper cleanup."""
        # Save state when leaving the screen
        self.save_state()
        # Call parent implementation if exists
        super().on_leave() if hasattr(super(), 'on_leave') else None
