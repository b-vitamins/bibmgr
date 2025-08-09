"""Bibliography import/export formats.

Handles multiple bibliography formats with validation and error recovery:

- **BibTeX**: Standard academic format with LaTeX escape handling
- **RIS**: Research Information Systems format
- **JSON**: Native format with metadata preservation

Supports batch operations, duplicate handling strategies, and detailed error reporting.
"""

from enum import Enum

from .bibtex import BibtexImporter
from .json import JsonImporter
from .ris import RisImporter


class ImportStrategy(Enum):
    """Strategy for handling duplicate entries during import."""

    SKIP_DUPLICATES = "skip"
    OVERWRITE = "overwrite"
    RENAME_DUPLICATES = "rename"
    MERGE_DUPLICATES = "merge"


__all__ = [
    "BibtexImporter",
    "JsonImporter",
    "RisImporter",
    "ImportStrategy",
]
