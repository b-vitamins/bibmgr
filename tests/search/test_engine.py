"""Tests for the search engine."""

import time
from unittest.mock import Mock, patch

import pytest

from bibmgr.core.fields import EntryType
from bibmgr.core.models import Entry
from bibmgr.search.backends.base import (
    BackendResult,
    QueryError,
    SearchBackend,
    SearchQuery,
)
from bibmgr.search.backends.base import (
    SearchMatch as BackendMatch,
)
from bibmgr.search.backends.memory import MemoryBackend
from bibmgr.search.engine import (
    SearchEngine,
    SearchEngineBuilder,
    SearchService,
    create_default_engine,
    create_memory_engine,
)
from bibmgr.search.indexing import FieldConfiguration
from bibmgr.search.query import QueryParser, TermQuery
from bibmgr.search.results import (
    SearchResultCollection,
    SortOrder,
)


@pytest.fixture
def sample_entries():
    """Create sample bibliography entries for testing."""
    return [
        Entry(
            key="ml2024",
            type=EntryType.ARTICLE,
            title="Machine Learning Fundamentals",
            author="Jane Smith",
            journal="AI Review",
            year=2024,
            abstract="Introduction to machine learning concepts and algorithms",
            keywords=("machine learning", "algorithms", "fundamentals"),
        ),
        Entry(
            key="dl2023",
            type=EntryType.ARTICLE,
            title="Deep Learning with Neural Networks",
            author="John Doe and Alice Brown",
            journal="Neural Computing",
            year=2023,
            abstract="Comprehensive guide to deep learning and machine learning architectures",
            keywords=("deep learning", "machine learning", "neural networks"),
        ),
        Entry(
            key="nlp2022",
            type=EntryType.INPROCEEDINGS,
            title="Natural Language Processing Applications",
            author="Bob Johnson",
            booktitle="Proceedings of NLP Conference",
            year=2022,
            abstract="Modern applications of NLP in real-world scenarios",
            keywords=("nlp", "natural language", "applications"),
        ),
        Entry(
            key="cv2021",
            type=EntryType.BOOK,
            title="Computer Vision Techniques",
            author="Carol White",
            publisher="Tech Books",
            year=2021,
            abstract="Advanced techniques in computer vision and image processing",
            keywords=("computer vision", "image processing", "techniques"),
        ),
    ]


@pytest.fixture
def mock_backend():
    """Create a mock search backend."""
    backend = Mock(spec=SearchBackend)

    # Default search result
    backend.search.return_value = BackendResult(
        results=[
            BackendMatch(entry_key="ml2024", score=2.5),
            BackendMatch(entry_key="dl2023", score=1.8),
        ],
        total=2,
        facets={
            "year": [(2024, 1), (2023, 1)],
            "entry_type": [("article", 2)],
        },
        took_ms=15,
    )

    # Other methods
    backend.index.return_value = None
    backend.index_batch.return_value = None
    backend.delete.return_value = True
    backend.clear.return_value = None
    backend.commit.return_value = None
    backend.get_statistics.return_value = {
        "total_documents": 4,
        "index_size_mb": 0.5,
    }
    backend.suggest.return_value = ["machine", "machine learning"]

    # Set class name for statistics
    backend.__class__.__name__ = "MockBackend"

    return backend


@pytest.fixture
def mock_repository(sample_entries):
    """Create a mock repository."""
    repository = Mock()

    # Create a mapping of keys to entries
    entry_map = {entry.key: entry for entry in sample_entries}

    # Mock find method to return entries by key
    repository.find.side_effect = lambda key: entry_map.get(key)

    return repository


@pytest.fixture
def search_engine(mock_backend, mock_repository):
    """Create a search engine with mock backend and repository."""
    return SearchEngine(
        backend=mock_backend,
        enable_highlighting=True,
        enable_query_expansion=True,
        repository=mock_repository,
    )


@pytest.fixture
def memory_engine():
    """Create a search engine with real memory backend."""
    return create_memory_engine()


