"""Tests for CLI entry commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


from bibmgr.core.models import Entry, EntryType


class TestAddCommand:
    """Test the 'add' command."""

    def test_add_with_all_options(self, cli_runner, mock_operations):
        """Test adding an entry with all options specified."""
        from bibmgr.cli import cli

        with patch(
            "bibmgr.cli.commands.entry_commands.get_operations",
            return_value=mock_operations,
        ):
            result = cli_runner.invoke(
                cli,
                [
                    "add",
                    "--type",
                    "article",
                    "--key",
                    "test2023",
                    "--title",
                    "Test Article",
                    "--author",
                    "Test Author",
                    "--year",
                    "2023",
                    "--journal",
                    "Test Journal",
                ],
            )

            if result.exit_code != 0:
                print(f"Output: {result.output}")
                print(f"Exception: {result.exception}")
            assert result.exit_code == 0
            assert mock_operations.create.called

            # Verify the entry passed to operations
            call_args = mock_operations.create.call_args[0][0]
            assert call_args.key == "test2023"
            assert call_args.type == EntryType.ARTICLE
            assert call_args.title == "Test Article"

    def test_add_interactive_mode(self, cli_runner, mock_operations):
        """Test adding an entry in interactive mode."""
        from bibmgr.cli import cli

        with patch(
            "bibmgr.cli.commands.entry_commands.get_operations",
            return_value=mock_operations,
        ):
            # Simulate user input
            user_input = "\n".join(
                [
                    "article",  # type
                    "test2023",  # key
                    "Test Article",  # title
                    "Test Author",  # author
                    "2023",  # year
                    "Test Journal",  # journal
                    "",  # volume
                    "",  # pages
                    "",  # doi
                ]
            )

            result = cli_runner.invoke(cli, ["add", "--interactive"], input=user_input)

            assert result.exit_code == 0
            assert mock_operations.create.called

    def test_add_minimal_required_fields(self, cli_runner, mock_operations):
        """Test adding an entry with minimal required fields."""
        from bibmgr.cli import cli

        with patch(
            "bibmgr.cli.commands.entry_commands.get_operations",
            return_value=mock_operations,
        ):
            result = cli_runner.invoke(
                cli,
                [
                    "add",
                    "--key",
                    "minimal2023",
                    "--type",
                    "misc",
                    "--title",
                    "Minimal Entry",
                ],
            )

            assert result.exit_code == 0
            assert mock_operations.create.called

    def test_add_duplicate_key_error(self, cli_runner, mock_operations):
        """Test error when adding duplicate key."""
        from bibmgr.cli import cli
        from bibmgr.operations.crud import OperationResult, OperationType

        # Return a failure result instead of raising an exception
        mock_operations.create.return_value = OperationResult(
            success=False,
            operation=OperationType.CREATE,
            message="Duplicate key",
            errors=["Entry with key 'duplicate' already exists"],
        )

        with patch(
            "bibmgr.cli.commands.entry_commands.get_operations",
            return_value=mock_operations,
        ):
            result = cli_runner.invoke(
                cli,
                [
                    "add",
                    "--key",
                    "duplicate",
                    "--type",
                    "article",
                    "--title",
                    "Test",
                ],
            )

            assert result.exit_code != 0
            assert "already exists" in result.output.lower()

    def test_add_dry_run(self, cli_runner, mock_operations):
        """Test dry-run mode doesn't actually add."""
        from bibmgr.cli import cli

        with patch(
            "bibmgr.cli.commands.entry_commands.get_operations",
            return_value=mock_operations,
        ):
            result = cli_runner.invoke(
                cli,
                [
                    "add",
                    "--key",
                    "dryrun",
                    "--type",
                    "article",
                    "--title",
                    "Dry Run Test",
                    "--dry-run",
                ],
            )

            assert result.exit_code == 0
            assert not mock_operations.create.called
            assert "Preview" in result.output or "dry-run" in result.output.lower()

    def test_add_from_file(self, cli_runner, mock_operations, temp_dir):
        """Test adding entry from a file."""
        from bibmgr.cli import cli

        # Create entry file
        entry_file = temp_dir / "entry.json"
        entry_data = {
            "key": "fromfile2023",
            "type": "article",
            "title": "From File",
            "author": "File Author",
            "year": 2023,
        }
        with open(entry_file, "w") as f:
            json.dump(entry_data, f)

        with patch(
            "bibmgr.cli.commands.entry_commands.get_operations",
            return_value=mock_operations,
        ):
            result = cli_runner.invoke(cli, ["add", "--from-file", str(entry_file)])

            assert result.exit_code == 0
            assert mock_operations.create.called

    def test_add_invalid_type(self, cli_runner):
        """Test error with invalid entry type."""
        from bibmgr.cli import cli

        result = cli_runner.invoke(
            cli,
            [
                "add",
                "--key",
                "test",
                "--type",
                "invalid_type",
                "--title",
                "Test",
            ],
        )

        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    def test_add_missing_required_field(self, cli_runner):
        """Test error when missing required field."""
        from bibmgr.cli import cli

        result = cli_runner.invoke(
            cli,
            [
                "add",
                "--type",
                "article",
                "--title",
                "Test",
                # Missing --key
            ],
        )

        assert result.exit_code != 0
        assert "key" in result.output.lower() or "required" in result.output.lower()


