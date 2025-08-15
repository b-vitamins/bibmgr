"""Entry management CLI commands."""

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from bibmgr.core.models import Entry, EntryType, generate_citation_key
from bibmgr.operations.commands.create import CreateCommand, CreateHandler
from bibmgr.operations.commands.delete import DeleteCommand, DeleteHandler
from bibmgr.operations.commands.update import UpdateCommand, UpdateHandler
from bibmgr.operations.results import ResultStatus
from bibmgr.storage.repository import QueryBuilder


def get_repository(ctx):
    """Get the entry repository from context."""
    return ctx.obj.repository


def get_event_bus(ctx):
    """Get the event bus from context."""
    return ctx.obj.event_bus


def get_create_handler(ctx):
    """Get a create handler instance."""
    return CreateHandler(get_repository(ctx), get_event_bus(ctx))


def get_update_handler(ctx):
    """Get an update handler instance."""
    return UpdateHandler(get_repository(ctx), get_event_bus(ctx))


def get_delete_handler(ctx):
    """Get a delete handler instance."""
    return DeleteHandler(
        repository=get_repository(ctx),
        collection_repository=ctx.obj.collection_repository,
        metadata_store=get_metadata_store(ctx),
        event_bus=get_event_bus(ctx),
    )


def get_metadata_store(ctx):
    """Get the metadata store from context."""
    return ctx.obj.metadata_store


@click.group()
def entry():
    """Manage bibliography entries."""
    pass


