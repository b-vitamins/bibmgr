"""Panel layouts and formatting for the CLI.

Provides functions for creating various panel types for displaying information.
"""

from typing import Any

from rich import box
from rich.panel import Panel
from rich.table import Table

from bibmgr.core.models import Entry


def create_entry_panel(entry: Entry) -> Panel:
    """Create a panel for displaying entry details.

    Args:
        entry: Entry to display

    Returns:
        Rich Panel with entry details
    """
    # Create table for entry fields
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Field", style="bold")
    table.add_column("Value")

    # Add basic fields
    table.add_row("Type", entry.type.value)
    table.add_row("Title", entry.title or "[dim]No title[/dim]")

    # Add authors
    if hasattr(entry, "authors") and entry.authors:
        authors = " and ".join(entry.authors)
    elif entry.author:
        authors = entry.author
    else:
        authors = "[dim]No authors[/dim]"
    table.add_row("Authors", authors)

    # Add year
    table.add_row("Year", str(entry.year) if entry.year else "[dim]No year[/dim]")

    # Add optional fields
    if entry.journal:
        table.add_row("Journal", entry.journal)
    if entry.booktitle:
        table.add_row("Book Title", entry.booktitle)
    if entry.doi:
        table.add_row("DOI", entry.doi)
    if entry.url:
        table.add_row("URL", entry.url)

    return Panel(
        table,
        title=f"Entry: {entry.key}",
        border_style="blue",
        box=box.ROUNDED,
    )


def create_error_panel(
    title: str,
    message: str,
    suggestions: list[str] | None = None,
) -> Panel:
    """Create an error panel with details.

    Args:
        title: Error title
        message: Error message
        suggestions: List of suggestions

    Returns:
        Rich Panel with error details
    """
    # Build content
    content_parts = [f"[bold red]{message}[/bold red]"]

    if suggestions:
        content_parts.append("")
        content_parts.append("[yellow]Suggestions:[/yellow]")
        for suggestion in suggestions:
            content_parts.append(f"  • {suggestion}")

    content = "\n".join(content_parts)

    return Panel(
        content,
        title=title,
        border_style="red",
        box=box.ROUNDED,
    )


def create_summary_panel(title: str, stats: dict[str, Any]) -> Panel:
    """Create a summary statistics panel.

    Args:
        title: Panel title
        stats: Dictionary of statistics

    Returns:
        Rich Panel with statistics
    """
    # Create table for stats
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    for key, value in stats.items():
        table.add_row(key, str(value))

    return Panel(
        table,
        title=title,
        border_style="blue",
        box=box.ROUNDED,
    )


def create_nested_panel(
    content: Any,
    title: str,
    subtitle: str | None = None,
    border_style: str = "blue",
) -> Panel:
    """Create a nested panel with title and optional subtitle.

    Args:
        content: Panel content (can be another Panel, Table, etc.)
        title: Panel title
        subtitle: Optional subtitle
        border_style: Border color style

    Returns:
        Rich Panel
    """
    full_title = title
    if subtitle:
        full_title = f"{title}: {subtitle}"

    return Panel(
        content,
        title=full_title,
        border_style=border_style,
        box=box.ROUNDED,
    )
