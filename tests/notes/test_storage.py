"""Comprehensive tests for notes storage layer."""

import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol

import pytest


class StorageProtocol(Protocol):
    """Protocol for note storage implementations."""

    def initialize(self) -> None: ...
    def close(self) -> None: ...

    # Note operations
    def add_note(self, note: Any) -> None: ...
    def get_note(self, note_id: str) -> Any | None: ...
    def update_note(self, note: Any) -> None: ...
    def delete_note(self, note_id: str) -> bool: ...
    def get_notes_for_entry(self, entry_key: str) -> list[Any]: ...
    def search_notes(self, query: str, **filters: Any) -> list[Any]: ...

    # Quote operations
    def add_quote(self, quote: Any) -> None: ...
    def get_quote(self, quote_id: str) -> Any | None: ...
    def delete_quote(self, quote_id: str) -> bool: ...
    def get_quotes_for_entry(self, entry_key: str) -> list[Any]: ...
    def search_quotes(self, query: str | None, **filters: Any) -> list[Any]: ...

    # Progress operations
    def add_progress(self, progress: Any) -> None: ...
    def get_progress(self, entry_key: str) -> Any | None: ...
    def update_progress(self, progress: Any) -> None: ...
    def delete_progress(self, entry_key: str) -> bool: ...
    def get_reading_list(self, **filters: Any) -> list[Any]: ...

    # Version operations
    def get_note_versions(self, note_id: str) -> list[Any]: ...
    def get_note_at_version(self, note_id: str, version: int) -> Any | None: ...

    # Batch operations
    def batch_add_notes(self, notes: list[Any]) -> None: ...
    def batch_update_notes(self, notes: list[Any]) -> None: ...
    def batch_delete_notes(self, note_ids: list[str]) -> int: ...

    # Statistics
    def get_statistics(self) -> dict[str, int]: ...


class TestStorageInitialization:
    """Test storage initialization and schema."""

    def test_create_storage(self, storage_factory, temp_db_path):
        """Test creating storage instance."""
        storage = storage_factory(temp_db_path)
        assert storage is not None
        storage.close()

    def test_initialize_schema(self, storage_factory, temp_db_path):
        """Test database schema initialization."""
        storage = storage_factory(temp_db_path)

        # Check that tables exist
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()

        # Check main tables
        tables = [
            "notes",
            "quotes",
            "reading_progress",
            "note_versions",
            "note_references",
        ]

        for table in tables:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            )
            assert cursor.fetchone() is not None, f"Table {table} not found"

        # Check FTS table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notes_fts'"
        )
        assert cursor.fetchone() is not None

        conn.close()
        storage.close()

    def test_reinitialize_existing(self, storage_factory, temp_db_path):
        """Test reinitializing existing database."""
        # Create and close first instance
        storage1 = storage_factory(temp_db_path)
        note = storage1.create_note(id="test", entry_key="e1", content="Content")
        storage1.add_note(note)
        storage1.close()

        # Create second instance
        storage2 = storage_factory(temp_db_path)
        retrieved = storage2.get_note("test")
        assert retrieved is not None
        assert retrieved.content == "Content"
        storage2.close()

    def test_storage_path_creation(self, storage_factory, tmp_path):
        """Test that storage creates missing directories."""
        nested_path = tmp_path / "deep" / "nested" / "path" / "notes.db"
        storage = storage_factory(nested_path)

        assert nested_path.parent.exists()
        storage.close()


