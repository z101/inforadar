import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from inforadar.storage import Storage
from inforadar.core import CoreEngine
from inforadar.models import Article

# Use a timezone-aware datetime object for consistency
UTC = ZoneInfo("UTC")

@pytest.fixture(scope="function")
def in_memory_storage():
    """Provides a Storage instance connected to an in-memory SQLite database."""
    storage = Storage(db_url="sqlite:///:memory:")
    storage.init_db()
    return storage

@pytest.fixture
def populated_storage(in_memory_storage):
    """Provides a storage instance populated with dummy articles."""
    articles = [
        # Source 'habr'
        Article(guid="habr1", link="http://example.com/1", source="habr", title="Habr Article 1", published_date=datetime.now(UTC) - timedelta(days=1)),
        Article(guid="habr2", link="http://example.com/2", source="habr", title="Habr Article 2", published_date=datetime.now(UTC) - timedelta(days=2)),
        
        # Source 'medium'
        Article(guid="medium1", link="http://example.com/3", source="medium", title="Medium Article 1", published_date=datetime.now(UTC) - timedelta(days=5)),
        
        # Another article for 'habr' to test max date
        Article(guid="habr3", link="http://example.com/4", source="habr", title="Habr Article 3 (latest)", published_date=datetime.now(UTC) - timedelta(hours=5)),
    ]
    in_memory_storage.add_or_update_articles(articles)
    return in_memory_storage

def test_get_article_count_by_source(populated_storage):
    """Tests that the article count for a source is retrieved correctly."""
    habr_count = populated_storage.get_article_count_by_source("habr")
    medium_count = populated_storage.get_article_count_by_source("medium")
    non_existent_count = populated_storage.get_article_count_by_source("non_existent")

    assert habr_count == 3
    assert medium_count == 1
    assert non_existent_count == 0

def test_get_latest_article_date_by_source(populated_storage):
    """Tests that the latest article date for a source is retrieved correctly."""
    latest_habr_date = populated_storage.get_latest_article_date_by_source("habr")
    
    # We know the latest habr article is ~5 hours old
    expected_latest_date = (datetime.now(UTC) - timedelta(hours=5)).replace(tzinfo=None)
    
    assert latest_habr_date is not None
    # Compare with a tolerance of a few seconds
    assert abs(latest_habr_date - expected_latest_date) < timedelta(seconds=5)

def test_get_sources_summary(populated_storage, mocker):
    """Tests the CoreEngine's ability to generate a summary of sources."""
    # Mock the config to define the sources we expect
    mock_config = {
        'sources': {
            'habr': {'type': 'habr'},
            'medium': {'type': 'medium_mock'},
            'dev.to': {'type': 'devto_mock'} # A source with no articles
        }
    }
    
    # We create a CoreEngine instance but then replace its storage and config
    engine = CoreEngine()
    engine.storage = populated_storage
    engine.config = mock_config
    
    summary = engine.get_sources_summary()
    
    assert len(summary) == 3
    
    habr_summary = next((s for s in summary if s['name'] == 'habr'), None)
    medium_summary = next((s for s in summary if s['name'] == 'medium'), None)
    devto_summary = next((s for s in summary if s['name'] == 'dev.to'), None)

    assert habr_summary is not None
    assert habr_summary['articles_count'] == 3
    expected_habr_date = (datetime.now(UTC) - timedelta(hours=5)).replace(tzinfo=None)
    assert abs(habr_summary['last_sync_date'] - expected_habr_date) < timedelta(seconds=5)

    assert medium_summary is not None
    assert medium_summary['articles_count'] == 1
    
    assert devto_summary is not None
    assert devto_summary['articles_count'] == 0
    assert devto_summary['last_sync_date'] is None
