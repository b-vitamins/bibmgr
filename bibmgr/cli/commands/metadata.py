"""Metadata management commands for bibliography entries.

Provides commands for managing tags, notes, ratings, and other metadata
associated with bibliography entries.
"""

import builtins
import json
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

# from bibmgr.cli.utils.context import pass_context
from bibmgr.cli.formatters import format_entry_table
from bibmgr.cli.utils.editor import open_in_editor
from bibmgr.storage.metadata import EntryMetadata, Note

console = Console()


def get_repository(ctx):
    """Get the entry repository from context."""
    return ctx.obj.repository


def get_metadata_store(ctx):
    """Get the metadata store from context."""
    return ctx.obj.metadata_store


@click.group()
def metadata():
    """Manage entry metadata (tags, notes, ratings)."""
    pass


@metadata.command()
@click.argument(
    "entry_key",
)
@click.pass_context
def show(ctx, entry_key: str):
    """Show all metadata for an entry."""
    repo = get_repository(ctx)
    store = get_metadata_store(ctx)

    # Verify entry exists
    entry = repo.find(key=entry_key)
    if not entry:
        console.print(f"[red]Entry not found:[/red] {entry_key}")
        ctx.exit(1)

    metadata = store.get_metadata(entry_key)
    notes = store.get_notes(entry_key)

    # Build metadata display
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    # Tags
    if metadata.tags:
        tags_str = ", ".join(sorted(metadata.tags))
        table.add_row("Tags", tags_str)

    # Rating
    if metadata.rating:
        stars = "★" * metadata.rating + "☆" * (5 - metadata.rating)
        table.add_row("Rating", f"[yellow]{stars}[/yellow]")

    # Read status
    status_color = {"unread": "dim", "reading": "yellow", "read": "green"}.get(
        metadata.read_status, "white"
    )

    status_str = f"[{status_color}]{metadata.read_status.title()}[/{status_color}]"
    if metadata.read_date:
        status_str += f" ({metadata.read_date.strftime('%Y-%m-%d')})"
    table.add_row("Read Status", status_str)

    # Importance
    importance_color = {"low": "dim", "normal": "white", "high": "red"}.get(
        metadata.importance, "white"
    )
    table.add_row(
        "Importance", f"[{importance_color}]{metadata.importance}[/{importance_color}]"
    )

    # Notes count - use notes_count from metadata if available
    if hasattr(metadata, "notes_count") and metadata.notes_count:
        table.add_row("Notes", f"{metadata.notes_count}")
    elif notes:
        table.add_row("Notes", f"{len(notes)}")

    panel = Panel(table, title=f"Metadata for {entry_key}", title_align="left")
    console.print(panel)


@metadata.command(name="set")
@click.argument(
    "entry_key",
)
@click.option("--rating", type=click.IntRange(1, 5), help="Set rating (1-5)")
@click.option(
    "--read-status",
    type=click.Choice(["unread", "reading", "read"]),
    help="Set read status",
)
@click.option(
    "--importance",
    type=click.Choice(["low", "normal", "high"]),
    help="Set importance level",
)
@click.option("--tag", "tags", multiple=True, help="Add tags")
@click.pass_context
def set_metadata(
    ctx,
    entry_key: str,
    rating: int | None,
    read_status: str | None,
    importance: str | None,
    tags: tuple[str, ...],
):
    """Set metadata for an entry."""
    repo = get_repository(ctx)
    store = get_metadata_store(ctx)

    # Verify entry exists
    entry = repo.find(key=entry_key)
    if not entry:
        console.print(f"[red]Entry not found:[/red] {entry_key}")
        ctx.exit(1)

    metadata = store.get_metadata(entry_key)
    updated = False

    if rating is not None:
        metadata.rating = rating
        updated = True

    if read_status is not None:
        metadata.read_status = read_status
        if read_status == "read" and not metadata.read_date:
            metadata.read_date = datetime.now()
        elif read_status != "read":
            metadata.read_date = None
        updated = True

    if importance is not None:
        metadata.importance = importance
        updated = True

    if tags:
        metadata.add_tags(*tags)
        updated = True

    if updated:
        store.save_metadata(metadata)
        console.print(f"[green]✓[/green] Updated metadata for {entry_key}")
    else:
        console.print("[yellow]No changes specified[/yellow]")


