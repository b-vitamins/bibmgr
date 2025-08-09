"""Tests for the event system."""

import threading
import time
from datetime import datetime
from unittest.mock import Mock

from bibmgr.core.models import Entry, EntryType


class TestEvent:
    """Test the Event data class."""

    def test_create_event(self):
        """Events can be created with type and data."""
        from bibmgr.storage.events import Event, EventType

        now = datetime.now()
        event = Event(
            type=EventType.ENTRY_CREATED,
            timestamp=now,
            data={"entry_key": "test123", "entry": Mock()},
        )

        assert event.type == EventType.ENTRY_CREATED
        assert event.timestamp == now
        assert event.entry_key == "test123"
        assert event.entry is not None

    def test_event_property_accessors(self):
        """Event provides convenient property access."""
        from bibmgr.storage.events import Event, EventType

        entry = Entry(key="test", type=EntryType.MISC, title="Test")

        event = Event(
            type=EventType.ENTRY_UPDATED,
            timestamp=datetime.now(),
            data={"entry_key": "test", "entry": entry},
        )

        assert event.entry_key == "test"
        assert event.entry == entry

    def test_event_without_entry_data(self):
        """Events without entry data return None."""
        from bibmgr.storage.events import Event, EventType

        event = Event(
            type=EventType.STORAGE_CLEARED,
            timestamp=datetime.now(),
            data={},
        )

        assert event.entry_key is None
        assert event.entry is None


class TestEventBus:
    """Test the event bus publish/subscribe system."""

    def test_subscribe_and_publish(self):
        """Basic pub/sub functionality works."""
        from bibmgr.storage.events import Event, EventBus, EventType

        bus = EventBus()
        received_events = []

        def handler(event):
            received_events.append(event)

        bus.subscribe(EventType.ENTRY_CREATED, handler)
        event = Event(
            type=EventType.ENTRY_CREATED,
            timestamp=datetime.now(),
            data={"entry_key": "test"},
        )
        bus.publish(event)

        assert len(received_events) == 1
        assert received_events[0] == event

    def test_multiple_subscribers(self):
        """Multiple handlers can subscribe to same event type."""
        from bibmgr.storage.events import Event, EventBus, EventType

        bus = EventBus()
        handler1_events = []
        handler2_events = []

        bus.subscribe(EventType.ENTRY_UPDATED, lambda e: handler1_events.append(e))
        bus.subscribe(EventType.ENTRY_UPDATED, lambda e: handler2_events.append(e))

        event = Event(
            type=EventType.ENTRY_UPDATED,
            timestamp=datetime.now(),
            data={},
        )
        bus.publish(event)

        assert len(handler1_events) == 1
        assert len(handler2_events) == 1
        assert handler1_events[0] == handler2_events[0] == event

    def test_unsubscribe(self):
        """Handlers can be unsubscribed."""
        from bibmgr.storage.events import Event, EventBus, EventType

        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(EventType.ENTRY_DELETED, handler)

        event1 = Event(type=EventType.ENTRY_DELETED, timestamp=datetime.now(), data={})
        bus.publish(event1)
        assert len(received) == 1

        bus.unsubscribe(EventType.ENTRY_DELETED, handler)
        event2 = Event(type=EventType.ENTRY_DELETED, timestamp=datetime.now(), data={})
        bus.publish(event2)
        assert len(received) == 1

    def test_event_type_filtering(self):
        """Handlers only receive events of subscribed type."""
        from bibmgr.storage.events import Event, EventBus, EventType

        bus = EventBus()
        created_events = []
        deleted_events = []

        bus.subscribe(EventType.ENTRY_CREATED, lambda e: created_events.append(e))
        bus.subscribe(EventType.ENTRY_DELETED, lambda e: deleted_events.append(e))

        create_event = Event(
            type=EventType.ENTRY_CREATED, timestamp=datetime.now(), data={}
        )
        delete_event = Event(
            type=EventType.ENTRY_DELETED, timestamp=datetime.now(), data={}
        )
        update_event = Event(
            type=EventType.ENTRY_UPDATED, timestamp=datetime.now(), data={}
        )

        bus.publish(create_event)
        bus.publish(delete_event)
        bus.publish(update_event)

        assert len(created_events) == 1
        assert len(deleted_events) == 1
        assert created_events[0].type == EventType.ENTRY_CREATED
        assert deleted_events[0].type == EventType.ENTRY_DELETED

    def test_handler_exception_isolation(self):
        """Handler exceptions don't affect other handlers or publisher."""
        from bibmgr.storage.events import Event, EventBus, EventType

        bus = EventBus()
        good_handler_called = []

        def bad_handler(event):
            raise Exception("Handler error")

        def good_handler(event):
            good_handler_called.append(event)

        bus.subscribe(EventType.ENTRY_CREATED, bad_handler)
        bus.subscribe(EventType.ENTRY_CREATED, good_handler)

        event = Event(type=EventType.ENTRY_CREATED, timestamp=datetime.now(), data={})

        bus.publish(event)

        assert len(good_handler_called) == 1

    def test_event_history(self):
        """Event bus maintains event history."""
        from bibmgr.storage.events import Event, EventBus, EventType

        bus = EventBus()

        for i in range(5):
            event = Event(
                type=EventType.ENTRY_CREATED,
                timestamp=datetime.now(),
                data={"index": i},
            )
            bus.publish(event)

        history = bus.get_history()
        assert len(history) == 5

        history = bus.get_history(limit=3)
        assert len(history) == 3
        assert history[0].data["index"] == 2
        assert history[2].data["index"] == 4

    def test_event_history_by_type(self):
        """Event history can be filtered by type."""
        from bibmgr.storage.events import Event, EventBus, EventType

        bus = EventBus()

        bus.publish(
            Event(type=EventType.ENTRY_CREATED, timestamp=datetime.now(), data={})
        )
        bus.publish(
            Event(type=EventType.ENTRY_UPDATED, timestamp=datetime.now(), data={})
        )
        bus.publish(
            Event(type=EventType.ENTRY_CREATED, timestamp=datetime.now(), data={})
        )
        bus.publish(
            Event(type=EventType.ENTRY_DELETED, timestamp=datetime.now(), data={})
        )

        created_history = bus.get_history(event_type=EventType.ENTRY_CREATED)
        assert len(created_history) == 2
        assert all(e.type == EventType.ENTRY_CREATED for e in created_history)

    def test_history_limit(self):
        """Event history has configurable size limit."""
        from bibmgr.storage.events import Event, EventBus, EventType

        bus = EventBus()
        bus._history_limit = 10
        for i in range(15):
            event = Event(
                type=EventType.ENTRY_CREATED,
                timestamp=datetime.now(),
                data={"index": i},
            )
            bus.publish(event)

        history = bus.get_history()
        assert len(history) == 10
        assert history[0].data["index"] == 5
        assert history[9].data["index"] == 14

    def test_clear_history(self):
        """Event history can be cleared."""
        from bibmgr.storage.events import Event, EventBus, EventType

        bus = EventBus()

        for _ in range(5):
            bus.publish(
                Event(type=EventType.ENTRY_CREATED, timestamp=datetime.now(), data={})
            )

        assert len(bus.get_history()) == 5

        bus.clear_history()
        assert len(bus.get_history()) == 0

        bus.publish(
            Event(type=EventType.ENTRY_UPDATED, timestamp=datetime.now(), data={})
        )
        assert len(bus.get_history()) == 1


