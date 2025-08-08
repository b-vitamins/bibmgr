"""Validation implementations for bibliography entries.

Modular validators that can be composed into validation pipelines.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Protocol
from urllib.parse import urlparse

from bibmgr.core.models import Entry, EntryType, ValidationError, REQUIRED_FIELDS


class EntryValidator(Protocol):
    """Protocol for entry validators."""

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Validate an entry and return errors/warnings."""
        ...


class RequiredFieldsValidator:
    """Validates required fields based on entry type."""

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Check for required fields."""
        errors: list[ValidationError] = []
        required = REQUIRED_FIELDS.get(entry.type, set())

        for field in required:
            value = getattr(entry, field, None)
            if not value:
                # Special case: book/inbook need author OR editor
                if field == "author" and entry.editor:
                    continue

                errors.append(
                    ValidationError(
                        field=field,
                        message=f"Required field for {entry.type.value}",
                        severity="error",
                    )
                )

        # Special validations for either/or requirements
        if entry.type in {EntryType.BOOK, EntryType.INBOOK}:
            if not entry.author and not entry.editor:
                errors.append(
                    ValidationError(
                        field="author/editor",
                        message="Either author or editor required",
                        severity="error",
                    )
                )

        if entry.type == EntryType.INBOOK:
            if not entry.chapter and not entry.pages:
                errors.append(
                    ValidationError(
                        field="chapter/pages",
                        message="Either chapter or pages required",
                        severity="error",
                    )
                )

        return errors


class FieldFormatValidator:
    """Validates field formats."""

    # Patterns
    DOI_PATTERN = re.compile(r"^10\.\d{4,}/[-._;()\/:a-zA-Z0-9]+$")
    PAGE_RANGE_PATTERN = re.compile(r"^\d+--\d+$")

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Validate field formats."""
        errors: list[ValidationError] = []

        # DOI validation
        if entry.doi:
            doi = entry.doi.strip()
            if not self.DOI_PATTERN.match(doi):
                errors.append(
                    ValidationError(
                        field="doi", message="Invalid DOI format", severity="warning"
                    )
                )

        # ISBN validation
        if entry.isbn:
            isbn_validator = ISBNValidator()
            if not isbn_validator.is_valid_isbn(entry.isbn):
                errors.append(
                    ValidationError(
                        field="isbn",
                        message="Invalid ISBN format or checksum",
                        severity="warning",
                    )
                )

        # ISSN validation
        if entry.issn:
            issn_validator = ISSNValidator()
            if not issn_validator.is_valid_issn(entry.issn):
                errors.append(
                    ValidationError(
                        field="issn", message="Invalid ISSN format", severity="warning"
                    )
                )

        # URL validation
        if entry.url:
            try:
                result = urlparse(entry.url)
                if not all([result.scheme, result.netloc]):
                    raise ValueError("Invalid URL")
            except Exception:
                errors.append(
                    ValidationError(
                        field="url", message="Invalid URL format", severity="warning"
                    )
                )

        # Page range validation
        if entry.pages:
            pages = entry.pages.strip()
            # Single page is OK
            if pages.isdigit():
                pass
            # Check for single dash (should be double)
            elif "-" in pages and "--" not in pages:
                errors.append(
                    ValidationError(
                        field="pages",
                        message="Use -- for page ranges (e.g., '7--33')",
                        severity="warning",
                    )
                )
            # Check format if it has double dash
            elif "--" in pages and not self.PAGE_RANGE_PATTERN.match(pages):
                errors.append(
                    ValidationError(
                        field="pages",
                        message="Invalid page range format",
                        severity="warning",
                    )
                )

        # Year validation
        if entry.year:
            current_year = datetime.now().year
            if entry.year < 1450:  # Before printing press
                errors.append(
                    ValidationError(
                        field="year",
                        message=f"Year {entry.year} is before printing press",
                        severity="error",
                    )
                )
            elif entry.year > current_year + 2:
                errors.append(
                    ValidationError(
                        field="year",
                        message=f"Year {entry.year} is in the future",
                        severity="warning",
                    )
                )

        # Month validation
        if entry.month:
            valid_months = {
                "1",
                "2",
                "3",
                "4",
                "5",
                "6",
                "7",
                "8",
                "9",
                "10",
                "11",
                "12",
                "jan",
                "feb",
                "mar",
                "apr",
                "may",
                "jun",
                "jul",
                "aug",
                "sep",
                "oct",
                "nov",
                "dec",
                "january",
                "february",
                "march",
                "april",
                "may",
                "june",
                "july",
                "august",
                "september",
                "october",
                "november",
                "december",
            }
            if entry.month.lower() not in valid_months:
                errors.append(
                    ValidationError(
                        field="month",
                        message="Use month number (1-12) or abbreviation",
                        severity="warning",
                    )
                )

        return errors


