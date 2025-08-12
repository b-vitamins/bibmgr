"""Tests for the facets module."""

from datetime import datetime

import pytest

from bibmgr.core import Entry, EntryType
from bibmgr.search.backends.base import SearchMatch
from bibmgr.search.facets import (
    DateHistogramFacet,
    FacetAggregator,
    FacetConfiguration,
    FacetExtractor,
    FacetFilter,
    FacetType,
    RangeFacet,
    TermsFacet,
)
from bibmgr.search.results import FacetValue


class TestFacetConfiguration:
    """Test facet configuration."""

    def test_default_configuration(self):
        """Test default facet configuration."""
        config = FacetConfiguration()

        # Should have default facet fields
        assert len(config.get_facet_fields()) > 0
        assert "entry_type" in config.get_facet_fields()
        assert "year" in config.get_facet_fields()
        assert "keywords" in config.get_facet_fields()

        # Should have appropriate facet types
        assert config.get_facet_type("entry_type") == FacetType.TERMS
        assert config.get_facet_type("year") == FacetType.RANGE
        assert config.get_facet_type("keywords") == FacetType.TERMS

    def test_custom_configuration(self):
        """Test custom facet configuration."""
        custom_config = {
            "author": {"type": "terms", "size": 20},
            "publication_date": {"type": "date_histogram", "interval": "year"},
            "page_count": {
                "type": "range",
                "ranges": [
                    {"to": 10, "label": "Short"},
                    {"from": 10, "to": 50, "label": "Medium"},
                    {"from": 50, "label": "Long"},
                ],
            },
        }

        config = FacetConfiguration(custom_config)

        # Should have custom fields
        assert "author" in config.get_facet_fields()
        assert "publication_date" in config.get_facet_fields()
        assert "page_count" in config.get_facet_fields()

        # Should have correct types
        assert config.get_facet_type("author") == FacetType.TERMS
        assert config.get_facet_type("publication_date") == FacetType.DATE_HISTOGRAM
        assert config.get_facet_type("page_count") == FacetType.RANGE

    def test_facet_field_settings(self):
        """Test facet field-specific settings."""
        config = FacetConfiguration(
            {
                "keywords": {"type": "terms", "size": 50, "min_count": 2},
                "year": {
                    "type": "range",
                    "ranges": [
                        {"to": 2000, "label": "Before 2000"},
                        {"from": 2000, "to": 2010, "label": "2000s"},
                        {"from": 2010, "to": 2020, "label": "2010s"},
                        {"from": 2020, "label": "2020s"},
                    ],
                },
            }
        )

        # Get field settings
        keywords_settings = config.get_field_settings("keywords")
        assert keywords_settings["size"] == 50
        assert keywords_settings["min_count"] == 2

        year_settings = config.get_field_settings("year")
        assert len(year_settings["ranges"]) == 4


@pytest.fixture
def sample_entries():
    """Create sample entries for testing."""
    return [
        Entry(
            key="entry1",
            type=EntryType.ARTICLE,
            title="Machine Learning Paper",
            author="Smith, John and Doe, Jane",
            year=2023,
            keywords=("machine learning", "algorithms", "ai"),
            journal="ML Journal",
        ),
        Entry(
            key="entry2",
            type=EntryType.BOOK,
            title="Deep Learning Book",
            author="Johnson, Alice",
            year=2022,
            keywords=("deep learning", "neural networks", "ai"),
            publisher="Tech Press",
        ),
        Entry(
            key="entry3",
            type=EntryType.INPROCEEDINGS,
            title="NLP Conference Paper",
            author="Brown, Bob and Smith, John",
            year=2023,
            keywords=("nlp", "transformers", "ai"),
            booktitle="NLP Conference 2023",
        ),
    ]


