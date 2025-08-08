"""Metadata sidecar for notes, tags, and extended metadata.

Features:
- Efficient tag indexing and search
- Note management with full-text search
- Reading progress tracking
- Custom metadata fields
- Data migration support
- Bulk operations
- Thread-safe operations
"""

from __future__ import annotations

import json
import threading
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


class SidecarError(Exception):
    """Base exception for sidecar errors."""

    pass


class ValidationError(SidecarError):
    """Validation errors."""

    pass


@dataclass
class EntryMetadata:
    """Metadata for a bibliography entry."""

    key: str
    notes: str | None = None
    tags: list[str] | None = None
    collections: list[str] | None = None
    reading_status: str | None = None  # unread, reading, read, skimmed
    rating: int | None = None  # 1-5 stars
    importance: str | None = None  # low, medium, high, critical

    # Reading progress
    current_page: int | None = None
    total_pages: int | None = None
    reading_started: datetime | None = None
    reading_completed: datetime | None = None

    # Custom fields
    custom_fields: dict[str, Any] | None = None

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self):
        """Validate and initialize metadata."""
        # Validate rating
        if self.rating is not None:
            if not 1 <= self.rating <= 5:
                raise ValidationError(
                    f"Rating must be between 1 and 5, got {self.rating}"
                )

        # Validate importance
        if self.importance is not None:
            valid_importance = {"low", "medium", "high", "critical"}
            if self.importance not in valid_importance:
                raise ValidationError(
                    f"Importance must be one of {valid_importance}, got {self.importance}"
                )

        # Validate reading status
        if self.reading_status is not None:
            valid_status = {"unread", "reading", "read", "skimmed"}
            if self.reading_status not in valid_status:
                raise ValidationError(
                    f"Reading status must be one of {valid_status}, got {self.reading_status}"
                )

        # Initialize timestamps
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

        # Normalize tags
        if self.tags:
            self.tags = sorted(list(set(self.tags)))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = {}
        for key, value in asdict(self).items():
            if value is not None:
                if isinstance(value, datetime):
                    data[key] = value.isoformat()
                else:
                    data[key] = value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntryMetadata:
        """Create from dictionary."""
        # Parse datetime fields
        for field_name in [
            "reading_started",
            "reading_completed",
            "created_at",
            "updated_at",
        ]:
            if field_name in data and data[field_name]:
                if isinstance(data[field_name], str):
                    data[field_name] = datetime.fromisoformat(data[field_name])

        return cls(**data)


@dataclass
class Note:
    """A note attached to an entry."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entry_key: str = ""
    content: str = ""
    type: str = "general"  # general, summary, critique, idea, quote

    # Quote-specific fields
    page_number: int | None = None
    chapter: str | None = None

    # Tags for notes
    tags: list[str] | None = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate note fields."""
        if not self.entry_key:
            raise ValidationError("Note must have an entry_key")

        valid_types = {"general", "summary", "critique", "idea", "quote"}
        if self.type not in valid_types:
            raise ValidationError(
                f"Note type must be one of {valid_types}, got {self.type}"
            )

        # Normalize tags
        if self.tags:
            self.tags = sorted(list(set(self.tags)))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Note:
        """Create from dictionary."""
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


