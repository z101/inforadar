import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import feedparser
from datetime import datetime
from zoneinfo import ZoneInfo

from inforadar.providers.habr import HabrProvider

FIXTURES_PATH = Path(__file__).parent / "fixtures"
UTC = ZoneInfo("UTC")

def mock_requests_get(url, headers=None):
    """Custom mock for requests.get to handle different URLs."""
    mock_response = MagicMock()
    mock_response.text = (FIXTURES_PATH / "habr_article.html").read_text()
    return mock_response


@patch('inforadar.providers.habr.requests.get', side_effect=mock_requests_get)
@patch('inforadar.providers.habr.feedparser')
def test_initial_fetch_date_filters_old_articles(mock_feedparser, mock_requests):
    """Tests that initial_fetch_date filters out old articles on first run."""
    rss_content = (FIXTURES_PATH / "habr_rss.xml").read_text()
    mock_feedparser.parse.return_value = feedparser.parse(rss_content)
    
    # Empty database (first run)
    mock_storage = MagicMock()
    mock_storage.get_last_article_date.return_value = None
    
    # Config with initial_fetch_date set to 2025-10-24 11:30:00
    # This should filter out Article 1 (10:00) but keep Article 2 (11:00) and Digest (12:00)
    mock_config = {
        'habr': {
            'hubs': ['python'],
            'initial_fetch_date': '2025-10-24 10:30:00'
        }
    }
    
    provider = HabrProvider(config=mock_config, storage=mock_storage)
    articles = provider.fetch()
    
    # Should get 2 articles: Article 2 (11:00) and Digest (12:00)
    # Article 1 (10:00) is filtered by initial_fetch_date
    assert len(articles) == 2
    titles = {a.title for a in articles}
    assert "Статья 2: Про asyncio" in titles
    assert "Еженедельный Дайджест новостей" in titles


@patch('inforadar.providers.habr.requests.get', side_effect=mock_requests_get)
@patch('inforadar.providers.habr.feedparser')
def test_initial_fetch_date_not_used_on_subsequent_runs(mock_feedparser, mock_requests):
    """Tests that initial_fetch_date is ignored when database has articles."""
    rss_content = (FIXTURES_PATH / "habr_rss.xml").read_text()
    mock_feedparser.parse.return_value = feedparser.parse(rss_content)
    
    # Database has articles (not first run)
    mock_storage = MagicMock()
    mock_storage.get_last_article_date.return_value = datetime(2025, 10, 24, 10, 30, 0, tzinfo=UTC)
    
    # Config with initial_fetch_date - should be ignored
    mock_config = {
        'habr': {
            'hubs': ['python'],
            'initial_fetch_date': '2025-10-01 00:00:00'  # Very old date, should be ignored
        }
    }
    
    provider = HabrProvider(config=mock_config, storage=mock_storage)
    articles = provider.fetch()
    
    # Should use last_known_date (10:30), not initial_fetch_date
    # Gets Article 2 (11:00) and Digest (12:00)
    assert len(articles) == 2
