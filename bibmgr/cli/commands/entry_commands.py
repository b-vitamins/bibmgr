"""Entry management commands."""

from __future__ import annotations

import json
from typing import Optional, Tuple

import click

from bibmgr.core.models import Entry, EntryType
from bibmgr.operations.crud import EntryOperations
from bibmgr.storage.backend import FileSystemStorage
from bibmgr.collections.manager import CollectionManager, FileCollectionRepository
from bibmgr.collections.tags import TagManager

from ..config import get_config
from ..formatters import (
    format_entry_table,
    format_entry_bibtex,
    format_entry_json,
    format_entry_yaml,
    format_entries_list,
)
from ..helpers import (
    parse_field_assignments,
    filter_entries,
    sort_entries,
    confirm_action,
    handle_error,
)
from ..output import (
    print_success,
    print_error,
    print_warning,
    print_json,
)
from ..validators import (
    validate_entry_key,
    validate_entry_type,
    validate_year,
)


def get_storage() -> FileSystemStorage:
    """Get storage backend instance."""
    config = get_config()
    return FileSystemStorage(config.database_path)


def get_operations() -> EntryOperations:
    """Get operations handler."""
    return EntryOperations(get_storage())


def get_collection_manager() -> CollectionManager:
    """Get collection manager instance."""
    config = get_config()
    repository = FileCollectionRepository(config.database_path.parent / "collections")
    return CollectionManager(repository, get_storage())


def get_tag_manager() -> TagManager:
    """Get tag manager instance."""
    config = get_config()
    return TagManager(config.database_path.parent / "tags")


@click.command()
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.option("--type", "-t", help="Entry type")
@click.option("--key", "-k", help="Citation key")
@click.option("--title", help="Entry title")
@click.option("--author", help="Entry authors")
@click.option("--year", type=int, help="Publication year")
@click.option("--journal", help="Journal name")
@click.option("--booktitle", help="Book title (for inproceedings)")
@click.option("--publisher", help="Publisher")
@click.option("--school", help="School (for theses)")
@click.option("--volume", help="Volume")
@click.option("--number", help="Number/Issue")
@click.option("--pages", help="Pages")
@click.option("--doi", help="DOI")
@click.option("--url", help="URL")
@click.option("--abstract", help="Abstract")
@click.option("--keywords", help="Keywords (comma-separated)")
@click.option("--from-file", type=click.Path(exists=True), help="Load from file")
@click.option("--dry-run", is_flag=True, help="Preview without saving")
@click.pass_context
def add(ctx: click.Context, **kwargs):
    """Add a new bibliography entry."""
    try:
        # Load from file if specified
        if kwargs["from_file"]:
            with open(kwargs["from_file"]) as f:
                data = json.load(f)

            # Override with file data
            for key, value in data.items():
                if value is not None:
                    kwargs[key] = value

        # Interactive mode (only if explicitly requested)
        if kwargs["interactive"]:
            kwargs = _interactive_add(kwargs)

        # Validate required fields
        missing = []
        if not kwargs.get("key"):
            missing.append("key")
        if not kwargs.get("type"):
            missing.append("type")
        if not kwargs.get("title"):
            missing.append("title")

        if missing:
            handle_error(f"Missing required fields: {', '.join(missing)}")
            return

        # Validate and create entry
        key = validate_entry_key(kwargs["key"])
        entry_type = validate_entry_type(kwargs["type"])

        # Build entry
        entry_data = {
            "key": key,
            "type": entry_type,
            "title": kwargs["title"],
        }

        # Add optional fields
        for field in [
            "author",
            "year",
            "journal",
            "booktitle",
            "publisher",
            "school",
            "volume",
            "number",
            "pages",
            "doi",
            "url",
            "abstract",
        ]:
            if kwargs.get(field):
                if field == "year":
                    entry_data[field] = validate_year(kwargs[field])
                else:
                    entry_data[field] = kwargs[field]

        # Handle keywords
        if kwargs.get("keywords"):
            if isinstance(kwargs["keywords"], str):
                entry_data["keywords"] = [
                    k.strip() for k in kwargs["keywords"].split(",")
                ]
            else:
                entry_data["keywords"] = kwargs["keywords"]

        entry = Entry(**entry_data)

        # Preview if dry-run
        if kwargs["dry_run"]:
            print_warning("Preview (dry-run):")
            click.echo(format_entry_table(entry))
            return

        # Add entry
        operations = get_operations()
        result = operations.create(entry)

        if result.success:
            print_success(f"Added entry: {key}")
        else:
            error_msg = result.message or "Unknown error"
            if result.errors:
                error_msg = "; ".join(result.errors)
            handle_error(f"Failed to add entry: {error_msg}")

    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        handle_error(str(e))


