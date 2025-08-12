"""Search engine implementation for bibliography entries."""

import time
from pathlib import Path
from typing import Any

from ..core.models import Entry as BibEntry
from .backends.base import SearchBackend, SearchQuery
from .backends.memory import MemoryBackend
from .highlighting import Highlighter
from .indexing import EntryIndexer, FieldConfiguration
from .query import QueryExpander, QueryParser
from .results import (
    ResultsBuilder,
    SearchResultCollection,
    SearchSuggestion,
    SortOrder,
    create_empty_results,
)


class SearchEngine:
    """Search engine for bibliography entries.

    Coordinates query parsing, indexing, backend operations,
    highlighting, and result formatting.
    """

    def __init__(
        self,
        backend: SearchBackend | None = None,
        field_config: FieldConfiguration | None = None,
        enable_highlighting: bool = True,
        enable_query_expansion: bool = True,
        ranker: Any = None,
        repository: Any = None,
    ):
        """Initialize search engine.

        Args:
            backend: Search backend to use (default: MemoryBackend)
            field_config: Field configuration for indexing
            enable_highlighting: Whether to enable result highlighting
            enable_query_expansion: Whether to enable query expansion
            ranker: Ranking algorithm to use (default: BM25Ranker)
            repository: Entry repository for retrieving full entry data
        """
        self.backend = backend or MemoryBackend()
        self.field_config = field_config or FieldConfiguration()
        self.indexer = EntryIndexer(self.field_config)
        self.query_parser = QueryParser()
        self.query_expander = QueryExpander() if enable_query_expansion else None
        self.highlighter = Highlighter() if enable_highlighting else None
        self.repository = repository

        from .ranking import BM25Ranker

        self.ranker = ranker or BM25Ranker()
        self.enable_highlighting = enable_highlighting
        self.enable_query_expansion = enable_query_expansion
        self.default_limit = 20
        self.max_limit = 1000
        self._index_size = 0
        self._last_query_time = 0

    def index_entry(self, entry: BibEntry) -> None:
        """Index a single bibliography entry.

        Args:
            entry: Bibliography entry to index
        """
        doc = self.indexer.index_entry(entry)
        self.backend.index(entry.key, doc)
        self._index_size += 1

    def index_entries(self, entries: list[BibEntry]) -> None:
        """Index multiple bibliography entries efficiently.

        Args:
            entries: List of bibliography entries to index
        """
        documents = []
        for entry in entries:
            doc = self.indexer.index_entry(entry)
            doc["key"] = entry.key
            documents.append(doc)

        self.backend.index_batch(documents)
        self._index_size += len(entries)

    def remove_entry(self, entry_key: str) -> bool:
        """Remove an entry from the search index.

        Args:
            entry_key: Key of entry to remove

        Returns:
            True if entry was removed, False if not found
        """
        success = self.backend.delete(entry_key)
        if success:
            self._index_size = max(0, self._index_size - 1)
        return success

    def clear_index(self) -> None:
        """Clear all entries from the search index."""
        self.backend.clear()
        self._index_size = 0

    def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        fields: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        sort_by: SortOrder | None = None,
        enable_facets: bool = True,
        enable_suggestions: bool = True,
        expand_query: bool = True,
        highlight_results: bool = True,
    ) -> SearchResultCollection:
        """Execute a search query.

        Args:
            query: Search query string
            limit: Maximum number of results to return
            offset: Number of results to skip
            fields: Optional list of fields to search in
            filters: Optional filters to apply
            sort_by: Sort order for results
            enable_facets: Whether to compute facets
            enable_suggestions: Whether to generate suggestions
            expand_query: Whether to apply query expansion
            highlight_results: Whether to highlight matches

        Returns:
            Search results with matches, facets, and metadata
        """
        start_time = time.time()

        if not query or not query.strip():
            return create_empty_results(query, limit, self.backend.__class__.__name__)

        limit = min(max(1, limit), self.max_limit)
        offset = max(0, offset)

        try:
            parsed_query = self.query_parser.parse(query.strip())

            if expand_query and self.query_expander:
                parsed_query = self.query_expander.expand_query(parsed_query)

            search_query = SearchQuery(
                query=parsed_query,
                limit=limit,
                offset=offset,
                fields=fields or [],
                facet_fields=self._get_facet_fields() if enable_facets else None,
                highlight=highlight_results and self.enable_highlighting,
                filters=filters or {},
            )

            backend_result = self.backend.search(search_query)

            ranked_matches = backend_result.results
            if ranked_matches and self.ranker:
                if self.repository:
                    for match in ranked_matches:
                        try:
                            entry = self.repository.find(match.entry_key)
                            if entry:
                                match.entry = entry
                        except Exception:
                            pass

                from .ranking import ScoringContext

                query_terms = self._extract_query_terms(parsed_query)
                context = ScoringContext(
                    total_docs=self._index_size,
                    avg_doc_length=100,
                    doc_frequencies=self._estimate_doc_frequencies(query_terms),
                    query_time_ms=backend_result.took_ms or 0,
                )

                ranked_matches = self.ranker.rank(ranked_matches, query_terms, context)
                total_before_pagination = backend_result.total
            else:
                total_before_pagination = backend_result.total

            builder = ResultsBuilder()
            builder.set_pagination(offset, limit, total_before_pagination)
            builder.set_query_info(query, parsed_query)
            builder.set_timing(backend_result.took_ms or 0)
            builder.set_backend_info(self.backend.__class__.__name__, self._index_size)

            for match in ranked_matches:
                builder.add_match(
                    match.entry_key,
                    match.score,
                    entry=getattr(match, "entry", None),
                    highlights=match.highlights,
                )

            if enable_facets and backend_result.facets:
                for field, values in backend_result.facets.items():
                    field_display_name = self._get_field_display_name(field)
                    builder.add_facet(field, field_display_name, values)

            if enable_suggestions:
                suggestions = self._generate_suggestions(
                    query, parsed_query, backend_result.total
                )
                for suggestion in suggestions:
                    builder.add_suggestion(
                        suggestion.suggestion,
                        suggestion.suggestion_type,
                        suggestion.confidence,
                        suggestion.description,
                    )

            results = builder.build()

            if sort_by and sort_by != SortOrder.RELEVANCE:
                results = results.sort_by(sort_by)

            total_time = int((time.time() - start_time) * 1000)
            self._last_query_time = total_time

            return results

        except Exception as e:
            error_results = create_empty_results(
                query, limit, self.backend.__class__.__name__
            )
            error_results.suggestions = [
                SearchSuggestion(
                    suggestion=query,
                    suggestion_type="error",
                    confidence=0.0,
                    description=f"Search error: {str(e)}",
                )
            ]
            return error_results

    def suggest(self, prefix: str, field: str = "title", limit: int = 10) -> list[str]:
        """Get search suggestions for a prefix.

        Args:
            prefix: Text prefix to complete
            field: Field to search for completions
            limit: Maximum number of suggestions

        Returns:
            List of suggested completions
        """
        if hasattr(self.backend, "suggest"):
            return self.backend.suggest(prefix, field, limit)
        return []

    def more_like_this(
        self, entry_key: str, limit: int = 10, min_score: float = 0.1
    ) -> SearchResultCollection:
        """Find entries similar to a given entry.

        Args:
            entry_key: Key of reference entry
            limit: Maximum number of similar entries
            min_score: Minimum similarity score threshold

        Returns:
            Search results with similar entries
        """
        try:
            if hasattr(self.backend, "more_like_this"):
                backend_result = self.backend.more_like_this(
                    entry_key, limit, min_score
                )

                builder = ResultsBuilder()
                builder.set_pagination(0, limit, backend_result.total)
                builder.set_query_info(f"more_like:{entry_key}")
                builder.set_timing(backend_result.took_ms or 0)
                builder.set_backend_info(
                    self.backend.__class__.__name__, self._index_size
                )

                for match in backend_result.results:
                    builder.add_match(match.entry_key, match.score)

                return builder.build()

        except Exception:
            pass

        return create_empty_results(
            f"more_like:{entry_key}", limit, self.backend.__class__.__name__
        )

    def validate_query(self, query: str) -> list[str]:
        """Validate a query string and return any issues.

        Args:
            query: Query string to validate

        Returns:
            List of validation error messages
        """
        try:
            parsed_query = self.query_parser.parse(query)
            return self.query_parser.validate_query(parsed_query)
        except Exception as e:
            return [f"Query parsing error: {str(e)}"]

    def get_statistics(self) -> dict[str, Any]:
        """Get search engine statistics.

        Returns:
            Dictionary with engine and backend statistics
        """
        backend_stats = self.backend.get_statistics()

        return {
            "engine": {
                "index_size": self._index_size,
                "last_query_time_ms": self._last_query_time,
                "backend_type": self.backend.__class__.__name__,
                "highlighting_enabled": self.enable_highlighting,
                "query_expansion_enabled": self.enable_query_expansion,
            },
            "backend": backend_stats,
            "field_config": {
                "total_fields": len(self.field_config.fields),
                "searchable_fields": len(self.field_config.get_searchable_fields()),
                "facet_fields": len(self.field_config.get_facet_fields()),
            },
        }

    def commit(self) -> None:
        """Commit any pending changes to the search index."""
        self.backend.commit()

    def _get_facet_fields(self) -> list[str]:
        """Get list of fields suitable for faceting."""
        return self.field_config.get_facet_fields()

    def _get_field_display_name(self, field: str) -> str:
        """Get human-readable display name for a field."""
        display_names = {
            "entry_type": "Entry Type",
            "author": "Authors",
            "journal": "Journal",
            "booktitle": "Book/Conference",
            "year": "Publication Year",
            "keywords": "Keywords",
            "publisher": "Publisher",
        }
        return display_names.get(field, field.title())

    def _generate_suggestions(
        self, original_query: str, parsed_query: Any, result_count: int
    ) -> list[SearchSuggestion]:
        """Generate search suggestions based on query and results."""
        suggestions = []

        if self.query_expander:
            try:
                expander_suggestions = self.query_expander.suggest_corrections(
                    parsed_query, 2
                )
                for suggestion in expander_suggestions:
                    suggestions.append(
                        SearchSuggestion(
                            suggestion=suggestion.suggested_query,
                            suggestion_type=suggestion.suggestion_type,
                            confidence=suggestion.confidence,
                            description=suggestion.explanation,
                        )
                    )
            except Exception:
                pass

        if result_count < 3 and self.query_expander:
            try:
                relaxed_query = self.query_expander.relax_query(parsed_query, 1)
                if relaxed_query.to_string() != parsed_query.to_string():
                    suggestions.append(
                        SearchSuggestion(
                            suggestion=relaxed_query.to_string(),
                            suggestion_type="relaxation",
                            confidence=0.7,
                            description="Try a broader search with relaxed constraints",
                        )
                    )
            except Exception:
                pass

        if result_count < 5 and ":" in original_query:
            suggestions.append(
                SearchSuggestion(
                    suggestion=original_query.replace(":", " "),
                    suggestion_type="field_expansion",
                    confidence=0.6,
                    description="Search across all fields instead of specific field",
                )
            )

        return suggestions[:3]

    def _extract_query_terms(self, parsed_query: Any) -> list[str]:
        """Extract search terms from parsed query."""
        terms = []

        from .query.parser import (
            BooleanQuery,
            FieldQuery,
            FuzzyQuery,
            PhraseQuery,
            TermQuery,
            WildcardQuery,
        )

        def extract_from_query(q):
            if isinstance(q, TermQuery):
                terms.append(q.term)
            elif isinstance(q, PhraseQuery):
                terms.extend(q.phrase.split())
            elif isinstance(q, FieldQuery):
                extract_from_query(q.query)
            elif isinstance(q, BooleanQuery):
                for subquery in q.queries:
                    extract_from_query(subquery)
            elif isinstance(q, WildcardQuery):
                base_term = q.pattern.replace("*", "").replace("?", "")
                if base_term:
                    terms.append(base_term)
            elif isinstance(q, FuzzyQuery):
                terms.append(q.term)

        extract_from_query(parsed_query)
        return terms

    def _estimate_doc_frequencies(self, terms: list[str]) -> dict[str, int]:
        """Estimate document frequencies for terms."""
        frequencies = {}
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at"}

        if self._index_size < 10:
            for term in terms:
                term_lower = term.lower()
                if term_lower in stop_words:
                    frequencies[term_lower] = max(1, self._index_size - 1)
                else:
                    frequencies[term_lower] = 1
        else:
            for term in terms:
                term_lower = term.lower()
                if term_lower in stop_words:
                    frequencies[term_lower] = max(1, int(self._index_size * 0.5))
                elif len(term_lower) <= 3:
                    frequencies[term_lower] = max(1, int(self._index_size * 0.2))
                else:
                    frequencies[term_lower] = max(1, int(self._index_size * 0.1))
        return frequencies


