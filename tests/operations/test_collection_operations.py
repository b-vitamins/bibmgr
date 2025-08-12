"""Tests for collection operations."""

import pytest

from bibmgr.core.models import Entry, EntryType
from bibmgr.operations.collection_commands import (
    AddToCollectionCommand,
    CreateCollectionCommand,
    MergeCollectionsCommand,
    RemoveFromCollectionCommand,
)
from bibmgr.operations.handlers import CollectionHandler
from bibmgr.operations.results import ResultStatus
from bibmgr.storage.backends.memory import MemoryBackend
from bibmgr.storage.extensions.collections import CollectionExtension


class TestCollectionOperations:
    """Test collection operations."""

    @pytest.fixture
    def handler(self):
        """Create collection handler with test backend."""
        backend = MemoryBackend()
        extension = CollectionExtension(backend)
        # Create repository for entry operations
        from bibmgr.storage.repository import EntryRepository

        repository = EntryRepository(backend)
        handler = CollectionHandler(repository, extension)
        return handler

    @pytest.fixture
    def sample_entries(self, handler):
        """Create sample entries."""
        entries = [
            Entry(
                key="entry1",
                type=EntryType.ARTICLE,
                title="First Article",
                author="Smith, John",
                journal="Nature",
                year=2023,
            ),
            Entry(
                key="entry2",
                type=EntryType.ARTICLE,
                title="Second Article",
                author="Doe, Jane",
                journal="Science",
                year=2023,
            ),
            Entry(
                key="entry3",
                type=EntryType.BOOK,
                title="A Book",
                author="Johnson, Alice",
                publisher="MIT Press",
                year=2022,
            ),
        ]

        # Store entries in repository (skip validation for test simplicity)
        for entry in entries:
            handler.storage.save(entry, skip_validation=True)

        return entries

    def test_create_collection_command(self, handler):
        """Test creating a collection via command."""
        command = CreateCollectionCommand(
            name="Research Papers",
            description="Important research papers",
            tags=["research", "important"],
        )

        result = handler.execute(command)

        assert result.status.is_success()
        assert result.data["collection"].name == "Research Papers"
        assert result.data["collection"].tags == ["research", "important"]

    def test_add_to_collection_command(self, handler, sample_entries):
        """Test adding entries to collection."""
        # Create collection
        create_cmd = CreateCollectionCommand(name="My Collection")
        create_result = handler.execute(create_cmd)
        collection_id = create_result.data["collection"].id

        # Add entries
        add_cmd = AddToCollectionCommand(
            collection_id=collection_id,
            entry_keys=["entry1", "entry2"],
        )

        add_result = handler.execute(add_cmd)

        assert add_result.status.is_success()
        assert add_result.data["added_count"] == 2

        # Verify membership
        assert handler.extension.is_in_collection(collection_id, "entry1")
        assert handler.extension.is_in_collection(collection_id, "entry2")
        assert not handler.extension.is_in_collection(collection_id, "entry3")

    def test_add_nonexistent_entries(self, handler):
        """Test adding non-existent entries."""
        # Create collection
        create_cmd = CreateCollectionCommand(name="Test")
        collection_id = handler.execute(create_cmd).data["collection"].id

        # Try to add non-existent entries
        add_cmd = AddToCollectionCommand(
            collection_id=collection_id,
            entry_keys=["entry1", "nonexistent1", "nonexistent2"],
        )

        # Only entry1 exists
        handler.storage.save(
            Entry(
                key="entry1",
                type=EntryType.ARTICLE,
                title="Test",
                author="Test Author",
                journal="Test Journal",
                year=2023,
            ),
            skip_validation=True,
        )

        result = handler.execute(add_cmd)

        assert result.status.is_success()
        assert result.data["added_count"] == 1
        assert result.data["missing_keys"] == ["nonexistent1", "nonexistent2"]

    def test_remove_from_collection_command(self, handler, sample_entries):
        """Test removing entries from collection."""
        # Setup
        create_cmd = CreateCollectionCommand(name="Test")
        collection_id = handler.execute(create_cmd).data["collection"].id

        add_cmd = AddToCollectionCommand(
            collection_id=collection_id,
            entry_keys=["entry1", "entry2", "entry3"],
        )
        handler.execute(add_cmd)

        # Remove one entry
        remove_cmd = RemoveFromCollectionCommand(
            collection_id=collection_id,
            entry_keys=["entry2"],
        )

        result = handler.execute(remove_cmd)

        assert result.status.is_success()
        assert handler.extension.is_in_collection(collection_id, "entry1")
        assert not handler.extension.is_in_collection(collection_id, "entry2")
        assert handler.extension.is_in_collection(collection_id, "entry3")

    def test_merge_collections_command(self, handler, sample_entries):
        """Test merging collections."""
        # Create collections
        col1 = handler.execute(
            CreateCollectionCommand(name="Collection 1", tags=["tag1"])
        ).data["collection"]

        col2 = handler.execute(
            CreateCollectionCommand(name="Collection 2", tags=["tag2"])
        ).data["collection"]

        # Add different entries
        handler.execute(AddToCollectionCommand(col1.id, ["entry1", "entry2"]))
        handler.execute(AddToCollectionCommand(col2.id, ["entry2", "entry3"]))

        # Merge
        merge_cmd = MergeCollectionsCommand(
            source_ids=[col1.id, col2.id],
            target_name="Merged Collection",
            combine_tags=True,
        )

        result = handler.execute(merge_cmd)

        assert result.status.is_success()
        merged = result.data["collection"]
        assert merged.name == "Merged Collection"
        assert set(merged.tags) == {"tag1", "tag2"}

        # Check all entries are included
        entries = handler.extension.get_collection_entries(merged.id)
        assert set(entries) == {"entry1", "entry2", "entry3"}

        # Original collections should be deleted
        assert handler.extension.get_collection(col1.id) is None
        assert handler.extension.get_collection(col2.id) is None

    def test_merge_without_deleting_sources(self, handler, sample_entries):
        """Test merging collections without deleting sources."""
        # Create collections
        col1 = handler.execute(CreateCollectionCommand(name="Source 1")).data[
            "collection"
        ]

        col2 = handler.execute(CreateCollectionCommand(name="Source 2")).data[
            "collection"
        ]

        # Add entries
        handler.execute(AddToCollectionCommand(col1.id, ["entry1"]))
        handler.execute(AddToCollectionCommand(col2.id, ["entry2"]))

        # Merge without deleting
        merge_cmd = MergeCollectionsCommand(
            source_ids=[col1.id, col2.id],
            target_name="Merged",
            delete_sources=False,
        )

        result = handler.execute(merge_cmd)

        assert result.status.is_success()

        # Sources should still exist
        assert handler.extension.get_collection(col1.id) is not None
        assert handler.extension.get_collection(col2.id) is not None

    def test_operations_with_invalid_collection(self, handler):
        """Test operations with invalid collection ID."""
        # Try to add to non-existent collection
        add_cmd = AddToCollectionCommand(
            collection_id="invalid-id",
            entry_keys=["entry1"],
        )

        result = handler.execute(add_cmd)

        assert not result.status.is_success()
        assert (
            "Invalid collection ID" in result.message
            or "Collection not found" in result.message
        )

    def test_merge_with_invalid_source(self, handler):
        """Test merging with invalid source collection."""
        # Create one valid collection
        col1 = handler.execute(CreateCollectionCommand(name="Valid")).data["collection"]

        # Try to merge with invalid source
        merge_cmd = MergeCollectionsCommand(
            source_ids=[col1.id, "invalid-id"],
            target_name="Merged",
        )

        result = handler.execute(merge_cmd)

        assert not result.status.is_success()
        assert (
            "Invalid collection ID" in result.message or "not found" in result.message
        )

    def test_empty_merge(self, handler):
        """Test merging empty collections."""
        # Create empty collections
        col1 = handler.execute(CreateCollectionCommand(name="Empty 1")).data[
            "collection"
        ]
        col2 = handler.execute(CreateCollectionCommand(name="Empty 2")).data[
            "collection"
        ]

        # Merge empty collections
        merge_cmd = MergeCollectionsCommand(
            source_ids=[col1.id, col2.id],
            target_name="Merged Empty",
        )

        result = handler.execute(merge_cmd)

        assert result.status.is_success()
        assert result.data["entry_count"] == 0

    def test_collection_command_error_handling(self, handler):
        """Test error handling in collection commands."""
        # Test with invalid command type
        class InvalidCommand:
            pass
        
        result = handler.execute(InvalidCommand())
        assert not result.status.is_success()
        assert result.status == ResultStatus.ERROR
        assert "Unknown command" in result.message

        # Test with empty name
        result = handler.execute(CreateCollectionCommand(name=""))
        assert not result.status.is_success()
        assert result.status == ResultStatus.ERROR
        assert "Collection name cannot be empty" in result.message

    def test_add_all_entries_to_collection(self, handler, sample_entries):
        """Test adding all entries at once."""
        collection = handler.execute(CreateCollectionCommand(name="All Entries")).data[
            "collection"
        ]

        # Get all entry keys
        all_keys = [e.key for e in sample_entries]

        # Add all
        result = handler.execute(AddToCollectionCommand(collection.id, all_keys))

        assert result.status.is_success()
        assert result.data["added_count"] == len(sample_entries)

    def test_remove_all_from_collection(self, handler, sample_entries):
        """Test removing all entries from collection."""
        # Setup
        collection = handler.execute(CreateCollectionCommand(name="Test")).data[
            "collection"
        ]

        all_keys = [e.key for e in sample_entries]
        handler.execute(AddToCollectionCommand(collection.id, all_keys))

        # Remove all
        result = handler.execute(RemoveFromCollectionCommand(collection.id, all_keys))

        assert result.status.is_success()
        assert handler.extension.get_collection_entries(collection.id) == []