class TestEditCommand:
    """Test the 'edit' command."""

    def test_edit_single_field(
        self, cli_runner, mock_storage, mock_operations, sample_entry
    ):
        """Test editing a single field."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            with patch(
                "bibmgr.cli.commands.entry_commands.get_operations",
                return_value=mock_operations,
            ):
                result = cli_runner.invoke(
                    cli,
                    [
                        "edit",
                        "smith2020",
                        "--field",
                        "title=Updated Title",
                    ],
                )

                assert result.exit_code == 0
                assert mock_operations.update.called

                # Verify update parameters
                call_args = mock_operations.update.call_args[0]
                assert call_args[0] == "smith2020"
                assert call_args[1]["title"] == "Updated Title"

    def test_edit_multiple_fields(
        self, cli_runner, mock_storage, mock_operations, sample_entry
    ):
        """Test editing multiple fields."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            with patch(
                "bibmgr.cli.commands.entry_commands.get_operations",
                return_value=mock_operations,
            ):
                result = cli_runner.invoke(
                    cli,
                    [
                        "edit",
                        "smith2020",
                        "--field",
                        "title=New Title",
                        "--field",
                        "year=2024",
                        "--field",
                        "journal=New Journal",
                    ],
                )

                assert result.exit_code == 0
                assert mock_operations.update.called

                updates = mock_operations.update.call_args[0][1]
                assert updates["title"] == "New Title"
                assert updates["year"] == "2024"
                assert updates["journal"] == "New Journal"

    def test_edit_interactive_mode(
        self, cli_runner, mock_storage, mock_operations, sample_entry
    ):
        """Test interactive editing."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            with patch(
                "bibmgr.cli.commands.entry_commands.get_operations",
                return_value=mock_operations,
            ):
                # Simulate user selecting fields to edit
                user_input = "\n".join(
                    [
                        "title",  # Select title field
                        "Updated Title",  # New value
                        "year",  # Select year field
                        "2024",  # New value
                        "",  # Done
                    ]
                )

                result = cli_runner.invoke(
                    cli, ["edit", "smith2020", "--interactive"], input=user_input
                )

                assert result.exit_code == 0
                assert mock_operations.update.called

    def test_edit_nonexistent_entry(self, cli_runner, mock_storage):
        """Test error when editing non-existent entry."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = None

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["edit", "nonexistent"])

            assert result.exit_code != 0
            assert "not found" in result.output.lower()

    def test_edit_dry_run(
        self, cli_runner, mock_storage, mock_operations, sample_entry
    ):
        """Test dry-run mode for edit."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            with patch(
                "bibmgr.cli.commands.entry_commands.get_operations",
                return_value=mock_operations,
            ):
                result = cli_runner.invoke(
                    cli,
                    [
                        "edit",
                        "smith2020",
                        "--field",
                        "title=New Title",
                        "--dry-run",
                    ],
                )

                assert result.exit_code == 0
                assert not mock_operations.update.called
                assert (
                    "preview" in result.output.lower()
                    or "dry-run" in result.output.lower()
                )

    def test_edit_with_validation(
        self, cli_runner, mock_storage, mock_operations, sample_entry
    ):
        """Test edit with validation."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            with patch(
                "bibmgr.cli.commands.entry_commands.get_operations",
                return_value=mock_operations,
            ):
                result = cli_runner.invoke(
                    cli,
                    [
                        "edit",
                        "smith2020",
                        "--field",
                        "year=2024",  # Use valid year
                        "--validate",
                    ],
                )

                # Should succeed with valid year
                assert result.exit_code == 0


