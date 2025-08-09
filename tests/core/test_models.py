"""Tests for core bibliography entry and collection models.

This module tests the Entry and Collection models for proper BibTeX compliance,
immutability, computed properties, and hierarchical organization.
"""

import time
import uuid
from datetime import datetime
from typing import Any

import msgspec
import pytest

from bibmgr.core.fields import EntryType
from bibmgr.core.models import Collection, Entry, Tag, ValidationError


class TestEntryCreation:
    """Test Entry model creation and basic functionality."""

    def test_create_minimal_article(self, sample_article_data: dict[str, Any]) -> None:
        """Create a minimal valid article entry."""
        entry = Entry(**sample_article_data)

        assert entry.key == "knuth1984"
        assert entry.type == EntryType.ARTICLE
        assert entry.author == "Donald E. Knuth"
        assert entry.title == "The {TeX}book"
        assert entry.journal == "Computers & Typesetting"
        assert entry.year == 1984

    def test_create_entry_with_all_fields(self) -> None:
        """Create an entry with many fields populated."""
        entry = Entry(
            key="comprehensive2024",
            type=EntryType.ARTICLE,
            # Standard fields
            author="Jane Doe and John Smith",
            title="A Comprehensive Study",
            journal="Nature",
            year=2024,
            volume="600",
            number="1",
            pages="1--20",
            month="jan",
            note="Forthcoming",
            # Modern fields
            doi="10.1038/nature.2024.12345",
            url="https://example.com",
            abstract="This is a test abstract.",
            keywords=("test", "comprehensive", "study"),
            # Additional fields
            tags=("important", "review"),
        )

        assert entry.volume == "600"
        assert entry.doi == "10.1038/nature.2024.12345"
        assert entry.keywords == ("test", "comprehensive", "study")
        assert entry.tags == ("important", "review")

    def test_create_entry_from_dict(self, sample_book_data: dict[str, Any]) -> None:
        """Create entry using from_dict class method."""
        entry = Entry.from_dict(sample_book_data)

        assert entry.key == "latex2e"
        assert entry.type == EntryType.BOOK
        assert entry.publisher == "Addison-Wesley"

    def test_entry_type_conversion_in_from_dict(self) -> None:
        """Entry type string should be converted to EntryType enum."""
        data = {
            "key": "test",
            "type": "article",  # String, not enum
            "author": "Test Author",
            "title": "Test Title",
            "journal": "Test Journal",
            "year": 2024,
        }

        entry = Entry.from_dict(data)
        assert isinstance(entry.type, EntryType)
        assert entry.type == EntryType.ARTICLE

    def test_timestamps_auto_populated(self) -> None:
        """Added and modified timestamps should be auto-populated."""
        before = datetime.now()
        entry = Entry(key="test", type=EntryType.MISC, title="Test")
        after = datetime.now()

        assert before <= entry.added <= after
        assert before <= entry.modified <= after
        # Timestamps should be very close (within 1ms)
        assert abs((entry.modified - entry.added).total_seconds()) < 0.001

    def test_empty_fields_as_none(self) -> None:
        """Empty string fields should be treated as None."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="",  # Empty string
            title=None,  # Explicit None
            journal="Nature",
            year=2024,
        )

        # Model should handle this in validation/processing
        assert entry.author == ""  # Kept as-is (validation will handle)
        assert entry.title is None


class TestEntryImmutability:
    """Test Entry immutability constraints."""

    def test_entry_is_frozen(self, sample_article_data: dict[str, Any]) -> None:
        """Entry instances must be immutable (frozen)."""
        entry = Entry(**sample_article_data)

        with pytest.raises(AttributeError):
            entry.title = "New Title"  # type: ignore

    def test_cannot_modify_entry_fields(
        self, sample_article_data: dict[str, Any]
    ) -> None:
        """No entry fields should be modifiable after creation."""
        entry = Entry(**sample_article_data)

        # Try to modify various field types
        with pytest.raises(AttributeError):
            entry.year = 2025  # type: ignore

        with pytest.raises(AttributeError):
            entry.tags = ["new", "tags"]  # type: ignore

        with pytest.raises(AttributeError):
            entry.type = EntryType.BOOK  # type: ignore

    def test_list_fields_are_immutable(self) -> None:
        """List fields like keywords and tags must be immutable."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Test",
            title="Test",
            journal="Test",
            year=2024,
            keywords=("original", "keywords"),
            tags=("tag1", "tag2"),
        )

        # Should be tuples, not lists
        assert isinstance(entry.keywords, tuple)
        assert isinstance(entry.tags, tuple)

        # Tuples don't have append method
        with pytest.raises(AttributeError):
            entry.keywords.append("new")  # type: ignore

        # Tuples don't support item assignment
        with pytest.raises(TypeError):
            entry.tags[0] = "modified"  # type: ignore

    def test_msgspec_replace_creates_new_instance(
        self, sample_article_data: dict[str, Any]
    ) -> None:
        """Using msgspec.structs.replace should create a new instance."""
        entry1 = Entry(**sample_article_data)
        entry2 = msgspec.structs.replace(entry1, title="New Title")

        assert entry1 is not entry2
        assert entry1.title == "The {TeX}book"
        assert entry2.title == "New Title"
        assert entry1.key == entry2.key  # Other fields unchanged


