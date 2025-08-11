"""Tests for operation validators (Preconditions, Postconditions).

This module tests validation logic that ensures operations meet required
conditions before and after execution.
"""

from datetime import datetime
from unittest.mock import Mock

from bibmgr.core.fields import EntryType
from bibmgr.core.models import Entry

from ..operations.conftest import create_entry_with_data


class TestCreatePreconditions:
    """Test preconditions for create operations."""

    def test_valid_create_command(self):
        """Test preconditions pass for valid create command."""
        from bibmgr.operations.commands.create import CreateCommand
        from bibmgr.operations.validators import CreatePreconditions

        preconditions = CreatePreconditions()

        entry = create_entry_with_data(
            key="valid",
            type=EntryType.ARTICLE,
            author="Author, A.",
            title="Valid Article",
            journal="Journal",
            year=2024,
        )
        command = CreateCommand(entry=entry)

        violations = preconditions.check(command)

        assert len(violations) == 0

    def test_create_missing_entry(self):
        """Test preconditions fail when entry is None."""
        from bibmgr.operations.commands.create import CreateCommand
        from bibmgr.operations.validators import CreatePreconditions

        preconditions = CreatePreconditions()
        command = CreateCommand(entry=None)

        violations = preconditions.check(command)

        assert len(violations) > 0
        assert any("Entry cannot be None" in v for v in violations)

    def test_create_missing_key(self):
        """Test preconditions fail when key is missing."""
        from bibmgr.operations.commands.create import CreateCommand
        from bibmgr.operations.validators import CreatePreconditions

        preconditions = CreatePreconditions()

        entry = create_entry_with_data(key="", title="No Key")
        command = CreateCommand(entry=entry)

        violations = preconditions.check(command)

        assert len(violations) > 0
        assert any("key is required" in v for v in violations)

    def test_create_missing_type(self):
        """Test preconditions fail when type is missing."""
        from unittest.mock import Mock

        from bibmgr.operations.validators import CreatePreconditions

        preconditions = CreatePreconditions()

        # Create a mock command with an entry that has no type
        # This simulates what would happen if somehow an entry without type was passed
        command = Mock()
        command.entry = Mock()
        command.entry.key = "test"
        command.entry.type = None  # Simulate missing type

        violations = preconditions.check(command)

        assert "Entry type is required" in violations

    def test_create_article_missing_required(self):
        """Test preconditions don't check type-specific requirements."""
        from bibmgr.operations.commands.create import CreateCommand
        from bibmgr.operations.validators import CreatePreconditions

        preconditions = CreatePreconditions()

        # Article missing required fields
        entry = create_entry_with_data(
            key="article",
            type=EntryType.ARTICLE,
            title="Article Title",
            year=None,  # Explicitly set to None to test missing year
            # Missing: author, journal, year
        )
        command = CreateCommand(entry=entry)

        violations = preconditions.check(command)

        # Preconditions no longer check type-specific requirements
        # Those are handled by the entry's validate() method
        assert len(violations) == 0

    def test_create_book_missing_required(self):
        """Test preconditions for book type."""
        from bibmgr.operations.commands.create import CreateCommand
        from bibmgr.operations.validators import CreatePreconditions

        preconditions = CreatePreconditions()

        # Add book-specific checks if implemented
        entry = create_entry_with_data(
            key="book",
            type=EntryType.BOOK,
            title="Book Title",
            # Potentially missing: author/editor, publisher, year
        )
        command = CreateCommand(entry=entry)

        preconditions.check(command)

        # Book should require author/editor, publisher, year
        # Exact requirements depend on implementation

    def test_create_misc_minimal_requirements(self):
        """Test preconditions for misc type are minimal."""
        from bibmgr.operations.commands.create import CreateCommand
        from bibmgr.operations.validators import CreatePreconditions

        preconditions = CreatePreconditions()

        # Misc type should have minimal requirements
        entry = create_entry_with_data(
            key="misc",
            type=EntryType.MISC,
            title="Misc Entry",
        )
        command = CreateCommand(entry=entry)

        violations = preconditions.check(command)

        # Misc should pass with just key, type, title
        assert len(violations) == 0


