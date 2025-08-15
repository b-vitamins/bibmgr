"""Table formatters for Rich console output.

Provides beautiful table formatting for entries, search results, and collections.
"""

from typing import Any

from rich.box import ROUNDED
from rich.panel import Panel
from rich.table import Table

from bibmgr.core.models import Collection, Entry
from bibmgr.search.results import SearchMatch


def format_entries_table(
    entries: list[Entry],
    fields: list[str] | None = None,
    show_index: bool = False,
    show_abstracts: bool = False,
    title: str | None = None,
) -> Table:
    """Format entries as a Rich table.

    Args:
        entries: List of entries to format
        fields: Fields to display (default: key, title, authors, year)
        show_index: Whether to show row numbers
        show_abstracts: Whether to show abstracts
        title: Table title

    Returns:
        Rich Table object
    """
    if not fields:
        fields = ["key", "title", "authors", "year"]

    # Create table
    table = Table(
        title=title,
        box=ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title_style="bold",
        row_styles=["none", "dim"],  # Alternating row colors
    )

    # Add index column if requested
    if show_index:
        table.add_column("#", style="dim", width=4, justify="right")

    # Add field columns
    column_config = {
        "key": {"style": "cyan", "width": 15},
        "title": {"style": "none"},
        "authors": {"style": "none"},
        "year": {"style": "yellow", "width": 6, "justify": "center"},
        "type": {"style": "magenta", "width": 12},
        "journal": {"style": "none", "overflow": "ellipsis"},
        "venue": {"style": "none", "overflow": "ellipsis"},
        "doi": {"style": "blue", "overflow": "ellipsis"},
        "tags": {"style": "green"},
    }

    for field in fields:
        config = column_config.get(field, {})
        table.add_column(field.title(), **config)

    # Add rows
    if not entries:
        # Empty table
        table.add_row(*["[dim]No entries[/dim]"] * len(fields))
    else:
        for i, entry in enumerate(entries):
            row = []

            if show_index:
                row.append(str(i + 1))

            for field in fields:
                value = ""

                if field == "key":
                    value = entry.key
                elif field == "title":
                    value = entry.title or "[dim]No title[/dim]"
                elif field == "authors":
                    if entry.authors:
                        # Format authors nicely
                        if len(entry.authors) <= 2:
                            value = " and ".join(entry.authors)
                        else:
                            value = f"{entry.authors[0]} et al."
                    else:
                        value = "[dim]No authors[/dim]"
                elif field == "year":
                    value = str(entry.year) if entry.year else "[dim]-[/dim]"
                elif field == "type":
                    value = entry.type.value
                elif field == "journal":
                    value = entry.journal or "[dim]-[/dim]"
                elif field == "venue":
                    # For conference papers
                    value = entry.booktitle or entry.journal or "[dim]-[/dim]"
                elif field == "doi":
                    value = entry.doi or "[dim]-[/dim]"
                elif field == "tags":
                    if hasattr(entry, "tags") and entry.tags:
                        value = ", ".join(entry.tags)
                    else:
                        value = "[dim]-[/dim]"
                else:
                    # Generic field access
                    value = str(getattr(entry, field, "[dim]-[/dim]"))

                row.append(value)

            table.add_row(*row)

            # Add abstract if requested
            if show_abstracts and entry.abstract:
                abstract_row = [""] * len(row)
                abstract_row[fields.index("title") if "title" in fields else 1] = (
                    f"[dim italic]{entry.abstract[:100]}...[/dim italic]"
                    if len(entry.abstract) > 100
                    else f"[dim italic]{entry.abstract}[/dim italic]"
                )
                table.add_row(*abstract_row)

    return table


def format_entry_table(entries: list[Entry], **kwargs) -> Table:
    """Alias for format_entries_table for compatibility."""
    return format_entries_table(entries, **kwargs)


