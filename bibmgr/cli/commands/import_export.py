"""Import and export commands for bibliography entries.

Provides commands for importing entries from various formats and exporting
to different formats with filtering and formatting options.
"""

from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

# from bibmgr.cli.utils.context import pass_context
from bibmgr.cli.utils.completion import get_collection_names, get_entry_keys
from bibmgr.operations.results import ResultStatus
from bibmgr.operations.workflows import (
    ExportFormat,
    ExportWorkflow,
    ExportWorkflowConfig,
    ImportFormat,
    ImportWorkflow,
    ImportWorkflowConfig,
)
from bibmgr.storage.events import Event, EventType
from bibmgr.storage.query import Condition, Operator

console = Console()


def get_repository_manager(ctx):
    """Get the repository manager from context."""
    return ctx.obj.repository_manager


def get_repository(ctx):
    """Get the entry repository from context."""
    return ctx.obj.repository


def get_collection_repository(ctx):
    """Get the collection repository from context."""
    return ctx.obj.collection_repository


def get_metadata_store(ctx):
    """Get the metadata store from context."""
    return ctx.obj.metadata_store


def get_search_service(ctx):
    """Get the search service from context."""
    return ctx.obj.search_service


def get_event_bus(ctx):
    """Get event bus from context."""
    return ctx.obj.event_bus


def get_collection_handler(ctx):
    """Get collection handler from context."""

    # Mock implementation for now
    class MockCollectionHandler:
        def add_entries(self, collection_name: str, entry_keys: list[str]):
            from bibmgr.operations.results import OperationResult

            return OperationResult(
                status=ResultStatus.SUCCESS,
                message=f"Added {len(entry_keys)} entries to collection",
            )

    return MockCollectionHandler()


