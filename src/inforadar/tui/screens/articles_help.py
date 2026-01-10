from typing import List, Tuple
from inforadar.tui.screens.help_screen import HelpScreen


class ArticlesHelpScreen(HelpScreen):
    """A screen that displays help information for the Articles View."""

    def __init__(self, app: "AppState"):
        super().__init__(app, title="Articles View Help")

    def _get_help_content(self) -> List[Tuple[str, List[Tuple[str, str]]]]:
        return [
            (
                "Navigation and Basic Actions",
                [
                    ("j/k, ↓/↑", "Navigate the list"),
                    ("d", "Show/hide detailed information (source, topic, metrics)"),
                    ("q", "Exit the application (only on the main screen)"),
                    ("ESCAPE", "Close the current screen or exit selection mode"),
                    ("ENTER", "Open selected article for detailed view"),
                    ("?", "Show this help screen"),
                ],
            ),
            (
                "Sorting",
                [
                    ("r", "Sort by date/rating"),
                    ("v", "Sort by views (desc/asc)"),
                    ("c", "Sort by comments (desc/asc)"),
                    ("b", "Sort by bookmarks (desc/asc)"),
                ],
            ),
            (
                "Actions and Filters",
                [
                    ("f", "Open screen to fetch new articles (Fetch)"),
                    ("s", "Open settings"),
                    ("t", "Open topic filter"),
                ],
            ),
            (
                "Commands (enter with :)",
                [
                    (":fetch", "Fetch new articles"),
                    (":help, :?", "Show this help screen"),
                    (":q", "Exit the application"),
                ],
            ),
        ]
