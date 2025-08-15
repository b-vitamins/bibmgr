"""Path utilities for the CLI.

Provides functions for managing application paths and directories.
"""

import os
from pathlib import Path


def get_storage_path() -> Path:
    """Get the storage path for bibliography data.

    Returns:
        Path to storage directory
    """
    # Check environment variable first
    if env_path := os.environ.get("BIBMGR_DATA_DIR"):
        return Path(env_path).expanduser().resolve()

    # Default to XDG data directory
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "bibmgr"

    # Fall back to ~/.local/share/bibmgr
    return Path.home() / ".local" / "share" / "bibmgr"


def get_config_path() -> Path:
    """Get the configuration directory path.

    Returns:
        Path to config directory
    """
    # Check environment variable first
    if env_path := os.environ.get("BIBMGR_CONFIG_DIR"):
        return Path(env_path).expanduser().resolve()

    # Default to XDG config directory
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / "bibmgr"

    # Fall back to ~/.config/bibmgr
    return Path.home() / ".config" / "bibmgr"


def get_cache_path() -> Path:
    """Get the cache directory path.

    Returns:
        Path to cache directory
    """
    # Check environment variable first
    if env_path := os.environ.get("BIBMGR_CACHE_DIR"):
        return Path(env_path).expanduser().resolve()

    # Default to XDG cache directory
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home) / "bibmgr"

    # Fall back to ~/.cache/bibmgr
    return Path.home() / ".cache" / "bibmgr"


def ensure_directory(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path

    Returns:
        The path
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_default_import_path() -> Path:
    """Get default path for importing files.

    Returns:
        Default import path (current directory)
    """
    return Path.cwd()


def get_default_export_path() -> Path:
    """Get default path for exporting files.

    Returns:
        Default export path (current directory)
    """
    return Path.cwd()


def expand_path(path: str | Path) -> Path:
    """Expand user home and environment variables in path.

    Args:
        path: Path to expand

    Returns:
        Expanded path
    """
    path_str = str(path)
    # Expand environment variables
    path_str = os.path.expandvars(path_str)
    # Expand user home
    return Path(path_str).expanduser().resolve()


def find_project_root(start_path: Path | None = None) -> Path | None:
    """Find project root by looking for .bibmgr directory.

    Args:
        start_path: Starting path (defaults to current directory)

    Returns:
        Project root path or None if not found
    """
    current = Path(start_path or Path.cwd()).resolve()

    while current != current.parent:
        if (current / ".bibmgr").is_dir():
            return current
        current = current.parent

    # Check root directory
    if (current / ".bibmgr").is_dir():
        return current

    return None
