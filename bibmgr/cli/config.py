"""CLI configuration management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class Config:
    """CLI configuration handler."""

    def __init__(self, config_file: Path | None = None):
        """Initialize configuration.

        Args:
            config_file: Optional path to config file
        """
        self._config: dict[str, Any] = {}
        self._load_defaults()
        self._load_from_file(config_file)
        self._load_from_env()

    def _load_defaults(self) -> None:
        """Load default configuration."""
        self._config = {
            "database": {
                "path": self._get_default_db_path(),
                "backup": True,
                "backup_count": 5,
            },
            "import": {
                "default_format": "bibtex",
                "merge_duplicates": False,
                "validate": True,
            },
            "export": {
                "default_format": "bibtex",
                "include_abstract": True,
                "include_keywords": True,
            },
            "validation": {
                "strict": False,
                "auto_fix": False,
                "required_fields": ["key", "type", "title"],
            },
            "display": {
                "page_size": 20,
                "use_colors": True,
                "table_format": "grid",
            },
            "search": {
                "fuzzy": False,
                "limit": 20,
                "highlight": True,
            },
        }

    def _get_default_db_path(self) -> str:
        """Get default database path."""
        data_dir = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        )
        bibmgr_dir = data_dir / "bibmgr"
        bibmgr_dir.mkdir(parents=True, exist_ok=True)
        return str(bibmgr_dir / "bibliography.db")

    def _load_from_file(self, config_file: Path | None = None) -> None:
        """Load configuration from file.

        Args:
            config_file: Path to config file
        """
        if config_file is None:
            config_dir = Path(
                os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
            )
            config_file = config_dir / "bibmgr" / "config.json"

        if config_file.exists():
            try:
                with open(config_file) as f:
                    file_config = json.load(f)
                self._merge_config(file_config)
            except (OSError, json.JSONDecodeError):
                pass  # Use defaults if config file is invalid

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        env_mappings = {
            "BIBMGR_DATABASE": ("database", "path"),
            "BIBMGR_FORMAT": ("export", "default_format"),
            "BIBMGR_IMPORT_FORMAT": ("import", "default_format"),
            "BIBMGR_EXPORT_FORMAT": ("export", "default_format"),
            "BIBMGR_STRICT": ("validation", "strict"),
            "BIBMGR_PAGE_SIZE": ("display", "page_size"),
            "BIBMGR_NO_COLOR": ("display", "use_colors"),
        }

        for env_var, (section, key) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Handle boolean values
                if key in ["strict", "use_colors"]:
                    value = value.lower() in ["true", "1", "yes"]
                    if key == "use_colors" and env_var == "BIBMGR_NO_COLOR":
                        value = not value  # Invert for NO_COLOR
                # Handle integer values
                elif key == "page_size":
                    try:
                        value = int(value)
                    except ValueError:
                        continue

                if section not in self._config:
                    self._config[section] = {}
                self._config[section][key] = value

    def _merge_config(self, new_config: dict[str, Any]) -> None:
        """Merge new configuration with existing.

        Args:
            new_config: New configuration to merge
        """
        for section, values in new_config.items():
            if section not in self._config:
                self._config[section] = {}
            if isinstance(values, dict):
                self._config[section].update(values)
            else:
                self._config[section] = values

    @property
    def database_path(self) -> Path:
        """Get database path."""
        return Path(self._config["database"]["path"])

    @property
    def import_format(self) -> str:
        """Get default import format."""
        return self._config["import"]["default_format"]

    @property
    def export_format(self) -> str:
        """Get default export format."""
        return self._config["export"]["default_format"]

    @property
    def validation_strict(self) -> bool:
        """Get strict validation flag."""
        return self._config["validation"]["strict"]

    @property
    def page_size(self) -> int:
        """Get display page size."""
        return self._config["display"]["page_size"]

    @property
    def use_colors(self) -> bool:
        """Get color usage flag."""
        return self._config["display"]["use_colors"]

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            section: Configuration section
            key: Configuration key
            default: Default value if not found

        Returns:
            Configuration value
        """
        return self._config.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        """Set configuration value.

        Args:
            section: Configuration section
            key: Configuration key
            value: Value to set
        """
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value

    def save(self, config_file: Path | None = None) -> None:
        """Save configuration to file.

        Args:
            config_file: Path to save configuration to
        """
        if config_file is None:
            config_dir = Path(
                os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
            )
            config_file = config_dir / "bibmgr" / "config.json"

        config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, "w") as f:
            json.dump(self._config, f, indent=2)


# Global configuration instance
_config: Config | None = None


def get_config() -> Config:
    """Get global configuration instance.

    Returns:
        Configuration instance
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config() -> None:
    """Reset global configuration."""
    global _config
    _config = None