# Command: add
@entry.command()
@click.option("--key", "-k", help="Citation key for the entry")
@click.option(
    "--type",
    "-t",
    "entry_type",
    type=click.Choice([t.value for t in EntryType]),
    default="article",
    help="Entry type",
)
@click.option("--title", help="Entry title")
@click.option("--author", help="Author(s), separated by 'and'")
@click.option("--year", help="Publication year")
@click.option("--journal", help="Journal name (for articles)")
@click.option("--booktitle", help="Book title (for proceedings)")
@click.option("--publisher", help="Publisher name")
@click.option("--volume", help="Volume number")
@click.option("--number", help="Issue number")
@click.option("--pages", help="Page numbers (e.g., '100--110')")
@click.option("--doi", help="Digital Object Identifier")
@click.option("--url", help="URL to the publication")
@click.option("--abstract", help="Abstract text")
@click.option("--keywords", help="Keywords, comma-separated")
@click.option("--file", help="Path to PDF file")
@click.option("--from-doi", help="Import entry from DOI")
@click.option("--from-pdf", help="Extract metadata from PDF file")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.option("--force", "-f", "--no-validate", is_flag=True, help="Skip validation")
@click.pass_context
def add(ctx: click.Context, **kwargs) -> None:
    """Add a new bibliography entry."""
    console = ctx.obj.console

    # Extract options
    interactive = kwargs.pop("interactive", False)
    force = kwargs.pop("force", False)
    entry_type_str = kwargs.pop("entry_type", "article")
    from_doi = kwargs.pop("from_doi", None)
    from_pdf = kwargs.pop("from_pdf", None)

    # Handle special import modes
    if from_doi:
        console.print("[yellow]DOI import not yet implemented[/yellow]")
        ctx.exit(0)

    if from_pdf:
        console.print("[yellow]PDF metadata extraction not yet implemented[/yellow]")
        ctx.exit(0)

    try:
        entry_type = EntryType(entry_type_str)

        # Collect fields interactively if needed
        if interactive or not any(v for k, v in kwargs.items() if v is not None):
            fields = _collect_entry_fields_interactive(console, entry_type, kwargs)
        else:
            fields = {k: v for k, v in kwargs.items() if v is not None}
            # Convert year to int if provided
            if "year" in fields and fields["year"]:
                try:
                    fields["year"] = int(fields["year"])
                except ValueError:
                    # Let the validation handler catch this
                    pass

        # Generate key if not provided
        if "key" not in fields or not fields["key"]:
            if "author" in fields and "year" in fields:
                fields["key"] = generate_citation_key(
                    Entry(key="temp", type=entry_type, **fields)
                )
            else:
                console.print(
                    "[red]Error:[/red] Cannot generate key without author and year"
                )
                ctx.exit(1)

        # Create entry
        entry = Entry(type=entry_type, **fields)

        # Create and execute command
        command = CreateCommand(entry=entry, force=force)
        handler = get_create_handler(ctx)
        result = handler.execute(command)

        # Handle result
        if result.status == ResultStatus.SUCCESS:
            console.print(f"[green]✓[/green] Entry added successfully: {entry.key}")
        elif result.status == ResultStatus.VALIDATION_FAILED:
            console.print("[red]Validation failed:[/red]")
            for error in result.validation_errors or []:
                console.print(f"  - {error.field}: {error.message}")
            ctx.exit(1)
        else:
            console.print(f"[red]Error:[/red] {result.message}")
            ctx.exit(1)

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Command: show
@entry.command()
@click.argument("key")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["rich", "bibtex", "json", "yaml"]),
    default="rich",
    help="Output format",
)
@click.pass_context
def show(ctx: click.Context, key: str, format: str) -> None:
    """Show entry details."""
    console = ctx.obj.console
    repository = get_repository(ctx)
    metadata_store = get_metadata_store(ctx)

    try:
        # Find entry
        entry = repository.find(key)
        if not entry:
            console.print(f"[red]Entry not found:[/red] {key}")
            ctx.exit(1)

        # Get metadata if available
        metadata = None
        try:
            metadata = metadata_store.get_metadata(key)
        except Exception:
            # Metadata is optional
            pass

        # Format and display
        if format == "rich":
            _display_entry_rich(console, entry, metadata)
        elif format == "bibtex":
            from bibmgr.cli.formatters.bibtex import format_entry_bibtex

            console.print(format_entry_bibtex(entry))
        elif format == "json":
            from bibmgr.cli.formatters.json import format_entry_json

            console.print(format_entry_json(entry))
        elif format == "yaml":
            from bibmgr.cli.formatters.yaml import format_entry_yaml

            console.print(format_entry_yaml(entry))

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Command: list
@entry.command(name="list")
@click.option("--limit", "-n", type=int, default=20, help="Number of entries to show")
@click.option("--offset", type=int, default=0, help="Skip first N entries")
@click.option("--all", "-a", "show_all", is_flag=True, help="Show all entries")
@click.option("--type", "-t", "entry_type", help="Filter by entry type")
@click.option("--author", help="Filter by author")
@click.option("--year", type=int, help="Filter by year")
@click.option("--tag", help="Filter by tag")
@click.option("--sort", "-s", default="key", help="Sort by field (e.g., 'year:desc')")
@click.option("--reverse", "-r", is_flag=True, help="Reverse sort order")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "compact", "json", "bibtex", "csv", "keys"]),
    default="table",
    help="Output format",
)
@click.pass_context
def list_cmd(ctx: click.Context, **kwargs) -> None:
    """List bibliography entries."""
    console = ctx.obj.console
    repository = get_repository(ctx)

    try:
        # Build query
        query_builder = QueryBuilder()

        if kwargs.get("entry_type"):
            query_builder.where("type", "=", kwargs["entry_type"])
        if kwargs.get("author"):
            query_builder.where("author", "contains", kwargs["author"])
        if kwargs.get("year"):
            query_builder.where("year", "=", kwargs["year"])

        # Parse sort
        sort_field, sort_order = _parse_sort(kwargs.get("sort", "key"))
        # Apply reverse flag if present
        if kwargs.get("reverse"):
            ascending = sort_order == "desc"  # Flip the order
        else:
            ascending = sort_order != "desc"
        query_builder.order_by(sort_field, ascending=ascending)

        # Set limit
        if not kwargs.get("show_all"):
            query_builder.limit(kwargs["limit"]).offset(kwargs["offset"])

        # Execute query
        query_builder.build()
        entries = repository.find_by(query_builder)
        total = repository.count()

        # Handle empty results
        if not entries:
            console.print("[dim]No entries found[/dim]")
            return

        # Display results
        if kwargs["format"] == "table":
            _display_entries_table(
                console, entries, total, kwargs["limit"], kwargs["offset"]
            )
        elif kwargs["format"] == "compact":
            _display_entries_compact(console, entries)
        elif kwargs["format"] == "json":
            from bibmgr.cli.formatters.json import format_entries_json

            console.print(format_entries_json(entries))
        elif kwargs["format"] == "bibtex":
            from bibmgr.cli.formatters.bibtex import format_entries_bibtex

            console.print(format_entries_bibtex(entries))
        elif kwargs["format"] == "csv":
            from bibmgr.cli.formatters.csv import format_entries_csv

            console.print(format_entries_csv(entries))
        elif kwargs["format"] == "keys":
            # Just print the keys, one per line
            for entry in entries:
                console.print(entry.key)

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Command: edit
@entry.command()
@click.argument("key")
@click.option(
    "--field", "-f", multiple=True, help="Field to edit (format: field=value)"
)
@click.option("--editor", "-e", is_flag=True, help="Open in external editor")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.pass_context
def edit(
    ctx: click.Context,
    key: str,
    field: tuple[str, ...],
    editor: bool,
    interactive: bool,
) -> None:
    """Edit an existing entry."""
    console = ctx.obj.console
    repository = get_repository(ctx)

    try:
        # Find entry
        entry = repository.find(key)
        if not entry:
            console.print(f"[red]Entry not found:[/red] {key}")
            ctx.exit(1)

        # Build updates
        updates = {}

        if field:
            # Parse field updates
            for f in field:
                if "=" not in f:
                    console.print(
                        f"[red]Invalid field format:[/red] {f} (use FIELD=VALUE)"
                    )
                    ctx.exit(1)
                field_name, value = f.split("=", 1)
                # Convert year to int if needed
                if field_name == "year":
                    try:
                        value = int(value)
                    except ValueError:
                        console.print(f"[red]Invalid year:[/red] {value}")
                        ctx.exit(1)
                updates[field_name] = value
        elif editor:
            # Open in external editor
            updates = _edit_in_editor(console, entry)
        elif interactive:
            # Interactive edit
            updates = _edit_interactive(console, entry)
        else:
            console.print(
                "[yellow]No changes specified. Use -f, -e, or -i option.[/yellow]"
            )
            ctx.exit(0)

        if not updates:
            console.print("[yellow]No changes made.[/yellow]")
            return

        # Execute update
        command = UpdateCommand(key=key, updates=updates)
        handler = get_update_handler(ctx)
        result = handler.execute(command)

        if result.status == ResultStatus.SUCCESS:
            console.print(f"[green]✓[/green] Entry updated successfully: {key}")
        else:
            console.print(f"[red]Error:[/red] {result.message}")
            ctx.exit(1)

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Command: delete
@entry.command()
@click.argument("keys", nargs=-1, required=False)
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.option("--all", "-a", "delete_all", is_flag=True, help="Delete all entries")
@click.pass_context
def delete(
    ctx: click.Context, keys: tuple[str, ...], force: bool, delete_all: bool
) -> None:
    """Delete one or more entries."""
    # Validate arguments at Click level for proper exit codes
    if not delete_all and not keys:
        raise click.UsageError("Missing argument 'KEYS' or use --all flag.")

    console = ctx.obj.console
    repository = get_repository(ctx)

    try:
        # Handle delete all
        if delete_all:
            if not force:
                if not Confirm.ask("[red]Delete ALL entries?[/red]"):
                    console.print("[yellow]Cancelled.[/yellow]")
                    return

            all_entries = repository.find_all()
            count = len(all_entries)

            # Delete each entry individually
            for entry in all_entries:
                repository.delete(entry.key)

            console.print(f"[green]✓[/green] Deleted all {count} entries")
            return

        # Verify entries exist
        missing = []
        for key in keys:
            if not repository.find(key):
                missing.append(key)

        if missing:
            console.print(f"[red]Entries not found:[/red] {', '.join(missing)}")
            ctx.exit(1)

        # Confirm deletion
        if not force:
            if len(keys) == 1:
                # Show entry details for single deletion
                entry = repository.find(keys[0])
                console.print("\n[bold]Entry to delete:[/bold]")
                console.print(f"  Key: {entry.key}")
                console.print(f"  Title: {entry.title}")
                if entry.author:
                    console.print(f"  Authors: {entry.author}")
                console.print()
                if not Confirm.ask("Are you sure you want to delete this entry?"):
                    console.print("[yellow]Deletion cancelled.[/yellow]")
                    return
            else:
                if not Confirm.ask(
                    f"Are you sure you want to delete {len(keys)} entries?"
                ):
                    console.print("[yellow]Deletion cancelled.[/yellow]")
                    return

        # Delete entries
        handler = get_delete_handler(ctx)
        successful = 0
        failed = 0

        for key in keys:
            command = DeleteCommand(key=key)
            result = handler.execute(command)
            if result.status != ResultStatus.SUCCESS:
                console.print(f"[red]Failed to delete:[/red] {key}")
                failed += 1
            else:
                successful += 1

        # Display appropriate message based on results
        if failed == 0:
            # All deletions succeeded
            if len(keys) == 1:
                console.print(f"[green]✓[/green] Entry deleted successfully: {keys[0]}")
            else:
                console.print(
                    f"[green]✓[/green] Successfully deleted {len(keys)} entries"
                )
        elif successful == 0:
            # All deletions failed
            console.print(f"[red]Failed to delete all {len(keys)} entries[/red]")
            ctx.exit(1)
        else:
            # Partial success
            console.print(f"Deleted {successful} of {len(keys)} entries")

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Helper functions
def _collect_entry_fields_interactive(
    console: Console, entry_type: EntryType, existing: dict
) -> dict:
    """Collect entry fields interactively."""
    fields = {}

    # Key
    fields["key"] = existing.get("key") or Prompt.ask("Key", default="")

    # Title (required)
    fields["title"] = existing.get("title") or Prompt.ask("Title")

    # Author (required for most types)
    if entry_type != EntryType.MISC:
        fields["author"] = existing.get("author") or Prompt.ask("Author(s)")

    # Year
    year_str = existing.get("year") or Prompt.ask("Year", default="")
    if year_str:
        fields["year"] = int(year_str)

    # Type-specific fields
    if entry_type == EntryType.ARTICLE:
        fields["journal"] = existing.get("journal") or Prompt.ask("Journal", default="")
    elif entry_type == EntryType.INPROCEEDINGS:
        fields["booktitle"] = existing.get("booktitle") or Prompt.ask(
            "Conference/Book title", default=""
        )
    elif entry_type == EntryType.BOOK:
        fields["publisher"] = existing.get("publisher") or Prompt.ask(
            "Publisher", default=""
        )

    # Optional fields
    try:
        if Prompt.ask("Add more fields?", choices=["y", "n"], default="n") == "y":
            fields["doi"] = existing.get("doi") or Prompt.ask("DOI", default="")
            fields["url"] = existing.get("url") or Prompt.ask("URL", default="")
            fields["abstract"] = existing.get("abstract") or Prompt.ask(
                "Abstract", default=""
            )
            fields["keywords"] = existing.get("keywords") or Prompt.ask(
                "Keywords (comma-separated)", default=""
            )
    except (EOFError, KeyboardInterrupt):
        # User ended input or pressed Ctrl+C, use defaults
        pass

    # Remove empty fields
    return {k: v for k, v in fields.items() if v}


