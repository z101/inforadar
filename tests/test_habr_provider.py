
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import feedparser

from inforadar.models import Article
from inforadar.providers.habr import HabrProvider

# Определяем путь к фикстурам
FIXTURES_PATH = Path(__file__).parent / "fixtures"

@pytest.fixture
def mock_config():
    """Мок конфигурации для Habr."""
    return {
        'habr': {
            'hubs': ['python'],
            'filters': {
                'min_rating': 10,
                'exclude_keywords': ['дайджест']
            }
        }
    }

@pytest.fixture
def mock_storage():
    """Мок хранилища."""
    storage = MagicMock()
    storage.add_articles.return_value = 0
    return storage

@patch('inforadar.providers.habr.feedparser')
def test_rss_parsing_and_cleaning(mock_feedparser):
    """Тестирует парсинг RSS, очистку URL и извлечение тегов."""
    rss_content = (FIXTURES_PATH / "habr_rss.xml").read_text()
    mock_feedparser.parse.return_value = feedparser.parse(rss_content)

    provider = HabrProvider(config={}, storage=MagicMock())
    articles = provider._fetch_rss_articles('python')

    assert len(articles) == 3
    # Проверяем очистку URL
    assert articles[0].link == "https://habr.com/ru/articles/100001/"
    # Проверяем извлечение тегов
    assert articles[0].extra_data['tags'] == ["python", "programming"]
    assert articles[1].extra_data['tags'] == ["python", "asyncio"]

@patch('inforadar.providers.habr.requests')
def test_article_enrichment(mock_requests):
    """Тестирует, что провайдер правильно обогащает статью данными из HTML."""
    mock_response = MagicMock()
    mock_response.text = (FIXTURES_PATH / "habr_article.html").read_text()
    mock_requests.get.return_value = mock_response

    provider = HabrProvider(config={}, storage=MagicMock())
    extra_data = provider._enrich_article_data("http://fake.url")

    assert extra_data['rating'] == 25
    assert extra_data['views'] == "15.9K"
    assert extra_data['reading_time'] == "5 мин"
    assert extra_data['comments'] == 12

@patch('inforadar.providers.habr.requests')
@patch('inforadar.providers.habr.feedparser')
def test_full_fetch_and_filter_logic(mock_feedparser, mock_requests, mock_config, mock_storage):
    """Интеграционный тест: проверяет весь процесс от сбора до фильтрации."""
    rss_content = (FIXTURES_PATH / "habr_rss.xml").read_text()
    mock_feedparser.parse.return_value = feedparser.parse(rss_content)

    mock_response = MagicMock()
    mock_response.text = (FIXTURES_PATH / "habr_article.html").read_text()
    mock_requests.get.return_value = mock_response
    
    provider = HabrProvider(config=mock_config, storage=mock_storage)
    fetched_articles = provider.fetch()

    assert len(fetched_articles) == 2

    article1 = next(a for a in fetched_articles if a.guid == "https://habr.com/ru/articles/100001/")
    assert article1.extra_data['rating'] == 25
    # Проверяем, что теги из RSS сохранились после обогащения
    assert article1.extra_data['tags'] == ["python", "programming"]

    mock_config['habr']['filters']['min_rating'] = 30
    provider_strict = HabrProvider(config=mock_config, storage=mock_storage)
    fetched_strict = provider_strict.fetch()
    assert len(fetched_strict) == 0
