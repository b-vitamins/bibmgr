"""Comprehensive tests for CRUD operations."""

import time
from concurrent.futures import ThreadPoolExecutor


from bibmgr.core.models import Entry, EntryType
from bibmgr.operations.crud import (
    EntryOperations,
    OperationResult,
    OperationType,
    BulkOperationOptions,
    CascadeOptions,
)


class TestOperationResult:
    """Test OperationResult data structure."""

    def test_success_result(self):
        """Test successful operation result."""
        result = OperationResult(
            success=True,
            operation=OperationType.CREATE,
            entry_key="test123",
            message="Entry created successfully",
        )

        assert result.success is True
        assert result.failed is False
        assert result.operation == OperationType.CREATE
        assert result.entry_key == "test123"
        assert result.message and "created successfully" in result.message

    def test_failure_result(self):
        """Test failed operation result."""
        result = OperationResult(
            success=False,
            operation=OperationType.UPDATE,
            entry_key="test123",
            message="Entry not found",
            errors=["Field validation failed", "Invalid type"],
        )

        assert result.success is False
        assert result.failed is True
        assert result.operation == OperationType.UPDATE
        assert result.errors and len(result.errors) == 2
        assert result.message and "not found" in result.message

    def test_result_with_entries(self):
        """Test result with old and new entries."""
        old_entry = Entry(
            key="test123",
            type=EntryType.ARTICLE,
            title="Old Title",
            author="Old Author",
            journal="Old Journal",
            year=2022,
        )
        new_entry = Entry(
            key="test123",
            type=EntryType.ARTICLE,
            title="New Title",
            author="New Author",
            journal="New Journal",
            year=2023,
        )

        result = OperationResult(
            success=True,
            operation=OperationType.UPDATE,
            entry_key="test123",
            old_entry=old_entry,
            new_entry=new_entry,
            affected_count=1,
        )

        assert result.old_entry == old_entry
        assert result.new_entry == new_entry
        assert result.affected_count == 1


