from typing import TYPE_CHECKING

from inforadar.tui.screens.multi_select import MultiSelectScreen
from inforadar.tui.keys import Key


if TYPE_CHECKING:
    from inforadar.tui.app import AppState
    from inforadar.tui.screens.articles_view import ArticlesViewScreen


class SourceFilterScreen(MultiSelectScreen):
    def __init__(self, app: "AppState", parent_screen: "ArticlesViewScreen"):
        sources = list(app.engine.config.get("sources", {}).keys())
        super().__init__(
            app,
            parent_screen,
            "Filter Sources",
            sources,
            parent_screen.selected_sources,
        )

    def on_apply(self):
        self.parent_screen.selected_sources = self.selected
        self.parent_screen.apply_filter_and_sort()

    def on_reset(self):
        self.parent_screen.selected_sources = set()
        self.parent_screen.apply_filter_and_sort()
