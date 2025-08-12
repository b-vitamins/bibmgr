"""Tests for search results and formatting."""

import pytest

from bibmgr.core.fields import EntryType
from bibmgr.core.models import Entry
from bibmgr.search.results import (
    Facet,
    FacetValue,
    ResultsBuilder,
    SearchMatch,
    SearchResultCollection,
    SearchStatistics,
    SearchSuggestion,
    SortOrder,
    create_empty_results,
    merge_result_collections,
)


class TestSearchMatch:
    """Test SearchMatch data class."""

    @pytest.fixture
    def sample_entry(self):
        """Sample bibliography entry."""
        return Entry(
            key="test2024",
            type=EntryType.ARTICLE,
            title="Machine Learning Applications",
            author="John Smith and Jane Doe",
            journal="AI Review",
            year=2024,
            abstract="This paper presents novel ML applications",
            keywords=("machine learning", "applications"),
        )

    def test_create_basic_match(self, sample_entry):
        """Create basic search match."""
        match = SearchMatch(entry_key="test2024", score=0.95, entry=sample_entry)

        assert match.entry_key == "test2024"
        assert match.score == 0.95
        assert match.entry == sample_entry
        assert match.highlights is None
        assert match.explanation is None

    def test_create_match_with_highlights(self, sample_entry):
        """Create search match with highlights."""
        highlights = {
            "title": ["<mark>Machine Learning</mark> Applications"],
            "abstract": ["novel <mark>ML</mark> applications"],
        }

        match = SearchMatch(
            entry_key="test2024",
            score=1.2,
            entry=sample_entry,
            highlights=highlights,
        )

        assert match.highlights == highlights
        assert match.highlights is not None
        assert len(match.highlights) == 2

    def test_create_match_with_explanation(self, sample_entry):
        """Create search match with scoring explanation."""
        explanation = "BM25(title:machine) = 0.8, BM25(abstract:learning) = 0.4"

        match = SearchMatch(
            entry_key="test2024",
            score=1.2,
            entry=sample_entry,
            explanation=explanation,
        )

        assert match.explanation == explanation

    def test_score_normalization(self):
        """Scores should be normalized to reasonable bounds."""
        # Negative score
        match = SearchMatch(entry_key="test", score=-5.0)
        assert match.score == 0.0

        # Very high score
        match = SearchMatch(entry_key="test", score=150.0)
        assert match.score == 100.0

        # Normal score
        match = SearchMatch(entry_key="test", score=5.0)
        assert match.score == 5.0


class TestFacetValue:
    """Test FacetValue data class."""

    def test_create_facet_value(self):
        """Create facet value."""
        facet_value = FacetValue(value="2024", count=15)

        assert facet_value.value == "2024"
        assert facet_value.count == 15
        assert facet_value.selected is False

    def test_create_selected_facet_value(self):
        """Create selected facet value."""
        facet_value = FacetValue(value="article", count=25, selected=True)

        assert facet_value.value == "article"
        assert facet_value.count == 25
        assert facet_value.selected is True

    def test_facet_value_string_representation(self):
        """Facet value should have readable string representation."""
        facet_value = FacetValue(value="2024", count=10)
        assert str(facet_value) == "2024 (10)"


class TestFacet:
    """Test Facet data class."""

    def test_create_facet(self):
        """Create facet."""
        values = [
            FacetValue("2024", 15),
            FacetValue("2023", 25),
            FacetValue("2022", 10),
        ]

        facet = Facet(field="year", display_name="Year", values=values)

        assert facet.field == "year"
        assert facet.display_name == "Year"
        assert len(facet.values) == 3
        assert facet.facet_type == "terms"

    def test_get_value_count(self):
        """Get count for specific value."""
        values = [
            FacetValue("2024", 15),
            FacetValue("2023", 25),
        ]

        facet = Facet(field="year", display_name="Year", values=values)

        assert facet.get_value_count("2024") == 15
        assert facet.get_value_count("2023") == 25
        assert facet.get_value_count("2022") == 0  # Not present

    def test_get_top_values(self):
        """Get top values should sort by count."""
        values = [
            FacetValue("2022", 5),
            FacetValue("2024", 20),
            FacetValue("2023", 15),
            FacetValue("2021", 8),
        ]

        facet = Facet(field="year", display_name="Year", values=values)

        # Get top 2 values
        top_values = facet.get_top_values(limit=2)

        assert len(top_values) == 2
        assert top_values[0].value == "2024"  # Highest count
        assert top_values[1].value == "2023"  # Second highest

    def test_get_top_values_all(self):
        """Get all values when limit is high."""
        values = [
            FacetValue("A", 10),
            FacetValue("B", 5),
        ]

        facet = Facet(field="category", display_name="Category", values=values)

        # Request more than available
        top_values = facet.get_top_values(limit=10)

        assert len(top_values) == 2


