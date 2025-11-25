import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from inforadar.storage import Storage
from inforadar.models import Article, Base

UTC = ZoneInfo("UTC")

@pytest.fixture
def storage_with_articles():
    """Creates a storage with some test articles."""
    storage = Storage("sqlite:///:memory:")
    storage.init_db()
    
    # Create articles with different dates and statuses
    now = datetime.now(UTC)
    
    articles = [
        # Recent, unread (should be refreshed)
        Article(
            guid="guid1", link="link1", title="Recent Unread",
            published_date=now - timedelta(days=1),
            status_read=False, extra_data={}
        ),
        # Recent, read (should be refreshed if unread_only=False)
        Article(
            guid="guid2", link="link2", title="Recent Read",
            published_date=now - timedelta(days=2),
            status_read=True, extra_data={}
        ),
        # Old, unread (should NOT be refreshed with 7 days limit)
        Article(
            guid="guid3", link="link3", title="Old Unread",
            published_date=now - timedelta(days=10),
            status_read=False, extra_data={}
        ),
    ]
    
    storage.add_or_update_articles(articles)
    return storage

def test_get_articles_for_refresh_unread_only(storage_with_articles):
    """Tests fetching articles for refresh with unread_only=True."""
    cutoff_date = datetime.now(UTC) - timedelta(days=7)
    
    articles = storage_with_articles.get_articles_for_refresh(
        after_date=cutoff_date,
        read=False
    )
    
    titles = {a.title for a in articles}
    assert "Recent Unread" in titles
    assert "Recent Read" not in titles
    assert "Old Unread" not in titles

def test_get_articles_for_refresh_all(storage_with_articles):
    """Tests fetching articles for refresh with unread_only=False."""
    cutoff_date = datetime.now(UTC) - timedelta(days=7)
    
    articles = storage_with_articles.get_articles_for_refresh(
        after_date=cutoff_date,
        read=None
    )
    
    titles = {a.title for a in articles}
    assert "Recent Unread" in titles
    assert "Recent Read" in titles
    assert "Old Unread" not in titles

def test_update_article_metadata(storage_with_articles):
    """Tests updating article metadata."""
    # Get an article ID
    articles = storage_with_articles.get_articles(read=False)
    article = articles[0]
    original_id = article.id
    
    # Update metadata
    new_data = {'rating': 100, 'views': 5000}
    success = storage_with_articles.update_article_metadata(original_id, new_data)
    
    assert success is True
    
    # Verify update
    updated_article = storage_with_articles._Session().query(Article).get(original_id)
    assert updated_article.extra_data['rating'] == 100
    assert updated_article.extra_data['views'] == 5000
