"""Repository pattern implementation for bibliography data access.

Provides type-safe interfaces for entry and collection management that abstract
storage implementation details. Supports validation, transactions, and complex
querying through a fluent builder interface.
"""

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Protocol

from bibmgr.core.models import Collection, Entry
from bibmgr.core.validators import ValidatorRegistry

from .query import Condition, Operator, Query


class StorageBackend(Protocol):
    """Protocol for storage backend implementations."""

    def read(self, key: str) -> dict[str, Any] | None:
        """Read raw entry data."""
        ...

    def write(self, key: str, data: dict[str, Any]) -> None:
        """Write raw entry data."""
        ...

    def delete(self, key: str) -> bool:
        """Delete entry data."""
        ...

    def exists(self, key: str) -> bool:
        """Check if entry exists."""
        ...

    def keys(self) -> list[str]:
        """Get all entry keys."""
        ...

    def clear(self) -> None:
        """Remove all entries."""
        ...

    def begin_transaction(self) -> AbstractContextManager[None]:
        """Begin a transaction (optional)."""
        ...


class QueryBuilder:
    """Fluent interface for building queries."""

    def __init__(self):
        self._filters = []
        self._order_by = []
        self._limit = None
        self._offset = None

    def where(self, field: str, operator: str, value: Any) -> "QueryBuilder":
        """Add a where clause."""
        self._filters.append((field, operator, value))
        return self

    def where_in(self, field: str, values: list[Any]) -> "QueryBuilder":
        """Add a where-in clause."""
        self._filters.append((field, "in", values))
        return self

    def order_by(self, field: str, ascending: bool = True) -> "QueryBuilder":
        """Add ordering."""
        self._order_by.append((field, ascending))
        return self

    def limit(self, count: int) -> "QueryBuilder":
        """Limit results."""
        self._limit = count
        return self

    def offset(self, count: int) -> "QueryBuilder":
        """Offset results."""
        self._offset = count
        return self

    def build(self) -> dict[str, Any]:
        """Build the query specification."""
        return {
            "filters": self._filters,
            "order_by": self._order_by,
            "limit": self._limit,
            "offset": self._offset,
        }


class Repository(ABC):
    """Abstract base repository."""

    def __init__(self, backend: StorageBackend):
        self.backend = backend
        self.validator_registry = ValidatorRegistry()

    @abstractmethod
    def find(self, key: str) -> Entry | None:
        """Find single entry by key."""
        pass

    @abstractmethod
    def find_all(self) -> list[Entry]:
        """Find all entries."""
        pass

    @abstractmethod
    def find_by(self, query: QueryBuilder) -> list[Entry]:
        """Find entries matching query."""
        pass

    @abstractmethod
    def save(self, entry: Entry) -> None:
        """Save entry (insert or update)."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete entry by key."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Count total entries."""
        pass