class TestNoteOperations:
    """Test note CRUD operations."""

    def test_add_note(self, storage, note_factory):
        """Test adding a note."""
        note = note_factory(
            id="test-1",
            entry_key="einstein1905",
            content="E = mc²",
        )

        storage.add_note(note)

        retrieved = storage.get_note("test-1")
        assert retrieved is not None
        assert retrieved.id == "test-1"
        assert retrieved.entry_key == "einstein1905"
        assert retrieved.content == "E = mc²"

    def test_add_duplicate_note(self, storage, note_factory):
        """Test adding duplicate note ID."""
        note1 = note_factory(id="dup", entry_key="e1", content="Content 1")
        note2 = note_factory(id="dup", entry_key="e2", content="Content 2")

        storage.add_note(note1)

        with pytest.raises(Exception):  # Should raise integrity error
            storage.add_note(note2)

    def test_get_nonexistent_note(self, storage):
        """Test getting nonexistent note."""
        result = storage.get_note("nonexistent")
        assert result is None

    def test_update_note(self, storage, note_factory):
        """Test updating a note."""
        # Add initial note
        note = note_factory(
            id="test-1",
            entry_key="e1",
            content="Original",
            version=1,
        )
        storage.add_note(note)

        # Update it
        updated = note.update(content="Updated", title="New Title")
        storage.update_note(updated)

        # Retrieve and verify
        retrieved = storage.get_note("test-1")
        assert retrieved.content == "Updated"
        assert retrieved.title == "New Title"
        assert retrieved.version == 2

    def test_update_nonexistent_note(self, storage, note_factory):
        """Test updating nonexistent note."""
        note = note_factory(id="nonexistent", entry_key="e1", content="Content")

        # Should handle gracefully
        storage.update_note(note)

        # Note should not be created
        assert storage.get_note("nonexistent") is None

    def test_delete_note(self, storage, note_factory):
        """Test deleting a note."""
        note = note_factory(id="test-1", entry_key="e1", content="Content")
        storage.add_note(note)

        # Verify it exists
        assert storage.get_note("test-1") is not None

        # Delete it
        result = storage.delete_note("test-1")
        assert result is True

        # Verify it's gone
        assert storage.get_note("test-1") is None

    def test_delete_nonexistent_note(self, storage):
        """Test deleting nonexistent note."""
        result = storage.delete_note("nonexistent")
        assert result is False

    def test_get_notes_for_entry(self, storage, note_factory):
        """Test getting notes for an entry."""
        # Add notes for different entries
        notes = [
            note_factory(id="n1", entry_key="e1", content="Note 1"),
            note_factory(id="n2", entry_key="e1", content="Note 2"),
            note_factory(id="n3", entry_key="e2", content="Note 3"),
        ]

        for note in notes:
            storage.add_note(note)

        # Get notes for e1
        e1_notes = storage.get_notes_for_entry("e1")
        assert len(e1_notes) == 2
        ids = [n.id for n in e1_notes]
        assert "n1" in ids
        assert "n2" in ids

        # Get notes for e2
        e2_notes = storage.get_notes_for_entry("e2")
        assert len(e2_notes) == 1
        assert e2_notes[0].id == "n3"

        # Get notes for nonexistent entry
        e3_notes = storage.get_notes_for_entry("e3")
        assert e3_notes == []


class TestQuoteOperations:
    """Test quote CRUD operations."""

    def test_add_quote(self, storage, quote_factory):
        """Test adding a quote."""
        quote = quote_factory(
            id="q1",
            entry_key="feynman1965",
            text="The first principle...",
            page=42,
        )

        storage.add_quote(quote)

        retrieved = storage.get_quote("q1")
        assert retrieved is not None
        assert retrieved.id == "q1"
        assert retrieved.text == "The first principle..."
        assert retrieved.page == 42

    def test_delete_quote(self, storage, quote_factory):
        """Test deleting a quote."""
        quote = quote_factory(id="q1", entry_key="e1", text="Text")
        storage.add_quote(quote)

        result = storage.delete_quote("q1")
        assert result is True
        assert storage.get_quote("q1") is None

    def test_get_quotes_for_entry(self, storage, quote_factory):
        """Test getting quotes for an entry."""
        quotes = [
            quote_factory(id="q1", entry_key="e1", text="Quote 1", page=10),
            quote_factory(id="q2", entry_key="e1", text="Quote 2", page=20),
            quote_factory(id="q3", entry_key="e2", text="Quote 3", page=5),
        ]

        for quote in quotes:
            storage.add_quote(quote)

        # Get quotes for e1
        e1_quotes = storage.get_quotes_for_entry("e1")
        assert len(e1_quotes) == 2
        # Should be ordered by page
        assert e1_quotes[0].page == 10
        assert e1_quotes[1].page == 20

    def test_search_quotes(self, storage, quote_factory):
        """Test searching quotes."""
        quotes = [
            quote_factory(
                id="q1",
                entry_key="e1",
                text="Important discovery about quantum mechanics",
                tags=["physics"],
            ),
            quote_factory(
                id="q2",
                entry_key="e2",
                text="Classical mechanics differs from quantum",
                tags=["physics", "comparison"],
            ),
            quote_factory(
                id="q3",
                entry_key="e3",
                text="Statistical analysis shows correlation",
                tags=["statistics"],
            ),
        ]

        for quote in quotes:
            storage.add_quote(quote)

        # Search by text
        results = storage.search_quotes("quantum")
        assert len(results) == 2

        # Search by tags
        results = storage.search_quotes(tags=["physics"])
        assert len(results) == 2

        # Combined search
        results = storage.search_quotes("quantum", tags=["comparison"])
        assert len(results) == 1
        assert results[0].id == "q2"


