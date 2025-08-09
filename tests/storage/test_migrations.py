"""Tests for data migration functionality.

This module tests the migration system that allows moving data between
different storage backends, creating backups, and managing data versioning.
"""

import json
import time
from datetime import datetime, timedelta

import pytest

from bibmgr.core.models import Collection, Entry, EntryType


class TestMigrationStats:
    """Test migration statistics tracking."""

    def test_migration_stats_creation(self):
        """MigrationStats tracks basic information."""
        from bibmgr.storage.migrations import MigrationStats

        started = datetime.now()
        stats = MigrationStats(
            started_at=started, total_entries=100, total_collections=10
        )

        assert stats.started_at == started
        assert stats.completed_at is None
        assert stats.total_entries == 100
        assert stats.migrated_entries == 0
        assert stats.failed_entries == 0
        assert stats.total_collections == 10
        assert stats.errors == []

    def test_migration_duration(self):
        """Duration calculated correctly."""
        from bibmgr.storage.migrations import MigrationStats

        started = datetime.now()
        stats = MigrationStats(started_at=started)

        assert stats.duration is None

        stats.completed_at = started + timedelta(seconds=5.5)
        assert stats.duration == 5.5

    def test_success_rate_calculation(self):
        """Success rate calculated correctly."""
        from bibmgr.storage.migrations import MigrationStats

        stats = MigrationStats(started_at=datetime.now())

        assert stats.success_rate == 100.0

        stats.total_entries = 80
        stats.migrated_entries = 75
        stats.failed_entries = 5
        stats.total_collections = 20
        stats.migrated_collections = 18
        stats.failed_collections = 2

        # (75 + 18) / (80 + 20) = 93 / 100 = 93%
        assert stats.success_rate == 93.0

    def test_stats_serialization(self):
        """Stats can be serialized to dict."""
        from bibmgr.storage.migrations import MigrationStats

        started = datetime.now()
        completed = started + timedelta(seconds=10)

        stats = MigrationStats(
            started_at=started,
            completed_at=completed,
            total_entries=50,
            migrated_entries=48,
            failed_entries=2,
            errors=["Error 1", "Error 2"],
        )

        data = stats.to_dict()

        assert data["started_at"] == started.isoformat()
        assert data["completed_at"] == completed.isoformat()
        assert data["duration"] == 10.0
        assert data["total_entries"] == 50
        assert data["success_rate"] == 96.0
        assert len(data["errors"]) == 2


