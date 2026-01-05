from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.console import Group

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.keys import Key
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from inforadar.tui.app import AppState

class ConfirmationScreen(BaseScreen):
    """
    A centered, dynamically sized confirmation popup.
    """
    def __init__(
        self, 
        app: "AppState", 
        message: str, 
        on_confirm: Callable[[], None], 
        on_cancel: Callable[[], None] = None
    ):
        super().__init__(app)
        self.message = message
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.confirm_key = Key.ENTER
        self.cancel_key = Key.ESCAPE

    def _get_shortcuts_text(self) -> str:
        """Creates the styled shortcut text as a markup string."""
        return "[[bold]Enter[/bold]] Yes  [[bold]Esc[/bold]] No"

    def render(self):
        """Renders the confirmation panel, centered on the screen."""
        console = self.app.console
        
        message_text = Text(self.message, justify="center")
        shortcuts_markup = self._get_shortcuts_text()
        shortcuts_text_renderable = Text.from_markup(shortcuts_markup, justify="center", style="dim")

        # Calculate dynamic width and height
        message_lines = message_text.wrap(console, width=console.width - 10)
        text_height = len(list(message_lines))
        max_text_width = max(line.cell_len for line in message_lines) if message_lines else 0
        
        shortcuts_width = shortcuts_text_renderable.cell_len
        
        panel_width = max(max_text_width, shortcuts_width) + 4 # +4 for padding
        # Height: text lines + 2 for panel border + 3 for spacer lines (top, middle, bottom) + 1 for shortcuts
        panel_height = text_height + 6 

        # Construct panel content
        panel_content = Group(
            Text(" "),
            message_text,
            Text(" "),
            shortcuts_text_renderable,
            Text(" ")
        )

        panel = Panel(
            panel_content,
            title="Confirmation",
            border_style="red",
            width=panel_width,
            height=panel_height,
            title_align="center"
        )
        
        # Manual vertical centering
        console.print("\n" * (console.size.height // 3))
        # Horizontal centering
        console.print(Align.center(panel))

    def handle_input(self, key: str) -> bool:
        if key == self.confirm_key:
            # Important: stop rendering this screen before calling callbacks
            # that might change the screen stack.
            self.app.pop_screen() 
            self.on_confirm()
            return True
        elif key == self.cancel_key:
            self.app.pop_screen()
            if self.on_cancel:
                self.on_cancel()
            return True
        return True # Consume all other input

    def on_leave(self):
        # Clear the console to prevent artifacts from remaining when this popup is closed.
        self.app.console.clear()