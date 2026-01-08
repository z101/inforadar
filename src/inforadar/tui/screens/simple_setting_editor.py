from typing import Any, TYPE_CHECKING, Callable, Optional
from datetime import datetime

from rich import box
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from inforadar.tui.keys import Key
from inforadar.tui.screens.base import BaseScreen

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class SimpleSettingEditor(BaseScreen):
    """
    Screen for editing simple setting types: string, integer, date, boolean.
    This screen uses rich.live.Live to provide a flicker-free experience.
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
        
        self._live_started = False
        self.live = Live(
            self._generate_renderable(),
            console=self.app.console,
            screen=True,
            auto_refresh=False,
            transient=True,
            vertical_overflow="visible"
        )

    def _mount(self):
        """Starts the live display."""
        if not self._live_started:
            self.live.start(refresh=True)
            self._live_started = True

    def on_leave(self):
        """Stops the live display and clears the screen."""
        if self._live_started:
            self.live.stop()
        self.app.console.clear()

    def render(self):
        """Mounts the screen."""
        self._mount()

    def handle_input(self, key: str) -> bool:
        """Handles user input and updates the live display."""
        self._mount()
        
        should_exit = self._process_key(key)
        
        if should_exit:
            return True

        self._check_validation()
        self.live.update(self._generate_renderable(), refresh=True)

        return False

    def _process_key(self, key: str) -> bool:
        """Processes a key press and updates state. Returns True if the screen should exit."""
        if key == Key.ENTER:
            if self._validate_and_save():
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
        elif key == Key.CTRL_A:
            self.cursor_pos = 0
        elif key == Key.CTRL_E:
            self.cursor_pos = len(self.edit_value)
        elif key == Key.BACKSPACE or key == Key.CTRL_H:
            self.error_message = ""
            if self.setting_type == 'datetime':
                if self.cursor_pos > 0:
                    self.cursor_pos -= 1
                    if self.cursor_pos in [4, 7]: self.cursor_pos -= 1
                    if self.cursor_pos >= 0:
                        val = list(self.edit_value)
                        val[self.cursor_pos] = 'yyyy-MM-dd'[self.cursor_pos]
                        self.edit_value = "".join(val)
            elif self.cursor_pos > 0:
                self.edit_value = self.edit_value[:self.cursor_pos-1] + self.edit_value[self.cursor_pos:]
                self.cursor_pos -= 1
        elif key == Key.DELETE:
            self.error_message = ""
            if self.setting_type == 'datetime':
                if self.cursor_pos < 10:
                    val = list(self.edit_value)
                    val[self.cursor_pos] = 'yyyy-MM-dd'[self.cursor_pos]
                    self.edit_value = "".join(val)
            elif self.cursor_pos < len(self.edit_value):
                self.edit_value = self.edit_value[:self.cursor_pos] + self.edit_value[self.cursor_pos+1:]
        elif key == Key.CTRL_W and self.setting_type != 'datetime':
            self.error_message = ""
            start_pos = self.cursor_pos
            while start_pos > 0 and self.edit_value[start_pos-1] == ' ': start_pos -= 1
            while start_pos > 0 and self.edit_value[start_pos-1] != ' ': start_pos -= 1
            self.edit_value = self.edit_value[:start_pos] + self.edit_value[self.cursor_pos:]
            self.cursor_pos = start_pos
        elif self.setting_type == 'boolean' and key in (Key.TAB, '\t'):
            val_lower = self.edit_value.lower()
            if val_lower:
                if 'true'.startswith(val_lower):
                    self.edit_value = "True"
                    self.cursor_pos = len(self.edit_value)
                elif 'false'.startswith(val_lower):
                    self.edit_value = "False"
                    self.cursor_pos = len(self.edit_value)
        elif self.setting_type == 'datetime' and key in (Key.TAB, '\t'):
            if self.cursor_pos <= 4:
                self.cursor_pos = 5  # Move to month
            elif self.cursor_pos <= 7:
                self.cursor_pos = 8  # Move to day
            else:  # Day (and any other position)
                self.cursor_pos = 0  # Cycle back to year
        elif self.setting_type == 'boolean' and key in (Key.UP, Key.DOWN, 'j', 'k'):
            current_bool = self.edit_value.lower() == 'true'
            self.edit_value = str(not current_bool).capitalize()
            self.cursor_pos = len(self.edit_value)
        elif self.setting_type in ('datetime', 'integer') and key in ('h', 'l'):
            if key == 'h': # Move left
                if self.cursor_pos > 0: self.cursor_pos -= 1
            elif key == 'l': # Move right
                if self.cursor_pos < len(self.edit_value): self.cursor_pos += 1
        elif len(key) == 1:
            self._handle_char_input(key)
        elif key == Key.LEFT:
            if self.cursor_pos > 0: self.cursor_pos -= 1
        elif key == Key.RIGHT:
            if self.cursor_pos < len(self.edit_value): self.cursor_pos += 1

        return False

    def _generate_renderable(self) -> Group:
        """Builds the rich renderable for the entire screen."""
        title_type = 'datetime' if self.setting_type == 'datetime' else self.setting_type
        title = f"[green bold dim]Info Radar Settings Edit[/green bold dim] | {self.setting_key} | [yellow]{title_type}[/yellow]"
        desc_text = self.description if self.description else f"Edit {self.setting_key}"

        if self.cursor_pos <= len(self.edit_value):
            before_cursor = self.edit_value[:self.cursor_pos]
            after_cursor = self.edit_value[self.cursor_pos:]
            cursor_char = after_cursor[0] if after_cursor else " "
            display_value = Text(before_cursor)
            display_value.append(cursor_char, style="reverse")
            display_value.append(after_cursor[1:])
        else:
            display_value = Text(self.edit_value).append(" ", style="reverse")
        
        input_line = Text.from_markup("[dim green]> [/dim green]")
        input_line.append(display_value)

        error_line = Text(self.error_message, style="red") if self.error_message else Text()

        instruction_lines = [
            "[green]Enter[/green]: Save and exit",
            "[yellow]Esc[/yellow]: Cancel",
            "",
        ]
        if self.setting_type == "boolean":
            instruction_lines.extend([
                "[blue]j, k, Up, Down[/blue]: Toggle value",
                "[blue]Tab[/blue]: Autocomplete",
                "",
            ])
        
        if self.setting_type == "datetime":
            instruction_lines.append("[blue]Tab[/blue]: Cycle through year/month/day")
            instruction_lines.append("")

        if self.setting_type in ('datetime', 'integer'):
            instruction_lines.append("[blue]h, l, Left, Right[/blue]: Move cursor")
            instruction_lines.append("")

        instruction_lines.extend([
            "[blue]Ctrl+U[/blue]: Clear input",
            "[blue]Ctrl+A[/blue]: Move to beginning",
            "[blue]Ctrl+E[/blue]: Move to end",
            "[blue]Ctrl+H[/blue]: Delete character before cursor",
        ])

        if self.setting_type != 'datetime':
            instruction_lines.append("[blue]Ctrl+W[/blue]: Delete word before cursor")

        help_panel = Panel(
            "\n".join(instruction_lines), title="Help", title_align="center",
            border_style="dim white", style="dim white"
        )

        return Group(
            Text.from_markup(title, justify="center"), Text(),
            Text(desc_text, justify="left"), Text(),
            input_line,
            error_line,
            help_panel
        )

    def _handle_char_input(self, key: str):
        """Handles single-character text input for different setting types."""
        if self.setting_type == 'integer':
            if not key.isdigit():
                self.error_message = "Only digits are allowed for integer settings."
            else:
                self.error_message = ""
                self.edit_value = self.edit_value[:self.cursor_pos] + key + self.edit_value[self.cursor_pos:]
                self.cursor_pos += 1
        elif self.setting_type == 'boolean':
            potential_value = self.edit_value[:self.cursor_pos] + key + self.edit_value[self.cursor_pos:]
            if 'true'.startswith(potential_value.lower()) or 'false'.startswith(potential_value.lower()):
                self.error_message = ""
                self.edit_value = potential_value
                self.cursor_pos += 1
            else:
                self.error_message = 'Only "True" or "False" are allowed.'
        elif self.setting_type == 'datetime':
            if not key.isdigit() or self.cursor_pos >= 10:
                self.error_message = "Only digits are allowed for datetime settings."
                return
            
            pos = self.cursor_pos
            temp_error_msg = ""
            if pos == 5 and key not in '01':
                temp_error_msg = "Month's first digit must be 0 or 1."
            elif pos == 6 and self.edit_value[5] == '1' and key not in '012':
                temp_error_msg = "For month 10-12, second digit must be 0, 1, or 2."
            elif pos == 8 and key not in '0123':
                temp_error_msg = "Day's first digit must be 0, 1, 2, or 3."
            elif pos == 9 and self.edit_value[8] == '3' and key not in '01':
                temp_error_msg = "For day 30-31, second digit must be 0 or 1."

            if temp_error_msg:
                self.error_message = temp_error_msg
                return
            
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
                    return

            self.cursor_pos += 1
            if self.cursor_pos in [4, 7]:
                self.cursor_pos += 1
        else: # Default string input
            self.error_message = ""
            self.edit_value = self.edit_value[:self.cursor_pos] + key + self.edit_value[self.cursor_pos:]
            self.cursor_pos += 1

    def _check_validation(self):
        """Check validation rules and update error_message."""
        if self.setting_key == 'sources.habr.name' and not self.edit_value.strip():
            self.error_message = "Value is required for sources.habr.name"
        if not self.error_message and self.validator:
            self.error_message = self.validator(self.edit_value)

    def _validate_and_save(self) -> bool:
        """Validate input and save if valid."""
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
                    self.error_message = "Invalid boolean value. Use True/False."
                    return False
            else:
                converted_value = self.edit_value
            
            if self.on_save:
                self.on_save(converted_value)
            self.app.pop_screen()
            return True
        except ValueError as e:
            self.error_message = f"Invalid value: {str(e)}"
            return False