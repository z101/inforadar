from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class BaseScreen:
    def __init__(self, app: "AppState"):
        self.app = app

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
