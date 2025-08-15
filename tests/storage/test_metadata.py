"""Tests for metadata management system.

This module tests the metadata system that manages tags, notes,
ratings, and other entry metadata in a clean, separate layer.
"""

import uuid
from datetime import datetime, timedelta


class TestNote:
    """Test the Note data class."""

    def test_create_note_with_defaults(self):
        """Note can be created with minimal fields."""
        from bibmgr.storage.metadata import Note

        note = Note(entry_key="test123", content="Test content")

        assert note.entry_key == "test123"
        assert note.content == "Test content"
        assert note.note_type == "general"
        assert note.page is None
        assert isinstance(note.id, uuid.UUID)
        assert isinstance(note.created, datetime)
        assert isinstance(note.modified, datetime)
        assert note.tags == []

    def test_create_note_with_all_fields(self):
        """Note can be created with all fields specified."""
        from bibmgr.storage.metadata import Note

        note_id = uuid.uuid4()
        created = datetime.now() - timedelta(days=1)
        modified = datetime.now()

        note = Note(
            id=note_id,
            entry_key="entry123",
            content="Important quote from the paper",
            note_type="quote",
            page=42,
            created=created,
            modified=modified,
            tags=["important", "methodology"],
        )

        assert note.id == note_id
        assert note.note_type == "quote"
        assert note.page == 42
        assert note.tags == ["important", "methodology"]

    def test_note_serialization(self):
        """Note can be serialized to/from dict."""
        from bibmgr.storage.metadata import Note

        original = Note(
            entry_key="test",
            content="Test note",
            note_type="summary",
            page=10,
            tags=["test", "summary"],
        )

        data = original.to_dict()
        assert data["entry_key"] == "test"
        assert data["content"] == "Test note"
        assert data["note_type"] == "summary"
        assert data["page"] == 10
        assert data["tags"] == ["test", "summary"]
        assert isinstance(data["id"], str)
        assert isinstance(data["created"], str)  # ISO format
        assert isinstance(data["modified"], str)

        restored = Note.from_dict(data)
        assert restored.id == original.id
        assert restored.entry_key == original.entry_key
        assert restored.content == original.content
        assert restored.note_type == original.note_type
        assert restored.page == original.page
        assert restored.tags == original.tags

    def test_note_types(self):
        """Note types are validated."""
        from bibmgr.storage.metadata import Note

        valid_types = ["general", "summary", "quote", "idea"]

        for note_type in valid_types:
            note = Note(entry_key="test", content="Content", note_type=note_type)
            assert note.note_type == note_type


