"""Tests for Whoosh search backend implementation."""

import pytest

from bibmgr.search.backends.whoosh import WhooshBackend

from .test_base import BackendContract


@pytest.fixture
def whoosh_backend(temp_index_dir):
    """Create a Whoosh backend for testing."""
    backend = WhooshBackend(temp_index_dir)
    return backend


@pytest.fixture
def populated_whoosh_backend(whoosh_backend):
    """Create a Whoosh backend with test data."""
    test_documents = [
        {
            "key": "ml2024",
            "title": "Machine Learning Fundamentals",
            "author": "Jane Smith",
            "abstract": "Introduction to machine learning concepts and algorithms",
            "journal": "AI Review",
            "year": 2024,
            "keywords": "machine learning, algorithms, fundamentals",
            "entry_type": "article",
        },
        {
            "key": "dl2023",
            "title": "Deep Learning with Neural Networks",
            "author": "John Doe and Alice Brown",
            "abstract": "Comprehensive guide to deep learning and neural network architectures",
            "journal": "Neural Computing",
            "year": 2023,
            "keywords": "deep learning, neural networks, architecture",
            "entry_type": "article",
        },
        {
            "key": "nlp2022",
            "title": "Natural Language Processing Applications",
            "author": "Bob Johnson",
            "abstract": "Modern applications of NLP in real-world scenarios",
            "booktitle": "Proceedings of NLP Conference",
            "year": 2022,
            "keywords": "nlp, natural language, applications",
            "entry_type": "inproceedings",
        },
        {
            "key": "cv2021",
            "title": "Computer Vision Techniques",
            "author": "Carol White",
            "abstract": "Advanced techniques in computer vision and image processing",
            "publisher": "Tech Books",
            "year": 2021,
            "keywords": "computer vision, image processing, techniques",
            "entry_type": "book",
        },
    ]

    whoosh_backend.index_batch(test_documents)
    whoosh_backend.commit()

    return whoosh_backend


