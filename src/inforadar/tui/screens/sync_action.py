from datetime import datetime
from typing import TYPE_CHECKING

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeRemainingColumn,
)
from rich.text import Text

from inforadar.tui.screens.action_screen import ActionScreen
from inforadar.tui.input import get_key
from inforadar.tui.keys import Key

if TYPE_CHECKING:
    from inforadar.tui.app import AppState
    from inforadar.tui.screens.view_screen import ViewScreen


class SyncActionScreen(ActionScreen):
    def __init__(self, app: "AppState", parent_screen: "ViewScreen"):
        super().__init__(app, parent_screen)
        self.started = False

    def render(self):
        if not self.started:
            self.started = True
            self.run_sync()

    def run_sync(self):
        console = self.app.console
        console.clear()

        # Setup UI components
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeRemainingColumn(),
        )

        log_text = Text()
        log_panel_height = 15
        all_log_lines = []

        def log_message(msg: str):
            timestamp = datetime.now().strftime("%H:%M:%S")
            all_log_lines.append(f"[{timestamp}] {msg}")
            # Keep only last N lines
            visible_lines = all_log_lines[-log_panel_height + 2 :]
            log_text.plain = "\n".join(visible_lines)

        header = Panel(
            Text("Syncing Articles...", justify="center"), style="bold white on blue"
        )

        layout = Group(
            header,
            Text(""),
            progress,
            Text(""),
            Panel(
                log_text,
                title="Sync Log",
                border_style="green",
                height=log_panel_height,
            ),
        )

        sources = self.app.engine.config.get("sources", {})
        task = progress.add_task("Syncing...", total=len(sources))

        with Live(layout, console=console, refresh_per_second=10):
            for name in sources.keys():
                self.app.engine.run_sync(
                    source_names=[name], progress=progress, log_callback=log_message
                )
                progress.advance(task, 1)

            log_message("Sync completed! Press Esc to return.")

        # Wait for Esc
        while True:
            key = get_key()
            if key == Key.ESCAPE:
                break

        self.parent_screen.refresh_data()
        self.app.pop_screen()
