"""Tests for full-text indexing functionality.

This module tests the indexing abstraction layer that provides
full-text search capabilities through different backend implementations.
"""

import time
from datetime import datetime
from unittest.mock import patch

import pytest

from bibmgr.core.models import Entry, EntryType

# Import for skipif conditions
try:
    from bibmgr.storage.indexing import WhooshIndexBackend
except ImportError:
    WhooshIndexBackend = None


class IndexBackendContract:
    """Contract tests that all index backends must pass."""

    def test_index_and_search_entry(self, backend):
        """Basic index and search operations work."""
        entry = Entry(
            key="test1",
            type=EntryType.ARTICLE,
            title="Introduction to Machine Learning",
            author="John Smith",
            abstract="This paper covers neural networks and deep learning algorithms.",
            journal="ML Journal",
            year=2020,
        )

        backend.index_entry(entry)

        results = backend.search("Introduction")
        assert len(results) > 0
        assert results[0].entry_key == "test1"

        results = backend.search("Smith")
        assert len(results) > 0
        assert results[0].entry_key == "test1"

        results = backend.search("neural")
        assert len(results) > 0
        assert results[0].entry_key == "test1"

    def test_update_entry(self, backend):
        """Updating an entry updates the index."""
        entry = Entry(
            key="update_test",
            type=EntryType.ARTICLE,
            title="Original Title",
            author="Original Author",
            journal="Journal",
            year=2020,
        )

        backend.index_entry(entry)

        results = backend.search("Original")
        assert len(results) == 1

        import msgspec

        updated_entry = msgspec.structs.replace(
            entry, title="Updated Title", author="New Author"
        )
        backend.update_entry(updated_entry)

        results = backend.search("Original")
        assert len(results) == 0

        results = backend.search("Updated")
        assert len(results) == 1
        assert results[0].entry_key == "update_test"

    def test_remove_entry(self, backend):
        """Removing an entry removes it from index."""
        entry = Entry(
            key="remove_test",
            type=EntryType.ARTICLE,
            title="To Be Removed",
            author="Test Author",
            journal="Journal",
            year=2020,
        )

        backend.index_entry(entry)

        results = backend.search("Removed")
        assert len(results) == 1

        backend.remove_entry("remove_test")

        results = backend.search("Removed")
        assert len(results) == 0

    def test_search_field(self, backend):
        """Field-specific search works correctly."""
        entries = [
            Entry(
                key="entry1",
                type=EntryType.ARTICLE,
                title="Machine Learning",
                author="Smith",
                abstract="About algorithms",
                journal="ML Journal",
                year=2020,
            ),
            Entry(
                key="entry2",
                type=EntryType.ARTICLE,
                title="Data Processing",
                author="Machine",  # "Machine" in author, not title
                abstract="About data",
                journal="Data Journal",
                year=2021,
            ),
        ]

        for entry in entries:
            backend.index_entry(entry)

        results = backend.search_field("title", "Machine")
        assert len(results) == 1
        assert results[0].entry_key == "entry1"

        results = backend.search_field("author", "Machine")
        assert len(results) == 1
        assert results[0].entry_key == "entry2"

    def test_clear_index(self, backend):
        """Clearing index removes all entries."""
        for i in range(5):
            entry = Entry(
                key=f"clear_test_{i}",
                type=EntryType.MISC,
                title=f"Entry {i}",
            )
            backend.index_entry(entry)

        results = backend.search("Entry")
        assert len(results) == 5

        backend.clear()

        results = backend.search("Entry")
        assert len(results) == 0

    def test_case_insensitive_search(self, backend):
        """Search is case-insensitive."""
        entry = Entry(
            key="case_test",
            type=EntryType.ARTICLE,
            title="UPPERCASE Title",
            author="MiXeD CaSe Author",
            journal="Journal",
            year=2020,
        )

        backend.index_entry(entry)

        assert len(backend.search("uppercase")) > 0
        assert len(backend.search("UPPERCASE")) > 0
        assert len(backend.search("Uppercase")) > 0
        assert len(backend.search("mixed")) > 0
        assert len(backend.search("MIXED")) > 0

    def test_ranking_relevance(self, backend):
        """More relevant results rank higher."""
        entries = [
            Entry(
                key="relevant1",
                type=EntryType.ARTICLE,
                title="Machine Learning Machine Learning",  # Term appears twice
                author="Author One",
                journal="Journal",
                year=2020,
            ),
            Entry(
                key="relevant2",
                type=EntryType.ARTICLE,
                title="Introduction to Machine Learning",  # Term appears once
                author="Author Two",
                journal="Journal",
                year=2020,
            ),
            Entry(
                key="relevant3",
                type=EntryType.ARTICLE,
                title="Unrelated Topic",
                author="Machine Author",  # Term in less important field
                journal="Journal",
                year=2020,
            ),
        ]

        for entry in entries:
            backend.index_entry(entry)

        results = backend.search("Machine")
        assert len(results) >= 2

        assert results[0].entry_key == "relevant1"
        assert results[0].score > results[1].score


