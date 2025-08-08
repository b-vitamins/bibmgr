"""CLI input validators."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from bibmgr.core.models import EntryType


def validate_entry_key(key: str) -> str:
    """Validate entry key.

    Args:
        key: Entry key to validate

    Returns:
        Validated key

    Raises:
        ValueError: If key is invalid
    """
    if not key:
        raise ValueError("Entry key cannot be empty")

    # Check for valid characters (alphanumeric, dash, underscore)
    if not re.match(r"^[a-zA-Z0-9_-]+$", key):
        raise ValueError(
            f"Invalid key '{key}': must contain only letters, numbers, "
            "dashes, and underscores"
        )

    return key


def validate_entry_type(type_str: str) -> EntryType:
    """Validate and convert entry type.

    Args:
        type_str: Entry type string

    Returns:
        EntryType enum value

    Raises:
        ValueError: If type is invalid
    """
    try:
        # Handle case variations
        type_str = type_str.lower()

        # Handle common variations
        type_map = {
            "inproceedings": "inproceedings",
            "in-proceedings": "inproceedings",
            "conference": "inproceedings",
            "phd": "phdthesis",
            "phdthesis": "phdthesis",
            "masters": "mastersthesis",
            "mastersthesis": "mastersthesis",
            "tech-report": "techreport",
            "techreport": "techreport",
        }

        type_str = type_map.get(type_str, type_str)
        return EntryType(type_str)

    except ValueError:
        valid_types = [t.value for t in EntryType]
        raise ValueError(
            f"Invalid entry type '{type_str}'. Valid types: {', '.join(valid_types)}"
        )


def validate_year(year: int | str | None) -> int | None:
    """Validate publication year.

    Args:
        year: Year value

    Returns:
        Validated year or None

    Raises:
        ValueError: If year is invalid
    """
    if year is None or year == "":
        return None

    try:
        year_int = int(year)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid year '{year}': must be a number")

    current_year = datetime.now().year

    if year_int < 1600:
        raise ValueError(f"Invalid year {year_int}: too old (before 1600)")

    if year_int > current_year + 5:
        raise ValueError(
            f"Invalid year {year_int}: too far in future (after {current_year + 5})"
        )

    return year_int


def validate_file_path(
    path: str, must_exist: bool = False, must_be_file: bool = True
) -> Path:
    """Validate file path.

    Args:
        path: Path string
        must_exist: Whether file must exist
        must_be_file: Whether path must be a file (not directory)

    Returns:
        Validated Path object

    Raises:
        ValueError: If path is invalid
    """
    try:
        path_obj = Path(path).expanduser().resolve()
    except (ValueError, OSError) as e:
        raise ValueError(f"Invalid path '{path}': {e}")

    if must_exist and not path_obj.exists():
        raise ValueError(f"File not found: {path}")

    if must_exist and must_be_file and not path_obj.is_file():
        raise ValueError(f"Not a file: {path}")

    return path_obj


def validate_format(format: str, valid_formats: list[str]) -> str:
    """Validate format string.

    Args:
        format: Format string
        valid_formats: List of valid formats

    Returns:
        Validated format (lowercase)

    Raises:
        ValueError: If format is invalid
    """
    format_lower = format.lower()

    if format_lower not in valid_formats:
        raise ValueError(
            f"Invalid format '{format}'. Valid formats: {', '.join(valid_formats)}"
        )

    return format_lower


def validate_author(author: str) -> str:
    """Validate author string.

    Args:
        author: Author string

    Returns:
        Validated author string

    Raises:
        ValueError: If author format is invalid
    """
    if not author or not author.strip():
        raise ValueError("Author cannot be empty")

    # Basic validation - check for reasonable format
    # Allow "Last, First" or "First Last" or "Last, F." etc.
    if len(author.strip()) < 2:
        raise ValueError("Author name too short")

    # Check for invalid characters
    if any(char in author for char in ["@", "#", "$", "%", "^", "&", "*"]):
        raise ValueError("Author contains invalid characters")

    return author.strip()


def validate_doi(doi: str) -> str:
    """Validate DOI.

    Args:
        doi: DOI string

    Returns:
        Validated DOI

    Raises:
        ValueError: If DOI format is invalid
    """
    if not doi:
        return ""

    # Basic DOI pattern (10.xxxxx/xxxxx)
    doi_pattern = r"^10\.\d{4,}/[-._;()/:\w]+$"

    # Remove common prefixes
    doi = doi.strip()
    for prefix in ["doi:", "DOI:", "https://doi.org/", "http://dx.doi.org/"]:
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]

    if not re.match(doi_pattern, doi):
        raise ValueError(f"Invalid DOI format: {doi}")

    return doi


def validate_url(url: str) -> str:
    """Validate URL.

    Args:
        url: URL string

    Returns:
        Validated URL

    Raises:
        ValueError: If URL format is invalid
    """
    if not url:
        return ""

    url = url.strip()

    # Basic URL validation
    url_pattern = r"^https?://"
    if not re.match(url_pattern, url, re.IGNORECASE):
        raise ValueError(f"Invalid URL (must start with http:// or https://): {url}")

    return url


def validate_pages(pages: str) -> str:
    """Validate pages string.

    Args:
        pages: Pages string (e.g., "10-20" or "100")

    Returns:
        Validated pages string

    Raises:
        ValueError: If pages format is invalid
    """
    if not pages:
        return ""

    pages = pages.strip()

    # Valid formats: "10", "10-20", "10--20", "viii-xii"
    pages_pattern = r"^[ivxlcdm\d]+(-{1,2}[ivxlcdm\d]+)?$"

    if not re.match(pages_pattern, pages, re.IGNORECASE):
        raise ValueError(
            f"Invalid pages format '{pages}'. Expected format: '10' or '10-20'"
        )

    return pages


def validate_required_fields(entry_dict: dict) -> list[str]:
    """Validate that required fields are present.

    Args:
        entry_dict: Dictionary of entry fields

    Returns:
        List of missing required fields
    """
    required = ["key", "type", "title"]
    missing = []

    for field in required:
        if field not in entry_dict or not entry_dict[field]:
            missing.append(field)

    # Type-specific requirements
    entry_type = entry_dict.get("type", "").lower()

    if entry_type == "article":
        for field in ["journal", "year"]:
            if field not in entry_dict or not entry_dict[field]:
                missing.append(field)

    elif entry_type == "inproceedings":
        if "booktitle" not in entry_dict or not entry_dict["booktitle"]:
            missing.append("booktitle")

    elif entry_type == "book":
        if "publisher" not in entry_dict or not entry_dict["publisher"]:
            missing.append("publisher")

    elif entry_type in ["phdthesis", "mastersthesis"]:
        if "school" not in entry_dict or not entry_dict["school"]:
            missing.append("school")

    return missing
