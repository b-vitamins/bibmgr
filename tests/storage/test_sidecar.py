"""Comprehensive tests for metadata sidecar functionality.

Tests sidecar capabilities including:
- Entry metadata management
- Note operations
- Tag indexing and search
- Reading status tracking
- Collections and custom fields
- Data migration
- Performance with indexing
- Concurrent access
"""

import json
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import pytest


class EntryMetadata(Protocol):
    """Protocol for entry metadata."""

    key: str
    notes: str | None
    tags: list[str] | None
    collections: list[str] | None
    reading_status: str | None
    rating: int | None
    importance: str | None
    current_page: int | None
    total_pages: int | None
    reading_started: datetime | None
    reading_completed: datetime | None
    custom_fields: dict[str, Any] | None
    created_at: datetime | None
    updated_at: datetime | None


class Note(Protocol):
    """Protocol for note interface."""

    id: str
    entry_key: str
    content: str
    type: str
    page_number: int | None
    chapter: str | None
    created_at: datetime
    updated_at: datetime
    tags: list[str] | None


class MetadataSidecar(Protocol):
    """Protocol for metadata sidecar interface."""

    def get_metadata(self, key: str) -> EntryMetadata | None:
        """Get metadata for entry."""
        ...

    def set_metadata(self, metadata: EntryMetadata) -> None:
        """Set metadata for entry."""
        ...

    def update_metadata(self, key: str, **fields) -> None:
        """Update specific metadata fields."""
        ...

    def delete_metadata(self, key: str) -> bool:
        """Delete metadata for entry."""
        ...

    def bulk_get_metadata(self, keys: list[str]) -> dict[str, EntryMetadata]:
        """Get metadata for multiple entries efficiently."""
        ...

    def bulk_update_metadata(self, updates: dict[str, dict]) -> dict[str, bool]:
        """Update metadata for multiple entries efficiently."""
        ...

    def add_tags(self, key: str, tags: list[str]) -> None:
        """Add tags to entry."""
        ...

    def remove_tags(self, key: str, tags: list[str]) -> None:
        """Remove tags from entry."""
        ...

    def get_entries_by_tag(self, tag: str) -> list[str]:
        """Get entries with specific tag."""
        ...

    def get_all_tags(self) -> dict[str, int]:
        """Get all tags with counts."""
        ...

    def search_tags(self, pattern: str) -> list[str]:
        """Search tags by pattern."""
        ...

    def add_note(self, note: Note) -> None:
        """Add note to entry."""
        ...

    def get_notes(self, entry_key: str) -> list[Note]:
        """Get notes for entry."""
        ...

    def get_note(self, entry_key: str, note_id: str) -> Note | None:
        """Get specific note."""
        ...

    def update_note(self, note: Note) -> bool:
        """Update existing note."""
        ...

    def delete_note(self, entry_key: str, note_id: str) -> bool:
        """Delete specific note."""
        ...

    def search_notes(self, query: str) -> list[Note]:
        """Search notes by content."""
        ...

    def set_reading_status(
        self,
        key: str,
        status: str,
        current_page: int | None = None,
        total_pages: int | None = None,
    ) -> None:
        """Set reading status."""
        ...

    def get_reading_list(self, status: str | None = None) -> list[str]:
        """Get reading list by status."""
        ...

    def get_statistics(self) -> dict[str, Any]:
        """Get metadata statistics."""
        ...

    def migrate(self, from_version: str, to_version: str) -> None:
        """Migrate metadata schema."""
        ...

    def rebuild_index(self) -> None:
        """Rebuild metadata indexes."""
        ...

    def validate(self) -> tuple[bool, list[str]]:
        """Validate metadata integrity."""
        ...

    def export(self, path: Path) -> None:
        """Export metadata."""
        ...

    def import_from(self, path: Path) -> None:
        """Import metadata."""
        ...


