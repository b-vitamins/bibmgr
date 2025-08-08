"""Comprehensive tests for file location functionality.

These tests are implementation-agnostic and focus on the expected behavior
of file-based search and location features.
"""

import tempfile
from pathlib import Path

# Module-level skip removed - implementation ready


class TestFileMatch:
    """Test file match model."""

    def test_file_match_creation(self):
        """Should create file match with basic info."""
        from bibmgr.search.locate import FileMatch

        match = FileMatch(
            entry_key="test2024",
            file_path=Path("/papers/test.pdf"),
            exists=True,
            size_bytes=1024000,
        )

        assert match.entry_key == "test2024"
        assert match.file_path == Path("/papers/test.pdf")
        assert match.exists
        assert match.size_bytes == 1024000

    def test_file_match_properties(self):
        """Should provide convenient properties."""
        from bibmgr.search.locate import FileMatch

        match = FileMatch(
            entry_key="test",
            file_path=Path("/docs/papers/machine_learning.pdf"),
            exists=True,
        )

        assert match.basename == "machine_learning.pdf"
        assert match.extension == ".pdf"

    def test_missing_file_match(self):
        """Should handle missing files."""
        from bibmgr.search.locate import FileMatch

        match = FileMatch(
            entry_key="test",
            file_path=Path("/nonexistent/file.pdf"),
            exists=False,
            size_bytes=None,
        )

        assert not match.exists
        assert match.size_bytes is None


class TestLocateResult:
    """Test locate result model."""

    def test_empty_result(self):
        """Should handle empty results."""
        from bibmgr.search.locate import LocateResult

        result = LocateResult(query="*.pdf", matches=[], total_found=0, missing_count=0)

        assert result.query == "*.pdf"
        assert result.matches == []
        assert result.total_found == 0
        assert result.existing_files == []
        assert result.missing_files == []

    def test_result_with_matches(self):
        """Should store file matches."""
        from bibmgr.search.locate import FileMatch, LocateResult

        matches = [
            FileMatch("entry1", Path("/a.pdf"), exists=True),
            FileMatch("entry2", Path("/b.pdf"), exists=False),
            FileMatch("entry3", Path("/c.pdf"), exists=True),
        ]

        result = LocateResult(
            query="*.pdf", matches=matches, total_found=3, missing_count=1
        )

        assert len(result.matches) == 3
        assert result.total_found == 3
        assert result.missing_count == 1

    def test_existing_files_filter(self):
        """Should filter existing files."""
        from bibmgr.search.locate import FileMatch, LocateResult

        matches = [
            FileMatch("e1", Path("/a.pdf"), exists=True),
            FileMatch("e2", Path("/b.pdf"), exists=False),
            FileMatch("e3", Path("/c.pdf"), exists=True),
        ]

        result = LocateResult("test", matches, 3, 1)

        existing = result.existing_files
        assert len(existing) == 2
        assert all(m.exists for m in existing)

    def test_missing_files_filter(self):
        """Should filter missing files."""
        from bibmgr.search.locate import FileMatch, LocateResult

        matches = [
            FileMatch("e1", Path("/a.pdf"), exists=True),
            FileMatch("e2", Path("/b.pdf"), exists=False),
            FileMatch("e3", Path("/c.pdf"), exists=False),
        ]

        result = LocateResult("test", matches, 3, 2)

        missing = result.missing_files
        assert len(missing) == 2
        assert all(not m.exists for m in missing)


class TestFileLocatorInitialization:
    """Test file locator initialization."""

    def test_default_initialization(self):
        """Should initialize with default search paths."""
        from bibmgr.search.locate import FileLocator

        locator = FileLocator()

        # Should have some default paths
        assert isinstance(locator.base_paths, list)
        # Only existing paths should be included
        assert all(p.exists() for p in locator.base_paths)

    def test_custom_paths(self):
        """Should use custom search paths."""
        from bibmgr.search.locate import FileLocator

        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = Path(tmpdir) / "dir1"
            path2 = Path(tmpdir) / "dir2"
            path1.mkdir()
            path2.mkdir()

            locator = FileLocator(base_paths=[path1, path2])

            assert len(locator.base_paths) == 2
            assert path1 in locator.base_paths
            assert path2 in locator.base_paths

    def test_filter_nonexistent_paths(self):
        """Should filter out non-existent paths."""
        from bibmgr.search.locate import FileLocator

        with tempfile.TemporaryDirectory() as tmpdir:
            exists = Path(tmpdir) / "exists"
            exists.mkdir()
            nonexistent = Path(tmpdir) / "nonexistent"

            locator = FileLocator(base_paths=[exists, nonexistent])

            assert len(locator.base_paths) == 1
            assert exists in locator.base_paths
            assert nonexistent not in locator.base_paths


