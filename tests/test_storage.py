
import pytest
import datetime
from sqlalchemy import create_engine, inspect
from zoneinfo import ZoneInfo

from inforadar.storage import Storage
from inforadar.models import Article

# Use a timezone-aware datetime object for consistency
UTC = ZoneInfo("UTC")

@pytest.fixture(scope="function")
def storage_instance():
    """Provides a Storage instance connected to an in-memory SQLite database for each test function."""
    storage = Storage(db_url="sqlite:///:memory:")
    storage.init_db()
    yield storage

@pytest.fixture
def article_factory():
    """Provides a factory function to create sample Article objects for testing."""
    def _factory():
        return [
            Article(guid="guid1", link="link1", title="title1", published_date=datetime.datetime.now(UTC)),
            Article(guid="guid2", link="link2", title="title2", published_date=datetime.datetime.now(UTC) - datetime.timedelta(days=1)),
            Article(guid="guid3", link="link3", title="title3", published_date=datetime.datetime.now(UTC) - datetime.timedelta(days=2)),
        ]
    return _factory

def test_init_db(storage_instance):
    """Tests if the database and the 'articles' table are created."""
    inspector = inspect(storage_instance.engine)
    assert "articles" in inspector.get_table_names()

def test_add_articles_no_duplicates(storage_instance, article_factory):
    """Tests adding new articles and ensures duplicates are ignored."""
    # Add new articles
    added_count = storage_instance.add_articles(article_factory())
    assert added_count == 3

    # Try to add the same articles again (using fresh objects from the factory)
    added_count_again = storage_instance.add_articles(article_factory())
    assert added_count_again == 0

    # Verify the total count in the DB
    with storage_instance._Session() as session:
        total_count = session.query(Article).count()
        assert total_count == 3

def test_add_articles_with_some_duplicates(storage_instance, article_factory):
    """Tests adding a list of articles where some already exist in the database."""
    articles = article_factory()
    # Add the first two articles
    storage_instance.add_articles(articles[:2])

    # Attempt to add all three (one is new, two are duplicates)
    # We must use fresh objects for the check
    added_count = storage_instance.add_articles(article_factory())
    assert added_count == 1 # Only the third article should be new

    # Verify the total count in the DB
    with storage_instance._Session() as session:
        total_count = session.query(Article).count()
        assert total_count == 3

def test_update_article_status(storage_instance, article_factory):
    """Tests updating the read and interesting status of an article."""
    storage_instance.add_articles([article_factory()[0]])

    # Get the article to check its initial state
    with storage_instance._Session() as session:
        article = session.query(Article).filter(Article.guid == "guid1").one()
        assert not article.status_read
        assert not article.status_interesting
        article_id = article.id

    # Update status to read
    storage_instance.update_article_status(article_id=article_id, read=True)
    with storage_instance._Session() as session:
        article = session.query(Article).filter(Article.id == article_id).one()
        assert article.status_read
        assert not article.status_interesting

    # Update status to interesting
    storage_instance.update_article_status(article_id=article_id, interesting=True)
    with storage_instance._Session() as session:
        article = session.query(Article).filter(Article.id == article_id).one()
        assert article.status_read
        assert article.status_interesting

    # Update both back to false
    storage_instance.update_article_status(article_id=article_id, read=False, interesting=False)
    with storage_instance._Session() as session:
        article = session.query(Article).filter(Article.id == article_id).one()
        assert not article.status_read
        assert not article.status_interesting

def test_get_articles_by_status(storage_instance, article_factory):
    """Tests fetching articles based on their read/interesting status."""
    storage_instance.add_articles(article_factory())

    # Mark articles with statuses
    storage_instance.update_article_status(article_id=1, read=True) # guid1
    storage_instance.update_article_status(article_id=2, interesting=True) # guid2

    # Get unread articles
    unread_articles = storage_instance.get_articles(read=False)
    assert len(unread_articles) == 2
    assert {article.guid for article in unread_articles} == {"guid2", "guid3"}

    # Get read articles
    read_articles = storage_instance.get_articles(read=True)
    assert len(read_articles) == 1
    assert read_articles[0].guid == "guid1"

    # Get unread and interesting articles
    unread_interesting = storage_instance.get_articles(read=False, interesting=True)
    assert len(unread_interesting) == 1
    assert unread_interesting[0].guid == "guid2"

    # Get unread and not interesting articles
    unread_not_interesting = storage_instance.get_articles(read=False, interesting=False)
    assert len(unread_not_interesting) == 1
    assert unread_not_interesting[0].guid == "guid3"
