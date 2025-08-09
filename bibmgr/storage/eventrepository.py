"""Event-aware repository implementation that publishes events on changes."""

from bibmgr.core.models import Collection, Entry
from bibmgr.storage.events import EventBus, EventPublisher, EventType
from bibmgr.storage.repository import (
    CollectionRepository,
    EntryRepository,
    RepositoryManager,
    StorageBackend,
)


class EventAwareEntryRepository(EntryRepository, EventPublisher):
    """Entry repository that publishes events on changes."""

    def __init__(self, backend: StorageBackend, event_bus: EventBus):
        EntryRepository.__init__(self, backend)
        EventPublisher.__init__(self, event_bus)

    def save(self, entry: Entry, skip_validation: bool = False) -> None:
        """Save entry and publish event."""
        is_new = not self.exists(entry.key)

        # Save the entry
        super().save(entry, skip_validation)

        # Publish appropriate event
        if is_new:
            self._publish_event(
                EventType.ENTRY_CREATED, entry_key=entry.key, entry=entry
            )
        else:
            self._publish_event(
                EventType.ENTRY_UPDATED, entry_key=entry.key, entry=entry
            )

    def delete(self, key: str) -> bool:
        """Delete entry and publish event."""
        # Get entry before deletion for event
        entry = self.find(key)

        result = super().delete(key)

        if result:
            self._publish_event(EventType.ENTRY_DELETED, entry_key=key, entry=entry)

        return result


class EventAwareCollectionRepository(CollectionRepository, EventPublisher):
    """Collection repository that publishes events on changes."""

    def __init__(self, backend: StorageBackend, event_bus: EventBus):
        CollectionRepository.__init__(self, backend)
        EventPublisher.__init__(self, event_bus)

    def save(self, collection: Collection) -> None:
        """Save collection and publish event."""
        is_new = self.find(str(collection.id)) is None

        # Save the collection
        super().save(collection)

        # Publish appropriate event
        if is_new:
            self._publish_event(
                EventType.COLLECTION_CREATED,
                collection_id=str(collection.id),
                collection=collection,
            )
        else:
            self._publish_event(
                EventType.COLLECTION_UPDATED,
                collection_id=str(collection.id),
                collection=collection,
            )

    def delete(self, collection_id: str) -> bool:
        """Delete collection and publish event."""
        # Get collection before deletion for event
        collection = self.find(collection_id)

        result = super().delete(collection_id)

        if result:
            self._publish_event(
                EventType.COLLECTION_DELETED,
                collection_id=collection_id,
                collection=collection,
            )

        return result


class EventAwareRepositoryManager(RepositoryManager, EventPublisher):
    """Repository manager with event support."""

    def __init__(self, backend: StorageBackend, event_bus: EventBus | None = None):
        self.backend = backend
        self.event_bus = event_bus or EventBus()

        RepositoryManager.__init__(self, backend)
        EventPublisher.__init__(self, self.event_bus)

        # Create event-aware repositories
        self.entries = EventAwareEntryRepository(backend, self.event_bus)
        self.collections = EventAwareCollectionRepository(backend, self.event_bus)

    def import_entries(
        self, entries: list[Entry], skip_validation: bool = False
    ) -> dict[str, bool]:
        """Import multiple entries and publish event."""
        results = super().import_entries(entries, skip_validation)

        # Publish batch import event
        successful_keys = [key for key, success in results.items() if success]
        if successful_keys:
            self._publish_event(
                EventType.ENTRIES_IMPORTED,
                entry_keys=successful_keys,
                count=len(successful_keys),
            )

        return results

    def clear_all(self) -> None:
        """Clear all data and publish event."""
        self.backend.clear()

        # Publish storage cleared event
        self._publish_event(EventType.STORAGE_CLEARED)

    def rebuild_index(self) -> None:
        """Rebuild any indices and publish event."""
        # This would trigger index rebuilding in search/indexing backends
        self._publish_event(EventType.INDEX_REBUILT)