class SearchEngineBuilder:
    """Builder for constructing SearchEngine instances."""

    def __init__(self):
        self.backend: SearchBackend | None = None
        self.field_config: FieldConfiguration | None = None
        self.enable_highlighting = True
        self.enable_query_expansion = True
        self.synonym_expander = None
        self.spell_checker = None
        self.ranker = None
        self.repository = None

    def with_backend(self, backend: SearchBackend) -> "SearchEngineBuilder":
        """Set the search backend."""
        self.backend = backend
        return self

    def with_field_config(self, config: FieldConfiguration) -> "SearchEngineBuilder":
        """Set the field configuration."""
        self.field_config = config
        return self

    def with_highlighting(self, enabled: bool) -> "SearchEngineBuilder":
        """Enable or disable result highlighting."""
        self.enable_highlighting = enabled
        return self

    def with_query_expansion(self, enabled: bool) -> "SearchEngineBuilder":
        """Enable or disable query expansion."""
        self.enable_query_expansion = enabled
        return self

    def with_synonym_expander(self, synonym_expander) -> "SearchEngineBuilder":
        """Set custom synonym expander."""
        self.synonym_expander = synonym_expander
        self.enable_query_expansion = True  # Ensure expansion is enabled
        return self

    def with_spell_checker(self, spell_checker) -> "SearchEngineBuilder":
        """Set custom spell checker."""
        self.spell_checker = spell_checker
        return self

    def with_ranker(self, ranker) -> "SearchEngineBuilder":
        """Set custom ranking algorithm."""
        self.ranker = ranker
        return self

    def with_repository(self, repository) -> "SearchEngineBuilder":
        """Set entry repository for retrieving full entry data."""
        self.repository = repository
        return self

    def build(self) -> SearchEngine:
        """Build the SearchEngine instance."""
        engine = SearchEngine(
            backend=self.backend,
            field_config=self.field_config,
            enable_highlighting=self.enable_highlighting,
            enable_query_expansion=self.enable_query_expansion,
            ranker=self.ranker,
            repository=self.repository,
        )

        if self.enable_query_expansion and (
            self.synonym_expander or self.spell_checker
        ):
            from .query import QueryExpander

            engine.query_expander = QueryExpander(
                spell_checker=self.spell_checker, synonym_expander=self.synonym_expander
            )

        return engine


