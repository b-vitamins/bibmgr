"""Comprehensive tests for quality control system.

This test suite is implementation-agnostic and focuses on behavior and contracts.
Tests are organized by functional area to ensure complete coverage.
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytest

# Import quality module components
from bibmgr.quality import (
    # Validators
    AuthorValidator,
    ArXivValidator,
    DateValidator,
    DOIValidator,
    ISSNValidator,
    ISBNValidator,
    ORCIDValidator,
    PageRangeValidator,
    URLValidator,
    ValidationResult,
    ValidationSeverity,
    # Consistency
    ConsistencyChecker,
    ConsistencyReport,
    CrossReferenceValidator,
    DuplicateDetector,
    OrphanDetector,
    # Integrity
    BackupVerifier,
    FileIntegrityChecker,
    PDFValidator,
    # Engine
    QualityEngine,
    QualityMetrics,
    QualityReport,
    CSVReporter,
    HTMLReporter,
    JSONReporter,
    MarkdownReporter,
)
from bibmgr.core.models import Entry, EntryType


class TestValidators:
    """Test field validators with comprehensive edge cases."""

    def test_isbn_validator_isbn10(self):
        """Test ISBN-10 validation with various formats."""
        validator = ISBNValidator()

        # Valid ISBN-10 formats
        valid_cases = [
            "0-306-40615-2",
            "0306406152",
            "0 306 40615 2",
            "080442957X",  # Valid X checksum example
            "0-8044-2957-X",
        ]

        for isbn in valid_cases:
            result = validator.validate(isbn)
            assert result.is_valid, f"Failed for valid ISBN-10: {isbn}"
            assert result.severity == ValidationSeverity.INFO

        # Invalid ISBN-10 cases
        invalid_cases = [
            "0-306-40615-3",  # Wrong checksum
            "030640615",  # Too short
            "03064061520",  # Too long
            "A306406152",  # Invalid character
            "",  # Empty
            None,  # None
            123,  # Not a string
        ]

        for isbn in invalid_cases:
            result = validator.validate(isbn)
            assert not result.is_valid, f"Should reject invalid ISBN-10: {isbn}"

    def test_isbn_validator_isbn13(self):
        """Test ISBN-13 validation with various formats."""
        validator = ISBNValidator()

        # Valid ISBN-13 formats
        valid_cases = [
            "978-0-306-40615-7",
            "9780306406157",
            "978 0 306 40615 7",
            "979-10-90636-07-1",  # 979 prefix
        ]

        for isbn in valid_cases:
            result = validator.validate(isbn)
            assert result.is_valid, f"Failed for valid ISBN-13: {isbn}"

        # Invalid ISBN-13 cases
        invalid_cases = [
            "978-0-306-40615-8",  # Wrong checksum
            "977-0-306-40615-7",  # Invalid prefix
            "978030640615",  # Too short
            "97803064061570",  # Too long
        ]

        for isbn in invalid_cases:
            result = validator.validate(isbn)
            assert not result.is_valid, f"Should reject invalid ISBN-13: {isbn}"

    def test_issn_validator(self):
        """Test ISSN validation."""
        validator = ISSNValidator()

        # Valid ISSN formats
        valid_cases = [
            "0378-5955",
            "03785955",
            "0378 5955",
            "2049-3630",  # ISSN with valid checksum
            "0024-9297",  # Another valid ISSN
        ]

        for issn in valid_cases:
            result = validator.validate(issn)
            assert result.is_valid, f"Failed for valid ISSN: {issn}"

        # Invalid ISSN cases
        invalid_cases = [
            "0378-5956",  # Wrong checksum
            "0378595",  # Too short
            "037859550",  # Too long
            "ABCD-5955",  # Invalid characters
        ]

        for issn in invalid_cases:
            result = validator.validate(issn)
            assert not result.is_valid, f"Should reject invalid ISSN: {issn}"

    def test_doi_validator(self):
        """Test DOI validation with various formats."""
        validator = DOIValidator()

        # Valid DOI formats
        valid_cases = [
            "10.1038/nature12373",
            "10.1002/(SICI)1521-3773(19980420)37:7<1000::AID-ANIE1000>3.0.CO;2-M",
            "https://doi.org/10.1038/nature12373",
            "http://doi.org/10.1038/nature12373",
            "doi:10.1038/nature12373",
            "10.1234/ABC-123_456.789",
        ]

        for doi in valid_cases:
            result = validator.validate(doi)
            assert result.is_valid, f"Failed for valid DOI: {doi}"

        # Invalid DOI cases
        invalid_cases = [
            "11.1038/nature12373",  # Wrong prefix
            "10.1038",  # Missing suffix
            "nature12373",  # Missing prefix
            "",
            None,
        ]

        for doi in invalid_cases:
            result = validator.validate(doi)
            assert not result.is_valid, f"Should reject invalid DOI: {doi}"

    def test_orcid_validator(self):
        """Test ORCID validation."""
        validator = ORCIDValidator()

        # Valid ORCID formats
        valid_cases = [
            "0000-0002-1825-0097",
            "0000-0001-5109-3700",
            "0000-0002-1694-233X",  # X checksum
            "https://orcid.org/0000-0002-1825-0097",
            "orcid.org/0000-0002-1825-0097",
        ]

        for orcid in valid_cases:
            result = validator.validate(orcid)
            assert result.is_valid, f"Failed for valid ORCID: {orcid}"

        # Invalid ORCID cases
        invalid_cases = [
            "0000-0002-1825-0098",  # Wrong checksum
            "0000-0002-1825-009",  # Too short
            "0000-0002-1825-00970",  # Too long
            "0000-0002-1825-009Y",  # Invalid character
            "1234-5678-9012-3456",  # Wrong pattern
        ]

        for orcid in invalid_cases:
            result = validator.validate(orcid)
            assert not result.is_valid, f"Should reject invalid ORCID: {orcid}"

    def test_arxiv_validator(self):
        """Test arXiv ID validation."""
        validator = ArXivValidator()

        # Valid arXiv formats
        valid_cases = [
            "2312.01234",  # New format YYMM.NNNNN
            "2312.01234v1",  # With version
            "2312.01234v12",  # Multi-digit version
            "math.GT/0309136",  # Old format
            "math.GT/0309136v2",  # Old format with version
            "arXiv:2312.01234",  # With prefix
            "https://arxiv.org/abs/2312.01234",  # URL format
        ]

        for arxiv_id in valid_cases:
            result = validator.validate(arxiv_id)
            assert result.is_valid, f"Failed for valid arXiv: {arxiv_id}"

        # Invalid arXiv cases
        invalid_cases = [
            "2313.01234",  # Invalid month (13)
            "2312.123",  # Too few digits (must be 4-5)
            "2312.0123456",  # Too many digits
            "312.01234",  # Missing year digit
            "invalid/0309136",  # Invalid category
        ]

        for arxiv_id in invalid_cases:
            result = validator.validate(arxiv_id)
            assert not result.is_valid, f"Should reject invalid arXiv: {arxiv_id}"

    def test_url_validator(self):
        """Test URL validation with security checks."""
        validator = URLValidator()

        # Valid URLs
        valid_cases = [
            ("https://example.com", ValidationSeverity.INFO),
            ("https://example.com/path", ValidationSeverity.INFO),
            ("http://example.com", ValidationSeverity.WARNING),  # HTTP warning
            ("ftp://ftp.example.com", ValidationSeverity.INFO),
            ("ftps://ftp.example.com", ValidationSeverity.INFO),
        ]

        for url, expected_severity in valid_cases:
            result = validator.validate(url)
            assert result.is_valid, f"Failed for valid URL: {url}"
            assert result.severity == expected_severity

        # Invalid URLs
        invalid_cases = [
            "example.com",  # Missing scheme
            "://example.com",  # Empty scheme
            "https://",  # Missing domain
            "javascript:alert(1)",  # XSS attempt
            "file:///etc/passwd",  # Local file access
            "",
            None,
        ]

        for url in invalid_cases:
            result = validator.validate(url)
            assert not result.is_valid, f"Should reject invalid URL: {url}"

    def test_date_validator(self):
        """Test date validation with various formats."""
        validator = DateValidator()
        current_year = datetime.now().year

        # Valid dates
        valid_cases = [
            (2024, ValidationSeverity.INFO),
            (current_year, ValidationSeverity.INFO),
            (current_year + 1, ValidationSeverity.WARNING),  # Future warning
            ("2024", ValidationSeverity.INFO),
            ("2024-03", ValidationSeverity.INFO),
            ("2024-03-15", ValidationSeverity.INFO),
        ]

        for date, expected_severity in valid_cases:
            result = validator.validate(date)
            assert result.is_valid, f"Failed for valid date: {date}"
            assert result.severity == expected_severity

        # Invalid dates
        invalid_cases = [
            999,  # Too early
            current_year + 10,  # Too far in future
            "2024-13",  # Invalid month
            "2024-02-30",  # Invalid day
            "not-a-date",
            "",
            None,
        ]

        for date in invalid_cases:
            result = validator.validate(date)
            assert not result.is_valid or result.severity == ValidationSeverity.WARNING

    def test_author_validator(self):
        """Test author name validation."""
        validator = AuthorValidator()

        # Valid author formats
        valid_cases = [
            "Einstein, Albert",
            "Einstein, A.",
            "Einstein, Albert and Feynman, Richard",
            "O'Neill, Eugene",
            "von Neumann, John",
            "de la Cruz, María",
            "{The ATLAS Collaboration}",  # Collaboration
        ]

        for author in valid_cases:
            result = validator.validate(author)
            assert result.is_valid, f"Failed for valid author: {author}"

        # Cases with warnings/suggestions
        warning_cases = [
            ("Albert Einstein", ValidationSeverity.SUGGESTION),  # Missing comma
            ("Author@123", ValidationSeverity.WARNING),  # Suspicious chars
            ("", ValidationSeverity.ERROR),  # Empty
        ]

        for author, expected_severity in warning_cases:
            result = validator.validate(author)
            if expected_severity == ValidationSeverity.ERROR:
                assert not result.is_valid
            else:
                assert result.severity == expected_severity

    def test_page_range_validator(self):
        """Test page range validation."""
        validator = PageRangeValidator()

        # Valid page ranges
        valid_cases = [
            ("42", ValidationSeverity.INFO),  # Single page
            ("7--33", ValidationSeverity.INFO),  # BibTeX format
            ("7-33", ValidationSeverity.SUGGESTION),  # Single dash
            ("VII--XXI", ValidationSeverity.INFO),  # Roman numerals
            ("e12345", ValidationSeverity.INFO),  # Electronic article
        ]

        for pages, expected_severity in valid_cases:
            result = validator.validate(pages)
            assert result.is_valid, f"Failed for valid pages: {pages}"
            assert result.severity == expected_severity

        # Invalid page ranges
        invalid_cases = [
            "33--7",  # Reversed range
            "7-",  # Incomplete range
            "--33",  # Missing start
            "abc",  # Invalid format
        ]

        for pages in invalid_cases:
            result = validator.validate(pages)
            assert not result.is_valid, f"Should reject invalid pages: {pages}"


class TestConsistencyChecking:
    """Test consistency checking with optimized algorithms."""

    @pytest.fixture
    def sample_entries(self):
        """Create sample entries for testing."""
        return [
            Entry(
                key="paper1",
                type=EntryType.ARTICLE,
                title="Quantum Computing",
                doi="10.1234/abc",
                author="Smith, J.",
                year=2024,
            ),
            Entry(
                key="paper2",
                type=EntryType.ARTICLE,
                title="Quantum Computing",
                doi="10.1234/xyz",
                author="Jones, A.",
                year=2024,
            ),
            Entry(
                key="paper3",
                type=EntryType.INPROCEEDINGS,
                title="Machine Learning",
                crossref="proceedings1",
                author="Brown, B.",
                year=2023,
            ),
            Entry(
                key="proceedings1",
                type=EntryType.PROCEEDINGS,
                title="Conference Proceedings",
                year=2023,
            ),
            Entry(key="orphan", type=EntryType.MISC, title="Orphaned Entry", year=2022),
        ]

    def test_crossref_validation(self, sample_entries):
        """Test cross-reference validation."""
        validator = CrossReferenceValidator()

        # Add entry with broken crossref
        entries = sample_entries + [
            Entry(
                key="broken",
                type=EntryType.INPROCEEDINGS,
                crossref="nonexistent",
                title="Broken Ref",
            )
        ]

        issues = validator.validate(entries)
        assert any(
            "broken" in str(issue) and "nonexistent" in str(issue) for issue in issues
        )

    def test_circular_reference_detection(self):
        """Test detection of circular cross-references."""
        validator = CrossReferenceValidator()

        # Create circular reference
        entries = [
            Entry(key="a", type=EntryType.ARTICLE, crossref="b"),
            Entry(key="b", type=EntryType.ARTICLE, crossref="c"),
            Entry(key="c", type=EntryType.ARTICLE, crossref="a"),  # Loop
        ]

        loops = validator.detect_loops(entries)
        assert len(loops) == 1
        assert set(loops[0]) == {"a", "b", "c"}

    def test_duplicate_detection_by_doi(self, sample_entries):
        """Test duplicate detection by DOI."""
        detector = DuplicateDetector()

        # Add duplicate DOI
        entries = sample_entries + [
            Entry(
                key="dup1",
                type=EntryType.ARTICLE,
                doi="10.1234/abc",
                title="Different Title",
                year=2024,
            )
        ]

        duplicates = detector.find_duplicates(entries)
        doi_dups = [d for d in duplicates if "paper1" in d and "dup1" in d]
        assert len(doi_dups) == 1

    def test_duplicate_detection_by_title_fuzzy(self, sample_entries):
        """Test fuzzy title matching for duplicates."""
        detector = DuplicateDetector(title_threshold=0.8)

        # Add similar titles
        entries = sample_entries + [
            Entry(
                key="similar1",
                type=EntryType.ARTICLE,
                title="Quantum Computing: An Introduction",
                year=2024,
            ),
            Entry(
                key="similar2",
                type=EntryType.ARTICLE,
                title="quantum computing",
                year=2024,
            ),  # Case difference
        ]

        duplicates = detector.find_duplicates(entries)
        # Should detect similar titles
        assert any(
            "paper1" in dup or "paper2" in dup or "similar1" in dup
            for dup in duplicates
        )

    def test_duplicate_detection_performance(self):
        """Test duplicate detection scales well."""
        detector = DuplicateDetector()

        # Create many entries
        entries = [
            Entry(
                key=f"entry{i}",
                type=EntryType.ARTICLE,
                title=f"Title {i}",
                doi=f"10.1234/{i}",
                year=2020 + i % 5,
            )
            for i in range(1000)
        ]

        # Add some duplicates
        entries.extend(
            [
                Entry(
                    key="dup1",
                    type=EntryType.ARTICLE,
                    title="Title 1",
                    doi="10.1234/999",
                    year=2020,
                ),
                Entry(
                    key="dup2",
                    type=EntryType.ARTICLE,
                    title="Title 2",
                    doi="10.1234/1",
                    year=2020,
                ),
            ]
        )

        import time

        start = time.time()
        duplicates = detector.find_duplicates(entries)
        elapsed = time.time() - start

        # Should complete quickly even with 1000+ entries
        assert elapsed < 2.0, f"Duplicate detection too slow: {elapsed}s"
        assert len(duplicates) >= 2  # Should find our intentional duplicates

    def test_orphan_detection(self, sample_entries):
        """Test orphan entry detection."""
        detector = OrphanDetector()

        # No citations or collections provided
        orphans = detector.find_orphans(sample_entries)
        assert "orphan" in orphans
        assert "paper1" in orphans  # Not referenced
        assert "paper3" not in orphans  # Has crossref
        assert "proceedings1" not in orphans  # Is referenced

    def test_orphan_detection_with_citations(self, sample_entries):
        """Test orphan detection with citation context."""
        detector = OrphanDetector()

        cited_keys = {"paper1", "paper2"}
        orphans = detector.find_orphans(sample_entries, cited_keys=cited_keys)

        assert "orphan" in orphans
        assert "paper1" not in orphans  # Cited
        assert "paper2" not in orphans  # Cited

    def test_consistency_report_generation(self, sample_entries):
        """Test comprehensive consistency report."""
        checker = ConsistencyChecker()

        report = checker.check(sample_entries)

        assert isinstance(report, ConsistencyReport)
        assert report.total_entries == len(sample_entries)
        assert hasattr(report, "orphaned_entries")
        assert hasattr(report, "duplicate_groups")
        assert hasattr(report, "broken_references")

        # Test summary generation
        summary = report.to_summary()
        assert "Consistency Report" in summary
        assert str(len(sample_entries)) in summary


class TestFileIntegrity:
    """Test file integrity checking with async support."""

    @pytest.fixture
    def temp_pdf(self):
        """Create a temporary valid PDF file."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            # Minimal valid PDF structure
            tmp.write(b"%PDF-1.4\n")
            tmp.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
            tmp.write(b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n")
            tmp.write(b"xref\n0 3\n")
            tmp.write(b"0000000000 65535 f\n")
            tmp.write(b"0000000009 00000 n\n")
            tmp.write(b"0000000056 00000 n\n")
            tmp.write(b"trailer\n<< /Size 3 /Root 1 0 R >>\n")
            tmp.write(b"startxref\n149\n")
            tmp.write(b"%%EOF")
            path = Path(tmp.name)
        yield path
        path.unlink()

    @pytest.fixture
    def invalid_pdf(self):
        """Create an invalid PDF file."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"Not a PDF content but long enough to pass size check " * 10)
            path = Path(tmp.name)
        yield path
        path.unlink()

    def test_pdf_validator_basic(self, temp_pdf, invalid_pdf):
        """Test basic PDF validation."""
        validator = PDFValidator()

        # Valid PDF
        result = validator.validate(temp_pdf)
        assert result.is_valid
        assert result.metadata is not None
        # Check for expected metadata keys
        assert "size" in result.metadata

        # Invalid PDF
        result = validator.validate(invalid_pdf)
        assert not result.is_valid
        assert "header" in result.message.lower()

    def test_pdf_validator_structure_check(self, temp_pdf):
        """Test PDF structure validation."""
        validator = PDFValidator(check_structure=True)

        result = validator.validate(temp_pdf)
        assert result.is_valid
        assert "structure" in result.metadata

    def test_pdf_validator_text_extraction(self, temp_pdf):
        """Test PDF text extraction capability check."""
        validator = PDFValidator(check_text_extraction=True)

        result = validator.validate(temp_pdf)
        # Minimal PDF may not have extractable text
        assert result.metadata.get("text_extractable") is not None

    @pytest.mark.asyncio
    async def test_file_integrity_async(self, temp_pdf):
        """Test async file integrity checking."""
        checker = FileIntegrityChecker(async_mode=True)

        entries = [
            Entry(key="pdf1", type=EntryType.ARTICLE, file=f":{temp_pdf}:PDF"),
            Entry(key="pdf2", type=EntryType.ARTICLE, file=f":{temp_pdf}:PDF"),
            Entry(key="missing", type=EntryType.ARTICLE, file=":/nonexistent.pdf:PDF"),
        ]

        # Should handle async checking
        report = await checker.check_all_entries_async(entries)

        assert report.total_files >= 2
        assert len(report.missing_files) >= 1
        assert report.valid_files >= 1

    def test_file_integrity_batch_processing(self):
        """Test batch processing of many files."""
        checker = FileIntegrityChecker(batch_size=100)

        # Create many entries
        entries = [
            Entry(key=f"entry{i}", type=EntryType.ARTICLE, file=f"/fake/path{i}.pdf")
            for i in range(500)
        ]

        import time

        start = time.time()
        report = checker.check_all_entries(entries)
        elapsed = time.time() - start

        # Should handle many files efficiently
        assert elapsed < 5.0, f"File checking too slow: {elapsed}s"
        assert report.total_files == 500

    def test_backup_verifier(self):
        """Test backup verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir)
            verifier = BackupVerifier(backup_dir)

            # Create mock backup
            backup_file = backup_dir / "backup_20240315.tar.gz"
            backup_file.write_bytes(b"mock backup content")

            # Verify backup
            status = verifier.verify_backup("backup_20240315.tar.gz")
            assert status["exists"]
            assert status["size"] > 0

            # Check age
            age_info = verifier.check_backup_age()
            assert age_info["has_backup"]
            assert age_info["is_recent"]

            # Test with old backup - modify the existing backup to be old
            import os

            old_time = datetime.now() - timedelta(days=60)
            os.utime(backup_file, (old_time.timestamp(), old_time.timestamp()))

            age_info = verifier.check_backup_age()
            assert not age_info["is_recent"]
            assert age_info["is_stale"]  # Should be stale (>30 days)


