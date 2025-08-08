"""Storage layer for bibliography management.

Provides:
- BibTeX parsing with format preservation
- Atomic storage operations with transactions
- Metadata and note management
- Concurrent access support
- Data integrity and validation
"""

from bibmgr.storage.backend import (
    FileSystemStorage,
    StorageError,
    TransactionError,
    IntegrityError,
    Transaction,
)
from bibmgr.storage.parser import (
    BibtexParser,
    ParseError,
    FormatMetadata,
)
from bibmgr.storage.sidecar import (
    MetadataSidecar,
    EntryMetadata,
    Note,
    SidecarError,
    ValidationError,
)
from bibmgr.storage.system import StorageSystem

__all__ = [
    # System
    "StorageSystem",
    # Backend
    "FileSystemStorage",
    "Transaction",
    # Parser
    "BibtexParser",
    "ParseError",
    "FormatMetadata",
    # Sidecar
    "MetadataSidecar",
    "EntryMetadata",
    "Note",
    # Errors
    "StorageError",
    "TransactionError",
    "IntegrityError",
    "SidecarError",
    "ValidationError",
]
