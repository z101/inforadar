from typing import List, Tuple
from inforadar.tui.screens.help_screen import HelpScreen


class SettingsHelpScreen(HelpScreen):
    """A screen that displays help for the Settings Screen."""

    def __init__(self, app: "AppState"):
        super().__init__(app, title="Settings")

    def _get_help_content(self) -> List[Tuple[str, List[Tuple[str, str]]]]:
        return [
            (
                "Navigation",
                [
                    ("j, ↓", "Move cursor down"),
                    ("k, ↑", "Move cursor up"),
                    ("l, →", "Next page"),
                    ("h, ←", "Previous page"),
                    ("gg", "Go to top of list"),
                    ("G", "Go to bottom of list"),
                ],
            ),
            (
                "Actions",
                [
                    ("Enter", "Edit selected setting"),
                    ("n", "Toggle sort by name (asc/desc)"),
                ],
            ),
            (
                "Filtering / Commands",
                [
                    ("/", "Filter settings by name"),
                    (":", "Enter command mode"),
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
