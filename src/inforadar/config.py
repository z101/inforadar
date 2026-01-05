import yaml
import json
from pathlib import Path
from appdirs import AppDirs
from sqlalchemy.orm import sessionmaker
from typing import Any, Optional
import logging
import ast
import logging

from inforadar.models import Setting, SettingListItem, SettingCustomField
from inforadar.tui.schemas import CUSTOM_TYPE_SCHEMAS

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
                current_level[part] = self._convert_value(setting)
            else:
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]

    def _convert_value(self, setting: Setting) -> Any:
        """
        Converts a setting value to its proper type based on the setting's type.
        """
        value = setting.value
        type_str = setting.type

        # Normalize legacy 'habr_hubs' type to 'custom'
        if type_str == 'habr_hubs':
            type_str = 'custom'

        if type_str == 'integer':
            return int(value)
        if type_str == 'boolean':
            return value.lower() in ('true', '1', 'yes')
        if type_str == 'date':
            return value  # Keep as string for now, could parse to datetime if needed
        if type_str == 'list':
            # For list type, we need to load the list items from the SettingListItem table
            with self._session_factory() as session:
                list_items = session.query(SettingListItem).filter_by(setting_key=setting.key).order_by(SettingListItem.item_index).all()
                return [item.item_value for item in list_items]
        if type_str == 'custom':
            # For custom type, we need to load the custom fields from the SettingCustomField table
            with self._session_factory() as session:
                custom_fields = session.query(SettingCustomField).filter_by(setting_key=setting.key).all()
                
                # If custom fields are present, use them
                if custom_fields:
                    schema = CUSTOM_TYPE_SCHEMAS.get(setting.key, {})
                    type_map = {f["name"]: f.get("type", "str") for f in schema.get("fields", [])}

                    def _cast_value(val_str: str, type_name: str) -> Any:
                        if val_str is None or val_str == '':
                            return None
                        try:
                            if type_name == "int":
                                return int(val_str)
                            if type_name == "float":
                                return float(val_str)
                            if type_name == "bool":
                                return val_str.lower() in ('true', '1', 'yes')
                        except (ValueError, TypeError):
                            return None # Gracefully handle casting errors
                        return val_str

                    items = {}
                    for field in custom_fields:
                        parts = field.field_name.split('_')
                        if len(parts) > 1 and parts[-1].isdigit():
                            idx = int(parts[-1])
                            field_name = '_'.join(parts[:-1])
                        else:
                            idx = 0
                            field_name = field.field_name

                        if idx not in items:
                            items[idx] = {}

                        field_type = type_map.get(field_name, "str")
                        items[idx][field_name] = _cast_value(field.field_value, field_type)
                        
                    return [items[key] for key in sorted(items.keys())]
                
                # Fallback: if no custom fields, try to parse from the 'value' column
                # This handles initial migration data or corrupted states
                if value:
                    try:
                        # Try parsing as JSON first (double quotes)
                        return json.loads(value)
                    except json.JSONDecodeError:
                        try:
                            # If JSON fails, try Python literal_eval (single quotes)
                            parsed_value = ast.literal_eval(value)
                            if isinstance(parsed_value, list):
                                # Handle list of strings (legacy format)
                                if parsed_value and all(isinstance(i, str) for i in parsed_value):
                                    schema = CUSTOM_TYPE_SCHEMAS.get(setting.key)
                                    if schema and schema.get("fields"):
                                        id_field = schema["fields"][0]["name"]
                                        return [{id_field: s} for s in parsed_value]
                                
                                # Handle list of dicts
                                if all(isinstance(i, dict) for i in parsed_value):
                                    return parsed_value
                            
                            # Any other format (mixed list, etc.) is invalid and will fall through
                        except (ValueError, SyntaxError):
                            pass  # Fall through to empty list

            return [] # Default to empty list if no custom fields and parsing fails

        if type_str == 'json':
            return json.loads(value)
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

    def set(self, key: str, value: Any, type_hint: str = 'string', description: str = None):
        """
        Sets a setting value in the database.
        """
        with self._session_factory() as session:
            # Check if setting exists
            setting = session.query(Setting).filter_by(key=key).first()

            if setting is None:
                # Create new setting
                setting = Setting(key=key, value=str(value), type=type_hint, description=description)
                session.add(setting)
            else:
                # Update existing setting
                setting.value = str(value)
                setting.type = type_hint
                if description:
                    setting.description = description

            session.commit()

            # If this is a list type, also update the list items
            if type_hint == 'list' and isinstance(value, list):
                # First, delete existing list items
                session.query(SettingListItem).filter_by(setting_key=key).delete()

                # Then add new list items
                for idx, item_value in enumerate(value):
                    list_item = SettingListItem(
                        setting_key=key,
                        item_index=idx,
                        item_value=str(item_value)
                    )
                    session.add(list_item)

            # If this is a custom type, also update the custom fields
            elif type_hint == 'custom' and isinstance(value, list):
                # First, delete existing custom fields
                session.query(SettingCustomField).filter_by(setting_key=key).delete()

                # Then add new custom fields
                for idx, item_obj in enumerate(value):
                    if isinstance(item_obj, dict):
                        for field_name, field_value in item_obj.items():
                            custom_field = SettingCustomField(
                                setting_key=key,
                                field_name=f"{field_name}_{idx}",
                                field_value=str(field_value)
                            )
                            session.add(custom_field)

            session.commit()

            # Reload settings to reflect the change
            self.load_settings()

    @property
    def all_settings(self) -> dict:
        """Returns the entire nested settings dictionary."""
        return self._settings