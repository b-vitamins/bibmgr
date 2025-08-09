"""Tests for event-aware repository implementations.

This module tests the event-aware repository classes that publish
events when entries, collections, and metadata change.
"""

import pytest

from bibmgr.core.models import Collection, Entry, EntryType


class TestEventAwareEntryRepository:
    """Test the event-aware entry repository."""

    def test_save_new_entry_publishes_created_event(self, mock_backend):
        """Saving new entry publishes ENTRY_CREATED event."""
        from bibmgr.storage.eventrepository import EventAwareEntryRepository
        from bibmgr.storage.events import EventBus, EventType

        event_bus = EventBus()
        received_events = []
        event_bus.subscribe(
            EventType.ENTRY_CREATED, lambda e: received_events.append(e)
        )

        repo = EventAwareEntryRepository(mock_backend, event_bus)

        entry = Entry(
            key="new_entry",
            type=EntryType.ARTICLE,
            title="New Article",
            author="Test Author",
            journal="Test Journal",
            year=2024,
        )
        repo.save(entry)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.type == EventType.ENTRY_CREATED
        assert event.data["entry_key"] == "new_entry"
        assert event.data["entry"] == entry

    def test_save_existing_entry_publishes_updated_event(self, mock_backend):
        """Saving existing entry publishes ENTRY_UPDATED event."""
        from bibmgr.storage.eventrepository import EventAwareEntryRepository
        from bibmgr.storage.events import EventBus, EventType

        event_bus = EventBus()
        received_events = []
        event_bus.subscribe(
            EventType.ENTRY_UPDATED, lambda e: received_events.append(e)
        )

        entry = Entry(key="existing", type=EntryType.MISC, title="Original")
        mock_backend.write("existing", entry.to_dict())

        repo = EventAwareEntryRepository(mock_backend, event_bus)

        import msgspec

        updated = msgspec.structs.replace(entry, title="Updated Title")
        repo.save(updated)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.type == EventType.ENTRY_UPDATED
        assert event.data["entry_key"] == "existing"
        assert event.data["entry"].title == "Updated Title"

    def test_delete_publishes_deleted_event(self, mock_backend):
        """Deleting entry publishes ENTRY_DELETED event."""
        from bibmgr.storage.eventrepository import EventAwareEntryRepository
        from bibmgr.storage.events import EventBus, EventType

        event_bus = EventBus()
        received_events = []
        event_bus.subscribe(
            EventType.ENTRY_DELETED, lambda e: received_events.append(e)
        )

        entry = Entry(key="to_delete", type=EntryType.MISC, title="Delete Me")
        mock_backend.write("to_delete", entry.to_dict())

        repo = EventAwareEntryRepository(mock_backend, event_bus)

        result = repo.delete("to_delete")

        assert result is True
        assert len(received_events) == 1
        event = received_events[0]
        assert event.type == EventType.ENTRY_DELETED
        assert event.data["entry_key"] == "to_delete"
        assert event.data["entry"].title == "Delete Me"

    def test_delete_nonexistent_no_event(self, mock_backend):
        """Deleting non-existent entry doesn't publish event."""
        from bibmgr.storage.eventrepository import EventAwareEntryRepository
        from bibmgr.storage.events import EventBus, EventType

        event_bus = EventBus()
        received_events = []
        event_bus.subscribe(
            EventType.ENTRY_DELETED, lambda e: received_events.append(e)
        )

        repo = EventAwareEntryRepository(mock_backend, event_bus)

        result = repo.delete("nonexistent")

        assert result is False
        assert len(received_events) == 0

    def test_repository_inherits_functionality(self, mock_backend):
        """Event-aware repository maintains base functionality."""
        from bibmgr.storage.eventrepository import EventAwareEntryRepository
        from bibmgr.storage.events import EventBus

        event_bus = EventBus()
        repo = EventAwareEntryRepository(mock_backend, event_bus)

        assert hasattr(repo, "find")
        assert hasattr(repo, "find_all")
        assert hasattr(repo, "find_by")
        assert hasattr(repo, "count")
        assert hasattr(repo, "exists")

        entry = Entry(key="test", type=EntryType.MISC, title="Test")
        repo.save(entry)

        assert repo.exists("test")
        assert repo.count() == 1

        found = repo.find("test")
        assert found is not None
        assert found.title == "Test"


