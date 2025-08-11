"""Tests for operation commands (Create, Update, Delete, Merge).

This module tests the command pattern implementation for all CRUD operations
including validation, error handling, transactions, and event publishing.
"""

from datetime import datetime
from unittest.mock import Mock

from bibmgr.core.models import Entry
from bibmgr.storage.events import EventType

from ..operations.conftest import (
    assert_entry_equal,
    assert_events_published,
    assert_result_failure,
    assert_result_success,
    create_entry_with_data,
)


class TestCreateCommand:
    """Test create command and handler."""

    def test_create_simple_entry(self, entry_repository, event_bus, minimal_entry):
        """Test creating a simple valid entry."""
        from bibmgr.operations.commands.create import CreateCommand, CreateHandler

        handler = CreateHandler(entry_repository, event_bus)
        command = CreateCommand(entry=minimal_entry)

        result = handler.execute(command)

        assert_result_success(result, "created successfully")
        assert result.entity_id == minimal_entry.key

        # Verify entry was saved
        saved = entry_repository.find(minimal_entry.key)
        assert saved is not None
        assert_entry_equal(saved, minimal_entry)

        # Verify event was published
        assert_events_published(event_bus, [EventType.ENTRY_CREATED])

    def test_create_with_validation_errors(self, entry_repository, event_bus):
        """Test create fails with validation errors."""
        from bibmgr.operations.commands.create import CreateCommand, CreateHandler

        # Entry missing required fields for article
        invalid_entry = create_entry_with_data(
            key="invalid",
            type="article",
            title="Missing Required Fields",
            # Missing: author, journal, year
        )

        handler = CreateHandler(entry_repository, event_bus)
        command = CreateCommand(entry=invalid_entry)

        result = handler.execute(command)

        assert_result_failure(result, "validation failed")
        assert result.validation_errors and len(result.validation_errors) > 0

        # Verify entry was not saved
        assert entry_repository.find(invalid_entry.key) is None

        # Verify no event was published
        assert event_bus.get_history() == []

    def test_create_with_force_flag(self, entry_repository, event_bus):
        """Test force create bypasses validation."""
        from bibmgr.operations.commands.create import CreateCommand, CreateHandler

        invalid_entry = create_entry_with_data(
            key="forced",
            type="article",
            title="Forced Entry",
            # Missing required fields
        )

        handler = CreateHandler(entry_repository, event_bus)
        command = CreateCommand(entry=invalid_entry, force=True)

        result = handler.execute(command)

        assert_result_success(result)
        assert entry_repository.find(invalid_entry.key) is not None

    def test_create_duplicate_key(self, entry_repository, event_bus, minimal_entry):
        """Test create fails when key already exists."""
        from bibmgr.operations.commands.create import CreateCommand, CreateHandler

        # First create
        handler = CreateHandler(entry_repository, event_bus)
        command = CreateCommand(entry=minimal_entry)
        handler.execute(command)

        # Try to create again
        duplicate = create_entry_with_data(
            key=minimal_entry.key,
            title="Different Title",
            year=2025,
        )
        command = CreateCommand(entry=duplicate)
        result = handler.execute(command)

        assert_result_failure(result)
        assert result.status.name == "CONFLICT"
        assert "already exists" in result.message

        # No naming policy provided, so no suggestions expected
        # If we had provided a naming policy, it would suggest an alternative key

    def test_create_with_naming_policy(self, entry_repository, event_bus):
        """Test create with custom naming policy."""
        from bibmgr.operations.commands.create import CreateCommand, CreateHandler
        from bibmgr.operations.policies.naming import KeyNamingPolicy

        # Create entry with existing key
        existing = create_entry_with_data(key="smith2024")
        entry_repository.save(existing)

        # Custom naming policy
        naming_policy = KeyNamingPolicy(style="author_year")

        handler = CreateHandler(entry_repository, event_bus, naming_policy)

        # Try to create with same key
        new_entry = create_entry_with_data(
            key="smith2024",
            author="Smith, John",
            title="Another Paper",
            year=2024,
        )
        command = CreateCommand(entry=new_entry)
        result = handler.execute(command)

        assert result.status.name == "CONFLICT"
        # Should suggest smith2024a or smith2024_1
        assert result.suggestions
        assert "smith2024" in result.suggestions["alternative_key"]

    def test_create_dry_run(self, entry_repository, event_bus, complete_article):
        """Test dry run doesn't actually create."""
        from bibmgr.operations.commands.create import CreateCommand, CreateHandler

        handler = CreateHandler(entry_repository, event_bus)
        command = CreateCommand(entry=complete_article, dry_run=True)

        result = handler.execute(command)

        assert result.status.name == "DRY_RUN"
        assert "would be created" in result.message

        # Verify nothing was saved
        assert entry_repository.find(complete_article.key) is None
        assert event_bus.get_history() == []

    def test_create_with_metadata(self, entry_repository, event_bus, minimal_entry):
        """Test create with additional metadata."""
        from bibmgr.operations.commands.create import CreateCommand, CreateHandler

        handler = CreateHandler(entry_repository, event_bus)
        metadata = {"source": "import", "tags": ["test", "sample"]}
        command = CreateCommand(entry=minimal_entry, metadata=metadata)

        result = handler.execute(command)

        assert_result_success(result)

        # Check event includes metadata
        events = event_bus.get_history()
        assert len(events) == 1
        assert events[0].data.get("metadata") == metadata

    def test_create_preconditions(self):
        """Test create command precondition validation."""
        from bibmgr.operations.commands.create import CreateCommand
        from bibmgr.operations.validators import CreatePreconditions

        preconditions = CreatePreconditions()

        # Test with None entry
        command = CreateCommand(entry=None)
        violations = preconditions.check(command)
        assert "Entry cannot be None" in violations

        # Test with missing key
        entry = create_entry_with_data(key="", title="No Key")
        command = CreateCommand(entry=entry)
        violations = preconditions.check(command)
        assert any("key is required" in v for v in violations)

        # Test with valid entry
        entry = create_entry_with_data(key="valid", title="Valid")
        command = CreateCommand(entry=entry)
        violations = preconditions.check(command)
        assert len(violations) == 0


