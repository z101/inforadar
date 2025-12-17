from typing import TYPE_CHECKING

from inforadar.tui.screens.multi_select import MultiSelectScreen
from inforadar.tui.keys import Key

if TYPE_CHECKING:
    from inforadar.tui.app import AppState
    from inforadar.tui.screens.articles_view import ArticlesViewScreen


class TopicFilterScreen(MultiSelectScreen):
    def __init__(self, app: "AppState", parent_screen: "ArticlesViewScreen"):
        # Gather all hubs/topics from sources
        valid_sources = parent_screen.selected_sources

        topics = set()
        sources_cfg = app.engine.config.get("sources", {})

        for src_name, src_cfg in sources_cfg.items():
            if valid_sources and src_name not in valid_sources:
                continue

            hubs = src_cfg.get("hubs", [])
            for hub in hubs:
                if isinstance(hub, dict):
                    topics.add(hub.get("slug", "unknown"))
                else:
                    topics.add(str(hub))

        super().__init__(
            app,
            parent_screen,
            "Filter Topics",
            list(topics),
            parent_screen.selected_topics,
        )

    def handle_input(self, key: str) -> bool:
        if key == Key.ESCAPE:
            self.app.pop_screen()
            return True
        return super().handle_input(key)

    def on_apply(self):
        self.parent_screen.selected_topics = self.selected
        self.parent_screen.apply_filter_and_sort()

    def on_reset(self):
        self.parent_screen.selected_topics = set()
        self.parent_screen.apply_filter_and_sort()