@metadata.command()
@click.option("--entries", required=True, help="Comma-separated list of entry keys")
@click.option("--tag", "tags", multiple=True, help="Tags to add")
@click.option("--rating", type=click.IntRange(1, 5), help="Set rating")
@click.option(
    "--read-status",
    type=click.Choice(["unread", "reading", "read"]),
    help="Set read status",
)
@click.option(
    "--importance", type=click.Choice(["low", "normal", "high"]), help="Set importance"
)
@click.pass_context
def bulk_set(
    ctx,
    entries: str,
    tags: tuple[str, ...],
    rating: int | None,
    read_status: str | None,
    importance: str | None,
):
    """Update metadata for multiple entries."""
    repo = get_repository(ctx)
    store = get_metadata_store(ctx)

    entry_keys = [k.strip() for k in entries.split(",") if k.strip()]
    updated_count = 0

    with console.status("Updating metadata..."):
        for key in entry_keys:
            entry = repo.find(key=key)
            if not entry:
                console.print(f"[yellow]Warning:[/yellow] Entry not found: {key}")
                continue

            metadata = store.get_metadata(key)

            if tags:
                metadata.add_tags(*tags)
            if rating is not None:
                metadata.rating = rating
            if read_status is not None:
                metadata.read_status = read_status
                if read_status == "read" and not metadata.read_date:
                    metadata.read_date = datetime.now()
            if importance is not None:
                metadata.importance = importance

            store.save_metadata(metadata)
            updated_count += 1

    console.print(f"[green]✓[/green] Updated metadata for {updated_count} entries")


@metadata.command()
@click.argument(
    "entry_key",
)
@click.pass_context
def clear(ctx, entry_key: str):
    """Clear all metadata for an entry."""
    repo = get_repository(ctx)
    store = get_metadata_store(ctx)

    # Verify entry exists
    entry = repo.find(key=entry_key)
    if not entry:
        console.print(f"[red]Entry not found:[/red] {entry_key}")
        ctx.exit(1)

    if not Confirm.ask(f"Clear all metadata for {entry_key}?"):
        return

    # Create fresh metadata
    metadata = EntryMetadata(entry_key=entry_key)
    store.save_metadata(metadata)

    console.print(f"[green]✓[/green] Cleared metadata for {entry_key}")


@metadata.command()
@click.argument("output_file", type=click.Path())
@click.pass_context
def export(ctx, output_file: str):
    """Export all metadata to a JSON file."""
    store = get_metadata_store(ctx)

    # Collect all metadata
    export_data = {}

    for path in store.metadata_dir.glob("*.json"):
        try:
            with open(path) as f:
                data = json.load(f)
            entry_key = data["entry_key"]
            export_data[entry_key] = data
        except Exception:
            pass

    # Write to file
    output_path = Path(output_file)
    with open(output_path, "w") as f:
        json.dump(export_data, f, indent=2)

    console.print(
        f"[green]✓[/green] Exported metadata for {len(export_data)} entries to {output_path}"
    )


@metadata.command("import")
@click.argument("input_file", type=click.Path(exists=True))
@click.pass_context
def import_metadata(ctx, input_file: str):
    """Import metadata from a JSON file."""
    store = get_metadata_store(ctx)

    # Load import data
    with open(input_file) as f:
        import_data = json.load(f)

    imported_count = 0

    with console.status("Importing metadata..."):
        for entry_key, data in import_data.items():
            try:
                # Add entry_key to the data
                data["entry_key"] = entry_key
                metadata = EntryMetadata.from_dict(data)
                store.save_metadata(metadata)
                imported_count += 1
            except Exception as e:
                console.print(
                    f"[yellow]Warning:[/yellow] Failed to import metadata for {entry_key}: {e}"
                )

    console.print(f"[green]✓[/green] Imported metadata for {imported_count} entries")


