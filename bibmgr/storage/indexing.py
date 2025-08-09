"""Full-text indexing for bibliography entries.

Provides pluggable full-text search backends with unified interface.
Supports both simple in-memory indexing and advanced Whoosh-based
search with field-specific queries and relevance scoring.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from bibmgr.core.models import Entry


@dataclass
class SearchResult:
    """A search result with relevance score."""

    entry_key: str
    score: float
    highlights: dict[str, list[str]] | None = None  # field -> highlighted snippets

    def __lt__(self, other):
        """Sort by score descending."""
        return self.score > other.score


class IndexBackend(ABC):
    """Abstract base class for indexing backends."""

    @abstractmethod
    def index_entry(self, entry: Entry) -> None:
        """Index a single entry."""
        pass

    @abstractmethod
    def update_entry(self, entry: Entry) -> None:
        """Update an existing entry in the index."""
        pass

    @abstractmethod
    def remove_entry(self, key: str) -> None:
        """Remove an entry from the index."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 100) -> list[SearchResult]:
        """Search the index."""
        pass

    @abstractmethod
    def search_field(
        self, field: str, query: str, limit: int = 100
    ) -> list[SearchResult]:
        """Search a specific field."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear the entire index."""
        pass

    @abstractmethod
    def optimize(self) -> None:
        """Optimize the index for better performance."""
        pass


