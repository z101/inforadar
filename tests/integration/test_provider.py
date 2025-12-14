
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
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
            'filters': {'min_rating': 10, 'exclude_keywords': ['дайджест']},
            'cutoff_date': '2023-01-01',
            'window_days': 30
        }
    }

@pytest.fixture
def mock_storage():
    storage = MagicMock()
    # Default: Article not found
    storage.get_article_by_guid.return_value = None
    return storage

def mock_requests_get(url, headers=None):
    """Custom mock for requests.get to handle different URLs."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    if "page" in url: # Hub page scraping
        # Use existing fixture even if it's for article, just to have HTML.
        # Ideally we need a list page fixture.
        # But let's assume habr_hub_page.html exists from previous tests or I should check.
        # The previous test used it.
        mock_response.text = (FIXTURES_PATH / "habr_hub_page.html").read_text()
    elif "comments" in url: # Comments API
        mock_response.json.return_value = {
            "comments": {
                "1": {
                    "id": 1, "parentId": None, "author": {"login": "user1"}, 
                    "message": "Test comment", "score": 5, "timePublished": "2025-10-24T12:00:00+00:00"
                }
            }
        }
    else: # Article enrichment (if called, but now we scan page)
        mock_response.text = (FIXTURES_PATH / "habr_article.html").read_text() 
    return mock_response

@patch('inforadar.providers.habr.requests.get', side_effect=mock_requests_get)
def test_fetch_basic(mock_requests, mock_config, mock_storage):
    """Tests basic fetch operation scanning a page."""
    
    # Setup storage to simulate no existing articles
    mock_storage.get_article_by_guid.return_value = None

    provider = HabrProvider(source_name='habr', config=mock_config['habr'], storage=mock_storage)
    
    # Mock _fetch_page_items to control loop or ensure it stops?
    # Actual fetch loop stops if items is empty or error.
    # We rely on requests mock returning a page.
    # To prevent infinite loop in test if logic is buggy, we might want to limit pages.
    # But mock_requests_get returns same page always.
    # The provider detects "empty page" if no articles found.
    # If fixtures has articles, it will find them.
    # If it finds them, it processes them.
    # It loops to page 2.
    # If page 2 returns same articles (mock), it will process duplicates?
    # Logic: if item exists (by guid).
    # If I mock requests to return articles on page 1, and NOTHING on page 2.
    
    # We need a dynamic mock for that.
    
    def side_effect(url, headers=None):
        resp = MagicMock()
        resp.status_code = 200
        if "page1" in url:
            resp.text = (FIXTURES_PATH / "habr_hub_page.html").read_text()
        else:
            resp.text = "<html><body></body></html>" # Empty page
        return resp

    mock_requests.side_effect = side_effect
    
    report = provider.fetch()
    
    assert report['errors_count'] == 0
    # Assuming habr_hub_page.html has articles.
    # Previous test said: "Without filtering, we get 4 articles".
    # So we expect Added > 0.
    assert len(report['added_articles']) > 0
    
    # Verify add_article was called
    assert mock_storage.add_article.called

@patch('inforadar.providers.habr.requests.get', side_effect=mock_requests_get)
def test_fetch_existing_update(mock_requests, mock_config, mock_storage):
    """Tests that existing articles are updated (diff)."""
    
    # Mock that article update exists
    existing_article = Article(
        guid="https://habr.com/ru/articles/100000/", # Must match fixture
        link="https://habr.com/ru/articles/100000/",
        title="Old Title",
        extra_data={'views': '100', 'comments': 5}
    )
    mock_storage.get_article_by_guid.return_value = existing_article
    
    def side_effect(url, headers=None):
        resp = MagicMock()
        resp.status_code = 200
        if "page1" in url:
            resp.text = (FIXTURES_PATH / "habr_hub_page.html").read_text()
        else:
            resp.text = "<html><body></body></html>"
        return resp
    mock_requests.side_effect = side_effect

    provider = HabrProvider(source_name='habr', config=mock_config['habr'], storage=mock_storage)
    
    report = provider.fetch()
    
    # Should update because Title or Metadata changed in HTML vs DB object
    assert len(report['updated_articles']) > 0
    assert mock_storage.update_article_fields.called