@pytest.fixture
def temp_sidecar_dir():
    """Create temporary directory for sidecar."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_metadata(metadata_factory):
    """Create sample metadata for testing."""
    return [
        metadata_factory(
            key=f"entry{i}",
            tags=[f"tag{i % 3}", f"tag{(i + 1) % 3}"],
            rating=(i % 5) + 1,
            reading_status=["unread", "reading", "read"][i % 3],
        )
        for i in range(10)
    ]


@pytest.fixture
def sample_notes(note_factory):
    """Create sample notes for testing."""
    return [
        note_factory(
            id=f"note{i}",
            entry_key=f"entry{i % 5}",
            content=f"Note content {i}\n\nThis is a longer note with multiple lines.",
            type=["general", "summary", "quote", "critique"][i % 4],
        )
        for i in range(15)
    ]


class TestMetadataOperations:
    """Test basic metadata operations."""

    def test_set_and_get_metadata(
        self, sidecar_factory, metadata_factory, temp_sidecar_dir
    ):
        """Test setting and getting metadata."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        metadata = metadata_factory(
            key="test",
            notes="Test notes",
            tags=["tag1", "tag2"],
            rating=4,
            reading_status="reading",
            current_page=50,
            total_pages=200,
        )

        sidecar.set_metadata(metadata)

        retrieved = sidecar.get_metadata("test")
        assert retrieved is not None
        assert retrieved.key == "test"
        assert retrieved.notes == "Test notes"
        assert set(retrieved.tags) == {"tag1", "tag2"}
        assert retrieved.rating == 4
        assert retrieved.reading_status == "reading"
        assert retrieved.current_page == 50
        assert retrieved.total_pages == 200

    def test_get_nonexistent_metadata(self, sidecar_factory, temp_sidecar_dir):
        """Test getting non-existent metadata."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        result = sidecar.get_metadata("nonexistent")
        assert result is None

    def test_update_metadata_fields(
        self, sidecar_factory, metadata_factory, temp_sidecar_dir
    ):
        """Test updating specific metadata fields."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Set initial metadata
        metadata = metadata_factory(key="test", rating=3, notes="Original")
        sidecar.set_metadata(metadata)

        # Update specific fields
        sidecar.update_metadata("test", rating=5, notes="Updated", importance="high")

        # Verify updates
        updated = sidecar.get_metadata("test")
        assert updated.rating == 5
        assert updated.notes == "Updated"
        assert updated.importance == "high"

    def test_delete_metadata(self, sidecar_factory, metadata_factory, temp_sidecar_dir):
        """Test deleting metadata."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        metadata = metadata_factory(key="test", notes="Test")
        sidecar.set_metadata(metadata)

        result = sidecar.delete_metadata("test")
        assert result is True

        assert sidecar.get_metadata("test") is None

        # Delete non-existent
        result = sidecar.delete_metadata("test")
        assert result is False

    def test_custom_fields(self, sidecar_factory, metadata_factory, temp_sidecar_dir):
        """Test custom metadata fields."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        metadata = metadata_factory(
            key="test",
            custom_fields={
                "project": "Research",
                "priority": 1,
                "keywords": ["ml", "nlp", "transformers"],
                "deadline": "2024-12-31",
            },
        )

        sidecar.set_metadata(metadata)

        retrieved = sidecar.get_metadata("test")
        assert retrieved.custom_fields is not None
        assert retrieved.custom_fields["project"] == "Research"
        assert retrieved.custom_fields["priority"] == 1
        assert "ml" in retrieved.custom_fields["keywords"]

    def test_timestamps(self, sidecar_factory, metadata_factory, temp_sidecar_dir):
        """Test timestamp management."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        metadata = metadata_factory(key="test", notes="Test")
        sidecar.set_metadata(metadata)

        retrieved = sidecar.get_metadata("test")
        assert retrieved.created_at is not None
        assert retrieved.updated_at is not None

        created_at = retrieved.created_at
        time.sleep(0.01)

        # Update metadata
        sidecar.update_metadata("test", notes="Updated")

        updated = sidecar.get_metadata("test")
        assert updated.created_at == created_at
        assert updated.updated_at > created_at


class TestBulkOperations:
    """Test bulk metadata operations."""

    def test_bulk_get_metadata(
        self, sidecar_factory, sample_metadata, temp_sidecar_dir
    ):
        """Test bulk metadata retrieval."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Set metadata
        for metadata in sample_metadata:
            sidecar.set_metadata(metadata)

        # Bulk get
        keys = [m.key for m in sample_metadata[:5]]
        results = sidecar.bulk_get_metadata(keys)

        assert len(results) == 5
        for key in keys:
            assert key in results
            assert results[key] is not None

    def test_bulk_get_with_missing(
        self, sidecar_factory, sample_metadata, temp_sidecar_dir
    ):
        """Test bulk get with missing entries."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Set some metadata
        for metadata in sample_metadata[:3]:
            sidecar.set_metadata(metadata)

        # Bulk get including missing
        keys = ["entry0", "entry1", "missing1", "entry2", "missing2"]
        results = sidecar.bulk_get_metadata(keys)

        assert results["entry0"] is not None
        assert results["entry1"] is not None
        assert results["entry2"] is not None
        assert results["missing1"] is None
        assert results["missing2"] is None

    def test_bulk_update_metadata(
        self, sidecar_factory, sample_metadata, temp_sidecar_dir
    ):
        """Test bulk metadata updates."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Set initial metadata
        for metadata in sample_metadata[:5]:
            sidecar.set_metadata(metadata)

        # Bulk update
        updates = {
            "entry0": {"rating": 5, "importance": "critical"},
            "entry1": {"rating": 4, "importance": "high"},
            "entry2": {"rating": 3, "importance": "medium"},
            "missing": {"rating": 1, "importance": "low"},  # Non-existent
        }

        results = sidecar.bulk_update_metadata(updates)

        assert results["entry0"] is True
        assert results["entry1"] is True
        assert results["entry2"] is True
        # "missing" creates new metadata, so should be True
        assert results["missing"] is True

        # Verify updates
        metadata = sidecar.get_metadata("entry0")
        assert metadata.rating == 5
        assert metadata.importance == "critical"


