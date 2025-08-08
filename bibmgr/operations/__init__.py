"""Entry operations module."""

from .crud import (
    EntryOperations,
    OperationResult,
    OperationType,
    BulkOperationOptions,
    CascadeOptions,
)
from .duplicates import (
    DuplicateDetector,
    DuplicateMatch,
    MatchType,
    DuplicateIndex,
    EntryMerger,
    MergeStrategy,
    StringSimilarity,
    TitleNormalizer,
    AuthorNormalizer,
)
from .importer import (
    BibTeXImporter,
    ImportResult,
    ImportOptions,
    ConflictStrategy,
    ImportStage,
    ImportError,
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
