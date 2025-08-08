"""Core domain models for bibliography entries.

High-performance, immutable models using msgspec with proper validation support.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import msgspec


class EntryType(str, Enum):
    """Standard BibTeX entry types."""

    ARTICLE = "article"
    BOOK = "book"
    BOOKLET = "booklet"
    CONFERENCE = "conference"
    INBOOK = "inbook"
    INCOLLECTION = "incollection"
    INPROCEEDINGS = "inproceedings"
    MANUAL = "manual"
    MASTERSTHESIS = "mastersthesis"
    MISC = "misc"
    PHDTHESIS = "phdthesis"
    PROCEEDINGS = "proceedings"
    TECHREPORT = "techreport"
    UNPUBLISHED = "unpublished"

    def __str__(self) -> str:
        """Return the string value."""
        return self.value


class ValidationError(msgspec.Struct, frozen=True):
    """Validation error with details."""

    field: str
    message: str
    severity: str = "error"  # error, warning, info

    def __str__(self) -> str:
        """Human-readable error message."""
        return f"[{self.severity.upper()}] {self.field}: {self.message}"


class Entry(msgspec.Struct, frozen=True, kw_only=True):
    """Bibliography entry with full BibTeX field support.

    Immutable structure with optional validation and cached properties.
    """

    # Core identifiers
    key: str
    type: EntryType

    # Standard BibTeX fields
    address: str | None = None
    annote: str | None = None
    author: str | None = None
    booktitle: str | None = None
    chapter: str | None = None
    crossref: str | None = None
    edition: str | None = None
    editor: str | None = None
    howpublished: str | None = None
    institution: str | None = None
    journal: str | None = None
    month: str | None = None
    note: str | None = None
    number: str | None = None
    organization: str | None = None
    pages: str | None = None
    publisher: str | None = None
    school: str | None = None
    series: str | None = None
    title: str | None = None
    volume: str | None = None
    year: int | None = None

    # Extended fields
    abstract: str | None = None
    doi: str | None = None
    eprint: str | None = None
    isbn: str | None = None
    issn: str | None = None
    keywords: str | None = None
    language: str | None = None
    location: str | None = None
    pmid: str | None = None
    url: str | None = None

    # File management
    file: str | None = None
    pdf_path: Path | None = None

    # No __post_init__ - Entry is a pure data structure
    # Validation should be done explicitly when needed

    def validate(self) -> list[ValidationError]:
        """Validate entry using default validator.

        Returns list of validation errors/warnings.
        """
        # Import here to avoid circular dependency
        from bibmgr.core.validators import create_default_validator

        validator = create_default_validator()
        return validator.validate(self)

    @property
    def authors_list(self) -> list[str]:
        """Parse author string into list of names."""
        if not self.author:
            return []

        # Split by ' and ' and clean up
        authors = [a.strip() for a in self.author.split(" and ")]
        return [a for a in authors if a]  # Filter empty

    @property
    def keywords_list(self) -> list[str]:
        """Parse keywords string into list."""
        if not self.keywords:
            return []

        # Split by comma or semicolon
        keywords = re.split(r"[,;]", self.keywords)
        return [k.strip() for k in keywords if k.strip()]

    @property
    def search_text(self) -> str:
        """Get combined text for search indexing."""
        parts = [
            self.title or "",
            self.author or "",
            self.editor or "",
            self.abstract or "",
            self.keywords or "",
            self.journal or "",
            self.booktitle or "",
            str(self.year) if self.year else "",
        ]
        return " ".join(filter(None, parts))

    def to_bibtex(self) -> str:
        """Convert entry to BibTeX format."""
        lines = [f"@{self.type.value}{{{self.key},"]

        def escape_bibtex(value: str) -> str:
            """Escape special characters for BibTeX."""
            # Double braces to escape them
            return value.replace("{", "{{").replace("}", "}}")

        # Add fields in standard order using braces
        if self.author:
            lines.append(f"    author = {{{escape_bibtex(self.author)}}},")
        if self.editor:
            lines.append(f"    editor = {{{escape_bibtex(self.editor)}}},")
        if self.title:
            lines.append(f"    title = {{{escape_bibtex(self.title)}}},")
        if self.journal:
            lines.append(f"    journal = {{{escape_bibtex(self.journal)}}},")
        if self.booktitle:
            lines.append(f"    booktitle = {{{escape_bibtex(self.booktitle)}}},")
        if self.publisher:
            lines.append(f"    publisher = {{{escape_bibtex(self.publisher)}}},")
        if self.year:
            lines.append(f"    year = {{{self.year}}},")
        if self.volume:
            lines.append(f"    volume = {{{escape_bibtex(self.volume)}}},")
        if self.number:
            lines.append(f"    number = {{{escape_bibtex(self.number)}}},")
        if self.pages:
            lines.append(f"    pages = {{{escape_bibtex(self.pages)}}},")
        if self.doi:
            lines.append(f"    doi = {{{escape_bibtex(self.doi)}}},")
        if self.url:
            lines.append(f"    url = {{{escape_bibtex(self.url)}}},")
        if self.isbn:
            lines.append(f"    isbn = {{{escape_bibtex(self.isbn)}}},")
        if self.note:
            lines.append(f"    note = {{{escape_bibtex(self.note)}}},")

        # Remove trailing comma from last field
        if lines[-1].endswith(","):
            lines[-1] = lines[-1][:-1]

        lines.append("}")
        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Entry:
        """Create entry from dictionary.

        Handles type conversion and field mapping.
        """
        # Convert type string to EntryType
        if "type" in data and isinstance(data["type"], str):
            data = data.copy()
            data["type"] = EntryType(data["type"].lower())

        # Convert pdf_path string to Path
        if "pdf_path" in data and isinstance(data["pdf_path"], str):
            data["pdf_path"] = Path(data["pdf_path"])

        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        """Convert entry to dictionary.

        Excludes None values and internal fields.
        """
        data = {}

        for field in self.__struct_fields__:
            if field == "validate":  # Skip internal field
                continue

            value = getattr(self, field)
            if value is not None:
                if field == "type":
                    data[field] = value.value
                elif field == "pdf_path":
                    data[field] = str(value)
                else:
                    data[field] = value

        return data


class Collection(msgspec.Struct, frozen=True, kw_only=True):
    """Collection of bibliography entries.

    Can be static (manual) or smart (query-based).
    """

    id: str
    name: str
    description: str | None = None
    parent_id: str | None = None

    # Smart collection
    query: str | None = None
    is_smart: bool = False

    # Timestamps
    created_at: datetime = msgspec.field(default_factory=datetime.now)
    updated_at: datetime = msgspec.field(default_factory=datetime.now)

    # Entry membership (static collections only)
    entry_keys: set[str] = msgspec.field(default_factory=set)

    def __post_init__(self) -> None:
        """Validate collection constraints."""
        if self.is_smart and self.entry_keys:
            raise ValueError("Smart collection cannot have manual entry keys")

        if self.is_smart and not self.query:
            raise ValueError("Smart collection must have a query")

    def add_entry(self, key: str) -> Collection:
        """Add entry to static collection (returns new instance)."""
        if self.is_smart:
            raise ValueError("Cannot add entries to smart collection")

        new_keys = self.entry_keys | {key}
        return self.__class__(
            **{**self.to_dict(), "entry_keys": new_keys, "updated_at": datetime.now()}
        )

    def remove_entry(self, key: str) -> Collection:
        """Remove entry from static collection (returns new instance)."""
        if self.is_smart:
            raise ValueError("Cannot remove entries from smart collection")

        new_keys = self.entry_keys - {key}
        return self.__class__(
            **{**self.to_dict(), "entry_keys": new_keys, "updated_at": datetime.now()}
        )

    def get_path(self, parent_map: dict[str, str] | None = None) -> str:
        """Get hierarchical path.

        Args:
            parent_map: Mapping of collection IDs to parent IDs

        Returns:
            Full path like "Research/ML/NLP"
        """
        if not parent_map or not self.parent_id:
            return self.name

        # Build path from parents
        path_parts = [self.name]
        current_id = self.parent_id

        while current_id:
            if current_id not in parent_map:
                break
            # Find parent collection name
            path_parts.insert(0, current_id)  # Simplified - would need full collection
            current_id = parent_map.get(current_id)

        return "/".join(path_parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parent_id": self.parent_id,
            "query": self.query,
            "is_smart": self.is_smart,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "entry_keys": self.entry_keys,
        }


class Tag(msgspec.Struct, frozen=True, kw_only=True):
    """Hierarchical tag for organizing entries."""

    path: str
    color: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate tag path."""
        if not self.path:
            raise ValueError("Tag path cannot be empty")

        if "//" in self.path:
            raise ValueError("Tag path cannot contain empty components")

        if self.path.startswith("/") or self.path.endswith("/"):
            raise ValueError("Tag path cannot start or end with /")

    @property
    def name(self) -> str:
        """Get tag name (last component)."""
        return self.path.split("/")[-1]

    @property
    def parent_path(self) -> str | None:
        """Get parent tag path."""
        parts = self.path.split("/")
        if len(parts) > 1:
            return "/".join(parts[:-1])
        return None

    @property
    def level(self) -> int:
        """Get nesting level (0 for root)."""
        return self.path.count("/")

    @property
    def path_components(self) -> list[str]:
        """Get path components."""
        return self.path.split("/")

    def is_ancestor_of(self, other: Tag) -> bool:
        """Check if this tag is ancestor of another."""
        return other.path.startswith(self.path + "/")

    def is_descendant_of(self, other: Tag) -> bool:
        """Check if this tag is descendant of another."""
        return self.path.startswith(other.path + "/")

    def is_sibling_of(self, other: Tag) -> bool:
        """Check if tags are siblings (same parent)."""
        return (
            self.parent_path == other.parent_path
            and self.path != other.path
            and self.parent_path is not None
        )


