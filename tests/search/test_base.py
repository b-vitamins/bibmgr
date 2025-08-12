"""Tests for search backend abstraction."""

import pytest

from bibmgr.search.backends.base import (
    BackendResult,
    IndexError,
    QueryError,
    SearchBackend,
    SearchError,
    SearchMatch,
    SearchQuery,
)


class TestSearchQuery:
    """Test SearchQuery data class."""

    def test_create_minimal_query(self):
        """Create query with minimal parameters."""
        query = SearchQuery(query="test")

        assert query.query == "test"
        assert query.limit == 20
        assert query.offset == 0
        assert query.fields == []
        assert query.facet_fields is None
        assert query.highlight is False
        assert query.sort_by is None
        assert query.filters == {}

    def test_create_full_query(self):
        """Create query with all parameters."""
        query = SearchQuery(
            query="machine learning",
            limit=50,
            offset=10,
            fields=["title", "abstract"],
            facet_fields=["year", "type"],
            highlight=True,
            sort_by="year",
            filters={"year": [2020, 2021]},
        )

        assert query.query == "machine learning"
        assert query.limit == 50
        assert query.offset == 10
        assert query.fields == ["title", "abstract"]
        assert query.facet_fields == ["year", "type"]
        assert query.highlight is True
        assert query.sort_by == "year"
        assert query.filters == {"year": [2020, 2021]}


class TestSearchMatch:
    """Test SearchMatch data class."""

    def test_create_minimal_match(self):
        """Create match with minimal data."""
        match = SearchMatch(entry_key="test123", score=0.95)

        assert match.entry_key == "test123"
        assert match.score == 0.95
        assert match.highlights is None

    def test_create_match_with_highlights(self):
        """Create match with highlighted fields."""
        highlights = {
            "title": ["Machine <mark>Learning</mark> Applications"],
            "abstract": ["Uses <mark>learning</mark> algorithms"],
        }

        match = SearchMatch(
            entry_key="ml2024",
            score=1.5,
            highlights=highlights,
        )

        assert match.entry_key == "ml2024"
        assert match.score == 1.5
        assert match.highlights == highlights
        assert match.highlights is not None
        assert len(match.highlights["title"]) == 1
        assert "<mark>" in match.highlights["title"][0]


class TestBackendResult:
    """Test BackendResult data class."""

    def test_create_minimal_result(self):
        """Create result with minimal data."""
        matches = [
            SearchMatch("key1", 1.0),
            SearchMatch("key2", 0.8),
        ]

        result = BackendResult(results=matches, total=2)

        assert len(result.results) == 2
        assert result.total == 2
        assert result.facets is None
        assert result.suggestions is None
        assert result.took_ms is None

    def test_create_full_result(self):
        """Create result with all fields."""
        matches = [SearchMatch("key1", 1.0)]
        facets = {
            "year": [(2024, 10), (2023, 8), (2022, 5)],
            "type": [("article", 15), ("book", 8)],
        }

        result = BackendResult(
            results=matches,
            total=23,
            facets=facets,
            suggestions=["machine learning", "deep learning"],
            took_ms=42,
        )

        assert len(result.results) == 1
        assert result.total == 23
        assert result.facets is not None
        assert len(result.facets) == 2
        assert len(result.facets["year"]) == 3
        assert result.suggestions == ["machine learning", "deep learning"]
        assert result.took_ms == 42


class TestSearchExceptions:
    """Test search-specific exceptions."""

    def test_search_error_base(self):
        """SearchError is the base exception."""
        error = SearchError("Something went wrong")

        assert str(error) == "Something went wrong"
        assert isinstance(error, Exception)

    def test_index_error(self):
        """IndexError for indexing problems."""
        error = IndexError("Failed to index document")

        assert isinstance(error, SearchError)
        assert str(error) == "Failed to index document"

    def test_query_error(self):
        """QueryError for query problems."""
        error = QueryError("Invalid query syntax")

        assert isinstance(error, SearchError)
        assert str(error) == "Invalid query syntax"


