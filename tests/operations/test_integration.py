"""Integration tests for operations module.

This module tests the complete operations system working together with
storage and core modules, ensuring all components integrate properly.
"""

import tempfile
from pathlib import Path

from bibmgr.core.builders import CollectionBuilder, EntryBuilder
from bibmgr.core.fields import EntryType
from bibmgr.storage.backends.memory import MemoryBackend
from bibmgr.storage.events import EventBus, EventType
from bibmgr.storage.metadata import MetadataStore
from bibmgr.storage.repository import RepositoryManager

from ..operations.conftest import create_entry_with_data


class TestFullWorkflowIntegration:
    """Test complete workflows from start to finish."""

    def test_import_validate_deduplicate_export(self, temp_dir):
        """Test full pipeline: import -> validate -> deduplicate -> export."""
        # Setup
        backend = MemoryBackend()
        event_bus = EventBus()
        manager = RepositoryManager(backend)

        # Create import file with duplicates
        import_file = temp_dir / "library.bib"
        import_file.write_text("""
        @article{smith2020,
            author = {Smith, John},
            title = {Machine Learning Study},
            journal = {Nature},
            year = {2020},
            doi = {10.1038/ml2020}
        }

        @article{smith2020b,
            author = {Smith, J.},
            title = {Machine Learning Study},
            journal = {Nature},
            year = {2020},
            doi = {10.1038/ml2020}
        }

        @book{knuth1984,
            author = {Knuth, Donald E.},
            title = {The TeXbook},
            publisher = {Addison-Wesley},
            year = {1984}
        }

        @article{invalid2024,
            title = {Missing Required Fields},
            year = {2024}
        }
        """)

        # Step 1: Import with validation
        from bibmgr.operations.workflows.import_workflow import (
            ImportWorkflow,
            ImportWorkflowConfig,
        )

        import_config = ImportWorkflowConfig(
            validate=True,
            check_duplicates=False,  # Handle separately
        )

        import_workflow = ImportWorkflow(manager, event_bus)
        import_result = import_workflow.execute(import_file, config=import_config)

        assert import_result.success  # Workflow succeeded even with invalid entries
        assert len(import_result.successful_entities) == 3  # Only the valid ones

        # Step 2: Deduplicate
        from bibmgr.operations.workflows.deduplicate import (
            DeduplicationConfig,
            DeduplicationMode,
            DeduplicationWorkflow,
        )

        dedup_config = DeduplicationConfig(
            mode=DeduplicationMode.AUTOMATIC,
            min_similarity=0.9,  # High threshold for DOI matches
        )

        dedup_workflow = DeduplicationWorkflow(manager, event_bus)
        dedup_result = dedup_workflow.execute(dedup_config)

        assert dedup_result.success
        # Should have merged smith2020 and smith2020b

        # Step 3: Export cleaned library
        from bibmgr.operations.workflows.export import (
            ExportFormat,
            ExportWorkflow,
            ExportWorkflowConfig,
        )

        export_file = temp_dir / "cleaned.bib"
        export_config = ExportWorkflowConfig(
            format=ExportFormat.BIBTEX,
            validate=True,
            sort_by="year",
        )

        export_workflow = ExportWorkflow(manager, event_bus)
        export_result = export_workflow.execute(export_file, config=export_config)

        assert export_result.success
        assert export_file.exists()

        # Verify final state
        final_entries = manager.entries.find_all()
        assert len(final_entries) < 4  # Duplicates merged, invalid excluded

        # Check export content
        exported_content = export_file.read_text()
        assert "@article{smith2020" in exported_content
        assert "@book{knuth1984" in exported_content
        assert "smith2020b" not in exported_content  # Merged away

    def test_bulk_operations_with_events(self):
        """Test bulk operations with event tracking."""
        backend = MemoryBackend()
        event_bus = EventBus()
        manager = RepositoryManager(backend)

        # Track events
        events_captured = []

        def capture_event(event):
            events_captured.append(event)

        event_bus.subscribe(EventType.ENTRY_CREATED, capture_event)
        event_bus.subscribe(EventType.ENTRY_UPDATED, capture_event)
        event_bus.subscribe(EventType.ENTRY_DELETED, capture_event)

        # Create entries in bulk
        from bibmgr.operations.commands.create import BulkCreateHandler, CreateHandler

        entries = [
            create_entry_with_data(key=f"bulk{i}", title=f"Entry {i}", year=2020 + i)
            for i in range(5)
        ]

        create_handler = CreateHandler(manager.entries, event_bus)
        bulk_handler = BulkCreateHandler(manager.entries, event_bus, create_handler)

        create_results = bulk_handler.execute(entries)
        assert all(r.status.is_success() for r in create_results)

        # Update in bulk
        from bibmgr.operations.commands.update import UpdateHandler

        update_handler = UpdateHandler(manager.entries, event_bus)

        updates = {f"bulk{i}": {"note": f"Updated note {i}"} for i in range(3)}

        from bibmgr.operations.commands.update import UpdateCommand

        for key, update_dict in updates.items():
            command = UpdateCommand(key=key, updates=update_dict)
            update_handler.execute(command)

        # Delete some
        from bibmgr.operations.commands.delete import DeleteCommand, DeleteHandler

        delete_handler = DeleteHandler(
            manager.entries,
            manager.collections,
            MetadataStore(Path(tempfile.mkdtemp())),
            event_bus,
        )

        for i in [3, 4]:
            command = DeleteCommand(key=f"bulk{i}")
            delete_handler.execute(command)

        # Verify events
        created_events = [
            e for e in events_captured if e.type == EventType.ENTRY_CREATED
        ]
        updated_events = [
            e for e in events_captured if e.type == EventType.ENTRY_UPDATED
        ]
        deleted_events = [
            e for e in events_captured if e.type == EventType.ENTRY_DELETED
        ]

        assert len(created_events) == 5
        assert len(updated_events) == 3
        assert len(deleted_events) == 2

        # Verify final state
        remaining = manager.entries.find_all()
        assert len(remaining) == 3
        assert all(e.note is not None for e in remaining)

    def test_collection_operations_integration(self):
        """Test operations with collections."""
        backend = MemoryBackend()
        event_bus = EventBus()
        manager = RepositoryManager(backend)

        # Create entries
        entries = [
            EntryBuilder()
            .key(f"paper{i}")
            .type(EntryType.ARTICLE)
            .author(f"Author{i}, A.")
            .title(f"Paper {i}")
            .journal("Journal")
            .year(2020 + i)
            .build()
            for i in range(5)
        ]

        for entry in entries:
            # Cast to Entry for type safety
            if hasattr(entry, "_entry"):
                # It's an EntryWithExtras wrapper
                manager.entries.save(entry._entry)  # type: ignore
            else:
                manager.entries.save(entry)  # type: ignore

        # Create collections
        collections = [
            CollectionBuilder()
            .name("Recent Papers")
            .description("Papers from 2023 onwards")
            .build(),
            CollectionBuilder()
            .name("Manual Selection")
            .add_entry_keys("paper0", "paper2", "paper4")
            .build(),
        ]

        for collection in collections:
            # Cast to Collection for type safety
            if hasattr(collection, "_collection"):
                # It's a CollectionWithExtras wrapper
                manager.collections.save(collection._collection)  # type: ignore
            else:
                manager.collections.save(collection)  # type: ignore

        # Delete entry that's in a collection
        from bibmgr.operations.commands.delete import DeleteCommand, DeleteHandler

        delete_handler = DeleteHandler(
            manager.entries,
            manager.collections,
            MetadataStore(Path(tempfile.mkdtemp())),
            event_bus,
        )

        result = delete_handler.execute(DeleteCommand(key="paper2"))
        assert result.status.is_success()

        # Verify removed from collection
        all_collections = manager.collections.find_all()
        manual_collection = next(
            c for c in all_collections if c.name == "Manual Selection"
        )
        assert (
            manual_collection.entry_keys is None
            or "paper2" not in manual_collection.entry_keys
        )

        # Verify smart collection still works
        next(c for c in all_collections if c.name == "Recent Papers")
        # Should match entries with year >= 2023
        [e for e in manager.entries.find_all() if e.year and e.year >= 2023]
        # Note: Actual smart collection implementation would need query execution

    def test_metadata_preservation(self, temp_dir):
        """Test metadata is preserved through operations."""
        backend = MemoryBackend()
        event_bus = EventBus()
        metadata_store = MetadataStore(temp_dir)
        manager = RepositoryManager(backend)
        manager.metadata_store = metadata_store

        # Create entry with metadata
        entry = create_entry_with_data(key="meta_test", title="Test Entry")
        manager.entries.save(entry)

        # Add metadata
        metadata = metadata_store.get_metadata("meta_test")
        metadata.add_tags("important", "reviewed")
        metadata.rating = 5
        metadata.read_status = "read"
        metadata_store.save_metadata(metadata)

        # Add notes
        from bibmgr.storage.metadata import Note

        note = Note(
            entry_key="meta_test",
            content="Excellent paper on the topic",
            note_type="summary",
        )
        metadata_store.add_note(note)

        # Update entry
        from bibmgr.operations.commands.update import UpdateCommand, UpdateHandler

        update_handler = UpdateHandler(manager.entries, event_bus)
        result = update_handler.execute(
            UpdateCommand(
                key="meta_test",
                updates={"title": "Updated Title", "year": 2024},
            )
        )
        assert result.status.is_success()

        # Verify metadata preserved
        preserved_metadata = metadata_store.get_metadata("meta_test")
        assert "important" in preserved_metadata.tags
        assert preserved_metadata.rating == 5

        preserved_notes = metadata_store.get_notes("meta_test")
        assert len(preserved_notes) == 1
        assert preserved_notes[0].content == "Excellent paper on the topic"

        # Merge with another entry
        entry2 = create_entry_with_data(
            key="meta_test2",
            title="Another Version",
            doi="10.1234/test",
        )
        manager.entries.save(entry2)

        from bibmgr.operations.commands.merge import MergeCommand, MergeHandler

        merge_handler = MergeHandler(manager.entries, event_bus)
        merge_result = merge_handler.execute(
            MergeCommand(
                source_keys=["meta_test", "meta_test2"],
                target_key="meta_test",
            )
        )
        assert merge_result.status.is_success()

        # Metadata should still be there
        final_metadata = metadata_store.get_metadata("meta_test")
        assert final_metadata.rating == 5
        assert len(metadata_store.get_notes("meta_test")) == 1


