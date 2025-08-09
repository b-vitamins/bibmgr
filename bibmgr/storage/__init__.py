"""Bibliography data storage and management layer.

Provides unified storage interface with multiple backend implementations:

- **Multiple backends**: FileSystem, SQLite, Memory with unified interface
- **Repository pattern**: Clean data access abstraction with validation
- **Full-text search**: Whoosh integration with relevance scoring
- **Event system**: Real-time notifications for data changes
- **Import/Export**: BibTeX, RIS, JSON format support
- **Metadata**: Sidecar files for notes, tags, ratings
- **Migrations**: Schema evolution and backup management
- **Query language**: Composable filtering with field-specific searches

Thread-safe with ACID transaction support where available.
"""

# Backend implementations
from bibmgr.storage.backends.base import BaseBackend, CachedBackend
from bibmgr.storage.backends.filesystem import FileSystemBackend
from bibmgr.storage.backends.memory import MemoryBackend
from bibmgr.storage.backends.sqlite import SQLiteBackend

# Event-aware repositories
from bibmgr.storage.eventrepository import (
    EventAwareCollectionRepository,
    EventAwareEntryRepository,
    EventAwareRepositoryManager,
)

# Event system
from bibmgr.storage.events import Event, EventBus, EventPublisher, EventType

# Import/Export
from bibmgr.storage.importers.bibtex import BibtexImporter
from bibmgr.storage.importers.json import JsonImporter
from bibmgr.storage.importers.ris import RisImporter

# Indexing
from bibmgr.storage.indexing import (
    IndexBackend,
    IndexManager,
    SearchResult,
    SimpleIndexBackend,
    WhooshIndexBackend,
)

# Metadata management
from bibmgr.storage.metadata import EntryMetadata, MetadataStore, Note

# Migrations
from bibmgr.storage.migrations import BackupManager, MigrationManager, MigrationStats

# Query language
from bibmgr.storage.query import (
    Condition,
    Operator,
    Query,
    recent_entries,
    search_entries,
    unread_entries,
)
from bibmgr.storage.query import QueryBuilder as AdvancedQueryBuilder

# Repository pattern
from bibmgr.storage.repository import (
    CollectionRepository,
    EntryRepository,
    QueryBuilder,
    Repository,
    RepositoryManager,
    StorageBackend,
)

__all__ = [
    # Backends
    "BaseBackend",
    "CachedBackend",
    "FileSystemBackend",
    "MemoryBackend",
    "SQLiteBackend",
    # Repository
    "StorageBackend",
    "QueryBuilder",
    "Repository",
    "EntryRepository",
    "CollectionRepository",
    "RepositoryManager",
    # Event-aware
    "EventAwareEntryRepository",
    "EventAwareCollectionRepository",
    "EventAwareRepositoryManager",
    # Events
    "EventType",
    "Event",
    "EventBus",
    "EventPublisher",
    # Metadata
    "Note",
    "EntryMetadata",
    "MetadataStore",
    # Query
    "Operator",
    "Condition",
    "Query",
    "AdvancedQueryBuilder",
    "search_entries",
    "recent_entries",
    "unread_entries",
    # Import/Export
    "BibtexImporter",
    "JsonImporter",
    "RisImporter",
    # Indexing
    "SearchResult",
    "IndexBackend",
    "SimpleIndexBackend",
    "WhooshIndexBackend",
    "IndexManager",
    # Migrations
    "MigrationStats",
    "MigrationManager",
    "BackupManager",
]