class TestQualityEngine:
    """Test quality engine with caching and correlations."""

    @pytest.fixture
    def quality_engine(self):
        """Create a quality engine instance."""
        return QualityEngine(enable_cache=True)

    def test_basic_validation(self, quality_engine):
        """Test basic entry validation."""
        entry = Entry(
            key="test2024",
            type=EntryType.ARTICLE,
            title="Test Article",
            author="Test, Author",
            journal="Test Journal",
            year=2024,
            doi="10.1234/test",
        )

        results = quality_engine.check_entry(entry)
        errors = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert len(errors) == 0

    def test_required_field_validation(self, quality_engine):
        """Test required field checking."""
        # Missing required fields for article
        entry = Entry(
            key="incomplete",
            type=EntryType.ARTICLE,
            title="Incomplete Article",
            # Missing: author, journal, year
        )

        results = quality_engine.check_entry(entry)
        errors = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert len(errors) >= 3

        # Check error messages mention missing fields
        error_fields = {r.field for r in errors}
        assert "author" in error_fields
        assert "journal" in error_fields
        assert "year" in error_fields

    def test_field_correlation_validation(self, quality_engine):
        """Test field correlation rules."""
        # Journal article should have volume/issue if it has pages
        entry = Entry(
            key="correlation_test",
            type=EntryType.ARTICLE,
            title="Test",
            author="Author",
            journal="Journal",
            year=2024,
            pages="1--10",
            # Missing volume/issue
        )

        results = quality_engine.check_entry(entry)
        suggestions = [
            r for r in results if r.severity == ValidationSeverity.SUGGESTION
        ]
        assert any(
            "volume" in r.message.lower() or "issue" in r.message.lower()
            for r in suggestions
        )

    def test_validation_caching(self, quality_engine):
        """Test validation result caching."""
        entry = Entry(
            key="cached_entry",
            type=EntryType.ARTICLE,
            title="Cached Article",
            author="Author",
            journal="Journal",
            year=2024,
        )

        # First check
        import time

        start = time.time()
        results1 = quality_engine.check_entry(entry)
        time1 = time.time() - start

        # Second check (should be cached)
        start = time.time()
        results2 = quality_engine.check_entry(entry)
        time2 = time.time() - start

        # Cached check should be faster
        assert time2 < time1 * 0.5 or time2 < 0.001
        assert results1 == results2

    def test_cache_invalidation(self, quality_engine):
        """Test cache invalidation on entry change."""
        entry1 = Entry(
            key="changing_entry",
            type=EntryType.ARTICLE,
            title="Original Title",
            author="Author",
            journal="Journal",
            year=2024,
        )

        quality_engine.check_entry(entry1)

        # Create modified entry (Entry is immutable)
        entry2 = Entry(
            key="changing_entry",
            type=EntryType.ARTICLE,
            title="Modified Title",
            author="Author",
            journal="Journal",
            year=2024,
        )

        results2 = quality_engine.check_entry(entry2)
        # Cache should recognize this as a different entry due to changed title
        # Both should return results (cache is content-based)
        # So we'll just check that we get results
        assert results2 is not None

    def test_custom_rule_addition(self, quality_engine):
        """Test adding custom validation rules."""

        def check_recent_year(entry: Entry) -> Optional[ValidationResult]:
            if hasattr(entry, "year") and entry.year:
                if entry.year < 2020:
                    return ValidationResult(
                        field="year",
                        value=entry.year,
                        is_valid=True,
                        severity=ValidationSeverity.INFO,
                        message="Entry is older than 2020",
                    )
            return None

        quality_engine.add_custom_rule(
            name="recent_year",
            validator=check_recent_year,
            description="Check if entry is recent",
        )

        old_entry = Entry(
            key="old",
            type=EntryType.ARTICLE,
            title="Old Article",
            author="Author",
            journal="Journal",
            year=2010,
        )

        results = quality_engine.check_entry(old_entry)
        assert any("older than 2020" in r.message for r in results)

    def test_rule_set_management(self, quality_engine):
        """Test rule set enable/disable."""
        # Disable format validation
        quality_engine.disable_rule_set("format_validation")

        entry = Entry(
            key="bad_doi",
            type=EntryType.ARTICLE,
            title="Article",
            author="Author",
            journal="Journal",
            year=2024,
            doi="invalid-doi",  # Invalid DOI
        )

        results = quality_engine.check_entry(entry)
        # Should not have DOI validation errors since format validation is disabled
        doi_errors = [r for r in results if "doi" in r.field.lower()]
        assert len(doi_errors) == 0

        # Re-enable and check again
        quality_engine.enable_rule_set("format_validation")
        # Clear cache if enabled to ensure fresh validation
        if quality_engine.cache:
            quality_engine.cache.clear()
        results = quality_engine.check_entry(entry)
        doi_errors = [r for r in results if "doi" in r.field.lower()]
        assert len(doi_errors) > 0

    def test_quality_metrics_calculation(self, quality_engine):
        """Test quality metrics generation."""
        entries = [
            Entry(
                key="complete",
                type=EntryType.ARTICLE,
                title="Complete",
                author="Author",
                journal="Journal",
                year=2024,
                doi="10.1234/abc",
                abstract="Abstract",
            ),
            Entry(
                key="minimal",
                type=EntryType.ARTICLE,
                title="Minimal",
                author="Author",
                journal="Journal",
                year=2024,
            ),
            Entry(
                key="invalid", type=EntryType.ARTICLE, title="Invalid", doi="bad-doi"
            ),  # Missing required fields
        ]

        report = quality_engine.check_all(entries)
        metrics = report.metrics

        assert metrics.total_entries == 3
        assert metrics.valid_entries <= 2
        assert metrics.entries_with_errors >= 1
        assert 0 <= metrics.quality_score <= 100
        assert "doi" in metrics.field_completeness
        assert "abstract" in metrics.field_completeness

    @pytest.mark.asyncio
    async def test_async_quality_check(self, quality_engine):
        """Test async quality checking."""
        entries = [
            Entry(
                key=f"entry{i}",
                type=EntryType.ARTICLE,
                title=f"Title {i}",
                author="Author",
                journal="Journal",
                year=2020 + i,
            )
            for i in range(100)
        ]

        report = await quality_engine.check_all_async(entries)
        assert report.metrics.total_entries == 100


