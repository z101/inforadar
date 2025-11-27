from .storage import Storage
from .config import load_config
from .providers.habr import HabrProvider
from .models import Article
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import time
import random
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, MofNCompleteColumn

class CoreEngine:
    """Orchestrates the entire data fetching and storing process."""

    def __init__(self, config_path: str = "config.yml"):
        self.config = load_config(config_path)
        self.storage = Storage() # Uses default DB path
        self.storage.init_db() # Ensure DB is created

    def run_fetch(self, source_name: Optional[str] = None):
        """Runs the fetch process for configured sources."""
        sources = self.config.get('sources', {})
        
        # Filter sources if specific one requested
        if source_name:
            if source_name not in sources:
                print(f"Source '{source_name}' not found in configuration.")
                return
            sources = {source_name: sources[source_name]}

        total_added = 0
        total_updated = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
        ) as progress:
            
            for name, config in sources.items():
                if config.get('type') == 'habr':
                    provider = HabrProvider(name, config, self.storage)
                    
                    task_id = progress.add_task(f"Fetching {name}...", total=None)

                    def update_progress(description: str, current: int, total: Optional[int]):
                        progress.update(task_id, description=f"[{name}] {description}", completed=current, total=total)

                    new_articles = provider.fetch(on_progress=update_progress)
                    
                    if new_articles:
                        result = self.storage.add_or_update_articles(new_articles)
                        total_added += result['added']
                        total_updated += result['updated']
                    
                    progress.remove_task(task_id)

        print(f"Fetch complete. Added {total_added} new, updated {total_updated} existing.")

    def get_articles(self, read: bool = False, interesting: Optional[bool] = None, source: Optional[str] = None) -> List[Article]:
        """Retrieves articles from storage based on status."""
        return self.storage.get_articles(read=read, interesting=interesting, source=source)

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
        updated_count = 0
        
        # Cache providers
        providers = {}

        for i, article in enumerate(articles, 1):
            print(f"  [{i}/{len(articles)}] {article.title[:50]}...")
            
            if not article.source:
                continue

            if article.source not in providers:
                source_config = self.config.get('sources', {}).get(article.source)
                if source_config and source_config.get('type') == 'habr':
                    providers[article.source] = HabrProvider(article.source, source_config, self.storage)
                else:
                    providers[article.source] = None
            
            provider = providers[article.source]
            if not provider:
                continue

            time.sleep(random.uniform(0.1, 0.5))  # Be nice to the server
            extra_data = provider._enrich_article_data(article.link)
            if self.storage.update_article_metadata(article.id, extra_data):
                updated_count += 1
        
        print(f"Successfully refreshed metadata for {updated_count} articles.")