class EntryRepository(Repository):
    """Repository for bibliography entries."""

    def find(self, key: str) -> Entry | None:
        """Find entry by key, returning None if not found or corrupted."""
        try:
            data = self.backend.read(key)
            if data is None:
                return None
            return self._convert_to_entry(data)
        except Exception:
            return None

    def find_all(self) -> list[Entry]:
        """Get all entries."""
        entries = []
        for key in self.backend.keys():
            entry = self.find(key)
            if entry:
                entries.append(entry)
        return entries

    def find_by(self, query: QueryBuilder) -> list[Entry]:
        """Find entries matching query with filtering, ordering, and pagination."""
        spec = query.build()
        all_entries = self.find_all()

        filtered = [
            entry
            for entry in all_entries
            if self._matches_filters(entry, spec["filters"])
        ]

        if spec["order_by"]:
            filtered = self._apply_ordering(filtered, spec["order_by"])

        if spec["offset"]:
            filtered = filtered[spec["offset"] :]
        if spec["limit"]:
            filtered = filtered[: spec["limit"]]

        return filtered

    def save(self, entry: Entry, skip_validation: bool = False) -> None:
        """Save entry with optional validation."""
        if not skip_validation:
            errors = self.validator_registry.validate(entry)
            if any(e.severity == "error" for e in errors):
                raise ValueError(f"Entry validation failed: {errors}")

        data = entry.to_dict()
        self.backend.write(entry.key, data)

    def delete(self, key: str) -> bool:
        """Delete entry."""
        return self.backend.delete(key)

    def count(self) -> int:
        """Count entries."""
        return len(self.backend.keys())

    def exists(self, key: str) -> bool:
        """Check if entry exists."""
        return self.backend.exists(key)

    def find_by_type(self, entry_type: str) -> list[Entry]:
        """Find all entries of a specific type."""
        return self.find_by(QueryBuilder().where("type", "=", entry_type))

    def find_by_year(self, year: int) -> list[Entry]:
        """Find all entries from a specific year."""
        return self.find_by(QueryBuilder().where("year", "=", year))

    def find_by_author(self, author: str) -> list[Entry]:
        """Find all entries by author (substring match)."""
        entries = []
        for entry in self.find_all():
            if entry.author and author.lower() in entry.author.lower():
                entries.append(entry)
        return entries

    def find_recent(self, limit: int = 10) -> list[Entry]:
        """Find most recently added entries."""
        return self.find_by(
            QueryBuilder().order_by("added", ascending=False).limit(limit)
        )

    def search(self, query: Query) -> list[Entry]:
        """Search entries using a Query object."""
        # For now, implement a simple search using find_all
        # This could be optimized with proper indexing later
        all_entries = self.find_all()
        return [entry for entry in all_entries if self._matches_query(entry, query)]

    def _matches_query(self, entry: Entry, query: Query | Condition) -> bool:
        """Check if an entry matches a query."""
        if isinstance(query, Condition):
            return self._matches_condition(entry, query)

        # Handle compound queries (AND/OR/NOT)
        if hasattr(query, "operator") and hasattr(query, "conditions"):
            if query.operator == Operator.AND:
                return all(
                    self._matches_query(entry, cond) for cond in query.conditions
                )
            elif query.operator == Operator.OR:
                return any(
                    self._matches_query(entry, cond) for cond in query.conditions
                )
            elif query.operator == Operator.NOT:
                return not self._matches_query(entry, query.conditions[0])

        return False

    def _matches_condition(self, entry: Entry, condition: Condition) -> bool:
        """Check if an entry matches a single condition."""
        entry_dict = entry.to_dict()
        field_value = entry_dict.get(condition.field)

        if field_value is None:
            return False

        # Convert to string for string operations
        if condition.operator in [
            Operator.CONTAINS,
            Operator.STARTS_WITH,
            Operator.ENDS_WITH,
        ]:
            field_value = str(field_value).lower()
            condition_value = str(condition.value).lower()

            if condition.operator == Operator.CONTAINS:
                return condition_value in field_value
            elif condition.operator == Operator.STARTS_WITH:
                return field_value.startswith(condition_value)
            elif condition.operator == Operator.ENDS_WITH:
                return field_value.endswith(condition_value)

        # Handle other operators
        if condition.operator == Operator.EQ:
            return field_value == condition.value
        elif condition.operator == Operator.NE:
            return field_value != condition.value
        elif condition.operator == Operator.GT:
            return field_value > condition.value
        elif condition.operator == Operator.GTE:
            return field_value >= condition.value
        elif condition.operator == Operator.LT:
            return field_value < condition.value
        elif condition.operator == Operator.LTE:
            return field_value <= condition.value
        elif condition.operator == Operator.IN:
            return field_value in condition.value
        elif condition.operator == Operator.NOT_IN:
            return field_value not in condition.value

        return False

    def _matches_filters(self, entry: Entry, filters: list[tuple]) -> bool:
        """Check if entry matches all filters."""
        for field, op, value in filters:
            entry_value = getattr(entry, field, None)

            if op == "=":
                if not self._values_equal(entry_value, value):
                    return False
            elif op == "!=":
                if self._values_equal(entry_value, value):
                    return False
            elif op == ">" and not (entry_value and entry_value > value):
                return False
            elif op == "<" and not (entry_value and entry_value < value):
                return False
            elif op == ">=" and not (entry_value and entry_value >= value):
                return False
            elif op == "<=" and not (entry_value and entry_value <= value):
                return False
            elif op == "in" and entry_value not in value:
                return False
            elif op == "contains" and not (entry_value and value in str(entry_value)):
                return False

        return True

    def _values_equal(self, entry_value: Any, filter_value: Any) -> bool:
        """Compare values handling both enum and primitive types."""

        def get_value(val):
            return val.value if hasattr(val, "value") else val

        return get_value(entry_value) == get_value(filter_value)

    def _apply_ordering(
        self, entries: list[Entry], order_by: list[tuple]
    ) -> list[Entry]:
        """Apply ordering to entries."""
        for field, ascending in reversed(order_by):
            entries.sort(key=lambda e: getattr(e, field, ""), reverse=not ascending)
        return entries

    def _convert_to_entry(self, data: dict[str, Any]) -> Entry:
        """Convert raw data to Entry with automatic migration support."""
        import msgspec

        migrated_data = data.copy()

        if "type" in migrated_data and isinstance(migrated_data["type"], str):
            migrated_data["type"] = migrated_data["type"].lower()

        if "year" in migrated_data and isinstance(migrated_data["year"], str):
            try:
                migrated_data["year"] = int(migrated_data["year"])
            except ValueError:
                del migrated_data["year"]

        if "keywords" in migrated_data and isinstance(migrated_data["keywords"], str):
            keywords = migrated_data["keywords"].split(",")
            migrated_data["keywords"] = tuple(
                kw.strip() for kw in keywords if kw.strip()
            )

        try:
            return msgspec.convert(migrated_data, Entry)
        except Exception as e:
            raise ValueError(f"Failed to convert entry data: {e}") from e