class TestEventPublisher:
    """Test the EventPublisher mixin."""

    def test_event_publisher_mixin(self):
        """EventPublisher mixin provides publishing capability."""
        from bibmgr.storage.events import EventBus, EventPublisher, EventType

        bus = EventBus()
        received_events = []

        bus.subscribe(EventType.ENTRY_CREATED, lambda e: received_events.append(e))

        publisher = EventPublisher(bus)

        publisher._publish_event(
            EventType.ENTRY_CREATED,
            entry_key="test",
            custom_data="value",
        )

        assert len(received_events) == 1
        assert received_events[0].type == EventType.ENTRY_CREATED
        assert received_events[0].data["entry_key"] == "test"
        assert received_events[0].data["custom_data"] == "value"


class TestEventAwareRepository:
    """Test repository with event publishing."""

    def test_save_publishes_create_event(self, mock_backend):
        """Saving new entry publishes ENTRY_CREATED event."""
        from bibmgr.storage.events import EventBus, EventPublisher, EventType

        bus = EventBus()
        received = []
        bus.subscribe(EventType.ENTRY_CREATED, lambda e: received.append(e))

        class TestRepository(EventPublisher):
            def __init__(self, backend, event_bus):
                super().__init__(event_bus)
                self.backend = backend

            def exists(self, key):
                return key in self.backend.data

            def save(self, entry):
                is_new = not self.exists(entry.key)
                self.backend.write(entry.key, entry.to_dict())

                if is_new:
                    self._publish_event(
                        EventType.ENTRY_CREATED, entry_key=entry.key, entry=entry
                    )
                else:
                    self._publish_event(
                        EventType.ENTRY_UPDATED, entry_key=entry.key, entry=entry
                    )

        repo = TestRepository(mock_backend, bus)

        entry = Entry(key="new", type=EntryType.MISC, title="New Entry")
        repo.save(entry)

        assert len(received) == 1
        assert received[0].type == EventType.ENTRY_CREATED
        assert received[0].data["entry_key"] == "new"
        assert received[0].data["entry"] == entry

    def test_save_publishes_update_event(self, mock_backend):
        """Saving existing entry publishes ENTRY_UPDATED event."""
        from bibmgr.storage.events import EventBus, EventPublisher, EventType

        bus = EventBus()
        received = []
        bus.subscribe(EventType.ENTRY_UPDATED, lambda e: received.append(e))

        entry = Entry(key="existing", type=EntryType.MISC, title="Original")
        mock_backend.data["existing"] = entry.to_dict()

        class TestRepository(EventPublisher):
            def __init__(self, backend, event_bus):
                super().__init__(event_bus)
                self.backend = backend

            def exists(self, key):
                return key in self.backend.data

            def save(self, entry):
                is_new = not self.exists(entry.key)
                self.backend.write(entry.key, entry.to_dict())

                if is_new:
                    self._publish_event(
                        EventType.ENTRY_CREATED, entry_key=entry.key, entry=entry
                    )
                else:
                    self._publish_event(
                        EventType.ENTRY_UPDATED, entry_key=entry.key, entry=entry
                    )

        repo = TestRepository(mock_backend, bus)

        import msgspec

        updated = msgspec.structs.replace(entry, title="Updated")
        repo.save(updated)

        assert len(received) == 1
        assert received[0].type == EventType.ENTRY_UPDATED
        assert received[0].data["entry"] == updated


