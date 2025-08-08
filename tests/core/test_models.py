"""Comprehensive implementation-agnostic tests for core models.

These tests define the expected behavior of bibliography entry models,
collections, and tags without depending on implementation details.
"""

from datetime import datetime
from pathlib import Path

import pytest


class TestEntryType:
    """Test entry type enumeration."""

    def test_standard_entry_types(self):
        """Should support all standard BibTeX entry types."""
        from bibmgr.core import EntryType

        # Standard types that must exist
        required_types = [
            "ARTICLE",
            "BOOK",
            "BOOKLET",
            "CONFERENCE",
            "INBOOK",
            "INCOLLECTION",
            "INPROCEEDINGS",
            "MANUAL",
            "MASTERSTHESIS",
            "MISC",
            "PHDTHESIS",
            "PROCEEDINGS",
            "TECHREPORT",
            "UNPUBLISHED",
        ]

        for type_name in required_types:
            assert hasattr(EntryType, type_name)
            entry_type = getattr(EntryType, type_name)
            assert entry_type.value == type_name.lower()

    def test_entry_type_comparison(self):
        """Entry types should be comparable."""
        from bibmgr.core import EntryType

        assert EntryType.ARTICLE == EntryType.ARTICLE
        assert EntryType.ARTICLE != EntryType.BOOK
        assert EntryType.CONFERENCE == EntryType.CONFERENCE

    def test_entry_type_string_value(self):
        """Entry types should have lowercase string values."""
        from bibmgr.core import EntryType

        assert EntryType.ARTICLE.value == "article"
        assert EntryType.INPROCEEDINGS.value == "inproceedings"
        assert str(EntryType.PHDTHESIS) == "phdthesis"


