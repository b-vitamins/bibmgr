"""Integration tests for the storage module.

This module tests the complete storage system working together,
including repositories, backends, metadata, queries, and events.
"""

import threading
import time
from datetime import datetime

from bibmgr.core.models import Collection, Entry, EntryType


class TestStorageSystemIntegration:
    """Test complete storage system integration."""

    def test_full_storage_lifecycle(self, temp_dir):
        """Test complete entry lifecycle through storage system."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.events import EventBus, EventType
        from bibmgr.storage.metadata import MetadataStore
        from bibmgr.storage.repository import RepositoryManager

        backend = FileSystemBackend(temp_dir / "storage")
        event_bus = EventBus()
        metadata_store = MetadataStore(temp_dir / "metadata")

        events = []
        event_bus.subscribe(EventType.ENTRY_CREATED, lambda e: events.append(e))
        event_bus.subscribe(EventType.ENTRY_UPDATED, lambda e: events.append(e))
        event_bus.subscribe(EventType.ENTRY_DELETED, lambda e: events.append(e))

        manager = RepositoryManager(backend, metadata_store)

        entry = Entry(
            key="test2024",
            type=EntryType.ARTICLE,
            title="Test Article",
            author="Test Author",
            journal="Test Journal",
            year=2024,
        )

        manager.entries.save(entry)

        metadata = metadata_store.get_metadata("test2024")
        metadata.add_tags("test", "integration")
        metadata.rating = 5
        metadata.read_status = "read"
        metadata_store.save_metadata(metadata)

        from bibmgr.storage.metadata import Note

        note = Note(
            entry_key="test2024",
            content="This is a test note for integration testing",
            note_type="general",
        )
        metadata_store.add_note(note)

        assert backend.exists("test2024")
        loaded = manager.entries.find("test2024")
        assert loaded is not None
        assert loaded.title == "Test Article"

        loaded_metadata = metadata_store.get_metadata("test2024")
        assert loaded_metadata.tags == {"test", "integration"}
        assert loaded_metadata.rating == 5
        assert loaded_metadata.notes_count == 1

        notes = metadata_store.get_notes("test2024")
        assert len(notes) == 1
        assert notes[0].content == "This is a test note for integration testing"

        import msgspec

        updated = msgspec.structs.replace(entry, title="Updated Article")
        manager.entries.save(updated)

        manager.entries.delete("test2024")

        assert not backend.exists("test2024")
        assert manager.entries.find("test2024") is None

        fresh_metadata = metadata_store.get_metadata("test2024")
        assert fresh_metadata.tags == set()  # New metadata created

    def test_query_with_metadata_integration(self, temp_dir, sample_entries):
        """Test querying entries with metadata filters."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.metadata import MetadataStore
        from bibmgr.storage.repository import QueryBuilder, RepositoryManager

        backend = FileSystemBackend(temp_dir / "storage")
        manager = RepositoryManager(backend)
        metadata_store = MetadataStore(temp_dir / "metadata")

        manager.import_entries(sample_entries)

        metadata1 = metadata_store.get_metadata("knuth1984")
        metadata1.add_tags("classic", "must-read")
        metadata1.rating = 5
        metadata1.importance = "high"
        metadata_store.save_metadata(metadata1)

        metadata2 = metadata_store.get_metadata("turing1950")
        metadata2.add_tags("classic", "ai", "foundational")
        metadata2.rating = 5
        metadata2.read_status = "read"
        metadata_store.save_metadata(metadata2)

        metadata3 = metadata_store.get_metadata("dijkstra1968")
        metadata3.add_tags("programming", "controversial")
        metadata3.rating = 4
        metadata_store.save_metadata(metadata3)

        old_entries = manager.entries.find_by(QueryBuilder().where("year", "<", 1970))
        assert len(old_entries) == 3  # Turing, Dijkstra, Shannon

        classic_keys = metadata_store.find_by_tag("classic")
        assert set(classic_keys) == {"knuth1984", "turing1950"}

        old_entry_keys = {e.key for e in old_entries}
        highly_rated = []

        for key in old_entry_keys:
            metadata = metadata_store.get_metadata(key)
            if metadata.rating and metadata.rating >= 4:
                entry = manager.entries.find(key)
                if entry:
                    highly_rated.append(entry)

        assert len(highly_rated) == 2  # Turing and Dijkstra

    def test_collection_management(self, temp_dir, sample_entries):
        """Test collection creation and management."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.repository import RepositoryManager

        backend = FileSystemBackend(temp_dir / "storage")
        manager = RepositoryManager(backend)

        manager.import_entries(sample_entries)

        classics = Collection(
            name="Classic Papers",
            description="Foundational CS papers",
            entry_keys=("knuth1984", "turing1950", "dijkstra1968"),
            color="#FF0000",
        )
        manager.collections.save(classics)

        recent = Collection(
            name="Recent Papers",
            description="Papers from last 30 years",
            query="year >= 1994",
        )
        manager.collections.save(recent)

        all_collections = manager.collections.find_all()
        assert len(all_collections) == 2

        classics_loaded = manager.collections.find(str(classics.id))
        assert classics_loaded is not None
        assert classics_loaded.entry_keys and len(classics_loaded.entry_keys) == 3

        smart_collections = manager.collections.find_smart_collections()
        assert len(smart_collections) == 1
        assert smart_collections[0].name == "Recent Papers"

    def test_concurrent_operations(self, temp_dir):
        """Test concurrent read/write operations."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.repository import QueryBuilder, RepositoryManager

        backend = FileSystemBackend(temp_dir / "storage")
        manager = RepositoryManager(backend)

        errors = []
        results = []

        def writer(start_idx):
            try:
                for i in range(10):
                    entry = Entry(
                        key=f"entry_{start_idx}_{i}",
                        type=EntryType.MISC,
                        title=f"Entry {start_idx}-{i}",
                        year=2020 + (i % 5),
                    )
                    manager.entries.save(entry)
                    time.sleep(0.001)  # Small delay
                results.append(f"writer_{start_idx}_done")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(20):
                    manager.entries.find_all()
                    manager.entries.find_by(QueryBuilder().where("year", ">=", 2022))
                    time.sleep(0.001)
                results.append("reader_done")
            except Exception as e:
                errors.append(e)

        threads = []

        for i in range(3):
            t = threading.Thread(target=writer, args=(i,))
            threads.append(t)
            t.start()

        for i in range(2):
            t = threading.Thread(target=reader)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5  # 3 writers + 2 readers

        all_entries = manager.entries.find_all()
        assert len(all_entries) == 30  # 3 writers × 10 entries

    def test_backup_and_restore(self, temp_dir, sample_entries):
        """Test backup and restore functionality."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.metadata import MetadataStore
        from bibmgr.storage.repository import RepositoryManager

        backend = FileSystemBackend(temp_dir / "storage")
        manager = RepositoryManager(backend)
        metadata_store = MetadataStore(temp_dir / "metadata")

        manager.import_entries(sample_entries)

        metadata = metadata_store.get_metadata("knuth1984")
        metadata.add_tags("backup-test")
        metadata.rating = 5
        metadata_store.save_metadata(metadata)

        backup_dir = temp_dir / "backup"
        backend.backup(backup_dir)

        backend.clear()
        metadata_store.delete_metadata("knuth1984")

        assert manager.entries.count() == 0
        assert metadata_store.get_metadata("knuth1984").tags == set()

        backend.restore(backup_dir)

        assert manager.entries.count() == len(sample_entries)
        restored_entry = manager.entries.find("knuth1984")
        assert restored_entry is not None
        assert restored_entry.title == "The TeXbook"

    def test_import_export_pipeline(self, temp_dir):
        """Test complete import/export pipeline."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.importers import BibtexImporter, JsonImporter
        from bibmgr.storage.repository import RepositoryManager

        backend = FileSystemBackend(temp_dir / "storage")
        manager = RepositoryManager(backend)

        bibtex_content = """
        @article{test2024,
            author = {Test Author},
            title = {Test Article with Special Characters: 100\\% Success},
            journal = {Test Journal},
            year = 2024,
            doi = {10.1234/test.2024},
            keywords = {test, import, export}
        }

        @book{book2024,
            author = {Book Author},
            title = {Test Book},
            publisher = {Test Publisher},
            year = 2024,
            isbn = {978-1234567890}
        }
        """

        bibtex_importer = BibtexImporter()
        entries, errors = bibtex_importer.import_text(bibtex_content)
        assert len(entries) == 2
        assert len(errors) == 0

        results = manager.import_entries(entries)
        assert all(results.values())

        json_file = temp_dir / "export.json"
        json_importer = JsonImporter()
        json_importer.export_entries(manager.entries.find_all(), json_file)

        backend.clear()
        assert manager.entries.count() == 0

        imported, import_errors = json_importer.import_file(json_file)
        assert len(imported) == 2
        assert len(import_errors) == 0

        manager.import_entries(imported)

        test_entry = manager.entries.find("test2024")
        assert test_entry is not None
        assert test_entry.title and "100% Success" in test_entry.title
        assert test_entry.doi == "10.1234/test.2024"
        assert test_entry.keywords == ("test", "import", "export")

    def test_performance_with_large_dataset(self, temp_dir, performance_entries):
        """Test performance with large number of entries."""
        import time

        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.repository import QueryBuilder, RepositoryManager

        backend = FileSystemBackend(temp_dir / "storage")
        manager = RepositoryManager(backend)

        start = time.time()
        results = manager.import_entries(performance_entries[:100])  # First 100
        import_time = time.time() - start

        assert all(results.values())
        assert import_time < 2.0  # Should complete within 2 seconds

        start = time.time()
        query = (
            QueryBuilder()
            .where("year", ">=", 2010)
            .where("year", "<=", 2020)
            .where("author", "contains", "Author 5")
        )
        results = manager.entries.find_by(query)
        query_time = time.time() - start

        assert len(results) > 0
        assert query_time < 0.5  # Should complete within 500ms

        start = time.time()
        all_entries = manager.entries.find_all()
        scan_time = time.time() - start

        assert len(all_entries) == 100
        assert scan_time < 1.0  # Should complete within 1 second

    def test_error_recovery(self, temp_dir):
        """Test system behavior under error conditions."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.repository import RepositoryManager

        backend = FileSystemBackend(temp_dir / "storage")
        manager = RepositoryManager(backend)

        invalid_entries = [
            Entry(key="valid", type=EntryType.MISC, title="Valid"),
            Entry(key="", type=EntryType.MISC, title="Empty Key"),  # Invalid
            Entry(
                key="valid2", type=EntryType.ARTICLE, title="Missing Required"
            ),  # Invalid
        ]

        results = manager.import_entries(invalid_entries)

        assert results["valid"] is True
        assert results[""] is False
        assert results["valid2"] is False

        assert manager.entries.count() == 1

        entry = Entry(
            key="corrupt_test", type=EntryType.MISC, title="Will be corrupted"
        )
        manager.entries.save(entry)

        entry_path = backend._get_path("corrupt_test")
        entry_path.write_text("not valid json{")

        assert manager.entries.find("corrupt_test") is None
        all_entries = manager.entries.find_all()
        assert len(all_entries) == 1  # Only the valid entry

    def test_migration_compatibility(self, temp_dir):
        """Test data migration and version compatibility."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.repository import RepositoryManager

        backend = FileSystemBackend(temp_dir / "storage")
        manager = RepositoryManager(backend)

        old_format_entry = {
            "key": "old_entry",
            "type": "article",  # String instead of enum
            "title": "Old Format Entry",
            "author": "Old Author",
            "year": "2020",  # String instead of int
            "journal": "Old Journal",
            "keywords": "old,format,test",  # String instead of tuple
        }

        backend.write("old_entry", old_format_entry)

        entry = manager.entries.find("old_entry")
        assert entry is not None
        assert entry.type == EntryType.ARTICLE
        assert entry.year == 2020  # Converted to int
        assert isinstance(entry.keywords, tuple)
        assert entry.keywords == ("old", "format", "test")


