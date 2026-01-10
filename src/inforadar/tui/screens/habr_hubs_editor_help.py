from typing import List, Tuple
from inforadar.tui.screens.help_screen import HelpScreen


class HabrHubsEditorHelpScreen(HelpScreen):
    """A screen that displays help for the Habr Hubs Editor."""

    def __init__(self, app: "AppState"):
        super().__init__(app, title="Hub Editor")

    def _get_help_content(self) -> List[Tuple[str, List[Tuple[str, str]]]]:
        return [
            (
                "Navigation",
                [
                    ("j, ↓", "Move cursor down"),
                    ("k, ↑", "Move cursor up"),
                    ("l", "Next page"),
                    ("h", "Previous page"),
                    ("gg", "Go to top of list"),
                    ("G", "Go to bottom of list"),
                    ("1-9", "Select row on page"),
                ],
            ),
            (
                "Hub Actions",
                [
                    ("Enter", "Edit selected hub's Name"),
                    ("e", "Toggle 'enabled' status of hub"),
                    ("o", "Open hub page in browser"),
                    ("f", "Fetch all hubs from Habr"),
                ],
            ),
            (
                "Sorting (toggles asc/desc)",
                [
                    ("r", "Sort by Rating"),
                    ("s", "Sort by Subscribers"),
                    ("n", "Sort by Name"),
                ],
            ),
            (
                "Filtering / Commands",
                [
                    ("/", "Filter hubs by ID or Name"),
                    (":", "Enter command mode (no commands implemented)"),
                ],
            ),
            (
                "Application",
                [
                    ("q, Esc", "Go back"),
                    ("?", "Show this help screen"),
                ],
            ),
        ]