class TestMigrationManager:
    """Test the migration manager functionality."""

    def test_migrate_entries_basic(self, mock_backend, sample_entries):
        """Basic entry migration between backends."""
        from bibmgr.storage.backends import MemoryBackend
        from bibmgr.storage.migrations import MigrationManager

        source = mock_backend
        for entry in sample_entries:
            source.write(entry.key, entry.to_dict())

        target = MemoryBackend()
        target.initialize()

        manager = MigrationManager()
        stats = manager.migrate_entries(source, target)

        assert stats.total_entries == len(sample_entries)
        assert stats.migrated_entries == len(sample_entries)
        assert stats.failed_entries == 0
        assert stats.completed_at is not None

        for entry in sample_entries:
            assert target.exists(entry.key)
            data = target.read(entry.key)
            assert data and data["title"] == entry.title

    def test_migrate_entries_with_failures(self, mock_backend):
        """Migration handles individual entry failures."""
        from bibmgr.storage.backends import MemoryBackend
        from bibmgr.storage.migrations import MigrationManager

        source = mock_backend
        source.write("good1", {"key": "good1", "type": "misc", "title": "Good 1"})
        source.write("bad", {"invalid": "data"})  # Missing required fields
        source.write("good2", {"key": "good2", "type": "misc", "title": "Good 2"})

        target = MemoryBackend()
        target.initialize()

        manager = MigrationManager()
        stats = manager.migrate_entries(source, target)

        assert stats.total_entries == 3
        assert stats.migrated_entries == 2
        assert stats.failed_entries == 1
        assert len(stats.errors) == 1
        assert "bad" in stats.errors[0]

        assert target.exists("good1")
        assert target.exists("good2")
        assert not target.exists("bad")

    def test_migrate_with_progress_callback(self, mock_backend, sample_entries):
        """Progress callback is called during migration."""
        from bibmgr.storage.backends import MemoryBackend
        from bibmgr.storage.migrations import MigrationManager

        source = mock_backend
        for entry in sample_entries:
            source.write(entry.key, entry.to_dict())

        target = MemoryBackend()
        target.initialize()

        progress_calls = []

        def track_progress(current, total):
            progress_calls.append((current, total))

        manager = MigrationManager()
        manager.set_progress_callback(track_progress)

        manager.migrate_entries(source, target, batch_size=2)

        assert len(progress_calls) > 0
        assert progress_calls[-1] == (len(sample_entries), len(sample_entries))

    @pytest.mark.skip(reason="Collections module will be reimplemented")
    def test_migrate_collections(self, mock_backend, nested_collections):
        """Collections can be migrated."""
        from bibmgr.storage.backends import MemoryBackend
        from bibmgr.storage.migrations import MigrationManager
        from bibmgr.storage.repository import CollectionRepository

        source = mock_backend
        source_repo = CollectionRepository(source)
        for collection in nested_collections:
            source_repo.save(collection)

        target = MemoryBackend()
        target.initialize()

        manager = MigrationManager()
        stats = manager.migrate_collections(source, target)

        assert stats.total_collections == len(nested_collections)
        assert stats.migrated_collections == len(nested_collections)
        assert stats.failed_collections == 0

        target_repo = CollectionRepository(target)
        for collection in nested_collections:
            migrated = target_repo.find(str(collection.id))
            assert migrated is not None
            assert migrated.name == collection.name

    def test_migrate_metadata(self, temp_dir):
        """Metadata can be migrated between directories."""
        from bibmgr.storage.metadata import EntryMetadata, MetadataStore, Note
        from bibmgr.storage.migrations import MigrationManager

        source_dir = temp_dir / "source"
        source_store = MetadataStore(source_dir)

        metadata = EntryMetadata(
            entry_key="test_entry", tags={"tag1", "tag2"}, rating=5, read_status="read"
        )
        source_store.save_metadata(metadata)

        note = Note(
            entry_key="test_entry", content="Test note content", note_type="summary"
        )
        source_store.add_note(note)

        target_dir = temp_dir / "target"
        manager = MigrationManager()
        stats = manager.migrate_metadata(source_dir, target_dir)

        assert stats.total_entries == 1
        assert stats.migrated_entries == 1
        assert stats.failed_entries == 0

        target_store = MetadataStore(target_dir)
        migrated_metadata = target_store.get_metadata("test_entry")
        assert migrated_metadata.tags == {"tag1", "tag2"}
        assert migrated_metadata.rating == 5

        migrated_notes = target_store.get_notes("test_entry")
        assert len(migrated_notes) == 1
        assert migrated_notes[0].content == "Test note content"

    @pytest.mark.skip(reason="Collections module will be reimplemented")
    def test_migrate_all_components(self, temp_dir, sample_entries):
        """Complete migration of all components."""
        from bibmgr.storage.backends import FileSystemBackend, MemoryBackend
        from bibmgr.storage.metadata import MetadataStore
        from bibmgr.storage.migrations import MigrationManager
        from bibmgr.storage.repository import RepositoryManager

        source_backend = FileSystemBackend(temp_dir / "source" / "storage")
        source_manager = RepositoryManager(source_backend)
        source_metadata = MetadataStore(temp_dir / "source")

        source_manager.import_entries(sample_entries)

        collection = Collection(name="Test Collection", entry_keys=("knuth1984",))
        source_manager.collections.save(collection)

        metadata = source_metadata.get_metadata("knuth1984")
        metadata.add_tags("classic")
        source_metadata.save_metadata(metadata)

        target_backend = MemoryBackend()
        target_backend.initialize()

        manager = MigrationManager()
        results = manager.migrate_all(
            source_backend, target_backend, temp_dir / "source", temp_dir / "target"
        )

        assert "entries" in results
        assert results["entries"].migrated_entries == len(sample_entries)
        assert "collections" in results
        assert results["collections"].migrated_collections == 1
        assert "metadata" in results
        assert results["metadata"].migrated_entries >= 1

    def test_verify_migration(self, mock_backend, sample_entries):
        """Migration verification detects issues."""
        from bibmgr.storage.backends import MemoryBackend
        from bibmgr.storage.migrations import MigrationManager

        source = mock_backend
        for entry in sample_entries:
            source.write(entry.key, entry.to_dict())

        target = MemoryBackend()
        target.initialize()

        for entry in sample_entries[:3]:
            target.write(entry.key, entry.to_dict())

        manager = MigrationManager()
        verification = manager.verify_migration(source, target)

        assert verification["source_count"] == len(sample_entries)
        assert verification["target_count"] == 3
        assert not verification["verification_passed"]
        assert len(verification["missing_in_target"]) == 2
        assert len(verification["extra_in_target"]) == 0

    def test_event_publishing(self):
        """Migration publishes events."""
        from bibmgr.storage.backends import MemoryBackend
        from bibmgr.storage.events import EventBus, EventType
        from bibmgr.storage.migrations import MigrationManager

        event_bus = EventBus()
        events = []
        event_bus.subscribe(EventType.INDEX_REBUILT, lambda e: events.append(e))

        source = MemoryBackend()
        source.initialize()
        source.write("test", {"key": "test", "type": "misc", "title": "Test"})

        target = MemoryBackend()
        target.initialize()

        manager = MigrationManager(event_bus)
        manager.migrate_entries(source, target)

        assert len(events) == 1
        assert events[0].type == EventType.INDEX_REBUILT
        assert "migration_stats" in events[0].data


