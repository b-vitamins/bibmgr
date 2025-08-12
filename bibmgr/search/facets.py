"""Faceted search support for bibliography entries.

This module provides faceting functionality to enable users to filter and
navigate search results by various dimensions like entry type, year,
keywords, authors, etc.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import datetime
from enum import Enum
from typing import Any

from ..core.models import Entry as BibEntry
from .backends.base import SearchMatch
from .results import FacetValue


class FacetType(Enum):
    """Types of facets supported."""

    TERMS = "terms"  # Discrete terms (keywords, authors, etc.)
    RANGE = "range"  # Numeric ranges (year ranges)
    DATE_HISTOGRAM = "date_histogram"  # Date buckets


@dataclass
class FacetConfiguration:
    """Configuration for faceted search."""

    def __init__(self, custom_config: dict[str, Any] | None = None):
        """Initialize facet configuration.

        Args:
            custom_config: Custom facet configuration to override defaults
        """
        # Default facet configuration
        self.default_config = {
            "entry_type": {"type": "terms", "size": 10},
            "year": {
                "type": "range",
                "ranges": [
                    {"to": 2000, "label": "Before 2000"},
                    {"from": 2000, "to": 2010, "label": "2000-2009"},
                    {"from": 2010, "to": 2020, "label": "2010-2019"},
                    {"from": 2020, "label": "2020+"},
                ],
            },
            "keywords": {"type": "terms", "size": 20, "min_count": 1},
            "author": {"type": "terms", "size": 15},
            "journal": {"type": "terms", "size": 10},
            "publisher": {"type": "terms", "size": 10},
        }

        # Apply custom configuration
        self.config = self.default_config.copy()
        if custom_config:
            self.config.update(custom_config)

    def get_facet_fields(self) -> list[str]:
        """Get list of fields configured for faceting."""
        return list(self.config.keys())

    def get_facet_type(self, field: str) -> FacetType:
        """Get facet type for a field."""
        field_config = self.config.get(field, {})
        type_str = field_config.get("type", "terms")
        return FacetType(type_str)

    def get_field_settings(self, field: str) -> dict[str, Any]:
        """Get all settings for a field."""
        return self.config.get(field, {})


class FacetExtractor:
    """Extracts facet values from entries."""

    def extract_field_values(
        self, entries: list[BibEntry], field_name: str
    ) -> list[Any]:
        """Extract values for a field from entries.

        Args:
            entries: List of bibliography entries
            field_name: Field to extract values from

        Returns:
            List of values (may contain duplicates for counting)
        """
        values = []

        for entry in entries:
            # Handle special field mappings
            actual_field = field_name
            if field_name == "entry_type":
                actual_field = "type"

            if hasattr(entry, actual_field):
                value = getattr(entry, actual_field)

                if value is None:
                    continue

                # Handle special fields
                if field_name == "entry_type":
                    # Convert entry type enum to string
                    values.append(
                        value.value if hasattr(value, "value") else str(value).lower()
                    )
                elif field_name == "keywords":
                    # Keywords are tuples/lists - add each keyword separately
                    if isinstance(value, list | tuple):
                        values.extend(value)
                    elif isinstance(value, str):
                        # Split comma-separated keywords
                        values.extend(k.strip() for k in value.split(",") if k.strip())
                elif field_name == "author":
                    # Split authors on "and"
                    if isinstance(value, str):
                        authors = value.split(" and ")
                        values.extend(a.strip() for a in authors if a.strip())
                else:
                    # Regular field
                    values.append(value)

        return values


class FacetAggregator:
    """Aggregates facet values and counts."""

    def __init__(self, config: FacetConfiguration | None = None):
        """Initialize aggregator with configuration."""
        self.config = config or FacetConfiguration()

    def aggregate_facet(self, matches: list[SearchMatch], field_name: str) -> "Facet":
        """Aggregate facet values from search matches.

        Args:
            matches: Search matches with entries
            field_name: Field to create facet for

        Returns:
            Facet with aggregated values and counts
        """
        # Extract entries from matches
        entries = [m.entry for m in matches if m.entry]

        # Get field settings
        settings = self.config.get_field_settings(field_name)
        facet_type = self.config.get_facet_type(field_name)

        # Extract values
        extractor = FacetExtractor()
        values = extractor.extract_field_values(entries, field_name)

        # Create appropriate facet type
        if facet_type == FacetType.RANGE:
            return self._create_range_facet(field_name, values, settings)
        elif facet_type == FacetType.DATE_HISTOGRAM:
            return self._create_date_histogram_facet(field_name, values, settings)
        else:
            return self._create_terms_facet(field_name, values, settings)

    def _create_terms_facet(
        self, field_name: str, values: list[Any], settings: dict
    ) -> "TermsFacet":
        """Create terms facet from values."""
        # Count occurrences
        counter = Counter(values)

        # Apply min_count filter
        min_count = settings.get("min_count", 1)
        filtered_counts = {k: v for k, v in counter.items() if v >= min_count}

        # Sort by count descending, then by value
        sorted_items = sorted(filtered_counts.items(), key=lambda x: (-x[1], str(x[0])))

        # Apply size limit
        size = settings.get("size", 10)
        limited_items = sorted_items[:size]

        # Create facet
        facet = TermsFacet(
            field=field_name,
            display_name=self._get_display_name(field_name),
            size=size,
            min_count=min_count,
        )

        for value, count in limited_items:
            facet.add_value(value, count)

        return facet

    def _create_range_facet(
        self, field_name: str, values: list[Any], settings: dict
    ) -> "RangeFacet":
        """Create range facet from numeric values."""
        ranges = settings.get("ranges", [])

        facet = RangeFacet(
            field=field_name,
            display_name=self._get_display_name(field_name),
            ranges=ranges,
        )

        # Add values to appropriate ranges
        for value in values:
            if isinstance(value, int | float):
                facet.add_value(value)

        return facet

    def _create_date_histogram_facet(
        self, field_name: str, values: list[Any], settings: dict
    ) -> "DateHistogramFacet":
        """Create date histogram facet."""
        interval = settings.get("interval", "month")

        facet = DateHistogramFacet(
            field=field_name,
            display_name=self._get_display_name(field_name),
            interval=interval,
        )

        # Add date values
        for value in values:
            if isinstance(value, datetime):
                facet.add_value(value)

        return facet

    def _get_display_name(self, field_name: str) -> str:
        """Get human-readable display name for field."""
        display_names = {
            "entry_type": "Entry Type",
            "year": "Publication Year",
            "keywords": "Keywords",
            "author": "Authors",
            "journal": "Journal",
            "publisher": "Publisher",
            "booktitle": "Conference/Book",
        }
        return display_names.get(field_name, field_name.replace("_", " ").title())


class FacetFilter:
    """Filters entries based on facet selections."""

    def filter_by_facets(
        self, entries: list[BibEntry], facet_filters: dict[str, list[Any]]
    ) -> list[BibEntry]:
        """Filter entries by facet values.

        Args:
            entries: List of entries to filter
            facet_filters: Dict of field -> selected values

        Returns:
            Filtered list of entries
        """
        if not facet_filters:
            return entries

        filtered = []

        for entry in entries:
            # Check if entry matches all facet filters (AND operation)
            matches_all = True

            for field_name, selected_values in facet_filters.items():
                if not selected_values:
                    continue

                if not self._entry_matches_facet(entry, field_name, selected_values):
                    matches_all = False
                    break

            if matches_all:
                filtered.append(entry)

        return filtered

    def _entry_matches_facet(
        self, entry: BibEntry, field_name: str, selected_values: list[Any]
    ) -> bool:
        """Check if entry matches any of the selected values for a field."""
        # Handle special field mappings
        actual_field = field_name
        if field_name == "entry_type":
            actual_field = "type"

        if not hasattr(entry, actual_field):
            return False

        value = getattr(entry, actual_field)
        if value is None:
            return False

        # Handle special fields
        if field_name == "entry_type":
            # We already have the type value
            entry_value = value.value if hasattr(value, "value") else str(value).lower()
            return entry_value in selected_values
        elif field_name == "keywords":
            # Check if any keyword matches
            if isinstance(value, list | tuple):
                return any(kw in selected_values for kw in value)
            elif isinstance(value, str):
                keywords = [k.strip() for k in value.split(",")]
                return any(kw in selected_values for kw in keywords)
        elif field_name == "author":
            # Check if any author matches
            if isinstance(value, str):
                authors = [a.strip() for a in value.split(" and ")]
                return any(author in selected_values for author in authors)
        else:
            # Regular field - direct comparison
            return value in selected_values

        return False


# Facet type implementations


@dataclass
class Facet:
    """Base class for facets."""

    field: str
    display_name: str
    values: list[FacetValue] = dataclass_field(default_factory=list)
    facet_type: str = "terms"

    def get_value_count(self, value: str) -> int:
        """Get count for a specific value."""
        for fv in self.values:
            if fv.value == value:
                return fv.count
        return 0

    def get_top_values(self, limit: int = 10) -> list[FacetValue]:
        """Get top N values by count."""
        return sorted(self.values, key=lambda v: v.count, reverse=True)[:limit]


class TermsFacet(Facet):
    """Terms facet for discrete values."""

    def __init__(
        self, field: str, display_name: str, size: int = 10, min_count: int = 1
    ):
        super().__init__(field, display_name, facet_type="terms")
        self.size = size
        self.min_count = min_count
        self._value_counts: dict[str, int] = {}

    def add_value(self, value: Any, count: int) -> None:
        """Add a value with its count."""
        str_value = str(value)
        self._value_counts[str_value] = count

        self.values = [
            FacetValue(value=v, count=c)
            for v, c in sorted(self._value_counts.items(), key=lambda x: (-x[1], x[0]))
        ]

    def get_values(self) -> list[FacetValue]:
        """Get facet values sorted by count."""
        return self.values


class RangeFacet(Facet):
    """Range facet for numeric values."""

    def __init__(self, field: str, display_name: str, ranges: list[dict[str, Any]]):
        super().__init__(field, display_name, facet_type="range")
        self.ranges = ranges
        self._range_counts = defaultdict(int)

        # Initialize range labels
        for r in ranges:
            label = r.get("label", self._default_range_label(r))
            self._range_counts[label] = 0

    def add_value(self, value: float | int) -> None:
        """Add a numeric value to appropriate range."""
        for r in self.ranges:
            from_val = r.get("from", float("-inf"))
            to_val = r.get("to", float("inf"))

            if from_val <= value < to_val:
                label = r.get("label", self._default_range_label(r))
                self._range_counts[label] += 1
                break

        self.values = [
            FacetValue(value=label, count=count)
            for label, count in self._range_counts.items()
            if count > 0
        ]

    def _default_range_label(self, range_dict: dict) -> str:
        """Generate default label for range."""
        from_val = range_dict.get("from")
        to_val = range_dict.get("to")

        if from_val is None:
            return f"< {to_val}"
        elif to_val is None:
            return f">= {from_val}"
        else:
            return f"{from_val}-{to_val}"

    def get_values(self) -> list[FacetValue]:
        """Get range values in order."""
        # Return in range definition order
        ordered_values = []
        for r in self.ranges:
            label = r.get("label", self._default_range_label(r))
            if label in self._range_counts and self._range_counts[label] > 0:
                ordered_values.append(
                    FacetValue(value=label, count=self._range_counts[label])
                )
        return ordered_values


class DateHistogramFacet(Facet):
    """Date histogram facet for time-based data."""

    def __init__(self, field: str, display_name: str, interval: str = "month"):
        super().__init__(field, display_name, facet_type="date_histogram")
        self.interval = interval
        self._bucket_counts = defaultdict(int)

    def add_value(self, date: datetime) -> None:
        """Add a date value to appropriate bucket."""
        bucket_key = self._get_bucket_key(date)
        self._bucket_counts[bucket_key] += 1

        self.values = [
            FacetValue(value=key, count=count)
            for key, count in sorted(self._bucket_counts.items())
        ]

    def _get_bucket_key(self, date: datetime) -> str:
        """Get bucket key for date based on interval."""
        if self.interval == "year":
            return str(date.year)
        elif self.interval == "month":
            return f"{date.year}-{date.month:02d}"
        elif self.interval == "day":
            return date.strftime("%Y-%m-%d")
        else:
            # Default to month
            return f"{date.year}-{date.month:02d}"

    def get_values(self) -> list[FacetValue]:
        """Get date histogram values in chronological order."""
        return self.values
