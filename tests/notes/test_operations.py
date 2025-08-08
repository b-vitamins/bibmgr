"""Comprehensive tests for notes operations and management."""

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol

import pytest


class ManagerProtocol(Protocol):
    """Protocol for note manager implementations."""

    # Note operations
    def create_note(self, entry_key: str, content: str, **kwargs: Any) -> Any: ...
    def update_note(self, note_id: str, **changes: Any) -> Any | None: ...
    def delete_note(self, note_id: str) -> bool: ...
    def get_note(self, note_id: str) -> Any | None: ...
    def get_notes(self, entry_key: str, **filters: Any) -> list[Any]: ...
    def search_notes(self, query: str, **filters: Any) -> list[Any]: ...

    # Quote operations
    def add_quote(self, entry_key: str, text: str, **kwargs: Any) -> Any: ...
    def delete_quote(self, quote_id: str) -> bool: ...
    def get_quotes(self, entry_key: str, **filters: Any) -> list[Any]: ...
    def search_quotes(self, query: str | None, **filters: Any) -> list[Any]: ...

    # Progress operations
    def track_reading(self, entry_key: str, **kwargs: Any) -> Any: ...
    def get_reading_progress(self, entry_key: str) -> Any | None: ...
    def get_reading_list(self, **filters: Any) -> list[Any]: ...
    def update_reading_status(self, entry_key: str, status: str) -> Any | None: ...

    # Template operations
    def create_note_from_template(
        self, entry_key: str, template_name: str, **variables: Any
    ) -> Any: ...
    def get_available_templates(self) -> list[str]: ...
    def add_custom_template(self, template: Any) -> None: ...

    # Bulk operations
    def bulk_update_tags(
        self, note_ids: list[str], add: list[str], remove: list[str]
    ) -> list[Any]: ...
    def merge_notes(self, note_ids: list[str], title: str | None) -> Any: ...
    def split_note(self, note_id: str, sections: list[str]) -> list[Any]: ...

    # Version operations
    def get_note_history(self, note_id: str) -> list[Any]: ...
    def restore_note_version(self, note_id: str, version: int) -> Any: ...
    def compare_versions(self, note_id: str, v1: int, v2: int) -> str: ...

    # Export operations
    def export_notes(self, entry_key: str, format: str = "markdown") -> str: ...
    def export_quotes(self, entry_key: str, format: str = "markdown") -> str: ...
    def export_reading_report(self, **filters: Any) -> str: ...

    # Statistics
    def get_statistics(self) -> dict[str, Any]: ...
    def get_entry_statistics(self, entry_key: str) -> dict[str, Any]: ...