class TagIndex:
    """Efficient tag indexing and search."""

    def __init__(self):
        self.tag_to_entries: dict[str, set[str]] = defaultdict(set)
        self.entry_to_tags: dict[str, set[str]] = defaultdict(set)
        self.tag_counts: dict[str, int] = defaultdict(int)
        self.lock = threading.RLock()

    def add_tags(self, entry_key: str, tags: list[str]) -> None:
        """Add tags for an entry."""
        with self.lock:
            for tag in tags:
                self.tag_to_entries[tag].add(entry_key)
                self.entry_to_tags[entry_key].add(tag)
                self.tag_counts[tag] += 1

    def remove_tags(self, entry_key: str, tags: list[str]) -> None:
        """Remove tags from an entry."""
        with self.lock:
            for tag in tags:
                if entry_key in self.tag_to_entries[tag]:
                    self.tag_to_entries[tag].remove(entry_key)
                    self.tag_counts[tag] -= 1
                    if self.tag_counts[tag] == 0:
                        del self.tag_counts[tag]
                        del self.tag_to_entries[tag]

                self.entry_to_tags[entry_key].discard(tag)

    def remove_entry(self, entry_key: str) -> None:
        """Remove all tags for an entry."""
        with self.lock:
            tags = list(self.entry_to_tags.get(entry_key, []))
            self.remove_tags(entry_key, tags)
            if entry_key in self.entry_to_tags:
                del self.entry_to_tags[entry_key]

    def get_entries_by_tag(self, tag: str) -> list[str]:
        """Get entries with a specific tag."""
        with self.lock:
            return list(self.tag_to_entries.get(tag, []))

    def get_tags_for_entry(self, entry_key: str) -> list[str]:
        """Get tags for an entry."""
        with self.lock:
            return sorted(list(self.entry_to_tags.get(entry_key, [])))

    def get_all_tags(self) -> dict[str, int]:
        """Get all tags with counts."""
        with self.lock:
            return dict(self.tag_counts)

    def search_tags(self, pattern: str) -> list[str]:
        """Search tags by pattern."""
        with self.lock:
            pattern_lower = pattern.lower().replace("*", "")
            results = []

            for tag in self.tag_counts:
                if pattern_lower in tag.lower():
                    results.append(tag)

            return sorted(results)

    def rebuild(self, entries_metadata: dict[str, EntryMetadata]) -> None:
        """Rebuild index from metadata."""
        with self.lock:
            self.tag_to_entries.clear()
            self.entry_to_tags.clear()
            self.tag_counts.clear()

            for entry_key, metadata in entries_metadata.items():
                if metadata.tags:
                    self.add_tags(entry_key, metadata.tags)