class TestFacetExtractor:
    """Test facet value extraction from entries."""

    def test_extract_terms_facet(self, sample_entries):
        """Test extracting terms facet values."""
        extractor = FacetExtractor()

        # Extract entry types
        type_values = extractor.extract_field_values(sample_entries, "entry_type")
        assert len(type_values) == 3
        assert "article" in type_values
        assert "book" in type_values
        assert "inproceedings" in type_values

        # Extract keywords (should be flattened)
        keyword_values = extractor.extract_field_values(sample_entries, "keywords")
        assert "machine learning" in keyword_values
        assert "ai" in keyword_values
        assert "neural networks" in keyword_values

    def test_extract_numeric_facet(self, sample_entries):
        """Test extracting numeric facet values."""
        extractor = FacetExtractor()

        # Extract years
        year_values = extractor.extract_field_values(sample_entries, "year")
        assert 2023 in year_values
        assert 2022 in year_values
        assert len(year_values) == 3  # Two 2023s and one 2022

    def test_extract_author_facet(self, sample_entries):
        """Test extracting author facet values."""
        extractor = FacetExtractor()

        # Extract authors (should split on "and")
        author_values = extractor.extract_field_values(sample_entries, "author")
        assert "Smith, John" in author_values
        assert "Doe, Jane" in author_values
        assert "Johnson, Alice" in author_values
        assert "Brown, Bob" in author_values

    def test_extract_missing_field(self, sample_entries):
        """Test extracting values from missing field."""
        extractor = FacetExtractor()

        # Extract non-existent field
        values = extractor.extract_field_values(sample_entries, "nonexistent")
        assert len(values) == 0


class TestFacetAggregator:
    """Test facet aggregation."""

    @pytest.fixture
    def sample_matches(self, sample_entries):
        """Create sample search matches."""
        return [
            SearchMatch(entry_key="entry1", score=0.9, entry=sample_entries[0]),
            SearchMatch(entry_key="entry2", score=0.8, entry=sample_entries[1]),
            SearchMatch(entry_key="entry3", score=0.7, entry=sample_entries[2]),
        ]

    def test_aggregate_terms_facet(self, sample_matches):
        """Test aggregating terms facet."""
        config = FacetConfiguration()
        aggregator = FacetAggregator(config)

        # Aggregate entry types
        facet = aggregator.aggregate_facet(sample_matches, "entry_type")
        assert facet.field == "entry_type"
        assert len(facet.values) == 3

        # Check counts
        article_value = next(v for v in facet.values if v.value == "article")
        assert article_value.count == 1

        # Should be sorted by count (if multiple) then alphabetically
        values = [v.value for v in facet.values]
        assert values == sorted(values)

    def test_aggregate_multi_value_facet(self, sample_matches):
        """Test aggregating multi-value fields like keywords."""
        config = FacetConfiguration()
        aggregator = FacetAggregator(config)

        # Aggregate keywords
        facet = aggregator.aggregate_facet(sample_matches, "keywords")

        # "ai" appears in all 3 entries
        ai_value = next(v for v in facet.values if v.value == "ai")
        assert ai_value.count == 3

        # Other keywords appear once
        ml_value = next(v for v in facet.values if v.value == "machine learning")
        assert ml_value.count == 1

    def test_aggregate_range_facet(self, sample_matches):
        """Test aggregating range facet."""
        config = FacetConfiguration(
            {
                "year": {
                    "type": "range",
                    "ranges": [
                        {"to": 2022, "label": "Before 2022"},
                        {"from": 2022, "to": 2023, "label": "2022"},
                        {"from": 2023, "label": "2023+"},
                    ],
                }
            }
        )
        aggregator = FacetAggregator(config)

        # Aggregate years
        facet = aggregator.aggregate_facet(sample_matches, "year")
        assert facet.facet_type == "range"

        # Check range counts
        range_2022 = next(v for v in facet.values if v.value == "2022")
        assert range_2022.count == 1

        range_2023 = next(v for v in facet.values if v.value == "2023+")
        assert range_2023.count == 2

    def test_aggregate_with_size_limit(self, sample_matches):
        """Test facet aggregation with size limit."""
        config = FacetConfiguration({"keywords": {"type": "terms", "size": 3}})
        aggregator = FacetAggregator(config)

        # Aggregate keywords with limit
        facet = aggregator.aggregate_facet(sample_matches, "keywords")

        # Should only return top 3
        assert len(facet.values) <= 3

        # Should be sorted by count descending
        counts = [v.count for v in facet.values]
        assert counts == sorted(counts, reverse=True)

    def test_aggregate_with_min_count(self, sample_matches):
        """Test facet aggregation with minimum count threshold."""
        config = FacetConfiguration({"keywords": {"type": "terms", "min_count": 2}})
        aggregator = FacetAggregator(config)

        # Aggregate keywords with min count
        facet = aggregator.aggregate_facet(sample_matches, "keywords")

        # Only "ai" appears 3 times, others appear once
        assert len(facet.values) == 1
        assert facet.values[0].value == "ai"
        assert facet.values[0].count == 3