def format_entry_details(entry: Entry, metadata: dict[str, Any] | None = None) -> Panel:
    """Format a single entry with all details in a panel.

    Args:
        entry: Entry to format
        metadata: Optional metadata (tags, rating, notes, etc.)

    Returns:
        Rich Panel object
    """
    # Build content table
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Field", style="cyan", width=12)
    table.add_column("Value")

    # Basic fields
    table.add_row("Type", entry.type.value)
    table.add_row("Title", entry.title or "[dim]No title[/dim]")

    if entry.authors:
        table.add_row("Authors", " and ".join(entry.authors))

    if entry.year:
        table.add_row("Year", str(entry.year))

    # Publication details
    if entry.journal:
        table.add_row("Journal", entry.journal)
    elif entry.booktitle:
        table.add_row("Book/Conf", entry.booktitle)

    if entry.volume:
        table.add_row("Volume", entry.volume)

    if entry.number:
        table.add_row("Number", entry.number)

    if entry.pages:
        table.add_row("Pages", entry.pages)

    # Identifiers
    if entry.doi:
        table.add_row("DOI", f"[blue]{entry.doi}[/blue]")

    if entry.url:
        table.add_row("URL", f"[blue]{entry.url}[/blue]")

    if entry.isbn:
        table.add_row("ISBN", entry.isbn)

    # Additional fields
    if entry.publisher:
        table.add_row("Publisher", entry.publisher)

    if entry.address:
        table.add_row("Address", entry.address)

    if entry.keywords:
        table.add_row("Keywords", ", ".join(entry.keywords))

    # Add separator before metadata
    if metadata:
        table.add_row("", "")  # Empty row as separator

        if "tags" in metadata and metadata["tags"]:
            table.add_row("Tags", f"[green]{', '.join(metadata['tags'])}[/green]")

        if "rating" in metadata and metadata["rating"]:
            stars = "★" * metadata["rating"] + "☆" * (5 - metadata["rating"])
            table.add_row("Rating", f"[yellow]{stars}[/yellow]")

        if "read_status" in metadata:
            status = metadata["read_status"]
            color = {"read": "green", "reading": "yellow", "unread": "dim"}.get(
                status, "white"
            )
            table.add_row("Status", f"[{color}]● {status.title()}[/{color}]")

        if "notes_count" in metadata and metadata["notes_count"] > 0:
            table.add_row("Notes", f"{metadata['notes_count']} notes")

        if "file_path" in metadata and metadata["file_path"]:
            table.add_row("File", f"[blue]📎 {metadata['file_path']}[/blue]")

    # Abstract in separate section
    if entry.abstract:
        table.add_row("", "")  # Empty row as separator
        table.add_row("Abstract", entry.abstract)

    # Create panel
    panel = Panel(
        table,
        title=f"[bold cyan]{entry.key}[/bold cyan]",
        title_align="left",
        border_style="blue",
        padding=(1, 2),
    )

    return panel


def format_search_results(
    matches: list[SearchMatch],
    show_snippets: bool = True,
    show_score: bool = True,
) -> Table:
    """Format search results with highlights and scores.

    Args:
        matches: Search matches to format
        show_snippets: Whether to show highlighted snippets
        show_score: Whether to show relevance scores

    Returns:
        Rich Table object
    """
    table = Table(
        title="Search Results",
        box=ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )

    # Add columns
    table.add_column("Key", style="cyan", width=15)
    table.add_column("Title", overflow="ellipsis")

    if show_score:
        table.add_column("Score", style="green", width=10, justify="right")

    table.add_column("Year", style="yellow", width=6, justify="center")

    # Add rows
    for match in matches:
        entry = match.entry if hasattr(match, "entry") and match.entry else None

        # Key
        key = match.entry_key

        # Title with highlights
        title = "[dim]No title[/dim]"
        if entry and entry.title:
            title = entry.title

            # Apply highlights if available
            if match.highlights and "title" in match.highlights:
                for highlight in match.highlights["title"]:
                    # Convert <mark> tags to Rich markup
                    title = highlight.replace("<mark>", "[bold yellow]").replace(
                        "</mark>", "[/bold yellow]"
                    )

        # Score
        score_str = ""
        if show_score:
            if match.score >= 0.9:
                score_str = f"[green]█████████ {match.score:.0%}[/green]"
            elif match.score >= 0.8:
                score_str = f"[yellow]███████ {match.score:.0%}[/yellow]"
            elif match.score >= 0.7:
                score_str = f"[blue]██████ {match.score:.0%}[/blue]"
            else:
                score_str = f"[dim]████ {match.score:.0%}[/dim]"

        # Year
        year = str(entry.year) if entry and entry.year else "[dim]-[/dim]"

        # Build row
        row = [key, title]
        if show_score:
            row.append(score_str)
        row.append(year)

        table.add_row(*row)

        # Add snippet if available
        if show_snippets and match.highlights:
            snippet_parts = []

            for field, highlights in match.highlights.items():
                if field != "title" and highlights:  # Title already shown above
                    for highlight in highlights[:1]:  # Show first highlight only
                        snippet = highlight.replace("<mark>", "[bold yellow]").replace(
                            "</mark>", "[/bold yellow]"
                        )
                        snippet_parts.append(f"...{snippet}...")

            if snippet_parts:
                snippet_row = [""] * len(row)
                snippet_row[1] = f"[dim italic]{' '.join(snippet_parts)}[/dim italic]"
                table.add_row(*snippet_row)

    return table


def format_collections_table(collections: list[Collection]) -> Table:
    """Format collections as a table.

    Args:
        collections: List of collections to format

    Returns:
        Rich Table object
    """
    table = Table(
        title="Collections",
        box=ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )

    # Add columns
    table.add_column("Name", style="cyan")
    table.add_column("Count", justify="right", style="yellow")
    table.add_column("Type", style="magenta")
    table.add_column("Description")

    # Add rows
    for collection in collections:
        # Icon based on type (manual has entry_keys, smart has query)
        is_manual = collection.entry_keys is not None
        icon = "📁" if is_manual else "🔍"
        name = f"{icon} {collection.name}"

        # Entry count
        if is_manual and collection.entry_keys:
            count = str(len(collection.entry_keys))
        else:
            count = "[dim]Dynamic[/dim]"

        # Type
        coll_type = "Manual" if is_manual else "Smart"

        # Description
        desc = collection.description or "[dim]No description[/dim]"

        table.add_row(name, count, coll_type, desc)

    if not collections:
        table.add_row("[dim]No collections[/dim]", "", "", "")

    return table