class TestBulkCreateCommand:
    """Test bulk create operations."""

    def test_bulk_create_success(self, entry_repository, event_bus, sample_entries):
        """Test bulk create of multiple entries."""
        from bibmgr.operations.commands.create import BulkCreateHandler, CreateHandler

        create_handler = CreateHandler(entry_repository, event_bus)
        handler = BulkCreateHandler(entry_repository, event_bus, create_handler)

        results = handler.execute(sample_entries)

        assert len(results) == len(sample_entries)
        for result in results:
            assert_result_success(result)

        # Verify all saved
        for entry in sample_entries:
            assert entry_repository.find(entry.key) is not None

    def test_bulk_create_stop_on_error(self, entry_repository, event_bus):
        """Test bulk create stops on first error."""
        from bibmgr.operations.commands.create import BulkCreateHandler, CreateHandler

        entries = [
            create_entry_with_data(key="valid1"),
            create_entry_with_data(key="invalid", type="article"),  # Missing fields
            create_entry_with_data(key="valid2"),
        ]

        create_handler = CreateHandler(entry_repository, event_bus)
        handler = BulkCreateHandler(entry_repository, event_bus, create_handler)

        results = handler.execute(entries, stop_on_error=True)

        assert len(results) == 2  # Stopped after error
        assert_result_success(results[0])
        assert_result_failure(results[1])

    def test_bulk_create_atomic(self, entry_repository, event_bus):
        """Test atomic bulk create - all or nothing."""
        from bibmgr.operations.commands.create import BulkCreateHandler, CreateHandler

        entries = [
            create_entry_with_data(key="atomic1"),
            create_entry_with_data(key="atomic2"),
            create_entry_with_data(
                key="invalid", type="article"
            ),  # Will fail validation
        ]

        create_handler = CreateHandler(entry_repository, event_bus)
        handler = BulkCreateHandler(entry_repository, event_bus, create_handler)

        results = handler.execute(entries, atomic=True)

        assert len(results) == len(entries)
        for result in results:
            assert result.status.name == "TRANSACTION_FAILED"

        # Verify nothing was saved
        for entry in entries:
            assert entry_repository.find(entry.key) is None

    def test_bulk_create_with_progress(
        self, entry_repository, event_bus, progress_reporter
    ):
        """Test bulk create reports progress."""
        from bibmgr.operations.commands.create import BulkCreateHandler, CreateHandler

        entries = [create_entry_with_data(key=f"entry{i}") for i in range(5)]

        # Mock event bus to capture progress events
        progress_events = []

        def capture_progress(event):
            if event.type == EventType.PROGRESS:
                progress_events.append(event)

        event_bus.subscribe(EventType.PROGRESS, capture_progress)

        create_handler = CreateHandler(entry_repository, event_bus)
        handler = BulkCreateHandler(entry_repository, event_bus, create_handler)

        results = handler.execute(entries)

        assert len(results) == 5
        assert len(progress_events) >= 5  # One per entry


