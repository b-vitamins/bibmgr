"""Tests for storage backend implementations.

This module tests the storage backend interface and its implementations
(filesystem, memory, SQLite). Each backend must conform to the same
interface and pass the same tests.
"""

import json
import sqlite3
import threading
import time
from pathlib import Path

import pytest


class BackendContract:
    """Contract tests that all backends must pass."""

    def test_initialize_creates_structure(self, backend):
        """initialize() sets up necessary structure."""
        backend.initialize()
        assert backend.keys() == []

    def test_read_write_cycle(self, backend):
        """Basic read/write operations work correctly."""
        backend.initialize()

        data = {"key": "test", "type": "article", "title": "Test Article"}

        assert backend.read("test") is None
        assert backend.exists("test") is False

        backend.write("test", data)

        assert backend.exists("test") is True
        read_data = backend.read("test")
        assert read_data == data

    def test_delete_existing_key(self, backend):
        """delete() removes existing data."""
        backend.initialize()

        backend.write("test", {"data": "value"})
        assert backend.exists("test") is True

        assert backend.delete("test") is True
        assert backend.exists("test") is False
        assert backend.read("test") is None

    def test_delete_nonexistent_key(self, backend):
        """delete() returns False for non-existent keys."""
        backend.initialize()

        assert backend.delete("nonexistent") is False

    def test_keys_returns_all_keys(self, backend):
        """keys() returns all stored keys."""
        backend.initialize()

        assert backend.keys() == []

        backend.write("key1", {"data": 1})
        backend.write("key2", {"data": 2})
        backend.write("key3", {"data": 3})

        keys = backend.keys()
        assert len(keys) == 3
        assert set(keys) == {"key1", "key2", "key3"}

    def test_clear_removes_all_data(self, backend):
        """clear() removes all stored data."""
        backend.initialize()

        backend.write("key1", {"data": 1})
        backend.write("key2", {"data": 2})
        assert len(backend.keys()) == 2

        backend.clear()

        assert backend.keys() == []
        assert backend.read("key1") is None
        assert backend.read("key2") is None

    def test_overwrite_existing_key(self, backend):
        """Writing to existing key overwrites data."""
        backend.initialize()

        backend.write("key", {"version": 1})
        backend.write("key", {"version": 2})

        data = backend.read("key")
        assert data == {"version": 2}

    def test_handle_complex_data(self, backend):
        """Backend handles complex nested data structures."""
        backend.initialize()

        complex_data = {
            "key": "complex",
            "nested": {
                "list": [1, 2, 3],
                "dict": {"a": "b"},
                "null": None,
                "bool": True,
            },
            "unicode": "αβγδ",
            "special": "Line\nbreak and\ttab",
        }

        backend.write("complex", complex_data)
        read_data = backend.read("complex")

        assert read_data == complex_data

    def test_concurrent_access(self, backend):
        """Backend handles concurrent access safely."""
        backend.initialize()

        errors = []

        def writer(key_prefix, count):
            try:
                for i in range(count):
                    backend.write(f"{key_prefix}_{i}", {"value": i})
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(3):
            t = threading.Thread(target=writer, args=(f"thread{i}", 10))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(backend.keys()) == 30  # 3 threads × 10 writes


class TestFileSystemBackend(BackendContract):
    """Test filesystem-specific backend functionality."""

    @pytest.fixture
    def backend(self, temp_dir):
        """Create filesystem backend instance."""
        from bibmgr.storage.backends import FileSystemBackend

        return FileSystemBackend(temp_dir)

    def test_creates_directory_structure(self, temp_dir):
        """FileSystemBackend creates necessary directories."""
        from bibmgr.storage.backends import FileSystemBackend

        FileSystemBackend(temp_dir)

        assert (temp_dir / "entries").is_dir()
        assert (temp_dir / "index.json").exists()

    def test_atomic_writes(self, backend, temp_dir):
        """Writes are atomic (no partial writes on failure)."""
        backend.initialize()

        def failing_write(key, data):
            path = backend._get_path(key)
            path.write_text("partial")
            raise Exception("Write failed")

        backend._write_impl = failing_write

        with pytest.raises(Exception, match="Write failed"):
            backend.write("test", {"data": "value"})

        assert backend.read("test") is None
        assert not any(temp_dir.glob("**/*.tmp"))

    def test_handles_invalid_keys(self, backend):
        """Filesystem backend sanitizes keys for safe filenames."""
        backend.initialize()

        unsafe_keys = [
            "../../etc/passwd",
            "key/with/slashes",
            "key:with:colons",
            "key with spaces",
            "key*with?wildcards",
        ]

        for key in unsafe_keys:
            backend.write(key, {"key": key})
            assert backend.read(key) == {"key": key}

    def test_backup_and_restore(self, backend, temp_dir):
        """Backup and restore functionality works correctly."""
        backend.initialize()

        backend.write("key1", {"data": 1})
        backend.write("key2", {"data": 2})

        import tempfile

        with tempfile.TemporaryDirectory() as backup_root:
            backup_dir = Path(backup_root) / "backup"
            backend.backup(backup_dir)

            backend.clear()
            assert backend.keys() == []

            backend.restore(backup_dir)

            assert set(backend.keys()) == {"key1", "key2"}
            assert backend.read("key1") == {"data": 1}
            assert backend.read("key2") == {"data": 2}

    def test_handles_corrupted_files(self, backend, temp_dir):
        """Backend handles corrupted JSON files gracefully."""
        backend.initialize()

        backend.write("valid", {"data": "ok"})

        backend.write("corrupt", {"data": "value"})
        corrupt_path = backend._get_path("corrupt")
        corrupt_path.write_text("not valid json{")

        assert backend.read("corrupt") is None
        assert backend.read("valid") == {"data": "ok"}

        # keys() should skip corrupted files
        keys = backend.keys()
        assert "valid" in keys
        # corrupt key might still be in index


