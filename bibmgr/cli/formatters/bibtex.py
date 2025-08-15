"""BibTeX output formatter."""

import re
from typing import Any

from bibmgr.core.models import Entry


def format_entry_bibtex(entry: Entry) -> str:
    """Format a single entry as BibTeX."""
    lines = [f"@{entry.type.value}{{{entry.key},"]

    # Add fields
    fields = []
    if entry.title:
        fields.append(f"  title = {{{entry.title}}}")

    # Handle authors - prefer authors list over author string
    if hasattr(entry, "authors") and entry.authors:
        author_str = " and ".join(entry.authors)
        fields.append(f"  author = {{{author_str}}}")
    elif entry.author:
        fields.append(f"  author = {{{entry.author}}}")

    if entry.year:
        fields.append(f"  year = {{{entry.year}}}")
    if entry.journal:
        fields.append(f"  journal = {{{entry.journal}}}")
    if entry.booktitle:
        fields.append(f"  booktitle = {{{entry.booktitle}}}")
    if entry.publisher:
        fields.append(f"  publisher = {{{entry.publisher}}}")
    if entry.volume:
        fields.append(f"  volume = {{{entry.volume}}}")
    if entry.number:
        fields.append(f"  number = {{{entry.number}}}")
    if entry.pages:
        fields.append(f"  pages = {{{entry.pages}}}")
    if entry.doi:
        fields.append(f"  doi = {{{entry.doi}}}")
    if entry.url:
        fields.append(f"  url = {{{entry.url}}}")
    if entry.abstract:
        fields.append(f"  abstract = {{{entry.abstract}}}")
    if entry.keywords:
        keywords_str = (
            ", ".join(entry.keywords)
            if isinstance(entry.keywords, list | tuple)
            else entry.keywords
        )
        fields.append(f"  keywords = {{{keywords_str}}}")

    # Add additional fields
    for field in [
        "isbn",
        "issn",
        "edition",
        "series",
        "chapter",
        "address",
        "month",
        "note",
    ]:
        if hasattr(entry, field) and getattr(entry, field):
            fields.append(f"  {field} = {{{getattr(entry, field)}}}")

    lines.extend([f + "," for f in fields[:-1]])
    if fields:
        lines.append(fields[-1])

    lines.append("}")
    return "\n".join(lines)


def format_entries_bibtex(entries: list[Entry]) -> str:
    """Format multiple entries as BibTeX."""
    return "\n\n".join(format_entry_bibtex(entry) for entry in entries)


def parse_bibtex_entry(bibtex: str) -> dict[str, Any]:
    """Parse a BibTeX entry string into a dictionary.

    This is a simple parser for basic use cases.
    For full BibTeX parsing, use the storage.importers.BibtexImporter.
    """
    data = {}

    # Extract entry type and key
    match = re.match(r"\s*@(\w+)\s*\{\s*([^,]+)\s*,", bibtex.strip(), re.IGNORECASE)
    if not match:
        raise ValueError("Invalid BibTeX format")

    data["type"] = match.group(1).lower()
    data["key"] = match.group(2).strip()

    # Extract fields
    field_pattern = r"(\w+)\s*=\s*\{([^}]*)\}"
    for match in re.finditer(field_pattern, bibtex):
        field_name = match.group(1).lower()
        field_value = match.group(2).strip()

        # Handle special fields
        if field_name == "author":
            # Split authors by " and "
            data["authors"] = [a.strip() for a in field_value.split(" and ")]
            data["author"] = field_value  # Keep original too
        elif field_name == "keywords":
            # Split keywords
            data["keywords"] = [k.strip() for k in field_value.split(",")]
        elif field_name == "year":
            # Convert to int/string
            try:
                data["year"] = str(int(field_value))
            except ValueError:
                data["year"] = field_value
        else:
            data[field_name] = field_value

    return data
