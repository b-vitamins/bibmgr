"""Tests for collection management CLI commands.

This module comprehensively tests collection functionality including:
- Creating collections (manual and smart)
- Listing collections with hierarchy
- Adding/removing entries from collections
- Editing collection properties
- Deleting collections
- Moving collections in hierarchy
- Exporting collection contents
"""

from unittest.mock import patch
from uuid import UUID

from bibmgr.core.models import Collection


def patch_collection_repository(collection_repository):
    """Helper to patch collection repository."""
    return patch(
        "bibmgr.cli.commands.collection.get_collection_repository",
        return_value=collection_repository,
    )


def patch_repository(repository):
    """Helper to patch entry repository."""
    return patch(
        "bibmgr.cli.commands.collection.get_repository", return_value=repository
    )


def patch_search_service(search_service):
    """Helper to patch search service."""
    return patch(
        "bibmgr.cli.commands.collection.get_search_service", return_value=search_service
    )


class TestCollectionCommand:
    """Test the 'bib collection' command group."""

    def test_collection_list_all(self, cli_runner, collection_repository):
        """Test listing all collections."""
        # Create collections with expected entry counts
        collections = [
            Collection(
                id=UUID("12345678-1234-5678-9012-123456789abc"),
                name="PhD Research",
                description="Core papers for dissertation",
                entry_keys=tuple(f"entry{i:03d}" for i in range(45)),  # 45 entries
            ),
            Collection(
                id=UUID("12345678-1234-5678-9012-123456789def"),
                name="To Read",
                description="Papers to read",
                query='read_status:"unread"',
            ),
        ]

        for collection in collections:
            collection_repository.save(collection)

        with patch(
            "bibmgr.cli.commands.collection.get_collection_repository",
            return_value=collection_repository,
        ):
            result = cli_runner.invoke(["collection", "list"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "PhD Research",
            "Core papers",
            "45",  # entry count
            "To Read",
            "Papers to read",
            "Smart",  # collection type
        )

    def test_collection_list_tree(self, cli_runner, collection_repository):
        """Test listing collections in tree view."""
        # Create hierarchical collections
        research_id = UUID("12345678-1234-5678-9012-123456789001")
        root = Collection(
            id=research_id,
            name="Research",
            description="All research papers",
            entry_keys=("entry1", "entry2"),
        )
        child1 = Collection(
            id=UUID("12345678-1234-5678-9012-123456789002"),
            name="Machine Learning",
            description="ML papers",
            parent_id=research_id,
            entry_keys=("entry1",),
        )
        child2 = Collection(
            id=UUID("12345678-1234-5678-9012-123456789003"),
            name="Quantum Computing",
            description="Quantum papers",
            parent_id=research_id,
            entry_keys=("entry2",),
        )

        for col in [root, child1, child2]:
            collection_repository.save(col)

        with patch(
            "bibmgr.cli.commands.collection.get_collection_repository",
            return_value=collection_repository,
        ):
            result = cli_runner.invoke(["collection", "list", "--tree"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "Research",
            "├── Machine Learning",
            "└── Quantum Computing",
        )

    def test_collection_create_manual(self, cli_runner, collection_repository):
        """Test creating a manual collection."""
        with patch(
            "bibmgr.cli.commands.collection.get_collection_repository",
            return_value=collection_repository,
        ):
            result = cli_runner.invoke(
                [
                    "collection",
                    "create",
                    "new-collection",
                    "--name",
                    "New Collection",
                    "--description",
                    "Test collection",
                ]
            )

        assert_exit_success(result)
        assert_output_contains(result, "Collection created successfully")

        # Verify collection was saved
        saved_collection = collection_repository.find("new-collection")
        assert saved_collection is not None
        assert saved_collection.name == "New Collection"
        assert saved_collection.description == "Test collection"

    def test_collection_create_smart(self, cli_runner, collection_repository):
        """Test creating a smart collection with query."""
        with patch(
            "bibmgr.cli.commands.collection.get_collection_repository",
            return_value=collection_repository,
        ):
            result = cli_runner.invoke(
                [
                    "collection",
                    "create",
                    "recent-ml",
                    "--name",
                    "Recent ML Papers",
                    "--query",
                    'year:2024 AND keywords:"machine learning"',
                ]
            )

        assert_exit_success(result)
        assert_output_contains(result, "Collection created successfully")

        # Verify collection was saved
        saved = collection_repository.find("recent-ml")
        assert saved is not None
        assert saved.is_smart
        assert saved.query == 'year:2024 AND keywords:"machine learning"'

    def test_collection_create_with_parent(self, cli_runner, collection_repository):
        """Test creating a collection with parent."""
        # Create parent collection first
        parent_id = UUID("12345678-1234-5678-9012-123456789004")
        parent = Collection(id=parent_id, name="Parent Collection")
        collection_repository.save(parent)

        with patch_collection_repository(collection_repository):
            result = cli_runner.invoke(
                [
                    "collection",
                    "create",
                    "child-collection",
                    "--name",
                    "Child Collection",
                    "--parent",
                    str(parent_id),
                ]
            )

        assert_exit_success(result)
        assert_output_contains(result, "Collection created successfully")

        # Verify collection was created with parent
        child = collection_repository.find("child-collection")
        assert child is not None
        assert str(child.parent_id) == str(parent_id)

    def test_collection_create_duplicate_id(
        self, cli_runner, collection_repository, sample_collections
    ):
        """Test error when creating collection with duplicate ID."""
        collection_repository.save(sample_collections[0])

        with patch_collection_repository(collection_repository):
            result = cli_runner.invoke(
                [
                    "collection",
                    "create",
                    "phd-research",
                    "--name",
                    "Duplicate",
                ]
            )

        assert_exit_failure(result)
        assert_output_contains(result, "already exists")

    def test_collection_show(
        self,
        cli_runner,
        collection_repository,
        sample_collections,
        populated_repository,
    ):
        """Test showing collection details."""
        collection = sample_collections[0]
        collection_repository.save(collection)

        with patch_collection_repository(collection_repository):
            with patch_repository(populated_repository):
                result = cli_runner.invoke(
                    ["collection", "show", "phd-research", "--entries"]
                )

        assert_exit_success(result)
        assert_output_contains(
            result,
            "PhD Research",
            "Core papers for dissertation",
            "Entries: 2",  # In the details panel
            "Entries (2):",  # In the entries list
            "doe2024",
            "Quantum Computing Advances",
        )

    def test_collection_add_entries(
        self, cli_runner, collection_repository, populated_repository
    ):
        """Test adding entries to a collection."""
        collection = Collection(
            id=UUID("12345678-1234-5678-9012-123456789005"),
            name="Test Collection",
            entry_keys=(),
        )
        collection_repository.save(collection)

        with patch_collection_repository(collection_repository):
            with patch_repository(populated_repository):
                result = cli_runner.invoke(
                    ["collection", "add", str(collection.id), "doe2024", "smith2023"]
                )

        assert_exit_success(result)
        assert_output_contains(result, "Added 2 entries")

        # Verify entries were added
        updated = collection_repository.find(str(collection.id))
        assert "doe2024" in updated.entry_keys
        assert "smith2023" in updated.entry_keys

    def test_collection_add_nonexistent_entries(
        self, cli_runner, collection_repository, entry_repository
    ):
        """Test adding nonexistent entries shows warning."""
        collection = Collection(
            id=UUID("12345678-1234-5678-9012-123456789006"), name="Test", entry_keys=()
        )
        collection_repository.save(collection)

        with patch(
            "bibmgr.cli.commands.collection.get_collection_repository",
            return_value=collection_repository,
        ):
            with patch(
                "bibmgr.cli.commands.collection.get_repository",
                return_value=entry_repository,
            ):
                result = cli_runner.invoke(
                    [
                        "collection",
                        "add",
                        str(collection.id),
                        "nonexistent1",
                        "nonexistent2",
                    ]
                )

        assert_exit_failure(result)
        assert_output_contains(result, "Entries not found")

    def test_collection_remove_entries(self, cli_runner, collection_repository):
        """Test removing entries from collection."""
        collection = Collection(
            id=UUID("12345678-1234-5678-9012-123456789007"),
            name="Test Collection",
            entry_keys=("doe2024", "smith2023", "jones2022"),
        )
        collection_repository.save(collection)

        with patch_collection_repository(collection_repository):
            result = cli_runner.invoke(
                ["collection", "remove", str(collection.id), "doe2024", "smith2023"]
            )

        assert_exit_success(result)
        assert_output_contains(result, "Removed 2 entries")

        # Verify entries were removed
        updated = collection_repository.find(str(collection.id))
        assert "doe2024" not in updated.entry_keys
        assert "smith2023" not in updated.entry_keys
        assert "jones2022" in updated.entry_keys

    def test_collection_edit(self, cli_runner, collection_repository):
        """Test editing collection properties."""
        collection = Collection(
            id=UUID("12345678-1234-5678-9012-123456789008"),
            name="Old Name",
            description="Old description",
        )
        collection_repository.save(collection)

        with patch_collection_repository(collection_repository):
            result = cli_runner.invoke(
                [
                    "collection",
                    "edit",
                    str(collection.id),
                    "--name",
                    "New Name",
                    "--description",
                    "New description",
                ]
            )

        assert_exit_success(result)
        assert_output_contains(result, "Collection updated successfully")

        # Verify changes
        updated = collection_repository.find(str(collection.id))
        assert updated.name == "New Name"
        assert updated.description == "New description"

    def test_collection_edit_convert_to_smart(self, cli_runner, collection_repository):
        """Test converting manual collection to smart collection."""
        collection = Collection(
            id=UUID("12345678-1234-5678-9012-123456789009"),
            name="Manual Collection",
            entry_keys=("entry1", "entry2"),
        )
        collection_repository.save(collection)

        with patch_collection_repository(collection_repository):
            result = cli_runner.invoke(
                [
                    "collection",
                    "edit",
                    str(collection.id),
                    "--query",
                    "year:2024",
                ]
            )

        assert_exit_success(result)
        assert_output_contains(result, "Collection updated successfully")
        assert_output_contains(result, "Note: Converted to smart collection")

        # Verify conversion
        updated = collection_repository.find(str(collection.id))
        assert updated.is_smart
        assert updated.query == "year:2024"
        assert updated.entry_keys is None

    def test_collection_delete(self, cli_runner, collection_repository):
        """Test deleting a collection."""
        collection = Collection(
            id=UUID("12345678-1234-5678-9012-12345678900a"), name="To Delete"
        )
        collection_repository.save(collection)

        with patch_collection_repository(collection_repository):
            result = cli_runner.invoke(
                ["collection", "delete", str(collection.id)],
                input="y\n",  # Confirm
            )

        assert_exit_success(result)
        assert_output_contains(
            result, "Delete collection 'To Delete'?", "Collection deleted successfully"
        )

        # Verify deletion
        assert collection_repository.find(str(collection.id)) is None

    def test_collection_delete_with_children(self, cli_runner, collection_repository):
        """Test deleting collection with children requires confirmation."""
        parent_id = UUID("12345678-1234-5678-9012-12345678900b")
        parent = Collection(id=parent_id, name="Parent")
        child = Collection(
            id=UUID("12345678-1234-5678-9012-12345678900c"),
            name="Child",
            parent_id=parent_id,
        )
        collection_repository.save(parent)
        collection_repository.save(child)

        with patch_collection_repository(collection_repository):
            result = cli_runner.invoke(
                ["collection", "delete", str(parent_id), "--recursive"],
                input="n\n",  # Don't confirm
            )

        assert_exit_success(result)
        assert_output_contains(
            result, "Collections to delete", "Parent, Child", "Cancelled"
        )

    def test_collection_move(self, cli_runner, collection_repository):
        """Test moving collection to different parent."""
        old_parent_id = UUID("12345678-1234-5678-9012-12345678900d")
        new_parent_id = UUID("12345678-1234-5678-9012-12345678900e")
        collection = Collection(
            id=UUID("12345678-1234-5678-9012-12345678900f"),
            name="To Move",
            parent_id=old_parent_id,
        )
        new_parent = Collection(id=new_parent_id, name="New Parent")
        collection_repository.save(collection)
        collection_repository.save(new_parent)

        with patch_collection_repository(collection_repository):
            result = cli_runner.invoke(
                [
                    "collection",
                    "move",
                    str(collection.id),
                    "--to",
                    str(new_parent_id),
                ]
            )

        assert_exit_success(result)
        assert_output_contains(result, "Collection moved")

    def test_collection_export(
        self, cli_runner, collection_repository, populated_repository, tmp_path
    ):
        """Test exporting collection entries."""
        collection = Collection(
            id=UUID("12345678-1234-5678-9012-123456789010"),
            name="To Export",
            entry_keys=("doe2024", "smith2023"),
        )
        collection_repository.save(collection)

        output_file = tmp_path / "export.bib"

        with patch(
            "bibmgr.cli.commands.collection.get_collection_repository",
            return_value=collection_repository,
        ):
            with patch(
                "bibmgr.cli.commands.collection.get_repository",
                return_value=populated_repository,
            ):
                result = cli_runner.invoke(
                    [
                        "collection",
                        "export",
                        str(collection.id),
                        str(output_file),
                    ]
                )

        assert_exit_success(result)
        assert_output_contains(result, "Exported 2 entries")
        assert output_file.exists()

    def test_collection_stats(
        self, cli_runner, collection_repository, populated_repository
    ):
        """Test showing collection statistics."""
        # Create collections with different properties
        collections = [
            Collection(
                id=UUID("12345678-1234-5678-9012-123456789011"),
                name="Large",
                entry_keys=("e1", "e2", "e3", "e4", "e5"),
            ),
            Collection(
                id=UUID("12345678-1234-5678-9012-123456789012"),
                name="Smart",
                query="year:2024",
            ),
            Collection(
                id=UUID("12345678-1234-5678-9012-123456789013"),
                name="Empty",
                entry_keys=(),
            ),
        ]
        for col in collections:
            collection_repository.save(col)

        with patch(
            "bibmgr.cli.commands.collection.get_collection_repository",
            return_value=collection_repository,
        ):
            result = cli_runner.invoke(["collection", "stats"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "Total collections",
            "3",
            "Manual collections",
            "2",
            "Smart collections",
            "1",
            "Average size",
        )


class TestCollectionsCommand:
    """Test the 'bib collections' shortcut command."""

    def test_collections_list_shortcut(
        self, cli_runner, collection_repository, sample_collections
    ):
        """Test that 'bib collections' is shortcut for 'bib collection list'."""
        for collection in sample_collections:
            collection_repository.save(collection)

        with patch(
            "bibmgr.cli.commands.collection.get_collection_repository",
            return_value=collection_repository,
        ):
            result = cli_runner.invoke(["collections"])

        assert_exit_success(result)
        assert_output_contains(result, "PhD Research", "To Read")

    def test_collections_with_entry_filter(self, cli_runner, collection_repository):
        """Test listing collections containing specific entry."""
        collections = [
            Collection(
                id=UUID("12345678-1234-5678-9012-123456789014"),
                name="Collection 1",
                entry_keys=("doe2024", "smith2023"),
            ),
            Collection(
                id=UUID("12345678-1234-5678-9012-123456789015"),
                name="Collection 2",
                entry_keys=("smith2023",),
            ),
            Collection(
                id=UUID("12345678-1234-5678-9012-123456789016"),
                name="Collection 3",
                entry_keys=("jones2022",),
            ),
        ]
        for col in collections:
            collection_repository.save(col)

        with patch(
            "bibmgr.cli.commands.collection.get_collection_repository",
            return_value=collection_repository,
        ):
            result = cli_runner.invoke(["collections", "--containing", "smith2023"])

        assert_exit_success(result)
        assert_output_contains(result, "Collection 1", "Collection 2")
        assert_output_not_contains(result, "Collection 3")

    def test_collections_empty(self, cli_runner, collection_repository):
        """Test when no collections exist."""
        with patch(
            "bibmgr.cli.commands.collection.get_collection_repository",
            return_value=collection_repository,
        ):
            result = cli_runner.invoke(["collections"])

        assert_exit_success(result)
        assert_output_contains(result, "No collections found")


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