class TestEntryMetadata:
    """Test the EntryMetadata data class."""

    def test_create_metadata_minimal(self):
        """Metadata can be created with just entry key."""
        from bibmgr.storage.metadata import EntryMetadata

        metadata = EntryMetadata(entry_key="test123")

        assert metadata.entry_key == "test123"
        assert metadata.tags == set()
        assert metadata.rating is None
        assert metadata.read_status == "unread"
        assert metadata.read_date is None
        assert metadata.importance == "normal"
        assert metadata.notes_count == 0

    def test_create_metadata_full(self):
        """Metadata can be created with all fields."""
        from bibmgr.storage.metadata import EntryMetadata

        read_date = datetime.now() - timedelta(days=7)

        metadata = EntryMetadata(
            entry_key="paper123",
            tags={"ml", "deep-learning", "computer-vision"},
            rating=5,
            read_status="read",
            read_date=read_date,
            importance="high",
            notes_count=3,
        )

        assert metadata.tags == {"ml", "deep-learning", "computer-vision"}
        assert metadata.rating == 5
        assert metadata.read_status == "read"
        assert metadata.read_date == read_date
        assert metadata.importance == "high"
        assert metadata.notes_count == 3

    def test_tag_operations(self):
        """Tag add/remove operations work correctly."""
        from bibmgr.storage.metadata import EntryMetadata

        metadata = EntryMetadata(entry_key="test")

        metadata.add_tags("python", "testing")
        assert metadata.tags == {"python", "testing"}

        metadata.add_tags("pytest", "python", "unit-test")
        assert metadata.tags == {"python", "testing", "pytest", "unit-test"}

        metadata.remove_tags("testing", "unit-test")
        assert metadata.tags == {"python", "pytest"}

        metadata.remove_tags("nonexistent")
        assert metadata.tags == {"python", "pytest"}

    def test_metadata_serialization(self):
        """Metadata can be serialized to/from dict."""
        from bibmgr.storage.metadata import EntryMetadata

        original = EntryMetadata(
            entry_key="test",
            tags={"tag1", "tag2"},
            rating=4,
            read_status="reading",
            read_date=datetime.now(),
            importance="high",
            notes_count=2,
        )

        data = original.to_dict()
        assert data["entry_key"] == "test"
        assert set(data["tags"]) == {"tag1", "tag2"}  # List in dict
        assert data["rating"] == 4
        assert data["read_status"] == "reading"
        assert isinstance(data["read_date"], str)

        restored = EntryMetadata.from_dict(data)
        assert restored.entry_key == original.entry_key
        assert restored.tags == original.tags
        assert restored.rating == original.rating
        assert restored.read_status == original.read_status
        assert restored.importance == original.importance

    def test_read_status_values(self):
        """Read status has specific allowed values."""
        from bibmgr.storage.metadata import EntryMetadata

        valid_statuses = ["unread", "reading", "read"]

        for status in valid_statuses:
            metadata = EntryMetadata(entry_key="test", read_status=status)
            assert metadata.read_status == status

    def test_importance_values(self):
        """Importance has specific allowed values."""
        from bibmgr.storage.metadata import EntryMetadata

        valid_importance = ["low", "normal", "high"]

        for importance in valid_importance:
            metadata = EntryMetadata(entry_key="test", importance=importance)
            assert metadata.importance == importance

    def test_rating_range(self):
        """Rating must be between 1 and 5."""
        from bibmgr.storage.metadata import EntryMetadata

        for rating in range(1, 6):
            metadata = EntryMetadata(entry_key="test", rating=rating)
            assert metadata.rating == rating


