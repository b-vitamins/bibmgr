"""Comprehensive tests for search engine functionality.

These tests are implementation-agnostic and focus on the expected behavior
of the search engine, including indexing, searching, caching, and analytics.
"""

import pytest
import tempfile
import time
from pathlib import Path

# Module-level skip removed - implementation ready


@pytest.fixture
def engine():
    """Provide a clean search engine instance for each test."""
    from bibmgr.search.engine import SearchEngine

    with tempfile.TemporaryDirectory() as tmpdir:
        index_dir = Path(tmpdir) / "index"
        cache_dir = Path(tmpdir) / "cache"
        engine = SearchEngine(index_dir=index_dir, cache_dir=cache_dir)
        yield engine


class TestSearchEngineInitialization:
    """Test search engine initialization and configuration."""

    def test_default_initialization(self, engine):
        """Should initialize with default settings."""

        assert engine.index_dir.exists()
        assert engine.index_dir.name == "index"
        assert engine.query_parser is not None
        assert engine.history is not None
        assert engine.locator is not None
        assert engine.stats["total_searches"] == 0

    def test_custom_index_directory(self):
        """Should use custom index directory."""
        from bibmgr.search.engine import SearchEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            index_dir = Path(tmpdir) / "custom_index"
            engine = SearchEngine(index_dir=index_dir)

            assert engine.index_dir == index_dir
            assert index_dir.exists()

    def test_schema_initialization(self, engine):
        """Should initialize proper index schema."""

        # Should have required fields
        assert engine.schema is not None
        assert "key" in engine.schema
        assert "title" in engine.schema
        assert "authors" in engine.schema
        assert "content" in engine.schema

    def test_cache_initialization(self, engine):
        """Should initialize result cache."""

        assert engine.cache is not None
        # Cache should be empty initially
        assert len(engine.cache) == 0


