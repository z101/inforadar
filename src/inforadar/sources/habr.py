import time
import random
import requests
import calendar
from bs4 import BeautifulSoup
import markdownify
from typing import List, Dict, Any, Optional, Tuple, Set, Callable
from urllib.parse import urlparse, urlunparse
from datetime import datetime, timezone, timedelta
import logging
import re
import asyncio
import httpx

from inforadar.models import Article
from inforadar.storage import Storage

# Configure logging
logger = logging.getLogger(__name__)


class HabrSource:
    """Source for fetching and enriching articles from Habr.com using strict page-by-page scraping."""

    def __init__(self, source_name: str, config: Dict[str, Any], storage: Storage):
        self.source_name = source_name
        self.config = config
        self.storage = storage
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }

        # Parse configuration
        self.cutoff_date = None
        if self.config.get("cutoff_date"):
            try:
                self.cutoff_date = datetime.strptime(
                    self.config["cutoff_date"], "%Y-%m-%d"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        self.window_days = self.config.get("window_days", 30)
        self.window_cutoff = datetime.now(timezone.utc) - timedelta(
            days=self.window_days
        )

    def fetch(
        self, on_progress: Optional[Any] = None, cancel_event: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Executes the fetch algorithm.
        Returns a report dict: {
            'added_articles': [],
            'updated_articles': [],
            'updated_fields_map': {},
            'errors_count': 0
        }
        """
        report = {
            "added_articles": [],
            "updated_articles": [],
            "updated_fields_map": {},
            "errors_count": 0,
        }

        hubs = self.config.get("hubs", [])

        for hub_entry in hubs:
            # Handle both string and dict config
            if isinstance(hub_entry, dict):
                hub_id = hub_entry.get("id")
            else:
                hub_id = hub_entry

            if not hub_id:
                continue

            if on_progress:
                on_progress(f"Processing hub '{hub_id}'...", 0, None)

            self._process_hub(hub_id, report, on_progress, cancel_event)

            if cancel_event and cancel_event.is_set():
                break

        return report

    def fetch_hubs(
        self, on_progress: Optional[Callable] = None, cancel_event: Optional[Any] = None, hub_limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches hubs from Habr.com/ru/hubs.
        If hub_limit is provided, it stops after collecting enough hubs.
        """
        all_hubs = []
        
        def _progress(data: dict):
            if on_progress:
                on_progress(data)

        total_pages = None
        if hub_limit is None:
            # Phase 1: Determine total pages only if not in a limited run
            try:
                url = "https://habr.com/ru/hubs/"
                _progress({'message': "Determining number of pages...", 'stage': 'init'})
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                
                pagination_el = soup.select_one("div.tm-pagination")
                if pagination_el:
                    last_page_el = pagination_el.select_one("a.tm-pagination__page:last-child")
                    if last_page_el and last_page_el.text.isdigit():
                        total_pages = int(last_page_el.text)
            except requests.RequestException as e:
                logger.error(f"Failed to fetch first hubs page to determine total pages: {e}")
                _progress({'message': "Error determining total pages. Stopping.", 'stage': 'error'})
                return []
        
        # Phase 2: Fetch pages
        import itertools
        for page in itertools.count(1):
            if cancel_event and cancel_event.is_set():
                _progress({'message': "Cancelled by user.", 'stage': 'cancelled'})
                break

            # Stop if we've fetched all pages (in non-limited mode)
            if total_pages is not None and page > total_pages:
                break
            
            max_pages = total_pages if total_pages is not None else page
            _progress({'message': f"Fetching hubs from page {page} of {max_pages}...", 'stage': 'fetching', 'current': page, 'total': total_pages})
            url = f"https://habr.com/ru/hubs/page{page}/"
            
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                
                hubs_on_page = self._parse_hubs_from_page(soup)
                if not hubs_on_page:
                    break # Stop if a page has no hubs

                all_hubs.extend(hubs_on_page)
                
                # If a limit is active, check if we have enough hubs
                if hub_limit is not None and len(all_hubs) >= hub_limit:
                    all_hubs = all_hubs[:hub_limit]
                    _progress({'message': f"[yellow]DEBUG: Hub limit ({hub_limit}) reached.[/yellow]", 'stage': 'log'})
                    break

                if total_pages and page < total_pages:
                    time.sleep(random.uniform(0.2, 0.5))

            except requests.RequestException as e:
                logger.error(f"Failed to fetch hubs page {page}: {e}")
                _progress({'message': f"Error fetching page {page}. Stopping.", 'stage': 'error'})
                break
        
        _progress({'message': f"Fetched a total of [bold green]{len(all_hubs)}[/bold green] hubs.", 'stage': 'done'})
        return all_hubs

    def _parse_hubs_from_page(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parses a list of hubs from a given BeautifulSoup object."""
        hubs_on_page = []
        hub_elements = soup.select("div.tm-hub")

        for hub_el in hub_elements:
            try:
                title_el = hub_el.select_one("a.tm-hub__title")
                if not title_el:
                    continue

                href = title_el["href"]
                # Try to match different URL formats for hub IDs
                hub_id_match = re.search(r'/(?:hub|hubs)/([^/]+)/', href)
                if hub_id_match:
                    hub_id = hub_id_match.group(1)
                else:
                    # Fallback for URLs like /ru/company/selectel/blog/
                    parts = href.strip('/').split('/')
                    if len(parts) > 2:
                         hub_id = parts[-2]
                    else:
                         hub_id = parts[-1]

                name = title_el.select_one("span").text.strip()

                rating_el = hub_el.select_one(".tm-hub__rating")
                rating_text = rating_el.text.strip() if rating_el else "0"
                rating = float(rating_text)

                subscribers_el = hub_el.select_one(".tm-hub__subscribers")
                subscribers_text = subscribers_el.text.strip() if subscribers_el else "0"
                subscribers = self._parse_subscribers(subscribers_text)

                hubs_on_page.append({
                    "id": hub_id,
                    "name": name,
                    "rating": rating,
                    "subscribers": subscribers,
                })
            except (AttributeError, ValueError, IndexError) as e:
                logger.error(f"Error parsing a hub from page content: {e}")
                continue
        return hubs_on_page


    def _parse_subscribers(self, s: str) -> int:
        s = s.lower().strip()
        if not s:
            return 0
        if 'k' in s:
            return int(float(s.replace('k', '')) * 1000)
        return int(s)
    
    async def enrich_hubs(
        self, hubs: List[Dict[str, Any]], on_progress: Optional[Callable] = None, cancel_event: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Enriches a list of hubs with last article date and total articles count.
        """
        enriched_hubs = []
        concurrency = self.config.get("concurrency", 10)
        semaphore = asyncio.Semaphore(concurrency)  # Limit concurrent requests
        total_hubs = len(hubs)
        completed_count = [0] # Mutable container

        def _progress(message: str = None, increment: bool = False):
            if increment:
                completed_count[0] += 1
            if on_progress and message:
                on_progress({'message': message, 'stage': 'enriching', 'current': completed_count[0], 'total': total_hubs})
            # Also notify if we just incremented, for progress bar, even if no message
            elif on_progress and increment:
                 on_progress({'message': None, 'stage': 'enriching', 'current': completed_count[0], 'total': total_hubs})

        async with httpx.AsyncClient(headers=self.headers, timeout=20, follow_redirects=True) as client:
            tasks = []
            for i, hub in enumerate(hubs):
                if cancel_event and cancel_event.is_set():
                    break
                task = asyncio.create_task(self._enrich_one_hub(client, semaphore, hub, i + 1, total_hubs, _progress))
                tasks.append(task)
            
            enriched_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(enriched_results):
            if isinstance(result, Exception):
                logger.error(f"Error enriching hub {hubs[i].get('id', 'N/A')}: {result}")
                enriched_hubs.append(hubs[i])  # Append original hub on error
            elif result:
                enriched_hubs.append(result)
        
        return enriched_hubs

    async def _enrich_one_hub(self, client: httpx.AsyncClient, semaphore: asyncio.Semaphore, hub: Dict[str, Any], hub_index: int, total_hubs: int, progress_cb: Callable) -> Dict[str, Any]:
        hub_id = hub.get("id")
        hub_name = hub.get("name", hub_id)
        # Handle cases where hub_id could be in a company blog etc.
        if '/company/' in hub.get('name', '').lower():
            url = f"https://habr.com/ru/company/{hub_id}/articles/"
        else:
            url = f"https://habr.com/ru/hubs/{hub_id}/articles/"
            
        updated_hub = hub.copy()

        async with semaphore:
            if progress_cb:
                progress_cb(message=f"Enriching hub '{hub_name}' {hub_index} from {total_hubs}...")
            
            # Fetch first page
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning(f"Hub '{hub_id}' not found at {url}. Skipping enrichment.")
                    if progress_cb:
                        progress_cb(increment=True)
                    return hub # Return original hub
                else:
                    raise
            except httpx.RequestError as e:
                logger.error(f"Request failed for hub '{hub_id}' at {url}: {e}")
                if progress_cb:
                    progress_cb(increment=True)
                return hub

            soup = BeautifulSoup(response.text, "html.parser")

            # 1. Get last article date
            updated_hub['last_article_date'] = self._parse_last_article_date(soup)

            # 2. Get articles count
            articles_on_first_page = len(soup.select("article.tm-articles-list__item"))
            pagination_pages = soup.select("a.tm-pagination__page")
            
            if not pagination_pages:
                updated_hub['articles'] = articles_on_first_page
            else:
                try:
                    # Find last page number, ignoring "next" links etc.
                    last_page_num = 0
                    for page_link in reversed(pagination_pages):
                        if page_link.text.strip().isdigit():
                            last_page_num = int(page_link.text.strip())
                            break
                    
                    if last_page_num <= 1:
                        updated_hub['articles'] = articles_on_first_page
                    else:
                        # Fetch last page to count articles there
                        last_page_url = f"{str(response.url).rstrip('/')}/page{last_page_num}/"
                        try:
                            last_page_response = await client.get(last_page_url)
                            last_page_response.raise_for_status()
                            last_page_soup = BeautifulSoup(last_page_response.text, "html.parser")
                            articles_on_last_page = len(last_page_soup.select("article.tm-articles-list__item"))
                            
                            total_articles = (articles_on_first_page * (last_page_num - 1)) + articles_on_last_page
                            updated_hub['articles'] = total_articles
                        except (httpx.RequestError, httpx.HTTPStatusError) as e:
                            logger.error(f"Failed to fetch last page for hub '{hub_id}': {e}")
                            updated_hub['articles'] = None # Mark as failed
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing pagination for hub '{hub_id}': {e}")
                    updated_hub['articles'] = None

        if progress_cb:
            progress_cb(increment=True)
        return updated_hub

    def _parse_last_article_date(self, soup: BeautifulSoup) -> Optional[str]:
        time_el = soup.select_one(".tm-article-datetime-published time")
        if time_el and time_el.has_attr('datetime'):
            return time_el['datetime']
        return None

    def _process_hub(
        self,
        hub_id: str,
        report: Dict[str, Any],
        on_progress: Optional[Any],
        cancel_event: Optional[Any] = None,
    ):
        seen_existing = False
        found_new_inside_window = False

        page = 1

        while True:
            if cancel_event and cancel_event.is_set():
                if on_progress:
                    on_progress("Cancelled by user.", 0, None)
                break

            if on_progress:
                on_progress(f"Hub '{hub_id}': Scanning page {page}...", 0, None)

            # 1. Parse page
            items = self._fetch_page_items(hub_id, page)

            if items is None:
                # Error parsing page
                report["errors_count"] += 1
                break  # Stop on error for this hub
                break

            if not items:
                # Condition 2: Empty page
                break

            for item in items:
                # Check date
                if self.cutoff_date and item.published_date < self.cutoff_date:
                    if seen_existing and not found_new_inside_window:
                        # Condition 1: Reached cutoff, saw existing, no new in window -> STOP
                        return
                    else:
                        # Continue scanning, maybe there are gaps?
                        continue

                # 6.3 Check existence
                existing_article = self.storage.get_article_by_guid(item.guid)

                if not existing_article:
                    # 6.4 New Article
                    self.storage.add_article(item)
                    report["added_articles"].append(item.link)

                    if seen_existing:
                        found_new_inside_window = True

                else:
                    # 6.5 Existing Article
                    seen_existing = True

                    # Update metadata (diff)
                    storage_updates, report_changes = self._calculate_diff(
                        existing_article, item
                    )

                    if storage_updates:
                        self.storage.update_article_fields(
                            existing_article.guid, storage_updates
                        )
                        report["updated_articles"].append(item.link)
                        report["updated_fields_map"][item.link] = report_changes

            # Move to next page
            page += 1
            # Add a small delay to be polite
            time.sleep(random.uniform(0.2, 0.5))

    def _fetch_page_items(self, hub: str, page: int) -> Optional[List[Article]]:
        url = f"https://habr.com/ru/hubs/{hub}/articles/page{page}/"
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 404:
                return []
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            articles = []

            article_elements = soup.select("article.tm-articles-list__item")

            for article_el in article_elements:
                try:
                    # Extract Data
                    link_el = article_el.select_one("a.tm-title__link")
                    time_el = article_el.select_one(
                        ".tm-article-datetime-published time"
                    )

                    if not link_el or not time_el:
                        continue

                    href = link_el["href"]
                    link = (
                        self._clean_url(f"https://habr.com{href}")
                        if not href.startswith("http")
                        else self._clean_url(href)
                    )

                    guid = link
                    if not guid.endswith("/"):
                        guid += "/"

                    title = link_el.text.strip()
                    pub_date = datetime.fromisoformat(
                        time_el["datetime"].replace("Z", "+00:00")
                    )

                    # Metadata
                    rating_text = self._find_text(
                        article_el, [".tm-votes-lever__score-counter"]
                    )
                    views_text = self._find_text(
                        article_el, [".tm-icon-counter__value"]
                    )
                    comments_text = self._find_text(
                        article_el,
                        [
                            ".tm-article-comments-counter-link__value",
                        ],
                    )

                    extra_data = {
                        "rating": (
                            int(rating_text.replace(" ", "").replace("−", "-"))
                            if rating_text
                            else None
                        ),
                        "views": views_text,
                        "comments": int(comments_text.strip()) if comments_text else 0,
                        "hub_id": hub,
                        "tags": [
                            t.text.strip()
                            for t in article_el.select(".tm-publication-hub__link")
                        ],
                    }

                    article = Article(
                        guid=guid,
                        link=link,
                        title=title,
                        published_date=pub_date,
                        source=self.source_name,
                        extra_data=extra_data,
                    )
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing item on page {page}: {e}")
                    continue

            return articles
        except requests.RequestException as e:
            logger.error(f"Error fetching page {url}: {e}")
            return None

    def _calculate_diff(
        self, existing: Article, new_item: Article
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        storage_updates = {}
        report_changes = {}

        # 1. Update title if changed and new is not empty
        if new_item.title and new_item.title != existing.title:
            storage_updates["title"] = new_item.title
            report_changes["title"] = f"{existing.title} -> {new_item.title}"

        # 2. Update extra_data
        existing_extra = existing.extra_data or {}
        new_extra = new_item.extra_data or {}

        merged_extra = existing_extra.copy()
        extra_changed = False

        for key, new_val in new_extra.items():
            old_val = existing_extra.get(key)

            if new_val is not None and new_val != "" and old_val != new_val:
                merged_extra[key] = new_val
                extra_changed = True
                report_changes[f"extra_data.{key}"] = f"{old_val} -> {new_val}"

        if extra_changed:
            storage_updates["extra_data"] = merged_extra

        return storage_updates, report_changes

    def _clean_url(self, url: str) -> str:
        u = urlparse(url)
        return urlunparse((u.scheme, u.netloc, u.path, "", "", ""))

    def discover_and_merge_hubs(
        self,
        current_hubs: List[Dict[str, Any]],
        enrich: bool = True,
        debug_limit: Optional[int] = None,
        on_progress: Optional[Callable] = None,
        cancel_event: Optional[Any] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Fetches hubs, optionally enriches them, and merges with existing list.
        """
        def _progress(data: dict):
            if on_progress:
                on_progress(data)

        # 1. Fetch hubs
        fetched_hubs = self.fetch_hubs(on_progress=_progress, cancel_event=cancel_event, hub_limit=debug_limit)

        if cancel_event and cancel_event.is_set():
            return [], {"added": 0, "updated": 0, "deleted": 0, "cancelled": 1}

        # 2. Enrich hubs
        if enrich and fetched_hubs:
            _progress({'message': "Starting hub enrichment...", 'stage': 'enriching', 'current': 0, 'total': len(fetched_hubs)})
            try:
                enriched_hubs = asyncio.run(
                    self.enrich_hubs(fetched_hubs, on_progress=_progress, cancel_event=cancel_event)
                )
                fetched_hubs = enriched_hubs
            except Exception as e:
                logger.error(f"Hub enrichment failed: {e}", exc_info=True)
                _progress({'message': f"[red]Hub enrichment failed: {e}[/red]", 'stage': 'error'})

        if cancel_event and cancel_event.is_set():
            return [], {"added": 0, "updated": 0, "deleted": 0, "cancelled": 1}

        # 3. Merge hubs
        _progress({'message': "Merging hubs with existing list...", 'stage': 'merging'})
        
        if debug_limit:
            # Safe merge for debug mode
            final_hubs_list, stats = self._safe_merge_hubs(current_hubs, fetched_hubs)
        else:
            # Full merge
            final_hubs_list, stats = self._full_merge_hubs(current_hubs, fetched_hubs)

        # 4. Report completion
        added_str = f"[bold green]{stats['added']}[/bold green]" if stats['added'] > 0 else str(stats['added'])
        updated_str = f"[bold green]{stats['updated']}[/bold green]" if stats['updated'] > 0 else str(stats['updated'])
        deleted_str = f"[bold yellow]{stats['deleted']}[/bold yellow]" if stats['deleted'] > 0 else str(stats['deleted'])
        _progress({'message': f"Merge complete. Added: {added_str}, Updated: {updated_str}, Deleted: {deleted_str}.", 'stage': 'done'})

        return final_hubs_list, stats

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

    def _find_text(self, element: Any, selectors: List[str]) -> Optional[str]:
        for selector in selectors:
            el = element.select_one(selector)
            if el:
                return el.text.strip()
        return None