"""High-level manager for notes operations.

This module provides a clean interface for managing notes, quotes,
reading progress, and templates with proper validation and error handling.
"""

from __future__ import annotations

import threading
from typing import Any
from uuid import uuid4

from bibmgr.core.models import Entry
from bibmgr.notes.exceptions import (
    NoteNotFoundError,
    NoteValidationError,
    QuoteValidationError,
    VersionNotFoundError,
)
from bibmgr.notes.models import (
    Note,
    NoteType,
    NoteVersion,
    Priority,
    Quote,
    QuoteCategory,
    ReadingProgress,
    ReadingStatus,
)
from bibmgr.notes.storage import NoteStorage
from bibmgr.notes.templates import NoteTemplate, TemplateManager


class NoteManager:
    """High-level manager for notes and annotations."""

    def __init__(self, storage: NoteStorage):
        """Initialize manager with storage backend.

        Args:
            storage: Storage backend instance
        """
        self.storage = storage
        self.template_manager = TemplateManager()
        self._lock = threading.RLock()

    # Note operations

    def create_note(
        self,
        entry_key: str,
        content: str,
        type: NoteType | str = NoteType.GENERAL,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> Note:
        """Create a new note.

        Args:
            entry_key: Associated bibliography entry
            content: Note content
            type: Type of note
            title: Optional title
            tags: Optional tags

        Returns:
            Created note

        Raises:
            NoteValidationError: If validation fails
        """
        # Validate input
        if not entry_key:
            raise NoteValidationError("entry_key", "Entry key cannot be empty")

        if not content and content != "":  # Allow empty string content
            raise NoteValidationError("content", "Content cannot be None")

        # Convert string type to enum if needed
        if isinstance(type, str):
            try:
                type = NoteType(type)
            except (ValueError, KeyError):
                raise NoteValidationError("type", f"Invalid note type: {type}")

        # Create note
        note = Note(
            id=str(uuid4()),
            entry_key=entry_key,
            content=content,
            type=type,
            title=title,
            tags=tags or [],
            references=[],
        )

        # Store it
        with self._lock:
            self.storage.add_note(note)

        return note

    def update_note(
        self,
        note_id: str,
        content: str | None = None,
        title: str | None = None,
        tags: list[str] | None = None,
        type: NoteType | str | None = None,
    ) -> Note | None:
        """Update an existing note.

        Args:
            note_id: Note ID
            content: New content
            title: New title
            tags: New tags
            type: New type

        Returns:
            Updated note or None if not found
        """
        with self._lock:
            # Get existing note
            note = self.storage.get_note(note_id)
            if not note:
                return None

            # Build update dict
            updates = {}
            if content is not None:
                updates["content"] = content
            if title is not None:
                updates["title"] = title
            if tags is not None:
                updates["tags"] = tags
            if type is not None:
                if isinstance(type, str):
                    type = NoteType(type)
                updates["type"] = type

            # Update note
            updated_note = note.update(**updates)
            self.storage.update_note(updated_note)

            return updated_note

    def delete_note(self, note_id: str) -> bool:
        """Delete a note.

        Args:
            note_id: Note ID

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            return self.storage.delete_note(note_id)

    def get_note(self, note_id: str) -> Note | None:
        """Get a note by ID.

        Args:
            note_id: Note ID

        Returns:
            Note or None if not found
        """
        return self.storage.get_note(note_id)

    def get_notes(
        self,
        entry_key: str,
        type: NoteType | str | None = None,
    ) -> list[Note]:
        """Get notes for an entry.

        Args:
            entry_key: Entry key
            type: Optional filter by type

        Returns:
            List of notes
        """
        notes = self.storage.get_notes_for_entry(entry_key)

        if type:
            if isinstance(type, str):
                type = NoteType(type)
            notes = [n for n in notes if n.type == type]

        return notes

    def search_notes(
        self,
        query: str,
        type: NoteType | str | None = None,
        tags: list[str] | None = None,
    ) -> list[Note]:
        """Search notes.

        Args:
            query: Search query
            type: Optional type filter
            tags: Optional tag filter

        Returns:
            List of matching notes
        """
        note_type = None
        if type:
            if isinstance(type, str):
                note_type = NoteType(type)
            else:
                note_type = type

        return self.storage.search_notes(query, type=note_type, tags=tags)

    # Quote operations

    def add_quote(
        self,
        entry_key: str,
        text: str,
        page: int | None = None,
        section: str | None = None,
        category: QuoteCategory | str | None = None,
        importance: int = 3,
        tags: list[str] | None = None,
        note: str | None = None,
    ) -> Quote:
        """Add a quote.

        Args:
            entry_key: Associated entry
            text: Quote text
            page: Optional page number
            section: Optional section
            category: Optional category
            importance: Importance (1-5)
            tags: Optional tags
            note: Optional note

        Returns:
            Created quote

        Raises:
            QuoteValidationError: If validation fails
        """
        # Validate
        if not entry_key:
            raise QuoteValidationError("entry_key", "Entry key cannot be empty")

        if not text:
            raise QuoteValidationError("text", "Quote text cannot be empty")

        if not 1 <= importance <= 5:
            raise QuoteValidationError(
                "importance",
                f"Importance must be 1-5, got {importance}",
            )

        # Convert category
        if category:
            if isinstance(category, str):
                try:
                    category = QuoteCategory(category)
                except (ValueError, KeyError):
                    raise QuoteValidationError(
                        "category",
                        f"Invalid category: {category}",
                    )
        else:
            category = QuoteCategory.OTHER

        # Create quote
        quote = Quote(
            id=str(uuid4()),
            entry_key=entry_key,
            text=text,
            page=page,
            section=section,
            category=category,
            importance=importance,
            tags=tags or [],
            note=note,
        )

        # Store it
        with self._lock:
            self.storage.add_quote(quote)

        return quote

    def delete_quote(self, quote_id: str) -> bool:
        """Delete a quote.

        Args:
            quote_id: Quote ID

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            return self.storage.delete_quote(quote_id)

    def get_quotes(
        self,
        entry_key: str,
        category: QuoteCategory | str | None = None,
    ) -> list[Quote]:
        """Get quotes for an entry.

        Args:
            entry_key: Entry key
            category: Optional category filter

        Returns:
            List of quotes
        """
        quotes = self.storage.get_quotes_for_entry(entry_key)

        if category:
            if isinstance(category, str):
                category = QuoteCategory(category)
            quotes = [q for q in quotes if q.category == category]

        return quotes

    def search_quotes(
        self,
        query: str | None = None,
        tags: list[str] | None = None,
        category: QuoteCategory | str | None = None,
    ) -> list[Quote]:
        """Search quotes.

        Args:
            query: Optional text query
            tags: Optional tag filter
            category: Optional category filter

        Returns:
            List of matching quotes
        """
        quote_category = None
        if category:
            if isinstance(category, str):
                quote_category = QuoteCategory(category)
            else:
                quote_category = category

        return self.storage.search_quotes(
            query=query,
            tags=tags,
            category=quote_category,
        )

    # Reading progress operations

    def track_reading(
        self,
        entry_key: str,
        page: int | None = None,
        total_pages: int | None = None,
        time_minutes: int | None = None,
        priority: Priority | int | None = None,
        status: ReadingStatus | str | None = None,
        importance: int | None = None,
        difficulty: int | None = None,
        enjoyment: int | None = None,
        comprehension: int | None = None,
    ) -> ReadingProgress:
        """Track reading progress for an entry.

        Args:
            entry_key: Entry key
            page: Current page
            total_pages: Total pages
            time_minutes: Reading time
            priority: Priority level
            status: Reading status
            importance: Importance rating
            difficulty: Difficulty rating
            enjoyment: Enjoyment rating
            comprehension: Comprehension rating

        Returns:
            Updated reading progress
        """
        with self._lock:
            # Get existing or create new
            progress = self.storage.get_progress(entry_key)

            if progress:
                # Update existing
                if page is not None or time_minutes is not None:
                    progress = progress.update_progress(
                        page=page,
                        time_minutes=time_minutes or 0,
                    )

                # Update other fields
                updates = {}
                if priority is not None:
                    if isinstance(priority, int):
                        priority = Priority(priority)
                    updates["priority"] = priority

                if status is not None:
                    if isinstance(status, str):
                        status = ReadingStatus(status)
                    updates["status"] = status

                if total_pages is not None:
                    updates["total_pages"] = total_pages

                if importance is not None:
                    updates["importance"] = importance

                if difficulty is not None:
                    updates["difficulty"] = difficulty

                if enjoyment is not None:
                    updates["enjoyment"] = enjoyment

                if comprehension is not None:
                    updates["comprehension"] = comprehension

                if updates:
                    from dataclasses import replace

                    progress = replace(progress, **updates)

                self.storage.update_progress(progress)

            else:
                # Create new
                if priority and isinstance(priority, int):
                    priority = Priority(priority)

                if status and isinstance(status, str):
                    status = ReadingStatus(status)

                # Determine initial status
                if not status:
                    if page and total_pages and page >= total_pages:
                        status = ReadingStatus.READ
                    elif page and page > 0:
                        status = ReadingStatus.READING
                    else:
                        status = ReadingStatus.UNREAD

                progress = ReadingProgress(
                    entry_key=entry_key,
                    status=status,
                    priority=priority or Priority.MEDIUM,
                    current_page=page or 0,
                    total_pages=total_pages,
                    reading_time_minutes=time_minutes or 0,
                    session_count=1 if (time_minutes and time_minutes > 0) else 0,
                    importance=importance or 3,
                    difficulty=difficulty or 3,
                    enjoyment=enjoyment or 3,
                    comprehension=comprehension or 3,
                )

                self.storage.add_progress(progress)

        return progress

    def get_reading_progress(self, entry_key: str) -> ReadingProgress | None:
        """Get reading progress for an entry.

        Args:
            entry_key: Entry key

        Returns:
            Reading progress or None
        """
        return self.storage.get_progress(entry_key)

    def update_reading_status(
        self,
        entry_key: str,
        status: ReadingStatus | str,
    ) -> ReadingProgress | None:
        """Update reading status.

        Args:
            entry_key: Entry key
            status: New status

        Returns:
            Updated progress or None if not found
        """
        with self._lock:
            progress = self.storage.get_progress(entry_key)
            if not progress:
                return None

            if isinstance(status, str):
                status = ReadingStatus(status)

            from dataclasses import replace

            updated = replace(progress, status=status)
            self.storage.update_progress(updated)

            return updated

    def get_reading_list(
        self,
        status: ReadingStatus | str | None = None,
        min_priority: Priority | int | None = None,
    ) -> list[ReadingProgress]:
        """Get reading list.

        Args:
            status: Optional status filter
            min_priority: Optional minimum priority

        Returns:
            List of reading progress entries
        """
        if status and isinstance(status, str):
            status = status

        if min_priority and isinstance(min_priority, Priority):
            min_priority = min_priority.value

        return self.storage.get_reading_list(
            status=status,
            min_priority=min_priority,
        )

    # Template operations

    def create_note_from_template(
        self,
        entry_key: str,
        template_name: str,
        entry: Entry | None = None,
        **variables: Any,
    ) -> Note:
        """Create note from template.

        Args:
            entry_key: Entry key
            template_name: Template name
            entry: Optional entry for context
            **variables: Template variables

        Returns:
            Created note

        Raises:
            TemplateNotFoundError: If template not found
            KeyError: If required variable missing
        """
        # Get template content
        title, content, note_type, tags = self.template_manager.create_note_content(
            template_name,
            entry=entry,
            **variables,
        )

        # Create note
        return self.create_note(
            entry_key=entry_key,
            content=content,
            type=note_type,
            title=title,
            tags=tags,
        )

    def get_available_templates(self) -> list[str]:
        """Get available template names.

        Returns:
            List of template names
        """
        return self.template_manager.list_templates()

    def add_custom_template(self, template: NoteTemplate) -> None:
        """Add a custom template.

        Args:
            template: Template to add
        """
        self.template_manager.add_template(template)

    # Bulk operations

    def bulk_update_tags(
        self,
        note_ids: list[str],
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> list[Note]:
        """Bulk update tags on notes.

        Args:
            note_ids: Note IDs to update
            add: Tags to add
            remove: Tags to remove

        Returns:
            List of updated notes
        """
        updated = []

        with self._lock:
            for note_id in note_ids:
                note = self.storage.get_note(note_id)
                if not note:
                    continue

                # Update tags
                new_tags = set(note.tags)
                if add:
                    new_tags.update(add)
                if remove:
                    new_tags.difference_update(remove)

                # Update note
                updated_note = note.update(tags=list(new_tags))
                self.storage.update_note(updated_note)
                updated.append(updated_note)

        return updated

    def merge_notes(
        self,
        note_ids: list[str],
        title: str | None = None,
    ) -> Note:
        """Merge multiple notes into one.

        Args:
            note_ids: Note IDs to merge
            title: Title for merged note

        Returns:
            Merged note

        Raises:
            ValueError: If invalid input
        """
        if not note_ids:
            raise ValueError("No note IDs provided")

        if len(note_ids) < 2:
            raise ValueError("Need at least 2 notes to merge")

        with self._lock:
            # Get notes
            notes = []
            for note_id in note_ids:
                note = self.storage.get_note(note_id)
                if note:
                    notes.append(note)

            if not notes:
                raise ValueError("No valid notes found")

            if len(notes) < 2:
                raise ValueError("Need at least 2 valid notes to merge")

            # Combine content
            combined_content = []
            combined_tags = set()

            for note in notes:
                if note.title:
                    combined_content.append(f"## {note.title}")
                combined_content.append(note.content)
                combined_content.append("")  # Blank line
                combined_tags.update(note.tags)

            # Create merged note
            merged = self.create_note(
                entry_key=notes[0].entry_key,
                content="\n".join(combined_content),
                title=title or "Merged Notes",
                type=notes[0].type,
                tags=list(combined_tags),
            )

            # Delete original notes
            for note in notes:
                self.storage.delete_note(note.id)

        return merged

    def split_note(
        self,
        note_id: str,
        sections: list[str],
    ) -> list[Note]:
        """Split a note into multiple notes by sections.

        Args:
            note_id: Note ID to split
            sections: Section markers to split by

        Returns:
            List of created notes

        Raises:
            NoteNotFoundError: If note not found
            ValueError: If invalid sections
        """
        if not sections:
            raise ValueError("No sections provided")

        with self._lock:
            # Get note
            note = self.storage.get_note(note_id)
            if not note:
                raise NoteNotFoundError(note_id)

            # Split content
            content_sections = []
            current_section = []
            lines = note.content.split("\n")

            for line in lines:
                if any(section in line for section in sections):
                    if current_section:
                        content_sections.append("\n".join(current_section))
                    current_section = [line]
                else:
                    current_section.append(line)

            if current_section:
                content_sections.append("\n".join(current_section))

            # Create new notes
            new_notes = []
            for i, content in enumerate(content_sections):
                if not content.strip():
                    continue

                # Extract title from first line if it's a header
                lines = content.split("\n")
                title = None
                if lines and lines[0].startswith("#"):
                    title = lines[0].lstrip("#").strip()

                new_note = self.create_note(
                    entry_key=note.entry_key,
                    content=content,
                    title=title or f"Part {i + 1} of {note.title or 'Split Note'}",
                    type=note.type,
                    tags=list(note.tags),
                )
                new_notes.append(new_note)

            # Delete original
            if new_notes:
                self.storage.delete_note(note_id)

        return new_notes

    # Version operations

    def get_note_history(self, note_id: str) -> list[NoteVersion]:
        """Get version history for a note.

        Args:
            note_id: Note ID

        Returns:
            List of versions
        """
        return self.storage.get_note_versions(note_id)

    def restore_note_version(self, note_id: str, version: int) -> Note:
        """Restore a previous version of a note.

        Args:
            note_id: Note ID
            version: Version number to restore

        Returns:
            Restored note

        Raises:
            VersionNotFoundError: If version not found
            ValueError: If invalid version
        """
        if version < 1:
            raise ValueError(f"Invalid version number: {version}")

        with self._lock:
            # Get the version
            historical = self.storage.get_note_at_version(note_id, version)
            if not historical:
                raise VersionNotFoundError(note_id, version)

            # Get current note for metadata
            current = self.storage.get_note(note_id)
            if not current:
                raise NoteNotFoundError(note_id)

            # Create restored version
            restored = current.update(content=historical.content)
            self.storage.update_note(
                restored,
                change_summary=f"Restored from version {version}",
            )

        return restored

    def compare_versions(
        self,
        note_id: str,
        v1: int,
        v2: int,
    ) -> str:
        """Compare two versions of a note.

        Args:
            note_id: Note ID
            v1: First version
            v2: Second version

        Returns:
            Diff string

        Raises:
            VersionNotFoundError: If version not found
        """
        # Get versions
        version1 = self.storage.get_note_at_version(note_id, v1)
        version2 = self.storage.get_note_at_version(note_id, v2)

        if not version1:
            raise VersionNotFoundError(note_id, v1)
        if not version2:
            raise VersionNotFoundError(note_id, v2)

        # Create version objects for diff
        nv1 = NoteVersion(
            note_id=note_id,
            version=v1,
            content=version1.content,
            content_hash=version1.content_hash,
            created_at=version1.updated_at,
        )

        nv2 = NoteVersion(
            note_id=note_id,
            version=v2,
            content=version2.content,
            content_hash=version2.content_hash,
            created_at=version2.updated_at,
        )

        return nv2.diff_from(nv1)

    # Export operations

    def export_notes(
        self,
        entry_key: str,
        format: str = "markdown",
    ) -> str:
        """Export notes for an entry.

        Args:
            entry_key: Entry key
            format: Export format (markdown)

        Returns:
            Exported content
        """
        notes = self.get_notes(entry_key)

        if not notes:
            return ""

        if format == "markdown":
            sections = []
            for note in notes:
                sections.append(note.to_markdown())
            return "\n\n---\n\n".join(sections)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def export_quotes(
        self,
        entry_key: str,
        format: str = "markdown",
    ) -> str:
        """Export quotes for an entry.

        Args:
            entry_key: Entry key
            format: Export format (markdown or latex)

        Returns:
            Exported content
        """
        quotes = self.get_quotes(entry_key)

        if not quotes:
            return ""

        if format == "markdown":
            lines = []
            for quote in quotes:
                lines.append(quote.to_markdown())
            return "\n\n".join(lines)

        elif format == "latex":
            lines = []
            for quote in quotes:
                lines.append(quote.to_latex())
            return "\n\n".join(lines)

        else:
            raise ValueError(f"Unsupported format: {format}")

    def export_reading_report(
        self,
        status: ReadingStatus | str | None = None,
        min_priority: Priority | int | None = None,
    ) -> str:
        """Export reading progress report.

        Args:
            status: Optional status filter
            min_priority: Optional priority filter

        Returns:
            Markdown report
        """
        progress_list = self.get_reading_list(
            status=status,
            min_priority=min_priority,
        )

        if not progress_list:
            return "# Reading Report\n\nNo entries found."

        lines = ["# Reading Report", ""]
        lines.append(f"**Total Entries**: {len(progress_list)}")
        lines.append("")

        for progress in progress_list:
            lines.append(f"## {progress.entry_key}")
            lines.append(f"- **Status**: {progress.status.value}")
            lines.append(f"- **Priority**: {progress.priority.name}")
            lines.append(f"- **Progress**: {progress.progress_percentage:.1f}%")

            if progress.current_page > 0:
                lines.append(
                    f"- **Pages**: {progress.current_page}/{progress.total_pages or '?'}"
                )

            if progress.reading_time_minutes > 0:
                hours = progress.reading_time_minutes // 60
                mins = progress.reading_time_minutes % 60
                lines.append(f"- **Time**: {hours}h {mins}m")

            lines.append("")

        return "\n".join(lines)

    # Statistics

    def get_statistics(self) -> dict[str, Any]:
        """Get global statistics.

        Returns:
            Dictionary of statistics
        """
        return self.storage.get_statistics()

    def get_entry_statistics(self, entry_key: str) -> dict[str, Any]:
        """Get statistics for an entry.

        Args:
            entry_key: Entry key

        Returns:
            Dictionary of statistics
        """
        stats = {
            "note_count": 0,
            "quote_count": 0,
            "reading_progress": 0.0,
            "reading_time": 0,
            "session_count": 0,
            "average_quote_importance": 0.0,
            "note_types": {},
        }

        # Count notes by type
        notes = self.get_notes(entry_key)
        stats["note_count"] = len(notes)

        for note in notes:
            type_name = note.type.value
            stats["note_types"][type_name] = stats["note_types"].get(type_name, 0) + 1

        # Count quotes
        quotes = self.get_quotes(entry_key)
        stats["quote_count"] = len(quotes)

        if quotes:
            total_importance = sum(q.importance for q in quotes)
            stats["average_quote_importance"] = total_importance / len(quotes)

        # Reading progress
        progress = self.get_reading_progress(entry_key)
        if progress:
            stats["reading_progress"] = progress.progress_percentage
            stats["reading_time"] = progress.reading_time_minutes
            stats["session_count"] = progress.session_count

        return stats
