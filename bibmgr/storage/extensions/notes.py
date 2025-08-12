"""Notes storage extension for bibliography entries."""

import json
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import msgspec


class NoteType(Enum):
    """Types of notes."""

    GENERAL = "general"
    SUMMARY = "summary"
    CRITIQUE = "critique"
    IDEA = "idea"
    QUESTION = "question"
    TODO = "todo"


class ReadingStatus(Enum):
    """Reading status for entries."""

    TO_READ = "to_read"
    READING = "reading"
    READ = "read"
    ABANDONED = "abandoned"
    REFERENCE = "reference"


class Note(msgspec.Struct):
    """A note attached to an entry."""

    id: UUID
    entry_key: str
    content: str
    type: NoteType = NoteType.GENERAL
    title: str | None = None
    tags: list[str] = msgspec.field(default_factory=list)
    created_at: datetime = msgspec.field(default_factory=datetime.now)
    updated_at: datetime = msgspec.field(default_factory=datetime.now)
    version: int = 1


class Quote(msgspec.Struct):
    """A quote from an entry."""

    id: UUID
    entry_key: str
    text: str
    page: int | None = None
    location: str | None = None
    tags: list[str] = msgspec.field(default_factory=list)
    comment: str | None = None
    created_at: datetime = msgspec.field(default_factory=datetime.now)


class ReadingProgress(msgspec.Struct):
    """Reading progress for an entry."""

    entry_key: str
    status: ReadingStatus = ReadingStatus.TO_READ
    current_page: int | None = None
    total_pages: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    rating: int | None = None
    notes: str | None = None
    updated_at: datetime = msgspec.field(default_factory=datetime.now)

    @property
    def percentage(self) -> float:
        """Calculate reading percentage."""
        if not self.total_pages or not self.current_page:
            return 0.0
        return (self.current_page / self.total_pages) * 100.0


class ReadingSession(msgspec.Struct):
    """A reading session record."""

    id: UUID
    entry_key: str
    duration_minutes: int
    pages_read: int | None = None
    notes: str | None = None
    created_at: datetime = msgspec.field(default_factory=datetime.now)