class TestSearchSuggestion:
    """Test SearchSuggestion data class."""

    def test_create_suggestion(self):
        """Create search suggestion."""
        suggestion = SearchSuggestion(
            suggestion="machine learning", suggestion_type="spell_check", confidence=0.9
        )

        assert suggestion.suggestion == "machine learning"
        assert suggestion.suggestion_type == "spell_check"
        assert suggestion.confidence == 0.9
        assert suggestion.description is None

    def test_create_suggestion_with_description(self):
        """Create suggestion with description."""
        suggestion = SearchSuggestion(
            suggestion="neural networks",
            suggestion_type="synonym",
            confidence=0.8,
            description="Related to deep learning",
        )

        assert suggestion.description == "Related to deep learning"


class TestSearchStatistics:
    """Test SearchStatistics data class."""

    def test_create_statistics(self):
        """Create search statistics."""
        stats = SearchStatistics(
            total_results=100, search_time_ms=45, backend_name="whoosh"
        )

        assert stats.total_results == 100
        assert stats.search_time_ms == 45
        assert stats.backend_name == "whoosh"
        assert stats.query_time_ms is None
        assert stats.fetch_time_ms is None
        assert stats.index_size is None

    def test_search_time_seconds(self):
        """Search time should be available in seconds."""
        stats = SearchStatistics(
            total_results=100, search_time_ms=1500, backend_name="whoosh"
        )

        assert stats.search_time_seconds == 1.5