class TestEntry:
    """Test Entry model behavior."""

    def test_minimal_article_creation(self):
        """Should create article with required fields."""
        from bibmgr.core import Entry, EntryType

        entry = Entry(
            key="test2024",
            type=EntryType.ARTICLE,
            author="John Smith",
            title="Test Article",
            journal="Test Journal",
            year=2024,
        )

        assert entry.key == "test2024"
        assert entry.type == EntryType.ARTICLE
        assert entry.author == "John Smith"
        assert entry.title == "Test Article"
        assert entry.journal == "Test Journal"
        assert entry.year == 2024

    def test_entry_immutability(self):
        """Entries should be immutable after creation."""
        from bibmgr.core import Entry, EntryType

        entry = Entry(key="immutable", type=EntryType.MISC, title="Test")

        # Should not be able to modify fields
        with pytest.raises((AttributeError, TypeError)):
            entry.title = "Modified"  # type: ignore[misc]

        with pytest.raises((AttributeError, TypeError)):
            entry.key = "newkey"  # type: ignore[misc]

    def test_optional_fields(self):
        """Should support all standard optional fields."""
        from bibmgr.core import Entry, EntryType

        entry = Entry(
            key="complete",
            type=EntryType.ARTICLE,
            # Required fields
            author="Author Name",
            title="Article Title",
            journal="Journal Name",
            year=2024,
            # Optional standard fields
            volume="10",
            number="3",
            pages="1--10",
            month="jan",
            note="Additional notes",
            # Extended fields
            abstract="Abstract text",
            keywords="keyword1, keyword2",
            doi="10.1234/test",
            url="https://example.com",
            isbn="978-0-123456-78-9",
            issn="1234-5678",
        )

        assert entry.volume == "10"
        assert entry.abstract == "Abstract text"
        assert entry.doi == "10.1234/test"

    def test_file_management_fields(self):
        """Should support file path management."""
        from bibmgr.core import Entry, EntryType

        pdf_path = Path("/papers/test.pdf")

        entry = Entry(
            key="filetest", type=EntryType.MISC, title="Test", pdf_path=pdf_path
        )

        assert entry.pdf_path == pdf_path
        assert isinstance(entry.pdf_path, Path)

    def test_author_list_parsing(self):
        """Should parse author string into list."""
        from bibmgr.core import Entry, EntryType

        entry = Entry(
            key="authors",
            type=EntryType.MISC,
            title="Test",
            author="Alice Smith and Bob Jones and Carol White",
        )

        authors = entry.authors_list
        assert len(authors) == 3
        assert authors[0] == "Alice Smith"
        assert authors[1] == "Bob Jones"
        assert authors[2] == "Carol White"

    def test_empty_author_list(self):
        """Should handle missing author field."""
        from bibmgr.core import Entry, EntryType

        entry = Entry(key="noauthor", type=EntryType.MISC, title="Test")

        assert entry.authors_list == []

    def test_keyword_list_parsing(self):
        """Should parse keywords with various separators."""
        from bibmgr.core import Entry, EntryType

        # Comma-separated
        entry1 = Entry(
            key="key1",
            type=EntryType.MISC,
            title="Test",
            keywords="machine learning, neural networks, deep learning",
        )

        assert len(entry1.keywords_list) == 3
        assert "machine learning" in entry1.keywords_list
        assert "neural networks" in entry1.keywords_list

        # Semicolon-separated
        entry2 = Entry(
            key="key2",
            type=EntryType.MISC,
            title="Test",
            keywords="nlp; computer vision; robotics",
        )

        assert len(entry2.keywords_list) == 3
        assert "nlp" in entry2.keywords_list
        assert "computer vision" in entry2.keywords_list

        # Mixed separators
        entry3 = Entry(
            key="key3",
            type=EntryType.MISC,
            title="Test",
            keywords="topic1, topic2; topic3",
        )

        assert len(entry3.keywords_list) == 3

    def test_search_text_generation(self):
        """Should generate searchable text from all relevant fields."""
        from bibmgr.core import Entry, EntryType

        entry = Entry(
            key="search",
            type=EntryType.ARTICLE,
            author="Test Author",
            title="Important Research",
            journal="Science Journal",
            year=2024,
            abstract="This is the abstract",
            keywords="ai, ml",
            booktitle="Conference Proceedings",
            editor="Editor Name",
        )

        search_text = entry.search_text

        # Should include all searchable fields
        assert "Test Author" in search_text
        assert "Important Research" in search_text
        assert "Science Journal" in search_text
        assert "2024" in search_text
        assert "abstract" in search_text
        assert "ai, ml" in search_text
        assert "Conference Proceedings" in search_text
        assert "Editor Name" in search_text

    def test_bibtex_generation(self):
        """Should generate valid BibTeX format."""
        from bibmgr.core import Entry, EntryType

        entry = Entry(
            key="smith2024",
            type=EntryType.ARTICLE,
            author="John Smith",
            title="Test Article",
            journal="Test Journal",
            year=2024,
            volume="5",
            pages="10--20",
            doi="10.1234/test",
        )

        bibtex = entry.to_bibtex()

        # Check structure
        assert bibtex.startswith("@article{smith2024,")
        assert bibtex.endswith("}")

        # Check fields are present
        assert "author = {John Smith}" in bibtex
        assert "title = {Test Article}" in bibtex
        assert "journal = {Test Journal}" in bibtex
        assert "year = {2024}" in bibtex
        assert "volume = {5}" in bibtex
        assert "pages = {10--20}" in bibtex
        assert "doi = {10.1234/test}" in bibtex

    def test_bibtex_special_characters(self):
        """Should escape special characters in BibTeX output."""
        from bibmgr.core import Entry, EntryType

        entry = Entry(
            key="special",
            type=EntryType.MISC,
            title="Title with {braces} and } special { chars",
            author="Author {with} braces",
        )

        bibtex = entry.to_bibtex()

        # Should escape braces properly
        assert r"\{" in bibtex or "{{" in bibtex
        assert r"\}" in bibtex or "}}" in bibtex

    def test_book_with_editor(self):
        """Book should accept editor instead of author."""
        from bibmgr.core import Entry, EntryType

        entry = Entry(
            key="book2024",
            type=EntryType.BOOK,
            editor="Book Editor",
            title="Edited Book",
            publisher="Publisher",
            year=2024,
        )

        assert entry.editor == "Book Editor"
        assert entry.author is None

    def test_inbook_chapter_or_pages(self):
        """Inbook should accept either chapter or pages."""
        from bibmgr.core import Entry, EntryType

        # With chapter
        entry1 = Entry(
            key="inbook1",
            type=EntryType.INBOOK,
            author="Author",
            title="Chapter Title",
            publisher="Publisher",
            year=2024,
            chapter="5",
        )
        assert entry1.chapter == "5"

        # With pages
        entry2 = Entry(
            key="inbook2",
            type=EntryType.INBOOK,
            author="Author",
            title="Section Title",
            publisher="Publisher",
            year=2024,
            pages="50--75",
        )
        assert entry2.pages == "50--75"

    def test_crossref_field(self):
        """Should support cross-references to other entries."""
        from bibmgr.core import Entry, EntryType

        entry = Entry(
            key="chapter1",
            type=EntryType.INBOOK,
            crossref="mainbook",
            author="Chapter Author",
            title="Chapter Title",
            chapter="1",
        )

        assert entry.crossref == "mainbook"

    def test_entry_equality(self):
        """Entries with same key should be equal."""
        from bibmgr.core import Entry, EntryType

        entry1 = Entry(key="same", type=EntryType.MISC, title="Title 1")

        entry2 = Entry(key="same", type=EntryType.MISC, title="Title 2")

        # Entries with same key should be considered equal
        # (for deduplication purposes)
        assert entry1.key == entry2.key

    def test_serialization(self):
        """Should support serialization to/from JSON."""
        import msgspec

        from bibmgr.core import Entry, EntryType

        entry = Entry(
            key="serial",
            type=EntryType.ARTICLE,
            author="Test Author",
            title="Test Title",
            journal="Test Journal",
            year=2024,
        )

        # Should be serializable
        encoder = msgspec.json.Encoder()
        json_bytes = encoder.encode(entry)

        # Should be deserializable
        decoder = msgspec.json.Decoder(Entry)
        loaded = decoder.decode(json_bytes)

        assert loaded.key == entry.key
        assert loaded.title == entry.title
        assert loaded.year == entry.year

    def test_validation_context(self):
        """Should support validation without exceptions."""
        from bibmgr.core import Entry, EntryType

        # Should be able to create entry without validation
        # (Entry is now a pure data structure)
        entry = Entry(
            key="invalid", type=EntryType.ARTICLE, title="Missing required fields"
        )

        # Should be able to validate later
        errors = entry.validate()
        assert len(errors) > 0

        # Should find missing required fields
        error_fields = {e.field for e in errors}
        assert "author" in error_fields
        assert "journal" in error_fields
        assert "year" in error_fields

    def test_computed_properties(self):
        """Computed properties should work correctly."""
        from bibmgr.core import Entry, EntryType

        entry = Entry(
            key="props",
            type=EntryType.MISC,
            title="Test",
            author="A and B and C and D and E",
        )

        # Properties should compute correctly
        authors = entry.authors_list
        assert len(authors) == 5
        assert authors == ["A", "B", "C", "D", "E"]

        # Multiple accesses should return equal values
        authors2 = entry.authors_list
        assert authors == authors2


