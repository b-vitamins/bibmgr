"""Core domain models and validators for bibliography management."""

# Fields and entry types
# BibTeX encoding/decoding
from bibmgr.core.bibtex import (
    BibtexDecoder,
    BibtexEncoder,
)

# Builders
from bibmgr.core.builders import (
    CollectionBuilder,
    EntryBuilder,
)
from bibmgr.core.fields import (
    ALL_FIELDS,
    COMPAT_FIELDS,
    MODERN_FIELDS,
    STANDARD_FIELDS,
    EntryType,
    FieldRequirements,
)

# Models
from bibmgr.core.models import (
    Collection,
    Entry,
    ErrorSeverity,
    Tag,
    ValidationError,
)

# Name parsing
from bibmgr.core.names import (
    NameParser,
    ParsedName,
)

# Sorting
from bibmgr.core.sorting import (
    LabelGenerator,
    SortKeyGenerator,
)

# String abbreviations
from bibmgr.core.strings import (
    StringRegistry,
)

# Title processing
from bibmgr.core.titles import (
    TitleProcessor,
)

# Duplicate detection
from bibmgr.core.duplicates import (
    DuplicateDetector,
)

# Validators
from bibmgr.core.validators import (
    AbstractLengthValidator,
    AuthorFormatValidator,
    ConsistencyValidator,
    CrossReferenceValidator,
    DOIValidator,
    EntryKeyValidator,
    FieldFormatValidator,
    ISBNValidator,
    ISSNValidator,
    RequiredFieldValidator,
    URLValidator,
    Validator,
    ValidatorRegistry,
    get_validator_registry,
)

__all__ = [
    # Fields and types
    "EntryType",
    "FieldRequirements",
    "ALL_FIELDS",
    "STANDARD_FIELDS",
    "MODERN_FIELDS",
    "COMPAT_FIELDS",
    # BibTeX processing
    "BibtexEncoder",
    "BibtexDecoder",
    # Builders
    "EntryBuilder",
    "CollectionBuilder",
    # Name parsing
    "NameParser",
    "ParsedName",
    # Sorting
    "SortKeyGenerator",
    "LabelGenerator",
    # String abbreviations
    "StringRegistry",
    # Title processing
    "TitleProcessor",
    # Models
    "Entry",
    "Collection",
    "Tag",
    "ValidationError",
    "ErrorSeverity",
    # Validators
    "Validator",
    "EntryKeyValidator",
    "RequiredFieldValidator",
    "FieldFormatValidator",
    "DOIValidator",
    "ISBNValidator",
    "ISSNValidator",
    "URLValidator",
    "AuthorFormatValidator",
    "AbstractLengthValidator",
    "CrossReferenceValidator",
    "ConsistencyValidator",
    "DuplicateDetector",
    "ValidatorRegistry",
    "get_validator_registry",
]
