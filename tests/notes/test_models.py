"""Comprehensive tests for note models."""

import hashlib
from datetime import datetime
from typing import Any, Protocol

import pytest


class NoteProtocol(Protocol):
    """Protocol for Note objects."""

    id: str
    entry_key: str
    content: str
    type: Any
    title: str | None
    tags: list[str]
    references: list[str]
    created_at: datetime
    updated_at: datetime
    version: int

    @property
    def word_count(self) -> int: ...
    @property
    def char_count(self) -> int: ...
    @property
    def content_hash(self) -> str: ...
    def to_markdown(self) -> str: ...
    def to_dict(self) -> dict[str, Any]: ...
    def update(self, **changes: Any) -> "NoteProtocol": ...


class QuoteProtocol(Protocol):
    """Protocol for Quote objects."""

    id: str
    entry_key: str
    text: str
    page: int | None
    section: str | None
    paragraph: int | None
    category: Any
    importance: int
    tags: list[str]
    note: str | None
    created_at: datetime

    @property
    def citation_text(self) -> str: ...
    def to_markdown(self) -> str: ...
    def to_latex(self) -> str: ...
    def to_dict(self) -> dict[str, Any]: ...


class ProgressProtocol(Protocol):
    """Protocol for ReadingProgress objects."""

    entry_key: str
    status: Any
    priority: Any
    current_page: int
    total_pages: int | None
    sections_read: int
    sections_total: int | None
    reading_time_minutes: int
    session_count: int
    started_at: datetime | None
    finished_at: datetime | None
    last_read_at: datetime | None
    importance: int
    difficulty: int
    enjoyment: int
    comprehension: int

    @property
    def progress_percentage(self) -> float: ...
    @property
    def is_complete(self) -> bool: ...
    @property
    def average_pace(self) -> float: ...
    def update_progress(self, **kwargs: Any) -> "ProgressProtocol": ...
    def to_dict(self) -> dict[str, Any]: ...