class TestNoteOperations:
    """Test note management operations."""

    def test_create_note_minimal(self, manager):
        """Test creating note with minimal fields."""
        note = manager.create_note(
            entry_key="einstein1905",
            content="E = mc²",
        )

        assert note.id is not None
        assert note.entry_key == "einstein1905"
        assert note.content == "E = mc²"
        assert note.version == 1

    def test_create_note_complete(self, manager):
        """Test creating note with all fields."""
        note = manager.create_note(
            entry_key="feynman1965",
            content="Quantum mechanics principles",
            type="summary",
            title="QED Summary",
            tags=["physics", "quantum"],
        )

        assert note.entry_key == "feynman1965"
        assert note.content == "Quantum mechanics principles"
        assert note.type.value == "summary"
        assert note.title == "QED Summary"
        assert list(note.tags) == ["physics", "quantum"]

    def test_update_note(self, manager):
        """Test updating a note."""
        # Create note
        note = manager.create_note(
            entry_key="test",
            content="Original",
            title="Original Title",
        )

        # Update it
        updated = manager.update_note(
            note.id,
            content="Updated content",
            title="New Title",
            tags=["updated"],
        )

        assert updated is not None
        assert updated.content == "Updated content"
        assert updated.title == "New Title"
        assert list(updated.tags) == ["updated"]
        assert updated.version == 2

    def test_update_nonexistent_note(self, manager):
        """Test updating nonexistent note."""
        result = manager.update_note(
            "nonexistent",
            content="New content",
        )
        assert result is None

    def test_delete_note(self, manager):
        """Test deleting a note."""
        note = manager.create_note(
            entry_key="test",
            content="To be deleted",
        )

        # Delete it
        result = manager.delete_note(note.id)
        assert result is True

        # Verify it's gone
        assert manager.get_note(note.id) is None

    def test_delete_nonexistent_note(self, manager):
        """Test deleting nonexistent note."""
        result = manager.delete_note("nonexistent")
        assert result is False

    def test_get_notes_for_entry(self, manager):
        """Test getting notes for an entry."""
        # Create notes for different entries
        note1 = manager.create_note("entry1", "Note 1", type="summary")
        manager.create_note("entry1", "Note 2", type="critique")
        manager.create_note("entry2", "Note 3", type="summary")

        # Get notes for entry1
        entry1_notes = manager.get_notes("entry1")
        assert len(entry1_notes) == 2

        # Filter by type
        summaries = manager.get_notes("entry1", type="summary")
        assert len(summaries) == 1
        assert summaries[0].id == note1.id

    def test_search_notes(self, manager):
        """Test searching notes."""
        # Create searchable notes
        manager.create_note("e1", "Quantum mechanics and wave functions")
        manager.create_note("e2", "Classical mechanics differs from quantum")
        manager.create_note("e3", "Statistical mechanics and thermodynamics")

        # Search
        results = manager.search_notes("quantum")
        assert len(results) == 2

        results = manager.search_notes("mechanics")
        assert len(results) == 3

    def test_search_with_filters(self, manager):
        """Test searching with filters."""
        manager.create_note("e1", "Summary content", type="summary", tags=["physics"])
        manager.create_note("e2", "Critique content", type="critique", tags=["physics"])
        manager.create_note("e3", "Summary review", type="summary", tags=["review"])

        # Filter by type
        results = manager.search_notes("content", type="summary")
        assert len(results) == 1

        # Filter by tags
        results = manager.search_notes("content", tags=["physics"])
        assert len(results) == 2


class TestQuoteOperations:
    """Test quote management operations."""

    def test_add_quote_minimal(self, manager):
        """Test adding quote with minimal fields."""
        quote = manager.add_quote(
            entry_key="feynman1965",
            text="The first principle is that you must not fool yourself.",
        )

        assert quote.id is not None
        assert quote.entry_key == "feynman1965"
        assert quote.text == "The first principle is that you must not fool yourself."
        assert quote.importance == 3  # Default

    def test_add_quote_complete(self, manager):
        """Test adding quote with all fields."""
        quote = manager.add_quote(
            entry_key="einstein1905",
            text="Imagination is more important than knowledge.",
            page=42,
            section="Chapter 3",
            category="inspiration",
            importance=5,
            tags=["creativity", "philosophy"],
            note="Key insight on scientific thinking",
        )

        assert quote.page == 42
        assert quote.section == "Chapter 3"
        assert quote.category.value == "inspiration"
        assert quote.importance == 5
        assert list(quote.tags) == ["creativity", "philosophy"]
        assert quote.note == "Key insight on scientific thinking"

    def test_delete_quote(self, manager):
        """Test deleting a quote."""
        quote = manager.add_quote(
            entry_key="test",
            text="To be deleted",
        )

        result = manager.delete_quote(quote.id)
        assert result is True

    def test_get_quotes_for_entry(self, manager):
        """Test getting quotes for an entry."""
        # Add quotes
        manager.add_quote("e1", "Quote 1", page=10)
        manager.add_quote("e1", "Quote 2", page=20)
        manager.add_quote("e2", "Quote 3", page=5)

        # Get quotes for e1
        e1_quotes = manager.get_quotes("e1")
        assert len(e1_quotes) == 2
        # Should be ordered by page
        assert e1_quotes[0].page == 10
        assert e1_quotes[1].page == 20

    def test_search_quotes(self, manager):
        """Test searching quotes."""
        manager.add_quote(
            "e1",
            "Important discovery about quantum mechanics",
            tags=["physics"],
        )
        manager.add_quote(
            "e2",
            "Classical mechanics differs from quantum",
            tags=["physics", "comparison"],
        )
        manager.add_quote(
            "e3",
            "Statistical analysis shows correlation",
            tags=["statistics"],
        )

        # Search by text
        results = manager.search_quotes("quantum")
        assert len(results) == 2

        # Search by tags
        results = manager.search_quotes(tags=["physics"])
        assert len(results) == 2

        # Get all quotes with category filter
        results = manager.search_quotes(None, category="other")
        assert len(results) >= 3  # All default to "other"