class TestGlobPatternLocate:
    """Test glob pattern file location."""

    def test_simple_glob_pattern(self):
        """Should find files with simple glob pattern."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        locator = FileLocator()

        entries = [
            Entry(
                key="test1",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/machine_learning.pdf"),
            ),
            Entry(
                key="test2",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/deep_learning.pdf"),
            ),
            Entry(
                key="test3",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/database.txt"),
            ),
        ]

        result = locator.locate("*.pdf", entries)

        assert result.total_found == 2
        assert all(m.file_path.suffix == ".pdf" for m in result.matches)

    def test_complex_glob_pattern(self):
        """Should handle complex glob patterns."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        locator = FileLocator()

        entries = [
            Entry(
                key="ml1",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/2024/ml_paper.pdf"),
            ),
            Entry(
                key="ml2",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/2023/ml_study.pdf"),
            ),
            Entry(
                key="db1",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/2024/db_paper.pdf"),
            ),
        ]

        result = locator.locate("*/ml_*.pdf", entries)

        assert result.total_found == 2
        assert all("ml_" in m.file_path.name for m in result.matches)

    def test_basename_glob(self):
        """Should match against basename."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        locator = FileLocator()

        entries = [
            Entry(
                key="test1",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/long/path/to/paper_2024.pdf"),
            ),
            Entry(
                key="test2",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/other/path/paper_2023.pdf"),
            ),
        ]

        result = locator.locate("paper_*.pdf", entries)

        assert result.total_found == 2


class TestRegexLocate:
    """Test regex pattern file location."""

    def test_simple_regex(self):
        """Should find files with regex pattern."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        locator = FileLocator()

        entries = [
            Entry(
                key="test1",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/paper_2024.pdf"),
            ),
            Entry(
                key="test2",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/study_2024.pdf"),
            ),
            Entry(
                key="test3",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/paper_2023.pdf"),
            ),
        ]

        result = locator.locate(r"paper_\d{4}\.pdf", entries, use_regex=True)

        assert result.total_found == 2
        assert all("paper_" in m.file_path.name for m in result.matches)

    def test_complex_regex(self):
        """Should handle complex regex patterns."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        locator = FileLocator()

        entries = [
            Entry(
                key="valid1",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/smith2024neural.pdf"),
            ),
            Entry(
                key="valid2",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/jones2023machine.pdf"),
            ),
            Entry(
                key="invalid",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/report_final.pdf"),
            ),
        ]

        # Match author-year-topic pattern
        result = locator.locate(r"[a-z]+\d{4}[a-z]+\.pdf", entries, use_regex=True)

        assert result.total_found == 2

    def test_case_insensitive_regex(self):
        """Regex should be case-insensitive."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        locator = FileLocator()

        entries = [
            Entry(
                key="test1",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/Paper.PDF"),
            ),
            Entry(
                key="test2",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/papers/PAPER.pdf"),
            ),
        ]

        result = locator.locate(r"paper\.pdf", entries, use_regex=True)

        assert result.total_found == 2