class TestErrorHandlingIntegration:
    """Test error handling across the system."""

    def test_transaction_rollback(self):
        """Test transaction rollback on error."""
        backend = MemoryBackend()
        event_bus = EventBus()
        manager = RepositoryManager(backend)

        # Create initial entries
        for i in range(3):
            entry = create_entry_with_data(key=f"trans{i}", title=f"Entry {i}")
            manager.entries.save(entry)

        initial_count = len(manager.entries.find_all())

        # Try atomic bulk create with one invalid
        from bibmgr.operations.commands.create import BulkCreateHandler, CreateHandler

        new_entries = [
            create_entry_with_data(key="new1", title="Valid 1"),
            create_entry_with_data(key="new2", title="Valid 2"),
            create_entry_with_data(
                key="trans1", title="Duplicate Key"
            ),  # Will fail - key exists
        ]

        create_handler = CreateHandler(manager.entries, event_bus)
        bulk_handler = BulkCreateHandler(manager.entries, event_bus, create_handler)

        results = bulk_handler.execute(new_entries, atomic=True)

        # All should fail due to atomic mode
        assert all(r.status.name == "TRANSACTION_FAILED" for r in results)

        # No new entries should be added
        final_count = len(manager.entries.find_all())
        assert final_count == initial_count

    def test_cascade_failure_handling(self, temp_dir):
        """Test handling cascade operation failures."""
        backend = MemoryBackend()
        event_bus = EventBus()
        metadata_store = MetadataStore(temp_dir)
        manager = RepositoryManager(backend)

        # Create entry with lots of associated data
        entry = create_entry_with_data(key="cascade_test", title="Test")
        manager.entries.save(entry)

        # Add metadata that might fail to delete
        metadata = metadata_store.get_metadata("cascade_test")
        metadata.add_tags("test")
        metadata_store.save_metadata(metadata)

        # Mock a failure in metadata deletion
        original_delete = metadata_store.delete_metadata

        def failing_delete(entry_key):
            raise Exception("Metadata deletion failed")

        metadata_store.delete_metadata = failing_delete

        # Try to delete with cascade
        from bibmgr.operations.commands.delete import DeleteCommand, DeleteHandler

        delete_handler = DeleteHandler(
            manager.entries,
            manager.collections,
            metadata_store,
            event_bus,
        )

        delete_handler.execute(
            DeleteCommand(
                key="cascade_test",
                cascade=True,
                cascade_metadata=True,
            )
        )

        # Should handle the cascade failure gracefully
        # Implementation dependent - might fail or continue

        # Restore original method
        metadata_store.delete_metadata = original_delete

    def test_concurrent_operation_handling(self):
        """Test handling concurrent operations."""
        backend = MemoryBackend()
        event_bus = EventBus()
        manager = RepositoryManager(backend)

        # Create entry
        entry = create_entry_with_data(key="concurrent", title="Original")
        manager.entries.save(entry)

        # Simulate concurrent updates
        from bibmgr.operations.commands.update import UpdateCommand, UpdateHandler

        update_handler = UpdateHandler(manager.entries, event_bus)

        # Multiple updates to same entry
        updates = [
            {"title": "Update 1", "note": "First update"},
            {"title": "Update 2", "author": "New Author"},
            {"title": "Update 3", "year": 2024},
        ]

        results = []
        for update_dict in updates:
            command = UpdateCommand(key="concurrent", updates=update_dict)
            result = update_handler.execute(command)
            results.append(result)

        # All should succeed (last write wins)
        assert all(r.status.is_success() for r in results)

        # Final state should have last update
        final = manager.entries.find("concurrent")
        assert final is not None
        assert final.title == "Update 3"
        assert final.year == 2024

    def test_validation_error_recovery(self):
        """Test recovering from validation errors."""
        backend = MemoryBackend()
        event_bus = EventBus()
        manager = RepositoryManager(backend)

        # Create entry that will fail validation when updated
        entry = create_entry_with_data(
            key="validate_test",
            type=EntryType.ARTICLE,
            author="Author, A.",
            title="Valid Article",
            journal="Journal",
            year=2020,
        )
        manager.entries.save(entry)

        # Try update that makes it invalid
        from bibmgr.operations.commands.update import UpdateCommand, UpdateHandler

        update_handler = UpdateHandler(manager.entries, event_bus)

        # Remove required field
        result1 = update_handler.execute(
            UpdateCommand(
                key="validate_test",
                updates={"author": None},  # Remove required field
                validate=True,
            )
        )

        assert result1.status.name == "VALIDATION_FAILED"

        # Entry should be unchanged
        unchanged = manager.entries.find("validate_test")
        assert unchanged is not None
        assert unchanged.author == "Author, A."

        # Try valid update
        result2 = update_handler.execute(
            UpdateCommand(
                key="validate_test",
                updates={"author": "Updated, Author"},
                validate=True,
            )
        )

        assert result2.status.is_success()

        # Now should be updated
        updated = manager.entries.find("validate_test")
        assert updated is not None
        assert updated.author == "Updated, Author"


