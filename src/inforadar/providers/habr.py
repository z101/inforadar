
import time
import random
import requests
import calendar
from bs4 import BeautifulSoup
import markdownify
from typing import List, Dict, Any, Optional, Tuple, Set
from urllib.parse import urlparse, urlunparse
from datetime import datetime, timezone, timedelta
import logging

from ..models import Article
from ..storage import Storage

# Configure logging
logger = logging.getLogger(__name__)

class HabrProvider:
    """Provider for fetching and enriching articles from Habr.com using strict page-by-page scraping."""

    def __init__(self, source_name: str, config: Dict[str, Any], storage: Storage):
        self.source_name = source_name
        self.config = config
        self.storage = storage
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        
        # Parse configuration
        self.cutoff_date = None
        if self.config.get('cutoff_date'):
            try:
                self.cutoff_date = datetime.strptime(self.config['cutoff_date'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        
        self.window_days = self.config.get('window_days', 30)
        self.window_cutoff = datetime.now(timezone.utc) - timedelta(days=self.window_days)

    def fetch(self, on_progress: Optional[Any] = None, cancel_event: Optional[Any] = None) -> Dict[str, Any]:
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
            'added_articles': [],
            'updated_articles': [],
            'updated_fields_map': {},
            'errors_count': 0
        }
        
        hubs = self.config.get('hubs', [])
        
        for hub_entry in hubs:
            # Handle both string and dict config
            if isinstance(hub_entry, dict):
                hub_id = hub_entry.get('id')
            else:
                hub_id = hub_entry

            if not hub_id: continue

            if on_progress:
                on_progress(f"Processing hub '{hub_id}'...", 0, None)
            
            self._process_hub(hub_id, report, on_progress, cancel_event)
            
            if cancel_event and cancel_event.is_set():
                break
            
        return report

    def _process_hub(self, hub_id: str, report: Dict[str, Any], on_progress: Optional[Any], cancel_event: Optional[Any] = None):
        seen_existing = False
        found_new_inside_window = False
        
        page = 1
        
        while True:
            if cancel_event and cancel_event.is_set():
                if on_progress: on_progress("Cancelled by user.", 0, None)
                break

            if on_progress:
                on_progress(f"Hub '{hub_id}': Scanning page {page}...", 0, None)
            
            # 1. Parse page
            items = self._fetch_page_items(hub_id, page)
            
            if items is None:
                # Error parsing page
                report['errors_count'] += 1
                break # Stop on error for this hub, or continue? Doc says "Result logs error", but implies robust. 
                      # "Condition 3: Parsing error... should log but not break idempotency". 
                      # If we can't parse page, we probably can't go deeper.
                break

            if not items:
                # Condition 2: Empty page
                break
                
            for item in items:
                # 6.1 Normalization is done in _fetch_page_items or here. 
                # Let's say item is a partial Article object.
                
                # Check date
                if self.cutoff_date and item.published_date < self.cutoff_date:
                    if seen_existing and not found_new_inside_window:
                        # Condition 1: Reached cutoff, saw existing, no new in window -> STOP
                        return
                    else:
                        # Continue scanning, maybe there are gaps? 
                        # Doc says: "If condition not met - CONTINUE".
                        pass
                
                # 6.3 Check existence
                existing_article = self.storage.get_article_by_guid(item.guid)
                
                if not existing_article:
                    # 6.4 New Article
                    # Insert with available fields (no nulls if possible)
                    # We need to enrich it first? Doc says "insert ... with all available fields".
                    # Usually snippet is on the list page. Full text needs fetch.
                    # We will insert what we have.
                    
                    self.storage.add_article(item)
                    report['added_articles'].append(item.link)
                    
                    if seen_existing:
                        found_new_inside_window = True
                        
                else:
                    # 6.5 Existing Article
                    seen_existing = True
                    
                    # Update metadata (diff)
    def _process_hub(self, hub_id: str, report: Dict[str, Any], on_progress: Optional[Any], cancel_event: Optional[Any] = None):
        seen_existing = False
        found_new_inside_window = False
        
        page = 1
        
        while True:
            if cancel_event and cancel_event.is_set():
                if on_progress: on_progress("Cancelled by user.", 0, None)
                break

            if on_progress:
                on_progress(f"Hub '{hub_id}': Scanning page {page}...", 0, None)
            
            # 1. Parse page
            items = self._fetch_page_items(hub_id, page)
            
            if items is None:
                # Error parsing page
                report['errors_count'] += 1
                break # Stop on error for this hub, or continue? Doc says "Result logs error", but implies robust. 
                      # "Condition 3: Parsing error... should log but not break idempotency". 
                      # If we can't parse page, we probably can't go deeper.
                break

            if not items:
                # Condition 2: Empty page
                break
                
            for item in items:
                # 6.1 Normalization is done in _fetch_page_items or here. 
                # Let's say item is a partial Article object.
                
                # Check date
                if self.cutoff_date and item.published_date < self.cutoff_date:
                    if seen_existing and not found_new_inside_window:
                        # Condition 1: Reached cutoff, saw existing, no new in window -> STOP
                        return
                    else:
                        # Continue scanning, maybe there are gaps? 
                        # Doc says: "If condition not met - CONTINUE".
                        continue
                
                # 6.3 Check existence
                existing_article = self.storage.get_article_by_guid(item.guid)
                
                if not existing_article:
                    # 6.4 New Article
                    # Insert with available fields (no nulls if possible)
                    # We need to enrich it first? Doc says "insert ... with all available fields".
                    # Usually snippet is on the list page. Full text needs fetch.
                    # We will insert what we have.
                    
                    self.storage.add_article(item)
                    report['added_articles'].append(item.link)
                    
                    if seen_existing:
                        found_new_inside_window = True
                        
                else:
                    # 6.5 Existing Article
                    seen_existing = True
                    
                    # Update metadata (diff)
                    storage_updates, report_changes = self._calculate_diff(existing_article, item)
                    
                    if storage_updates:
                        self.storage.update_article_fields(existing_article.guid, storage_updates)
                        report['updated_articles'].append(item.link)
                        report['updated_fields_map'][item.link] = report_changes
            
            # Move to next page
            page += 1
            # Add a small delay to be polite
            time.sleep(random.uniform(0.2, 0.5))
            
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
            
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []
            
            article_elements = soup.select("article.tm-articles-list__item")
            if not article_elements and page == 1:
                # Might be a different layout or error?
                pass
            
            for article_el in article_elements:
                try:
                    # Extract Data
                    link_el = article_el.select_one("a.tm-title__link")
                    title_el = article_el.select_one("h2.tm-title")
                    time_el = article_el.select_one(".tm-article-datetime-published time")
                    
                    if not link_el or not time_el: continue

                    href = link_el['href']
                    link = self._clean_url(f"https://habr.com{href}") if not href.startswith('http') else self._clean_url(href)
                    
                    guid = link
                    if not guid.endswith('/'): guid += '/'
                    
                    title = title_el.text.strip() if title_el else link_el.text.strip()
                    pub_date = datetime.fromisoformat(time_el['datetime'].replace('Z', '+00:00'))
                    
                    # Metadata
                    rating_text = self._find_text(article_el, [".tm-votes-lever__score-counter"])
                    views_text = self._find_text(article_el, [".tm-icon-counter__value"])
                    comments_text = self._find_text(article_el, [".article-comments-counter-link span.value", ".tm-article-comments-counter-link__value"])
                    
                    extra_data = {
                        'rating': int(rating_text.replace('+', '').replace('−', '-')) if rating_text else None,
                        'views': views_text,
                        'comments': int(comments_text.strip()) if comments_text else 0,
                        'hub_id': hub,
                        'tags': [t.text.strip() for t in article_el.select(".tm-publication-hub__link")]
                    }
                    
                    article = Article(
                        guid=guid,
                        link=link,
                        title=title,
                        published_date=pub_date,
                        source=self.source_name,
                        extra_data=extra_data,
                        # Don't set content_md here, it's a list item
                    )
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing item on page {page}: {e}")
                    continue
                    
            return articles
        except requests.RequestException:
            return None

    def _calculate_diff(self, existing: Article, new_item: Article) -> Tuple[Dict[str, Any], Dict[str, str]]:
        storage_updates = {}
        report_changes = {}

        # 1. Update title if changed and new is not empty
        if new_item.title and new_item.title != existing.title:
            storage_updates['title'] = new_item.title
            report_changes['title'] = f"{existing.title} -> {new_item.title}"

        # 2. Update extra_data
        existing_extra = existing.extra_data or {}
        new_extra = new_item.extra_data or {}
        
        merged_extra = existing_extra.copy()
        extra_changed = False

        for key, new_val in new_extra.items():
            old_val = existing_extra.get(key)
            
            if new_val is None or new_val == "":
                continue
            
            if old_val != new_val:
                merged_extra[key] = new_val
                extra_changed = True
                report_changes[f"extra_data.{key}"] = f"{old_val} -> {new_val}"
        
        if extra_changed:
            storage_updates['extra_data'] = merged_extra
            
        return storage_updates, report_changes

    def _clean_url(self, url: str) -> str:
        u = urlparse(url)
        return urlunparse((u.scheme, u.netloc, u.path, "", "", ""))

    def _find_text(self, element: Any, selectors: List[str]) -> Optional[str]:
        for selector in selectors:
            el = element.select_one(selector)
            if el: return el.text.strip()
        return None
