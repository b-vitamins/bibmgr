"""CLI output formatters."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.text import Text

from bibmgr.core.models import Entry


def format_entry_table(entry: Entry) -> str:
    """Format entry as a table.

    Args:
        entry: Entry to format

    Returns:
        Formatted table string
    """
    console = Console(record=True)

    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan", width=15)
    table.add_column("Value", style="white")

    # Add fields
    table.add_row("Key", entry.key)
    table.add_row("Type", entry.type.value)
    table.add_row("Title", entry.title)

    if entry.author:
        table.add_row("Author(s)", entry.author)
    if entry.year:
        table.add_row("Year", str(entry.year))

    # Add other fields
    for field in [
        "journal",
        "booktitle",
        "publisher",
        "school",
        "volume",
        "number",
        "pages",
        "doi",
        "url",
    ]:
        value = getattr(entry, field, None)
        if value:
            field_name = field.capitalize()
            if field == "booktitle":
                field_name = "Book Title"
            table.add_row(field_name, str(value))

    # Add abstract (truncated)
    if hasattr(entry, "abstract") and entry.abstract:
        abstract = entry.abstract
        if len(abstract) > 200:
            abstract = abstract[:197] + "..."
        table.add_row("Abstract", abstract)

    # Add keywords
    if hasattr(entry, "keywords") and entry.keywords:
        keywords = ", ".join(entry.keywords)
        table.add_row("Keywords", keywords)

    console.print(table)
    return console.export_text()


def format_entry_bibtex(entry: Entry) -> str:
    """Format entry as BibTeX.

    Args:
        entry: Entry to format

    Returns:
        BibTeX string
    """
    from .helpers import format_entry_bibtex as helper_format

    return helper_format(entry)


def format_entry_json(entry: Entry, indent: int = 2) -> str:
    """Format entry as JSON.

    Args:
        entry: Entry to format
        indent: JSON indentation

    Returns:
        JSON string
    """
    data = {
        "key": entry.key,
        "type": entry.type.value,
        "title": entry.title,
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
        "keywords",
    ]:
        value = getattr(entry, field, None)
        if value is not None:
            data[field] = value

    return json.dumps(data, indent=indent, default=str)


def format_entry_yaml(entry: Entry) -> str:
    """Format entry as YAML.

    Args:
        entry: Entry to format

    Returns:
        YAML string
    """
    lines = []
    lines.append(f"key: {entry.key}")
    lines.append(f"type: {entry.type.value}")
    lines.append(f"title: {entry.title}")

    if entry.author:
        lines.append(f"author: {entry.author}")
    if entry.year:
        lines.append(f"year: {entry.year}")

    for field in [
        "journal",
        "booktitle",
        "publisher",
        "school",
        "volume",
        "number",
        "pages",
        "doi",
        "url",
    ]:
        value = getattr(entry, field, None)
        if value:
            lines.append(f"{field}: {value}")

    if hasattr(entry, "abstract") and entry.abstract:
        # Multi-line abstract
        lines.append("abstract: |")
        for line in entry.abstract.split("\n"):
            lines.append(f"  {line}")

    if hasattr(entry, "keywords") and entry.keywords:
        lines.append("keywords:")
        for keyword in entry.keywords:
            lines.append(f"  - {keyword}")

    return "\n".join(lines)


def format_entries_list(
    entries: List[Entry], format: str = "table", fields: Optional[List[str]] = None
) -> str:
    """Format list of entries.

    Args:
        entries: List of entries
        format: Output format (table, compact, keys, json)
        fields: Fields to include (None for default)

    Returns:
        Formatted string
    """
    if format == "keys":
        return "\n".join(e.key for e in entries)

    elif format == "json":
        data = []
        for entry in entries:
            entry_data = json.loads(format_entry_json(entry))
            if fields:
                entry_data = {k: v for k, v in entry_data.items() if k in fields}
            data.append(entry_data)
        return json.dumps(data, indent=2, default=str)

    elif format == "compact":
        lines = []
        for entry in entries:
            year = f"({entry.year})" if entry.year else ""
            title = (
                entry.title[:60] + "..."
                if entry.title and len(entry.title) > 60
                else (entry.title or "")
            )
            line = f"{entry.key}: {title} {year} [{entry.type.value}]"
            lines.append(line)
        return "\n".join(lines)

    else:  # table
        console = Console(record=True)

        table = Table(title=f"Bibliography Entries ({len(entries)} total)")

        # Default fields
        if not fields:
            fields = ["key", "type", "title", "author", "year"]

        # Add columns
        for field in fields:
            style = {
                "key": "cyan",
                "type": "magenta",
                "title": "white",
                "author": "green",
                "year": "yellow",
            }.get(field, "white")

            table.add_column(field.capitalize(), style=style)

        # Add rows
        for entry in entries:
            row = []
            for field in fields:
                value = getattr(entry, field, "")
                if value is None:
                    value = ""
                else:
                    value = str(value)

                # Truncate long values
                if field == "title" and len(value) > 50:
                    value = value[:47] + "..."
                elif field == "author" and len(value) > 30:
                    value = value[:27] + "..."

                row.append(value)

            table.add_row(*row)

        console.print(table)
        return console.export_text()


def format_stats_table(stats: Dict[str, Any]) -> str:
    """Format statistics as a table.

    Args:
        stats: Statistics dictionary

    Returns:
        Formatted table string
    """
    console = Console(record=True)

    # Overall stats
    table = Table(title="Bibliography Statistics", show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")

    if "total" in stats:
        table.add_row("Total Entries", str(stats["total"]))

    if "by_type" in stats:
        for entry_type, count in stats["by_type"].items():
            table.add_row(f"  {entry_type}", str(count))

    console.print(table)

    # Year distribution
    if "by_year" in stats:
        year_table = Table(title="Entries by Year")
        year_table.add_column("Year", style="yellow")
        year_table.add_column("Count", justify="right")
        year_table.add_column("Bar")

        max_count = max(stats["by_year"].values()) if stats["by_year"] else 1

        for year in sorted(stats["by_year"].keys(), reverse=True)[:10]:
            count = stats["by_year"][year]
            bar_width = int((count / max_count) * 30)
            bar = "█" * bar_width
            year_table.add_row(str(year), str(count), bar)

        console.print(year_table)

    return console.export_text()


def format_validation_report(report: Dict[str, Any], verbose: bool = False) -> str:
    """Format validation report.

    Args:
        report: Validation report
        verbose: Include detailed errors

    Returns:
        Formatted report string
    """
    console = Console(record=True)

    # Summary
    table = Table(title="Validation Summary", show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    total = report.get("total", 0)
    valid = report.get("valid", 0)
    errors = len(report.get("errors", []))
    warnings = len(report.get("warnings", []))

    table.add_row("Total Entries", str(total))
    table.add_row(
        "Valid Entries", Text(str(valid), style="green" if valid == total else "yellow")
    )
    table.add_row("Errors", Text(str(errors), style="red" if errors > 0 else "green"))
    table.add_row(
        "Warnings", Text(str(warnings), style="yellow" if warnings > 0 else "green")
    )

    console.print(table)

    # Detailed errors
    if verbose and report.get("errors"):
        console.print("\n[bold red]Errors:[/bold red]")
        for error in report["errors"][:20]:
            console.print(f"  • {error}")

        if len(report["errors"]) > 20:
            console.print(f"  ... and {len(report['errors']) - 20} more")

    # Detailed warnings
    if verbose and report.get("warnings"):
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for warning in report["warnings"][:10]:
            console.print(f"  • {warning}")

        if len(report["warnings"]) > 10:
            console.print(f"  ... and {len(report['warnings']) - 10} more")

    return console.export_text()


def format_search_results(results: Dict[str, Any], explain: bool = False) -> str:
    """Format search results.

    Args:
        results: Search results
        explain: Include score explanation

    Returns:
        Formatted results string
    """
    console = Console(record=True)

    hits = results.get("hits", [])
    total = results.get("total", 0)
    time_ms = results.get("time_ms", 0)

    if not hits:
        console.print("[yellow]No results found[/yellow]")
        return console.export_text()

    # Results table
    table = Table(title=f"Search Results ({total} found, {time_ms:.1f}ms)")

    table.add_column("#", style="dim", width=4)
    table.add_column("Key", style="green")
    table.add_column("Title", style="white")
    table.add_column("Authors", style="yellow")
    table.add_column("Year", style="magenta")

    if explain:
        table.add_column("Score", style="cyan", justify="right")

    for i, hit in enumerate(hits, 1):
        title = hit.get("title", "")
        if len(title) > 50:
            title = title[:47] + "..."

        authors = hit.get("authors", "")
        if len(authors) > 30:
            authors = authors[:27] + "..."

        row = [
            str(i),
            hit.get("key", ""),
            title,
            authors,
            str(hit.get("year", "")),
        ]

        if explain:
            score = hit.get("score", 0)
            row.append(f"{score:.2f}")

        table.add_row(*row)

    console.print(table)

    # Facets
    if results.get("facets"):
        console.print("\n[bold cyan]Refine by:[/bold cyan]")
        for field, values in results["facets"].items():
            if values:
                top = sorted(values.items(), key=lambda x: x[1], reverse=True)[:5]
                value_str = ", ".join(f"{v} ({c})" for v, c in top)
                console.print(f"  {field}: {value_str}")

    return console.export_text()
