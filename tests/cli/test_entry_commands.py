"""Tests for entry management CLI commands.

This module comprehensively tests all entry CRUD operations including:
- Adding entries (interactive, from DOI, from PDF, batch)
- Showing entry details (various formats)
- Listing entries (filtering, sorting, pagination)
- Editing entries (interactive, field-based, external editor)
- Deleting entries (single, multiple, with confirmation)
"""

import json
from unittest.mock import Mock, patch

import yaml

from bibmgr.core.models import ValidationError
from bibmgr.operations.results import OperationResult, ResultStatus


class TestAddCommand:
    """Test the 'bib add' command."""

    def test_add_basic_entry(
        self, cli_runner, mock_get_repository, mock_create_handler
    ):
        """Test adding a basic entry with minimal required fields."""
        with patch(
            "bibmgr.cli.commands.entry.get_create_handler",
            return_value=mock_create_handler,
        ):
            result = cli_runner.invoke(
                [
                    "add",
                    "--key",
                    "test2024",
                    "--title",
                    "Test Article",
                    "--type",
                    "article",
                ]
            )

        assert_exit_success(result)
        assert_output_contains(result, "Entry added successfully", "test2024")
        assert mock_create_handler.execute.called

    def test_add_interactive_mode(
        self, cli_runner, mock_get_repository, mock_create_handler
    ):
        """Test interactive entry addition."""
        with patch(
            "bibmgr.cli.commands.entry.get_create_handler",
            return_value=mock_create_handler,
        ):
            # Simulate user input
            user_input = "\n".join(
                [
                    "test2024",  # key
                    "Test Article",  # title
                    "Doe, John",  # author
                    "2024",  # year
                    "Nature",  # journal (for article type)
                ]
            )
            result = cli_runner.invoke(["add", "--interactive"], input=user_input)

        assert_exit_success(result)
        assert_output_contains(result, "Key", "Title", "Author", "Year", "Journal")
        assert mock_create_handler.execute.called

    def test_add_without_key_generates_key(
        self, cli_runner, mock_get_repository, mock_create_handler
    ):
        """Test that key is auto-generated when not provided."""
        with patch(
            "bibmgr.cli.commands.entry.get_create_handler",
            return_value=mock_create_handler,
        ):
            result = cli_runner.invoke(
                [
                    "add",
                    "--title",
                    "Test Article",
                    "--author",
                    "Doe, John",
                    "--year",
                    "2024",
                ]
            )

        assert_exit_success(result)
        # Should generate key like 'doe2024'
        assert mock_create_handler.execute.called
        command = mock_create_handler.execute.call_args[0][0]
        assert command.entry.key == "doe2024"

    def test_add_duplicate_key_error(self, cli_runner, populated_repository):
        """Test error when adding entry with duplicate key."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(
                ["add", "--key", "doe2024", "--title", "Another Article"]
            )

        assert_exit_failure(result)
        assert_output_contains(result, "already exists")

    def test_add_with_validation_errors(self, cli_runner, mock_get_repository):
        """Test adding entry with validation errors."""
        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.VALIDATION_FAILED,
            message="Validation failed",
            validation_errors=[
                ValidationError("year", "Invalid year format", "error"),
                ValidationError("doi", "Invalid DOI format", "warning"),
            ],
        )

        with patch(
            "bibmgr.cli.commands.entry.get_create_handler", return_value=handler
        ):
            result = cli_runner.invoke(
                ["add", "--key", "test2024", "--title", "Test", "--year", "invalid"]
            )

        assert_exit_failure(result)
        assert_output_contains(result, "Validation failed", "Invalid year format")

    def test_add_with_all_fields(
        self, cli_runner, mock_get_repository, mock_create_handler
    ):
        """Test adding entry with all possible fields."""
        with patch(
            "bibmgr.cli.commands.entry.get_create_handler",
            return_value=mock_create_handler,
        ):
            result = cli_runner.invoke(
                [
                    "add",
                    "--key",
                    "complete2024",
                    "--type",
                    "article",
                    "--title",
                    "Complete Article",
                    "--author",
                    "Doe, John and Smith, Jane",
                    "--year",
                    "2024",
                    "--journal",
                    "Nature",
                    "--volume",
                    "123",
                    "--number",
                    "4",
                    "--pages",
                    "100--110",
                    "--doi",
                    "10.1038/nature.2024.123",
                    "--url",
                    "https://example.com",
                    "--abstract",
                    "This is the abstract",
                    "--keywords",
                    "quantum,computing,ml",
                    "--file",
                    "/path/to/file.pdf",
                ]
            )

        assert_exit_success(result)
        assert mock_create_handler.execute.called
        command = mock_create_handler.execute.call_args[0][0]
        entry = command.entry
        assert entry.key == "complete2024"
        assert entry.author == "Doe, John and Smith, Jane"
        assert entry.keywords == "quantum,computing,ml"

    def test_add_from_doi(self, cli_runner):
        """Test adding entry by fetching metadata from DOI."""
        # Currently not implemented
        result = cli_runner.invoke(["add", "--from-doi", "10.1038/nature12373"])
        assert_output_contains(result, "not yet implemented")

    def test_add_from_pdf(self, cli_runner, tmp_path):
        """Test adding entry by extracting metadata from PDF."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        # Currently not implemented
        result = cli_runner.invoke(["add", "--from-pdf", str(pdf_file)])
        assert_output_contains(result, "not yet implemented")

    def test_add_force_flag_skips_validation(
        self, cli_runner, mock_get_repository, mock_create_handler
    ):
        """Test that --no-validate flag skips validation."""
        with patch(
            "bibmgr.cli.commands.entry.get_create_handler",
            return_value=mock_create_handler,
        ):
            result = cli_runner.invoke(
                [
                    "add",
                    "--key",
                    "invalid2024",
                    "--title",
                    "Invalid Entry",
                    "--year",
                    "invalid",  # Invalid year
                    "--no-validate",
                ]
            )

        assert_exit_success(result)
        assert mock_create_handler.execute.called


