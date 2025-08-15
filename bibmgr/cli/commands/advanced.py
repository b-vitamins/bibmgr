"""Advanced commands for the CLI.

Provides commands for initialization, status checking, and other advanced operations.
"""

import os
from pathlib import Path

from rich.console import Console

console = Console()


def get_repository(ctx):
    """Get the entry repository from context."""
    return ctx.obj.repository


def get_storage_path(data_dir: Path | None = None) -> Path:
    """Get the storage path for the bibliography database."""
    if data_dir:
        return data_dir

    # Check environment variable
    if env_dir := os.environ.get("BIBMGR_DATA_DIR"):
        return Path(env_dir)

    # Default to XDG data home
    xdg_data_home = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    )
    return xdg_data_home / "bibmgr"
