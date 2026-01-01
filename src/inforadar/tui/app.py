import sys
import signal
import termios
import tty
from typing import List, Optional

from rich.console import Console
from rich.control import Control

from inforadar.core import CoreEngine
from inforadar.tui.input import get_key, handle_winch, ResizeScreen
from inforadar.tui.screens.base import BaseScreen


class AppState:
    def __init__(self):
        self.engine = CoreEngine()
        self.console = Console()
        self.running = True
        self.screen_stack: List["BaseScreen"] = []
        self.screen_states = {}

    def push_screen(self, screen: "BaseScreen"):
        self.screen_stack.append(screen)

    def pop_screen(self):
        if self.screen_stack:
            screen_to_pop = self.screen_stack[-1]
            if hasattr(screen_to_pop, "on_leave"):
                screen_to_pop.on_leave()
            self.screen_stack.pop()
        if not self.screen_stack:
            self.running = False

    @property
    def current_screen(self) -> Optional["BaseScreen"]:
        return self.screen_stack[-1] if self.screen_stack else None

    def run(self):
        from inforadar.tui.screens.articles_view import ArticlesViewScreen

        # Initial screen: ArticlesViewScreen
        self.push_screen(ArticlesViewScreen(self))

        # Register resize handler
        old_handler = signal.signal(signal.SIGWINCH, handle_winch)

        # Save terminal settings
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setcbreak(fd)
            with self.console.screen():
                self.console.show_cursor(False)
                should_render = True
                while self.running and self.current_screen:
                    if should_render:
                        manages_own_screen = (
                            hasattr(self.current_screen, "manages_own_screen")
                            and self.current_screen.manages_own_screen
                        )

                        if not manages_own_screen:
                            # Use home() only in command mode dealing with typing to prevent flickering.
                            # Otherwise use clear() to ensure no artifacts (e.g. when changing pages).
                            use_clear = True
                            if (
                                hasattr(self.current_screen, "command_mode")
                                and self.current_screen.command_mode
                            ):
                                use_clear = False
                            elif (
                                hasattr(self.current_screen, "active_mode")
                                and self.current_screen.active_mode
                            ):
                                use_clear = False

                            if use_clear:
                                self.console.clear()
                            else:
                                self.console.control(Control.home())

                        self.current_screen.render()
                        self.console.show_cursor(False)
                        should_render = False

                    try:
                        key = get_key()
                        if key is None:
                            # Timeout - check if screen needs refresh (for animations)
                            if (
                                hasattr(self.current_screen, "needs_refresh")
                                and self.current_screen.needs_refresh()
                            ):
                                should_render = True
                        elif self.current_screen:
                            should_render = self.current_screen.handle_input(key)
                    except ResizeScreen:
                        should_render = True
                        if hasattr(self.current_screen, "on_resize"):
                            self.current_screen.on_resize()
        except KeyboardInterrupt:
            pass  # Handle Ctrl+C gracefully
        finally:
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            # Restore signal handler
            signal.signal(signal.SIGWINCH, old_handler)
