from typing import Any, TYPE_CHECKING, Callable, Optional
import calendar
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
        if self.setting_type == 'date':
            self.setting_type = 'datetime'

        self.description = description
        self.on_save = on_save
        self.validator = validator

        if self.setting_type == 'datetime':
            self.edit_value = 'yyyy-MM-dd'
            if current_value:
                try:
                    if isinstance(current_value, datetime):
                        self.edit_value = current_value.strftime('%Y-%m-%d')
                    else:
                        dt = datetime.strptime(str(current_value), '%Y-%m-%d')
                        self.edit_value = dt.strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    pass
            self.cursor_pos = 0
        elif self.setting_type == 'boolean':
            self.edit_value = str(current_value)
            self.cursor_pos = len(self.edit_value)
        else:
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
        title_type = 'datetime' if self.setting_type == 'datetime' else self.setting_type
        title = f"[green bold dim]Info Radar Settings Edit[/green bold dim] | {self.setting_key} | [yellow]{title_type}[/yellow]"
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
        instructions += "[green]Enter[/green]: Save and exit\n"
        instructions += "[yellow]Esc[/yellow]: Cancel\n"
        instructions += "\n"
        if self.setting_type == "boolean":
            instructions += "[blue]j, k, Up, Down[/blue]: Toggle value\n\n"
        instructions += "[blue]Ctrl+U[/blue]: Clear input\n"
        instructions += "[blue]Ctrl+A[/blue]: Move to beginning\n"
        instructions += "[blue]Ctrl+E[/blue]: Move to end\n"
        instructions += "[blue]Ctrl+H[/blue]: Delete character before cursor\n"
        if self.setting_type != 'datetime':
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
            if self._validate_and_save():
                return True
            return True
        elif key == Key.ESCAPE:
            self.app.pop_screen()
            return True
        elif key == Key.CTRL_U:
            self.error_message = ""
            if self.setting_type == 'datetime':
                self.edit_value = 'yyyy-MM-dd'
                self.cursor_pos = 0
            else:
                self.edit_value = ""
                self.cursor_pos = 0
            value_changed = True
        elif key == Key.CTRL_A:
            self.cursor_pos = 0
            return True
        elif key == Key.CTRL_E:
            self.cursor_pos = len(self.edit_value)
            return True
        elif key == Key.BACKSPACE or key == Key.CTRL_H:
            self.error_message = ""
            if self.setting_type == 'datetime':
                if self.cursor_pos > 0:
                    self.cursor_pos -= 1
                    if self.cursor_pos in [4, 7]:
                        self.cursor_pos -= 1
                    
                    if self.cursor_pos >= 0:
                        val = list(self.edit_value)
                        val[self.cursor_pos] = 'yyyy-MM-dd'[self.cursor_pos]
                        self.edit_value = "".join(val)
                        value_changed = True
            elif self.cursor_pos > 0:
                self.edit_value = self.edit_value[:self.cursor_pos-1] + self.edit_value[self.cursor_pos:]
                self.cursor_pos -= 1
                value_changed = True
            return True
        elif key == Key.DELETE:
            self.error_message = ""
            if self.setting_type == 'datetime':
                if self.cursor_pos < 10:
                    val = list(self.edit_value)
                    val[self.cursor_pos] = 'yyyy-MM-dd'[self.cursor_pos]
                    self.edit_value = "".join(val)
                    value_changed = True
            elif self.cursor_pos < len(self.edit_value):
                 self.edit_value = self.edit_value[:self.cursor_pos] + self.edit_value[self.cursor_pos+1:]
                 value_changed = True
            return True
        elif key == Key.CTRL_W:
            if self.setting_type != 'datetime':
                self.error_message = ""
                start_pos = self.cursor_pos
                while start_pos > 0 and self.edit_value[start_pos-1] == ' ':
                    start_pos -= 1
                while start_pos > 0 and self.edit_value[start_pos-1] != ' ':
                    start_pos -= 1
                self.edit_value = self.edit_value[:start_pos] + self.edit_value[self.cursor_pos:]
                self.cursor_pos = start_pos
                value_changed = True
            else:
                return True
        elif self.setting_type == 'boolean' and key in (Key.UP, Key.DOWN, 'j', 'k'):
            current_bool = self.edit_value.lower() == 'true'
            self.edit_value = str(not current_bool).capitalize()
            self.cursor_pos = len(self.edit_value)
            value_changed = True
        elif len(key) == 1:
            if self.setting_type == 'integer':
                if not key.isdigit():
                    error_msg = "Only digits are allowed for integer settings."
                    if self.error_message == error_msg:
                        return False
                    else:
                        self.error_message = error_msg
                        return True
                
                self.error_message = ""
                self.edit_value = self.edit_value[:self.cursor_pos] + key + self.edit_value[self.cursor_pos:]
                self.cursor_pos += 1
                value_changed = True
            elif self.setting_type == 'boolean':
                potential_value = self.edit_value[:self.cursor_pos] + key + self.edit_value[self.cursor_pos:]
                
                is_prefix_of_true = 'true'.startswith(potential_value.lower())
                is_prefix_of_false = 'false'.startswith(potential_value.lower())

                if is_prefix_of_true or is_prefix_of_false:
                    self.error_message = ""
                    self.edit_value = potential_value
                    self.cursor_pos += 1
                    value_changed = True
                else:
                    error_msg = 'Only "True" or "False" are allowed.'
                    if self.error_message == error_msg:
                        return False
                    else:
                        self.error_message = error_msg
                        return True
            elif self.setting_type == 'datetime':
                if not key.isdigit() or self.cursor_pos >= 10:
                    error_msg = "Only digits are allowed for datetime settings."
                    if self.error_message == error_msg:
                        return False
                    self.error_message = error_msg
                    return True
                
                pos = self.cursor_pos
                
                error_msg = ""
                if pos == 5 and key not in '01':
                    error_msg = "Month's first digit must be 0 or 1."
                elif pos == 6 and self.edit_value[5] == '1' and key not in '012':
                    error_msg = "For month 10-12, second digit must be 0, 1, or 2."
                elif pos == 8 and key not in '0123':
                    error_msg = "Day's first digit must be 0, 1, 2, or 3."
                elif pos == 9 and self.edit_value[8] == '3' and key not in '01':
                    error_msg = "For day 30-31, second digit must be 0 or 1."

                if error_msg:
                    if self.error_message == error_msg:
                        return False
                    self.error_message = error_msg
                    return True
                
                self.error_message = ""
                val = list(self.edit_value)
                val[pos] = key
                self.edit_value = "".join(val)

                if pos == 9:
                    try:
                        datetime.strptime(self.edit_value, '%Y-%m-%d')
                    except ValueError:
                        self.error_message = 'Invalid day for the given month and year.'
                        val[pos] = 'd'
                        self.edit_value = "".join(val)
                        return True

                self.cursor_pos += 1
                if self.cursor_pos in [4, 7]:
                    self.cursor_pos += 1
                value_changed = True
                return True

            else:
                self.error_message = ""
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
            return super().handle_input(key)
        
        if value_changed:
            self._check_validation()
            return True
        else:
            return False

    def _check_validation(self):
        """Check validation rules and update error_message."""
        if self.setting_key == 'sources.habr.name' and not self.edit_value.strip():
            self.error_message = "Value is required for sources.habr.name"
            
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
                converted_value = int(self.edit_value) if self.edit_value else 0
            elif self.setting_type == 'datetime':
                datetime.strptime(self.edit_value, '%Y-%m-%d')
                converted_value = self.edit_value
            elif self.setting_type == 'boolean':
                if self.edit_value.lower() in ('true', 'false'):
                    converted_value = self.edit_value.lower() == 'true'
                else:
                    self.error_message = f"Invalid boolean value. Use True/False."
                    return False
            else:
                converted_value = self.edit_value

            if self.on_save:
                self.on_save(converted_value)

            self.app.pop_screen()
            return True

        except ValueError as e:
            if self.setting_type == 'integer':
                self.error_message = f"Invalid integer value: {self.edit_value}"
            elif self.setting_type == 'datetime':
                self.error_message = f"Invalid date format or value. Use YYYY-MM-DD: {self.edit_value}"
            else:
                self.error_message = f"Invalid value: {str(e)}"
            return False

    def on_leave(self):
        """Called when leaving this screen."""
        self.app.console.clear()