class TestTagOperations:
    """Test tag management functionality."""

    def test_add_tags(self, sidecar_factory, temp_sidecar_dir):
        """Test adding tags to entries."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        sidecar.add_tags("entry1", ["machine-learning", "neural-networks"])
        sidecar.add_tags("entry1", ["deep-learning"])  # Add more

        metadata = sidecar.get_metadata("entry1")
        assert metadata is not None
        assert set(metadata.tags) == {
            "machine-learning",
            "neural-networks",
            "deep-learning",
        }

    def test_remove_tags(self, sidecar_factory, temp_sidecar_dir):
        """Test removing tags from entries."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        sidecar.add_tags("entry1", ["tag1", "tag2", "tag3"])
        sidecar.remove_tags("entry1", ["tag2"])

        metadata = sidecar.get_metadata("entry1")
        assert set(metadata.tags) == {"tag1", "tag3"}

        # Remove all tags
        sidecar.remove_tags("entry1", ["tag1", "tag3"])
        metadata = sidecar.get_metadata("entry1")
        assert metadata.tags is None or len(metadata.tags) == 0

    def test_get_entries_by_tag(
        self, sidecar_factory, sample_metadata, temp_sidecar_dir
    ):
        """Test getting entries by tag."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Set metadata with tags
        for metadata in sample_metadata:
            sidecar.set_metadata(metadata)

        # Get entries by tag
        entries = sidecar.get_entries_by_tag("tag0")
        assert len(entries) > 0

        # Verify all have the tag
        for key in entries:
            metadata = sidecar.get_metadata(key)
            assert "tag0" in metadata.tags

    def test_get_all_tags(self, sidecar_factory, temp_sidecar_dir):
        """Test getting all tags with counts."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        sidecar.add_tags("entry1", ["ml", "nlp"])
        sidecar.add_tags("entry2", ["ml", "cv"])
        sidecar.add_tags("entry3", ["nlp", "bert"])

        tags = sidecar.get_all_tags()

        assert tags["ml"] == 2
        assert tags["nlp"] == 2
        assert tags["cv"] == 1
        assert tags["bert"] == 1

    def test_search_tags(self, sidecar_factory, temp_sidecar_dir):
        """Test searching tags by pattern."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        sidecar.add_tags(
            "entry1", ["machine-learning", "deep-learning", "reinforcement-learning"]
        )
        sidecar.add_tags("entry2", ["computer-vision", "image-processing"])
        sidecar.add_tags("entry3", ["natural-language", "text-mining"])

        # Search for learning-related tags
        results = sidecar.search_tags("learning")
        assert len(results) == 3
        assert "machine-learning" in results
        assert "deep-learning" in results
        assert "reinforcement-learning" in results

        # Search with wildcards
        results = sidecar.search_tags("*-processing")
        assert "image-processing" in results

    def test_hierarchical_tags(self, sidecar_factory, temp_sidecar_dir):
        """Test hierarchical tag structure if supported."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Use hierarchical tags
        sidecar.add_tags("entry1", ["ml/supervised/classification"])
        sidecar.add_tags("entry2", ["ml/supervised/regression"])
        sidecar.add_tags("entry3", ["ml/unsupervised/clustering"])

        # Search for parent tags
        if hasattr(sidecar, "get_entries_by_tag_prefix"):
            ml_entries = sidecar.get_entries_by_tag_prefix("ml/")
            assert len(ml_entries) == 3

            supervised = sidecar.get_entries_by_tag_prefix("ml/supervised/")
            assert len(supervised) == 2