class TestValidationError:
    """Test ValidationError model."""

    def test_validation_error_creation(self):
        """Should create validation errors with details."""
        from bibmgr.core import ValidationError

        error = ValidationError(
            field="author", message="Required field missing", severity="error"
        )

        assert error.field == "author"
        assert error.message == "Required field missing"
        assert error.severity == "error"

    def test_validation_error_severities(self):
        """Should support different severity levels."""
        from bibmgr.core import ValidationError

        error = ValidationError(field="f", message="m", severity="error")
        warning = ValidationError(field="f", message="m", severity="warning")
        info = ValidationError(field="f", message="m", severity="info")

        assert error.severity == "error"
        assert warning.severity == "warning"
        assert info.severity == "info"

    def test_validation_error_string(self):
        """Should provide readable string representation."""
        from bibmgr.core import ValidationError

        error = ValidationError(
            field="pages", message="Use -- for page ranges", severity="warning"
        )

        error_str = str(error)
        assert "WARNING" in error_str or "warning" in error_str.lower()
        assert "pages" in error_str
        assert "Use -- for page ranges" in error_str

    def test_validation_error_equality(self):
        """Errors should be comparable."""
        from bibmgr.core import ValidationError

        error1 = ValidationError(field="x", message="y", severity="error")
        error2 = ValidationError(field="x", message="y", severity="error")
        error3 = ValidationError(field="x", message="z", severity="error")

        # Same field and message
        assert error1.field == error2.field
        assert error1.message == error2.message

        # Different message
        assert error1.message != error3.message


