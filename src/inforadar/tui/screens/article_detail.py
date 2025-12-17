from typing import TYPE_CHECKING

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.keys import Key
from inforadar.models import Article

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class ArticleDetailScreen(BaseScreen):
    def __init__(self, app: "AppState", article: Article):
        super().__init__(app)
        self.article = article
        self.scroll_offset = 0
        self.total_lines = 0
        self.visible_height = 0

    def render(self):
        console = self.app.console
        width, height = console.size

        # Header
        header = Panel(
            Text(
                f"Article: {self.article.title}", justify="center", style="bold white"
            ),
            style="blue",
        )
        console.print(header)

        # Content
        content_height = height - 6

        md_content = self.article.content_md or "*No content available*"

        with console.capture() as capture:
            console.print(Markdown(md_content))
        full_text = capture.get()
        lines = full_text.splitlines()
        self.total_lines = len(lines)
        self.visible_height = content_height

        # Slice lines
        visible_lines = lines[self.scroll_offset : self.scroll_offset + content_height]

        for line in visible_lines:
            console.print(line)

        # Fill empty space
        for _ in range(content_height - len(visible_lines)):
            console.print("")

        # Footer
        footer_text = f"Lines {self.scroll_offset}-{self.scroll_offset+len(visible_lines)}/{len(lines)} | [Esc]Back [Up/Down]Scroll"
        console.print(Panel(footer_text, style="grey50"))

        # Mark as read
        if not self.article.status_read:
            self.article.status_read = True
            self.app.engine.update_article_status(self.article.id, read=True)

    def handle_input(self, key: str) -> bool:
        if key == Key.UP or key == Key.K:
            self.scroll_offset = max(0, self.scroll_offset - 1)
            return True
        elif key == Key.DOWN or key == Key.J:
            self.scroll_offset = min(
                self.total_lines - self.visible_height, self.scroll_offset + 1
            )
            return True
        elif key == Key.CTRL_D:
            self.scroll_offset = min(
                self.total_lines - self.visible_height,
                self.scroll_offset + self.visible_height,
            )
            return True
        elif key == Key.CTRL_U:
            self.scroll_offset = max(0, self.scroll_offset - self.visible_height)
            return True
        else:
            return super().handle_input(key)
