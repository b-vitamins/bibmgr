"""Tests for metadata management CLI commands.

This module comprehensively tests metadata functionality including:
- Tag management (add, remove, rename, merge)
- Note management (add, edit, delete, list)
- Rating and read status updates
- Metadata queries and filtering
- Bulk metadata operations
"""

from unittest.mock import patch

from bibmgr.storage.metadata import EntryMetadata, Note


class TestTagCommand:
    """Test the 'bib tag' command group."""

    def test_tag_add_single(self, cli_runner, populated_repository, metadata_store):
        """Test adding a single tag to an entry."""
        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(["tag", "add", "doe2024", "quantum"])

        assert_exit_success(result)
        assert_output_contains(result, "Added tag 'quantum' to doe2024")

        # Verify tag was added
        metadata = metadata_store.get_metadata("doe2024")
        assert "quantum" in metadata.tags

    def test_tag_add_multiple(self, cli_runner, populated_repository, metadata_store):
        """Test adding multiple tags at once."""
        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(
                    ["tag", "add", "doe2024", "quantum", "computing", "important"]
                )

        assert_exit_success(result)
        assert_output_contains(result, "Added 3 tags")

        metadata = metadata_store.get_metadata("doe2024")
        assert metadata.tags == {"quantum", "computing", "important"}

    def test_tag_add_to_multiple_entries(
        self, cli_runner, populated_repository, metadata_store
    ):
        """Test adding tags to multiple entries."""
        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(
                    ["tag", "add", "--entries", "doe2024,smith2023", "review"]
                )

        assert_exit_success(result)
        assert_output_contains(result, "Added tag 'review' to 2 entries")

    def test_tag_remove(self, cli_runner, populated_repository, metadata_store):
        """Test removing tags from an entry."""
        # First add some tags
        metadata = metadata_store.get_metadata("doe2024")
        metadata.add_tags("quantum", "computing", "important")
        metadata_store.save_metadata(metadata)

        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(["tag", "remove", "doe2024", "quantum"])

        assert_exit_success(result)
        assert_output_contains(result, "Removed tag 'quantum'")

        metadata = metadata_store.get_metadata("doe2024")
        assert "quantum" not in metadata.tags
        assert "computing" in metadata.tags  # Others remain

    def test_tag_list_all(self, cli_runner, metadata_store):
        """Test listing all tags in the database."""
        # Add tags to multiple entries
        for key, tags in [
            ("doe2024", ["quantum", "computing", "important"]),
            ("smith2023", ["ml", "climate", "important"]),
            ("jones2022", ["algorithms", "textbook"]),
        ]:
            metadata = metadata_store.get_metadata(key)
            metadata.add_tags(*tags)
            metadata_store.save_metadata(metadata)

        with patch(
            "bibmgr.cli.commands.metadata.get_metadata_store",
            return_value=metadata_store,
        ):
            result = cli_runner.invoke(["tag", "list"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "important (2)",  # Used by 2 entries
            "quantum (1)",
            "ml (1)",
            "algorithms (1)",
        )

    def test_tag_list_for_entry(self, cli_runner, populated_repository, metadata_store):
        """Test listing tags for a specific entry."""
        metadata = metadata_store.get_metadata("doe2024")
        metadata.add_tags("quantum", "computing", "important")
        metadata_store.save_metadata(metadata)

        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(["tag", "list", "--entry", "doe2024"])

        assert_exit_success(result)
        assert_output_contains(
            result, "Tags for doe2024:", "quantum", "computing", "important"
        )

    def test_tag_rename(self, cli_runner, metadata_store):
        """Test renaming a tag across all entries."""
        # Add old tag to multiple entries
        for key in ["doe2024", "smith2023"]:
            metadata = metadata_store.get_metadata(key)
            metadata.add_tags("ml")
            metadata_store.save_metadata(metadata)

        with patch(
            "bibmgr.cli.commands.metadata.get_metadata_store",
            return_value=metadata_store,
        ):
            result = cli_runner.invoke(
                ["tag", "rename", "ml", "machine-learning"],
                input="y\n",  # Confirm
            )

        assert_exit_success(result)
        assert_output_contains(
            result, "Renamed tag 'ml' to 'machine-learning' in 2 entries"
        )

    def test_tag_find_entries(self, cli_runner, populated_repository, metadata_store):
        """Test finding entries by tags."""
        # Tag some entries
        for key, tags in [
            ("doe2024", ["quantum", "important"]),
            ("smith2023", ["ml", "important"]),
        ]:
            metadata = metadata_store.get_metadata(key)
            metadata.add_tags(*tags)
            metadata_store.save_metadata(metadata)

        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(["tag", "find", "important"])

        assert_exit_success(result)
        assert_output_contains(
            result, "doe2024", "smith2023", "2 entries tagged with 'important'"
        )


class TestNoteCommand:
    """Test the 'bib note' command group."""

    def test_note_add_simple(self, cli_runner, populated_repository, metadata_store):
        """Test adding a simple note to an entry."""
        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(
                    [
                        "note",
                        "add",
                        "doe2024",
                        "--content",
                        "This is a breakthrough paper",
                    ]
                )

        assert_exit_success(result)
        assert_output_contains(result, "Note added to doe2024")

        notes = metadata_store.get_notes("doe2024")
        assert len(notes) == 1
        assert notes[0].content == "This is a breakthrough paper"

    def test_note_add_interactive(
        self, cli_runner, populated_repository, metadata_store
    ):
        """Test adding a note interactively."""
        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                user_input = "\n".join(
                    [
                        "Important findings about quantum error correction",  # content
                        "summary",  # type
                        "5",  # page
                        "breakthrough,quantum",  # tags
                    ]
                )
                result = cli_runner.invoke(["note", "add", "doe2024"], input=user_input)

        assert_exit_success(result)
        notes = metadata_store.get_notes("doe2024")
        assert len(notes) == 1
        assert notes[0].note_type == "summary"
        assert notes[0].page == 5
        assert notes[0].tags == ["breakthrough", "quantum"]

    def test_note_add_with_type(self, cli_runner, populated_repository, metadata_store):
        """Test adding different types of notes."""
        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                # Add quote
                result = cli_runner.invoke(
                    [
                        "note",
                        "add",
                        "doe2024",
                        "--content",
                        "Quantum supremacy is not just about speed",
                        "--type",
                        "quote",
                        "--page",
                        "42",
                    ]
                )
                assert_exit_success(result)

                # Add idea
                result = cli_runner.invoke(
                    [
                        "note",
                        "add",
                        "doe2024",
                        "--content",
                        "Could apply this to cryptography",
                        "--type",
                        "idea",
                    ]
                )
                assert_exit_success(result)

        notes = metadata_store.get_notes("doe2024")
        assert len(notes) == 2
        assert any(n.note_type == "quote" and n.page == 42 for n in notes)
        assert any(n.note_type == "idea" for n in notes)

    def test_note_list(
        self, cli_runner, populated_repository, metadata_store, sample_notes
    ):
        """Test listing notes for an entry."""
        for note in sample_notes:
            metadata_store.add_note(note)

        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(["note", "list", "doe2024"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "Notes for doe2024",
            "Key breakthrough in error correction",
            "Quantum supremacy is not just about speed",
            "general",
            "quote",
            "Page 5",
        )

    def test_note_edit(
        self, cli_runner, populated_repository, metadata_store, sample_notes
    ):
        """Test editing an existing note."""
        note = sample_notes[0]
        metadata_store.add_note(note)

        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                with patch(
                    "bibmgr.cli.commands.metadata.open_in_editor"
                ) as mock_editor:
                    mock_editor.return_value = "Updated content for the note"
                    result = cli_runner.invoke(
                        ["note", "edit", "doe2024", str(note.id)]
                    )

        assert_exit_success(result)
        assert_output_contains(result, "Note updated")

    def test_note_delete(
        self, cli_runner, populated_repository, metadata_store, sample_notes
    ):
        """Test deleting a note."""
        note = sample_notes[0]
        metadata_store.add_note(note)

        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(
                    ["note", "delete", "doe2024", str(note.id)],
                    input="y\n",  # Confirm
                )

        assert_exit_success(result)
        assert_output_contains(result, "Note deleted")
        assert len(metadata_store.get_notes("doe2024")) == 0

    def test_note_search(self, cli_runner, populated_repository, metadata_store):
        """Test searching notes by content."""
        # Add notes to multiple entries
        notes = [
            Note(entry_key="doe2024", content="Quantum error correction breakthrough"),
            Note(entry_key="smith2023", content="Climate model improvements"),
            Note(entry_key="doe2024", content="Could revolutionize quantum computing"),
        ]
        for note in notes:
            metadata_store.add_note(note)

        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(["note", "search", "quantum"])

        assert_exit_success(result)
        assert_output_contains(result, "Found 2 notes", "doe2024")
        assert_output_not_contains(result, "smith2023")


class TestMetadataCommand:
    """Test the 'bib metadata' command for general metadata operations."""

    def test_metadata_show(
        self, cli_runner, populated_repository, metadata_store, sample_metadata
    ):
        """Test showing all metadata for an entry."""
        metadata_store.save_metadata(sample_metadata)

        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(["metadata", "show", "doe2024"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "Metadata for doe2024",
            "computing, important, quantum",  # Tags are sorted alphabetically
            "Rating",
            "★★★★★",
            "Read Status",
            "Read (2024-01-15)",
            "Importance",
            "high",
            "Notes",
            "2",
        )

    def test_metadata_set_rating(
        self, cli_runner, populated_repository, metadata_store
    ):
        """Test setting entry rating."""
        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(
                    ["metadata", "set", "doe2024", "--rating", "5"]
                )

        assert_exit_success(result)
        assert_output_contains(result, "Updated metadata for doe2024")

        metadata = metadata_store.get_metadata("doe2024")
        assert metadata.rating == 5

    def test_metadata_set_read_status(
        self, cli_runner, populated_repository, metadata_store
    ):
        """Test setting read status."""
        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(
                    ["metadata", "set", "doe2024", "--read-status", "read"]
                )

        assert_exit_success(result)

        metadata = metadata_store.get_metadata("doe2024")
        assert metadata.read_status == "read"
        assert metadata.read_date is not None

    def test_metadata_set_importance(
        self, cli_runner, populated_repository, metadata_store
    ):
        """Test setting importance level."""
        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(
                    ["metadata", "set", "doe2024", "--importance", "high"]
                )

        assert_exit_success(result)

        metadata = metadata_store.get_metadata("doe2024")
        assert metadata.importance == "high"

    def test_metadata_bulk_update(
        self, cli_runner, populated_repository, metadata_store
    ):
        """Test bulk metadata updates."""
        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(
                    [
                        "metadata",
                        "bulk-set",
                        "--entries",
                        "doe2024,smith2023,jones2022",
                        "--tag",
                        "to-review",
                        "--importance",
                        "normal",
                    ]
                )

        assert_exit_success(result)
        assert_output_contains(result, "Updated metadata for 3 entries")

        for key in ["doe2024", "smith2023", "jones2022"]:
            metadata = metadata_store.get_metadata(key)
            assert "to-review" in metadata.tags
            assert metadata.importance == "normal"

    def test_metadata_clear(
        self, cli_runner, populated_repository, metadata_store, sample_metadata
    ):
        """Test clearing metadata for an entry."""
        metadata_store.save_metadata(sample_metadata)

        with patch(
            "bibmgr.cli.commands.metadata.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.metadata.get_metadata_store",
                return_value=metadata_store,
            ):
                result = cli_runner.invoke(
                    ["metadata", "clear", "doe2024"],
                    input="y\n",  # Confirm
                )

        assert_exit_success(result)
        assert_output_contains(result, "Cleared metadata for doe2024")

        metadata = metadata_store.get_metadata("doe2024")
        assert len(metadata.tags) == 0
        assert metadata.rating is None
        assert metadata.read_status == "unread"

    def test_metadata_export(self, cli_runner, metadata_store, tmp_path):
        """Test exporting metadata to file."""
        # Add metadata for multiple entries
        for key in ["doe2024", "smith2023"]:
            metadata = EntryMetadata(
                entry_key=key,
                tags={"test", "export"},
                rating=4,
            )
            metadata_store.save_metadata(metadata)

        output_file = tmp_path / "metadata.json"

        with patch(
            "bibmgr.cli.commands.metadata.get_metadata_store",
            return_value=metadata_store,
        ):
            result = cli_runner.invoke(["metadata", "export", str(output_file)])

        assert_exit_success(result)
        assert_output_contains(result, "Exported metadata for 2 entries")
        assert output_file.exists()

    def test_metadata_import(self, cli_runner, metadata_store, tmp_path):
        """Test importing metadata from file."""
        import json

        # Create import file
        import_data = {
            "doe2024": {
                "tags": ["imported", "test"],
                "rating": 3,
                "read_status": "reading",
            },
            "smith2023": {"tags": ["imported"], "importance": "high"},
        }
        import_file = tmp_path / "import.json"
        import_file.write_text(json.dumps(import_data))

        with patch(
            "bibmgr.cli.commands.metadata.get_metadata_store",
            return_value=metadata_store,
        ):
            result = cli_runner.invoke(["metadata", "import", str(import_file)])

        assert_exit_success(result)
        assert_output_contains(result, "Imported metadata for 2 entries")

        metadata = metadata_store.get_metadata("doe2024")
        assert "imported" in metadata.tags
        assert metadata.rating == 3


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