@pytest.mark.skip(reason="Collections module will be reimplemented")
class TestEventAwareCollectionRepository:
    """Test the event-aware collection repository."""

    def test_save_new_collection_publishes_created_event(self, mock_backend):
        """Saving new collection publishes COLLECTION_CREATED event."""
        from bibmgr.storage.eventrepository import EventAwareCollectionRepository
        from bibmgr.storage.events import EventBus, EventType

        event_bus = EventBus()
        received_events = []
        event_bus.subscribe(
            EventType.COLLECTION_CREATED, lambda e: received_events.append(e)
        )

        repo = EventAwareCollectionRepository(mock_backend, event_bus)

        collection = Collection(
            name="Test Collection",
            description="A test collection",
            entry_keys=("entry1", "entry2"),
        )
        repo.save(collection)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.type == EventType.COLLECTION_CREATED
        assert event.data["collection_id"] == str(collection.id)
        assert event.data["collection"] == collection

    def test_save_existing_collection_publishes_updated_event(self, mock_backend):
        """Saving existing collection publishes COLLECTION_UPDATED event."""
        from bibmgr.storage.eventrepository import EventAwareCollectionRepository
        from bibmgr.storage.events import EventBus, EventType

        event_bus = EventBus()
        received_events = []
        event_bus.subscribe(
            EventType.COLLECTION_UPDATED, lambda e: received_events.append(e)
        )

        collection = Collection(name="Original Name")
        data = {
            "id": str(collection.id),
            "name": collection.name,
            "description": collection.description,
            "parent_id": str(collection.parent_id) if collection.parent_id else None,
            "entry_keys": collection.entry_keys,
            "query": collection.query,
            "color": collection.color,
            "icon": collection.icon,
            "created": collection.created.isoformat(),
            "modified": collection.modified.isoformat(),
        }
        mock_backend.write(f"collection:{collection.id}", data)

        repo = EventAwareCollectionRepository(mock_backend, event_bus)

        # Update collection - need to create a new instance since Collection is frozen
        import msgspec.structs

        updated_collection = msgspec.structs.replace(collection, name="Updated Name")
        repo.save(updated_collection)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.type == EventType.COLLECTION_UPDATED
        assert event.data["collection_id"] == str(collection.id)
        assert event.data["collection"].name == "Updated Name"

    def test_delete_collection_publishes_deleted_event(self, mock_backend):
        """Deleting collection publishes COLLECTION_DELETED event."""
        from bibmgr.storage.eventrepository import EventAwareCollectionRepository
        from bibmgr.storage.events import EventBus, EventType

        event_bus = EventBus()
        received_events = []
        event_bus.subscribe(
            EventType.COLLECTION_DELETED, lambda e: received_events.append(e)
        )

        collection = Collection(name="To Delete")
        data = {
            "id": str(collection.id),
            "name": collection.name,
            "description": collection.description,
            "parent_id": str(collection.parent_id) if collection.parent_id else None,
            "entry_keys": collection.entry_keys,
            "query": collection.query,
            "color": collection.color,
            "icon": collection.icon,
            "created": collection.created.isoformat(),
            "modified": collection.modified.isoformat(),
        }
        mock_backend.write(f"collection:{collection.id}", data)

        repo = EventAwareCollectionRepository(mock_backend, event_bus)

        result = repo.delete(str(collection.id))

        assert result is True
        assert len(received_events) == 1
        event = received_events[0]
        assert event.type == EventType.COLLECTION_DELETED
        assert event.data["collection_id"] == str(collection.id)
        assert event.data["collection"].name == "To Delete"


