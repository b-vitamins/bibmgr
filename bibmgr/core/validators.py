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


class DuplicateDetector:
    """
    Detect duplicate bibliography entries using multiple strategies.

    This class identifies duplicate entries based on:
    - DOI (exact match after normalization)
    - Title + Author + Year (with configurable year tolerance)

    The detection process includes sophisticated normalization to handle:
    - Unicode characters and accents
    - LaTeX commands and formatting
    - Author name variations
    - URL prefixes in DOIs
    """

    def __init__(self, entries: list[Entry], year_tolerance: int = 0):
        """
        Initialize duplicate detector.

        Args:
            entries: List of bibliography entries to check
            year_tolerance: Maximum year difference to consider duplicates (0 = exact match)
        """
        self.entries = entries
        self.year_tolerance = year_tolerance

        # Maps for fast lookup
        self.doi_map: dict[str, list[Entry]] = {}
        self.title_author_year_map: dict[str, list[Entry]] = {}

        # Build lookup structures
        self._build_index()

    def _build_index(self) -> None:
        """Build index structures for efficient duplicate detection."""
        for entry in self.entries:
            # Index by DOI
            if entry.doi:
                normalized_doi = self._normalize_doi(entry.doi)
                if normalized_doi:  # Only index non-empty DOIs
                    self.doi_map.setdefault(normalized_doi, []).append(entry)

            # Index by title-author-year (only for exact year matching)
            if entry.title and entry.author and entry.year and self.year_tolerance == 0:
                tay_key = self._make_tay_key(entry)
                self.title_author_year_map.setdefault(tay_key, []).append(entry)

    def _normalize_doi(self, doi: str) -> str:
        """
        Normalize DOI for comparison.

        - Convert to lowercase
        - Strip whitespace
        - Remove common URL prefixes
        """
        if not doi:
            return ""

        # Basic normalization
        doi = doi.lower().strip()

        # Remove URL prefixes
        prefixes = [
            "https://doi.org/",
            "http://doi.org/",
            "https://dx.doi.org/",
            "http://dx.doi.org/",
            "doi:",
        ]

        for prefix in prefixes:
            if doi.startswith(prefix):
                return doi[len(prefix) :]

        return doi

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for robust comparison.

        - Convert to lowercase
        - Handle LaTeX commands
        - Normalize Unicode to ASCII
        - Remove articles and punctuation
        """
        import unicodedata

        # Convert to lowercase
        text = text.lower()

        # Handle common LaTeX commands
        latex_replacements = {
            r"\{\\latex\}": "latex",
            r"\\latex": "latex",
            r"\{\\tex\}": "tex",
            r"\\tex": "tex",
        }

        for pattern, replacement in latex_replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Remove other LaTeX commands
        text = re.sub(r"\{\\[a-zA-Z]+\*?\}", " ", text)  # {\command}
        text = re.sub(r"\\[a-zA-Z]+\*?\s*\{\}", " ", text)  # \command{}
        text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)  # \command

        # Remove braces
        text = text.replace("{", "").replace("}", "")

        # Normalize Unicode
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))

        # Remove articles
        text = re.sub(r"\b(the|a|an)\b", "", text)

        # Remove punctuation
        text = re.sub(r"[^\w\s]", " ", text)

        # Normalize whitespace
        text = " ".join(text.split())

        return text

    def _normalize_authors(self, authors: str) -> str:
        """
        Normalize author names for comparison.

        Extract and sort last names to handle:
        - Different name orders
        - Abbreviations
        - Multiple authors
        """
        # Split authors first (before normalization to preserve structure)
        author_list = re.split(r"\s+and\s+", authors)

        # Extract last names
        last_names = []
        for author in author_list:
            author = author.strip()
            if not author:
                continue

            # Check if it's "Last, First" format
            if "," in author:
                # Split by comma and take the first part as last name
                parts = author.split(",", 1)
                last_name = parts[0].strip()
            else:
                # "First Last" format - take the last word
                words = author.split()
                if not words:
                    continue

                # Skip common suffixes
                suffixes = {
                    "jr",
                    "sr",
                    "ii",
                    "iii",
                    "iv",
                    "v",
                    "phd",
                    "md",
                    "Jr",
                    "Sr",
                    "II",
                    "III",
                    "IV",
                    "V",
                    "PhD",
                    "MD",
                }

                # Work backwards to find last name
                last_name = None
                for i in range(len(words) - 1, -1, -1):
                    word = words[i]
                    if word not in suffixes and len(word) > 1:
                        last_name = word
                        break

                # If we couldn't find a suitable last name, use the last word
                if not last_name and words:
                    last_name = words[-1]

            if last_name:
                # Normalize the last name
                last_name = self._normalize_text(last_name)
                if last_name:  # Only add non-empty normalized names
                    last_names.append(last_name)

        # Sort for consistent ordering
        last_names.sort()

        return " ".join(last_names)

    def _make_tay_key(self, entry: Entry) -> str:
        """Create normalized title-author-year key."""
        # These fields are guaranteed to exist by the callers
        assert entry.title is not None
        assert entry.author is not None
        assert entry.year is not None

        title = self._normalize_text(entry.title)
        authors = self._normalize_authors(entry.author)
        year = str(entry.year)

        return f"{title}|{authors}|{year}"

    def find_duplicates(self) -> list[list[Entry]]:
        """
        Find all groups of duplicate entries.

        Returns:
            List of duplicate groups, where each group contains 2+ duplicate entries
        """
        duplicates = []
        seen_groups = set()

        # Find DOI duplicates
        for doi, entries in self.doi_map.items():
            if len(entries) > 1:
                group_keys = frozenset(e.key for e in entries)
                if group_keys not in seen_groups:
                    duplicates.append(entries)
                    seen_groups.add(group_keys)

        # Find title-author-year duplicates
        if self.year_tolerance == 0:
            # Exact year matching - use pre-built index
            for key, entries in self.title_author_year_map.items():
                if len(entries) > 1:
                    group_keys = frozenset(e.key for e in entries)
                    if group_keys not in seen_groups:
                        duplicates.append(entries)
                        seen_groups.add(group_keys)
        else:
            # Year tolerance - need custom grouping
            self._find_tay_duplicates_with_tolerance(duplicates, seen_groups)

        return duplicates

    def _find_tay_duplicates_with_tolerance(
        self, duplicates: list[list[Entry]], seen_groups: set[frozenset[str]]
    ) -> None:
        """Find title-author-year duplicates with year tolerance."""
        # Group by title and author only
        ta_groups: dict[str, list[Entry]] = {}

        for entry in self.entries:
            if entry.title and entry.author and entry.year:
                title = self._normalize_text(entry.title)
                authors = self._normalize_authors(entry.author)
                ta_key = f"{title}|{authors}"
                ta_groups.setdefault(ta_key, []).append(entry)

        # Check each group for year proximity
        for entries in ta_groups.values():
            if len(entries) < 2:
                continue

            # Group by year tolerance using union-find approach
            year_groups = self._group_by_year_tolerance(entries)

            # Add groups with 2+ entries
            for group in year_groups:
                if len(group) > 1:
                    group_keys = frozenset(e.key for e in group)
                    if group_keys not in seen_groups:
                        duplicates.append(group)
                        seen_groups.add(group_keys)

    def _group_by_year_tolerance(self, entries: list[Entry]) -> list[list[Entry]]:
        """Group entries by year tolerance using connected components."""
        if not entries:
            return []

        # Build adjacency list
        n = len(entries)
        adjacent = [set() for _ in range(n)]

        for i in range(n):
            for j in range(i + 1, n):
                # Year fields are guaranteed to exist by caller
                year_i = entries[i].year
                year_j = entries[j].year
                assert year_i is not None
                assert year_j is not None
                if abs(year_i - year_j) <= self.year_tolerance:
                    adjacent[i].add(j)
                    adjacent[j].add(i)

        # Find connected components
        visited = [False] * n
        components = []

        for i in range(n):
            if not visited[i]:
                component = []
                self._dfs(i, visited, adjacent, component, entries)
                components.append(component)

        return components

    def _dfs(
        self,
        node: int,
        visited: list[bool],
        adjacent: list[set[int]],
        component: list[Entry],
        entries: list[Entry],
    ) -> None:
        """Depth-first search for connected components."""
        visited[node] = True
        component.append(entries[node])

        for neighbor in adjacent[node]:
            if not visited[neighbor]:
                self._dfs(neighbor, visited, adjacent, component, entries)

    def validate_entry(self, entry: Entry) -> list[ValidationError]:
        """Check if a single entry has duplicates."""
        errors = []

        # Check DOI duplicates
        if entry.doi:
            normalized_doi = self._normalize_doi(entry.doi)
            if normalized_doi:
                doi_duplicates = self.doi_map.get(normalized_doi, [])
                other_entries = [e for e in doi_duplicates if e.key != entry.key]

                if other_entries:
                    errors.append(
                        ValidationError(
                            field="doi",
                            message=f"Duplicate DOI found in entries: {', '.join(e.key for e in other_entries)}",
                            severity="warning",
                            entry_key=entry.key,
                        )
                    )

        # Check title-author-year duplicates
        if entry.title and entry.author and entry.year:
            if self.year_tolerance == 0:
                # Use index for exact matching
                tay_key = self._make_tay_key(entry)
                tay_duplicates = self.title_author_year_map.get(tay_key, [])
                other_entries = [e for e in tay_duplicates if e.key != entry.key]
            else:
                # Manual search with tolerance
                other_entries = self._find_tay_matches_with_tolerance(entry)

            if other_entries:
                errors.append(
                    ValidationError(
                        field=None,
                        message=f"Possible duplicate (same title/author/year) in entries: {', '.join(e.key for e in other_entries)}",
                        severity="info",
                        entry_key=entry.key,
                    )
                )

        return errors

    def _find_tay_matches_with_tolerance(self, target: Entry) -> list[Entry]:
        """Find entries matching title/author/year with tolerance."""
        matches = []

        # These are guaranteed by the caller
        assert target.title is not None
        assert target.author is not None
        assert target.year is not None

        target_title = self._normalize_text(target.title)
        target_authors = self._normalize_authors(target.author)

        for entry in self.entries:
            if entry.key == target.key:
                continue

            if entry.title and entry.author and entry.year:
                if (
                    self._normalize_text(entry.title) == target_title
                    and self._normalize_authors(entry.author) == target_authors
                    and abs(entry.year - target.year) <= self.year_tolerance
                ):
                    matches.append(entry)

        return matches

    def find_duplicates_with_confidence(self) -> list[dict[str, Any]]:
        """
        Find duplicates with confidence scores.

        Returns:
            List of duplicate groups with confidence scores (0.0-1.0)
        """
        results = []
        duplicate_groups = self.find_duplicates()

        for group in duplicate_groups:
            confidence = self._calculate_confidence(group)
            results.append({"entries": group, "confidence": confidence})

        return results

    def _calculate_confidence(self, group: list[Entry]) -> float:
        """Calculate confidence score for a duplicate group."""
        confidence = 0.0

        # Check DOI match (highest confidence)
        dois = [self._normalize_doi(e.doi) for e in group if e.doi]
        if dois:
            # Calculate what fraction have the same DOI
            doi_counts = {}
            for doi in dois:
                doi_counts[doi] = doi_counts.get(doi, 0) + 1

            max_doi_count = max(doi_counts.values())
            doi_fraction = max_doi_count / len(group)

            if doi_fraction == 1.0:
                # All entries have the same DOI
                confidence = 0.95
            elif doi_fraction > 0.5:
                # Majority have the same DOI
                confidence = 0.85
            else:
                # Some have matching DOIs
                confidence = 0.75

        # Check exact title-author-year match
        if all(e.title and e.author and e.year for e in group):
            tay_keys = [self._make_tay_key(e) for e in group]
            if all(k == tay_keys[0] for k in tay_keys):
                # Exact TAY match
                if confidence == 0:
                    # No DOI match, just TAY
                    confidence = 0.8
                elif confidence >= 0.95:
                    # Both full DOI and TAY match
                    confidence = 1.0
                else:
                    # Partial DOI match + TAY match
                    confidence = max(confidence, 0.9)
            else:
                # Partial match (year tolerance or minor variations)
                confidence = max(confidence, 0.6)

        return confidence

    def get_merge_suggestions(self, entry1: Entry, entry2: Entry) -> dict[str, Any]:
        """
        Suggest which fields to keep when merging duplicates.

        Args:
            entry1: First entry
            entry2: Second entry

        Returns:
            Dictionary of field names to suggested values
        """
        suggestions = {}

        # Get all relevant fields
        fields = [
            "type",
            "title",
            "author",
            "editor",
            "journal",
            "booktitle",
            "year",
            "month",
            "volume",
            "number",
            "pages",
            "publisher",
            "address",
            "doi",
            "url",
            "isbn",
            "issn",
            "abstract",
            "keywords",
            "note",
            "crossref",
            "eprint",
            "archiveprefix",
            "primaryclass",
        ]

        for field in fields:
            val1 = getattr(entry1, field, None)
            val2 = getattr(entry2, field, None)

            # Select best value
            if val2 and not val1:
                suggestions[field] = val2
            elif val1 and not val2:
                suggestions[field] = val1
            elif val1 and val2:
                # Both have values - use heuristics
                suggestions[field] = self._select_best_value(field, val1, val2)

        return suggestions

    def _select_best_value(self, field: str, val1: Any, val2: Any) -> Any:
        """Select the best value when both entries have the field."""
        if field == "author":
            # Prefer more complete author list
            return val2 if len(str(val2)) > len(str(val1)) else val1
        elif field in ["doi", "url", "isbn", "issn"]:
            # For identifiers, prefer the second (assume newer/more complete)
            return val2
        elif field == "abstract":
            # Prefer longer abstract
            return val2 if len(str(val2)) > len(str(val1)) else val1
        elif field == "pages":
            # Prefer complete page range
            if "--" in str(val2) and "--" not in str(val1):
                return val2
            elif "--" in str(val1) and "--" not in str(val2):
                return val1
            else:
                return val2
        else:
            # Default to second entry
            return val2


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
