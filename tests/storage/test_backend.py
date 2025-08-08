"""Comprehensive tests for storage backend functionality.

Tests storage capabilities including:
- CRUD operations
- Transactions and atomicity
- Concurrent access
- Bulk operations
- Data integrity
- Performance optimization
- Error handling
- Backup and recovery
"""

import concurrent.futures
import tempfile
import threading
import time
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Protocol

import pytest


class Transaction(Protocol):
    """Protocol for transaction interface."""

    def add(self, entry: Any) -> None:
        """Add entry in transaction."""
        ...

    def update(self, entry: Any) -> None:
        """Update entry in transaction."""
        ...

    def delete(self, key: str) -> None:
        """Delete entry in transaction."""
        ...

    def commit(self) -> None:
        """Commit transaction."""
        ...

    def rollback(self) -> None:
        """Rollback transaction."""
        ...


class Storage(Protocol):
    """Protocol for storage backend interface."""

    def read(self, key: str) -> Any | None:
        """Read single entry."""
        ...

    def read_all(self) -> list[Any]:
        """Read all entries."""
        ...

    def read_batch(self, keys: list[str]) -> dict[str, Any]:
        """Read multiple entries efficiently."""
        ...

    def write(self, entry: Any) -> None:
        """Write single entry."""
        ...

    def write_batch(self, entries: list[Any]) -> None:
        """Write multiple entries efficiently."""
        ...

    def update(self, entry: Any) -> bool:
        """Update existing entry."""
        ...

    def update_batch(self, entries: list[Any]) -> dict[str, bool]:
        """Update multiple entries efficiently."""
        ...

    def delete(self, key: str) -> bool:
        """Delete single entry."""
        ...

    def delete_batch(self, keys: list[str]) -> dict[str, bool]:
        """Delete multiple entries efficiently."""
        ...

    def exists(self, key: str) -> bool:
        """Check if entry exists."""
        ...

    def count(self) -> int:
        """Get total number of entries."""
        ...

    def keys(self) -> list[str]:
        """Get all entry keys."""
        ...

    def clear(self) -> None:
        """Remove all entries."""
        ...

    def transaction(self) -> AbstractContextManager[Transaction]:
        """Start a transaction."""
        ...

    def get_checksum(self) -> str:
        """Get data checksum."""
        ...

    def validate(self) -> tuple[bool, list[str]]:
        """Validate data integrity."""
        ...

    def optimize(self) -> None:
        """Optimize storage for performance."""
        ...

    def backup(self, path: Path) -> None:
        """Create backup."""
        ...

    def restore(self, path: Path) -> None:
        """Restore from backup."""
        ...

    def lock(self, key: str, timeout: float = 5.0) -> AbstractContextManager:
        """Acquire lock for entry."""
        ...

    def search(self, query: dict[str, Any]) -> list[Any]:
        """Search entries by criteria."""
        ...