class TestUpdateCommand:
    """Test update command and handler."""

    def test_update_single_field(self, populated_repository, event_bus):
        """Test updating a single field."""
        from bibmgr.operations.commands.update import UpdateCommand, UpdateHandler

        handler = UpdateHandler(populated_repository, event_bus)

        # Update title
        command = UpdateCommand(
            key="smith2020",
            updates={"title": "Updated Title"},
        )
        result = handler.execute(command)

        assert_result_success(result)

        # Verify update
        updated = populated_repository.find("smith2020")
        assert updated.title == "Updated Title"
        assert updated.author == "Smith, John"  # Unchanged

        # Verify event
        assert_events_published(event_bus, [EventType.ENTRY_UPDATED])

    def test_update_multiple_fields(self, populated_repository, event_bus):
        """Test updating multiple fields at once."""
        from bibmgr.operations.commands.update import UpdateCommand, UpdateHandler

        handler = UpdateHandler(populated_repository, event_bus)

        updates = {
            "title": "Completely New Title",
            "journal": "Science",
            "volume": "123",
            "pages": "45--67",
        }

        command = UpdateCommand(key="smith2020", updates=updates)
        result = handler.execute(command)

        assert_result_success(result)

        updated = populated_repository.find("smith2020")
        assert updated.title == updates["title"]
        assert updated.journal == updates["journal"]
        assert updated.volume == updates["volume"]
        assert updated.pages == updates["pages"]

    def test_update_remove_field(self, populated_repository, event_bus):
        """Test removing a field by setting to None."""
        from bibmgr.operations.commands.update import UpdateCommand, UpdateHandler

        # First add a field
        entry = populated_repository.find("smith2020")
        data = entry.to_dict()
        data["note"] = "This will be removed"
        populated_repository.save(Entry.from_dict(data))

        handler = UpdateHandler(populated_repository, event_bus)
        command = UpdateCommand(
            key="smith2020",
            updates={"note": None},  # Remove note field
        )
        result = handler.execute(command)

        assert_result_success(result)

        updated = populated_repository.find("smith2020")
        assert not hasattr(updated, "note") or updated.note is None

    def test_update_nonexistent_entry(self, populated_repository, event_bus):
        """Test updating entry that doesn't exist."""
        from bibmgr.operations.commands.update import UpdateCommand, UpdateHandler

        handler = UpdateHandler(populated_repository, event_bus)
        command = UpdateCommand(
            key="nonexistent",
            updates={"title": "New Title"},
        )
        result = handler.execute(command)

        assert_result_failure(result)
        assert result.status.name == "NOT_FOUND"

    def test_update_with_validation(self, populated_repository, event_bus):
        """Test update validates the result."""
        from bibmgr.operations.commands.update import UpdateCommand, UpdateHandler

        handler = UpdateHandler(populated_repository, event_bus)

        # Update that makes entry invalid
        command = UpdateCommand(
            key="smith2020",
            updates={"year": "invalid_year"},  # Invalid year
            validate=True,
        )
        result = handler.execute(command)

        assert_result_failure(result, "validation failed")
        assert hasattr(result, "validation_errors")

    def test_update_skip_validation(self, populated_repository, event_bus):
        """Test update can skip validation."""
        from bibmgr.operations.commands.update import UpdateCommand, UpdateHandler

        handler = UpdateHandler(populated_repository, event_bus)

        # Update with potentially invalid business logic (e.g., future year)
        # but valid type. Type validation cannot be skipped.
        command = UpdateCommand(
            key="smith2020",
            updates={"year": 2099},  # Far future year - would fail business validation
            validate=False,
        )
        result = handler.execute(command)

        assert_result_success(result)

    def test_update_track_changes(self, populated_repository, event_bus):
        """Test update tracks field-level changes."""
        from bibmgr.operations.commands.update import UpdateCommand, UpdateHandler

        handler = UpdateHandler(populated_repository, event_bus)

        original = populated_repository.find("smith2020")
        original_title = original.title

        command = UpdateCommand(
            key="smith2020",
            updates={"title": "New Title", "volume": "999"},
            track_changes=True,
        )
        result = handler.execute(command)

        assert_result_success(result)
        assert result.data and "changes" in result.data

        changes = result.data["changes"]
        assert len(changes) >= 1

        # Find title change
        title_change = next((c for c in changes if c.field == "title"), None)
        assert title_change is not None
        assert title_change.old_value == original_title
        assert title_change.new_value == "New Title"

    def test_update_create_if_missing(self, populated_repository, event_bus):
        """Test update can create entry if missing."""
        from bibmgr.operations.commands.update import UpdateCommand, UpdateHandler

        handler = UpdateHandler(populated_repository, event_bus)

        command = UpdateCommand(
            key="new_entry",
            updates={
                "type": "misc",
                "title": "Created by Update",
                "year": 2024,
            },
            create_if_missing=True,
        )
        result = handler.execute(command)

        # Should create new entry
        assert_result_success(result)
        created = populated_repository.find("new_entry")
        assert created is not None
        assert created.title == "Created by Update"

    def test_update_preconditions(self):
        """Test update command precondition validation."""
        from bibmgr.operations.commands.update import UpdateCommand
        from bibmgr.operations.validators import UpdatePreconditions

        preconditions = UpdatePreconditions()

        # Test with empty key
        command = UpdateCommand(key="", updates={"title": "New"})
        violations = preconditions.check(command)
        assert any("key is required" in v for v in violations)

        # Test with no updates
        command = UpdateCommand(key="valid", updates={})
        violations = preconditions.check(command)
        assert any("No updates provided" in v for v in violations)

        # Test updating protected field
        command = UpdateCommand(key="valid", updates={"added": datetime.now()})
        violations = preconditions.check(command)
        assert any("protected field" in v for v in violations)