class TestMemoryBackend(BackendContract):
    """Test in-memory backend implementation."""

    @pytest.fixture
    def backend(self):
        """Create memory backend instance."""
        from bibmgr.storage.backends import MemoryBackend

        return MemoryBackend()

    def test_data_isolation(self):
        """Multiple instances have isolated data."""
        from bibmgr.storage.backends import MemoryBackend

        backend1 = MemoryBackend()
        backend2 = MemoryBackend()

        backend1.initialize()
        backend2.initialize()

        backend1.write("key", {"instance": 1})
        backend2.write("key", {"instance": 2})

        assert backend1.read("key") == {"instance": 1}
        assert backend2.read("key") == {"instance": 2}

    def test_deep_copy_on_read(self, backend):
        """Reading returns deep copies to prevent mutation."""
        backend.initialize()

        original = {"nested": {"list": [1, 2, 3]}}
        backend.write("key", original)

        read1 = backend.read("key")
        read1["nested"]["list"].append(4)

        read2 = backend.read("key")
        assert read2 == {"nested": {"list": [1, 2, 3]}}
        assert read2 is not read1

    def test_transaction_rollback(self, backend):
        """Transactions can be rolled back."""
        backend.initialize()

        backend.write("existing", {"value": "original"})

        with pytest.raises(Exception):
            with backend.begin_transaction():
                backend.write("new", {"value": "new"})
                backend.write("existing", {"value": "modified"})
                raise Exception("Rollback")

        assert backend.read("new") is None
        assert backend.read("existing") == {"value": "original"}


