

import time
import random
import requests
import feedparser
import calendar
from bs4 import BeautifulSoup
import markdownify
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, urlunparse
from datetime import datetime, timezone, timedelta

from ..models import Article
from ..storage import Storage

class HabrProvider:
    """Provider for fetching and enriching articles from Habr.com."""

    def __init__(self, source_name: str, config: Dict[str, Any], storage: Storage):
        self.source_name = source_name
        self.config = config
        self.storage = storage
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }

    def fetch(self, on_progress: Optional[Any] = None) -> List[Article]:
        """
        Fetches, enriches, and filters articles using the hybrid strategy.
        
        :param on_progress: Optional callback function(description: str, current: int, total: Optional[int])
        """
        all_new_articles = []
        hubs = self.config.get('hubs', [])
        
        for hub in hubs:
            if on_progress:
                on_progress(f"Scanning RSS for hub '{hub}'...", 0, None)

            # Step 1: Get articles from RSS
            rss_articles_map = {a.guid: a for a in self._fetch_rss_articles(hub)}
            
            # Step 2: Check for a gap
            last_known_date = self.storage.get_last_article_date(hub)
            if last_known_date:
                last_known_date = last_known_date.replace(tzinfo=timezone.utc)
            
            # Use initial_fetch_date on first run if configured
            cutoff_date = last_known_date
            if last_known_date is None:
                initial_date_str = self.config.get('initial_fetch_date')
                if initial_date_str:
                    try:
                        cutoff_date = datetime.strptime(initial_date_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        # Invalid date format, ignore and use None
                        pass
            
            oldest_rss_date = min(a.published_date for a in rss_articles_map.values()) if rss_articles_map else None

            scraped_articles_map = {}
            if cutoff_date and oldest_rss_date and oldest_rss_date > cutoff_date:
                if on_progress:
                    on_progress(f"Gap detected in '{hub}', scraping pages...", 0, None)
                # Step 3: Gap detected, start scraping hub pages
                scraped_articles_map = self._scrape_hub_pages(hub, cutoff_date)

            # Step 4: Combine and deduplicate
            combined_articles_map = {**scraped_articles_map, **rss_articles_map}
            
            # Determine which articles to process
            # 1. New articles (newer than cutoff_date)
            # 2. Recent articles (newer than auto-update threshold)
            
            auto_update_days = self.config.get('auto_update_within_days', 0)
            update_threshold = None
            if auto_update_days > 0:
                update_threshold = datetime.now(timezone.utc) - timedelta(days=auto_update_days)

            articles_to_process = []
            for article in combined_articles_map.values():
                is_new = not cutoff_date or article.published_date > cutoff_date
                is_recent = update_threshold and article.published_date > update_threshold
                
                if is_new or is_recent:
                    articles_to_process.append(article)

            # Step 5: Enrich articles
            total_articles = len(articles_to_process)
            for i, article in enumerate(articles_to_process, 1):
                if on_progress:
                    on_progress(f"Enriching: {article.title[:40]}...", i, total_articles)

                time.sleep(random.uniform(0.1, 0.5)) # Be nice to the server
                enrichment_data = self._enrich_article_data(article.link)
                
                # Update extra_data
                article.extra_data.update(enrichment_data.get('extra_data', {}))
                
                # Update new model fields
                article.content_md = enrichment_data.get('content_md')
                article.comments_data = enrichment_data.get('comments_data', [])
                
                all_new_articles.append(article)

        return all_new_articles

    def _clean_url(self, url: str) -> str:
        u = urlparse(url)
        return urlunparse((u.scheme, u.netloc, u.path, "", "", ""))

    def _fetch_rss_articles(self, hub: str) -> List[Article]:
        url = f"https://habr.com/ru/rss/hubs/{hub}/articles/?with_tags=true"
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries:
            published_dt = datetime.fromtimestamp(calendar.timegm(entry.published_parsed), tz=timezone.utc)
            tags = [tag.term for tag in entry.get('tags', [])]
            
            article = Article(
                guid=entry.id,
                link=self._clean_url(entry.link),
                title=entry.title,
                published_date=published_dt,
                source=self.source_name,
                extra_data={'tags': tags}
            )
            articles.append(article)
        return articles

    def _scrape_hub_pages(self, hub: str, stop_date: datetime) -> Dict[str, Article]:
        """Scrapes hub pages until an article older than stop_date is found."""
        scraped_articles = {}
        for page_num in range(1, 10): # Limit to 10 pages to prevent infinite loops
            url = f"https://habr.com/ru/hubs/{hub}/articles/page{page_num}/"
            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                page_is_getting_old = False
                for article_el in soup.select("article.tm-articles-list__item"):
                    link_el = article_el.select_one("a.tm-title__link")
                    time_el = article_el.select_one(".tm-article-datetime-published time")
                    
                    if not link_el or not time_el: continue

                    href = link_el['href']
                    # Handle both relative and absolute URLs
                    if href.startswith('http'):
                        link = self._clean_url(href)
                    else:
                        link = self._clean_url(f"https://habr.com{href}")
                    
                    guid = link
                    if not guid.endswith('/'):
                        guid += '/'
                    
                    title = link_el.text.strip()
                    pub_date = datetime.fromisoformat(time_el['datetime'].replace('Z', '+00:00'))

                    if pub_date <= stop_date:
                        page_is_getting_old = True
                        continue # Skip articles older than or same as stop_date

                    scraped_articles[guid] = Article(
                        guid=guid, link=link, title=title, published_date=pub_date, source=self.source_name, extra_data={}
                    )
                
                if page_is_getting_old:
                    break # Stop pagination
            except requests.RequestException:
                break # Stop on network error
        return scraped_articles

    def _find_text(self, soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
        for selector in selectors:
            element = soup.select_one(selector)
            if element: return element.text.strip()
        return None

    def _get_article_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extracts article content and converts it to Markdown."""
        # Try new selector first, then old one
        body = soup.select_one(".article-body") or soup.select_one(".tm-article-body")
        if not body:
            return None
        
        # Convert to Markdown
        md = markdownify.markdownify(str(body), heading_style="ATX")
        # Basic cleanup of excessive newlines
        return "\n".join(line for line in md.splitlines() if line.strip())

    def _get_article_comments(self, article_id: str) -> List[Dict[str, Any]]:
        """Fetches comments using Habr's internal API."""
        if not article_id:
            return []
            
        url = f"https://habr.com/kek/v2/articles/{article_id}/comments"
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                return []
            
            data = response.json()
            comments = []
            for comment_id, comment_data in data.get('comments', {}).items():
                if comment_data.get('delete'): continue
                
                comments.append({
                    'id': comment_data.get('id'),
                    'parent_id': comment_data.get('parentId'),
                    'author': comment_data.get('author', {}).get('login'),
                    'text': comment_data.get('message'),
                    'score': comment_data.get('score'),
                    'time': comment_data.get('timePublished')
                })
            return comments
        except (requests.RequestException, ValueError):
            return []

    def _enrich_article_data(self, url: str) -> Dict[str, Any]:
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract article ID from URL for comments API
            # URL format: https://habr.com/ru/articles/123456/
            path_parts = urlparse(url).path.strip('/').split('/')
            article_id = path_parts[-1] if path_parts else None

            # Updated selectors for current Habr.com structure
            rating_text = self._find_text(soup, [".tm-votes-lever__score-counter"])
            comments_text = self._find_text(soup, [".article-comments-counter-link span.value"])

            extra_data = {
                'rating': int(rating_text.replace('+', '').replace('−', '-')) if rating_text else None,
                'views': self._find_text(soup, [".tm-icon-counter__value"]),
                'reading_time': self._find_text(soup, [".tm-article-reading-time__label"]),
                'comments': int(comments_text) if comments_text else None
            }
            
            return {
                'extra_data': extra_data,
                'content_md': self._get_article_content(soup),
                'comments_data': self._get_article_comments(article_id) if article_id else []
            }
        except (AttributeError, ValueError, requests.RequestException):
            return {'extra_data': {}, 'content_md': None, 'comments_data': []}

    def _is_filtered_by_keyword(self, title: str) -> bool:
        exclude_keywords = self.config.get('filters', {}).get('exclude_keywords', [])
        return any(keyword.lower() in title.lower() for keyword in exclude_keywords)

    def _is_filtered_by_rating(self, rating: Optional[int]) -> bool:
        min_rating = self.config.get('filters', {}).get('min_rating', 0)
        if rating is None: return True
        return rating < min_rating
