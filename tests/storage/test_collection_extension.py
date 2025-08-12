"""Tests for collection support in storage."""

import pytest

from bibmgr.storage.backends.filesystem import FileSystemBackend
from bibmgr.storage.extensions.collections import CollectionExtension


class TestCollectionExtension:
    """Test collection extension for storage."""

    @pytest.fixture
    def storage_with_collections(self, tmp_path):
        """Create storage backend with collection extension."""
        backend = FileSystemBackend(tmp_path)
        extension = CollectionExtension(backend)
        return extension

    def test_create_collection(self, storage_with_collections):
        """Test creating a collection."""
        collection = storage_with_collections.create_collection(
            name="ML Papers",
            description="Machine learning research papers",
            tags=["ml", "ai", "research"],
        )

        assert collection.id
        assert collection.name == "ML Papers"
        assert collection.description == "Machine learning research papers"
        assert collection.tags == ["ml", "ai", "research"]
        assert collection.entry_count == 0

    def test_add_entry_to_collection(self, storage_with_collections):
        """Test adding entries to collections."""
        # Create collection
        collection = storage_with_collections.create_collection("Test")

        # Add entries
        storage_with_collections.add_to_collection(
            collection.id, ["entry1", "entry2", "entry3"]
        )

        # Check membership
        assert storage_with_collections.is_in_collection(collection.id, "entry1")
        assert storage_with_collections.is_in_collection(collection.id, "entry2")
        assert not storage_with_collections.is_in_collection(collection.id, "entry4")

        # Check count
        updated = storage_with_collections.get_collection(collection.id)
        assert updated.entry_count == 3

    def test_remove_from_collection(self, storage_with_collections):
        """Test removing entries from collections."""
        collection = storage_with_collections.create_collection("Test")

        # Add and remove
        storage_with_collections.add_to_collection(collection.id, ["entry1", "entry2"])
        storage_with_collections.remove_from_collection(collection.id, ["entry1"])

        assert not storage_with_collections.is_in_collection(collection.id, "entry1")
        assert storage_with_collections.is_in_collection(collection.id, "entry2")

    def test_get_entry_collections(self, storage_with_collections):
        """Test getting collections for an entry."""
        # Create multiple collections
        col1 = storage_with_collections.create_collection("Collection 1")
        col2 = storage_with_collections.create_collection("Collection 2")
        col3 = storage_with_collections.create_collection("Collection 3")

        # Add entry to some collections
        storage_with_collections.add_to_collection(col1.id, ["entry1"])
        storage_with_collections.add_to_collection(col2.id, ["entry1", "entry2"])

        # Check collections
        collections = storage_with_collections.get_entry_collections("entry1")
        assert len(collections) == 2
        assert col1.id in [c.id for c in collections]
        assert col2.id in [c.id for c in collections]
        assert col3.id not in [c.id for c in collections]

    def test_delete_collection(self, storage_with_collections):
        """Test deleting a collection."""
        collection = storage_with_collections.create_collection("To Delete")
        storage_with_collections.add_to_collection(collection.id, ["entry1"])

        # Delete collection
        assert storage_with_collections.delete_collection(collection.id)

        # Check it's gone
        assert storage_with_collections.get_collection(collection.id) is None
        assert not storage_with_collections.is_in_collection(collection.id, "entry1")

    def test_collection_tags(self, storage_with_collections):
        """Test collection tag operations."""
        collection = storage_with_collections.create_collection(
            "Tagged", tags=["initial", "test"]
        )

        # Update tags
        storage_with_collections.update_collection_tags(
            collection.id, add=["new", "additional"], remove=["test"]
        )

        updated = storage_with_collections.get_collection(collection.id)
        assert "initial" in updated.tags
        assert "new" in updated.tags
        assert "additional" in updated.tags
        assert "test" not in updated.tags

    def test_search_collections(self, storage_with_collections):
        """Test searching collections."""
        # Create collections
        storage_with_collections.create_collection(
            "ML Research", tags=["ml", "research"]
        )
        storage_with_collections.create_collection("DL Papers", tags=["dl", "research"])
        storage_with_collections.create_collection("Misc", tags=["other"])

        # Search by tag
        research = storage_with_collections.search_collections(tags=["research"])
        assert len(research) == 2

        ml = storage_with_collections.search_collections(tags=["ml"])
        assert len(ml) == 1

        # Search by name
        dl = storage_with_collections.search_collections(query="DL")
        assert len(dl) == 1

    def test_update_collection_metadata(self, storage_with_collections):
        """Test updating collection metadata."""
        collection = storage_with_collections.create_collection(
            name="Original Name", description="Original description"
        )

        # Update metadata
        updated = storage_with_collections.update_collection(
            collection.id, name="New Name", description="New description"
        )

        assert updated.name == "New Name"
        assert updated.description == "New description"
        assert updated.id == collection.id  # ID should not change

    def test_list_collections(self, storage_with_collections):
        """Test listing all collections."""
        # Create several collections
        names = ["Alpha", "Beta", "Gamma"]
        for name in names:
            storage_with_collections.create_collection(name)

        # List all
        collections = storage_with_collections.list_collections()
        assert len(collections) == 3

        # Should be sorted by name
        collection_names = [c.name for c in collections]
        assert collection_names == sorted(names)

    def test_get_collection_entries(self, storage_with_collections):
        """Test getting all entries in a collection."""
        collection = storage_with_collections.create_collection("Test")

        # Add entries
        entries = ["entry1", "entry2", "entry3"]
        storage_with_collections.add_to_collection(collection.id, entries)

        # Get entries
        result = storage_with_collections.get_collection_entries(collection.id)
        assert set(result) == set(entries)

    def test_collection_persistence(self, tmp_path):
        """Test that collections persist across instances."""
        # Create collection with first instance
        backend1 = FileSystemBackend(tmp_path)
        extension1 = CollectionExtension(backend1)

        collection = extension1.create_collection(
            "Persistent", description="Test persistence", tags=["test"]
        )
        collection_id = collection.id

        extension1.add_to_collection(collection_id, ["entry1", "entry2"])

        # Create new instance and check persistence
        backend2 = FileSystemBackend(tmp_path)
        extension2 = CollectionExtension(backend2)

        loaded = extension2.get_collection(collection_id)
        assert loaded is not None
        assert loaded.name == "Persistent"
        assert loaded.description == "Test persistence"
        assert loaded.tags == ["test"]
        assert extension2.is_in_collection(collection_id, "entry1")
        assert extension2.is_in_collection(collection_id, "entry2")

    def test_empty_collection_operations(self, storage_with_collections):
        """Test operations on empty collections."""
        collection = storage_with_collections.create_collection("Empty")

        # Operations on empty collection should work
        assert storage_with_collections.get_collection_entries(collection.id) == []

        # Remove from empty collection should not error
        storage_with_collections.remove_from_collection(collection.id, ["nonexistent"])

        # Search should find empty collection
        all_collections = storage_with_collections.list_collections()
        assert any(c.id == collection.id for c in all_collections)

    def test_collection_with_nonexistent_entries(self, storage_with_collections):
        """Test adding non-existent entries to collection."""
        collection = storage_with_collections.create_collection("Test")

        # Should be able to add any entry key (validation happens at higher level)
        storage_with_collections.add_to_collection(
            collection.id, ["nonexistent1", "nonexistent2"]
        )

        assert storage_with_collections.is_in_collection(collection.id, "nonexistent1")
        assert len(storage_with_collections.get_collection_entries(collection.id)) == 2