class TestMetadataStore:
    """Test the metadata storage system."""

    def test_store_initialization(self, temp_dir):
        """MetadataStore creates directory structure."""
        from bibmgr.storage.metadata import MetadataStore

        MetadataStore(temp_dir)

        assert (temp_dir / "metadata").is_dir()
        assert (temp_dir / "notes").is_dir()

    def test_get_metadata_creates_default(self, temp_dir):
        """get_metadata creates default metadata if none exists."""
        from bibmgr.storage.metadata import MetadataStore

        store = MetadataStore(temp_dir)

        metadata = store.get_metadata("new_entry")
        assert metadata.entry_key == "new_entry"
        assert metadata.tags == set()
        assert metadata.read_status == "unread"

    def test_save_and_load_metadata(self, temp_dir):
        """Metadata can be saved and loaded."""
        from bibmgr.storage.metadata import EntryMetadata, MetadataStore

        store = MetadataStore(temp_dir)

        metadata = EntryMetadata(
            entry_key="test123",
            tags={"python", "testing"},
            rating=5,
            read_status="read",
        )
        store.save_metadata(metadata)

        store._metadata_cache.clear()

        loaded = store.get_metadata("test123")
        assert loaded.entry_key == "test123"
        assert loaded.tags == {"python", "testing"}
        assert loaded.rating == 5
        assert loaded.read_status == "read"

    def test_delete_metadata(self, temp_dir):
        """Metadata can be deleted."""
        from bibmgr.storage.metadata import EntryMetadata, MetadataStore

        store = MetadataStore(temp_dir)

        metadata = EntryMetadata(entry_key="to_delete", tags={"temp"})
        store.save_metadata(metadata)

        from bibmgr.storage.metadata import Note

        note = Note(entry_key="to_delete", content="Test note")
        store.add_note(note)

        store.delete_metadata("to_delete")

        loaded = store.get_metadata("to_delete")
        assert loaded.tags == set()

        notes = store.get_notes("to_delete")
        assert notes == []

    def test_add_and_get_notes(self, temp_dir):
        """Notes can be added and retrieved."""
        from bibmgr.storage.metadata import MetadataStore, Note

        store = MetadataStore(temp_dir)

        note1 = Note(entry_key="entry1", content="First note", note_type="general")
        note2 = Note(entry_key="entry1", content="Second note", note_type="summary")
        note3 = Note(entry_key="entry2", content="Different entry", note_type="quote")

        store.add_note(note1)
        store.add_note(note2)
        store.add_note(note3)

        entry1_notes = store.get_notes("entry1")
        assert len(entry1_notes) == 2
        assert {n.content for n in entry1_notes} == {"First note", "Second note"}

        entry2_notes = store.get_notes("entry2")
        assert len(entry2_notes) == 1
        assert entry2_notes[0].content == "Different entry"

        assert entry1_notes[0].created <= entry1_notes[1].created

    def test_delete_note(self, temp_dir):
        """Individual notes can be deleted."""
        from bibmgr.storage.metadata import MetadataStore, Note

        store = MetadataStore(temp_dir)

        note1 = Note(entry_key="test", content="Keep this")
        note2 = Note(entry_key="test", content="Delete this")

        store.add_note(note1)
        store.add_note(note2)

        assert store.delete_note("test", note2.id) is True

        notes = store.get_notes("test")
        assert len(notes) == 1
        assert notes[0].content == "Keep this"

        assert store.delete_note("test", uuid.uuid4()) is False

    def test_notes_update_metadata_count(self, temp_dir):
        """Adding/deleting notes updates metadata count."""
        from bibmgr.storage.metadata import MetadataStore, Note

        store = MetadataStore(temp_dir)

        metadata = store.get_metadata("test")
        assert metadata.notes_count == 0

        note = Note(entry_key="test", content="Test")
        store.add_note(note)

        metadata = store.get_metadata("test")
        assert metadata.notes_count == 1

        note2 = Note(entry_key="test", content="Test 2")
        store.add_note(note2)

        metadata = store.get_metadata("test")
        assert metadata.notes_count == 2

        store.delete_note("test", note.id)

        metadata = store.get_metadata("test")
        assert metadata.notes_count == 1