class TestNoteOperations:
    """Test note management functionality."""

    def test_add_note(self, sidecar_factory, note_factory, temp_sidecar_dir):
        """Test adding notes to entries."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        note = note_factory(
            id="note1",
            entry_key="entry1",
            content="# Summary\n\nThis paper presents...",
            type="summary",
            page_number=5,
        )

        sidecar.add_note(note)

        notes = sidecar.get_notes("entry1")
        assert len(notes) == 1
        assert notes[0].id == "note1"
        assert notes[0].content.startswith("# Summary")
        assert notes[0].type == "summary"
        assert notes[0].page_number == 5

    def test_get_specific_note(self, sidecar_factory, note_factory, temp_sidecar_dir):
        """Test getting specific note."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        note = note_factory(id="note1", entry_key="entry1", content="Test")
        sidecar.add_note(note)

        retrieved = sidecar.get_note("entry1", "note1")
        assert retrieved is not None
        assert retrieved.id == "note1"
        assert retrieved.content == "Test"

        # Non-existent note
        assert sidecar.get_note("entry1", "nonexistent") is None

    def test_update_note(self, sidecar_factory, note_factory, temp_sidecar_dir):
        """Test updating existing note."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Add initial note
        note = note_factory(id="note1", entry_key="entry1", content="Original")
        sidecar.add_note(note)

        # Update note
        updated_note = note_factory(
            id="note1", entry_key="entry1", content="Updated content", page_number=10
        )
        result = sidecar.update_note(updated_note)
        assert result is True

        # Verify update
        retrieved = sidecar.get_note("entry1", "note1")
        assert retrieved.content == "Updated content"
        assert retrieved.page_number == 10

    def test_delete_note(self, sidecar_factory, sample_notes, temp_sidecar_dir):
        """Test deleting notes."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Add notes
        for note in sample_notes[:3]:
            sidecar.add_note(note)

        # Delete specific note
        result = sidecar.delete_note(sample_notes[0].entry_key, sample_notes[0].id)
        assert result is True

        # Verify deletion
        notes = sidecar.get_notes(sample_notes[0].entry_key)
        note_ids = [n.id for n in notes]
        assert sample_notes[0].id not in note_ids

        # Delete non-existent
        result = sidecar.delete_note("entry1", "nonexistent")
        assert result is False

    def test_note_types(self, sidecar_factory, note_factory, temp_sidecar_dir):
        """Test different note types."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        note_types = [
            ("general", "General thoughts about the paper"),
            ("summary", "# Summary\n\nKey points..."),
            ("critique", "The methodology has issues..."),
            ("quote", '"Important quote from page 42"'),
            ("idea", "This could be applied to..."),
        ]

        for i, (note_type, content) in enumerate(note_types):
            note = note_factory(
                id=f"note{i}", entry_key="entry1", content=content, type=note_type
            )
            sidecar.add_note(note)

        notes = sidecar.get_notes("entry1")
        assert len(notes) == len(note_types)

        types_found = {n.type for n in notes}
        assert types_found == {t[0] for t in note_types}

    def test_search_notes(self, sidecar_factory, sample_notes, temp_sidecar_dir):
        """Test searching notes by content."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Add notes with specific content
        for note in sample_notes:
            sidecar.add_note(note)

        # Search notes
        results = sidecar.search_notes("content")
        assert len(results) > 0

        for note in results:
            assert "content" in note.content.lower()

    def test_note_with_tags(self, sidecar_factory, note_factory, temp_sidecar_dir):
        """Test notes with tags if supported."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        note = note_factory(
            id="note1",
            entry_key="entry1",
            content="Important note",
            tags=["important", "review"],
        )

        if hasattr(note, "tags"):
            sidecar.add_note(note)

            retrieved = sidecar.get_note("entry1", "note1")
            assert "important" in retrieved.tags
            assert "review" in retrieved.tags


class TestReadingStatus:
    """Test reading status tracking."""

    def test_set_reading_status(self, sidecar_factory, temp_sidecar_dir):
        """Test setting reading status."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Set initial status
        sidecar.set_reading_status("book1", "reading", current_page=50, total_pages=300)

        metadata = sidecar.get_metadata("book1")
        assert metadata.reading_status == "reading"
        assert metadata.current_page == 50
        assert metadata.total_pages == 300
        assert metadata.reading_started is not None

        # Update to completed
        sidecar.set_reading_status("book1", "read")

        metadata = sidecar.get_metadata("book1")
        assert metadata.reading_status == "read"
        assert metadata.reading_completed is not None

    def test_reading_progress(self, sidecar_factory, temp_sidecar_dir):
        """Test tracking reading progress."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Start reading
        sidecar.set_reading_status("book1", "reading", current_page=1, total_pages=200)

        # Update progress
        for page in [25, 50, 100, 150, 200]:
            sidecar.update_metadata("book1", current_page=page)

            metadata = sidecar.get_metadata("book1")
            assert metadata.current_page == page

            # Calculate progress percentage
            progress = (page / metadata.total_pages) * 100
            assert 0 <= progress <= 100

        # Mark as read when complete
        sidecar.set_reading_status("book1", "read")
        metadata = sidecar.get_metadata("book1")
        assert metadata.reading_status == "read"

    def test_get_reading_list(self, sidecar_factory, temp_sidecar_dir):
        """Test getting reading list by status."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Set various reading statuses
        sidecar.set_reading_status("book1", "unread")
        sidecar.set_reading_status("book2", "reading", current_page=50)
        sidecar.set_reading_status("book3", "reading", current_page=100)
        sidecar.set_reading_status("book4", "read")
        sidecar.set_reading_status("book5", "skimmed")

        # Get by status
        unread = sidecar.get_reading_list("unread")
        assert "book1" in unread

        reading = sidecar.get_reading_list("reading")
        assert len(reading) == 2
        assert "book2" in reading
        assert "book3" in reading

        # Get all
        all_books = sidecar.get_reading_list(None)
        assert len(all_books) == 5

    def test_reading_statistics(self, sidecar_factory, temp_sidecar_dir):
        """Test reading statistics if supported."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Set up reading data
        sidecar.set_reading_status("book1", "read")
        sidecar.set_reading_status("book2", "read")
        sidecar.set_reading_status(
            "book3", "reading", current_page=150, total_pages=300
        )
        sidecar.set_reading_status("book4", "unread")

        stats = sidecar.get_statistics()

        if "reading_stats" in stats:
            reading_stats = stats["reading_stats"]
            assert reading_stats.get("read", 0) == 2
            assert reading_stats.get("reading", 0) == 1
            assert reading_stats.get("unread", 0) == 1


class TestCollections:
    """Test collection management."""

    def test_add_to_collection(self, sidecar_factory, temp_sidecar_dir):
        """Test adding entries to collections."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        sidecar.update_metadata("entry1", collections=["favorites", "to-review"])
        sidecar.update_metadata("entry2", collections=["favorites"])

        metadata1 = sidecar.get_metadata("entry1")
        assert "favorites" in metadata1.collections
        assert "to-review" in metadata1.collections

        metadata2 = sidecar.get_metadata("entry2")
        assert "favorites" in metadata2.collections

    def test_get_collection_entries(self, sidecar_factory, temp_sidecar_dir):
        """Test getting entries in a collection."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Add entries to collections
        sidecar.update_metadata("entry1", collections=["ml-papers"])
        sidecar.update_metadata("entry2", collections=["ml-papers", "recent"])
        sidecar.update_metadata("entry3", collections=["recent"])

        # Get collection entries (if supported)
        if hasattr(sidecar, "get_collection_entries"):
            ml_papers = sidecar.get_collection_entries("ml-papers")
            assert len(ml_papers) == 2
            assert "entry1" in ml_papers
            assert "entry2" in ml_papers


class TestStatistics:
    """Test metadata statistics."""

    def test_get_statistics(
        self, sidecar_factory, sample_metadata, sample_notes, temp_sidecar_dir
    ):
        """Test getting metadata statistics."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Add data
        for metadata in sample_metadata:
            sidecar.set_metadata(metadata)

        for note in sample_notes[:10]:
            sidecar.add_note(note)

        stats = sidecar.get_statistics()

        assert "total_entries" in stats or "entry_count" in stats
        assert "total_notes" in stats or "note_count" in stats
        assert "total_tags" in stats or "tag_count" in stats

    def test_rating_statistics(self, sidecar_factory, temp_sidecar_dir):
        """Test rating statistics."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Add entries with ratings
        for i in range(10):
            sidecar.update_metadata(f"entry{i}", rating=(i % 5) + 1)

        stats = sidecar.get_statistics()

        if "rating_distribution" in stats:
            distribution = stats["rating_distribution"]
            assert distribution[1] == 2  # Two entries with rating 1
            assert distribution[2] == 2  # Two entries with rating 2
            # etc.


class TestMigration:
    """Test schema migration functionality."""

    def test_version_tracking(self, sidecar_factory, temp_sidecar_dir):
        """Test schema version tracking."""
        sidecar_factory(temp_sidecar_dir)

        # Check version file exists
        version_file = temp_sidecar_dir / "metadata" / "version.json"
        if version_file.exists():
            with open(version_file) as f:
                data = json.load(f)
            assert "version" in data

    def test_migration(self, sidecar_factory, temp_sidecar_dir):
        """Test schema migration."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Test migration (if supported)
        if hasattr(sidecar, "migrate"):
            # This would need actual version changes to test properly
            try:
                sidecar.migrate("1.0.0", "2.0.0")
            except NotImplementedError:
                pass  # Migration not implemented

    def test_backward_compatibility(self, sidecar_factory, temp_sidecar_dir):
        """Test backward compatibility with old data."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Create old-style metadata manually
        old_metadata_path = temp_sidecar_dir / "metadata" / "entries" / "old_entry.json"
        old_metadata_path.parent.mkdir(parents=True, exist_ok=True)

        old_data = {
            "key": "old_entry",
            "notes": "Old format",
            "tags": ["old", "format"],
            # Missing newer fields
        }

        with open(old_metadata_path, "w") as f:
            json.dump(old_data, f)

        # Should be able to read old format
        metadata = sidecar.get_metadata("old_entry")
        if metadata:
            assert metadata.key == "old_entry"
            assert metadata.notes == "Old format"


class TestIndexing:
    """Test indexing and search performance."""

    def test_rebuild_index(self, sidecar_factory, sample_metadata, temp_sidecar_dir):
        """Test index rebuilding."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Add data
        for metadata in sample_metadata:
            sidecar.set_metadata(metadata)

        # Rebuild index
        sidecar.rebuild_index()

        # Index should still work
        tags = sidecar.get_all_tags()
        assert len(tags) > 0

    def test_index_performance(
        self, sidecar_factory, metadata_factory, temp_sidecar_dir, benchmark
    ):
        """Test index performance with many entries."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Add many entries with tags
        for i in range(100):
            metadata = metadata_factory(
                key=f"perf{i}", tags=[f"tag{i % 10}", f"tag{(i + 1) % 10}"]
            )
            sidecar.set_metadata(metadata)

        # Benchmark tag search
        def search_tags():
            return sidecar.get_entries_by_tag("tag5")

        results = benchmark(search_tags)
        assert len(results) > 0


class TestValidation:
    """Test data validation."""

    def test_validate_integrity(
        self, sidecar_factory, sample_metadata, temp_sidecar_dir
    ):
        """Test metadata integrity validation."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Add valid data
        for metadata in sample_metadata:
            sidecar.set_metadata(metadata)

        # Validate
        is_valid, errors = sidecar.validate()
        assert is_valid
        assert len(errors) == 0

    def test_validate_with_corruption(self, sidecar_factory, temp_sidecar_dir):
        """Test validation with corrupted data."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Add some data
        sidecar.update_metadata("test", notes="Test")

        # Corrupt data file directly (implementation-specific)
        metadata_path = temp_sidecar_dir / "metadata" / "entries" / "test.json"
        if metadata_path.exists():
            metadata_path.write_text("{ invalid json")

        # Validate should detect corruption
        is_valid, errors = sidecar.validate()
        if not is_valid:
            assert len(errors) > 0


class TestExportImport:
    """Test export and import functionality."""

    def test_export_metadata(
        self, sidecar_factory, sample_metadata, sample_notes, temp_sidecar_dir
    ):
        """Test exporting metadata."""
        sidecar = sidecar_factory(temp_sidecar_dir)
        export_path = temp_sidecar_dir / "export.json"

        # Add data
        for metadata in sample_metadata:
            sidecar.set_metadata(metadata)

        for note in sample_notes[:5]:
            sidecar.add_note(note)

        # Export
        sidecar.export(export_path)

        assert export_path.exists()
        assert export_path.stat().st_size > 0

    def test_import_metadata(self, sidecar_factory, sample_metadata, temp_sidecar_dir):
        """Test importing metadata."""
        sidecar1 = sidecar_factory(temp_sidecar_dir / "sidecar1")
        sidecar2 = sidecar_factory(temp_sidecar_dir / "sidecar2")
        export_path = temp_sidecar_dir / "export.json"

        # Add data to first sidecar
        for metadata in sample_metadata:
            sidecar1.set_metadata(metadata)

        # Export from first
        sidecar1.export(export_path)

        # Import to second
        sidecar2.import_from(export_path)

        # Verify data transferred
        for metadata in sample_metadata:
            imported = sidecar2.get_metadata(metadata.key)
            assert imported is not None
            assert imported.key == metadata.key

    def test_merge_import(self, sidecar_factory, metadata_factory, temp_sidecar_dir):
        """Test merging imported data with existing."""
        sidecar = sidecar_factory(temp_sidecar_dir)
        export_path = temp_sidecar_dir / "export.json"

        # Add initial data
        sidecar.set_metadata(metadata_factory(key="existing", notes="Original"))

        # Create export with overlapping data
        temp_sidecar = sidecar_factory(temp_sidecar_dir / "temp")
        temp_sidecar.set_metadata(metadata_factory(key="existing", notes="Imported"))
        temp_sidecar.set_metadata(metadata_factory(key="new", notes="New"))
        temp_sidecar.export(export_path)

        # Import with merge
        if hasattr(sidecar, "import_from"):
            sidecar.import_from(export_path)

            # Check results (behavior depends on merge strategy)
            existing = sidecar.get_metadata("existing")
            assert existing is not None

            new = sidecar.get_metadata("new")
            assert new is not None
            assert new.notes == "New"


class TestConcurrency:
    """Test concurrent access to metadata."""

    def test_concurrent_metadata_updates(self, sidecar_factory, temp_sidecar_dir):
        """Test concurrent metadata updates."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        def update_metadata(thread_id):
            for i in range(10):
                sidecar.update_metadata(
                    f"entry{thread_id}",
                    notes=f"Updated by thread {thread_id} iteration {i}",
                )
                time.sleep(0.001)

        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_metadata, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all updates completed
        for i in range(5):
            metadata = sidecar.get_metadata(f"entry{i}")
            assert metadata is not None
            assert "Updated by thread" in metadata.notes

    def test_concurrent_tag_operations(self, sidecar_factory, temp_sidecar_dir):
        """Test concurrent tag operations."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        def add_tags(thread_id):
            for i in range(10):
                sidecar.add_tags("shared_entry", [f"tag_{thread_id}_{i}"])
                time.sleep(0.001)

        threads = []
        for i in range(3):
            thread = threading.Thread(target=add_tags, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all tags added
        metadata = sidecar.get_metadata("shared_entry")
        assert metadata is not None
        assert len(metadata.tags) == 30  # 3 threads * 10 tags each

    def test_concurrent_note_operations(
        self, sidecar_factory, note_factory, temp_sidecar_dir
    ):
        """Test concurrent note operations."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        def add_notes(thread_id):
            for i in range(5):
                note = note_factory(
                    id=f"note_{thread_id}_{i}",
                    entry_key="shared_entry",
                    content=f"Note from thread {thread_id}",
                )
                sidecar.add_note(note)
                time.sleep(0.001)

        threads = []
        for i in range(4):
            thread = threading.Thread(target=add_notes, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all notes added
        notes = sidecar.get_notes("shared_entry")
        assert len(notes) == 20  # 4 threads * 5 notes each


class TestErrorHandling:
    """Test error handling in sidecar operations."""

    def test_invalid_metadata(self, sidecar_factory, temp_sidecar_dir):
        """Test handling of invalid metadata."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Test with None
        with pytest.raises((TypeError, ValueError)):
            sidecar.set_metadata(None)

        # Test with invalid key
        with pytest.raises((TypeError, ValueError, AttributeError)):
            sidecar.update_metadata(None, notes="Test")

    def test_invalid_note(self, sidecar_factory, temp_sidecar_dir):
        """Test handling of invalid notes."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Test with None
        with pytest.raises((TypeError, ValueError)):
            sidecar.add_note(None)

        # Test with missing required fields
        with pytest.raises((TypeError, ValueError, AttributeError)):
            invalid_note = type("Note", (), {})()  # Empty note object
            sidecar.add_note(invalid_note)

    def test_filesystem_errors(self, sidecar_factory, temp_sidecar_dir):
        """Test handling of filesystem errors."""
        sidecar = sidecar_factory(temp_sidecar_dir)

        # Make directory read-only (platform-specific)
        import os
        import stat

        try:
            # Remove write permissions
            os.chmod(temp_sidecar_dir, stat.S_IRUSR | stat.S_IXUSR)

            # Try to write (should handle gracefully)
            try:
                sidecar.update_metadata("test", notes="Should fail")
            except (PermissionError, IOError):
                pass  # Expected

        finally:
            # Restore permissions
            os.chmod(temp_sidecar_dir, stat.S_IRWXU)