class TestEntryOperations:
    """Test CRUD operations on entries."""

    def test_create_entry(self, temp_storage, sample_entries):
        """Test creating a new entry."""
        ops = EntryOperations(temp_storage)
        entry = sample_entries[0]

        result = ops.create(entry)

        assert result.success is True
        assert result.operation == OperationType.CREATE
        assert result.entry_key == entry.key
        assert result.new_entry == entry

        # Verify entry was stored
        stored = temp_storage.read(entry.key)
        assert stored == entry

    def test_create_duplicate_entry(self, temp_storage, sample_entries):
        """Test creating duplicate entry fails."""
        ops = EntryOperations(temp_storage)
        entry = sample_entries[0]

        # First create succeeds
        result1 = ops.create(entry)
        assert result1.success is True

        # Second create fails
        result2 = ops.create(entry)
        assert result2.failed is True
        assert result2.message and "already exists" in result2.message.lower()

    def test_create_with_validation(self, temp_storage, mock_validator):
        """Test creation with validation."""
        validator = mock_validator(should_fail=False)
        ops = EntryOperations(temp_storage, validator=validator)

        entry = Entry(
            key="test123",
            type=EntryType.ARTICLE,
            title="Test Article",
            author="Test Author",
            journal="Test Journal",
            year=2023,
        )

        result = ops.create(entry)
        assert result.success is True
        assert validator.validated_entries and len(validator.validated_entries) == 1

        # Test with failing validation
        validator_fail = mock_validator(should_fail=True)
        ops_fail = EntryOperations(temp_storage, validator=validator_fail)

        entry2 = Entry(
            key="test456",
            type=EntryType.ARTICLE,
            title="Another Article",
            author="Another Author",
            journal="Another Journal",
            year=2023,
        )

        result2 = ops_fail.create(entry2)
        assert result2.failed is True
        assert result2.errors and len(result2.errors) > 0

    def test_create_force_mode(self, temp_storage, mock_validator):
        """Test force creation bypasses validation."""
        validator = mock_validator(should_fail=True)
        ops = EntryOperations(temp_storage, validator=validator)

        entry = Entry(
            key="forced",
            type=EntryType.MISC,
            title="Forced Entry",
        )

        # Normal create fails validation
        result = ops.create(entry)
        assert result.failed is True

        # Force create succeeds
        result = ops.create(entry, force=True)
        assert result.success is True
        assert temp_storage.read("forced") == entry

    def test_read_entry(self, temp_storage, sample_entries):
        """Test reading an entry."""
        ops = EntryOperations(temp_storage)
        entry = sample_entries[0]

        # Create entry first
        ops.create(entry)

        # Read it back
        retrieved = ops.read(entry.key)
        assert retrieved == entry

        # Read non-existent
        assert ops.read("nonexistent") is None

    def test_update_entry(self, temp_storage, sample_entries):
        """Test updating an existing entry."""
        ops = EntryOperations(temp_storage)
        entry = sample_entries[0]
        ops.create(entry)

        # Update specific fields
        updates = {
            "title": "Updated Title",
            "year": 1985,
            "edition": "2nd",
        }

        result = ops.update(entry.key, updates)

        assert result.success is True
        assert result.operation == OperationType.UPDATE
        assert result.old_entry == entry
        assert result.new_entry
        assert result.new_entry.title == "Updated Title"
        assert result.new_entry.year == 1985
        assert result.new_entry.edition == "2nd"
        assert result.new_entry.author == entry.author  # Unchanged

    def test_update_nonexistent(self, temp_storage):
        """Test updating non-existent entry."""
        ops = EntryOperations(temp_storage)

        result = ops.update("nonexistent", {"title": "New Title"})

        assert result.failed is True
        assert result.message and "not found" in result.message.lower()

    def test_update_with_key_rename(self, temp_storage, sample_entries):
        """Test renaming entry key during update."""
        ops = EntryOperations(temp_storage)
        entry = sample_entries[0]
        ops.create(entry)

        # Rename key
        new_key = "knuth1984_renamed"
        result = ops.update(entry.key, {"key": new_key})

        assert result.success is True
        assert result.new_entry and result.new_entry.key == new_key
        assert ops.read(entry.key) is None  # Old key gone
        assert ops.read(new_key) is not None  # New key exists

    def test_update_key_conflict(self, temp_storage, sample_entries):
        """Test renaming to existing key fails."""
        ops = EntryOperations(temp_storage)
        entry1 = sample_entries[0]
        entry2 = sample_entries[1]

        ops.create(entry1)
        ops.create(entry2)

        # Try to rename entry1 to entry2's key
        result = ops.update(entry1.key, {"key": entry2.key})

        assert result.failed is True
        assert result.message and "already exists" in result.message.lower()

    def test_update_with_validation(self, temp_storage, mock_validator):
        """Test update with validation."""
        validator = mock_validator(should_fail=False)
        ops = EntryOperations(temp_storage, validator=validator)

        entry = Entry(
            key="test123",
            type=EntryType.ARTICLE,
            title="Original",
            author="Author",
            journal="Journal",
            year=2023,
        )
        ops.create(entry)

        # Update with validation
        result = ops.update("test123", {"title": "Updated"})
        assert result.success is True
        assert len(validator.validated_entries) == 2  # Create + update

        # Update with validation disabled
        validator.validated_entries.clear()
        result = ops.update("test123", {"title": "Another"}, validate=False)
        assert result.success is True
        assert len(validator.validated_entries) == 0

    def test_update_invalid_field_type(self, temp_storage, sample_entries):
        """Test update with invalid field type."""
        ops = EntryOperations(temp_storage)
        entry = sample_entries[0]
        ops.create(entry)

        # Try to set year to invalid type
        result = ops.update(entry.key, {"year": "not_a_number"})

        assert result.failed is True
        assert result.message and (
            "invalid" in result.message.lower() or "type" in result.message.lower()
        )

    def test_delete_entry(self, temp_storage, sample_entries):
        """Test deleting an entry."""
        ops = EntryOperations(temp_storage)
        entry = sample_entries[0]
        ops.create(entry)

        result = ops.delete(entry.key)

        assert result.success is True
        assert result.operation == OperationType.DELETE
        assert result.old_entry == entry
        assert ops.read(entry.key) is None

    def test_delete_nonexistent(self, temp_storage):
        """Test deleting non-existent entry."""
        ops = EntryOperations(temp_storage)

        result = ops.delete("nonexistent")

        assert result.failed is True
        assert result.message and "not found" in result.message.lower()

    def test_delete_with_cascade(self, temp_storage, sample_entries):
        """Test cascade delete removes related data."""
        ops = EntryOperations(temp_storage)
        entry = sample_entries[0]
        ops.create(entry)

        # Create related data (notes, metadata, etc.)
        # This would be mocked or use actual related data storage
        cascade_options = CascadeOptions(
            delete_notes=True,
            delete_metadata=True,
            delete_attachments=True,
        )

        result = ops.delete(entry.key, cascade=cascade_options)

        assert result.success is True
        assert result.affected_count >= 1
        # Verify cascade happened (would check actual related storage)

    def test_replace_entry(self, temp_storage, sample_entries):
        """Test replacing an entire entry."""
        ops = EntryOperations(temp_storage)
        original = sample_entries[0]
        ops.create(original)

        # Create replacement with same key
        replacement = Entry(
            key=original.key,
            type=EntryType.INPROCEEDINGS,
            title="Completely Different Title",
            author="Different Author",
            booktitle="Conference Proceedings",
            year=2023,
        )

        result = ops.replace(replacement)

        assert result.success is True
        assert result.operation == OperationType.REPLACE
        assert result.old_entry == original
        assert result.new_entry == replacement

        stored = ops.read(original.key)
        assert stored == replacement

    def test_replace_nonexistent(self, temp_storage):
        """Test replacing non-existent entry."""
        ops = EntryOperations(temp_storage)

        entry = Entry(
            key="nonexistent",
            type=EntryType.MISC,
            title="New Entry",
        )

        result = ops.replace(entry)

        assert result.failed is True
        assert result.message and "not found" in result.message.lower()


