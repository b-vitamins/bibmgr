"""Validation system for bibliography entries.

This module implements a comprehensive validation framework for BibTeX
entries, ensuring compliance with standard requirements as documented
in TameTheBeast. The validation system is extensible and includes checks
for required fields, field formats, and data consistency.

Key validators:
- EntryKeyValidator: Ensures valid BibTeX entry keys
- RequiredFieldValidator: Checks required fields by entry type
- FieldFormatValidator: Validates field content formats
- ConsistencyValidator: Cross-field consistency checks
- CrossRefValidator: Validates cross-reference integrity
"""

import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from .duplicates import DuplicateDetector
from .fields import EntryType, FieldRequirements
from .models import Entry, ValidationError


class Validator(ABC):
    """Base validator interface."""

    @abstractmethod
    def validate(self, entry: Entry) -> list[ValidationError]:
        """Validate an entry and return list of errors."""
        pass


class EntryKeyValidator(Validator):
    """Validate entry keys according to BibTeX rules.

    BibTeX keys must contain only alphanumeric characters, underscores,
    hyphens, and colons. Modern usage allows keys starting with digits
    to support DOI-based identifiers.
    """

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Validate entry key format.

        Args:
            entry: Entry to validate.

        Returns:
            List of validation errors found.
        """
        errors = []

        if not entry.key:
            errors.append(
                ValidationError(
                    field="key",
                    message="Entry key cannot be empty",
                    severity="error",
                    entry_key=entry.key,
                )
            )
            return errors

        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_\-:]*$", entry.key):
            errors.append(
                ValidationError(
                    field="key",
                    message=f"Entry key contains invalid characters: {entry.key}",
                    severity="error",
                    entry_key=entry.key,
                )
            )
            return errors

        if len(entry.key) > 250:
            errors.append(
                ValidationError(
                    field="key",
                    message=f"Entry key is too long ({len(entry.key)} chars > 250)",
                    severity="warning",
                    entry_key=entry.key,
                )
            )

        return errors


class RequiredFieldValidator(Validator):
    """Validate required fields for each entry type.

    Implements the standard BibTeX field requirements as defined in
    TameTheBeast sections 2.2-2.3. Some entry types have alternative
    field requirements (e.g., author OR editor for @book).
    """

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Check if all required fields are present.

        Args:
            entry: Entry to validate.

        Returns:
            List of validation errors for missing required fields.
        """
        errors = []

        requirements = FieldRequirements.get_requirements(entry.type)
        required_fields = requirements["required"]

        for field_spec in required_fields:
            if "|" in field_spec:
                alternatives = field_spec.split("|")
                if not any(getattr(entry, alt, None) for alt in alternatives):
                    errors.append(
                        ValidationError(
                            field=field_spec,
                            message=f"Entry requires one of: {field_spec}",
                            severity="error",
                            entry_key=entry.key,
                        )
                    )
            else:
                if not getattr(entry, field_spec, None):
                    errors.append(
                        ValidationError(
                            field=field_spec,
                            message=f"Required field '{field_spec}' is missing",
                            severity="error",
                            entry_key=entry.key,
                        )
                    )

        return errors


