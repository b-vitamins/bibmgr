"""Commands for quality check operations."""

from dataclasses import dataclass

from ..core.models import Entry


@dataclass
class ValidateEntryCommand:
    """Command to validate a single entry."""

    entry: Entry


@dataclass
class ValidateBatchCommand:
    """Command to validate multiple entries."""

    entries: list[Entry]
    stop_on_error: bool = False


@dataclass
class CheckConsistencyCommand:
    """Command to check consistency across entries."""

    entries: list[Entry]
    check_duplicates: bool = True
    check_crossrefs: bool = True


@dataclass
class GenerateQualityReportCommand:
    """Command to generate a quality report."""

    entries: list[Entry]
    format: str = "json"  # json, markdown, html
    include_consistency: bool = True
    include_suggestions: bool = True