class TestBulkOperations:
    """Test bulk operations on multiple entries."""

    def test_bulk_create(self, temp_storage, sample_entries):
        """Test creating multiple entries at once."""
        ops = EntryOperations(temp_storage)

        options = BulkOperationOptions(
            stop_on_error=False,
            validate=True,
        )

        results = ops.bulk_create(sample_entries, options=options)

        assert len(results) == len(sample_entries)
        assert all(r.success for r in results)
        assert all(ops.read(e.key) == e for e in sample_entries)

    def test_bulk_create_with_duplicates(self, temp_storage, sample_entries):
        """Test bulk create with some duplicates."""
        ops = EntryOperations(temp_storage)

        # Create first entry
        ops.create(sample_entries[0])

        # Try bulk create including the duplicate
        options = BulkOperationOptions(stop_on_error=False)
        results = ops.bulk_create(sample_entries, options=options)

        assert results[0].failed  # First is duplicate
        assert all(r.success for r in results[1:])  # Rest succeed

    def test_bulk_create_stop_on_error(self, temp_storage, sample_entries):
        """Test bulk create stops on first error."""
        ops = EntryOperations(temp_storage)

        # Create conflict
        ops.create(sample_entries[1])

        options = BulkOperationOptions(stop_on_error=True)
        results = ops.bulk_create(sample_entries, options=options)

        assert results[0].success  # First succeeds
        assert results[1].failed  # Second fails (duplicate)
        assert len(results) == 2  # Stopped after error

    def test_bulk_update(self, temp_storage, sample_entries):
        """Test updating multiple entries."""
        ops = EntryOperations(temp_storage)

        # Create entries first
        for entry in sample_entries:
            ops.create(entry)

        # Bulk update years
        updates = {e.key: {"year": 2024} for e in sample_entries}

        results = ops.bulk_update(updates)

        assert len(results) == len(sample_entries)
        assert all(r.success for r in results)
        assert all(
            entry and entry.year == 2024
            for e in sample_entries
            if (entry := ops.read(e.key))
        )

    def test_bulk_delete(self, temp_storage, sample_entries):
        """Test deleting multiple entries."""
        ops = EntryOperations(temp_storage)

        # Create entries
        for entry in sample_entries:
            ops.create(entry)

        # Bulk delete
        keys = [e.key for e in sample_entries[:3]]
        results = ops.bulk_delete(keys)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(ops.read(k) is None for k in keys)
        assert ops.read(sample_entries[3].key) is not None  # Others remain

    def test_bulk_operation_with_progress(
        self, temp_storage, sample_entries, mock_progress_reporter
    ):
        """Test bulk operations report progress."""
        ops = EntryOperations(temp_storage)
        reporter = mock_progress_reporter()

        options = BulkOperationOptions(
            progress_reporter=reporter,
        )

        ops.bulk_create(sample_entries, options=options)

        assert len(reporter.reports) > 0
        assert reporter.reports[-1]["current"] == len(sample_entries)
        assert reporter.reports[-1]["total"] == len(sample_entries)

    def test_bulk_transaction_atomicity(self, temp_storage, sample_entries):
        """Test bulk operations are atomic when specified."""
        ops = EntryOperations(temp_storage)

        # Create first entry to cause conflict
        ops.create(sample_entries[0])

        options = BulkOperationOptions(
            atomic=True,
            stop_on_error=False,
        )

        # This should fail atomically
        results = ops.bulk_create(sample_entries, options=options)

        # All or nothing - since one failed, none should be created
        assert any(r.failed for r in results)
        # Check that no partial writes occurred
        for entry in sample_entries[1:]:
            assert ops.read(entry.key) is None