class TestDeleteCommand:
    """Test delete command and handler."""

    def test_delete_simple(self, populated_repository, event_bus):
        """Test simple delete operation."""
        from bibmgr.operations.commands.delete import DeleteCommand, DeleteHandler

        handler = DeleteHandler(
            populated_repository,
            Mock(),  # collection_repository
            Mock(),  # metadata_store
            event_bus,
        )

        command = DeleteCommand(key="smith2020")
        result = handler.execute(command)

        assert_result_success(result)
        assert populated_repository.find("smith2020") is None
        assert_events_published(event_bus, [EventType.ENTRY_DELETED])

    def test_delete_nonexistent(self, populated_repository, event_bus):
        """Test deleting nonexistent entry."""
        from bibmgr.operations.commands.delete import DeleteCommand, DeleteHandler

        handler = DeleteHandler(
            populated_repository,
            Mock(),
            Mock(),
            event_bus,
        )

        command = DeleteCommand(key="nonexistent")
        result = handler.execute(command)

        assert_result_failure(result)
        assert result.status.name == "NOT_FOUND"

    def test_delete_with_references(self, entry_repository, event_bus):
        """Test delete fails when entry has references."""
        from bibmgr.operations.commands.delete import DeleteCommand, DeleteHandler

        # Create entries with cross-reference
        main_entry = create_entry_with_data(key="main", title="Main Entry")
        ref_entry = create_entry_with_data(
            key="ref",
            title="References Main",
            crossref="main",
        )

        entry_repository.save(main_entry)
        entry_repository.save(ref_entry)

        handler = DeleteHandler(
            entry_repository,
            Mock(),
            Mock(),
            event_bus,
        )

        command = DeleteCommand(key="main")
        result = handler.execute(command)

        assert_result_failure(result)
        assert result.status.name == "CONFLICT"
        assert "references" in result.message

    def test_delete_force_with_references(self, entry_repository, event_bus):
        """Test force delete ignores references."""
        from bibmgr.operations.commands.delete import DeleteCommand, DeleteHandler

        # Create entries with cross-reference
        main_entry = create_entry_with_data(key="main", title="Main Entry")
        ref_entry = create_entry_with_data(
            key="ref",
            title="References Main",
            crossref="main",
        )

        entry_repository.save(main_entry)
        entry_repository.save(ref_entry)

        handler = DeleteHandler(
            entry_repository,
            Mock(),
            Mock(),
            event_bus,
        )

        command = DeleteCommand(key="main", force=True)
        result = handler.execute(command)

        assert_result_success(result)
        assert entry_repository.find("main") is None

    def test_delete_cascade_metadata(
        self, populated_repository, collection_repository, metadata_store, event_bus
    ):
        """Test cascade delete of metadata."""
        from bibmgr.operations.commands.delete import DeleteCommand, DeleteHandler

        # Add metadata
        metadata = metadata_store.get_metadata("smith2020")
        metadata.add_tags("test", "delete")
        metadata.rating = 5
        metadata_store.save_metadata(metadata)

        # Add notes
        from bibmgr.storage.metadata import Note

        note = Note(entry_key="smith2020", content="Test note")
        metadata_store.add_note(note)

        handler = DeleteHandler(
            populated_repository,
            collection_repository,
            metadata_store,
            event_bus,
        )

        command = DeleteCommand(
            key="smith2020",
            cascade=True,
            cascade_metadata=True,
            cascade_notes=True,
        )
        result = handler.execute(command)

        assert_result_success(result)
        assert populated_repository.find("smith2020") is None

        # Verify cascade
        assert metadata_store.get_metadata("smith2020").tags == set()
        assert metadata_store.get_notes("smith2020") == []

        # Check cascade info in result
        assert result.data and "cascaded" in result.data
        assert any("metadata" in c for c in result.data["cascaded"])

    def test_delete_remove_from_collections(
        self, populated_repository, collection_repository, event_bus
    ):
        """Test entry is removed from collections on delete."""

        # Create collection with entry
        # Collection stores entry keys directly
        from bibmgr.core.models import Collection
        from bibmgr.operations.commands.delete import DeleteCommand, DeleteHandler

        collection_data = {
            "name": "Test Collection",
            "entry_keys": ("smith2020",),
        }
        collection = Collection(**collection_data)
        collection_repository.save(collection)

        handler = DeleteHandler(
            populated_repository,
            collection_repository,
            Mock(),  # metadata_store
            event_bus,
        )

        command = DeleteCommand(key="smith2020")
        result = handler.execute(command)

        assert_result_success(result)

        # Verify removed from collection
        updated_collection = collection_repository.find(collection.id)
        assert "smith2020" not in updated_collection.entry_keys