@click.command("import")
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "-f",
    type=click.Choice(["bibtex", "ris", "json", "auto"]),
    default="auto",
    help="Input format (auto-detect by default)",
)
@click.option("--no-validate", is_flag=True, help="Skip entry validation")
@click.option(
    "--on-duplicate",
    type=click.Choice(["skip", "update", "merge", "ask"]),
    default="ask",
    help="How to handle duplicate entries",
)
@click.option(
    "--add-to-collection",
    help="Add imported entries to collection",
    shell_complete=get_collection_names,
)
@click.option("--tag", "-t", multiple=True, help="Add tags to imported entries")
@click.option("--dry-run", is_flag=True, help="Preview import without making changes")
@click.option(
    "--continue-on-error",
    is_flag=True,
    help="Continue importing even if some entries fail",
)
@click.pass_context
def import_command(
    ctx,
    source: Path,
    format: str,
    no_validate: bool,
    on_duplicate: str,
    add_to_collection: str | None,
    tag: tuple[str, ...],
    dry_run: bool,
    continue_on_error: bool,
):
    """Import bibliography entries from file or directory."""
    manager = get_repository_manager(ctx)
    event_bus = get_event_bus(ctx)

    # Convert format string to enum
    format_enum = ImportFormat.AUTO
    if format != "auto":
        format_enum = ImportFormat(format)

    # Build config
    config = ImportWorkflowConfig(
        validate=not no_validate,
        dry_run=dry_run,
        continue_on_error=continue_on_error,
        tags=list(tag) if tag else None,
        collection=add_to_collection,
    )

    # Set duplicate handling
    if on_duplicate == "skip":
        from bibmgr.operations.policies import ConflictResolution

        config.conflict_resolution = ConflictResolution.SKIP
    elif on_duplicate == "update":
        config.update_existing = True
    elif on_duplicate == "merge":
        config.merge_duplicates = True

    # Handle directory import
    if source.is_dir():
        files = []
        for ext, fmt in [
            (".bib", ImportFormat.BIBTEX),
            (".ris", ImportFormat.RIS),
            (".json", ImportFormat.JSON),
        ]:
            files.extend((f, fmt) for f in source.glob(f"*{ext}"))

        if not files:
            console.print("[red]No importable files found in directory[/red]")
            raise SystemExit(1)

        console.print(f"\n[bold]Found {len(files)} files to import[/bold]\n")

        total_imported = 0
        total_skipped = 0
        total_errors = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Importing files...", total=len(files))

            for file_path, file_format in files:
                progress.update(task, description=f"Importing {file_path.name}...")

                workflow = ImportWorkflow(manager, event_bus)
                result = workflow.execute(file_path, file_format, config)

                if hasattr(result, "data") and result.data:  # type: ignore
                    total_imported += result.data.get("imported", 0)  # type: ignore
                    total_skipped += result.data.get("skipped", 0)  # type: ignore
                    total_errors += result.data.get("errors", 0)  # type: ignore

                progress.advance(task)

        console.print("\n[bold]Import Summary[/bold]")
        console.print(f"Total imported: {total_imported}")
        if total_skipped:
            console.print(f"Total skipped: {total_skipped}")
        if total_errors:
            console.print(f"[red]Total errors: {total_errors}[/red]")

    else:
        # Single file import
        workflow = ImportWorkflow(manager, event_bus)

        # Subscribe to progress events
        progress_handler = None

        def handle_progress(event: Event):
            if event.type == EventType.PROGRESS and event.data:
                current = event.data.get("current", 0)
                total = event.data.get("total", 0)
                if progress_handler:
                    progress_handler.update(task, completed=current, total=total)

        event_bus.subscribe(EventType.PROGRESS, handle_progress)

        try:
            with Progress(console=console) as progress:
                progress_handler = progress
                task = progress.add_task(f"Importing from {source.name}...", total=100)

                result = workflow.execute(source, format_enum, config)
        finally:
            event_bus.unsubscribe(EventType.PROGRESS, handle_progress)

        # Display results based on WorkflowResult properties
        if result.success:
            console.print("\n[green]✓[/green] Import completed successfully")
        elif result.partial_success:
            console.print("\n[yellow]⚠[/yellow] Import partially completed")
        else:
            console.print("\n[red]✗[/red] Import failed")
            failed_steps = result.failed_steps
            if failed_steps:
                for step in failed_steps:
                    if hasattr(step, "errors") and step.errors:
                        for error in step.errors:
                            console.print(f"  • {error}")
            raise SystemExit(1)

        # Show summary using WorkflowResult interface
        summary = result.get_summary()
        successful_count = len(result.successful_entities)
        failed_count = summary.get("failed_steps", 0)
        skipped_count = summary.get("skipped", 0)

        console.print(f"\nImported: {successful_count}")
        if skipped_count:
            console.print(f"Skipped: {skipped_count}")
            # Show duplicate information if available
            if "duplicates" in summary and summary["duplicates"]:
                duplicates = summary["duplicates"]
                console.print(f"  • Duplicates: {', '.join(duplicates)}")
        # Show merged information if available
        merged_count = summary.get("merged", 0)
        if merged_count:
            console.print(f"Merged: {merged_count}")
        if failed_count:
            console.print(f"[red]Errors: {failed_count}[/red]")
            # Show detailed error information
            failed_steps = result.failed_steps
            if failed_steps:
                for step in failed_steps:
                    if hasattr(step, "entity_id") and step.entity_id:
                        console.print(f"  • {step.entity_id}: {step.message}")
                    elif hasattr(step, "errors") and step.errors:
                        for error in step.errors[:3]:  # Show first 3 errors
                            console.print(f"  • {error}")
                    elif hasattr(step, "message") and step.message:
                        console.print(f"  • {step.message}")

        # Add to collection if requested
        if add_to_collection and result.successful_entities:
            entry_keys = result.successful_entities
            handler = get_collection_handler(ctx)
            coll_result = handler.add_entries(add_to_collection, entry_keys)
            if coll_result.status == ResultStatus.SUCCESS:
                console.print(
                    f"\n[green]✓[/green] Added {len(entry_keys)} entries to collection '{add_to_collection}'"
                )

        # Add tags if requested
        if tag and result.successful_entities:
            metadata_store = get_metadata_store(ctx)
            entry_keys = result.successful_entities

            with console.status("Adding tags..."):
                for key in entry_keys:
                    metadata = metadata_store.get_metadata(key)
                    metadata.add_tags(*tag)
                    metadata_store.save_metadata(metadata)

            console.print(
                f"\n[green]✓[/green] Tagged {len(entry_keys)} entries with: {', '.join(tag)}"
            )