class FieldFormatValidator(Validator):
    """Validate field content formats.

    Checks common BibTeX fields for proper formatting according to
    standard conventions. This includes year ranges, month formats,
    and page numbering styles.
    """

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Validate formats of various fields.

        Args:
            entry: Entry to validate.

        Returns:
            List of format validation errors.
        """
        errors = []

        if entry.year is not None:
            errors.extend(self._validate_year(entry))

        if entry.month:
            errors.extend(self._validate_month(entry))

        if entry.pages:
            errors.extend(self._validate_pages(entry))

        return errors

    def _validate_year(self, entry: Entry) -> list[ValidationError]:
        """Validate year field format."""
        errors = []

        if isinstance(entry.year, str):
            special_values = {
                "in press",
                "forthcoming",
                "preprint",
                "submitted",
                "accepted",
                "to appear",
            }
            if entry.year.lower() not in special_values:
                errors.append(
                    ValidationError(
                        field="year",
                        message=f"Invalid year value: {entry.year}",
                        severity="warning",
                        entry_key=entry.key,
                    )
                )
        elif isinstance(entry.year, int):
            current_year = datetime.now().year

            if entry.year < 1000:
                errors.append(
                    ValidationError(
                        field="year",
                        message=f"Year seems too far in the past: {entry.year}",
                        severity="warning",
                        entry_key=entry.key,
                    )
                )
            elif entry.year > current_year + 5:
                errors.append(
                    ValidationError(
                        field="year",
                        message=f"Year seems too far in the future: {entry.year}",
                        severity="warning",
                        entry_key=entry.key,
                    )
                )

        return errors

    def _validate_month(self, entry: Entry) -> list[ValidationError]:
        """Validate month field format."""
        errors = []

        valid_months = {
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

        if entry.month and entry.month.lower() not in valid_months:
            errors.append(
                ValidationError(
                    field="month",
                    message=f"Invalid month format: {entry.month}",
                    severity="warning",
                    entry_key=entry.key,
                )
            )

        return errors

    def _validate_pages(self, entry: Entry) -> list[ValidationError]:
        """Validate pages field format."""
        errors = []

        if not entry.pages:
            return errors

        page_patterns = [
            r"^\d+$",
            r"^\d+--?\d+$",
            r"^[A-Z]\d+--?[A-Z]\d+$",
            r"^\d+(,\s*\d+)+$",
            r"^\d+--?\d+(,\s*\d+--?\d+)*$",
        ]

        if not any(re.match(pattern, entry.pages) for pattern in page_patterns):
            errors.append(
                ValidationError(
                    field="pages",
                    message=f"Invalid page format: {entry.pages}",
                    severity="warning",
                    entry_key=entry.key,
                )
            )
        elif "-" in entry.pages and "--" not in entry.pages:
            # Single dash instead of double dash
            errors.append(
                ValidationError(
                    field="pages",
                    message="Consider using double dash (--) for page ranges in BibTeX format",
                    severity="info",
                    entry_key=entry.key,
                )
            )

        return errors


class DOIValidator(Validator):
    """Validate Digital Object Identifier (DOI) format.

    DOIs follow the pattern 10.XXXX/YYYY where XXXX is the registrant
    code and YYYY is the item identifier.
    """

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Validate DOI format.

        Args:
            entry: Entry to validate.

        Returns:
            List of DOI validation errors.
        """
        errors = []

        if entry.doi:
            doi = entry.doi
            for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
                if doi.startswith(prefix):
                    doi = doi[len(prefix) :]

            if not re.match(r"^10\.\d{4,}/\S+$", doi):
                errors.append(
                    ValidationError(
                        field="doi",
                        message=f"Invalid DOI format: {entry.doi}",
                        severity="warning",
                        entry_key=entry.key,
                    )
                )

        return errors


