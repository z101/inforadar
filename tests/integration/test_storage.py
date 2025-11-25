
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
            Article(
                guid="guid1", link="link1", title="title1", published_date=datetime.datetime.now(UTC), 
                extra_data={"rating": 10},
                content_md="# Title 1\nContent 1",
                comments_data=[{"id": 1, "text": "Comment 1"}]
            ),
            Article(guid="guid2", link="link2", title="title2", published_date=datetime.datetime.now(UTC) - datetime.timedelta(days=1)),
            Article(guid="guid3", link="link3", title="title3", published_date=datetime.datetime.now(UTC) - datetime.timedelta(days=2)),
        ]
    return _factory

def test_init_db(storage_instance):
    """Tests if the database and the 'articles' table are created."""
    inspector = inspect(storage_instance.engine)
    assert "articles" in inspector.get_table_names()

def test_add_articles_no_duplicates(storage_instance, article_factory):
    """Tests adding new articles and ensures duplicates are updated, not added."""
    result = storage_instance.add_or_update_articles(article_factory())
    assert result['added'] == 3
    assert result['updated'] == 0
    
    result_again = storage_instance.add_or_update_articles(article_factory())
    assert result_again['added'] == 0
    assert result_again['updated'] == 3
    with storage_instance._Session() as session:
        total_count = session.query(Article).count()
        assert total_count == 3

def test_storage_saves_extra_data(storage_instance, article_factory):
    """Проверяет сохранение и чтение данных из JSON-поля (FT1.3.3)."""
    storage_instance.add_or_update_articles(article_factory())
    with storage_instance._Session() as session:
        article = session.query(Article).filter(Article.guid == "guid1").one()
        assert article.extra_data["rating"] == 10

def test_update_article_status(storage_instance, article_factory):
    """Tests updating the read and interesting status of an article."""
    storage_instance.add_or_update_articles([article_factory()[0]])
    with storage_instance._Session() as session:
        article = session.query(Article).filter(Article.guid == "guid1").one()
        article_id = article.id

    storage_instance.update_article_status(article_id=article_id, read=True, interesting=True)
    with storage_instance._Session() as session:
        article = session.query(Article).filter(Article.id == article_id).one()
        assert article.status_read is True
        assert article.status_interesting is True

def test_storage_saves_content_and_comments(storage_instance, article_factory):
    """Tests saving and retrieving content_md and comments_data."""
    storage_instance.add_or_update_articles(article_factory())
    with storage_instance._Session() as session:
        article = session.query(Article).filter(Article.guid == "guid1").one()
        assert article.content_md == "# Title 1\nContent 1"
        assert article.comments_data == [{"id": 1, "text": "Comment 1"}]
        
        # Check default values for other articles
        article2 = session.query(Article).filter(Article.guid == "guid2").one()
        assert article2.content_md is None
        assert article2.comments_data == []