@click.command("export")
@click.argument("destination", type=click.Path())
@click.option(
    "--format",
    "-f",
    type=click.Choice(["bibtex", "ris", "json", "csv", "markdown"]),
    help="Export format (auto-detect from extension by default)",
)
@click.option(
    "--keys",
    "-k",
    help="Export specific entries (comma-separated)",
    shell_complete=get_entry_keys,
)
@click.option(
    "--collection",
    "-c",
    help="Export entries from collection",
    shell_complete=get_collection_names,
)
@click.option("--query", "-q", help="Export entries matching search query")
@click.option("--type", "-t", multiple=True, help="Filter by entry type")
@click.option(
    "--year", "-y", help="Filter by year (exact or range, e.g., 2020 or 2020-2024)"
)
@click.option("--tag", multiple=True, help="Filter by tags")
@click.option("--append", "-a", is_flag=True, help="Append to existing file")
@click.option(
    "--sort",
    type=click.Choice(["key", "year", "author", "title"]),
    help="Sort entries by field",
)
@click.option("--reverse", is_flag=True, help="Reverse sort order")
@click.option("--pretty/--compact", default=True, help="Pretty print output (JSON/XML)")
@click.pass_context
def export_command(
    ctx,
    destination: str,
    format: str | None,
    keys: str | None,
    collection: str | None,
    query: str | None,
    type: tuple[str, ...],
    year: str | None,
    tag: tuple[str, ...],
    append: bool,
    sort: str | None,
    reverse: bool,
    pretty: bool,
):
    """Export bibliography entries to file."""
    manager = get_repository_manager(ctx)
    repo = get_repository(ctx)
    event_bus = get_event_bus(ctx)

    # Determine format from destination if not specified
    if format is None:
        if destination == "-":
            format = "bibtex"  # Default for stdout
        else:
            dest_path = Path(destination)
            ext_map = {
                ".bib": "bibtex",
                ".bibtex": "bibtex",
                ".ris": "ris",
                ".json": "json",
                ".csv": "csv",
                ".md": "markdown",
            }
            format = ext_map.get(dest_path.suffix.lower(), "bibtex")

    format_enum = ExportFormat(format)

    # Collect entries to export
    entry_keys_list: list[str] = []

    if keys:
        # Specific keys provided
        entry_keys_list = [k.strip() for k in keys.split(",") if k.strip()]

    elif collection:
        # Export from collection
        coll_repo = get_collection_repository(ctx)
        # Find collection by ID first, then by name
        coll = coll_repo.find(collection)
        if not coll:
            # Try finding by name
            all_collections = coll_repo.find_all()
            for c in all_collections:
                if c.name == collection:
                    coll = c
                    break

        if not coll:
            console.print(f"[red]Collection not found:[/red] {collection}")
            raise SystemExit(1)

        console.print(f"\n[bold]Exporting from collection: {coll.name}[/bold]")
        entry_keys_list = list(coll.entry_keys)

    elif query:
        # Export from search query
        search_service = get_search_service(ctx)
        results = search_service.search(query)

        if not results.matches:
            console.print(f"[yellow]No entries found matching query:[/yellow] {query}")
            raise SystemExit(0)

        console.print(
            f"\n[bold]Found {len(results.matches)} entries matching query[/bold]"
        )
        entry_keys_list = [match.entry_key for match in results.matches]

    else:
        # Build query from filters or export all
        conditions = []

        if type:
            from bibmgr.core.models import EntryType

            for t in type:
                try:
                    entry_type = EntryType(t.lower())
                    conditions.append(Condition("type", Operator.EQ, entry_type))
                except ValueError:
                    # Invalid entry type will result in no matches
                    conditions.append(Condition("type", Operator.EQ, t.lower()))

        if year:
            if "-" in year or ".." in year:
                # Range
                parts = year.replace("..", "-").split("-")
                if len(parts) == 2:
                    conditions.append(Condition("year", Operator.GTE, int(parts[0])))
                    conditions.append(Condition("year", Operator.LTE, int(parts[1])))
            else:
                # Exact year
                conditions.append(Condition("year", Operator.EQ, int(year)))

        if tag:
            # For tags, we need to use metadata store
            metadata_store = get_metadata_store(ctx)
            tag_entries = set()
            for t in tag:
                tag_entries.update(metadata_store.find_by_tag(t))

            if not tag_entries:
                console.print(
                    f"[yellow]No entries found with tags:[/yellow] {', '.join(tag)}"
                )
                raise SystemExit(0)

            # Filter by both query conditions and tags
            if conditions:
                from bibmgr.storage.repository import QueryBuilder

                qb = QueryBuilder()
                for cond in conditions:
                    qb = qb.where(cond.field, cond.operator.value, cond.value)
                all_entries = repo.find_by(qb)
                entry_keys_list = [e.key for e in all_entries if e.key in tag_entries]
            else:
                entry_keys_list = list(tag_entries)
        elif conditions:
            from bibmgr.storage.repository import QueryBuilder

            qb = QueryBuilder()
            for cond in conditions:
                qb = qb.where(cond.field, cond.operator.value, cond.value)
            entries = repo.find_by(qb)
            entry_keys_list = [e.key for e in entries]
        else:
            # Export all entries
            entries = repo.find_all()
            entry_keys_list = [e.key for e in entries]

    # Check if file exists and not appending
    if destination != "-" and not append:
        dest_path = Path(destination)
        if dest_path.exists():
            if not Confirm.ask(f"File {destination} already exists. Overwrite?"):
                console.print("[yellow]Export cancelled[/yellow]")
                raise SystemExit(0)

    # Build config
    config = ExportWorkflowConfig(
        format=format_enum,
        sort_by=sort,
        sort_reverse=reverse,
        pretty_print=pretty,
    )

    # Execute export
    workflow = ExportWorkflow(manager, event_bus)

    with console.status(f"Exporting {len(entry_keys_list)} entries..."):
        result = workflow.execute(
            destination, entry_keys=entry_keys_list, config=config
        )

    # Display results based on WorkflowResult properties
    if result.success:
        if destination == "-":
            # Output to stdout - get content from workflow result and print it
            summary = result.get_summary()
            if "content" in summary and summary["content"]:
                # Print the content directly to stdout without formatting
                print(summary["content"], end="")
        else:
            # Get successful count
            exported_count = len(result.successful_entities)
            if exported_count == 0:
                console.print("[yellow]No entries exported[/yellow]")
            else:
                console.print(
                    f"\n[green]✓[/green] Exported {exported_count} entries to {destination}"
                )

            # Show file size
            if Path(destination).exists() and exported_count > 0:
                size = Path(destination).stat().st_size
                if size < 1024:
                    size_str = f"{size} bytes"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                console.print(f"  File size: {size_str}")
    else:
        console.print("\n[red]✗[/red] Export failed")
        failed_steps = result.failed_steps
        if failed_steps:
            for step in failed_steps:
                if hasattr(step, "message") and step.message:
                    console.print(f"  • {step.message}")
                if hasattr(step, "errors") and step.errors:
                    for error in step.errors:
                        console.print(f"  • {error}")
        ctx.exit(1)
