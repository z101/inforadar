

import time
import random
import requests
import feedparser
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urlunparse
from datetime import datetime

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
        """Fetches, enriches, and filters articles from all configured Habr hubs."""
        all_new_articles = []
        hubs = self.config.get('hubs', [])
        
        for hub in hubs:
            rss_articles = self._fetch_rss_articles(hub)
            for article in rss_articles:
                if self._is_filtered_by_keyword(article.title):
                    continue

                time.sleep(random.uniform(0.5, 1.5))
                extra_data = self._enrich_article_data(article.link)
                article.extra_data.update(extra_data)

                if self._is_filtered_by_rating(extra_data.get('rating')):
                    continue
                
                all_new_articles.append(article)

        return all_new_articles

    def _clean_url(self, url: str) -> str:
        """Removes UTM tracking parameters from a URL."""
        u = urlparse(url)
        return urlunparse((u.scheme, u.netloc, u.path, "", "", ""))

    def _fetch_rss_articles(self, hub: str) -> List[Article]:
        """Fetches articles from a specific hub's RSS feed."""
        url = f"https://habr.com/ru/rss/hubs/{hub}/articles/?with_tags=true"
        feed = feedparser.parse(url)
        
        articles = []
        for entry in feed.entries:
            published_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
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

    def _find_text(self, soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
        """Tries a list of selectors and returns the text of the first match."""
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.text.strip()
        return None

    def _enrich_article_data(self, url: str) -> Dict[str, Any]:
        """Scrapes a single article page to get extra metadata."""
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
        if rating is None:
            return True
        return rating < min_rating
