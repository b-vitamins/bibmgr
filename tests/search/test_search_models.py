"""Comprehensive tests for search models.

These tests are implementation-agnostic and focus on the expected behavior
and data contracts of search models.
"""

import pytest
from pathlib import Path

# Tests are now ready to run


class TestEntryType:
    """Test bibliography entry type enumeration."""

    def test_standard_types_exist(self):
        """All standard BibTeX types should be available."""
        from bibmgr.search.models import EntryType

        expected_types = [
            "ARTICLE",
            "BOOK",
            "BOOKLET",
            "CONFERENCE",
            "INBOOK",
            "INCOLLECTION",
            "INPROCEEDINGS",
            "MANUAL",
            "MASTERSTHESIS",
            "MISC",
            "PHDTHESIS",
            "PROCEEDINGS",
            "TECHREPORT",
            "UNPUBLISHED",
        ]

        for type_name in expected_types:
            assert hasattr(EntryType, type_name)
            assert isinstance(getattr(EntryType, type_name).value, str)

    def test_type_values_lowercase(self):
        """Entry type values should be lowercase strings."""
        from bibmgr.search.models import EntryType

        for member in EntryType:
            assert member.value == member.name.lower()

    def test_type_comparison(self):
        """Entry types should support equality comparison."""
        from bibmgr.search.models import EntryType

        assert EntryType.ARTICLE == EntryType.ARTICLE
        assert EntryType.ARTICLE != EntryType.BOOK
        assert EntryType.ARTICLE.value == "article"


class TestEntry:
    """Test the Entry model for bibliography entries."""

    def test_minimal_entry_creation(self):
        """Should create entry with minimal required fields."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(key="test2024", type=EntryType.ARTICLE, title="Test Article")

        assert entry.key == "test2024"
        assert entry.type == EntryType.ARTICLE
        assert entry.title == "Test Article"
        assert entry.authors == []
        assert entry.year is None
        assert entry.text != ""  # Should have searchable text

    def test_full_entry_creation(self):
        """Should create entry with all fields."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(
            key="smith2024comprehensive",
            type=EntryType.ARTICLE,
            title="A Comprehensive Study",
            authors=["John Smith", "Jane Doe"],
            year=2024,
            venue="Nature",
            abstract="This is an abstract.",
            keywords=["machine learning", "AI"],
            doi="10.1234/test",
            url="https://example.com",
            pdf_path=Path("/papers/smith2024.pdf"),
        )

        assert entry.key == "smith2024comprehensive"
        assert len(entry.authors) == 2
        assert entry.year == 2024
        assert entry.venue == "Nature"
        assert entry.doi == "10.1234/test"
        assert isinstance(entry.pdf_path, Path)

    def test_entry_immutability(self):
        """Entry should be immutable after creation."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(key="test2024", type=EntryType.ARTICLE, title="Test")

        with pytest.raises((AttributeError, TypeError)):
            entry.title = "Modified"  # type: ignore[misc]

    def test_entry_text_generation(self):
        """Entry should generate searchable text from all fields."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(
            key="test2024",
            type=EntryType.ARTICLE,
            title="Machine Learning Study",
            authors=["Alice", "Bob"],
            venue="ICML",
            abstract="Deep learning research.",
            keywords=["ML", "DL"],
            year=2024,
        )

        # Text should contain all searchable content
        assert "Machine Learning Study" in entry.text
        assert "Alice" in entry.text
        assert "Bob" in entry.text
        assert "ICML" in entry.text
        assert "Deep learning research" in entry.text
        assert "ML" in entry.text
        assert "2024" in entry.text

    def test_entry_serialization(self):
        """Entry should be serializable with msgspec."""
        import msgspec
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(
            key="test2024",
            type=EntryType.ARTICLE,
            title="Test Article",
            authors=["Author"],
            year=2024,
        )

        # Should serialize and deserialize correctly
        encoder = msgspec.json.Encoder()
        decoder = msgspec.json.Decoder(Entry)

        serialized = encoder.encode(entry)
        deserialized = decoder.decode(serialized)

        assert deserialized.key == entry.key
        assert deserialized.title == entry.title
        assert deserialized.authors == entry.authors


class TestSearchHit:
    """Test search result hit model."""

    def test_hit_creation(self):
        """Should create search hit with scoring info."""
        from bibmgr.search.models import Entry, EntryType, SearchHit

        entry = Entry(key="test2024", type=EntryType.ARTICLE, title="Test")

        hit = SearchHit(entry=entry, score=10.5, rank=1)

        assert hit.entry == entry
        assert hit.score == 10.5
        assert hit.rank == 1
        assert hit.text_score == 0.0  # Default
        assert hit.highlights == {}  # Default

    def test_hit_with_components(self):
        """Should track scoring components."""
        from bibmgr.search.models import Entry, EntryType, SearchHit

        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test")

        hit = SearchHit(
            entry=entry,
            score=15.0,
            rank=1,
            text_score=10.0,
            freshness_score=3.0,
            field_boosts={"title_match": 2.0},
        )

        assert hit.text_score == 10.0
        assert hit.freshness_score == 3.0
        assert hit.field_boosts["title_match"] == 2.0

        # Should provide relevance breakdown
        breakdown = hit.relevance_breakdown
        assert breakdown["text_relevance"] == 10.0
        assert breakdown["freshness"] == 3.0
        assert breakdown["title_match"] == 2.0
        assert breakdown["total"] == 15.0

    def test_hit_with_highlights(self):
        """Should store field highlights."""
        from bibmgr.search.models import Entry, EntryType, SearchHit

        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test")

        hit = SearchHit(
            entry=entry,
            score=10.0,
            rank=1,
            highlights={
                "title": ["<mark>Machine Learning</mark> Study"],
                "abstract": ["Research in <mark>ML</mark>"],
            },
        )

        assert "title" in hit.highlights
        assert len(hit.highlights["title"]) == 1
        assert "<mark>" in hit.highlights["title"][0]

    def test_hit_with_explanation(self):
        """Should store scoring explanation."""
        from bibmgr.search.models import Entry, EntryType, SearchHit

        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test")

        hit = SearchHit(
            entry=entry,
            score=10.0,
            rank=1,
            explanation="Matched title field with boost 2.0",
        )

        assert hit.explanation == "Matched title field with boost 2.0"