class TestFacetFilter:
    """Test facet-based filtering."""

    @pytest.fixture
    def sample_entries_large(self):
        """Create larger set of entries for filtering tests."""
        entries = []
        for i in range(20):
            entry = Entry(
                key=f"entry{i}",
                type=EntryType.ARTICLE if i % 3 == 0 else EntryType.BOOK,
                title=f"Title {i}",
                author=f"Author {i % 5}",
                year=2020 + (i % 4),
                keywords=(f"keyword{i % 3}", f"topic{i % 2}"),
            )
            entries.append(entry)
        return entries

    def test_filter_by_single_facet(self, sample_entries_large):
        """Test filtering by single facet value."""
        filter = FacetFilter()

        # Filter by entry type
        filtered = filter.filter_by_facets(
            sample_entries_large, {"entry_type": ["article"]}
        )

        # Should only have articles
        assert all(e.type == EntryType.ARTICLE for e in filtered)
        assert len(filtered) == 7  # entries 0, 3, 6, 9, 12, 15, 18

    def test_filter_by_multiple_values(self, sample_entries_large):
        """Test filtering by multiple values in same facet."""
        filter = FacetFilter()

        # Filter by multiple years
        filtered = filter.filter_by_facets(sample_entries_large, {"year": [2020, 2021]})

        # Should have entries from 2020 or 2021
        assert all(e.year in [2020, 2021] for e in filtered)

    def test_filter_by_multiple_facets(self, sample_entries_large):
        """Test filtering by multiple facets (AND operation)."""
        filter = FacetFilter()

        # Filter by type AND year
        filtered = filter.filter_by_facets(
            sample_entries_large, {"entry_type": ["article"], "year": [2022]}
        )

        # Should have articles from 2022
        assert all(e.type == EntryType.ARTICLE for e in filtered)
        assert all(e.year == 2022 for e in filtered)

    def test_filter_by_keyword_facet(self, sample_entries_large):
        """Test filtering by keyword facet."""
        filter = FacetFilter()

        # Filter by keyword
        filtered = filter.filter_by_facets(
            sample_entries_large, {"keywords": ["keyword1"]}
        )

        # Should have entries with keyword1
        assert all(e.keywords and "keyword1" in e.keywords for e in filtered)

    def test_filter_with_empty_selection(self, sample_entries_large):
        """Test filtering with empty selection returns all."""
        filter = FacetFilter()

        # Empty filter
        filtered = filter.filter_by_facets(sample_entries_large, {})

        # Should return all entries
        assert len(filtered) == len(sample_entries_large)

    def test_filter_preserves_order(self, sample_entries_large):
        """Test that filtering preserves original order."""
        filter = FacetFilter()

        # Filter by year
        filtered = filter.filter_by_facets(sample_entries_large, {"year": [2020]})

        # Check order is preserved
        keys = [e.key for e in filtered]
        expected_keys = [f"entry{i}" for i in range(20) if i % 4 == 0]
        assert keys == expected_keys


