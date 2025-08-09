"""Entry metadata management interface.

Provides structured management for bibliography entry metadata including tags,
notes, ratings, and reading status tracking.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4


@dataclass
class Note:
    """A note attached to an entry."""

    id: UUID = field(default_factory=uuid4)
    entry_key: str = ""
    content: str = ""
    note_type: str = "general"  # general, summary, quote, idea
    page: int | None = None
    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "entry_key": self.entry_key,
            "content": self.content,
            "note_type": self.note_type,
            "page": self.page,
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Note":
        """Create from dictionary."""
        data["id"] = UUID(data["id"])
        data["created"] = datetime.fromisoformat(data["created"])
        data["modified"] = datetime.fromisoformat(data["modified"])
        return cls(**data)


@dataclass
class EntryMetadata:
    """Metadata for a bibliography entry."""

    entry_key: str
    tags: set[str] = field(default_factory=set)
    rating: int | None = None  # 1-5
    read_status: str = "unread"  # unread, reading, read
    read_date: datetime | None = None
    importance: str = "normal"  # low, normal, high
    notes_count: int = 0

    def add_tags(self, *tags: str) -> None:
        """Add tags."""
        self.tags.update(tags)

    def remove_tags(self, *tags: str) -> None:
        """Remove tags."""
        self.tags.difference_update(tags)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_key": self.entry_key,
            "tags": list(self.tags),
            "rating": self.rating,
            "read_status": self.read_status,
            "read_date": self.read_date.isoformat() if self.read_date else None,
            "importance": self.importance,
            "notes_count": self.notes_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntryMetadata":
        """Create from dictionary."""
        data["tags"] = set(data.get("tags", []))
        if data.get("read_date"):
            data["read_date"] = datetime.fromisoformat(data["read_date"])
        return cls(**data)


class MetadataStore:
    """Store for entry metadata and notes."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.metadata_dir = self.data_dir / "metadata"
        self.notes_dir = self.data_dir / "notes"

        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir.mkdir(parents=True, exist_ok=True)

        self._tag_index: dict[str, set[str]] = {}
        self._metadata_cache: dict[str, EntryMetadata] = {}

        self._build_indices()

    def _build_indices(self) -> None:
        """Build in-memory indices."""
        for path in self.metadata_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                metadata = EntryMetadata.from_dict(data)
                self._metadata_cache[metadata.entry_key] = metadata

                for tag in metadata.tags:
                    if tag not in self._tag_index:
                        self._tag_index[tag] = set()
                    self._tag_index[tag].add(metadata.entry_key)
            except Exception:
                pass

    def get_metadata(self, entry_key: str) -> EntryMetadata:
        """Get metadata for entry, creating if needed."""
        if entry_key in self._metadata_cache:
            return self._metadata_cache[entry_key]

        path = self.metadata_dir / f"{entry_key}.json"
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                metadata = EntryMetadata.from_dict(data)
                self._metadata_cache[entry_key] = metadata
                return metadata
            except Exception:
                pass

        metadata = EntryMetadata(entry_key=entry_key)
        self._metadata_cache[entry_key] = metadata
        return metadata

    def save_metadata(self, metadata: EntryMetadata) -> None:
        """Save metadata to disk."""
        path = self.metadata_dir / f"{metadata.entry_key}.json"

        self._metadata_cache[metadata.entry_key] = metadata

        old_tags = set()
        if path.exists():
            try:
                with open(path) as f:
                    old_data = json.load(f)
                old_tags = set(old_data.get("tags", []))
            except Exception:
                pass

        for tag in old_tags - metadata.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(metadata.entry_key)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]

        for tag in metadata.tags - old_tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(metadata.entry_key)

        with open(path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

    def delete_metadata(self, entry_key: str) -> None:
        """Delete metadata for entry."""
        metadata = self._metadata_cache.pop(entry_key, None)

        if metadata:
            for tag in metadata.tags:
                if tag in self._tag_index:
                    self._tag_index[tag].discard(entry_key)
                    if not self._tag_index[tag]:
                        del self._tag_index[tag]

        path = self.metadata_dir / f"{entry_key}.json"
        path.unlink(missing_ok=True)

        note_dir = self.notes_dir / entry_key
        if note_dir.exists():
            import shutil

            shutil.rmtree(note_dir)

    def add_note(self, note: Note) -> None:
        """Add a note."""
        note_dir = self.notes_dir / note.entry_key
        note_dir.mkdir(parents=True, exist_ok=True)

        path = note_dir / f"{note.id}.json"
        with open(path, "w") as f:
            json.dump(note.to_dict(), f, indent=2)

        metadata = self.get_metadata(note.entry_key)
        metadata.notes_count += 1
        self.save_metadata(metadata)

    def get_notes(self, entry_key: str) -> list[Note]:
        """Get all notes for entry."""
        note_dir = self.notes_dir / entry_key
        if not note_dir.exists():
            return []

        notes = []
        for path in note_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                notes.append(Note.from_dict(data))
            except Exception:
                pass

        notes.sort(key=lambda n: n.created)
        return notes

    def delete_note(self, entry_key: str, note_id: UUID) -> bool:
        """Delete a note."""
        path = self.notes_dir / entry_key / f"{note_id}.json"
        if path.exists():
            path.unlink()

            metadata = self.get_metadata(entry_key)
            metadata.notes_count = max(0, metadata.notes_count - 1)
            self.save_metadata(metadata)

            return True
        return False

    def find_by_tag(self, tag: str) -> list[str]:
        """Find entries by tag."""
        return list(self._tag_index.get(tag, set()))

    def find_by_tags(self, tags: list[str], match_all: bool = False) -> list[str]:
        """Find entries by multiple tags."""
        if not tags:
            return []

        tag_sets = [self._tag_index.get(tag, set()) for tag in tags]

        if match_all:
            result = tag_sets[0]
            for tag_set in tag_sets[1:]:
                result = result.intersection(tag_set)
            return list(result)
        else:
            result = set()
            for tag_set in tag_sets:
                result.update(tag_set)
            return list(result)

    def get_all_tags(self) -> dict[str, int]:
        """Get all tags with counts."""
        return {tag: len(entries) for tag, entries in self._tag_index.items()}

    def rename_tag(self, old_tag: str, new_tag: str) -> int:
        """Rename a tag across all entries."""
        if old_tag not in self._tag_index:
            return 0

        entries = list(self._tag_index[old_tag])
        count = 0

        for entry_key in entries:
            metadata = self.get_metadata(entry_key)
            if old_tag in metadata.tags:
                metadata.remove_tags(old_tag)
                metadata.add_tags(new_tag)
                self.save_metadata(metadata)
                count += 1

        return count

    def merge_tags(self, source_tags: list[str], target_tag: str) -> int:
        """Merge multiple tags into one."""
        all_entries = set()

        for tag in source_tags:
            all_entries.update(self._tag_index.get(tag, set()))

        count = 0
        for entry_key in all_entries:
            metadata = self.get_metadata(entry_key)

            for tag in source_tags:
                metadata.remove_tags(tag)

            metadata.add_tags(target_tag)
            self.save_metadata(metadata)
            count += 1

        return count