# Required fields configuration
REQUIRED_FIELDS: dict[EntryType, set[str]] = {
    EntryType.ARTICLE: {"author", "title", "journal", "year"},
    EntryType.BOOK: {"title", "publisher", "year"},  # + author OR editor
    EntryType.BOOKLET: {"title"},
    EntryType.CONFERENCE: {"author", "title", "booktitle", "year"},
    EntryType.INBOOK: {
        "title",
        "publisher",
        "year",
    },  # + author OR editor, chapter OR pages
    EntryType.INCOLLECTION: {"author", "title", "booktitle", "publisher", "year"},
    EntryType.INPROCEEDINGS: {"author", "title", "booktitle", "year"},
    EntryType.MANUAL: {"title"},
    EntryType.MASTERSTHESIS: {"author", "title", "school", "year"},
    EntryType.MISC: set(),  # No required fields
    EntryType.PHDTHESIS: {"author", "title", "school", "year"},
    EntryType.PROCEEDINGS: {"title", "year"},
    EntryType.TECHREPORT: {"author", "title", "institution", "year"},
    EntryType.UNPUBLISHED: {"author", "title", "note"},
}


def get_required_fields(entry_type: EntryType) -> set[str]:
    """Get required fields for an entry type.

    Note: Some types have alternatives (author/editor, chapter/pages).
    """
    return REQUIRED_FIELDS.get(entry_type, set()).copy()
