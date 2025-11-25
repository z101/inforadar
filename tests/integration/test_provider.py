
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
    mock_response.status_code = 200
    if "page" in url: # Hub page scraping
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
    else: # Article enrichment
        mock_response.text = (FIXTURES_PATH / "habr_article.html").read_text()
    return mock_response

@patch('inforadar.providers.habr.requests.get', side_effect=mock_requests_get)
@patch('inforadar.providers.habr.feedparser')
def test_fetch_with_gap(mock_feedparser, mock_requests, mock_config, mock_storage):
    """Tests hybrid fetch: RSS has a gap, so page scraping is triggered (FT1.2.2, FT1.2.3)."""
    rss_content = (FIXTURES_PATH / "habr_rss.xml").read_text()
    mock_feedparser.parse.return_value = feedparser.parse(rss_content)
    mock_storage.get_last_article_date.return_value = datetime(2025, 10, 22, 18, 0, 0, tzinfo=UTC)

    provider = HabrProvider(config=mock_config, storage=mock_storage)
    articles = provider.fetch()

    # Without filtering, we get all 4 articles (including digest)
    assert len(articles) == 4
    guids = {a.guid for a in articles}
    assert "https://habr.com/ru/articles/100001/" in guids
    assert "https://habr.com/ru/articles/100000/" in guids


@patch('inforadar.providers.habr.requests.get', side_effect=mock_requests_get)
@patch('inforadar.providers.habr.feedparser')
def test_fetch_no_gap(mock_feedparser, mock_requests, mock_config, mock_storage):
    """Tests hybrid fetch: RSS is sufficient, no page scraping needed (FT1.2.2)."""
    rss_content = (FIXTURES_PATH / "habr_rss.xml").read_text()
    mock_feedparser.parse.return_value = feedparser.parse(rss_content)
    mock_storage.get_last_article_date.return_value = datetime(2025, 10, 24, 10, 30, 0, tzinfo=UTC)

    provider = HabrProvider(config=mock_config, storage=mock_storage)
    articles = provider.fetch()
    
    # Without filtering, we get 2 articles (Article 2 and Digest)
    assert len(articles) == 2
    # 2 articles * (1 page request + 1 comments request) = 4 requests
    assert mock_requests.call_count == 4
    for call in mock_requests.call_args_list:
        assert "articles/page" not in call.args[0]

@patch('inforadar.providers.habr.requests.get')
def test_provider_uses_user_agent(mock_get, mock_config, mock_storage):
    """Проверяет, что провайдер использует User-Agent (NFT1.1.1)."""
    provider = HabrProvider(config=mock_config, storage=mock_storage)
    mock_get.return_value.text = "<html></html>"
    # Вызываем внутренний метод, чтобы проверить один конкретный вызов
    provider._enrich_article_data("http://fake.url")
    mock_get.assert_called_once()
    # Проверяем, что в вызове были переданы headers
    call_args, call_kwargs = mock_get.call_args
    assert "headers" in call_kwargs
    assert "User-Agent" in call_kwargs["headers"]
    assert "User-Agent" in call_kwargs["headers"]

@patch('inforadar.providers.habr.requests.get', side_effect=mock_requests_get)
@patch('inforadar.providers.habr.feedparser')
def test_content_and_comments_extraction(mock_feedparser, mock_requests, mock_config, mock_storage):
    """Tests that content and comments are correctly extracted (FT1.3.4)."""
    rss_content = (FIXTURES_PATH / "habr_rss.xml").read_text()
    mock_feedparser.parse.return_value = feedparser.parse(rss_content)
    mock_storage.get_last_article_date.return_value = datetime(2025, 10, 24, 10, 30, 0, tzinfo=UTC)

    provider = HabrProvider(config=mock_config, storage=mock_storage)
    articles = provider.fetch()
    
    article = articles[0]
    # Check content extraction (mocked HTML has some content)
    assert article.content_md is not None
    # Check comments extraction (mocked API returns 1 comment)
    assert len(article.comments_data) == 1
    assert article.comments_data[0]['author'] == 'user1'
    assert article.comments_data[0]['text'] == 'Test comment'