class TestShowCommand:
    """Test the 'bib show' command."""

    def test_show_entry_detailed(self, cli_runner, populated_repository):
        """Test showing entry in detailed format (default)."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["show", "doe2024"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "doe2024",
            "Quantum Computing Advances",
            "Doe, John and Smith, Jane",
            "2024",
            "Nature Quantum",
        )

    def test_show_entry_bibtex_format(self, cli_runner, populated_repository):
        """Test showing entry in BibTeX format."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["show", "doe2024", "--format", "bibtex"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "@article{doe2024",
            "title = {Quantum Computing Advances}",
            "author = {Doe, John and Smith, Jane}",
            "year = {2024}",
        )

    def test_show_entry_json_format(self, cli_runner, populated_repository):
        """Test showing entry in JSON format."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["show", "doe2024", "--format", "json"])

        assert_exit_success(result)
        # Verify valid JSON
        output_json = json.loads(result.output)
        assert output_json["key"] == "doe2024"
        assert output_json["title"] == "Quantum Computing Advances"

    def test_show_entry_yaml_format(self, cli_runner, populated_repository):
        """Test showing entry in YAML format."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["show", "doe2024", "--format", "yaml"])

        assert_exit_success(result)
        # Verify valid YAML
        output_yaml = yaml.safe_load(result.output)
        assert output_yaml["key"] == "doe2024"

    def test_show_nonexistent_entry(self, cli_runner, populated_repository):
        """Test showing entry that doesn't exist."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["show", "nonexistent"])

        assert_exit_failure(result)
        assert_output_contains(result, "Entry not found", "nonexistent")

    def test_show_with_metadata(
        self, cli_runner, populated_repository, metadata_store, sample_metadata
    ):
        """Test showing entry with metadata (tags, rating, notes)."""
        metadata_store.save_metadata(sample_metadata)

        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.entry.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(["show", "doe2024"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "Tags",
            "computing, important, quantum",  # All tags shown, sorted alphabetically
            "Rating",
            "★★★★★",
            "Read Status",
            "read",  # Matches the fixture's lowercase status
        )


class TestListCommand:
    """Test the 'bib list' command."""

    def test_list_all_entries(self, cli_runner, populated_repository):
        """Test listing all entries with default settings."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["list"])

        assert_exit_success(result)
        assert_output_contains(result, "doe2024", "smith2023", "jones2022")
        assert_output_contains(result, "Showing 3 of 3 entries")

    def test_list_with_limit(self, cli_runner, populated_repository):
        """Test listing with limit."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["list", "--limit", "2"])

        assert_exit_success(result)
        assert_output_contains(result, "Showing 2 of 3 entries")

    def test_list_with_offset(self, cli_runner, populated_repository):
        """Test listing with offset."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["list", "--offset", "1", "--limit", "2"])

        assert_exit_success(result)
        assert_output_not_contains(result, "doe2024")  # First entry skipped

    def test_list_sorted_by_year(self, cli_runner, populated_repository):
        """Test listing sorted by year."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["list", "--sort", "year"])

        assert_exit_success(result)
        # Should be in year order: 2022, 2023, 2024
        lines = result.output.splitlines()
        jones_line = next(i for i, line in enumerate(lines) if "jones2022" in line)
        doe_line = next(i for i, line in enumerate(lines) if "doe2024" in line)
        assert jones_line < doe_line

    def test_list_reverse_sorted(self, cli_runner, populated_repository):
        """Test listing with reverse sort."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["list", "--sort", "year", "--reverse"])

        assert_exit_success(result)
        # Should be in reverse year order: 2024, 2023, 2022
        lines = result.output.splitlines()
        doe_line = next(i for i, line in enumerate(lines) if "doe2024" in line)
        jones_line = next(i for i, line in enumerate(lines) if "jones2022" in line)
        assert doe_line < jones_line

    def test_list_filter_by_type(self, cli_runner, populated_repository):
        """Test listing filtered by entry type."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["list", "--type", "article"])

        assert_exit_success(result)
        assert_output_contains(result, "doe2024")
        assert_output_not_contains(result, "smith2023", "jones2022")

    def test_list_filter_by_year(self, cli_runner, populated_repository):
        """Test listing filtered by year."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["list", "--year", "2023"])

        assert_exit_success(result)
        assert_output_contains(result, "smith2023")
        assert_output_not_contains(result, "doe2024", "jones2022")

    def test_list_filter_by_author(self, cli_runner, populated_repository):
        """Test listing filtered by author (partial match)."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["list", "--author", "Jane"])

        assert_exit_success(result)
        assert_output_contains(result, "doe2024", "smith2023")  # Both have Jane
        assert_output_not_contains(result, "jones2022")

    def test_list_bibtex_format(self, cli_runner, populated_repository):
        """Test listing in BibTeX format."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["list", "--format", "bibtex", "--limit", "1"])

        assert_exit_success(result)
        assert_output_contains(result, "@article{", "title = {", "author = {")

    def test_list_json_format(self, cli_runner, populated_repository):
        """Test listing in JSON format."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["list", "--format", "json"])

        assert_exit_success(result)
        output_json = json.loads(result.output)
        assert "entries" in output_json
        assert "total" in output_json
        assert output_json["total"] == 3

    def test_list_keys_only_format(self, cli_runner, populated_repository):
        """Test listing keys only."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["list", "--format", "keys"])

        assert_exit_success(result)
        lines = result.output.strip().split("\n")
        assert "doe2024" in lines
        assert "smith2023" in lines
        assert "jones2022" in lines

    def test_list_empty_repository(self, cli_runner, entry_repository):
        """Test listing when no entries exist."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository", return_value=entry_repository
        ):
            result = cli_runner.invoke(["list"])

        assert_exit_success(result)
        assert_output_contains(result, "No entries found")


class TestEditCommand:
    """Test the 'bib edit' command."""

    def test_edit_single_field(
        self, cli_runner, populated_repository, mock_update_handler
    ):
        """Test editing a single field."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.entry.get_update_handler",
                return_value=mock_update_handler,
            ):
                result = cli_runner.invoke(["edit", "doe2024", "-f", "year=2025"])

        assert_exit_success(result)
        assert_output_contains(result, "Entry updated successfully")
        assert mock_update_handler.execute.called
        command = mock_update_handler.execute.call_args[0][0]
        assert command.key == "doe2024"
        assert command.updates["year"] == 2025

    def test_edit_multiple_fields(
        self, cli_runner, populated_repository, mock_update_handler
    ):
        """Test editing multiple fields at once."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.entry.get_update_handler",
                return_value=mock_update_handler,
            ):
                result = cli_runner.invoke(
                    [
                        "edit",
                        "doe2024",
                        "-f",
                        "year=2025",
                        "-f",
                        "volume=13",
                        "-f",
                        "pages=20--30",
                    ]
                )

        assert_exit_success(result)
        command = mock_update_handler.execute.call_args[0][0]
        assert command.updates["year"] == 2025
        assert command.updates["volume"] == "13"
        assert command.updates["pages"] == "20--30"

    def test_edit_interactive_mode(
        self, cli_runner, populated_repository, mock_update_handler
    ):
        """Test interactive editing mode."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.entry.get_update_handler",
                return_value=mock_update_handler,
            ):
                # Simulate user keeping most fields, changing year
                user_input = "\n".join(
                    [
                        "",  # Keep title
                        "",  # Keep author
                        "2025",  # Change year
                        "",  # Keep journal
                    ]
                )
                result = cli_runner.invoke(
                    ["edit", "doe2024", "--interactive"], input=user_input
                )

        assert_exit_success(result)
        assert_output_contains(
            result, "Editing entry", "Press Enter to keep current value"
        )

    def test_edit_with_external_editor(
        self, cli_runner, populated_repository, mock_update_handler, mock_editor
    ):
        """Test editing with external editor."""
        # Mock subprocess.call to avoid actually opening an editor
        with patch("subprocess.call") as mock_subprocess:
            # Mock the BibtexImporter to return a modified entry
            mock_importer = Mock()
            mock_importer.import_text.return_value = (
                [populated_repository.find("doe2024")],
                [],
            )

            with patch(
                "bibmgr.cli.commands.entry.get_repository",
                return_value=populated_repository,
            ):
                with patch(
                    "bibmgr.cli.commands.entry.get_update_handler",
                    return_value=mock_update_handler,
                ):
                    with patch(
                        "bibmgr.storage.importers.bibtex.BibtexImporter",
                        return_value=mock_importer,
                    ):
                        result = cli_runner.invoke(["edit", "doe2024", "--editor"])

        assert_exit_success(result)
        assert mock_subprocess.called

    def test_edit_invalid_field_format(self, cli_runner, populated_repository):
        """Test error on invalid field format."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["edit", "doe2024", "-f", "invalid_format"])

        assert_exit_failure(result)
        assert_output_contains(result, "Invalid field format", "use FIELD=VALUE")

    def test_edit_nonexistent_entry(self, cli_runner, populated_repository):
        """Test editing entry that doesn't exist."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["edit", "nonexistent", "-f", "year=2025"])

        assert_exit_failure(result)
        assert_output_contains(result, "Entry not found")

    def test_edit_no_changes(self, cli_runner, populated_repository):
        """Test when no changes are made in interactive mode."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            # User presses enter for all fields (no changes)
            user_input = "\n" * 5
            result = cli_runner.invoke(
                ["edit", "doe2024", "--interactive"], input=user_input
            )

        assert_exit_success(result)
        assert_output_contains(result, "No changes made")


class TestDeleteCommand:
    """Test the 'bib delete' command."""

    def test_delete_single_entry_with_confirmation(
        self, cli_runner, populated_repository, mock_delete_handler
    ):
        """Test deleting single entry with confirmation."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.entry.get_delete_handler",
                return_value=mock_delete_handler,
            ):
                result = cli_runner.invoke(["delete", "doe2024"], input="y\n")

        assert_exit_success(result)
        assert_output_contains(
            result,
            "Are you sure",
            "Quantum Computing Advances",  # Shows title
            "Entry deleted successfully",
        )

    def test_delete_single_entry_force(
        self, cli_runner, populated_repository, mock_delete_handler
    ):
        """Test deleting single entry with --force flag."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.entry.get_delete_handler",
                return_value=mock_delete_handler,
            ):
                result = cli_runner.invoke(["delete", "doe2024", "--force"])

        assert_exit_success(result)
        assert_output_not_contains(result, "Are you sure")  # No confirmation
        assert_output_contains(result, "Entry deleted successfully")

    def test_delete_multiple_entries(
        self, cli_runner, populated_repository, mock_delete_handler
    ):
        """Test deleting multiple entries at once."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.entry.get_delete_handler",
                return_value=mock_delete_handler,
            ):
                result = cli_runner.invoke(
                    ["delete", "doe2024", "smith2023", "--force"]
                )

        assert_exit_success(result)
        assert_output_contains(result, "Successfully deleted 2 entries")
        assert mock_delete_handler.execute.call_count == 2

    def test_delete_cancelled_by_user(self, cli_runner, populated_repository):
        """Test delete cancelled by user."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["delete", "doe2024"], input="n\n")

        assert_exit_success(result)
        assert_output_contains(result, "Deletion cancelled")

    def test_delete_nonexistent_entry(self, cli_runner, populated_repository):
        """Test deleting entry that doesn't exist."""
        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            result = cli_runner.invoke(["delete", "nonexistent", "--force"])

        assert_exit_failure(result)
        assert_output_contains(result, "Entries not found", "nonexistent")

    def test_delete_partial_failure(self, cli_runner, populated_repository):
        """Test when some entries fail to delete."""
        handler = Mock()
        handler.execute.side_effect = [
            OperationResult(
                status=ResultStatus.SUCCESS,
                message="Entry 'doe2024' deleted",
                entity_id="doe2024",
            ),
            OperationResult(
                status=ResultStatus.ERROR,
                message="Failed to delete 'smith2023'",
                entity_id="smith2023",
            ),
        ]

        with patch(
            "bibmgr.cli.commands.entry.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.entry.get_delete_handler", return_value=handler
            ):
                result = cli_runner.invoke(
                    ["delete", "doe2024", "smith2023", "--force"]
                )

        assert_exit_success(result)  # Partial success still exits 0
        assert_output_contains(result, "Deleted 1 of 2 entries")

    def test_delete_requires_at_least_one_key(self, cli_runner):
        """Test that delete command requires at least one key."""
        result = cli_runner.invoke(["delete"])

        assert_exit_failure(
            result, expected_code=2
        )  # Click exits with 2 for missing arguments
        assert_output_contains(result, "Missing argument")


# Test helpers
def assert_exit_success(result):
    """Assert CLI command exited successfully."""
    assert result.exit_code == 0, f"Command failed: {result.output}"


def assert_exit_failure(result, expected_code=1):
    """Assert CLI command failed with expected code."""
    assert result.exit_code == expected_code, (
        f"Expected exit code {expected_code}, got {result.exit_code}: {result.output}"
    )


def assert_output_contains(result, *expected):
    """Assert CLI output contains expected strings."""
    for text in expected:
        assert text in result.output, f"Expected '{text}' in output:\n{result.output}"


def assert_output_not_contains(result, *unexpected):
    """Assert CLI output does not contain strings."""
    for text in unexpected:
        assert text not in result.output, (
            f"Unexpected '{text}' in output:\n{result.output}"
        )