class TestReadingProgress:
    """Test reading progress tracking."""

    def test_track_reading_initial(self, manager):
        """Test initial reading tracking."""
        progress = manager.track_reading(
            entry_key="knuth1984",
            page=1,
            total_pages=700,
            priority=3,  # HIGH
        )

        assert progress.entry_key == "knuth1984"
        assert progress.current_page == 1
        assert progress.total_pages == 700
        assert progress.priority.value == 3
        assert progress.status.value == "reading"

    def test_update_reading_progress(self, manager):
        """Test updating reading progress."""
        # Start reading
        manager.track_reading("e1", page=1, total_pages=100)

        # Update progress
        progress = manager.track_reading(
            "e1",
            page=50,
            time_minutes=60,
        )

        assert progress.current_page == 50
        assert progress.reading_time_minutes == 60
        assert progress.session_count > 0

    def test_complete_reading(self, manager):
        """Test completing reading."""
        # Start reading
        manager.track_reading("e1", page=90, total_pages=100)

        # Complete it
        progress = manager.track_reading("e1", page=100)

        assert progress.current_page == 100
        assert progress.status.value == "read"
        assert progress.is_complete
        assert progress.finished_at is not None

    def test_update_reading_status(self, manager):
        """Test updating reading status directly."""
        # Create progress
        manager.track_reading("e1", page=50, total_pages=100)

        # Update status
        progress = manager.update_reading_status("e1", "skimmed")

        assert progress is not None
        assert progress.status.value == "skimmed"
        assert progress.is_complete

    def test_get_reading_list(self, manager):
        """Test getting reading list."""
        # Track multiple entries
        manager.track_reading("e1", priority=1)  # LOW
        manager.track_reading("e2", priority=3)  # HIGH
        manager.track_reading("e3", priority=5)  # CRITICAL

        # Get all
        all_items = manager.get_reading_list()
        assert len(all_items) == 3

        # Filter by priority
        high_priority = manager.get_reading_list(min_priority=3)
        assert len(high_priority) == 2

    def test_reading_metrics(self, manager):
        """Test reading quality metrics."""
        progress = manager.track_reading(
            "e1",
            page=50,
            total_pages=100,
            importance=5,
            difficulty=4,
            enjoyment=3,
            comprehension=2,
        )

        assert progress.importance == 5
        assert progress.difficulty == 4
        assert progress.enjoyment == 3
        assert progress.comprehension == 2


class TestTemplateOperations:
    """Test template-based note creation."""

    def test_get_available_templates(self, manager):
        """Test getting available templates."""
        templates = manager.get_available_templates()

        # Should have default templates
        assert len(templates) > 0
        assert "summary" in templates
        assert "critique" in templates
        assert "paper_review" in templates

    def test_create_from_template(self, manager, entry_factory):
        """Test creating note from template."""
        # Create entry for context
        entry = entry_factory(
            key="einstein1905",
            title="On the Electrodynamics of Moving Bodies",
            author="Einstein, A.",
            year="1905",
        )

        note = manager.create_note_from_template(
            entry_key="einstein1905",
            template_name="summary",
            entry=entry,
        )

        assert note.entry_key == "einstein1905"
        assert "einstein1905" in note.content
        assert "On the Electrodynamics of Moving Bodies" in note.content
        assert note.type.value == "summary"

    def test_create_from_template_with_variables(self, manager):
        """Test template with custom variables."""
        note = manager.create_note_from_template(
            entry_key="test",
            template_name="paper_review",
            title="Test Paper",
            authors="Smith, J.",
            year="2024",
            summary="This is a test paper summary",
            custom_field="Custom value",
        )

        assert "Test Paper" in note.content
        assert "Smith, J." in note.content
        assert "2024" in note.content

    def test_add_custom_template(self, manager, template_factory):
        """Test adding custom template."""
        template = template_factory(
            name="custom",
            type="general",
            title_template="Custom: {title}",
            content_template="Custom template content: {content}",
            tags=["custom"],
            description="Custom template",
        )

        manager.add_custom_template(template)

        # Should be available
        templates = manager.get_available_templates()
        assert "custom" in templates

        # Should be usable
        note = manager.create_note_from_template(
            entry_key="test",
            template_name="custom",
            title="Test",
            content="Test content",
        )

        assert "Custom: Test" in note.title
        assert "Custom template content: Test content" in note.content

    def test_invalid_template(self, manager):
        """Test using invalid template."""
        from bibmgr.notes.exceptions import TemplateNotFoundError

        with pytest.raises(TemplateNotFoundError):
            manager.create_note_from_template(
                entry_key="test",
                template_name="nonexistent",
            )


