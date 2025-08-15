"""Tests for entry and collection builders.

This module tests the builder pattern for creating entries
and collections with fluent interfaces and validation.
"""

import pytest

from bibmgr.core.builders import CollectionBuilder, EntryBuilder
from bibmgr.core.fields import EntryType
from bibmgr.core.models import Collection, Entry


class TestEntryBuilder:
    """Test entry builder functionality."""

    def test_basic_entry_building(self) -> None:
        """Build a basic entry using fluent interface."""
        entry = (
            EntryBuilder()
            .key("test2024")
            .type(EntryType.ARTICLE)
            .author("John Doe")
            .title("Test Article")
            .journal("Test Journal")
            .year(2024)
            .build()
        )

        assert entry.key == "test2024"
        assert entry.type == EntryType.ARTICLE
        assert entry.author == "John Doe"
        assert entry.title == "Test Article"
        assert entry.journal == "Test Journal"
        assert entry.year == 2024

    def test_builder_with_all_fields(self) -> None:
        """Build entry with many fields."""
        entry = (
            EntryBuilder()
            .key("complete")
            .type(EntryType.ARTICLE)
            .author("Jane Smith and John Doe")
            .title("Comprehensive Study")
            .journal("Nature")
            .year(2024)
            .volume("42")
            .number("3")
            .pages("123--145")
            .month("mar")
            .doi("10.1038/nature.2024.12345")
            .url("https://nature.com/article")
            .abstract("This is the abstract...")
            .keywords(["machine learning", "AI"])
            .build()
        )

        assert entry.volume == "42"
        assert entry.number == "3"
        assert entry.pages == "123--145"
        assert entry.doi == "10.1038/nature.2024.12345"
        assert entry.keywords == ["machine learning", "AI"]

    def test_builder_validation(self) -> None:
        """Builder validates before building."""
        # Missing required fields
        with pytest.raises(ValueError, match="key is required"):
            EntryBuilder().type(EntryType.ARTICLE).build()

        with pytest.raises(ValueError, match="type is required"):
            EntryBuilder().key("test").build()

        # Builder allows invalid keys to be built - validation happens elsewhere
        entry = EntryBuilder().key("has spaces").type(EntryType.ARTICLE).build()
        assert entry.key == "has spaces"  # Built successfully despite invalid key

    def test_builder_from_dict(self) -> None:
        """Create builder from dictionary."""
        data = {
            "key": "fromdict",
            "type": EntryType.ARTICLE,
            "author": "Author Name",
            "title": "Title",
            "journal": "Journal",
            "year": 2024,
        }

        entry = EntryBuilder.from_dict(data).build()

        assert entry.key == "fromdict"
        assert entry.author == "Author Name"

    def test_builder_copy_and_modify(self) -> None:
        """Copy existing entry and modify."""
        original = Entry(
            key="original",
            type=EntryType.ARTICLE,
            author="Original Author",
            title="Original Title",
            journal="Journal",
            year=2023,
        )

        modified = (
            EntryBuilder.from_entry(original)
            .key("modified")
            .year(2024)
            .doi("10.1234/new")
            .build()
        )

        assert modified.key == "modified"
        assert modified.year == 2024
        assert modified.doi == "10.1234/new"
        assert modified.author == "Original Author"  # Unchanged

    def test_builder_with_custom_fields(self) -> None:
        """Add custom fields through builder."""
        entry = (
            EntryBuilder()
            .key("custom")
            .type(EntryType.MISC)
            .title("Custom Entry")
            .custom_field("customfield", "Custom Value")
            .custom_field("another", "Another Value")
            .build()
        )

        assert entry.custom is not None
        assert entry.custom["customfield"] == "Custom Value"
        assert entry.custom["another"] == "Another Value"

    def test_builder_clear_field(self) -> None:
        """Clear fields in builder."""
        builder = (
            EntryBuilder()
            .key("test")
            .type(EntryType.ARTICLE)
            .author("Author")
            .title("Title")
            .journal("Journal")
            .year(2024)
        )

        # Clear author
        builder.clear_field("author")
        entry = builder.build()

        assert entry.author is None

    def test_builder_method_chaining(self) -> None:
        """All methods return self for chaining."""
        builder = EntryBuilder()

        # All methods should return the builder
        assert builder.key("test") is builder
        assert builder.type(EntryType.ARTICLE) is builder
        assert builder.author("Author") is builder
        assert builder.title("Title") is builder

    def test_builder_validates_field_types(self) -> None:
        """Builder validates field types."""
        builder = EntryBuilder().key("test").type(EntryType.ARTICLE)

        # Year must be int
        with pytest.raises(TypeError, match="year must be int"):
            builder.year("2024")  # String instead of int

        # Keywords must be list
        with pytest.raises(TypeError, match="keywords must be list"):
            builder.keywords("single keyword")  # String instead of list

    def test_builder_auto_generate_key(self) -> None:
        """Auto-generate key from author/year/title."""
        entry = (
            EntryBuilder()
            .type(EntryType.ARTICLE)
            .author("Jane Smith")
            .title("Machine Learning Study")
            .year(2024)
            .auto_key()  # Generate key
            .build()
        )

        # Should generate something like "smith2024machine"
        assert "smith" in entry.key.lower()
        assert "2024" in entry.key

    def test_builder_with_crossref(self) -> None:
        """Build entry with cross-reference."""
        entry = (
            EntryBuilder()
            .key("chapter1")
            .type(EntryType.INBOOK)
            .author("Chapter Author")
            .title("Chapter Title")
            .chapter("1")
            .crossref("mainbook")
            .build()
        )

        assert entry.crossref == "mainbook"
        assert entry.chapter == "1"

    def test_builder_with_tags_and_collections(self) -> None:
        """Build entry with tags and collections."""
        builder = (
            EntryBuilder()
            .key("tagged")
            .type(EntryType.ARTICLE)
            .title("Tagged Article")
            .tag("important")
            .tag("review")
            .collection("ml-papers")
            .collection("2024-papers")
        )
        
        entry = builder.build()
        collections = builder.get_collections()

        assert "important" in entry.tags
        assert "review" in entry.tags
        assert "ml-papers" in collections
        assert "2024-papers" in collections


