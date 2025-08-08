"""Additional tests to improve quality module coverage."""

import tempfile
from pathlib import Path


from bibmgr.core.models import Entry, EntryType
from bibmgr.quality import (
    # Test additional methods and edge cases
    ArXivValidator,
    AuthorValidator,
    BackupVerifier,
    ConsistencyIssue,
    ConsistencyReport,
    CorrelationValidator,
    CSVReporter,
    DateValidator,
    DOIValidator,
    DuplicateDetector,
    FileIntegrityChecker,
    FileIssue,
    HTMLReporter,
    IntegrityReport,
    ISSNValidator,
    ISBNValidator,
    JSONReporter,
    MarkdownReporter,
    ORCIDValidator,
    OrphanDetector,
    PageRangeValidator,
    PDFValidator,
    QualityMetrics,
    QualityReport,
    RuleSet,
    RuleType,
    URLValidator,
    ValidationCache,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
)


class TestValidatorsCoverage:
    """Additional validator tests for coverage."""

    def test_validators_edge_cases(self):
        """Test edge cases in validators."""
        # ISBN validator with None and wrong types
        isbn = ISBNValidator()
        assert not isbn.validate(None).is_valid
        assert not isbn.validate(123).is_valid
        assert not isbn.validate("").is_valid

        # ISSN validator with None
        issn = ISSNValidator()
        assert not issn.validate(None).is_valid
        assert not issn.validate(123).is_valid

        # DOI validator with None
        doi = DOIValidator()
        assert not doi.validate(None).is_valid
        assert not doi.validate(123).is_valid
        assert not doi.validate("").is_valid

        # ORCID validator with None
        orcid = ORCIDValidator()
        assert not orcid.validate(None).is_valid
        assert not orcid.validate(123).is_valid

        # ArXiv validator with None
        arxiv = ArXivValidator()
        assert not arxiv.validate(None).is_valid
        assert not arxiv.validate(123).is_valid

        # URL validator with None and empty
        url = URLValidator()
        assert not url.validate(None).is_valid
        assert not url.validate(123).is_valid
        assert not url.validate("").is_valid

        # Date validator with None
        date = DateValidator()
        assert not date.validate(None).is_valid

        # Author validator with None
        author = AuthorValidator()
        assert not author.validate(None).is_valid
        assert not author.validate(123).is_valid

        # Page range validator with None
        pages = PageRangeValidator()
        assert not pages.validate(None).is_valid
        assert not pages.validate(123).is_valid
        assert not pages.validate("").is_valid

    def test_validation_result_methods(self):
        """Test ValidationResult methods."""
        result = ValidationResult(
            field="test",
            value="value",
            is_valid=False,
            severity=ValidationSeverity.ERROR,
            message="Test error",
            suggestion="Fix it",
        )

        # Test to_string method
        string = result.to_string()
        assert "[ERROR]" in string
        assert "test" in string
        assert "Test error" in string
        assert "Fix it" in string


class TestConsistencyCoverage:
    """Additional consistency tests for coverage."""

    def test_consistency_issue_methods(self):
        """Test ConsistencyIssue methods."""
        issue = ConsistencyIssue(
            issue_type="test",
            severity=ValidationSeverity.ERROR,
            entries=["entry1", "entry2"],
            message="Test message",
            suggestion="Fix it",
        )

        # Test __str__ and to_string
        string = str(issue)
        assert "[ERROR]" in string
        assert "test" in string
        assert "entry1" in string

        # Test with many entries
        issue_many = ConsistencyIssue(
            issue_type="test",
            severity=ValidationSeverity.WARNING,
            entries=["e1", "e2", "e3", "e4", "e5"],
            message="Many entries",
        )
        string_many = issue_many.to_string()
        assert "5 total" in string_many

    def test_duplicate_detector_methods(self):
        """Test DuplicateDetector edge cases."""
        detector = DuplicateDetector(use_fuzzy=False)

        # Test with empty entries
        duplicates = detector.find_duplicates([])
        assert len(duplicates) == 0

        # Test exact title matching
        entries = [
            Entry(key="e1", type=EntryType.ARTICLE, title="Test Title"),
            Entry(key="e2", type=EntryType.ARTICLE, title="test title"),
            Entry(key="e3", type=EntryType.ARTICLE, title="Different"),
        ]
        duplicates = detector.find_duplicates(entries)
        assert len(duplicates) > 0

    def test_orphan_detector_edge_cases(self):
        """Test OrphanDetector edge cases."""
        detector = OrphanDetector()

        # Test with empty entries
        orphans = detector.find_orphans([])
        assert len(orphans) == 0

        # Test with collections
        entries = [
            Entry(key="e1", type=EntryType.ARTICLE),
            Entry(key="e2", type=EntryType.ARTICLE),
        ]

        class MockCollection:
            entry_keys = ["e1"]

        orphans = detector.find_orphans(entries, collections=[MockCollection()])
        assert "e2" in orphans
        assert "e1" not in orphans