class TestNoteModel:
    """Test Note model functionality."""

    def test_create_minimal_note(self, note_factory):
        """Test creating a note with minimal required fields."""
        note = note_factory(
            id="test-1",
            entry_key="einstein1905",
            content="E = mc²",
        )

        assert note.id == "test-1"
        assert note.entry_key == "einstein1905"
        assert note.content == "E = mc²"
        assert note.version == 1
        assert list(note.tags) == []
        assert list(note.references) == []
        assert note.title is None

    def test_create_complete_note(self, note_factory, sample_note_data):
        """Test creating a note with all fields."""
        note = note_factory(**sample_note_data)

        assert note.id == sample_note_data["id"]
        assert note.entry_key == sample_note_data["entry_key"]
        assert note.content == sample_note_data["content"]
        assert note.type.value == sample_note_data["type"]
        assert note.title == sample_note_data["title"]
        assert list(note.tags) == sample_note_data["tags"]
        assert list(note.references) == sample_note_data["references"]
        assert note.version == sample_note_data["version"]

    def test_note_immutability(self, note_factory):
        """Test that notes are immutable."""
        note = note_factory(
            id="test-1",
            entry_key="test",
            content="Original",
        )

        with pytest.raises((AttributeError, TypeError)):
            note.content = "Modified"

        with pytest.raises((AttributeError, TypeError)):
            note.tags.append("new-tag")

    def test_word_count(self, note_factory):
        """Test word count calculation."""
        test_cases = [
            ("Single word", 2),
            ("This is a five word sentence.", 6),
            ("Multiple   spaces   between   words", 4),
            ("Line\nbreaks\ncount\nas\nspaces", 5),
            ("", 0),
            ("   ", 0),
        ]

        for content, expected in test_cases:
            note = note_factory(id="test", entry_key="e", content=content)
            assert note.word_count == expected

    def test_char_count(self, note_factory):
        """Test character count calculation."""
        test_cases = [
            ("Hello", 5),
            ("Hello, world!", 13),
            ("", 0),
            ("Unicode: ñ é ü", 14),
            ("Emoji: 🚀", len("Emoji: 🚀")),  # Let Python determine the length
        ]

        for content, expected in test_cases:
            note = note_factory(id="test", entry_key="e", content=content)
            assert note.char_count == expected

    def test_content_hash(self, note_factory):
        """Test content hash generation."""
        content = "Test content for hashing"
        note1 = note_factory(id="n1", entry_key="e1", content=content)
        note2 = note_factory(id="n2", entry_key="e2", content=content)

        # Same content should produce same hash
        assert note1.content_hash == note2.content_hash
        assert len(note1.content_hash) == 16  # Truncated SHA256

        # Different content should produce different hash
        note3 = note_factory(id="n3", entry_key="e3", content="Different")
        assert note3.content_hash != note1.content_hash

    def test_to_markdown(self, note_factory):
        """Test markdown export."""
        created = datetime(2024, 1, 15, 10, 30, 0)
        updated = datetime(2024, 1, 16, 14, 20, 0)

        note = note_factory(
            id="test",
            entry_key="einstein1905",
            content="# Summary\n\nE = mc²",
            type="summary",
            title="Special Relativity",
            tags=["physics", "relativity"],
            references=["lorentz1904"],
            created_at=created,
            updated_at=updated,
            version=2,
        )

        markdown = note.to_markdown()

        # Check required elements
        assert "# Special Relativity" in markdown
        assert "**Entry**: einstein1905" in markdown
        assert "**Type**: summary" in markdown
        assert "**Created**: 2024-01-15" in markdown
        assert "**Updated**: 2024-01-16" in markdown
        assert "**Version**: 2" in markdown
        assert "**Tags**: physics, relativity" in markdown
        assert "**References**: lorentz1904" in markdown
        assert "E = mc²" in markdown

    def test_to_dict(self, note_factory, sample_note_data):
        """Test dictionary conversion."""
        note = note_factory(**sample_note_data)
        data = note.to_dict()

        assert data["id"] == sample_note_data["id"]
        assert data["entry_key"] == sample_note_data["entry_key"]
        assert data["content"] == sample_note_data["content"]
        assert data["type"] == sample_note_data["type"]
        assert data["title"] == sample_note_data["title"]
        assert data["tags"] == sample_note_data["tags"]
        assert data["version"] == sample_note_data["version"]

    def test_update_note(self, note_factory):
        """Test updating a note."""
        original = note_factory(
            id="test",
            entry_key="e1",
            content="Original",
            title="Original Title",
            tags=["tag1"],
            version=1,
        )

        # Update content
        updated = original.update(content="Updated content")

        assert updated.id == original.id
        assert updated.entry_key == original.entry_key
        assert updated.content == "Updated content"
        assert updated.title == original.title
        assert list(updated.tags) == list(original.tags)
        assert updated.version == 2
        assert updated.updated_at > original.updated_at

        # Original should be unchanged
        assert original.content == "Original"
        assert original.version == 1

    def test_update_multiple_fields(self, note_factory):
        """Test updating multiple fields at once."""
        original = note_factory(
            id="test",
            entry_key="e1",
            content="Content",
        )

        updated = original.update(
            content="New content",
            title="New Title",
            tags=["new", "tags"],
        )

        assert updated.content == "New content"
        assert updated.title == "New Title"
        assert list(updated.tags) == ["new", "tags"]
        assert updated.version == 2

    def test_update_invalid_fields(self, note_factory):
        """Test that invalid fields are ignored in updates."""
        note = note_factory(id="test", entry_key="e1", content="Content")

        # Should ignore invalid fields
        updated = note.update(
            invalid_field="value",
            another_invalid="test",
            content="Valid update",
        )

        assert updated.content == "Valid update"
        assert not hasattr(updated, "invalid_field")
        assert not hasattr(updated, "another_invalid")

    def test_note_types(self, note_factory, note_type_enum):
        """Test all available note types."""
        expected_types = [
            "summary",
            "critique",
            "idea",
            "question",
            "todo",
            "reference",
            "quote",
            "general",
            "methodology",
            "results",
        ]

        for type_name in expected_types:
            note = note_factory(
                id=f"test-{type_name}",
                entry_key="e1",
                content=f"Content for {type_name}",
                type=type_name,
            )
            assert note.type.value == type_name

    def test_empty_content(self, note_factory):
        """Test handling of empty content."""
        note = note_factory(id="test", entry_key="e1", content="")

        assert note.content == ""
        assert note.word_count == 0
        assert note.char_count == 0
        assert len(note.content_hash) == 16  # Still generates hash

    def test_unicode_content(self, note_factory):
        """Test handling of Unicode content."""
        content = "Schrödinger's equation: ψ(x,t) = Ψ(x)e^(-iEt/ℏ)"
        note = note_factory(id="test", entry_key="e1", content=content)

        assert note.content == content
        assert note.char_count == len(content)
        # Hash should handle Unicode properly
        assert len(note.content_hash) == 16

    def test_large_content(self, note_factory):
        """Test handling of large content."""
        # 10,000 words
        content = " ".join(["word"] * 10000)
        note = note_factory(id="test", entry_key="e1", content=content)

        assert note.word_count == 10000
        assert note.char_count == len(content)
        assert len(note.content_hash) == 16


