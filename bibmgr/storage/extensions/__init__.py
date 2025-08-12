"""Storage extensions for additional functionality."""

from .collections import CollectionExtension
from .notes import Note, NotesExtension, NoteType, Quote, ReadingProgress, ReadingStatus

__all__ = [
    "CollectionExtension",
    "NotesExtension",
    "Note",
    "NoteType",
    "Quote",
    "ReadingProgress",
    "ReadingStatus",
]
