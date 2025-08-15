"""JSON output formatter."""

import json
from typing import Any

from bibmgr.core.models import Entry
from bibmgr.search.results import SearchResultCollection
from bibmgr.storage.metadata import EntryMetadata


def _entry_to_dict(entry: Entry) -> dict[str, Any]:
    """Convert entry to dictionary."""
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
        if hasattr(entry, field) and getattr(entry, field):
            data[field] = getattr(entry, field)

    return data


def format_entry_json(
    entry: Entry,
    pretty: bool = True,
    include_metadata: bool = False,
    metadata: EntryMetadata | None = None,
) -> str:
    """Format a single entry as JSON."""
    data = _entry_to_dict(entry)

    if include_metadata and metadata:
        data["metadata"] = {
            "tags": list(metadata.tags),
            "rating": metadata.rating,
            "read_status": metadata.read_status,
            "importance": metadata.importance,
            "notes_count": metadata.notes_count,
        }
        if metadata.read_date:
            data["metadata"]["read_date"] = metadata.read_date.isoformat()

    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


def format_entries_json(entries: list[Entry], pretty: bool = True) -> str:
    """Format multiple entries as JSON."""
    data = {
        "entries": [_entry_to_dict(entry) for entry in entries],
        "total": len(entries),
    }
    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


def format_search_results_json(
    results: SearchResultCollection, pretty: bool = True
) -> str:
    """Format search results as JSON."""
    data = {
        "query": results.query,
        "total": results.total,
        "matches": [
            {
                "entry_key": match.entry_key,
                "score": match.score,
                "highlights": match.highlights if hasattr(match, "highlights") else {},
            }
            for match in results.matches
        ],
        "facets": results.facets,
        "suggestions": results.suggestions,
        "statistics": (
            {
                "total_results": results.statistics.total_results,
                "search_time_ms": results.statistics.search_time_ms,
                "took_ms": results.statistics.search_time_ms,  # Backward compatibility
                "query_time_ms": results.statistics.query_time_ms,
                "fetch_time_ms": results.statistics.fetch_time_ms,
                "backend_name": results.statistics.backend_name,
                "index_size": results.statistics.index_size,
            }
            if results.statistics
            else None
        ),
    }

    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)
