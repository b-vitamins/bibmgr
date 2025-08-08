"""Main quality control engine with caching and correlations.

Provides:
- Unified quality checking interface
- Rule-based validation system with custom rules
- Validation result caching with LRU eviction
- Field correlation validation
- Quality metrics and reporting
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import msgspec

from bibmgr.core.models import Entry, EntryType, REQUIRED_FIELDS
from bibmgr.quality.consistency import ConsistencyChecker, ConsistencyReport
from bibmgr.quality.integrity import FileIntegrityChecker, IntegrityReport
from bibmgr.quality.validators import (
    ArXivValidator,
    AuthorValidator,
    DateValidator,
    DOIValidator,
    ISSNValidator,
    ISBNValidator,
    ORCIDValidator,
    PageRangeValidator,
    URLValidator,
    ValidationResult,
    ValidationSeverity,
)


class RuleType(Enum):
    """Types of validation rules."""

    REQUIRED_FIELD = auto()
    FIELD_FORMAT = auto()
    FIELD_CORRELATION = auto()
    CUSTOM = auto()
    CONSISTENCY = auto()
    INTEGRITY = auto()


@dataclass
class ValidationRule:
    """A validation rule."""

    name: str
    rule_type: RuleType
    field: Optional[str] = None
    validator: Any = None
    condition: Optional[Callable[[Entry], bool]] = None
    severity: ValidationSeverity = ValidationSeverity.ERROR
    message: Optional[str] = None
    description: Optional[str] = None

    def applies_to(self, entry: Entry) -> bool:
        """Check if rule applies to an entry."""
        if self.condition:
            return self.condition(entry)
        return True

    def validate(self, entry: Entry) -> Optional[ValidationResult]:
        """Validate an entry against this rule."""
        if not self.applies_to(entry):
            return None

        if self.rule_type == RuleType.REQUIRED_FIELD:
            if not self.field:
                return None

            value = getattr(entry, self.field, None)
            if not value:
                return ValidationResult(
                    field=self.field,
                    value=None,
                    is_valid=False,
                    severity=self.severity,
                    message=self.message or f"Required field '{self.field}' is missing",
                )
            return None

        elif self.rule_type == RuleType.FIELD_FORMAT:
            if not self.field or not self.validator:
                return None

            value = getattr(entry, self.field, None)
            if value:
                return self.validator.validate(value)
            return None

        elif self.rule_type == RuleType.CUSTOM:
            if self.validator:
                return self.validator(entry)
            return None

        return None


@dataclass
class RuleSet:
    """A set of validation rules."""

    name: str
    description: Optional[str] = None
    rules: List[ValidationRule] = field(default_factory=list)
    enabled: bool = True

    def add_rule(self, rule: ValidationRule) -> None:
        """Add a rule to the set."""
        self.rules.append(rule)

    def validate(self, entry: Entry) -> List[ValidationResult]:
        """Validate an entry against all rules."""
        if not self.enabled:
            return []

        results = []
        for rule in self.rules:
            result = rule.validate(entry)
            if result:
                results.append(result)

        return results


class CorrelationValidator:
    """Validates correlations between fields."""

    def validate(self, entry: Entry) -> List[ValidationResult]:
        """Check field correlations for an entry."""
        results = []

        # Journal articles should have volume/issue if they have pages
        if entry.type == EntryType.ARTICLE:
            if hasattr(entry, "pages") and entry.pages:
                if not hasattr(entry, "volume") or not entry.volume:
                    results.append(
                        ValidationResult(
                            field="volume",
                            value=None,
                            is_valid=True,
                            severity=ValidationSeverity.SUGGESTION,
                            message="Journal articles with page numbers typically have volume information",
                        )
                    )

        # Conference papers should have booktitle or crossref
        if entry.type == EntryType.INPROCEEDINGS:
            has_booktitle = hasattr(entry, "booktitle") and entry.booktitle
            has_crossref = hasattr(entry, "crossref") and entry.crossref

            if not has_booktitle and not has_crossref:
                results.append(
                    ValidationResult(
                        field="booktitle",
                        value=None,
                        is_valid=True,
                        severity=ValidationSeverity.WARNING,
                        message="Conference papers should have booktitle or crossref",
                    )
                )

        # Books should have publisher if they have ISBN
        if entry.type == EntryType.BOOK:
            if hasattr(entry, "isbn") and entry.isbn:
                if not hasattr(entry, "publisher") or not entry.publisher:
                    results.append(
                        ValidationResult(
                            field="publisher",
                            value=None,
                            is_valid=True,
                            severity=ValidationSeverity.SUGGESTION,
                            message="Books with ISBN typically have publisher information",
                        )
                    )

        # Misc entries with URL should have it validated
        if entry.type == EntryType.MISC:
            if hasattr(entry, "url") and not entry.url:
                results.append(
                    ValidationResult(
                        field="url",
                        value=None,
                        is_valid=False,
                        severity=ValidationSeverity.WARNING,
                        message="URL field is empty",
                    )
                )

        # Thesis entries should have school
        if entry.type in [EntryType.PHDTHESIS, EntryType.MASTERSTHESIS]:
            if not hasattr(entry, "school") or not entry.school:
                results.append(
                    ValidationResult(
                        field="school",
                        value=None,
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message="Thesis entries must have a school",
                    )
                )

        return results


class ValidationCache:
    """LRU cache for validation results."""

    def __init__(self, max_size: int = 1000):
        """Initialize cache.

        Args:
            max_size: Maximum number of cached entries
        """
        self.max_size = max_size
        self.cache: OrderedDict[str, Tuple[List[ValidationResult], datetime]] = (
            OrderedDict()
        )
        self.hits = 0
        self.misses = 0

    def _get_key(self, entry: Entry) -> str:
        """Generate cache key for an entry."""
        # Create hash from entry attributes
        data = msgspec.to_builtins(entry)
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(json_str.encode()).hexdigest()

    def get(self, entry: Entry) -> Optional[List[ValidationResult]]:
        """Get cached results for an entry."""
        key = self._get_key(entry)

        if key in self.cache:
            self.hits += 1
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            results, timestamp = self.cache[key]

            # Check if cache is still valid (1 hour TTL)
            age = (datetime.now() - timestamp).total_seconds()
            if age < 3600:
                return results
            else:
                # Expired
                del self.cache[key]

        self.misses += 1
        return None

    def put(self, entry: Entry, results: List[ValidationResult]) -> None:
        """Cache validation results for an entry."""
        key = self._get_key(entry)

        # Remove oldest if at capacity
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)

        self.cache[key] = (results, datetime.now())

    def clear(self) -> None:
        """Clear the cache."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class QualityMetrics(msgspec.Struct, frozen=True, kw_only=True):
    """Quality metrics for the bibliography."""

    total_entries: int
    valid_entries: int
    entries_with_errors: int
    entries_with_warnings: int
    field_completeness: Dict[str, float] = msgspec.field(default_factory=dict)
    common_issues: Dict[str, int] = msgspec.field(default_factory=dict)
    quality_score: float = 0.0

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "Quality Metrics",
            f"Total entries: {self.total_entries}",
            f"Valid entries: {self.valid_entries} ({self.valid_entries / max(1, self.total_entries) * 100:.1f}%)",
            f"Quality score: {self.quality_score:.1f}/100",
        ]

        if self.entries_with_errors:
            lines.append(f"Entries with errors: {self.entries_with_errors}")

        if self.entries_with_warnings:
            lines.append(f"Entries with warnings: {self.entries_with_warnings}")

        if self.field_completeness:
            lines.append("\nField completeness:")
            for field, pct in sorted(self.field_completeness.items()):
                lines.append(f"  {field}: {pct:.1f}%")

        if self.common_issues:
            lines.append("\nMost common issues:")
            sorted_issues = sorted(
                self.common_issues.items(), key=lambda x: x[1], reverse=True
            )[:5]
            for issue, count in sorted_issues:
                lines.append(f"  {issue}: {count}")

        return "\n".join(lines)


