"""Tests for quality operations."""

import pytest

from bibmgr.core.models import Entry, EntryType
from bibmgr.operations.quality_commands import (
    CheckConsistencyCommand,
    GenerateQualityReportCommand,
    ValidateBatchCommand,
    ValidateEntryCommand,
)
from bibmgr.operations.quality_handlers import QualityHandler


class TestQualityOperations:
    """Test quality check operations."""

    @pytest.fixture
    def handler(self):
        """Create quality handler."""
        return QualityHandler()

    @pytest.fixture
    def valid_entry(self):
        """Create a valid entry."""
        return Entry(
            key="valid2023",
            type=EntryType.ARTICLE,
            title="Valid Article",
            author="Smith, John",
            year=2023,
            journal="Nature",
            doi="10.1038/s41586-023-06001-9",
        )

    @pytest.fixture
    def invalid_entry(self):
        """Create an entry with validation issues."""
        return Entry(
            key="invalid2023",
            type=EntryType.ARTICLE,
            title="Invalid Article",
            # Missing required author
            year=2023,
            doi="invalid-doi-format",
        )

    @pytest.fixture
    def sample_entries(self, valid_entry, invalid_entry):
        """Create sample entries with issues."""
        return [
            valid_entry,
            invalid_entry,
            Entry(
                key="duplicate2023",
                type=EntryType.ARTICLE,
                title="Valid Article",  # Duplicate title
                author="Smith, John",  # Same author
                year=2023,
                journal="Science",
            ),
        ]

    def test_validate_entry_command_valid(self, handler, valid_entry):
        """Test validating a valid entry."""
        command = ValidateEntryCommand(entry=valid_entry)
        result = handler.execute(command)

        assert result.success
        assert len(result.data["issues"]) == 0
        assert result.data["error_count"] == 0

    def test_validate_entry_command_invalid(self, handler, invalid_entry):
        """Test validating an invalid entry."""
        command = ValidateEntryCommand(entry=invalid_entry)
        result = handler.execute(command)

        assert not result.success
        assert len(result.data["issues"]) >= 2  # Missing author, invalid DOI
        assert result.data["error_count"] >= 1
        assert "validation errors" in result.message

    def test_validate_entry_with_warnings(self, handler):
        """Test entry with warnings but no errors."""
        entry = Entry(
            key="warning2023",
            type=EntryType.ARTICLE,
            title="Article with Warnings",
            author="Smith, John",
            year=2023,
            journal="Test Journal",
            url="http://example.com",  # HTTP instead of HTTPS
        )

        command = ValidateEntryCommand(entry=entry)
        result = handler.execute(command)

        assert result.success  # Warnings don't fail validation
        assert "warnings" in result.message.lower()
        assert result.data["warning_count"] > 0

    def test_validate_batch_command(self, handler, sample_entries):
        """Test batch validation."""
        command = ValidateBatchCommand(
            entries=sample_entries,
            stop_on_error=False,
        )

        result = handler.execute(command)

        assert result.success  # Command succeeds even with invalid entries
        assert result.data["total_entries"] == 3
        assert result.data["valid_entries"] == 2  # valid2023 and duplicate2023
        assert result.data["entries_with_errors"] == 1  # invalid2023
        assert len(result.data["all_issues"]) > 0

    def test_validate_batch_stop_on_error(self, handler, sample_entries):
        """Test batch validation with stop on error."""
        command = ValidateBatchCommand(
            entries=sample_entries,
            stop_on_error=True,
        )

        result = handler.execute(command)

        # Should stop at first error (invalid entry is second)
        assert not result.success
        assert "stopped at" in result.message.lower()
        assert result.data["stopped_at"] == "invalid2023"

    def test_check_consistency_command(self, handler, sample_entries):
        """Test consistency checking."""
        command = CheckConsistencyCommand(
            entries=sample_entries,
            check_duplicates=True,
            check_crossrefs=True,
        )

        result = handler.execute(command)

        assert result.success
        assert len(result.data["duplicates"]) > 0  # Should find duplicate
        assert result.data["duplicate_count"] == 1
        assert result.data["has_issues"]

    def test_generate_quality_report_json(self, handler, sample_entries):
        """Test quality report generation in JSON format."""
        command = GenerateQualityReportCommand(
            entries=sample_entries,
            format="json",
            include_consistency=True,
            include_suggestions=True,
        )

        result = handler.execute(command)

        assert result.success
        assert "report" in result.data
        assert "formatted" in result.data

        report = result.data["report"]
        assert "metrics" in report
        assert "validation_results" in report
        assert "consistency_report" in report
        assert "suggestions" in report

        # Check metrics
        metrics = report["metrics"]
        assert metrics["total_entries"] == 3
        assert metrics["valid_entries"] == 2  # valid2023 and duplicate2023
        assert metrics["quality_score"] < 100  # Due to invalid entries

    def test_generate_quality_report_markdown(self, handler, sample_entries):
        """Test quality report generation in Markdown format."""
        command = GenerateQualityReportCommand(
            entries=sample_entries,
            format="markdown",
            include_consistency=False,
            include_suggestions=False,
        )

        result = handler.execute(command)

        assert result.success
        formatted = result.data["formatted"]
        assert isinstance(formatted, str)
        assert "# Quality Report" in formatted or "Quality Report" in formatted
        assert "Total entries:" in formatted

    def test_generate_quality_report_invalid_format(self, handler, sample_entries):
        """Test report generation with invalid format."""
        command = GenerateQualityReportCommand(
            entries=sample_entries,
            format="invalid_format",
        )

        result = handler.execute(command)

        assert not result.success
        assert "Unknown report format" in result.message
        assert "Supported formats" in result.errors[0]

    def test_empty_batch_validation(self, handler):
        """Test validating empty batch."""
        command = ValidateBatchCommand(entries=[])
        result = handler.execute(command)

        assert result.success
        assert result.data["total_entries"] == 0
        assert result.data["valid_entries"] == 0

    def test_consistency_check_without_duplicates(self, handler):
        """Test consistency check on unique entries."""
        unique_entries = [
            Entry(
                key="unique1",
                type=EntryType.ARTICLE,
                title="First Unique Article",
                author="Smith, John",
                year=2023,
            ),
            Entry(
                key="unique2",
                type=EntryType.ARTICLE,
                title="Second Unique Article",
                author="Doe, Jane",
                year=2023,
            ),
        ]

        command = CheckConsistencyCommand(
            entries=unique_entries,
            check_duplicates=True,
        )

        result = handler.execute(command)

        assert result.success
        assert result.data["duplicate_count"] == 0
        assert not result.data["has_issues"]

    def test_quality_report_with_suggestions(self, handler):
        """Test that suggestions are properly extracted."""
        entry = Entry(
            key="test2023",
            type=EntryType.ARTICLE,
            title="Test Article",
            author="Smith, John",
            year=2023,
            journal="Test Journal",
            pages="10-20",  # Should suggest BibTeX format
        )

        command = GenerateQualityReportCommand(
            entries=[entry],
            format="json",
            include_suggestions=True,
        )

        result = handler.execute(command)

        assert result.success
        suggestions = result.data["report"]["suggestions"]
        # Should have suggestion about page format
        assert any("pages" in s["field"] for s in suggestions)

    def test_validate_thesis_without_school(self, handler):
        """Test validating thesis entries without school."""
        thesis = Entry(
            key="thesis2023",
            type=EntryType.PHDTHESIS,
            title="PhD Thesis Title",
            author="Student, John",
            year=2023,
            # Missing required school field
        )

        command = ValidateEntryCommand(entry=thesis)
        result = handler.execute(command)

        assert not result.success
        assert any(issue.field == "school" for issue in result.data["issues"])

    def test_validate_book_with_isbn(self, handler):
        """Test validating book with ISBN."""
        book = Entry(
            key="book2023",
            type=EntryType.BOOK,
            title="Machine Learning Book",
            author="Author, Jane",
            year=2023,
            publisher="MIT Press",
            isbn="978-0-262-04482-0",  # Valid ISBN-13
        )

        command = ValidateEntryCommand(entry=book)
        result = handler.execute(command)

        assert result.success
        # Should have no errors, possibly info about valid ISBN

    def test_batch_validation_progress(self, handler):
        """Test batch validation provides progress info."""
        # Create many entries
        entries = []
        for i in range(10):
            entries.append(
                Entry(
                    key=f"entry{i}",
                    type=EntryType.MISC,
                    title=f"Entry {i}",
                    year=2023,
                )
            )

        command = ValidateBatchCommand(entries=entries)
        result = handler.execute(command)

        assert result.success
        assert result.data["total_entries"] == 10