class CollectionRepository:
    """Repository for collections."""

    def __init__(self, backend: StorageBackend):
        self.backend = backend

    def find(self, collection_id: str) -> Collection | None:
        """Find collection by ID."""
        data = self.backend.read(f"collection:{collection_id}")
        if not data:
            return None

        # Parse datetime fields
        from datetime import datetime

        if "created" in data and isinstance(data["created"], str):
            data["created"] = datetime.fromisoformat(data["created"])
        if "modified" in data and isinstance(data["modified"], str):
            data["modified"] = datetime.fromisoformat(data["modified"])

        return Collection(**data)

    def find_all(self) -> list[Collection]:
        """Get all collections."""
        collections = []
        for key in self.backend.keys():
            if key.startswith("collection:"):
                collection = self.find(key[11:])
                if collection:
                    collections.append(collection)
        return collections

    def save(self, collection: Collection) -> None:
        """Save collection."""
        from datetime import datetime

        # Handle datetime fields - they might be datetime objects or strings
        created = collection.created
        if isinstance(created, datetime):
            created_str = created.isoformat()
        else:
            created_str = created

        modified = collection.modified
        if isinstance(modified, datetime):
            modified_str = modified.isoformat()
        else:
            modified_str = modified

        data = {
            "id": str(collection.id),
            "name": collection.name,
            "description": collection.description,
            "parent_id": str(collection.parent_id) if collection.parent_id else None,
            "entry_keys": collection.entry_keys,
            "query": collection.query,
            "color": collection.color,
            "icon": collection.icon,
            "created": created_str,
            "modified": modified_str,
        }
        self.backend.write(f"collection:{collection.id}", data)

    def delete(self, collection_id: str) -> bool:
        """Delete collection."""
        return self.backend.delete(f"collection:{collection_id}")

    def find_by_parent(self, parent_id: str | None) -> list[Collection]:
        """Find collections by parent."""
        collections = []
        for collection in self.find_all():
            if parent_id is None:
                if collection.parent_id is None:
                    collections.append(collection)
            else:
                if collection.parent_id and str(collection.parent_id) == parent_id:
                    collections.append(collection)
        return collections

    def find_smart_collections(self) -> list[Collection]:
        """Find all smart (query-based) collections."""
        return [c for c in self.find_all() if c.is_smart]

    def find_by_name(self, name: str) -> list[Collection]:
        """Find collections by name (exact match)."""
        return [c for c in self.find_all() if c.name == name]


