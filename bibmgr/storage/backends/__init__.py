"""Pluggable storage backends.

Provides unified interface for different storage mechanisms:

- **FileSystemBackend**: JSON files with atomic writes
- **SQLiteBackend**: Embedded database with full-text search
- **MemoryBackend**: In-memory storage for testing
- **CachedBackend**: LRU cache wrapper for performance

All backends support CRUD operations and optional transactions.
"""

from .base import BaseBackend, CachedBackend
from .filesystem import FileSystemBackend
from .memory import MemoryBackend
from .sqlite import SQLiteBackend

__all__ = [
    "BaseBackend",
    "CachedBackend",
    "FileSystemBackend",
    "MemoryBackend",
    "SQLiteBackend",
]