def create_default_engine() -> SearchEngine:
    """Create a SearchEngine with default configuration."""
    return SearchEngineBuilder().build()


def create_memory_engine(
    enable_highlighting: bool = True, enable_query_expansion: bool = True
) -> SearchEngine:
    """Create a SearchEngine with in-memory backend."""
    return (
        SearchEngineBuilder()
        .with_backend(MemoryBackend())
        .with_highlighting(enable_highlighting)
        .with_query_expansion(enable_query_expansion)
        .build()
    )


class SearchServiceBuilder:
    """Builder for SearchService with repository integration."""

    def __init__(self):
        """Initialize builder."""
        self._engine_builder = SearchEngineBuilder()
        self._repository = None
        self._event_bus = None
        self._config = {}

    def with_whoosh(self, index_dir: Path):
        """Configure with Whoosh backend."""
        from .backends.whoosh import WhooshBackend

        backend = WhooshBackend(index_dir)
        self._engine_builder = self._engine_builder.with_backend(backend)
        return self

    def with_memory(self):
        """Configure with memory backend."""
        from .backends.memory import MemoryBackend

        backend = MemoryBackend()
        self._engine_builder = self._engine_builder.with_backend(backend)
        return self

    def with_repository(self, repository):
        """Configure with entry repository."""
        self._repository = repository
        return self

    def with_events(self, event_bus):
        """Configure with event bus."""
        self._event_bus = event_bus
        return self

    def with_config(self, config: dict):
        """Configure with search config."""
        self._config.update(config)
        if config.get("expand_queries"):
            self._engine_builder = self._engine_builder.with_query_expansion(True)
        if config.get("enable_highlighting", True):
            self._engine_builder = self._engine_builder.with_highlighting(True)
        return self

    def with_synonyms(self, synonyms: dict):
        """Configure with synonyms."""
        self._config["synonyms"] = synonyms
        return self

    def with_fields(self, fields: dict):
        """Configure with field configuration."""
        self._config["fields"] = fields
        return self

    def build(self) -> "SearchService":
        """Build the SearchService."""
        if "synonyms" in self._config:
            from .indexing.analyzers import SynonymExpander

            synonym_expander = SynonymExpander(self._config["synonyms"])
            self._engine_builder = self._engine_builder.with_synonym_expander(
                synonym_expander
            )

        if "fields" in self._config:
            from .indexing.fields import FieldConfiguration

            field_config = FieldConfiguration()

            for field_name, settings in self._config["fields"].items():
                if "boost" in settings:
                    if field_name in field_config.fields:
                        field_config.fields[field_name].boost = settings["boost"]
                if "type" in settings:
                    from .indexing.fields import FieldDefinition, FieldType

                    field_type = FieldType(settings["type"])
                    if field_name not in field_config.fields:
                        field_config.fields[field_name] = FieldDefinition(
                            name=field_name,
                            field_type=field_type,
                            boost=settings.get("boost", 1.0),
                            indexed=settings.get("indexed", True),
                            stored=settings.get("stored", True),
                            analyzed=settings.get("analyzed", True),
                            analyzer=settings.get("analyzer"),
                        )
                    else:
                        field_config.fields[field_name].field_type = field_type
                if "analyzer" in settings:
                    if field_name in field_config.fields:
                        field_config.fields[field_name].analyzer = settings["analyzer"]

            self._engine_builder = self._engine_builder.with_field_config(field_config)

            if not self._engine_builder.ranker and any(
                field.boost != 1.0 for field in field_config.fields.values()
            ):
                from .ranking import BM25Ranker, FieldWeights

                field_weights = FieldWeights(
                    {
                        field_name: field_def.boost
                        for field_name, field_def in field_config.fields.items()
                    }
                )
                self._engine_builder = self._engine_builder.with_ranker(
                    BM25Ranker(field_weights=field_weights)
                )

        engine = self._engine_builder.build()
        service = SearchService(engine)
        service.backend = engine.backend
        service._repository = self._repository
        service._event_bus = self._event_bus
        service.repository = self._repository
        service.event_bus = self._event_bus
        service.config = self._config.copy()
        return service