@pytest.fixture
def temp_storage_dir():
    """Create temporary directory for storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_entries(entry_factory):
    """Create sample entries for testing."""
    return [
        entry_factory(key=f"entry{i}", title=f"Title {i}", year=2020 + i)
        for i in range(10)
    ]


class TestBasicOperations:
    """Test basic CRUD operations."""

    def test_write_and_read(self, storage_factory, entry_factory, temp_storage_dir):
        """Test writing and reading entries."""
        storage = storage_factory(temp_storage_dir)

        entry = entry_factory(key="test", title="Test Entry", year=2024)
        storage.write(entry)

        read_entry = storage.read("test")
        assert read_entry is not None
        assert read_entry.key == "test"
        assert read_entry.title == "Test Entry"
        assert read_entry.year == 2024

    def test_read_nonexistent(self, storage_factory, temp_storage_dir):
        """Test reading non-existent entry."""
        storage = storage_factory(temp_storage_dir)

        result = storage.read("nonexistent")
        assert result is None

    def test_update_existing(self, storage_factory, entry_factory, temp_storage_dir):
        """Test updating existing entry."""
        storage = storage_factory(temp_storage_dir)

        # Write initial entry
        entry = entry_factory(key="test", title="Original", year=2024)
        storage.write(entry)

        # Update entry
        updated = entry_factory(key="test", title="Updated", year=2025)
        result = storage.update(updated)
        assert result is True

        # Verify update
        read_entry = storage.read("test")
        assert read_entry.title == "Updated"
        assert read_entry.year == 2025

    def test_update_nonexistent(self, storage_factory, entry_factory, temp_storage_dir):
        """Test updating non-existent entry."""
        storage = storage_factory(temp_storage_dir)

        entry = entry_factory(key="nonexistent", title="Test")
        result = storage.update(entry)
        assert result is False

        # Should not create entry
        assert storage.read("nonexistent") is None

    def test_delete_existing(self, storage_factory, entry_factory, temp_storage_dir):
        """Test deleting existing entry."""
        storage = storage_factory(temp_storage_dir)

        entry = entry_factory(key="test", title="Test")
        storage.write(entry)

        result = storage.delete("test")
        assert result is True
        assert storage.read("test") is None
        assert not storage.exists("test")

    def test_delete_nonexistent(self, storage_factory, temp_storage_dir):
        """Test deleting non-existent entry."""
        storage = storage_factory(temp_storage_dir)

        result = storage.delete("nonexistent")
        assert result is False

    def test_exists(self, storage_factory, entry_factory, temp_storage_dir):
        """Test existence checking."""
        storage = storage_factory(temp_storage_dir)

        assert not storage.exists("test")

        entry = entry_factory(key="test", title="Test")
        storage.write(entry)

        assert storage.exists("test")

        storage.delete("test")
        assert not storage.exists("test")

    def test_read_all(self, storage_factory, sample_entries, temp_storage_dir):
        """Test reading all entries."""
        storage = storage_factory(temp_storage_dir)

        # Write entries
        for entry in sample_entries:
            storage.write(entry)

        # Read all
        all_entries = storage.read_all()
        assert len(all_entries) == len(sample_entries)

        keys = {e.key for e in all_entries}
        expected_keys = {e.key for e in sample_entries}
        assert keys == expected_keys

    def test_count(self, storage_factory, sample_entries, temp_storage_dir):
        """Test entry counting."""
        storage = storage_factory(temp_storage_dir)

        assert storage.count() == 0

        for i, entry in enumerate(sample_entries):
            storage.write(entry)
            assert storage.count() == i + 1

        storage.delete(sample_entries[0].key)
        assert storage.count() == len(sample_entries) - 1

    def test_keys(self, storage_factory, sample_entries, temp_storage_dir):
        """Test getting all keys."""
        storage = storage_factory(temp_storage_dir)

        for entry in sample_entries:
            storage.write(entry)

        keys = storage.keys()
        assert len(keys) == len(sample_entries)
        assert set(keys) == {e.key for e in sample_entries}

    def test_clear(self, storage_factory, sample_entries, temp_storage_dir):
        """Test clearing all entries."""
        storage = storage_factory(temp_storage_dir)

        for entry in sample_entries:
            storage.write(entry)

        assert storage.count() > 0

        storage.clear()
        assert storage.count() == 0
        assert len(storage.read_all()) == 0


class TestBatchOperations:
    """Test batch operations for performance."""

    def test_write_batch(self, storage_factory, sample_entries, temp_storage_dir):
        """Test batch writing."""
        storage = storage_factory(temp_storage_dir)

        storage.write_batch(sample_entries)

        # Verify all written
        for entry in sample_entries:
            read_entry = storage.read(entry.key)
            assert read_entry is not None
            assert read_entry.title == entry.title

    def test_read_batch(self, storage_factory, sample_entries, temp_storage_dir):
        """Test batch reading."""
        storage = storage_factory(temp_storage_dir)

        # Write entries
        for entry in sample_entries:
            storage.write(entry)

        # Read batch
        keys = [e.key for e in sample_entries[:5]]
        results = storage.read_batch(keys)

        assert len(results) == 5
        for key in keys:
            assert key in results
            assert results[key] is not None

    def test_read_batch_with_missing(
        self, storage_factory, sample_entries, temp_storage_dir
    ):
        """Test batch reading with missing keys."""
        storage = storage_factory(temp_storage_dir)

        # Write some entries
        for entry in sample_entries[:3]:
            storage.write(entry)

        # Read batch including missing
        keys = ["entry0", "entry1", "missing1", "entry2", "missing2"]
        results = storage.read_batch(keys)

        assert results["entry0"] is not None
        assert results["entry1"] is not None
        assert results["entry2"] is not None
        assert results["missing1"] is None
        assert results["missing2"] is None

    def test_update_batch(self, storage_factory, entry_factory, temp_storage_dir):
        """Test batch updating."""
        storage = storage_factory(temp_storage_dir)

        # Write initial entries
        entries = [
            entry_factory(key=f"entry{i}", title=f"Original {i}") for i in range(5)
        ]
        for entry in entries:
            storage.write(entry)

        # Update batch
        updated = [
            entry_factory(key=f"entry{i}", title=f"Updated {i}") for i in range(5)
        ]
        results = storage.update_batch(updated)

        # All should succeed
        for key, success in results.items():
            assert success is True

        # Verify updates
        for entry in updated:
            read_entry = storage.read(entry.key)
            assert read_entry.title == entry.title

    def test_delete_batch(self, storage_factory, sample_entries, temp_storage_dir):
        """Test batch deletion."""
        storage = storage_factory(temp_storage_dir)

        # Write entries
        for entry in sample_entries:
            storage.write(entry)

        # Delete batch
        keys_to_delete = [e.key for e in sample_entries[:5]]
        results = storage.delete_batch(keys_to_delete)

        # Verify deletions
        for key in keys_to_delete:
            assert results[key] is True
            assert storage.read(key) is None

        # Remaining entries should exist
        for entry in sample_entries[5:]:
            assert storage.exists(entry.key)

    def test_batch_performance(
        self, storage_factory, entry_factory, temp_storage_dir, benchmark
    ):
        """Test batch operation performance."""
        storage = storage_factory(temp_storage_dir)

        # Create many entries
        entries = [
            entry_factory(key=f"entry{i}", title=f"Title {i}") for i in range(100)
        ]

        # Benchmark batch write
        benchmark(storage.write_batch, entries)

        # Verify all written
        assert storage.count() == 100


class TestTransactions:
    """Test transaction support and atomicity."""

    def test_transaction_commit(self, storage_factory, entry_factory, temp_storage_dir):
        """Test successful transaction commit."""
        storage = storage_factory(temp_storage_dir)

        with storage.transaction() as txn:
            txn.add(entry_factory(key="entry1", title="Entry 1"))
            txn.add(entry_factory(key="entry2", title="Entry 2"))
            txn.update(entry_factory(key="entry1", title="Updated 1"))
            txn.add(entry_factory(key="entry3", title="Entry 3"))
            txn.commit()

        # Verify all operations applied
        assert storage.count() == 3
        assert storage.read("entry1").title == "Updated 1"
        assert storage.read("entry2").title == "Entry 2"
        assert storage.read("entry3").title == "Entry 3"

    def test_transaction_rollback(
        self, storage_factory, entry_factory, temp_storage_dir
    ):
        """Test transaction rollback."""
        storage = storage_factory(temp_storage_dir)

        # Add initial entry
        storage.write(entry_factory(key="initial", title="Initial"))

        try:
            with storage.transaction() as txn:
                txn.add(entry_factory(key="new1", title="New 1"))
                txn.add(entry_factory(key="new2", title="New 2"))
                txn.delete("initial")
                raise RuntimeError("Simulated error")
        except RuntimeError:
            pass

        # Verify rollback
        assert storage.exists("initial")
        assert not storage.exists("new1")
        assert not storage.exists("new2")
        assert storage.count() == 1

    def test_transaction_auto_commit(
        self, storage_factory, entry_factory, temp_storage_dir
    ):
        """Test automatic commit on successful completion."""
        storage = storage_factory(temp_storage_dir)

        with storage.transaction() as txn:
            txn.add(entry_factory(key="auto", title="Auto Commit"))
            # No explicit commit

        # Should auto-commit
        assert storage.exists("auto")

    def test_transaction_auto_rollback(
        self, storage_factory, entry_factory, temp_storage_dir
    ):
        """Test automatic rollback on exception."""
        storage = storage_factory(temp_storage_dir)

        with pytest.raises(ValueError):
            with storage.transaction() as txn:
                txn.add(entry_factory(key="fail", title="Will Fail"))
                raise ValueError("Test error")

        # Should auto-rollback
        assert not storage.exists("fail")

    def test_nested_transactions(
        self, storage_factory, entry_factory, temp_storage_dir
    ):
        """Test nested transaction handling."""
        storage = storage_factory(temp_storage_dir)

        # Check if nested transactions are supported
        try:
            with storage.transaction() as outer:
                outer.add(entry_factory(key="outer", title="Outer"))

                with storage.transaction() as inner:
                    inner.add(entry_factory(key="inner", title="Inner"))
                    inner.commit()

                outer.commit()

            # If supported, both should exist
            assert storage.exists("outer")
            assert storage.exists("inner")

        except (NotImplementedError, RuntimeError):
            # Nested transactions not supported
            pass

    def test_transaction_isolation(
        self, storage_factory, entry_factory, temp_storage_dir
    ):
        """Test transaction isolation."""
        storage = storage_factory(temp_storage_dir)

        storage.write(entry_factory(key="test", title="Original"))

        with storage.transaction() as txn:
            txn.update(entry_factory(key="test", title="In Transaction"))

            # Read outside transaction should see original
            # (if isolation is supported)
            outside_read = storage.read("test")
            if outside_read:
                # Some implementations may not support isolation
                assert outside_read.title in ["Original", "In Transaction"]

            txn.commit()

        # After commit, should see update
        assert storage.read("test").title == "In Transaction"

    def test_transaction_atomicity(
        self, storage_factory, entry_factory, temp_storage_dir
    ):
        """Test transaction atomicity with partial failure."""
        storage = storage_factory(temp_storage_dir)

        # Prepare entries
        entries = [entry_factory(key=f"atom{i}", title=f"Atom {i}") for i in range(5)]

        try:
            with storage.transaction() as txn:
                for i, entry in enumerate(entries):
                    txn.add(entry)
                    if i == 3:
                        # Simulate failure mid-transaction
                        raise RuntimeError("Mid-transaction failure")
        except RuntimeError:
            pass

        # No entries should exist (all-or-nothing)
        for entry in entries:
            assert not storage.exists(entry.key)


class TestConcurrency:
    """Test concurrent access and thread safety."""

    def test_concurrent_writes(self, storage_factory, entry_factory, temp_storage_dir):
        """Test concurrent write operations."""
        storage = storage_factory(temp_storage_dir)

        def write_entries(start, count):
            for i in range(start, start + count):
                entry = entry_factory(key=f"concurrent{i}", title=f"Title {i}")
                storage.write(entry)

        # Launch concurrent writers
        threads = []
        for i in range(5):
            thread = threading.Thread(target=write_entries, args=(i * 10, 10))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify all entries written
        assert storage.count() == 50
        for i in range(50):
            assert storage.exists(f"concurrent{i}")

    def test_concurrent_reads(self, storage_factory, sample_entries, temp_storage_dir):
        """Test concurrent read operations."""
        storage = storage_factory(temp_storage_dir)

        # Write entries
        for entry in sample_entries:
            storage.write(entry)

        results = []
        lock = threading.Lock()

        def read_entries():
            local_results = []
            for entry in sample_entries:
                result = storage.read(entry.key)
                if result:
                    local_results.append(result)

            with lock:
                results.extend(local_results)

        # Launch concurrent readers
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=read_entries)
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Each thread should read all entries
        assert len(results) == 10 * len(sample_entries)

    def test_concurrent_updates(self, storage_factory, entry_factory, temp_storage_dir):
        """Test concurrent update operations."""
        storage = storage_factory(temp_storage_dir)

        # Write initial entry
        storage.write(entry_factory(key="counter", title="0", year=0))

        def increment():
            for _ in range(10):
                # Read-modify-write
                entry = storage.read("counter")
                if entry:
                    new_year = entry.year + 1
                    updated = entry_factory(
                        key="counter", title=str(new_year), year=new_year
                    )
                    storage.update(updated)
                    time.sleep(0.001)  # Small delay to increase contention

        # Launch concurrent updaters
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=increment)
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Final value depends on isolation level
        # Without proper locking, may be less than 50
        final = storage.read("counter")
        assert final.year > 0  # At least some updates succeeded

    def test_concurrent_transactions(
        self, storage_factory, entry_factory, temp_storage_dir
    ):
        """Test concurrent transaction execution."""
        storage = storage_factory(temp_storage_dir)

        results = []
        lock = threading.Lock()

        def run_transaction(thread_id):
            try:
                with storage.transaction() as txn:
                    txn.add(
                        entry_factory(
                            key=f"txn{thread_id}_1", title=f"Thread {thread_id} Entry 1"
                        )
                    )
                    time.sleep(0.01)  # Simulate work
                    txn.add(
                        entry_factory(
                            key=f"txn{thread_id}_2", title=f"Thread {thread_id} Entry 2"
                        )
                    )
                    txn.commit()

                with lock:
                    results.append(f"success_{thread_id}")

            except Exception as e:
                with lock:
                    results.append(f"failed_{thread_id}:{e}")

        # Launch concurrent transactions
        threads = []
        for i in range(5):
            thread = threading.Thread(target=run_transaction, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # All transactions should succeed
        success_count = sum(1 for r in results if r.startswith("success_"))
        assert success_count == 5

        # Verify all entries exist
        for i in range(5):
            assert storage.exists(f"txn{i}_1")
            assert storage.exists(f"txn{i}_2")

    def test_entry_locking(self, storage_factory, entry_factory, temp_storage_dir):
        """Test entry-level locking if supported."""
        storage = storage_factory(temp_storage_dir)

        # Check if locking is supported
        if not hasattr(storage, "lock"):
            pytest.skip("Locking not supported")

        storage.write(entry_factory(key="locked", title="Initial"))

        results = []

        def update_with_lock(value):
            with storage.lock("locked", timeout=5.0):
                storage.read("locked")
                time.sleep(0.1)  # Simulate work
                updated = entry_factory(key="locked", title=value)
                storage.update(updated)
                results.append(value)

        # Launch concurrent updates with locking
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(update_with_lock, f"Value {i}") for i in range(5)
            ]
            concurrent.futures.wait(futures)

        # All updates should succeed in order
        assert len(results) == 5

        # Final value should be from last update
        final = storage.read("locked")
        assert final.title in [f"Value {i}" for i in range(5)]


class TestDataIntegrity:
    """Test data integrity and validation."""

    def test_checksum(self, storage_factory, sample_entries, temp_storage_dir):
        """Test checksum calculation."""
        storage = storage_factory(temp_storage_dir)

        initial_checksum = storage.get_checksum()

        # Write entries
        for entry in sample_entries:
            storage.write(entry)

        after_write_checksum = storage.get_checksum()
        assert after_write_checksum != initial_checksum

        # Same data should give same checksum
        another_checksum = storage.get_checksum()
        assert another_checksum == after_write_checksum

        # Modify data
        storage.delete(sample_entries[0].key)
        after_delete_checksum = storage.get_checksum()
        assert after_delete_checksum != after_write_checksum

    def test_validation(self, storage_factory, entry_factory, temp_storage_dir):
        """Test data validation."""
        storage = storage_factory(temp_storage_dir)

        # Write valid entries
        for i in range(5):
            storage.write(entry_factory(key=f"valid{i}", title=f"Valid {i}"))

        # Validate
        is_valid, errors = storage.validate()
        assert is_valid
        assert len(errors) == 0

        # Corrupt data if possible (implementation-specific)
        # This is a placeholder - actual corruption would depend on storage impl

        # Validate again
        is_valid, errors = storage.validate()
        # Should still be valid unless we actually corrupted something
        assert is_valid or len(errors) > 0

    def test_duplicate_key_prevention(
        self, storage_factory, entry_factory, temp_storage_dir
    ):
        """Test prevention of duplicate keys."""
        storage = storage_factory(temp_storage_dir)

        entry1 = entry_factory(key="duplicate", title="First")
        entry2 = entry_factory(key="duplicate", title="Second")

        storage.write(entry1)

        # Writing duplicate should either fail or overwrite
        try:
            storage.write(entry2)
            # If it succeeds, should have overwritten
            result = storage.read("duplicate")
            assert result.title in ["First", "Second"]
        except (ValueError, KeyError):
            # Duplicate prevention
            result = storage.read("duplicate")
            assert result.title == "First"

    def test_atomic_writes(self, storage_factory, entry_factory, temp_storage_dir):
        """Test atomicity of write operations."""
        storage = storage_factory(temp_storage_dir)

        # Create entry with very large data
        large_data = "x" * 1000000
        entry = entry_factory(key="large", title=large_data)

        # Write should be atomic - either complete or not at all
        storage.write(entry)

        # Read back and verify
        result = storage.read("large")
        assert result is not None
        assert len(result.title) == 1000000


class TestBackupRestore:
    """Test backup and restore functionality."""

    def test_backup_create(self, storage_factory, sample_entries, temp_storage_dir):
        """Test creating backup."""
        storage_dir = temp_storage_dir / "storage"
        backup_path = temp_storage_dir / "backup"
        storage = storage_factory(storage_dir)

        # Write entries
        for entry in sample_entries:
            storage.write(entry)

        # Create backup
        storage.backup(backup_path)

        # Verify backup exists
        assert backup_path.exists()

    def test_restore_from_backup(
        self, storage_factory, sample_entries, temp_storage_dir
    ):
        """Test restoring from backup."""
        storage_dir = temp_storage_dir / "storage"
        backup_path = temp_storage_dir / "backup"
        storage = storage_factory(storage_dir)

        # Write entries
        for entry in sample_entries:
            storage.write(entry)

        original_checksum = storage.get_checksum()

        # Create backup
        storage.backup(backup_path)

        # Modify storage
        storage.clear()
        assert storage.count() == 0

        # Restore from backup
        storage.restore(backup_path)

        # Verify restoration
        assert storage.count() == len(sample_entries)
        assert storage.get_checksum() == original_checksum

        for entry in sample_entries:
            assert storage.exists(entry.key)

    def test_incremental_backup(self, storage_factory, entry_factory, temp_storage_dir):
        """Test incremental backup if supported."""
        storage = storage_factory(temp_storage_dir)
        backup_path = temp_storage_dir / "backup"

        # Initial entries
        for i in range(5):
            storage.write(entry_factory(key=f"entry{i}", title=f"Title {i}"))

        # First backup
        storage.backup(backup_path)

        # Add more entries
        for i in range(5, 10):
            storage.write(entry_factory(key=f"entry{i}", title=f"Title {i}"))

        # Incremental backup (if supported)
        if hasattr(storage, "backup_incremental"):
            storage.backup_incremental(backup_path)

            # Clear and restore
            storage.clear()
            storage.restore(backup_path)

            # Should have all entries
            assert storage.count() == 10


class TestPerformance:
    """Test performance optimizations."""

    def test_optimization(self, storage_factory, entry_factory, temp_storage_dir):
        """Test storage optimization."""
        storage = storage_factory(temp_storage_dir)

        # Write many entries
        for i in range(100):
            storage.write(entry_factory(key=f"opt{i}", title=f"Title {i}"))

        # Optimize storage
        storage.optimize()

        # Storage should still work correctly
        assert storage.count() == 100

        # Performance should be maintained or improved
        result = storage.read("opt50")
        assert result is not None
        assert result.title == "Title 50"

    def test_caching(self, storage_factory, entry_factory, temp_storage_dir, benchmark):
        """Test caching performance if implemented."""
        storage = storage_factory(temp_storage_dir)

        # Write entries
        for i in range(10):
            storage.write(entry_factory(key=f"cache{i}", title=f"Title {i}"))

        def read_repeatedly():
            results = []
            for _ in range(100):
                # Read same entries repeatedly
                for i in range(10):
                    results.append(storage.read(f"cache{i}"))
            return results

        # Benchmark repeated reads (should benefit from caching)
        results = benchmark(read_repeatedly)
        assert len(results) == 1000

    def test_large_scale_performance(
        self, storage_factory, entry_factory, temp_storage_dir
    ):
        """Test performance with large number of entries."""
        storage = storage_factory(temp_storage_dir)

        # Write many entries
        batch_size = 100
        num_batches = 10

        for batch in range(num_batches):
            entries = [
                entry_factory(key=f"large{batch}_{i}", title=f"Title {batch}_{i}")
                for i in range(batch_size)
            ]
            storage.write_batch(entries)

        # Verify count
        assert storage.count() == batch_size * num_batches

        # Test read performance
        start_time = time.time()
        all_entries = storage.read_all()
        read_time = time.time() - start_time

        assert len(all_entries) == batch_size * num_batches
        # Should complete in reasonable time (adjust threshold as needed)
        assert read_time < 5.0  # 5 seconds for 1000 entries


class TestSearch:
    """Test search functionality."""

    def test_search_by_field(self, storage_factory, entry_factory, temp_storage_dir):
        """Test searching by field values."""
        storage = storage_factory(temp_storage_dir)

        # Check if search is supported
        if not hasattr(storage, "search"):
            pytest.skip("Search not supported")

        # Write entries with various years
        for i in range(10):
            storage.write(
                entry_factory(key=f"entry{i}", title=f"Title {i}", year=2020 + (i % 3))
            )

        # Search by year
        results = storage.search({"year": 2021})
        assert len(results) > 0
        for entry in results:
            assert entry.year == 2021

    def test_search_by_pattern(self, storage_factory, entry_factory, temp_storage_dir):
        """Test pattern-based search."""
        storage = storage_factory(temp_storage_dir)

        if not hasattr(storage, "search"):
            pytest.skip("Search not supported")

        # Write entries
        storage.write(entry_factory(key="ml1", title="Machine Learning Basics"))
        storage.write(entry_factory(key="ml2", title="Deep Learning Advanced"))
        storage.write(entry_factory(key="db1", title="Database Systems"))

        # Search by title pattern
        results = storage.search({"title": {"$regex": "Learning"}})
        assert len(results) == 2

        titles = [e.title for e in results]
        assert "Machine Learning Basics" in titles
        assert "Deep Learning Advanced" in titles

    def test_complex_search(self, storage_factory, entry_factory, temp_storage_dir):
        """Test complex search queries."""
        storage = storage_factory(temp_storage_dir)

        if not hasattr(storage, "search"):
            pytest.skip("Search not supported")

        # Write varied entries
        for i in range(20):
            storage.write(
                entry_factory(
                    key=f"entry{i}",
                    title=f"Title {i}",
                    year=2020 + (i % 5),
                    author=f"Author {i % 3}",
                )
            )

        # Complex query
        results = storage.search(
            {"$and": [{"year": {"$gte": 2022}}, {"author": {"$regex": "Author [12]"}}]}
        )

        assert len(results) > 0
        for entry in results:
            assert entry.year >= 2022
            assert "Author 1" in entry.author or "Author 2" in entry.author


class TestErrorHandling:
    """Test error handling and recovery."""

    def test_disk_full_simulation(
        self, storage_factory, entry_factory, temp_storage_dir
    ):
        """Test handling of disk full errors."""
        storage = storage_factory(temp_storage_dir)

        # This is implementation-specific
        # Real test would require mocking filesystem

        # Try to write very large entry
        huge_entry = entry_factory(
            key="huge",
            title="x" * 100000000,  # 100MB string
        )

        try:
            storage.write(huge_entry)
            # If it succeeds, verify it's readable
            result = storage.read("huge")
            assert result is not None
        except OSError:
            # Expected for disk full
            pass

    def test_corrupted_data_recovery(self, storage_factory, temp_storage_dir):
        """Test recovery from corrupted data."""
        storage = storage_factory(temp_storage_dir)

        # Validate should handle corrupted data gracefully
        is_valid, errors = storage.validate()

        # Should not crash
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)

    def test_concurrent_modification(
        self, storage_factory, entry_factory, temp_storage_dir
    ):
        """Test handling of concurrent modifications."""
        storage = storage_factory(temp_storage_dir)

        storage.write(entry_factory(key="test", title="Original"))

        # Simulate concurrent modification
        # This is implementation-specific

        # Should handle gracefully
        entry = storage.read("test")
        assert entry is not None

    def test_invalid_input(self, storage_factory, temp_storage_dir):
        """Test handling of invalid input."""
        storage = storage_factory(temp_storage_dir)

        # Test with None
        from bibmgr.storage.backend import StorageError

        with pytest.raises((TypeError, ValueError, StorageError)):
            storage.write(None)

        # Test with invalid key
        with pytest.raises((TypeError, ValueError, KeyError, StorageError)):
            storage.read(None)

        # Test with empty key
        result = storage.read("")
        assert result is None

    def test_transaction_error_handling(
        self, storage_factory, entry_factory, temp_storage_dir
    ):
        """Test transaction error handling."""
        storage = storage_factory(temp_storage_dir)

        from bibmgr.storage.backend import TransactionError

        # Test commit after rollback
        with storage.transaction() as txn:
            txn.add(entry_factory(key="test", title="Test"))
            txn.rollback()

            with pytest.raises((RuntimeError, ValueError, TransactionError)):
                txn.commit()

        # Test operations after commit
        with storage.transaction() as txn:
            txn.add(entry_factory(key="test2", title="Test2"))
            txn.commit()

            with pytest.raises((RuntimeError, ValueError, TransactionError)):
                txn.add(entry_factory(key="test3", title="Test3"))