class TestBulkOperations:
    """Test bulk operations."""

    def test_bulk_update_tags(self, manager):
        """Test bulk tag updates."""
        # Create notes
        notes = []
        for i in range(5):
            note = manager.create_note(
                f"entry-{i}",
                f"Content {i}",
                tags=["draft", "unreviewed"],
            )
            notes.append(note)

        # Bulk update tags
        updated = manager.bulk_update_tags(
            note_ids=[n.id for n in notes],
            add=["reviewed", "processed"],
            remove=["draft", "unreviewed"],
        )

        assert len(updated) == 5
        for note in updated:
            assert "reviewed" in note.tags
            assert "processed" in note.tags
            assert "draft" not in note.tags
            assert "unreviewed" not in note.tags

    def test_bulk_update_partial(self, manager):
        """Test bulk update with some invalid IDs."""
        # Create notes
        notes = []
        for i in range(3):
            note = manager.create_note(f"e{i}", f"Content {i}", tags=["old"])
            notes.append(note)

        # Include some invalid IDs
        note_ids = [n.id for n in notes] + ["invalid1", "invalid2"]

        updated = manager.bulk_update_tags(
            note_ids=note_ids,
            add=["new"],
            remove=["old"],
        )

        # Should update only valid notes
        assert len(updated) == 3
        for note in updated:
            assert "new" in note.tags
            assert "old" not in note.tags

    def test_merge_notes(self, manager):
        """Test merging multiple notes."""
        # Create notes to merge
        note1 = manager.create_note(
            "test", "First content", title="Note 1", tags=["tag1"]
        )
        note2 = manager.create_note(
            "test", "Second content", title="Note 2", tags=["tag2"]
        )
        note3 = manager.create_note(
            "test", "Third content", title="Note 3", tags=["tag1", "tag3"]
        )

        # Merge them
        merged = manager.merge_notes(
            note_ids=[note1.id, note2.id, note3.id],
            title="Merged Notes",
        )

        assert merged.title == "Merged Notes"
        assert "First content" in merged.content
        assert "Second content" in merged.content
        assert "Third content" in merged.content
        # Tags should be combined
        assert set(merged.tags) == {"tag1", "tag2", "tag3"}

        # Original notes should be deleted
        assert manager.get_note(note1.id) is None
        assert manager.get_note(note2.id) is None
        assert manager.get_note(note3.id) is None

    def test_split_note(self, manager):
        """Test splitting a note into sections."""
        # Create note with sections
        content = """# Section 1
Content for section 1

# Section 2
Content for section 2

# Section 3
Content for section 3"""

        note = manager.create_note("test", content, title="Original")

        # Split by sections
        sections = ["# Section 1", "# Section 2", "# Section 3"]
        split_notes = manager.split_note(note.id, sections)

        assert len(split_notes) == 3
        assert "Section 1" in split_notes[0].content
        assert "Section 2" in split_notes[1].content
        assert "Section 3" in split_notes[2].content

        # Original should be deleted
        assert manager.get_note(note.id) is None


class TestVersionOperations:
    """Test version management operations."""

    def test_get_note_history(self, manager):
        """Test getting note version history."""
        # Create and update note
        note = manager.create_note("test", "Version 1")

        manager.update_note(note.id, content="Version 2")
        manager.update_note(note.id, content="Version 3")
        manager.update_note(note.id, content="Version 4")

        # Get history
        history = manager.get_note_history(note.id)

        assert len(history) == 4
        assert history[0].content == "Version 1"
        assert history[1].content == "Version 2"
        assert history[2].content == "Version 3"
        assert history[3].content == "Version 4"

    def test_restore_version(self, manager):
        """Test restoring a previous version."""
        # Create and update note
        note = manager.create_note("test", "Original", title="Title")

        manager.update_note(note.id, content="Modified")
        manager.update_note(note.id, content="Current")

        # Restore version 1
        restored = manager.restore_note_version(note.id, version=1)

        assert restored.content == "Original"
        assert restored.title == "Title"  # Metadata preserved
        assert restored.version == 4  # New version after restore

    def test_restore_invalid_version(self, manager):
        """Test restoring invalid version."""
        note = manager.create_note("test", "Content")

        with pytest.raises(ValueError):
            manager.restore_note_version(note.id, version=999)

    def test_compare_versions(self, manager):
        """Test comparing versions."""
        # Create and update note
        note = manager.create_note("test", "Line 1\nLine 2\nLine 3")

        manager.update_note(note.id, content="Line 1\nLine 2 modified\nLine 3")
        manager.update_note(note.id, content="Line 1\nLine 2 modified\nLine 3\nLine 4")

        # Compare versions
        diff = manager.compare_versions(note.id, v1=1, v2=3)

        assert "-Line 2" in diff
        assert "+Line 2 modified" in diff
        assert "+Line 4" in diff