class TestIntegrityCoverage:
    """Additional integrity tests for coverage."""

    def test_file_issue_methods(self):
        """Test FileIssue methods."""
        issue = FileIssue(
            entry_key="test",
            file_path="/path/to/file",
            issue_type="missing",
            message="File not found",
            suggestion="Check path",
        )

        string = issue.to_string()
        assert "[missing]" in string
        assert "test" in string
        assert "/path/to/file" in string
        assert "Check path" in string

    def test_pdf_validator_edge_cases(self):
        """Test PDFValidator edge cases."""
        validator = PDFValidator(check_structure=True, check_text_extraction=True)

        # Test with non-existent file
        result = validator.validate(Path("/nonexistent"))
        assert not result.is_valid
        assert "not exist" in result.message

        # Test readable check
        assert not validator.check_readable(Path("/nonexistent"))

    def test_backup_verifier_methods(self):
        """Test BackupVerifier methods."""
        with tempfile.TemporaryDirectory() as tmpdir:
            verifier = BackupVerifier(Path(tmpdir))

            # Test with non-existent backup
            status = verifier.verify_backup("nonexistent")
            assert not status["exists"]

            # Test with no backups
            latest = verifier.find_latest_backup()
            assert latest is None

            age_info = verifier.check_backup_age()
            assert not age_info["has_backup"]

    def test_file_integrity_checker_methods(self):
        """Test FileIntegrityChecker additional methods."""
        checker = FileIntegrityChecker()

        # Test compute_checksum with non-existent file
        checksum = checker.compute_checksum(Path("/nonexistent"))
        assert checksum is None

        # Test check_entry_files with various issues
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            file="invalid",  # Invalid format
            pdf_path=Path("/nonexistent.pdf"),
        )
        issues = checker.check_entry_files(entry)
        assert len(issues) > 0


class TestEngineCoverage:
    """Additional engine tests for coverage."""

    def test_validation_rule_methods(self):
        """Test ValidationRule methods."""
        # Test rule that doesn't apply
        rule = ValidationRule(
            name="test",
            rule_type=RuleType.CUSTOM,
            condition=lambda e: False,
            validator=lambda e: None,
        )

        entry = Entry(key="test", type=EntryType.ARTICLE)
        assert not rule.applies_to(entry)
        assert rule.validate(entry) is None

    def test_rule_set_methods(self):
        """Test RuleSet methods."""
        rule_set = RuleSet(name="test", description="Test rules", enabled=False)

        # Test disabled rule set
        entry = Entry(key="test", type=EntryType.ARTICLE)
        results = rule_set.validate(entry)
        assert len(results) == 0

    def test_correlation_validator_edge_cases(self):
        """Test CorrelationValidator edge cases."""
        validator = CorrelationValidator()

        # Test book with ISBN but no publisher
        book = Entry(
            key="book", type=EntryType.BOOK, title="Test Book", isbn="978-0-123456-78-9"
        )
        results = validator.validate(book)
        assert any("publisher" in r.message.lower() for r in results)

        # Test thesis without school
        thesis = Entry(key="thesis", type=EntryType.PHDTHESIS, title="Test Thesis")
        results = validator.validate(thesis)
        assert any("school" in r.message.lower() for r in results)

        # Test MISC with empty URL
        misc = Entry(key="misc", type=EntryType.MISC, title="Test", url="")
        results = validator.validate(misc)
        assert any("url" in r.field.lower() for r in results)

    def test_validation_cache_methods(self):
        """Test ValidationCache methods."""
        cache = ValidationCache(max_size=2)

        # Test cache operations
        entry1 = Entry(key="e1", type=EntryType.ARTICLE, title="Test 1")
        entry2 = Entry(key="e2", type=EntryType.ARTICLE, title="Test 2")
        entry3 = Entry(key="e3", type=EntryType.ARTICLE, title="Test 3")

        results1 = [
            ValidationResult(field="test", value="test", is_valid=True, message="Test")
        ]

        # Test cache miss
        assert cache.get(entry1) is None
        assert cache.misses == 1

        # Test cache put and hit
        cache.put(entry1, results1)
        cached = cache.get(entry1)
        assert cached == results1
        assert cache.hits == 1

        # Test LRU eviction
        cache.put(entry2, results1)
        cache.put(entry3, results1)  # Should evict entry1

        # Test hit rate
        assert cache.hit_rate > 0

        # Test clear
        cache.clear()
        assert len(cache.cache) == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_quality_metrics_methods(self):
        """Test QualityMetrics methods."""
        metrics = QualityMetrics(
            total_entries=10,
            valid_entries=8,
            entries_with_errors=2,
            entries_with_warnings=1,
            quality_score=80.0,
        )

        summary = metrics.to_summary()
        assert "Quality Metrics" in summary
        assert "80.0" in summary

    def test_quality_report_methods(self):
        """Test QualityReport methods."""
        from datetime import datetime

        report = QualityReport(
            metrics=QualityMetrics(
                total_entries=10,
                valid_entries=8,
                entries_with_errors=2,
                entries_with_warnings=1,
                quality_score=80.0,
            ),
            timestamp=datetime.now(),
        )

        # Test has_errors property
        assert not report.has_errors  # No validation results

        # Test to_summary
        summary = report.to_summary()
        assert "Quality Report" in summary


