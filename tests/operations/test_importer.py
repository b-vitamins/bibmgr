"""Comprehensive tests for BibTeX import functionality."""

import tempfile
from pathlib import Path


from bibmgr.core.models import Entry, EntryType
from bibmgr.operations.importer import (
    BibTeXImporter,
    ImportResult,
    ImportOptions,
    ConflictStrategy,
    ImportStage,
    EntryProcessor,
    ImportValidator,
)
from bibmgr.operations.crud import EntryOperations
from bibmgr.operations.duplicates import DuplicateDetector


class TestImportResult:
    """Test ImportResult data structure."""

    def test_empty_result(self):
        """Test empty import result."""
        result = ImportResult()

        assert result.total_entries == 0
        assert result.imported == 0
        assert result.skipped == 0
        assert result.failed == 0
        assert result.replaced == 0
        assert result.merged == 0
        assert result.success is False
        assert result.partial_success is False

    def test_successful_result(self):
        """Test successful import result."""
        result = ImportResult()
        result.total_entries = 10
        result.imported = 10

        assert result.success is True
        assert result.partial_success is True
        assert result.imported == 10

    def test_partial_success(self):
        """Test partial success detection."""
        result = ImportResult()
        result.total_entries = 10
        result.imported = 5
        result.failed = 3
        result.skipped = 2

        assert result.success is False  # Not fully successful
        assert result.partial_success is True  # Some imported

    def test_result_tracking(self):
        """Test tracking of individual entries."""
        result = ImportResult()

        result.add_imported("entry1")
        result.add_imported("entry2")
        assert result.imported == 2
        assert result.imported_keys == ["entry1", "entry2"]

        result.add_skipped("entry3", reason="Duplicate")
        assert result.skipped == 1
        assert result.skipped_keys == ["entry3"]
        assert "entry3" in result.skip_reasons

        result.add_failed("entry4", errors=["Invalid field"])
        assert result.failed == 1
        assert result.failed_keys == ["entry4"]
        assert "entry4" in result.error_details

    def test_result_summary(self):
        """Test result summary generation."""
        result = ImportResult()
        result.total_entries = 10
        result.imported = 5
        result.replaced = 2
        result.merged = 1
        result.skipped = 1
        result.failed = 1

        summary = result.get_summary()
        assert "10" in summary
        assert "5" in summary
        assert "imported" in summary.lower()


class TestImportOptions:
    """Test import configuration options."""

    def test_default_options(self):
        """Test default import options."""
        options = ImportOptions()

        assert options.validate is True
        assert options.check_duplicates is True
        assert options.conflict_strategy == ConflictStrategy.ASK
        assert options.dry_run is False
        assert options.force is False

    def test_custom_options(self):
        """Test custom import options."""
        options = ImportOptions(
            validate=False,
            check_duplicates=False,
            conflict_strategy=ConflictStrategy.REPLACE,
            dry_run=True,
            force=True,
        )

        assert options.validate is False
        assert options.check_duplicates is False
        assert options.conflict_strategy == ConflictStrategy.REPLACE
        assert options.dry_run is True
        assert options.force is True