class TestStorageSystemScenarios:
    """Test real-world usage scenarios."""

    def test_research_workflow(self, temp_dir):
        """Test typical research workflow with papers."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.metadata import MetadataStore, Note
        from bibmgr.storage.repository import RepositoryManager

        backend = FileSystemBackend(temp_dir / "storage")
        manager = RepositoryManager(backend)
        metadata_store = MetadataStore(temp_dir / "metadata")

        # 1. Import papers from conference
        conference_papers = [
            Entry(
                key="ml2024_paper1",
                type=EntryType.INPROCEEDINGS,
                title="Novel Deep Learning Architecture",
                author="Alice Smith and Bob Jones",
                booktitle="ICML 2024",
                year=2024,
            ),
            Entry(
                key="ml2024_paper2",
                type=EntryType.INPROCEEDINGS,
                title="Transformer Improvements",
                author="Carol White and Dave Black",
                booktitle="ICML 2024",
                year=2024,
            ),
        ]

        manager.import_entries(conference_papers)

        # 2. Add to reading list
        for paper in conference_papers:
            metadata = metadata_store.get_metadata(paper.key)
            metadata.add_tags("icml2024", "to-read", "deep-learning")
            metadata.importance = "high"
            metadata_store.save_metadata(metadata)

        # 3. Read and annotate first paper
        metadata = metadata_store.get_metadata("ml2024_paper1")
        metadata.read_status = "read"
        metadata.rating = 4
        metadata.read_date = datetime.now()
        metadata_store.save_metadata(metadata)

        note1 = Note(
            entry_key="ml2024_paper1",
            content="Interesting approach to batch normalization",
            note_type="idea",
            page=5,
        )
        metadata_store.add_note(note1)

        note2 = Note(
            entry_key="ml2024_paper1",
            content="Could be applied to our current project",
            note_type="idea",
        )
        metadata_store.add_note(note2)

        # 4. Find unread high-importance papers
        unread_important = []
        for key in metadata_store.find_by_tag("to-read"):
            metadata = metadata_store.get_metadata(key)
            if metadata.importance == "high" and metadata.read_status == "unread":
                entry = manager.entries.find(key)
                if entry:
                    unread_important.append(entry)

        assert len(unread_important) == 1
        assert unread_important[0].key == "ml2024_paper2"

        # 5. Create collection for good papers
        good_papers = Collection(
            name="High Quality ML Papers",
            description="Papers rated 4 or 5 stars",
        )

        for entry in manager.entries.find_all():
            metadata = metadata_store.get_metadata(entry.key)
            if metadata.rating and metadata.rating >= 4:
                good_papers = good_papers.add_entry(entry.key)

        manager.collections.save(good_papers)

        assert len(good_papers.entry_keys or []) == 1

    def test_collaborative_bibliography(self, temp_dir):
        """Test collaborative bibliography management."""

        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.events import EventBus
        from bibmgr.storage.repository import RepositoryManager

        backend1 = FileSystemBackend(temp_dir / "user1")
        manager1 = RepositoryManager(backend1)

        backend2 = FileSystemBackend(temp_dir / "user2")
        manager2 = RepositoryManager(backend2)

        EventBus()

        entries_user1 = [
            Entry(
                key="shared1",
                type=EntryType.ARTICLE,
                title="Shared Paper 1",
                author="Author A",
                journal="Journal A",
                year=2023,
            ),
            Entry(
                key="user1_only",
                type=EntryType.ARTICLE,
                title="User 1 Paper",
                author="Author B",
                journal="Journal B",
                year=2023,
            ),
        ]
        manager1.import_entries(entries_user1)

        entries_user2 = [
            Entry(
                key="shared1",
                type=EntryType.ARTICLE,
                title="Shared Paper 1",
                author="Author A",
                journal="Journal A",
                year=2023,
            ),
            Entry(
                key="user2_only",
                type=EntryType.ARTICLE,
                title="User 2 Paper",
                author="Author C",
                journal="Journal C",
                year=2023,
            ),
        ]
        manager2.import_entries(entries_user2)

        merged_dir = temp_dir / "merged"
        backend_merged = FileSystemBackend(merged_dir)
        manager_merged = RepositoryManager(backend_merged)

        all_entries = {}

        for entry in manager1.entries.find_all():
            all_entries[entry.key] = entry

        for entry in manager2.entries.find_all():
            if entry.key not in all_entries:
                all_entries[entry.key] = entry

        manager_merged.import_entries(list(all_entries.values()))

        assert manager_merged.entries.count() == 3  # shared1, user1_only, user2_only

        shared = manager_merged.entries.find("shared1")
        assert shared is not None
        assert shared.title == "Shared Paper 1"