class TestProgressOperations:
    """Test reading progress operations."""

    def test_add_progress(self, storage, progress_factory):
        """Test adding reading progress."""
        progress = progress_factory(
            entry_key="knuth1984",
            status="reading",
            current_page=150,
            total_pages=700,
        )

        storage.add_progress(progress)

        retrieved = storage.get_progress("knuth1984")
        assert retrieved is not None
        assert retrieved.entry_key == "knuth1984"
        assert retrieved.current_page == 150

    def test_update_progress(self, storage, progress_factory):
        """Test updating reading progress."""
        # Add initial progress
        progress = progress_factory(
            entry_key="e1",
            status="unread",
        )
        storage.add_progress(progress)

        # Update it
        updated = progress.update_progress(page=50, time_minutes=60)
        storage.update_progress(updated)

        # Retrieve and verify
        retrieved = storage.get_progress("e1")
        assert retrieved.current_page == 50
        assert retrieved.reading_time_minutes == 60
        assert retrieved.status.value == "reading"

    def test_delete_progress(self, storage, progress_factory):
        """Test deleting reading progress."""
        progress = progress_factory(entry_key="e1")
        storage.add_progress(progress)

        result = storage.delete_progress("e1")
        assert result is True
        assert storage.get_progress("e1") is None

    def test_get_reading_list(self, storage, progress_factory):
        """Test getting reading list with filters."""
        # Add progress for multiple entries
        progress_data = [
            ("e1", "reading", 3),  # HIGH
            ("e2", "unread", 5),  # CRITICAL
            ("e3", "read", 1),  # LOW
            ("e4", "reading", 2),  # MEDIUM
        ]

        for entry_key, status, priority in progress_data:
            progress = progress_factory(
                entry_key=entry_key,
                status=status,
                priority=priority,
            )
            storage.add_progress(progress)

        # Get all
        all_items = storage.get_reading_list()
        assert len(all_items) == 4

        # Filter by status
        reading = storage.get_reading_list(status="reading")
        assert len(reading) == 2

        # Filter by priority
        high_priority = storage.get_reading_list(min_priority=3)
        assert len(high_priority) == 2  # HIGH and CRITICAL

        # Combined filters
        high_reading = storage.get_reading_list(
            status="reading",
            min_priority=3,
        )
        assert len(high_reading) == 1  # Only e1