class TestQuoteModel:
    """Test Quote model functionality."""

    def test_create_minimal_quote(self, quote_factory):
        """Test creating a quote with minimal fields."""
        quote = quote_factory(
            id="q1",
            entry_key="feynman1965",
            text="The first principle is that you must not fool yourself.",
        )

        assert quote.id == "q1"
        assert quote.entry_key == "feynman1965"
        assert quote.text == "The first principle is that you must not fool yourself."
        assert quote.importance == 3  # Default
        assert list(quote.tags) == []

    def test_create_complete_quote(self, quote_factory, sample_quote_data):
        """Test creating a quote with all fields."""
        quote = quote_factory(**sample_quote_data)

        assert quote.id == sample_quote_data["id"]
        assert quote.entry_key == sample_quote_data["entry_key"]
        assert quote.text == sample_quote_data["text"]
        assert quote.page == sample_quote_data["page"]
        assert quote.section == sample_quote_data["section"]
        assert quote.paragraph == sample_quote_data["paragraph"]
        assert quote.category.value == sample_quote_data["category"]
        assert quote.importance == sample_quote_data["importance"]
        assert list(quote.tags) == sample_quote_data["tags"]
        assert quote.note == sample_quote_data["note"]

    def test_citation_text(self, quote_factory):
        """Test citation text generation."""
        # With page
        quote1 = quote_factory(id="q1", entry_key="e1", text="Text", page=42)
        assert quote1.citation_text == "(p. 42)"

        # With section
        quote2 = quote_factory(
            id="q2", entry_key="e1", text="Text", section="Introduction"
        )
        assert quote2.citation_text == "(Introduction)"

        # With both (page takes precedence)
        quote3 = quote_factory(
            id="q3", entry_key="e1", text="Text", page=10, section="Chapter 1"
        )
        assert quote3.citation_text == "(p. 10)"

        # With neither
        quote4 = quote_factory(id="q4", entry_key="e1", text="Text")
        assert quote4.citation_text == ""

    def test_to_markdown(self, quote_factory):
        """Test markdown export."""
        quote = quote_factory(
            id="q1",
            entry_key="einstein1905",
            text="Imagination is more important than knowledge.",
            page=15,
            context="Discussing scientific discovery",
            note="Key insight",
            tags=["philosophy", "creativity"],
        )

        markdown = quote.to_markdown()

        assert "> Imagination is more important than knowledge." in markdown
        assert "— einstein1905 (p. 15)" in markdown
        assert "**Context**: Discussing scientific discovery" in markdown
        assert "**Note**: Key insight" in markdown
        assert "#philosophy" in markdown
        assert "#creativity" in markdown

    def test_to_latex(self, quote_factory):
        """Test LaTeX export."""
        quote = quote_factory(
            id="q1",
            entry_key="knuth1984",
            text="Premature optimization is the root of all evil.",
            page=268,
            note="Famous programming wisdom",
        )

        latex = quote.to_latex()

        assert "\\begin{quote}" in latex
        assert "Premature optimization is the root of all evil." in latex
        assert "\\cite{knuth1984}" in latex
        assert "(p. 268)" in latex
        assert "\\end{quote}" in latex
        assert "\\textit{Famous programming wisdom}" in latex

    def test_quote_categories(self, quote_factory, quote_category_enum):
        """Test all quote categories."""
        expected_categories = [
            "definition",
            "methodology",
            "finding",
            "conclusion",
            "criticism",
            "inspiration",
            "reference",
            "data",
            "other",
        ]

        for category in expected_categories:
            quote = quote_factory(
                id=f"q-{category}",
                entry_key="e1",
                text=f"Quote about {category}",
                category=category,
            )
            assert quote.category.value == category

    def test_importance_levels(self, quote_factory):
        """Test importance levels."""
        for importance in range(1, 6):
            quote = quote_factory(
                id=f"q-{importance}",
                entry_key="e1",
                text="Text",
                importance=importance,
            )
            assert quote.importance == importance

    def test_quote_immutability(self, quote_factory):
        """Test that quotes are immutable."""
        quote = quote_factory(
            id="q1",
            entry_key="e1",
            text="Original text",
        )

        with pytest.raises((AttributeError, TypeError)):
            quote.text = "Modified text"

        with pytest.raises((AttributeError, TypeError)):
            quote.tags.append("new-tag")


