from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Static, Markdown
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual import work
from rich.text import Text
import webbrowser
from datetime import datetime

from .core import CoreEngine
from .models import Article

class SourcesScreen(Screen):
    BINDINGS = [
        Binding("q", "app.quit", "Quit"),
        Binding("f", "fetch_all", "Fetch All"),
        Binding("enter", "select_source", "Select Source"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Source", "Type", "Hubs/Topics")
        self.load_sources()

    def load_sources(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        config = self.app.engine.config.get('sources', {})
        for name, data in config.items():
            hubs = ", ".join(data.get('hubs', []))
            table.add_row(name, data.get('type'), hubs, key=name)

    def action_fetch_all(self) -> None:
        self.app.push_screen(FetchScreen())

    def action_select_source(self) -> None:
        table = self.query_one(DataTable)
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key:
            self.app.push_screen(TopicsScreen(source_name=row_key.value))

class TopicsScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("f", "fetch_source", "Fetch Source"),
        Binding("enter", "select_topic", "Select Topic"),
    ]

    def __init__(self, source_name: str):
        super().__init__()
        self.source_name = source_name

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"Source: {self.source_name}", id="source_header")
        yield DataTable(cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Topic", "Last Update")
        self.load_topics()

    def load_topics(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        source_config = self.app.engine.config.get('sources', {}).get(self.source_name, {})
        hubs = source_config.get('hubs', [])
        
        for hub in hubs:
            # TODO: Get real last update date
            table.add_row(hub, "N/A", key=hub)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_fetch_source(self) -> None:
        self.app.push_screen(FetchScreen(source_name=self.source_name))

    def action_select_topic(self) -> None:
        table = self.query_one(DataTable)
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key:
            self.app.push_screen(ArticlesScreen(source_name=self.source_name, topic=row_key.value))

class ArticlesScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("enter", "view_article", "View Article"),
        Binding("o", "open_browser", "Open in Browser"),
        Binding("i", "toggle_interesting", "Interesting"),
        Binding("d", "mark_read", "Mark Read"),
    ]

    def __init__(self, source_name: str, topic: str):
        super().__init__()
        self.source_name = source_name
        self.topic = topic
        self.articles = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"Source: {self.source_name} > Topic: {self.topic}", id="topic_header")
        yield DataTable(cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("ID", "Date", "Title", "Rating", "Views", "Comments")
        self.load_articles()

    def load_articles(self) -> None:
        # TODO: Filter by topic/hub in storage (currently not implemented in storage, filtering in memory for MVP)
        # We need to fetch all articles for source and filter by tag/hub
        all_articles = self.app.engine.get_articles(read=False, source=self.source_name)
        
        # Filter by topic (hub)
        # Assuming tag matches topic for now
        self.articles = [a for a in all_articles if self.topic in a.extra_data.get('tags', [])]
        
        table = self.query_one(DataTable)
        table.clear()
        
        for article in self.articles:
            rating = str(article.extra_data.get('rating', ''))
            views = str(article.extra_data.get('views', ''))
            comments = str(article.extra_data.get('comments', ''))
            
            table.add_row(
                str(article.id),
                article.published_date.strftime("%Y-%m-%d"),
                article.title,
                rating,
                views,
                comments,
                key=str(article.id)
            )

    def get_selected_article(self):
        table = self.query_one(DataTable)
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key:
            article_id = int(row_key.value)
            return next((a for a in self.articles if a.id == article_id), None)
        return None

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_view_article(self) -> None:
        article = self.get_selected_article()
        if article:
            self.app.push_screen(ArticleViewScreen(article))

    def action_open_browser(self) -> None:
        article = self.get_selected_article()
        if article:
            webbrowser.open(article.link)
            self.app.engine.update_article_status(article.id, read=True)
            self.load_articles() # Refresh list

    def action_toggle_interesting(self) -> None:
        article = self.get_selected_article()
        if article:
            new_status = not article.status_interesting
            self.app.engine.update_article_status(article.id, interesting=new_status)
            self.app.notify(f"Marked as {'Interesting' if new_status else 'Not Interesting'}")

    def action_mark_read(self) -> None:
        article = self.get_selected_article()
        if article:
            self.app.engine.update_article_status(article.id, read=True)
            self.load_articles() # Refresh list

class ArticleViewScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("o", "open_browser", "Open in Browser"),
    ]

    def __init__(self, article: Article):
        super().__init__()
        self.article = article

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(f"# {self.article.title}", classes="title"),
            Static(f"Link: {self.article.link}", classes="link"),
            Markdown(self.article.content_md or "*No content available*"),
            id="article_container"
        )
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_open_browser(self) -> None:
        webbrowser.open(self.article.link)

class FetchScreen(Screen):
    def __init__(self, source_name: str = None):
        super().__init__()
        self.source_name = source_name

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Fetching articles... Please wait.", id="loading_message")
        yield Footer()

    def on_mount(self) -> None:
        self.run_fetch()

    @work(exclusive=True, thread=True)
    def run_fetch(self) -> None:
        self.app.engine.run_fetch(source_name=self.source_name)
        self.app.call_from_thread(self.app.pop_screen)
        self.app.call_from_thread(self.app.notify, "Fetch complete!")
        # Refresh current screen if it's Sources or Topics
        # This is a bit tricky, ideally we should use messages to notify screens to refresh

class InforadarApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    DataTable {
        height: 1fr;
    }
    #article_container {
        height: 1fr;
        overflow-y: scroll;
        padding: 1;
    }
    .title {
        text-style: bold;
        padding-bottom: 1;
    }
    .link {
        color: blue;
        padding-bottom: 1;
    }
    """

    BINDINGS = [
        ("p", "command_palette", "Палитра команд"),
    ]

    def __init__(self):
        super().__init__()
        self.engine = CoreEngine()

    def on_mount(self) -> None:
        self.push_screen(SourcesScreen())

if __name__ == "__main__":
    app = InforadarApp()
    app.run()
