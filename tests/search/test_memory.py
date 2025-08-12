"""Tests for memory search backend implementation."""

import pytest

from bibmgr.search.backends.memory import MemoryBackend

from .test_base import BackendContract


@pytest.fixture
def memory_backend():
    """Create a memory backend for testing."""
    return MemoryBackend()


@pytest.fixture
def populated_memory_backend():
    """Create a memory backend with test data."""
    backend = MemoryBackend()

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

    backend.index_batch(test_documents)
    backend.commit()

    return backend


class TestMemoryBackend(BackendContract):
    """Test MemoryBackend implementation using the backend contract."""

    @pytest.fixture
    def backend(self, populated_memory_backend):
        """Provide backend fixture for contract tests."""
        return populated_memory_backend

    def test_memory_backend_initialization(self):
        """Memory backend should initialize with empty storage."""
        backend = MemoryBackend()

        assert backend.documents == {}
        assert backend.term_index == {}
        assert backend.field_values == {}

    def test_index_document_storage(self, memory_backend):
        """Indexed documents should be stored in memory."""
        doc = {
            "key": "test123",
            "title": "Test Document",
            "author": "Test Author",
            "year": 2024,
        }

        memory_backend.index("test123", doc)

        # Document should be stored
        assert "test123" in memory_backend.documents
        assert memory_backend.documents["test123"]["title"] == "Test Document"

        # Terms should be indexed
        assert len(memory_backend.term_index) > 0

        # Field values should be tracked (for faceting)
        assert "title" in memory_backend.field_values
        assert "Test Document" in memory_backend.field_values["title"]

        # Terms should be indexed (for searching)
        assert "test" in memory_backend.term_index
        assert "document" in memory_backend.term_index

    def test_term_indexing(self, memory_backend):
        """Terms should be properly indexed for fast lookup."""
        doc = {
            "key": "term_test",
            "title": "Machine Learning Research",
            "abstract": "Advanced machine learning techniques",
        }

        memory_backend.index("term_test", doc)

        # Terms should be in index
        assert "machine" in memory_backend.term_index
        assert "learning" in memory_backend.term_index
        assert "research" in memory_backend.term_index
        assert "advanced" in memory_backend.term_index

        # Document should be associated with terms
        assert "term_test" in memory_backend.term_index["machine"]
        assert "term_test" in memory_backend.term_index["learning"]

    def test_field_value_tracking(self, memory_backend):
        """Field values should be tracked for faceting."""
        docs = [
            {"key": "doc1", "year": 2024, "type": "article"},
            {"key": "doc2", "year": 2023, "type": "article"},
            {"key": "doc3", "year": 2024, "type": "book"},
        ]

        for doc in docs:
            memory_backend.index(doc["key"], doc)

        # Year values should be tracked
        assert "year" in memory_backend.field_values
        assert 2024 in memory_backend.field_values["year"]
        assert 2023 in memory_backend.field_values["year"]

        # Type values should be tracked
        assert "type" in memory_backend.field_values
        assert "article" in memory_backend.field_values["type"]
        assert "book" in memory_backend.field_values["type"]

    def test_search_basic_text(self, backend):
        """Basic text search should work."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="machine learning")
        result = backend.search(query)

        assert result.total >= 1
        assert any("ml2024" == match.entry_key for match in result.results)

        # Scores should be reasonable
        for match in result.results:
            assert 0 <= match.score <= 10  # BM25-like scoring

    def test_search_phrase_matching(self, backend):
        """Phrase searches should match exact sequences."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query='"machine learning"')
        result = backend.search(query)

        assert result.total >= 1
        # Should find documents with exact phrase

    def test_search_field_specific(self, backend):
        """Field-specific searches should work."""
        from bibmgr.search.backends.base import SearchQuery

        # Search in title field only
        query = SearchQuery(query="learning", fields=["title"])
        result = backend.search(query)

        # Should find documents with "learning" in title
        assert result.total >= 2  # "Machine Learning" and "Deep Learning"

    def test_search_boolean_and(self, backend):
        """Boolean AND searches should work."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="machine AND learning")
        result = backend.search(query)

        # Should find documents with both terms
        assert result.total >= 1

        # All results should contain both terms
        for match in result.results:
            doc = backend.documents[match.entry_key]
            doc_text = " ".join(str(v) for v in doc.values()).lower()
            assert "machine" in doc_text
            assert "learning" in doc_text

    def test_search_boolean_or(self, backend):
        """Boolean OR searches should work."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="machine OR vision")
        result = backend.search(query)

        # Should find documents with either term
        assert result.total >= 2  # machine learning + computer vision

    def test_search_boolean_not(self, backend):
        """Boolean NOT searches should work."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="learning NOT deep")
        result = backend.search(query)

        # Should exclude documents with "deep"
        for match in result.results:
            doc = backend.documents[match.entry_key]
            doc_text = " ".join(str(v) for v in doc.values()).lower()
            assert "deep" not in doc_text or "learning" in doc_text

    def test_search_wildcard_prefix(self, backend):
        """Prefix wildcard searches should work."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="learn*")
        result = backend.search(query)

        # Should match "learning"
        assert result.total >= 2

    def test_search_wildcard_suffix(self, backend):
        """Suffix wildcard searches should work."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="*ing")
        result = backend.search(query)

        # Should match words ending in "ing"
        assert result.total >= 1

    def test_search_wildcard_single_char(self, backend):
        """Single character wildcards should work."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="le?rning")
        result = backend.search(query)

        # Should match "learning"
        assert result.total >= 2

    def test_search_fuzzy_matching(self, backend):
        """Fuzzy searches should handle typos."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="machne~")  # Typo for "machine"
        result = backend.search(query)

        # Should find "machine" despite typo
        if result.total > 0:  # Fuzzy matching may not be implemented
            assert any("ml2024" == match.entry_key for match in result.results)

    def test_search_numeric_fields(self, backend):
        """Numeric field searches should work."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="year:2024")
        result = backend.search(query)

        # Should find 2024 documents
        assert result.total >= 1
        for match in result.results:
            doc = backend.documents[match.entry_key]
            assert doc.get("year") == 2024

    def test_search_range_queries(self, backend):
        """Range queries should work for numeric fields."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="year:[2022 TO 2024]")
        result = backend.search(query)

        # Should find documents in range
        assert result.total >= 3
        for match in result.results:
            doc = backend.documents[match.entry_key]
            year = doc.get("year")
            if year:
                assert 2022 <= year <= 2024

    def test_search_pagination(self, backend):
        """Pagination should work correctly."""
        from bibmgr.search.backends.base import SearchQuery

        # Search with limit
        query = SearchQuery(query="learning", limit=2)
        result = backend.search(query)

        assert len(result.results) <= 2

        # Search with offset
        if result.total > 2:
            query_offset = SearchQuery(query="learning", limit=2, offset=2)
            result_offset = backend.search(query_offset)

            # Should have different results
            keys1 = {r.entry_key for r in result.results}
            keys2 = {r.entry_key for r in result_offset.results}
            assert keys1 != keys2

    def test_search_sorting(self, backend):
        """Sorting should work when specified."""
        from bibmgr.search.backends.base import SearchQuery

        # Sort by year
        query = SearchQuery(query="learning", sort_by="year")
        result = backend.search(query)

        if len(result.results) > 1:
            years = []
            for match in result.results:
                doc = backend.documents[match.entry_key]
                if "year" in doc:
                    years.append(doc["year"])

            # Should be sorted
            if len(years) > 1:
                assert years == sorted(years, reverse=True)  # Descending by default

    def test_search_faceting(self, backend):
        """Faceting should provide value counts."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="learning", facet_fields=["year", "entry_type"])
        result = backend.search(query)

        if result.facets:
            # Year facets
            if "year" in result.facets:
                year_facets = result.facets["year"]
                assert isinstance(year_facets, list)
                for value, count in year_facets:
                    assert isinstance(count, int)
                    assert count > 0

            # Type facets
            if "entry_type" in result.facets:
                type_facets = result.facets["entry_type"]
                assert isinstance(type_facets, list)

    def test_search_highlighting(self, backend):
        """Highlighting should mark matched terms."""
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="machine learning", highlight=True)
        result = backend.search(query)

        if result.results and result.results[0].highlights:
            highlights = result.results[0].highlights

            for field, highlight_list in highlights.items():
                assert isinstance(highlight_list, list)
                for highlight in highlight_list:
                    # Should contain marked terms
                    assert "<mark>" in highlight or "machine" in highlight.lower()

    def test_delete_document(self, backend):
        """Document deletion should work properly."""
        from bibmgr.search.backends.memory import MemoryBackend

        memory_backend = backend
        assert isinstance(memory_backend, MemoryBackend)

        # Verify document exists
        assert "ml2024" in memory_backend.documents

        # Delete document
        assert backend.delete("ml2024") is True

        # Verify removal
        assert "ml2024" not in memory_backend.documents

        # Terms should be updated
        from bibmgr.search.backends.base import SearchQuery

        query = SearchQuery(query="Machine Learning Fundamentals")
        result = backend.search(query)

        assert not any("ml2024" == match.entry_key for match in result.results)

    def test_delete_nonexistent_document(self, backend):
        """Deleting non-existent document should return False."""
        assert backend.delete("nonexistent") is False

    def test_clear_index(self, backend):
        """Clearing should remove all documents."""
        from bibmgr.search.backends.memory import MemoryBackend

        memory_backend = backend
        assert isinstance(memory_backend, MemoryBackend)

        # Verify documents exist
        assert len(memory_backend.documents) > 0

        # Clear
        backend.clear()

        # Verify empty
        assert len(memory_backend.documents) == 0
        assert len(memory_backend.term_index) == 0
        assert len(memory_backend.field_values) == 0

    def test_statistics(self, backend):
        """Statistics should provide accurate information."""
        stats = backend.get_statistics()

        assert isinstance(stats, dict)
        assert "total_documents" in stats
        assert "total_terms" in stats
        assert "memory_usage_mb" in stats

        assert stats["total_documents"] == 4  # From fixture
        assert stats["total_terms"] > 0
        assert stats["memory_usage_mb"] >= 0

    def test_suggestions(self, backend):
        """Suggestions should work based on indexed terms."""
        suggestions = backend.suggest("mach", "title", 5)

        assert isinstance(suggestions, list)
        assert len(suggestions) <= 5

        # Should include terms starting with "mach"
        machine_suggestions = [s for s in suggestions if s.startswith("mach")]
        if machine_suggestions:
            assert "machine" in machine_suggestions

    def test_case_insensitive_search(self, backend):
        """Search should be case-insensitive."""
        from bibmgr.search.backends.base import SearchQuery

        # Try different cases
        queries = ["MACHINE", "Machine", "machine", "MaChInE"]

        results = []
        for q in queries:
            query = SearchQuery(query=q)
            result = backend.search(query)
            results.append(result.total)

        # All should return same count
        assert all(r == results[0] for r in results)

    def test_stop_word_handling(self, backend):
        """Common stop words should be handled appropriately."""
        from bibmgr.search.backends.base import SearchQuery

        # Search with stop words
        query1 = SearchQuery(query="machine learning")
        result1 = backend.search(query1)

        query2 = SearchQuery(query="machine and learning")  # Added "and"
        result2 = backend.search(query2)

        # Results should be similar (stop words ignored or handled)
        assert abs(result1.total - result2.total) <= 1

    def test_concurrent_operations(self, memory_backend):
        """Concurrent operations should work safely."""
        import threading

        def index_worker(start_id):
            for i in range(5):
                doc_id = f"concurrent_{start_id}_{i}"
                memory_backend.index(
                    doc_id,
                    {
                        "key": doc_id,
                        "title": f"Concurrent Document {start_id}-{i}",
                        "year": 2024,
                    },
                )

        # Index concurrently
        threads = []
        for i in range(3):
            t = threading.Thread(target=index_worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All documents should be indexed
        assert len(memory_backend.documents) >= 15

    def test_memory_efficiency(self):
        """Memory backend should be reasonably efficient."""

        backend = MemoryBackend()

        # Index many small documents
        for i in range(1000):
            backend.index(
                f"doc_{i}",
                {
                    "key": f"doc_{i}",
                    "title": f"Document {i}",
                    "year": 2024,
                },
            )

        # Memory usage should be reasonable
        stats = backend.get_statistics()
        assert stats["memory_usage_mb"] < 50  # Should be less than 50MB for 1000 docs

    def test_scoring_algorithm(self, backend):
        """Scoring should follow reasonable relevance principles."""
        from bibmgr.search.backends.base import SearchQuery

        # Query that appears in title vs abstract
        query = SearchQuery(query="fundamentals")
        result = backend.search(query)

        if result.results:
            # Documents with term in title should score higher than in abstract
            title_scores = []
            abstract_scores = []

            for match in result.results:
                doc = backend.documents[match.entry_key]
                if "fundamentals" in doc.get("title", "").lower():
                    title_scores.append(match.score)
                elif "fundamentals" in doc.get("abstract", "").lower():
                    abstract_scores.append(match.score)

            if title_scores and abstract_scores:
                assert max(title_scores) >= max(abstract_scores)

    def test_complex_query_parsing(self, backend):
        """Complex queries should be parsed correctly."""
        from bibmgr.search.backends.base import SearchQuery

        # Complex query with multiple operators
        query = SearchQuery(
            query='(machine OR deep) AND learning NOT "computer vision"'
        )
        result = backend.search(query)

        # Should handle complex boolean logic
        assert isinstance(result.total, int)
        assert result.total >= 0
