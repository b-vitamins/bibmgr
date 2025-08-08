"""Exception classes for notes module."""


class NoteError(Exception):
    """Base exception for note-related errors."""

    pass


class NoteNotFoundError(NoteError):
    """Raised when a note is not found."""

    def __init__(self, note_id: str):
        """Initialize with note ID."""
        self.note_id = note_id
        super().__init__(f"Note not found: {note_id}")


class NoteValidationError(NoteError, ValueError):
    """Raised when note validation fails."""

    def __init__(self, field: str, message: str):
        """Initialize with field and message."""
        self.field = field
        super().__init__(f"Validation error for {field}: {message}")


class QuoteError(Exception):
    """Base exception for quote-related errors."""

    pass


class QuoteNotFoundError(QuoteError):
    """Raised when a quote is not found."""

    def __init__(self, quote_id: str):
        """Initialize with quote ID."""
        self.quote_id = quote_id
        super().__init__(f"Quote not found: {quote_id}")


class QuoteValidationError(QuoteError, ValueError):
    """Raised when quote validation fails."""

    def __init__(self, field: str, message: str):
        """Initialize with field and message."""
        self.field = field
        super().__init__(f"Validation error for {field}: {message}")


class StorageError(Exception):
    """Base exception for storage-related errors."""

    pass


class StorageLockError(StorageError):
    """Raised when storage lock cannot be acquired."""

    def __init__(self, message: str = "Failed to acquire storage lock"):
        """Initialize with message."""
        super().__init__(message)


class StorageCorruptionError(StorageError):
    """Raised when storage corruption is detected."""

    def __init__(self, path: str, details: str = ""):
        """Initialize with path and details."""
        self.path = path
        message = f"Storage corruption detected at {path}"
        if details:
            message += f": {details}"
        super().__init__(message)


class TemplateError(Exception):
    """Base exception for template-related errors."""

    pass


class TemplateNotFoundError(TemplateError, ValueError):
    """Raised when a template is not found."""

    def __init__(self, template_name: str):
        """Initialize with template name."""
        self.template_name = template_name
        super().__init__(f"Template not found: {template_name}")


class TemplateValidationError(TemplateError, ValueError):
    """Raised when template validation fails."""

    def __init__(self, field: str, message: str):
        """Initialize with field and message."""
        self.field = field
        super().__init__(f"Template validation error for {field}: {message}")


class VersionError(Exception):
    """Base exception for version-related errors."""

    pass


class VersionNotFoundError(VersionError, ValueError):
    """Raised when a version is not found."""

    def __init__(self, note_id: str, version: int):
        """Initialize with note ID and version."""
        self.note_id = note_id
        self.version = version
        super().__init__(f"Version {version} not found for note {note_id}")


class ConcurrencyError(Exception):
    """Base exception for concurrency-related errors."""

    pass


class OptimisticLockError(ConcurrencyError):
    """Raised when optimistic locking fails."""

    def __init__(self, note_id: str, expected_version: int, actual_version: int):
        """Initialize with version conflict details."""
        self.note_id = note_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Version conflict for note {note_id}: "
            f"expected v{expected_version}, found v{actual_version}"
        )
