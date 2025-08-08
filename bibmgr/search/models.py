"""Data models for search functionality using msgspec for performance."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import msgspec


class EntryType(str, Enum):
    """Bibliography entry types."""

    ARTICLE = "article"
    BOOK = "book"
    BOOKLET = "booklet"
    CONFERENCE = "conference"
    INBOOK = "inbook"
    INCOLLECTION = "incollection"
    INPROCEEDINGS = "inproceedings"
    MANUAL = "manual"
    MASTERSTHESIS = "mastersthesis"
    MISC = "misc"
    PHDTHESIS = "phdthesis"
    PROCEEDINGS = "proceedings"
    TECHREPORT = "techreport"
    UNPUBLISHED = "unpublished"


class Entry(msgspec.Struct, frozen=True, kw_only=True):
    """A bibliography entry optimized for search.

    Uses msgspec.Struct for fastest possible serialization/deserialization.
    All fields are immutable (frozen=True) to ensure data integrity.
    """

    # Required fields
    key: str
    type: EntryType
    title: str

    # Optional fields with defaults
    authors: list[str] = msgspec.field(default_factory=list)
    year: int | None = None
    venue: str | None = None  # journal, booktitle, etc.
    abstract: str | None = None
    keywords: list[str] = msgspec.field(default_factory=list)
    doi: str | None = None
    url: str | None = None
    pdf_path: Path | None = None

    @property
    def text(self) -> str:
        """Generate searchable text from all fields."""
        parts = [
            self.title,
            " ".join(self.authors),
            self.venue or "",
            self.abstract or "",
            " ".join(self.keywords),
            str(self.year) if self.year else "",
        ]
        return " ".join(filter(None, parts))


@dataclass
class SearchHit:
    """A single search result with scoring and highlights."""

    entry: Entry
    score: float
    rank: int

    # Relevance scoring components
    text_score: float = 0.0
    freshness_score: float = 0.0
    field_boosts: dict[str, float] = field(default_factory=dict)

    # Highlighting for matched terms
    highlights: dict[str, list[str]] = field(default_factory=dict)

    # Optional explanation of scoring
    explanation: str | None = None

    @property
    def relevance_breakdown(self) -> dict[str, float]:
        """Get detailed scoring breakdown for transparency."""
        return {
            "text_relevance": self.text_score,
            "freshness": self.freshness_score,
            **self.field_boosts,
            "total": self.score,
        }


@dataclass
class SearchResult:
    """Complete search results with metadata and facets."""

    query: str
    hits: list[SearchHit]
    total_found: int
    search_time_ms: float

    # Facets for filtering and drill-down
    facets: dict[str, dict[str, int]] = field(default_factory=dict)

    # Search enhancements
    suggestions: list[str] = field(default_factory=list)
    spell_corrections: list[tuple[str, str]] = field(default_factory=list)

    # Query understanding metadata
    parsed_query: dict[str, Any] = field(default_factory=dict)
    expanded_terms: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """Check if no results were found."""
        return self.total_found == 0

    @property
    def top_hit(self) -> SearchHit | None:
        """Get the highest scoring result."""
        return self.hits[0] if self.hits else None

    def get_facet_values(self, field: str) -> list[tuple[str, int]]:
        """Get facet values sorted by count for a specific field."""
        facet = self.facets.get(field, {})
        return sorted(facet.items(), key=lambda x: x[1], reverse=True)