class BackendContract:
    """Contract tests that all search backends must pass.

    This class is designed to be inherited by concrete backend test classes.
    Each backend implementation should have a test class that inherits from
    this contract and provides a 'backend' fixture.
    """

    def test_index_single_document(self, backend: SearchBackend):
        """index() should store a single document."""
        fields = {
            "key": "test123",
            "title": "Test Document",
            "author": "Test Author",
            "year": 2024,
        }

        backend.index("test123", fields)
        backend.commit()

        # Should be searchable
        query = SearchQuery(query="Test Document")
        result = backend.search(query)

        assert result.total >= 1
        assert any(match.entry_key == "test123" for match in result.results)

    def test_index_batch_documents(self, backend: SearchBackend):
        """index_batch() should efficiently store multiple documents."""
        documents = [
            {
                "key": f"doc{i}",
                "title": f"Document {i}",
                "author": f"Author {i}",
                "year": 2020 + i,
            }
            for i in range(5)
        ]

        backend.index_batch(documents)
        backend.commit()

        # All should be searchable
        query = SearchQuery(query="Document")
        result = backend.search(query)

        assert result.total >= 5

    def test_update_existing_document(self, backend: SearchBackend):
        """Indexing with same key should update the document."""
        backend.index(
            "update_test",
            {"key": "update_test", "title": "Machine Learning Fundamentals"},
        )
        backend.commit()

        backend.index(
            "update_test", {"key": "update_test", "title": "Deep Neural Networks"}
        )
        backend.commit()

        query1 = SearchQuery(query="Fundamentals")
        result1 = backend.search(query1)

        query2 = SearchQuery(query="Neural")
        result2 = backend.search(query2)

        assert not any(match.entry_key == "update_test" for match in result1.results)
        assert any(match.entry_key == "update_test" for match in result2.results)

    def test_delete_document(self, backend: SearchBackend):
        """delete() should remove document from index."""
        backend.index("delete_test", {"key": "delete_test", "title": "To Be Deleted"})
        backend.commit()

        query = SearchQuery(query="To Be Deleted")
        result1 = backend.search(query)
        assert any(match.entry_key == "delete_test" for match in result1.results)

        assert backend.delete("delete_test") is True
        backend.commit()

        result2 = backend.search(query)
        assert not any(match.entry_key == "delete_test" for match in result2.results)

    def test_delete_nonexistent_document(self, backend: SearchBackend):
        """delete() should handle non-existent documents gracefully."""
        assert backend.delete("nonexistent_key") is False

    def test_clear_index(self, backend: SearchBackend):
        """clear() should remove all documents."""
        documents = [{"key": f"clear{i}", "title": f"Clear Test {i}"} for i in range(3)]
        backend.index_batch(documents)
        backend.commit()

        query = SearchQuery(query="Clear Test")
        result1 = backend.search(query)
        assert result1.total >= 3

        backend.clear()
        backend.commit()

        result2 = backend.search(query)
        assert result2.total == 0

    def test_search_empty_index(self, backend: SearchBackend):
        """Search on empty index should return empty results."""
        backend.clear()
        backend.commit()

        query = SearchQuery(query="anything")
        result = backend.search(query)

        assert result.total == 0
        assert len(result.results) == 0

    def test_search_with_limit_offset(self, backend: SearchBackend):
        """Search should respect limit and offset for pagination."""
        documents = [
            {"key": f"page{i:03d}", "title": f"Page Test Document {i:03d}"}
            for i in range(25)
        ]
        backend.index_batch(documents)
        backend.commit()

        query1 = SearchQuery(query="Page Test", limit=10, offset=0)
        result1 = backend.search(query1)

        assert len(result1.results) <= 10
        assert result1.total >= 25

        query2 = SearchQuery(query="Page Test", limit=10, offset=10)
        result2 = backend.search(query2)

        assert len(result2.results) <= 10

        keys1 = {r.entry_key for r in result1.results}
        keys2 = {r.entry_key for r in result2.results}
        assert keys1.isdisjoint(keys2)

    def test_search_field_specific(self, backend: SearchBackend):
        """Search should work on specific fields."""
        backend.index(
            "field1",
            {
                "key": "field1",
                "title": "Quantum Computing",
                "abstract": "Classical computing methods",
            },
        )
        backend.index(
            "field2",
            {
                "key": "field2",
                "title": "Classical Music",
                "abstract": "Quantum mechanics in music",
            },
        )
        backend.commit()

        query_title = SearchQuery(query="Quantum", fields=["title"])
        result_title = backend.search(query_title)

        assert any(m.entry_key == "field1" for m in result_title.results)
        assert not any(m.entry_key == "field2" for m in result_title.results)

    def test_commit_behavior(self, backend: SearchBackend):
        """Changes should be visible after commit."""
        backend.index("commit_test", {"key": "commit_test", "title": "Uncommitted"})

        backend.commit()

        query = SearchQuery(query="Uncommitted")
        result = backend.search(query)

        assert any(match.entry_key == "commit_test" for match in result.results)

    def test_get_statistics(self, backend: SearchBackend):
        """get_statistics() should return index information."""
        backend.clear()
        backend.commit()

        documents = [
            {"key": f"stat{i}", "title": f"Statistics Test {i}"} for i in range(5)
        ]
        backend.index_batch(documents)
        backend.commit()

        stats = backend.get_statistics()

        assert isinstance(stats, dict)
        assert "total_documents" in stats
        assert stats["total_documents"] >= 5

    def test_suggest_completions(self, backend: SearchBackend):
        """suggest() should return completions if supported."""
        backend.index("sug1", {"key": "sug1", "title": "Machine Learning"})
        backend.index("sug2", {"key": "sug2", "title": "Machine Translation"})
        backend.index("sug3", {"key": "sug3", "title": "Deep Learning"})
        backend.commit()

        suggestions = backend.suggest("mach", "title", 5)

        if suggestions:
            assert isinstance(suggestions, list)
            assert all(isinstance(s, str) for s in suggestions)
            assert any("machine" in s.lower() for s in suggestions)

    def test_error_handling_invalid_query(self, backend: SearchBackend):
        """Invalid queries should raise QueryError."""
        query = SearchQuery(query=None)

        try:
            result = backend.search(query)
            assert result.total == 0
        except QueryError:
            pass

    def test_special_characters_in_content(self, backend: SearchBackend):
        """Backend should handle special characters in content."""
        special_doc = {
            "key": "special",
            "title": "Special: & Characters! @ Test #",
            "author": "José García-López",
            "abstract": "Testing «quotes» and ñ unicode",
        }

        backend.index("special", special_doc)
        backend.commit()

        query = SearchQuery(query="Special Characters")
        result = backend.search(query)

        assert any(match.entry_key == "special" for match in result.results)

    def test_numeric_field_search(self, backend: SearchBackend):
        """Backend should support numeric field searches if applicable."""
        docs = [
            {"key": "old", "title": "Old Paper", "year": 1990},
            {"key": "medium", "title": "Medium Paper", "year": 2010},
            {"key": "new", "title": "New Paper", "year": 2024},
        ]

        for doc in docs:
            backend.index(doc["key"], doc)
        backend.commit()

        query = SearchQuery(query="Paper")
        result = backend.search(query)

        assert result.total >= 3

    def test_concurrent_indexing(self, backend: SearchBackend):
        """Backend should handle concurrent indexing safely."""
        import threading

        def index_docs(start_id):
            for i in range(5):
                doc_id = f"concurrent_{start_id}_{i}"
                backend.index(
                    doc_id,
                    {
                        "key": doc_id,
                        "title": f"Concurrent Document {start_id}-{i}",
                    },
                )

        threads = []
        for i in range(3):
            t = threading.Thread(target=index_docs, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        backend.commit()

        query = SearchQuery(query="Concurrent Document")
        result = backend.search(query)

        assert result.total >= 15


class TestSearchBackendBase:
    """Test the abstract SearchBackend class itself."""

    def test_backend_is_abstract(self):
        """SearchBackend cannot be instantiated directly."""
        try:
            SearchBackend()  # type: ignore
            assert False, "Should have raised TypeError"
        except TypeError as e:
            assert "Can't instantiate abstract class" in str(e)

    def test_backend_defines_interface(self):
        """SearchBackend defines required methods."""
        required_methods = [
            "index",
            "index_batch",
            "search",
            "delete",
            "clear",
            "commit",
            "get_statistics",
        ]

        for method in required_methods:
            assert hasattr(SearchBackend, method)
            assert getattr(SearchBackend, method).__isabstractmethod__

    def test_optional_methods_have_defaults(self):
        """Optional methods should have default implementations."""

        class MinimalBackend(SearchBackend):
            def index(self, entry_key: str, fields: dict) -> None:
                pass

            def index_batch(self, documents: list) -> None:
                pass

            def search(self, query: SearchQuery) -> BackendResult:
                return BackendResult(results=[], total=0)

            def delete(self, entry_key: str) -> bool:
                return False

            def clear(self) -> None:
                pass

            def commit(self) -> None:
                pass

            def get_statistics(self) -> dict:
                return {}

        backend = MinimalBackend()

        assert backend.suggest("test", "field", 10) == []

        with pytest.raises(NotImplementedError):
            backend.more_like_this("key", 10, 0.5)