class TestReadingProgressModel:
    """Test ReadingProgress model functionality."""

    def test_create_minimal_progress(self, progress_factory):
        """Test creating progress with minimal fields."""
        progress = progress_factory(entry_key="knuth1984")

        assert progress.entry_key == "knuth1984"
        assert progress.status.value == "unread"
        assert progress.priority.value == 2  # MEDIUM
        assert progress.current_page == 0
        assert progress.reading_time_minutes == 0
        assert progress.session_count == 0

    def test_create_complete_progress(self, progress_factory, sample_progress_data):
        """Test creating progress with all fields."""
        progress = progress_factory(**sample_progress_data)

        assert progress.entry_key == sample_progress_data["entry_key"]
        assert progress.status.value == sample_progress_data["status"]
        assert progress.priority.value == sample_progress_data["priority"]
        assert progress.current_page == sample_progress_data["current_page"]
        assert progress.total_pages == sample_progress_data["total_pages"]
        assert (
            progress.reading_time_minutes
            == sample_progress_data["reading_time_minutes"]
        )
        assert progress.importance == sample_progress_data["importance"]
        assert progress.difficulty == sample_progress_data["difficulty"]

    def test_progress_percentage_pages(self, progress_factory):
        """Test progress calculation with pages."""
        progress = progress_factory(
            entry_key="e1",
            current_page=25,
            total_pages=100,
        )
        assert progress.progress_percentage == 25.0

        # Test over 100%
        progress2 = progress_factory(
            entry_key="e2",
            current_page=150,
            total_pages=100,
        )
        assert progress2.progress_percentage == 100.0

        # Test with zero pages
        progress3 = progress_factory(
            entry_key="e3",
            current_page=0,
            total_pages=100,
        )
        assert progress3.progress_percentage == 0.0

    def test_progress_percentage_sections(self, progress_factory):
        """Test progress calculation with sections."""
        progress = progress_factory(
            entry_key="e1",
            sections_read=3,
            sections_total=10,
        )
        assert progress.progress_percentage == 30.0

    def test_progress_percentage_by_status(self, progress_factory):
        """Test progress percentage based on status."""
        test_cases = [
            ("unread", 0.0),
            ("reading", 50.0),
            ("partially_read", 50.0),
            ("skimmed", 75.0),
            ("read", 100.0),
            ("to_reread", 100.0),
        ]

        for status, expected in test_cases:
            progress = progress_factory(
                entry_key="e1",
                status=status,
            )
            assert progress.progress_percentage == expected

    def test_is_complete(self, progress_factory):
        """Test completion check."""
        incomplete_statuses = ["unread", "reading", "partially_read", "to_reread"]
        complete_statuses = ["read", "skimmed"]

        for status in incomplete_statuses:
            progress = progress_factory(entry_key="e1", status=status)
            assert not progress.is_complete

        for status in complete_statuses:
            progress = progress_factory(entry_key="e1", status=status)
            assert progress.is_complete

    def test_average_pace(self, progress_factory):
        """Test reading pace calculation."""
        progress = progress_factory(
            entry_key="e1",
            current_page=60,
            reading_time_minutes=120,
        )
        assert progress.average_pace == 0.5  # pages per minute

        # Test with zero time
        progress2 = progress_factory(
            entry_key="e2",
            current_page=60,
            reading_time_minutes=0,
        )
        assert progress2.average_pace == 0.0

        # Test with zero pages
        progress3 = progress_factory(
            entry_key="e3",
            current_page=0,
            reading_time_minutes=120,
        )
        assert progress3.average_pace == 0.0

    def test_update_progress_page(self, progress_factory):
        """Test updating progress with page."""
        progress = progress_factory(
            entry_key="e1",
            status="unread",
            total_pages=100,
        )

        updated = progress.update_progress(page=25, time_minutes=30)

        assert updated.current_page == 25
        assert updated.reading_time_minutes == 30
        assert updated.session_count == 1
        assert updated.status.value == "reading"
        assert updated.started_at is not None
        assert updated.last_read_at is not None
        assert updated.finished_at is None

    def test_update_progress_complete(self, progress_factory):
        """Test completing reading."""
        progress = progress_factory(
            entry_key="e1",
            status="reading",
            current_page=90,
            total_pages=100,
        )

        updated = progress.update_progress(page=100, time_minutes=20)

        assert updated.current_page == 100
        assert updated.status.value == "read"
        assert updated.finished_at is not None

    def test_update_progress_sections(self, progress_factory):
        """Test updating progress with sections."""
        progress = progress_factory(
            entry_key="e1",
            sections_total=5,
        )

        updated = progress.update_progress(section=3)
        assert updated.sections_read == 3
        assert updated.status.value == "reading"

        completed = updated.update_progress(section=5)
        assert completed.status.value == "read"
        assert completed.finished_at is not None

    def test_reading_statuses(self, progress_factory, reading_status_enum):
        """Test all reading statuses."""
        expected_statuses = [
            "unread",
            "reading",
            "read",
            "skimmed",
            "to_reread",
            "partially_read",
        ]

        for status in expected_statuses:
            progress = progress_factory(
                entry_key="e1",
                status=status,
            )
            assert progress.status.value == status

    def test_priority_levels(self, progress_factory, priority_enum):
        """Test all priority levels."""
        expected_priorities = [
            (1, "low"),
            (2, "medium"),
            (3, "high"),
            (4, "urgent"),
            (5, "critical"),
        ]

        for value, name in expected_priorities:
            progress = progress_factory(
                entry_key="e1",
                priority=value,
            )
            assert progress.priority.value == value

    def test_quality_metrics(self, progress_factory):
        """Test reading quality metrics."""
        progress = progress_factory(
            entry_key="e1",
            importance=5,
            difficulty=4,
            enjoyment=3,
            comprehension=2,
        )

        assert progress.importance == 5
        assert progress.difficulty == 4
        assert progress.enjoyment == 3
        assert progress.comprehension == 2


