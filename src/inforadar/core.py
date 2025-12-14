from .storage import Storage
from .config import load_config
from .providers.habr import HabrProvider
from .models import Article
from typing import List, Optional, Callable, Any
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

    def run_sync(self, source_names: Optional[List[str]] = None, progress: Optional[Progress] = None, log_callback: Optional[Callable[[str], None]] = None, cancel_event: Optional[Any] = None):
        """Runs the sync process for configured sources."""
        sources = self.config.get('sources', {})
        
        # Filter sources if specific ones requested
        if source_names:
            sources = {name: sources[name] for name in source_names if name in sources}

        total_added = 0
        total_updated = 0

        from contextlib import nullcontext
        
        if progress is None:
            progress_ctx = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeRemainingColumn(),
            )
        else:
            progress_ctx = nullcontext(progress)

        with progress_ctx as p:
            
            for name, config in sources.items():
                if cancel_event and cancel_event.is_set():
                    break

                if config.get('type') == 'habr':
                    provider = HabrProvider(name, config, self.storage)
                    
                    task_id = p.add_task(f"Syncing {name}...", total=None)

                    def update_progress(description: str, current: int, total: Optional[int]):
                        p.update(task_id, description=f"[{name}] {description}", completed=current, total=total)
                        if log_callback:
                            log_callback(f"[{name}] {description}")

                    report = provider.fetch(on_progress=update_progress, cancel_event=cancel_event)
                    
                    if report:
                        total_added += len(report.get('added_articles', []))
                        total_updated += len(report.get('updated_articles', []))
                        
                        # Log details if needed
                        if log_callback and report.get('errors_count', 0) > 0:
                            log_callback(f"[{name}] Completed with {report['errors_count']} errors.")
                    
                    p.remove_task(task_id)

        if progress is None:
            # Only print summary if we own the progress bar (CLI mode)
            print(f"Sync complete. Added {total_added} new, updated {total_updated} existing.")

    def get_sources_summary(self) -> List[dict]:
        """Gets a summary for each configured source (article count and last sync date)."""
        sources_summary = []
        sources_config = self.config.get('sources', {})
        for name in sources_config:
            count = self.storage.get_article_count_by_source(name)
            latest_date = self.storage.get_latest_article_date_by_source(name)
            # Calculate topics count from config
            source_config = sources_config.get(name, {})
            topics_count = len(source_config.get('hubs', []))
            
            sources_summary.append({
                "name": name,
                "articles_count": count,
                "topics_count": topics_count,
                "last_sync_date": latest_date
            })
        return sources_summary

    def get_articles(self, read: Optional[bool] = None, interesting: Optional[bool] = None, source: Optional[str] = None) -> List[Article]:
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
    def run_sync(self, source_names: Optional[List[str]] = None, progress: Optional[Progress] = None, log_callback: Optional[Callable[[str], None]] = None, cancel_event: Optional[Any] = None):
        """Runs the sync process for configured sources."""
        sources = self.config.get('sources', {})
        
        # Filter sources if specific ones requested
        if source_names:
            sources = {name: sources[name] for name in source_names if name in sources}

        total_added = 0
        total_updated = 0

        from contextlib import nullcontext
        
        if progress is None:
            progress_ctx = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeRemainingColumn(),
            )
        else:
            progress_ctx = nullcontext(progress)

        with progress_ctx as p:
            
            for name, config in sources.items():
                if cancel_event and cancel_event.is_set():
                    break

                if config.get('type') == 'habr':
                    provider = HabrProvider(name, config, self.storage)
                    
                    task_id = p.add_task(f"Syncing {name}...", total=None)

                    def update_progress(description: str, current: int, total: Optional[int]):
                        p.update(task_id, description=f"[{name}] {description}", completed=current, total=total)
                        if log_callback:
                            log_callback(f"[{name}] {description}")

                    report = provider.fetch(on_progress=update_progress, cancel_event=cancel_event)
                    
                    if report:
                        total_added += len(report.get('added_articles', []))
                        total_updated += len(report.get('updated_articles', []))
                        
                        # Log details if needed
                        if log_callback and report.get('errors_count', 0) > 0:
                            log_callback(f"[{name}] Completed with {report['errors_count']} errors.")
                    
                    p.remove_task(task_id)

        if progress is None:
            # Only print summary if we own the progress bar (CLI mode)
            print(f"Sync complete. Added {total_added} new, updated {total_updated} existing.")