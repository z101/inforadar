from .storage import Storage
from .config import load_config
from .providers.habr import HabrProvider
from .models import Article
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import time
import random

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

        print(f"Found {len(new_articles)} articles. Saving to database...")
        result = self.storage.add_or_update_articles(new_articles)
        print(f"Added {result['added']} new articles, updated {result['updated']} existing articles.")

    def get_articles(self, read: bool = False, interesting: Optional[bool] = None) -> List[Article]:
        """Retrieves articles from storage based on status."""
        return self.storage.get_articles(read=read, interesting=interesting)

    def update_article_status(self, article_id: int, read: Optional[bool] = None, interesting: Optional[bool] = None):
        """Updates the status of an article in storage."""
        self.storage.update_article_status(article_id, read=read, interesting=interesting)

    def run_refresh(self, days: int = 7, unread_only: bool = True):
        """Refreshes metadata for existing articles."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        articles = self.storage.get_articles_for_refresh(
            after_date=cutoff_date,
            read=False if unread_only else None
        )
        
        if not articles:
            print("No articles to refresh.")
            return
        
        print(f"Refreshing metadata for {len(articles)} articles...")
        habr_provider = HabrProvider(config=self.config, storage=self.storage)
        updated_count = 0
        
        for i, article in enumerate(articles, 1):
            print(f"  [{i}/{len(articles)}] {article.title[:50]}...")
            time.sleep(random.uniform(0.1, 0.5))  # Be nice to the server
            extra_data = habr_provider._enrich_article_data(article.link)
            if self.storage.update_article_metadata(article.id, extra_data):
                updated_count += 1
        
        print(f"Successfully refreshed metadata for {updated_count} articles.")