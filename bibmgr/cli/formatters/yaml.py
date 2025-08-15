"""YAML output formatter."""

from typing import Any

import yaml

from bibmgr.core.models import Entry


def format_entry_yaml(entry: Entry) -> str:
    """Format a single entry as YAML."""
    data = _entry_to_dict(entry)
    return yaml.safe_dump(
        data, default_flow_style=False, allow_unicode=True, sort_keys=False
    )


def format_entries_yaml(entries: list[Entry]) -> str:
    """Format multiple entries as YAML."""
    data = {
        "entries": [_entry_to_dict(entry) for entry in entries],
        "total": len(entries),
    }
    return yaml.safe_dump(
        data, default_flow_style=False, allow_unicode=True, sort_keys=False
    )


def _entry_to_dict(entry: Entry) -> dict[str, Any]:
    """Convert entry to dictionary for YAML serialization."""
    data = {
        "key": entry.key,
        "type": entry.type.value,
        "title": entry.title,
        "year": entry.year,
    }

    # Add authors
    if hasattr(entry, "authors") and entry.authors:
        data["authors"] = entry.authors
    elif entry.author:
        data["author"] = entry.author

    # Add other fields
    for field in [
        "journal",
        "booktitle",
        "publisher",
        "volume",
        "number",
        "pages",
        "doi",
        "isbn",
        "issn",
        "url",
        "abstract",
        "keywords",
        "month",
        "note",
        "edition",
        "series",
        "chapter",
        "address",
    ]:
        if hasattr(entry, field):
            value = getattr(entry, field)
            if value is not None:
                data[field] = value

    return data