# Tag command group
@click.group()
def tag():
    """Manage entry tags."""
    pass


@tag.command()
@click.argument("args", nargs=-1, required=True)
@click.option("--entries", help="Apply to multiple entries (comma-separated)")
@click.pass_context
def add(ctx, args: tuple[str, ...], entries: str | None):
    """Add tags to entries.

    Usage:
        tag add ENTRY_KEY TAG1 [TAG2 ...]
        tag add --entries ENTRY1,ENTRY2 TAG1 [TAG2 ...]
    """
    repo = get_repository(ctx)
    store = get_metadata_store(ctx)

    # Parse arguments based on whether --entries is used
    if entries:
        # When using --entries, all args are tags
        entry_keys = [k.strip() for k in entries.split(",") if k.strip()]
        tags = args
    else:
        # When not using --entries, first arg is entry_key, rest are tags
        if len(args) < 2:
            console.print(
                "[red]Error:[/red] Must specify entry key and at least one tag"
            )
            ctx.exit(1)
        entry_keys = [args[0]]  # type: ignore
        tags = args[1:]

    if not tags:
        console.print("[red]Error:[/red] Must specify at least one tag")
        ctx.exit(1)

    added_count = 0

    for key in entry_keys:
        entry = repo.find(key=key)
        if not entry:
            console.print(f"[yellow]Warning:[/yellow] Entry not found: {key}")
            continue

        metadata = store.get_metadata(key)
        metadata.add_tags(*tags)
        store.save_metadata(metadata)
        added_count += 1

    if len(entry_keys) == 1:
        if len(tags) == 1:
            console.print(f"Added tag '{tags[0]}' to {entry_keys[0]}")
        else:
            console.print(f"Added {len(tags)} tags to {entry_keys[0]}")
    else:
        tags_str = ", ".join(f"'{t}'" for t in tags)
        console.print(
            f"Added tag{'s' if len(tags) > 1 else ''} {tags_str} to {added_count} entries"
        )


@tag.command()
@click.argument(
    "entry_key",
)
@click.argument(
    "tags",
    nargs=-1,
    required=True,
)
@click.pass_context
def remove(ctx, entry_key: str, tags: tuple[str, ...]):
    """Remove tags from an entry."""
    repo = get_repository(ctx)
    store = get_metadata_store(ctx)

    entry = repo.find(key=entry_key)
    if not entry:
        console.print(f"[red]Entry not found:[/red] {entry_key}")
        ctx.exit(1)

    metadata = store.get_metadata(entry_key)
    metadata.remove_tags(*tags)
    store.save_metadata(metadata)

    tags_str = ", ".join(f"'{t}'" for t in tags)
    console.print(
        f"Removed tag{'s' if len(tags) > 1 else ''} {tags_str} from {entry_key}"
    )


@tag.command()
@click.option(
    "--entry",
    help="Show tags for specific entry",
)
@click.pass_context
def list(ctx, entry: str | None):
    """List tags."""
    store = get_metadata_store(ctx)

    if entry:
        # Show tags for specific entry
        repo = get_repository(ctx)
        entry_obj = repo.find(key=entry)
        if not entry_obj:
            console.print(f"[red]Entry not found:[/red] {entry}")
            ctx.exit(1)

        metadata = store.get_metadata(entry)
        if metadata.tags:
            console.print(f"\n[bold]Tags for {entry}:[/bold]")
            for tag in sorted(metadata.tags):
                console.print(f"  • {tag}")
        else:
            console.print(f"[dim]No tags for {entry}[/dim]")
    else:
        # Show all tags with counts
        all_tags = store.get_all_tags()
        if not all_tags:
            console.print("[dim]No tags found[/dim]")
            return

        # Sort by count descending, then by tag name
        sorted_tags = sorted(all_tags.items(), key=lambda x: (-x[1], x[0]))

        for tag, count in sorted_tags:
            console.print(f"{tag} ({count})")


