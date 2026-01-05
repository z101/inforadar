from typing import TYPE_CHECKING
from rich.align import Align
from rich.console import Console, RenderableType

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class BaseScreen:
    def __init__(self, app: "AppState"):
        self.app = app
        self.need_clear = False

    def render(self):
        pass

    def handle_input(self, key: str) -> bool:
        from inforadar.tui.screens.help import HelpScreen
        from inforadar.tui.screens.settings_screen import SettingsScreen
        from inforadar.tui.keys import Key

        if key == Key.QUESTION:
            self.app.push_screen(HelpScreen(self.app))
            return True
        elif key == Key.S:
            self.app.push_screen(SettingsScreen(self.app))
            return True
        elif key == Key.Q:
            if len(self.app.screen_stack) > 1:
                self.app.pop_screen()
            else:
                self.app.running = False
            return True
        elif key == Key.ESCAPE:
            if len(self.app.screen_stack) > 1:
                self.app.pop_screen()
                return True
        return False

    def on_leave(self):
        """Called when leaving this screen."""
        pass


class ModalScreen(BaseScreen):
    """A screen that renders as a modal on top of the previous screen."""
    
    @property
    def manages_own_screen(self) -> bool:
        # This tells the app loop not to clear the screen before rendering
        return True

    def render(self):
        # We need to render the screen below first
        if len(self.app.screen_stack) > 1:
            underlying_screen = self.app.screen_stack[-2]
            underlying_screen.render()

        # Now render the modal content on top
        modal_content = self.render_modal_content()
        self.app.console.print(Align.center(modal_content, vertical="middle"))

    def render_modal_content(self) -> "Renderable":
        """Subclasses must implement this to return a Rich renderable."""
        raise NotImplementedError