class TestReportingCoverage:
    """Additional reporting tests for coverage."""

    def test_json_reporter_methods(self):
        """Test JSONReporter methods."""
        reporter = JSONReporter(indent=2, include_metadata=False)

        report = QualityReport(
            metrics=QualityMetrics(
                total_entries=10,
                valid_entries=8,
                entries_with_errors=2,
                entries_with_warnings=0,
                quality_score=80.0,
            )
        )

        output = reporter.format(report)
        assert '"total_entries": 10' in output

        # Test save method
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            reporter.save(report, Path(tmp.name))
            assert Path(tmp.name).exists()
            Path(tmp.name).unlink()

    def test_html_reporter_dark_theme(self):
        """Test HTMLReporter with dark theme."""
        reporter = HTMLReporter(theme="dark")

        report = QualityReport(
            metrics=QualityMetrics(
                total_entries=10,
                valid_entries=8,
                entries_with_errors=2,
                entries_with_warnings=0,
                quality_score=80.0,
            )
        )

        output = reporter.format(report)
        assert "#1a1a1a" in output  # Dark background

    def test_markdown_reporter_methods(self):
        """Test MarkdownReporter methods."""
        reporter = MarkdownReporter()

        # Test with consistency and integrity reports
        report = QualityReport(
            metrics=QualityMetrics(
                total_entries=10,
                valid_entries=8,
                entries_with_errors=2,
                entries_with_warnings=0,
                quality_score=80.0,
            ),
            consistency_report=ConsistencyReport(
                total_entries=10,
                orphaned_entries=["orphan1"],
                duplicate_groups=[["dup1", "dup2"]],
                broken_references={"ref1": ["missing"]},
                citation_loops=[["loop1", "loop2"]],
            ),
            integrity_report=IntegrityReport(
                total_files=5,
                valid_files=4,
                missing_files=[FileIssue("e1", "/missing", "missing", "Not found")],
            ),
            cache_stats={"hit_rate": 0.75, "size": 100, "hits": 75, "misses": 25},
        )

        output = reporter.format(report)
        assert "# Quality Report" in output
        assert "Orphaned Entries" in output
        assert "File Integrity" in output
        assert "Cache Statistics" in output

        # Test progress bar generation
        bar = reporter._make_progress_bar(50)
        assert "█" in bar
        assert "░" in bar

    def test_csv_reporter_methods(self):
        """Test CSVReporter methods."""
        reporter = CSVReporter()

        # Test with empty validation results
        report = QualityReport(
            metrics=QualityMetrics(
                total_entries=10,
                valid_entries=10,
                entries_with_errors=0,
                entries_with_warnings=0,
                quality_score=100.0,
            ),
            validation_results={},
        )

        output = reporter.format(report)
        assert "entry_key,field,severity" in output
        assert "SUMMARY" in output
