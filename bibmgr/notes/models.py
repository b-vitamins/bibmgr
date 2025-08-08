"""Data models for notes and annotations.

This module provides immutable dataclass models for notes, quotes,
reading progress, and version tracking with comprehensive validation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from datetime import datetime
from difflib import unified_diff
from enum import Enum
from typing import Any

from bibmgr.notes.exceptions import NoteValidationError, QuoteValidationError


class NoteType(str, Enum):
    """Types of notes for categorization."""

    SUMMARY = "summary"
    CRITIQUE = "critique"
    IDEA = "idea"
    QUESTION = "question"
    TODO = "todo"
    REFERENCE = "reference"
    QUOTE = "quote"
    GENERAL = "general"
    METHODOLOGY = "methodology"
    RESULTS = "results"


class ReadingStatus(str, Enum):
    """Reading status for bibliography entries."""

    UNREAD = "unread"
    READING = "reading"
    READ = "read"
    SKIMMED = "skimmed"
    TO_REREAD = "to_reread"
    PARTIALLY_READ = "partially_read"


class Priority(int, Enum):
    """Priority levels for reading list."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class QuoteCategory(str, Enum):
    """Categories for quotes and highlights."""

    DEFINITION = "definition"
    METHODOLOGY = "methodology"
    FINDING = "finding"
    CONCLUSION = "conclusion"
    CRITICISM = "criticism"
    INSPIRATION = "inspiration"
    REFERENCE = "reference"
    DATA = "data"
    OTHER = "other"