class TestSearchResultCollection:
    """Test SearchResultCollection data class."""

    @pytest.fixture
    def sample_matches(self):
        """Sample search matches."""
        entry1 = Entry(
            key="hit1",
            type=EntryType.ARTICLE,
            title="First Result",
            author="Author One",
            year=2024,
        )
        entry2 = Entry(
            key="hit2",
            type=EntryType.BOOK,
            title="Second Result",
            author="Author Two",
            year=2023,
        )

        return [
            SearchMatch(entry_key="hit1", score=1.5, entry=entry1),
            SearchMatch(entry_key="hit2", score=1.2, entry=entry2),
        ]

    def test_create_basic_collection(self, sample_matches):
        """Create basic search result collection."""
        collection = SearchResultCollection(matches=sample_matches, total=2)

        assert len(collection.matches) == 2
        assert collection.total == 2
        assert collection.offset == 0
        assert collection.limit == 20
        assert collection.has_results is True

    def test_create_full_collection(self, sample_matches):
        """Create collection with all fields."""
        facets = [
            Facet("year", "Year", [FacetValue("2024", 1)]),
            Facet("type", "Type", [FacetValue("article", 1)]),
        ]

        suggestions = [
            SearchSuggestion("machine", "spell_check", 0.9),
            SearchSuggestion("learning", "completion", 0.8),
        ]

        stats = SearchStatistics(
            total_results=100, search_time_ms=45, backend_name="whoosh"
        )

        collection = SearchResultCollection(
            matches=sample_matches,
            total=100,
            offset=20,
            limit=10,
            facets=facets,
            suggestions=suggestions,
            statistics=stats,
            query="machine learning",
            sort_order=SortOrder.RELEVANCE,
        )

        assert collection.total == 100
        assert collection.offset == 20
        assert collection.limit == 10
        assert len(collection.facets) == 2
        assert len(collection.suggestions) == 2
        assert collection.statistics is not None
        assert collection.statistics.search_time_ms == 45
        assert collection.query == "machine learning"

    def test_pagination_calculations(self, sample_matches):
        """Pagination calculations should work correctly."""
        # First page
        collection = SearchResultCollection(
            matches=sample_matches, total=100, offset=0, limit=20
        )
        assert collection.current_page == 1
        assert collection.total_pages == 5
        assert collection.has_more is True
        assert collection.has_previous is False

        # Middle page
        collection = SearchResultCollection(
            matches=sample_matches, total=100, offset=40, limit=20
        )
        assert collection.current_page == 3
        assert collection.has_more is True
        assert collection.has_previous is True

        # Last page
        collection = SearchResultCollection(
            matches=sample_matches, total=100, offset=80, limit=20
        )
        assert collection.current_page == 5
        assert collection.has_more is False
        assert collection.has_previous is True

    def test_post_init_validation(self):
        """Collection should validate parameters on creation."""
        # Negative offset
        collection = SearchResultCollection(matches=[], total=0, offset=-5)
        assert collection.offset == 0

        # Zero limit
        collection = SearchResultCollection(matches=[], total=0, limit=0)
        assert collection.limit == 1

        # Total less than matches
        matches = [SearchMatch("key1", 1.0), SearchMatch("key2", 1.0)]
        collection = SearchResultCollection(matches=matches, total=1)
        assert collection.total == 2

    def test_get_facet(self, sample_matches):
        """Get facet by field name."""
        facets = [
            Facet("year", "Year", [FacetValue("2024", 10)]),
            Facet("type", "Type", [FacetValue("article", 5)]),
        ]

        collection = SearchResultCollection(
            matches=sample_matches, total=2, facets=facets
        )

        year_facet = collection.get_facet("year")
        assert year_facet is not None
        assert year_facet.field == "year"

        missing_facet = collection.get_facet("missing")
        assert missing_facet is None

    def test_get_facet_values(self, sample_matches):
        """Get facet values for a field."""
        facets = [
            Facet("year", "Year", [FacetValue("2024", 10), FacetValue("2023", 5)]),
        ]

        collection = SearchResultCollection(
            matches=sample_matches, total=2, facets=facets
        )

        year_values = collection.get_facet_values("year")
        assert len(year_values) == 2
        assert year_values[0].value == "2024"

        missing_values = collection.get_facet_values("missing")
        assert missing_values == []

    def test_get_top_facet_values(self, sample_matches):
        """Get top facet values for a field."""
        facets = [
            Facet(
                "year",
                "Year",
                [
                    FacetValue("2024", 10),
                    FacetValue("2023", 5),
                    FacetValue("2022", 3),
                    FacetValue("2021", 1),
                ],
            ),
        ]

        collection = SearchResultCollection(
            matches=sample_matches, total=2, facets=facets
        )

        top_years = collection.get_top_facet_values("year", limit=2)
        assert len(top_years) == 2
        assert top_years[0].value == "2024"
        assert top_years[1].value == "2023"

    def test_get_results_for_page(self, sample_matches):
        """Get results for specific page."""
        # Create 10 matches
        matches = [SearchMatch(entry_key=f"key{i}", score=float(i)) for i in range(10)]

        collection = SearchResultCollection(
            matches=matches, total=25, offset=0, limit=3
        )

        # Get page 1
        page1 = collection.get_results_for_page(1)
        assert len(page1) == 3
        assert page1[0].entry_key == "key0"

        # Get page 2
        page2 = collection.get_results_for_page(2)
        assert len(page2) == 3
        assert page2[0].entry_key == "key3"

        # Get beyond available
        page10 = collection.get_results_for_page(10)
        assert len(page10) == 0

    def test_get_score_range(self, sample_matches):
        """Get min and max scores."""
        collection = SearchResultCollection(matches=sample_matches, total=2)

        min_score, max_score = collection.get_score_range()
        assert min_score == 1.2
        assert max_score == 1.5

        # Empty collection
        empty_collection = SearchResultCollection(matches=[], total=0)
        min_score, max_score = empty_collection.get_score_range()
        assert min_score == 0.0
        assert max_score == 0.0

    def test_filter_by_score(self, sample_matches):
        """Filter results by minimum score."""
        collection = SearchResultCollection(matches=sample_matches, total=2)

        # Filter with threshold
        filtered = collection.filter_by_score(min_score=1.3)
        assert len(filtered.matches) == 1
        assert filtered.matches[0].score == 1.5
        assert filtered.total == 1
        assert filtered.offset == 0

    def test_sort_by_relevance(self):
        """Sort by relevance (score)."""
        matches = [
            SearchMatch("key1", 1.0),
            SearchMatch("key2", 3.0),
            SearchMatch("key3", 2.0),
        ]

        collection = SearchResultCollection(matches=matches, total=3)
        sorted_collection = collection.sort_by(SortOrder.RELEVANCE)

        assert sorted_collection.matches[0].score == 3.0
        assert sorted_collection.matches[1].score == 2.0
        assert sorted_collection.matches[2].score == 1.0

    def test_to_dict(self, sample_matches):
        """Convert collection to dictionary."""
        facets = [Facet("year", "Year", [FacetValue("2024", 10)])]

        suggestions = [SearchSuggestion("test", "spell_check", 0.9)]

        stats = SearchStatistics(
            total_results=2, search_time_ms=10, backend_name="whoosh"
        )

        collection = SearchResultCollection(
            matches=sample_matches,
            total=2,
            facets=facets,
            suggestions=suggestions,
            statistics=stats,
            query="test",
        )

        result = collection.to_dict()

        assert result["total"] == 2
        assert result["query"] == "test"
        assert len(result["matches"]) == 2
        assert len(result["facets"]) == 1
        assert len(result["suggestions"]) == 1
        assert result["statistics"]["search_time_ms"] == 10