class TestTagIndex:
    """Test tag indexing functionality."""

    def test_tag_index_operations(self, temp_dir):
        """Tag index maintains tag-to-entry mappings."""
        from bibmgr.storage.metadata import EntryMetadata, MetadataStore

        store = MetadataStore(temp_dir)

        store.save_metadata(
            EntryMetadata(entry_key="entry1", tags={"python", "testing", "pytest"})
        )

        store.save_metadata(
            EntryMetadata(entry_key="entry2", tags={"python", "django"})
        )

        store.save_metadata(EntryMetadata(entry_key="entry3", tags={"rust", "testing"}))

        python_entries = store.find_by_tag("python")
        assert set(python_entries) == {"entry1", "entry2"}

        testing_entries = store.find_by_tag("testing")
        assert set(testing_entries) == {"entry1", "entry3"}

        assert store.find_by_tag("nonexistent") == []

    def test_find_by_multiple_tags(self, temp_dir):
        """find_by_tags supports AND/OR matching."""
        from bibmgr.storage.metadata import EntryMetadata, MetadataStore

        store = MetadataStore(temp_dir)

        store.save_metadata(
            EntryMetadata(
                entry_key="ml_paper",
                tags={"machine-learning", "neural-networks", "python"},
            )
        )

        store.save_metadata(
            EntryMetadata(
                entry_key="ml_theory",
                tags={"machine-learning", "theory", "mathematics"},
            )
        )

        store.save_metadata(
            EntryMetadata(entry_key="web_dev", tags={"python", "django", "web"})
        )

        results = store.find_by_tags(["python", "theory"], match_all=False)
        assert set(results) == {"ml_paper", "ml_theory", "web_dev"}

        results = store.find_by_tags(["machine-learning", "python"], match_all=True)
        assert results == ["ml_paper"]

        results = store.find_by_tags(["nonexistent", "tags"], match_all=True)
        assert results == []

    def test_get_all_tags(self, temp_dir):
        """get_all_tags returns tag counts."""
        from bibmgr.storage.metadata import EntryMetadata, MetadataStore

        store = MetadataStore(temp_dir)

        for i in range(5):
            tags = {"common"}
            if i < 3:
                tags.add("popular")
            if i == 0:
                tags.add("unique")

            store.save_metadata(EntryMetadata(entry_key=f"entry{i}", tags=tags))

        all_tags = store.get_all_tags()
        assert all_tags == {
            "common": 5,
            "popular": 3,
            "unique": 1,
        }

    def test_rename_tag(self, temp_dir):
        """Tags can be renamed across all entries."""
        from bibmgr.storage.metadata import EntryMetadata, MetadataStore

        store = MetadataStore(temp_dir)

        store.save_metadata(
            EntryMetadata(entry_key="entry1", tags={"old-name", "other"})
        )

        store.save_metadata(
            EntryMetadata(entry_key="entry2", tags={"old-name", "different"})
        )

        store.save_metadata(EntryMetadata(entry_key="entry3", tags={"unrelated"}))

        count = store.rename_tag("old-name", "new-name")
        assert count == 2

        assert store.find_by_tag("old-name") == []
        assert set(store.find_by_tag("new-name")) == {"entry1", "entry2"}

        assert store.get_metadata("entry1").tags == {"new-name", "other"}
        assert store.get_metadata("entry3").tags == {"unrelated"}

    def test_tag_index_persistence(self, temp_dir):
        """Tag index is persisted and reloaded correctly."""
        from bibmgr.storage.metadata import EntryMetadata, MetadataStore

        store1 = MetadataStore(temp_dir)

        store1.save_metadata(EntryMetadata(entry_key="entry1", tags={"tag1", "tag2"}))

        store1.save_metadata(EntryMetadata(entry_key="entry2", tags={"tag2", "tag3"}))

        store2 = MetadataStore(temp_dir)

        assert set(store2.find_by_tag("tag1")) == {"entry1"}
        assert set(store2.find_by_tag("tag2")) == {"entry1", "entry2"}
        assert set(store2.find_by_tag("tag3")) == {"entry2"}


class TestMetadataStoreErrors:
    """Test error handling in metadata store."""

    def test_corrupted_metadata_file(self, temp_dir):
        """Store handles corrupted metadata files gracefully."""
        from bibmgr.storage.metadata import EntryMetadata, MetadataStore

        store = MetadataStore(temp_dir)

        store.save_metadata(EntryMetadata(entry_key="valid", tags={"ok"}))

        metadata_file = temp_dir / "metadata" / "corrupt.json"
        metadata_file.write_text("not valid json{")

        metadata = store.get_metadata("corrupt")
        assert metadata.entry_key == "corrupt"
        assert metadata.tags == set()

        valid = store.get_metadata("valid")
        assert valid.tags == {"ok"}

    def test_missing_note_directory(self, temp_dir):
        """Store handles missing note directories gracefully."""
        from bibmgr.storage.metadata import MetadataStore

        store = MetadataStore(temp_dir)

        notes = store.get_notes("no_notes")
        assert notes == []

    def test_concurrent_metadata_access(self, temp_dir):
        """Metadata store handles concurrent access safely."""
        import threading

        from bibmgr.storage.metadata import MetadataStore

        store = MetadataStore(temp_dir)
        errors = []

        def update_tags(entry_key, tags):
            try:
                for _ in range(10):
                    metadata = store.get_metadata(entry_key)
                    for tag in tags:
                        metadata.add_tags(tag)
                    store.save_metadata(metadata)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(3):
            t = threading.Thread(target=update_tags, args=("shared_entry", [f"tag{i}"]))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0

        final = store.get_metadata("shared_entry")
        assert "tag0" in final.tags
        assert "tag1" in final.tags
        assert "tag2" in final.tags
