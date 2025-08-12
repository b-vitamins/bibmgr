"""Base search backend interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchQuery:
    """Structured search query passed to backends."""

    query: Any
    limit: int = 20
    offset: int = 0
    fields: list[str] = field(default_factory=list)
    facet_fields: list[str] | None = None
    highlight: bool = False
    sort_by: str | None = None
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchMatch:
    """Individual search result from backend."""

    entry_key: str
    score: float
    highlights: dict[str, list[str]] | None = None
    entry: Any = None
    explanation: str | None = None

    def __post_init__(self):
        """Ensure score is within reasonable bounds."""
        if self.score < 0:
            self.score = 0.0
        elif self.score > 100:
            self.score = 100.0


@dataclass
class BackendResult:
    """Raw search results returned by backends."""

    results: list[SearchMatch]
    total: int
    facets: dict[str, list[tuple]] | None = None
    suggestions: list[str] | None = None
    took_ms: int | None = None


class SearchBackend(ABC):
    """Abstract interface for search backends."""

    @abstractmethod
    def index(self, entry_key: str, fields: dict[str, Any]) -> None:
        """Index a single document.

        Args:
            entry_key: Unique identifier for the document
            fields: Dictionary of field names to values

        Raises:
            IndexError: If indexing fails
        """
        pass

    @abstractmethod
    def index_batch(self, documents: list[dict[str, Any]]) -> None:
        """Index multiple documents efficiently.

        Args:
            documents: List of document dictionaries, each must include 'key' field

        Raises:
            IndexError: If batch indexing fails
        """
        pass

    @abstractmethod
    def search(self, query: SearchQuery) -> BackendResult:
        """Execute a search query.

        Args:
            query: Structured search query

        Returns:
            BackendResult with matches and metadata

        Raises:
            QueryError: If search execution fails
        """
        pass

    @abstractmethod
    def delete(self, entry_key: str) -> bool:
        """Delete a document from the index.

        Args:
            entry_key: Unique identifier of document to delete

        Returns:
            True if document was deleted, False if not found
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all documents from the index.

        Raises:
            IndexError: If clearing fails
        """
        pass

    @abstractmethod
    def commit(self) -> None:
        """Commit pending changes to the index.

        This ensures that all indexing operations are persisted
        and visible to subsequent searches.
        """
        pass

    @abstractmethod
    def get_statistics(self) -> dict[str, Any]:
        """Get index statistics.

        Returns:
            Dictionary with statistics like document count, index size, etc.
        """
        pass

    def suggest(self, prefix: str, field: str, limit: int) -> list[str]:
        """Get search suggestions for a prefix (optional feature).

        Args:
            prefix: Text prefix to complete
            field: Field to search for completions
            limit: Maximum number of suggestions

        Returns:
            List of suggested completions
        """
        return []

    def more_like_this(
        self, entry_key: str, limit: int, min_score: float
    ) -> BackendResult:
        """Find similar documents (optional feature).

        Args:
            entry_key: Key of reference document
            limit: Maximum number of similar documents
            min_score: Minimum similarity score threshold

        Returns:
            BackendResult with similar documents

        Raises:
            NotImplementedError: If backend doesn't support this feature
        """
        raise NotImplementedError("Backend doesn't support more-like-this")


class SearchError(Exception):
    """Base exception for search-related errors."""


class IndexError(SearchError):
    """Error during document indexing operations."""


class QueryError(SearchError):
    """Error during query parsing or execution."""