class TestSearchEngine:
    """Test SearchEngine class."""

    def test_engine_initialization_default(self):
        """Engine should initialize with default components."""
        engine = SearchEngine()

        assert isinstance(engine.backend, MemoryBackend)
        assert isinstance(engine.field_config, FieldConfiguration)
        assert engine.indexer is not None
        assert isinstance(engine.query_parser, QueryParser)
        assert engine.query_expander is not None
        assert engine.highlighter is not None
        assert engine.enable_highlighting is True
        assert engine.enable_query_expansion is True
        assert engine.default_limit == 20
        assert engine.max_limit == 1000

    def test_engine_initialization_custom(self, mock_backend):
        """Engine should accept custom components."""
        field_config = FieldConfiguration()

        engine = SearchEngine(
            backend=mock_backend,
            field_config=field_config,
            enable_highlighting=False,
            enable_query_expansion=False,
        )

        assert engine.backend is mock_backend
        assert engine.field_config is field_config
        assert engine.enable_highlighting is False
        assert engine.enable_query_expansion is False
        assert engine.query_expander is None
        assert engine.highlighter is None

    def test_index_single_entry(self, search_engine, mock_backend, sample_entries):
        """Indexing single entry should work."""
        entry = sample_entries[0]

        search_engine.index_entry(entry)

        # Backend should be called with indexed document
        mock_backend.index.assert_called_once()
        call_args = mock_backend.index.call_args[0]
        assert call_args[0] == "ml2024"  # entry key
        assert isinstance(call_args[1], dict)  # indexed document
        assert call_args[1]["key"] == "ml2024"
        assert call_args[1]["title"] == "Machine Learning Fundamentals"
        assert search_engine._index_size == 1

    def test_index_multiple_entries(self, search_engine, mock_backend, sample_entries):
        """Batch indexing should work efficiently."""
        search_engine.index_entries(sample_entries)

        # Backend batch method should be called
        mock_backend.index_batch.assert_called_once()
        documents = mock_backend.index_batch.call_args[0][0]
        assert len(documents) == 4
        assert all("key" in doc for doc in documents)
        assert search_engine._index_size == 4

    def test_remove_entry(self, search_engine, mock_backend):
        """Removing entry should work."""
        search_engine._index_size = 5

        result = search_engine.remove_entry("test_key")

        mock_backend.delete.assert_called_once_with("test_key")
        assert result is True
        assert search_engine._index_size == 4

    def test_remove_entry_not_found(self, search_engine, mock_backend):
        """Removing non-existent entry should return False."""
        mock_backend.delete.return_value = False
        search_engine._index_size = 5

        result = search_engine.remove_entry("nonexistent")

        assert result is False
        assert search_engine._index_size == 5  # Unchanged

    def test_clear_index(self, search_engine, mock_backend):
        """Clearing index should work."""
        search_engine._index_size = 10

        search_engine.clear_index()

        mock_backend.clear.assert_called_once()
        assert search_engine._index_size == 0

    def test_commit(self, search_engine, mock_backend):
        """Commit should delegate to backend."""
        search_engine.commit()

        mock_backend.commit.assert_called_once()

    def test_search_basic(self, search_engine, mock_backend, sample_entries):
        """Basic search should work correctly."""
        # Index some entries so the engine knows the collection size
        search_engine._index_size = len(sample_entries)

        results = search_engine.search("machine learning")

        # Check backend was called
        mock_backend.search.assert_called_once()
        search_query = mock_backend.search.call_args[0][0]
        assert isinstance(search_query, SearchQuery)
        assert search_query.limit == 20
        assert search_query.offset == 0

        # Check results
        assert isinstance(results, SearchResultCollection)
        assert results.query == "machine learning"
        assert len(results.matches) == 2
        assert results.total == 2
        # BM25 ranker should have re-ranked based on entry content
        # The first match should still be ml2024 since it has "machine learning" in title
        assert results.matches[0].entry_key == "ml2024"
        # Score should be positive from BM25 calculation
        assert results.matches[0].score > 0

        # Check facets
        assert len(results.facets) == 2
        year_facet = results.get_facet("year")
        assert year_facet is not None
        assert len(year_facet.values) == 2

        # Check statistics
        assert results.statistics is not None
        assert results.statistics.backend_name == "MockBackend"
        assert results.statistics.search_time_ms == 15

    def test_search_with_parameters(self, search_engine, mock_backend):
        """Search with custom parameters should work."""
        results = search_engine.search(
            "test query",
            limit=50,
            offset=10,
            fields=["title", "abstract"],
            filters={"year": 2024},
            sort_by=SortOrder.DATE_DESC,
            enable_facets=False,
            enable_suggestions=False,
            expand_query=False,
            highlight_results=False,
        )

        # Check search query parameters
        search_query = mock_backend.search.call_args[0][0]
        assert search_query.limit == 50
        assert search_query.offset == 10
        assert search_query.fields == ["title", "abstract"]
        assert search_query.filters == {"year": 2024}
        assert search_query.facet_fields is None
        assert search_query.highlight is False

        # Results should not have facets or suggestions
        assert len(results.facets) == 0
        assert len(results.suggestions) == 0

    def test_search_empty_query(self, search_engine):
        """Empty query should return empty results."""
        results = search_engine.search("")

        assert isinstance(results, SearchResultCollection)
        assert results.query == ""
        assert len(results.matches) == 0
        assert results.total == 0

    def test_search_whitespace_query(self, search_engine):
        """Whitespace-only query should return empty results."""
        results = search_engine.search("   \t\n   ")

        assert len(results.matches) == 0
        assert results.total == 0

    def test_search_with_limit_validation(self, search_engine, mock_backend):
        """Search should validate and clamp limit values."""
        # Test max limit
        search_engine.search("test", limit=2000)
        search_query = mock_backend.search.call_args[0][0]
        assert search_query.limit == 1000  # Clamped to max

        # Test min limit
        mock_backend.reset_mock()
        search_engine.search("test", limit=0)
        search_query = mock_backend.search.call_args[0][0]
        assert search_query.limit == 1

        # Test negative limit
        mock_backend.reset_mock()
        search_engine.search("test", limit=-5)
        search_query = mock_backend.search.call_args[0][0]
        assert search_query.limit == 1

    def test_search_with_offset_validation(self, search_engine, mock_backend):
        """Search should validate offset values."""
        search_engine.search("test", offset=-10)
        search_query = mock_backend.search.call_args[0][0]
        assert search_query.offset == 0  # Negative clamped to 0

    def test_search_with_query_expansion(self, search_engine, mock_backend):
        """Query expansion should work when enabled."""
        with patch.object(search_engine.query_expander, "expand_query") as mock_expand:
            mock_expand.return_value = TermQuery("expanded query")

            search_engine.search("ml", expand_query=True)

            mock_expand.assert_called_once()
            search_query = mock_backend.search.call_args[0][0]
            assert isinstance(search_query.query, TermQuery)
            assert search_query.query.term == "expanded query"

    def test_search_without_query_expansion(self, search_engine, mock_backend):
        """Query expansion should be skippable."""
        with patch.object(search_engine.query_expander, "expand_query") as mock_expand:
            search_engine.search("test", expand_query=False)

            mock_expand.assert_not_called()

    def test_search_with_suggestions(self, search_engine):
        """Search should generate suggestions for low result counts."""
        # Mock low result count
        search_engine.backend.search.return_value = BackendResult(
            results=[BackendMatch(entry_key="ml2024", score=1.0)],
            total=1,
            took_ms=10,
        )

        results = search_engine.search("machine learing", enable_suggestions=True)

        # Should have suggestions for low result count
        assert len(results.suggestions) > 0

        # Check suggestion types
        suggestion_types = {s.suggestion_type for s in results.suggestions}
        assert "relaxation" in suggestion_types or "spelling" in suggestion_types

    def test_search_field_expansion_suggestion(self, search_engine):
        """Search should suggest field expansion for field queries."""
        search_engine.backend.search.return_value = BackendResult(
            results=[],
            total=0,
            took_ms=5,
        )

        results = search_engine.search("title:nonexistent", enable_suggestions=True)

        # Should suggest removing field restriction
        field_suggestions = [
            s for s in results.suggestions if s.suggestion_type == "field_expansion"
        ]
        assert len(field_suggestions) > 0
        assert ":" not in field_suggestions[0].suggestion  # Colon should be removed

    def test_search_with_highlighting(self, search_engine, mock_backend):
        """Search with highlighting should request highlights from backend."""
        search_engine.search("test", highlight_results=True)

        search_query = mock_backend.search.call_args[0][0]
        assert search_query.highlight is True

    def test_search_without_highlighting_engine(self):
        """Engine without highlighter should handle highlighting gracefully."""
        engine = SearchEngine(enable_highlighting=False)
        engine.backend = Mock()
        engine.backend.search.return_value = BackendResult([], 0)
        engine.backend.__class__.__name__ = "MockBackend"

        # Should not crash
        results = engine.search("test", highlight_results=True)
        assert isinstance(results, SearchResultCollection)

    def test_search_with_sorting(self, search_engine):
        """Search results should be sortable."""
        # Create matches with entries for sorting
        entry1 = Entry(
            key="a",
            type=EntryType.ARTICLE,
            title="Beta Article",
            author="Zulu Author",
            year=2020,
        )
        entry2 = Entry(
            key="b",
            type=EntryType.ARTICLE,
            title="Alpha Article",
            author="Alpha Author",
            year=2024,
        )

        matches = [
            BackendMatch(entry_key="a", score=1.0, entry=entry1),
            BackendMatch(entry_key="b", score=2.0, entry=entry2),
        ]

        results = SearchResultCollection(
            matches=matches,
            total=2,
            query="test",
        )

        # Test different sort orders
        sorted_results = results.sort_by(SortOrder.TITLE_ASC)
        assert sorted_results.matches[0].entry is not None
        assert sorted_results.matches[0].entry.title == "Alpha Article"
        assert sorted_results.matches[1].entry is not None
        assert sorted_results.matches[1].entry.title == "Beta Article"

        # Create fresh results for author sorting
        results2 = SearchResultCollection(
            matches=[
                BackendMatch(entry_key="a", score=1.0, entry=entry1),
                BackendMatch(entry_key="b", score=2.0, entry=entry2),
            ],
            total=2,
            query="test",
        )
        sorted_results = results2.sort_by(SortOrder.AUTHOR_ASC)
        assert sorted_results.matches[0].entry is not None
        assert sorted_results.matches[0].entry.author == "Alpha Author"
        assert sorted_results.matches[1].entry is not None
        assert sorted_results.matches[1].entry.author == "Zulu Author"

        # Create fresh results for date sorting
        results3 = SearchResultCollection(
            matches=[
                BackendMatch(entry_key="a", score=1.0, entry=entry1),
                BackendMatch(entry_key="b", score=2.0, entry=entry2),
            ],
            total=2,
            query="test",
        )
        sorted_results = results3.sort_by(SortOrder.DATE_DESC)
        assert sorted_results.matches[0].entry is not None
        assert sorted_results.matches[0].entry.year == 2024
        assert sorted_results.matches[1].entry is not None
        assert sorted_results.matches[1].entry.year == 2020

    def test_search_error_handling(self, search_engine, mock_backend):
        """Search should handle backend errors gracefully."""
        mock_backend.search.side_effect = QueryError("Invalid query")

        results = search_engine.search("bad query")

        # Should return empty results with error suggestion
        assert isinstance(results, SearchResultCollection)
        assert len(results.matches) == 0
        assert len(results.suggestions) == 1
        assert results.suggestions[0].suggestion_type == "error"
        assert results.suggestions[0].description is not None
        assert "Invalid query" in results.suggestions[0].description

    def test_search_timing(self, search_engine):
        """Search should track timing correctly."""
        results = search_engine.search("test")

        assert search_engine._last_query_time > 0
        assert results.statistics is not None
        assert results.statistics.search_time_ms >= 0

    def test_suggest_method(self, search_engine, mock_backend):
        """Suggest method should work correctly."""
        suggestions = search_engine.suggest("mach", "title", 5)

        mock_backend.suggest.assert_called_once_with("mach", "title", 5)
        assert suggestions == ["machine", "machine learning"]

    def test_suggest_no_backend_support(self, search_engine):
        """Suggest should handle backends without suggest method."""
        # Remove suggest method
        delattr(search_engine.backend, "suggest")

        suggestions = search_engine.suggest("test")

        assert suggestions == []

    def test_more_like_this(self, search_engine, mock_backend):
        """More-like-this search should work."""
        mock_backend.more_like_this.return_value = BackendResult(
            results=[
                BackendMatch(entry_key="similar1", score=0.9),
                BackendMatch(entry_key="similar2", score=0.7),
            ],
            total=2,
            took_ms=20,
        )

        results = search_engine.more_like_this("ml2024", limit=5, min_score=0.5)

        mock_backend.more_like_this.assert_called_once_with("ml2024", 5, 0.5)
        assert isinstance(results, SearchResultCollection)
        assert results.query == "more_like:ml2024"
        assert len(results.matches) == 2
        assert results.matches[0].score == 0.9

    def test_more_like_this_no_backend_support(self, search_engine):
        """More-like-this should handle backends without support."""
        # Remove more_like_this method
        delattr(search_engine.backend, "more_like_this")

        results = search_engine.more_like_this("test")

        assert isinstance(results, SearchResultCollection)
        assert len(results.matches) == 0
        assert results.query == "more_like:test"

    def test_more_like_this_error_handling(self, search_engine, mock_backend):
        """More-like-this should handle errors gracefully."""
        mock_backend.more_like_this.side_effect = Exception("Backend error")

        results = search_engine.more_like_this("test")

        assert isinstance(results, SearchResultCollection)
        assert len(results.matches) == 0

    def test_validate_query(self, search_engine):
        """Query validation should work."""
        # Valid query
        errors = search_engine.validate_query("machine learning")
        assert len(errors) == 0

        # Invalid query (empty term in boolean query)
        # This will create a TermQuery with empty term which should fail validation
        errors = search_engine.validate_query('""')  # Empty quoted string
        assert len(errors) > 0

    def test_validate_query_parse_error(self, search_engine):
        """Query validation should handle parse errors."""
        with patch.object(search_engine.query_parser, "parse") as mock_parse:
            mock_parse.side_effect = Exception("Parse error")

            errors = search_engine.validate_query("bad query")

            assert len(errors) == 1
            assert "Parse error" in errors[0]

    def test_get_statistics(self, search_engine, mock_backend):
        """Get statistics should aggregate information."""
        search_engine._index_size = 42
        search_engine._last_query_time = 123

        stats = search_engine.get_statistics()

        assert isinstance(stats, dict)
        assert "engine" in stats
        assert "backend" in stats
        assert "field_config" in stats

        # Check engine stats
        assert stats["engine"]["index_size"] == 42
        assert stats["engine"]["last_query_time_ms"] == 123
        assert stats["engine"]["backend_type"] == "MockBackend"
        assert stats["engine"]["highlighting_enabled"] is True
        assert stats["engine"]["query_expansion_enabled"] is True

        # Check backend stats
        assert stats["backend"]["total_documents"] == 4
        assert stats["backend"]["index_size_mb"] == 0.5

        # Check field config stats
        assert stats["field_config"]["total_fields"] > 0
        assert stats["field_config"]["searchable_fields"] > 0
        assert stats["field_config"]["facet_fields"] > 0


