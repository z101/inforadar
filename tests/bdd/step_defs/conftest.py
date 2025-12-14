
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import requests_mock as req_mock

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
def requests_mock(request):
    """Фикстура requests-mock, которая автоматически активируется для тестов."""
    with req_mock.Mocker() as m:
        yield m

@pytest.fixture
def mock_feedparser():
    """Мок для feedparser."""
    with patch('inforadar.providers.habr.feedparser') as mock:
        yield mock
