import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import feedparser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from inforadar.providers.habr import HabrProvider
from inforadar.models import Article

FIXTURES_PATH = Path(__file__).parent / "fixtures"
UTC = ZoneInfo("UTC")

def mock_requests_get(url, headers=None):
    """Custom mock for requests.get."""
    mock_response = MagicMock()
    mock_response.text = (FIXTURES_PATH / "habr_article.html").read_text()
    return mock_response

@patch('inforadar.providers.habr.requests.get', side_effect=mock_requests_get)
@patch('inforadar.providers.habr.feedparser')
def test_auto_update_recent_articles(mock_feedparser, mock_requests):
    """Tests that articles within auto-update threshold are re-processed."""
    rss_content = (FIXTURES_PATH / "habr_rss.xml").read_text()
    mock_feedparser.parse.return_value = feedparser.parse(rss_content)
    
    # Setup storage with an existing article that is RECENT (e.g. yesterday)
    # RSS fixture has articles from 2025-10-24.
    # Let's pretend "now" is 2025-10-25.
    
    # Article 2 in RSS is from 2025-10-24 11:00:00
    mock_storage = MagicMock()
    # Last known date is AFTER the RSS article, so normally it would be filtered out
    mock_storage.get_last_article_date.return_value = datetime(2025, 10, 25, 10, 0, 0, tzinfo=UTC)
    
    # Config: auto-update 3 days
    mock_config = {
        'habr': {
            'hubs': ['python'],
            'auto_update_within_days': 3
        }
    }
    
    # We need to mock datetime.now to control the "recent" check
    with patch('inforadar.providers.habr.datetime') as mock_datetime:
        # Set "now" to 2025-10-25
        mock_datetime.now.return_value = datetime(2025, 10, 25, 12, 0, 0, tzinfo=UTC)
        mock_datetime.fromisoformat = datetime.fromisoformat # Keep original method
        mock_datetime.fromtimestamp = datetime.fromtimestamp # Keep original method
        
        provider = HabrProvider(config=mock_config, storage=mock_storage)
        articles = provider.fetch()
        
        # Article 2 (2025-10-24) is older than last_known_date (2025-10-25)
        # BUT it is within 3 days of "now" (2025-10-25)
        # So it SHOULD be included for update
        
        titles = {a.title for a in articles}
        assert "Статья 2: Про asyncio" in titles
        
        # Digest (2025-10-24 12:00) should also be included
        assert "Еженедельный Дайджест новостей" in titles


@patch('inforadar.providers.habr.requests.get', side_effect=mock_requests_get)
@patch('inforadar.providers.habr.feedparser')
def test_no_auto_update_old_articles(mock_feedparser, mock_requests):
    """Tests that old articles are NOT re-processed."""
    rss_content = (FIXTURES_PATH / "habr_rss.xml").read_text()
    mock_feedparser.parse.return_value = feedparser.parse(rss_content)
    
    mock_storage = MagicMock()
    mock_storage.get_last_article_date.return_value = datetime(2025, 10, 25, 10, 0, 0, tzinfo=UTC)
    
    # Config: auto-update 3 days
    mock_config = {
        'habr': {
            'hubs': ['python'],
            'auto_update_within_days': 3
        }
    }
    
    with patch('inforadar.providers.habr.datetime') as mock_datetime:
        # Set "now" to 2025-11-01 (more than 3 days after 2025-10-24)
        mock_datetime.now.return_value = datetime(2025, 11, 1, 12, 0, 0, tzinfo=UTC)
        mock_datetime.fromisoformat = datetime.fromisoformat
        mock_datetime.fromtimestamp = datetime.fromtimestamp
        
        provider = HabrProvider(config=mock_config, storage=mock_storage)
        articles = provider.fetch()
        
        # Articles from 2025-10-24 are > 3 days old relative to 2025-11-01
        # And they are older than last_known_date (2025-10-25)
        # So they should NOT be included
        
        assert len(articles) == 0