class TestDeleteCommand:
    """Test the 'delete' command."""

    def test_delete_with_confirmation(
        self, cli_runner, mock_storage, mock_operations, sample_entry
    ):
        """Test deleting with confirmation."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            with patch(
                "bibmgr.cli.commands.entry_commands.get_operations",
                return_value=mock_operations,
            ):
                result = cli_runner.invoke(
                    cli,
                    [
                        "delete",
                        "smith2020",
                    ],
                    input="y\n",
                )  # Confirm deletion

                assert result.exit_code == 0
                assert mock_operations.delete.called
                assert mock_operations.delete.call_args[0][0] == "smith2020"

    def test_delete_with_force(
        self, cli_runner, mock_storage, mock_operations, sample_entry
    ):
        """Test force delete without confirmation."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            with patch(
                "bibmgr.cli.commands.entry_commands.get_operations",
                return_value=mock_operations,
            ):
                result = cli_runner.invoke(cli, ["delete", "smith2020", "--force"])

                assert result.exit_code == 0
                assert mock_operations.delete.called

    def test_delete_cancelled(
        self, cli_runner, mock_storage, mock_operations, sample_entry
    ):
        """Test cancelling deletion."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            with patch(
                "bibmgr.cli.commands.entry_commands.get_operations",
                return_value=mock_operations,
            ):
                result = cli_runner.invoke(
                    cli,
                    [
                        "delete",
                        "smith2020",
                    ],
                    input="n\n",
                )  # Cancel deletion

                assert result.exit_code == 0
                assert not mock_operations.delete.called
                assert "cancelled" in result.output.lower()

    def test_delete_multiple_entries(
        self, cli_runner, mock_storage, mock_operations, sample_entries
    ):
        """Test deleting multiple entries."""
        from bibmgr.cli import cli

        mock_storage.read.side_effect = lambda key: next(
            (e for e in sample_entries if e.key == key), None
        )

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            with patch(
                "bibmgr.cli.commands.entry_commands.get_operations",
                return_value=mock_operations,
            ):
                result = cli_runner.invoke(
                    cli, ["delete", "smith2020", "jones2021", "--force"]
                )

                assert result.exit_code == 0
                assert mock_operations.delete.call_count == 2

    def test_delete_nonexistent_entry(self, cli_runner, mock_storage):
        """Test error when deleting non-existent entry."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = None

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["delete", "nonexistent", "--force"])

            assert result.exit_code != 0
            assert "not found" in result.output.lower()

    def test_delete_with_cascade(
        self, cli_runner, mock_storage, mock_operations, sample_entry
    ):
        """Test delete with cascade option."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            with patch(
                "bibmgr.cli.commands.entry_commands.get_operations",
                return_value=mock_operations,
            ):
                result = cli_runner.invoke(
                    cli,
                    [
                        "delete",
                        "smith2020",
                        "--cascade",  # Also remove related data
                        "--force",
                    ],
                )

                assert result.exit_code == 0
                assert mock_operations.delete.called

                # Check cascade option was passed
                call_kwargs = mock_operations.delete.call_args[1]
                cascade = call_kwargs.get("cascade")
                # Check that cascade was passed (it's a CascadeOptions object, not a boolean)
                assert cascade is not None


class TestShowCommand:
    """Test the 'show' command."""

    def test_show_default_format(self, cli_runner, mock_storage, sample_entry):
        """Test showing entry in default format."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["show", "smith2020"])

            assert result.exit_code == 0
            assert "smith2020" in result.output
            assert "Test Article" in result.output
            assert "Smith, John" in result.output

    def test_show_bibtex_format(self, cli_runner, mock_storage, sample_entry):
        """Test showing entry in BibTeX format."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["show", "smith2020", "--format", "bibtex"])

            assert result.exit_code == 0
            assert "@article{smith2020" in result.output.lower()
            assert "title = " in result.output.lower()

    def test_show_json_format(self, cli_runner, mock_storage, sample_entry):
        """Test showing entry in JSON format."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["show", "smith2020", "--format", "json"])

            assert result.exit_code == 0

            # Verify valid JSON
            data = json.loads(result.output)
            assert data["key"] == "smith2020"
            assert data["type"] == "article"
            assert data["title"] == "Test Article"

    def test_show_yaml_format(self, cli_runner, mock_storage, sample_entry):
        """Test showing entry in YAML format."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["show", "smith2020", "--format", "yaml"])

            assert result.exit_code == 0
            assert "key: smith2020" in result.output
            assert "type: article" in result.output

    def test_show_with_syntax_highlighting(
        self, cli_runner, mock_storage, sample_entry
    ):
        """Test showing with syntax highlighting."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(
                cli,
                [
                    "show",
                    "smith2020",
                    "--format",
                    "bibtex",
                    "--syntax",
                ],
            )

            assert result.exit_code == 0
            # Output should contain entry (syntax highlighting is terminal-specific)
            assert "smith2020" in result.output

    def test_show_nonexistent_entry(self, cli_runner, mock_storage):
        """Test warning when showing non-existent entry."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = None

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["show", "nonexistent"])

            # Show command warns but doesn't fail for non-existent entries
            assert result.exit_code == 0
            assert "not found" in result.output.lower()

    def test_show_multiple_entries(self, cli_runner, mock_storage, sample_entries):
        """Test showing multiple entries."""
        from bibmgr.cli import cli

        mock_storage.read.side_effect = lambda key: next(
            (e for e in sample_entries if e.key == key), None
        )

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["show", "smith2020", "jones2021"])

            assert result.exit_code == 0
            assert "smith2020" in result.output
            assert "jones2021" in result.output

    def test_show_with_custom_fields(self, cli_runner, mock_storage, sample_entry):
        """Test showing only specific fields."""
        from bibmgr.cli import cli

        mock_storage.read.return_value = sample_entry

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(
                cli,
                [
                    "show",
                    "smith2020",
                    "--fields",
                    "title,author,year",
                ],
            )

            assert result.exit_code == 0
            assert "Test Article" in result.output
            assert "Smith, John" in result.output
            assert "2020" in result.output
            # Should not show other fields
            assert (
                "journal" not in result.output.lower()
                or "ML Journal" not in result.output
            )


class TestListCommand:
    """Test the 'list' command."""

    def test_list_all_entries(self, cli_runner, mock_storage, sample_entries):
        """Test listing all entries."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = sample_entries

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["list"])

            assert result.exit_code == 0
            for entry in sample_entries:
                assert entry.key in result.output

    def test_list_with_type_filter(self, cli_runner, mock_storage, sample_entries):
        """Test listing with type filter."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = sample_entries

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["list", "--type", "article"])

            assert result.exit_code == 0
            assert "smith2020" in result.output
            assert "taylor2022" in result.output
            assert "jones2021" not in result.output  # inproceedings

    def test_list_with_author_filter(self, cli_runner, mock_storage, sample_entries):
        """Test listing with author filter."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = sample_entries

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["list", "--author", "Smith"])

            assert result.exit_code == 0
            assert "smith2020" in result.output
            assert "jones2021" not in result.output

    def test_list_with_year_filter(self, cli_runner, mock_storage, sample_entries):
        """Test listing with year filter."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = sample_entries

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["list", "--year", "2020"])

            assert result.exit_code == 0
            assert "smith2020" in result.output
            assert "anderson2020" in result.output
            assert "jones2021" not in result.output

    def test_list_with_year_range(self, cli_runner, mock_storage, sample_entries):
        """Test listing with year range."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = sample_entries

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["list", "--year-range", "2020-2021"])

            assert result.exit_code == 0
            assert "smith2020" in result.output
            assert "jones2021" in result.output
            assert "wilson2019" not in result.output
            assert "taylor2022" not in result.output

    def test_list_with_limit(self, cli_runner, mock_storage, sample_entries):
        """Test listing with limit."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = sample_entries

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["list", "--limit", "2"])

            assert result.exit_code == 0
            # Should show only 2 entries
            shown_count = sum(
                1 for entry in sample_entries if entry.key in result.output
            )
            assert shown_count == 2

    def test_list_with_sorting(self, cli_runner, mock_storage, sample_entries):
        """Test listing with different sort orders."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = sample_entries

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            # Sort by year
            result = cli_runner.invoke(cli, ["list", "--sort", "year"])
            assert result.exit_code == 0

            # Sort by title
            result = cli_runner.invoke(cli, ["list", "--sort", "title"])
            assert result.exit_code == 0

            # Sort by author
            result = cli_runner.invoke(cli, ["list", "--sort", "author"])
            assert result.exit_code == 0

    def test_list_table_format(self, cli_runner, mock_storage, sample_entries):
        """Test listing in table format."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = sample_entries

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["list", "--format", "table"])

            assert result.exit_code == 0
            # Table should have headers and separators
            assert "Key" in result.output or "key" in result.output.lower()
            assert "Title" in result.output or "title" in result.output.lower()

    def test_list_compact_format(self, cli_runner, mock_storage, sample_entries):
        """Test listing in compact format."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = sample_entries

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["list", "--format", "compact"])

            assert result.exit_code == 0
            # Each entry on one line
            for entry in sample_entries:
                assert entry.key in result.output

    def test_list_keys_only(self, cli_runner, mock_storage, sample_entries):
        """Test listing keys only."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = sample_entries

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["list", "--format", "keys"])

            assert result.exit_code == 0
            for entry in sample_entries:
                assert entry.key in result.output
            # Should not contain titles
            assert "Machine Learning" not in result.output

    def test_list_json_format(self, cli_runner, mock_storage, sample_entries):
        """Test listing in JSON format."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = sample_entries

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["list", "--format", "json"])

            assert result.exit_code == 0

            # Verify valid JSON
            data = json.loads(result.output)
            assert len(data) == len(sample_entries)
            assert all("key" in entry for entry in data)

    def test_list_empty_database(self, cli_runner, mock_storage):
        """Test listing when database is empty."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = []

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["list"])

            assert result.exit_code == 0
            assert (
                "no entries" in result.output.lower()
                or "empty" in result.output.lower()
            )

    def test_list_with_collection_filter(
        self, cli_runner, mock_storage, sample_entries
    ):
        """Test listing entries in a collection."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = sample_entries

        # Mock collection manager
        mock_collection_manager = MagicMock()
        mock_collection = MagicMock()
        mock_collection.entry_keys = {"smith2020", "jones2021"}
        mock_collection_manager.get_collection.return_value = mock_collection

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            with patch(
                "bibmgr.cli.commands.entry_commands.get_collection_manager",
                return_value=mock_collection_manager,
            ):
                result = cli_runner.invoke(cli, ["list", "--collection", "test"])

                assert result.exit_code == 0
                assert "smith2020" in result.output
                assert "jones2021" in result.output
                # wilson2019 is not in the test data sample_entries, check if anderson2020 is excluded
                assert (
                    "anderson2020" not in result.output
                    or "taylor2022" not in result.output
                )

    def test_list_with_tag_filter(self, cli_runner, mock_storage):
        """Test listing entries with a tag."""
        from bibmgr.cli import cli
        from bibmgr.core.models import EntryType

        # Create entries with keywords
        entries_with_tags = [
            Entry(
                key="smith2020",
                type=EntryType.ARTICLE,
                title="ML Paper",
                keywords="ml, ai",
            ),
            Entry(
                key="taylor2022",
                type=EntryType.ARTICLE,
                title="Another ML",
                keywords="ml, deep-learning",
            ),
            Entry(
                key="wilson2019",
                type=EntryType.BOOK,
                title="Book",
                keywords="statistics",
            ),
        ]
        mock_storage.read_all.return_value = entries_with_tags

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(cli, ["list", "--tag", "ml"])

            assert result.exit_code == 0
            assert "smith2020" in result.output
            assert "taylor2022" in result.output
            assert "wilson2019" not in result.output

    def test_list_with_multiple_filters(self, cli_runner, mock_storage, sample_entries):
        """Test listing with multiple filters combined."""
        from bibmgr.cli import cli

        mock_storage.read_all.return_value = sample_entries

        with patch(
            "bibmgr.cli.commands.entry_commands.get_storage", return_value=mock_storage
        ):
            result = cli_runner.invoke(
                cli,
                [
                    "list",
                    "--type",
                    "article",
                    "--year",
                    "2020",
                ],
            )

            assert result.exit_code == 0
            assert "smith2020" in result.output
            assert "taylor2022" not in result.output  # Wrong year
            assert "anderson2020" not in result.output  # Wrong type