class TestEventAwareRepositoryManager:
    """Test the event-aware repository manager."""

    def test_manager_creates_event_aware_repos(self, mock_backend):
        """Manager creates event-aware repositories."""
        from bibmgr.storage.eventrepository import EventAwareRepositoryManager
        from bibmgr.storage.events import EventBus

        event_bus = EventBus()
        manager = EventAwareRepositoryManager(mock_backend, event_bus)

        assert hasattr(manager.entries, "_publish_event")
        # Skip collection assertions for now
        # assert hasattr(manager.collections, "_publish_event")
        assert manager.entries.event_bus == event_bus
        # assert manager.collections.event_bus == event_bus

    def test_import_entries_publishes_batch_event(self, mock_backend, sample_entries):
        """Batch import publishes ENTRIES_IMPORTED event."""
        from bibmgr.storage.eventrepository import EventAwareRepositoryManager
        from bibmgr.storage.events import EventBus, EventType

        event_bus = EventBus()
        received_events = []
        event_bus.subscribe(
            EventType.ENTRIES_IMPORTED, lambda e: received_events.append(e)
        )

        manager = EventAwareRepositoryManager(mock_backend, event_bus)

        results = manager.import_entries(sample_entries)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.type == EventType.ENTRIES_IMPORTED
        assert event.data["count"] == len(sample_entries)
        assert len(event.data["entry_keys"]) == len(sample_entries)

        assert all(results.values())

    def test_import_with_failures_publishes_partial_event(self, mock_backend):
        """Import with failures only includes successful entries in event."""
        from bibmgr.storage.eventrepository import EventAwareRepositoryManager
        from bibmgr.storage.events import EventBus, EventType

        event_bus = EventBus()
        received_events = []
        event_bus.subscribe(
            EventType.ENTRIES_IMPORTED, lambda e: received_events.append(e)
        )

        manager = EventAwareRepositoryManager(mock_backend, event_bus)

        entries = [
            Entry(key="valid1", type=EntryType.MISC, title="Valid 1"),
            Entry(key="", type=EntryType.MISC, title="Invalid Key"),  # Invalid
            Entry(key="valid2", type=EntryType.MISC, title="Valid 2"),
        ]

        results = manager.import_entries(entries)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.data["count"] == 2  # Only valid entries
        assert set(event.data["entry_keys"]) == {"valid1", "valid2"}

        assert results["valid1"] is True
        assert results[""] is False
        assert results["valid2"] is True

    def test_clear_all_publishes_event(self, mock_backend):
        """Clearing all data publishes STORAGE_CLEARED event."""
        from bibmgr.storage.eventrepository import EventAwareRepositoryManager
        from bibmgr.storage.events import EventBus, EventType

        event_bus = EventBus()
        received_events = []
        event_bus.subscribe(
            EventType.STORAGE_CLEARED, lambda e: received_events.append(e)
        )

        mock_backend.write("test1", {"key": "test1"})
        mock_backend.write("test2", {"key": "test2"})

        manager = EventAwareRepositoryManager(mock_backend, event_bus)

        manager.clear_all()

        assert len(received_events) == 1
        assert received_events[0].type == EventType.STORAGE_CLEARED

        assert len(mock_backend.keys()) == 0

    def test_rebuild_index_publishes_event(self, mock_backend):
        """Rebuilding index publishes INDEX_REBUILT event."""
        from bibmgr.storage.eventrepository import EventAwareRepositoryManager
        from bibmgr.storage.events import EventBus, EventType

        event_bus = EventBus()
        received_events = []
        event_bus.subscribe(
            EventType.INDEX_REBUILT, lambda e: received_events.append(e)
        )

        manager = EventAwareRepositoryManager(mock_backend, event_bus)

        manager.rebuild_index()

        assert len(received_events) == 1
        assert received_events[0].type == EventType.INDEX_REBUILT


