"""Search history and saved searches management.

This module provides persistent storage for search history and saved searches,
enabling query analytics and user convenience features.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SearchHistoryEntry:
    """A single search history entry."""

    query: str
    timestamp: datetime
    result_count: int
    search_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "timestamp": self.timestamp.isoformat(),
            "result_count": self.result_count,
            "search_time_ms": self.search_time_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchHistoryEntry:
        """Create from dictionary."""
        return cls(
            query=data["query"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            result_count=data["result_count"],
            search_time_ms=data["search_time_ms"],
        )


@dataclass
class SavedSearch:
    """A saved search with metadata."""

    name: str
    query: str
    description: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "query": self.query,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SavedSearch:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            query=data["query"],
            description=data.get("description"),
            created_at=datetime.fromisoformat(data["created_at"]),
            tags=data.get("tags", []),
        )


class SearchHistory:
    """Manages search history and saved searches persistently."""

    def __init__(self, data_dir: Path | None = None):
        """Initialize history manager.

        Args:
            data_dir: Directory for storing history (default: ~/.cache/bibmgr/history)
        """
        if data_dir is None:
            data_dir = Path.home() / ".cache" / "bibmgr" / "history"

        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.history_file = self.data_dir / "history.json"
        self.saved_file = self.data_dir / "saved_searches.json"

        # Load existing data
        self.history = self._load_history()
        self.saved_searches = self._load_saved()

    def _load_history(self) -> list[SearchHistoryEntry]:
        """Load search history from disk."""
        if not self.history_file.exists():
            return []

        try:
            with open(self.history_file, "r") as f:
                data = json.load(f)
                return [SearchHistoryEntry.from_dict(item) for item in data]
        except (json.JSONDecodeError, KeyError, ValueError):
            # Handle corrupt files gracefully
            return []

    def _load_saved(self) -> dict[str, SavedSearch]:
        """Load saved searches from disk."""
        if not self.saved_file.exists():
            return {}

        try:
            with open(self.saved_file, "r") as f:
                data = json.load(f)
                return {
                    name: SavedSearch.from_dict(item) for name, item in data.items()
                }
        except (json.JSONDecodeError, KeyError, ValueError):
            # Handle corrupt files gracefully
            return {}

    def _save_history(self) -> None:
        """Persist history to disk."""
        # Keep only last 1000 entries
        recent = self.history[-1000:]
        data = [entry.to_dict() for entry in recent]

        with open(self.history_file, "w") as f:
            json.dump(data, f, indent=2)

    def _save_saved(self) -> None:
        """Persist saved searches to disk."""
        data = {name: search.to_dict() for name, search in self.saved_searches.items()}

        with open(self.saved_file, "w") as f:
            json.dump(data, f, indent=2)

    def add_search(self, query: str, result_count: int, search_time_ms: float) -> None:
        """Add a search to history.

        Args:
            query: The search query
            result_count: Number of results found
            search_time_ms: Search execution time
        """
        entry = SearchHistoryEntry(
            query=query,
            timestamp=datetime.now(),
            result_count=result_count,
            search_time_ms=search_time_ms,
        )

        self.history.append(entry)
        self._save_history()

    def save_search(
        self,
        name: str,
        query: str,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Save a search for later use.

        Args:
            name: Unique name for the search
            query: The search query
            description: Optional description
            tags: Optional tags for organization
        """
        saved = SavedSearch(
            name=name,
            query=query,
            description=description,
            tags=tags or [],
        )

        self.saved_searches[name] = saved
        self._save_saved()

    def get_saved(self, name: str) -> SavedSearch | None:
        """Get a saved search by name.

        Args:
            name: Name of the saved search

        Returns:
            SavedSearch or None if not found
        """
        return self.saved_searches.get(name)

    def list_saved(self, tag: str | None = None) -> list[SavedSearch]:
        """List saved searches, optionally filtered by tag.

        Args:
            tag: Optional tag to filter by

        Returns:
            List of saved searches
        """
        searches = list(self.saved_searches.values())

        if tag:
            searches = [s for s in searches if tag in s.tags]

        # Sort by creation date, newest first
        searches.sort(key=lambda s: s.created_at, reverse=True)

        return searches

    def get_popular_queries(self, limit: int = 10) -> list[tuple[str, int]]:
        """Get most popular queries by frequency.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of (query, count) tuples
        """
        counter = Counter(entry.query for entry in self.history)
        return counter.most_common(limit)

    def get_recent_queries(self, limit: int = 10) -> list[SearchHistoryEntry]:
        """Get most recent queries.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of recent history entries
        """
        return self.history[-limit:][::-1]  # Reverse for newest first

    def get_statistics(self) -> dict[str, Any]:
        """Get search history statistics.

        Returns:
            Dictionary of statistics
        """
        if not self.history:
            return {
                "total_searches": 0,
                "unique_queries": 0,
                "avg_search_time_ms": 0.0,
                "avg_result_count": 0.0,
            }

        unique_queries = len(set(e.query for e in self.history))
        avg_time = sum(e.search_time_ms for e in self.history) / len(self.history)
        avg_results = sum(e.result_count for e in self.history) / len(self.history)

        return {
            "total_searches": len(self.history),
            "unique_queries": unique_queries,
            "avg_search_time_ms": avg_time,
            "avg_result_count": avg_results,
            "saved_searches": len(self.saved_searches),
        }

    def clear_history(self) -> None:
        """Clear all search history."""
        self.history = []
        self._save_history()