def _interactive_add(initial: dict) -> dict:
    """Interactive entry addition."""
    data = initial.copy()

    if not data.get("type"):
        types = [t.value for t in EntryType]
        data["type"] = click.prompt(
            "Entry type", type=click.Choice(types), default=EntryType.ARTICLE.value
        )

    if not data.get("key"):
        data["key"] = click.prompt("Citation key")

    if not data.get("title"):
        data["title"] = click.prompt("Title")

    if not data.get("author"):
        data["author"] = click.prompt("Author(s)", default="")

    if not data.get("year"):
        year_str = click.prompt("Year", default="")
        if year_str:
            data["year"] = int(year_str)

    # Type-specific fields
    entry_type = data["type"].lower()

    if entry_type == "article":
        if not data.get("journal"):
            data["journal"] = click.prompt("Journal", default="")
        if not data.get("volume"):
            data["volume"] = click.prompt("Volume", default="")
        if not data.get("pages"):
            data["pages"] = click.prompt("Pages", default="")

    elif entry_type == "inproceedings":
        if not data.get("booktitle"):
            data["booktitle"] = click.prompt("Book title/Conference")

    elif entry_type == "book":
        if not data.get("publisher"):
            data["publisher"] = click.prompt("Publisher")

    elif entry_type in ["phdthesis", "mastersthesis"]:
        if not data.get("school"):
            data["school"] = click.prompt("School/University")

    # Optional fields
    if not data.get("doi"):
        data["doi"] = click.prompt("DOI", default="")

    if not data.get("url"):
        data["url"] = click.prompt("URL", default="")

    return data


@click.command()
@click.argument("key")
@click.option("--field", "-f", multiple=True, help="Field to edit (field=value)")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.option("--validate", is_flag=True, help="Validate changes")
@click.option("--dry-run", is_flag=True, help="Preview without saving")
@click.pass_context
def edit(
    ctx: click.Context,
    key: str,
    field: Tuple[str, ...],
    interactive: bool,
    validate: bool,
    dry_run: bool,
):
    """Edit an existing entry."""
    try:
        storage = get_storage()
        entry = storage.read(key)

        if not entry:
            handle_error(f"Entry not found: {key}")
            return

        # Parse field assignments
        if field:
            changes = parse_field_assignments(list(field))
        else:
            changes = {}

        # Interactive mode
        if interactive or not changes:
            changes = _interactive_edit(entry)

        if not changes:
            print_warning("No changes made")
            return

        # Validate changes
        if validate:
            for field_name, value in changes.items():
                if field_name == "year" and value:
                    changes[field_name] = str(validate_year(value))
                elif field_name == "type" and value:
                    changes[field_name] = validate_entry_type(value).value

        # Preview
        if dry_run:
            print_warning("Preview (dry-run):")
            for field_name, value in changes.items():
                click.echo(f"  {field_name}: {value}")
            return

        # Apply changes
        operations = get_operations()
        result = operations.update(key, changes)

        if result.success:
            print_success(f"Updated entry: {key}")
        else:
            error_msg = result.message or "Unknown error"
            if result.errors:
                error_msg = "; ".join(result.errors)
            handle_error(f"Failed to update: {error_msg}")

    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        handle_error(str(e))


def _interactive_edit(entry: Entry) -> dict:
    """Interactive entry editing."""
    changes = {}

    click.echo("\nCurrent entry:")
    click.echo(format_entry_table(entry))
    click.echo("\nEnter field name to edit (empty to finish):")

    while True:
        field_name = click.prompt("Field", default="", show_default=False)
        if not field_name:
            break

        current_value = getattr(entry, field_name, None)
        if current_value is not None:
            click.echo(f"Current {field_name}: {current_value}")

        new_value = click.prompt(
            f"New {field_name}", default=str(current_value) if current_value else ""
        )

        if new_value and new_value != str(current_value):
            changes[field_name] = new_value

    return changes


@click.command()
@click.argument("keys", nargs=-1, required=True)
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.option("--cascade", is_flag=True, help="Remove related data")
@click.pass_context
def delete(ctx: click.Context, keys: Tuple[str, ...], force: bool, cascade: bool):
    """Delete one or more entries."""
    try:
        storage = get_storage()
        operations = get_operations()

        # Verify entries exist
        entries_to_delete = []
        for key in keys:
            entry = storage.read(key)
            if not entry:
                print_warning(f"Entry not found: {key}")
            else:
                entries_to_delete.append(entry)

        if not entries_to_delete:
            handle_error("No valid entries to delete")
            return

        # Show entries to be deleted
        if not force:
            click.echo("Entries to delete:")
            for entry in entries_to_delete:
                click.echo(f"  • {entry.key}: {entry.title}")

            if not confirm_action(f"\nDelete {len(entries_to_delete)} entries?"):
                print_warning("Cancelled")
                return

        # Delete entries
        deleted = 0
        failed = []

        for entry in entries_to_delete:
            from bibmgr.operations.crud import CascadeOptions

            cascade_opts = (
                CascadeOptions(
                    delete_notes=cascade,
                    delete_metadata=cascade,
                    delete_attachments=cascade,
                )
                if cascade
                else None
            )
            result = operations.delete(entry.key, cascade=cascade_opts)
            if result.success:
                deleted += 1
            else:
                error_msg = result.message or "Unknown error"
                if result.errors:
                    error_msg = "; ".join(result.errors)
                failed.append((entry.key, error_msg))

        # Report results
        if deleted > 0:
            print_success(f"Deleted {deleted} entries")

        if failed:
            print_error(f"Failed to delete {len(failed)} entries:")
            for key, error in failed:
                click.echo(f"  • {key}: {error}")

    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        handle_error(str(e))