class TestEntryComputedProperties:
    """Test Entry computed properties and caching."""

    def test_authors_property_parses_names(self) -> None:
        """The authors property should parse author field into tuple."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Donald E. Knuth and Leslie Lamport and Alan M. Turing",
            title="Test",
            journal="Test",
            year=2024,
        )

        assert entry.authors == ("Donald E. Knuth", "Leslie Lamport", "Alan M. Turing")

    def test_authors_handles_escaped_ampersand(self) -> None:
        """Authors parsing must handle \\& correctly."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Barnes \\& Noble and Smith \\& Wesson",
            title="Test",
            journal="Test",
            year=2024,
        )

        assert entry.authors == ("Barnes & Noble", "Smith & Wesson")

    def test_authors_empty_when_no_author(self) -> None:
        """Authors property returns empty tuple when no author field."""
        entry = Entry(
            key="test",
            type=EntryType.PROCEEDINGS,
            title="Test Proceedings",
            year=2024,
        )

        assert entry.authors == ()

    def test_editors_property_parses_names(self) -> None:
        """The editors property should parse editor field into tuple."""
        entry = Entry(
            key="test",
            type=EntryType.BOOK,
            editor="Jane Doe and John Smith",
            title="Edited Volume",
            publisher="Publisher",
            year=2024,
        )

        assert entry.editors == ("Jane Doe", "John Smith")

    def test_search_text_includes_all_relevant_fields(self) -> None:
        """Search text should concatenate all searchable fields."""
        entry = Entry(
            key="searchtest2024",
            type=EntryType.ARTICLE,
            author="Test Author",
            title="Search Test Article",
            journal="Journal of Testing",
            year=2024,
            abstract="This is a test abstract with keywords.",
            keywords=("search", "test", "example"),
            tags=("important",),
        )

        search_text = entry.search_text

        # Should include all text fields
        assert "searchtest2024" in search_text
        assert "test author" in search_text  # Lowercase
        assert "search test article" in search_text
        assert "journal of testing" in search_text
        assert "2024" in search_text
        assert "test abstract" in search_text
        assert "search" in search_text  # From keywords
        assert "important" in search_text  # From tags
        assert "article" in search_text  # Entry type

    def test_computed_properties_are_cached(self) -> None:
        """Computed properties must be cached for performance."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Author One and Author Two and Author Three",
            title="Test Article",
            journal="Test Journal",
            year=2024,
            abstract="Long abstract " * 100,
            keywords=tuple("keyword" + str(i) for i in range(50)),
        )

        # First access
        start = time.perf_counter()
        authors1 = entry.authors
        first_time = time.perf_counter() - start

        # Second access should be much faster (cached)
        start = time.perf_counter()
        authors2 = entry.authors
        second_time = time.perf_counter() - start

        # Should be the same object (cached)
        assert authors1 is authors2

        # Second access should be at least 2x faster
        # (In practice, it's usually 100x+ faster)
        if first_time > 0:  # Avoid division by zero
            assert second_time < first_time * 0.5

    def test_to_dict_excludes_none_values(
        self, sample_article_data: dict[str, Any]
    ) -> None:
        """to_dict should exclude None values."""
        entry = Entry(**sample_article_data)
        data = entry.to_dict()

        # Should have the provided fields
        assert "author" in data
        assert "title" in data

        # Should not have None fields
        for key, value in data.items():
            assert value is not None


class TestEntryValidation:
    """Test Entry validation integration."""

    def test_entry_validate_method_returns_errors(self) -> None:
        """Entry.validate() should return list of validation errors."""
        # Create invalid entry
        entry = Entry(
            key="invalid key with spaces",
            type=EntryType.ARTICLE,
            author="",  # Empty required field
            title="Test",
            journal="Test",
            year=2024,
        )

        errors = entry.validate()
        assert isinstance(errors, list)
        assert len(errors) > 0
        assert all(isinstance(e, ValidationError) for e in errors)

    def test_valid_entry_returns_no_errors(
        self, sample_article_data: dict[str, Any]
    ) -> None:
        """Valid entry should return empty error list."""
        entry = Entry(**sample_article_data)
        errors = entry.validate()
        assert errors == []

    def test_to_bibtex_method_exists(self, sample_article_data: dict[str, Any]) -> None:
        """Entry should have to_bibtex method."""
        entry = Entry(**sample_article_data)
        bibtex = entry.to_bibtex()
        assert isinstance(bibtex, str)
        assert bibtex.startswith("@article{knuth1984,")


class TestCollectionCreation:
    """Test Collection model creation."""

    def test_create_manual_collection(self) -> None:
        """Create a manual collection with entry keys."""
        collection = Collection(
            name="My Papers",
            description="Personal paper collection",
            entry_keys=("paper1", "paper2", "paper3"),
            color="#FF6B6B",
            icon="folder",
        )

        assert collection.name == "My Papers"
        assert collection.entry_keys == ("paper1", "paper2", "paper3")
        assert collection.query is None
        assert not collection.is_smart

    def test_create_smart_collection(self) -> None:
        """Create a smart collection with search query."""
        collection = Collection(
            name="Recent ML Papers",
            description="Machine learning papers from 2023-2024",
            query="keywords:machine-learning AND year:2023..2024",
            color="#4ECDC4",
        )

        assert collection.name == "Recent ML Papers"
        assert collection.query == "keywords:machine-learning AND year:2023..2024"
        assert collection.entry_keys is None
        assert collection.is_smart

    def test_cannot_have_both_entries_and_query(self) -> None:
        """Collection cannot have both entry_keys and query."""
        with pytest.raises(ValueError, match="cannot have both"):
            Collection(
                name="Invalid",
                entry_keys=("key1",),
                query="year:2024",
            )

    def test_auto_generated_uuid(self) -> None:
        """Collection should auto-generate UUID."""
        collection = Collection(name="Test")
        assert isinstance(collection.id, uuid.UUID)

    def test_timestamps_auto_populated_collection(self) -> None:
        """Collection timestamps should be auto-populated."""
        before = datetime.now()
        collection = Collection(name="Test")
        after = datetime.now()

        assert before <= collection.created <= after
        assert before <= collection.modified <= after

    def test_empty_manual_collection_gets_empty_list(self) -> None:
        """Manual collection without entries gets empty list."""
        collection = Collection(name="Empty", entry_keys=())
        assert collection.entry_keys == ()
        assert not collection.is_smart


class TestCollectionHierarchy:
    """Test Collection hierarchical organization."""

    def test_collection_with_parent(self) -> None:
        """Collection can have parent_id for hierarchy."""
        parent_id = uuid.uuid4()
        child = Collection(
            name="Neural Networks",
            parent_id=parent_id,
        )

        assert child.parent_id == parent_id

    def test_get_path_single_level(self) -> None:
        """get_path returns just name for root collection."""
        collection = Collection(name="Root Collection")

        # Mock storage for testing
        class MockStorage:
            def get_collection(self, cid: uuid.UUID) -> None:
                return None

        path = collection.get_path(MockStorage())
        assert path == "Root Collection"

    def test_get_path_nested_hierarchy(self) -> None:
        """get_path returns full hierarchical path."""
        # Create hierarchy: Science > Physics > Quantum
        science = Collection(name="Science")
        physics = Collection(name="Physics", parent_id=science.id)
        quantum = Collection(name="Quantum", parent_id=physics.id)

        # Mock storage
        class MockStorage:
            def __init__(self):
                self.collections = {
                    science.id: science,
                    physics.id: physics,
                    quantum.id: quantum,
                }

            def get_collection(self, cid: uuid.UUID) -> Collection:
                return self.collections.get(cid)  # type: ignore

        storage = MockStorage()
        path = quantum.get_path(storage)
        assert path == "Science > Physics > Quantum"

    def test_get_path_returns_names_not_ids(self) -> None:
        """get_path must return collection names, not UUIDs."""
        parent = Collection(name="Parent Collection")
        child = Collection(name="Child Collection", parent_id=parent.id)

        class MockStorage:
            def get_collection(self, cid: uuid.UUID) -> Collection:
                return parent

        path = child.get_path(MockStorage())
        assert str(parent.id) not in path  # No UUIDs in path
        assert "Parent Collection" in path
        assert "Child Collection" in path


class TestCollectionOperations:
    """Test Collection modification operations."""

    def test_add_entry_to_manual_collection(self) -> None:
        """Add entry to manual collection."""
        collection = Collection(
            name="Test",
            entry_keys=("key1", "key2"),
        )

        new_collection = collection.add_entry("key3")

        # Original unchanged (immutable)
        assert collection.entry_keys == ("key1", "key2")

        # New collection has added entry
        assert new_collection.entry_keys == ("key1", "key2", "key3")
        assert new_collection.modified > collection.modified

    def test_add_duplicate_entry_ignored(self) -> None:
        """Adding duplicate entry should be ignored."""
        collection = Collection(
            name="Test",
            entry_keys=("key1", "key2"),
        )

        new_collection = collection.add_entry("key1")  # Duplicate
        assert new_collection.entry_keys == ("key1", "key2")  # Unchanged

    def test_cannot_add_to_smart_collection(self) -> None:
        """Cannot add entries to smart collection."""
        collection = Collection(
            name="Smart",
            query="year:2024",
        )

        with pytest.raises(ValueError, match="Cannot add entries to smart collection"):
            collection.add_entry("key1")

    def test_remove_entry_from_collection(self) -> None:
        """Remove entry from manual collection."""
        collection = Collection(
            name="Test",
            entry_keys=("key1", "key2", "key3"),
        )

        new_collection = collection.remove_entry("key2")

        assert collection.entry_keys == ("key1", "key2", "key3")  # Original unchanged
        assert new_collection.entry_keys == ("key1", "key3")
        assert new_collection.modified > collection.modified

    def test_remove_nonexistent_entry(self) -> None:
        """Removing non-existent entry should work without error."""
        collection = Collection(
            name="Test",
            entry_keys=("key1", "key2"),
        )

        new_collection = collection.remove_entry("key99")
        assert new_collection.entry_keys == ("key1", "key2")  # Unchanged

    def test_cannot_remove_from_smart_collection(self) -> None:
        """Cannot remove entries from smart collection."""
        collection = Collection(
            name="Smart",
            query="year:2024",
        )

        with pytest.raises(
            ValueError, match="Cannot remove entries from smart collection"
        ):
            collection.remove_entry("key1")

    def test_collection_immutability(self) -> None:
        """Collection instances must be immutable."""
        collection = Collection(name="Test")

        with pytest.raises(AttributeError):
            collection.name = "New Name"  # type: ignore

        with pytest.raises(AttributeError):
            collection.entry_keys = ("new",)  # type: ignore


class TestTagModel:
    """Test Tag model functionality."""

    def test_create_simple_tag(self) -> None:
        """Create a simple tag."""
        tag = Tag(name="important")
        assert tag.name == "important"
        assert tag.color is None

    def test_create_tag_with_color(self) -> None:
        """Create tag with color."""
        tag = Tag(name="urgent", color="#FF0000")
        assert tag.name == "urgent"
        assert tag.color == "#FF0000"

    def test_tag_string_representation(self) -> None:
        """Tag string representation is its name."""
        tag = Tag(name="review", color="#00FF00")
        assert str(tag) == "review"

    def test_tag_immutability(self) -> None:
        """Tag must be immutable."""
        tag = Tag(name="test")

        with pytest.raises(AttributeError):
            tag.name = "modified"  # type: ignore


class TestValidationErrorModel:
    """Test ValidationError model."""

    def test_create_validation_error(self) -> None:
        """Create validation error with all fields."""
        error = ValidationError(
            field="year",
            message="Year must be a valid integer",
            severity="error",
            entry_key="smith2024",
        )

        assert error.field == "year"
        assert error.message == "Year must be a valid integer"
        assert error.severity == "error"
        assert error.entry_key == "smith2024"

    def test_validation_error_severities(self) -> None:
        """Test different severity levels."""
        error = ValidationError(field=None, message="Error", severity="error")
        warning = ValidationError(field=None, message="Warning", severity="warning")
        info = ValidationError(field=None, message="Info", severity="info")

        assert error.severity == "error"
        assert warning.severity == "warning"
        assert info.severity == "info"

    def test_validation_error_without_field(self) -> None:
        """Validation error can be for entire entry."""
        error = ValidationError(
            field=None,
            message="Entry has inconsistent fields",
            severity="warning",
        )

        assert error.field is None
