"""Collection management CLI commands."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.tree import Tree

from bibmgr.core.models import Collection


def get_collection_repository(ctx):
    """Get the collection repository from context."""
    return ctx.obj.collection_repository


def get_repository(ctx):
    """Get the entry repository from context."""
    return ctx.obj.repository


def get_search_service(ctx):
    """Get the search service from context."""
    return ctx.obj.search_service


@click.group()
def collection():
    """Manage bibliography collections."""
    pass


# Command: list
@collection.command(name="list")
@click.option("--tree", is_flag=True, help="Show collections in tree view")
@click.option("--smart-only", is_flag=True, help="Show only smart collections")
@click.option("--manual-only", is_flag=True, help="Show only manual collections")
@click.pass_context
def list_collections(
    ctx: click.Context, tree: bool, smart_only: bool, manual_only: bool
) -> None:
    """List all collections."""
    console = ctx.obj.console
    collection_repo = get_collection_repository(ctx)

    try:
        collections = collection_repo.find_all()

        # Filter by type if requested
        if smart_only:
            collections = [c for c in collections if c.is_smart]
        elif manual_only:
            collections = [c for c in collections if not c.is_smart]

        if not collections:
            console.print("[yellow]No collections found[/yellow]")
            return

        console.print("\n📚 [bold]Collections[/bold]\n")

        if tree:
            _display_collections_tree(console, collections)
        else:
            _display_collections_table(console, collections)

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Command: create
@collection.command()
@click.argument("collection_id")
@click.option("--name", "-n", help="Collection name (defaults to ID)")
@click.option("--description", "-d", help="Collection description")
@click.option("--query", "-q", help="Smart collection query")
@click.option("--parent", "-p", help="Parent collection ID")
@click.option("--icon", help="Collection icon/emoji")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.pass_context
def create(ctx: click.Context, collection_id: str, **kwargs) -> None:
    """Create a new collection."""
    console = ctx.obj.console
    collection_repo = get_collection_repository(ctx)

    try:
        # Check if ID already exists
        if collection_repo.find(collection_id):
            console.print(
                f"[red]Collection with ID '{collection_id}' already exists[/red]"
            )
            ctx.exit(1)

        # Collect fields
        if kwargs["interactive"]:
            fields = _collect_collection_fields_interactive(
                console, collection_id, kwargs
            )
        else:
            fields = {
                "id": collection_id,
                "name": kwargs.get("name") or collection_id,
                "description": kwargs.get("description"),
                "query": kwargs.get("query"),
                "parent_id": kwargs.get("parent"),
                "icon": kwargs.get("icon"),
            }

        # Create collection
        collection = Collection(
            id=fields["id"],
            name=fields["name"],
            description=fields.get("description"),
            query=fields.get("query"),
            parent_id=fields.get("parent_id"),
            icon=fields.get("icon"),
            entry_keys=tuple() if not fields.get("query") else None,
        )

        # Save collection
        collection_repo.save(collection)

        console.print("[green]✓[/green] Collection created successfully")

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Command: show
@collection.command()
@click.argument("collection_id")
@click.option("--entries", "-e", is_flag=True, help="Show entries in collection")
@click.pass_context
def show(ctx: click.Context, collection_id: str, entries: bool) -> None:
    """Show collection details."""
    console = ctx.obj.console
    collection_repo = get_collection_repository(ctx)
    entry_repo = get_repository(ctx)

    try:
        collection = collection_repo.find(collection_id)
        if not collection:
            console.print(f"[red]Collection not found:[/red] {collection_id}")
            ctx.exit(1)

        # Display collection info
        _display_collection_details(console, collection)

        # Display entries if requested
        if entries:
            if collection.is_smart:
                console.print(
                    "\n[yellow]Smart collection entries are determined by query[/yellow]"
                )
            else:
                _display_collection_entries(console, collection, entry_repo)

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Command: add
@collection.command()
@click.argument("collection_id")
@click.argument("entry_keys", nargs=-1, required=True)
@click.option("--search", "-s", help="Add entries matching search query")
@click.pass_context
def add(
    ctx: click.Context,
    collection_id: str,
    entry_keys: tuple[str, ...],
    search: str | None,
) -> None:
    """Add entries to a collection."""
    console = ctx.obj.console
    collection_repo = get_collection_repository(ctx)
    entry_repo = get_repository(ctx)

    try:
        # Find collection
        collection = collection_repo.find(collection_id)
        if not collection:
            console.print(f"[red]Collection not found:[/red] {collection_id}")
            ctx.exit(1)

        if collection.is_smart:
            console.print("[red]Cannot add entries to smart collection[/red]")
            ctx.exit(1)

        # Get entry keys to add
        keys_to_add = list(entry_keys)

        if search:
            # Find entries matching search query
            search_service = get_search_service(ctx)
            results = search_service.search(search, limit=100)
            search_keys = [match.entry_key for match in results.matches]
            keys_to_add.extend(search_keys)
            console.print(f"Found {len(search_keys)} entries matching '{search}'")

        # Verify entries exist
        missing = []
        for key in keys_to_add:
            if not entry_repo.find(key):
                missing.append(key)

        if missing:
            console.print(f"[red]Entries not found:[/red] {', '.join(missing)}")
            ctx.exit(1)

        # Add entries to collection
        added = []
        skipped = []
        for key in keys_to_add:
            if key not in (collection.entry_keys or []):
                collection = collection.add_entry(key)
                added.append(key)
            else:
                skipped.append(key)

        # Save updated collection
        collection_repo.save(collection)

        # Report results
        if added:
            console.print(f"[green]✓[/green] Added {len(added)} entries to collection")
        if skipped:
            console.print(
                f"[yellow]Skipped {len(skipped)} entries (already in collection)[/yellow]"
            )

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Command: remove
@collection.command()
@click.argument("collection_id")
@click.argument("entry_keys", nargs=-1, required=True)
@click.option("--all", "-a", "remove_all", is_flag=True, help="Remove all entries")
@click.pass_context
def remove(
    ctx: click.Context,
    collection_id: str,
    entry_keys: tuple[str, ...],
    remove_all: bool,
) -> None:
    """Remove entries from a collection."""
    console = ctx.obj.console
    collection_repo = get_collection_repository(ctx)

    try:
        # Find collection
        collection = collection_repo.find(collection_id)
        if not collection:
            console.print(f"[red]Collection not found:[/red] {collection_id}")
            ctx.exit(1)

        if collection.is_smart:
            console.print("[red]Cannot remove entries from smart collection[/red]")
            ctx.exit(1)

        # Handle remove all
        if remove_all:
            if not Confirm.ask(f"Remove all entries from '{collection.name}'?"):
                console.print("[yellow]Cancelled[/yellow]")
                return

            collection = Collection(
                id=collection.id,
                name=collection.name,
                description=collection.description,
                parent_id=collection.parent_id,
                icon=collection.icon,
                entry_keys=tuple(),
            )
            collection_repo.save(collection)
            console.print("[green]✓[/green] Removed all entries from collection")
            return

        # Remove specific entries
        removed = []
        not_found = []
        for key in entry_keys:
            if key in (collection.entry_keys or []):
                collection = collection.remove_entry(key)
                removed.append(key)
            else:
                not_found.append(key)

        # Save updated collection
        collection_repo.save(collection)

        # Report results
        if removed:
            console.print(
                f"[green]✓[/green] Removed {len(removed)} entries from collection"
            )
        if not_found:
            console.print(f"[yellow]Not in collection: {', '.join(not_found)}[/yellow]")

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Command: edit
@collection.command()
@click.argument("collection_id")
@click.option("--name", "-n", help="New collection name")
@click.option("--description", "-d", help="New description")
@click.option("--query", "-q", help="New query (converts to smart collection)")
@click.option("--parent", "-p", help="New parent collection ID")
@click.option("--no-parent", is_flag=True, help="Remove parent")
@click.pass_context
def edit(ctx: click.Context, collection_id: str, **kwargs) -> None:
    """Edit collection properties."""
    console = ctx.obj.console
    collection_repo = get_collection_repository(ctx)

    try:
        # Find collection
        collection = collection_repo.find(collection_id)
        if not collection:
            console.print(f"[red]Collection not found:[/red] {collection_id}")
            ctx.exit(1)

        # Build updates
        updates = {}
        if kwargs.get("name"):
            updates["name"] = kwargs["name"]
        if kwargs.get("description") is not None:
            updates["description"] = kwargs["description"]
        if kwargs.get("query") is not None:
            updates["query"] = kwargs["query"]
            if kwargs["query"]:
                # Converting to smart collection
                updates["entry_keys"] = None
        if kwargs.get("parent") is not None:
            updates["parent_id"] = kwargs["parent"]
        if kwargs.get("no_parent"):
            updates["parent_id"] = None

        if not updates:
            console.print("[yellow]No changes specified[/yellow]")
            return

        # Create updated collection
        updated_data = {
            "id": collection.id,
            "name": collection.name,
            "description": collection.description,
            "query": collection.query,
            "parent_id": collection.parent_id,
            "icon": collection.icon,
            "entry_keys": collection.entry_keys,
        }
        updated_data.update(updates)

        updated_collection = Collection(**updated_data)
        collection_repo.save(updated_collection)

        console.print("[green]✓[/green] Collection updated successfully")

        # Show warning if converted to smart collection
        if "query" in updates and updates["query"] and not collection.is_smart:
            console.print(
                "[yellow]Note: Converted to smart collection. Manual entries cleared.[/yellow]"
            )

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Command: delete
@collection.command()
@click.argument("collection_ids", nargs=-1, required=True)
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.option("--recursive", "-r", is_flag=True, help="Delete child collections")
@click.pass_context
def delete(
    ctx: click.Context, collection_ids: tuple[str, ...], force: bool, recursive: bool
) -> None:
    """Delete one or more collections."""
    console = ctx.obj.console
    collection_repo = get_collection_repository(ctx)

    try:
        # Verify collections exist
        collections_to_delete = []
        for cid in collection_ids:
            collection = collection_repo.find(cid)
            if not collection:
                console.print(f"[red]Collection not found:[/red] {cid}")
                ctx.exit(1)
            collections_to_delete.append(collection)

        # Check for child collections
        if recursive:
            for collection in list(collections_to_delete):
                children = collection_repo.find_by_parent(collection.id)
                collections_to_delete.extend(children)

        # Confirm deletion
        if not force:
            names = [c.name for c in collections_to_delete]
            if len(collections_to_delete) == 1:
                if not Confirm.ask(f"Delete collection '{names[0]}'?"):
                    console.print("[yellow]Cancelled[/yellow]")
                    return
            else:
                console.print(f"Collections to delete: {', '.join(names)}")
                if not Confirm.ask(f"Delete {len(collections_to_delete)} collections?"):
                    console.print("[yellow]Cancelled[/yellow]")
                    return

        # Delete collections
        for collection in collections_to_delete:
            collection_repo.delete(collection.id)

        if len(collections_to_delete) == 1:
            console.print("[green]✓[/green] Collection deleted successfully")
        else:
            console.print(
                f"[green]✓[/green] Deleted {len(collections_to_delete)} collections"
            )

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Command: export
@collection.command()
@click.argument("collection_id")
@click.argument("output_file", type=click.Path())
@click.option(
    "--format",
    "-f",
    type=click.Choice(["bibtex", "json", "csv"]),
    default="bibtex",
    help="Export format",
)
@click.pass_context
def export(
    ctx: click.Context, collection_id: str, output_file: str, format: str
) -> None:
    """Export collection entries to file."""
    console = ctx.obj.console
    collection_repo = get_collection_repository(ctx)
    entry_repo = get_repository(ctx)

    try:
        # Find collection
        collection = collection_repo.find(collection_id)
        if not collection:
            console.print(f"[red]Collection not found:[/red] {collection_id}")
            ctx.exit(1)

        # Get entries
        if collection.is_smart:
            # For smart collections, we'd need to execute the query
            # For now, just show a message
            console.print(
                "[yellow]Smart collection export not yet implemented[/yellow]"
            )
            ctx.exit(1)
        else:
            # Get entries from the collection
            entries = []
            for key in collection.entry_keys or []:
                entry = entry_repo.find(key)
                if entry:
                    entries.append(entry)

        if not entries:
            console.print("[yellow]No entries to export[/yellow]")
            return

        # Export based on format
        content = ""
        if format == "bibtex":
            from bibmgr.cli.formatters.bibtex import format_entries_bibtex

            content = format_entries_bibtex(entries)
        elif format == "json":
            from bibmgr.cli.formatters.json import format_entries_json

            content = format_entries_json(entries)
        elif format == "csv":
            # Simple CSV implementation
            import csv
            from io import StringIO

            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(["key", "type", "title", "author", "year", "journal"])
            for entry in entries:
                writer.writerow(
                    [
                        entry.key,
                        entry.type.value,
                        entry.title or "",
                        entry.author or "",
                        entry.year or "",
                        entry.journal or "",
                    ]
                )
            content = output.getvalue()

        # Write to file
        with open(output_file, "w") as f:
            f.write(content)

        console.print(
            f"[green]✓[/green] Exported {len(entries)} entries to {output_file}"
        )

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Command: move
@collection.command()
@click.argument("collection_id")
@click.option("--to", "-t", "new_parent", help="New parent collection ID")
@click.pass_context
def move(ctx: click.Context, collection_id: str, new_parent: str | None) -> None:
    """Move collection to a different parent."""
    console = ctx.obj.console
    collection_repo = get_collection_repository(ctx)

    try:
        # Find the collection
        collection = collection_repo.find(collection_id)
        if not collection:
            console.print(f"[red]Collection not found:[/red] {collection_id}")
            ctx.exit(1)

        # Verify new parent exists (if specified)
        if new_parent:
            parent = collection_repo.find(new_parent)
            if not parent:
                console.print(f"[red]Parent collection not found:[/red] {new_parent}")
                ctx.exit(1)

            # Check for circular references
            if new_parent == collection_id:
                console.print("[red]Cannot move collection to itself[/red]")
                ctx.exit(1)

        # Update the collection
        updated = Collection(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            query=collection.query,
            parent_id=new_parent if new_parent else None,  # type: ignore
            icon=collection.icon,
            entry_keys=collection.entry_keys,
        )

        collection_repo.save(updated)
        console.print("[green]✓[/green] Collection moved")

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Command: stats
@collection.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """Show collection statistics."""
    console = ctx.obj.console
    collection_repo = get_collection_repository(ctx)

    try:
        collections = collection_repo.find_all()

        if not collections:
            console.print("[yellow]No collections found[/yellow]")
            return

        # Calculate statistics
        total = len(collections)
        manual = len([c for c in collections if not c.is_smart])
        smart = len([c for c in collections if c.is_smart])

        # Calculate sizes
        sizes = []
        for collection in collections:
            if collection.entry_keys:
                sizes.append(len(collection.entry_keys))

        avg_size = sum(sizes) / len(sizes) if sizes else 0

        # Display stats
        console.print("\n[bold]Collection Statistics[/bold]\n")

        table = Table()
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Total collections", str(total))
        table.add_row("Manual collections", str(manual))
        table.add_row("Smart collections", str(smart))
        if sizes:
            table.add_row("Average size", f"{avg_size:.1f}")
            table.add_row("Largest collection", str(max(sizes)))
            table.add_row("Smallest collection", str(min(sizes)))

        console.print(table)

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Helper functions
def _display_collections_table(console: Console, collections: list[Collection]) -> None:
    """Display collections in table format."""
    table = Table()
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type", style="magenta")
    table.add_column("Entries", justify="right")
    table.add_column("Description", overflow="ellipsis", max_width=40)

    for collection in collections:
        collection_type = "Smart" if collection.is_smart else "Manual"
        entry_count = len(collection.entry_keys) if collection.entry_keys else 0
        icon = collection.icon + " " if collection.icon else ""

        table.add_row(
            str(collection.id),
            icon + collection.name,
            collection_type,
            str(entry_count),
            collection.description or "",
        )

    console.print(table)


def _display_collections_tree(console: Console, collections: list[Collection]) -> None:
    """Display collections in tree view."""
    # Build tree structure
    root_collections = [c for c in collections if not c.parent_id]

    import uuid

    def build_tree(parent_id: uuid.UUID | None, tree_node: Tree) -> None:
        children = [c for c in collections if c.parent_id == parent_id]
        for child in children:
            icon = child.icon + " " if child.icon else ""
            entry_count = len(child.entry_keys) if child.entry_keys else 0
            label = f"{icon}{child.name} ({entry_count})"
            if child.is_smart:
                label += " [magenta][Smart][/magenta]"

            child_node = tree_node.add(label)
            build_tree(child.id, child_node)

    tree = Tree("📚 Collections")
    for root in root_collections:
        icon = root.icon + " " if root.icon else ""
        entry_count = len(root.entry_keys) if root.entry_keys else 0
        label = f"{icon}{root.name} ({entry_count})"
        if root.is_smart:
            label += " [magenta][Smart][/magenta]"

        root_node = tree.add(label)
        build_tree(root.id, root_node)

    console.print(tree)


def _display_collection_details(console: Console, collection: Collection) -> None:
    """Display detailed collection information."""
    # Build content
    content = []
    content.append(f"[bold]Name:[/bold] {collection.name}")
    content.append(f"[bold]ID:[/bold] {collection.id}")
    content.append(f"[bold]Type:[/bold] {'Smart' if collection.is_smart else 'Manual'}")

    if collection.description:
        content.append(f"[bold]Description:[/bold] {collection.description}")

    if collection.is_smart and collection.query:
        content.append(f"[bold]Query:[/bold] {collection.query}")
    else:
        entry_count = len(collection.entry_keys) if collection.entry_keys else 0
        content.append(f"[bold]Entries:[/bold] {entry_count}")

    if collection.parent_id:
        content.append(f"[bold]Parent:[/bold] {collection.parent_id}")

    if collection.created:
        content.append(
            f"[bold]Created:[/bold] {collection.created.strftime('%Y-%m-%d %H:%M')}"
        )

    if collection.modified:
        content.append(
            f"[bold]Modified:[/bold] {collection.modified.strftime('%Y-%m-%d %H:%M')}"
        )

    # Display in panel
    icon = collection.icon + " " if collection.icon else "📁 "
    panel = Panel(
        "\n".join(content), title=f"{icon}{collection.name}", border_style="blue"
    )
    console.print(panel)


def _display_collection_entries(
    console: Console, collection: Collection, repository
) -> None:
    """Display entries in a collection."""
    if not collection.entry_keys:
        console.print("\n[yellow]No entries in collection[/yellow]")
        return

    console.print(f"\n[bold]Entries ({len(collection.entry_keys)}):[/bold]\n")

    table = Table()
    table.add_column("Key", style="cyan")
    table.add_column("Title", overflow="ellipsis", max_width=50)
    table.add_column("Authors", overflow="ellipsis", max_width=30)
    table.add_column("Year", justify="center")

    for key in collection.entry_keys:
        entry = repository.find(key)
        if entry:
            table.add_row(
                entry.key,
                entry.title or "",
                (entry.author or "")[:30] + "..."
                if entry.author and len(entry.author) > 30
                else entry.author or "",
                str(entry.year) if entry.year else "",
            )

    console.print(table)


def _collect_collection_fields_interactive(
    console: Console, collection_id: str, existing: dict
) -> dict:
    """Collect collection fields interactively."""
    fields = {"id": collection_id}

    # Name
    fields["name"] = existing.get("name") or Prompt.ask(
        "Collection name", default=collection_id
    )

    # Description
    fields["description"] = existing.get("description") or Prompt.ask(
        "Description", default=""
    )

    # Type (manual or smart)
    collection_type = Prompt.ask(
        "Collection type", choices=["manual", "smart"], default="manual"
    )

    if collection_type == "smart":
        fields["query"] = existing.get("query") or Prompt.ask(
            "Query (e.g., year:2024 AND keywords:quantum)"
        )

    # Parent collection
    parent = existing.get("parent") or Prompt.ask(
        "Parent collection ID (optional)", default=""
    )
    if parent:
        fields["parent_id"] = parent

    # Icon
    icon = existing.get("icon") or Prompt.ask("Icon/emoji (optional)", default="")
    if icon:
        fields["icon"] = icon

    return fields
