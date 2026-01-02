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

        # Deep copy to avoid mutating original list until save
        self.items_list = [item.copy() for item in (current_value or [])]
        self.description = description
        self.on_save = on_save

        self.fields = self.schema["fields"]
        self.item_name = self.schema.get("item_name", "Item")
        self.id_column_width = 20 # Default width
        self.num_column_width = 4 # Default width for '#'

        self.refresh_data()

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
        from inforadar.tui.screens.filter_action import FilterActionScreen
        from inforadar.tui.screens.sort_action import SortActionScreen
        from inforadar.tui.screens.sync_action import SyncActionScreen

        console_height = self.app.console.size[1]
        available_rows = max(1, console_height - self.RESERVED_ROWS)
        # width = self.app.console.size[0] # Not directly used in handle_input

        # --- Logic copied from ViewScreen.handle_input() ---
        if self.command_mode or self.filter_mode:
            def _update_filter():
                if self.filter_mode:
                    self.filter_text = self.command_line.text
                    self.apply_filter_and_sort()

            if key == Key.ESCAPE:
                if self.filter_mode:
                    self.filter_text = self.final_filter_text
                    self.apply_filter_and_sort()
                self.command_mode = False
                self.filter_mode = False
                self.command_line.clear()
                return True
            elif key == Key.ENTER:
                if self.command_mode:
                    self.execute_command() 
                elif self.filter_mode:
                    self.final_filter_text = self.command_line.text
                    self.filter_text = self.final_filter_text

                self.command_mode = False
                self.filter_mode = False
                self.command_line.clear()
                return True
            elif key == Key.BACKSPACE or key == Key.CTRL_H:
                self.command_line.delete_back()
                _update_filter()
                return True
            elif key == Key.DELETE:
                self.command_line.delete_forward()
                _update_filter()
                return True
            elif key == Key.LEFT or key == Key.CTRL_B:
                self.command_line.move_left()
                return True
            elif key == Key.RIGHT or key == Key.CTRL_F:
                self.command_line.move_right()
                return True
            elif key == Key.CTRL_A:
                self.command_line.move_start()
                return True
            elif key == Key.CTRL_E:
                self.command_line.move_end()
                return True
            elif key == Key.ALT_B:
                self.command_line.move_word_left()
                return True
            elif key == Key.ALT_F:
                self.command_line.move_word_right()
                return True
            elif key == Key.CTRL_W:
                self.command_line.delete_word_back()
                _update_filter()
                return True
            elif key == Key.CTRL_U:
                self.command_line.delete_to_start()
                _update_filter()
                return True
            elif len(key) == 1 and key.isprintable():
                self.command_line.insert(key)
                _update_filter()
                return True
            return True

        # Normal Mode
        if key == Key.COLON:
            self.command_mode = True
            self.command_line.clear()
            return True

        if key == Key.SLASH:
            self.filter_mode = True
            self.command_mode = False
            self.command_line.clear()
            self.command_line.set_text(self.filter_text)
            self.final_filter_text = ""
            return True
        
        # --- CustomListEditorScreen specific escape logic ---
        if key == Key.ESCAPE:
            if self.active_mode:
                self.active_mode = False
                self.input_buffer = ""
                return True
            self._save() # Save changes before popping
            self.app.pop_screen()
            return True
        # --- End CustomListEditorScreen specific escape logic ---

        if key == Key.Q:
             self.save_state()
             self._save() # Save changes before popping
             self.app.pop_screen()
             return True

        # --- CustomListEditorScreen specific keys ('a' and 'd') ---
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
                
                display_name = item_to_delete.get(self.fields[0]['name'], f"item #{self.active_cursor}")
                confirm_screen = ConfirmationScreen(
                    self.app,
                    f"Are you sure you want to delete {self.item_name.lower()} '{display_name}'?",
                    on_confirm=do_delete
                )
                self.app.push_screen(confirm_screen)
            return True
        # --- End CustomListEditorScreen specific keys ---

        # Digits enter/update Active Mode
        if key.isdigit():
            new_buffer = self.input_buffer + key
            if self.current_page_items:
                try:
                    row_num = int(new_buffer)
                    if 1 <= row_num <= len(self.current_page_items):
                        self.input_buffer = new_buffer
                        self.active_mode = True
                        self.active_cursor = self.start_index + (row_num - 1)
                        return True
                except ValueError:
                    pass

            # If input buffer exceeds available rows, clear it
            if int(new_buffer) > available_rows and len(new_buffer) > 1:
                self.input_buffer = ""
            elif int(new_buffer) <= available_rows:
                 self.input_buffer = new_buffer
            return True

        if key == Key.BACKSPACE:
            if self.input_buffer:
                self.input_buffer = self.input_buffer[:-1]
                if self.input_buffer:
                    try:
                        row_num = int(self.input_buffer)
                        if 1 <= row_num <= len(self.current_page_items):
                            self.active_mode = True
                            self.active_cursor = self.start_index + (row_num - 1)
                    except ValueError:
                        pass
                else: # buffer is now empty
                    self.active_mode = False
            return True

        if key == Key.ENTER:
            if self.active_mode:
                if 0 <= self.active_cursor < len(self.filtered_items):
                    item = self.filtered_items[self.active_cursor]
                    self.on_select(item)
                return True
            if self.input_buffer:
                try:
                    row_num = int(self.input_buffer)
                    if 1 <= row_num <= len(self.current_page_items):
                        item = self.current_page_items[row_num - 1]
                        self.on_select(item)
                except ValueError:
                    pass
                self.input_buffer = ""
                return True

        # Navigation
        if self.input_buffer and key not in [Key.J, Key.K, Key.UP, Key.DOWN]:
            self.input_buffer = ""

        # J/K and Arrow keys for cursor movement (activates active_mode)
        if key == Key.DOWN or key == Key.J:
            if not self.active_mode:
                self.active_mode = True
            else:
                if len(self.filtered_items) > 0:
                    self.active_cursor = (self.active_cursor + 1) % len(self.filtered_items)

            self.input_buffer = ""
            return True

        if key == Key.UP or key == Key.K:
            if not self.active_mode:
                self.active_mode = True
            else:
                if len(self.filtered_items) > 0:
                    self.active_cursor = (self.active_cursor - 1 + len(self.filtered_items)) % len(self.filtered_items)

            self.input_buffer = ""
            return True


        elif key == Key.G:  # First page (Double 'g')
            if self.pending_g:
                if self.start_index != 0:
                    self.start_index = 0
                    self.active_cursor = 0
                    if self.active_mode:
                        self.active_cursor = 0
                    self.pending_g = False
                    return True
                self.pending_g = False
            else:
                self.pending_g = True
                return False

        elif key == Key.SHIFT_G:  # Last page
            total = len(self.filtered_items)
            if total > 0:
                last_page_idx = (total - 1) // available_rows
                new_start = last_page_idx * available_rows
                if self.start_index != new_start:
                    self.start_index = new_start
                    if self.active_mode:
                        self.active_cursor = total - 1
                    return True
        # --- CustomListEditorScreen doesn't need these specific actions ---
        # elif key == Key.R:
        #     self.app.push_screen(SyncActionScreen(self.app, self))
        #     return True
        # elif key == Key.F:
        #     self.app.push_screen(FilterActionScreen(self.app, self))
        #     return True
        # elif key == Key.S:
        #     self.app.push_screen(SortActionScreen(self.app, self))
        #     return True
        elif key == Key.L:
            pass # No specific action for L here

        if key != Key.G:
            self.pending_g = False

        return False
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
                # Update the original item dictionary in place
                item_data.update(new_data)

            self.refresh_data()
            # The form saves the item, and the list is saved on exit from this screen
            # self._save() # No, save on exit from the list editor

        form_screen = ItemEditorScreen(
            app=self.app,
            schema=self.schema,
            item_data=item_data,
            on_save=on_form_save,
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
        return "[[dim bold green]a[/dim bold green]] Add [[dim bold green]Enter[/dim bold green]] Edit [[dim bold green]d[/dim bold green]] Delete"

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
                info_status = f" | Active [dim green]{visible_row}[/dim green]"
            elif self.input_buffer:
                info_status = f" | Goto: {self.input_buffer}"

            # Combine ViewScreen's footer with CustomListEditorScreen's shortcuts
            view_footer_text = f"Page [dim green]{current_page}[/dim green] of [dim green]{total_pages}[/dim green] | Items [dim green]{total_items}[/dim green]{filter_status}{info_status}"
            
            shortcuts_text = self._get_shortcuts_text()
            combined_footer_text = f"{view_footer_text} | {shortcuts_text}"
            console.print(Text.from_markup(combined_footer_text), style="dim", justify="center")

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