class MetadataSidecar:
    """Manages metadata storage alongside bibliography entries.

    Structure:
    base_dir/
        metadata/
            entries/
                {key}.json      # Entry metadata
            notes/
                {entry_key}/
                    {note_id}.json  # Individual notes
            indices/
                tags.json       # Tag index
                collections.json # Collection index
            version.json        # Schema version
    """

    SCHEMA_VERSION = "2.0.0"

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.metadata_dir = self.base_dir / "metadata"
        self.entries_dir = self.metadata_dir / "entries"
        self.notes_dir = self.metadata_dir / "notes"
        self.indices_dir = self.metadata_dir / "indices"

        # Create directory structure
        self.entries_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.indices_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.tag_index = TagIndex()
        self._metadata_cache: dict[str, EntryMetadata] = {}
        self._lock = threading.RLock()

        # Check version and migrate if needed
        self._check_version()

        # Load indices
        self._load_indices()

    def _check_version(self) -> None:
        """Check and update schema version."""
        version_file = self.metadata_dir / "version.json"

        if version_file.exists():
            try:
                with open(version_file) as f:
                    data = json.load(f)
                current_version = data.get("version", "1.0.0")

                if current_version != self.SCHEMA_VERSION:
                    self.migrate(current_version, self.SCHEMA_VERSION)

            except (OSError, json.JSONDecodeError):
                pass

        # Write current version
        try:
            with open(version_file, "w") as f:
                json.dump({"version": self.SCHEMA_VERSION}, f)
        except OSError:
            pass

    def migrate(self, from_version: str, to_version: str) -> None:
        """Migrate metadata schema between versions."""
        if from_version == "1.0.0" and to_version == "2.0.0":
            # Migrate from v1 to v2
            # - Move notes to separate files
            # - Add indices
            self._migrate_v1_to_v2()

    def _migrate_v1_to_v2(self) -> None:
        """Migrate from version 1.0.0 to 2.0.0."""
        # This is a placeholder for actual migration logic
        pass

    def _load_indices(self) -> None:
        """Load indices from disk."""
        # Load tag index
        tag_index_file = self.indices_dir / "tags.json"
        if tag_index_file.exists():
            try:
                with open(tag_index_file) as f:
                    data = json.load(f)

                # Rebuild index from saved data
                for tag, entries in data.get("tag_to_entries", {}).items():
                    for entry in entries:
                        self.tag_index.tag_to_entries[tag].add(entry)
                        self.tag_index.entry_to_tags[entry].add(tag)
                        self.tag_index.tag_counts[tag] += 1

            except (OSError, json.JSONDecodeError):
                pass

    def _save_indices(self) -> None:
        """Save indices to disk."""
        # Save tag index
        tag_index_file = self.indices_dir / "tags.json"
        try:
            with self.tag_index.lock:
                data = {
                    "tag_to_entries": {
                        tag: list(entries)
                        for tag, entries in self.tag_index.tag_to_entries.items()
                    }
                }

            temp_file = tag_index_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2)
            temp_file.replace(tag_index_file)

        except OSError:
            pass

    def _metadata_path(self, key: str) -> Path:
        """Get path for entry metadata."""
        safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        return self.entries_dir / f"{safe_key}.json"

    def _note_dir(self, entry_key: str) -> Path:
        """Get directory for entry notes."""
        safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in entry_key)
        return self.notes_dir / safe_key

    def _note_path(self, entry_key: str, note_id: str) -> Path:
        """Get path for specific note."""
        return self._note_dir(entry_key) / f"{note_id}.json"

    # Metadata operations

    def get_metadata(self, key: str) -> EntryMetadata | None:
        """Get metadata for an entry."""
        with self._lock:
            # Check cache
            if key in self._metadata_cache:
                return self._metadata_cache[key]

            path = self._metadata_path(key)
            if not path.exists():
                return None

            try:
                with open(path) as f:
                    data = json.load(f)
                metadata = EntryMetadata.from_dict(data)

                # Update cache
                self._metadata_cache[key] = metadata

                return metadata

            except (OSError, json.JSONDecodeError, ValidationError):
                return None

    def set_metadata(self, metadata: EntryMetadata) -> None:
        """Set metadata for an entry."""
        if metadata is None:
            raise TypeError("Metadata cannot be None")

        with self._lock:
            # Update timestamps
            metadata.updated_at = datetime.now()
            if metadata.created_at is None:
                metadata.created_at = metadata.updated_at

            # Update tag index
            old_metadata = self.get_metadata(metadata.key)
            if old_metadata and old_metadata.tags:
                self.tag_index.remove_tags(metadata.key, old_metadata.tags)
            if metadata.tags:
                self.tag_index.add_tags(metadata.key, metadata.tags)

            # Save to disk
            path = self._metadata_path(metadata.key)
            try:
                temp_path = path.with_suffix(".tmp")
                with open(temp_path, "w") as f:
                    json.dump(metadata.to_dict(), f, indent=2)
                temp_path.replace(path)

                # Update cache
                self._metadata_cache[metadata.key] = metadata

                # Save indices
                self._save_indices()

            except OSError as e:
                raise SidecarError(f"Failed to save metadata: {e}") from e

    def update_metadata(self, key: str, **fields) -> None:
        """Update specific metadata fields."""
        if not key:
            raise ValueError("Key cannot be empty")

        with self._lock:
            metadata = self.get_metadata(key)
            if metadata is None:
                # Create new with fields
                metadata = EntryMetadata(key=key, **fields)
            else:
                # Create updated metadata to trigger validation
                current_dict = metadata.to_dict()
                current_dict.update(fields)
                metadata = EntryMetadata.from_dict(current_dict)

            self.set_metadata(metadata)

    def delete_metadata(self, key: str) -> bool:
        """Delete metadata for an entry."""
        with self._lock:
            path = self._metadata_path(key)

            # Remove from tag index
            self.tag_index.remove_entry(key)

            # Delete notes
            note_dir = self._note_dir(key)
            if note_dir.exists():
                try:
                    import shutil

                    shutil.rmtree(note_dir)
                except OSError:
                    pass

            # Delete metadata file
            if path.exists():
                try:
                    path.unlink()

                    # Remove from cache
                    self._metadata_cache.pop(key, None)

                    # Save indices
                    self._save_indices()

                    return True

                except OSError:
                    return False

            return False

    def bulk_get_metadata(self, keys: list[str]) -> dict[str, EntryMetadata | None]:
        """Get metadata for multiple entries efficiently."""
        results = {}
        for key in keys:
            results[key] = self.get_metadata(key)
        return results

    def bulk_update_metadata(self, updates: dict[str, dict]) -> dict[str, bool]:
        """Update metadata for multiple entries efficiently."""
        results = {}

        for key, fields in updates.items():
            try:
                self.update_metadata(key, **fields)
                results[key] = True
            except (ValidationError, SidecarError):
                results[key] = False

        return results

    # Tag operations

    def add_tags(self, key: str, tags: list[str]) -> None:
        """Add tags to an entry."""
        with self._lock:
            metadata = self.get_metadata(key)
            if metadata is None:
                metadata = EntryMetadata(key=key)

            current_tags = set(metadata.tags or [])
            current_tags.update(tags)
            metadata.tags = sorted(list(current_tags))

            self.set_metadata(metadata)

    def remove_tags(self, key: str, tags: list[str]) -> None:
        """Remove tags from an entry."""
        with self._lock:
            metadata = self.get_metadata(key)
            if metadata and metadata.tags:
                current_tags = set(metadata.tags)
                current_tags.difference_update(tags)
                metadata.tags = sorted(list(current_tags)) if current_tags else None
                self.set_metadata(metadata)

    def get_entries_by_tag(self, tag: str) -> list[str]:
        """Get entries with specific tag."""
        return self.tag_index.get_entries_by_tag(tag)

    def get_all_tags(self) -> dict[str, int]:
        """Get all tags with counts."""
        return self.tag_index.get_all_tags()

    def search_tags(self, pattern: str) -> list[str]:
        """Search tags by pattern."""
        return self.tag_index.search_tags(pattern)

    def get_entries_by_tag_prefix(self, prefix: str) -> list[str]:
        """Get entries with tags matching prefix (for hierarchical tags)."""
        entries = set()
        for tag in self.tag_index.tag_counts:
            if tag.startswith(prefix):
                entries.update(self.tag_index.get_entries_by_tag(tag))
        return list(entries)

    # Note operations

    def add_note(self, note: Note) -> None:
        """Add note to an entry."""
        if note is None:
            raise TypeError("Note cannot be None")

        note_dir = self._note_dir(note.entry_key)
        note_dir.mkdir(parents=True, exist_ok=True)

        path = self._note_path(note.entry_key, note.id)

        try:
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(note.to_dict(), f, indent=2)
            temp_path.replace(path)

        except OSError as e:
            raise SidecarError(f"Failed to save note: {e}") from e

    def get_notes(self, entry_key: str) -> list[Note]:
        """Get notes for an entry."""
        note_dir = self._note_dir(entry_key)
        if not note_dir.exists():
            return []

        notes = []
        for path in note_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                notes.append(Note.from_dict(data))
            except (OSError, json.JSONDecodeError, ValidationError):
                continue

        # Sort by creation date
        notes.sort(key=lambda n: n.created_at)
        return notes

    def get_note(self, entry_key: str, note_id: str) -> Note | None:
        """Get specific note."""
        path = self._note_path(entry_key, note_id)
        if not path.exists():
            return None

        try:
            with open(path) as f:
                data = json.load(f)
            return Note.from_dict(data)
        except (OSError, json.JSONDecodeError, ValidationError):
            return None

    def update_note(self, note: Note) -> bool:
        """Update existing note."""
        if note is None:
            raise ValidationError("Note cannot be None")

        path = self._note_path(note.entry_key, note.id)
        if not path.exists():
            return False

        note.updated_at = datetime.now()

        try:
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(note.to_dict(), f, indent=2)
            temp_path.replace(path)
            return True

        except OSError:
            return False

    def delete_note(self, entry_key: str, note_id: str) -> bool:
        """Delete specific note."""
        path = self._note_path(entry_key, note_id)
        if path.exists():
            try:
                path.unlink()
                return True
            except OSError:
                return False
        return False

    def search_notes(self, query: str) -> list[Note]:
        """Search notes by content."""
        query_lower = query.lower()
        results = []

        for note_dir in self.notes_dir.iterdir():
            if note_dir.is_dir():
                for note_file in note_dir.glob("*.json"):
                    try:
                        with open(note_file) as f:
                            data = json.load(f)

                        note = Note.from_dict(data)
                        if query_lower in note.content.lower():
                            results.append(note)

                    except (OSError, json.JSONDecodeError, ValidationError):
                        continue

        return results

    # Reading status operations

    def set_reading_status(
        self,
        key: str,
        status: str,
        current_page: int | None = None,
        total_pages: int | None = None,
    ) -> None:
        """Set reading status for an entry."""
        with self._lock:
            metadata = self.get_metadata(key)
            if metadata is None:
                metadata = EntryMetadata(key=key)

            metadata.reading_status = status

            if current_page is not None:
                metadata.current_page = current_page
            if total_pages is not None:
                metadata.total_pages = total_pages

            # Update timestamps
            if status == "reading" and metadata.reading_started is None:
                metadata.reading_started = datetime.now()
            elif status == "read" and metadata.reading_completed is None:
                metadata.reading_completed = datetime.now()

            self.set_metadata(metadata)

    def get_reading_list(self, status: str | None = None) -> list[str]:
        """Get reading list by status."""
        entries = []

        for path in self.entries_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)

                if status is None or data.get("reading_status") == status:
                    entries.append(data["key"])

            except (OSError, json.JSONDecodeError):
                continue

        return entries

    def get_collection_entries(self, collection: str) -> list[str]:
        """Get entries in a collection."""
        entries = []

        for path in self.entries_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)

                collections = data.get("collections", [])
                if collection in collections:
                    entries.append(data["key"])

            except (OSError, json.JSONDecodeError):
                continue

        return entries

    # Statistics and validation

    def get_statistics(self) -> dict[str, Any]:
        """Get metadata statistics."""
        stats = {
            "total_entries": 0,
            "total_notes": 0,
            "total_tags": 0,
            "tag_distribution": {},
            "rating_distribution": defaultdict(int),
            "reading_stats": defaultdict(int),
        }

        # Count entries and gather stats
        for path in self.entries_dir.glob("*.json"):
            stats["total_entries"] += 1

            try:
                with open(path) as f:
                    data = json.load(f)

                # Rating distribution
                rating = data.get("rating")
                if rating:
                    stats["rating_distribution"][rating] += 1

                # Reading status
                status = data.get("reading_status")
                if status:
                    stats["reading_stats"][status] += 1

            except (OSError, json.JSONDecodeError):
                continue

        # Count notes
        for note_dir in self.notes_dir.iterdir():
            if note_dir.is_dir():
                stats["total_notes"] += len(list(note_dir.glob("*.json")))

        # Tag statistics
        tag_counts = self.tag_index.get_all_tags()
        stats["total_tags"] = len(tag_counts)
        stats["tag_distribution"] = dict(tag_counts)

        return stats

    def validate(self) -> tuple[bool, list[str]]:
        """Validate metadata integrity."""
        errors = []

        # Check metadata files
        for path in self.entries_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                EntryMetadata.from_dict(data)
            except (json.JSONDecodeError, ValidationError) as e:
                errors.append(f"Invalid metadata in {path.name}: {e}")
            except OSError as e:
                errors.append(f"Cannot read {path.name}: {e}")

        # Check note files
        for note_dir in self.notes_dir.iterdir():
            if note_dir.is_dir():
                for note_file in note_dir.glob("*.json"):
                    try:
                        with open(note_file) as f:
                            data = json.load(f)
                        Note.from_dict(data)
                    except (json.JSONDecodeError, ValidationError) as e:
                        errors.append(f"Invalid note in {note_file.name}: {e}")
                    except OSError as e:
                        errors.append(f"Cannot read {note_file.name}: {e}")

        return len(errors) == 0, errors

    def rebuild_index(self) -> None:
        """Rebuild metadata indexes."""
        # Rebuild tag index
        entries_metadata = {}

        for path in self.entries_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                metadata = EntryMetadata.from_dict(data)
                entries_metadata[metadata.key] = metadata
            except Exception:
                continue

        self.tag_index.rebuild(entries_metadata)
        self._save_indices()

    # Export/Import

    def export(self, path: Path) -> None:
        """Export all metadata."""
        export_data = {"version": self.SCHEMA_VERSION, "metadata": [], "notes": []}

        # Export metadata
        for metadata_file in self.entries_dir.glob("*.json"):
            try:
                with open(metadata_file) as f:
                    export_data["metadata"].append(json.load(f))
            except (OSError, json.JSONDecodeError):
                continue

        # Export notes
        for note_dir in self.notes_dir.iterdir():
            if note_dir.is_dir():
                for note_file in note_dir.glob("*.json"):
                    try:
                        with open(note_file) as f:
                            export_data["notes"].append(json.load(f))
                    except (OSError, json.JSONDecodeError):
                        continue

        # Write export
        try:
            with open(path, "w") as f:
                json.dump(export_data, f, indent=2)
        except OSError as e:
            raise SidecarError(f"Failed to export metadata: {e}") from e

    def import_from(self, path: Path) -> None:
        """Import metadata from export."""
        if not path.exists():
            raise SidecarError(f"Import file does not exist: {path}")

        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise SidecarError(f"Failed to read import file: {e}") from e

        # Import metadata
        for metadata_dict in data.get("metadata", []):
            try:
                metadata = EntryMetadata.from_dict(metadata_dict)
                self.set_metadata(metadata)
            except ValidationError:
                continue

        # Import notes
        for note_dict in data.get("notes", []):
            try:
                note = Note.from_dict(note_dict)
                self.add_note(note)
            except ValidationError:
                continue
