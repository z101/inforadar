from typing import Any, Dict, List, Tuple, TYPE_CHECKING, Optional, Callable
from rich import box
from rich.table import Table
from rich.text import Text

from inforadar.tui.screens.view_screen import ViewScreen
from inforadar.tui.keys import Key

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class ListSettingEditor(ViewScreen):
    """
    Screen for editing list-type settings.
    """
    def __init__(
        self,
        app: "AppState",
        setting_key: str,
        current_value: List[str],
        description: Optional[str] = None,
        on_save: Optional[Callable[[List[str]], None]] = None
    ):
        super().__init__(app, f"[green dim bold]Edit List: {setting_key}[/green dim bold]")
        self.setting_key = setting_key
        self.current_value = current_value or []
        self.description = description
        self.on_save = on_save
        self.items = list(self.current_value)  # Create a copy to work with
        self.edit_mode = False
        self.edit_index = -1
        self.edit_value = ""
        self.edit_cursor_pos = 0
        self.error_message = ""

    def get_columns(self, width: int) -> List[Dict[str, Any]]:
        """Return the column definitions for the list table."""
        return [
            {"header": "#", "justify": "right", "no_wrap": True},
            {"header": "Value", "ratio": 1, "no_wrap": True, "overflow": "ellipsis"},
            {"header": "Actions", "width": 15, "no_wrap": True},
        ]

    def render_row(self, item: Tuple[int, str], index: int) -> Tuple[List[str], str]:
        """Render a single list item into a row."""
        item_idx, value = item
        index_str = f"[green dim]{item_idx}[/green dim]"
        value_str = str(value)

        if self.edit_mode and self.edit_index == item_idx:
            # Show edit field instead of value
            if self.edit_cursor_pos <= len(self.edit_value):
                before_cursor = self.edit_value[:self.edit_cursor_pos]
                after_cursor = self.edit_value[self.edit_cursor_pos:]
                value_str = before_cursor + "[reverse]" + (after_cursor[0] if after_cursor else " ") + "[/reverse]" + after_cursor[1:]
            else:
                value_str = self.edit_value + "[reverse] [/reverse]"
            action_str = "[green]✓[/green] Save | [red]Esc[/red] Cancel"
        else:
            action_str = f"[green]E[/green]dit | [red]D[/red]elete"

        return [index_str, value_str, action_str], ""

    def get_item_for_filter(self, item: Tuple[int, str]) -> str:
        """Return the item value for filtering."""
        return item[1]

    def refresh_data(self):
        """Refresh the list of items."""
        # Create list of (index, value) tuples
        self.items = [(i, val) for i, val in enumerate(self.current_value)]
        self.apply_filter_and_sort()

    def _handle_normal_mode(self, key: str) -> bool:
        if key == Key.ENTER:
            # Add new item
            self._start_add_item()
            return True
        elif key == Key.A:
            # Alternative way to add new item
            self._start_add_item()
            return True
        elif key == Key.E:
            # Edit selected item
            if 0 <= self.cursor_index < len(self.filtered_items):
                item_idx, value = self.filtered_items[self.cursor_index]
                self._start_edit_item(item_idx, value)
            return True
        elif key == Key.D:
            # Delete selected item
            if 0 <= self.cursor_index < len(self.filtered_items):
                item_idx, value = self.filtered_items[self.cursor_index]
                self.items.pop(item_idx)
                # Update current_value to reflect the change
                self.current_value = [item[1] for item in self.items]
                self.refresh_data()
            return True
        elif key == Key.S:
            # Save and exit
            if self.on_save:
                self.on_save(self.current_value)
            self.app.pop_screen()
            return True
        else:
            # Handle other keys (navigation, etc.) using parent
            handled = super().handle_input(key)
            if not handled:
                return super().handle_input(key)
            return handled

    def _handle_edit_mode(self, key: str) -> bool:
        if key == Key.ENTER:
            # Save the edited value
            self._save_edit()
            return True
        elif key == Key.ESCAPE:
            # Cancel edit
            self.edit_mode = False
            self.edit_index = -1
            self.edit_value = ""
            self.edit_cursor_pos = 0
            # Refresh the display to clear edit mode
            self.refresh_data()
            return True
        elif key == Key.CTRL_U:
            # Clear input
            self.edit_value = ""
            self.edit_cursor_pos = 0
            return True
        elif key == Key.CTRL_A:
            # Move to beginning
            self.edit_cursor_pos = 0
            return True
        elif key == Key.CTRL_E:
            # Move to end
            self.edit_cursor_pos = len(self.edit_value)
            return True
        elif key == Key.CTRL_H or key == Key.BACKSPACE:
            # Delete character before cursor
            if self.edit_cursor_pos > 0:
                self.edit_value = self.edit_value[:self.edit_cursor_pos-1] + self.edit_value[self.edit_cursor_pos:]
                self.edit_cursor_pos -= 1
            return True
        elif key == Key.LEFT:
            if self.edit_cursor_pos > 0:
                self.edit_cursor_pos -= 1
            return True
        elif key == Key.RIGHT:
            if self.edit_cursor_pos < len(self.edit_value):
                self.edit_cursor_pos += 1
            return True
        elif len(key) == 1:
            # Regular character input - preserve case
            self.edit_value = self.edit_value[:self.edit_cursor_pos] + key + self.edit_value[self.edit_cursor_pos:]
            self.edit_cursor_pos += 1
            return True

        return False

    def _start_edit_item(self, item_idx: int, current_value: str):
        """Start editing an existing item."""
        self.edit_mode = True
        self.edit_index = item_idx
        self.edit_value = current_value
        self.edit_cursor_pos = len(self.edit_value)

    def _start_add_item(self):
        """Start adding a new item."""
        self.edit_mode = True
        self.edit_index = len(self.items)  # Will be the index of the new item
        self.edit_value = ""
        self.edit_cursor_pos = 0

    def _save_edit(self):
        """Save the edited or new item."""
        if self.edit_value.strip():  # Only save if not empty
            if self.edit_index < len(self.items):
                # Editing existing item
                self.items[self.edit_index] = (self.edit_index, self.edit_value)
                # Update current_value
                self.current_value[self.edit_index] = self.edit_value
            else:
                # Adding new item
                self.items.append((len(self.items), self.edit_value))
                self.current_value.append(self.edit_value)

        # Exit edit mode
        self.edit_mode = False
        self.edit_index = -1
        self.edit_value = ""
        self.edit_cursor_pos = 0

        # Refresh the display
        self.refresh_data()

    def handle_input(self, key: str) -> bool:
        if self.edit_mode:
            return self._handle_edit_mode(key)
        else:
            if key == Key.S:
                # Save and exit
                if self.on_save:
                    self.on_save(self.current_value)
                self.app.pop_screen()
                return True
            elif key == Key.ESCAPE or key == Key.Q:
                # Cancel and exit
                self.app.pop_screen()
                return True
            else:
                return self._handle_normal_mode(key)

    def render(self):
        console = self.app.console
        width, height = console.size

        # Title and description
        console.print(self.title, style="bold green dim", justify="center")
        if self.description:
            console.print(f"[dim]{self.description}[/dim]", justify="center")
        console.print()

        # Show error message if any
        if self.error_message:
            console.print(f"[red]{self.error_message}[/red]")
            console.print()

        # Render the table
        super().render()

        # Footer with instructions
        if not self.edit_mode:
            footer_text = (
                f"[[bold green]Enter[/bold green], [bold green]A[/bold green]] Add "
                f"[[bold green]E[/bold green]] Edit "
                f"[[bold green]D[/bold green]] Delete "
                f"[[bold green]S[/bold green]] Save "
                f"[[bold yellow]Esc[/bold yellow], [bold yellow]Q[/bold yellow]] Cancel"
            )
        else:
            footer_text = (
                f"[[bold green]Enter[/bold green]] Save "
                f"[[bold yellow]Esc[/bold yellow]] Cancel "
                f"[[bold blue]Ctrl+U[/bold blue]] Clear "
                f"[[bold blue]Ctrl+A[/bold blue]] Start "
                f"[[bold blue]Ctrl+E[/bold blue]] End"
            )

        console.print(Text.from_markup(footer_text), style="dim", justify="center")