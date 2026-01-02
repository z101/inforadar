from typing import Any, List, Dict, TYPE_CHECKING, Callable, Optional
from rich.text import Text
from rich.panel import Panel
from rich.style import Style

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.keys import Key
from inforadar.tui.screens.simple_setting_editor import SimpleSettingEditor
from inforadar.tui.screens.confirmation_screen import ConfirmationScreen

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class ItemEditorScreen(BaseScreen):
    """
    A form screen for creating or editing a single custom-type item (a dictionary).
    """
    def __init__(
        self,
        app: "AppState",
        schema: Dict[str, Any],
        item_data: Optional[Dict[str, str]],
        on_save: Callable[[Dict[str, str]], None],
    ):
        is_new = not item_data
        item_type_name = schema.get("item_name", "Item")
        title_mode = "New" if is_new else "Edit"
        title = f"Info Radar Item | {title_mode} | {item_type_name}"

        super().__init__(app, title)

        self.schema = schema
        # Work on a copy of the data to handle edits and cancellations
        self.item_data = item_data.copy() if item_data else {}
        self.original_item_data = item_data.copy() if item_data else {}
        self.on_save = on_save
        self.is_new = is_new

        self.fields = self.schema.get("fields", [])
        self.cursor_index = 0

    def _get_footer_text(self) -> Text:
        """Returns the footer text with key bindings."""
        return Text.from_markup(
            f"[bold]↑[/]/[bold]k[/] Up | "
            f"[bold]↓[/]/[bold]j[/] Down | "
            f"[bold]Enter[/] Edit | "
            f"[bold]Ctrl+Enter[/] Save | "
            f"[bold]Esc[/] Cancel",
            justify="center",
            style="dim"
        )

    def handle_input(self, key: str) -> bool:
        if key == Key.J or key == Key.DOWN:
            if self.cursor_index < len(self.fields) - 1:
                self.cursor_index += 1
            return True
        elif key == Key.K or key == Key.UP:
            if self.cursor_index > 0:
                self.cursor_index -= 1
            return True
        elif key == Key.ENTER:
            self._edit_current_field()
            return True
        elif key == Key.CTRL_ENTER:
            self._save_item()
            return True
        elif key == Key.ESCAPE:
            self._handle_cancel()
            return True

        return False

    def _edit_current_field(self):
        if not self.fields:
            return

        field_def = self.fields[self.cursor_index]
        field_name = field_def["name"]
        field_label = field_def.get("label", field_name)
        current_value = self.item_data.get(field_name, "")

        def on_field_save(new_value: str):
            """Callback to update the item_data when a field is saved."""
            self.item_data[field_name] = new_value

        editor = SimpleSettingEditor(
            app=self.app,
            setting_key=f"Edit {field_label}",
            current_value=current_value,
            setting_type='string', # All custom fields are strings for now
            description=f"Enter value for {field_label}",
            on_save=on_field_save
        )
        self.app.push_screen(editor)

    def _save_item(self):
        """Validate and save the item."""
        missing_fields = []
        for field_def in self.fields:
            is_required = field_def.get("required", True) # Default to required
            field_name = field_def["name"]
            if is_required and not self.item_data.get(field_name, "").strip():
                missing_fields.append(field_def.get("label", field_name))

        if missing_fields:
            self.app.show_toast(f"Error: Required fields are empty: {', '.join(missing_fields)}", "error")
            return

        self.on_save(self.item_data)
        self.app.pop_screen()

    def _handle_cancel(self):
        """Handle cancellation, checking for unsaved changes."""
        has_changed = self.item_data != self.original_item_data

        if self.is_new and not self.item_data:
             # If it's a new item and no data has been entered, just close.
             self.app.pop_screen()
        elif self.is_new and self.item_data:
             # If it's a new item with data, confirm exit.
            confirm_screen = ConfirmationScreen(
                self.app,
                "Discard new item?",
                on_confirm=self.app.pop_screen
            )
            self.app.push_screen(confirm_screen)
        elif not self.is_new and has_changed:
            # If an existing item was changed, confirm exit.
             confirm_screen = ConfirmationScreen(
                self.app,
                "Discard changes?",
                on_confirm=self.app.pop_screen
            )
             self.app.push_screen(confirm_screen)
        else:
            # If no changes, just close.
            self.app.pop_screen()

    def render(self):
        console = self.app.console
        width, height = console.size
        
        # Description
        description = self.schema.get("description", "")
        if description:
            console.print(Text(description, style="dim", justify="center"), width=width)
            console.print()

        # Render fields
        for i, field_def in enumerate(self.fields):
            label = field_def.get("label", field_def["name"])
            value = self.item_data.get(field_def["name"], "")
            
            line = Text()
            line.append(f"{label}: ", style="bold")
            line.append(value if value else "", style="dim italic")

            if i == self.cursor_index:
                line.style = Style(reverse=True)
            
            console.print(line)

        # Spacer
        console.print()

        # Footer
        console.print(self._get_footer_text(), width=width)

    def on_enter(self):
        self.app.set_title(self.title)

    def on_leave(self):
        self.app.set_title("")