class TestBackupManager:
    """Test backup and restore functionality."""

    def test_create_backup(self, temp_dir, sample_entries):
        """Backup creation works correctly."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.migrations import BackupManager
        from bibmgr.storage.repository import EntryRepository

        backend = FileSystemBackend(temp_dir / "storage")
        repo = EntryRepository(backend)

        for entry in sample_entries:
            repo.save(entry)

        backup_manager = BackupManager(temp_dir)
        backup_path = backup_manager.create_backup(backend, "test_backup")

        assert backup_path.exists()
        assert backup_path.name == "test_backup"
        assert (backup_path / "metadata.json").exists()
        assert (backup_path / "entries.json").exists()

        with open(backup_path / "metadata.json") as f:
            metadata = json.load(f)

        assert metadata["entry_count"] == len(sample_entries)
        assert metadata["backend_type"] == "FileSystemBackend"
        assert "created_at" in metadata

        with open(backup_path / "entries.json") as f:
            data = json.load(f)

        assert len(data["entries"]) == len(sample_entries)

    def test_auto_named_backup(self, temp_dir):
        """Backup with auto-generated name."""
        from bibmgr.storage.backends import MemoryBackend
        from bibmgr.storage.migrations import BackupManager

        backend = MemoryBackend()
        backend.initialize()

        backup_manager = BackupManager(temp_dir)
        backup_path = backup_manager.create_backup(backend)

        assert backup_path.exists()
        import re

        assert re.match(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}", backup_path.name)

    def test_list_backups(self, temp_dir):
        """List backups returns all backups with metadata."""
        from bibmgr.storage.backends import MemoryBackend
        from bibmgr.storage.migrations import BackupManager

        backend = MemoryBackend()
        backend.initialize()
        backend.write("test1", {"key": "test1", "type": "misc", "title": "Test 1"})
        backend.write("test2", {"key": "test2", "type": "misc", "title": "Test 2"})

        backup_manager = BackupManager(temp_dir)

        backup_manager.create_backup(backend, "backup1")
        time.sleep(0.1)  # Ensure different timestamps
        backup_manager.create_backup(backend, "backup2")

        backups = backup_manager.list_backups()

        assert len(backups) == 2
        assert backups[0]["name"] == "backup2"
        assert backups[1]["name"] == "backup1"

        for backup in backups:
            assert "path" in backup
            assert "created_at" in backup
            assert backup["entry_count"] == 2
            assert backup["size"] > 0

    def test_restore_backup(self, temp_dir, sample_entries):
        """Restore from backup works correctly."""
        from bibmgr.storage.backends import FileSystemBackend, MemoryBackend
        from bibmgr.storage.migrations import BackupManager
        from bibmgr.storage.repository import EntryRepository

        source_backend = FileSystemBackend(temp_dir / "source")
        source_repo = EntryRepository(source_backend)

        for entry in sample_entries:
            source_repo.save(entry)

        backup_manager = BackupManager(temp_dir)
        backup_manager.create_backup(source_backend, "test_restore")

        target_backend = MemoryBackend()
        target_backend.initialize()

        stats = backup_manager.restore_backup("test_restore", target_backend)

        assert stats.total_entries == len(sample_entries)
        assert stats.migrated_entries == len(sample_entries)
        assert stats.failed_entries == 0

        target_repo = EntryRepository(target_backend)
        for entry in sample_entries:
            restored = target_repo.find(entry.key)
            assert restored is not None
            assert restored.title == entry.title

    def test_restore_nonexistent_backup(self, temp_dir):
        """Restore from non-existent backup raises error."""
        from bibmgr.storage.backends import MemoryBackend
        from bibmgr.storage.migrations import BackupManager

        backup_manager = BackupManager(temp_dir)
        backend = MemoryBackend()
        backend.initialize()

        with pytest.raises(ValueError, match="Backup not found"):
            backup_manager.restore_backup("nonexistent", backend)

    def test_backup_with_errors(self, temp_dir):
        """Backup handles errors gracefully."""
        from bibmgr.storage.backends import MemoryBackend
        from bibmgr.storage.migrations import BackupManager

        backend = MemoryBackend()
        backend.initialize()

        backend.write(
            "bad", {"key": "bad", "func": lambda x: x}
        )  # Functions can't be serialized
        backend.write("good", {"key": "good", "type": "misc", "title": "Good"})

        backup_manager = BackupManager(temp_dir)

        backup_path = backup_manager.create_backup(backend, "graceful_backup")

        assert backup_path.exists()
        assert (backup_path / "metadata.json").exists()
        assert (backup_path / "entries.json").exists()

        import json

        with open(backup_path / "metadata.json") as f:
            metadata = json.load(f)
        assert metadata["entry_count"] == 2  # Backend has 2 entries

        from bibmgr.storage.importers.json import JsonImporter

        importer = JsonImporter()
        entries, errors = importer.import_file(backup_path / "entries.json")
        assert len(entries) == 1  # Only the good entry was exported
        assert entries[0].key == "good"
        assert entries[0].title == "Good"


class TestMigrationScenarios:
    """Test real-world migration scenarios."""

    def test_filesystem_to_sqlite_migration(self, temp_dir, sample_entries):
        """Migrate from filesystem to SQLite backend."""
        from bibmgr.storage.backends import FileSystemBackend, SQLiteBackend
        from bibmgr.storage.migrations import MigrationManager
        from bibmgr.storage.repository import RepositoryManager

        fs_backend = FileSystemBackend(temp_dir / "filesystem")
        fs_manager = RepositoryManager(fs_backend)
        fs_manager.import_entries(sample_entries)

        sqlite_backend = SQLiteBackend(temp_dir / "database.db")

        manager = MigrationManager()
        stats = manager.migrate_entries(fs_backend, sqlite_backend)

        assert stats.migrated_entries == len(sample_entries)
        assert stats.failed_entries == 0

        sqlite_manager = RepositoryManager(sqlite_backend)
        for entry in sample_entries:
            migrated = sqlite_manager.entries.find(entry.key)
            assert migrated is not None
            assert migrated.title == entry.title

        results = sqlite_backend.search("Knuth")
        assert len(results) == 1
        assert results[0] == "knuth1984"

    def test_incremental_backup_strategy(self, temp_dir):
        """Test incremental backup strategy."""

        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.migrations import BackupManager
        from bibmgr.storage.repository import RepositoryManager

        backend = FileSystemBackend(temp_dir / "storage")
        manager = RepositoryManager(backend)
        backup_manager = BackupManager(temp_dir)

        entries_v1 = [
            Entry(key="entry1", type=EntryType.MISC, title="Entry 1"),
            Entry(key="entry2", type=EntryType.MISC, title="Entry 2"),
        ]
        manager.import_entries(entries_v1)

        backup_manager.create_backup(backend, "backup_v1")

        entries_v2 = [
            Entry(key="entry3", type=EntryType.MISC, title="Entry 3"),
        ]
        manager.import_entries(entries_v2)

        backup_manager.create_backup(backend, "backup_v2")

        backups = backup_manager.list_backups()
        assert len(backups) == 2

        assert backups[0]["name"] == "backup_v2"
        assert backups[0]["entry_count"] == 3
        assert backups[1]["name"] == "backup_v1"
        assert backups[1]["entry_count"] == 2

    def test_migration_rollback(self, temp_dir, sample_entries):
        """Test migration with rollback on failure."""
        from bibmgr.storage.backends import FileSystemBackend, MemoryBackend
        from bibmgr.storage.migrations import MigrationManager

        source = FileSystemBackend(temp_dir / "source")
        for entry in sample_entries:
            source.write(entry.key, entry.to_dict())

        target = MemoryBackend()
        target.initialize()

        write_count = 0
        original_write = target.write

        def failing_write(key, data):
            nonlocal write_count
            write_count += 1
            if write_count == 3:
                raise Exception("Write failed")
            original_write(key, data)

        target.write = failing_write

        manager = MigrationManager()
        stats = manager.migrate_entries(source, target, batch_size=2)

        assert stats.migrated_entries == 4  # All except the failed one
        assert stats.failed_entries >= 1
        assert len(stats.errors) >= 1

        assert len(target.keys()) == 4


class TestMigrationPerformance:
    """Test migration performance with large datasets."""

    def test_large_migration_performance(self, temp_dir, performance_entries):
        """Large migrations complete in reasonable time."""
        from bibmgr.storage.backends import MemoryBackend
        from bibmgr.storage.migrations import MigrationManager

        source = MemoryBackend()
        source.initialize()

        for entry in performance_entries[:500]:  # 500 entries
            source.write(entry.key, entry.to_dict())

        target = MemoryBackend()
        target.initialize()

        manager = MigrationManager()

        start = time.time()
        stats = manager.migrate_entries(source, target, batch_size=50)
        duration = time.time() - start

        assert duration < 2.0  # Within 2 seconds
        assert stats.migrated_entries == 500
        assert stats.failed_entries == 0

    def test_progress_callback_overhead(self, temp_dir, performance_entries):
        """Progress callbacks don't significantly impact performance."""
        from bibmgr.storage.backends import MemoryBackend
        from bibmgr.storage.migrations import MigrationManager

        source = MemoryBackend()
        source.initialize()

        for entry in performance_entries[:100]:
            source.write(entry.key, entry.to_dict())

        target = MemoryBackend()
        target.initialize()

        manager = MigrationManager()

        start = time.time()
        manager.migrate_entries(source, target)
        time_without_callback = time.time() - start

        target.clear()

        call_count = 0

        def progress_callback(current, total):
            nonlocal call_count
            call_count += 1

        manager.set_progress_callback(progress_callback)

        start = time.time()
        manager.migrate_entries(source, target, batch_size=10)
        time_with_callback = time.time() - start

        assert (
            time_with_callback < time_without_callback * 1.5
        )  # Less than 50% overhead
        assert call_count > 0  # Callback was called
