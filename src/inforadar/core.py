from .storage import Storage
from .config import load_config
from .providers.habr import HabrProvider
from .models import Article
from typing import List, Optional

class CoreEngine:
    """Orchestrates the entire data fetching and storing process."""

    def __init__(self, config_path: str = "config.yml"):
        self.config = load_config(config_path)
        self.storage = Storage() # Uses default DB path
        self.storage.init_db() # Ensure DB is created

    def run_fetch(self):
        """Runs the fetch process for all configured providers."""
        # For now, we only have one provider
        habr_provider = HabrProvider(config=self.config, storage=self.storage)
        
        print("Fetching articles from Habr...")
        new_articles = habr_provider.fetch()
        
        if not new_articles:
            print("No new articles found.")
            return

        print(f"Found {len(new_articles)} new articles. Saving to database...")
        added_count = self.storage.add_articles(new_articles)
        print(f"Successfully saved {added_count} articles.")

    def get_articles(self, read: bool = False, interesting: Optional[bool] = None) -> List[Article]:
        """Retrieves articles from storage based on status."""
        return self.storage.get_articles(read=read, interesting=interesting)

    def update_article_status(self, article_id: int, read: Optional[bool] = None, interesting: Optional[bool] = None):
        """Updates the status of an article in storage."""
        self.storage.update_article_status(article_id, read=read, interesting=interesting)