class TestNoteVersionModel:
    """Test NoteVersion model functionality."""

    def test_create_version(self, version_factory):
        """Test creating a note version."""
        version = version_factory(
            note_id="note-1",
            version=1,
            content="Original content",
            content_hash="hash123",
            created_at=datetime.now(),
        )

        assert version.note_id == "note-1"
        assert version.version == 1
        assert version.content == "Original content"
        assert version.content_hash == "hash123"

    def test_version_with_metadata(self, version_factory):
        """Test version with change metadata."""
        version = version_factory(
            note_id="note-1",
            version=2,
            content="Updated content",
            content_hash="hash456",
            created_at=datetime.now(),
            change_summary="Fixed typos",
            changed_by="user123",
        )

        assert version.change_summary == "Fixed typos"
        assert version.changed_by == "user123"

    def test_word_count(self, version_factory):
        """Test word count for version."""
        version = version_factory(
            note_id="note-1",
            version=1,
            content="This has five words here",
            content_hash="hash",
            created_at=datetime.now(),
        )

        assert version.word_count == 5

    def test_diff_generation(self, version_factory):
        """Test generating diff between versions."""
        v1 = version_factory(
            note_id="note-1",
            version=1,
            content="Line 1\nLine 2\nLine 3",
            content_hash="hash1",
            created_at=datetime.now(),
        )

        v2 = version_factory(
            note_id="note-1",
            version=2,
            content="Line 1\nLine 2 modified\nLine 3\nLine 4",
            content_hash="hash2",
            created_at=datetime.now(),
        )

        diff = v2.diff_from(v1)

        assert "Version 1" in diff
        assert "Version 2" in diff
        assert "-Line 2" in diff
        assert "+Line 2 modified" in diff
        assert "+Line 4" in diff

    def test_version_immutability(self, version_factory):
        """Test that versions are immutable."""
        version = version_factory(
            note_id="note-1",
            version=1,
            content="Content",
            content_hash="hash",
            created_at=datetime.now(),
        )

        with pytest.raises((AttributeError, TypeError)):
            version.content = "Modified"

        with pytest.raises((AttributeError, TypeError)):
            version.version = 2


