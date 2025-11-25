
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

FIXTURES_PATH = Path(__file__).parent.parent.parent / "integration/fixtures"

@pytest.fixture
def mock_config():
    """Общая мок-конфигурация."""
    return {
        'habr': {
            'hubs': ['python'],
            'filters': {'min_rating': 10, 'exclude_keywords': ['дайджест']}
        }
    }

@pytest.fixture
def mock_requests_get():
    """Мок для requests.get, который будет использоваться в BDD."""
    def _mock_get(url, headers=None):
        mock_response = MagicMock()
        if "articles/page" in url:
            mock_response.text = (FIXTURES_PATH / "habr_hub_page.html").read_text()
        else:
            mock_response.text = (FIXTURES_PATH / "habr_article.html").read_text()
        return mock_response

    with patch('inforadar.providers.habr.requests.get', side_effect=_mock_get) as mock:
        yield mock

@pytest.fixture
def mock_feedparser():
    """Мок для feedparser."""
    with patch('inforadar.providers.habr.feedparser') as mock:
        yield mock
