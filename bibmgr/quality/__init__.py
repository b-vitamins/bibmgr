"""Quality control system for bibliography entries.

This package provides comprehensive quality checking including:
- Field validation with format checking (ISBN, ISSN, DOI, ORCID, ArXiv, etc.)
- Consistency checks across entries (duplicates, cross-references, orphans)
- File integrity verification with async support
- Quality reporting in multiple formats (JSON, HTML, Markdown, CSV)
- Validation result caching for performance
- Field correlation validation
"""

from bibmgr.quality.consistency import (
    ConsistencyChecker,
    ConsistencyIssue,
    ConsistencyReport,
    CrossReferenceValidator,
    DuplicateDetector,
    OrphanDetector,
)
from bibmgr.quality.engine import (
    CorrelationValidator,
    QualityEngine,
    QualityMetrics,
    QualityReport,
    RuleSet,
    RuleType,
    ValidationCache,
    ValidationRule,
)
from bibmgr.quality.integrity import (
    BackupVerifier,
    FileIntegrityChecker,
    FileIssue,
    IntegrityReport,
    PDFValidator,
)
from bibmgr.quality.reporting import (
    CSVReporter,
    HTMLReporter,
    JSONReporter,
    MarkdownReporter,
    ReportFormatter,
)
from bibmgr.quality.validators import (
    ArXivValidator,
    AuthorValidator,
    DateValidator,
    DOIValidator,
    FieldValidator,
    ISSNValidator,
    ISBNValidator,
    ORCIDValidator,
    PageRangeValidator,
    URLValidator,
    ValidationResult,
    ValidationSeverity,
)

__all__ = [
    # Validators
    "FieldValidator",
    "ISBNValidator",
    "ISSNValidator",
    "DOIValidator",
    "ORCIDValidator",
    "ArXivValidator",
    "URLValidator",
    "DateValidator",
    "AuthorValidator",
    "PageRangeValidator",
    "ValidationResult",
    "ValidationSeverity",
    # Consistency
    "ConsistencyChecker",
    "ConsistencyReport",
    "ConsistencyIssue",
    "CrossReferenceValidator",
    "DuplicateDetector",
    "OrphanDetector",
    # Integrity
    "FileIntegrityChecker",
    "IntegrityReport",
    "FileIssue",
    "PDFValidator",
    "BackupVerifier",
    # Engine
    "QualityEngine",
    "QualityReport",
    "QualityMetrics",
    "ValidationRule",
    "RuleSet",
    "RuleType",
    "ValidationCache",
    "CorrelationValidator",
    # Reporting
    "ReportFormatter",
    "JSONReporter",
    "HTMLReporter",
    "MarkdownReporter",
    "CSVReporter",
]
