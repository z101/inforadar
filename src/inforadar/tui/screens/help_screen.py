from typing import List, Tuple
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.keys import Key


class HelpScreen(BaseScreen):
    """A screen that displays scrollable help information using rich.live."""

    def __init__(self, app: "AppState", title: str = "Help"):
        super().__init__(app)
        self.scroll_offset = 0
        self.total_lines = 0
        self.all_help_lines = []
        self.title = title
        self._format_and_set_content()
        
        self._live_started = False
        self.live = Live(
            None,
            console=self.app.console,
            screen=False,
            auto_refresh=False,
            transient=True,
            vertical_overflow="visible"
        )

    def _mount(self):
        """Starts the live display if not already running."""
        if not self._live_started:
            # Clear the screen before starting the live view
            self.app.console.clear()
            self.live.start(refresh=False)
            self._live_started = True
            self.live.update(self._generate_renderable(), refresh=True)

    def on_leave(self):
        """Stops the live display."""
        if self._live_started:
            self.live.stop()
        self._live_started = False
        # Request a clear from the app loop to clean up after the transient live view
        self.need_clear = True
        super().on_leave() if hasattr(super(), 'on_leave') else None

    def render(self):
        """The render method is now only responsible for ensuring the Live view is active."""
        self._mount()
        self.live.update(self._generate_renderable(), refresh=True)

    def on_resize(self):
        """Handles terminal resize events by re-rendering the screen."""
        self.render()
        
    def _get_help_content(self) -> List[Tuple[str, List[Tuple[str, str]]]]:
        """
        Subclasses should override this to return their help content.
        Format: [("Section Title", [("key", "description"), ...]), ...]
        """
        return []

    def _format_and_set_content(self):
        """Formats the structured help content into aligned text lines."""
        help_sections = self._get_help_content()
        all_lines = []

        # Calculate the maximum key width across all sections for consistent alignment
        all_bindings = [binding for _, bindings in help_sections for binding in bindings]
        max_key_width = max(len(key) for key, desc in all_bindings) if all_bindings else 0

        for i, (section_title, bindings) in enumerate(help_sections):
            # Add a separator line before sections, but not the first one.
            if i > 0:
                all_lines.append(Text(""))

            if section_title:
                all_lines.append(Text.from_markup(f"[dim green]{section_title}[/dim green]"))
                all_lines.append(Text(""))  # Newline after title

            for key, desc in bindings:
                padded_key = key.ljust(max_key_width)
                line = Text.from_markup(f"  [green]{padded_key}[/green]   - {desc}")
                all_lines.append(line)

        if all_lines:
            self.all_help_lines = Text("\n").join(all_lines).split('\n')
        else:
            self.all_help_lines = []

        self.total_lines = len(self.all_help_lines)

    def _generate_renderable(self) -> Panel:
        """Builds the Panel renderable for the live view."""
        _, height = self.app.console.size

        reserved_lines = 4
        visible_height = height - reserved_lines
        if visible_height < 1:
            visible_height = 1

        max_scroll_offset = max(0, self.total_lines - visible_height)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll_offset))

        display_lines = self.all_help_lines[self.scroll_offset : self.scroll_offset + visible_height]
        content_to_render = Text("\n").join(display_lines)

        # Scroll indicator logic
        scroll_indicator_text = ""
        if self.total_lines > visible_height:
            # Content is scrollable, so show the indicator
            if self.scroll_offset == 0:
                scroll_indicator_text = "Top"
            elif self.scroll_offset >= max_scroll_offset:
                scroll_indicator_text = "Bottom"
            else:
                if max_scroll_offset > 0:
                    percentage = (self.scroll_offset / max_scroll_offset) * 100
                    scroll_indicator_text = f"{int(percentage)}%"

        # Format the final title
        title_text = f"[dim green bold]Info Radar Help[/dim green bold] | {self.title}"
        if scroll_indicator_text:
            title_text += f" | [bold yellow]{scroll_indicator_text}[/bold yellow]"

        return Panel(
            content_to_render,
            title=title_text,
            border_style="dim",
            expand=True,
        )

    def handle_input(self, key: str) -> bool:
        """Handles key presses and updates the live view."""
        self._mount()
        redraw = False

        if key == Key.K or key == Key.UP:
            if self.scroll_offset > 0:
                self.scroll_offset -= 1
                redraw = True
        elif key == Key.J or key == Key.DOWN:
            _, height = self.app.console.size
            reserved_lines = 4
            visible_height = height - reserved_lines
            max_scroll_offset = max(0, self.total_lines - visible_height)
            if self.scroll_offset < max_scroll_offset:
                self.scroll_offset += 1
                redraw = True
        elif key in (Key.Q, Key.ESCAPE, Key.QUESTION):
            self.on_leave()
            self.app.pop_screen()
            return True # Let the underlying screen redraw itself completely

        if redraw:
            self.live.update(self._generate_renderable(), refresh=True)
            return False # We handled the redraw

        return False # No state change
