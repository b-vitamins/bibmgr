"""Collection management with hierarchical organization and smart queries.

This module implements:
- Collection CRUD operations
- Smart collection auto-updating
- Collection statistics and analytics
- Hierarchical collection navigation
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import msgspec

from bibmgr.collections.models import (
    Collection,
    CollectionPredicate,
    CollectionQuery,
    CollectionStats,
    SmartCollection,
)


class CollectionRepository(Protocol):
    """Protocol for collection storage."""

    def save(self, collection: Collection | SmartCollection) -> None:
        """Save a collection."""
        ...

    def load(self, collection_id: str) -> Collection | SmartCollection | None:
        """Load a collection by ID."""
        ...

    def load_all(self) -> list[Collection | SmartCollection]:
        """Load all collections."""
        ...

    def delete(self, collection_id: str) -> bool:
        """Delete a collection."""
        ...

    def exists(self, collection_id: str) -> bool:
        """Check if collection exists."""
        ...


class FileCollectionRepository:
    """File-based collection repository."""

    def __init__(self, base_path: Path):
        """Initialize with base path.

        Args:
            base_path: Base directory for collections
        """
        self.base_path = Path(base_path)
        self.collections_dir = self.base_path / "collections"
        self.collections_dir.mkdir(parents=True, exist_ok=True)

        self.encoder = msgspec.json.Encoder()
        self.decoder = msgspec.json.Decoder()

    def save(self, collection: Collection | SmartCollection) -> None:
        """Save a collection to disk."""
        path = self.collections_dir / f"{collection.id}.json"

        # Convert to dict for JSON serialization
        data = collection.to_dict()

        # Write atomically
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, indent=2))
        temp_path.replace(path)

    def load(self, collection_id: str) -> Collection | SmartCollection | None:
        """Load a collection from disk."""
        path = self.collections_dir / f"{collection_id}.json"
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())

            # Reconstruct the collection
            if "query" in data and data["query"]:
                # It's a smart collection
                query_data = data.pop("query")
                predicates = [
                    CollectionPredicate(**p) for p in query_data.get("predicates", [])
                ]
                query = CollectionQuery(
                    predicates=predicates,
                    combinator=query_data.get("combinator", "AND"),
                )

                return SmartCollection(
                    **{
                        **data,
                        "query": query,
                        "entry_keys": set(data.get("entry_keys", [])),
                        "created_at": datetime.fromisoformat(data["created_at"]),
                        "updated_at": datetime.fromisoformat(data["updated_at"]),
                        "last_refresh": datetime.fromisoformat(
                            data.get("last_refresh", data["updated_at"])
                        ),
                    }
                )
            else:
                # Regular collection
                return Collection(
                    **{
                        **data,
                        "entry_keys": set(data.get("entry_keys", [])),
                        "created_at": datetime.fromisoformat(data["created_at"]),
                        "updated_at": datetime.fromisoformat(data["updated_at"]),
                    }
                )
        except Exception:
            return None

    def load_all(self) -> list[Collection | SmartCollection]:
        """Load all collections from disk."""
        collections = []
        for path in self.collections_dir.glob("*.json"):
            collection_id = path.stem
            collection = self.load(collection_id)
            if collection:
                collections.append(collection)
        return collections

    def delete(self, collection_id: str) -> bool:
        """Delete a collection from disk."""
        path = self.collections_dir / f"{collection_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def exists(self, collection_id: str) -> bool:
        """Check if collection exists on disk."""
        path = self.collections_dir / f"{collection_id}.json"
        return path.exists()


class CollectionManager:
    """Manages collections and their operations."""

    def __init__(
        self,
        repository: CollectionRepository,
        entry_repository: Any = None,
    ):
        """Initialize collection manager.

        Args:
            repository: Collection storage repository
            entry_repository: Optional entry repository for smart collections
        """
        self.repository = repository
        self.entry_repository = entry_repository
        self._cache: dict[str, Collection | SmartCollection] = {}

    def create_collection(
        self,
        name: str,
        description: str | None = None,
        parent_id: str | None = None,
    ) -> Collection:
        """Create a new collection.

        Args:
            name: Collection name
            description: Optional description
            parent_id: Optional parent collection ID

        Returns:
            Created collection

        Raises:
            ValueError: If parent doesn't exist
        """
        if parent_id and not self.repository.exists(parent_id):
            raise ValueError(f"Parent collection {parent_id} does not exist")

        collection = Collection(
            name=name,
            description=description,
            parent_id=parent_id,
        )

        self.repository.save(collection)
        self._cache[collection.id] = collection

        return collection

    def create_smart_collection(
        self,
        name: str,
        query: CollectionQuery,
        description: str | None = None,
        parent_id: str | None = None,
        auto_update: bool = True,
    ) -> SmartCollection:
        """Create a new smart collection.

        Args:
            name: Collection name
            query: Query for auto-updating
            description: Optional description
            parent_id: Optional parent collection ID
            auto_update: Whether to auto-update

        Returns:
            Created smart collection
        """
        if parent_id and not self.repository.exists(parent_id):
            raise ValueError(f"Parent collection {parent_id} does not exist")

        collection = SmartCollection(
            name=name,
            description=description,
            parent_id=parent_id,
            query=query,
            auto_update=auto_update,
        )

        # Initial population if we have entry repository
        if self.entry_repository and auto_update:
            entries = self.entry_repository.read_all()
            collection = collection.refresh(entries)

        self.repository.save(collection)
        self._cache[collection.id] = collection

        return collection

    def get_collection(self, collection_id: str) -> Collection | SmartCollection | None:
        """Get a collection by ID.

        Args:
            collection_id: Collection ID

        Returns:
            Collection or None if not found
        """
        if collection_id in self._cache:
            return self._cache[collection_id]

        collection = self.repository.load(collection_id)
        if collection:
            self._cache[collection_id] = collection

        return collection

    def get_all_collections(self) -> list[Collection | SmartCollection]:
        """Get all collections.

        Returns:
            List of all collections
        """
        return self.repository.load_all()

    def update_collection(
        self,
        collection_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> Collection | SmartCollection | None:
        """Update a collection.

        Args:
            collection_id: Collection ID
            name: New name
            description: New description

        Returns:
            Updated collection or None if not found
        """
        collection = self.get_collection(collection_id)
        if not collection:
            return None

        if name:
            if isinstance(collection, Collection):
                collection = collection.rename(name)
            else:
                # SmartCollection doesn't have rename method
                collection = msgspec.structs.replace(
                    collection, name=name, updated_at=datetime.now()
                )

        if description is not None:
            collection = msgspec.structs.replace(
                collection, description=description, updated_at=datetime.now()
            )

        self.repository.save(collection)
        self._cache[collection_id] = collection

        return collection

    def delete_collection(
        self,
        collection_id: str,
        cascade: bool = False,
    ) -> bool:
        """Delete a collection.

        Args:
            collection_id: Collection ID
            cascade: Whether to delete child collections

        Returns:
            True if deleted
        """
        if cascade:
            # Delete all child collections
            for collection in self.get_all_collections():
                if collection.parent_id == collection_id:
                    self.delete_collection(collection.id, cascade=True)

        # Delete the collection
        if collection_id in self._cache:
            del self._cache[collection_id]

        return self.repository.delete(collection_id)

    def add_to_collection(
        self,
        collection_id: str,
        entry_key: str,
    ) -> Collection | SmartCollection | None:
        """Add an entry to a collection.

        Args:
            collection_id: Collection ID
            entry_key: Entry key to add

        Returns:
            Updated collection or None if not found
        """
        collection = self.get_collection(collection_id)
        if not collection:
            return None

        if isinstance(collection, Collection):
            collection = collection.add_entry(entry_key)
        else:
            # SmartCollection uses list for entry_keys
            new_keys = list(collection.entry_keys)
            if entry_key not in new_keys:
                new_keys.append(entry_key)
            collection = msgspec.structs.replace(
                collection, entry_keys=new_keys, updated_at=datetime.now()
            )
        self.repository.save(collection)
        self._cache[collection_id] = collection

        return collection

    def remove_from_collection(
        self,
        collection_id: str,
        entry_key: str,
    ) -> Collection | SmartCollection | None:
        """Remove an entry from a collection.

        Args:
            collection_id: Collection ID
            entry_key: Entry key to remove

        Returns:
            Updated collection or None if not found
        """
        collection = self.get_collection(collection_id)
        if not collection:
            return None

        if isinstance(collection, Collection):
            collection = collection.remove_entry(entry_key)
        else:
            # SmartCollection uses list for entry_keys
            new_keys = [k for k in collection.entry_keys if k != entry_key]
            collection = msgspec.structs.replace(
                collection, entry_keys=new_keys, updated_at=datetime.now()
            )
        self.repository.save(collection)
        self._cache[collection_id] = collection

        return collection

    def move_collection(
        self,
        collection_id: str,
        new_parent_id: str | None,
    ) -> Collection | SmartCollection | None:
        """Move a collection to a new parent.

        Args:
            collection_id: Collection ID
            new_parent_id: New parent ID or None for root

        Returns:
            Updated collection or None if not found

        Raises:
            ValueError: If would create a cycle
        """
        collection = self.get_collection(collection_id)
        if not collection:
            return None

        # Check for cycles
        if new_parent_id:
            if new_parent_id == collection_id:
                raise ValueError("Cannot make collection its own parent")

            # Check if new parent is a descendant
            if self._is_descendant(new_parent_id, collection_id):
                raise ValueError("Cannot create cycle in collection hierarchy")

        if isinstance(collection, Collection):
            collection = collection.move_to(new_parent_id)
        else:
            # SmartCollection doesn't have move_to method
            collection = msgspec.structs.replace(
                collection, parent_id=new_parent_id, updated_at=datetime.now()
            )
        self.repository.save(collection)
        self._cache[collection_id] = collection

        return collection

    def _is_descendant(self, potential_child: str, potential_parent: str) -> bool:
        """Check if one collection is a descendant of another.

        Args:
            potential_child: Potential child ID
            potential_parent: Potential parent ID

        Returns:
            True if potential_child is a descendant of potential_parent
        """
        current = self.get_collection(potential_child)
        while current and current.parent_id:
            if current.parent_id == potential_parent:
                return True
            current = self.get_collection(current.parent_id)
        return False

    def get_collection_stats(self, collection_id: str) -> CollectionStats | None:
        """Get statistics for a collection.

        Args:
            collection_id: Collection ID

        Returns:
            Collection statistics or None
        """
        collection = self.get_collection(collection_id)
        if not collection or not self.entry_repository:
            return None

        # Get entries in collection
        entries = []
        for key in collection.entry_keys:
            entry = self.entry_repository.read(key)
            if entry:
                entries.append(entry)

        # Calculate statistics
        tag_dist = {}
        type_dist = {}
        year_dist = {}
        author_dist = {}

        for entry in entries:
            # Type distribution
            if hasattr(entry, "type"):
                entry_type = str(entry.type)
                type_dist[entry_type] = type_dist.get(entry_type, 0) + 1

            # Year distribution
            if hasattr(entry, "year") and entry.year:
                year_dist[entry.year] = year_dist.get(entry.year, 0) + 1

            # Author distribution
            if hasattr(entry, "authors_list"):
                for author in entry.authors_list:
                    author_dist[author] = author_dist.get(author, 0) + 1

            # Tag distribution (if entry has tags)
            if hasattr(entry, "tags"):
                for tag in entry.tags:
                    tag_dist[tag] = tag_dist.get(tag, 0) + 1

        return CollectionStats(
            entry_count=len(entries),
            tag_distribution=tag_dist,
            type_distribution=type_dist,
            year_distribution=year_dist,
            author_distribution=author_dist,
        )

    def refresh_smart_collections(self) -> int:
        """Refresh all smart collections.

        Returns:
            Number of collections refreshed
        """
        if not self.entry_repository:
            return 0

        entries = self.entry_repository.read_all()
        count = 0

        for collection in self.get_all_collections():
            if isinstance(collection, SmartCollection) and collection.auto_update:
                updated = collection.refresh(entries)
                if updated.entry_keys != collection.entry_keys:
                    self.repository.save(updated)
                    self._cache[collection.id] = updated
                    count += 1

        return count

    def export_collection(
        self,
        collection_id: str,
        format: str = "bibtex",
    ) -> str | None:
        """Export a collection.

        Args:
            collection_id: Collection ID
            format: Export format

        Returns:
            Exported content or None
        """
        collection = self.get_collection(collection_id)
        if not collection or not self.entry_repository:
            return None

        entries = []
        for key in collection.entry_keys:
            entry = self.entry_repository.read(key)
            if entry:
                entries.append(entry)

        if format == "bibtex":
            # Simple BibTeX export
            lines = []
            for entry in entries:
                lines.append(f"@{entry.type}{{{entry.key},")

                # Add fields
                fields = []
                for field in [
                    "author",
                    "title",
                    "journal",
                    "year",
                    "volume",
                    "pages",
                    "doi",
                ]:
                    if hasattr(entry, field) and getattr(entry, field):
                        value = getattr(entry, field)
                        fields.append(f"  {field} = {{{value}}}")

                lines.extend(fields)
                lines.append("}\n")

            return "\n".join(lines)

        elif format == "keys":
            return "\n".join(collection.entry_keys)

        else:
            return None
