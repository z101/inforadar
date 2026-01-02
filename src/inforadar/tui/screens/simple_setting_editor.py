from typing import Any, TYPE_CHECKING, Callable, Optional
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from datetime import datetime

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.keys import Key

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class SimpleSettingEditor(BaseScreen):
    """
    Screen for editing simple setting types: string, integer, date.
    """
    def __init__(
        self,
        app: "AppState",
        setting_key: str,
        current_value: Any,
        setting_type: str,

        description: Optional[str] = None,
        on_save: Optional[Callable[[Any], None]] = None,
        validator: Optional[Callable[[str], str]] = None
    ):
        super().__init__(app)
        self.setting_key = setting_key
        self.current_value = current_value
        self.setting_type = setting_type
        self.description = description
        self.on_save = on_save
        self.validator = validator
        self.edit_value = str(current_value) if current_value is not None else ""
        self.cursor_pos = len(self.edit_value)
        self.error_message = ""
        self.input_mode = True  # True for input mode, False for command mode
        self.first_render = True

    @property
    def command_mode(self) -> bool:
        return self.input_mode

    def render(self):
        # Force clear on first render to remove artifacts from previous screen
        if self.first_render:
            self.app.console.clear()
            self.first_render = False

        console = self.app.console
        width = console.size.width

        # Title
        title = f"[green bold dim]Info Radar Settings Edit[/green bold dim] | {self.setting_key} | [yellow]{self.setting_type}[/yellow]"
        console.print(title, justify="center")
        console.print()

        # Description
        desc_text = self.description if self.description else f"Edit {self.setting_key}"
        console.print(f"[dim]{desc_text}[/dim]", justify="left")
        console.print()

        # Input field
        if self.input_mode:
            # Highlight cursor position
            if self.cursor_pos <= len(self.edit_value):
                before_cursor = self.edit_value[:self.cursor_pos]
                after_cursor = self.edit_value[self.cursor_pos:]
                display_value = before_cursor + "[reverse]" + (after_cursor[0] if after_cursor else " ") + "[/reverse]" + after_cursor[1:]
            else:
                display_value = self.edit_value + "[reverse] [/reverse]"

            # Pad with spaces to clear potential artifacts from backspace
            console.print(f"[dim green]> [/dim green]{display_value}" + " " * 20, highlight=False)
        else:
            console.print(f"[dim green]> [/dim green]{self.edit_value}" + " " * 20, highlight=False)

        # Error message if any (always reserve space)
        if self.error_message:
            console.print(f"[red]{self.error_message}[/red]" + " " * (width - len(self.error_message)))
        else:
            console.print(" " * width)

        # Instructions
        instructions = ""
        # instructions += "Type to edit the value\n"
        instructions += "[green]Enter[/green]: Save and exit\n"
        instructions += "[yellow]Esc[/yellow]: Cancel\n"
        instructions += "\n"
        instructions += "[blue]Ctrl+U[/blue]: Clear input\n"
        instructions += "[blue]Ctrl+A[/blue]: Move to beginning\n"
        instructions += "[blue]Ctrl+E[/blue]: Move to end\n"
        instructions += "[blue]Ctrl+H[/blue]: Delete character before cursor\n"
        instructions += "[blue]Ctrl+W[/blue]: Delete word before cursor"
        console.print(Panel(instructions, title="Help", title_align="center", border_style="dim white", style="dim white"))

    def handle_input(self, key: str) -> bool:
        if self.input_mode:
            return self._handle_input_mode(key)
        else:
            return super().handle_input(key)

    def _handle_input_mode(self, key: str) -> bool:
        value_changed = False

        if key == Key.ENTER:
            # Validate and save
            if self._validate_and_save():
                return True
            return True # Handled even if validation fails
        elif key == Key.ESCAPE:
            # Cancel - just go back to previous screen
            self.app.pop_screen()
            return True
        elif key == Key.CTRL_U:
            # Clear input
            self.edit_value = ""
            self.cursor_pos = 0
            value_changed = True
        elif key == Key.CTRL_A:
            # Move to beginning
            self.cursor_pos = 0
            return True
        elif key == Key.CTRL_E:
            # Move to end
            self.cursor_pos = len(self.edit_value)
            return True
        elif key == Key.CTRL_H or key == Key.BACKSPACE:
            # Delete character before cursor
            if self.cursor_pos > 0:
                self.edit_value = self.edit_value[:self.cursor_pos-1] + self.edit_value[self.cursor_pos:]
                self.cursor_pos -= 1
                value_changed = True
            else:
                return True
        elif key == Key.CTRL_W:
            # Delete word before cursor
            # Find the start of the word before cursor
            start_pos = self.cursor_pos
            # Move back to find first non-space character
            while start_pos > 0 and self.edit_value[start_pos-1] == ' ':
                start_pos -= 1
            # Move back to find first space character or beginning
            while start_pos > 0 and self.edit_value[start_pos-1] != ' ':
                start_pos -= 1
            # Delete from start_pos to cursor_pos
            self.edit_value = self.edit_value[:start_pos] + self.edit_value[self.cursor_pos:]
            self.cursor_pos = start_pos
            value_changed = True
        elif len(key) == 1:
            # Regular character input - preserve case
            self.edit_value = self.edit_value[:self.cursor_pos] + key + self.edit_value[self.cursor_pos:]
            self.cursor_pos += 1
            value_changed = True
        elif key == Key.LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
            return True
        elif key == Key.RIGHT:
            if self.cursor_pos < len(self.edit_value):
                self.cursor_pos += 1
            return True
        else:
             # If we didn't handle the key, pass to parent
            return super().handle_input(key)
        
        if value_changed:
            self._check_validation()
            
        return True

    def _check_validation(self):
        """Check validation rules and update error_message."""
        self.error_message = ""
        
        # Check mandatory fields
        if self.setting_key == 'sources.habr.type' and not self.edit_value.strip():
            self.error_message = "Value is required for sources.habr.type"
            
        # Custom validator
        if not self.error_message and self.validator:
            self.error_message = self.validator(self.edit_value)

    def _validate_and_save(self) -> bool:
        """
        Validate the input based on the setting type and save if valid.
        """
        self._check_validation()
        if self.error_message:
            return False

        try:
            if self.setting_type == 'integer':
                # Try to convert to integer
                converted_value = int(self.edit_value)
            elif self.setting_type == 'date':
                # Try to validate date format (YYYY-MM-DD)
                datetime.strptime(self.edit_value, '%Y-%m-%d')
                converted_value = self.edit_value
            elif self.setting_type == 'boolean':
                # Validate boolean values
                if self.edit_value.lower() in ('true', 'false', '1', '0', 'yes', 'no'):
                    converted_value = self.edit_value.lower() in ('true', '1', 'yes')
                else:
                    self.error_message = f"Invalid boolean value. Use true/false, yes/no, or 1/0."
                    return False
            else:  # string
                converted_value = self.edit_value

            # If validation passed, save the setting
            if self.on_save:
                self.on_save(converted_value)

            # Go back to previous screen
            self.app.pop_screen()
            return True

        except ValueError as e:
            if self.setting_type == 'integer':
                self.error_message = f"Invalid integer value: {self.edit_value}"
            elif self.setting_type == 'date':
                self.error_message = f"Invalid date format. Use YYYY-MM-DD: {self.edit_value}"
            else:
                self.error_message = f"Invalid value: {str(e)}"
            return False

    def on_leave(self):
        """Called when leaving this screen."""
        self.app.console.clear()