class TestSearchEngineIntegration:
    """Integration tests with real memory backend."""

    def test_full_search_workflow(self, memory_engine, sample_entries):
        """Test complete search workflow with real backend."""
        # Index entries
        memory_engine.index_entries(sample_entries)
        memory_engine.commit()

        # Search for machine learning
        results = memory_engine.search("machine learning")

        assert results.total >= 2
        assert any(m.entry_key == "ml2024" for m in results.matches)
        assert any(m.entry_key == "dl2023" for m in results.matches)

        # Search with field
        results = memory_engine.search("author:Smith")
        assert results.total >= 1
        assert any(m.entry_key == "ml2024" for m in results.matches)

        # Search with year filter
        results = memory_engine.search("learning", filters={"year": 2024})
        assert all(m.entry_key == "ml2024" for m in results.matches)

        # Remove entry
        assert memory_engine.remove_entry("ml2024") is True
        memory_engine.commit()

        # Verify removal
        results = memory_engine.search("machine learning fundamentals")
        assert not any(m.entry_key == "ml2024" for m in results.matches)

    def test_complex_queries(self, memory_engine, sample_entries):
        """Test complex query patterns."""
        memory_engine.index_entries(sample_entries)
        memory_engine.commit()

        # Boolean queries
        results = memory_engine.search("machine AND learning")
        assert results.total >= 1

        results = memory_engine.search("machine OR vision")
        assert results.total >= 2

        results = memory_engine.search("learning NOT deep")
        assert results.total >= 1
        assert not any(m.entry_key == "dl2023" for m in results.matches)

        # Phrase query
        results = memory_engine.search('"machine learning"')
        assert results.total >= 1

        # Wildcard query
        results = memory_engine.search("learn*")
        assert results.total >= 2

        # Range query
        results = memory_engine.search("year:[2022 TO 2023]")
        assert results.total >= 2
        assert all(
            2022 <= int(m.entry_key[2:6]) <= 2023
            for m in results.matches
            if m.entry_key[2:6].isdigit()
        )

    def test_pagination(self, memory_engine, sample_entries):
        """Test result pagination."""
        memory_engine.index_entries(sample_entries)
        memory_engine.commit()

        # First page
        page1 = memory_engine.search("learning", limit=2, offset=0)
        assert len(page1.matches) <= 2

        # Second page
        page2 = memory_engine.search("learning", limit=2, offset=2)

        # Pages should not overlap
        page1_keys = {m.entry_key for m in page1.matches}
        page2_keys = {m.entry_key for m in page2.matches}
        assert page1_keys.isdisjoint(page2_keys)

    def test_performance(self, memory_engine):
        """Test search performance with larger dataset."""
        # Create many entries
        entries = []
        for i in range(100):
            entry = Entry(
                key=f"entry{i:04d}",
                type=EntryType.ARTICLE,
                title=f"Document {i} about {'machine' if i % 2 == 0 else 'deep'} learning",
                author=f"Author {i % 10}",
                year=2020 + (i % 5),
                abstract=f"Abstract for document {i} with various keywords",
            )
            entries.append(entry)

        # Index all entries
        start_time = time.time()
        memory_engine.index_entries(entries)
        memory_engine.commit()
        index_time = time.time() - start_time

        # Indexing should be reasonably fast
        assert index_time < 1.0  # Less than 1 second for 100 entries

        # Search performance
        start_time = time.time()
        results = memory_engine.search("machine learning")
        search_time = time.time() - start_time

        # Search should be fast
        assert search_time < 0.1  # Less than 100ms
        assert results.total == 50  # Half have "machine" in title


