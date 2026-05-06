"""
Chargement de la configuration multi-cluster depuis config.yml.
"""
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.yml"

DEFAULTS = {
    "clusters": [
        {"name": "default", "bootstrap_servers": "localhost:9092", "color": "teal"}
    ],
    "monitor": {"refresh_interval": 5, "history_retention_days": 7},
    "alerts": {"warning_threshold": 1000, "critical_threshold": 10000},
    "web": {"host": "0.0.0.0", "port": 8080},
    "exclude_topics": [],
    "exclude_groups": [],
}


def load_config() -> dict:
    config = DEFAULTS.copy()
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            user_config = yaml.safe_load(f) or {}
        for section, values in user_config.items():
            if isinstance(values, dict) and section in config:
                config[section].update(values)
            else:
                config[section] = values
    return config


CONFIG = load_config()