class NotesExtension:
    """Extension for managing notes, quotes, and reading progress."""

    def __init__(self, backend):
        """Initialize notes extension.

        Args:
            backend: Storage backend instance
        """
        self.backend = backend

        # For filesystem backends, use file storage
        if hasattr(backend, "data_dir"):
            self._notes_dir = backend.data_dir / "notes"
            self._notes_dir.mkdir(exist_ok=True)
            self._quotes_dir = backend.data_dir / "quotes"
            self._quotes_dir.mkdir(exist_ok=True)
            self._progress_dir = backend.data_dir / "progress"
            self._progress_dir.mkdir(exist_ok=True)
            self._sessions_dir = backend.data_dir / "sessions"
            self._sessions_dir.mkdir(exist_ok=True)
            self._use_files = True
        else:
            # For memory backends, use in-memory storage
            self._notes_data = {}
            self._notes_history = {}  # Note ID -> list of versions
            self._quotes_data = {}
            self._progress_data = {}  # Entry key -> progress
            self._sessions_data = {}
            self._use_files = False

    def _serialize_for_json(self, obj: Any) -> dict[str, Any]:
        """Serialize msgspec struct for JSON storage."""
        data = msgspec.to_builtins(obj)
        # Convert UUIDs to strings
        if "id" in data and isinstance(data["id"], UUID):
            data["id"] = str(data["id"])
        # Convert enums
        if "type" in data and hasattr(data["type"], "value"):
            data["type"] = data["type"].value
        if "status" in data and hasattr(data["status"], "value"):
            data["status"] = data["status"].value
        # Convert datetimes
        for field in ["created_at", "updated_at", "started_at", "finished_at"]:
            if field in data and isinstance(data[field], datetime):
                data[field] = data[field].isoformat()
        return data

    def _deserialize_from_json(self, data: dict[str, Any], cls) -> Any:
        """Deserialize from JSON to msgspec struct."""
        # Convert UUIDs
        if "id" in data and isinstance(data["id"], str):
            data["id"] = UUID(data["id"])
        # Convert enums
        if "type" in data and cls == Note:
            data["type"] = NoteType(data["type"])
        if "status" in data and cls == ReadingProgress:
            data["status"] = ReadingStatus(data["status"])
        # Convert datetimes
        for field in ["created_at", "updated_at", "started_at", "finished_at"]:
            if field in data and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field])
        return msgspec.convert(data, cls)

    def _save_note(self, note: Note) -> None:
        """Save note to storage."""
        if self._use_files:
            # Save current version
            file_path = self._notes_dir / f"{note.id}.json"
            data = self._serialize_for_json(note)
            file_path.write_text(json.dumps(data, indent=2))

            # Also save to version history
            version_path = self._notes_dir / f"{note.id}_v{note.version}.json"
            version_path.write_text(json.dumps(data, indent=2))
        else:
            self._notes_data[note.id] = note
            # Save to history
            if note.id not in self._notes_history:
                self._notes_history[note.id] = []
            self._notes_history[note.id].append(note)

    def _load_note(self, note_id: UUID) -> Note | None:
        """Load note from storage."""
        if self._use_files:
            file_path = self._notes_dir / f"{note_id}.json"
            if not file_path.exists():
                return None
            data = json.loads(file_path.read_text())
            return self._deserialize_from_json(data, Note)
        else:
            return self._notes_data.get(note_id)

    def create_note(
        self,
        entry_key: str,
        content: str,
        type: NoteType = NoteType.GENERAL,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> Note:
        """Create a new note.

        Args:
            entry_key: Entry key this note belongs to
            content: Note content
            type: Type of note
            title: Optional title
            tags: Optional tags

        Returns:
            Created note
        """
        note = Note(
            id=uuid4(),
            entry_key=entry_key,
            content=content,
            type=type,
            title=title,
            tags=tags or [],
        )

        self._save_note(note)
        return note

    def update_note(
        self,
        note_id: UUID,
        content: str | None = None,
        title: str | None = None,
        tags: list[str] | None = None,
        type: NoteType | None = None,
    ) -> Note:
        """Update an existing note.

        Args:
            note_id: Note ID
            content: New content (optional)
            title: New title (optional)
            tags: New tags (optional)
            type: New type (optional)

        Returns:
            Updated note
        """
        note = self._load_note(note_id)
        if not note:
            raise ValueError(f"Note {note_id} not found")

        # Create updated version
        updated_data = msgspec.to_builtins(note)
        if content is not None:
            updated_data["content"] = content
        if title is not None:
            updated_data["title"] = title
        if tags is not None:
            updated_data["tags"] = tags
        if type is not None:
            updated_data["type"] = type

        updated_data["updated_at"] = datetime.now()
        updated_data["version"] = note.version + 1

        updated_note = msgspec.convert(updated_data, Note)
        self._save_note(updated_note)

        return updated_note

    def get_note(self, note_id: UUID) -> Note | None:
        """Get a note by ID."""
        return self._load_note(note_id)

    def delete_note(self, note_id: UUID) -> bool:
        """Delete a note.

        Args:
            note_id: Note ID

        Returns:
            True if deleted, False if not found
        """
        if self._use_files:
            file_path = self._notes_dir / f"{note_id}.json"
            if file_path.exists():
                file_path.unlink()
                # Also delete history files
                history_files = list(self._notes_dir.glob(f"{note_id}_v*.json"))
                for hf in history_files:
                    hf.unlink()
                return True
            return False
        else:
            if note_id in self._notes_data:
                del self._notes_data[note_id]
                if note_id in self._notes_history:
                    del self._notes_history[note_id]
                return True
            return False

    def get_note_history(self, note_id: UUID) -> list[Note]:
        """Get version history for a note.

        Args:
            note_id: Note ID

        Returns:
            List of note versions
        """
        if self._use_files:
            # Load all version files
            versions = []
            version_files = sorted(self._notes_dir.glob(f"{note_id}_v*.json"))

            for vf in version_files:
                data = json.loads(vf.read_text())
                note = self._deserialize_from_json(data, Note)
                versions.append(note)

            return versions
        else:
            return self._notes_history.get(note_id, [])

    def get_entry_notes(
        self, entry_key: str, type: NoteType | None = None
    ) -> list[Note]:
        """Get all notes for an entry.

        Args:
            entry_key: Entry key
            type: Filter by note type (optional)

        Returns:
            List of notes
        """
        notes = []

        if self._use_files:
            for file_path in self._notes_dir.glob("*.json"):
                # Skip version files
                if "_v" in file_path.stem:
                    continue
                data = json.loads(file_path.read_text())
                if data.get("entry_key") == entry_key:
                    note = self._deserialize_from_json(data, Note)
                    if type is None or note.type == type:
                        notes.append(note)
        else:
            for note in self._notes_data.values():
                if note.entry_key == entry_key:
                    if type is None or note.type == type:
                        notes.append(note)

        # Sort by creation time
        notes.sort(key=lambda n: n.created_at)
        return notes

    def search_notes(
        self,
        query: str | None = None,
        tags: list[str] | None = None,
        type: NoteType | None = None,
    ) -> list[Note]:
        """Search notes.

        Args:
            query: Text search query
            tags: Filter by tags
            type: Filter by type

        Returns:
            List of matching notes
        """
        results = []

        if self._use_files:
            for file_path in self._notes_dir.glob("*.json"):
                if "_v" in file_path.stem:
                    continue
                data = json.loads(file_path.read_text())
                note = self._deserialize_from_json(data, Note)

                # Apply filters
                if type and note.type != type:
                    continue
                if tags and not any(tag in note.tags for tag in tags):
                    continue
                if query and query.lower() not in note.content.lower():
                    continue

                results.append(note)
        else:
            for note in self._notes_data.values():
                # Apply filters
                if type and note.type != type:
                    continue
                if tags and not any(tag in note.tags for tag in tags):
                    continue
                if query and query.lower() not in note.content.lower():
                    continue

                results.append(note)

        return results

    def add_quote(
        self,
        entry_key: str,
        text: str,
        page: int | None = None,
        location: str | None = None,
        tags: list[str] | None = None,
        comment: str | None = None,
    ) -> Quote:
        """Add a quote from an entry.

        Args:
            entry_key: Entry key
            text: Quote text
            page: Page number (optional)
            location: Location description (optional)
            tags: Tags (optional)
            comment: Comment (optional)

        Returns:
            Created quote
        """
        quote = Quote(
            id=uuid4(),
            entry_key=entry_key,
            text=text,
            page=page,
            location=location,
            tags=tags or [],
            comment=comment,
        )

        if self._use_files:
            file_path = self._quotes_dir / f"{quote.id}.json"
            data = self._serialize_for_json(quote)
            file_path.write_text(json.dumps(data, indent=2))
        else:
            self._quotes_data[quote.id] = quote

        return quote

    def get_entry_quotes(self, entry_key: str) -> list[Quote]:
        """Get all quotes for an entry.

        Args:
            entry_key: Entry key

        Returns:
            List of quotes sorted by creation time
        """
        quotes = []

        if self._use_files:
            for file_path in self._quotes_dir.glob("*.json"):
                data = json.loads(file_path.read_text())
                if data.get("entry_key") == entry_key:
                    quote = self._deserialize_from_json(data, Quote)
                    quotes.append(quote)
        else:
            for quote in self._quotes_data.values():
                if quote.entry_key == entry_key:
                    quotes.append(quote)

        # Sort by creation time
        quotes.sort(key=lambda q: q.created_at)
        return quotes

    def search_quotes(
        self,
        query: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Quote]:
        """Search quotes.

        Args:
            query: Text search query
            tags: Filter by tags

        Returns:
            List of matching quotes
        """
        results = []

        if self._use_files:
            for file_path in self._quotes_dir.glob("*.json"):
                data = json.loads(file_path.read_text())
                quote = self._deserialize_from_json(data, Quote)

                # Apply filters
                if tags and not any(tag in quote.tags for tag in tags):
                    continue
                if query and query.lower() not in quote.text.lower():
                    continue

                results.append(quote)
        else:
            for quote in self._quotes_data.values():
                # Apply filters
                if tags and not any(tag in quote.tags for tag in tags):
                    continue
                if query and query.lower() not in quote.text.lower():
                    continue

                results.append(quote)

        return results

    def track_reading_progress(
        self,
        entry_key: str,
        status: ReadingStatus | None = None,
        current_page: int | None = None,
        total_pages: int | None = None,
        rating: int | None = None,
        notes: str | None = None,
    ) -> ReadingProgress:
        """Track reading progress for an entry.

        Args:
            entry_key: Entry key
            status: Reading status
            current_page: Current page
            total_pages: Total pages
            rating: Rating (1-5)
            notes: Notes

        Returns:
            Updated reading progress
        """
        # Load existing or create new
        progress = self._load_progress(entry_key)

        if progress:
            # Update existing
            data = msgspec.to_builtins(progress)
            if status is not None:
                data["status"] = status
            if current_page is not None:
                data["current_page"] = current_page
            if total_pages is not None:
                data["total_pages"] = total_pages
            if rating is not None:
                data["rating"] = rating
            if notes is not None:
                data["notes"] = notes
            data["updated_at"] = datetime.now()

            progress = msgspec.convert(data, ReadingProgress)
        else:
            # Create new
            progress = ReadingProgress(
                entry_key=entry_key,
                status=status or ReadingStatus.TO_READ,
                current_page=current_page,
                total_pages=total_pages,
                rating=rating,
                notes=notes,
            )

        # Handle status transitions
        if status == ReadingStatus.READING and progress.started_at is None:
            progress = msgspec.structs.replace(progress, started_at=datetime.now())
        elif status == ReadingStatus.READ and progress.finished_at is None:
            progress = msgspec.structs.replace(progress, finished_at=datetime.now())

        self._save_progress(progress)
        return progress

    def update_reading_progress(
        self,
        entry_key: str,
        current_page: int | None = None,
        rating: int | None = None,
        notes: str | None = None,
    ) -> ReadingProgress:
        """Update reading progress.

        Args:
            entry_key: Entry key
            current_page: New current page
            rating: New rating
            notes: New notes

        Returns:
            Updated progress
        """
        return self.track_reading_progress(
            entry_key=entry_key,
            current_page=current_page,
            rating=rating,
            notes=notes,
        )

    def _load_progress(self, entry_key: str) -> ReadingProgress | None:
        """Load reading progress for an entry."""
        if self._use_files:
            file_path = self._progress_dir / f"{entry_key}.json"
            if not file_path.exists():
                return None
            data = json.loads(file_path.read_text())
            return self._deserialize_from_json(data, ReadingProgress)
        else:
            return self._progress_data.get(entry_key)

    def _save_progress(self, progress: ReadingProgress) -> None:
        """Save reading progress."""
        if self._use_files:
            file_path = self._progress_dir / f"{progress.entry_key}.json"
            data = self._serialize_for_json(progress)
            file_path.write_text(json.dumps(data, indent=2))
        else:
            self._progress_data[progress.entry_key] = progress

    def add_reading_session(
        self,
        entry_key: str,
        duration_minutes: int,
        pages_read: int | None = None,
        notes: str | None = None,
    ) -> ReadingSession:
        """Add a reading session.

        Args:
            entry_key: Entry key
            duration_minutes: Session duration in minutes
            pages_read: Pages read in session
            notes: Session notes

        Returns:
            Created session
        """
        session = ReadingSession(
            id=uuid4(),
            entry_key=entry_key,
            duration_minutes=duration_minutes,
            pages_read=pages_read,
            notes=notes,
        )

        if self._use_files:
            file_path = self._sessions_dir / f"{session.id}.json"
            data = self._serialize_for_json(session)
            file_path.write_text(json.dumps(data, indent=2))
        else:
            self._sessions_data[session.id] = session

        return session

    def get_reading_stats(self, entry_key: str) -> dict[str, Any]:
        """Get reading statistics for an entry.

        Args:
            entry_key: Entry key

        Returns:
            Dictionary with stats
        """
        sessions = []

        if self._use_files:
            for file_path in self._sessions_dir.glob("*.json"):
                data = json.loads(file_path.read_text())
                if data.get("entry_key") == entry_key:
                    session = self._deserialize_from_json(data, ReadingSession)
                    sessions.append(session)
        else:
            sessions = [
                s for s in self._sessions_data.values() if s.entry_key == entry_key
            ]

        if not sessions:
            return {
                "session_count": 0,
                "total_time_minutes": 0,
                "total_pages_read": 0,
                "avg_session_duration": 0.0,
                "avg_pages_per_session": 0.0,
            }

        total_time = sum(s.duration_minutes for s in sessions)
        total_pages = sum(s.pages_read or 0 for s in sessions)

        return {
            "session_count": len(sessions),
            "total_time_minutes": total_time,
            "total_pages_read": total_pages,
            "avg_session_duration": total_time / len(sessions),
            "avg_pages_per_session": total_pages / len(sessions)
            if total_pages
            else 0.0,
        }

    def bulk_update_tags(
        self,
        note_ids: list[UUID],
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
    ) -> list[Note]:
        """Bulk update tags on multiple notes.

        Args:
            note_ids: List of note IDs
            add_tags: Tags to add
            remove_tags: Tags to remove

        Returns:
            List of updated notes
        """
        updated = []

        for note_id in note_ids:
            note = self.get_note(note_id)
            if not note:
                continue

            # Update tags
            current_tags = set(note.tags)
            if remove_tags:
                current_tags -= set(remove_tags)
            if add_tags:
                current_tags |= set(add_tags)

            updated_note = self.update_note(note_id, tags=sorted(list(current_tags)))
            updated.append(updated_note)

        return updated
