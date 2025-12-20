import threading
import time
from datetime import datetime
from typing import List, TYPE_CHECKING, Any

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
from inforadar.tui.keys import Key

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


RESERVED_LINES_FOR_UI = (
    9  # Header (1), empty line (1), progress bar (1), footer (4), panel borders (2)
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
        self,
        app: "AppState",
        parent: Any,
        selected_sources: set = None,
        selected_topics: set = None,
    ):
        super().__init__(app)
        self.parent = parent
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

        self.state = "init"  # "init", "running", "done"
        self.log_scroll_offset = 0
        self.live: Optional[Live] = None
        self.manages_own_screen = True
        self.needs_final_render = False

        # --- New Feature State ---
        # Search state
        self.search_mode = "inactive"  # inactive, input, navigating
        self.search_term = ""
        self.search_matches: List[int] = []
        self.current_match_index = 0

        # Navigation state
        self.auto_scroll_enabled = True
        self.pending_g = False
        # -------------------------

    def on_leave(self) -> None:
        """Cleanly stops the Live object when the screen is popped."""
        if self.live:
            self.live.stop()
            self.live = None

    def on_resize(self):
        if self.live:
            self.live.stop()
            self.live = None

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
                is_at_bottom = self.log_scroll_offset == 0
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.logs.append(f"[grey50][{timestamp}][/grey50] {msg}")

                if self.auto_scroll_enabled and is_at_bottom:
                    # Stay at the bottom, do nothing to the offset
                    pass
                else:
                    # Freeze the view by incrementing offset to account for the new log
                    self.log_scroll_offset += 1

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

                time.sleep(0.5)

                num_found = 5
                total_articles_found += num_found
                log_cb(f"Found {num_found} article links in {topic}")

                self.progress.advance(self.main_task_id)

            if self.cancel_event.is_set():
                return

            # On success, refresh the parent screen's data
            if hasattr(self.parent, "refresh_data"):
                self.parent.refresh_data()

        except Exception as e:
            with self.lock:
                log_cb(f"[red]Error: {str(e)}[/red]")
        finally:
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                if self.cancel_event.is_set():
                    self.logs.append(
                        f"[grey50][{timestamp}][/grey50] [yellow]Fetch cancelled by user.[/yellow]"
                    )
                elif "total_articles_found" in locals():
                    self.logs.append(
                        f"[grey50][{timestamp}][/grey50] [green]Stage 1 finished. Found a total of {total_articles_found} articles to read.[/green]"
                    )
                self._reset_to_init_state()
                self.needs_final_render = True

    def _jump_to_match(self, match_index: int):
        """Calculates log_scroll_offset to show the given line index."""
        console_height = self.app.console.height
        log_lines_to_show = (
            console_height - RESERVED_LINES_FOR_UI
            if console_height > RESERVED_LINES_FOR_UI
            else 1
        )
        # Aim to place the matched line in the top third of the panel
        target_pos_in_view = log_lines_to_show // 3

        # This is the line index (from the top of all logs) that should be at the top of the panel
        target_top_line = max(0, match_index - target_pos_in_view)

        # The offset is how many lines are hidden from the bottom.
        # If we show from target_top_line, it means there are target_top_line lines hidden above.
        # Total lines hidden = len(logs) - visible_lines.
        # total lines hidden above + total lines hidden below = total lines - visible_lines
        # We need to find the offset that makes target_top_line the start_index
        # start_index = max(0, (len(self.logs) - self.log_scroll_offset) - log_lines_to_show)
        # We want target_top_line = max(0, (len(self.logs) - offset) - log_lines_to_show)
        # offset = len(self.logs) - log_lines_to_show - target_top_line
        self.log_scroll_offset = max(
            0, len(self.logs) - target_top_line - log_lines_to_show
        )

    def start_fetch(self):
        if self.state == "init":
            self.state = "running"
            self.cancel_event = threading.Event()
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.logs.append(
                    f"[grey50][{timestamp}][/grey50] [cyan]Starting fetch...[/cyan]"
                )
            self.worker_thread = threading.Thread(target=self.work, daemon=True)
            self.worker_thread.start()

    def cancel_fetch(self):
        if self.state == "running":
            self.state = "done"  # Move to done state
            self.cancel_event.set()
            with self.lock:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.logs.append(
                    f"[grey50][{timestamp}][/grey50] [yellow]Cancelling...[/yellow]"
                )

    def needs_refresh(self) -> bool:
        """Indicates to the main app loop if this screen needs frequent updates."""
        return self.state == "running" or self.needs_final_render

    def handle_input(self, key: str) -> bool:
        """Handles user input for the fetch screen."""
        should_render = False

        if self.search_mode == "input":
            if key == Key.ESCAPE:
                self.search_mode = "inactive"
                self.search_term = ""
            elif key == Key.ENTER:
                if self.search_term:
                    with self.lock:
                        self.search_matches = [
                            i
                            for i, log_line in enumerate(self.logs)
                            if self.search_term.lower() in log_line.lower()
                        ]
                    if self.search_matches:
                        self.current_match_index = 0
                        self._jump_to_match(self.search_matches[0])
                    self.search_mode = "navigating"
                else:
                    self.search_mode = "inactive"
            elif key in (Key.BACKSPACE, Key.CTRL_H):
                self.search_term = self.search_term[:-1]
            elif len(key) == 1 and key.isprintable():
                self.search_term += key
            return True

        elif self.search_mode == "navigating":
            if key == "n":  # Next match
                if self.search_matches:
                    self.current_match_index = (self.current_match_index + 1) % len(
                        self.search_matches
                    )
                    self._jump_to_match(self.search_matches[self.current_match_index])
                    return True
            elif key == "N":  # Previous match
                if self.search_matches:
                    self.current_match_index = (self.current_match_index - 1) % len(
                        self.search_matches
                    )
                    self._jump_to_match(self.search_matches[self.current_match_index])
                    return True

        if self.pending_g and key == "g":
            with self.lock:
                console_height = self.app.console.height
                log_lines_to_show = (
                    console_height - RESERVED_LINES_FOR_UI
                    if console_height > RESERVED_LINES_FOR_UI
                    else 1
                )
                self.log_scroll_offset = max(0, len(self.logs) - log_lines_to_show)
            self.pending_g = False
            return True

        if key != "g":
            self.pending_g = False

        if key in (Key.Q, Key.ESCAPE):
            if self.search_mode != "inactive":
                self.search_mode = "inactive"
                self.search_term = ""
            elif self.state == "running":
                self.cancel_fetch()
            else:
                self.app.pop_screen()
            should_render = True
        elif key == Key.S and self.state == "init":
            self.start_fetch()
            should_render = True
        elif key == "c" and self.state == "init":
            with self.lock:
                self.logs.clear()
                self.log_scroll_offset = 0
            should_render = True
        elif key == "a":
            self.auto_scroll_enabled = not self.auto_scroll_enabled
            should_render = True
        elif key == "/":
            self.search_mode = "input"
            self.search_term = ""
            self.search_matches = []
            should_render = True
        elif key in (Key.K, "h"):  # Scroll up
            with self.lock:
                console_height = self.app.console.height
                log_lines_to_show = (
                    console_height - RESERVED_LINES_FOR_UI
                    if console_height > RESERVED_LINES_FOR_UI
                    else 1
                )
                max_scroll_offset = max(0, len(self.logs) - log_lines_to_show)

                if key == "h":  # Page up
                    self.log_scroll_offset = min(
                        max_scroll_offset, self.log_scroll_offset + log_lines_to_show
                    )
                else:  # Line up
                    if self.log_scroll_offset < max_scroll_offset:
                        self.log_scroll_offset += 1
                should_render = True
        elif key in (Key.J, "l"):  # Scroll down
            with self.lock:
                console_height = self.app.console.height
                log_lines_to_show = (
                    console_height - RESERVED_LINES_FOR_UI
                    if console_height > RESERVED_LINES_FOR_UI
                    else 1
                )
                if key == "l":  # Page down
                    self.log_scroll_offset = max(
                        0, self.log_scroll_offset - log_lines_to_show
                    )
                else:  # Line down
                    if self.log_scroll_offset > 0:
                        self.log_scroll_offset -= 1
                should_render = True
        elif key == Key.SHIFT_G:
            with self.lock:
                if self.log_scroll_offset > 0:
                    self.log_scroll_offset = 0
                    should_render = True
        elif key == "g":
            self.pending_g = True
            return False

        return should_render

    def _build_header_text(self, log_lines_to_show: int) -> str:
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

        # --- Auto-Scroll and Scroll indicators ---
        auto_scroll_status = "ON" if self.auto_scroll_enabled else "OFF"
        parts.append(
            f"[dim]Auto-Scroll[/dim] [bold white]{auto_scroll_status}[/bold white]"
        )

        total_logs = len(self.logs)
        if total_logs > log_lines_to_show:
            max_scroll_offset = max(0, total_logs - log_lines_to_show)
            scroll_percent_str = ""
            if self.log_scroll_offset == 0:
                scroll_percent_str = "100%"  # Bottom
            elif self.log_scroll_offset == max_scroll_offset:
                scroll_percent_str = "0%"  # Top
            else:
                scroll_percent = (
                    (max_scroll_offset - self.log_scroll_offset) / max_scroll_offset
                ) * 100
                scroll_percent_str = f"{scroll_percent:.0f}%"
            parts.append(
                f"[dim]Scroll[/dim] [bold white]{scroll_percent_str}[/bold white]"
            )
        # ----------------------------------------

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
        """Assembles the renderable layout for the screen."""
        console_height = self.app.console.height
        log_lines_to_show = (
            console_height - RESERVED_LINES_FOR_UI
            if console_height > RESERVED_LINES_FOR_UI
            else 1
        )

        header = self._build_header_text(log_lines_to_show)

        with self.lock:
            end_index = len(self.logs) - self.log_scroll_offset
            start_index = max(0, end_index - log_lines_to_show)
            visible_logs = self.logs[start_index:end_index]

            # --- Log content with line numbers and highlighting ---
            text_lines = []
            max_line_num_width = len(str(len(self.logs)))
            for i, line_content_str in enumerate(visible_logs):
                actual_line_num = start_index + i + 1

                # Create a Text object for the line number part
                line_num_styled_text = Text(
                    f"{actual_line_num:>{max_line_num_width}}  ", style="grey50"
                )

                # Create a Text object for the log content, preserving its markup
                log_content_styled_text = Text.from_markup(
                    line_content_str, style="white"
                )  # Explicitly set white

                # Apply search highlighting if needed
                if self.search_mode == "navigating" and self.search_term:
                    log_content_styled_text.highlight_words(
                        [self.search_term], style="black on yellow"
                    )

                combined_line = line_num_styled_text + log_content_styled_text
                text_lines.append(combined_line)

            log_content = Text("\n").join(text_lines)
            # ------------------------------------

        logs_panel = Panel(
            log_content,
            title="Logs",
            border_style="green",
            height=log_lines_to_show + 2,
            expand=True,
        )

        # --- Footer Logic ---
        if self.search_mode == "input":
            footer_text = f"Search: {self.search_term}"
            footer = Text.from_markup(footer_text, justify="left")
            footer.append(" ", style="reverse")
        elif self.search_mode == "navigating":
            if self.search_matches:
                match_count = len(self.search_matches)
                footer_text = f"Found {match_count} matches for '[bold white]{self.search_term}[/bold white]' | Match {self.current_match_index + 1}/{match_count} | [[bold white]n[/bold white]] Next [[bold white]N[/bold white]] Prev [[bold white]Esc[/bold white]] Exit Search"
            else:
                footer_text = f"No matches found for '[bold white]{self.search_term}[/bold white]' | [[bold white]Esc[/bold white]] Exit Search"

            footer = Text.from_markup(footer_text, style="dim", justify="center")
        else:
            footer_text = ""
            if self.state == "init":
                footer_text = "[[bold white]s[/bold white]] Start [[bold white]c[/bold white]] Clear [[bold white]/[/bold white]] Search [[bold white]Esc, q[/bold white]] Back"
            elif self.state == "running":
                footer_text = "[[bold white]/[/bold white]] Search [[bold white]Esc, q[/bold white]] Cancel"
            elif self.state == "done":
                footer_text = "[[bold white]Esc, q[/bold white]] Back"  # Just a simple back command

            footer = Text.from_markup(footer_text, style="dim", justify="center")
        # --------------------

        return Group(
            Text.from_markup(header, justify="center"),
            "",
            self.progress,
            logs_panel,
            "",
            footer,
        )

    def render(self) -> None:
        """Manages the Live object for rendering."""
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