class TestExtensionFiltering:
    """Test file extension filtering."""

    def test_single_extension_filter(self):
        """Should filter by single extension."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        locator = FileLocator()

        entries = [
            Entry(
                key="pdf1", type=EntryType.ARTICLE, title="T", pdf_path=Path("/a.pdf")
            ),
            Entry(
                key="pdf2", type=EntryType.ARTICLE, title="T", pdf_path=Path("/b.pdf")
            ),
            Entry(key="ps", type=EntryType.ARTICLE, title="T", pdf_path=Path("/c.ps")),
            Entry(
                key="txt", type=EntryType.ARTICLE, title="T", pdf_path=Path("/d.txt")
            ),
        ]

        result = locator.locate("*", entries, extensions=[".pdf"])

        assert result.total_found == 2
        assert all(m.file_path.suffix == ".pdf" for m in result.matches)

    def test_multiple_extension_filter(self):
        """Should filter by multiple extensions."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        locator = FileLocator()

        entries = [
            Entry(
                key="pdf", type=EntryType.ARTICLE, title="T", pdf_path=Path("/a.pdf")
            ),
            Entry(key="ps", type=EntryType.ARTICLE, title="T", pdf_path=Path("/b.ps")),
            Entry(
                key="txt", type=EntryType.ARTICLE, title="T", pdf_path=Path("/c.txt")
            ),
            Entry(
                key="doc", type=EntryType.ARTICLE, title="T", pdf_path=Path("/d.doc")
            ),
        ]

        result = locator.locate("*", entries, extensions=[".pdf", ".ps"])

        assert result.total_found == 2
        assert all(m.file_path.suffix in [".pdf", ".ps"] for m in result.matches)

    def test_case_insensitive_extensions(self):
        """Extension filtering should be case-insensitive."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        locator = FileLocator()

        entries = [
            Entry(
                key="lower", type=EntryType.ARTICLE, title="T", pdf_path=Path("/a.pdf")
            ),
            Entry(
                key="upper", type=EntryType.ARTICLE, title="T", pdf_path=Path("/b.PDF")
            ),
            Entry(
                key="mixed", type=EntryType.ARTICLE, title="T", pdf_path=Path("/c.Pdf")
            ),
        ]

        result = locator.locate("*", entries, extensions=[".pdf"])

        assert result.total_found == 3


class TestExistenceChecking:
    """Test file existence verification."""

    def test_existence_check_enabled(self):
        """Should check file existence when enabled."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create one file
            existing = Path(tmpdir) / "exists.pdf"
            existing.write_text("content")

            locator = FileLocator()

            entries = [
                Entry(
                    key="exists", type=EntryType.ARTICLE, title="T", pdf_path=existing
                ),
                Entry(
                    key="missing",
                    type=EntryType.ARTICLE,
                    title="T",
                    pdf_path=Path(tmpdir) / "missing.pdf",
                ),
            ]

            result = locator.locate("*.pdf", entries, check_existence=True)

            assert result.total_found == 2
            assert result.missing_count == 1
            assert result.existing_files[0].file_path == existing
            assert (
                result.existing_files[0].size_bytes
                and result.existing_files[0].size_bytes > 0
            )

    def test_existence_check_disabled(self):
        """Should skip existence check when disabled."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        locator = FileLocator()

        entries = [
            Entry(
                key="test",
                type=EntryType.ARTICLE,
                title="T",
                pdf_path=Path("/nonexistent/file.pdf"),
            ),
        ]

        result = locator.locate("*.pdf", entries, check_existence=False)

        assert result.total_found == 1
        assert not result.matches[0].exists  # Default to False
        assert result.matches[0].size_bytes is None

    def test_file_size_detection(self):
        """Should detect file sizes for existing files."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with different sizes
            file1 = Path(tmpdir) / "small.pdf"
            file1.write_bytes(b"x" * 100)

            file2 = Path(tmpdir) / "large.pdf"
            file2.write_bytes(b"x" * 10000)

            locator = FileLocator()

            entries = [
                Entry(key="small", type=EntryType.ARTICLE, title="T", pdf_path=file1),
                Entry(key="large", type=EntryType.ARTICLE, title="T", pdf_path=file2),
            ]

            result = locator.locate("*.pdf", entries, check_existence=True)

            small_match = next(m for m in result.matches if m.entry_key == "small")
            large_match = next(m for m in result.matches if m.entry_key == "large")

            assert small_match.size_bytes == 100
            assert large_match.size_bytes == 10000


class TestFindByBasename:
    """Test finding files by exact basename."""

    def test_exact_basename_match(self):
        """Should find files with exact basename."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        locator = FileLocator()

        entries = [
            Entry(
                key="match1",
                type=EntryType.ARTICLE,
                title="T",
                pdf_path=Path("/path/to/target.pdf"),
            ),
            Entry(
                key="match2",
                type=EntryType.ARTICLE,
                title="T",
                pdf_path=Path("/other/target.pdf"),
            ),
            Entry(
                key="nomatch",
                type=EntryType.ARTICLE,
                title="T",
                pdf_path=Path("/path/different.pdf"),
            ),
        ]

        result = locator.find_by_basename("target.pdf", entries)

        assert result.total_found == 2
        assert all(m.file_path.name == "target.pdf" for m in result.matches)

    def test_no_basename_match(self):
        """Should handle no matches."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        locator = FileLocator()

        entries = [
            Entry(
                key="test",
                type=EntryType.ARTICLE,
                title="T",
                pdf_path=Path("/path/file.pdf"),
            ),
        ]

        result = locator.find_by_basename("nonexistent.pdf", entries)

        assert result.total_found == 0
        assert result.matches == []