class TestSearchResult:
    """Test complete search result model."""

    def test_empty_result(self):
        """Should handle empty search results."""
        from bibmgr.search.models import SearchResult

        result = SearchResult(
            query="nonexistent", hits=[], total_found=0, search_time_ms=5.2
        )

        assert result.query == "nonexistent"
        assert result.is_empty
        assert result.total_found == 0
        assert result.top_hit is None
        assert result.search_time_ms == 5.2

    def test_result_with_hits(self):
        """Should store search hits and metadata."""
        from bibmgr.search.models import Entry, EntryType, SearchHit, SearchResult

        entry1 = Entry(key="test1", type=EntryType.ARTICLE, title="First")
        entry2 = Entry(key="test2", type=EntryType.BOOK, title="Second")

        hit1 = SearchHit(entry=entry1, score=10.0, rank=1)
        hit2 = SearchHit(entry=entry2, score=8.0, rank=2)

        result = SearchResult(
            query="test", hits=[hit1, hit2], total_found=2, search_time_ms=12.5
        )

        assert not result.is_empty
        assert result.total_found == 2
        assert len(result.hits) == 2
        assert result.top_hit == hit1
        assert result.top_hit and result.top_hit.score == 10.0

    def test_result_with_facets(self):
        """Should store faceted counts."""
        from bibmgr.search.models import SearchResult

        result = SearchResult(
            query="machine learning",
            hits=[],
            total_found=50,
            search_time_ms=20.0,
            facets={
                "type": {"article": 30, "inproceedings": 15, "book": 5},
                "year": {"2024": 10, "2023": 15, "2022": 25},
            },
        )

        assert "type" in result.facets
        assert result.facets["type"]["article"] == 30

        # Should provide sorted facet values
        type_facets = result.get_facet_values("type")
        assert type_facets[0] == ("article", 30)
        assert type_facets[1] == ("inproceedings", 15)

    def test_result_with_suggestions(self):
        """Should store query suggestions and corrections."""
        from bibmgr.search.models import SearchResult

        result = SearchResult(
            query="machne learnig",
            hits=[],
            total_found=0,
            search_time_ms=5.0,
            suggestions=["machine learning", "machine teaching"],
            spell_corrections=[("machne", "machine"), ("learnig", "learning")],
        )

        assert len(result.suggestions) == 2
        assert "machine learning" in result.suggestions
        assert len(result.spell_corrections) == 2
        assert result.spell_corrections[0] == ("machne", "machine")

    def test_result_with_query_analysis(self):
        """Should store parsed query information."""
        from bibmgr.search.models import SearchResult

        result = SearchResult(
            query="author:smith AND deep learning",
            hits=[],
            total_found=10,
            search_time_ms=15.0,
            parsed_query={
                "terms": ["author:smith", "deep", "learning"],
                "operators": ["AND"],
            },
            expanded_terms=["DL", "neural networks"],
        )

        assert "terms" in result.parsed_query
        assert len(result.parsed_query["terms"]) == 3
        assert len(result.expanded_terms) == 2
        assert "DL" in result.expanded_terms


class TestModelIntegration:
    """Test model interactions and real-world scenarios."""

    def test_complete_search_flow(self):
        """Test complete search result creation flow."""
        from bibmgr.search.models import Entry, EntryType, SearchHit, SearchResult

        # Create entries
        entries = [
            Entry(
                key=f"paper{i}",
                type=EntryType.ARTICLE,
                title=f"Paper {i}",
                year=2020 + i,
            )
            for i in range(5)
        ]

        # Create hits with scoring
        hits = [
            SearchHit(
                entry=entry,
                score=10.0 - i,
                rank=i + 1,
                text_score=8.0 - i,
                freshness_score=2.0 - i * 0.4,
            )
            for i, entry in enumerate(entries)
        ]

        # Create result
        result = SearchResult(
            query="test query",
            hits=hits,
            total_found=5,
            search_time_ms=25.0,
            facets={"year": {str(2020 + i): 1 for i in range(5)}},
        )

        assert result.total_found == 5
        assert len(result.hits) == 5
        assert result.hits[0].rank == 1
        assert result.hits[0].score > result.hits[1].score
        assert len(result.facets["year"]) == 5

    def test_serialization_roundtrip(self):
        """Test serialization of all models."""
        import msgspec
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(
            key="test2024",
            type=EntryType.ARTICLE,
            title="Test Article",
            authors=["Author One", "Author Two"],
            year=2024,
            venue="Test Conference",
            keywords=["test", "example"],
        )

        # Encode and decode
        encoder = msgspec.json.Encoder()
        decoder = msgspec.json.Decoder(Entry)

        json_bytes = encoder.encode(entry)
        decoded = decoder.decode(json_bytes)

        assert decoded.key == entry.key
        assert decoded.type == entry.type
        assert decoded.title == entry.title
        assert decoded.authors == entry.authors
        assert decoded.keywords == entry.keywords
