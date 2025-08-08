"""Collection models for organizing bibliography entries.

Implements hierarchical collections with smart query-based updates.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum, auto
from typing import Any
from uuid import uuid4

import msgspec


class PredicateOperator(Enum):
    """Operators for collection predicates."""

    EQUALS = auto()
    NOT_EQUALS = auto()
    CONTAINS = auto()
    NOT_CONTAINS = auto()
    STARTS_WITH = auto()
    ENDS_WITH = auto()
    GREATER_THAN = auto()
    LESS_THAN = auto()
    IN = auto()
    NOT_IN = auto()
    MATCHES = auto()  # Regex
    EXISTS = auto()
    NOT_EXISTS = auto()


class CollectionPredicate(msgspec.Struct, frozen=True):
    """A single predicate for smart collection queries."""

    field: str
    operator: PredicateOperator
    value: Any
    case_sensitive: bool = False

    def matches(self, entry: Any) -> bool:
        """Check if an entry matches this predicate.

        Args:
            entry: Entry to check

        Returns:
            True if entry matches predicate
        """
        # Get field value from entry
        if hasattr(entry, self.field):
            field_value = getattr(entry, self.field)
        else:
            field_value = None

        # Handle existence checks
        if self.operator == PredicateOperator.EXISTS:
            return field_value is not None
        elif self.operator == PredicateOperator.NOT_EXISTS:
            return field_value is None

        # Handle None values
        if field_value is None:
            return False

        # Convert to string for comparison if needed
        if not self.case_sensitive and isinstance(field_value, str):
            field_value = field_value.lower()
            compare_value = (
                self.value.lower() if isinstance(self.value, str) else self.value
            )
        else:
            compare_value = self.value

        # Apply operator
        match self.operator:
            case PredicateOperator.EQUALS:
                return field_value == compare_value
            case PredicateOperator.NOT_EQUALS:
                return field_value != compare_value
            case PredicateOperator.CONTAINS:
                return str(compare_value) in str(field_value)
            case PredicateOperator.NOT_CONTAINS:
                return str(compare_value) not in str(field_value)
            case PredicateOperator.STARTS_WITH:
                return str(field_value).startswith(str(compare_value))
            case PredicateOperator.ENDS_WITH:
                return str(field_value).endswith(str(compare_value))
            case PredicateOperator.GREATER_THAN:
                return field_value > compare_value
            case PredicateOperator.LESS_THAN:
                return field_value < compare_value
            case PredicateOperator.IN:
                return field_value in compare_value
            case PredicateOperator.NOT_IN:
                return field_value not in compare_value
            case PredicateOperator.MATCHES:
                import re

                pattern = re.compile(str(compare_value))
                return bool(pattern.match(str(field_value)))
            case _:
                return False


class CollectionQuery(msgspec.Struct, frozen=True):
    """Query for smart collections."""

    predicates: list[CollectionPredicate]
    combinator: str = "AND"  # AND or OR

    def matches(self, entry: Any) -> bool:
        """Check if an entry matches this query.

        Args:
            entry: Entry to check

        Returns:
            True if entry matches query
        """
        if not self.predicates:
            return True

        results = [p.matches(entry) for p in self.predicates]

        if self.combinator == "AND":
            return all(results)
        else:  # OR
            return any(results)


class CollectionStats(msgspec.Struct, frozen=True):
    """Statistics for a collection."""

    entry_count: int = 0
    tag_distribution: dict[str, int] = msgspec.field(default_factory=dict)
    type_distribution: dict[str, int] = msgspec.field(default_factory=dict)
    year_distribution: dict[int, int] = msgspec.field(default_factory=dict)
    author_distribution: dict[str, int] = msgspec.field(default_factory=dict)
    last_updated: datetime = msgspec.field(default_factory=datetime.now)

    def to_summary(self) -> str:
        """Generate human-readable summary.

        Returns:
            Summary string
        """
        lines = [
            f"Entries: {self.entry_count}",
            f"Last updated: {self.last_updated.strftime('%Y-%m-%d %H:%M')}",
        ]

        if self.type_distribution:
            lines.append("\nEntry Types:")
            for entry_type, count in sorted(self.type_distribution.items()):
                lines.append(f"  {entry_type}: {count}")

        if self.year_distribution:
            years = sorted(self.year_distribution.keys())
            if years:
                lines.append(f"\nYear Range: {min(years)}-{max(years)}")

        if self.tag_distribution:
            top_tags = sorted(
                self.tag_distribution.items(), key=lambda x: x[1], reverse=True
            )[:5]
            if top_tags:
                lines.append("\nTop Tags:")
                for tag, count in top_tags:
                    lines.append(f"  {tag}: {count}")

        return "\n".join(lines)


class Collection(msgspec.Struct, frozen=True, kw_only=True):
    """A collection of bibliography entries."""

    id: str = msgspec.field(default_factory=lambda: str(uuid4()))
    name: str
    description: str | None = None
    parent_id: str | None = None
    entry_keys: set[str] = msgspec.field(default_factory=set)
    created_at: datetime = msgspec.field(default_factory=datetime.now)
    updated_at: datetime = msgspec.field(default_factory=datetime.now)
    metadata: dict[str, Any] = msgspec.field(default_factory=dict)

    @property
    def path(self) -> str:
        """Get hierarchical path for this collection.

        Returns:
            Path string like "parent/child/grandchild"
        """
        # In a real implementation, this would traverse parent_id chain
        # For now, just return the name
        return self.name

    @property
    def size(self) -> int:
        """Get number of entries in collection.

        Returns:
            Entry count
        """
        return len(self.entry_keys)

    def add_entry(self, key: str) -> Collection:
        """Add an entry to the collection.

        Args:
            key: Entry key to add

        Returns:
            Updated collection
        """
        new_keys = self.entry_keys | {key}
        return msgspec.structs.replace(
            self, entry_keys=new_keys, updated_at=datetime.now()
        )

    def remove_entry(self, key: str) -> Collection:
        """Remove an entry from the collection.

        Args:
            key: Entry key to remove

        Returns:
            Updated collection
        """
        new_keys = self.entry_keys - {key}
        return msgspec.structs.replace(
            self, entry_keys=new_keys, updated_at=datetime.now()
        )

    def rename(self, new_name: str) -> Collection:
        """Rename the collection.

        Args:
            new_name: New collection name

        Returns:
            Updated collection
        """
        return msgspec.structs.replace(self, name=new_name, updated_at=datetime.now())

    def move_to(self, parent_id: str | None) -> Collection:
        """Move collection to a new parent.

        Args:
            parent_id: New parent ID or None for root

        Returns:
            Updated collection
        """
        return msgspec.structs.replace(
            self, parent_id=parent_id, updated_at=datetime.now()
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parent_id": self.parent_id,
            "entry_keys": list(self.entry_keys),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class SmartCollection(msgspec.Struct, frozen=True, kw_only=True):
    """A smart collection with query-based membership."""

    # Inherit Collection fields
    id: str = msgspec.field(default_factory=lambda: str(uuid4()))
    name: str
    description: str | None = None
    entry_keys: list[str] = msgspec.field(default_factory=list)
    parent_id: str | None = None
    color: str | None = None
    icon: str | None = None
    created_at: datetime = msgspec.field(default_factory=datetime.now)
    updated_at: datetime = msgspec.field(default_factory=datetime.now)
    metadata: dict[str, Any] = msgspec.field(default_factory=dict)

    # SmartCollection specific fields
    query: CollectionQuery | None = None
    auto_update: bool = True
    last_refresh: datetime = msgspec.field(default_factory=datetime.now)

    def matches(self, entry: Any) -> bool:
        """Check if an entry matches this collection's query.

        Args:
            entry: Entry to check

        Returns:
            True if entry matches or no query defined
        """
        if not self.query:
            return False
        return self.query.matches(entry)

    def refresh(self, entries: list[Any]) -> SmartCollection:
        """Refresh collection membership based on query.

        Args:
            entries: All entries to check

        Returns:
            Updated collection
        """
        if not self.query or not self.auto_update:
            return self

        new_keys = {entry.key for entry in entries if self.matches(entry)}

        return msgspec.structs.replace(
            self,
            entry_keys=new_keys,
            last_refresh=datetime.now(),
            updated_at=datetime.now(),
        )

    def update_query(self, query: CollectionQuery) -> SmartCollection:
        """Update the collection's query.

        Args:
            query: New query

        Returns:
            Updated collection
        """
        return msgspec.structs.replace(self, query=query, updated_at=datetime.now())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        # SmartCollection doesn't inherit from Collection, so we build the dict directly
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parent_id": self.parent_id,
            "entry_keys": list(self.entry_keys),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "query": msgspec.to_builtins(self.query) if self.query else None,
            "auto_update": self.auto_update,
            "last_refresh": self.last_refresh.isoformat(),
        }