class TestSearchEngineBuilder:
    """Test SearchEngineBuilder class."""

    def test_builder_defaults(self):
        """Builder should have sensible defaults."""
        builder = SearchEngineBuilder()

        assert builder.backend is None
        assert builder.field_config is None
        assert builder.enable_highlighting is True
        assert builder.enable_query_expansion is True

    def test_builder_with_backend(self, mock_backend):
        """Builder should accept backend."""
        engine = SearchEngineBuilder().with_backend(mock_backend).build()

        assert engine.backend is mock_backend

    def test_builder_with_field_config(self):
        """Builder should accept field configuration."""
        config = FieldConfiguration()
        engine = SearchEngineBuilder().with_field_config(config).build()

        assert engine.field_config is config

    def test_builder_with_highlighting(self):
        """Builder should configure highlighting."""
        engine = SearchEngineBuilder().with_highlighting(False).build()

        assert engine.enable_highlighting is False
        assert engine.highlighter is None

    def test_builder_with_query_expansion(self):
        """Builder should configure query expansion."""
        engine = SearchEngineBuilder().with_query_expansion(False).build()

        assert engine.enable_query_expansion is False
        assert engine.query_expander is None

    def test_builder_chaining(self, mock_backend):
        """Builder methods should be chainable."""
        config = FieldConfiguration()

        engine = (
            SearchEngineBuilder()
            .with_backend(mock_backend)
            .with_field_config(config)
            .with_highlighting(False)
            .with_query_expansion(True)
            .build()
        )

        assert engine.backend is mock_backend
        assert engine.field_config is config
        assert engine.enable_highlighting is False
        assert engine.enable_query_expansion is True

    def test_create_default_engine(self):
        """create_default_engine should work."""
        engine = create_default_engine()

        assert isinstance(engine, SearchEngine)
        assert isinstance(engine.backend, MemoryBackend)
        assert engine.enable_highlighting is True
        assert engine.enable_query_expansion is True

    def test_create_memory_engine(self):
        """create_memory_engine should work with parameters."""
        engine = create_memory_engine(
            enable_highlighting=False, enable_query_expansion=False
        )

        assert isinstance(engine, SearchEngine)
        assert isinstance(engine.backend, MemoryBackend)
        assert engine.enable_highlighting is False
        assert engine.enable_query_expansion is False