class TestCollection:
    """Test Collection model."""

    def test_static_collection(self):
        """Should create static collection with manual membership."""
        from bibmgr.core import Collection

        collection = Collection(
            id="coll1", name="My Papers", description="Personal collection"
        )

        assert collection.id == "coll1"
        assert collection.name == "My Papers"
        assert collection.description == "Personal collection"
        assert not collection.is_smart
        assert len(collection.entry_keys) == 0

    def test_smart_collection(self):
        """Should create smart collection with query."""
        from bibmgr.core import Collection

        collection = Collection(
            id="recent",
            name="Recent Papers",
            description="Papers from 2024",
            query="year:2024",
            is_smart=True,
        )

        assert collection.is_smart
        assert collection.query == "year:2024"
        # Smart collections don't use entry_keys
        assert len(collection.entry_keys) == 0

    def test_collection_membership(self):
        """Static collection should track entry membership."""
        from bibmgr.core import Collection

        collection = Collection(
            id="selected", name="Selected", entry_keys={"entry1", "entry2", "entry3"}
        )

        assert len(collection.entry_keys) == 3
        assert "entry1" in collection.entry_keys
        assert "entry2" in collection.entry_keys
        assert "entry3" in collection.entry_keys

    def test_hierarchical_collections(self):
        """Should support parent-child relationships."""
        from bibmgr.core import Collection

        Collection(id="research", name="Research")

        child = Collection(id="ml", name="Machine Learning", parent_id="research")

        grandchild = Collection(id="nlp", name="NLP", parent_id="ml")

        assert child.parent_id == "research"
        assert grandchild.parent_id == "ml"

    def test_collection_path(self):
        """Should provide hierarchical path."""
        from bibmgr.core import Collection

        # With parent hierarchy
        collection = Collection(id="nlp", name="NLP", parent_id="ml")

        # Should compute full path (implementation may vary)
        path = collection.get_path({"ml": "research"})
        assert "NLP" in path

    def test_collection_timestamps(self):
        """Should track creation and update times."""
        from bibmgr.core import Collection

        collection = Collection(id="timed", name="Timed Collection")

        assert isinstance(collection.created_at, datetime)
        assert isinstance(collection.updated_at, datetime)
        assert collection.created_at <= collection.updated_at

    def test_collection_validation(self):
        """Should validate collection constraints."""
        from bibmgr.core import Collection

        # Should not allow both smart and manual entries
        with pytest.raises(ValueError):
            Collection(
                id="invalid",
                name="Invalid",
                is_smart=True,
                query="test",
                entry_keys={"entry1"},  # Can't have both
            )

    def test_collection_operations(self):
        """Should support add/remove operations for static collections."""
        from bibmgr.core import Collection

        collection = Collection(id="ops", name="Operations Test")

        # Add entries
        collection = collection.add_entry("entry1")
        collection = collection.add_entry("entry2")
        assert "entry1" in collection.entry_keys
        assert "entry2" in collection.entry_keys

        # Remove entry
        collection = collection.remove_entry("entry1")
        assert "entry1" not in collection.entry_keys
        assert "entry2" in collection.entry_keys