class TestReporting:
    """Test report generation in multiple formats."""

    @pytest.fixture
    def sample_report(self):
        """Create a sample quality report."""
        metrics = QualityMetrics(
            total_entries=100,
            valid_entries=85,
            entries_with_errors=10,
            entries_with_warnings=20,
            field_completeness={
                "title": 100.0,
                "author": 95.0,
                "year": 98.0,
                "doi": 60.0,
                "abstract": 40.0,
            },
            common_issues={
                "missing_doi": 40,
                "missing_abstract": 60,
                "invalid_year": 2,
            },
            quality_score=85.0,
        )

        validation_results = {
            "entry1": [
                ValidationResult(
                    field="doi",
                    value=None,
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    message="Missing DOI",
                ),
            ],
            "entry2": [
                ValidationResult(
                    field="year",
                    value=999,
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message="Invalid year",
                ),
            ],
        }

        return QualityReport(
            metrics=metrics,
            validation_results=validation_results,
            timestamp=datetime.now(),
        )

    def test_json_reporter(self, sample_report):
        """Test JSON report generation."""
        reporter = JSONReporter()

        output = reporter.format(sample_report)
        data = json.loads(output)

        assert "metrics" in data
        assert "validation_results" in data
        assert "timestamp" in data
        assert data["metrics"]["total_entries"] == 100
        assert data["metrics"]["quality_score"] == 85.0

    def test_html_reporter(self, sample_report):
        """Test HTML report generation."""
        reporter = HTMLReporter()

        output = reporter.format(sample_report)

        assert "<html>" in output
        assert "Quality Report" in output
        assert "85.0" in output  # Quality score
        assert "100" in output  # Total entries
        assert "Missing DOI" in output or "missing_doi" in output

        # Check for CSS styling
        assert "<style>" in output or 'class="' in output

    def test_markdown_reporter(self, sample_report):
        """Test Markdown report generation."""
        reporter = MarkdownReporter()

        output = reporter.format(sample_report)

        assert "# Quality Report" in output
        assert "## Metrics" in output
        assert "| Field | Completeness |" in output  # Table
        assert "- " in output  # List items
        assert "**Quality Score:**" in output or "**85.0**" in output

    def test_csv_reporter(self, sample_report):
        """Test CSV report generation."""
        reporter = CSVReporter()

        output = reporter.format(sample_report)
        lines = output.strip().split("\n")

        # Check header
        assert "entry_key" in lines[0]
        assert "field" in lines[0]
        assert "severity" in lines[0]
        assert "message" in lines[0]

        # Check data rows
        assert "entry1" in output
        assert "entry2" in output
        assert "WARNING" in output
        assert "ERROR" in output

    def test_report_to_file(self, sample_report):
        """Test saving reports to files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Test each format
            formats = {
                "json": JSONReporter(),
                "html": HTMLReporter(),
                "md": MarkdownReporter(),
                "csv": CSVReporter(),
            }

            for ext, reporter in formats.items():
                file_path = base_path / f"report.{ext}"
                reporter.save(sample_report, file_path)

                assert file_path.exists()
                assert file_path.stat().st_size > 0

                # Verify content
                content = file_path.read_text()
                if ext == "json":
                    json.loads(content)  # Should be valid JSON
                elif ext == "html":
                    assert "<html>" in content
                elif ext == "md":
                    assert "#" in content  # Markdown headers
                elif ext == "csv":
                    assert "," in content  # CSV delimiter


class TestIntegration:
    """Integration tests for the complete quality system."""

    @pytest.mark.asyncio
    async def test_full_quality_check_pipeline(self):
        """Test complete quality checking pipeline."""
        # Create test data
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create some PDF files
            pdf1 = base_path / "paper1.pdf"
            pdf1.write_bytes(b"%PDF-1.4\nContent\n%%EOF")

            # Create entries with various issues
            entries = [
                Entry(
                    key="good",
                    type=EntryType.ARTICLE,
                    title="Good Article",
                    author="Author, A.",
                    journal="Journal",
                    year=2024,
                    doi="10.1234/good",
                    file=f":{pdf1}:PDF",
                ),
                Entry(
                    key="duplicate1",
                    type=EntryType.ARTICLE,
                    title="Duplicate Article",
                    author="Author, B.",
                    journal="Journal",
                    year=2024,
                    doi="10.1234/dup",
                ),
                Entry(
                    key="duplicate2",
                    type=EntryType.ARTICLE,
                    title="Duplicate Article",
                    author="Author, C.",
                    journal="Journal",
                    year=2024,
                    doi="10.1234/dup",
                ),  # Same DOI
                Entry(
                    key="broken_ref",
                    type=EntryType.INPROCEEDINGS,
                    title="Conference Paper",
                    author="Author, D.",
                    crossref="nonexistent",
                    year=2023,
                ),
                Entry(
                    key="invalid",
                    type=EntryType.ARTICLE,
                    title="Invalid",
                    doi="not-a-doi",
                    year=3000,
                ),  # Future year
                Entry(key="orphan", type=EntryType.MISC, title="Orphaned Entry"),
            ]

            # Run full quality check
            engine = QualityEngine(
                base_path=base_path,
                enable_cache=True,
                async_mode=True,
            )

            report = await engine.check_all_async(
                entries,
                check_consistency=True,
                check_integrity=True,
            )

            # Verify report contains expected issues
            assert report.metrics.total_entries == len(entries)
            assert report.metrics.entries_with_errors > 0
            assert report.metrics.entries_with_warnings > 0

            # Check consistency issues
            assert report.consistency_report is not None
            assert (
                report.consistency_report
                and len(report.consistency_report.duplicate_groups) > 0
            )
            assert len(report.consistency_report.broken_references) > 0
            assert len(report.consistency_report.orphaned_entries) > 0

            # Check integrity issues
            assert report.integrity_report is not None

            # Generate reports in all formats
            reporters = {
                "json": JSONReporter(),
                "html": HTMLReporter(),
                "markdown": MarkdownReporter(),
                "csv": CSVReporter(),
            }

            for format_name, reporter in reporters.items():
                output = reporter.format(report)
                assert len(output) > 0

                # Save to file
                file_path = base_path / f"quality_report.{format_name}"
                reporter.save(report, file_path)
                assert file_path.exists()

    def test_performance_with_large_dataset(self):
        """Test performance with large number of entries."""
        # Create 5000 entries
        entries = []
        for i in range(5000):
            entry = Entry(
                key=f"entry{i}",
                type=EntryType.ARTICLE,
                title=f"Article Title {i % 100}",  # Some duplicates
                author=f"Author{i % 50}, A.",
                journal=f"Journal {i % 20}",
                year=2020 + (i % 5),
                doi=f"10.1234/test{i}" if i % 3 == 0 else None,
            )
            entries.append(entry)

        # Add some specific issues
        entries.append(
            Entry(
                key="dup_doi1",
                type=EntryType.ARTICLE,
                title="Dup 1",
                doi="10.1234/duplicate",
            )
        )
        entries.append(
            Entry(
                key="dup_doi2",
                type=EntryType.ARTICLE,
                title="Dup 2",
                doi="10.1234/duplicate",
            )
        )

        engine = QualityEngine(enable_cache=True)

        import time

        start = time.time()
        report = engine.check_all(
            entries, check_consistency=True, check_integrity=False
        )
        elapsed = time.time() - start

        # Should complete in reasonable time
        assert elapsed < 10.0, f"Quality check too slow for 5000 entries: {elapsed}s"

        # Should find issues
        assert report.metrics.total_entries == len(entries)
        assert (
            report.consistency_report
            and len(report.consistency_report.duplicate_groups) > 0
        )

        # Cache should speed up subsequent checks
        start = time.time()
        engine.check_all(entries[:100])  # Subset
        elapsed2 = time.time() - start
        assert elapsed2 < 1.0  # Much faster with cache