class TestSearchService:
    """Test SearchService convenience class."""

    @pytest.fixture
    def search_service(self, mock_backend):
        """Create search service with mock backend."""
        engine = SearchEngine(backend=mock_backend)
        return SearchService(engine)

    def test_service_initialization(self):
        """Service should initialize with default engine."""
        service = SearchService()

        assert isinstance(service.engine, SearchEngine)
        assert isinstance(service.engine.backend, MemoryBackend)
        assert len(service._entry_cache) == 0

    def test_service_with_custom_engine(self, mock_backend):
        """Service should accept custom engine."""
        engine = SearchEngine(backend=mock_backend)
        service = SearchService(engine)

        assert service.engine is engine

    def test_add_entries(self, search_service, sample_entries):
        """Adding entries should index and cache them."""
        service = search_service

        service.add_entries(sample_entries)

        # Should cache entries
        assert len(service._entry_cache) == 4
        assert service._entry_cache["ml2024"] == sample_entries[0]

        # Should index entries
        service.engine.backend.index_batch.assert_called_once()
        service.engine.backend.commit.assert_called_once()

    def test_search_entries_with_hydration(self, search_service, sample_entries):
        """Search should hydrate results with cached entries."""
        service = search_service
        service.add_entries(sample_entries)

        # Mock backend to return keys we have cached
        service.engine.backend.search.return_value = BackendResult(
            results=[
                BackendMatch(entry_key="ml2024", score=1.0),
                BackendMatch(entry_key="dl2023", score=0.8),
            ],
            total=2,
        )

        results = service.search_entries("test", include_entries=True)

        # Results should have entry objects
        assert results.matches[0].entry is not None
        assert results.matches[0].entry.key == "ml2024"
        assert results.matches[0].entry.title == "Machine Learning Fundamentals"

        assert results.matches[1].entry is not None
        assert results.matches[1].entry.key == "dl2023"

    def test_search_entries_without_hydration(self, search_service, sample_entries):
        """Search can skip entry hydration."""
        service = search_service
        service.add_entries(sample_entries)

        results = service.search_entries("test", include_entries=False)

        # Results should not have entry objects
        for match in results.matches:
            assert match.entry is None

    def test_search_entries_parameters(self, search_service):
        """Search should pass through all parameters."""
        service = search_service

        with patch.object(service.engine, "search") as mock_search:
            mock_search.return_value = SearchResultCollection([], 0)

            service.search_entries(
                "test query",
                limit=30,
                offset=10,
                fields=["title"],
                filters={"year": 2024},
                sort_by=SortOrder.DATE_ASC,
            )

            mock_search.assert_called_once_with(
                "test query",
                30,  # limit as positional arg
                10,  # offset as positional arg
                fields=["title"],
                filters={"year": 2024},
                sort_by=SortOrder.DATE_ASC,
            )

    def test_remove_entry(self, search_service, sample_entries):
        """Removing entry should update cache and index."""
        service = search_service
        service.add_entries(sample_entries)

        result = service.remove_entry("ml2024")

        # Should remove from cache
        assert "ml2024" not in service._entry_cache
        assert len(service._entry_cache) == 3

        # Should remove from index
        service.engine.backend.delete.assert_called_with("ml2024")
        assert result is True

    def test_clear_all(self, search_service, sample_entries):
        """Clear all should empty cache and index."""
        service = search_service
        service.add_entries(sample_entries)

        service.clear_all()

        # Cache should be empty
        assert len(service._entry_cache) == 0

        # Index should be cleared
        service.engine.backend.clear.assert_called_once()

    def test_get_entry(self, search_service, sample_entries):
        """Get entry should retrieve from cache."""
        service = search_service
        service.add_entries(sample_entries)

        entry = service.get_entry("ml2024")
        assert entry is not None
        assert entry.key == "ml2024"

        # Non-existent entry
        assert service.get_entry("nonexistent") is None

    def test_get_cached_entry_count(self, search_service, sample_entries):
        """Should return correct cache count."""
        service = search_service

        assert service.get_cached_entry_count() == 0

        service.add_entries(sample_entries)
        assert service.get_cached_entry_count() == 4

        service.remove_entry("ml2024")
        assert service.get_cached_entry_count() == 3

    def test_get_search_statistics(self, search_service):
        """Should return comprehensive statistics."""
        service = search_service

        stats = service.get_search_statistics()

        assert isinstance(stats, dict)
        assert "service" in stats
        assert stats["service"]["cached_entries"] == 0

        # Should include engine statistics
        assert "engine" in stats
        assert "backend" in stats
        assert "field_config" in stats
