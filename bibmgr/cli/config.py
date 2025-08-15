"""Configuration management for the CLI."""

import os
from pathlib import Path
from typing import Any

import yaml


class Config:
    """Configuration management for the CLI application."""

    @staticmethod
    def from_file(path: Path) -> dict[str, Any]:
        """Load configuration from a YAML file."""
        try:
            with open(path) as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")
        except Exception as e:
            raise ValueError(f"Error reading config file: {e}")

    @staticmethod
    def get_config_paths() -> list[Path]:
        """Get the default configuration file paths to check."""
        paths = []

        # User config
        xdg_config_home = Path(
            os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        )
        paths.append(xdg_config_home / "bibmgr" / "config.yaml")

        # Project config
        paths.append(Path(".bibmgr.yaml"))
        paths.append(Path("bibmgr.yaml"))

        return paths

    @staticmethod
    def load_default() -> dict[str, Any]:
        """Load configuration from default locations."""
        for path in Config.get_config_paths():
            if path.exists():
                try:
                    return Config.from_file(path)
                except Exception:
                    continue

        return {}

    @staticmethod
    def merge_configs(*configs: dict[str, Any]) -> dict[str, Any]:
        """Merge multiple configuration dictionaries."""
        result = {}
        for config in configs:
            result = _deep_merge(result, config)
        return result


def get_config_paths() -> list[Path]:
    """Get configuration paths in precedence order."""
    return Config.get_config_paths()


def load_config() -> dict[str, Any]:
    """Load configuration from files and environment variables."""
    config = {}

    # Load from all config paths (last one wins for conflicting keys)
    for path in get_config_paths():
        if path.exists():
            try:
                file_config = Config.from_file(path)
                config = Config.merge_configs(config, file_config)
            except Exception:
                continue

    # Override with environment variables
    env_overrides = {}
    if theme := os.environ.get("BIBMGR_THEME"):
        env_overrides["theme"] = theme
    if data_dir := os.environ.get("BIBMGR_DATA_DIR"):
        env_overrides["data_dir"] = data_dir

    return Config.merge_configs(config, env_overrides)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result