class SearchService:
    """High-level search service providing convenience methods."""

    def __init__(
        self,
        engine: SearchEngine | None = None,
        backend: SearchBackend | None = None,
        repository=None,
        event_bus=None,
    ):
        """Initialize search service.

        Args:
            engine: SearchEngine instance (default: create new memory engine)
            backend: Search backend (for compatibility, creates engine if provided)
            repository: Entry repository for result hydration
            event_bus: Event bus for search events
        """
        if engine:
            self.engine = engine
        elif backend:
            # Create engine with provided backend for compatibility
            self.engine = SearchEngine(backend=backend)
        else:
            self.engine = create_memory_engine()

        self._entry_cache: dict[str, BibEntry] = {}
        self._repository = repository
        self._event_bus = event_bus

        # Public properties for tests and builder
        self.repository = repository
        self.event_bus = event_bus
        self.backend = self.engine.backend  # Expose backend for tests
        self.config: dict = {}  # Configuration dict for builder

        # Subscribe to events if event bus is provided
        if self._event_bus:
            self._subscribe_to_events()

    def add_entries(self, entries: list[BibEntry]) -> None:
        """Add entries to search index and cache."""
        for entry in entries:
            self._entry_cache[entry.key] = entry

        self.engine.index_entries(entries)
        self.engine.commit()

    def search_entries(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        include_entries: bool = True,
        **kwargs,
    ) -> SearchResultCollection:
        """Search for entries and optionally hydrate results.

        Args:
            query: Search query
            limit: Maximum results
            offset: Results offset
            include_entries: Whether to include full entry objects in results
            **kwargs: Additional search parameters

        Returns:
            Search results with optional entry objects
        """
        results = self.engine.search(query, limit, offset, **kwargs)

        if include_entries:
            valid_matches = []
            for match in results.matches:
                entry = None

                if self._repository:
                    try:
                        entry = self._repository.find(match.entry_key)
                        if entry:
                            match.entry = entry
                            self._entry_cache[match.entry_key] = entry
                            valid_matches.append(match)
                    except Exception:
                        pass
                elif match.entry_key in self._entry_cache:
                    match.entry = self._entry_cache[match.entry_key]
                    valid_matches.append(match)
                else:
                    valid_matches.append(match)

            results.matches = valid_matches
            results.total = len(valid_matches)

        return results

    def remove_entry(self, entry_key: str) -> bool:
        """Remove entry from index and cache."""
        self._entry_cache.pop(entry_key, None)
        return self.engine.remove_entry(entry_key)

    def clear_all(self) -> None:
        """Clear all entries from index and cache."""
        self._entry_cache.clear()
        self.engine.clear_index()

    def get_entry(self, entry_key: str) -> BibEntry | None:
        """Get cached entry by key."""
        return self._entry_cache.get(entry_key)

    def get_cached_entry_count(self) -> int:
        """Get number of cached entries."""
        return len(self._entry_cache)

    def get_search_statistics(self) -> dict[str, Any]:
        """Get comprehensive search statistics."""
        engine_stats = self.engine.get_statistics()

        if "backend" in engine_stats and "total_documents" in engine_stats["backend"]:
            engine_stats["total_documents"] = engine_stats["backend"]["total_documents"]

        engine_stats["service"] = {
            "cached_entries": len(self._entry_cache),
        }
        return engine_stats

    def index_all(self, batch_size: int | None = None) -> int:
        """Index all entries from repository."""
        if not self._repository:
            return 0

        entries = self._repository.find_all()

        if batch_size and len(entries) > batch_size:
            total_indexed = 0
            for i in range(0, len(entries), batch_size):
                batch = entries[i : i + batch_size]
                self.add_entries(batch)
                total_indexed += len(batch)

                if self._event_bus:
                    from datetime import datetime

                    from ..storage.events import Event, EventType

                    progress_event = Event(
                        type=EventType.INDEX_PROGRESS,
                        timestamp=datetime.now(),
                        data={"indexed": total_indexed, "total": len(entries)},
                    )
                    self._event_bus.publish(progress_event)
            return total_indexed
        else:
            self.add_entries(entries)
            total_indexed = len(entries)

            if self._event_bus:
                from datetime import datetime

                from ..storage.events import Event, EventType

                progress_event = Event(
                    type=EventType.INDEX_PROGRESS,
                    timestamp=datetime.now(),
                    data={"indexed": total_indexed, "total": len(entries)},
                )
                self._event_bus.publish(progress_event)

            return total_indexed

    def index_entry(self, entry: BibEntry) -> None:
        """Index a single entry."""
        self.add_entries([entry])

    def search(self, query: str, **kwargs) -> SearchResultCollection:
        """Search with simple interface."""
        return self.search_entries(query, **kwargs)

    def delete_entry(self, entry_key: str) -> bool:
        """Delete entry (alias for remove_entry)."""
        return self.remove_entry(entry_key)

    def clear_index(self) -> None:
        """Clear index (alias for clear_all)."""
        self.clear_all()

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics (alias for get_search_statistics)."""
        return self.get_search_statistics()

    def _subscribe_to_events(self) -> None:
        """Subscribe to relevant events for automatic indexing."""
        from ..storage.events import EventType

        if self._event_bus and hasattr(self._event_bus, "subscribe"):
            self._event_bus.subscribe(
                EventType.ENTRY_CREATED, self._handle_entry_created
            )
            self._event_bus.subscribe(
                EventType.ENTRY_UPDATED, self._handle_entry_updated
            )
            self._event_bus.subscribe(
                EventType.ENTRY_DELETED, self._handle_entry_deleted
            )
            self._event_bus.subscribe(
                EventType.STORAGE_CLEARED, self._handle_storage_cleared
            )

    def _handle_entry_created(self, event) -> None:
        """Handle entry created event."""
        if "entry" in event.data:
            entry = event.data["entry"]
            self.index_entry(entry)

    def _handle_entry_updated(self, event) -> None:
        """Handle entry updated event."""
        if "entry_key" in event.data:
            entry_key = event.data["entry_key"]
            self.delete_entry(entry_key)
            if "new_entry" in event.data:
                self.index_entry(event.data["new_entry"])

    def _handle_entry_deleted(self, event) -> None:
        """Handle entry deleted event."""
        if "entry_key" in event.data:
            entry_key = event.data["entry_key"]
            self.delete_entry(entry_key)

    def _handle_storage_cleared(self, event) -> None:
        """Handle storage cleared event."""
        self.clear_index()
