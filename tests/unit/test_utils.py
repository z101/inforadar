
import pytest
from unittest.mock import MagicMock, patch
import requests
from inforadar.config import load_config
from inforadar.providers.habr import HabrProvider


def test_config_loader_success(tmp_path):
    """Проверяет успешную загрузку YAML конфига."""
    config_content = "habr:\n  hubs:\n    - python"
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_content)
    config = load_config(str(config_file))
    assert config['habr']['hubs'] == ['python']

def test_config_loader_file_not_found():
    """Проверяет, что падает ошибка, если файл не найден."""
    with pytest.raises(FileNotFoundError):
        load_config("non_existent_file.yml")

def test_habr_url_cleaner():
    """Проверяет, что из URL удаляются UTM-метки."""
    provider = HabrProvider(source_name='habr', config={}, storage=MagicMock())
    dirty_url = "https://habr.com/ru/articles/123/?utm_source=habrahabr"
    clean_url = "https://habr.com/ru/articles/123/"
    assert provider._clean_url(dirty_url) == clean_url

@patch('inforadar.providers.habr.requests.get')
def test_provider_handles_network_error(mock_get):
    """Проверяет, что скрапер не падает при ошибке сети и логирует ошибку."""
    mock_get.side_effect = requests.exceptions.RequestException("Connection error")
    
    # We need to ensure _process_hub handles the error.
    # In my implementation, _process_hub catches exception?
    # Wait, _fetch_page_items catches RequestException and returns None.
    # Base fetch loop sees None and increments error_count.
    
    provider = HabrProvider(source_name='habr', config={'hubs': ['py_hub']}, storage=MagicMock())
    
    report = provider.fetch()
    
    assert report['errors_count'] > 0