class TestMergeCommand:
    """Test merge command and handler."""

    def test_merge_two_entries(self, entry_repository, event_bus):
        """Test merging two duplicate entries."""
        from bibmgr.operations.commands.merge import MergeCommand, MergeHandler

        # Create two versions of same paper
        entry1 = create_entry_with_data(
            key="smith2020a",
            author="Smith, J.",
            title="Machine Learning",
            journal="Nature",
            year=2020,
            doi="10.1038/test",
        )
        entry2 = create_entry_with_data(
            key="smith2020b",
            author="Smith, John and Doe, Jane",
            title="Machine Learning Applications",
            journal="Nature",
            year=2020,
            doi="10.1038/test",
            pages="100--110",
        )

        entry_repository.save(entry1)
        entry_repository.save(entry2)

        handler = MergeHandler(entry_repository, event_bus)
        command = MergeCommand(
            source_keys=[entry1.key, entry2.key],
            target_key=entry1.key,
        )
        result = handler.execute(command)

        assert_result_success(result)

        # Check merged entry
        merged = entry_repository.find(entry1.key)
        assert merged is not None
        assert "John" in merged.author  # Got full name
        assert "Doe" in merged.author  # Got co-author
        assert merged.pages == "100--110"  # Got additional field

        # Check source deleted
        assert entry_repository.find(entry2.key) is None

    def test_merge_multiple_entries(self, entry_repository, event_bus):
        """Test merging more than two entries."""
        from bibmgr.operations.commands.merge import MergeCommand, MergeHandler

        entries = []
        for i in range(3):
            entry = create_entry_with_data(
                key=f"paper{i}",
                author="Author, A.",
                title=f"Paper Version {i}",
                year=2020,
                note=f"Note {i}",
            )
            entries.append(entry)
            entry_repository.save(entry)

        handler = MergeHandler(entry_repository, event_bus)
        command = MergeCommand(
            source_keys=[e.key for e in entries],
            strategy="SMART",
        )
        result = handler.execute(command)

        assert_result_success(result)
        assert "Merged 3 entries" in result.message

    def test_merge_auto_select_target(self, entry_repository, event_bus):
        """Test merge automatically selects best target key."""
        from bibmgr.operations.commands.merge import MergeCommand, MergeHandler

        # Create entries with different completeness
        minimal = create_entry_with_data(
            key="minimal",
            title="Paper",
            year=2020,
        )
        complete = create_entry_with_data(
            key="complete",
            author="Smith, John",
            title="Complete Paper Title",
            journal="Nature",
            year=2020,
            volume="123",
            pages="45--67",
            doi="10.1038/test",
        )

        entry_repository.save(minimal)
        entry_repository.save(complete)

        handler = MergeHandler(entry_repository, event_bus)
        command = MergeCommand(
            source_keys=[minimal.key, complete.key],
            # No target_key specified
        )
        result = handler.execute(command)

        assert_result_success(result)
        # Should pick "complete" as target due to more fields
        assert result.entity_id == complete.key

    def test_merge_validation_fixup(self, entry_repository, event_bus):
        """Test merge fixes validation errors in result."""
        from bibmgr.operations.commands.merge import MergeCommand, MergeHandler

        # Create entries that when merged might have issues
        entry1 = create_entry_with_data(
            key="entry1",
            type="article",
            title="Paper",
            journal="Nature",
            year=2020,
            # Missing author
        )
        entry2 = create_entry_with_data(
            key="entry2",
            type="article",
            editor="Editor, E.",  # Has editor but not author
            title="Paper Title",
            journal="Nature",
            year=2020,
        )

        entry_repository.save(entry1, skip_validation=True)
        entry_repository.save(entry2, skip_validation=True)

        handler = MergeHandler(entry_repository, event_bus)
        command = MergeCommand(source_keys=[entry1.key, entry2.key])
        result = handler.execute(command)

        assert_result_success(result)
        # Policy should fix missing author by using editor

    def test_merge_strategies(self, entry_repository, event_bus):
        """Test different merge strategies."""
        from bibmgr.operations.commands.merge import MergeCommand, MergeHandler

        # Create entries with overlapping fields
        entry1 = create_entry_with_data(
            key="v1",
            title="Version 1",
            keywords=["ML", "AI"],
            note="First note",
        )
        entry2 = create_entry_with_data(
            key="v2",
            title="Version 2",
            keywords=["AI", "Deep Learning"],
            note="Second note",
        )

        entry_repository.save(entry1)
        entry_repository.save(entry2)

        handler = MergeHandler(entry_repository, event_bus)

        # Test UNION strategy
        command = MergeCommand(
            source_keys=["v1", "v2"],
            strategy="UNION",
        )
        result = handler.execute(command)
        assert_result_success(result)

        merged = result.data["merged_entry"] if result.data else None
        assert merged is not None
        # Keywords should be combined
        assert set(merged.keywords) == {"ML", "AI", "Deep Learning"}

    def test_merge_custom_rules(self, entry_repository, event_bus):
        """Test merge with custom rules."""
        from bibmgr.operations.commands.merge import MergeCommand, MergeHandler

        entry1 = create_entry_with_data(key="e1", title="Title 1", year=2020)
        entry2 = create_entry_with_data(key="e2", title="Title 2", year=2021)

        entry_repository.save(entry1)
        entry_repository.save(entry2)

        handler = MergeHandler(entry_repository, event_bus)

        # Custom rules to prefer newer year
        custom_rules = {"prefer_field": "year", "prefer_value": "newest"}

        command = MergeCommand(
            source_keys=["e1", "e2"],
            strategy="CUSTOM",
            custom_rules=custom_rules,
        )
        result = handler.execute(command)

        assert_result_success(result)
        merged = result.data["merged_entry"] if result.data else None
        assert merged is not None
        assert merged.year == 2021  # Newer year

    def test_merge_keep_sources(self, entry_repository, event_bus):
        """Test merge without deleting source entries."""
        from bibmgr.operations.commands.merge import MergeCommand, MergeHandler

        entry1 = create_entry_with_data(key="keep1")
        entry2 = create_entry_with_data(key="keep2")

        entry_repository.save(entry1)
        entry_repository.save(entry2)

        handler = MergeHandler(entry_repository, event_bus)
        command = MergeCommand(
            source_keys=["keep1", "keep2"],
            target_key="merged",
            delete_sources=False,
        )
        result = handler.execute(command)

        assert_result_success(result)
        # All entries should exist
        assert entry_repository.find("keep1") is not None
        assert entry_repository.find("keep2") is not None
        assert entry_repository.find("merged") is not None

    def test_merge_preconditions(self):
        """Test merge command precondition validation."""
        from bibmgr.operations.commands.merge import MergeCommand
        from bibmgr.operations.validators import MergePreconditions

        preconditions = MergePreconditions()

        # Test with no sources
        command = MergeCommand(source_keys=[])
        violations = preconditions.check(command)
        assert any("No source keys" in v for v in violations)

        # Test with single source
        command = MergeCommand(source_keys=["only_one"])
        violations = preconditions.check(command)
        assert any("At least 2 entries" in v for v in violations)

        # Test with duplicate keys
        command = MergeCommand(source_keys=["dup", "dup"])
        violations = preconditions.check(command)
        assert any("Duplicate keys" in v for v in violations)