@tag.command()
@click.argument(
    "old_tag",
)
@click.argument("new_tag")
@click.pass_context
def rename(ctx, old_tag: str, new_tag: str):
    """Rename a tag across all entries."""
    store = get_metadata_store(ctx)

    # Check if old tag exists
    all_tags = store.get_all_tags()
    if old_tag not in all_tags:
        console.print(f"[red]Tag not found:[/red] {old_tag}")
        ctx.exit(1)

    count = all_tags[old_tag]
    if not Confirm.ask(f"Rename tag '{old_tag}' to '{new_tag}' in {count} entries?"):
        return

    renamed_count = store.rename_tag(old_tag, new_tag)
    console.print(
        f"[green]✓[/green] Renamed tag '{old_tag}' to '{new_tag}' in {renamed_count} entries"
    )


@tag.command()
@click.argument(
    "tag_name",
)
@click.pass_context
def find(ctx, tag_name: str):
    """Find entries with a specific tag."""
    repo = get_repository(ctx)
    store = get_metadata_store(ctx)

    entry_keys = store.find_by_tag(tag_name)
    if not entry_keys:
        console.print(f"[dim]No entries tagged with '{tag_name}'[/dim]")
        return

    # Get entries
    entries = []
    for key in entry_keys:
        entry = repo.find(key=key)
        if entry:
            entries.append(entry)

    # Display results
    console.print(f"\n[bold]{len(entries)} entries tagged with '{tag_name}'[/bold]\n")
    table = format_entry_table(entries, show_abstracts=False)
    console.print(table)


# Note command group
@click.group()
def note():
    """Manage entry notes."""
    pass


@note.command(name="add")
@click.argument(
    "entry_key",
)
@click.option("--content", help="Note content (opens editor if not provided)")
@click.option(
    "--type",
    "note_type",
    type=click.Choice(["general", "summary", "quote", "idea"]),
    default="general",
    help="Type of note",
)
@click.option("--page", type=int, help="Page number reference")
@click.pass_context
def add_note(
    ctx, entry_key: str, content: str | None, note_type: str, page: int | None
):
    """Add a note to an entry."""
    repo = get_repository(ctx)
    store = get_metadata_store(ctx)

    # Verify entry exists
    entry = repo.find(key=entry_key)
    if not entry:
        console.print(f"[red]Entry not found:[/red] {entry_key}")
        ctx.exit(1)

    # Get content
    tags: builtins.list[str] = []
    if content is None:
        if note_type == "quote":
            content = Prompt.ask("Quote")
            comment = Prompt.ask("Comment (optional)", default="")
            if comment:
                content = f'"{content}"\n\n{comment}'
        else:
            # Interactive prompts
            content = Prompt.ask("Content")
            note_type = Prompt.ask(
                "Type",
                default=note_type,
                choices=["general", "summary", "quote", "idea"],
            )
            page_input = Prompt.ask("Page number (optional)", default="")
            if page_input:
                try:
                    page = int(page_input)
                except ValueError:
                    console.print("[red]Invalid page number[/red]")
                    ctx.exit(1)

            tags_input = Prompt.ask("Tags (comma-separated, optional)", default="")
            tags = (
                [t.strip() for t in tags_input.split(",") if t.strip()]
                if tags_input
                else []
            )
    else:
        tags = []

    # Create note
    note = Note(
        entry_key=entry_key,
        content=content,
        note_type=note_type,
        page=page,
        tags=tags,
    )

    store.add_note(note)
    console.print(f"[green]✓[/green] Note added to {entry_key}")


@note.command(name="list")
@click.argument(
    "entry_key",
)
@click.pass_context
def list_notes(ctx, entry_key: str):
    """List notes for an entry."""
    repo = get_repository(ctx)
    store = get_metadata_store(ctx)

    # Verify entry exists
    entry = repo.find(key=entry_key)
    if not entry:
        console.print(f"[red]Entry not found:[/red] {entry_key}")
        ctx.exit(1)

    notes = store.get_notes(entry_key)
    if not notes:
        console.print(f"[dim]No notes for {entry_key}[/dim]")
        return

    console.print(f"\n[bold]📝 Notes for {entry_key}[/bold]\n")

    table = Table(show_header=True)
    table.add_column("Type", style="cyan")
    table.add_column("Created", style="dim")
    table.add_column("Preview")

    for note in notes:
        preview = note.content[:50] + "..." if len(note.content) > 50 else note.content
        preview = preview.replace("\n", " ")

        created_str = note.created.strftime("%Y-%m-%d")

        type_with_page = note.note_type
        if note.page:
            type_with_page += f" (Page {note.page})"

        table.add_row(type_with_page, created_str, preview)

    console.print(table)