class TestTemplateModel:
    """Test NoteTemplate model functionality."""

    def test_create_template(self, template_factory):
        """Test creating a note template."""
        template = template_factory(
            name="review",
            type="critique",
            title_template="Review: {title}",
            content_template="## {title}\n\nBy {author}",
            tags=["review"],
            description="Paper review template",
        )

        assert template.name == "review"
        assert template.type.value == "critique"
        assert list(template.tags) == ["review"]

    def test_render_template(self, template_factory, entry_factory):
        """Test rendering a template."""
        template = template_factory(
            name="summary",
            type="summary",
            title_template="Summary: {title}",
            content_template="""Entry: {entry_key}
Title: {title}
Author: {author}
Year: {year}
Date: {date}""",
            tags=["summary"],
        )

        entry = entry_factory(
            key="einstein1905",
            title="On the Electrodynamics of Moving Bodies",
            author="Einstein, A.",
            year="1905",
        )

        title, content = template.render(entry)

        assert title == "Summary: On the Electrodynamics of Moving Bodies"
        assert "Entry: einstein1905" in content
        assert "Title: On the Electrodynamics of Moving Bodies" in content
        assert "Author: Einstein, A." in content
        assert "Year: 1905" in content
        assert "Date:" in content  # Should include current date

    def test_render_with_custom_variables(self, template_factory):
        """Test rendering with custom variables."""
        template = template_factory(
            name="custom",
            type="general",
            title_template="{custom_title}",
            content_template="{custom_var1}\n{custom_var2}",
            tags=[],
        )

        title, content = template.render(
            entry=None,
            custom_title="Custom Title",
            custom_var1="Value 1",
            custom_var2="Value 2",
        )

        assert title == "Custom Title"
        assert "Value 1" in content
        assert "Value 2" in content

    def test_template_validation(self, template_factory):
        """Test template validation."""
        # Valid template
        template = template_factory(
            name="valid",
            type="summary",
            title_template="Title",
            content_template="Content",
            tags=[],
        )
        assert template.is_valid()

        # Test invalid templates
        with pytest.raises(ValueError):
            # Empty name
            template_factory(
                name="",
                type="summary",
                title_template="Title",
                content_template="Content",
            )

        with pytest.raises(ValueError):
            # Invalid type
            template_factory(
                name="invalid",
                type="invalid_type",
                title_template="Title",
                content_template="Content",
            )


class TestModelEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_content_hash(self, note_factory):
        """Test hash of empty content."""
        note = note_factory(
            id="test",
            entry_key="e1",
            content="",
        )

        expected_hash = hashlib.sha256(b"").hexdigest()[:16]
        assert note.content_hash == expected_hash

    def test_very_long_content(self, note_factory):
        """Test handling of very long content."""
        content = "word " * 100000  # 100,000 words
        note = note_factory(
            id="test",
            entry_key="e1",
            content=content,
        )

        assert note.word_count == 100000
        assert note.char_count == len(content)

    def test_special_characters(self, note_factory, quote_factory):
        """Test handling of special characters."""
        special_content = "Test with 'quotes' and \"double quotes\" and \\backslash"

        note = note_factory(
            id="test",
            entry_key="e1",
            content=special_content,
        )
        assert note.content == special_content

        quote = quote_factory(
            id="q1",
            entry_key="e1",
            text=special_content,
        )
        assert quote.text == special_content

    def test_null_fields(self, note_factory, progress_factory):
        """Test handling of null/None fields."""
        note = note_factory(
            id="test",
            entry_key="e1",
            content="Content",
            title=None,
        )
        assert note.title is None

        progress = progress_factory(
            entry_key="e1",
            total_pages=None,
            started_at=None,
            finished_at=None,
        )
        assert progress.total_pages is None
        assert progress.started_at is None

    def test_circular_references(self, note_factory):
        """Test handling of circular references."""
        # Note referencing itself
        note = note_factory(
            id="note1",
            entry_key="e1",
            content="Content",
            references=["note1"],  # Self-reference
        )

        # Should handle gracefully
        assert "note1" in note.references

    def test_invalid_enum_values(self, note_factory, progress_factory):
        """Test handling of invalid enum values."""
        with pytest.raises((ValueError, KeyError)):
            note_factory(
                id="test",
                entry_key="e1",
                content="Content",
                type="invalid_type",
            )

        with pytest.raises((ValueError, KeyError)):
            progress_factory(
                entry_key="e1",
                status="invalid_status",
            )

    def test_datetime_edge_cases(self, note_factory):
        """Test datetime handling edge cases."""
        # Very old date
        old_date = datetime(1900, 1, 1)
        note = note_factory(
            id="test",
            entry_key="e1",
            content="Content",
            created_at=old_date,
        )
        assert note.created_at == old_date

        # Future date
        future_date = datetime(2100, 12, 31)
        note2 = note_factory(
            id="test2",
            entry_key="e1",
            content="Content",
            created_at=future_date,
        )
        assert note2.created_at == future_date
