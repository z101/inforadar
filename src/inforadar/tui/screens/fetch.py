import threading
import time
from datetime import datetime
from typing import List, TYPE_CHECKING
import random

from rich.console import Group
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    Task,
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


class OptionalMofNCompleteColumn(MofNCompleteColumn):
    """Custom MofNCompleteColumn that renders nothing if task.total is None."""

    def render(self, task: Task) -> Text:
        if task.total is None:
            return Text("")
        return super().render(task)


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
            OptionalMofNCompleteColumn(),
            expand=True,
        )
        self.main_task_id = self.progress.add_task("Press 's' to start...", total=None)
        self.logs: List[str] = []
        self.cancel_event = threading.Event()
        self.worker_thread = None
        self.lock = threading.Lock()

        self.state = "init"  # "init", "running"
        self.is_active = True
        self.log_scroll_offset = 0

    def _reset_to_init_state(self):
        """Resets the screen to its initial state after a process."""
        self.progress.remove_task(self.main_task_id)
        self.main_task_id = self.progress.add_task("Press 's' to start...", total=None)
        self.state = "init"
        self.log_scroll_offset = 0

    def work(self):
        """Simulates Stage 1 of the fetch process."""
        total_articles_found = 0

        def log_cb(msg):
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.logs.append(f"[{timestamp}] {msg}")
                # Auto-scroll to bottom on new log unless user has scrolled up
                if self.log_scroll_offset > 0:
                    self.log_scroll_offset += 1
                else:
                    self.log_scroll_offset = 0

        try:
            log_cb("Starting Stage 1: collecting topics...")

            # 1. Get configuration and determine sources
            all_sources_config = self.app.engine.config.get("sources", {})
            source_names_to_process = self.selected_sources or all_sources_config.keys()

            # 2. Collect all topics from the selected sources
            topics_to_process = []
            for name in source_names_to_process:
                if name in all_sources_config:
                    source_config = all_sources_config[name]
                    topics_to_process.extend(source_config.get("hubs", []))

            # 3. Filter topics if a topic filter is set
            if self.selected_topics:
                topics_to_process = [
                    topic
                    for topic in topics_to_process
                    if topic in self.selected_topics
                ]

            if not topics_to_process:
                log_cb(
                    "[yellow]No topics to process based on current filters.[/yellow]"
                )
                return

            log_cb(f"Found {len(topics_to_process)} topics to process.")
            time.sleep(1)

            # 4. Set up progress bar for Stage 1
            self.progress.update(
                self.main_task_id,
                description="Stage 1: Getting Articles",
                total=len(topics_to_process),
                completed=0,
                visible=True,
            )

            # 5. Process topics
            for i, topic in enumerate(topics_to_process):
                if self.cancel_event.is_set():
                    break

                self.progress.update(
                    self.main_task_id, description=f"Reading topic: {topic}"
                )
                log_cb(f"Reading topic: {topic} ({i+1}/{len(topics_to_process)})")

                time.sleep(random.uniform(0.3, 1.0))

                num_found = random.randint(0, 5)
                total_articles_found += num_found
                log_cb(f"Found {num_found} article links in {topic}")

                self.progress.advance(self.main_task_id)

            if self.cancel_event.is_set():
                return

        except Exception as e:
            with self.lock:
                log_cb(f"[red]Error: {str(e)}[/red]")
        finally:
            with self.lock:
                if self.cancel_event.is_set():
                    self.logs.append("[yellow]Fetch cancelled by user.[/yellow]")
                elif "total_articles_found" in locals():
                    self.logs.append(
                        f"[green]Stage 1 finished. Found a total of {total_articles_found} articles to read.[/green]"
                    )
                self._reset_to_init_state()

    def start_fetch(self):
        if self.state == "init":
            self.state = "running"
            self.cancel_event = threading.Event()
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
            # Adjust slicing based on scroll offset
            end_index = len(self.logs) - self.log_scroll_offset
            start_index = max(0, end_index - log_lines_to_show)
            visible_logs = self.logs[start_index:end_index]

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
            footer_text = "[[bold white]s[/bold white]] Start [[bold white]j/k[/bold white]] Scroll [[bold white]Esc, q[/bold white]] Exit"
        elif self.state == "running":
            footer_text = "[[bold white]j/k[/bold white]] Scroll [[bold white]Esc, q[/bold white]] Cancel"

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
                while self.is_active:
                    live.update(self._build_layout())
                    key = get_key()
                    if key:
                        if key in (Key.Q, Key.ESCAPE):
                            if self.state == "running":
                                self.cancel_fetch()
                            elif self.state == "init":
                                self.is_active = False
                        elif key == Key.S and self.state == "init":
                            self.start_fetch()
                        elif key == Key.K:  # Scroll up
                            with self.lock:
                                max_scroll = len(self.logs) - 1
                                self.log_scroll_offset = min(
                                    max_scroll, self.log_scroll_offset + 1
                                )
                        elif key == Key.J:  # Scroll down
                            with self.lock:
                                self.log_scroll_offset = max(
                                    0, self.log_scroll_offset - 1
                                )

        finally:
            self.app.console.show_cursor(False)