class TestEventIntegrationScenarios:
    """Test event system integration scenarios."""

    def test_entry_lifecycle_events(self, temp_dir):
        """Test complete entry lifecycle with all events."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.eventrepository import EventAwareRepositoryManager
        from bibmgr.storage.events import EventBus, EventType
        from bibmgr.storage.metadata import MetadataStore

        backend = FileSystemBackend(temp_dir / "storage")
        event_bus = EventBus()
        manager = EventAwareRepositoryManager(backend, event_bus)
        metadata_store = MetadataStore(temp_dir / "metadata")

        all_events = []
        for event_type in EventType:
            event_bus.subscribe(event_type, lambda e: all_events.append(e))

        # 1. Create entry
        entry = Entry(
            key="lifecycle_test",
            type=EntryType.ARTICLE,
            title="Test Article",
            author="Test Author",
            journal="Test Journal",
            year=2024,
        )
        manager.entries.save(entry)

        # 2. Add metadata
        # (Would publish METADATA_UPDATED if metadata store was event-aware)
        metadata = metadata_store.get_metadata("lifecycle_test")
        metadata.add_tags("test", "lifecycle")
        metadata.rating = 5
        metadata_store.save_metadata(metadata)

        # 3. Update entry
        import msgspec

        updated = msgspec.structs.replace(entry, title="Updated Article")
        manager.entries.save(updated)

        # 4. Delete entry
        manager.entries.delete("lifecycle_test")

        event_types = [e.type for e in all_events]
        assert EventType.ENTRY_CREATED in event_types
        assert EventType.ENTRY_UPDATED in event_types
        assert EventType.ENTRY_DELETED in event_types

        created_idx = next(
            i for i, e in enumerate(all_events) if e.type == EventType.ENTRY_CREATED
        )
        updated_idx = next(
            i for i, e in enumerate(all_events) if e.type == EventType.ENTRY_UPDATED
        )
        deleted_idx = next(
            i for i, e in enumerate(all_events) if e.type == EventType.ENTRY_DELETED
        )

        assert created_idx < updated_idx < deleted_idx

    def test_batch_operations_event_flow(self, temp_dir):
        """Test event flow for batch operations."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.eventrepository import EventAwareRepositoryManager
        from bibmgr.storage.events import EventBus, EventType

        backend = FileSystemBackend(temp_dir / "storage")
        event_bus = EventBus()
        manager = EventAwareRepositoryManager(backend, event_bus)

        events_by_type = {event_type: [] for event_type in EventType}

        for event_type in EventType:
            event_bus.subscribe(
                event_type, lambda e, t=event_type: events_by_type[t].append(e)
            )

        entries = [
            Entry(key=f"batch_{i}", type=EntryType.MISC, title=f"Entry {i}")
            for i in range(5)
        ]
        manager.import_entries(entries)

        assert len(events_by_type[EventType.ENTRIES_IMPORTED]) == 1
        assert events_by_type[EventType.ENTRIES_IMPORTED][0].data["count"] == 5

        manager.clear_all()

        assert len(events_by_type[EventType.STORAGE_CLEARED]) == 1

        manager.rebuild_index()

        assert len(events_by_type[EventType.INDEX_REBUILT]) == 1

    def test_event_driven_cache_invalidation(self, temp_dir):
        """Test using events for cache invalidation."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.eventrepository import EventAwareRepositoryManager
        from bibmgr.storage.events import EventBus, EventType

        backend = FileSystemBackend(temp_dir / "storage")
        event_bus = EventBus()
        manager = EventAwareRepositoryManager(backend, event_bus)

        cache = {}

        def invalidate_cache(event):
            if hasattr(event, "entry_key"):
                cache.pop(event.entry_key, None)

        event_bus.subscribe(EventType.ENTRY_UPDATED, invalidate_cache)
        event_bus.subscribe(EventType.ENTRY_DELETED, invalidate_cache)

        entry = Entry(key="cached", type=EntryType.MISC, title="Original")
        manager.entries.save(entry)
        cache["cached"] = entry

        import msgspec

        updated = msgspec.structs.replace(entry, title="Updated")
        manager.entries.save(updated)

        assert "cached" not in cache

        cache["cached"] = updated

        manager.entries.delete("cached")

        assert "cached" not in cache

    def test_event_driven_ui_updates(self, temp_dir):
        """Test using events for UI update notifications."""
        from bibmgr.storage.backends import FileSystemBackend
        from bibmgr.storage.eventrepository import EventAwareRepositoryManager
        from bibmgr.storage.events import EventBus, EventType

        backend = FileSystemBackend(temp_dir / "storage")
        event_bus = EventBus()
        manager = EventAwareRepositoryManager(backend, event_bus)

        ui_updates = []

        def queue_ui_update(event):
            update = {
                "type": event.type.name,
                "timestamp": event.timestamp,
            }

            if hasattr(event, "entry_key"):
                update["entry_key"] = event.entry_key
            if "collection_id" in event.data:
                update["collection_id"] = event.data["collection_id"]

            ui_updates.append(update)

        for event_type in [
            EventType.ENTRY_CREATED,
            EventType.ENTRY_UPDATED,
            EventType.ENTRY_DELETED,
            EventType.COLLECTION_CREATED,
            EventType.COLLECTION_UPDATED,
            EventType.COLLECTION_DELETED,
        ]:
            event_bus.subscribe(event_type, queue_ui_update)

        entry = Entry(key="ui_test", type=EntryType.MISC, title="Test")
        manager.entries.save(entry)

        # collection = Collection(name="UI Test Collection", entry_keys=["ui_test"])
        # manager.collections.save(collection)

        import msgspec

        updated = msgspec.structs.replace(entry, title="Updated")
        manager.entries.save(updated)

        manager.entries.delete("ui_test")
        # manager.collections.delete(str(collection.id))

        assert len(ui_updates) == 3
        update_types = [u["type"] for u in ui_updates]
        assert "ENTRY_CREATED" in update_types
        # assert "COLLECTION_CREATED" in update_types
        assert "ENTRY_UPDATED" in update_types
        assert "ENTRY_DELETED" in update_types
        # assert "COLLECTION_DELETED" in update_types

    def test_event_consistency_across_backends(self, temp_dir):
        """Events are consistent across different backends."""
        from bibmgr.storage.backends import FileSystemBackend, MemoryBackend
        from bibmgr.storage.eventrepository import EventAwareRepositoryManager
        from bibmgr.storage.events import EventBus, EventType

        backends = [
            FileSystemBackend(temp_dir / "fs_storage"),
            MemoryBackend(),
        ]

        for backend in backends:
            backend.initialize()

            event_bus = EventBus()
            manager = EventAwareRepositoryManager(backend, event_bus)

            created_events = []
            event_bus.subscribe(
                EventType.ENTRY_CREATED, lambda e: created_events.append(e)
            )

            entry = Entry(key="test", type=EntryType.MISC, title="Test")
            manager.entries.save(entry)

            assert len(created_events) == 1
            assert created_events[0].type == EventType.ENTRY_CREATED
            assert created_events[0].data["entry_key"] == "test"


class TestEventErrorHandling:
    """Test error handling in event system."""

    def test_event_publishing_continues_on_handler_error(self, mock_backend):
        """Event publishing continues even if handler raises exception."""
        from bibmgr.storage.eventrepository import EventAwareRepositoryManager
        from bibmgr.storage.events import EventBus, EventType

        event_bus = EventBus()
        manager = EventAwareRepositoryManager(mock_backend, event_bus)

        def bad_handler(event):
            raise Exception("Handler error")

        good_events = []

        def good_handler(event):
            good_events.append(event)

        event_bus.subscribe(EventType.ENTRY_CREATED, bad_handler)
        event_bus.subscribe(EventType.ENTRY_CREATED, good_handler)

        entry = Entry(key="test", type=EntryType.MISC, title="Test")

        manager.entries.save(entry)

        assert len(good_events) == 1
        assert good_events[0].type == EventType.ENTRY_CREATED

    def test_repository_operations_succeed_without_event_bus(self, mock_backend):
        """Repository operations work even without event bus."""
        from bibmgr.storage.eventrepository import EventAwareRepositoryManager

        manager = EventAwareRepositoryManager(mock_backend, None)

        entry = Entry(key="test", type=EntryType.MISC, title="Test")
        manager.entries.save(entry)

        assert manager.entries.exists("test")

        assert manager.entries.delete("test") is True
        assert not manager.entries.exists("test")