class TestAutoMerge:
    """Test automatic duplicate detection and merging."""

    def test_auto_merge_by_doi(self, populated_repository, event_bus):
        """Test auto-merge finds and merges entries with same DOI."""
        from bibmgr.core.duplicates import DuplicateDetector
        from bibmgr.operations.commands.merge import AutoMergeHandler, MergeHandler

        # Add duplicate entry with same DOI
        original = populated_repository.find("smith2020")
        duplicate_data = original.to_dict()
        duplicate_data.update(
            {
                "key": "smith2020_dup",
                "doi": "10.1038/nature.2020.1234",  # Same DOI
                "pages": "100--200",  # Additional info
            }
        )
        duplicate = Entry.from_dict(duplicate_data)
        populated_repository.save(duplicate)

        merge_handler = MergeHandler(populated_repository, event_bus)
        detector = DuplicateDetector(populated_repository.find_all())
        handler = AutoMergeHandler(populated_repository, merge_handler, detector)

        results = handler.execute(min_similarity=0.8)

        assert len(results) > 0
        # Should find and merge the DOI duplicates
        assert any(r.status.is_success() for r in results)

    def test_auto_merge_dry_run(self, populated_repository, event_bus):
        """Test auto-merge in dry run mode."""
        from bibmgr.core.duplicates import DuplicateDetector
        from bibmgr.operations.commands.merge import AutoMergeHandler, MergeHandler

        merge_handler = MergeHandler(populated_repository, event_bus)
        detector = DuplicateDetector(populated_repository.find_all())
        handler = AutoMergeHandler(populated_repository, merge_handler, detector)

        results = handler.execute(dry_run=True)

        # All results should be dry run
        for result in results:
            assert result.status.name == "DRY_RUN"
            assert "Would merge" in result.message