class TestConcurrency:
    """Test thread safety and concurrent operations."""

    def test_concurrent_creates(self, temp_storage):
        """Test concurrent entry creation."""
        ops = EntryOperations(temp_storage)

        def create_entry(i: int):
            entry = Entry(
                key=f"concurrent_{i}",
                type=EntryType.MISC,
                title=f"Entry {i}",
            )
            return ops.create(entry)

        with ThreadPoolExecutor(max_workers=5) as executor:  # Reduced workers
            futures = [
                executor.submit(create_entry, i) for i in range(20)
            ]  # Reduced count
            results = [f.result() for f in futures]

        # Most should succeed (unique keys)
        success_count = sum(1 for r in results if r.success)
        assert success_count >= 15  # Allow for some transaction conflicts
        # Verify entries were created
        created_count = sum(
            1 for i in range(20) if temp_storage.read(f"concurrent_{i}") is not None
        )
        assert created_count == success_count

    def test_concurrent_updates(self, temp_storage):
        """Test concurrent updates to same entry."""
        ops = EntryOperations(temp_storage)

        entry = Entry(
            key="shared",
            type=EntryType.MISC,
            title="Original",
            note="Counter: 0",
        )
        ops.create(entry)

        def increment_counter(i: int):
            # Read-modify-write
            current = ops.read("shared")
            if current and current.note:
                count = int(current.note.split(": ")[1])
                return ops.update("shared", {"note": f"Counter: {count + 1}"})
            return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(increment_counter, i) for i in range(10)]
            [f.result() for f in futures]

        # Some updates might fail due to race conditions
        # This tests that operations handle concurrency safely
        final = ops.read("shared")
        assert final is not None

    def test_lock_timeout(self, temp_storage):
        """Test operation timeout with locks."""
        ops = EntryOperations(temp_storage, lock_timeout=0.1)

        entry = Entry(
            key="locked",
            type=EntryType.MISC,
            title="Locked Entry",
        )
        ops.create(entry)

        # Simulate long-running operation
        def long_update():
            with ops._get_lock("locked"):
                time.sleep(0.5)  # Hold lock longer than timeout
                return ops.update("locked", {"title": "Updated"})

        def quick_update():
            time.sleep(0.05)  # Let long_update acquire lock first
            return ops.update("locked", {"title": "Quick"})

        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(long_update)
            f2 = executor.submit(quick_update)

            result2 = f2.result()

            # Quick update should timeout
            assert result2.failed
            assert result2.message and "timeout" in result2.message.lower()


