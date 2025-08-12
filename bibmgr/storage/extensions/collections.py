"""Collection support extension for storage backends."""

import json
from pathlib import Path
from uuid import UUID, uuid4

import msgspec


class CollectionInfo(msgspec.Struct):
    """Information about a collection."""

    id: UUID
    name: str
    description: str | None = None
    tags: list[str] = msgspec.field(default_factory=list)
    entry_count: int = 0


class CollectionData(msgspec.Struct):
    """Internal collection data structure."""

    id: UUID
    name: str
    description: str | None = None
    tags: list[str] = msgspec.field(default_factory=list)
    entries: list[str] = msgspec.field(default_factory=list)


class CollectionExtension:
    """Extension for managing collections in storage backends."""

    def __init__(self, backend):
        """Initialize collection extension.

        Args:
            backend: Storage backend instance
        """
        self.backend = backend

        # For filesystem backends, use file storage
        if hasattr(backend, "data_dir"):
            self._collections_dir = backend.data_dir / "collections"
            self._collections_dir.mkdir(exist_ok=True)
            self._index_file = self._collections_dir / "index.json"
            self._use_files = True
        else:
            # For memory backends, use in-memory storage
            self._collections_data = {}
            self._index = {}
            self._use_files = False

        if self._use_files:
            self._load_index()

    def _load_index(self) -> None:
        """Load collection index from disk."""
        if self._index_file.exists():
            data = self._index_file.read_text()
            self._index = json.loads(data)
        else:
            self._index = {}
            self._save_index()

    def _save_index(self) -> None:
        """Save collection index to disk."""
        if self._use_files:
            self._index_file.write_text(json.dumps(self._index, indent=2))

    def _get_collection_file(self, collection_id: UUID) -> Path:
        """Get path to collection data file."""
        return self._collections_dir / f"{collection_id}.json"

    def _load_collection_data(self, collection_id: UUID) -> CollectionData | None:
        """Load collection data from disk or memory."""
        if self._use_files:
            file_path = self._get_collection_file(collection_id)
            if not file_path.exists():
                return None

            data = json.loads(file_path.read_text())
            # Convert id string back to UUID
            data["id"] = UUID(data["id"])
            return msgspec.convert(data, CollectionData)
        else:
            # Memory backend
            return self._collections_data.get(collection_id)

    def _save_collection_data(self, collection: CollectionData) -> None:
        """Save collection data to disk or memory."""
        if self._use_files:
            file_path = self._get_collection_file(collection.id)
            # Convert to dict for JSON serialization
            data = msgspec.to_builtins(collection)
            # Convert UUID to string for JSON
            data["id"] = str(data["id"])
            file_path.write_text(json.dumps(data, indent=2))
        else:
            # Memory backend
            self._collections_data[collection.id] = collection

    def create_collection(
        self, name: str, description: str | None = None, tags: list[str] | None = None
    ) -> CollectionInfo:
        """Create a new collection.

        Args:
            name: Collection name
            description: Optional description
            tags: Optional list of tags

        Returns:
            Created collection info
        """
        collection_id = uuid4()
        collection = CollectionData(
            id=collection_id, name=name, description=description, tags=tags or []
        )

        # Save collection data
        self._save_collection_data(collection)

        # Update index
        self._index[str(collection_id)] = {"name": name, "tags": tags or []}
        self._save_index()

        return CollectionInfo(
            id=collection_id,
            name=name,
            description=description,
            tags=tags or [],
            entry_count=0,
        )

    def get_collection(self, collection_id: UUID) -> CollectionInfo | None:
        """Get collection information.

        Args:
            collection_id: Collection UUID

        Returns:
            Collection info or None if not found
        """
        collection_data = self._load_collection_data(collection_id)
        if not collection_data:
            return None

        return CollectionInfo(
            id=collection_data.id,
            name=collection_data.name,
            description=collection_data.description,
            tags=collection_data.tags,
            entry_count=len(collection_data.entries),
        )

    def add_to_collection(self, collection_id: UUID, entry_keys: list[str]) -> None:
        """Add entries to a collection.

        Args:
            collection_id: Collection UUID
            entry_keys: List of entry keys to add
        """
        collection_data = self._load_collection_data(collection_id)
        if not collection_data:
            raise ValueError(f"Collection {collection_id} not found")

        # Add unique entries
        existing = set(collection_data.entries)
        for key in entry_keys:
            if key not in existing:
                collection_data.entries.append(key)

        self._save_collection_data(collection_data)

    def remove_from_collection(
        self, collection_id: UUID, entry_keys: list[str]
    ) -> None:
        """Remove entries from a collection.

        Args:
            collection_id: Collection UUID
            entry_keys: List of entry keys to remove
        """
        collection_data = self._load_collection_data(collection_id)
        if not collection_data:
            return

        # Remove entries
        to_remove = set(entry_keys)
        collection_data.entries = [
            e for e in collection_data.entries if e not in to_remove
        ]

        self._save_collection_data(collection_data)

    def is_in_collection(self, collection_id: UUID, entry_key: str) -> bool:
        """Check if entry is in collection.

        Args:
            collection_id: Collection UUID
            entry_key: Entry key to check

        Returns:
            True if entry is in collection
        """
        collection_data = self._load_collection_data(collection_id)
        if not collection_data:
            return False

        return entry_key in collection_data.entries

    def get_entry_collections(self, entry_key: str) -> list[CollectionInfo]:
        """Get all collections containing an entry.

        Args:
            entry_key: Entry key

        Returns:
            List of collections containing the entry
        """
        collections = []

        for collection_id_str in self._index:
            collection_id = UUID(collection_id_str)
            if self.is_in_collection(collection_id, entry_key):
                collection_info = self.get_collection(collection_id)
                if collection_info:
                    collections.append(collection_info)

        return collections

    def delete_collection(self, collection_id: UUID) -> bool:
        """Delete a collection.

        Args:
            collection_id: Collection UUID

        Returns:
            True if deleted, False if not found
        """
        if self._use_files:
            file_path = self._get_collection_file(collection_id)
            if not file_path.exists():
                return False

            # Delete file
            file_path.unlink()
        else:
            # Memory backend
            if collection_id not in self._collections_data:
                return False
            del self._collections_data[collection_id]

        # Update index
        collection_id_str = str(collection_id)
        if collection_id_str in self._index:
            del self._index[collection_id_str]
            self._save_index()

        return True

    def update_collection_tags(
        self,
        collection_id: UUID,
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> None:
        """Update collection tags.

        Args:
            collection_id: Collection UUID
            add: Tags to add
            remove: Tags to remove
        """
        collection_data = self._load_collection_data(collection_id)
        if not collection_data:
            raise ValueError(f"Collection {collection_id} not found")

        # Update tags
        current_tags = set(collection_data.tags)

        if remove:
            current_tags -= set(remove)

        if add:
            current_tags |= set(add)

        collection_data.tags = sorted(list(current_tags))
        self._save_collection_data(collection_data)

        # Update index
        self._index[str(collection_id)]["tags"] = collection_data.tags
        self._save_index()

    def search_collections(
        self, query: str | None = None, tags: list[str] | None = None
    ) -> list[CollectionInfo]:
        """Search collections by name or tags.

        Args:
            query: Search query for name
            tags: Tags to filter by

        Returns:
            List of matching collections
        """
        results = []

        for collection_id_str, index_data in self._index.items():
            # Check tag match
            if tags:
                collection_tags = set(index_data.get("tags", []))
                if not any(tag in collection_tags for tag in tags):
                    continue

            # Check name match
            if query:
                name = index_data.get("name", "")
                if query.lower() not in name.lower():
                    continue

            # Get full collection info
            collection_id = UUID(collection_id_str)
            collection_info = self.get_collection(collection_id)
            if collection_info:
                results.append(collection_info)

        return results

    def update_collection(
        self,
        collection_id: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> CollectionInfo:
        """Update collection metadata.

        Args:
            collection_id: Collection UUID
            name: New name (optional)
            description: New description (optional)

        Returns:
            Updated collection info
        """
        collection_data = self._load_collection_data(collection_id)
        if not collection_data:
            raise ValueError(f"Collection {collection_id} not found")

        # Update fields
        if name is not None:
            collection_data.name = name
            self._index[str(collection_id)]["name"] = name

        if description is not None:
            collection_data.description = description

        self._save_collection_data(collection_data)
        self._save_index()

        return CollectionInfo(
            id=collection_data.id,
            name=collection_data.name,
            description=collection_data.description,
            tags=collection_data.tags,
            entry_count=len(collection_data.entries),
        )

    def list_collections(self) -> list[CollectionInfo]:
        """List all collections sorted by name.

        Returns:
            List of all collections
        """
        collections = []

        for collection_id_str in self._index:
            collection_id = UUID(collection_id_str)
            collection_info = self.get_collection(collection_id)
            if collection_info:
                collections.append(collection_info)

        # Sort by name
        collections.sort(key=lambda c: c.name)
        return collections

    def get_collection_entries(self, collection_id: UUID) -> list[str]:
        """Get all entry keys in a collection.

        Args:
            collection_id: Collection UUID

        Returns:
            List of entry keys
        """
        collection_data = self._load_collection_data(collection_id)
        if not collection_data:
            return []

        return collection_data.entries.copy()
