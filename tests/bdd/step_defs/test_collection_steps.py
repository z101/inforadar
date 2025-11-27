
from pytest_bdd import scenario, given, when, then, parsers
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import feedparser
from datetime import datetime, timezone

from inforadar.providers.habr import HabrProvider
from inforadar.storage import Storage
from inforadar.models import Article

FIXTURES_PATH = Path(__file__).parent.parent.parent / "integration/fixtures"

@scenario('../features/data_collection.feature', 'Сбор данных при наличии разрыва в RSS')
def test_data_collection_with_gap():
    pass

@scenario('../features/data_collection.feature', 'Сохранение всех метаданных статьи')
def test_metadata_storage():
    pass

@pytest.fixture
def context():
    """Контекст для передачи данных между шагами."""
    return {}

# --- Шаги для первого сценария ---

@given(parsers.parse('В базе данных есть статья с датой "{date_str}"'), target_fixture="mock_storage")
def mock_storage_with_date(date_str):
    storage = MagicMock()
    storage.get_last_article_date.return_value = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    return storage

@given('RSS-фид содержит статьи только за "2025-10-24"')
def mock_rss_feed(mock_feedparser):
    rss_content = (FIXTURES_PATH / "habr_rss.xml").read_text()
    mock_feedparser.parse.return_value = feedparser.parse(rss_content)

@given('Страница хаба содержит статью за "2025-10-23"')
def mock_hub_page(mock_requests_get):
    # Это уже настроено в conftest.py, но можно было бы и здесь
    pass

@when('Пользователь запускает сбор данных', target_fixture="collected_articles")
def run_data_collection(mock_storage, mock_config):
    provider = HabrProvider(source_name='habr', config=mock_config['habr'], storage=mock_storage)
    return provider.fetch()

@then(parsers.parse('Должно быть собрано {count:d} новые статьи'))
def check_article_count(collected_articles, count):
    # Without filtering, we expect all articles including digest
    assert len(collected_articles) == count

# --- Шаги для второго сценария ---

@given('Найдена одна новая статья', target_fixture="single_article")
def single_new_article():
    article = Article(
        guid="test-guid",
        link="http://test.link",
        title="Test Title",
        published_date=datetime.now(timezone.utc),
        extra_data={"rating": 99, "views": "10K"}
    )
    return article

@when('Статья сохраняется в базу данных', target_fixture="saved_article")
def save_article_to_db(single_article):
    storage = Storage(db_url="sqlite:///:memory:")
    storage.init_db()
    storage.add_or_update_articles([single_article])
    
    with storage._Session() as session:
        return session.query(Article).filter_by(guid="test-guid").one()

@then('В базе данных у этой статьи должен быть уникальный GUID')
def check_guid(saved_article):
    assert saved_article.guid == "test-guid"

@then('В базе данных у этой статьи в JSON-поле должен быть рейтинг')
def check_json_rating(saved_article):
    assert "rating" in saved_article.extra_data
    assert saved_article.extra_data["rating"] == 99