class TestEventIntegration:
    """Test event system integration scenarios."""

    def test_import_events(self):
        """Batch import publishes appropriate events."""
        from bibmgr.storage.events import EventBus, EventType
        from bibmgr.storage.repository import RepositoryManager

        bus = EventBus()
        created_count = 0

        def count_created(event):
            nonlocal created_count
            created_count += 1

        bus.subscribe(EventType.ENTRY_CREATED, count_created)

        class EventAwareManager(RepositoryManager):
            def __init__(self, backend, event_bus):
                super().__init__(backend)
                self.event_bus = event_bus

            def import_entries(self, entries, skip_validation=False):
                results = super().import_entries(entries, skip_validation)

                self.event_bus.publish(
                    Event(
                        type=EventType.ENTRIES_IMPORTED,
                        timestamp=datetime.now(),
                        data={
                            "count": sum(1 for success in results.values() if success),
                            "entries": entries,
                        },
                    )
                )

                return results

        entries = [
            Entry(key=f"entry{i}", type=EntryType.MISC, title=f"Entry {i}")
            for i in range(5)
        ]

        from contextlib import contextmanager

        from bibmgr.storage.events import Event

        class MockBackend:
            def __init__(self):
                self.data = {}

            def write(self, key, value):
                self.data[key] = value

            def read(self, key):
                return self.data.get(key)

            def exists(self, key):
                return key in self.data

            def keys(self):
                return list(self.data.keys())

            @contextmanager
            def begin_transaction(self):
                yield  # Simple no-op transaction

        mock_backend = MockBackend()

        manager = EventAwareManager(mock_backend, bus)
        manager.import_entries(entries)

        history = bus.get_history(event_type=EventType.ENTRIES_IMPORTED)
        assert len(history) == 1
        assert history[0].data["count"] == 5

    def test_cascade_events(self):
        """Related events cascade appropriately."""
        from bibmgr.storage.events import Event, EventBus, EventType

        bus = EventBus()
        events_received = []

        for event_type in EventType:
            bus.subscribe(event_type, lambda e: events_received.append(e))

        entry_key = "to_delete"

        bus.publish(
            Event(
                type=EventType.ENTRY_DELETED,
                timestamp=datetime.now(),
                data={"entry_key": entry_key},
            )
        )

        bus.publish(
            Event(
                type=EventType.METADATA_UPDATED,
                timestamp=datetime.now(),
                data={"entry_key": entry_key, "action": "deleted"},
            )
        )

        bus.publish(
            Event(
                type=EventType.TAG_REMOVED,
                timestamp=datetime.now(),
                data={"entry_key": entry_key, "tags": ["tag1", "tag2"]},
            )
        )

        bus.publish(
            Event(
                type=EventType.NOTE_DELETED,
                timestamp=datetime.now(),
                data={"entry_key": entry_key, "note_ids": ["note1", "note2"]},
            )
        )

        assert len(events_received) == 4
        event_types = [e.type for e in events_received]
        assert EventType.ENTRY_DELETED in event_types
        assert EventType.METADATA_UPDATED in event_types
        assert EventType.TAG_REMOVED in event_types
        assert EventType.NOTE_DELETED in event_types

    def test_concurrent_event_publishing(self):
        """Event system handles concurrent publishing."""
        from bibmgr.storage.events import Event, EventBus, EventType

        bus = EventBus()
        all_events = []

        def collect_events(event):
            all_events.append(event)

        bus.subscribe(EventType.ENTRY_CREATED, collect_events)

        def publisher(thread_id):
            for i in range(10):
                event = Event(
                    type=EventType.ENTRY_CREATED,
                    timestamp=datetime.now(),
                    data={"thread": thread_id, "index": i},
                )
                bus.publish(event)
                time.sleep(0.001)  # Small delay

        threads = []
        for i in range(3):
            t = threading.Thread(target=publisher, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(all_events) == 30  # 3 threads × 10 events

        thread_ids = {e.data["thread"] for e in all_events}
        assert thread_ids == {0, 1, 2}