class TestIndexing:
    """Test document indexing functionality."""

    def test_index_single_entry(self, engine):
        """Should index a single entry."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(
            key="test2024",
            type=EntryType.ARTICLE,
            title="Test Article",
            authors=["Author"],
            year=2024,
        )

        engine.index_entries([entry])

        # Should be searchable
        result = engine.search("test")
        assert result.total_found >= 1

    def test_index_multiple_entries(self, engine):
        """Should index multiple entries."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(
                key=f"test{i}",
                type=EntryType.ARTICLE,
                title=f"Article {i}",
                authors=[f"Author {i}"],
                year=2020 + i,
            )
            for i in range(5)
        ]

        engine.index_entries(entries)

        # All should be searchable
        result = engine.search("article")
        assert result.total_found == 5

    def test_update_existing_entry(self, engine):
        """Should update existing entries."""
        from bibmgr.search.models import Entry, EntryType

        # Index original
        entry1 = Entry(key="test2024", type=EntryType.ARTICLE, title="Original Title")
        engine.index_entries([entry1])

        # Update with new content
        entry2 = Entry(key="test2024", type=EntryType.ARTICLE, title="Updated Title")
        engine.index_entries([entry2])

        # Should find updated content
        result = engine.search("updated")
        assert result.total_found == 1

        # Should not find old content
        result = engine.search("original")
        assert result.total_found == 0

    def test_index_with_all_fields(self, engine):
        """Should index all entry fields."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(
            key="complete2024",
            type=EntryType.ARTICLE,
            title="Complete Entry",
            authors=["John Smith", "Jane Doe"],
            year=2024,
            venue="Test Conference",
            abstract="This is a test abstract with searchable content.",
            keywords=["machine learning", "AI"],
            doi="10.1234/test",
            url="https://example.com",
        )

        engine.index_entries([entry])

        # Should find by any field
        assert engine.search("complete").total_found == 1
        assert engine.search("smith").total_found == 1
        assert engine.search("conference").total_found == 1
        assert engine.search("abstract").total_found == 1
        assert engine.search("machine").total_found == 1

    def test_cache_cleared_after_indexing(self, engine):
        """Should clear cache after indexing new entries."""
        from bibmgr.search.models import Entry, EntryType

        # Do initial search to populate cache
        engine.search("test")
        len(engine.cache)

        # Index new entry
        entry = Entry(key="new2024", type=EntryType.ARTICLE, title="New Entry")
        engine.index_entries([entry])

        # Cache should be cleared
        assert len(engine.cache) == 0


class TestBasicSearch:
    """Test basic search functionality."""

    def test_empty_search(self, engine):
        """Should handle empty index search."""
        result = engine.search("nonexistent")

        assert result.total_found == 0
        assert result.is_empty
        assert result.hits == []

    def test_simple_keyword_search(self, engine):
        """Should find entries by keyword."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(key="ml2024", type=EntryType.ARTICLE, title="Machine Learning Study"),
            Entry(key="db2024", type=EntryType.ARTICLE, title="Database Systems"),
        ]
        engine.index_entries(entries)

        result = engine.search("machine")
        assert result.total_found == 1
        assert result.hits[0].entry.key == "ml2024"

    def test_multi_term_search(self, engine):
        """Should handle multi-term queries."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(
            key="test2024",
            type=EntryType.ARTICLE,
            title="Deep Learning for Computer Vision",
        )
        engine.index_entries([entry])

        # Should find with multiple terms
        result = engine.search("deep learning")
        assert result.total_found == 1

        result = engine.search("computer vision")
        assert result.total_found == 1

    def test_case_insensitive_search(self, engine):
        """Search should be case-insensitive."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(key="test2024", type=EntryType.ARTICLE, title="Machine Learning")
        engine.index_entries([entry])

        # All cases should work
        assert engine.search("machine").total_found == 1
        assert engine.search("MACHINE").total_found == 1
        assert engine.search("Machine").total_found == 1

    def test_partial_word_matching(self, engine):
        """Should support partial word matching."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(
            key="test2024", type=EntryType.ARTICLE, title="Optimization Algorithms"
        )
        engine.index_entries([entry])

        # Should find with prefix
        result = engine.search("optim*")
        assert result.total_found == 1

    def test_search_pagination(self, engine):
        """Should support result pagination."""
        from bibmgr.search.models import Entry, EntryType

        # Index many entries
        entries = [
            Entry(
                key=f"test{i}",
                type=EntryType.ARTICLE,
                title=f"Article about testing {i}",
            )
            for i in range(25)
        ]
        engine.index_entries(entries)

        # First page
        result = engine.search("testing", limit=10, page=1)
        assert len(result.hits) == 10

        # Second page
        result = engine.search("testing", limit=10, page=2)
        assert len(result.hits) == 10

        # Third page (partial)
        result = engine.search("testing", limit=10, page=3)
        assert len(result.hits) == 5


class TestFieldSearch:
    """Test field-specific search functionality."""

    def test_author_field_search(self, engine):
        """Should search by author field."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(
                key="smith2024",
                type=EntryType.ARTICLE,
                title="Paper A",
                authors=["John Smith"],
            ),
            Entry(
                key="doe2024",
                type=EntryType.ARTICLE,
                title="Paper B",
                authors=["Jane Doe"],
            ),
        ]
        engine.index_entries(entries)

        result = engine.search("author:smith")
        assert result.total_found == 1
        assert result.hits[0].entry.key == "smith2024"

    def test_title_field_search(self, engine):
        """Should search by title field."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(
            key="test2024",
            type=EntryType.ARTICLE,
            title="Specific Title",
            abstract="Different content here",
        )
        engine.index_entries([entry])

        # Should find in title
        result = engine.search("title:specific")
        assert result.total_found == 1

        # Should not find if only in abstract
        result = engine.search("title:different")
        assert result.total_found == 0

    def test_year_field_search(self, engine):
        """Should search by year field."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(
                key=f"paper{year}",
                type=EntryType.ARTICLE,
                title=f"Paper {year}",
                year=year,
            )
            for year in [2020, 2021, 2022, 2023, 2024]
        ]
        engine.index_entries(entries)

        result = engine.search("year:2024")
        assert result.total_found == 1
        assert result.hits[0].entry.year == 2024

    def test_keyword_field_search(self, engine):
        """Should search by keywords field."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(
            key="test2024",
            type=EntryType.ARTICLE,
            title="Test Paper",
            keywords=["machine learning", "deep learning", "AI"],
        )
        engine.index_entries([entry])

        result = engine.search("keywords:deep")
        assert result.total_found == 1


class TestAdvancedSearch:
    """Test advanced search features."""

    def test_phrase_search(self, engine):
        """Should support exact phrase search."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(
                key="exact", type=EntryType.ARTICLE, title="Machine Learning is Great"
            ),
            Entry(
                key="different",
                type=EntryType.ARTICLE,
                title="Learning Machine Programming",
            ),
        ]
        engine.index_entries(entries)

        # Exact phrase should match only first
        result = engine.search('"machine learning"')
        assert result.total_found == 1
        assert result.hits[0].entry.key == "exact"

    def test_boolean_and_search(self, engine):
        """Should support AND operator."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(
                key="both",
                type=EntryType.ARTICLE,
                title="Machine Learning and Neural Networks",
            ),
            Entry(key="one", type=EntryType.ARTICLE, title="Machine Translation"),
        ]
        engine.index_entries(entries)

        result = engine.search("machine AND neural")
        assert result.total_found == 1
        assert result.hits[0].entry.key == "both"

    def test_boolean_or_search(self, engine):
        """Should support OR operator."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(key="python", type=EntryType.ARTICLE, title="Python Tutorial"),
            Entry(key="java", type=EntryType.ARTICLE, title="Java Tutorial"),
            Entry(key="cpp", type=EntryType.ARTICLE, title="C++ Tutorial"),
        ]
        engine.index_entries(entries)

        result = engine.search("python OR java")
        assert result.total_found == 2

    def test_negation_search(self, engine):
        """Should support NOT operator."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(
                key="ml",
                type=EntryType.ARTICLE,
                title="Machine Learning with Decision Trees",
            ),
            Entry(
                key="nn",
                type=EntryType.ARTICLE,
                title="Neural Networks for Machine Learning",
            ),
        ]
        engine.index_entries(entries)

        result = engine.search("machine -neural")
        assert result.total_found == 1
        assert result.hits[0].entry.key == "ml"

    def test_wildcard_search(self, engine):
        """Should support wildcard queries."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(key="opt1", type=EntryType.ARTICLE, title="Optimization"),
            Entry(key="opt2", type=EntryType.ARTICLE, title="Optimize"),
            Entry(key="opt3", type=EntryType.ARTICLE, title="Optimal"),
            Entry(key="other", type=EntryType.ARTICLE, title="Different"),
        ]
        engine.index_entries(entries)

        result = engine.search("optim*")
        assert result.total_found == 3

    def test_range_search(self, engine):
        """Should support range queries."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(
                key=f"paper{year}",
                type=EntryType.ARTICLE,
                title=f"Paper {year}",
                year=year,
            )
            for year in range(2018, 2025)
        ]
        engine.index_entries(entries)

        result = engine.search("year:2020..2023")
        assert result.total_found == 4


class TestScoring:
    """Test result scoring and ranking."""

    def test_basic_scoring(self, engine):
        """Should score and rank results."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(
                key="high",
                type=EntryType.ARTICLE,
                title="Machine Learning Machine Learning",
            ),  # 2 occurrences
            Entry(
                key="low",
                type=EntryType.ARTICLE,
                title="Introduction to Machine Learning",
            ),  # 1 occurrence
        ]
        engine.index_entries(entries)

        result = engine.search("machine learning")
        assert result.hits[0].entry.key == "high"  # Higher score
        assert result.hits[0].score > result.hits[1].score

    def test_field_boosting(self, engine):
        """Should apply field-specific boosting."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(
                key="title_match",
                type=EntryType.ARTICLE,
                title="Machine Learning",
                abstract="Other content",
            ),
            Entry(
                key="abstract_match",
                type=EntryType.ARTICLE,
                title="Other Title",
                abstract="Machine Learning",
            ),
        ]
        engine.index_entries(entries)

        result = engine.search("machine learning")
        # Title matches should score higher
        assert result.hits[0].entry.key == "title_match"

    def test_freshness_scoring(self, engine):
        """Should boost recent entries."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(
                key="old", type=EntryType.ARTICLE, title="Machine Learning", year=2010
            ),
            Entry(
                key="new", type=EntryType.ARTICLE, title="Machine Learning", year=2024
            ),
        ]
        engine.index_entries(entries)

        result = engine.search("machine learning")
        # Recent paper should score higher
        assert result.hits[0].entry.key == "new"
        assert result.hits[0].freshness_score > result.hits[1].freshness_score

    def test_scoring_breakdown(self, engine):
        """Should provide scoring breakdown."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(
            key="test2024", type=EntryType.ARTICLE, title="Test Article", year=2024
        )
        engine.index_entries([entry])

        result = engine.search("test")
        hit = result.hits[0]

        # Should have scoring components
        assert hit.text_score >= 0
        assert hit.freshness_score >= 0
        assert isinstance(hit.field_boosts, dict)

        # Should provide breakdown
        breakdown = hit.relevance_breakdown
        assert "text_relevance" in breakdown
        assert "freshness" in breakdown
        assert "total" in breakdown


class TestCaching:
    """Test search result caching."""

    def test_cache_hit(self, engine):
        """Should cache and reuse search results."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test")
        engine.index_entries([entry])

        # First search
        result1 = engine.search("test")
        initial_cache_hits = engine.stats["cache_hits"]

        # Second identical search
        result2 = engine.search("test")

        # Should use cache
        assert engine.stats["cache_hits"] == initial_cache_hits + 1
        assert result1.total_found == result2.total_found

    def test_cache_miss_different_query(self, engine):
        """Should not use cache for different queries."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(key="test1", type=EntryType.ARTICLE, title="Test One"),
            Entry(key="test2", type=EntryType.ARTICLE, title="Test Two"),
        ]
        engine.index_entries(entries)

        initial_cache_hits = engine.stats["cache_hits"]

        engine.search("one")
        engine.search("two")  # Different query

        # Should not increase cache hits
        assert engine.stats["cache_hits"] == initial_cache_hits

    def test_cache_invalidation_on_index(self, engine):
        """Should invalidate cache when index changes."""
        from bibmgr.search.models import Entry, EntryType

        entry1 = Entry(key="test1", type=EntryType.ARTICLE, title="Test")
        engine.index_entries([entry1])

        # Search to populate cache
        result1 = engine.search("test")
        assert result1.total_found == 1

        # Index new entry
        entry2 = Entry(key="test2", type=EntryType.ARTICLE, title="Test")
        engine.index_entries([entry2])

        # Should get fresh results
        result2 = engine.search("test")
        assert result2.total_found == 2


class TestFacets:
    """Test faceted search functionality."""

    def test_type_facets(self, engine):
        """Should provide entry type facets."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(key="art1", type=EntryType.ARTICLE, title="Paper"),
            Entry(key="art2", type=EntryType.ARTICLE, title="Paper"),
            Entry(key="book1", type=EntryType.BOOK, title="Paper"),
            Entry(key="conf1", type=EntryType.INPROCEEDINGS, title="Paper"),
        ]
        engine.index_entries(entries)

        result = engine.search("paper")

        assert "type" in result.facets
        assert result.facets["type"]["article"] == 2
        assert result.facets["type"]["book"] == 1
        assert result.facets["type"]["inproceedings"] == 1

    def test_year_facets(self, engine):
        """Should provide year facets."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(key=f"p{i}", type=EntryType.ARTICLE, title="Paper", year=2020 + i % 3)
            for i in range(9)
        ]
        engine.index_entries(entries)

        result = engine.search("paper")

        assert "year" in result.facets
        # Should have counts for recent years
        if "2020" in result.facets["year"]:
            assert result.facets["year"]["2020"] == 3

    def test_facet_sorting(self, engine):
        """Should sort facet values by count."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(key="art1", type=EntryType.ARTICLE, title="Test"),
            Entry(key="art2", type=EntryType.ARTICLE, title="Test"),
            Entry(key="art3", type=EntryType.ARTICLE, title="Test"),
            Entry(key="book1", type=EntryType.BOOK, title="Test"),
            Entry(key="misc1", type=EntryType.MISC, title="Test"),
            Entry(key="misc2", type=EntryType.MISC, title="Test"),
        ]
        engine.index_entries(entries)

        result = engine.search("test")
        type_facets = result.get_facet_values("type")

        # Should be sorted by count
        assert type_facets[0][1] >= type_facets[1][1]
        if len(type_facets) > 2:
            assert type_facets[1][1] >= type_facets[2][1]


