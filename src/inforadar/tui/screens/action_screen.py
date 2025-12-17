from typing import TYPE_CHECKING

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.keys import Key

if TYPE_CHECKING:
    from inforadar.tui.app import AppState
    from inforadar.tui.screens.view_screen import ViewScreen


class ActionScreen(BaseScreen):
    def __init__(self, app: "AppState", parent_screen: "ViewScreen"):
        super().__init__(app)
        self.parent_screen = parent_screen

    def handle_input(self, key: str) -> bool:
        if key == Key.ESCAPE:
            self.app.pop_screen()
            return True
        else:
            return super().handle_input(key)