class TestOrphanedFiles:
    """Test finding orphaned files."""

    def test_find_orphaned_files(self):
        """Should find PDFs not referenced by any entry."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create PDF files
            referenced = tmppath / "referenced.pdf"
            referenced.write_text("ref")

            orphan1 = tmppath / "orphan1.pdf"
            orphan1.write_text("o1")

            orphan2 = tmppath / "subdir" / "orphan2.pdf"
            orphan2.parent.mkdir()
            orphan2.write_text("o2")

            # Create entries
            entries = [
                Entry(
                    key="ref", type=EntryType.ARTICLE, title="T", pdf_path=referenced
                ),
            ]

            locator = FileLocator(base_paths=[tmppath])
            orphaned = locator.find_orphaned_files(entries)

            # Should find orphaned files
            orphaned_names = {f.name for f in orphaned}
            assert "orphan1.pdf" in orphaned_names
            assert "orphan2.pdf" in orphaned_names
            assert "referenced.pdf" not in orphaned_names

    def test_no_orphaned_files(self):
        """Should handle case with no orphaned files."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create referenced file
            ref_file = tmppath / "ref.pdf"
            ref_file.write_text("content")

            entries = [
                Entry(key="ref", type=EntryType.ARTICLE, title="T", pdf_path=ref_file),
            ]

            locator = FileLocator(base_paths=[tmppath])
            orphaned = locator.find_orphaned_files(entries)

            assert orphaned == []


class TestVerifyAll:
    """Test verifying all file references."""

    def test_verify_all_files(self):
        """Should verify all file references."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create some files
            exists1 = tmppath / "exists1.pdf"
            exists1.write_bytes(b"x" * 500)

            exists2 = tmppath / "exists2.pdf"
            exists2.write_bytes(b"y" * 1000)

            missing = tmppath / "missing.pdf"

            entries = [
                Entry(key="e1", type=EntryType.ARTICLE, title="T", pdf_path=exists1),
                Entry(key="e2", type=EntryType.ARTICLE, title="T", pdf_path=exists2),
                Entry(key="m", type=EntryType.ARTICLE, title="T", pdf_path=missing),
            ]

            locator = FileLocator()
            verification = locator.verify_all(entries)

            assert len(verification["existing"]) == 2
            assert len(verification["missing"]) == 1

            # Check existing files have size info
            for match in verification["existing"]:
                assert match.exists
                assert match.size_bytes and match.size_bytes > 0

            # Check missing files
            for match in verification["missing"]:
                assert not match.exists
                assert match.size_bytes is None

    def test_verify_empty_entries(self):
        """Should handle empty entry list."""
        from bibmgr.search.locate import FileLocator

        locator = FileLocator()
        verification = locator.verify_all([])

        assert verification["existing"] == []
        assert verification["missing"] == []


class TestStatistics:
    """Test file statistics generation."""

    def test_file_statistics(self):
        """Should generate file statistics."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create files with different extensions
            pdf1 = tmppath / "file1.pdf"
            pdf1.write_bytes(b"x" * 1024 * 1024)  # 1MB

            pdf2 = tmppath / "file2.pdf"
            pdf2.write_bytes(b"x" * 512 * 1024)  # 512KB

            ps = tmppath / "file.ps"
            ps.write_bytes(b"x" * 256 * 1024)  # 256KB

            missing = tmppath / "missing.pdf"

            entries = [
                Entry(key="p1", type=EntryType.ARTICLE, title="T", pdf_path=pdf1),
                Entry(key="p2", type=EntryType.ARTICLE, title="T", pdf_path=pdf2),
                Entry(key="ps", type=EntryType.ARTICLE, title="T", pdf_path=ps),
                Entry(key="m", type=EntryType.ARTICLE, title="T", pdf_path=missing),
            ]

            locator = FileLocator()
            stats = locator.get_statistics(entries)

            assert stats["total_files"] == 4
            assert stats["existing_files"] == 3
            assert stats["missing_files"] == 1

            # Check size calculation (in MB)
            expected_mb = (1024 + 512 + 256) / 1024  # ~1.75 MB
            assert abs(stats["total_size_mb"] - expected_mb) < 0.01

            # Check extension breakdown
            assert stats["extensions"][".pdf"] == 2
            assert stats["extensions"][".ps"] == 1

    def test_empty_statistics(self):
        """Should handle empty entry list."""
        from bibmgr.search.locate import FileLocator

        locator = FileLocator()
        stats = locator.get_statistics([])

        assert stats["total_files"] == 0
        assert stats["existing_files"] == 0
        assert stats["missing_files"] == 0
        assert stats["total_size_mb"] == 0
        assert stats["extensions"] == {}