class ISBNValidator(Validator):
    """Validate International Standard Book Number (ISBN).

    Supports both ISBN-10 and ISBN-13 formats with checksum validation.
    """

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Validate ISBN format and checksum.

        Args:
            entry: Entry to validate.

        Returns:
            List of ISBN validation errors.
        """
        errors = []

        if entry.isbn:
            isbn = entry.isbn.replace("-", "").replace(" ", "").upper()

            if len(isbn) == 10:
                if not self._validate_isbn10(isbn):
                    errors.append(
                        ValidationError(
                            field="isbn",
                            message=f"Invalid ISBN-10: {entry.isbn}",
                            severity="warning",
                            entry_key=entry.key,
                        )
                    )
            elif len(isbn) == 13:
                if not self._validate_isbn13(isbn):
                    errors.append(
                        ValidationError(
                            field="isbn",
                            message=f"Invalid ISBN-13: {entry.isbn}",
                            severity="warning",
                            entry_key=entry.key,
                        )
                    )
            else:
                errors.append(
                    ValidationError(
                        field="isbn",
                        message=f"ISBN must be 10 or 13 digits: {entry.isbn}",
                        severity="warning",
                        entry_key=entry.key,
                    )
                )

        return errors

    def _validate_isbn10(self, isbn: str) -> bool:
        """Validate ISBN-10 checksum using modulo 11."""
        if not re.match(r"^\d{9}[\dX]$", isbn):
            return False

        total = 0
        for i in range(9):
            total += int(isbn[i]) * (10 - i)

        check = isbn[9]
        if check == "X":
            total += 10
        else:
            total += int(check)

        return total % 11 == 0

    def _validate_isbn13(self, isbn: str) -> bool:
        """Validate ISBN-13 checksum using modulo 10."""
        if not re.match(r"^\d{13}$", isbn):
            return False

        total = 0
        for i in range(12):
            if i % 2 == 0:
                total += int(isbn[i])
            else:
                total += int(isbn[i]) * 3

        check = (10 - (total % 10)) % 10
        return int(isbn[12]) == check


class ISSNValidator(Validator):
    """Validate International Standard Serial Number (ISSN).

    ISSNs are 8-digit codes for serial publications with a modulo 11
    checksum in the last position.
    """

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Validate ISSN format and checksum.

        Args:
            entry: Entry to validate.

        Returns:
            List of ISSN validation errors.
        """
        errors = []

        if entry.issn:
            issn = entry.issn.replace("-", "").upper()

            if not re.match(r"^\d{7}[\dX]$", issn):
                errors.append(
                    ValidationError(
                        field="issn",
                        message=f"Invalid ISSN format: {entry.issn}",
                        severity="warning",
                        entry_key=entry.key,
                    )
                )
            elif not self._validate_checksum(issn):
                errors.append(
                    ValidationError(
                        field="issn",
                        message=f"Invalid ISSN checksum: {entry.issn}",
                        severity="warning",
                        entry_key=entry.key,
                    )
                )

        return errors

    def _validate_checksum(self, issn: str) -> bool:
        """Validate ISSN checksum using modulo 11."""
        total = 0
        for i in range(7):
            total += int(issn[i]) * (8 - i)

        remainder = total % 11
        if remainder == 0:
            check = "0"
        elif remainder == 1:
            check = "X"
        else:
            check = str(11 - remainder)

        return issn[7] == check