@click.command()
@click.argument("keys", nargs=-1, required=True)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "bibtex", "json", "yaml"]),
    default="table",
    help="Output format",
)
@click.option("--fields", help="Comma-separated list of fields to show")
@click.option("--syntax", is_flag=True, help="Enable syntax highlighting")
@click.pass_context
def show(
    ctx: click.Context,
    keys: Tuple[str, ...],
    format: str,
    fields: Optional[str],
    syntax: bool,
):
    """Display one or more entries."""
    try:
        storage = get_storage()

        for key in keys:
            entry = storage.read(key)

            if not entry:
                print_warning(f"Entry not found: {key}")
                continue

            # Format output
            if format == "json":
                output = format_entry_json(entry)
                if syntax:
                    from rich.syntax import Syntax
                    from ..output import console

                    if console:
                        console.print(Syntax(output, "json"))
                else:
                    click.echo(output)

            elif format == "yaml":
                output = format_entry_yaml(entry)
                if syntax:
                    from rich.syntax import Syntax
                    from ..output import console

                    if console:
                        console.print(Syntax(output, "yaml"))
                else:
                    click.echo(output)

            elif format == "bibtex":
                output = format_entry_bibtex(entry)
                if syntax:
                    from rich.syntax import Syntax
                    from ..output import console

                    if console:
                        console.print(Syntax(output, "latex"))
                else:
                    click.echo(output)

            else:  # table
                click.echo(format_entry_table(entry))

            if len(keys) > 1:
                click.echo()  # Separator between entries

    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        handle_error(str(e))


@click.command(name="list")
@click.option("--type", "-t", help="Filter by type")
@click.option("--author", "-a", help="Filter by author")
@click.option("--year", "-y", type=int, help="Filter by year")
@click.option("--year-range", help="Year range (e.g., 2020-2023)")
@click.option("--tag", help="Filter by tag")
@click.option("--collection", "-c", help="Filter by collection")
@click.option("--limit", "-l", default=50, help="Max entries to show")
@click.option("--offset", default=0, help="Offset for pagination")
@click.option(
    "--sort",
    type=click.Choice(["key", "title", "year", "author", "type"]),
    default="key",
    help="Sort field",
)
@click.option("--reverse", is_flag=True, help="Reverse sort order")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "compact", "keys", "json"]),
    default="table",
    help="Output format",
)
@click.pass_context
def list_entries(ctx: click.Context, **kwargs):
    """List bibliography entries with filters."""
    try:
        storage = get_storage()
        entries = storage.read_all()

        # Apply filters
        if kwargs["type"]:
            entries = filter_entries(entries, type=kwargs["type"])

        if kwargs["author"]:
            entries = filter_entries(entries, author=kwargs["author"])

        if kwargs["year"]:
            entries = filter_entries(entries, year=kwargs["year"])

        if kwargs["year_range"]:
            parts = kwargs["year_range"].split("-")
            if len(parts) == 2:
                start, end = int(parts[0]), int(parts[1])
                entries = filter_entries(entries, year=range(start, end + 1))

        if kwargs["collection"]:
            # Filter by collection
            collection_manager = get_collection_manager()
            collection = collection_manager.get_collection(kwargs["collection"])
            if collection:
                # Filter entries to only those in the collection
                collection_keys = collection.entry_keys
                entries = [e for e in entries if e.key in collection_keys]
            else:
                print_warning(f"Collection not found: {kwargs['collection']}")
                entries = []

        if kwargs["tag"]:
            # Filter by tag (using keywords field for now)
            tag = kwargs["tag"].lower()
            tagged_entries = []
            for entry in entries:
                if entry.keywords:
                    # Check if tag is in keywords (case-insensitive)
                    keywords = [k.strip().lower() for k in entry.keywords.split(",")]
                    if tag in keywords:
                        tagged_entries.append(entry)
            entries = tagged_entries

        # Sort
        entries = sort_entries(entries, by=kwargs["sort"], reverse=kwargs["reverse"])

        # Pagination
        total = len(entries)
        offset = kwargs["offset"]
        limit = kwargs["limit"]
        entries = entries[offset : offset + limit]

        # Display
        if not entries:
            print_warning("No entries found")
            return

        if kwargs["format"] == "json":
            data = []
            for entry in entries:
                entry_dict = json.loads(format_entry_json(entry))
                data.append(entry_dict)
            print_json(data)
        else:
            output = format_entries_list(entries, format=kwargs["format"])
            click.echo(output)

        # Show pagination info
        if total > limit:
            shown = len(entries)
            remaining = total - offset - shown
            if remaining > 0:
                click.echo(
                    f"\nShowing {shown} of {total} entries. "
                    f"Use --offset {offset + limit} to see more."
                )

    except Exception as e:
        if ctx.obj.get("debug"):
            raise
        handle_error(str(e))
