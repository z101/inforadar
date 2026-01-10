import sys
import signal
import termios
import tty
from typing import List, Optional, Any

from rich.console import Console
from rich.control import Control

from inforadar.core import CoreEngine
from inforadar.tui.input import get_key, handle_winch, ResizeScreen
from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.screens.articles_view import ArticlesViewScreen


class AppState:
    def __init__(self):
        self.engine = CoreEngine()
        self.console = Console()
        self.running = True
        self.screen_stack: List["BaseScreen"] = []
        self.screen_states = {}

    def push_screen(self, screen: "BaseScreen"):
        if self.current_screen and hasattr(self.current_screen, "on_leave"):
            self.current_screen.on_leave()
        self.screen_stack.append(screen)

    def pop_screen(self, on_after_pop=None):
        if self.screen_stack:
            screen_to_pop = self.screen_stack[-1]
            if hasattr(screen_to_pop, "on_leave"):
                screen_to_pop.on_leave()
            self.screen_stack.pop()
            if on_after_pop:
                on_after_pop()
        if not self.screen_stack:
            self.running = False

    @property
    def current_screen(self) -> Optional["BaseScreen"]:
        return self.screen_stack[-1] if self.screen_stack else None

    def run(self):
        # Initial screen: ArticlesViewScreen
        self.push_screen(ArticlesViewScreen(self))

        # Register resize handler
        old_handler = signal.signal(signal.SIGWINCH, handle_winch)

        # Save terminal settings
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            try:
                tty.setcbreak(fd)
            except termios.error as e:
                print(f"ERROR: Failed to set terminal to cbreak mode. This is often due to running in a non-interactive terminal or an unsupported environment. Original error: {e}", file=sys.stderr)
                self.running = False # Set running to False to exit gracefully
                return # Exit the run method immediately if termios fails
            except Exception as e:
                print(f"ERROR: An unexpected error occurred while setting cbreak mode: {e}", file=sys.stderr)
                self.running = False
                return
            
            self.console.show_cursor(False)
            should_render = True
            while self.running and self.current_screen:
                if should_render:
                    manages_own_screen = (
                        hasattr(self.current_screen, "manages_own_screen")
                        and self.current_screen.manages_own_screen
                    )

                    if not manages_own_screen:
                        # By default, clear the screen to prevent artifacts
                        use_clear = True
                        
                        # But for text input or simple cursor movement,
                        # just move to home to prevent flickering
                        is_input_mode = hasattr(self.current_screen, 'is_text_input_mode') and self.current_screen.is_text_input_mode
                        is_active_mode = hasattr(self.current_screen, 'active_mode') and self.current_screen.active_mode
                        if is_input_mode or is_active_mode:
                            use_clear = False
                        
                        # However, always force a clear if the screen explicitly requests it
                        if hasattr(self.current_screen, "need_clear") and self.current_screen.need_clear:
                            use_clear = True
                            self.current_screen.need_clear = False

                        if use_clear:
                            self.console.clear()
                        else:
                            self.console.control(Control.home())

                    self.current_screen.render()
                    self.console.show_cursor(False)
                    should_render = False

                try:
                    raw_mode = False
                    if hasattr(self.current_screen, "is_text_input_mode"):
                        raw_mode = self.current_screen.is_text_input_mode
                    
                    key = get_key(raw=raw_mode)

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
            self.console.show_cursor(True)
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            # Restore signal handler
            signal.signal(signal.SIGWINCH, old_handler)