class AuthorFormatValidator:
    """Validates author/editor name formats."""

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Validate author/editor fields."""
        errors: list[ValidationError] = []

        for field in ["author", "editor"]:
            value = getattr(entry, field, None)
            if not value:
                continue

            # Check for semicolon separator
            if ";" in value:
                errors.append(
                    ValidationError(
                        field=field,
                        message="Use ' and ' to separate authors, not semicolon",
                        severity="error",
                    )
                )
                continue

            # Parse authors
            authors = value.split(" and ")
            for i, author in enumerate(authors, 1):
                author = author.strip()

                # Check for empty author
                if not author:
                    errors.append(
                        ValidationError(
                            field=field, message=f"Empty author #{i}", severity="error"
                        )
                    )
                    continue

                # Check for et al.
                if "et al" in author.lower():
                    errors.append(
                        ValidationError(
                            field=field,
                            message="Use 'and others' instead of 'et al.'",
                            severity="warning",
                        )
                    )

                # Check for too many commas
                if author.count(",") > 2:
                    errors.append(
                        ValidationError(
                            field=field,
                            message=f"Too many commas in author #{i}: {author}",
                            severity="warning",
                        )
                    )

        return errors


class CrossReferenceValidator:
    """Validates cross-references between entries."""

    def __init__(self, all_keys: set[str] | None = None):
        """Initialize with set of all valid entry keys."""
        self.all_keys = all_keys or set()

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Validate cross-references."""
        errors: list[ValidationError] = []

        if entry.crossref:
            if not self.all_keys:
                # Can't validate without knowing all keys
                errors.append(
                    ValidationError(
                        field="crossref",
                        message="Cannot validate cross-reference (no entry list)",
                        severity="info",
                    )
                )
            elif entry.crossref not in self.all_keys:
                errors.append(
                    ValidationError(
                        field="crossref",
                        message=f"Cross-reference to unknown entry: {entry.crossref}",
                        severity="error",
                    )
                )
            elif entry.crossref == entry.key:
                errors.append(
                    ValidationError(
                        field="crossref",
                        message="Entry cannot cross-reference itself",
                        severity="error",
                    )
                )

        return errors

    def validate_circular(
        self, entry: Entry, all_entries: dict[str, Entry]
    ) -> list[ValidationError]:
        """Check for circular references."""
        errors: list[ValidationError] = []

        if not entry.crossref:
            return errors

        # Follow chain of cross-references
        visited = {entry.key}
        current = entry.crossref

        while current:
            if current in visited:
                errors.append(
                    ValidationError(
                        field="crossref",
                        message=f"Circular reference detected: {' -> '.join(visited)} -> {current}",
                        severity="error",
                    )
                )
                break

            visited.add(current)

            if current in all_entries:
                current = all_entries[current].crossref
            else:
                break

        return errors


class ISBNValidator:
    """Validates ISBN format and checksum."""

    def is_valid_isbn(self, isbn: str) -> bool:
        """Check if ISBN is valid (format and checksum)."""
        # Remove hyphens and spaces
        isbn = isbn.replace("-", "").replace(" ", "")

        if len(isbn) == 10:
            return self.is_valid_isbn10(isbn)
        elif len(isbn) == 13:
            return self.is_valid_isbn13(isbn)

        return False

    def is_valid_isbn10(self, isbn: str) -> bool:
        """Validate ISBN-10 checksum."""
        if len(isbn) != 10:
            return False

        # Check format (9 digits + 1 digit or X)
        if not (isbn[:9].isdigit() and (isbn[9].isdigit() or isbn[9] == "X")):
            return False

        # Calculate checksum
        total = 0
        for i in range(9):
            total += int(isbn[i]) * (10 - i)

        # Last digit
        if isbn[9] == "X":
            total += 10
        else:
            total += int(isbn[9])

        return total % 11 == 0

    def is_valid_isbn13(self, isbn: str) -> bool:
        """Validate ISBN-13 checksum."""
        if len(isbn) != 13:
            return False

        if not isbn.isdigit():
            return False

        # Must start with 978 or 979
        if not (isbn.startswith("978") or isbn.startswith("979")):
            return False

        # Calculate checksum
        total = 0
        for i in range(12):
            if i % 2 == 0:
                total += int(isbn[i])
            else:
                total += int(isbn[i]) * 3

        check_digit = (10 - (total % 10)) % 10
        return int(isbn[12]) == check_digit


class ISSNValidator:
    """Validates ISSN format."""

    def is_valid_issn(self, issn: str) -> bool:
        """Check if ISSN is valid."""
        # Basic format check
        if len(issn) != 9:
            return False

        if issn[4] != "-":
            return False

        # Check digits
        part1 = issn[:4]
        part2 = issn[5:]

        if not (part1.isdigit() and part2.isdigit()):
            return False

        # Could add checksum validation here
        return True


class CompositeValidator:
    """Combines multiple validators."""

    def __init__(self, validators: list[EntryValidator]):
        """Initialize with list of validators."""
        self.validators = validators

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Run all validators and combine results."""
        all_errors: list[ValidationError] = []

        for validator in self.validators:
            errors = validator.validate(entry)
            all_errors.extend(errors)

        # Deduplicate while preserving order
        seen = set()
        unique_errors = []
        for error in all_errors:
            key = (error.field, error.message)
            if key not in seen:
                seen.add(key)
                unique_errors.append(error)

        return unique_errors


def create_default_validator(all_keys: set[str] | None = None) -> EntryValidator:
    """Create validator with all standard checks."""
    return CompositeValidator(
        [
            RequiredFieldsValidator(),
            FieldFormatValidator(),
            AuthorFormatValidator(),
            CrossReferenceValidator(all_keys),
        ]
    )