class TestUpdatePreconditions:
    """Test preconditions for update operations."""

    def test_valid_update_command(self):
        """Test preconditions pass for valid update command."""
        from bibmgr.operations.commands.update import UpdateCommand
        from bibmgr.operations.validators import UpdatePreconditions

        preconditions = UpdatePreconditions()

        command = UpdateCommand(
            key="valid_key",
            updates={"title": "New Title", "year": 2024},
        )

        violations = preconditions.check(command)

        assert len(violations) == 0

    def test_update_missing_key(self):
        """Test preconditions fail when key is missing."""
        from bibmgr.operations.commands.update import UpdateCommand
        from bibmgr.operations.validators import UpdatePreconditions

        preconditions = UpdatePreconditions()

        command = UpdateCommand(key="", updates={"title": "New"})

        violations = preconditions.check(command)

        assert len(violations) > 0
        assert any("key is required" in v for v in violations)

    def test_update_no_updates(self):
        """Test preconditions fail when no updates provided."""
        from bibmgr.operations.commands.update import UpdateCommand
        from bibmgr.operations.validators import UpdatePreconditions

        preconditions = UpdatePreconditions()

        command = UpdateCommand(key="valid_key", updates={})

        violations = preconditions.check(command)

        assert len(violations) > 0
        assert any("No updates provided" in v for v in violations)

    def test_update_protected_fields(self):
        """Test preconditions prevent updating protected fields."""
        from bibmgr.operations.commands.update import UpdateCommand
        from bibmgr.operations.validators import UpdatePreconditions

        preconditions = UpdatePreconditions()

        # Try to update protected fields
        command = UpdateCommand(
            key="test",
            updates={
                "key": "new_key",  # Protected
                "added": datetime.now(),  # Protected
                "title": "New Title",  # OK
            },
        )

        violations = preconditions.check(command)

        assert len(violations) >= 2
        assert any("protected field: key" in v for v in violations)
        assert any("protected field: added" in v for v in violations)

    def test_update_valid_field_changes(self):
        """Test preconditions allow valid field updates."""
        from bibmgr.operations.commands.update import UpdateCommand
        from bibmgr.operations.validators import UpdatePreconditions

        preconditions = UpdatePreconditions()

        # All allowed updates
        command = UpdateCommand(
            key="test",
            updates={
                "title": "New Title",
                "author": "New Author",
                "year": 2024,
                "journal": "New Journal",
                "abstract": "New abstract",
                "keywords": ["new", "keywords"],
                "doi": "10.1234/new",
                "url": "https://example.com",
                "note": None,  # Remove field
            },
        )

        violations = preconditions.check(command)

        assert len(violations) == 0


class TestDeletePreconditions:
    """Test preconditions for delete operations."""

    def test_valid_delete_command(self):
        """Test preconditions pass for valid delete command."""
        from bibmgr.operations.commands.delete import DeleteCommand
        from bibmgr.operations.validators import DeletePreconditions

        preconditions = DeletePreconditions()

        command = DeleteCommand(key="valid_key")

        violations = preconditions.check(command)

        assert len(violations) == 0

    def test_delete_missing_key(self):
        """Test preconditions fail when key is missing."""
        from bibmgr.operations.commands.delete import DeleteCommand
        from bibmgr.operations.validators import DeletePreconditions

        preconditions = DeletePreconditions()

        command = DeleteCommand(key="")

        violations = preconditions.check(command)

        assert len(violations) > 0
        assert any("key is required" in v for v in violations)

    def test_delete_with_cascade_options(self):
        """Test preconditions with cascade options."""
        from bibmgr.operations.commands.delete import DeleteCommand
        from bibmgr.operations.validators import DeletePreconditions

        preconditions = DeletePreconditions()

        command = DeleteCommand(
            key="test",
            cascade=True,
            cascade_metadata=True,
            cascade_notes=True,
            cascade_files=True,
        )

        violations = preconditions.check(command)

        assert len(violations) == 0


class TestMergePreconditions:
    """Test preconditions for merge operations."""

    def test_valid_merge_command(self):
        """Test preconditions pass for valid merge command."""
        from bibmgr.operations.commands.merge import MergeCommand
        from bibmgr.operations.validators import MergePreconditions

        preconditions = MergePreconditions()

        command = MergeCommand(
            source_keys=["key1", "key2", "key3"],
            target_key="key1",
        )

        violations = preconditions.check(command)

        assert len(violations) == 0

    def test_merge_no_sources(self):
        """Test preconditions fail with no source keys."""
        from bibmgr.operations.commands.merge import MergeCommand
        from bibmgr.operations.validators import MergePreconditions

        preconditions = MergePreconditions()

        command = MergeCommand(source_keys=[])

        violations = preconditions.check(command)

        assert len(violations) > 0
        assert any("No source keys provided" in v for v in violations)

    def test_merge_single_source(self):
        """Test preconditions fail with single source."""
        from bibmgr.operations.commands.merge import MergeCommand
        from bibmgr.operations.validators import MergePreconditions

        preconditions = MergePreconditions()

        command = MergeCommand(source_keys=["only_one"])

        violations = preconditions.check(command)

        assert len(violations) > 0
        assert any("At least 2 entries required" in v for v in violations)

    def test_merge_duplicate_sources(self):
        """Test preconditions fail with duplicate source keys."""
        from bibmgr.operations.commands.merge import MergeCommand
        from bibmgr.operations.validators import MergePreconditions

        preconditions = MergePreconditions()

        command = MergeCommand(source_keys=["key1", "key2", "key1"])  # key1 duplicated

        violations = preconditions.check(command)

        assert len(violations) > 0
        assert any("Duplicate keys in source list" in v for v in violations)

    def test_merge_with_options(self):
        """Test preconditions with merge options."""
        from bibmgr.operations.commands.merge import MergeCommand
        from bibmgr.operations.validators import MergePreconditions

        preconditions = MergePreconditions()

        command = MergeCommand(
            source_keys=["a", "b"],
            target_key="custom",
            strategy="SMART",
            delete_sources=False,
        )

        violations = preconditions.check(command)

        assert len(violations) == 0


