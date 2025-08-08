"""Search engine implementation using Whoosh for full-text indexing.

This module provides the core search functionality with advanced features
like faceted search, spell correction, and result caching.
"""

from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from diskcache import Cache
from whoosh import index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import Schema, TEXT, ID, NUMERIC
from whoosh.qparser import MultifieldParser
from whoosh.qparser.plugins import FuzzyTermPlugin

from .history import SearchHistory
from .models import Entry, EntryType, SearchHit, SearchResult
from .query import QueryParser as CustomQueryParser, QueryField


class SearchEngine:
    """Full-text search engine with advanced features."""

    def __init__(
        self,
        index_dir: Path | None = None,
        cache_dir: Path | None = None,
    ):
        """Initialize search engine with index and cache.

        Args:
            index_dir: Directory for search index (default: ~/.cache/bibmgr/index)
            cache_dir: Directory for result cache (default: ~/.cache/bibmgr/cache)
        """
        # Set up directories
        if index_dir is None:
            index_dir = Path.home() / ".cache" / "bibmgr" / "index"
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "bibmgr" / "cache"

        self.index_dir = index_dir
        self.index_dir.mkdir(parents=True, exist_ok=True)

        # Initialize schema with stemming analyzer for better matching
        analyzer = StemmingAnalyzer()
        self.schema = Schema(
            key=ID(unique=True, stored=True),
            type=ID(stored=True),
            title=TEXT(stored=True, field_boost=2.0, analyzer=analyzer),
            authors=TEXT(stored=True, field_boost=1.5, analyzer=analyzer),
            year=NUMERIC(stored=True),
            venue=TEXT(stored=True, field_boost=1.2, analyzer=analyzer),
            abstract=TEXT(stored=True, analyzer=analyzer),
            keywords=TEXT(stored=True, field_boost=1.5, analyzer=analyzer),
            doi=ID(stored=True),
            url=ID(stored=True),
            content=TEXT(analyzer=analyzer),  # Combined searchable content
        )

        # Create or open index
        if index.exists_in(str(self.index_dir)):
            self.ix = index.open_dir(str(self.index_dir))
        else:
            self.ix = index.create_in(str(self.index_dir), self.schema)

        # Initialize query parser
        self.query_parser = CustomQueryParser()

        # Initialize Whoosh query parser for actual searching
        self.whoosh_parser = MultifieldParser(
            ["title", "authors", "abstract", "keywords", "content"], schema=self.schema
        )
        self.whoosh_parser.add_plugin(FuzzyTermPlugin())

        # Initialize components
        self.history = SearchHistory()
        self.locator = FileLocator()  # Will be implemented with locate.py

        # Initialize cache with 1GB size limit
        self.cache = Cache(str(cache_dir), size_limit=1_000_000_000)

        # Statistics
        self.stats = {
            "total_searches": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_search_time_ms": 0.0,
            "avg_search_time_ms": 0.0,
        }

    def index_entries(self, entries: list[Entry]) -> None:
        """Index or update bibliography entries.

        Args:
            entries: List of entries to index
        """
        writer = self.ix.writer()

        try:
            for entry in entries:
                # Prepare document fields
                doc = {
                    "key": entry.key,
                    "type": entry.type.value,
                    "title": entry.title,
                    "authors": " ".join(entry.authors),
                    "year": entry.year,
                    "venue": entry.venue,
                    "abstract": entry.abstract,
                    "keywords": " ".join(entry.keywords) if entry.keywords else None,
                    "doi": entry.doi,
                    "url": entry.url,
                    "content": entry.text,  # Combined searchable text
                }

                # Remove None values
                doc = {k: v for k, v in doc.items() if v is not None}

                # Update or add document
                writer.update_document(**doc)

            writer.commit()

            # Clear cache after indexing
            self.cache.clear()

        except Exception:
            writer.cancel()
            raise

    def search(
        self,
        query_string: str,
        limit: int = 20,
        page: int = 1,
    ) -> SearchResult:
        """Search the index with advanced features.

        Args:
            query_string: Search query
            limit: Results per page
            page: Page number (1-indexed)

        Returns:
            SearchResult with hits, facets, and metadata
        """
        start_time = time.time()

        # Check cache
        cache_key = f"{query_string}:{limit}:{page}"
        if cache_key in self.cache:
            self.stats["cache_hits"] += 1
            cached_result = self.cache[cache_key]
            # Update search time
            if isinstance(cached_result, SearchResult):
                cached_result.search_time_ms = (time.time() - start_time) * 1000
                return cached_result

        self.stats["cache_misses"] += 1

        # Parse query with custom parser for understanding
        parsed = self.query_parser.parse(query_string)

        # Check for negated terms that we need to filter
        negated_terms = [t.text.lower() for t in parsed.terms if t.is_negated]

        # Build Whoosh query
        whoosh_query = self._build_whoosh_query(parsed)

        # Search
        with self.ix.searcher() as searcher:
            # Calculate pagination
            offset = (page - 1) * limit

            # Execute search with proper pagination
            results = searcher.search_page(
                whoosh_query,
                pagenum=page,
                pagelen=limit,
                terms=True,  # Enable term highlighting
            )

            # Get total count of matches (before filtering)
            total_matches = len(results)
            if hasattr(results, "total"):
                total_matches = results.total

            # Build hits
            hits = []
            for rank, result in enumerate(results, start=offset + 1):
                # Create Entry from stored fields
                entry = Entry(
                    key=result["key"],
                    type=EntryType(result["type"]),
                    title=result["title"],
                    authors=result.get("authors", "").split()
                    if result.get("authors")
                    else [],
                    year=result.get("year"),
                    venue=result.get("venue"),
                    abstract=result.get("abstract"),
                    keywords=result.get("keywords", "").split()
                    if result.get("keywords")
                    else [],
                    doi=result.get("doi"),
                    url=result.get("url"),
                )

                # Calculate freshness score
                freshness_score = 0.0
                if entry.year:
                    years_old = 2024 - entry.year
                    freshness_score = max(0, 1.0 - (years_old / 50.0))

                # Create hit with combined score
                combined_score = result.score + (
                    freshness_score * 0.5
                )  # Apply freshness boost
                hit = SearchHit(
                    entry=entry,
                    score=combined_score,
                    rank=rank,
                    text_score=result.score,
                    freshness_score=freshness_score,
                    field_boosts={},
                    highlights=self._extract_highlights(result),
                )

                # Filter out results containing negated terms
                skip = False
                if negated_terms:
                    entry_text = entry.text.lower()
                    for neg_term in negated_terms:
                        if neg_term in entry_text:
                            skip = True
                            break

                if not skip:
                    hits.append(hit)

            # Re-sort hits by combined score
            hits.sort(key=lambda h: h.score, reverse=True)

            # Rebuild hits with correct ranks
            sorted_hits = []
            for i, hit in enumerate(hits, start=1):
                sorted_hit = SearchHit(
                    entry=hit.entry,
                    score=hit.score,
                    rank=i,
                    text_score=hit.text_score,
                    freshness_score=hit.freshness_score,
                    field_boosts=hit.field_boosts,
                    highlights=hit.highlights,
                )
                sorted_hits.append(sorted_hit)
            hits = sorted_hits

            # Build facets
            facets = self._build_facets(searcher, whoosh_query)

            # Get suggestions
            suggestions = self._get_suggestions(searcher, query_string)

            # Check spelling
            spell_corrections = self._check_spelling(searcher, query_string)

            # For negated queries, we need to adjust total_found
            if negated_terms:
                # The total is the number of filtered results
                # This is an approximation since we only filtered one page
                total_found = len(hits)
            else:
                total_found = total_matches

            # Create result
            result = SearchResult(
                query=query_string,
                hits=hits,
                total_found=total_found,
                search_time_ms=(time.time() - start_time) * 1000,
                facets=facets,
                suggestions=suggestions,
                spell_corrections=spell_corrections,
                parsed_query={"terms": [str(t) for t in parsed.terms]},
                expanded_terms=[],
            )

            # Cache result
            self.cache[cache_key] = result

            # Update statistics
            self.stats["total_searches"] += 1
            self.stats["total_search_time_ms"] += result.search_time_ms
            self.stats["avg_search_time_ms"] = (
                self.stats["total_search_time_ms"] / self.stats["total_searches"]
            )

            # Add to history
            self.history.add_search(
                query_string, result.total_found, result.search_time_ms
            )

            return result

    def _build_whoosh_query(self, parsed):
        """Build Whoosh query from parsed query."""
        # Check if we have negated terms to handle specially
        has_negated = any(t.is_negated for t in parsed.terms)

        # For simple queries with boolean operators (but no negation)
        original_upper = parsed.original.upper()
        if (
            not has_negated
            and any(op in original_upper for op in [" OR ", " AND "])
            and not parsed.has_field_queries()
        ):
            return self.whoosh_parser.parse(parsed.original)

        # For phrase queries (but no negation)
        if (
            not has_negated
            and parsed.original.startswith('"')
            and parsed.original.endswith('"')
        ):
            return self.whoosh_parser.parse(parsed.original)

        # For field-specific queries or queries with negation
        if parsed.has_field_queries() or has_negated:
            query_parts = []

            for term in parsed.terms:
                # Skip negated terms - we filter them after search
                if term.is_negated:
                    continue

                # Map field names to index fields
                if term.field != QueryField.ALL:
                    field_map = {
                        QueryField.AUTHOR: "authors",
                        QueryField.TITLE: "title",
                        QueryField.YEAR: "year",
                        QueryField.VENUE: "venue",
                        QueryField.KEYWORDS: "keywords",
                        QueryField.ABSTRACT: "abstract",
                        QueryField.TYPE: "type",
                    }
                    field_name = field_map.get(term.field, "content")

                    # Handle different query types
                    if term.is_phrase:
                        query_parts.append(f'{field_name}:"{term.text}"')
                    elif ".." in term.text and term.field == QueryField.YEAR:
                        # Year range
                        start, end = term.text.split("..")
                        query_parts.append(f"{field_name}:[{start} TO {end}]")
                    else:
                        query_parts.append(f"{field_name}:{term.text}")
                else:
                    # General search term
                    if term.is_phrase:
                        query_parts.append(f'"{term.text}"')
                    else:
                        query_parts.append(term.text)

            query_str = " ".join(query_parts) if query_parts else "*"
            return self.whoosh_parser.parse(query_str)

        # Default: use original query
        return self.whoosh_parser.parse(parsed.original)

    def _extract_highlights(self, result) -> dict[str, list[str]]:
        """Extract highlighted snippets from search result."""
        highlights = {}

        # Get highlighted fields
        if hasattr(result, "highlights"):
            for field in ["title", "abstract", "authors"]:
                if field in result:
                    highlight = result.highlights(field)
                    if highlight:
                        highlights[field] = [highlight]

        return highlights

    def _build_facets(self, searcher, query) -> dict[str, dict[str, int]]:
        """Build facets for search results."""
        facets = defaultdict(lambda: defaultdict(int))

        # Search without limit to get all matching docs
        results = searcher.search(query, limit=None)

        for result in results:
            # Type facet
            if "type" in result:
                facets["type"][result["type"]] += 1

            # Year facet
            if "year" in result and result["year"]:
                facets["year"][str(result["year"])] += 1

            # Venue facet (top venues only)
            if "venue" in result and result["venue"]:
                facets["venue"][result["venue"]] += 1

        # Convert to regular dict
        return {k: dict(v) for k, v in facets.items()}

    def _get_suggestions(self, searcher, query: str) -> list[str]:
        """Get query suggestions."""
        suggestions = []

        # Get terms from index
        reader = searcher.reader()

        # Find related terms
        for fieldname in ["title", "abstract", "keywords"]:
            try:
                # Get top terms from field
                terms = list(reader.field_terms(fieldname))[:5]
                suggestions.extend(terms)
            except (AttributeError, KeyError):
                # Field may not exist or reader doesn't support it
                continue

        return list(set(suggestions))[:10]

    def _check_spelling(self, searcher, query: str) -> list[tuple[str, str]]:
        """Check spelling and suggest corrections."""
        corrections = []

        # Simple spell checking using Whoosh corrector
        corrector = searcher.corrector("content")

        for word in query.split():
            if len(word) > 2:  # Skip short words
                suggestions = corrector.suggest(word, limit=1)
                if suggestions and suggestions[0] != word:
                    corrections.append((word, suggestions[0]))

        return corrections

    def clear_index(self) -> None:
        """Clear all entries from the index."""
        # Create new empty index (this overwrites existing)
        self.ix = index.create_in(str(self.index_dir), self.schema)

        # Clear cache
        self.cache.clear()

        # Reset stats
        self.stats["total_searches"] = 0
        self.stats["cache_hits"] = 0
        self.stats["cache_misses"] = 0

    def optimize_index(self) -> None:
        """Optimize the search index for better performance."""
        writer = self.ix.writer()
        writer.commit(optimize=True)

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive search engine statistics."""
        cache_total = self.stats["cache_hits"] + self.stats["cache_misses"]
        cache_hit_rate = (
            self.stats["cache_hits"] / cache_total if cache_total > 0 else 0
        )

        return {
            "total_searches": self.stats["total_searches"],
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "cache_hit_rate": cache_hit_rate,
            "avg_search_time_ms": self.stats["avg_search_time_ms"],
            "index_size": self.ix.doc_count(),
            "cache_size": 0,  # diskcache.Cache doesn't provide direct len()
        }


class FileLocator:
    """Placeholder for file location functionality.

    Will be implemented in locate.py module.
    """

    def __init__(self):
        """Initialize file locator."""
        pass
