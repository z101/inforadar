import threading
from datetime import datetime
from typing import List, TYPE_CHECKING, Any, Optional, Callable
import traceback

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
)
from rich.text import Text

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.keys import Key
from inforadar.tui.screens.fetch import (
    OptionalMofNCompleteColumn,
    RESERVED_LINES_FOR_UI,
)

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class HubFetchScreen(BaseScreen):
    """Screen for fetching hubs with progress and logs."""

    def __init__(self, app: "AppState", on_complete: Optional[Callable] = None):
        super().__init__(app)
        self.on_complete = on_complete

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

        self.state = "init"  # "init", "running", "done"
        self.log_scroll_offset = 0
        self.live: Optional[Live] = None
        self.manages_own_screen = True
        self.needs_final_render = False
        self.auto_scroll_enabled = True
        self.error_occurred = False # New flag to track errors

    def on_leave(self) -> None:
        if self.live:
            self.live.stop()
            self.live = None

    def on_resize(self):
        if self.live:
            self.live.stop()
            self.live = None

    def _reset_to_init_state(self):
        self.progress.remove_task(self.main_task_id)
        self.main_task_id = self.progress.add_task("Press 's' to start...", total=None)
        self.state = "init"
        self.log_scroll_offset = 0
        self.error_occurred = False # Reset error flag

    def work(self):
        """Runs the hub fetch and merge process."""

        def progress_cb(progress_data: dict):
            """Callback to handle progress updates from the core engine."""
            with self.lock:
                message = progress_data.get("message", "...")
                stage = progress_data.get("stage", "log")
                current = progress_data.get("current")
                total = progress_data.get("total")
                
                # Always log the message
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.logs.append(f"[grey50][{timestamp}][/grey50] {message}")

                # Update progress bar based on stage
                task = self.progress.tasks[0] if self.progress.tasks else None
                if not task:
                    return

                if stage == 'fetching':
                    if task.total is None and total is not None:
                        self.progress.update(self.main_task_id, total=total, description="Fetching...")
                    self.progress.update(self.main_task_id, completed=current)
                elif stage == 'merging':
                    self.progress.update(self.main_task_id, total=None, description="Merging...")

        try:
            # The first log is now handled by start_fetch
            self.app.engine.fetch_and_merge_hubs(
                on_progress=progress_cb,
                cancel_event=self.cancel_event,
            )

            # The on_complete callback is now called via on_after_pop
            # to ensure it runs in the main thread.
            pass

        except Exception as e:
            # This block is executed in the worker thread.
            # It's critical to only modify shared data (self.logs) inside the lock
            # and not to call any methods that might interact with the UI thread.
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                error_msg = f"[bold red]An unexpected error occurred: {str(e)}[/bold red]"
                stack_trace = traceback.format_exc()
                self.logs.append(f"[grey50][{timestamp}][/grey50] {error_msg}")
                self.logs.append(f"[dim]{stack_trace}[/dim]")
                self.error_occurred = True # Set the error flag
        finally:
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                if self.cancel_event.is_set():
                    self.logs.append(
                        f"[grey50][{timestamp}][/grey50] [yellow]Fetch cancelled by user.[/yellow]"
                    )
                elif self.error_occurred: # Check the new error flag
                    self.logs.append(
                        f"[grey50][{timestamp}][/grey50] [red]Fetch completed with errors.[/red]"
                    )
                else:
                    self.logs.append(
                        f"[grey50][{timestamp}][/grey50] [green]Fetch completed.[/green]"
                    )
                self._reset_to_init_state()
                self.needs_final_render = True

    def start_fetch(self):
        if self.state == "init":
            self.state = "running"
            self.cancel_event = threading.Event()
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.logs.append(
                    f"[grey50][{timestamp}][/grey50] [cyan]Starting to fetch hubs from Habr...[/cyan]"
                )
            self.worker_thread = threading.Thread(target=self.work, daemon=True)
            self.worker_thread.start()

    def cancel_fetch(self):
        if self.state == "running":
            self.state = "done"
            self.cancel_event.set()
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.logs.append(
                    f"[grey50][{timestamp}][/grey50] [yellow]Cancelling...[/yellow]"
                )

    def needs_refresh(self) -> bool:
        return self.state == "running" or self.needs_final_render

    def handle_input(self, key: str) -> bool:
        should_render = False

        if key in (Key.Q, Key.ESCAPE):
            if self.state == "running":
                self.cancel_fetch()
            else:
                self.app.pop_screen(on_after_pop=self.on_complete)
            should_render = True
        elif key == Key.S and self.state == "init":
            self.start_fetch()
            should_render = True
        
        return should_render

    def _build_header_text(self) -> str:
        return "[bold green dim]Info Radar Hub Fetch[/bold green dim]"

    def _build_layout(self) -> Group:
        console_height = self.app.console.height
        log_lines_to_show = (
            console_height - RESERVED_LINES_FOR_UI
            if console_height > RESERVED_LINES_FOR_UI
            else 1
        )
        header = self._build_header_text()
        with self.lock:
            end_index = len(self.logs) - self.log_scroll_offset
            start_index = max(0, end_index - log_lines_to_show)
            visible_logs = self.logs[start_index:end_index]
            log_content = Text("\n").join(
                [Text.from_markup(line) for line in visible_logs]
            )

        logs_panel = Panel(
            log_content,
            title="Logs",
            border_style="green",
            height=log_lines_to_show + 2,
            expand=True,
        )

        footer_text = ""
        if self.state == "init":
            footer_text = "[[bold white]s[/bold white]] Start [[bold white]Esc, q[/bold white]] Back"
        elif self.state == "running":
            footer_text = "[[bold white]Esc, q[/bold white]] Cancel"
        elif self.state == "done":
            footer_text = "[[bold white]Esc, q[/bold white]] Back"
        footer = Text.from_markup(footer_text, style="dim", justify="center")
        
        return Group(
            Text.from_markup(header, justify="center"),
            "",
            self.progress,
            logs_panel,
            "",
            footer,
        )

    def render(self) -> None:
        if self.needs_final_render:
            self.needs_final_render = False

        if not self.live:
            self.app.console.clear()
            self.live = Live(
                self._build_layout(),
                console=self.app.console,
                screen=False,
                refresh_per_second=10,
            )
            self.live.start(refresh=True)
        else:
            self.live.update(self._build_layout())