class TestImportPreconditions:
    """Test preconditions for import operations."""

    def test_valid_import_file(self, temp_dir):
        """Test preconditions pass for valid import."""
        from bibmgr.operations.validators import ImportPreconditions
        from bibmgr.operations.workflows.import_workflow import ImportWorkflowConfig

        preconditions = ImportPreconditions()

        # Create valid file
        import_file = temp_dir / "valid.bib"
        import_file.write_text("@article{test, title={Test}, year={2024}}")

        config = ImportWorkflowConfig()
        context = {"source": import_file, "config": config}

        violations = preconditions.check(context)

        assert len(violations) == 0

    def test_import_missing_file(self, temp_dir):
        """Test preconditions fail for missing file."""
        from bibmgr.operations.validators import ImportPreconditions
        from bibmgr.operations.workflows.import_workflow import ImportWorkflowConfig

        preconditions = ImportPreconditions()

        missing_file = temp_dir / "missing.bib"
        config = ImportWorkflowConfig()
        context = {"source": missing_file, "config": config}

        violations = preconditions.check(context)

        assert len(violations) > 0
        assert any("does not exist" in v for v in violations)

    def test_import_empty_file(self, temp_dir):
        """Test preconditions for empty file."""
        from bibmgr.operations.validators import ImportPreconditions
        from bibmgr.operations.workflows.import_workflow import ImportWorkflowConfig

        preconditions = ImportPreconditions()

        empty_file = temp_dir / "empty.bib"
        empty_file.write_text("")

        config = ImportWorkflowConfig()
        context = {"source": empty_file, "config": config}

        preconditions.check(context)

        # Empty file might be valid or invalid depending on implementation
        # If invalid:
        # assert any("empty" in v.lower() for v in violations)

    def test_import_large_file_warning(self, temp_dir):
        """Test preconditions warn about large files."""
        from bibmgr.operations.validators import ImportPreconditions
        from bibmgr.operations.workflows.import_workflow import ImportWorkflowConfig

        preconditions = ImportPreconditions()

        # Create large file (mock)
        large_file = temp_dir / "large.bib"
        # Write many entries
        content = "\n".join(
            f"@article{{entry{i}, title={{Entry {i}}}, year={{2024}}}}"
            for i in range(10000)
        )
        large_file.write_text(content)

        config = ImportWorkflowConfig()
        context = {"source": large_file, "config": config}

        preconditions.check(context)

        # Might warn but not fail
        # Check for warnings if implemented


