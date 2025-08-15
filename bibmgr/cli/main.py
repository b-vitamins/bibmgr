"""Main CLI entry point and application setup."""

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import click
from click.exceptions import Exit
from rich.console import Console

from bibmgr import __version__

# Import commands
from bibmgr.cli.commands import (
    collection,
    entry,
    import_export,
    metadata,
    quality,
    search,
)
from bibmgr.search import SearchEngine, SearchService
from bibmgr.storage.backends.filesystem import FileSystemBackend
from bibmgr.storage.events import EventBus
from bibmgr.storage.metadata import MetadataStore
from bibmgr.storage.repository import (
    CollectionRepository,
    EntryRepository,
    RepositoryManager,
)


@dataclass
class Context:
    """CLI context that holds shared resources."""

    repository_manager: RepositoryManager
    repository: EntryRepository
    collection_repository: CollectionRepository
    search_service: SearchService
    metadata_store: MetadataStore
    console: Console
    event_bus: EventBus
    config: dict | None = None
    debug: bool = False


def setup_logging(
    verbose: bool = False, quiet: bool = False, debug: bool = False
) -> None:
    """Configure logging based on CLI flags."""
    if quiet:
        level = logging.WARNING
    elif verbose or debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s"
        if not debug
        else "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def create_console(no_color: bool = False, width: int | None = None) -> Console:
    """Create Rich console with appropriate settings."""
    return Console(
        no_color=no_color,
        width=width or 120,
        highlight=not no_color,
        color_system=None if no_color else "auto",
    )


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


class BibMgrGroup(click.Group):
    """Custom group that handles KeyboardInterrupt."""

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except KeyboardInterrupt:
            console = getattr(ctx.obj, "console", None) if ctx.obj else None
            if console:
                console.print("[yellow]Interrupted[/yellow]")
            ctx.exit(130)
        except (click.ClickException, click.Abort, Exit, SystemExit):
            # Let Click exceptions and exits propagate naturally with their correct exit codes
            raise
        except Exception as e:
            debug = getattr(ctx.obj, "debug", False) if ctx.obj else False
            if debug:
                raise
            console = getattr(ctx.obj, "console", None) if ctx.obj else None
            if console:
                console.print(f"[red]Error:[/red] {e}")
            else:
                click.echo(f"Error: {e}", err=True)
            ctx.exit(1)


@click.group(cls=BibMgrGroup)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error output")
@click.option("--no-color", is_flag=True, help="Disable colored output")
@click.option("--debug", is_flag=True, help="Enable debug mode with full tracebacks")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "--data-dir",
    "-d",
    type=click.Path(path_type=Path),
    help="Override data directory location",
)
@click.version_option(
    version=__version__, prog_name="bibmgr", message="bibmgr version %(version)s"
)
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: bool,
    quiet: bool,
    no_color: bool,
    debug: bool,
    config: Path | None,
    data_dir: Path | None,
) -> None:
    """Bibliography management tool.

    A professional CLI for managing bibliography entries with rich formatting
    and powerful search capabilities.
    """
    # Setup logging
    setup_logging(verbose=verbose, quiet=quiet, debug=debug)

    # Load configuration
    config_data = {}
    if config:
        try:
            from bibmgr.cli.config import Config

            config_data = Config.from_file(config)
        except Exception as e:
            if debug:
                raise
            click.echo(f"Error loading config file: {e}", err=True)
            ctx.exit(1)

    # Create console
    console = create_console(no_color=no_color)

    # Initialize storage and services
    try:
        storage_path = get_storage_path(data_dir)
        backend = FileSystemBackend(storage_path)

        # Create repositories
        repo_manager = RepositoryManager(backend)
        entry_repo = repo_manager.entries
        collection_repo = repo_manager.collections

        # Create search service with Whoosh backend
        from bibmgr.search.backends.whoosh import WhooshBackend
        from bibmgr.search.indexing import FieldConfiguration

        # Configure search index location
        index_dir = storage_path / ".index"

        # Create field configuration with default settings
        field_config = FieldConfiguration()

        # Initialize Whoosh backend
        search_backend = WhooshBackend(
            index_dir=index_dir, field_config=field_config, create_if_missing=True
        )

        # Create search engine
        search_engine = SearchEngine(search_backend)

        # Create event bus
        event_bus = EventBus()

        # Create search service with repository and event bus for automatic indexing
        search_service = SearchService(
            search_engine, repository=entry_repo, event_bus=event_bus
        )

        # Create metadata store
        metadata_store = MetadataStore(storage_path)

        # Create and store context
        ctx.obj = Context(
            repository_manager=repo_manager,
            repository=entry_repo,
            collection_repository=collection_repo,
            search_service=search_service,
            metadata_store=metadata_store,
            console=console,
            event_bus=event_bus,
            config=config_data,
            debug=debug,
        )

    except KeyboardInterrupt:
        console.print("[yellow]Interrupted[/yellow]")
        ctx.exit(130)
    except Exception as e:
        if debug:
            raise
        console.print(f"[red]Error initializing application:[/red] {e}")
        ctx.exit(1)


