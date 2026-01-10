import time
import threading # Import threading

from rich.spinner import Spinner
from rich.text import Text
from rich.align import Align

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.screens.articles_view import ArticlesViewScreen

class SplashScreen(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self.spinner = Spinner("dots", text="Loading Info Radar...", style="green")
        self.loading_complete = False
        self.articles_screen = None # To hold the loaded articles screen instance

    @property
    def manages_own_screen(self) -> bool:
        return True

    def render(self):
        console = self.app.console
        # No explicit console.clear() here. AppState.run()'s loop should handle it for manages_own_screen.
        # But if the current_screen.render() is the only thing drawing, it needs to clear.
        # However, for a manages_own_screen=True screen, the screen() context handles clearing between renders.
        
        self.spinner.update()
        
        content = Align.center(
            self.spinner,
            vertical="middle",
            height=console.size.height,
        )
        console.print(content)

    def handle_input(self, key: str) -> bool:
        # Ignore input while loading, unless it's a critical exit key like Ctrl+C
        # For now, just ignore all input
        return False

    def _load_data_thread(self):
        self.app.console.log("[Splash] Loading data in background thread started.")
        
        # Instantiate the ArticlesViewScreen and load its data
        loaded_articles_screen = ArticlesViewScreen(self.app)
        self.app.console.log("[Splash] ArticlesViewScreen instantiated.")
        loaded_articles_screen.refresh_data() # This is the main loading operation
        self.app.console.log("[Splash] ArticlesViewScreen.refresh_data() called.")
        
        self.articles_screen = loaded_articles_screen # Store the loaded screen
        self.app.console.log("[Splash] articles_screen assigned.")
        self.loading_complete = True # Signal completion
        self.app.console.log("[Splash] loading_complete set to True. Thread finishing.")
        
        # Request a redraw of the app, which will then check loading_complete
        # A simple way to trigger a check for screen transition is to return True from handle_input
        # but since handle_input ignores, we might need a different mechanism in app.run() or
        # rely on the continuous needs_refresh() and the app loop's check.

    def on_mount(self):
        self.app.console.log("[Splash] SplashScreen mounted, starting loading thread...")
        # Start the loading process in a new thread
        loading_thread = threading.Thread(target=self._load_data_thread, daemon=True)
        loading_thread.start()

    def needs_refresh(self) -> bool:
        # Only indicate if the spinner needs continuous animation.
        # Transition logic will be handled in app.py
        return not self.loading_complete