class TestCaching:
    """Test file existence caching."""

    def test_existence_caching(self):
        """Should cache file existence checks."""
        from bibmgr.search.locate import FileLocator

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.pdf"
            test_file.write_text("content")

            locator = FileLocator()

            # First check
            exists1 = locator._check_exists(test_file)
            assert exists1

            # Should be cached
            assert test_file in locator._file_cache

            # Delete file
            test_file.unlink()

            # Should still return cached value
            exists2 = locator._check_exists(test_file)
            assert exists2  # Still True from cache

    def test_cache_different_files(self):
        """Should cache multiple file checks."""
        from bibmgr.search.locate import FileLocator

        locator = FileLocator()

        files = [Path(f"/test{i}.pdf") for i in range(5)]

        for f in files:
            locator._check_exists(f)

        # All should be cached
        assert len(locator._file_cache) == 5
        assert all(f in locator._file_cache for f in files)


class TestIntegration:
    """Test complete file location workflows."""

    def test_research_file_management(self):
        """Test typical research file management workflow."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        with tempfile.TemporaryDirectory() as tmpdir:
            papers_dir = Path(tmpdir) / "papers"
            papers_dir.mkdir()

            # Create paper files
            (papers_dir / "2024").mkdir()
            (papers_dir / "2023").mkdir()

            paper_2024_1 = papers_dir / "2024" / "smith2024transformer.pdf"
            paper_2024_1.write_bytes(b"x" * 2000000)

            paper_2024_2 = papers_dir / "2024" / "jones2024bert.pdf"
            paper_2024_2.write_bytes(b"x" * 1500000)

            paper_2023 = papers_dir / "2023" / "doe2023attention.pdf"
            paper_2023.write_bytes(b"x" * 1000000)

            # Missing file
            missing = papers_dir / "2024" / "missing2024.pdf"

            # Create entries
            entries = [
                Entry(
                    key="smith2024",
                    type=EntryType.ARTICLE,
                    title="T",
                    pdf_path=paper_2024_1,
                ),
                Entry(
                    key="jones2024",
                    type=EntryType.ARTICLE,
                    title="T",
                    pdf_path=paper_2024_2,
                ),
                Entry(
                    key="doe2023",
                    type=EntryType.ARTICLE,
                    title="T",
                    pdf_path=paper_2023,
                ),
                Entry(
                    key="missing", type=EntryType.ARTICLE, title="T", pdf_path=missing
                ),
            ]

            locator = FileLocator(base_paths=[papers_dir])

            # Find 2024 papers
            result = locator.locate("*/2024/*.pdf", entries)
            assert result.total_found == 3  # Including missing
            assert result.missing_count == 1

            # Find by author pattern
            result = locator.locate(r"[a-z]+2024[a-z]+\.pdf", entries, use_regex=True)
            assert result.total_found == 2

            # Verify all files
            verification = locator.verify_all(entries)
            assert len(verification["existing"]) == 3
            assert len(verification["missing"]) == 1

            # Get statistics
            stats = locator.get_statistics(entries)
            assert stats["existing_files"] == 3
            assert stats["total_size_mb"] > 4.0  # ~4.5 MB total

    def test_file_organization_check(self):
        """Test checking file organization standards."""
        from bibmgr.search.locate import FileLocator
        from bibmgr.search.models import Entry, EntryType

        # Create entries with various naming patterns
        entries = [
            # Good: author-year-keyword pattern
            Entry(
                key="good1",
                type=EntryType.ARTICLE,
                title="T",
                pdf_path=Path("/papers/smith2024transformer.pdf"),
            ),
            Entry(
                key="good2",
                type=EntryType.ARTICLE,
                title="T",
                pdf_path=Path("/papers/jones2023attention.pdf"),
            ),
            # Bad: non-standard naming
            Entry(
                key="bad1",
                type=EntryType.ARTICLE,
                title="T",
                pdf_path=Path("/papers/paper_final_v2.pdf"),
            ),
            Entry(
                key="bad2",
                type=EntryType.ARTICLE,
                title="T",
                pdf_path=Path("/papers/download.pdf"),
            ),
        ]

        locator = FileLocator()

        # Check standard naming pattern
        standard_pattern = r"[a-z]+\d{4}[a-z]+\.pdf"
        result = locator.locate(standard_pattern, entries, use_regex=True)

        # Should find only properly named files
        assert result.total_found == 2
        matching_keys = {m.entry_key for m in result.matches}
        assert "good1" in matching_keys
        assert "good2" in matching_keys