def _display_entry_rich(console: Console, entry: Entry, metadata=None) -> None:
    """Display entry in rich format."""
    from rich.panel import Panel
    from rich.table import Table

    # Create details table
    table = Table(show_header=False, show_edge=False, pad_edge=False)
    table.add_column("Field", style="cyan", width=12)
    table.add_column("Value")

    # Add fields
    table.add_row("Type", entry.type.value)
    table.add_row("Title", entry.title)
    if entry.author:
        table.add_row("Authors", entry.author)
    if entry.year:
        table.add_row("Year", str(entry.year))
    if entry.journal:
        table.add_row("Journal", entry.journal)
    if entry.booktitle:
        table.add_row("Book/Conf", entry.booktitle)
    if entry.pages:
        table.add_row("Pages", entry.pages)
    if entry.doi:
        table.add_row("DOI", entry.doi)
    if entry.url:
        table.add_row("URL", entry.url)

    # Add metadata if available
    if metadata:
        if metadata.tags:
            tags_str = ", ".join(sorted(metadata.tags))
            table.add_row("Tags", tags_str)
        if metadata.rating:
            rating_str = "★" * metadata.rating + "☆" * (5 - metadata.rating)
            table.add_row("Rating", rating_str)
        if metadata.read_status:
            table.add_row("Read Status", metadata.read_status)
        if metadata.importance:
            table.add_row("Importance", metadata.importance)
        if metadata.notes_count:
            table.add_row("Notes", f"{metadata.notes_count} notes")

    # Display in panel
    panel = Panel(table, title=f"[bold]{entry.key}[/bold]", border_style="blue")
    console.print(panel)