class QualityReport(msgspec.Struct, frozen=True, kw_only=True):
    """Complete quality report."""

    metrics: QualityMetrics
    timestamp: datetime = msgspec.field(default_factory=datetime.now)
    validation_results: Dict[str, List[ValidationResult]] = msgspec.field(
        default_factory=dict
    )
    consistency_report: Optional[ConsistencyReport] = None
    integrity_report: Optional[IntegrityReport] = None
    cache_stats: Optional[Dict[str, Any]] = None

    @property
    def has_errors(self) -> bool:
        """Check if report contains errors."""
        # Check validation errors
        for results in self.validation_results.values():
            if any(
                r.severity == ValidationSeverity.ERROR and not r.is_valid
                for r in results
            ):
                return True

        # Check consistency errors
        if self.consistency_report and self.consistency_report.has_errors:
            return True

        # Check integrity issues
        if self.integrity_report and self.integrity_report.has_issues:
            return True

        return False

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=== Quality Report ===",
            f"Generated: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            self.metrics.to_summary(),
        ]

        if self.consistency_report:
            lines.append("")
            lines.append(self.consistency_report.to_summary())

        if self.integrity_report:
            lines.append("")
            lines.append(self.integrity_report.to_summary())

        # Summary of issues by severity
        severity_counts = defaultdict(int)
        for results in self.validation_results.values():
            for result in results:
                if not result.is_valid:
                    severity_counts[result.severity.name] += 1

        if severity_counts:
            lines.append("\nValidation issues by severity:")
            for severity in ["ERROR", "WARNING", "INFO", "SUGGESTION"]:
                if severity in severity_counts:
                    lines.append(f"  {severity}: {severity_counts[severity]}")

        if self.cache_stats:
            lines.append("\nCache statistics:")
            lines.append(f"  Hit rate: {self.cache_stats.get('hit_rate', 0):.1%}")
            lines.append(f"  Cached entries: {self.cache_stats.get('size', 0)}")

        return "\n".join(lines)