@note.command()
@click.argument(
    "entry_key",
)
@click.argument("note_id")
@click.pass_context
def edit(ctx, entry_key: str, note_id: str):
    """Edit an existing note."""
    repo = get_repository(ctx)
    store = get_metadata_store(ctx)

    # Verify entry exists
    entry = repo.find(key=entry_key)
    if not entry:
        console.print(f"[red]Entry not found:[/red] {entry_key}")
        ctx.exit(1)

    # Find note
    notes = store.get_notes(entry_key)
    note = None
    for n in notes:
        if str(n.id).startswith(note_id):
            note = n
            break

    if not note:
        console.print(f"[red]Note not found:[/red] {note_id}")
        ctx.exit(1)

    assert note is not None  # For type checker
    # Edit content
    new_content = open_in_editor(note.content, suffix=".md")
    if new_content and new_content != note.content:
        note.content = new_content
        note.modified = datetime.now()
        store.add_note(note)  # This will overwrite the existing note
        console.print("[green]✓[/green] Note updated")
    else:
        console.print("[yellow]No changes made[/yellow]")


@note.command()
@click.argument(
    "entry_key",
)
@click.argument("note_id")
@click.pass_context
def delete(ctx, entry_key: str, note_id: str):
    """Delete a note."""
    repo = get_repository(ctx)
    store = get_metadata_store(ctx)

    # Verify entry exists
    entry = repo.find(key=entry_key)
    if not entry:
        console.print(f"[red]Entry not found:[/red] {entry_key}")
        ctx.exit(1)

    # Find note
    notes = store.get_notes(entry_key)
    note = None
    for n in notes:
        if str(n.id).startswith(note_id):
            note = n
            break

    if not note:
        console.print(f"[red]Note not found:[/red] {note_id}")
        ctx.exit(1)

    assert note is not None  # For type checker
    if not Confirm.ask("Delete this note?"):
        return

    if store.delete_note(entry_key, note.id):
        console.print("[green]✓[/green] Note deleted")
    else:
        console.print("[red]Failed to delete note[/red]")


@note.command()
@click.argument("search_term")
@click.pass_context
def search(ctx, search_term: str):
    """Search notes by content."""
    repo = get_repository(ctx)
    store = get_metadata_store(ctx)

    search_lower = search_term.lower()
    found_notes = []

    # Search all notes
    with console.status("Searching notes..."):
        # Get all entry keys from metadata files
        entry_keys = []
        for path in store.metadata_dir.glob("*.json"):
            entry_keys.append(path.stem)

        for entry_key in entry_keys:
            notes = store.get_notes(entry_key)
            for note in notes:
                if search_lower in note.content.lower():
                    found_notes.append((entry_key, note))

    if not found_notes:
        console.print(f"[dim]No notes found containing '{search_term}'[/dim]")
        return

    console.print(
        f"\n[bold]Found {len(found_notes)} notes containing '{search_term}'[/bold]\n"
    )

    # Group by entry
    by_entry = {}
    for entry_key, note in found_notes:
        if entry_key not in by_entry:
            by_entry[entry_key] = []
        by_entry[entry_key].append(note)

    for entry_key, notes in by_entry.items():
        entry = repo.find(key=entry_key)
        if entry:
            console.print(f"[cyan]{entry_key}[/cyan] - {entry.title}")
            for note in notes:
                preview = (
                    note.content[:100] + "..."
                    if len(note.content) > 100
                    else note.content
                )
                preview = preview.replace("\n", " ")
                console.print(f"  • {preview}")
            console.print()


# Note: tag and note are registered as top-level commands in main.py
# They are not subcommands of metadata