def _display_entries_table(
    console: Console, entries: list[Entry], total: int, limit: int, offset: int
) -> None:
    """Display entries in table format."""
    table = Table(title=f"Bibliography Entries ({len(entries)} of {total})")

    # Add columns
    table.add_column("Key", style="cyan")
    table.add_column("Title", overflow="ellipsis", max_width=40)
    table.add_column("Authors", overflow="ellipsis", max_width=20)
    table.add_column("Year", justify="center")
    table.add_column("Type", style="magenta")

    # Add rows
    for entry in entries:
        table.add_row(
            entry.key,
            entry.title or "",
            (entry.author or "")[:20] + "..."
            if entry.author and len(entry.author) > 20
            else entry.author or "",
            str(entry.year) if entry.year else "",
            entry.type.value,
        )

    console.print(table)

    # Show pagination info
    if len(entries) == total:
        # All entries shown
        console.print(f"\n[dim]Showing {total} of {total} entries[/dim]")
    else:
        # Partial list shown
        console.print(
            f"\n[dim]Showing {len(entries)} of {total} entries • Use --all to show all[/dim]"
        )


def _display_entries_compact(console: Console, entries: list[Entry]) -> None:
    """Display entries in compact format."""
    for entry in entries:
        author_short = entry.author.split(",")[0] if entry.author else "Unknown"
        year = str(entry.year) if entry.year else "----"
        console.print(
            f"{entry.key:20} {author_short:15} {year:4} {(entry.title or '')[:50]}"
        )


