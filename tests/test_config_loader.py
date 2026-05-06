"""
Tests du chargement de configuration.
Vérifie que les valeurs par défaut sont bien appliquées
et que config.yml est correctement lu.
"""
import pytest
from unittest.mock import patch, mock_open
import yaml

from core.config_loader import load_config


class TestConfigLoader:

    def test_defaults_applied_when_no_file(self):
        """Si config.yml n'existe pas, les valeurs par défaut sont utilisées."""
        with patch("core.config_loader.CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            config = load_config()

        assert "clusters" in config
        assert len(config["clusters"]) > 0
        assert config["monitor"]["refresh_interval"] == 5
        assert config["alerts"]["warning_threshold"] == 1000
        assert config["alerts"]["critical_threshold"] == 10000

    def test_user_config_overrides_defaults(self):
        """Les valeurs de config.yml remplacent les valeurs par défaut."""
        user_config = yaml.dump({
            "monitor": {"refresh_interval": 10},
            "alerts": {"warning_threshold": 500, "critical_threshold": 5000},
        })
        with patch("core.config_loader.CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=user_config)):
                config = load_config()

        assert config["monitor"]["refresh_interval"] == 10
        assert config["alerts"]["warning_threshold"] == 500
        assert config["alerts"]["critical_threshold"] == 5000

    def test_clusters_list_loaded(self):
        """La liste de clusters est bien chargée depuis config.yml."""
        user_config = yaml.dump({
            "clusters": [
                {"name": "prod", "bootstrap_servers": "prod:9092"},
                {"name": "dev",  "bootstrap_servers": "dev:9092"},
            ]
        })
        with patch("core.config_loader.CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=user_config)):
                config = load_config()

        assert len(config["clusters"]) == 2
        assert config["clusters"][0]["name"] == "prod"
        assert config["clusters"][1]["name"] == "dev"

    def test_partial_config_keeps_other_defaults(self):
        """Une config partielle ne supprime pas les autres valeurs par défaut."""
        user_config = yaml.dump({
            "monitor": {"refresh_interval": 30}
        })
        with patch("core.config_loader.CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=user_config)):
                config = load_config()

        # refresh_interval modifié
        assert config["monitor"]["refresh_interval"] == 30
        # history_retention_days garde sa valeur par défaut
        assert config["monitor"]["history_retention_days"] == 7