class QualityEngine:
    """Main quality control engine."""

    def __init__(
        self,
        base_path: Optional[Path] = None,
        enable_cache: bool = False,
        cache_size: int = 1000,
        async_mode: bool = False,
    ):
        """Initialize quality engine.

        Args:
            base_path: Base path for file resolution
            enable_cache: Whether to enable validation caching
            cache_size: Maximum cache size
            async_mode: Whether to enable async operations
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.enable_cache = enable_cache
        self.async_mode = async_mode

        # Initialize cache
        self.cache = ValidationCache(cache_size) if enable_cache else None

        # Initialize validators
        self.doi_validator = DOIValidator()
        self.isbn_validator = ISBNValidator()
        self.issn_validator = ISSNValidator()
        self.orcid_validator = ORCIDValidator()
        self.arxiv_validator = ArXivValidator()
        self.url_validator = URLValidator()
        self.date_validator = DateValidator("year")
        self.author_validator = AuthorValidator()
        self.pages_validator = PageRangeValidator()
        self.correlation_validator = CorrelationValidator()

        # Initialize checkers
        self.consistency_checker = ConsistencyChecker()
        self.integrity_checker = FileIntegrityChecker(
            self.base_path, async_mode=async_mode
        )

        # Initialize rule sets
        self.rule_sets = self._create_default_rule_sets()
        self.custom_rules: List[ValidationRule] = []

    def _create_default_rule_sets(self) -> Dict[str, RuleSet]:
        """Create default validation rule sets."""
        rule_sets = {}

        # Required fields rule set
        required_set = RuleSet(
            name="required_fields",
            description="Check required fields for each entry type",
        )

        for entry_type, fields in REQUIRED_FIELDS.items():
            for field_name in fields:
                required_set.add_rule(
                    ValidationRule(
                        name=f"{entry_type.value}_{field_name}_required",
                        rule_type=RuleType.REQUIRED_FIELD,
                        field=field_name,
                        condition=lambda e, t=entry_type: e.type == t,
                        severity=ValidationSeverity.ERROR,
                        message=f"Required field '{field_name}' missing for {entry_type.value}",
                    )
                )

        rule_sets["required_fields"] = required_set

        # Format validation rule set
        format_set = RuleSet(
            name="format_validation", description="Validate field formats"
        )

        # Add all format validators
        validators = [
            ("doi", self.doi_validator, ValidationSeverity.WARNING),
            ("isbn", self.isbn_validator, ValidationSeverity.WARNING),
            ("issn", self.issn_validator, ValidationSeverity.WARNING),
            ("orcid", self.orcid_validator, ValidationSeverity.INFO),
            ("arxiv", self.arxiv_validator, ValidationSeverity.INFO),
            ("url", self.url_validator, ValidationSeverity.WARNING),
            ("year", self.date_validator, ValidationSeverity.ERROR),
            ("author", self.author_validator, ValidationSeverity.WARNING),
            ("pages", self.pages_validator, ValidationSeverity.SUGGESTION),
        ]

        for field_name, validator, severity in validators:
            format_set.add_rule(
                ValidationRule(
                    name=f"{field_name}_format",
                    rule_type=RuleType.FIELD_FORMAT,
                    field=field_name,
                    validator=validator,
                    severity=severity,
                )
            )

        rule_sets["format_validation"] = format_set

        # Field correlation rule set
        correlation_set = RuleSet(
            name="field_correlations", description="Check relationships between fields"
        )

        correlation_set.add_rule(
            ValidationRule(
                name="field_correlations",
                rule_type=RuleType.CUSTOM,
                validator=lambda e: self.correlation_validator.validate(e),
                description="Check field correlations",
            )
        )

        rule_sets["field_correlations"] = correlation_set

        return rule_sets

    def add_custom_rule(
        self,
        name: str,
        validator: Callable[[Entry], Optional[ValidationResult]],
        condition: Optional[Callable[[Entry], bool]] = None,
        description: Optional[str] = None,
    ) -> None:
        """Add a custom validation rule."""
        rule = ValidationRule(
            name=name,
            rule_type=RuleType.CUSTOM,
            validator=validator,
            condition=condition,
            description=description,
        )
        self.custom_rules.append(rule)

    def enable_rule_set(self, name: str) -> None:
        """Enable a rule set."""
        if name in self.rule_sets:
            self.rule_sets[name].enabled = True

    def disable_rule_set(self, name: str) -> None:
        """Disable a rule set."""
        if name in self.rule_sets:
            self.rule_sets[name].enabled = False

    def check_entry(self, entry: Entry) -> List[ValidationResult]:
        """Check a single entry."""
        # Check cache
        if self.enable_cache and self.cache:
            cached = self.cache.get(entry)
            if cached is not None:
                return cached

        results = []

        # Apply rule sets
        for rule_set in self.rule_sets.values():
            if rule_set.enabled:
                rule_results = rule_set.validate(entry)
                # Flatten nested results from correlation validator
                for result in rule_results:
                    if isinstance(result, list):
                        results.extend(result)
                    else:
                        results.append(result)

        # Apply custom rules
        for rule in self.custom_rules:
            result = rule.validate(entry)
            if result:
                results.append(result)

        # Cache results
        if self.enable_cache and self.cache:
            self.cache.put(entry, results)

        return results

    def check_all(
        self,
        entries: List[Entry],
        check_consistency: bool = True,
        check_integrity: bool = True,
        collections: Optional[List[Any]] = None,
        cited_keys: Optional[Set[str]] = None,
    ) -> QualityReport:
        """Run complete quality check."""
        # Validate each entry
        validation_results = {}
        entries_with_errors = set()
        entries_with_warnings = set()
        issue_counts = defaultdict(int)

        for entry in entries:
            results = self.check_entry(entry)
            if results:
                validation_results[entry.key] = results

                for result in results:
                    if not result.is_valid:
                        # Track issue types
                        issue_key = f"{result.field}_{result.severity.name}"
                        issue_counts[issue_key] += 1

                        # Track entries with issues
                        if result.severity == ValidationSeverity.ERROR:
                            entries_with_errors.add(entry.key)
                        elif result.severity == ValidationSeverity.WARNING:
                            entries_with_warnings.add(entry.key)

        # Calculate field completeness
        field_completeness = self._calculate_field_completeness(entries)

        # Calculate quality score
        quality_score = self._calculate_quality_score(
            len(entries), len(entries_with_errors), len(entries_with_warnings)
        )

        # Create metrics
        metrics = QualityMetrics(
            total_entries=len(entries),
            valid_entries=len(entries) - len(entries_with_errors),
            entries_with_errors=len(entries_with_errors),
            entries_with_warnings=len(entries_with_warnings),
            field_completeness=field_completeness,
            common_issues=dict(issue_counts),
            quality_score=quality_score,
        )

        # Run consistency check
        consistency_report = None
        if check_consistency:
            consistency_report = self.consistency_checker.check(
                entries, collections, cited_keys
            )

        # Run integrity check
        integrity_report = None
        if check_integrity:
            integrity_report = self.integrity_checker.check_all_entries(entries)

        # Get cache stats
        cache_stats = None
        if self.cache:
            cache_stats = {
                "hit_rate": self.cache.hit_rate,
                "size": len(self.cache.cache),
                "hits": self.cache.hits,
                "misses": self.cache.misses,
            }

        return QualityReport(
            metrics=metrics,
            validation_results=validation_results,
            consistency_report=consistency_report,
            integrity_report=integrity_report,
            cache_stats=cache_stats,
        )

    async def check_all_async(
        self,
        entries: List[Entry],
        check_consistency: bool = True,
        check_integrity: bool = True,
        collections: Optional[List[Any]] = None,
        cited_keys: Optional[Set[str]] = None,
    ) -> QualityReport:
        """Run complete quality check asynchronously."""
        if not self.async_mode:
            return self.check_all(
                entries, check_consistency, check_integrity, collections, cited_keys
            )

        # Validate entries asynchronously
        validation_tasks = [self._check_entry_async(entry) for entry in entries]
        validation_results_list = await asyncio.gather(*validation_tasks)

        # Process results
        validation_results = {}
        entries_with_errors = set()
        entries_with_warnings = set()
        issue_counts = defaultdict(int)

        for entry, results in zip(entries, validation_results_list):
            if results:
                validation_results[entry.key] = results

                for result in results:
                    if not result.is_valid:
                        issue_key = f"{result.field}_{result.severity.name}"
                        issue_counts[issue_key] += 1

                        if result.severity == ValidationSeverity.ERROR:
                            entries_with_errors.add(entry.key)
                        elif result.severity == ValidationSeverity.WARNING:
                            entries_with_warnings.add(entry.key)

        # Calculate metrics
        field_completeness = self._calculate_field_completeness(entries)
        quality_score = self._calculate_quality_score(
            len(entries), len(entries_with_errors), len(entries_with_warnings)
        )

        metrics = QualityMetrics(
            total_entries=len(entries),
            valid_entries=len(entries) - len(entries_with_errors),
            entries_with_errors=len(entries_with_errors),
            entries_with_warnings=len(entries_with_warnings),
            field_completeness=field_completeness,
            common_issues=dict(issue_counts),
            quality_score=quality_score,
        )

        # Run async checks
        tasks = []

        if check_consistency:
            tasks.append(
                self._check_consistency_async(entries, collections, cited_keys)
            )

        if check_integrity:
            tasks.append(self.integrity_checker.check_all_entries_async(entries))

        async_results = await asyncio.gather(*tasks) if tasks else []

        consistency_report = None
        integrity_report = None

        for result in async_results:
            if isinstance(result, ConsistencyReport):
                consistency_report = result
            elif isinstance(result, IntegrityReport):
                integrity_report = result

        # Get cache stats
        cache_stats = None
        if self.cache:
            cache_stats = {
                "hit_rate": self.cache.hit_rate,
                "size": len(self.cache.cache),
                "hits": self.cache.hits,
                "misses": self.cache.misses,
            }

        return QualityReport(
            metrics=metrics,
            validation_results=validation_results,
            consistency_report=consistency_report,
            integrity_report=integrity_report,
            cache_stats=cache_stats,
        )

    async def _check_entry_async(self, entry: Entry) -> List[ValidationResult]:
        """Check entry asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.check_entry, entry)

    async def _check_consistency_async(
        self,
        entries: List[Entry],
        collections: Optional[List[Any]],
        cited_keys: Optional[Set[str]],
    ) -> ConsistencyReport:
        """Check consistency asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.consistency_checker.check, entries, collections, cited_keys
        )

    def _calculate_field_completeness(self, entries: List[Entry]) -> Dict[str, float]:
        """Calculate field completeness percentages."""
        if not entries:
            return {}

        field_counts = defaultdict(int)
        field_totals = defaultdict(int)

        important_fields = [
            "title",
            "author",
            "year",
            "doi",
            "url",
            "abstract",
            "journal",
            "booktitle",
            "publisher",
            "pages",
            "volume",
            "isbn",
            "issn",
        ]

        for entry in entries:
            for field_name in important_fields:
                field_totals[field_name] += 1
                if hasattr(entry, field_name) and getattr(entry, field_name):
                    field_counts[field_name] += 1

        return {
            field: (count / field_totals[field] * 100) if field_totals[field] > 0 else 0
            for field, count in field_counts.items()
            if field_totals[field] > 0  # Only include fields that apply to some entries
        }

    def _calculate_quality_score(self, total: int, errors: int, warnings: int) -> float:
        """Calculate overall quality score."""
        if total == 0:
            return 100.0

        # Base score from valid entries
        valid = total - errors
        score = (valid / total) * 100

        # Minor penalty for warnings
        warning_penalty = min(warnings * 0.5, 20)  # Max 20 point penalty
        score = max(0, score - warning_penalty)

        return round(score, 1)