class RepositoryManager:
    """Manages repositories and coordinates operations."""

    def __init__(self, backend: StorageBackend, metadata_store=None):
        self.backend = backend
        self.entries = EntryRepository(backend)
        self.collections = CollectionRepository(backend)
        self.metadata_store = metadata_store
        self._transaction_depth = 0

        if self.metadata_store:
            self._setup_metadata_coordination()

    @contextmanager
    def transaction(self):
        """Transaction context manager."""
        self._transaction_depth += 1
        try:
            if hasattr(self.backend, "begin_transaction"):
                with self.backend.begin_transaction():
                    yield self
            else:
                yield self
        finally:
            self._transaction_depth -= 1

    def import_entries(
        self, entries: list[Entry], skip_validation: bool = False
    ) -> dict[str, bool]:
        """Import multiple entries."""
        results = {}

        with self.transaction():
            for entry in entries:
                try:
                    if not skip_validation:
                        errors = self.entries.validator_registry.validate(entry)
                        if any(e.severity == "error" for e in errors):
                            results[entry.key] = False
                            continue

                    self.entries.save(entry, skip_validation=skip_validation)
                    results[entry.key] = True
                except Exception:
                    results[entry.key] = False

        return results

    def export_entries(self, keys: list[str] | None = None) -> list[Entry]:
        """Export entries."""
        if keys:
            entries = []
            for key in keys:
                entry = self.entries.find(key)
                if entry:
                    entries.append(entry)
            return entries
        else:
            return self.entries.find_all()

    def get_statistics(self) -> dict[str, Any]:
        """Get repository statistics."""
        entries = self.entries.find_all()

        stats = {
            "total_entries": len(entries),
            "entries_by_type": {},
            "entries_by_year": {},
            "collections": {
                "total": len(self.collections.find_all()),
                "smart": len(self.collections.find_smart_collections()),
            },
        }

        for entry in entries:
            type_name = entry.type.value
            stats["entries_by_type"][type_name] = (
                stats["entries_by_type"].get(type_name, 0) + 1
            )

        for entry in entries:
            if entry.year:
                stats["entries_by_year"][entry.year] = (
                    stats["entries_by_year"].get(entry.year, 0) + 1
                )

        return stats

    def _setup_metadata_coordination(self):
        """Setup coordination between entries and metadata."""
        original_delete = self.entries.delete

        def coordinated_delete(key: str) -> bool:
            """Delete entry and its associated metadata."""
            result = original_delete(key)
            if result and self.metadata_store:
                self.metadata_store.delete_metadata(key)
            return result

        self.entries.delete = coordinated_delete

        if self.metadata_store and hasattr(self.metadata_store, "get_metadata"):
            original_get_metadata = self.metadata_store.get_metadata

            def coordinated_get_metadata(entry_key: str, **kwargs):
                """Get metadata, returning fresh metadata if entry doesn't exist."""
                if not self.entries.exists(entry_key):
                    from bibmgr.storage.metadata import EntryMetadata

                    return EntryMetadata(entry_key=entry_key)
                return original_get_metadata(entry_key, **kwargs)

            self.metadata_store.get_metadata = coordinated_get_metadata