class TestSearchOperations:
    """Test search functionality."""

    def test_search_notes_basic(self, storage, note_factory):
        """Test basic note search."""
        notes = [
            note_factory(
                id="n1",
                entry_key="e1",
                content="Quantum mechanics is fascinating",
            ),
            note_factory(
                id="n2",
                entry_key="e2",
                content="Classical mechanics differs from quantum theory",
            ),
            note_factory(
                id="n3",
                entry_key="e3",
                content="Thermodynamics and statistical mechanics",
            ),
        ]

        for note in notes:
            storage.add_note(note)

        # Search for "quantum"
        results = storage.search_notes("quantum")
        assert len(results) == 2
        ids = [n.id for n in results]
        assert "n1" in ids
        assert "n2" in ids

    def test_search_notes_with_filters(self, storage, note_factory):
        """Test note search with filters."""
        notes = [
            note_factory(
                id="n1",
                entry_key="e1",
                content="Summary content",
                type="summary",
                tags=["physics"],
            ),
            note_factory(
                id="n2",
                entry_key="e2",
                content="Critique content",
                type="critique",
                tags=["physics", "review"],
            ),
            note_factory(
                id="n3",
                entry_key="e3",
                content="Summary of review",
                type="summary",
                tags=["review"],
            ),
        ]

        for note in notes:
            storage.add_note(note)

        # Filter by type
        results = storage.search_notes("content", type="summary")
        assert len(results) == 1
        assert results[0].id == "n1"

        # Filter by tags
        results = storage.search_notes("content", tags=["review"])
        assert len(results) == 1
        assert results[0].id == "n2"

        # Multiple filters
        results = storage.search_notes("summary", type="summary", tags=["review"])
        assert len(results) == 1
        assert results[0].id == "n3"

    def test_search_ranking(self, storage, note_factory):
        """Test search result ranking."""
        notes = [
            note_factory(
                id="n1",
                entry_key="e1",
                content="quantum",  # Exact match
            ),
            note_factory(
                id="n2",
                entry_key="e2",
                content="Quantum mechanics and quantum computing",  # Multiple matches
            ),
            note_factory(
                id="n3",
                entry_key="e3",
                content="The quantum theory of fields",  # Single match in longer text
            ),
        ]

        for note in notes:
            storage.add_note(note)

        results = storage.search_notes("quantum")
        assert len(results) == 3

        # Results should be ranked by relevance
        # Exact match or multiple occurrences should rank higher
        assert results[0].id in ["n1", "n2"]


class TestVersionOperations:
    """Test version tracking operations."""

    def test_version_tracking(self, storage, note_factory):
        """Test automatic version tracking."""
        # Add initial note
        note = note_factory(
            id="test",
            entry_key="e1",
            content="Version 1",
        )
        storage.add_note(note)

        # Update multiple times
        for i in range(2, 5):
            note = note.update(content=f"Version {i}")
            storage.update_note(note)

        # Get version history
        versions = storage.get_note_versions("test")
        assert len(versions) == 4

        for i, version in enumerate(versions):
            assert version.version == i + 1
            assert version.content == f"Version {i + 1}"

    def test_get_note_at_version(self, storage, note_factory):
        """Test retrieving specific version."""
        # Add and update note
        note = note_factory(
            id="test",
            entry_key="e1",
            content="Original",
        )
        storage.add_note(note)

        note = note.update(content="Updated")
        storage.update_note(note)

        note = note.update(content="Final")
        storage.update_note(note)

        # Get specific versions
        v1 = storage.get_note_at_version("test", 1)
        assert v1.content == "Original"

        v2 = storage.get_note_at_version("test", 2)
        assert v2.content == "Updated"

        v3 = storage.get_note_at_version("test", 3)
        assert v3.content == "Final"

        # Nonexistent version
        v4 = storage.get_note_at_version("test", 4)
        assert v4 is None

    def test_version_metadata(self, storage, note_factory):
        """Test version metadata tracking."""
        note = note_factory(
            id="test",
            entry_key="e1",
            content="Initial",
        )
        storage.add_note(note)

        # Update with metadata
        note = note.update(content="Updated")
        storage.update_note(note, change_summary="Fixed typos", changed_by="user123")

        versions = storage.get_note_versions("test")
        latest = versions[-1]

        assert latest.change_summary == "Fixed typos"
        assert latest.changed_by == "user123"


