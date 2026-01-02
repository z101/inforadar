from rich.panel import Panel
from rich.align import Align
from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.keys import Key
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from inforadar.tui.app import AppState

class ConfirmationScreen(BaseScreen):
    """
    Generic confirmation popup screen.
    """
    def __init__(
        self, 
        app: "AppState", 
        message: str, 
        on_confirm: Callable[[], None], 
        on_cancel: Callable[[], None] = None,
        confirm_key: str = Key.ENTER,
        cancel_key: str = Key.ESCAPE,
        confirm_label: str = "Yes",
        cancel_label: str = "No"
    ):
        super().__init__(app)
        self.message = message
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.confirm_key = confirm_key
        self.cancel_key = cancel_key
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label

    def render(self):
        width = self.app.console.size.width
        
        # Format keys like footer: [ reverse ] Key [ /reverse ] Label
        # Use friendly names for keys
        k_confirm = "Enter" if self.confirm_key == Key.ENTER else self.confirm_key
        k_cancel = "Esc" if self.cancel_key == Key.ESCAPE else self.cancel_key
        
        shortcuts = f"[reverse] {k_confirm} [/reverse] {self.confirm_label}    [reverse] {k_cancel} [/reverse] {self.cancel_label}"

        panel = Panel(
            Align.center(f"\n{self.message}\n\n{shortcuts}\n"),
            title="Confirmation",
            border_style="red",
            width=min(60, width - 4),
            padding=(1, 2)
        )
        
        self.app.console.print("\n" * (self.app.console.size.height // 3))
        self.app.console.print(Align.center(panel))

    def handle_input(self, key: str) -> bool:
        if key == self.confirm_key:
            self.on_confirm()
            self.app.pop_screen()
            return True
        elif key == self.cancel_key:
            if self.on_cancel:
                self.on_cancel()
            self.app.pop_screen()
            return True
        return True

    def on_leave(self):
        self.app.console.clear()
