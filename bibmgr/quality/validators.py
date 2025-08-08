"""Field validators for bibliography entries.

Comprehensive validation for various field types including:
- ISBN (10 and 13 digit with checksum validation)
- ISSN (8 digit with checksum validation)
- DOI (Digital Object Identifier)
- ORCID (researcher identifier with checksum)
- ArXiv (preprint identifier)
- URLs (with security checks)
- Dates and date ranges
- Author names (with format detection)
- Page ranges (various formats)
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, Optional, Protocol
from urllib.parse import urlparse

import msgspec


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    ERROR = auto()  # Must fix
    WARNING = auto()  # Should fix
    INFO = auto()  # Consider fixing
    SUGGESTION = auto()  # Optional improvement


class ValidationResult(msgspec.Struct, frozen=True, kw_only=True):
    """Result of a validation check."""

    field: str
    value: Any
    is_valid: bool
    severity: ValidationSeverity = ValidationSeverity.ERROR
    message: str
    suggestion: Optional[str] = None
    metadata: Dict[str, Any] = msgspec.field(default_factory=dict)

    def to_string(self) -> str:
        """Format as human-readable string."""
        severity_str = self.severity.name
        status = "✓" if self.is_valid else "✗"

        parts = [f"[{severity_str}] {status} {self.field}"]
        parts.append(f": {self.message}")

        if self.suggestion:
            parts.append(f" (Suggestion: {self.suggestion})")

        return "".join(parts)


class FieldValidator(Protocol):
    """Protocol for field validators."""

    def validate(self, value: Any) -> ValidationResult:
        """Validate a field value."""
        ...


class ISBNValidator:
    """Validates ISBN-10 and ISBN-13 formats with checksums."""

    def __init__(self, field_name: str = "isbn"):
        self.field_name = field_name
        self.isbn10_pattern = re.compile(r"^(\d{9}[\dX])$")
        self.isbn13_pattern = re.compile(r"^(97[89]\d{10})$")

    def validate(self, value: Any) -> ValidationResult:
        """Validate ISBN format and checksum."""
        if value is None:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="ISBN is None",
            )

        if not isinstance(value, str):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message=f"ISBN must be a string, got {type(value).__name__}",
            )

        if not value:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="ISBN is empty",
            )

        # Remove common separators
        clean = value.replace("-", "").replace(" ", "").upper()

        # Check ISBN-10
        if len(clean) == 10:
            if not self.isbn10_pattern.match(clean):
                return ValidationResult(
                    field=self.field_name,
                    value=value,
                    is_valid=False,
                    message="Invalid ISBN-10 format",
                )

            if not self._validate_isbn10_checksum(clean):
                return ValidationResult(
                    field=self.field_name,
                    value=value,
                    is_valid=False,
                    message="Invalid ISBN-10 checksum",
                )

            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Valid ISBN-10",
                metadata={"type": "ISBN-10", "normalized": clean},
            )

        # Check ISBN-13
        elif len(clean) == 13:
            if not self.isbn13_pattern.match(clean):
                return ValidationResult(
                    field=self.field_name,
                    value=value,
                    is_valid=False,
                    message="Invalid ISBN-13 format (must start with 978 or 979)",
                )

            if not self._validate_isbn13_checksum(clean):
                return ValidationResult(
                    field=self.field_name,
                    value=value,
                    is_valid=False,
                    message="Invalid ISBN-13 checksum",
                )

            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Valid ISBN-13",
                metadata={"type": "ISBN-13", "normalized": clean},
            )

        else:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message=f"ISBN must be 10 or 13 digits (got {len(clean)})",
            )

    def _validate_isbn10_checksum(self, isbn: str) -> bool:
        """Validate ISBN-10 checksum."""
        total = sum(int(isbn[i]) * (10 - i) for i in range(9))
        check = isbn[9]
        total += 10 if check == "X" else int(check)
        return total % 11 == 0

    def _validate_isbn13_checksum(self, isbn: str) -> bool:
        """Validate ISBN-13 checksum."""
        total = sum(int(isbn[i]) * (3 if i % 2 else 1) for i in range(12))
        check_digit = (10 - (total % 10)) % 10
        return check_digit == int(isbn[12])


class ISSNValidator:
    """Validates ISSN format with checksum."""

    def __init__(self, field_name: str = "issn"):
        self.field_name = field_name
        self.issn_pattern = re.compile(r"^(\d{7}[\dX])$")

    def validate(self, value: Any) -> ValidationResult:
        """Validate ISSN format and checksum."""
        if value is None:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="ISSN is None",
            )

        if not isinstance(value, str):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message=f"ISSN must be a string, got {type(value).__name__}",
            )

        # Remove common separators
        clean = value.replace("-", "").replace(" ", "").upper()

        if len(clean) != 8:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message=f"ISSN must be 8 characters (got {len(clean)})",
            )

        if not self.issn_pattern.match(clean):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="Invalid ISSN format",
            )

        # Validate checksum
        total = sum(int(clean[i]) * (8 - i) for i in range(7))
        check = clean[7]
        check_value = 10 if check == "X" else int(check)
        computed_check = (11 - (total % 11)) % 11

        if computed_check != check_value:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="Invalid ISSN checksum",
            )

        return ValidationResult(
            field=self.field_name,
            value=value,
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message="Valid ISSN",
            metadata={"normalized": f"{clean[:4]}-{clean[4:]}"},
        )


class DOIValidator:
    """Validates DOI (Digital Object Identifier) format."""

    def __init__(self, field_name: str = "doi"):
        self.field_name = field_name
        # DOI pattern: 10.prefix/suffix (very permissive for suffix)
        self.doi_pattern = re.compile(r"^10\.\d{4,}(?:\.\d+)?/.*$", re.IGNORECASE)

    def validate(self, value: Any) -> ValidationResult:
        """Validate DOI format."""
        if value is None:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="DOI is None",
            )

        if not isinstance(value, str):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message=f"DOI must be a string, got {type(value).__name__}",
            )

        # Remove common prefixes
        clean = value.strip()
        for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
            if clean.lower().startswith(prefix):
                clean = clean[len(prefix) :]
                break

        if not self.doi_pattern.match(clean):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="Invalid DOI format",
                suggestion="DOI should be in format: 10.prefix/suffix",
            )

        return ValidationResult(
            field=self.field_name,
            value=value,
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message="Valid DOI",
            metadata={"normalized": clean, "url": f"https://doi.org/{clean}"},
        )


class ORCIDValidator:
    """Validates ORCID identifier with checksum."""

    def __init__(self, field_name: str = "orcid"):
        self.field_name = field_name
        self.orcid_pattern = re.compile(r"^(\d{4}-\d{4}-\d{4}-\d{3}[\dX])$")

    def validate(self, value: Any) -> ValidationResult:
        """Validate ORCID format and checksum."""
        if value is None:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="ORCID is None",
            )

        if not isinstance(value, str):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message=f"ORCID must be a string, got {type(value).__name__}",
            )

        # Remove common prefixes
        clean = value.strip().upper()
        for prefix in ["HTTPS://ORCID.ORG/", "HTTP://ORCID.ORG/", "ORCID.ORG/"]:
            if clean.startswith(prefix):
                clean = clean[len(prefix) :]
                break

        if not self.orcid_pattern.match(clean):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="Invalid ORCID format",
                suggestion="ORCID should be: 0000-0000-0000-0000",
            )

        # Validate checksum using ISO 7064 MOD 11-2
        digits = clean.replace("-", "")
        total = 0
        for digit in digits[:-1]:
            total = (total + int(digit)) * 2

        remainder = total % 11
        check_digit = (12 - remainder) % 11
        expected = "X" if check_digit == 10 else str(check_digit)

        if digits[-1] != expected:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="Invalid ORCID checksum",
            )

        return ValidationResult(
            field=self.field_name,
            value=value,
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message="Valid ORCID",
            metadata={"normalized": clean, "url": f"https://orcid.org/{clean}"},
        )


class ArXivValidator:
    """Validates arXiv identifier format."""

    def __init__(self, field_name: str = "arxiv"):
        self.field_name = field_name
        # New format: YYMM.NNNNN[vN]
        self.new_pattern = re.compile(r"^(\d{4})\.(\d{5})(v\d+)?$")
        # Old format: archive.subject/YYMMNNN[vN]
        # Valid archives: astro-ph, cond-mat, gr-qc, hep-ex, hep-lat, hep-ph, hep-th, math-ph, nlin, nucl-ex, nucl-th, physics, quant-ph, math, cs, q-bio, q-fin, stat
        self.old_pattern = re.compile(
            r"^(astro-ph|cond-mat|gr-qc|hep-ex|hep-lat|hep-ph|hep-th|math-ph|nlin|nucl-ex|nucl-th|physics|quant-ph|math|cs|q-bio|q-fin|stat)(?:\.[A-Z]{2})?/(\d{7})(v\d+)?$"
        )

    def validate(self, value: Any) -> ValidationResult:
        """Validate arXiv ID format."""
        if value is None:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="arXiv ID is None",
            )

        if not isinstance(value, str):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message=f"arXiv ID must be a string, got {type(value).__name__}",
            )

        # Remove common prefixes
        clean = value.strip()
        for prefix in [
            "https://arxiv.org/abs/",
            "http://arxiv.org/abs/",
            "arxiv:",
            "arXiv:",
        ]:
            if clean.lower().startswith(prefix.lower()):
                clean = clean[len(prefix) :]
                break

        # Try new format
        match = self.new_pattern.match(clean)
        if match:
            year_month = match.group(1)
            year = int(year_month[:2]) + 2000
            month = int(year_month[2:])

            if month < 1 or month > 12:
                return ValidationResult(
                    field=self.field_name,
                    value=value,
                    is_valid=False,
                    message=f"Invalid month in arXiv ID: {month}",
                )

            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Valid arXiv ID (new format)",
                metadata={
                    "normalized": clean,
                    "format": "new",
                    "year": year,
                    "month": month,
                    "url": f"https://arxiv.org/abs/{clean}",
                },
            )

        # Try old format
        match = self.old_pattern.match(clean)
        if match:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Valid arXiv ID (old format)",
                metadata={
                    "normalized": clean,
                    "format": "old",
                    "url": f"https://arxiv.org/abs/{clean}",
                },
            )

        return ValidationResult(
            field=self.field_name,
            value=value,
            is_valid=False,
            message="Invalid arXiv ID format",
            suggestion="Use format: YYMM.NNNNN or archive/YYMMNNN",
        )


class URLValidator:
    """Validates URL format with security checks."""

    def __init__(self, field_name: str = "url"):
        self.field_name = field_name
        self.allowed_schemes = {"http", "https", "ftp", "ftps"}
        self.dangerous_schemes = {"javascript", "data", "vbscript", "file"}

    def validate(self, value: Any) -> ValidationResult:
        """Validate URL format and security."""
        if value is None:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="URL is None",
            )

        if not isinstance(value, str):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message=f"URL must be a string, got {type(value).__name__}",
            )

        if not value:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="URL is empty",
            )

        try:
            parsed = urlparse(value)

            if not parsed.scheme:
                return ValidationResult(
                    field=self.field_name,
                    value=value,
                    is_valid=False,
                    message="URL missing scheme",
                    suggestion="Add http:// or https:// prefix",
                )

            # Security check
            if parsed.scheme.lower() in self.dangerous_schemes:
                return ValidationResult(
                    field=self.field_name,
                    value=value,
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Dangerous URL scheme: {parsed.scheme}",
                )

            if parsed.scheme not in self.allowed_schemes:
                return ValidationResult(
                    field=self.field_name,
                    value=value,
                    is_valid=True,
                    severity=ValidationSeverity.WARNING,
                    message=f"Unusual URL scheme: {parsed.scheme}",
                )

            if not parsed.netloc:
                return ValidationResult(
                    field=self.field_name,
                    value=value,
                    is_valid=False,
                    message="URL missing domain",
                )

            # Warn about HTTP
            if parsed.scheme == "http":
                return ValidationResult(
                    field=self.field_name,
                    value=value,
                    is_valid=True,
                    severity=ValidationSeverity.WARNING,
                    message="Consider using HTTPS instead of HTTP",
                )

            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Valid URL",
                metadata={"scheme": parsed.scheme, "domain": parsed.netloc},
            )

        except Exception as e:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message=f"Invalid URL: {e}",
            )


class DateValidator:
    """Validates date formats and ranges."""

    def __init__(self, field_name: str = "date"):
        self.field_name = field_name
        self.min_year = 1000
        self.current_year = datetime.now().year
        self.max_year = self.current_year + 10  # Allow up to 10 years in future
        self.date_formats = [
            "%Y-%m-%d",
            "%Y-%m",
            "%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y/%m/%d",
        ]

    def validate(self, value: Any) -> ValidationResult:
        """Validate date/year format and range."""
        if value is None:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="Date is None",
            )

        # Handle integer years
        if isinstance(value, int):
            if value < self.min_year:
                return ValidationResult(
                    field=self.field_name,
                    value=value,
                    is_valid=False,
                    message=f"Year {value} is too early (minimum: {self.min_year})",
                )

            if value > self.current_year:
                if value > self.max_year:
                    return ValidationResult(
                        field=self.field_name,
                        value=value,
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Year {value} is too far in the future (max: {self.max_year})",
                    )
                else:
                    return ValidationResult(
                        field=self.field_name,
                        value=value,
                        is_valid=True,
                        severity=ValidationSeverity.WARNING,
                        message=f"Year {value} is in the future",
                    )

            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Valid year",
                metadata={"year": value},
            )

        # Handle string dates
        if isinstance(value, str):
            # Try to parse as year
            try:
                year = int(value)
                return self.validate(year)
            except ValueError:
                pass

            # Try common date formats
            for fmt in self.date_formats:
                try:
                    date = datetime.strptime(value, fmt)

                    # Validate parsed date
                    if date.year < self.min_year:
                        return ValidationResult(
                            field=self.field_name,
                            value=value,
                            is_valid=False,
                            message=f"Year {date.year} is too early",
                        )

                    if date.year > self.max_year:
                        return ValidationResult(
                            field=self.field_name,
                            value=value,
                            is_valid=True,
                            severity=ValidationSeverity.WARNING,
                            message="Date is in the future",
                        )

                    return ValidationResult(
                        field=self.field_name,
                        value=value,
                        is_valid=True,
                        severity=ValidationSeverity.INFO,
                        message="Valid date",
                        metadata={
                            "year": date.year,
                            "month": date.month if fmt != "%Y" else None,
                            "day": date.day if "%d" in fmt else None,
                        },
                    )
                except ValueError:
                    continue

            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="Unrecognized date format",
                suggestion="Use YYYY-MM-DD, YYYY-MM, or YYYY",
            )

        return ValidationResult(
            field=self.field_name,
            value=value,
            is_valid=False,
            message=f"Date must be integer year or date string, got {type(value).__name__}",
        )


class AuthorValidator:
    """Validates author name formats."""

    def __init__(self, field_name: str = "author"):
        self.field_name = field_name
        # Pattern for suspicious characters
        self.suspicious_pattern = re.compile(r"[0-9@#$%^*()+=\[\]|\\<>?/]")
        # Pattern for collaboration/group names
        self.collaboration_pattern = re.compile(r"^\{.*\}$")

    def validate(self, value: Any) -> ValidationResult:
        """Validate author name format."""
        if value is None:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="Author is None",
            )

        if not isinstance(value, str):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message=f"Author must be a string, got {type(value).__name__}",
            )

        if not value or not value.strip():
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Author field is empty",
            )

        # Check for collaboration/group (valid in braces)
        if self.collaboration_pattern.match(value.strip()):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Valid collaboration/group name",
                metadata={"type": "collaboration"},
            )

        # Check for suspicious characters (not in collaboration)
        if self.suspicious_pattern.search(value):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                message="Author name contains unusual characters",
            )

        # Check for proper "and" separation
        if " and " in value:
            authors = value.split(" and ")

            # Check each author
            for i, author in enumerate(authors):
                if not author.strip():
                    return ValidationResult(
                        field=self.field_name,
                        value=value,
                        is_valid=False,
                        message=f"Empty author at position {i + 1} in list",
                    )

                # Suggest Last, First format
                if " " in author.strip() and "," not in author:
                    return ValidationResult(
                        field=self.field_name,
                        value=value,
                        is_valid=True,
                        severity=ValidationSeverity.SUGGESTION,
                        message="Consider using 'Last, First' format for consistency",
                        metadata={"author_count": len(authors)},
                    )

            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message=f"Valid author list ({len(authors)} authors)",
                metadata={"author_count": len(authors)},
            )

        # Single author - check format
        if " " in value.strip() and "," not in value:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.SUGGESTION,
                message="Consider using 'Last, First' format for consistency",
                metadata={"author_count": 1},
            )

        return ValidationResult(
            field=self.field_name,
            value=value,
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message="Valid author format",
            metadata={"author_count": 1},
        )


class PageRangeValidator:
    """Validates page range formats."""

    def __init__(self, field_name: str = "pages"):
        self.field_name = field_name
        # Patterns for various formats
        self.single_page = re.compile(r"^\d+$")
        self.page_range = re.compile(r"^(\d+)\s*[-–—]\s*(\d+)$")
        self.bibtex_range = re.compile(r"^(\d+)\s*--\s*(\d+)$")
        self.roman_single = re.compile(r"^[IVXLCDM]+$", re.IGNORECASE)
        self.roman_range = re.compile(
            r"^([IVXLCDM]+)\s*[-–—]+\s*([IVXLCDM]+)$", re.IGNORECASE
        )
        self.electronic = re.compile(r"^e\d+$", re.IGNORECASE)

    def validate(self, value: Any) -> ValidationResult:
        """Validate page range format."""
        if value is None:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="Pages is None",
            )

        if not isinstance(value, str):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message=f"Pages must be a string, got {type(value).__name__}",
            )

        value = value.strip()

        if not value:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=False,
                message="Pages field is empty",
            )

        # Electronic article number
        if self.electronic.match(value):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Valid electronic article number",
                metadata={"type": "electronic"},
            )

        # Single page (numeric)
        if self.single_page.match(value):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Valid single page",
                metadata={"type": "single", "page": int(value)},
            )

        # Single page (roman)
        if self.roman_single.match(value):
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Valid roman numeral page",
                metadata={"type": "roman_single"},
            )

        # BibTeX format (preferred)
        match = self.bibtex_range.match(value)
        if match:
            start, end = int(match.group(1)), int(match.group(2))

            if start > end:
                return ValidationResult(
                    field=self.field_name,
                    value=value,
                    is_valid=False,
                    message=f"Invalid range: start ({start}) > end ({end})",
                )

            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Valid page range (BibTeX format)",
                metadata={
                    "type": "range",
                    "format": "bibtex",
                    "start": start,
                    "end": end,
                    "count": end - start + 1,
                },
            )

        # Roman numeral range
        match = self.roman_range.match(value)
        if match:
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Valid roman numeral range",
                metadata={"type": "roman_range"},
            )

        # Other dash formats
        match = self.page_range.match(value)
        if match:
            start, end = int(match.group(1)), int(match.group(2))

            if start > end:
                return ValidationResult(
                    field=self.field_name,
                    value=value,
                    is_valid=False,
                    message=f"Invalid range: start ({start}) > end ({end})",
                )

            # Suggest BibTeX format
            bibtex_format = f"{start}--{end}"
            return ValidationResult(
                field=self.field_name,
                value=value,
                is_valid=True,
                severity=ValidationSeverity.SUGGESTION,
                message="Valid page range",
                suggestion=f"Consider BibTeX format: {bibtex_format}",
                metadata={
                    "type": "range",
                    "format": "single_dash",
                    "start": start,
                    "end": end,
                    "count": end - start + 1,
                },
            )

        return ValidationResult(
            field=self.field_name,
            value=value,
            is_valid=False,
            message="Invalid page range format",
            suggestion="Use format: 7--33 (double dash for BibTeX) or single page",
        )
