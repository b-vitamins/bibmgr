"""CLI helper functions."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import click

from bibmgr.core.models import Entry, EntryType
from bibmgr.storage.parser import BibtexParser


def parse_field_assignments(fields: list[str]) -> dict[str, str]:
    """Parse field assignments from strings.

    Args:
        fields: List of "field=value" strings

    Returns:
        Dictionary of field assignments
    """
    result = {}
    for field_str in fields:
        if "=" not in field_str:
            continue

        # Split only on first equals to handle values with equals
        parts = field_str.split("=", 1)
        if len(parts) == 2:
            key, value = parts
            result[key.strip()] = value.strip()

    return result


def parse_filter_query(query: str) -> dict[str, Any]:
    """Parse filter query string.

    Args:
        query: Filter query string (e.g., "type:article year:2020..2023")

    Returns:
        Dictionary of filters
    """
    filters = {}

    # Pattern for field:value with optional quotes
    pattern = r'(\w+):(?:"([^"]+)"|(\S+))'

    for match in re.finditer(pattern, query):
        field = match.group(1)
        value = match.group(2) if match.group(2) else match.group(3)

        # Handle year ranges
        if field == "year" and ".." in value:
            start, end = value.split("..")
            try:
                filters[field] = range(int(start), int(end) + 1)
            except ValueError:
                filters[field] = value
        else:
            filters[field] = value

    return filters


def confirm_action(message: str, default: bool = False, force: bool = False) -> bool:
    """Confirm an action with the user.

    Args:
        message: Confirmation message
        default: Default response
        force: Skip confirmation if True

    Returns:
        True if confirmed
    """
    if force:
        return True

    return click.confirm(message, default=default)


def handle_error(
    message: str, exception: Exception | None = None, exit_code: int | None = 1
) -> None:
    """Handle an error.

    Args:
        message: Error message
        exception: Optional exception that caused the error
        exit_code: Exit code (None to not exit)
    """
    click.echo(f"Error: {message}", err=True)

    if exception and click.get_current_context().obj.get("debug", False):
        click.echo(f"Debug: {exception}", err=True)

    if exit_code is not None:
        sys.exit(exit_code)


def load_entries_from_file(file_path: Path, format: str = "bibtex") -> list[Entry]:
    """Load entries from a file.

    Args:
        file_path: Path to file
        format: File format (bibtex, json, etc.)

    Returns:
        List of entries
    """
    if not file_path.exists():
        raise ValueError(f"File not found: {file_path}")

    if format == "json":
        with open(file_path) as f:
            data = json.load(f)

        entries = []
        for item in data:
            # Handle both dict and Entry-like structures
            if isinstance(item, dict):
                entry = Entry(
                    key=item["key"],
                    type=EntryType(item.get("type", "misc")),
                    title=item.get("title", ""),
                    author=item.get("author"),
                    year=item.get("year"),
                    journal=item.get("journal"),
                    booktitle=item.get("booktitle"),
                    publisher=item.get("publisher"),
                    school=item.get("school"),
                    volume=item.get("volume"),
                    number=item.get("number"),
                    pages=item.get("pages"),
                    doi=item.get("doi"),
                    url=item.get("url"),
                    abstract=item.get("abstract"),
                    keywords=item.get("keywords", []),
                )
                entries.append(entry)

        return entries

    elif format == "bibtex":
        parser = BibtexParser()
        with open(file_path) as f:
            content = f.read()
        return parser.parse(content)

    else:
        raise ValueError(f"Unsupported format: {format}")


def save_entries_to_file(
    entries: list[Entry], file_path: Path, format: str = "bibtex"
) -> None:
    """Save entries to a file.

    Args:
        entries: List of entries to save
        file_path: Path to save to
        format: Output format
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if format == "json":
        data = []
        for entry in entries:
            entry_dict = {
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
                    entry_dict[field] = value

            data.append(entry_dict)

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    elif format == "bibtex":
        with open(file_path, "w") as f:
            for entry in entries:
                f.write(format_entry_bibtex(entry))
                f.write("\n\n")

    elif format == "csv":
        import csv

        fieldnames = ["key", "type", "title", "author", "year", "journal", "doi", "url"]

        with open(file_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for entry in entries:
                row = {
                    "key": entry.key,
                    "type": entry.type.value,
                    "title": entry.title,
                    "author": entry.author,
                    "year": entry.year,
                    "journal": getattr(entry, "journal", ""),
                    "doi": getattr(entry, "doi", ""),
                    "url": getattr(entry, "url", ""),
                }
                writer.writerow(row)

    else:
        raise ValueError(f"Unsupported format: {format}")


def filter_entries(
    entries: list[Entry],
    type: str | None = None,
    author: str | None = None,
    year: int | range | None = None,
    **kwargs,
) -> list[Entry]:
    """Filter entries based on criteria.

    Args:
        entries: List of entries to filter
        type: Entry type filter
        author: Author filter (substring match)
        year: Year filter (int or range)
        **kwargs: Additional field filters

    Returns:
        Filtered list of entries
    """
    result = entries

    if type:
        type_enum = EntryType(type.lower())
        result = [e for e in result if e.type == type_enum]

    if author:
        author_lower = author.lower()
        result = [e for e in result if e.author and author_lower in e.author.lower()]

    if year is not None:
        if isinstance(year, range):
            result = [e for e in result if e.year in year]
        else:
            result = [e for e in result if e.year == year]

    # Apply additional filters
    for field, value in kwargs.items():
        if value is not None:
            result = [
                e
                for e in result
                if hasattr(e, field)
                and str(getattr(e, field, "")).lower() == str(value).lower()
            ]

    return result


def sort_entries(
    entries: list[Entry], by: str = "key", reverse: bool = False
) -> list[Entry]:
    """Sort entries.

    Args:
        entries: List of entries to sort
        by: Field to sort by
        reverse: Reverse sort order

    Returns:
        Sorted list of entries
    """
    if by == "key":
        return sorted(entries, key=lambda e: e.key, reverse=reverse)
    elif by == "title":
        return sorted(entries, key=lambda e: e.title or "", reverse=reverse)
    elif by == "year":
        return sorted(entries, key=lambda e: e.year or 0, reverse=reverse)
    elif by == "author":
        return sorted(entries, key=lambda e: e.author or "", reverse=reverse)
    elif by == "type":
        return sorted(entries, key=lambda e: e.type.value, reverse=reverse)
    else:
        return entries


def format_entry_bibtex(entry: Entry) -> str:
    """Format entry as BibTeX.

    Args:
        entry: Entry to format

    Returns:
        BibTeX string
    """
    lines = [f"@{entry.type.value}{{{entry.key},"]

    # Required fields
    lines.append(f"  title = {{{entry.title}}},")

    # Optional fields
    if entry.author:
        lines.append(f"  author = {{{entry.author}}},")
    if entry.year:
        lines.append(f"  year = {{{entry.year}}},")

    # Type-specific fields
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
            lines.append(f"  {field} = {{{value}}},")

    # Abstract and keywords
    if hasattr(entry, "abstract") and entry.abstract:
        # Escape abstract for BibTeX
        abstract = entry.abstract.replace("\n", " ")
        lines.append(f"  abstract = {{{abstract}}},")

    if hasattr(entry, "keywords") and entry.keywords:
        keywords = ", ".join(entry.keywords)
        lines.append(f"  keywords = {{{keywords}}},")

    # Remove trailing comma from last field
    if lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]

    lines.append("}")

    return "\n".join(lines)
