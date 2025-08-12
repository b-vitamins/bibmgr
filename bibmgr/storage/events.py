"""Event system for tracking changes to entries and metadata."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Any

from bibmgr.core.models import Entry


class EventType(Enum):
    """Types of events that can occur."""

    # Entry events
    ENTRY_CREATED = auto()
    ENTRY_UPDATED = auto()
    ENTRY_DELETED = auto()
    ENTRIES_IMPORTED = auto()
    ENTRIES_MERGED = auto()
    BULK_CREATED = auto()
    PROGRESS = auto()

    # Metadata events
    METADATA_UPDATED = auto()
    TAG_ADDED = auto()
    TAG_REMOVED = auto()
    NOTE_ADDED = auto()
    NOTE_UPDATED = auto()
    NOTE_DELETED = auto()

    # Collection events
    COLLECTION_CREATED = auto()
    COLLECTION_UPDATED = auto()
    COLLECTION_DELETED = auto()

    # System events
    STORAGE_CLEARED = auto()
    INDEX_REBUILT = auto()
    INDEX_PROGRESS = auto()

    # Workflow events
    WORKFLOW_COMPLETED = auto()
    PROGRESS_UPDATE = auto()


@dataclass
class Event:
    """An event that occurred in the system."""

    type: EventType
    timestamp: datetime
    data: dict[str, Any]

    @property
    def entry_key(self) -> str | None:
        """Get entry key if this is an entry-related event."""
        return self.data.get("entry_key")

    @property
    def entry(self) -> Entry | None:
        """Get entry if included in event data."""
        return self.data.get("entry")


class EventBus:
    """Simple event bus for publishing and subscribing to events."""

    def __init__(self):
        self._subscribers: dict[EventType, list[Callable[[Event], None]]] = {}
        self._history: list[Event] = []
        self._history_limit = 1000

    def subscribe(
        self, event_type: EventType, handler: Callable[[Event], None]
    ) -> None:
        """Subscribe to events of a specific type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(
        self, event_type: EventType, handler: Callable[[Event], None]
    ) -> None:
        """Unsubscribe from events."""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        # Add to history
        self._history.append(event)
        if len(self._history) > self._history_limit:
            self._history = self._history[-self._history_limit :]

        # Notify subscribers
        if event.type in self._subscribers:
            for handler in self._subscribers[event.type]:
                try:
                    handler(event)
                except Exception:
                    pass  # Don't let subscriber errors break publishing

    def get_history(
        self, event_type: EventType | None = None, limit: int = 100
    ) -> list[Event]:
        """Get event history."""
        history = self._history

        if event_type:
            history = [e for e in history if e.type == event_type]

        return history[-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()


class EventPublisher:
    """Mixin for classes that publish events."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    def _publish_event(self, event_type: EventType, **data) -> None:
        """Publish an event."""
        event = Event(type=event_type, timestamp=datetime.now(), data=data)
        self.event_bus.publish(event)