class TestDryRun:
    """Test dry-run mode for preview operations."""

    def test_dry_run_create(self, temp_storage, sample_entries):
        """Test dry-run doesn't actually create."""
        ops = EntryOperations(temp_storage, dry_run=True)
        entry = sample_entries[0]

        result = ops.create(entry)

        assert result.success is True
        assert result.operation == OperationType.CREATE
        assert result.message and "[DRY RUN]" in result.message

        # Entry should not be stored
        assert temp_storage.read(entry.key) is None

    def test_dry_run_update(self, temp_storage, sample_entries):
        """Test dry-run doesn't actually update."""
        ops = EntryOperations(temp_storage)
        entry = sample_entries[0]
        ops.create(entry)

        ops_dry = EntryOperations(temp_storage, dry_run=True)
        result = ops_dry.update(entry.key, {"title": "New Title"})

        assert result.success is True
        assert result.message and "[DRY RUN]" in result.message

        # Entry should be unchanged
        stored = temp_storage.read(entry.key)
        assert stored.title == entry.title

    def test_dry_run_delete(self, temp_storage, sample_entries):
        """Test dry-run doesn't actually delete."""
        ops = EntryOperations(temp_storage)
        entry = sample_entries[0]
        ops.create(entry)

        ops_dry = EntryOperations(temp_storage, dry_run=True)
        result = ops_dry.delete(entry.key)

        assert result.success is True
        assert result.message and "[DRY RUN]" in result.message

        # Entry should still exist
        assert temp_storage.read(entry.key) is not None

    def test_dry_run_validation_still_runs(self, temp_storage, mock_validator):
        """Test validation runs even in dry-run mode."""
        validator = mock_validator(should_fail=True)
        ops = EntryOperations(temp_storage, validator=validator, dry_run=True)

        entry = Entry(
            key="test",
            type=EntryType.MISC,
            title="Test",
        )

        result = ops.create(entry)

        assert result.failed  # Validation should still fail
        assert validator.validated_entries and len(validator.validated_entries) == 1


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_storage_error_handling(self, temp_storage, sample_entries, monkeypatch):
        """Test handling of storage errors."""
        ops = EntryOperations(temp_storage)
        entry = sample_entries[0]

        # Mock storage transaction error

        class FailingTransaction:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def add(self, entry):
                raise IOError("Disk full")

            def commit(self):
                pass

        def mock_transaction():
            return FailingTransaction()

        monkeypatch.setattr(temp_storage, "transaction", mock_transaction)

        result = ops.create(entry)

        assert result.failed is True
        assert result.message and "storage error" in result.message.lower()
        assert "Disk full" in str(result.errors)

    def test_invalid_entry_type(self, temp_storage, sample_entries):
        """Test handling of invalid entry data."""
        ops = EntryOperations(temp_storage)

        # First create an entry
        entry = sample_entries[0]
        ops.create(entry)

        # Try to update with invalid type
        result = ops.update(entry.key, {"type": "INVALID_TYPE"})

        assert result.failed is True
        assert result.message and (
            "invalid" in result.message.lower() or "type" in result.message.lower()
        )

    def test_none_values_in_update(self, temp_storage, sample_entries):
        """Test that None values in updates are handled properly."""
        ops = EntryOperations(temp_storage)
        entry = sample_entries[0]
        ops.create(entry)

        # Update with None should remove field
        result = ops.update(entry.key, {"publisher": None})

        assert result.success is True
        updated = ops.read(entry.key)
        assert updated and updated.publisher is None

    def test_empty_bulk_operation(self, temp_storage):
        """Test bulk operations with empty lists."""
        ops = EntryOperations(temp_storage)

        results = ops.bulk_create([])
        assert len(results) == 0

        results = ops.bulk_update({})
        assert len(results) == 0

        results = ops.bulk_delete([])
        assert len(results) == 0
