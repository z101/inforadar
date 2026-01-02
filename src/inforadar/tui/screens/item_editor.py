from typing import Any, List, Dict, TYPE_CHECKING, Callable, Optional
from rich.text import Text
from rich.panel import Panel
from rich.style import Style
from rich.padding import Padding

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
        super().__init__(app)
        
        is_new = not item_data
        item_type_name = schema.get("item_name", "Item")
        title_mode = "New" if is_new else "Edit"
        
        self.title = f"[dim green bold]Info Radar Item[/dim green bold] | [dim green bold]{title_mode}[/dim green bold] | {item_type_name}"

        self.schema = schema
        self.item_data = item_data.copy() if item_data else {}
        self.original_item_data = item_data.copy() if item_data else {}
        self.on_save = on_save
        self.is_new = is_new

        self.fields = self.schema.get("fields", [])
        self.cursor_index = 0
        self.scroll_offset = 0
        
        self.active_mode = True

        self.max_label_width = 0
        if self.fields:
            self.max_label_width = max(len(field.get("label", field["name"])) for field in self.fields)

    def _get_footer_text(self) -> Text:
        """Returns the footer text with key bindings, centered."""
        return Text.from_markup(
            f"[[dim bold green]↑/k[/]] Up | [[dim bold green]↓/j[/]] Down | [[dim bold green]Enter[/]] Edit | [[dim bold green]Ctrl+Enter[/]] Save | [[dim bold green]Esc[/]] Cancel",
            justify="center",
            style="dim"
        )

    def _get_reserved_rows(self) -> int:
        """Calculates the number of rows reserved for non-panel content."""
        header_height = 2 # Title (1) + blank line (1)
        description_height = 1 if self.schema.get("description") else 0 # Description line (1 if exists)
        panel_top_bottom_padding = 2 # Padding(1,0,1,0) adds 2 lines of padding total
        footer_height = 2 # Footer line (1) + blank line above it (1)
        panel_header_footer_height = 2 # Panel border + title within panel

        return header_height + description_height + panel_top_bottom_padding + footer_height + panel_header_footer_height

    def handle_input(self, key: str) -> bool:
        if not self.fields:
            return super().handle_input(key)

        if key == Key.J or key == Key.DOWN:
            self.cursor_index = (self.cursor_index + 1) % len(self.fields)
            return True
        elif key == Key.K or key == Key.UP:
            self.cursor_index = (self.cursor_index - 1 + len(self.fields)) % len(self.fields)
            return True
        elif key == Key.ENTER:
            self._edit_current_field()
            return True
        elif key == 'ctrl_enter': # Fix: changed from Key.CTRL_ENTER to string literal
            self._save_item()
            return True
        elif key == Key.ESCAPE:
            self._handle_cancel()
            return True

        return False

    def _edit_current_field(self):
        # ... (rest of the methods are unchanged)
        if not self.fields:
            return

        field_def = self.fields[self.cursor_index]
        field_name = field_def["name"]
        field_label = field_def.get("label", field_name)
        current_value = self.item_data.get(field_name, "")

        def on_field_save(new_value: str):
            self.item_data[field_name] = new_value

        editor = SimpleSettingEditor(
            app=self.app,
            setting_key=f"Edit {field_label}",
            current_value=current_value,
            setting_type='string',
            description=f"Enter value for {field_label}",
            on_save=on_field_save
        )
        self.app.push_screen(editor)

    def _save_item(self):
        missing_fields = []
        for field_def in self.fields:
            is_required = field_def.get("required", True)
            field_name = field_def["name"]
            if is_required and not self.item_data.get(field_name, "").strip():
                missing_fields.append(field_def.get("label", field_name))

        if missing_fields:
            self.app.show_toast(f"Error: Required fields are empty: {', '.join(missing_fields)}", "error")
            return

        self.on_save(self.item_data)
        self.app.pop_screen()

    def _handle_cancel(self):
        has_changed = self.item_data != self.original_item_data

        if self.is_new and not self.item_data:
             self.app.pop_screen()
        elif self.is_new and self.item_data:
            confirm_screen = ConfirmationScreen(self.app, "Discard new item?", on_confirm=self.app.pop_screen)
            self.app.push_screen(confirm_screen)
        elif not self.is_new and has_changed:
             confirm_screen = ConfirmationScreen(self.app, "Discard changes?", on_confirm=self.app.pop_screen)
             self.app.push_screen(confirm_screen)
        else:
            self.app.pop_screen()

    def render(self):
        console = self.app.console
        width, height = console.size
        
        console.print(Text.from_markup(self.title), justify="center")
        console.print(" ") # Blank line after title

        description = self.schema.get("description", "")
        if description:
            console.print(Text(description, style="dim", justify="center"), width=width)

        reserved_rows = self._get_reserved_rows()
        panel_content_height = max(1, height - reserved_rows)
        num_fields = len(self.fields)
        panel_display_height = min(num_fields, panel_content_height)

        if self.cursor_index < self.scroll_offset:
            self.scroll_offset = self.cursor_index
        elif self.cursor_index >= self.scroll_offset + panel_display_height:
            self.scroll_offset = self.cursor_index - panel_display_height + 1

        visible_fields = self.fields[self.scroll_offset : self.scroll_offset + panel_display_height]
        
        renderables = []
        for i, field_def in enumerate(visible_fields):
            current_field_index = self.scroll_offset + i
            label = field_def.get("label", field_def["name"])
            value = self.item_data.get(field_def["name"], "")
            
            padded_label = label.ljust(self.max_label_width)
            
            line = Text()
            if current_field_index == self.cursor_index:
                line.append(padded_label, style="dim bold green")
                line.append("  ", style="normal")
                line.append("> ", style="dim green")
                line.append(value, style="green")
            else:
                line.append(padded_label, style="dim bold")
                line.append("  ", style="normal")
                line.append("> ", style="dim")
                line.append(value, style="normal")
            
            renderables.append(line)
        
        panel = Panel(
            Text("\n").join(renderables),
            title="Fields",
            border_style="dim",
            height=panel_display_height + 2,
            title_align="center",
        )
        
        console.print(Padding(panel, (1, 0, 1, 0))) # Add padding top and bottom
        
        console.print(self._get_footer_text(), justify="center")