class TestResultsBuilder:
    """Test ResultsBuilder class."""

    def test_create_builder(self):
        """Create results builder."""
        builder = ResultsBuilder()

        assert builder.matches == []
        assert builder.total == 0
        assert builder.offset == 0
        assert builder.limit == 20

    def test_add_match(self):
        """Add matches to builder."""
        builder = ResultsBuilder()

        builder.add_match("key1", 1.5)
        builder.add_match("key2", 1.2, explanation="Test explanation")

        assert len(builder.matches) == 2
        assert builder.matches[0].entry_key == "key1"
        assert builder.matches[0].score == 1.5
        assert builder.matches[1].explanation == "Test explanation"

    def test_add_facet(self):
        """Add facets to builder."""
        builder = ResultsBuilder()

        builder.add_facet(
            field="year", display_name="Year", values=[("2024", 10), ("2023", 5)]
        )

        assert len(builder.facets) == 1
        assert builder.facets[0].field == "year"
        assert len(builder.facets[0].values) == 2

    def test_add_suggestion(self):
        """Add suggestions to builder."""
        builder = ResultsBuilder()

        builder.add_suggestion(
            suggestion="machine learning",
            suggestion_type="spell_check",
            confidence=0.9,
            description="Did you mean?",
        )

        assert len(builder.suggestions) == 1
        assert builder.suggestions[0].suggestion == "machine learning"

    def test_set_pagination(self):
        """Set pagination parameters."""
        builder = ResultsBuilder()

        builder.set_pagination(offset=20, limit=10, total=100)

        assert builder.offset == 20
        assert builder.limit == 10
        assert builder.total == 100

    def test_set_query_info(self):
        """Set query information."""
        builder = ResultsBuilder()

        builder.set_query_info("test query", parsed_query={"type": "term"})

        assert builder.query == "test query"
        assert builder.parsed_query == {"type": "term"}

    def test_set_timing(self):
        """Set timing information."""
        builder = ResultsBuilder()

        builder.set_timing(search_time_ms=50)

        assert builder.search_time_ms == 50

    def test_set_backend_info(self):
        """Set backend information."""
        builder = ResultsBuilder()

        builder.set_backend_info(backend_name="whoosh", index_size=1000)

        assert builder.backend_name == "whoosh"
        assert builder.index_size == 1000

    def test_build_complete(self):
        """Build complete result collection."""
        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test", year=2024)

        collection = (
            ResultsBuilder()
            .add_match("test", 1.5, entry=entry)
            .add_facet("year", "Year", [("2024", 1)])
            .add_suggestion("test", "spell_check", 0.9)
            .set_pagination(0, 10, 1)
            .set_query_info("test query")
            .set_timing(25)
            .set_backend_info("whoosh")
            .build()
        )

        assert isinstance(collection, SearchResultCollection)
        assert len(collection.matches) == 1
        assert len(collection.facets) == 1
        assert len(collection.suggestions) == 1
        assert collection.statistics is not None
        assert collection.statistics.search_time_ms == 25
        assert collection.statistics.backend_name == "whoosh"

    def test_build_adjusts_total(self):
        """Build should adjust total if less than matches."""
        builder = ResultsBuilder()

        builder.add_match("key1", 1.0)
        builder.add_match("key2", 1.0)
        builder.set_pagination(0, 10, 1)  # Total is 1 but have 2 matches

        collection = builder.build()

        assert collection.total == 2  # Adjusted to match count


