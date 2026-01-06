from inforadar.storage import Storage
from inforadar.config import SettingsManager, get_db_url
from inforadar.providers.habr import HabrProvider
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

    def fetch_and_merge_hubs(
        self,
        source_name: str = "habr",
        enrich: bool = True,
        on_progress: Optional[Callable] = None,
        cancel_event: Optional[Any] = None,
    ) -> Dict[str, int]:
        """
        Fetches hubs for a given source, optionally enriches them,
        and merges them with the existing list in settings.
        In debug mode, this process is limited and non-destructive.
        """
        sources = self.settings.get("sources", {})
        source_config = sources.get(source_name)
        is_debug = self.settings.get("debug.enabled", False)

        def _progress(data: dict):
            if on_progress:
                on_progress(data)

        if not source_config or source_config.get("type") != "habr":
            _progress({'message': f"Source '{source_name}' not found or is not a habr type.", 'stage': 'error'})
            return {"added": 0, "updated": 0, "deleted": 0}

        # Inject concurrency setting into config
        concurrency = self.settings.get("fetch.concurrency", 10)
        source_config['concurrency'] = concurrency

        provider = HabrProvider(source_name, source_config, self.storage)

        # 1. Fetch hubs from the provider, respecting debug limit
        hub_limit = self.settings.get("debug.hub_limit", 10) if is_debug else None
        fetched_hubs = provider.fetch_hubs(on_progress=_progress, cancel_event=cancel_event, hub_limit=hub_limit)
        
        if cancel_event and cancel_event.is_set():
            return {"added": 0, "updated": 0, "deleted": 0, "cancelled": 1}

        # 2. Enrich hubs if requested
        if enrich and fetched_hubs:
            _progress({'message': "Starting hub enrichment...", 'stage': 'enriching', 'current': 0, 'total': len(fetched_hubs)})
            try:
                enriched_hubs = asyncio.run(
                    provider.enrich_hubs(fetched_hubs, on_progress=_progress, cancel_event=cancel_event)
                )
                fetched_hubs = enriched_hubs
            except Exception as e:
                logger.error(f"Hub enrichment failed: {e}", exc_info=True)
                _progress({'message': f"[red]Hub enrichment failed: {e}[/red]", 'stage': 'error'})

        if cancel_event and cancel_event.is_set():
            return {"added": 0, "updated": 0, "deleted": 0, "cancelled": 1}

        # 3. Merge hubs
        _progress({'message': "Merging hubs with existing list...", 'stage': 'merging'})
        key = f"sources.{source_name}.hubs"
        existing_hubs_list = self.settings.get(key, [])
        
        if is_debug:
            # Safe merge for debug mode: only add or update, never delete
            final_hubs_list, stats = self._safe_merge_hubs(existing_hubs_list, fetched_hubs)
        else:
            # Full merge for normal mode: add, update, and delete
            final_hubs_list, stats = self._full_merge_hubs(existing_hubs_list, fetched_hubs)

        # 4. Save the final list back to settings
        self.settings.set(key, final_hubs_list, type_hint='custom')

        # 5. Report completion
        added_str = f"[bold green]{stats['added']}[/bold green]" if stats['added'] > 0 else str(stats['added'])
        updated_str = f"[bold green]{stats['updated']}[/bold green]" if stats['updated'] > 0 else str(stats['updated'])
        deleted_str = f"[bold yellow]{stats['deleted']}[/bold yellow]" if stats['deleted'] > 0 else str(stats['deleted'])
        _progress({'message': f"Merge complete. Added: {added_str}, Updated: {updated_str}, Deleted: {deleted_str}.", 'stage': 'done'})

        return stats

    def _safe_merge_hubs(self, existing_hubs: List[Dict], fetched_hubs: List[Dict]) -> Tuple[List[Dict], Dict[str, int]]:
        """
        Merges hubs in a non-destructive way. Only adds new hubs or updates existing ones.
        Never deletes. Returns the modified list and stats.
        """
        stats = {"added": 0, "updated": 0, "deleted": 0}
        final_hubs = existing_hubs[:]  # Work on a copy
        existing_hubs_map = {hub["id"]: hub for hub in final_hubs}
        fetch_timestamp = datetime.now(timezone.utc).isoformat()

        for fetched_hub in fetched_hubs:
            hub_id = fetched_hub["id"]
            existing_hub = existing_hubs_map.get(hub_id)

            update_data = {
                "fetch_date": fetch_timestamp,
                "rating": fetched_hub.get("rating"),
                "subscribers": fetched_hub.get("subscribers"),
            }
            if fetched_hub.get("articles") is not None:
                update_data["articles"] = fetched_hub.get("articles")
            if fetched_hub.get("last_article_date") is not None:
                update_data["last_article_date"] = fetched_hub.get("last_article_date")

            if existing_hub:
                existing_hub.update(update_data)
                if not existing_hub.get("name"):
                    existing_hub["name"] = fetched_hub["name"]
                stats["updated"] += 1
            else:
                new_hub = {
                    "id": hub_id,
                    "name": fetched_hub.get("name"),
                    "enabled": True,
                    **update_data,
                }
                final_hubs.append(new_hub)
                stats["added"] += 1
        
        return final_hubs, stats

    def _full_merge_hubs(self, existing_hubs: List[Dict], fetched_hubs: List[Dict]) -> Tuple[List[Dict], Dict[str, int]]:
        """
        Performs a full merge, including adding, updating, and deleting hubs.
        Returns the new list and stats.
        """
        final_hubs = []
        stats = {"added": 0, "updated": 0, "deleted": 0}
        
        existing_hubs_map = {hub["id"]: hub for hub in existing_hubs}
        fetched_hub_ids = {hub['id'] for hub in fetched_hubs}
        
        # Calculate deleted hubs
        deleted_ids = set(existing_hubs_map.keys()) - fetched_hub_ids
        stats["deleted"] = len(deleted_ids)
        
        fetch_timestamp = datetime.now(timezone.utc).isoformat()

        for fetched_hub in fetched_hubs:
            hub_id = fetched_hub["id"]
            existing_hub = existing_hubs_map.get(hub_id)

            if existing_hub:
                # Update existing hub
                update_data = {
                    "rating": fetched_hub.get("rating"),
                    "subscribers": fetched_hub.get("subscribers"),
                    "fetch_date": fetch_timestamp,
                }
                if fetched_hub.get("articles") is not None:
                    update_data["articles"] = fetched_hub.get("articles")
                if fetched_hub.get("last_article_date") is not None:
                    update_data["last_article_date"] = fetched_hub.get("last_article_date")
                
                existing_hub.update(update_data)
                if not existing_hub.get("name"):
                    existing_hub["name"] = fetched_hub["name"]
                final_hubs.append(existing_hub)
                stats["updated"] += 1
            else:
                # Add new hub
                new_hub = {
                    "id": hub_id,
                    "name": fetched_hub.get("name"),
                    "enabled": True,
                    "fetch_date": fetch_timestamp,
                    "rating": fetched_hub.get("rating"),
                    "subscribers": fetched_hub.get("subscribers"),
                    "articles": fetched_hub.get("articles"),
                    "last_article_date": fetched_hub.get("last_article_date"),
                }
                final_hubs.append(new_hub)
                stats["added"] += 1
                
        return final_hubs, stats


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

        # Cache providers
        providers = {}

        for i, article in enumerate(articles, 1):
            print(f"  [{i}/{len(articles)}] {article.title[:50]}...")

            if not article.source:
                continue

            if article.source not in providers:
                source_config = self.settings.get("sources", {}).get(article.source)
                if source_config and source_config.get("type") == "habr":
                    providers[article.source] = HabrProvider(
                        article.source, source_config, self.storage
                    )
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
                    provider = HabrProvider(name, config, self.storage)

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

                    report = provider.fetch(
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