class TestSimpleIndexBackend(IndexBackendContract):
    """Test the simple in-memory index implementation."""

    @pytest.fixture
    def backend(self):
        from bibmgr.storage.indexing import SimpleIndexBackend

        return SimpleIndexBackend()

    def test_tokenization(self, backend):
        """Test tokenization logic."""
        tokens = backend._tokenize("Hello, World! Test-case 123.")
        assert set(tokens) == {"hello", "world", "test", "case", "123"}

        assert backend._tokenize("") == []
        assert backend._tokenize(None) == []

    def test_memory_based_index(self, backend):
        """Verify in-memory storage."""
        entry = Entry(
            key="memory_test",
            type=EntryType.MISC,
            title="Test Entry",
        )

        backend.index_entry(entry)

        assert "memory_test" in backend._entries
        assert "test" in backend._index
        assert "entry" in backend._index
        assert "memory_test" in backend._index["test"]

    def test_multiple_field_indexing(self, backend):
        """All relevant fields are indexed."""
        entry = Entry(
            key="fields_test",
            type=EntryType.ARTICLE,
            title="Title Words",
            author="Author Name",
            abstract="Abstract Content",
            keywords=("keyword1", "keyword2"),
            journal="Journal Name",
            year=2020,
        )

        backend.index_entry(entry)

        assert len(backend.search("Title")) > 0
        assert len(backend.search("Author")) > 0
        assert len(backend.search("Abstract")) > 0
        assert len(backend.search("keyword1")) > 0
        assert len(backend.search("Journal")) > 0


class TestWhooshIndexBackend(IndexBackendContract):
    """Test the Whoosh-based index implementation."""

    @pytest.fixture
    def backend(self, temp_dir):
        from bibmgr.storage.indexing import WhooshIndexBackend

        return WhooshIndexBackend(temp_dir / "whoosh_index")

    def test_whoosh_availability(self, backend):
        """Test behavior with/without Whoosh installed."""
        if backend.whoosh_available:
            assert backend.schema is not None
            assert backend.ix is not None
        else:
            assert hasattr(backend, "_fallback")

    @pytest.mark.skipif(
        WhooshIndexBackend is None, reason="WhooshIndexBackend not available"
    )
    def test_whoosh_schema_fields(self, backend):
        """Whoosh schema has correct fields."""
        schema = backend.schema
        assert "key" in schema
        assert "title" in schema
        assert "author" in schema
        assert "abstract" in schema
        assert "keywords" in schema
        assert "journal" in schema
        assert "year" in schema
        assert "content" in schema  # Combined field

    @pytest.mark.skipif(
        WhooshIndexBackend is None, reason="WhooshIndexBackend not available"
    )
    def test_whoosh_phrase_search(self, backend):
        """Whoosh supports phrase searching."""
        entry = Entry(
            key="phrase_test",
            type=EntryType.ARTICLE,
            title="Introduction to Machine Learning Algorithms",
            author="Test Author",
            journal="Journal",
            year=2020,
        )

        backend.index_entry(entry)

        results = backend.search('"Machine Learning"')
        assert len(results) == 1

        results = backend.search('"Learning Machine"')
        assert len(results) == 0

    def test_fallback_behavior(self, temp_dir):
        """Test fallback when Whoosh is not available."""
        from bibmgr.storage.indexing import WhooshIndexBackend

        with patch.dict("sys.modules", {"whoosh": None}):
            backend = WhooshIndexBackend(temp_dir / "index")

            assert not backend.whoosh_available
            assert backend._fallback is not None

            entry = Entry(key="test", type=EntryType.MISC, title="Test")
            backend.index_entry(entry)

            results = backend.search("Test")
            assert len(results) == 1