class TestExportOperations:
    """Test export functionality."""

    def test_export_notes_markdown(self, manager):
        """Test exporting notes as markdown."""
        # Create notes
        manager.create_note("test", "Note 1 content", title="Note 1", type="summary")
        manager.create_note("test", "Note 2 content", title="Note 2", type="critique")

        # Export
        markdown = manager.export_notes("test", format="markdown")

        assert "# Note 1" in markdown
        assert "Note 1 content" in markdown
        assert "# Note 2" in markdown
        assert "Note 2 content" in markdown
        assert "**Type**: summary" in markdown
        assert "**Type**: critique" in markdown

    def test_export_quotes_markdown(self, manager):
        """Test exporting quotes as markdown."""
        # Add quotes
        manager.add_quote("test", "Quote 1", page=10)
        manager.add_quote("test", "Quote 2", page=20)
        manager.add_quote("test", "Quote 3")

        # Export
        markdown = manager.export_quotes("test", format="markdown")

        assert "> Quote 1" in markdown
        assert "> Quote 2" in markdown
        assert "> Quote 3" in markdown
        assert "(p. 10)" in markdown
        assert "(p. 20)" in markdown

    def test_export_quotes_latex(self, manager):
        """Test exporting quotes as LaTeX."""
        # Add quotes
        manager.add_quote("test", "Important quote", page=42)

        # Export
        latex = manager.export_quotes("test", format="latex")

        assert "\\begin{quote}" in latex
        assert "Important quote" in latex
        assert "\\cite{test}" in latex
        assert "(p. 42)" in latex
        assert "\\end{quote}" in latex

    def test_export_reading_report(self, manager):
        """Test exporting reading progress report."""
        # Track reading for multiple entries
        manager.track_reading("paper1", page=100, total_pages=200, priority=3)
        manager.track_reading("paper2", page=200, total_pages=200, priority=5)
        manager.track_reading("paper3", page=0, total_pages=150, priority=1)

        # Export report
        report = manager.export_reading_report()

        assert "paper1" in report
        assert "paper2" in report
        assert "paper3" in report
        assert "50%" in report or "50.0" in report  # Progress for paper1
        assert "100%" in report or "100.0" in report  # Progress for paper2

    def test_export_empty_entry(self, manager):
        """Test exporting empty entry."""
        # Export notes for entry with no data
        markdown = manager.export_notes("nonexistent", format="markdown")
        assert markdown == "" or "No notes" in markdown

        quotes = manager.export_quotes("nonexistent", format="markdown")
        assert quotes == "" or "No quotes" in quotes


class TestStatistics:
    """Test statistics operations."""

    def test_get_global_statistics(self, manager):
        """Test getting global statistics."""
        # Create various data
        for i in range(5):
            manager.create_note(f"entry{i % 3}", f"Note {i}")

        for i in range(3):
            manager.add_quote(f"entry{i}", f"Quote {i}")

        for i in range(4):
            status = ["unread", "reading", "read", "reading"][i]
            manager.track_reading(f"entry{i}", status=status)

        stats = manager.get_statistics()

        assert stats["total_notes"] == 5
        assert stats["total_quotes"] == 3
        assert stats["entries_with_notes"] == 3
        assert stats["entries_in_progress"] == 2
        assert stats["entries_completed"] == 1

    def test_get_entry_statistics(self, manager):
        """Test getting entry-specific statistics."""
        # Create data for one entry
        manager.create_note("test", "Note 1", type="summary")
        manager.create_note("test", "Note 2", type="critique")
        manager.create_note("test", "Note 3", type="idea")

        manager.add_quote("test", "Quote 1", importance=5)
        manager.add_quote("test", "Quote 2", importance=3)

        # Track reading - session_count is managed internally
        manager.track_reading(
            "test",
            page=150,
            total_pages=300,
            time_minutes=180,
        )

        stats = manager.get_entry_statistics("test")

        assert stats["note_count"] == 3
        assert stats["quote_count"] == 2
        assert stats["reading_progress"] == 50.0
        assert stats["reading_time"] == 180
        assert stats["session_count"] == 1  # One session from the track_reading call
        assert stats["average_quote_importance"] == 4.0

        # Note type breakdown
        assert stats["note_types"]["summary"] == 1
        assert stats["note_types"]["critique"] == 1
        assert stats["note_types"]["idea"] == 1

    def test_statistics_empty_database(self, manager):
        """Test statistics on empty database."""
        stats = manager.get_statistics()

        assert stats["total_notes"] == 0
        assert stats["total_quotes"] == 0
        assert stats["entries_with_notes"] == 0