class TestBatchOperations:
    """Test batch operations for performance."""

    def test_batch_add_notes(self, storage, note_factory):
        """Test batch adding notes."""
        notes = [
            note_factory(id=f"batch-{i}", entry_key="e1", content=f"Note {i}")
            for i in range(100)
        ]

        storage.batch_add_notes(notes)

        # Verify all were added
        for i in range(100):
            note = storage.get_note(f"batch-{i}")
            assert note is not None
            assert note.content == f"Note {i}"

    def test_batch_update_notes(self, storage, note_factory):
        """Test batch updating notes."""
        # Add notes
        notes = [
            note_factory(id=f"batch-{i}", entry_key="e1", content=f"Original {i}")
            for i in range(50)
        ]
        storage.batch_add_notes(notes)

        # Update them
        updated = [n.update(content=f"Updated {i}") for i, n in enumerate(notes)]
        storage.batch_update_notes(updated)

        # Verify updates
        for i in range(50):
            note = storage.get_note(f"batch-{i}")
            assert note.content == f"Updated {i}"
            assert note.version == 2

    def test_batch_delete_notes(self, storage, note_factory):
        """Test batch deleting notes."""
        # Add notes
        notes = [
            note_factory(id=f"batch-{i}", entry_key="e1", content=f"Note {i}")
            for i in range(50)
        ]
        storage.batch_add_notes(notes)

        # Delete half
        ids_to_delete = [f"batch-{i}" for i in range(25)]
        count = storage.batch_delete_notes(ids_to_delete)
        assert count == 25

        # Verify deletions
        for i in range(25):
            assert storage.get_note(f"batch-{i}") is None

        # Verify remaining
        for i in range(25, 50):
            assert storage.get_note(f"batch-{i}") is not None

    def test_batch_performance(self, storage, note_factory, benchmark):
        """Test batch operation performance."""
        notes = [
            note_factory(id=f"perf-{i}", entry_key=f"e{i % 10}", content=f"Content {i}")
            for i in range(1000)
        ]

        # Benchmark batch add
        benchmark(storage.batch_add_notes, notes)

        # Should complete quickly (adjust threshold as needed)
        assert benchmark.stats["mean"] < 1.0  # Less than 1 second


class TestConcurrency:
    """Test concurrent access and thread safety."""

    def test_concurrent_adds(self, storage, note_factory):
        """Test concurrent note additions."""

        def add_notes(start, count):
            for i in range(start, start + count):
                note = note_factory(
                    id=f"concurrent-{i}",
                    entry_key="e1",
                    content=f"Note {i}",
                )
                storage.add_note(note)

        # Run concurrent additions
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(5):
                future = executor.submit(add_notes, i * 20, 20)
                futures.append(future)

            # Wait for completion
            for future in futures:
                future.result()

        # Verify all notes were added
        for i in range(100):
            note = storage.get_note(f"concurrent-{i}")
            assert note is not None

    def test_concurrent_updates(self, storage, note_factory):
        """Test concurrent updates to same note."""
        # Add initial note
        note = note_factory(
            id="test",
            entry_key="e1",
            content="Initial",
            version=1,
        )
        storage.add_note(note)

        from bibmgr.notes.exceptions import OptimisticLockError

        def update_note(value):
            # Retry on version conflict
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    current = storage.get_note("test")
                    if current:
                        updated = current.update(content=f"Updated by {value}")
                        storage.update_note(updated)
                        return True
                except OptimisticLockError:
                    if attempt == max_retries - 1:
                        return False  # Give up after max retries
                    time.sleep(0.01)  # Small delay before retry
            return False

        # Run concurrent updates
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(10):
                future = executor.submit(update_note, i)
                futures.append(future)

            results = [future.result() for future in futures]

        # At least some updates should succeed
        assert any(results), "At least some updates should succeed"

        # Note should exist with some update
        final = storage.get_note("test")
        assert final is not None
        assert "Updated by" in final.content
        # Version should be greater than 1
        assert final.version > 1

    def test_concurrent_reads_writes(self, storage, note_factory):
        """Test concurrent reads and writes."""
        # Add some initial notes
        for i in range(10):
            note = note_factory(
                id=f"note-{i}",
                entry_key="e1",
                content=f"Content {i}",
            )
            storage.add_note(note)

        results = {"reads": 0, "writes": 0, "errors": 0}

        def reader():
            try:
                for _ in range(50):
                    note_id = f"note-{_ % 10}"
                    note = storage.get_note(note_id)
                    if note:
                        results["reads"] += 1
            except Exception:
                results["errors"] += 1

        def writer(writer_id):
            try:
                for i in range(50):
                    note_id = f"new-{writer_id}-{i}"  # Unique ID per writer
                    note = note_factory(
                        id=note_id,
                        entry_key="e1",
                        content=f"New {i}",
                    )
                    storage.add_note(note)
                    results["writes"] += 1
            except Exception:
                results["errors"] += 1

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []

            # 5 readers, 5 writers
            for i in range(5):
                futures.append(executor.submit(reader))
                futures.append(executor.submit(writer, i))  # Pass writer ID

            for future in futures:
                future.result()

        # Verify operations completed
        assert results["reads"] > 0
        assert results["writes"] > 0
        assert results["errors"] == 0

    def test_write_lock_timeout(self, storage, note_factory):
        """Test write lock timeout handling."""
        # This test simulates a long-running write transaction
        # and verifies that other operations don't block indefinitely

        note = note_factory(id="test", entry_key="e1", content="Content")
        storage.add_note(note)

        # Simulate long transaction (implementation-specific)
        # Storage should handle this gracefully
        with storage.transaction():
            # Hold transaction open
            time.sleep(0.1)

            # Other thread should timeout or retry
            def other_operation():
                try:
                    other_note = note_factory(
                        id="other",
                        entry_key="e2",
                        content="Other",
                    )
                    storage.add_note(other_note)
                    return True
                except Exception:
                    return False

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(other_operation)
                result = future.result(timeout=1.0)
                # Should either succeed or fail gracefully
                assert isinstance(result, bool)


