"""BibTeX import system with validation and conflict resolution."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol

import msgspec

from ..core.models import Entry, EntryType
from ..storage.parser import BibtexParser, ParseError
from .crud import EntryOperations
from .duplicates import DuplicateDetector, EntryMerger, MergeStrategy

logger = logging.getLogger(__name__)


class ConflictStrategy(str, Enum):
    """Strategy for handling conflicts during import."""

    SKIP = "skip"
    REPLACE = "replace"
    RENAME = "rename"
    MERGE = "merge"
    ASK = "ask"


class ImportStage(str, Enum):
    """Stages of the import pipeline."""

    PARSING = "parsing"
    PROCESSING = "processing"
    VALIDATION = "validation"
    DUPLICATE_CHECK = "duplicate_check"
    CONFLICT_RESOLUTION = "conflict_resolution"
    WRITING = "writing"
    COMPLETE = "complete"


@dataclass
class ImportError:
    """Represents an import error."""

    key: str | None
    stage: ImportStage
    message: str
    details: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    """Result of an import operation."""

    total_entries: int = 0
    imported: int = 0
    skipped: int = 0
    failed: int = 0
    replaced: int = 0
    merged: int = 0

    parse_errors: list[ParseError] = field(default_factory=list)
    error_details: dict[str, list[str]] = field(default_factory=dict)
    skip_reasons: dict[str, str] = field(default_factory=dict)

    imported_keys: list[str] = field(default_factory=list)
    skipped_keys: list[str] = field(default_factory=list)
    failed_keys: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if import was fully successful."""
        return self.failed == 0 and self.total_entries > 0

    @property
    def partial_success(self) -> bool:
        """Check if some entries were imported."""
        return self.imported > 0 or self.replaced > 0 or self.merged > 0

    def add_imported(self, key: str) -> None:
        """Mark entry as imported."""
        self.imported += 1
        self.imported_keys.append(key)

    def add_skipped(self, key: str, reason: str = "") -> None:
        """Mark entry as skipped."""
        self.skipped += 1
        self.skipped_keys.append(key)
        if reason:
            self.skip_reasons[key] = reason

    def add_failed(self, key: str, errors: list[str]) -> None:
        """Mark entry as failed."""
        self.failed += 1
        self.failed_keys.append(key)
        self.error_details[key] = errors

    def add_replaced(self, key: str) -> None:
        """Mark entry as replaced."""
        self.replaced += 1
        self.imported_keys.append(key)

    def add_merged(self, key: str) -> None:
        """Mark entry as merged."""
        self.merged += 1
        self.imported_keys.append(key)

    def get_summary(self) -> str:
        """Get summary of import results."""
        lines = [
            f"Total entries: {self.total_entries}",
            f"Imported: {self.imported}",
        ]

        if self.replaced:
            lines.append(f"Replaced: {self.replaced}")
        if self.merged:
            lines.append(f"Merged: {self.merged}")
        if self.skipped:
            lines.append(f"Skipped: {self.skipped}")
        if self.failed:
            lines.append(f"Failed: {self.failed}")

        if self.parse_errors:
            lines.append(f"Parse errors: {len(self.parse_errors)}")

        if self.skip_reasons:
            lines.append("\nSkip reasons:")
            for key, reason in list(self.skip_reasons.items())[:5]:
                lines.append(f"  {key}: {reason}")
            if len(self.skip_reasons) > 5:
                lines.append(f"  ... and {len(self.skip_reasons) - 5} more")

        return "\n".join(lines)


@dataclass
class ImportOptions:
    """Options for import operation."""

    validate: bool = True
    check_duplicates: bool = True
    conflict_strategy: ConflictStrategy = ConflictStrategy.ASK
    dry_run: bool = False
    force: bool = False
    stop_on_error: bool = True
    progress_reporter: ProgressReporter | None = None


class ProgressReporter(Protocol):
    """Protocol for progress reporting."""

    def report(
        self,
        stage: ImportStage | str,
        current: int,
        total: int,
        message: str | None = None,
    ) -> None:
        """Report import progress."""
        ...


class EntryProcessor(Protocol):
    """Protocol for custom entry processing."""

    def process(self, entry: Entry) -> Entry:
        """Process an entry before import."""
        ...


class ImportValidator(Protocol):
    """Protocol for custom import validation."""

    def validate(self, entry: Entry) -> list[str]:
        """Validate an entry for import."""
        ...


