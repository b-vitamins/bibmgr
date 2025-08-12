"""Search result types and formatting."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..core.models import Entry as BibEntry
from .backends.base import SearchMatch


class SortOrder(Enum):
    """Sort order options for search results."""

    RELEVANCE = "relevance"
    DATE_DESC = "date_desc"
    DATE_ASC = "date_asc"
    TITLE_ASC = "title_asc"
    TITLE_DESC = "title_desc"
    AUTHOR_ASC = "author_asc"
    AUTHOR_DESC = "author_desc"


@dataclass
class FacetValue:
    """Individual facet value with count."""

    value: str
    count: int
    selected: bool = False

    def __str__(self) -> str:
        return f"{self.value} ({self.count})"


@dataclass
class Facet:
    """Facet information for a field."""

    field: str
    display_name: str
    values: list[FacetValue]
    facet_type: str = "terms"

    def get_value_count(self, value: str) -> int:
        """Get count for a specific facet value."""
        for facet_value in self.values:
            if facet_value.value == value:
                return facet_value.count
        return 0

    def get_top_values(self, limit: int = 10) -> list[FacetValue]:
        """Get top N facet values by count."""
        sorted_values = sorted(self.values, key=lambda x: x.count, reverse=True)
        return sorted_values[:limit]


@dataclass
class SearchSuggestion:
    """Search suggestion for query improvement."""

    suggestion: str
    suggestion_type: str
    confidence: float
    description: str | None = None


@dataclass
class SearchStatistics:
    """Statistics about the search execution."""

    total_results: int
    search_time_ms: int
    query_time_ms: int | None = None
    fetch_time_ms: int | None = None
    backend_name: str = "unknown"
    index_size: int | None = None

    @property
    def search_time_seconds(self) -> float:
        """Get search time in seconds."""
        return self.search_time_ms / 1000.0


@dataclass
class SearchResultCollection:
    """Collection of search results with metadata."""

    matches: list[SearchMatch]
    total: int
    offset: int = 0
    limit: int = 20
    facets: list[Facet] = field(default_factory=list)
    suggestions: list[SearchSuggestion] = field(default_factory=list)
    statistics: SearchStatistics | None = None
    query: str | None = None
    parsed_query: Any | None = None
    sort_order: SortOrder = SortOrder.RELEVANCE

    def __post_init__(self):
        """Validate result collection."""
        if self.offset < 0:
            self.offset = 0
        if self.limit < 1:
            self.limit = 1
        if self.total < len(self.matches):
            self.total = len(self.matches)

    @property
    def hits(self) -> list[SearchMatch]:
        """Alias for matches (for compatibility)."""
        return self.matches

    @property
    def has_results(self) -> bool:
        """Check if there are any results."""
        return len(self.matches) > 0

    @property
    def current_page(self) -> int:
        """Get current page number (1-based)."""
        return (self.offset // self.limit) + 1

    @property
    def total_pages(self) -> int:
        """Get total number of pages."""
        if self.limit == 0:
            return 1
        return (self.total + self.limit - 1) // self.limit

    @property
    def has_more(self) -> bool:
        """Check if there are more results available."""
        return self.offset + self.limit < self.total

    @property
    def has_previous(self) -> bool:
        """Check if there are previous results."""
        return self.offset > 0

    def get_facet(self, field: str) -> Facet | None:
        """Get facet by field name."""
        for facet in self.facets:
            if facet.field == field:
                return facet
        return None

    def get_facet_values(self, field: str) -> list[FacetValue]:
        """Get facet values for a field."""
        facet = self.get_facet(field)
        return facet.values if facet else []

    def get_top_facet_values(self, field: str, limit: int = 5) -> list[FacetValue]:
        """Get top N facet values for a field."""
        facet = self.get_facet(field)
        return facet.get_top_values(limit) if facet else []

    def get_results_for_page(self, page: int) -> list[SearchMatch]:
        """Get results for a specific page (1-based)."""
        if page < 1:
            page = 1

        start_idx = (page - 1) * self.limit
        end_idx = start_idx + self.limit

        # Adjust for current offset
        current_start = start_idx - self.offset
        current_end = end_idx - self.offset

        if current_start < 0:
            current_start = 0
        if current_end > len(self.matches):
            current_end = len(self.matches)

        if current_start >= len(self.matches):
            return []

        return self.matches[current_start:current_end]

    def get_score_range(self) -> tuple[float, float]:
        """Get min and max scores in results."""
        if not self.matches:
            return (0.0, 0.0)

        scores = [match.score for match in self.matches]
        return (min(scores), max(scores))

    def filter_by_score(self, min_score: float) -> "SearchResultCollection":
        """Filter results by minimum score."""
        filtered_matches = [match for match in self.matches if match.score >= min_score]

        return SearchResultCollection(
            matches=filtered_matches,
            total=len(filtered_matches),
            offset=0,
            limit=self.limit,
            facets=self.facets,
            suggestions=self.suggestions,
            statistics=self.statistics,
            query=self.query,
            parsed_query=self.parsed_query,
            sort_order=self.sort_order,
        )

    def sort_by(self, sort_order: SortOrder) -> "SearchResultCollection":
        """Sort results by specified order."""
        sorted_matches = self.matches.copy()

        if sort_order == SortOrder.RELEVANCE:
            sorted_matches.sort(key=lambda x: x.score, reverse=True)
        elif sort_order == SortOrder.DATE_DESC:
            sorted_matches.sort(key=lambda x: self._get_sort_key_date(x), reverse=True)
        elif sort_order == SortOrder.DATE_ASC:
            sorted_matches.sort(key=lambda x: self._get_sort_key_date(x))
        elif sort_order == SortOrder.TITLE_ASC:
            sorted_matches.sort(key=lambda x: self._get_sort_key_title(x))
        elif sort_order == SortOrder.TITLE_DESC:
            sorted_matches.sort(key=lambda x: self._get_sort_key_title(x), reverse=True)
        elif sort_order == SortOrder.AUTHOR_ASC:
            sorted_matches.sort(key=lambda x: self._get_sort_key_author(x))
        elif sort_order == SortOrder.AUTHOR_DESC:
            sorted_matches.sort(
                key=lambda x: self._get_sort_key_author(x), reverse=True
            )

        return SearchResultCollection(
            matches=sorted_matches,
            total=self.total,
            offset=self.offset,
            limit=self.limit,
            facets=self.facets,
            suggestions=self.suggestions,
            statistics=self.statistics,
            query=self.query,
            parsed_query=self.parsed_query,
            sort_order=sort_order,
        )

    def _get_sort_key_date(self, match: SearchMatch) -> int:
        """Get sort key for date sorting."""
        if match.entry and hasattr(match.entry, "year") and match.entry.year:
            try:
                return int(match.entry.year)
            except (ValueError, TypeError):
                pass
        return 9999

    def _get_sort_key_title(self, match: SearchMatch) -> str:
        """Get sort key for title sorting."""
        if match.entry and hasattr(match.entry, "title") and match.entry.title:
            title = str(match.entry.title).lower()
            for article in ["the ", "a ", "an "]:
                if title.startswith(article):
                    title = title[len(article) :]
                    break
            return title
        return ""

    def _get_sort_key_author(self, match: SearchMatch) -> str:
        """Get sort key for author sorting."""
        if match.entry and hasattr(match.entry, "author") and match.entry.author:
            author = str(match.entry.author).lower()
            if "," in author:
                return author.split(",")[0].strip()
            else:
                words = author.split()
                if words:
                    last_word = words[-1]
                    return f"{last_word}|{author}"
                return author
        return ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "matches": [
                {
                    "entry_key": match.entry_key,
                    "score": match.score,
                    "entry": match.entry.to_dict() if match.entry else None,
                    "highlights": match.highlights,
                    "explanation": match.explanation,
                }
                for match in self.matches
            ],
            "total": self.total,
            "offset": self.offset,
            "limit": self.limit,
            "current_page": self.current_page,
            "total_pages": self.total_pages,
            "has_more": self.has_more,
            "has_previous": self.has_previous,
            "facets": [
                {
                    "field": facet.field,
                    "display_name": facet.display_name,
                    "values": [
                        {"value": fv.value, "count": fv.count, "selected": fv.selected}
                        for fv in facet.values
                    ],
                }
                for facet in self.facets
            ],
            "suggestions": [
                {
                    "suggestion": sug.suggestion,
                    "type": sug.suggestion_type,
                    "confidence": sug.confidence,
                    "description": sug.description,
                }
                for sug in self.suggestions
            ],
            "statistics": {
                "total_results": self.statistics.total_results,
                "search_time_ms": self.statistics.search_time_ms,
                "search_time_seconds": self.statistics.search_time_seconds,
                "backend_name": self.statistics.backend_name,
                "index_size": self.statistics.index_size,
            }
            if self.statistics
            else None,
            "query": self.query,
            "sort_order": self.sort_order.value,
        }


@dataclass
class ResultsBuilder:
    """Builder for constructing SearchResultCollection objects."""

    matches: list[SearchMatch] = field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 20
    facets: list[Facet] = field(default_factory=list)
    suggestions: list[SearchSuggestion] = field(default_factory=list)
    query: str | None = None
    parsed_query: Any | None = None
    sort_order: SortOrder = SortOrder.RELEVANCE

    # Statistics
    search_time_ms: int = 0
    backend_name: str = "unknown"
    index_size: int | None = None

    def add_match(
        self,
        entry_key: str,
        score: float,
        entry: BibEntry | None = None,
        highlights: dict[str, list[str]] | None = None,
        explanation: str | None = None,
    ) -> "ResultsBuilder":
        """Add a search match."""
        match = SearchMatch(
            entry_key=entry_key,
            score=score,
            entry=entry,
            highlights=highlights,
            explanation=explanation,
        )
        self.matches.append(match)
        return self

    def add_facet(
        self,
        field: str,
        display_name: str,
        values: list[tuple[str, int]],
        facet_type: str = "terms",
    ) -> "ResultsBuilder":
        """Add a facet with values."""
        facet_values = [FacetValue(value, count) for value, count in values]
        facet = Facet(field, display_name, facet_values, facet_type)
        self.facets.append(facet)
        return self

    def add_suggestion(
        self,
        suggestion: str,
        suggestion_type: str,
        confidence: float,
        description: str | None = None,
    ) -> "ResultsBuilder":
        """Add a search suggestion."""
        sug = SearchSuggestion(suggestion, suggestion_type, confidence, description)
        self.suggestions.append(sug)
        return self

    def set_pagination(self, offset: int, limit: int, total: int) -> "ResultsBuilder":
        """Set pagination parameters."""
        self.offset = offset
        self.limit = limit
        self.total = total
        return self

    def set_query_info(
        self, query: str, parsed_query: Any | None = None
    ) -> "ResultsBuilder":
        """Set query information."""
        self.query = query
        self.parsed_query = parsed_query
        return self

    def set_timing(self, search_time_ms: int) -> "ResultsBuilder":
        """Set search timing information."""
        self.search_time_ms = search_time_ms
        return self

    def set_backend_info(
        self, backend_name: str, index_size: int | None = None
    ) -> "ResultsBuilder":
        """Set backend information."""
        self.backend_name = backend_name
        self.index_size = index_size
        return self

    def build(self) -> SearchResultCollection:
        """Build the final SearchResultCollection."""
        if self.total < len(self.matches):
            self.total = len(self.matches)

        statistics = SearchStatistics(
            total_results=self.total,
            search_time_ms=self.search_time_ms,
            backend_name=self.backend_name,
            index_size=self.index_size,
        )

        return SearchResultCollection(
            matches=self.matches,
            total=self.total,
            offset=self.offset,
            limit=self.limit,
            facets=self.facets,
            suggestions=self.suggestions,
            statistics=statistics,
            query=self.query,
            parsed_query=self.parsed_query,
            sort_order=self.sort_order,
        )


def create_empty_results(
    query: str | None = None, limit: int = 20, backend_name: str = "unknown"
) -> SearchResultCollection:
    """Create empty search results."""
    return (
        ResultsBuilder()
        .set_pagination(0, limit, 0)
        .set_query_info(query or "")
        .set_backend_info(backend_name)
        .build()
    )


def merge_result_collections(
    collections: list[SearchResultCollection], sort_by_relevance: bool = True
) -> SearchResultCollection:
    """Merge multiple result collections into one.

    Args:
        collections: List of result collections to merge
        sort_by_relevance: Whether to sort merged results by relevance

    Returns:
        Merged result collection
    """
    if not collections:
        return create_empty_results()

    if len(collections) == 1:
        return collections[0]

    all_matches = []
    for collection in collections:
        all_matches.extend(collection.matches)

    seen_keys = set()
    unique_matches = []
    for match in all_matches:
        if match.entry_key not in seen_keys:
            seen_keys.add(match.entry_key)
            unique_matches.append(match)

    if sort_by_relevance:
        unique_matches.sort(key=lambda x: x.score, reverse=True)

    merged_facets = {}
    for collection in collections:
        for facet in collection.facets:
            if facet.field not in merged_facets:
                merged_facets[facet.field] = {
                    "display_name": facet.display_name,
                    "type": facet.facet_type,
                    "values": {},
                }

            for facet_value in facet.values:
                if facet_value.value in merged_facets[facet.field]["values"]:
                    merged_facets[facet.field]["values"][facet_value.value] += (
                        facet_value.count
                    )
                else:
                    merged_facets[facet.field]["values"][facet_value.value] = (
                        facet_value.count
                    )

    final_facets = []
    for field_name, facet_data in merged_facets.items():
        values = [
            FacetValue(value, count) for value, count in facet_data["values"].items()
        ]
        values.sort(key=lambda x: x.count, reverse=True)
        final_facets.append(
            Facet(field_name, facet_data["display_name"], values, facet_data["type"])
        )

    base_collection = collections[0]

    return SearchResultCollection(
        matches=unique_matches,
        total=len(unique_matches),
        offset=0,
        limit=base_collection.limit,
        facets=final_facets,
        suggestions=base_collection.suggestions,
        statistics=base_collection.statistics,
        query=base_collection.query,
        parsed_query=base_collection.parsed_query,
        sort_order=SortOrder.RELEVANCE
        if sort_by_relevance
        else base_collection.sort_order,
    )