class TestIndexManager:
    """Test the index manager that coordinates indexing."""

    def test_index_multiple_entries(self):
        """Index multiple entries at once."""
        from bibmgr.storage.indexing import IndexManager, SimpleIndexBackend

        backend = SimpleIndexBackend()
        manager = IndexManager(backend)

        entries = [
            Entry(key=f"entry{i}", type=EntryType.MISC, title=f"Entry {i}")
            for i in range(5)
        ]

        manager.index_entries(entries)

        results = manager.search("Entry")
        assert len(results) == 5

    def test_reindex_all(self):
        """Reindexing clears and rebuilds index."""
        from bibmgr.storage.indexing import IndexManager, SimpleIndexBackend

        backend = SimpleIndexBackend()
        manager = IndexManager(backend)

        old_entries = [
            Entry(key="old1", type=EntryType.MISC, title="Old Entry 1"),
            Entry(key="old2", type=EntryType.MISC, title="Old Entry 2"),
        ]
        manager.index_entries(old_entries)

        new_entries = [
            Entry(key="new1", type=EntryType.MISC, title="New Entry 1"),
            Entry(key="new2", type=EntryType.MISC, title="New Entry 2"),
        ]

        manager.reindex_all(new_entries)

        assert len(manager.search("Old")) == 0

        assert len(manager.search("New")) == 2

    def test_field_specific_searches(self):
        """Manager provides convenient field-specific searches."""
        from bibmgr.storage.indexing import IndexManager, SimpleIndexBackend

        backend = SimpleIndexBackend()
        manager = IndexManager(backend)

        entries = [
            Entry(
                key="entry1",
                type=EntryType.ARTICLE,
                title="Machine Learning",
                author="John Smith",
                abstract="About ML",
                journal="ML Journal",
                year=2020,
            ),
            Entry(
                key="entry2",
                type=EntryType.ARTICLE,
                title="Data Science",
                author="Jane Machine",
                abstract="About data",
                journal="Data Journal",
                year=2021,
            ),
        ]

        manager.index_entries(entries)

        results = manager.search_title("Machine")
        assert len(results) == 1
        assert results[0].entry_key == "entry1"

        results = manager.search_author("Machine")
        assert len(results) == 1
        assert results[0].entry_key == "entry2"

        results = manager.search_abstract("data")
        assert len(results) == 1
        assert results[0].entry_key == "entry2"


class TestSearchResult:
    """Test the SearchResult data class."""

    def test_search_result_creation(self):
        """SearchResult stores key and score."""
        from bibmgr.storage.indexing import SearchResult

        result = SearchResult(entry_key="test", score=0.95)
        assert result.entry_key == "test"
        assert result.score == 0.95
        assert result.highlights is None

    def test_search_result_with_highlights(self):
        """SearchResult can include highlighted snippets."""
        from bibmgr.storage.indexing import SearchResult

        highlights = {
            "title": ["Introduction to <mark>Machine Learning</mark>"],
            "abstract": ["...about <mark>machine</mark> learning algorithms..."],
        }

        result = SearchResult(entry_key="test", score=0.9, highlights=highlights)

        assert result.highlights == highlights
        assert result.highlights and len(result.highlights["title"]) == 1
        assert result.highlights and "<mark>" in result.highlights["title"][0]

    def test_search_result_sorting(self):
        """SearchResults sort by score descending."""
        from bibmgr.storage.indexing import SearchResult

        results = [
            SearchResult("entry1", 0.5),
            SearchResult("entry2", 0.9),
            SearchResult("entry3", 0.7),
        ]

        sorted_results = sorted(results)

        assert sorted_results[0].score == 0.9
        assert sorted_results[1].score == 0.7
        assert sorted_results[2].score == 0.5


