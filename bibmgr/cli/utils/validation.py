"""Input validation helpers for the CLI.

Provides validation functions for user input.
"""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import click

from bibmgr.core.models import EntryType

T = TypeVar("T")


def validate_entry_key(key: str) -> str:
    """Validate entry key format.

    Args:
        key: Entry key to validate

    Returns:
        Validated key

    Raises:
        click.BadParameter: If key is invalid
    """
    if not key:
        raise click.BadParameter("Entry key cannot be empty")

    # Check format (alphanumeric, underscores, hyphens)
    if not re.match(r"^[a-zA-Z0-9_-]+$", key):
        raise click.BadParameter(
            "Entry key must contain only letters, numbers, underscores, and hyphens"
        )

    # Check reasonable length
    if len(key) > 100:
        raise click.BadParameter("Entry key is too long (max 100 characters)")

    return key


def validate_entry_type(type_str: str) -> EntryType:
    """Validate and convert entry type string.

    Args:
        type_str: Entry type string

    Returns:
        EntryType enum value

    Raises:
        click.BadParameter: If type is invalid
    """
    try:
        return EntryType(type_str.lower())
    except ValueError:
        valid_types = ", ".join(t.value for t in EntryType)
        raise click.BadParameter(
            f"Invalid entry type '{type_str}'. Valid types: {valid_types}"
        )


def validate_year(year_str: str) -> int:
    """Validate year value.

    Args:
        year_str: Year string

    Returns:
        Year as integer

    Raises:
        click.BadParameter: If year is invalid
    """
    try:
        year = int(year_str)
    except ValueError:
        raise click.BadParameter(f"Invalid year '{year_str}' - must be a number")

    # Reasonable range check
    if year < 1000 or year > 2100:
        raise click.BadParameter(f"Year {year} seems unlikely - please check")

    return year


def validate_doi(doi: str) -> str:
    """Validate DOI format.

    Args:
        doi: DOI string

    Returns:
        Validated DOI

    Raises:
        click.BadParameter: If DOI is invalid
    """
    # Basic DOI pattern
    doi_pattern = r"^10\.\d{4,}/[-._;()/:A-Za-z0-9]+$"

    if not re.match(doi_pattern, doi):
        raise click.BadParameter(
            f"Invalid DOI format: {doi}. DOIs should start with '10.' followed by a prefix and suffix"
        )

    return doi


def validate_file_path(
    path: str,
    must_exist: bool = False,
    must_be_file: bool = True,
) -> Path:
    """Validate file path.

    Args:
        path: File path string
        must_exist: Whether file must exist
        must_be_file: Whether path must be a file (not directory)

    Returns:
        Path object

    Raises:
        click.BadParameter: If path is invalid
    """
    file_path = Path(path).expanduser().resolve()

    if must_exist and not file_path.exists():
        raise click.BadParameter(f"File does not exist: {file_path}")

    if must_exist and must_be_file and not file_path.is_file():
        raise click.BadParameter(f"Path is not a file: {file_path}")

    return file_path


def validate_directory_path(
    path: str,
    must_exist: bool = False,
) -> Path:
    """Validate directory path.

    Args:
        path: Directory path string
        must_exist: Whether directory must exist

    Returns:
        Path object

    Raises:
        click.BadParameter: If path is invalid
    """
    dir_path = Path(path).expanduser().resolve()

    if must_exist and not dir_path.exists():
        raise click.BadParameter(f"Directory does not exist: {dir_path}")

    if must_exist and not dir_path.is_dir():
        raise click.BadParameter(f"Path is not a directory: {dir_path}")

    return dir_path


def validate_email(email: str) -> str:
    """Validate email address format.

    Args:
        email: Email address

    Returns:
        Validated email

    Raises:
        click.BadParameter: If email is invalid
    """
    # Simple email pattern
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(email_pattern, email):
        raise click.BadParameter(f"Invalid email format: {email}")

    return email


def validate_url(url: str) -> str:
    """Validate URL format.

    Args:
        url: URL string

    Returns:
        Validated URL

    Raises:
        click.BadParameter: If URL is invalid
    """
    # Basic URL pattern
    url_pattern = r"^https?://[^\s/$.?#].[^\s]*$"

    if not re.match(url_pattern, url, re.IGNORECASE):
        raise click.BadParameter(
            f"Invalid URL format: {url}. URLs should start with http:// or https://"
        )

    return url


def validate_choice(
    value: str,
    choices: list[str],
    case_sensitive: bool = False,
) -> str:
    """Validate choice from list.

    Args:
        value: Value to validate
        choices: Valid choices
        case_sensitive: Whether comparison is case-sensitive

    Returns:
        Validated choice (normalized if case-insensitive)

    Raises:
        click.BadParameter: If value not in choices
    """
    if case_sensitive:
        if value not in choices:
            raise click.BadParameter(
                f"Invalid choice '{value}'. Valid choices: {', '.join(choices)}"
            )
        return value
    else:
        # Case-insensitive comparison
        value_lower = value.lower()
        choices_map = {c.lower(): c for c in choices}

        if value_lower not in choices_map:
            raise click.BadParameter(
                f"Invalid choice '{value}'. Valid choices: {', '.join(choices)}"
            )

        return choices_map[value_lower]


def create_validator(
    func: Callable[[Any], T],
    error_message: str | None = None,
) -> Callable[[Any], T]:
    """Create a Click-compatible validator from a function.

    Args:
        func: Validation function
        error_message: Custom error message

    Returns:
        Click validator function
    """

    def validator(ctx, param, value):  # type: ignore[misc]
        if value is None:
            return value

        try:
            return func(value)
        except (ValueError, TypeError) as e:
            msg = error_message or str(e)
            raise click.BadParameter(msg)

    return validator  # type: ignore[return-value]