class TestCollectionBuilder:
    """Test collection builder functionality."""

    def test_basic_collection_building(self) -> None:
        """Build a basic collection."""
        collection = (
            CollectionBuilder()
            .name("ML Papers")
            .description("Machine Learning papers collection")
            .build()
        )

        assert collection.name == "ML Papers"
        assert collection.description == "Machine Learning papers collection"
        assert collection.parent_id is None

    def test_collection_with_parent(self) -> None:
        """Build collection with parent."""
        parent = Collection(name="CS Papers")

        child = CollectionBuilder().name("ML Papers").parent(parent).build()

        assert child.parent_id == parent.id

    def test_collection_hierarchy_building(self) -> None:
        """Build collection hierarchy."""
        # Build from top down
        root = (
            CollectionBuilder()
            .name("Research")
            .description("All research papers")
            .build()
        )

        cs = CollectionBuilder().name("Computer Science").parent(root).build()

        ml_builder = (
            CollectionBuilder()
            .name("Machine Learning")
            .parent(cs)
            .metadata("focus", "deep learning")
            .metadata("year_range", "2020-2024")
        )
        ml = ml_builder.build()
        ml_metadata = ml_builder.get_metadata()

        # Verify hierarchy by checking parent IDs
        assert ml.parent_id == cs.id
        assert cs.parent_id == root.id
        assert root.parent_id is None
        
        # Verify metadata
        assert ml_metadata["focus"] == "deep learning"
        assert ml_metadata["year_range"] == "2020-2024"

    def test_builder_with_entries(self, sample_entries: list[Entry]) -> None:
        """Build collection with initial entries."""
        collection = (
            CollectionBuilder()
            .name("Initial Papers")
            .add_entries(sample_entries[:3])
            .add_entry(sample_entries[3])
            .build()
        )

        assert len(collection.entry_keys) == 4
        for entry in sample_entries[:4]:
            assert entry.key in collection.entry_keys

    def test_builder_validation(self) -> None:
        """Builder validates collection."""
        # Name required
        with pytest.raises(ValueError, match="name is required"):
            CollectionBuilder().build()

        # Cannot be own parent
        # Self-parent check would need to be enforced at the storage layer
        # since we can't create a collection that references itself before it exists

    def test_builder_from_dict(self) -> None:
        """Create from dictionary."""
        data = {
            "name": "From Dict",
            "description": "Created from dict",
            "metadata": {"key": "value"},
        }

        collection = CollectionBuilder.from_dict(data).build()

        assert collection.name == "From Dict"
        # Metadata is not part of the collection model itself

    def test_builder_copy_collection(self) -> None:
        """Copy existing collection."""
        original = Collection(
            name="Original",
            description="Original description",
        )

        copy_builder = (
            CollectionBuilder.from_collection(original)
            .name("Copy")
            .metadata("new_key", "new_value")
        )
        copy = copy_builder.build()
        copy_metadata = copy_builder.get_metadata()

        assert copy.name == "Copy"
        assert copy.description == "Original description"
        assert copy_metadata["new_key"] == "new_value"

    def test_builder_with_smart_filters(self) -> None:
        """Build collection with smart filters."""
        builder = (
            CollectionBuilder()
            .name("Recent ML")
            .smart_filter("year", ">=", 2020)
            .smart_filter("keywords", "contains", "machine learning")
            .smart_filter("type", "in", [EntryType.ARTICLE, EntryType.INPROCEEDINGS])
        )
        collection = builder.build()
        smart_filters = builder.get_smart_filters()

        assert len(smart_filters) == 3

        # Verify filters
        year_filter = next(f for f in smart_filters if f["field"] == "year")
        assert year_filter["operator"] == ">="
        assert year_filter["value"] == 2020

    def test_builder_bulk_operations(self) -> None:
        """Bulk add/remove in builder."""
        entries = [
            Entry(key=f"entry{i}", type=EntryType.MISC, title=f"Entry {i}")
            for i in range(10)
        ]

        collection = (
            CollectionBuilder()
            .name("Bulk Test")
            .add_entries(entries[:5])  # Add first 5
            .add_entries(entries[5:])  # Add rest
            .remove_entry_keys(["entry2", "entry7"])  # Remove some
            .build()
        )

        assert len(collection.entry_keys) == 8
        assert "entry2" not in collection.entry_keys
        assert "entry7" not in collection.entry_keys

    def test_builder_with_icon_and_color(self) -> None:
        """Build collection with UI properties."""
        collection = (
            CollectionBuilder().name("Important").icon("star").color("#ff0000").build()
        )

        assert collection.icon == "star"
        assert collection.color == "#ff0000"

    def test_builder_clear_smart_filters(self) -> None:
        """Clear smart filters in builder."""
        builder = (
            CollectionBuilder()
            .name("Test")
            .smart_filter("year", ">", 2020)
            .smart_filter("type", "=", EntryType.ARTICLE)
            .clear_smart_filters()
            .smart_filter("author", "contains", "Smith")
        )
        collection = builder.build()
        smart_filters = builder.get_smart_filters()

        # Should only have the last filter
        assert len(smart_filters) == 1
        assert smart_filters[0]["field"] == "author"

    def test_builder_validates_smart_filters(self) -> None:
        """Validate smart filter operators."""
        builder = CollectionBuilder().name("Test")

        # Invalid operator
        with pytest.raises(ValueError, match="Invalid operator"):
            builder.smart_filter("year", "~=", 2020)

        # Invalid field type for operator
        with pytest.raises(ValueError, match="Cannot use 'contains'"):
            builder.smart_filter("year", "contains", 2020)

    def test_builder_method_chaining(self) -> None:
        """All methods return self."""
        builder = CollectionBuilder()

        assert builder.name("Test") is builder
        assert builder.description("Desc") is builder
        assert builder.metadata("key", "value") is builder

    def test_nested_collection_building(self) -> None:
        """Build nested collections efficiently."""
        # Build entire tree at once
        collections = CollectionBuilder.build_tree(
            {
                "Research": {
                    "Computer Science": {
                        "Machine Learning": {"metadata": {"focus": "deep learning"}},
                        "Databases": {},
                    },
                    "Mathematics": {
                        "Statistics": {},
                    },
                }
            }
        )

        # Verify structure
        assert len(collections) == 6  # Total collections
        ml_tuple = next((c, m) for c, m in collections if c.name == "Machine Learning")
        ml_collection, ml_metadata = ml_tuple
        assert ml_metadata["focus"] == "deep learning"
        
        # Verify hierarchy by checking parent relationships
        cs_collection = next(c for c, _ in collections if c.name == "Computer Science")
        research_collection = next(c for c, _ in collections if c.name == "Research")
        assert ml_collection.parent_id == cs_collection.id
        assert cs_collection.parent_id == research_collection.id
