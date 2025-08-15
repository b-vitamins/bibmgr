"""CLI context management utilities.

Provides helpers for managing Click context and passing state between commands.
"""

from typing import Any

import click

from bibmgr.search import SearchEngine
from bibmgr.storage import RepositoryManager
from bibmgr.storage.metadata import MetadataStore


class Context:
    """CLI context object for passing state between commands."""

    def __init__(self):
        """Initialize context."""
        self.repository_manager: RepositoryManager | None = None
        self.metadata_store: MetadataStore | None = None
        self.search_engine: SearchEngine | None = None
        self.config: dict[str, Any] = {}
        self.verbose: bool = False
        self.debug: bool = False
        self.output_format: str = "table"


def get_context() -> Context:
    """Get the current CLI context.

    Returns:
        Current context object
    """
    ctx = click.get_current_context()
    if not hasattr(ctx, "obj") or ctx.obj is None:
        ctx.obj = Context()
    return ctx.obj


def pass_context(f):
    """Decorator to pass context to command function.

    Args:
        f: Function to decorate

    Returns:
        Decorated function
    """
    return click.pass_obj(f)


def ensure_repository(ctx: Context) -> RepositoryManager:
    """Ensure repository manager is initialized.

    Args:
        ctx: CLI context

    Returns:
        Repository manager instance

    Raises:
        click.ClickException: If repository not initialized
    """
    if ctx.repository_manager is None:
        raise click.ClickException("Repository not initialized. Run 'bib init' first.")
    return ctx.repository_manager


def ensure_metadata_store(ctx: Context) -> MetadataStore:
    """Ensure metadata store is initialized.

    Args:
        ctx: CLI context

    Returns:
        Metadata store instance

    Raises:
        click.ClickException: If metadata store not initialized
    """
    if ctx.metadata_store is None:
        raise click.ClickException(
            "Metadata store not initialized. Run 'bib init' first."
        )
    return ctx.metadata_store


def ensure_search_engine(ctx: Context) -> SearchEngine:
    """Ensure search engine is initialized.

    Args:
        ctx: CLI context

    Returns:
        Search engine instance

    Raises:
        click.ClickException: If search engine not initialized
    """
    if ctx.search_engine is None:
        raise click.ClickException(
            "Search engine not initialized. Run 'bib init' first."
        )
    return ctx.search_engine
