"""Notes and annotations module for bibliography management.

This module provides comprehensive note-taking, annotation, and reading
progress tracking functionality with version history and concurrent access
support.
"""

from bibmgr.notes.exceptions import (
    NoteError,
    NoteNotFoundError,
    NoteValidationError,
    QuoteError,
    QuoteNotFoundError,
    StorageError,
    TemplateError,
    TemplateNotFoundError,
    VersionError,
)
from bibmgr.notes.manager import NoteManager
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

__all__ = [
    # Models
    "Note",
    "NoteType",
    "NoteVersion",
    "Quote",
    "QuoteCategory",
    "ReadingProgress",
    "ReadingStatus",
    "Priority",
    # Storage
    "NoteStorage",
    # Manager
    "NoteManager",
    # Templates
    "NoteTemplate",
    "TemplateManager",
    # Exceptions
    "NoteError",
    "NoteNotFoundError",
    "NoteValidationError",
    "QuoteError",
    "QuoteNotFoundError",
    "StorageError",
    "TemplateError",
    "TemplateNotFoundError",
    "VersionError",
]