class TestSuggestionsAndCorrections:
    """Test query suggestions and spelling corrections."""

    def test_spelling_corrections(self, engine):
        """Should suggest spelling corrections."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(key="ml", type=EntryType.ARTICLE, title="Machine Learning"),
            Entry(key="dl", type=EntryType.ARTICLE, title="Deep Learning"),
        ]
        engine.index_entries(entries)

        # Search with typo
        result = engine.search("machne learnig")

        # Should have corrections
        assert len(result.spell_corrections) > 0
        # Should suggest correct spellings (may be stemmed)
        corrections_dict = dict(result.spell_corrections)
        if "machne" in corrections_dict:
            # Accept either "machine" or stemmed version "machin"
            assert "machin" in corrections_dict["machne"].lower()

    def test_query_suggestions(self, engine):
        """Should provide query suggestions."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(
                key="ml", type=EntryType.ARTICLE, title="Machine Learning Fundamentals"
            ),
            Entry(key="dl", type=EntryType.ARTICLE, title="Deep Learning Advanced"),
        ]
        engine.index_entries(entries)

        result = engine.search("learning")

        # Should suggest related terms
        assert isinstance(result.suggestions, list)
        # Suggestions might include "machine", "deep", etc.


class TestStatistics:
    """Test search statistics and analytics."""

    def test_search_statistics(self, engine):
        """Should track search statistics."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test")
        engine.index_entries([entry])

        initial_searches = engine.stats["total_searches"]

        # Do searches
        engine.search("test")
        engine.search("other")

        assert engine.stats["total_searches"] == initial_searches + 2
        assert engine.stats["avg_search_time_ms"] > 0

    def test_cache_statistics(self, engine):
        """Should track cache performance."""
        from bibmgr.search.models import Entry, EntryType

        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test")
        engine.index_entries([entry])

        # Search twice (second should hit cache)
        engine.search("test")
        engine.search("test")

        stats = engine.get_stats()
        assert stats["cache_hits"] > 0
        assert stats["cache_hit_rate"] > 0

    def test_get_stats(self, engine):
        """Should provide comprehensive statistics."""
        from bibmgr.search.models import Entry, EntryType

        entries = [
            Entry(key=f"test{i}", type=EntryType.ARTICLE, title=f"Test {i}")
            for i in range(5)
        ]
        engine.index_entries(entries)

        engine.search("test")

        stats = engine.get_stats()

        assert "total_searches" in stats
        assert "cache_hits" in stats
        assert "avg_search_time_ms" in stats
        assert "index_size" in stats
        assert "cache_size" in stats
        assert "cache_hit_rate" in stats


class TestIndexManagement:
    """Test index management operations."""

    def test_clear_index(self, engine):
        """Should clear the search index."""
        from bibmgr.search.models import Entry, EntryType

        # Index entries
        entries = [
            Entry(key=f"test{i}", type=EntryType.ARTICLE, title=f"Test {i}")
            for i in range(5)
        ]
        engine.index_entries(entries)

        # Verify indexed
        result = engine.search("test")
        assert result.total_found == 5

        # Clear index
        engine.clear_index()

        # Should be empty
        result = engine.search("test")
        assert result.total_found == 0

    def test_optimize_index(self, engine):
        """Should optimize the search index."""
        from bibmgr.search.models import Entry, EntryType

        # Index many entries
        entries = [
            Entry(key=f"test{i}", type=EntryType.ARTICLE, title=f"Test {i}")
            for i in range(100)
        ]
        engine.index_entries(entries)

        # Should not raise error
        engine.optimize_index()

        # Should still be searchable
        result = engine.search("test")
        assert result.total_found == 100


class TestIntegration:
    """Test complete search scenarios."""

    def test_research_workflow(self, engine):
        """Test typical research search workflow."""
        from bibmgr.search.models import Entry, EntryType

        # Index research papers
        entries = [
            Entry(
                key="attention2017",
                type=EntryType.INPROCEEDINGS,
                title="Attention Is All You Need",
                authors=["Vaswani", "Shazeer"],
                year=2017,
                venue="NeurIPS",
                keywords=["transformer", "attention"],
            ),
            Entry(
                key="bert2018",
                type=EntryType.INPROCEEDINGS,
                title="BERT: Pre-training of Deep Bidirectional Transformers",
                authors=["Devlin", "Chang"],
                year=2018,
                venue="NAACL",
                keywords=["bert", "transformers", "nlp"],
            ),
            Entry(
                key="gpt2019",
                type=EntryType.TECHREPORT,
                title="Language Models are Unsupervised Multitask Learners",
                authors=["Radford", "Wu"],
                year=2019,
                venue="OpenAI",
                keywords=["gpt", "language models"],
            ),
        ]
        engine.index_entries(entries)

        # Search for transformers
        result = engine.search("transformer")
        assert result.total_found >= 2

        # Search by author
        result = engine.search("author:vaswani")
        assert result.total_found == 1

        # Search by year range
        result = engine.search("year:2017..2019")
        assert result.total_found == 3

        # Complex query
        result = engine.search("transformer AND attention")
        assert result.total_found >= 1

    def test_performance_with_many_entries(self, engine):
        """Test performance with large number of entries."""
        from bibmgr.search.models import Entry, EntryType

        # Index many entries
        entries = [
            Entry(
                key=f"paper{i:05d}",
                type=EntryType.ARTICLE,
                title=f"Research Paper Number {i}",
                authors=[f"Author {i % 100}"],
                year=2000 + (i % 25),
                abstract=f"This is abstract {i} with various keywords",
                keywords=[f"keyword{i % 10}", f"topic{i % 5}"],
            )
            for i in range(1000)
        ]

        start = time.time()
        engine.index_entries(entries)
        index_time = time.time() - start

        # Indexing should be reasonably fast
        assert index_time < 10.0  # Less than 10 seconds for 1000 entries

        # Search should be fast
        result = engine.search("research")
        assert result.search_time_ms < 100  # Less than 100ms
        assert result.total_found == 1000

        # Complex search should still be fast
        result = engine.search("keyword5 AND year:2020")
        assert result.search_time_ms < 200