class SimpleIndexBackend(IndexBackend):
    """Simple in-memory index for basic searching."""

    def __init__(self):
        self._index: dict[str, dict[str, dict[str, int]]] = {}
        self._entries: dict[str, Entry] = {}

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization - lowercase and split on non-alphanumeric."""
        import re

        if not text:
            return []
        tokens = re.findall(r"\w+", text.lower())
        return tokens

    def _index_field(self, entry_key: str, field_name: str, text: str) -> None:
        """Index a single field."""
        tokens = self._tokenize(text)
        token_counts: dict[str, int] = {}
        for token in tokens:
            token_counts[token] = token_counts.get(token, 0) + 1

        for token, count in token_counts.items():
            if token not in self._index:
                self._index[token] = {}
            if entry_key not in self._index[token]:
                self._index[token][entry_key] = {}
            self._index[token][entry_key][field_name] = count

    def index_entry(self, entry: Entry) -> None:
        """Index a single entry."""
        self._entries[entry.key] = entry

        fields = [
            ("title", entry.title),
            ("author", entry.author),
            ("abstract", entry.abstract),
            ("journal", entry.journal),
            ("keywords", " ".join(entry.keywords) if entry.keywords else None),
        ]

        for field_name, value in fields:
            if value:
                self._index_field(entry.key, field_name, value)

    def update_entry(self, entry: Entry) -> None:
        """Update an existing entry in the index."""
        # Remove old entry
        self.remove_entry(entry.key)
        # Re-index
        self.index_entry(entry)

    def remove_entry(self, key: str) -> None:
        """Remove an entry from the index."""
        # Remove from entries
        if key in self._entries:
            del self._entries[key]

        # Remove from inverted index
        tokens_to_remove = []
        for token, entry_data in self._index.items():
            if key in entry_data:
                del entry_data[key]
                if not entry_data:
                    tokens_to_remove.append(token)

        # Clean up empty tokens
        for token in tokens_to_remove:
            del self._index[token]

    def search(self, query: str, limit: int = 100) -> list[SearchResult]:
        """Search the index."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores: dict[str, float] = {}

        for token in query_tokens:
            if token in self._index:
                for entry_key, field_counts in self._index[token].items():
                    if entry_key not in scores:
                        scores[entry_key] = 0
                    scores[entry_key] += sum(field_counts.values())

        results = [
            SearchResult(entry_key=entry_key, score=score / len(query_tokens))
            for entry_key, score in scores.items()
        ]

        results.sort()
        return results[:limit]

    def search_field(
        self, field: str, query: str, limit: int = 100
    ) -> list[SearchResult]:
        """Search a specific field."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Score entries by matching tokens in specific field
        scores: dict[str, float] = {}

        for token in query_tokens:
            if token in self._index:
                for entry_key, field_counts in self._index[token].items():
                    if field in field_counts:
                        if entry_key not in scores:
                            scores[entry_key] = 0
                        # Use term frequency in the specific field
                        scores[entry_key] += field_counts[field]

        # Convert to results
        results = []
        for entry_key, score in scores.items():
            results.append(
                SearchResult(entry_key=entry_key, score=score / len(query_tokens))
            )

        results.sort()
        return results[:limit]

    def clear(self) -> None:
        """Clear the entire index."""
        self._index.clear()
        self._entries.clear()

    def optimize(self) -> None:
        """No optimization needed for in-memory index."""
        pass


class WhooshIndexBackend(IndexBackend):
    """Whoosh-based full-text indexing (if available)."""

    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir)
        self._writer = None

        try:
            from whoosh import index
            from whoosh.fields import ID, KEYWORD, TEXT, Schema

            self.whoosh_available = True

            # Define schema
            self.schema = Schema(
                key=ID(stored=True, unique=True),
                title=TEXT(stored=True),
                author=TEXT(stored=True),
                abstract=TEXT(stored=True),
                keywords=KEYWORD(stored=True, commas=True),
                journal=TEXT(stored=True),
                year=ID(stored=True),
                content=TEXT,  # Combined field for general search
            )

            # Create or open index
            self.index_dir.mkdir(parents=True, exist_ok=True)
            if index.exists_in(str(self.index_dir)):
                self.ix = index.open_dir(str(self.index_dir))
            else:
                self.ix = index.create_in(str(self.index_dir), self.schema)

        except ImportError:
            self.whoosh_available = False
            # Fall back to simple implementation
            self._fallback = SimpleIndexBackend()

    @property
    def _whoosh_available(self) -> bool:
        """Compatibility property for skipif conditions."""
        return self.whoosh_available

    def index_entry(self, entry: Entry) -> None:
        """Index a single entry."""
        if not self.whoosh_available:
            return self._fallback.index_entry(entry)

        # Combine all text for content field
        content_parts = []
        if entry.title:
            content_parts.append(entry.title)
        if entry.author:
            content_parts.append(entry.author)
        if entry.abstract:
            content_parts.append(entry.abstract)
        if entry.keywords:
            content_parts.append(" ".join(entry.keywords))

        writer = self.ix.writer()
        writer.update_document(
            key=entry.key,
            title=entry.title or "",
            author=entry.author or "",
            abstract=entry.abstract or "",
            keywords=",".join(entry.keywords) if entry.keywords else "",
            journal=entry.journal or "",
            year=str(entry.year) if entry.year else "",
            content=" ".join(content_parts),
        )
        writer.commit()

    def update_entry(self, entry: Entry) -> None:
        """Update an existing entry in the index."""
        # update_document handles both insert and update
        self.index_entry(entry)

    def remove_entry(self, key: str) -> None:
        """Remove an entry from the index."""
        if not self.whoosh_available:
            return self._fallback.remove_entry(key)

        writer = self.ix.writer()
        writer.delete_by_term("key", key)
        writer.commit()

    def search(self, query: str, limit: int = 100) -> list[SearchResult]:
        """Search the index."""
        if not self.whoosh_available:
            return self._fallback.search(query, limit)

        from whoosh.qparser import MultifieldParser

        # Search multiple fields
        parser = MultifieldParser(
            ["title", "author", "abstract", "keywords", "content"], self.ix.schema
        )

        results = []
        with self.ix.searcher() as searcher:
            q = parser.parse(query)
            search_results = searcher.search(q, limit=limit)

            for hit in search_results:
                results.append(
                    SearchResult(entry_key=hit["key"], score=hit.score or 0.0)
                )

        return results

    def search_field(
        self, field: str, query: str, limit: int = 100
    ) -> list[SearchResult]:
        """Search a specific field."""
        if not self.whoosh_available:
            return self._fallback.search_field(field, query, limit)

        from whoosh.qparser import QueryParser

        parser = QueryParser(field, self.ix.schema)

        results = []
        with self.ix.searcher() as searcher:
            q = parser.parse(query)
            search_results = searcher.search(q, limit=limit)

            for hit in search_results:
                results.append(
                    SearchResult(entry_key=hit["key"], score=hit.score or 0.0)
                )

        return results

    def clear(self) -> None:
        """Clear the entire index."""
        if not self.whoosh_available:
            return self._fallback.clear()

        # Create new empty index
        from whoosh import index

        self.ix = index.create_in(str(self.index_dir), self.schema)

    def optimize(self) -> None:
        """Optimize the index for better performance."""
        if not self.whoosh_available:
            return self._fallback.optimize()

        self.ix.optimize()


class IndexManager:
    """Manages full-text indexing for entries."""

    def __init__(self, backend: IndexBackend):
        self.backend = backend

    def index_entries(self, entries: list[Entry]) -> None:
        """Index multiple entries."""
        for entry in entries:
            self.backend.index_entry(entry)

    def reindex_all(self, entries: list[Entry]) -> None:
        """Rebuild the entire index."""
        self.backend.clear()
        self.index_entries(entries)
        self.backend.optimize()

    def search(self, query: str, limit: int = 100) -> list[SearchResult]:
        """Search all fields."""
        return self.backend.search(query, limit)

    def search_title(self, query: str, limit: int = 100) -> list[SearchResult]:
        """Search titles only."""
        return self.backend.search_field("title", query, limit)

    def search_author(self, query: str, limit: int = 100) -> list[SearchResult]:
        """Search authors only."""
        return self.backend.search_field("author", query, limit)

    def search_abstract(self, query: str, limit: int = 100) -> list[SearchResult]:
        """Search abstracts only."""
        return self.backend.search_field("abstract", query, limit)