@dataclass(frozen=True)
class Note:
    """Immutable note associated with a bibliography entry.

    Notes support markdown formatting, version tracking, and
    cross-references to other notes and entries.
    """

    # Required fields
    id: str
    entry_key: str
    content: str

    # Type and metadata
    type: NoteType = NoteType.GENERAL
    title: str | None = None

    # Organization
    tags: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)  # Other note/entry IDs

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Version tracking
    version: int = 1

    def __post_init__(self) -> None:
        """Validate note data after initialization."""
        if not self.id:
            raise NoteValidationError("id", "Note ID cannot be empty")

        if not self.entry_key:
            raise NoteValidationError("entry_key", "Entry key cannot be empty")

        if not isinstance(self.type, NoteType):
            try:
                # Try to convert string to NoteType
                object.__setattr__(self, "type", NoteType(self.type))
            except (ValueError, KeyError):
                raise NoteValidationError(
                    "type",
                    f"Invalid note type: {self.type}",
                )

        # Ensure lists are immutable
        object.__setattr__(self, "tags", tuple(self.tags))
        object.__setattr__(self, "references", tuple(self.references))

    @property
    def word_count(self) -> int:
        """Calculate word count of content."""
        return len(self.content.split())

    @property
    def char_count(self) -> int:
        """Calculate character count of content."""
        return len(self.content)

    @property
    def content_hash(self) -> str:
        """Generate hash of content for change detection."""
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]

    def to_markdown(self) -> str:
        """Export note as formatted markdown."""
        lines = []

        # Title
        if self.title:
            lines.append(f"# {self.title}")
        else:
            lines.append(f"# Note: {self.type.value.title()}")

        lines.append("")

        # Metadata
        lines.append(f"**Entry**: {self.entry_key}")
        lines.append(f"**Type**: {self.type.value}")
        lines.append(f"**Created**: {self.created_at.isoformat()}")

        if self.updated_at != self.created_at:
            lines.append(f"**Updated**: {self.updated_at.isoformat()}")

        lines.append(f"**Version**: {self.version}")

        if self.tags:
            lines.append(f"**Tags**: {', '.join(self.tags)}")

        if self.references:
            lines.append(f"**References**: {', '.join(self.references)}")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Content
        lines.append(self.content)

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert note to dictionary."""
        return {
            "id": self.id,
            "entry_key": self.entry_key,
            "content": self.content,
            "type": self.type.value,
            "title": self.title,
            "tags": list(self.tags),
            "references": list(self.references),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
        }

    def update(self, **changes: Any) -> Note:
        """Create updated version of note with validation.

        Args:
            **changes: Fields to update

        Returns:
            New note instance with updates and incremented version
        """
        # Filter out None values and invalid fields
        valid_fields = {
            "content",
            "type",
            "title",
            "tags",
            "references",
        }

        valid_changes = {
            k: v for k, v in changes.items() if k in valid_fields and v is not None
        }

        # Always update metadata
        valid_changes["updated_at"] = datetime.now()
        valid_changes["version"] = self.version + 1

        # Create new instance with changes
        return replace(self, **valid_changes)


@dataclass(frozen=True)
class Quote:
    """Immutable quote or highlight from a bibliography entry."""

    # Required fields
    id: str
    entry_key: str
    text: str

    # Location
    page: int | None = None
    section: str | None = None
    paragraph: int | None = None
    context: str | None = None  # Surrounding text

    # Categorization
    category: QuoteCategory = QuoteCategory.OTHER
    importance: int = 3  # 1-5 scale

    # Metadata
    tags: list[str] = field(default_factory=list)
    note: str | None = None  # Additional commentary

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    highlighted_at: datetime | None = None  # When highlighted in source

    def __post_init__(self) -> None:
        """Validate quote data after initialization."""
        if not self.id:
            raise QuoteValidationError("id", "Quote ID cannot be empty")

        if not self.entry_key:
            raise QuoteValidationError("entry_key", "Entry key cannot be empty")

        if not self.text:
            raise QuoteValidationError("text", "Quote text cannot be empty")

        if not isinstance(self.category, QuoteCategory):
            try:
                object.__setattr__(self, "category", QuoteCategory(self.category))
            except (ValueError, KeyError):
                raise QuoteValidationError(
                    "category",
                    f"Invalid quote category: {self.category}",
                )

        if not 1 <= self.importance <= 5:
            raise QuoteValidationError(
                "importance",
                f"Importance must be between 1 and 5, got {self.importance}",
            )

        # Ensure tags are immutable
        object.__setattr__(self, "tags", tuple(self.tags))

    @property
    def citation_text(self) -> str:
        """Generate citation text for the quote."""
        if self.page:
            return f"(p. {self.page})"
        elif self.section:
            return f"({self.section})"
        else:
            return ""

    def to_markdown(self) -> str:
        """Export quote as markdown."""
        lines = []

        # Quote block
        lines.append(f"> {self.text}")

        # Citation
        if self.citation_text:
            lines.append(">")
            lines.append(f"> — {self.entry_key} {self.citation_text}")

        # Context
        if self.context:
            lines.append("")
            lines.append(f"**Context**: {self.context}")

        # Note
        if self.note:
            lines.append("")
            lines.append(f"**Note**: {self.note}")

        # Tags
        if self.tags:
            lines.append("")
            lines.append(f"**Tags**: #{' #'.join(self.tags)}")

        return "\n".join(lines)

    def to_latex(self) -> str:
        """Export quote as LaTeX."""
        lines = []

        lines.append("\\begin{quote}")
        lines.append(self.text)

        if self.citation_text:
            lines.append(f"\\hfill --- \\cite{{{self.entry_key}}} {self.citation_text}")

        lines.append("\\end{quote}")

        if self.note:
            lines.append(f"\\textit{{{self.note}}}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert quote to dictionary."""
        return {
            "id": self.id,
            "entry_key": self.entry_key,
            "text": self.text,
            "page": self.page,
            "section": self.section,
            "paragraph": self.paragraph,
            "context": self.context,
            "category": self.category.value,
            "importance": self.importance,
            "tags": list(self.tags),
            "note": self.note,
            "created_at": self.created_at.isoformat(),
            "highlighted_at": self.highlighted_at.isoformat()
            if self.highlighted_at
            else None,
        }


