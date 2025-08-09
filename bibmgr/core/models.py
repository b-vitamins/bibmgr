"""Core data models for bibliography entries.

This module defines the fundamental data structures for representing
bibliographic entries in accordance with BibTeX standards. The Entry
model supports all standard BibTeX fields as defined in TameTheBeast,
plus modern extensions for DOIs, URLs, and other digital identifiers.

Key components:
- Entry: Immutable bibliography entry with full BibTeX field support
- Collection: Hierarchical grouping of entries with smart filtering
- Tag: Lightweight categorization for entries
- ValidationError: Structured error reporting for entry validation
"""

import enum
import uuid
from datetime import datetime
from typing import Any

import msgspec

from .bibtex import BibtexEncoder
from .fields import EntryType

_entry_cache: dict[int, dict[str, Any]] = {}


class Entry(msgspec.Struct, frozen=True, kw_only=True):
    """Immutable bibliography entry conforming to BibTeX standards.

    This class represents a single bibliographic entry with support for
    all standard BibTeX fields. The design follows BibTeX conventions
    where field availability depends on entry type (see TameTheBeast
    sections 2.2-2.3 for field requirements by type).

    The entry is immutable (frozen) to ensure data integrity and enable
    safe caching of computed properties.
    """

    key: str
    type: EntryType
    address: str | None = None
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
    type_: str | None = None
    volume: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    isbn: str | None = None
    issn: str | None = None
    eprint: str | None = None
    archiveprefix: str | None = None
    primaryclass: str | None = None
    abstract: str | None = None
    keywords: tuple[str, ...] | None = None
    file: str | None = None

    annotation: str | None = None
    comment: str | None = None
    timestamp: datetime | None = None

    custom: dict[str, Any] | None = None
    added: datetime = msgspec.field(default_factory=datetime.now)
    modified: datetime = msgspec.field(default_factory=datetime.now)
    tags: tuple[str, ...] = msgspec.field(default_factory=tuple)

    def __post_init__(self):
        """Post-initialization hook for msgspec."""
        pass

    @property
    def authors(self) -> tuple[str, ...]:
        """Parse author field into individual names.

        BibTeX uses ' and ' as the delimiter between author names.
        This method handles escaped ampersands (\\&) which should not
        be treated as delimiters.

        Returns:
            Tuple of author names in the order they appear.
        """
        cache_key = hash((self.key, self.author))

        if cache_key in _entry_cache and "authors" in _entry_cache[cache_key]:
            return _entry_cache[cache_key]["authors"]

        if not self.author:
            result = ()
        else:
            import re

            temp = self.author.replace(r"\&", "\x00")
            names = re.split(r"\s+and\s+", temp)
            result = tuple(
                name.replace("\x00", "&").strip() for name in names if name.strip()
            )

        if cache_key not in _entry_cache:
            _entry_cache[cache_key] = {}
        _entry_cache[cache_key]["authors"] = result

        return result

    @property
    def editors(self) -> tuple[str, ...]:
        """Parse editor field into individual names.

        Uses the same parsing logic as authors, splitting on ' and '.

        Returns:
            Tuple of editor names in the order they appear.
        """
        cache_key = hash((self.key, self.editor))

        if cache_key in _entry_cache and "editors" in _entry_cache[cache_key]:
            return _entry_cache[cache_key]["editors"]

        if not self.editor:
            result = ()
        else:
            import re

            temp = self.editor.replace(r"\&", "\x00")
            names = re.split(r"\s+and\s+", temp)
            result = tuple(
                name.replace("\x00", "&").strip() for name in names if name.strip()
            )

        if cache_key not in _entry_cache:
            _entry_cache[cache_key] = {}
        _entry_cache[cache_key]["editors"] = result

        return result

    @property
    def search_text(self) -> str:
        """Generate searchable text representation of the entry.

        Combines all relevant text fields for full-text search.
        The result is cached to avoid repeated string concatenation.

        Returns:
            Lowercase concatenation of all searchable fields.
        """
        cache_key = hash(self.key)

        if cache_key in _entry_cache and "search_text" in _entry_cache[cache_key]:
            return _entry_cache[cache_key]["search_text"]

        parts = []

        text_fields = [
            self.key,
            self.title,
            self.author,
            self.editor,
            self.journal,
            self.booktitle,
            self.publisher,
            self.institution,
            self.school,
            self.organization,
            self.note,
            self.abstract,
            self.comment,
            self.annotation,
        ]

        for field in text_fields:
            if field:
                parts.append(str(field))

        if self.year:
            parts.append(str(self.year))

        if self.keywords:
            parts.extend(self.keywords)

        parts.extend(self.tags)
        parts.append(self.type.value)

        result = " ".join(parts).lower()

        if cache_key not in _entry_cache:
            _entry_cache[cache_key] = {}
        _entry_cache[cache_key]["search_text"] = result

        return result

    def validate(self) -> list["ValidationError"]:
        """Validate this entry using the validator registry."""
        from .validators import get_validator_registry

        registry = get_validator_registry()
        return registry.validate(self)

    def to_bibtex(self) -> str:
        """Convert to BibTeX format."""
        encoder = BibtexEncoder()
        return encoder.encode_entry(self)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values.

        Returns:
            Dictionary with only non-None fields.
        """
        data = msgspec.to_builtins(self)
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entry":
        """Create Entry from dictionary representation.

        Handles type conversion and ensures immutability of list fields.

        Args:
            data: Dictionary with entry fields.

        Returns:
            New Entry instance.
        """
        if "type" in data and not isinstance(data["type"], EntryType):
            data["type"] = EntryType(data["type"])

        if "keywords" in data and data["keywords"] is not None:
            data["keywords"] = (
                tuple(data["keywords"])
                if isinstance(data["keywords"], list)
                else data["keywords"]
            )
        if "tags" in data and data["tags"] is not None:
            data["tags"] = (
                tuple(data["tags"]) if isinstance(data["tags"], list) else data["tags"]
            )

        return msgspec.convert(data, cls)


class Collection(msgspec.Struct, frozen=True, kw_only=True):
    """Hierarchical grouping of bibliography entries.

    Collections can be either manual (containing specific entry keys)
    or smart (defined by a search query). They support nesting through
    parent_id to create a tree structure.
    """

    id: uuid.UUID = msgspec.field(default_factory=uuid.uuid4)
    name: str
    description: str | None = None
    parent_id: uuid.UUID | None = None

    entry_keys: tuple[str, ...] | None = None
    query: str | None = None

    color: str | None = None
    icon: str | None = None

    created: datetime = msgspec.field(default_factory=datetime.now)
    modified: datetime = msgspec.field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate collection configuration."""
        if self.entry_keys and self.query is not None:
            raise ValueError("Collection cannot have both entry_keys and query")

    @property
    def is_smart(self) -> bool:
        """Check if this is a smart (query-based) collection."""
        return self.query is not None

    def get_path(self, storage: Any) -> str:
        """Get hierarchical path using collection names."""
        if not self.parent_id:
            return self.name

        path_parts = [self.name]
        current = self

        while current.parent_id:
            parent = storage.get_collection(current.parent_id)
            if not parent:
                break
            path_parts.append(parent.name)
            current = parent

        return " > ".join(reversed(path_parts))

    def add_entry(self, key: str) -> "Collection":
        """Add an entry to this collection."""
        if self.is_smart:
            raise ValueError("Cannot add entries to smart collection")

        current_keys = self.entry_keys or ()
        if key not in current_keys:
            new_keys = current_keys + (key,)
        else:
            new_keys = current_keys

        return msgspec.structs.replace(
            self, entry_keys=new_keys, modified=datetime.now()
        )

    def remove_entry(self, key: str) -> "Collection":
        """Remove an entry from this collection."""
        if self.is_smart:
            raise ValueError("Cannot remove entries from smart collection")

        if self.entry_keys:
            new_keys = tuple(k for k in self.entry_keys if k != key)
        else:
            new_keys = ()
        return msgspec.structs.replace(
            self, entry_keys=new_keys, modified=datetime.now()
        )


class Tag(msgspec.Struct, frozen=True):
    """Lightweight tag for entry categorization."""

    name: str
    color: str | None = None

    def __str__(self) -> str:
        return self.name


class ValidationError(msgspec.Struct):
    """Structured validation error information.

    Used to report validation issues with different severity levels.
    """

    field: str | None
    message: str
    severity: str = "error"
    entry_key: str | None = None


class ErrorSeverity(enum.Enum):
    """Severity levels for validation errors."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
