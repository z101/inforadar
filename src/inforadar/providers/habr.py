

import time
import random
import requests
import feedparser
import calendar
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, urlunparse
from datetime import datetime, timezone

from ..models import Article
from ..storage import Storage

class HabrProvider:
    """Provider for fetching and enriching articles from Habr.com."""

    def __init__(self, config: Dict[str, Any], storage: Storage):
        self.config = config.get('habr', {})
        self.storage = storage
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }

    def fetch(self) -> List[Article]:
        """Fetches, enriches, and filters articles using the hybrid strategy."""
        all_new_articles = []
        hubs = self.config.get('hubs', [])
        
        for hub in hubs:
            # Step 1: Get articles from RSS
            rss_articles_map = {a.guid: a for a in self._fetch_rss_articles(hub)}
            
            # Step 2: Check for a gap
            last_known_date = self.storage.get_last_article_date(hub)
            oldest_rss_date = min(a.published_date for a in rss_articles_map.values()) if rss_articles_map else None

            scraped_articles_map = {}
            if last_known_date and oldest_rss_date and oldest_rss_date > last_known_date:
                # Step 3: Gap detected, start scraping hub pages
                scraped_articles_map = self._scrape_hub_pages(hub, last_known_date)

            # Step 4: Combine and deduplicate
            combined_articles_map = {**scraped_articles_map, **rss_articles_map}
            
            # Filter out articles older than the last known date
            articles_to_process = [
                article for article in combined_articles_map.values()
                if not last_known_date or article.published_date > last_known_date
            ]

            # Step 5: Enrich and filter
            for article in articles_to_process:
                if self._is_filtered_by_keyword(article.title):
                    continue

                time.sleep(random.uniform(0.1, 0.5)) # Be nice
                extra_data = self._enrich_article_data(article.link)
                article.extra_data.update(extra_data)

                if self._is_filtered_by_rating(extra_data.get('rating')):
                    continue
                
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
                    time_el = article_el.select_one("span.tm-article-datetime-published > time")
                    
                    if not link_el or not time_el: continue

                    link = self._clean_url(f"https://habr.com{link_el['href']}")
                    guid = link
                    if not guid.endswith('/'):
                        guid += '/'
                    
                    title = link_el.text.strip()
                    pub_date = datetime.fromisoformat(time_el['datetime'].replace('Z', '+00:00'))

                    if pub_date <= stop_date:
                        page_is_getting_old = True
                        continue # Skip articles older than or same as stop_date

                    scraped_articles[guid] = Article(
                        guid=guid, link=link, title=title, published_date=pub_date
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

    def _enrich_article_data(self, url: str) -> Dict[str, Any]:
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            rating_text = self._find_text(soup, [".tm-votes-meter__value"])
            comments_text = self._find_text(soup, [".tm-comments-link__comment-count"])

            return {
                'rating': int(rating_text.replace('+', '')) if rating_text else None,
                'views': self._find_text(soup, [".tm-icon-counter__value"]),
                'reading_time': self._find_text(soup, [".tm-article-reading-time__label"]),
                'comments': int(comments_text) if comments_text else None
            }
        except (AttributeError, ValueError, requests.RequestException):
            return {}

    def _is_filtered_by_keyword(self, title: str) -> bool:
        exclude_keywords = self.config.get('filters', {}).get('exclude_keywords', [])
        return any(keyword.lower() in title.lower() for keyword in exclude_keywords)

    def _is_filtered_by_rating(self, rating: Optional[int]) -> bool:
        min_rating = self.config.get('filters', {}).get('min_rating', 0)
        if rating is None: return True
        return rating < min_rating