class TestIndexingPerformance:
    """Test indexing performance with large datasets."""

    def test_index_performance(self, performance_entries):
        """Indexing performs well with many entries."""
        from bibmgr.storage.indexing import IndexManager, SimpleIndexBackend

        backend = SimpleIndexBackend()
        manager = IndexManager(backend)

        start = time.time()
        manager.index_entries(performance_entries[:100])  # First 100
        index_time = time.time() - start

        assert index_time < 1.0  # Within 1 second for 100 entries

    def test_search_performance(self, performance_entries):
        """Search performs well with large index."""
        from bibmgr.storage.indexing import IndexManager, SimpleIndexBackend

        backend = SimpleIndexBackend()
        manager = IndexManager(backend)

        manager.index_entries(performance_entries[:500])

        start = time.time()
        results = manager.search("Paper", limit=500)
        search_time = time.time() - start

        assert search_time < 0.1  # Within 100ms
        assert len(results) == 500  # All entries have "Paper" in title

    def test_memory_usage(self, performance_entries):
        """Index memory usage is reasonable."""
        from bibmgr.storage.indexing import SimpleIndexBackend

        backend = SimpleIndexBackend()

        for entry in performance_entries[:200]:
            backend.index_entry(entry)

        assert len(backend._entries) == 200

        assert len(backend._index) < 6000  # Less than 30 tokens per entry


class TestIndexingIntegration:
    """Test indexing integration with storage system."""

    def test_index_with_repository(self, temp_dir, sample_entries):
        """Indexing integrates with repository operations."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.indexing import IndexManager, SimpleIndexBackend
        from bibmgr.storage.repository import RepositoryManager

        backend = FileSystemBackend(temp_dir)
        manager = RepositoryManager(backend)

        index_backend = SimpleIndexBackend()
        index_manager = IndexManager(index_backend)

        manager.import_entries(sample_entries)

        all_entries = manager.entries.find_all()
        index_manager.index_entries(all_entries)

        results = index_manager.search("Knuth")
        assert len(results) == 1
        assert results[0].entry_key == "knuth1984"

        entry = manager.entries.find(results[0].entry_key)
        assert entry is not None
        assert entry.author and "Knuth" in entry.author

    def test_index_update_on_entry_change(self, temp_dir):
        """Index updates when entries change."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.events import EventBus, EventType
        from bibmgr.storage.indexing import IndexManager, SimpleIndexBackend
        from bibmgr.storage.repository import RepositoryManager

        backend = FileSystemBackend(temp_dir)
        event_bus = EventBus()
        manager = RepositoryManager(backend)

        index_backend = SimpleIndexBackend()
        index_manager = IndexManager(index_backend)

        def on_entry_updated(event):
            if event.entry:
                index_backend.update_entry(event.entry)

        event_bus.subscribe(EventType.ENTRY_UPDATED, on_entry_updated)

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Original Title",
            author="Author",
            journal="Journal",
            year=2020,
        )

        manager.entries.save(entry)
        index_backend.index_entry(entry)

        import msgspec

        updated = msgspec.structs.replace(entry, title="New Title")
        manager.entries.save(updated)

        from bibmgr.storage.events import Event

        event_bus.publish(
            Event(
                type=EventType.ENTRY_UPDATED,
                timestamp=datetime.now(),
                data={"entry_key": "test", "entry": updated},
            )
        )

        results = index_manager.search("New")
        assert len(results) == 1

        results = index_manager.search("Original")
        assert len(results) == 0