def _parse_sort(sort_spec: str) -> tuple[str, str]:
    """Parse sort specification like 'year:desc'."""
    if ":" in sort_spec:
        field, order = sort_spec.split(":", 1)
        return field, order.lower()
    return sort_spec, "asc"


def _edit_in_editor(console: Console, entry: Entry) -> dict:
    """Edit entry in external editor."""
    import os
    import subprocess
    import tempfile

    from bibmgr.storage.importers.bibtex import BibtexImporter

    # Get editor
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"

    # Create temp file with current entry
    with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
        from bibmgr.cli.formatters.bibtex import format_entry_bibtex

        f.write(format_entry_bibtex(entry))
        temp_path = f.name

    try:
        # Open editor - handle editor commands with arguments
        import shlex

        editor_cmd = shlex.split(editor) + [temp_path]
        subprocess.call(editor_cmd)

        # Parse result
        importer = BibtexImporter()
        with open(temp_path) as f:
            entries, _ = importer.import_text(f.read())

        if not entries:
            return {}

        # Compare and extract changes
        new_entry = entries[0]
        updates = {}

        # Get all field names from the entry
        for field in entry.__struct_fields__:
            old_value = getattr(entry, field)
            new_value = getattr(new_entry, field)
            if old_value != new_value:
                updates[field] = new_value

        return updates

    finally:
        os.unlink(temp_path)


def _edit_interactive(console: Console, entry: Entry) -> dict:
    """Edit entry interactively."""
    console.print("[bold]Editing entry:[/bold] " + entry.key)
    console.print("[dim]Press Enter to keep current value[/dim]\n")

    updates = {}

    try:
        # Title
        new_title = Prompt.ask(f"Title [{entry.title}]", default=entry.title)
        if new_title != entry.title:
            updates["title"] = new_title

        # Author
        if entry.author:
            new_author = Prompt.ask(f"Author [{entry.author}]", default=entry.author)
            if new_author != entry.author:
                updates["author"] = new_author

        # Year
        if entry.year:
            new_year = Prompt.ask(f"Year [{entry.year}]", default=str(entry.year))
            if new_year != str(entry.year):
                updates["year"] = int(new_year)

        # Type-specific fields
        if entry.type == EntryType.ARTICLE and entry.journal:
            new_journal = Prompt.ask(
                f"Journal [{entry.journal}]", default=entry.journal
            )
            if new_journal != entry.journal:
                updates["journal"] = new_journal

    except (EOFError, KeyboardInterrupt):
        # User ended input, return what we have so far
        pass

    return updates