class TestWhooshBackend(BackendContract):
    """Test WhooshBackend implementation using the backend contract."""

    @pytest.fixture
    def backend(self, populated_whoosh_backend):
        """Provide backend fixture for contract tests."""
        return populated_whoosh_backend

    def test_whoosh_backend_initialization(self, temp_index_dir):
        """Whoosh backend should initialize properly."""
        backend = WhooshBackend(temp_index_dir)

        # Should create index directory
        assert temp_index_dir.exists()

        # Should have schema
        assert backend.schema is not None

        # Should have index
        assert backend.index is not None

    def test_schema_has_required_fields(self, whoosh_backend):
        """Schema should include all expected fields."""
        schema = whoosh_backend.schema

        required_fields = [
            "key",
            "title",
            "author",
            "abstract",
            "keywords",
            "journal",
            "booktitle",
            "publisher",
            "year",
            "doi",
            "entry_type",
            "content",
            "added",
            "modified",
        ]

        for field in required_fields:
            assert field in schema, f"Field {field} missing from schema"

    def test_field_types_correct(self, whoosh_backend):
        """Schema fields should have correct types."""
        from whoosh.fields import DATETIME, ID, KEYWORD, NUMERIC, TEXT

        schema = whoosh_backend.schema

        # Text fields with analysis
        assert isinstance(schema["title"], TEXT)
        assert isinstance(schema["abstract"], TEXT)
        assert isinstance(schema["author"], TEXT)

        # Keyword fields (exact match)
        assert isinstance(schema["keywords"], KEYWORD)
        assert isinstance(schema["entry_type"], KEYWORD)

        # ID fields
        assert isinstance(schema["key"], ID)

        # Identifier fields (keyword)
        assert isinstance(schema["doi"], KEYWORD)

        # Numeric fields
        assert isinstance(schema["year"], NUMERIC)

        # Date fields
        assert isinstance(schema["added"], DATETIME)

    def test_document_preparation(self, whoosh_backend):
        """Document should be properly prepared for indexing."""
        entry_data = {
            "key": "test2024",
            "title": "Test Document",
            "author": "Test Author",
            "year": 2024,
            "keywords": ["test", "document"],
            "entry_type": "article",
        }

        doc = whoosh_backend._prepare_document("test2024", entry_data)

        assert doc["key"] == "test2024"
        assert doc["title"] == "Test Document"
        assert doc["author"] == "Test Author"
        assert doc["year"] == 2024
        assert doc["keywords"] == "test,document"  # List converted to comma-separated
        assert doc["entry_type"] == "article"
        assert "content" in doc  # Combined content field should be created

    def test_content_field_creation(self, whoosh_backend):
        """Combined content field should include searchable text."""
        entry_data = {
            "key": "content_test",
            "title": "Machine Learning",
            "author": "John Smith",
            "abstract": "Study of algorithms",
            "keywords": ["ml", "ai"],
        }

        doc = whoosh_backend._prepare_document("content_test", entry_data)

        content = doc["content"]
        assert "Machine Learning" in content
        assert "John Smith" in content
        assert "Study of algorithms" in content
        assert "ml,ai" in content

    def test_search_basic_functionality(self, backend):
        """Basic search should work correctly."""
        from bibmgr.search.backends.base import SearchQuery

        # Search for "machine learning"
        query = SearchQuery(query="machine learning")
        result = backend.search(query)

        assert result.total >= 1
        assert any("ml2024" == match.entry_key for match in result.results)
        assert all(match.score > 0 for match in result.results)

    def test_search_field_specific(self, backend):
        """Field-specific searches should work."""
        from bibmgr.search.backends.base import SearchQuery

        # Search for author
        query = SearchQuery(query="Smith", fields=["author"])
        result = backend.search(query)

        assert result.total >= 1
        assert any("ml2024" == match.entry_key for match in result.results)

    def test_search_phrase_query(self, backend):
        """Phrase queries should work correctly."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query='"machine learning"')
        result = backend.search(query)

        assert result.total >= 1

    def test_search_boolean_operators(self, backend):
        """Boolean operators should work in queries."""
        from bibmgr.search.backends.base import SearchQuery

        # AND query
        query_and = SearchQuery(query="machine AND learning")
        result_and = backend.search(query_and)

        # OR query
        query_or = SearchQuery(query="machine OR vision")
        result_or = backend.search(query_or)

        # NOT query
        query_not = SearchQuery(query="learning NOT deep")
        result_not = backend.search(query_not)

        assert result_and.total >= 1
        assert (
            result_or.total >= 2
        )  # Should find both machine learning and computer vision
        assert result_not.total >= 1

    def test_search_wildcard_queries(self, backend):
        """Wildcard queries should work."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="learn*")
        result = backend.search(query)

        # Should match "learning" in multiple documents
        assert result.total >= 2

    def test_search_numeric_year(self, backend):
        """Numeric year searches should work."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="2024")
        result = backend.search(query)

        assert result.total >= 1
        assert any("ml2024" == match.entry_key for match in result.results)

    def test_search_pagination(self, backend):
        """Pagination should work correctly."""
        from bibmgr.search.backends.base import SearchQuery

        # First page
        query1 = SearchQuery(query="learning", limit=2, offset=0)
        result1 = backend.search(query1)

        # Second page
        query2 = SearchQuery(query="learning", limit=2, offset=2)
        result2 = backend.search(query2)

        # Should have different results (if enough documents)
        if result1.total > 2:
            keys1 = {r.entry_key for r in result1.results}
            keys2 = {r.entry_key for r in result2.results}
            assert keys1 != keys2

    def test_search_with_highlighting(self, backend):
        """Highlighting should work when requested."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="machine learning", highlight=True)
        result = backend.search(query)

        assert result.total >= 1

        # Check if highlighting is provided (implementation specific)
        for match in result.results:
            if match.highlights:
                # Should have highlighted text
                assert isinstance(match.highlights, dict)
                for field, highlights in match.highlights.items():
                    assert isinstance(highlights, list)

    def test_search_faceting(self, backend):
        """Faceting should work when requested."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="learning", facet_fields=["year", "entry_type"])
        result = backend.search(query)

        assert result.total >= 1

        # Check facets (implementation specific)
        if result.facets:
            assert isinstance(result.facets, dict)
            for field, facet_values in result.facets.items():
                assert field in ["year", "entry_type"]
                assert isinstance(facet_values, list)
                for value, count in facet_values:
                    assert isinstance(count, int)
                    assert count > 0

    def test_search_timing(self, backend):
        """Search should report timing information."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="machine learning")
        result = backend.search(query)

        assert result.took_ms is not None
        assert result.took_ms >= 0
        assert isinstance(result.took_ms, int)

    def test_suggest_functionality(self, backend):
        """Suggestion functionality should work."""
        suggestions = backend.suggest("mach", "title", 5)

        assert isinstance(suggestions, list)
        # May or may not find suggestions depending on index content
        if suggestions:
            assert all(isinstance(s, str) for s in suggestions)
            assert len(suggestions) <= 5

    def test_statistics(self, backend):
        """Statistics should provide useful information."""
        stats = backend.get_statistics()

        assert isinstance(stats, dict)
        assert "total_documents" in stats
        assert "index_size_mb" in stats
        assert "fields" in stats
        assert "last_modified" in stats

        assert stats["total_documents"] >= 4  # From populated fixture
        assert stats["index_size_mb"] >= 0
        assert isinstance(stats["fields"], list)
        assert len(stats["fields"]) > 0

    def test_index_size_calculation(self, backend):
        """Index size should be calculated correctly."""
        size = backend._get_index_size()

        assert isinstance(size, int)
        assert size > 0  # Should have some size with indexed documents

    def test_last_modified_tracking(self, backend):
        """Last modified time should be tracked."""
        from datetime import datetime

        last_modified = backend._get_last_modified()

        if last_modified:  # May be None if no files
            assert isinstance(last_modified, datetime)

    def test_error_handling_invalid_field(self, whoosh_backend):
        """Invalid field references should be handled gracefully."""
        from bibmgr.search.backends.base import SearchQuery

        # Query with non-existent field
        query = SearchQuery(query="test", fields=["nonexistent_field"])

        # Should not crash - may return empty results
        result = whoosh_backend.search(query)
        assert isinstance(result.total, int)

    def test_unicode_content_handling(self, whoosh_backend):
        """Unicode content should be handled properly."""
        unicode_doc = {
            "key": "unicode_test",
            "title": "Tëst Dócument with Ünicødé",
            "author": "José García-López",
            "abstract": "Testing unicode: αβγ ñ ü ø å",
            "year": 2024,
        }

        whoosh_backend.index("unicode_test", unicode_doc)
        whoosh_backend.commit()

        from bibmgr.search.backends.base import SearchQuery

        # Should be searchable
        query = SearchQuery(query="Tëst")
        result = whoosh_backend.search(query)

        assert any(match.entry_key == "unicode_test" for match in result.results)

    def test_large_document_handling(self, whoosh_backend):
        """Large documents should be handled efficiently."""
        large_doc = {
            "key": "large_test",
            "title": "Large Document Test",
            "author": "Test Author",
            "abstract": "x" * 10000,  # Large abstract
            "year": 2024,
        }

        whoosh_backend.index("large_test", large_doc)
        whoosh_backend.commit()

        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="Large Document")
        result = whoosh_backend.search(query)

        assert any(match.entry_key == "large_test" for match in result.results)

    def test_special_characters_escaping(self, whoosh_backend):
        """Special characters should be handled properly."""
        special_doc = {
            "key": "special_test",
            "title": "Special Characters: & @ # $ % ^ & * ( )",
            "author": "Test & Author",
            "year": 2024,
        }

        whoosh_backend.index("special_test", special_doc)
        whoosh_backend.commit()

        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="Special Characters")
        result = whoosh_backend.search(query)

        assert any(match.entry_key == "special_test" for match in result.results)

    def test_empty_field_handling(self, whoosh_backend):
        """Empty fields should be handled gracefully."""
        empty_doc = {
            "key": "empty_test",
            "title": "Test Document",
            "author": "",  # Empty string
            "abstract": None,  # None value
            "year": 2024,
        }

        whoosh_backend.index("empty_test", empty_doc)
        whoosh_backend.commit()

        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="Test Document")
        result = whoosh_backend.search(query)

        assert any(match.entry_key == "empty_test" for match in result.results)

    def test_index_persistence(self, temp_index_dir):
        """Index should persist across backend instances."""
        # Create first backend and index data
        backend1 = WhooshBackend(temp_index_dir)
        backend1.index(
            "persist_test",
            {
                "key": "persist_test",
                "title": "Persistence Test",
                "year": 2024,
            },
        )
        backend1.commit()

        # Create second backend instance
        backend2 = WhooshBackend(temp_index_dir)

        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="Persistence Test")
        result = backend2.search(query)

        assert any(match.entry_key == "persist_test" for match in result.results)

    def test_concurrent_search(self, backend):
        """Concurrent searches should work safely."""
        import threading

        from bibmgr.search.backends.base import SearchQuery

        results = []
        errors = []

        def search_worker(query_term):
            try:
                query = SearchQuery(query=query_term)
                result = backend.search(query)
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Start multiple search threads
        threads = []
        for term in ["machine", "learning", "neural", "vision"]:
            t = threading.Thread(target=search_worker, args=(term,))
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Should complete without errors
        assert len(errors) == 0
        assert len(results) == 4

        # All results should be valid
        for result in results:
            assert isinstance(result.total, int)
            assert result.total >= 0

    def test_index_optimization(self, backend):
        """Index optimization should work if supported."""
        # Add optimize method if backend supports it
        if hasattr(backend, "optimize"):
            # Should not raise error
            backend.optimize()

        # Index should still work after optimization
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="machine learning")
        result = backend.search(query)

        assert result.total >= 1
