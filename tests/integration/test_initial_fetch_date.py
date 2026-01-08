
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from inforadar.sources.habr import HabrSource
from inforadar.models import Article

FIXTURES_PATH = Path(__file__).parent / "fixtures"
UTC = ZoneInfo("UTC")

def mock_requests_get(url, headers=None):
    """Custom mock for requests.get."""
    mock_response = MagicMock()
    mock_response.text = (FIXTURES_PATH / "habr_hub_page.html").read_text()
    return mock_response

@patch('inforadar.sources.habr.requests.get', side_effect=mock_requests_get)
def test_cutoff_date_filters_old_articles(mock_requests):
    """Tests that cutoff_date filters out old articles."""
    
    mock_storage = MagicMock()
    # Mock no existing articles
    mock_storage.get_article_by_guid.return_value = None
    
    # Config with cutoff_date set to 2025-01-01
    mock_config = {
        'habr': {
            'hubs': ['python'],
            'cutoff_date': '2025-01-01'
        }
    }
    
    provider = HabrSource(source_name='habr', config=mock_config['habr'], storage=mock_storage)
    
    # We need to ensure the mocked HTML contains articles older than 2025-01-01 if we want to test filtering?
    # Or cleaner: mock _fetch_page_items to return specific objects with dates.
    
    # But let's rely on provider logic.
    # If we mocked provider._fetch_page_items:
    
    with patch.object(provider, '_fetch_page_items') as mock_fetch_items:
        # Return 2 articles: one old, one new
        old_article = Article(guid='old', link='old', title='Old', published_date=datetime(2024, 12, 31, tzinfo=UTC), source='habr', extra_data={})
        new_article = Article(guid='new', link='new', title='New', published_date=datetime(2025, 1, 2, tzinfo=UTC), source='habr', extra_data={})
        
        mock_fetch_items.side_effect = [[old_article, new_article], []] # Page 1, then Page 2 empty
        
        report = provider.fetch()
        
        # Should add only new_article
        assert len(report['added_articles']) == 1
        assert 'new' in report['added_articles']
        assert 'old' not in report['added_articles']