class TestBibTeXImporter:
    """Test BibTeX import functionality."""

    def test_import_simple_file(self, temp_storage, bibtex_content):
        """Test importing a simple BibTeX file."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        # Write content to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex_content)
            filepath = Path(f.name)

        try:
            result = importer.import_file(filepath)

            assert result.success is True
            assert result.imported == 4  # 4 entries in fixture
            assert len(result.imported_keys) == 4

            # Verify entries were imported
            assert ops.read("einstein1905") is not None
            assert ops.read("feynman1965") is not None
            assert ops.read("berners-lee1991") is not None
            assert ops.read("satoshi2008") is not None
        finally:
            filepath.unlink()

    def test_import_with_validation(self, temp_storage, bibtex_content, mock_validator):
        """Test import with validation enabled."""
        validator = mock_validator(should_fail=False)
        ops = EntryOperations(temp_storage, validator=validator)
        importer = BibTeXImporter(ops)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex_content)
            filepath = Path(f.name)

        try:
            options = ImportOptions(validate=True)
            result = importer.import_file(filepath, options=options)

            assert result.success is True
            # Entries are validated twice: once during import validation, once during create
            assert (
                len(validator.validated_entries) == 8
            )  # All 4 entries validated twice
        finally:
            filepath.unlink()

    def test_import_with_invalid_entries(self, temp_storage, invalid_bibtex_content):
        """Test import with invalid entries."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(invalid_bibtex_content)
            filepath = Path(f.name)

        try:
            options = ImportOptions(validate=True, stop_on_error=False)
            result = importer.import_file(filepath, options=options)

            assert result.partial_success  # Some might succeed
            assert result.failed > 0  # Some should fail
            assert len(result.parse_errors) > 0 or len(result.error_details) > 0
        finally:
            filepath.unlink()

    def test_import_with_duplicates(self, temp_storage, duplicate_entries):
        """Test import with duplicate detection."""
        ops = EntryOperations(temp_storage)
        detector = DuplicateDetector()
        importer = BibTeXImporter(ops, duplicate_detector=detector)

        # Add first entry
        ops.create(duplicate_entries[0])

        # Create BibTeX with duplicate
        bibtex = """
        @article{paper2023_new,
            title = {Machine Learning for Climate Prediction},
            author = {Jane Smith and John Doe},
            journal = {Nature Climate Change},
            year = {2023},
            doi = {10.1038/s41558-023-01234}
        }
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex)
            filepath = Path(f.name)

        try:
            options = ImportOptions(
                check_duplicates=True,
                conflict_strategy=ConflictStrategy.SKIP,
            )
            result = importer.import_file(filepath, options=options)

            assert result.skipped >= 1  # Should skip duplicate
            assert "duplicate" in result.get_summary().lower()
        finally:
            filepath.unlink()

    def test_conflict_strategy_skip(self, temp_storage, sample_entries):
        """Test SKIP conflict strategy."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        # Add existing entry
        ops.create(sample_entries[0])

        # Create BibTeX with same key
        bibtex = """
        @book{knuth1984,
            title = {Different Title},
            author = {Different Author},
            publisher = {Different Publisher},
            year = {1999}
        }
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex)
            filepath = Path(f.name)

        try:
            options = ImportOptions(conflict_strategy=ConflictStrategy.SKIP)
            result = importer.import_file(filepath, options=options)

            assert result.skipped == 1
            # Original should remain
            entry = ops.read("knuth1984")
            assert entry and entry.title == sample_entries[0].title
        finally:
            filepath.unlink()

    def test_conflict_strategy_replace(self, temp_storage, sample_entries):
        """Test REPLACE conflict strategy."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        # Add existing entry
        ops.create(sample_entries[0])

        # Create BibTeX with same key
        bibtex = """
        @book{knuth1984,
            title = {Replaced Title},
            author = {Replaced Author},
            publisher = {Replaced Publisher},
            year = {1999}
        }
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex)
            filepath = Path(f.name)

        try:
            options = ImportOptions(conflict_strategy=ConflictStrategy.REPLACE)
            result = importer.import_file(filepath, options=options)

            assert result.replaced == 1
            # Should be replaced
            entry = ops.read("knuth1984")
            assert entry and entry.title == "Replaced Title"
            assert entry and entry.year == 1999
        finally:
            filepath.unlink()

    def test_conflict_strategy_rename(self, temp_storage, sample_entries):
        """Test RENAME conflict strategy."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        # Add existing entry
        ops.create(sample_entries[0])

        # Create BibTeX with same key
        bibtex = """
        @book{knuth1984,
            title = {New Version},
            author = {Donald Knuth},
            publisher = {Publisher},
            year = {1999}
        }
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex)
            filepath = Path(f.name)

        try:
            options = ImportOptions(conflict_strategy=ConflictStrategy.RENAME)
            result = importer.import_file(filepath, options=options)

            assert result.imported == 1
            # Original should remain
            original = ops.read("knuth1984")
            assert original and original.title == sample_entries[0].title

            # New entry with renamed key should exist
            renamed_keys = [k for k in result.imported_keys if k != "knuth1984"]
            assert len(renamed_keys) == 1
            assert "knuth1984" in renamed_keys[0]  # Base key in new name
        finally:
            filepath.unlink()

    def test_conflict_strategy_merge(self, temp_storage):
        """Test MERGE conflict strategy."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        # Add existing entry with partial data
        existing = Entry(
            key="paper2023",
            type=EntryType.ARTICLE,
            title="Existing Paper",
            author="Author One",
            journal="Journal",
            year=2023,
        )
        ops.create(existing)

        # Import entry with additional data
        bibtex = """
        @article{paper2023,
            title = {Existing Paper},
            author = {Author One and Author Two},
            journal = {Journal},
            year = {2023},
            volume = {10},
            pages = {1-20},
            doi = {10.1234/test}
        }
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex)
            filepath = Path(f.name)

        try:
            options = ImportOptions(conflict_strategy=ConflictStrategy.MERGE)
            result = importer.import_file(filepath, options=options)

            assert result.merged == 1
            # Should have merged data
            entry = ops.read("paper2023")
            assert entry and entry.author == "Author One and Author Two"  # Updated
            assert entry and entry.volume == "10"  # Added
            assert entry and entry.pages == "1-20"  # Added
            assert entry and entry.doi == "10.1234/test"  # Added
        finally:
            filepath.unlink()

    def test_import_with_progress_reporting(
        self, temp_storage, bibtex_content, mock_progress_reporter
    ):
        """Test progress reporting during import."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)
        reporter = mock_progress_reporter()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex_content)
            filepath = Path(f.name)

        try:
            options = ImportOptions(progress_reporter=reporter)
            importer.import_file(filepath, options=options)

            assert len(reporter.reports) > 0

            # Check stages were reported
            stages = {r["stage"] for r in reporter.reports}
            assert ImportStage.PARSING in stages
            assert ImportStage.PROCESSING in stages
            assert ImportStage.COMPLETE in stages

            # Check progress increments
            final_report = reporter.reports[-1]
            assert final_report["current"] == final_report["total"]
        finally:
            filepath.unlink()

    def test_import_directory(self, temp_storage):
        """Test importing multiple files from directory."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        # Create temp directory with BibTeX files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create multiple BibTeX files
            for i in range(3):
                content = f"""
                @article{{paper{i},
                    title = {{Paper {i}}},
                    author = {{Author {i}}},
                    journal = {{Journal {i}}},
                    year = {{202{i}}}
                }}
                """
                (tmppath / f"file{i}.bib").write_text(content)

            # Import directory
            results = importer.import_directory(tmppath)

            assert len(results) == 3
            for filepath, result in results.items():
                assert result.success is True
                assert result.imported == 1

            # Verify all entries imported
            for i in range(3):
                assert ops.read(f"paper{i}") is not None

    def test_import_directory_recursive(self, temp_storage):
        """Test recursive directory import."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create nested structure
            (tmppath / "subdir1").mkdir()
            (tmppath / "subdir2").mkdir()

            # Add files at different levels
            (tmppath / "root.bib").write_text("@misc{root, title={Root}}")
            (tmppath / "subdir1" / "sub1.bib").write_text("@misc{sub1, title={Sub1}}")
            (tmppath / "subdir2" / "sub2.bib").write_text("@misc{sub2, title={Sub2}}")

            # Import recursively
            results = importer.import_directory(tmppath, recursive=True)

            assert len(results) == 3
            assert ops.read("root") is not None
            assert ops.read("sub1") is not None
            assert ops.read("sub2") is not None

    def test_import_with_entry_processor(self, temp_storage):
        """Test custom entry processing during import."""
        ops = EntryOperations(temp_storage)

        class CustomProcessor(EntryProcessor):
            def process(self, entry: Entry) -> Entry:
                # Add custom field to all entries
                import msgspec

                entry_dict = msgspec.structs.asdict(entry)
                entry_dict["note"] = "Imported via custom processor"
                return msgspec.convert(entry_dict, Entry)

        processor = CustomProcessor()
        importer = BibTeXImporter(ops, entry_processor=processor)

        bibtex = """
        @article{test,
            title = {Test Article},
            author = {Test Author},
            journal = {Test Journal},
            year = {2023}
        }
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex)
            filepath = Path(f.name)

        try:
            result = importer.import_file(filepath)

            assert result.success is True
            entry = ops.read("test")
            assert entry and entry.note == "Imported via custom processor"
        finally:
            filepath.unlink()

    def test_import_dry_run(self, temp_storage, bibtex_content):
        """Test dry-run import mode."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex_content)
            filepath = Path(f.name)

        try:
            options = ImportOptions(dry_run=True)
            result = importer.import_file(filepath, options=options)

            # Result should show what would happen
            assert result.total_entries == 4
            assert result.imported == 4  # Would import 4

            # But nothing actually imported
            assert ops.read("einstein1905") is None
            assert ops.read("feynman1965") is None
        finally:
            filepath.unlink()

    def test_import_force_mode(self, temp_storage, mock_validator):
        """Test force import bypasses validation."""
        validator = mock_validator(should_fail=True)
        ops = EntryOperations(temp_storage, validator=validator)
        importer = BibTeXImporter(ops)

        bibtex = """
        @misc{forced,
            title = {Forced Entry}
        }
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex)
            filepath = Path(f.name)

        try:
            # Normal import fails validation
            options = ImportOptions(validate=True, force=False)
            result = importer.import_file(filepath, options=options)
            assert result.failed == 1

            # Force import succeeds
            options = ImportOptions(validate=True, force=True)
            result = importer.import_file(filepath, options=options)
            assert result.success is True
            assert ops.read("forced") is not None
        finally:
            filepath.unlink()

    def test_import_error_recovery(self, temp_storage):
        """Test error recovery during import."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        # BibTeX with mix of valid and invalid entries
        bibtex = """
        @article{valid1,
            title = {Valid Entry 1},
            author = {Author 1},
            journal = {Journal 1},
            year = {2023}
        }
        
        @article{,  # Invalid: missing key
            title = {Invalid Entry},
            author = {Author},
            journal = {Journal},
            year = {2023}
        }
        
        @article{valid2,
            title = {Valid Entry 2},
            author = {Author 2},
            journal = {Journal 2},
            year = {2023}
        }
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex)
            filepath = Path(f.name)

        try:
            options = ImportOptions(stop_on_error=False)
            result = importer.import_file(filepath, options=options)

            # Should import valid entries despite errors
            assert result.partial_success is True
            assert result.imported >= 2
            assert result.failed >= 1

            assert ops.read("valid1") is not None
            assert ops.read("valid2") is not None
        finally:
            filepath.unlink()


class TestImportValidator:
    """Test import validation rules."""

    def test_custom_import_validator(self, temp_storage):
        """Test custom validation during import."""
        ops = EntryOperations(temp_storage)

        class YearValidator(ImportValidator):
            def validate(self, entry: Entry) -> list[str]:
                errors = []
                if entry.year and entry.year > 2024:
                    errors.append(f"Year {entry.year} is in the future")
                return errors

        validator = YearValidator()
        importer = BibTeXImporter(ops, import_validator=validator)

        bibtex = """
        @article{future,
            title = {Future Paper},
            author = {Time Traveler},
            journal = {Future Journal},
            year = {2050}
        }
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex)
            filepath = Path(f.name)

        try:
            result = importer.import_file(filepath)

            assert result.failed == 1
            assert "future" in str(result.error_details).lower()
        finally:
            filepath.unlink()