class TestSQLiteBackend(BackendContract):
    """Test SQLite-specific backend functionality."""

    @pytest.fixture
    def backend(self, temp_dir):
        """Create SQLite backend instance."""
        from bibmgr.storage.backends import SQLiteBackend

        return SQLiteBackend(temp_dir / "test.db")

    def test_creates_schema(self, backend, temp_dir):
        """SQLiteBackend creates proper database schema."""
        backend.initialize()

        conn = sqlite3.connect(str(temp_dir / "test.db"))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor}

        assert "entries" in tables
        assert "entries_fts" in tables  # Full-text search

        conn.close()

    def test_full_text_search(self, backend):
        """SQLite backend supports full-text search."""
        backend.initialize()

        backend.write(
            "entry1",
            {
                "key": "entry1",
                "title": "Introduction to Machine Learning",
                "abstract": "This paper discusses neural networks and deep learning.",
                "author": "John Smith",
            },
        )

        backend.write(
            "entry2",
            {
                "key": "entry2",
                "title": "Database Systems",
                "abstract": "A comprehensive guide to relational databases.",
                "author": "Jane Doe",
            },
        )

        backend.write(
            "entry3",
            {
                "key": "entry3",
                "title": "Deep Learning Fundamentals",
                "abstract": "Advanced topics in neural network architectures.",
                "author": "Bob Johnson",
            },
        )

        results = backend.search("learning")
        assert len(results) == 2
        assert set(results) == {"entry1", "entry3"}

        results = backend.search("database")
        assert results == ["entry2"]

        results = backend.search("Smith")
        assert results == ["entry1"]

    def test_query_entries(self, backend):
        """SQLite backend supports structured queries."""
        backend.initialize()

        for i in range(5):
            backend.write(
                f"article{i}",
                {
                    "key": f"article{i}",
                    "type": "article",
                    "year": 2020 + i,
                    "author": f"Author {i % 2}",
                },
            )

        for i in range(3):
            backend.write(
                f"book{i}",
                {
                    "key": f"book{i}",
                    "type": "book",
                    "year": 2018 + i,
                    "author": "Book Author",
                },
            )

        articles = backend.query_entries({"type": "article"})
        assert len(articles) == 5
        assert all(key.startswith("article") for key in articles)

        recent = backend.query_entries({"year": 2022})
        assert len(recent) == 1

        author0 = backend.query_entries({"author": "Author 0"})
        assert len(author0) == 3  # article0, article2, article4

    def test_transaction_isolation(self, backend):
        """Transactions provide proper isolation."""
        backend.initialize()

        backend.write("key", {"version": 1})

        conn2 = sqlite3.connect(backend.db_path)
        conn2.execute("BEGIN")
        conn2.execute(
            "UPDATE entries SET data = ? WHERE key = ?",
            (json.dumps({"version": 2}), "key"),
        )

        assert backend.read("key") == {"version": 1}

        conn2.commit()
        conn2.close()

        assert backend.read("key") == {"version": 2}

    def test_concurrent_transactions(self, backend):
        """Multiple concurrent transactions work correctly."""
        backend.initialize()

        results = []

        def writer(value):
            try:
                with backend.begin_transaction():
                    for i in range(5):
                        backend.write(f"{value}_{i}", {"value": value, "index": i})
                        time.sleep(0.001)  # Simulate work
                results.append("success")
            except Exception as e:
                results.append(f"error: {e}")

        threads = []
        for i in range(3):
            t = threading.Thread(target=writer, args=(f"thread{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert all(r == "success" for r in results)
        assert len(backend.keys()) == 15  # 3 threads × 5 writes

    def test_statistics(self, backend):
        """SQLite backend provides statistics efficiently."""
        backend.initialize()

        for i in range(10):
            backend.write(
                f"entry{i}",
                {
                    "key": f"entry{i}",
                    "type": "article" if i < 6 else "book",
                    "year": 2020 + (i % 3),
                },
            )

        stats = backend.get_statistics()

        assert stats["total_entries"] == 10
        assert stats["by_type"]["article"] == 6
        assert stats["by_type"]["book"] == 4
        assert stats["by_year"][2020] == 4
        assert stats["by_year"][2021] == 3
        assert stats["by_year"][2022] == 3


class TestCachedBackend:
    """Test caching backend functionality."""

    def test_cache_hit_on_repeated_reads(self):
        """Repeated reads use cache."""
        from bibmgr.storage.backends import CachedBackend

        class CachedMemoryBackend(CachedBackend):
            def __init__(self, cache_size=10):
                super().__init__(cache_size)
                self._data = {}

            def initialize(self):
                """Initialize the backend."""
                pass

            def _read_impl(self, key):
                return self._data.get(key)

            def _write_impl(self, key, data):
                self._data[key] = data

            def _delete_impl(self, key):
                if key in self._data:
                    del self._data[key]
                    return True
                return False

            def exists(self, key):
                return key in self._data

            def keys(self):
                return list(self._data.keys())

            def clear(self):
                self._data.clear()
                self._read_cache.cache_clear()

            def close(self):
                pass

        backend = CachedMemoryBackend(cache_size=10)
        backend.initialize()

        backend.write("key", {"data": "value"})

        data1 = backend.read("key")
        assert data1 == {"data": "value"}

        cache_info = backend._read_cache.cache_info()
        hits_before = cache_info.hits

        data2 = backend.read("key")
        assert data2 == {"data": "value"}

        cache_info = backend._read_cache.cache_info()
        assert cache_info.hits == hits_before + 1

    def test_cache_invalidation_on_write(self):
        """Cache is invalidated when data is written."""
        from bibmgr.storage.backends import CachedBackend

        class CachedMemoryBackend(CachedBackend):
            def __init__(self, cache_size=10):
                super().__init__(cache_size)
                self._data = {}

            def initialize(self):
                """Initialize the backend."""
                pass

            def _read_impl(self, key):
                return self._data.get(key)

            def _write_impl(self, key, data):
                self._data[key] = data

            def _delete_impl(self, key):
                if key in self._data:
                    del self._data[key]
                    return True
                return False

            def exists(self, key):
                return key in self._data

            def keys(self):
                return list(self._data.keys())

            def clear(self):
                self._data.clear()
                self._read_cache.cache_clear()

            def close(self):
                pass

        backend = CachedMemoryBackend(cache_size=10)
        backend.initialize()

        backend.write("key", {"version": 1})
        assert backend.read("key") == {"version": 1}

        backend.write("key", {"version": 2})

        assert backend.read("key") == {"version": 2}

    def test_cache_size_limit(self):
        """Cache respects size limit using LRU eviction."""
        from bibmgr.storage.backends import CachedBackend

        class CachedMemoryBackend(CachedBackend):
            def __init__(self, cache_size=3):
                super().__init__(cache_size)
                self._data = {}

            def initialize(self):
                """Initialize the backend."""
                pass

            def _read_impl(self, key):
                return self._data.get(key)

            def _write_impl(self, key, data):
                self._data[key] = data

            def _delete_impl(self, key):
                if key in self._data:
                    del self._data[key]
                    return True
                return False

            def exists(self, key):
                return key in self._data

            def keys(self):
                return list(self._data.keys())

            def clear(self):
                self._data.clear()
                self._read_cache.cache_clear()

            def close(self):
                pass

        backend = CachedMemoryBackend(cache_size=3)
        backend.initialize()

        for i in range(5):
            backend.write(f"key{i}", {"value": i})

        for i in range(5):
            backend.read(f"key{i}")

        cache_info = backend._read_cache.cache_info()
        assert cache_info.currsize == 3