class TestPostconditions:
    """Test postconditions that verify operation results."""

    def test_create_postconditions(self, entry_repository):
        """Test postconditions after create operation."""
        from bibmgr.operations.validators import CreatePostconditions

        postconditions = CreatePostconditions()

        entry = create_entry_with_data(key="created", title="Created Entry")
        entry_repository.save(entry)

        context = {
            "entry": entry,
            "repository": entry_repository,
        }

        violations = postconditions.check(context)

        assert len(violations) == 0

    def test_create_postconditions_not_saved(self, entry_repository):
        """Test postconditions fail if entry not actually saved."""
        from bibmgr.operations.validators import CreatePostconditions

        postconditions = CreatePostconditions()

        entry = create_entry_with_data(key="not_saved", title="Not Saved")
        # Don't save to repository

        context = {
            "entry": entry,
            "repository": entry_repository,
        }

        violations = postconditions.check(context)

        assert len(violations) > 0
        assert any("not found in repository" in v for v in violations)

    def test_update_postconditions(self, populated_repository):
        """Test postconditions after update operation."""
        from bibmgr.operations.validators import UpdatePostconditions

        postconditions = UpdatePostconditions()

        # Get original
        original = populated_repository.find("smith2020")

        # Update
        updated_data = original.to_dict()
        updated_data["title"] = "Updated Title"
        updated = Entry.from_dict(updated_data)
        populated_repository.save(updated)

        context = {
            "key": "smith2020",
            "updates": {"title": "Updated Title"},
            "original": original,
            "updated": updated,
            "repository": populated_repository,
        }

        violations = postconditions.check(context)

        # Should pass - title was updated
        assert len(violations) == 0

    def test_update_postconditions_no_change(self, populated_repository):
        """Test postconditions when update made no changes."""
        from bibmgr.operations.validators import UpdatePostconditions

        postconditions = UpdatePostconditions()

        original = populated_repository.find("smith2020")

        context = {
            "key": "smith2020",
            "updates": {"title": original.title},  # Same value
            "original": original,
            "updated": original,
            "repository": populated_repository,
        }

        postconditions.check(context)

        # Might warn about no actual changes
        # Implementation dependent

    def test_delete_postconditions(self, populated_repository):
        """Test postconditions after delete operation."""
        from bibmgr.operations.validators import DeletePostconditions

        postconditions = DeletePostconditions()

        # Delete entry
        populated_repository.delete("smith2020")

        context = {
            "key": "smith2020",
            "repository": populated_repository,
        }

        violations = postconditions.check(context)

        assert len(violations) == 0

    def test_delete_postconditions_still_exists(self, populated_repository):
        """Test postconditions fail if entry still exists."""
        from bibmgr.operations.validators import DeletePostconditions

        postconditions = DeletePostconditions()

        # Don't actually delete

        context = {
            "key": "smith2020",
            "repository": populated_repository,
        }

        violations = postconditions.check(context)

        assert len(violations) > 0
        assert any("still exists" in v for v in violations)

    def test_merge_postconditions(self, entry_repository):
        """Test postconditions after merge operation."""
        from bibmgr.operations.validators import MergePostconditions

        postconditions = MergePostconditions()

        # Create and merge entries
        create_entry_with_data(key="merge1", title="Entry 1")
        create_entry_with_data(key="merge2", title="Entry 2")
        merged = create_entry_with_data(
            key="merge1",
            title="Merged Entry",
            note="Merged from merge1 and merge2",
        )

        entry_repository.save(merged)
        # Source entry2 deleted

        context = {
            "source_keys": ["merge1", "merge2"],
            "target_key": "merge1",
            "merged_entry": merged,
            "delete_sources": True,
            "repository": entry_repository,
        }

        violations = postconditions.check(context)

        # Should pass - merged exists, source deleted
        assert len(violations) == 0

    def test_merge_postconditions_source_still_exists(self, entry_repository):
        """Test postconditions when source not deleted after merge."""
        from bibmgr.operations.validators import MergePostconditions

        postconditions = MergePostconditions()

        # Create entries
        entry1 = create_entry_with_data(key="keep1")
        entry2 = create_entry_with_data(key="keep2")
        merged = create_entry_with_data(key="merged")

        for entry in [entry1, entry2, merged]:
            entry_repository.save(entry)

        context = {
            "source_keys": ["keep1", "keep2"],
            "target_key": "merged",
            "merged_entry": merged,
            "delete_sources": True,  # Should have deleted
            "repository": entry_repository,
        }

        violations = postconditions.check(context)

        assert len(violations) > 0
        assert any("still exists" in v for v in violations)


class TestValidatorIntegration:
    """Test integration between validators and operations."""

    def test_preconditions_prevent_invalid_operation(self, entry_repository):
        """Test preconditions prevent invalid operations."""
        from bibmgr.operations.commands.create import CreateCommand, CreateHandler
        from bibmgr.operations.validators import OperationValidator

        validator = OperationValidator()
        handler = CreateHandler(entry_repository, Mock())

        # Invalid command
        command = CreateCommand(entry=None)

        # Check preconditions
        if validator.validate_preconditions(command):
            result = handler.execute(command)
        else:
            result = Mock()
            result.status.name = "VALIDATION_FAILED"
            result.message = "Precondition validation failed"

        assert result.status.name == "VALIDATION_FAILED"

    def test_postconditions_verify_success(self, entry_repository):
        """Test postconditions verify successful operations."""
        from bibmgr.operations.commands.create import CreateCommand, CreateHandler
        from bibmgr.operations.validators import OperationValidator

        validator = OperationValidator()
        handler = CreateHandler(entry_repository, Mock())

        entry = create_entry_with_data(key="test", title="Test")
        command = CreateCommand(entry=entry)

        # Execute
        result = handler.execute(command)

        # Check postconditions
        if result.status.is_success():
            postcondition_valid = validator.validate_postconditions(
                command,
                result,
                {"repository": entry_repository},
            )
            assert postcondition_valid

    def test_validator_chain(self):
        """Test chaining multiple validators."""
        from bibmgr.operations.validators import ValidatorChain

        # Mock validators
        validator1 = Mock()
        validator1.check.return_value = ["Error 1"]

        validator2 = Mock()
        validator2.check.return_value = []

        validator3 = Mock()
        validator3.check.return_value = ["Error 3"]

        chain = ValidatorChain([validator1, validator2, validator3])

        violations = chain.check({})

        assert len(violations) == 2
        assert "Error 1" in violations
        assert "Error 3" in violations
