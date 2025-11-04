
import yaml
from pathlib import Path

def load_config(path: str = "config.yml") -> dict:
    """Loads the YAML configuration file."""
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found at: {config_path.resolve()}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