class TestStatistics:
    """Test statistics and reporting."""

    def test_get_statistics(
        self, storage, note_factory, quote_factory, progress_factory
    ):
        """Test getting storage statistics."""
        # Add various data
        for i in range(5):
            note = note_factory(
                id=f"note-{i}",
                entry_key=f"entry-{i % 3}",
                content=f"Content {i}",
            )
            storage.add_note(note)

        for i in range(3):
            quote = quote_factory(
                id=f"quote-{i}",
                entry_key=f"entry-{i}",
                text=f"Quote {i}",
            )
            storage.add_quote(quote)

        for i in range(4):
            progress = progress_factory(
                entry_key=f"entry-{i}",
                status=["unread", "reading", "read", "reading"][i],
            )
            storage.add_progress(progress)

        stats = storage.get_statistics()

        assert stats["total_notes"] == 5
        assert stats["total_quotes"] == 3
        assert stats["entries_with_notes"] == 3
        assert stats["entries_in_progress"] == 2
        assert stats["entries_completed"] == 1

    def test_statistics_empty_storage(self, storage):
        """Test statistics on empty storage."""
        stats = storage.get_statistics()

        assert stats["total_notes"] == 0
        assert stats["total_quotes"] == 0
        assert stats["entries_with_notes"] == 0
        assert stats["entries_in_progress"] == 0
        assert stats["entries_completed"] == 0


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_note_data(self, storage, note_factory):
        """Test handling of invalid note data."""
        # Missing required fields
        with pytest.raises(Exception):
            storage.add_note(None)

        # Invalid entry key
        with pytest.raises(Exception):
            note = note_factory(id="test", entry_key=None, content="Content")
            storage.add_note(note)

    def test_oversized_content(self, storage, note_factory):
        """Test handling of very large content."""
        # 10 MB of text
        huge_content = "x" * (10 * 1024 * 1024)
        note = note_factory(
            id="huge",
            entry_key="e1",
            content=huge_content,
        )

        # Should handle gracefully (store or reject)
        try:
            storage.add_note(note)
            retrieved = storage.get_note("huge")
            assert retrieved is not None
            assert len(retrieved.content) == len(huge_content)
        except Exception as e:
            # Should be a specific error about size
            assert "size" in str(e).lower() or "large" in str(e).lower()

    def test_database_corruption_recovery(
        self, storage_factory, temp_db_path, note_factory
    ):
        """Test recovery from database corruption."""
        # Create storage and add data
        storage = storage_factory(temp_db_path)
        note = note_factory(id="test", entry_key="e1", content="Content")
        storage.add_note(note)
        storage.close()

        # Corrupt the database file
        with open(temp_db_path, "r+b") as f:
            f.seek(100)
            f.write(b"CORRUPTED")

        # Try to create new storage
        try:
            storage2 = storage_factory(temp_db_path)
            # Should either recover or raise clear error
            result = storage2.get_note("test")
            # If it recovers, data might be lost
            assert result is None or result.id == "test"
            storage2.close()
        except Exception as e:
            # Should be a clear corruption error
            assert "corrupt" in str(e).lower() or "malformed" in str(e).lower()

    def test_transaction_rollback(self, storage, note_factory):
        """Test transaction rollback on error."""
        notes = [
            note_factory(id=f"txn-{i}", entry_key="e1", content=f"Note {i}")
            for i in range(5)
        ]

        # Add one duplicate to cause error
        notes.append(note_factory(id="txn-2", entry_key="e1", content="Duplicate"))

        # Batch operation should rollback on error
        with pytest.raises(Exception):
            storage.batch_add_notes(notes)

        # None of the notes should be added
        for i in range(5):
            assert storage.get_note(f"txn-{i}") is None