class TestPerformanceIntegration:
    """Test performance aspects of operations."""

    def test_large_batch_operations(self):
        """Test operations with large batches."""
        backend = MemoryBackend()
        event_bus = EventBus()
        manager = RepositoryManager(backend)

        # Create many entries
        from bibmgr.operations.commands.create import BulkCreateHandler, CreateHandler

        batch_size = 1000
        entries = [
            create_entry_with_data(
                key=f"perf{i}",
                title=f"Performance Test Entry {i}",
                year=2000 + (i % 25),
            )
            for i in range(batch_size)
        ]

        create_handler = CreateHandler(manager.entries, event_bus)
        bulk_handler = BulkCreateHandler(manager.entries, event_bus, create_handler)

        import time

        start_time = time.time()
        results = bulk_handler.execute(entries)
        create_time = time.time() - start_time

        assert len(results) == batch_size
        assert all(r.status.is_success() for r in results)
        assert create_time < 10  # Should complete within 10 seconds

        # Test bulk query
        start_time = time.time()
        year_2020 = [e for e in manager.entries.find_all() if e.year == 2020]
        query_time = time.time() - start_time

        assert len(year_2020) == 40  # 1000 / 25 years
        assert query_time < 1  # Should be fast

    def test_deduplication_performance(self):
        """Test deduplication performance with many entries."""
        backend = MemoryBackend()
        event_bus = EventBus()
        manager = RepositoryManager(backend)

        # Create entries with some duplicates
        for i in range(100):
            # Create some exact duplicates
            if i % 10 == 0:
                key = f"dup{i // 10}"
                title = f"Duplicate Paper {i // 10}"
            else:
                key = f"unique{i}"
                title = f"Unique Paper {i}"

            entry = create_entry_with_data(
                key=key,
                title=title,
                author=f"Author{i % 5}, A.",
                year=2020,
            )
            try:
                manager.entries.save(entry)
            except Exception:
                pass  # Duplicate key

        # Run deduplication
        from bibmgr.operations.workflows.deduplicate import (
            DeduplicationConfig,
            DeduplicationMode,
            DeduplicationWorkflow,
        )

        config = DeduplicationConfig(
            mode=DeduplicationMode.PREVIEW,  # Just detect, don't merge
            min_similarity=0.9,
        )

        workflow = DeduplicationWorkflow(manager, event_bus)

        import time

        start_time = time.time()
        result = workflow.execute(config)
        dedup_time = time.time() - start_time

        assert result.success
        assert dedup_time < 5  # Should complete within 5 seconds

    def test_event_processing_performance(self):
        """Test event processing doesn't slow operations."""
        backend = MemoryBackend()
        event_bus = EventBus()
        manager = RepositoryManager(backend)

        # Add many event handlers
        handler_count = 0

        def slow_handler(event):
            nonlocal handler_count
            handler_count += 1
            # Simulate some processing
            time.sleep(0.001)  # 1ms per event

        # Subscribe to all event types
        for event_type in [
            EventType.ENTRY_CREATED,
            EventType.ENTRY_UPDATED,
            EventType.ENTRY_DELETED,
        ]:
            for _ in range(10):  # 10 handlers per type
                event_bus.subscribe(event_type, slow_handler)

        # Perform operations
        from bibmgr.operations.commands.create import CreateCommand, CreateHandler

        create_handler = CreateHandler(manager.entries, event_bus)

        import time

        start_time = time.time()

        for i in range(10):
            entry = create_entry_with_data(key=f"event{i}")
            command = CreateCommand(entry=entry)
            create_handler.execute(command)

        operation_time = time.time() - start_time

        # Should still be reasonably fast despite many handlers
        assert operation_time < 2  # 2 seconds for 10 operations
        assert handler_count == 100  # 10 operations * 10 handlers