class TestCommandIntegration:
    """Test integration between different commands."""

    def test_create_update_delete_flow(self, entry_repository, event_bus):
        """Test full lifecycle of an entry."""
        from bibmgr.operations.commands.create import CreateCommand, CreateHandler
        from bibmgr.operations.commands.delete import DeleteCommand, DeleteHandler
        from bibmgr.operations.commands.update import UpdateCommand, UpdateHandler

        # Create
        create_handler = CreateHandler(entry_repository, event_bus)
        entry = create_entry_with_data(key="lifecycle", title="Original")
        result = create_handler.execute(CreateCommand(entry=entry))
        assert_result_success(result)

        # Update
        update_handler = UpdateHandler(entry_repository, event_bus)
        result = update_handler.execute(
            UpdateCommand(key="lifecycle", updates={"title": "Updated"})
        )
        assert_result_success(result)

        # Delete
        delete_handler = DeleteHandler(
            entry_repository,
            Mock(),
            Mock(),
            event_bus,
        )
        result = delete_handler.execute(DeleteCommand(key="lifecycle"))
        assert_result_success(result)

        # Verify events in order
        events = event_bus.get_history()
        event_types = [e.type for e in events]
        assert EventType.ENTRY_CREATED in event_types
        assert EventType.ENTRY_UPDATED in event_types
        assert EventType.ENTRY_DELETED in event_types

    def test_bulk_create_then_merge(self, entry_repository, event_bus):
        """Test creating entries in bulk then merging duplicates."""
        from bibmgr.core.duplicates import DuplicateDetector
        from bibmgr.operations.commands.create import BulkCreateHandler, CreateHandler
        from bibmgr.operations.commands.merge import AutoMergeHandler, MergeHandler

        # Create entries with duplicates
        # Note: DuplicateDetector requires exact normalized matches
        # or same DOI to detect duplicates
        entries = [
            create_entry_with_data(
                key="paper1",
                author="Smith, J.",
                title="Machine Learning Study",
                year=2020,
                doi="10.1234/ml.2020",  # Same DOI
            ),
            create_entry_with_data(
                key="paper2",
                author="Smith, John",  # Different author format
                title="Machine Learning Study",
                year=2020,
                doi="10.1234/ml.2020",  # Same DOI - will be detected as duplicate
            ),
            create_entry_with_data(
                key="other",
                author="Doe, J.",
                title="Different Paper",
                year=2021,
            ),
        ]

        # Bulk create
        create_handler = CreateHandler(entry_repository, event_bus)
        bulk_handler = BulkCreateHandler(entry_repository, event_bus, create_handler)
        results = bulk_handler.execute(entries)
        assert all(r.status.is_success() for r in results)

        # Auto merge duplicates
        merge_handler = MergeHandler(entry_repository, event_bus)
        detector = DuplicateDetector(entry_repository.find_all())
        auto_handler = AutoMergeHandler(entry_repository, merge_handler, detector)
        merge_results = auto_handler.execute(min_similarity=0.7)

        # Should find and merge paper1 and paper2
        assert len(merge_results) >= 1
        assert any(
            "paper1" in str(r.data) or "paper2" in str(r.data) for r in merge_results
        )