class TestFacetTypes:
    """Test specific facet type implementations."""

    def test_terms_facet(self):
        """Test terms facet type."""
        facet = TermsFacet(
            field="keywords", display_name="Keywords", size=10, min_count=1
        )

        # Add values
        facet.add_value("machine learning", 5)
        facet.add_value("ai", 10)
        facet.add_value("nlp", 3)

        # Get results
        values = facet.get_values()

        # Should be sorted by count descending
        assert values[0].value == "ai"
        assert values[0].count == 10
        assert values[1].value == "machine learning"
        assert values[1].count == 5

    def test_range_facet(self):
        """Test range facet type."""
        facet = RangeFacet(
            field="year",
            display_name="Publication Year",
            ranges=[
                {"from": 2020, "to": 2022, "label": "2020-2021"},
                {"from": 2022, "to": 2024, "label": "2022-2023"},
                {"from": 2024, "label": "2024+"},
            ],
        )

        # Add values
        for year in [2020, 2021, 2021, 2022, 2023, 2024]:
            facet.add_value(year)

        # Get results
        values = facet.get_values()

        # Check range counts
        range_2020 = next(v for v in values if v.value == "2020-2021")
        assert range_2020.count == 3  # 2020, 2021, 2021

        range_2022 = next(v for v in values if v.value == "2022-2023")
        assert range_2022.count == 2  # 2022, 2023

    def test_date_histogram_facet(self):
        """Test date histogram facet type."""
        facet = DateHistogramFacet(
            field="added", display_name="Date Added", interval="month"
        )

        # Add date values
        dates = [
            datetime(2024, 1, 15),
            datetime(2024, 1, 20),
            datetime(2024, 2, 5),
            datetime(2024, 2, 10),
            datetime(2024, 2, 15),
        ]

        for date in dates:
            facet.add_value(date)

        # Get results
        values = facet.get_values()

        # Should have monthly buckets
        jan_bucket = next(v for v in values if "2024-01" in v.value)
        assert jan_bucket.count == 2

        feb_bucket = next(v for v in values if "2024-02" in v.value)
        assert feb_bucket.count == 3


class TestFacetIntegration:
    """Test facet integration with search results."""

    def test_facets_in_search_results(self):
        """Test that facets are properly integrated in search results."""
        from bibmgr.search.results import Facet, SearchResultCollection

        # Create search results with facets
        results = SearchResultCollection(
            query="test",
            matches=[],
            total=0,
            facets=[
                Facet(
                    field="entry_type",
                    display_name="Entry Type",
                    values=[
                        FacetValue("article", 10),
                        FacetValue("book", 5),
                    ],
                ),
                Facet(
                    field="year",
                    display_name="Year",
                    values=[
                        FacetValue("2023", 8),
                        FacetValue("2022", 7),
                    ],
                ),
            ],
        )

        # Access facets
        assert len(results.facets) == 2

        # Check facet fields
        facet_fields = [f.field for f in results.facets]
        assert "entry_type" in facet_fields
        assert "year" in facet_fields

        # Check facet values using get_facet method
        type_facet = results.get_facet("entry_type")
        assert type_facet is not None
        assert type_facet.get_value_count("article") == 10
        assert type_facet.get_value_count("book") == 5

    def test_facet_driven_navigation(self):
        """Test facet-driven search refinement."""
        from bibmgr.search import create_memory_engine
        from bibmgr.search.facets import FacetConfiguration

        # Create engine with facet configuration
        FacetConfiguration(
            {
                "entry_type": {"type": "terms"},
                "year": {
                    "type": "range",
                    "ranges": [
                        {"to": 2022, "label": "Before 2022"},
                        {"from": 2022, "label": "2022+"},
                    ],
                },
                "keywords": {"type": "terms", "size": 5},
            }
        )

        engine = create_memory_engine()

        # Create test entries
        entries = [
            Entry(
                key=f"entry{i}",
                type=EntryType.ARTICLE if i % 2 == 0 else EntryType.BOOK,
                title=f"Title about {['machine learning', 'deep learning'][i % 2]}",
                author=f"Author {i}",
                year=2020 + i,
                keywords=(f"keyword{i % 3}", "ai"),
            )
            for i in range(10)
        ]

        # Index entries
        engine.index_entries(entries)

        # Initial search with facets
        results = engine.search("learning", enable_facets=True)

        # Should have facets
        assert results.facets is not None
        assert len(results.facets) > 0

        # Refine by facet
        refined_results = engine.search(
            "learning", filters={"entry_type": ["article"]}, enable_facets=True
        )

        # Should have fewer results
        assert refined_results.total < results.total
        # All should be articles
        assert all(
            m.entry.type == EntryType.ARTICLE
            for m in refined_results.matches
            if m.entry
        )
