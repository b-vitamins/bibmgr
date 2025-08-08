"""Additional tests to improve locate.py coverage to >90%."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from bibmgr.search.locate import FileLocator, FileStatistics
from bibmgr.search.models import Entry, EntryType


class TestFileStatisticsEdgeCases:
    """Test FileStatistics edge cases for better coverage."""

    def test_average_size_with_no_existing_files(self):
        """Should handle average size calculation with no existing files."""
        stats = FileStatistics()
        stats.existing_files = 0
        stats.total_size_bytes = 0

        # Should return 0.0 when no existing files
        assert stats.average_size_bytes == 0.0

    def test_average_size_with_existing_files(self):
        """Should calculate average size with existing files."""
        stats = FileStatistics()
        stats.existing_files = 3
        stats.total_size_bytes = 3000

        # Should calculate average
        assert stats.average_size_bytes == 1000.0

    def test_missing_rate_with_no_total_files(self):
        """Should handle missing rate calculation with no total files."""
        stats = FileStatistics()
        stats.total_files = 0
        stats.missing_files = 0

        # Should return 0.0 when no total files
        assert stats.missing_rate == 0.0

    def test_missing_rate_with_total_files(self):
        """Should calculate missing rate with total files."""
        stats = FileStatistics()
        stats.total_files = 10
        stats.missing_files = 3

        # Should calculate percentage
        assert stats.missing_rate == 30.0


class TestFindByKey:
    """Test find_by_key method."""

    def test_find_by_key_existing(self):
        """Should find file by entry key."""
        locator = FileLocator()

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf_path.write_bytes(b"test content")

            entries = [
                Entry(
                    key="found", type=EntryType.ARTICLE, title="Test", pdf_path=pdf_path
                ),
                Entry(
                    key="other",
                    type=EntryType.ARTICLE,
                    title="Other",
                    pdf_path=Path("/other.pdf"),
                ),
            ]

            match = locator.find_by_key("found", entries)

            assert match is not None
            assert match.entry_key == "found"
            assert match.file_path == pdf_path
            assert match.exists
            assert match.size_bytes == 12  # "test content"

    def test_find_by_key_nonexistent(self):
        """Should return None for non-existent key."""
        locator = FileLocator()

        entries = [
            Entry(
                key="test",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/test.pdf"),
            ),
        ]

        match = locator.find_by_key("nonexistent", entries)
        assert match is None

    def test_find_by_key_no_pdf(self):
        """Should return None if entry has no PDF."""
        locator = FileLocator()

        entries = [
            Entry(key="nopdf", type=EntryType.ARTICLE, title="Test"),
        ]

        match = locator.find_by_key("nopdf", entries)
        assert match is None

    def test_find_by_key_with_os_error(self):
        """Should handle OSError when getting file size."""
        locator = FileLocator()

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf_path.write_bytes(b"content")

            entries = [
                Entry(
                    key="test", type=EntryType.ARTICLE, title="Test", pdf_path=pdf_path
                ),
            ]

            # First call to exists() should succeed, second call to stat() for size should fail
            original_stat = Path.stat
            call_count = [0]

            def mock_stat(self):
                call_count[0] += 1
                if call_count[0] == 1:
                    # First call for exists() check
                    return original_stat(self)
                else:
                    # Second call for size
                    raise OSError("Permission denied")

            with patch.object(Path, "stat", mock_stat):
                match = locator.find_by_key("test", entries)

                assert match is not None
                assert match.exists
                assert match.size_bytes is None  # Size couldn't be determined


class TestRegexErrorHandling:
    """Test regex error handling in _matches_pattern."""

    def test_invalid_regex_pattern(self):
        """Should handle invalid regex patterns gracefully."""
        locator = FileLocator()

        entries = [
            Entry(
                key="test",
                type=EntryType.ARTICLE,
                title="Test",
                pdf_path=Path("/test.pdf"),
            ),
        ]

        # Invalid regex pattern (unmatched parenthesis)
        result = locator.locate(r"[invalid(regex", entries, use_regex=True)

        # Should return empty result due to regex error
        assert result.total_found == 0


class TestOSErrorHandling:
    """Test OSError handling in various methods."""

    def test_locate_with_os_error(self):
        """Should handle OSError in locate method when getting file size."""
        locator = FileLocator()

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf_path.write_bytes(b"content")

            entries = [
                Entry(
                    key="test", type=EntryType.ARTICLE, title="Test", pdf_path=pdf_path
                ),
            ]

            # Mock stat to fail only for size, not for exists
            original_stat = Path.stat
            call_count = [0]

            def mock_stat(self):
                call_count[0] += 1
                if call_count[0] == 1:
                    return original_stat(self)
                else:
                    raise OSError("Permission denied")

            with patch.object(Path, "stat", mock_stat):
                result = locator.locate("*.pdf", entries, check_existence=True)

                assert result.total_found == 1
                assert result.matches[0].exists
                assert result.matches[0].size_bytes is None

    def test_find_by_basename_with_os_error(self):
        """Should handle OSError in find_by_basename when getting file size."""
        locator = FileLocator()

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "target.pdf"
            pdf_path.write_bytes(b"content")

            entries = [
                Entry(
                    key="test", type=EntryType.ARTICLE, title="Test", pdf_path=pdf_path
                ),
            ]

            # Mock stat to fail only for size
            original_stat = Path.stat
            call_count = [0]

            def mock_stat(self):
                call_count[0] += 1
                if call_count[0] == 1:
                    return original_stat(self)
                else:
                    raise OSError("Permission denied")

            with patch.object(Path, "stat", mock_stat):
                result = locator.find_by_basename("target.pdf", entries)

                assert result.total_found == 1
                assert result.matches[0].exists
                assert result.matches[0].size_bytes is None

    def test_get_statistics_with_os_error(self):
        """Should handle OSError in get_statistics when getting file size."""
        locator = FileLocator()

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf_path.write_bytes(b"x" * 1000)

            entries = [
                Entry(
                    key="test", type=EntryType.ARTICLE, title="Test", pdf_path=pdf_path
                ),
            ]

            # Mock stat to fail only for size
            original_stat = Path.stat
            call_count = [0]

            def mock_stat(self):
                call_count[0] += 1
                if call_count[0] == 1:
                    return original_stat(self)
                else:
                    raise OSError("Permission denied")

            with patch.object(Path, "stat", mock_stat):
                stats = locator.get_statistics(entries)

                assert stats["existing_files"] == 1
                assert stats["total_size_mb"] == 0  # Couldn't get size

    def test_verify_all_with_os_error(self):
        """Should handle OSError in verify_all when getting file size."""
        locator = FileLocator()

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf_path.write_bytes(b"content")

            entries = [
                Entry(
                    key="test", type=EntryType.ARTICLE, title="Test", pdf_path=pdf_path
                ),
            ]

            # Mock stat to fail only for size
            original_stat = Path.stat
            call_count = [0]

            def mock_stat(self):
                call_count[0] += 1
                if call_count[0] == 1:
                    return original_stat(self)
                else:
                    raise OSError("Permission denied")

            with patch.object(Path, "stat", mock_stat):
                result = locator.verify_all(entries)

                assert len(result["existing"]) == 1
                assert result["existing"][0].size_bytes is None
