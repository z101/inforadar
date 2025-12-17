import threading
import time
from datetime import datetime
from typing import List, TYPE_CHECKING

from rich.console import Group
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeRemainingColumn,
)
from rich.text import Text

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.input import get_key
from inforadar.tui.keys import Key

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


RESERVED_LINES_FOR_UI = (
    8  # Header (1), empty line (1), progress bar (1), footer (3), panel borders (2)
)


class FetchScreen(BaseScreen):
    """Screen for fetching articles with progress and logs."""

    def __init__(
        self, app: "AppState", selected_sources: set = None, selected_topics: set = None
    ):
        super().__init__(app)
        self.selected_sources = selected_sources or set()
        self.selected_topics = selected_topics or set()

        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TimeRemainingColumn(),
            expand=True,
        )
        # Add an initial indefinite task for the 'init' state
        self.progress.add_task("Press 's' to start...", total=None)
        self.logs: List[str] = []
        self.cancel_event = threading.Event()
        self.worker_thread = None
        self.lock = threading.Lock()

        self.state = "init"  # "init", "running", "cancelled", "finished"

    def work(self):
        """The actual fetch logic that runs in a background thread."""

        def log_cb(msg):
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.logs.append(f"[{timestamp}] {msg}")

        try:
            self.app.engine.run_sync(
                source_names=(
                    list(self.selected_sources) if self.selected_sources else None
                ),
                log_callback=log_cb,
                progress=self.progress,
                cancel_event=self.cancel_event,
            )
            with self.lock:
                self.logs.append("[green]Fetch completed.[/green]")
                self.state = "finished"
        except Exception as e:
            with self.lock:
                self.logs.append(f"[red]Error: {str(e)}[/red]")
                self.state = "finished"
        finally:
            if self.cancel_event.is_set() and self.state != "finished":
                with self.lock:
                    self.logs.append("[yellow]Fetch cancelled by user.[/yellow]")
                    self.state = "cancelled"

    def start_fetch(self):
        if self.state == "init":
            self.state = "running"
            # Remove the initial indefinite task
            self.progress.remove_task(self.progress.tasks[0].id)
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.logs.append(f"[{timestamp}] [cyan]Starting fetch...[/cyan]")
            self.worker_thread = threading.Thread(target=self.work, daemon=True)
            self.worker_thread.start()

    def cancel_fetch(self):
        if self.state == "running":
            self.cancel_event.set()
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.logs.append(f"[{timestamp}] [yellow]Cancelling...[/yellow]")
            # The worker thread will see the event and stop

    def _build_header_text(self) -> str:
        """Builds header text matching the main screen's styling."""
        parts = ["[bold green dim]Info Radar Fetch[/bold green dim]"]

        sources_config = self.app.engine.config.get("sources", {})
        cutoff_dates = [
            cfg.get("initial_fetch_date", "").split()[0]
            for cfg in sources_config.values()
            if "initial_fetch_date" in cfg
        ]
        if cutoff_dates:
            parts.append(
                f"[dim]Cutoff[/dim] [bold white]{min(cutoff_dates)}[/bold white]"
            )

        if self.selected_sources:
            items = ", ".join(sorted(self.selected_sources))
            parts.append(
                f"[dim]Sources[/dim] [[bold white]{escape(items)}[/bold white]]"
            )

        if self.selected_topics:
            items = ", ".join(sorted(self.selected_topics))
            parts.append(
                f"[dim]Topics[/dim] [[bold white]{escape(items)}[/bold white]]"
            )

        return " | ".join(parts)

    def _build_layout(self) -> Group:
        """Assembles the renderable layout for the Live display."""
        header = self._build_header_text()
        log_lines_to_show = self.app.console.height - RESERVED_LINES_FOR_UI

        with self.lock:
            visible_logs = (
                self.logs[-log_lines_to_show:] if log_lines_to_show > 0 else []
            )
            log_content = "\n".join(visible_logs)

        logs_panel = Panel(
            Text.from_markup(log_content),
            title="Logs",
            border_style="green",
            height=log_lines_to_show + 2,
            expand=True,
        )

        footer_text = ""
        if self.state == "init":
            footer_text = "[[bold white]s[/bold white]] Start [[bold white]Esc, q[/bold white]] Exit"
        elif self.state == "running":
            footer_text = "[[bold white]Esc, q[/bold white]] Cancel"
        else:  # "finished" or "cancelled"
            footer_text = "[[bold white]Esc, q[/bold white]] Close"

        return Group(
            Text.from_markup(header, justify="center"),
            "",
            self.progress,
            logs_panel,
            "",  # Empty line for spacing
            Text.from_markup(footer_text, style="dim", justify="center"),
        )

    def run(self):
        """Blocking method that runs the fetch process within a Live context."""
        try:
            self.app.console.clear()
            with Live(
                self._build_layout(),
                console=self.app.console,
                refresh_per_second=10,
                transient=True,
            ) as live:
                while not self.cancel_event.is_set():
                    live.update(self._build_layout())
                    key = get_key()
                    if key:
                        if key in (Key.Q, Key.ESCAPE):
                            if self.state == "running":
                                self.cancel_fetch()
                            else:
                                break  # Exit the loop and screen
                        elif key == Key.S and self.state == "init":
                            self.start_fetch()

                    # Check if worker is done
                    if (
                        self.state in ("finished", "cancelled")
                        and self.worker_thread
                        and not self.worker_thread.is_alive()
                    ):
                        # Just wait for final 'q'
                        pass

                    # Exit loop if worker finished and we are not in running state
                    if (
                        self.state != "running"
                        and self.worker_thread
                        and not self.worker_thread.is_alive()
                    ):
                        # Final render, then wait for q
                        live.update(self._build_layout())
                        while get_key() not in (Key.Q, Key.ESCAPE):
                            time.sleep(0.1)
                        break

                    # Removed redundant time.sleep(0.05)
        finally:
            self.app.console.show_cursor(False)