class URLValidator(Validator):
    """Validate URL format and structure."""

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Validate URL format.

        Args:
            entry: Entry to validate.

        Returns:
            List of URL validation errors.
        """
        errors = []

        if entry.url:
            try:
                result = urlparse(entry.url)

                if not result.scheme:
                    raise ValueError("Missing URL scheme")
                if result.scheme not in ["http", "https"]:
                    raise ValueError("URL must use http or https")
                if not result.netloc:
                    raise ValueError("Missing domain")

                hostname = result.netloc.split(":")[0]
                if (
                    "." not in hostname
                    and hostname != "localhost"
                    and not hostname.replace(".", "").isdigit()
                ):
                    raise ValueError("Invalid domain format")

            except Exception:
                errors.append(
                    ValidationError(
                        field="url",
                        message=f"Invalid URL format: {entry.url}",
                        severity="warning",
                        entry_key=entry.key,
                    )
                )
            else:
                # Valid URL, check for HTTP vs HTTPS
                if result.scheme == "http":
                    errors.append(
                        ValidationError(
                            field="url",
                            message="Consider using HTTPS instead of HTTP for better security",
                            severity="warning",
                            entry_key=entry.key,
                        )
                    )

        return errors


class AuthorFormatValidator(Validator):
    """Validate author and editor name formats.

    Checks for common formatting issues in name fields according to
    BibTeX conventions. Names should be separated by ' and ', and
    'et al.' should be replaced with 'and others'.
    """

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Validate author and editor fields.

        Args:
            entry: Entry to validate.

        Returns:
            List of name format validation errors.
        """
        errors = []

        if entry.author is not None:
            errors.extend(self._validate_names(entry.author, "author", entry.key))

        if entry.editor is not None:
            errors.extend(self._validate_names(entry.editor, "editor", entry.key))

        return errors

    def _validate_names(
        self, names: str, field: str, entry_key: str
    ) -> list[ValidationError]:
        """Validate name field format."""
        errors = []

        if not names or not names.strip():
            errors.append(
                ValidationError(
                    field=field,
                    message=f"{field.capitalize()} field is empty",
                    severity="warning",
                    entry_key=entry_key,
                )
            )
            return errors

        if names.strip().endswith(","):
            errors.append(
                ValidationError(
                    field=field,
                    message=f"{field.capitalize()} field ends with comma",
                    severity="warning",
                    entry_key=entry_key,
                )
            )

        if " and and " in names:
            errors.append(
                ValidationError(
                    field=field,
                    message=f"{field.capitalize()} field contains empty name",
                    severity="warning",
                    entry_key=entry_key,
                )
            )

        if "et al." in names.lower():
            errors.append(
                ValidationError(
                    field=field,
                    message=f"Use 'and others' instead of 'et al.' in {field} field",
                    severity="info",
                    entry_key=entry_key,
                )
            )

        return errors


class AbstractLengthValidator(Validator):
    """Validate abstract length constraints."""

    def __init__(self, max_length: int = 5000):
        self.max_length = max_length

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Check abstract length.

        Args:
            entry: Entry to validate.

        Returns:
            List of abstract length validation errors.
        """
        errors = []

        if entry.abstract and len(entry.abstract) > self.max_length:
            errors.append(
                ValidationError(
                    field="abstract",
                    message=f"Abstract is too long ({len(entry.abstract)} > {self.max_length} chars)",
                    severity="warning",
                    entry_key=entry.key,
                )
            )

        return errors


class CrossReferenceValidator(Validator):
    """Validate cross-references between entries.

    Ensures cross-referenced entries exist and have compatible types
    according to BibTeX conventions. For example, @inbook entries
    should only cross-reference @book entries.
    """

    def __init__(self, all_entries: dict[str, Entry]):
        self.all_entries = all_entries

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Validate cross-reference integrity.

        Args:
            entry: Entry to validate.

        Returns:
            List of cross-reference validation errors.
        """
        errors = []

        if entry.crossref:
            if entry.crossref not in self.all_entries:
                errors.append(
                    ValidationError(
                        field="crossref",
                        message=f"Cross-reference to non-existent entry: {entry.crossref}",
                        severity="error",
                        entry_key=entry.key,
                    )
                )
            else:
                parent = self.all_entries[entry.crossref]
                errors.extend(self._check_compatibility(entry, parent))

        return errors

    def _check_compatibility(
        self, child: Entry, parent: Entry
    ) -> list[ValidationError]:
        """Check if cross-reference types are compatible."""
        errors = []

        valid_relationships = {
            EntryType.INBOOK: {EntryType.BOOK},
            EntryType.INCOLLECTION: {EntryType.BOOK, EntryType.PROCEEDINGS},
            EntryType.INPROCEEDINGS: {EntryType.PROCEEDINGS},
            EntryType.CONFERENCE: {EntryType.PROCEEDINGS},
        }

        if child.type in valid_relationships:
            if parent.type not in valid_relationships[child.type]:
                errors.append(
                    ValidationError(
                        field="crossref",
                        message=f"{child.type.value} cannot cross-reference {parent.type.value}",
                        severity="warning",
                        entry_key=child.key,
                    )
                )
        elif child.type == EntryType.ARTICLE:
            errors.append(
                ValidationError(
                    field="crossref",
                    message=f"{child.type.value} cannot cross-reference {parent.type.value}",
                    severity="warning",
                    entry_key=child.key,
                )
            )

        return errors