class TestConcurrentOperations:
    """Test concurrent access and thread safety."""

    def test_concurrent_note_creation(self, manager):
        """Test concurrent note creation."""

        def create_notes(start, count):
            notes = []
            for i in range(start, start + count):
                note = manager.create_note(
                    f"entry{i % 5}",
                    f"Content {i}",
                    tags=[f"tag{i % 3}"],
                )
                notes.append(note)
            return notes

        # Run concurrent creations
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(5):
                future = executor.submit(create_notes, i * 20, 20)
                futures.append(future)

            results = [f.result() for f in futures]

        # Verify all notes were created
        all_notes = []
        for batch in results:
            all_notes.extend(batch)

        assert len(all_notes) == 100

        # All should have unique IDs
        ids = [n.id for n in all_notes]
        assert len(set(ids)) == 100

    def test_concurrent_updates(self, manager):
        """Test concurrent updates to different notes."""
        # Create notes
        notes = []
        for i in range(10):
            note = manager.create_note(f"e{i}", f"Original {i}")
            notes.append(note)

        def update_note(note):
            return manager.update_note(
                note.id,
                content=f"Updated by thread {threading.current_thread().name}",
            )

        # Run concurrent updates
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(update_note, n) for n in notes]
            results = [f.result() for f in futures]

        # All updates should succeed
        assert all(r is not None for r in results)
        assert all("Updated by thread" in r.content for r in results)

    def test_concurrent_search(self, manager):
        """Test concurrent search operations."""
        # Create searchable content
        for i in range(100):
            manager.create_note(
                f"e{i}",
                f"Content with keyword{i % 10}",
                tags=[f"tag{i % 5}"],
            )

        def search(query):
            return manager.search_notes(query)

        # Run concurrent searches
        queries = [f"keyword{i}" for i in range(10)]
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(search, q) for q in queries]
            results = [f.result() for f in futures]

        # All searches should return results
        assert all(len(r) > 0 for r in results)


