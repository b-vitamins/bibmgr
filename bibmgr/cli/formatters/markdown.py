"""Markdown output formatter.

Provides formatting of entries and collections to Markdown format.
"""

from bibmgr.core.models import Collection, Entry


def format_entry_markdown(entry: Entry) -> str:
    """Format a single entry as Markdown.

    Args:
        entry: Entry to format

    Returns:
        Markdown formatted string
    """
    lines = [f"# {entry.key}\n"]

    # Basic fields
    lines.append(f"**Type:** {entry.type.value}")
    lines.append(f"**Title:** {entry.title or 'No title'}")

    if hasattr(entry, "authors") and entry.authors:
        lines.append(f"**Authors:** {' and '.join(entry.authors)}")
    elif entry.author:
        lines.append(f"**Authors:** {entry.author}")

    if entry.year:
        lines.append(f"**Year:** {entry.year}")

    # Publication details
    if entry.journal:
        lines.append(f"**Journal:** {entry.journal}")
    elif entry.booktitle:
        lines.append(f"**Book/Conference:** {entry.booktitle}")

    if entry.publisher:
        lines.append(f"**Publisher:** {entry.publisher}")

    if entry.volume:
        lines.append(f"**Volume:** {entry.volume}")

    if entry.number:
        lines.append(f"**Number:** {entry.number}")

    if entry.pages:
        lines.append(f"**Pages:** {entry.pages}")

    # Identifiers
    if entry.doi:
        lines.append(f"**DOI:** [{entry.doi}](https://doi.org/{entry.doi})")

    if entry.url:
        lines.append(f"**URL:** [{entry.url}]({entry.url})")

    if entry.isbn:
        lines.append(f"**ISBN:** {entry.isbn}")

    # Keywords
    if entry.keywords:
        keywords_str = (
            ", ".join(entry.keywords)
            if isinstance(entry.keywords, list | tuple)
            else entry.keywords
        )
        lines.append(f"**Keywords:** {keywords_str}")

    # Abstract
    if entry.abstract:
        lines.append("\n## Abstract\n")
        lines.append(entry.abstract)

    return "\n".join(lines)


def format_entries_markdown(entries: list[Entry], as_table: bool = True) -> str:
    """Format multiple entries as Markdown.

    Args:
        entries: Entries to format
        as_table: Whether to format as table (True) or individual entries (False)

    Returns:
        Markdown formatted string
    """
    if as_table:
        # Table format
        lines = ["| Key | Title | Authors | Year |", "|-----|-------|---------|------|"]

        for entry in entries:
            key = entry.key
            title = (entry.title or "No title").replace("|", "\\|")

            # Format authors
            if hasattr(entry, "authors") and entry.authors:
                if len(entry.authors) <= 2:
                    authors = " and ".join(entry.authors)
                else:
                    authors = f"{entry.authors[0]} et al."
            elif entry.author:
                authors = entry.author
            else:
                authors = "-"
            authors = authors.replace("|", "\\|")

            year = str(entry.year) if entry.year else "-"

            lines.append(f"| {key} | {title} | {authors} | {year} |")

        return "\n".join(lines)
    else:
        # Individual entries
        return "\n\n---\n\n".join(format_entry_markdown(entry) for entry in entries)


def format_collections_markdown(collections: list[Collection]) -> str:
    """Format collections as Markdown.

    Args:
        collections: Collections to format

    Returns:
        Markdown formatted string
    """
    lines = ["# Collections\n"]

    for collection in collections:
        lines.append(f"## {collection.name}\n")

        if collection.description:
            lines.append(f"{collection.description}\n")

        # Determine type based on whether it has entry_keys or query
        is_manual = collection.entry_keys is not None
        coll_type = "Manual" if is_manual else "Smart"
        lines.append(f"**Type:** {coll_type}")

        if is_manual and collection.entry_keys:
            lines.append(f"**Entries:** {len(collection.entry_keys)}")
        elif collection.query:
            lines.append(f"**Query:** `{collection.query}`")
            lines.append("**Entries:** Dynamic")

        lines.append("")  # Empty line between collections

    return "\n".join(lines)
