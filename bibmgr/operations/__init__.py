"""Entry operations module."""

from .crud import (
    BulkOperationOptions,
    CascadeOptions,
    EntryOperations,
    OperationResult,
    OperationType,
)
from .duplicates import (
    AuthorNormalizer,
    DuplicateDetector,
    DuplicateIndex,
    DuplicateMatch,
    EntryMerger,
    MatchType,
    MergeStrategy,
    StringSimilarity,
    TitleNormalizer,
)
from .importer import (
    BibTeXImporter,
    ConflictStrategy,
    ImportError,
    ImportOptions,
    ImportResult,
    ImportStage,
)

__all__ = [
    # CRUD
    "EntryOperations",
    "OperationResult",
    "OperationType",
    "BulkOperationOptions",
    "CascadeOptions",
    # Duplicates
    "DuplicateDetector",
    "DuplicateMatch",
    "MatchType",
    "DuplicateIndex",
    "EntryMerger",
    "MergeStrategy",
    "StringSimilarity",
    "TitleNormalizer",
    "AuthorNormalizer",
    # Importer
    "BibTeXImporter",
    "ImportResult",
    "ImportOptions",
    "ConflictStrategy",
    "ImportStage",
    "ImportError",
]