class BibTeXImporter:
    """Imports BibTeX entries with validation and conflict resolution."""

    def __init__(
        self,
        operations: EntryOperations,
        duplicate_detector: DuplicateDetector | None = None,
        entry_processor: EntryProcessor | None = None,
        import_validator: ImportValidator | None = None,
    ):
        """Initialize importer.

        Args:
            operations: Entry operations for CRUD
            duplicate_detector: Duplicate detector
            entry_processor: Custom entry processor
            import_validator: Custom import validator
        """
        self.operations = operations
        self.duplicate_detector = duplicate_detector
        self.entry_processor = entry_processor
        self.import_validator = import_validator
        self.parser = BibtexParser()
        self.merger = EntryMerger()

        # Create default validator if operations has one
        if (
            not self.import_validator
            and hasattr(operations, "validator")
            and operations.validator
        ):
            # Use the operations validator as import validator
            class DefaultImportValidator:
                def __init__(self, validator):
                    self.validator = validator

                def validate(self, entry):
                    return self.validator.validate(entry)

            self.import_validator = DefaultImportValidator(operations.validator)

    def import_file(
        self,
        path: Path,
        options: ImportOptions | None = None,
    ) -> ImportResult:
        """Import entries from a BibTeX file.

        Args:
            path: Path to BibTeX file
            options: Import options

        Returns:
            Import result with statistics and errors
        """
        options = options or ImportOptions()
        result = ImportResult()

        # Enable dry-run in operations if needed
        original_dry_run = self.operations.dry_run
        if options.dry_run:
            self.operations.dry_run = True

        try:
            # Stage 1: Parse file
            if options.progress_reporter:
                options.progress_reporter.report(
                    ImportStage.PARSING, 0, 1, f"Parsing {path}"
                )

            try:
                content = path.read_text(encoding="utf-8")
                entries = self.parser.parse(content)
                result.total_entries = len(entries)

                # Check for parse errors
                if hasattr(self.parser, "errors") and self.parser.errors:
                    for error in self.parser.errors:
                        result.parse_errors.append(error)
            except FileNotFoundError:
                result.parse_errors.append(
                    ParseError(
                        message=f"File not found: {path}",
                        line=0,
                        column=0,
                        context="",
                    )
                )
                return result
            except Exception as e:
                result.parse_errors.append(
                    ParseError(
                        message=str(e),
                        line=0,
                        column=0,
                        context="",
                    )
                )
                return result

            if not entries:
                return result

            if options.progress_reporter:
                options.progress_reporter.report(
                    ImportStage.PARSING, 1, 1, f"Parsed {len(entries)} entries"
                )

            # Stage 2: Process each entry
            for i, entry in enumerate(entries):
                if options.progress_reporter:
                    options.progress_reporter.report(
                        ImportStage.PROCESSING,
                        i + 1,
                        len(entries),
                        f"Processing {entry.key}",
                    )

                # Apply custom processing
                if self.entry_processor:
                    try:
                        entry = self.entry_processor.process(entry)
                    except Exception as e:
                        result.add_failed(entry.key, [f"Processing error: {e}"])
                        if options.stop_on_error:
                            break
                        continue

                # Custom validation
                if options.validate:
                    errors = []

                    # Basic validation for required fields
                    if entry.type == EntryType.ARTICLE:
                        if not entry.author:
                            errors.append("Missing required field: author")
                        if not entry.journal:
                            errors.append("Missing required field: journal")
                    elif entry.type == EntryType.BOOK:
                        if not entry.author and not entry.editor:
                            errors.append("Missing required field: author or editor")
                        if not entry.publisher:
                            errors.append("Missing required field: publisher")

                    # Check year is valid
                    if entry.year:
                        try:
                            year_val = int(entry.year)
                            if year_val < 1000 or year_val > 3000:
                                errors.append(f"Invalid year: {entry.year}")
                        except (ValueError, TypeError):
                            errors.append(f"Invalid year format: {entry.year}")

                    # Custom validator
                    if self.import_validator:
                        custom_errors = self.import_validator.validate(entry)
                        errors.extend(custom_errors)

                    if errors and not options.force:
                        result.add_failed(entry.key, errors)
                        if options.stop_on_error:
                            break
                        continue

                # Check for duplicates
                if options.check_duplicates and self.duplicate_detector:
                    # Get all existing entries from storage
                    existing_entries = []
                    # Get list of all keys from storage
                    for key in self.operations.storage.keys():
                        existing_entry = self.operations.read(key)
                        if existing_entry:
                            existing_entries.append(existing_entry)

                    duplicate = self.duplicate_detector.check_duplicate(
                        entry, existing_entries
                    )
                    if duplicate:
                        # Handle based on strategy
                        handled = self._handle_duplicate(
                            entry, duplicate, options.conflict_strategy, result
                        )
                        if not handled and options.stop_on_error:
                            break
                        continue

                # Check for key conflicts
                existing = self.operations.read(entry.key)
                if existing:
                    # Handle conflict
                    handled = self._handle_conflict(
                        entry, existing, options.conflict_strategy, result
                    )
                    if not handled and options.stop_on_error:
                        break
                    continue

                # Import entry
                op_result = self.operations.create(entry, force=options.force)

                if op_result.success:
                    result.add_imported(entry.key)
                else:
                    result.add_failed(entry.key, op_result.errors or ["Import failed"])
                    if options.stop_on_error:
                        break

            # Stage 3: Complete
            if options.progress_reporter:
                options.progress_reporter.report(
                    ImportStage.COMPLETE,
                    result.total_entries,
                    result.total_entries,
                    "Import complete",
                )

            return result

        finally:
            # Restore original dry-run setting
            self.operations.dry_run = original_dry_run

    def import_directory(
        self,
        directory: Path,
        pattern: str = "*.bib",
        recursive: bool = True,
        options: ImportOptions | None = None,
    ) -> dict[Path, ImportResult]:
        """Import all BibTeX files from a directory.

        Args:
            directory: Directory to import from
            pattern: Glob pattern for files
            recursive: Whether to search recursively
            options: Import options

        Returns:
            Dictionary mapping file paths to import results
        """
        results = {}

        if recursive:
            files = sorted(directory.rglob(pattern))
        else:
            files = sorted(directory.glob(pattern))

        for file_path in files:
            if file_path.is_file():
                logger.info(f"Importing {file_path}")
                result = self.import_file(file_path, options)
                results[file_path] = result

        return results

    def _handle_duplicate(
        self,
        new_entry: Entry,
        duplicate: Entry,
        strategy: ConflictStrategy,
        result: ImportResult,
    ) -> bool:
        """Handle duplicate entry.

        Args:
            new_entry: New entry being imported
            duplicate: Existing duplicate entry
            strategy: Conflict strategy
            result: Import result to update

        Returns:
            True if handled, False if error
        """
        if strategy == ConflictStrategy.SKIP:
            result.add_skipped(new_entry.key, f"Duplicate of {duplicate.key}")
            return True

        elif strategy == ConflictStrategy.REPLACE:
            # Replace the duplicate
            op_result = self.operations.replace(new_entry)
            if op_result.success:
                result.add_replaced(new_entry.key)
            else:
                result.add_failed(new_entry.key, op_result.errors or ["Replace failed"])
                return False
            return True

        elif strategy == ConflictStrategy.MERGE:
            # Merge entries
            try:
                merged = self.merger.merge(
                    [duplicate, new_entry],
                    strategy=MergeStrategy.UNION,
                )
                op_result = self.operations.replace(merged)
                if op_result.success:
                    result.add_merged(new_entry.key)
                else:
                    result.add_failed(
                        new_entry.key, op_result.errors or ["Merge failed"]
                    )
                    return False
            except Exception as e:
                result.add_failed(new_entry.key, [f"Merge error: {e}"])
                return False
            return True

        else:
            # Default to skip
            result.add_skipped(new_entry.key, "Duplicate detected")
            return True

    def _handle_conflict(
        self,
        new_entry: Entry,
        existing: Entry,
        strategy: ConflictStrategy,
        result: ImportResult,
    ) -> bool:
        """Handle key conflict.

        Args:
            new_entry: New entry being imported
            existing: Existing entry with same key
            strategy: Conflict strategy
            result: Import result to update

        Returns:
            True if handled, False if error
        """
        if strategy == ConflictStrategy.SKIP:
            result.add_skipped(new_entry.key, "Key already exists")
            return True

        elif strategy == ConflictStrategy.REPLACE:
            # Replace existing
            op_result = self.operations.replace(new_entry)
            if op_result.success:
                result.add_replaced(new_entry.key)
            else:
                result.add_failed(new_entry.key, op_result.errors or ["Replace failed"])
                return False
            return True

        elif strategy == ConflictStrategy.RENAME:
            # Generate new key
            renamed = self._rename_entry(new_entry)
            op_result = self.operations.create(renamed)
            if op_result.success:
                result.add_imported(renamed.key)
            else:
                result.add_failed(new_entry.key, op_result.errors or ["Rename failed"])
                return False
            return True

        elif strategy == ConflictStrategy.MERGE:
            # Merge with existing
            try:
                merged = self.merger.merge(
                    [existing, new_entry],
                    strategy=MergeStrategy.UNION,
                )
                op_result = self.operations.replace(merged)
                if op_result.success:
                    result.add_merged(new_entry.key)
                else:
                    result.add_failed(
                        new_entry.key, op_result.errors or ["Merge failed"]
                    )
                    return False
            except Exception as e:
                result.add_failed(new_entry.key, [f"Merge error: {e}"])
                return False
            return True

        else:
            # Default to skip
            result.add_skipped(new_entry.key, "Key conflict")
            return True

    def _rename_entry(self, entry: Entry) -> Entry:
        """Generate a new key for an entry to avoid conflicts.

        Args:
            entry: Entry to rename

        Returns:
            Entry with new unique key
        """
        base_key = entry.key
        counter = 1
        new_key = f"{base_key}_{counter}"

        while self.operations.read(new_key):
            counter += 1
            new_key = f"{base_key}_{counter}"

        # Create new entry with renamed key
        entry_dict = msgspec.structs.asdict(entry)
        entry_dict["key"] = new_key

        return msgspec.convert(entry_dict, Entry)
