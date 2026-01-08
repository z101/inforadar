from inforadar.storage import Storage
from inforadar.config import SettingsManager, get_db_url
from inforadar.sources.habr import HabrSource
from inforadar.models import Article
from typing import List, Optional, Callable, Any, Dict, Tuple
from datetime import datetime, timedelta, timezone
import time
import random
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
)
from alembic.config import Config
from alembic import command
import logging
import asyncio


class CoreEngine:
    """Orchestrates the entire data fetching and storing process."""

    def __init__(self):
        db_url = get_db_url()
        self._run_migrations(db_url)
        self.storage = Storage(db_url)
        self.settings = SettingsManager(self.storage.Session)
        self.settings.load_settings()

    def _run_migrations(self, db_url: str):
        """Programmatically runs Alembic migrations to upgrade DB to the latest version."""
        try:
            alembic_cfg = Config("database/alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", db_url)
            command.upgrade(alembic_cfg, "head")
        except Exception as e:
            logging.getLogger(__name__).error(f"Alembic migration failed: {e}", exc_info=True)
            raise

    def get_sources_summary(self) -> List[dict]:
        """Gets a summary for each configured source (article count and last sync date)."""
        sources_summary = []
        sources_config = self.settings.get("sources", {})
        for name in sources_config:
            count = self.storage.get_article_count_by_source(name)
            latest_date = self.storage.get_latest_article_date_by_source(name)
            # Calculate topics count from config
            source_config = sources_config.get(name, {})
            topics_count = len(source_config.get("hubs", []))

            sources_summary.append(
                {
                    "name": name,
                    "articles_count": count,
                    "topics_count": topics_count,
                    "last_sync_date": latest_date,
                }
            )
        return sources_summary

    def get_articles(
        self,
        read: Optional[bool] = None,
        interesting: Optional[bool] = None,
        source: Optional[str] = None,
    ) -> List[Article]:
        """Retrieves articles from storage based on status."""
        return self.storage.get_articles(
            read=read, interesting=interesting, source=source
        )

    def get_provider(self, source_name: str) -> Optional[Any]:
        """Returns an initialized provider instance for the given source name."""
        sources = self.settings.get("sources", {})
        source_config = sources.get(source_name)
        
        if not source_config or source_config.get("type") != "habr":
            return None

        return HabrSource(source_name, source_config, self.storage)



    def update_article_status(
        self,
        article_id: int,
        read: Optional[bool] = None,
        interesting: Optional[bool] = None,
    ):
        """Updates the status of an article in storage."""
        self.storage.update_article_status(
            article_id, read=read, interesting=interesting
        )

    def run_refresh(self, days: int = 7, unread_only: bool = True):
        """Refreshes metadata for existing articles."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        articles = self.storage.get_articles_for_refresh(
            after_date=cutoff_date, read=False if unread_only else None
        )

        if not articles:
            print("No articles to refresh.")
            return

        print(f"Refreshing metadata for {len(articles)} articles...")
        updated_count = 0

        # Cache source instances
        source_instances = {}

        for i, article in enumerate(articles, 1):
            print(f"  [{i}/{len(articles)}] {article.title[:50]}...")

            if not article.source:
                continue

            if article.source not in source_instances:
                source_config = self.settings.get("sources", {}).get(article.source)
                if source_config and source_config.get("type") == "habr":
                    source_instances[article.source] = HabrSource(
                        article.source, source_config, self.storage
                    )
                else:
                    source_instances[article.source] = None

            source_instance = source_instances[article.source]
            if not source_instance:
                continue

            time.sleep(random.uniform(0.1, 0.5))  # Be nice to the server
            extra_data = source_instance._enrich_article_data(article.link)
            if self.storage.update_article_metadata(article.id, extra_data):
                updated_count += 1

        print(f"Successfully refreshed metadata for {updated_count} articles.")

    def run_sync(
        self,
        source_names: Optional[List[str]] = None,
        progress: Optional[Progress] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        cancel_event: Optional[Any] = None,
    ):
        """Runs the sync process for configured sources."""
        sources = self.settings.get("sources", {})

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

                if config.get("type") == "habr":
                    source_instance = HabrSource(name, config, self.storage)

                    task_id = p.add_task(f"Syncing {name}...", total=None)

                    def update_progress(
                        description: str, current: int, total: Optional[int]
                    ):
                        p.update(
                            task_id,
                            description=f"[{name}] {description}",
                            completed=current,
                            total=total,
                        )
                        if log_callback:
                            log_callback(f"[{name}] {description}")

                    report = source_instance.fetch(
                        on_progress=update_progress, cancel_event=cancel_event
                    )

                    if report:
                        total_added += len(report.get("added_articles", []))
                        total_updated += len(report.get("updated_articles", []))

                        # Log details if needed
                        if log_callback and report.get("errors_count", 0) > 0:
                            log_callback(
                                f"[{name}] Completed with {report['errors_count']} errors."
                            )

                    p.remove_task(task_id)

        if progress is None:
            # Only print summary if we own the progress bar (CLI mode)
            print(
                f"Sync complete. Added {total_added} new, updated {total_updated} existing."
            )