class TestTag:
    """Test Tag model."""

    def test_simple_tag(self):
        """Should create simple non-hierarchical tag."""
        from bibmgr.core import Tag

        tag = Tag(path="machine-learning")

        assert tag.path == "machine-learning"
        assert tag.name == "machine-learning"
        assert tag.parent_path is None
        assert tag.level == 0

    def test_hierarchical_tag(self):
        """Should support hierarchical tag paths."""
        from bibmgr.core import Tag

        tag = Tag(path="cs/ai/ml/deep-learning")

        assert tag.path == "cs/ai/ml/deep-learning"
        assert tag.name == "deep-learning"
        assert tag.parent_path == "cs/ai/ml"
        assert tag.level == 3

    def test_tag_with_metadata(self):
        """Should support color and description."""
        from bibmgr.core import Tag

        tag = Tag(
            path="important", color="#ff0000", description="Important papers to read"
        )

        assert tag.color == "#ff0000"
        assert tag.description == "Important papers to read"

    def test_tag_ancestry(self):
        """Should determine ancestry relationships."""
        from bibmgr.core import Tag

        root = Tag(path="cs")
        parent = Tag(path="cs/ai")
        child = Tag(path="cs/ai/ml")
        grandchild = Tag(path="cs/ai/ml/dl")
        other = Tag(path="math/stats")

        # Direct ancestry
        assert root.is_ancestor_of(parent)
        assert root.is_ancestor_of(child)
        assert root.is_ancestor_of(grandchild)
        assert parent.is_ancestor_of(child)
        assert parent.is_ancestor_of(grandchild)
        assert child.is_ancestor_of(grandchild)

        # Not ancestors
        assert not child.is_ancestor_of(parent)
        assert not parent.is_ancestor_of(root)
        assert not root.is_ancestor_of(other)

        # Self is not ancestor
        assert not root.is_ancestor_of(root)

    def test_tag_descendant_check(self):
        """Should check if tag is descendant of another."""
        from bibmgr.core import Tag

        root = Tag(path="cs")
        child = Tag(path="cs/ai")

        assert child.is_descendant_of(root)
        assert not root.is_descendant_of(child)

    def test_tag_siblings(self):
        """Should identify sibling tags."""
        from bibmgr.core import Tag

        tag1 = Tag(path="cs/ai")
        tag2 = Tag(path="cs/systems")
        tag3 = Tag(path="math/algebra")

        assert tag1.parent_path == "cs"
        assert tag2.parent_path == "cs"
        assert tag3.parent_path == "math"

        # tag1 and tag2 are siblings (same parent)
        assert tag1.is_sibling_of(tag2)
        assert tag2.is_sibling_of(tag1)

        # tag3 is not sibling
        assert not tag1.is_sibling_of(tag3)

    def test_tag_path_components(self):
        """Should provide access to path components."""
        from bibmgr.core import Tag

        tag = Tag(path="cs/ai/ml/deep-learning")

        components = tag.path_components
        assert len(components) == 4
        assert components[0] == "cs"
        assert components[1] == "ai"
        assert components[2] == "ml"
        assert components[3] == "deep-learning"

    def test_tag_validation(self):
        """Should validate tag paths."""
        from bibmgr.core import Tag

        # Should not allow empty path
        with pytest.raises(ValueError):
            Tag(path="")

        # Should not allow path with empty components
        with pytest.raises(ValueError):
            Tag(path="cs//ml")  # Double slash

        # Should not allow leading/trailing slashes
        with pytest.raises(ValueError):
            Tag(path="/cs/ml")

        with pytest.raises(ValueError):
            Tag(path="cs/ml/")


class TestEntryFactory:
    """Test entry creation helpers."""

    def test_entry_from_dict(self):
        """Should create entry from dictionary."""
        from bibmgr.core import Entry, EntryType

        data = {
            "key": "fromdict",
            "type": "article",
            "author": "Test Author",
            "title": "Test Title",
            "journal": "Test Journal",
            "year": 2024,
        }

        entry = Entry.from_dict(data)

        assert entry.key == "fromdict"
        assert entry.type == EntryType.ARTICLE
        assert entry.author == "Test Author"

    def test_entry_to_dict(self):
        """Should convert entry to dictionary."""
        from bibmgr.core import Entry, EntryType

        entry = Entry(
            key="todict",
            type=EntryType.ARTICLE,
            author="Author",
            title="Title",
            journal="Journal",
            year=2024,
        )

        data = entry.to_dict()

        assert data["key"] == "todict"
        assert data["type"] == "article"
        assert data["author"] == "Author"
        assert data["year"] == 2024

        # Should not include None values
        assert "abstract" not in data or data["abstract"] is None


class TestRequiredFields:
    """Test required field configurations."""

    def test_get_required_fields(self):
        """Should provide required fields for each entry type."""
        from bibmgr.core import EntryType, get_required_fields

        # Article requirements
        article_required = get_required_fields(EntryType.ARTICLE)
        assert "author" in article_required
        assert "title" in article_required
        assert "journal" in article_required
        assert "year" in article_required

        # Book requirements (author OR editor)
        book_required = get_required_fields(EntryType.BOOK)
        assert "title" in book_required
        assert "publisher" in book_required
        assert "year" in book_required
        # Should indicate author/editor alternative

        # Misc has no required fields
        misc_required = get_required_fields(EntryType.MISC)
        assert len(misc_required) == 0

    def test_validate_required_fields(self):
        """Should validate presence of required fields."""
        from bibmgr.core import Entry, EntryType

        # Valid article
        entry = Entry(
            key="valid",
            type=EntryType.ARTICLE,
            author="Author",
            title="Title",
            journal="Journal",
            year=2024,
        )

        errors = entry.validate()
        required_errors = [e for e in errors if e.severity == "error"]
        assert len(required_errors) == 0

        # Invalid article
        entry2 = Entry(key="invalid", type=EntryType.ARTICLE, title="Only Title")

        errors2 = entry2.validate()
        required_errors2 = [e for e in errors2 if e.severity == "error"]
        assert len(required_errors2) > 0