class TestHelperFunctions:
    """Test helper functions."""

    def test_create_empty_results(self):
        """Create empty results."""
        results = create_empty_results()

        assert isinstance(results, SearchResultCollection)
        assert results.total == 0
        assert len(results.matches) == 0
        assert results.limit == 20
        assert results.statistics is not None
        assert results.statistics.backend_name == "unknown"

        # With parameters
        results = create_empty_results(query="test", limit=10, backend_name="whoosh")

        assert results.query == "test"
        assert results.limit == 10
        assert results.statistics is not None
        assert results.statistics.backend_name == "whoosh"

    def test_merge_empty_collections(self):
        """Merge empty collections."""
        result = merge_result_collections([])

        assert isinstance(result, SearchResultCollection)
        assert result.total == 0

    def test_merge_single_collection(self):
        """Merge single collection returns itself."""
        collection = SearchResultCollection(matches=[SearchMatch("key1", 1.0)], total=1)

        result = merge_result_collections([collection])

        assert result is collection

    def test_merge_multiple_collections(self):
        """Merge multiple collections."""
        col1 = SearchResultCollection(
            matches=[
                SearchMatch("key1", 2.0),
                SearchMatch("key2", 1.5),
            ],
            total=2,
            facets=[
                Facet(
                    "year",
                    "Year",
                    [
                        FacetValue("2024", 5),
                        FacetValue("2023", 3),
                    ],
                )
            ],
        )

        col2 = SearchResultCollection(
            matches=[
                SearchMatch("key3", 1.8),
                SearchMatch("key2", 1.5),  # Duplicate
            ],
            total=2,
            facets=[
                Facet(
                    "year",
                    "Year",
                    [
                        FacetValue("2024", 3),
                        FacetValue("2022", 2),
                    ],
                )
            ],
        )

        result = merge_result_collections([col1, col2])

        # Should have 3 unique matches
        assert len(result.matches) == 3
        assert result.total == 3

        # Should be sorted by relevance
        assert result.matches[0].entry_key == "key1"  # Score 2.0
        assert result.matches[1].entry_key == "key3"  # Score 1.8
        assert result.matches[2].entry_key == "key2"  # Score 1.5

        # Facets should be merged
        year_facet = result.get_facet("year")
        assert year_facet is not None
        assert year_facet.get_value_count("2024") == 8  # 5 + 3
        assert year_facet.get_value_count("2023") == 3
        assert year_facet.get_value_count("2022") == 2

    def test_merge_without_sorting(self):
        """Merge without sorting by relevance."""
        col1 = SearchResultCollection(matches=[SearchMatch("key1", 1.0)], total=1)

        col2 = SearchResultCollection(matches=[SearchMatch("key2", 2.0)], total=1)

        result = merge_result_collections([col1, col2], sort_by_relevance=False)

        # Should maintain original order
        assert result.matches[0].entry_key == "key1"
        assert result.matches[1].entry_key == "key2"
