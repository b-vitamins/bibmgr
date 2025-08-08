"""Core domain models and validators for bibliography management."""

from bibmgr.core.models import (
    Collection,
    Entry,
    EntryType,
    Tag,
    ValidationError,
    get_required_fields,
)
from bibmgr.core.validators import (
    AuthorFormatValidator,
    CompositeValidator,
    CrossReferenceValidator,
    EntryValidator,
    FieldFormatValidator,
    ISBNValidator,
    ISSNValidator,
    RequiredFieldsValidator,
    create_default_validator,
)

__all__ = [
    # Models
    "Entry",
    "EntryType",
    "ValidationError",
    "Collection",
    "Tag",
    "get_required_fields",
    # Validators
    "EntryValidator",
    "RequiredFieldsValidator",
    "FieldFormatValidator",
    "AuthorFormatValidator",
    "CrossReferenceValidator",
    "ISBNValidator",
    "ISSNValidator",
    "CompositeValidator",
    "create_default_validator",
]