class TestIntegration:
    """Integration tests for complex scenarios."""

    def test_full_workflow(
        self, storage, note_factory, quote_factory, progress_factory
    ):
        """Test complete workflow with notes, quotes, and progress."""
        entry_key = "feynman1965"

        # Add reading progress
        progress = progress_factory(
            entry_key=entry_key,
            status="reading",
            current_page=50,
            total_pages=300,
        )
        storage.add_progress(progress)

        # Add notes
        note1 = note_factory(
            id="note-1",
            entry_key=entry_key,
            content="Chapter 1 summary",
            type="summary",
        )
        note2 = note_factory(
            id="note-2",
            entry_key=entry_key,
            content="Critique of methodology",
            type="critique",
        )
        storage.add_note(note1)
        storage.add_note(note2)

        # Add quotes
        quote1 = quote_factory(
            id="quote-1",
            entry_key=entry_key,
            text="The first principle...",
            page=42,
        )
        quote2 = quote_factory(
            id="quote-2",
            entry_key=entry_key,
            text="Science is a way of thinking...",
            page=87,
        )
        storage.add_quote(quote1)
        storage.add_quote(quote2)

        # Update progress
        updated_progress = progress.update_progress(page=100, time_minutes=120)
        storage.update_progress(updated_progress)

        # Update note
        updated_note = note1.update(content="Chapter 1 detailed summary")
        storage.update_note(updated_note)

        # Verify complete state
        final_progress = storage.get_progress(entry_key)
        assert final_progress.current_page == 100
        assert final_progress.reading_time_minutes == 120

        notes = storage.get_notes_for_entry(entry_key)
        assert len(notes) == 2

        quotes = storage.get_quotes_for_entry(entry_key)
        assert len(quotes) == 2

        # Check version history
        versions = storage.get_note_versions("note-1")
        assert len(versions) == 2

    def test_cross_reference_handling(self, storage, note_factory):
        """Test handling of cross-references between notes."""
        # Create notes with references
        note1 = note_factory(
            id="note-1",
            entry_key="e1",
            content="See note-2",
            references=["note-2"],
        )
        note2 = note_factory(
            id="note-2",
            entry_key="e2",
            content="See note-1 and note-3",
            references=["note-1", "note-3"],
        )
        note3 = note_factory(
            id="note-3",
            entry_key="e3",
            content="Independent",
            references=[],
        )

        storage.add_note(note1)
        storage.add_note(note2)
        storage.add_note(note3)

        # Delete note-3
        storage.delete_note("note-3")

        # Notes 1 and 2 should still exist
        assert storage.get_note("note-1") is not None
        assert storage.get_note("note-2") is not None

        # References should be preserved (dangling reference is ok)
        note2_retrieved = storage.get_note("note-2")
        assert "note-3" in note2_retrieved.references