class TestErrorHandling:
    """Test error handling and validation."""

    def test_create_note_validation(self, manager):
        """Test note creation validation."""
        # Missing entry key
        with pytest.raises(ValueError):
            manager.create_note(entry_key=None, content="Content")

        # Empty entry key
        with pytest.raises(ValueError):
            manager.create_note(entry_key="", content="Content")

        # Invalid type
        with pytest.raises(ValueError):
            manager.create_note("test", "Content", type="invalid_type")

    def test_quote_validation(self, manager):
        """Test quote validation."""
        # Empty text
        with pytest.raises(ValueError):
            manager.add_quote("test", text="")

        # Invalid importance
        with pytest.raises(ValueError):
            manager.add_quote("test", "Text", importance=0)

        with pytest.raises(ValueError):
            manager.add_quote("test", "Text", importance=6)

    def test_template_validation(self, manager):
        """Test template validation."""
        # Invalid template name
        with pytest.raises(ValueError):
            manager.create_note_from_template(
                "test",
                template_name="",
            )

        # Missing required variables
        with pytest.raises(KeyError):
            manager.create_note_from_template(
                "test",
                template_name="paper_review",
                # Missing title, authors, year
            )

    def test_merge_validation(self, manager):
        """Test merge operation validation."""
        # Empty list
        with pytest.raises(ValueError):
            manager.merge_notes(note_ids=[], title="Merged")

        # Invalid IDs
        with pytest.raises(ValueError):
            manager.merge_notes(
                note_ids=["invalid1", "invalid2"],
                title="Merged",
            )

        # Single note
        note = manager.create_note("test", "Content")
        with pytest.raises(ValueError):
            manager.merge_notes(note_ids=[note.id], title="Merged")

    def test_version_validation(self, manager):
        """Test version operation validation."""
        note = manager.create_note("test", "Content")

        # Invalid version number
        with pytest.raises(ValueError):
            manager.restore_note_version(note.id, version=0)

        with pytest.raises(ValueError):
            manager.restore_note_version(note.id, version=-1)

        # Nonexistent note
        with pytest.raises(ValueError):
            manager.restore_note_version("nonexistent", version=1)

    def test_oversized_content_handling(self, manager):
        """Test handling of oversized content."""
        # 10 MB of text
        huge_content = "x" * (10 * 1024 * 1024)

        # Should either accept or reject with clear error
        try:
            note = manager.create_note("test", huge_content)
            # If accepted, should be retrievable
            retrieved = manager.get_note(note.id)
            assert retrieved is not None
            assert len(retrieved.content) == len(huge_content)
        except ValueError as e:
            # Should have clear error message
            assert "size" in str(e).lower() or "large" in str(e).lower()


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_research_workflow(self, manager):
        """Test complete research workflow."""
        entry_key = "smith2024"

        # 1. Start tracking reading
        progress = manager.track_reading(
            entry_key,
            page=1,
            total_pages=250,
            priority=3,
        )

        # 2. Create initial notes from template
        manager.create_note_from_template(
            entry_key,
            "paper_review",
            title="Advanced Machine Learning",
            authors="Smith et al.",
            year="2024",
            summary="This paper presents novel approaches to deep learning",
        )

        # 3. Add quotes while reading
        quotes = []
        quotes.append(
            manager.add_quote(
                entry_key,
                "Novel approach to deep learning",
                page=15,
                category="methodology",
                importance=5,
            )
        )
        quotes.append(
            manager.add_quote(
                entry_key,
                "Significant improvement over baseline",
                page=87,
                category="finding",
                importance=4,
            )
        )

        # 4. Update reading progress
        progress = manager.track_reading(
            entry_key,
            page=100,
            time_minutes=120,
        )

        # 5. Add more notes
        manager.create_note(
            entry_key,
            "Summary of methodology section",
            type="summary",
            tags=["methodology", "important"],
        )

        manager.create_note(
            entry_key,
            "Potential issues with experimental design",
            type="critique",
            tags=["methodology", "concerns"],
        )

        # 6. Complete reading
        progress = manager.track_reading(
            entry_key,
            page=250,
            time_minutes=60,
        )

        # 7. Export everything
        notes_export = manager.export_notes(entry_key)
        quotes_export = manager.export_quotes(entry_key)

        # Verify complete workflow
        assert progress.is_complete
        assert progress.total_pages == 250
        assert progress.reading_time_minutes == 180

        all_notes = manager.get_notes(entry_key)
        assert len(all_notes) == 3

        all_quotes = manager.get_quotes(entry_key)
        assert len(all_quotes) == 2

        # Exports should contain all content
        assert "Advanced Machine Learning" in notes_export
        assert "Novel approach" in quotes_export

    def test_collaborative_workflow(self, manager):
        """Test collaborative note-taking workflow."""
        entry_key = "collab2024"

        # Simulate multiple users adding notes
        users = ["alice", "bob", "charlie"]

        for user in users:
            # Each user adds their notes
            manager.create_note(
                entry_key,
                f"{user}'s summary of the paper",
                type="summary",
                tags=[user, "summary"],
            )

            # Each user adds quotes
            manager.add_quote(
                entry_key,
                f"Important point noted by {user}",
                tags=[user],
            )

        # Merge all summaries
        summaries = manager.get_notes(entry_key, type="summary")
        merged = manager.merge_notes(
            note_ids=[s.id for s in summaries],
            title="Combined Summary",
        )

        # Verify collaborative result
        assert "alice's summary" in merged.content
        assert "bob's summary" in merged.content
        assert "charlie's summary" in merged.content

        # All user tags should be present
        assert set(["alice", "bob", "charlie", "summary"]).issubset(set(merged.tags))

        # Quotes should all be preserved
        quotes = manager.get_quotes(entry_key)
        assert len(quotes) == 3
