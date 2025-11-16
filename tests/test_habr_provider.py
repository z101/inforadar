
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import feedparser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from inforadar.models import Article
from inforadar.providers.habr import HabrProvider

FIXTURES_PATH = Path(__file__).parent / "fixtures"
UTC = ZoneInfo("UTC")

@pytest.fixture
def mock_config():
    return {
        'habr': {
            'hubs': ['python'],
            'filters': {'min_rating': 10, 'exclude_keywords': ['дайджест']}
        }
    }

@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.get_last_article_date.return_value = None
    return storage

def mock_requests_get(url, headers=None):
    """Custom mock for requests.get to handle different URLs."""
    mock_response = MagicMock()
    if "articles" in url: # Article enrichment
        mock_response.text = (FIXTURES_PATH / "habr_article.html").read_text()
    else: # Hub page scraping
        mock_response.text = (FIXTURES_PATH / "habr_hub_page.html").read_text()
    return mock_response

@patch('inforadar.providers.habr.requests.get', side_effect=mock_requests_get)
@patch('inforadar.providers.habr.feedparser')
def test_fetch_with_gap(mock_feedparser, mock_requests, mock_config, mock_storage):
    """
    Tests hybrid fetch: RSS has a gap, so page scraping is triggered.
    """
    # --- Setup ---
    # RSS feed (oldest article is from Oct 24)
    rss_content = (FIXTURES_PATH / "habr_rss.xml").read_text()
    mock_feedparser.parse.return_value = feedparser.parse(rss_content)
    
    # DB has an article from Oct 22, creating a gap on Oct 23
    mock_storage.get_last_article_date.return_value = datetime(2025, 10, 22, 18, 0, 0, tzinfo=UTC)

    # --- Action ---
    provider = HabrProvider(config=mock_config, storage=mock_storage)
    articles = provider.fetch()

    # --- Assertions ---
    # We expect 3 articles:
    # 2 from RSS (guid1, guid2)
    # 1 from hub page scrape (guid0)
    # "Дайджест" (guid3) is filtered out by keyword
    # "Старая статья" (guid99999) is skipped because it's older than last_known_date
    assert len(articles) == 3
    guids = {a.guid for a in articles}
    assert "https://habr.com/ru/articles/100001/" in guids
    assert "https://habr.com/ru/articles/100002/" in guids
    assert "https://habr.com/ru/articles/100000/" in guids
    
    # Check that hub page scraping was called
    hub_page_url = "https://habr.com/ru/hubs/python/articles/page1/"
    mock_requests.assert_any_call(hub_page_url, headers=provider.headers)


@patch('inforadar.providers.habr.requests.get', side_effect=mock_requests_get)
@patch('inforadar.providers.habr.feedparser')
def test_fetch_no_gap(mock_feedparser, mock_requests, mock_config, mock_storage):
    """
    Tests hybrid fetch: RSS is sufficient, no page scraping needed.
    """
    # --- Setup ---
    rss_content = (FIXTURES_PATH / "habr_rss.xml").read_text()
    mock_feedparser.parse.return_value = feedparser.parse(rss_content)
    
    # DB has a recent article, no gap exists
    mock_storage.get_last_article_date.return_value = datetime(2025, 10, 24, 9, 0, 0, tzinfo=UTC)

    # --- Action ---
    provider = HabrProvider(config=mock_config, storage=mock_storage)
    articles = provider.fetch()

    # --- Assertions ---
    # We expect 2 articles from RSS that are newer than the last known date.
    # "Дайджест" is filtered out.
    assert len(articles) == 2
    guids = {a.guid for a in articles}
    assert "https://habr.com/ru/articles/100001/" in guids
    assert "https://habr.com/ru/articles/100002/" in guids

    # Check that hub page scraping was NOT called
    # We do this by checking the call count for requests.get
    # It should be called twice for enrichment, but never for a hub page.
    enrichment_call_count = 2
    assert mock_requests.call_count == enrichment_call_count
    for call in mock_requests.call_args_list:
        assert "articles/page" not in call.args[0]
