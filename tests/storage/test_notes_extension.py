"""Tests for notes storage extension."""

import pytest

from bibmgr.storage.backends.filesystem import FileSystemBackend
from bibmgr.storage.extensions.notes import (
    NotesExtension,
    NoteType,
    ReadingStatus,
)


class TestNotesExtension:
    """Test notes extension for storage."""

    @pytest.fixture
    def storage_with_notes(self, tmp_path):
        """Create storage backend with notes extension."""
        backend = FileSystemBackend(tmp_path)
        extension = NotesExtension(backend)
        return extension

    def test_create_note(self, storage_with_notes):
        """Test creating a note."""
        note = storage_with_notes.create_note(
            entry_key="test123",
            content="This is a test note",
            type=NoteType.SUMMARY,
            title="Test Summary",
            tags=["test", "summary"],
        )

        assert note.id
        assert note.entry_key == "test123"
        assert note.content == "This is a test note"
        assert note.type == NoteType.SUMMARY
        assert note.title == "Test Summary"
        assert note.tags == ["test", "summary"]
        assert note.version == 1

    def test_update_note(self, storage_with_notes):
        """Test updating a note."""
        # Create note
        note = storage_with_notes.create_note(
            entry_key="test123",
            content="Original content",
        )

        # Update it
        updated = storage_with_notes.update_note(
            note.id,
            content="Updated content",
            tags=["updated"],
        )

        assert updated.content == "Updated content"
        assert updated.tags == ["updated"]
        assert updated.version == 2
        assert updated.updated_at > note.created_at

    def test_note_versioning(self, storage_with_notes):
        """Test note version history."""
        # Create and update note multiple times
        note = storage_with_notes.create_note(
            entry_key="test123",
            content="Version 1",
        )

        storage_with_notes.update_note(note.id, content="Version 2")
        storage_with_notes.update_note(note.id, content="Version 3")

        # Get history
        history = storage_with_notes.get_note_history(note.id)
        assert len(history) == 3
        assert history[0].content == "Version 1"
        assert history[1].content == "Version 2"
        assert history[2].content == "Version 3"

    def test_delete_note(self, storage_with_notes):
        """Test deleting a note."""
        note = storage_with_notes.create_note(
            entry_key="test123",
            content="To be deleted",
        )

        # Delete
        assert storage_with_notes.delete_note(note.id)

        # Should be gone
        assert storage_with_notes.get_note(note.id) is None

        # History should also be gone
        assert storage_with_notes.get_note_history(note.id) == []

    def test_get_entry_notes(self, storage_with_notes):
        """Test getting notes for an entry."""
        # Create multiple notes for same entry
        storage_with_notes.create_note(
            entry_key="paper123",
            content="First note",
            type=NoteType.GENERAL,
        )
        storage_with_notes.create_note(
            entry_key="paper123",
            content="Summary note",
            type=NoteType.SUMMARY,
        )
        storage_with_notes.create_note(
            entry_key="other456",
            content="Different entry",
        )

        # Get notes for paper123
        notes = storage_with_notes.get_entry_notes("paper123")
        assert len(notes) == 2

        # Filter by type
        summaries = storage_with_notes.get_entry_notes(
            "paper123", type=NoteType.SUMMARY
        )
        assert len(summaries) == 1
        assert summaries[0].content == "Summary note"

    def test_search_notes(self, storage_with_notes):
        """Test searching notes."""
        # Create notes with different attributes
        storage_with_notes.create_note(
            entry_key="paper1",
            content="Machine learning is powerful",
            tags=["ml", "intro"],
            type=NoteType.GENERAL,
        )
        storage_with_notes.create_note(
            entry_key="paper2",
            content="Deep learning revolutionized CV",
            tags=["dl", "cv"],
            type=NoteType.SUMMARY,
        )
        storage_with_notes.create_note(
            entry_key="paper3",
            content="Transfer learning is effective",
            tags=["ml", "transfer"],
            type=NoteType.GENERAL,
        )

        # Search by text
        ml_notes = storage_with_notes.search_notes(query="learning")
        assert len(ml_notes) == 3

        # Search by tag
        ml_tag_notes = storage_with_notes.search_notes(tags=["ml"])
        assert len(ml_tag_notes) == 2

        # Search by type
        summaries = storage_with_notes.search_notes(type=NoteType.SUMMARY)
        assert len(summaries) == 1

    def test_add_quote(self, storage_with_notes):
        """Test adding quotes."""
        quote = storage_with_notes.add_quote(
            entry_key="paper123",
            text="This is an important finding",
            page=42,
            tags=["important", "finding"],
            comment="Consider for introduction",
        )

        assert quote.id
        assert quote.entry_key == "paper123"
        assert quote.text == "This is an important finding"
        assert quote.page == 42
        assert quote.tags == ["important", "finding"]
        assert quote.comment == "Consider for introduction"

    def test_quote_with_location(self, storage_with_notes):
        """Test quotes with location instead of page."""
        quote = storage_with_notes.add_quote(
            entry_key="ebook123",
            text="Digital quote",
            location="Chapter 3, Section 2",
            tags=["digital"],
        )

        assert quote.location == "Chapter 3, Section 2"
        assert quote.page is None

    def test_get_entry_quotes(self, storage_with_notes):
        """Test getting quotes for an entry."""
        # Add multiple quotes
        storage_with_notes.add_quote(
            entry_key="paper123",
            text="First quote",
            page=10,
        )
        storage_with_notes.add_quote(
            entry_key="paper123",
            text="Second quote",
            page=20,
        )
        storage_with_notes.add_quote(
            entry_key="other456",
            text="Different paper",
            page=5,
        )

        # Get quotes for paper123
        quotes = storage_with_notes.get_entry_quotes("paper123")
        assert len(quotes) == 2
        assert quotes[0].text == "First quote"  # Sorted by creation time

    def test_search_quotes(self, storage_with_notes):
        """Test searching quotes."""
        # Add quotes with different attributes
        storage_with_notes.add_quote(
            entry_key="paper1",
            text="Machine learning is powerful",
            tags=["ml", "intro"],
        )
        storage_with_notes.add_quote(
            entry_key="paper2",
            text="Deep learning revolutionized CV",
            tags=["dl", "cv"],
        )
        storage_with_notes.add_quote(
            entry_key="paper1",
            text="Transfer learning is effective",
            tags=["ml", "transfer"],
        )

        # Search by text
        ml_quotes = storage_with_notes.search_quotes(query="learning")
        assert len(ml_quotes) == 3

        # Search by tag
        ml_tag_quotes = storage_with_notes.search_quotes(tags=["ml"])
        assert len(ml_tag_quotes) == 2

    def test_reading_progress(self, storage_with_notes):
        """Test reading progress tracking."""
        # Create progress
        progress = storage_with_notes.track_reading_progress(
            entry_key="book123",
            current_page=50,
            total_pages=300,
            status=ReadingStatus.READING,
        )

        assert progress.entry_key == "book123"
        assert progress.current_page == 50
        assert progress.total_pages == 300
        assert progress.status == ReadingStatus.READING
        assert progress.percentage == pytest.approx(16.67, 0.01)

        # Update progress
        updated = storage_with_notes.update_reading_progress(
            entry_key="book123",
            current_page=150,
            notes="Halfway through, very interesting",
        )

        assert updated.current_page == 150
        assert updated.percentage == 50.0
        assert updated.notes == "Halfway through, very interesting"

    def test_reading_status_transitions(self, storage_with_notes):
        """Test reading status transitions."""
        # Start reading
        progress = storage_with_notes.track_reading_progress(
            entry_key="book123",
            status=ReadingStatus.READING,
            total_pages=200,
        )

        assert progress.started_at is not None
        assert progress.finished_at is None

        # Finish reading
        finished = storage_with_notes.track_reading_progress(
            entry_key="book123",
            status=ReadingStatus.READ,
            current_page=200,
        )

        assert finished.finished_at is not None

    def test_reading_sessions(self, storage_with_notes):
        """Test reading session tracking."""
        # Track a reading session
        session = storage_with_notes.add_reading_session(
            entry_key="paper123",
            duration_minutes=45,
            pages_read=15,
            notes="Focused on methodology section",
        )

        assert session.duration_minutes == 45
        assert session.pages_read == 15
        assert session.notes == "Focused on methodology section"

        # Get reading stats
        stats = storage_with_notes.get_reading_stats("paper123")
        assert stats["total_time_minutes"] == 45
        assert stats["total_pages_read"] == 15
        assert stats["session_count"] == 1
        assert stats["avg_pages_per_session"] == 15.0
        assert stats["avg_session_duration"] == 45.0

    def test_multiple_reading_sessions(self, storage_with_notes):
        """Test multiple reading sessions."""
        # Add multiple sessions
        storage_with_notes.add_reading_session("book123", 30, 20)
        storage_with_notes.add_reading_session("book123", 45, 35)
        storage_with_notes.add_reading_session("book123", 60, 40)

        # Check stats
        stats = storage_with_notes.get_reading_stats("book123")
        assert stats["session_count"] == 3
        assert stats["total_time_minutes"] == 135
        assert stats["total_pages_read"] == 95
        assert stats["avg_session_duration"] == 45.0

    def test_bulk_update_tags(self, storage_with_notes):
        """Test bulk operations on notes."""
        # Create multiple notes
        note_ids = []
        for i in range(5):
            note = storage_with_notes.create_note(
                entry_key="test123",
                content=f"Note {i}",
                tags=[f"tag{i}"],
            )
            note_ids.append(note.id)

        # Bulk tag update
        updated = storage_with_notes.bulk_update_tags(
            note_ids=note_ids[:3],
            add_tags=["bulk", "updated"],
            remove_tags=["tag0"],
        )

        assert len(updated) == 3

        # Verify updates
        for i, note_id in enumerate(note_ids[:3]):
            note = storage_with_notes.get_note(note_id)
            assert "bulk" in note.tags
            assert "updated" in note.tags
            if i == 0:
                assert "tag0" not in note.tags

    def test_notes_persistence(self, tmp_path):
        """Test that notes persist across instances."""
        # Create notes with first instance
        backend1 = FileSystemBackend(tmp_path)
        extension1 = NotesExtension(backend1)

        note = extension1.create_note(
            entry_key="test123",
            content="Persistent note",
            tags=["test"],
        )
        note_id = note.id

        extension1.add_quote(
            entry_key="test123",
            text="Persistent quote",
        )

        # Create new instance and check persistence
        backend2 = FileSystemBackend(tmp_path)
        extension2 = NotesExtension(backend2)

        loaded_note = extension2.get_note(note_id)
        assert loaded_note is not None
        assert loaded_note.content == "Persistent note"

        quotes = extension2.get_entry_quotes("test123")
        assert len(quotes) == 1
        assert quotes[0].text == "Persistent quote"

    def test_empty_content_handling(self, storage_with_notes):
        """Test handling of empty content."""
        # Should allow empty content
        note = storage_with_notes.create_note(
            entry_key="test123",
            content="",
            title="Note with empty content",
        )

        assert note.content == ""
        assert note.title == "Note with empty content"

    def test_note_types(self, storage_with_notes):
        """Test different note types."""
        types = [
            NoteType.GENERAL,
            NoteType.SUMMARY,
            NoteType.CRITIQUE,
            NoteType.IDEA,
            NoteType.QUESTION,
            NoteType.TODO,
        ]

        for note_type in types:
            note = storage_with_notes.create_note(
                entry_key="test123",
                content=f"Note of type {note_type.value}",
                type=note_type,
            )
            assert note.type == note_type

    def test_reading_progress_rating(self, storage_with_notes):
        """Test reading progress with rating."""
        progress = storage_with_notes.track_reading_progress(
            entry_key="book123",
            status=ReadingStatus.READ,
            rating=5,
        )

        assert progress.rating == 5

        # Update rating
        updated = storage_with_notes.update_reading_progress(
            entry_key="book123",
            rating=4,
        )

        assert updated.rating == 4