class ConsistencyValidator(Validator):
    """Check consistency between related fields.

    Validates logical relationships between fields, such as ensuring
    volume/number are only used with journals, or that ISBNs are
    primarily used with book-type entries.
    """

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Check field consistency.

        Args:
            entry: Entry to validate.

        Returns:
            List of consistency validation errors.
        """
        errors = []

        if (entry.volume or entry.number) and not entry.journal:
            errors.append(
                ValidationError(
                    field=None,
                    message="Volume/number specified without journal",
                    severity="warning",
                    entry_key=entry.key,
                )
            )

        if entry.pages and not any([entry.journal, entry.booktitle]):
            errors.append(
                ValidationError(
                    field=None,
                    message="Pages specified without journal or book",
                    severity="info",
                    entry_key=entry.key,
                )
            )

        if entry.isbn and entry.type not in [
            EntryType.BOOK,
            EntryType.INBOOK,
            EntryType.INCOLLECTION,
            EntryType.PROCEEDINGS,
        ]:
            errors.append(
                ValidationError(
                    field="isbn",
                    message=f"ISBN unusual for entry type {entry.type.value}",
                    severity="info",
                    entry_key=entry.key,
                )
            )

        if entry.issn and entry.type not in [EntryType.ARTICLE, EntryType.PROCEEDINGS]:
            errors.append(
                ValidationError(
                    field="issn",
                    message=f"ISSN unusual for entry type {entry.type.value}",
                    severity="info",
                    entry_key=entry.key,
                )
            )

        return errors


# DuplicateDetector is now imported from duplicates module


class ValidatorRegistry:
    """Central registry for all validators.

    Manages a collection of validators and provides methods to
    validate individual entries or entire bibliographies.
    """

    def __init__(self, entries: list[Entry] | None = None):
        """Initialize with optional entry list for cross-validation.

        Args:
            entries: Optional list of all entries for cross-validation.
        """
        self.entries = entries or []
        self.entries_dict = {e.key: e for e in self.entries}

        self.validators = [
            EntryKeyValidator(),
            RequiredFieldValidator(),
            FieldFormatValidator(),
            DOIValidator(),
            ISBNValidator(),
            ISSNValidator(),
            URLValidator(),
            AuthorFormatValidator(),
            AbstractLengthValidator(),
            ConsistencyValidator(),
        ]

        if self.entries:
            self.validators.append(CrossReferenceValidator(self.entries_dict))

    def validate(self, entry: Entry) -> list[ValidationError]:
        """Run all validators on a single entry.

        Args:
            entry: Entry to validate.

        Returns:
            Combined list of all validation errors.
        """
        all_errors = []

        for validator in self.validators:
            errors = validator.validate(entry)
            all_errors.extend(errors)

        return all_errors

    def validate_all(self) -> dict[str, list[ValidationError]]:
        """Validate all entries and check for duplicates.

        Returns:
            Dictionary mapping entry keys to their validation errors.
        """
        results = {}

        for entry in self.entries:
            errors = self.validate(entry)
            if errors:
                results[entry.key] = errors

        if self.entries:
            detector = DuplicateDetector(self.entries)
            for entry in self.entries:
                duplicate_errors = detector.validate_entry(entry)
                if duplicate_errors:
                    if entry.key not in results:
                        results[entry.key] = []
                    results[entry.key].extend(duplicate_errors)

        return results


_global_registry: ValidatorRegistry | None = None


def get_validator_registry(entries: list[Entry] | None = None) -> ValidatorRegistry:
    """Get or create the global validator registry.

    Args:
        entries: Optional list of entries for cross-validation.

    Returns:
        The global ValidatorRegistry instance.
    """
    global _global_registry

    if entries is not None or _global_registry is None:
        _global_registry = ValidatorRegistry(entries)

    return _global_registry
