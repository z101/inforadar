import yaml
from pathlib import Path
from appdirs import AppDirs
from sqlalchemy.orm import sessionmaker
from typing import Any, Optional
import logging

from inforadar.models import Setting

log = logging.getLogger(__name__)

# Define app-specific details
APP_NAME = "inforadar"
APP_AUTHOR = "inforadar"
_dirs = AppDirs(APP_NAME, APP_AUTHOR)


def get_db_path() -> Path:
    """
    Determines the path to the database file.

    It first checks for a `user_config.yml` in the user's config directory.
    If `database_path` is specified there, it's used.
    Otherwise, it defaults to the user's data directory.

    Returns:
        Path object for the database file.
    """
    config_path = Path(_dirs.user_config_dir) / "user_config.yml"
    default_db_path = Path(_dirs.user_data_dir) / "inforadar.db"

    if not config_path.is_file():
        return default_db_path

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            user_config = yaml.safe_load(f)
        
        if user_config and 'database_path' in user_config:
            # Path in config can be relative to user's home or absolute
            db_path_str = user_config['database_path']
            return Path(db_path_str).expanduser()

    except Exception as e:
        log.error(f"Failed to read user config at {config_path}: {e}")
    
    return default_db_path


def get_db_url() -> str:
    """
    Constructs the SQLAlchemy database URL from the DB path.
    """
    path = get_db_path()
    # Ensure the parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


class SettingsManager:
    """
    Manages loading and accessing settings from the database.
    """

    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory
        self._settings = {}

    def load_settings(self):
        """
        Loads all settings from the 'settings' table into a nested dictionary.
        """
        log.info("Loading settings from database...")
        self._settings = {}
        try:
            with self._session_factory() as session:
                all_settings = session.query(Setting).all()

                for setting in all_settings:
                    self._set_nested_key(self._settings, setting.key, setting)
            log.info(f"Loaded {len(all_settings)} settings.")
        except Exception as e:
            # This can happen if DB is not initialized yet.
            # It's safe to proceed with empty settings.
            log.warning(f"Could not load settings from database: {e}. Using defaults.")

    def _set_nested_key(self, data: dict, key: str, setting: Setting):
        """
        Sets a value in a nested dictionary based on a dot-separated key.
        """
        keys = key.split('.')
        current_level = data
        for i, part in enumerate(keys):
            if i == len(keys) - 1:
                current_level[part] = self._convert_value(setting.value, setting.type)
            else:
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]

    def _convert_value(self, value: str, type_str: str) -> Any:
        """
        Converts a string value to its proper type.
        """
        if type_str == 'integer':
            return int(value)
        if type_str == 'boolean':
            return value.lower() in ('true', '1', 'yes')
        if type_str == 'list':
            return [item.strip() for item in value.split(',')]
        return value  # 'string'

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Retrieves a setting value using a dot-separated key.

        Args:
            key: The dot-separated key (e.g., 'fetch.habr.hubs').
            default: The value to return if the key is not found.

        Returns:
            The setting value or the default.
        """
        keys = key.split('.')
        current_level = self._settings
        for part in keys:
            if isinstance(current_level, dict) and part in current_level:
                current_level = current_level[part]
            else:
                return default
        return current_level

    @property
    def all_settings(self) -> dict:
        """Returns the entire nested settings dictionary."""
        return self._settings