@dataclass(frozen=True)
class ReadingProgress:
    """Track reading progress and metrics for a bibliography entry."""

    # Required
    entry_key: str

    # Status
    status: ReadingStatus = ReadingStatus.UNREAD
    priority: Priority = Priority.MEDIUM

    # Page tracking
    current_page: int = 0
    total_pages: int | None = None

    # Section tracking
    sections_read: int = 0
    sections_total: int | None = None

    # Time tracking
    reading_time_minutes: int = 0
    session_count: int = 0

    # Timestamps
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_read_at: datetime | None = None

    # Quality metrics (1-5 scale)
    importance: int = 3
    difficulty: int = 3
    enjoyment: int = 3
    comprehension: int = 3

    def __post_init__(self) -> None:
        """Validate progress data after initialization."""
        if not self.entry_key:
            raise NoteValidationError("entry_key", "Entry key cannot be empty")

        if not isinstance(self.status, ReadingStatus):
            try:
                object.__setattr__(self, "status", ReadingStatus(self.status))
            except (ValueError, KeyError):
                raise NoteValidationError(
                    "status",
                    f"Invalid reading status: {self.status}",
                )

        if not isinstance(self.priority, Priority):
            try:
                object.__setattr__(self, "priority", Priority(self.priority))
            except (ValueError, KeyError):
                raise NoteValidationError(
                    "priority",
                    f"Invalid priority: {self.priority}",
                )

    @property
    def progress_percentage(self) -> float:
        """Calculate reading progress as percentage."""
        if self.total_pages and self.total_pages > 0:
            return min(100.0, (self.current_page / self.total_pages) * 100)
        elif self.sections_total and self.sections_total > 0:
            return min(100.0, (self.sections_read / self.sections_total) * 100)
        else:
            # Map status to approximate percentage
            status_map = {
                ReadingStatus.UNREAD: 0.0,
                ReadingStatus.READING: 50.0,
                ReadingStatus.PARTIALLY_READ: 50.0,
                ReadingStatus.SKIMMED: 75.0,
                ReadingStatus.READ: 100.0,
                ReadingStatus.TO_REREAD: 100.0,
            }
            return status_map.get(self.status, 0.0)

    @property
    def is_complete(self) -> bool:
        """Check if reading is complete."""
        return self.status in {ReadingStatus.READ, ReadingStatus.SKIMMED}

    @property
    def average_pace(self) -> float:
        """Calculate average reading pace (pages per minute)."""
        if self.reading_time_minutes > 0 and self.current_page > 0:
            return self.current_page / self.reading_time_minutes
        return 0.0

    def update_progress(
        self,
        page: int | None = None,
        section: int | None = None,
        time_minutes: int = 0,
    ) -> ReadingProgress:
        """Update reading progress with new data.

        Args:
            page: Current page number
            section: Current section number
            time_minutes: Additional reading time

        Returns:
            New ReadingProgress instance with updates
        """
        updates = {
            "last_read_at": datetime.now(),
            "reading_time_minutes": self.reading_time_minutes + time_minutes,
            "session_count": self.session_count + 1
            if time_minutes > 0
            else self.session_count,
        }

        if page is not None:
            updates["current_page"] = page

        if section is not None:
            updates["sections_read"] = section

        # Update status based on progress
        if self.status == ReadingStatus.UNREAD:
            updates["status"] = ReadingStatus.READING
            updates["started_at"] = datetime.now()

        # Check if complete
        if (self.total_pages and page and page >= self.total_pages) or (
            self.sections_total and section and section >= self.sections_total
        ):
            updates["status"] = ReadingStatus.READ
            updates["finished_at"] = datetime.now()

        return replace(self, **updates)

    def to_dict(self) -> dict[str, Any]:
        """Convert progress to dictionary."""
        return {
            "entry_key": self.entry_key,
            "status": self.status.value,
            "priority": self.priority.value,
            "current_page": self.current_page,
            "total_pages": self.total_pages,
            "sections_read": self.sections_read,
            "sections_total": self.sections_total,
            "reading_time_minutes": self.reading_time_minutes,
            "session_count": self.session_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "last_read_at": self.last_read_at.isoformat()
            if self.last_read_at
            else None,
            "importance": self.importance,
            "difficulty": self.difficulty,
            "enjoyment": self.enjoyment,
            "comprehension": self.comprehension,
        }


@dataclass(frozen=True)
class NoteVersion:
    """Immutable version of a note for history tracking."""

    note_id: str
    version: int
    content: str
    content_hash: str
    created_at: datetime

    # Change metadata
    change_summary: str | None = None
    changed_by: str | None = None  # User/system identifier

    @property
    def word_count(self) -> int:
        """Get word count of version content."""
        return len(self.content.split())

    def diff_from(self, other: NoteVersion) -> str:
        """Generate unified diff from another version.

        Args:
            other: Version to compare with

        Returns:
            Unified diff string
        """
        lines1 = other.content.splitlines()
        lines2 = self.content.splitlines()

        diff = unified_diff(
            lines1,
            lines2,
            fromfile=f"Version {other.version}",
            tofile=f"Version {self.version}",
            lineterm="",
        )

        return "\n".join(diff)

    def to_dict(self) -> dict[str, Any]:
        """Convert version to dictionary."""
        return {
            "note_id": self.note_id,
            "version": self.version,
            "content": self.content,
            "content_hash": self.content_hash,
            "created_at": self.created_at.isoformat(),
            "change_summary": self.change_summary,
            "changed_by": self.changed_by,
        }