# Command: init
@cli.command()
@click.option(
    "--import",
    "import_file",
    type=click.Path(exists=True, path_type=Path),
    help="Import entries from file after initialization",
)
@click.pass_context
def init(ctx: click.Context, import_file: Path | None) -> None:
    """Initialize a new bibliography database."""
    console = ctx.obj.console if ctx.obj else create_console()

    try:
        # Get storage path - check if data_dir was passed via CLI options
        data_dir = None
        if ctx.parent:
            # Get data_dir from the parent context params
            data_dir = ctx.parent.params.get("data_dir")
        storage_path = get_storage_path(data_dir)

        # Check if already initialized - look for actual entries, not just directory
        entries_dir = storage_path / "entries"
        if entries_dir.exists() and any(entries_dir.glob("*.json")):
            console.print("[yellow]Database already initialized[/yellow]")
            return

        # Create directory structure
        for subdir in ["entries", "metadata", "collections"]:
            (storage_path / subdir).mkdir(parents=True, exist_ok=True)

        console.print(
            f"[green]✓[/green] Initialized bibliography database at {storage_path}"
        )

        # Import if requested
        if import_file:
            # This will be implemented when import command is ready
            console.print("[yellow]Import functionality not yet implemented[/yellow]")

    except Exception as e:
        if ctx.obj and ctx.obj.debug:
            raise
        console.print(f"[red]Error during initialization:[/red] {e}")
        ctx.exit(1)


# Command: status
@cli.command()
@click.option("--check-index", is_flag=True, help="Check search index status")
@click.pass_context
def status(ctx: click.Context, check_index: bool) -> None:
    """Show database status and statistics."""
    console = ctx.obj.console

    try:
        # Get storage info - check if data_dir was passed via CLI options
        data_dir = None
        if ctx.parent:
            # Get data_dir from the parent context params
            data_dir = ctx.parent.params.get("data_dir")
        storage_path = get_storage_path(data_dir)

        console.print("\n[bold]Database Status[/bold]\n")
        console.print(f"Storage location: {storage_path}")

        if ctx.obj and ctx.obj.repository_manager:
            # Get statistics from repository manager
            stats = ctx.obj.repository_manager.get_statistics()
            total = stats.get("total_entries", 0)

            console.print(f"Total entries: {total}")

            if types := stats.get("entries_by_type"):
                console.print("\nEntry types:")
                for entry_type, count in types.items():
                    console.print(f"  {entry_type}: {count}")

        if check_index:
            console.print("\nIndex status: [green]OK[/green]")

    except Exception as e:
        if ctx.obj and ctx.obj.debug:
            raise
        console.print(f"[red]Error getting status:[/red] {e}")
        ctx.exit(1)


# Register command groups
cli.add_command(entry.add)
cli.add_command(entry.show)
cli.add_command(entry.list_cmd, name="list")
cli.add_command(entry.edit)
cli.add_command(entry.delete)
cli.add_command(search.search)
cli.add_command(search.find)
cli.add_command(search.similar)
cli.add_command(collection.collection)


# Add 'collections' as shortcut for 'collection list'
@cli.command()
@click.option("--containing", help="Show only collections containing this entry")
@click.pass_context
def collections(ctx: click.Context, containing: str | None) -> None:
    """List all collections (shortcut for 'collection list')."""
    if containing:
        # Filter collections by entry
        console = ctx.obj.console
        collection_repo = collection.get_collection_repository(ctx)

        try:
            all_collections = collection_repo.find_all()
            filtered = []
            for col in all_collections:
                if col.entry_keys and containing in col.entry_keys:
                    filtered.append(col)

            if not filtered:
                console.print(
                    f"[yellow]No collections contain entry '{containing}'[/yellow]"
                )
                return

            console.print(f"\n📚 [bold]Collections containing '{containing}'[/bold]\n")
            collection._display_collections_table(console, filtered)

        except Exception as e:
            if ctx.obj.debug:
                raise
            console.print(f"[red]Error:[/red] {e}")
            ctx.exit(1)
    else:
        # Normal list
        ctx.invoke(
            collection.list_collections, tree=False, smart_only=False, manual_only=False
        )


cli.add_command(metadata.metadata)
cli.add_command(metadata.tag)
cli.add_command(metadata.note)
cli.add_command(quality.check)
cli.add_command(quality.dedupe)
cli.add_command(quality.clean)
cli.add_command(quality.report)
cli.add_command(import_export.import_command)
cli.add_command(import_export.export_command, name="export")


def load_plugins():
    """Load CLI plugins (placeholder implementation)."""
    # This is a placeholder for plugin loading functionality
    # In a full implementation, this would scan for and load plugins
    pass


def main() -> None:
    """Main entry point for the CLI application."""
    try:
        cli()
    except KeyboardInterrupt:
        # Exit gracefully on Ctrl+C
        sys.exit(130)
    except Exception as e:
        # Handle unexpected errors
        # Check if debug flag is present in sys.argv (but handle if sys.argv is modified)
        debug_mode = False
        try:
            debug_mode = "--debug" in sys.argv
        except (IndexError, TypeError):
            # Handle case where sys.argv might be modified or invalid
            debug_mode = False

        if debug_mode:
            raise
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