class TestImportEdgeCases:
    """Test edge cases and error conditions."""

    def test_import_nonexistent_file(self, temp_storage):
        """Test importing non-existent file."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        result = importer.import_file(Path("/nonexistent/file.bib"))

        assert result.success is False
        assert len(result.parse_errors) > 0

    def test_import_empty_file(self, temp_storage):
        """Test importing empty file."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write("")  # Empty file
            filepath = Path(f.name)

        try:
            result = importer.import_file(filepath)

            assert result.total_entries == 0
            assert result.success is False
        finally:
            filepath.unlink()

    def test_import_malformed_bibtex(self, temp_storage):
        """Test importing malformed BibTeX."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        bibtex = """
        This is not valid BibTeX content
        @article{missing_braces
            title = {No closing brace}
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(bibtex)
            filepath = Path(f.name)

        try:
            result = importer.import_file(filepath)

            assert result.success is False or result.failed > 0
            assert len(result.parse_errors) > 0
        finally:
            filepath.unlink()

    def test_import_encoding_issues(self, temp_storage):
        """Test handling of encoding issues."""
        ops = EntryOperations(temp_storage)
        importer = BibTeXImporter(ops)

        # BibTeX with UTF-8 characters
        bibtex = """
        @article{utf8,
            title = {Über die Quantenmechanik},
            author = {Schrödinger, Erwin},
            journal = {Annalen der Physik},
            year = {1926}
        }
        """

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".bib", delete=False) as f:
            f.write(bibtex.encode("utf-8"))
            filepath = Path(f.name)

        try:
            result = importer.import_file(filepath)

            assert result.success is True
            entry = ops.read("utf8")
            assert entry and entry.title and "Über" in entry.title
            assert entry and entry.author and "Schrödinger" in entry.author
        finally:
            filepath.unlink()
