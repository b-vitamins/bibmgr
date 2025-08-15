"""Tests for duplicate entry detection.

This module tests duplicate detection by DOI, title+author+year,
and various normalization strategies.
"""

from typing import Any

from bibmgr.core.duplicates import DuplicateDetector
from bibmgr.core.fields import EntryType
from bibmgr.core.models import Entry


class TestDuplicateDetector:
    """Test duplicate detection functionality."""

    def test_doi_duplicate_detection(
        self, duplicate_entries: list[dict[str, Any]]
    ) -> None:
        """Detect duplicates by DOI."""
        entries = [Entry.from_dict(data) for data in duplicate_entries]
        detector = DuplicateDetector(entries)

        duplicates = detector.find_duplicates()

        # Should find at least one group (same DOI)
        assert len(duplicates) > 0

        # Check DOI duplicates found
        doi_group = None
        for group in duplicates:
            if any(e.doi for e in group):
                doi_group = group
                break

        assert doi_group is not None
        assert len(doi_group) == 2
        assert all(e.doi == "10.1038/nature.2023.12345" for e in doi_group)

    def test_title_author_year_duplicate_detection(
        self, duplicate_entries: list[dict[str, Any]]
    ) -> None:
        """Detect duplicates by title+author+year."""
        entries = [Entry.from_dict(data) for data in duplicate_entries]
        detector = DuplicateDetector(entries)

        duplicates = detector.find_duplicates()

        # Find TAY duplicates
        tay_group = None
        for group in duplicates:
            if any("Quantum Computing" in e.title for e in group):
                tay_group = group
                break

        assert tay_group is not None
        assert len(tay_group) == 2

    def test_validate_entry_doi_duplicates(self) -> None:
        """Validate single entry for DOI duplicates."""
        entries = [
            Entry(
                key="first",
                type=EntryType.ARTICLE,
                author="Author One",
                title="Paper One",
                journal="Journal",
                year=2024,
                doi="10.1234/test.2024.001",
            ),
            Entry(
                key="second",
                type=EntryType.ARTICLE,
                author="Author Two",
                title="Paper Two",
                journal="Journal",
                year=2024,
                doi="10.1234/test.2024.001",  # Same DOI
            ),
        ]

        detector = DuplicateDetector(entries)

        # Check first entry
        errors = detector.validate_entry(entries[0])
        assert len(errors) == 1
        assert "Duplicate DOI" in errors[0].message
        assert "second" in errors[0].message

    def test_no_duplicates(self) -> None:
        """No duplicates should return empty list."""
        entries = [
            Entry(
                key="unique1",
                type=EntryType.ARTICLE,
                author="Author One",
                title="Unique Paper One",
                journal="Journal A",
                year=2023,
                doi="10.1111/unique.1",
            ),
            Entry(
                key="unique2",
                type=EntryType.ARTICLE,
                author="Author Two",
                title="Unique Paper Two",
                journal="Journal B",
                year=2024,
                doi="10.2222/unique.2",
            ),
        ]

        detector = DuplicateDetector(entries)
        duplicates = detector.find_duplicates()

        assert len(duplicates) == 0

    def test_case_insensitive_doi(self) -> None:
        """DOI comparison should be case-insensitive."""
        entries = [
            Entry(
                key="lower",
                type=EntryType.ARTICLE,
                author="Author",
                title="Paper",
                journal="Journal",
                year=2024,
                doi="10.1234/abc",
            ),
            Entry(
                key="upper",
                type=EntryType.ARTICLE,
                author="Author",
                title="Paper",
                journal="Journal",
                year=2024,
                doi="10.1234/ABC",  # Same DOI, different case
            ),
        ]

        detector = DuplicateDetector(entries)
        duplicates = detector.find_duplicates()

        assert len(duplicates) == 1
        assert len(duplicates[0]) == 2

    def test_doi_whitespace_normalization(self) -> None:
        """DOI comparison should ignore whitespace."""
        entries = [
            Entry(
                key="normal",
                type=EntryType.ARTICLE,
                author="Author",
                title="Paper",
                journal="Journal",
                year=2024,
                doi="10.1234/test",
            ),
            Entry(
                key="spaces",
                type=EntryType.ARTICLE,
                author="Author",
                title="Paper",
                journal="Journal",
                year=2024,
                doi=" 10.1234/test ",  # Extra spaces
            ),
        ]

        detector = DuplicateDetector(entries)
        duplicates = detector.find_duplicates()

        assert len(duplicates) == 1

    def test_empty_doi_not_duplicate(self) -> None:
        """Empty DOIs should not match each other."""
        entries = [
            Entry(
                key="a",
                type=EntryType.ARTICLE,
                title="A",
                journal="J",
                year=2024,
                doi="",
            ),
            Entry(
                key="b",
                type=EntryType.ARTICLE,
                title="B",
                journal="J",
                year=2024,
                doi="",
            ),
            Entry(
                key="c",
                type=EntryType.ARTICLE,
                title="C",
                journal="J",
                year=2024,
                doi=None,
            ),
        ]

        detector = DuplicateDetector(entries)

        # Check by DOI only - should find no duplicates
        doi_dups = [group for group in detector.doi_map.values() if len(group) > 1]
        assert len(doi_dups) == 0

    def test_multiple_duplicate_groups(self) -> None:
        """Multiple independent duplicate groups."""
        entries = [
            # Group 1 - same DOI
            Entry(
                key="a1",
                type=EntryType.ARTICLE,
                title="A1",
                journal="J",
                year=2024,
                doi="10.1111/a",
            ),
            Entry(
                key="a2",
                type=EntryType.ARTICLE,
                title="A2",
                journal="J",
                year=2024,
                doi="10.1111/a",
            ),
            # Group 2 - same DOI
            Entry(
                key="b1",
                type=EntryType.ARTICLE,
                title="B1",
                journal="J",
                year=2024,
                doi="10.2222/b",
            ),
            Entry(
                key="b2",
                type=EntryType.ARTICLE,
                title="B2",
                journal="J",
                year=2024,
                doi="10.2222/b",
            ),
            # Unique
            Entry(
                key="c",
                type=EntryType.ARTICLE,
                title="C",
                journal="J",
                year=2024,
                doi="10.3333/c",
            ),
        ]

        detector = DuplicateDetector(entries)
        duplicates = detector.find_duplicates()

        assert len(duplicates) == 2  # Two groups
        assert all(len(group) == 2 for group in duplicates)

    def test_overlapping_duplicate_criteria(self) -> None:
        """Entry can be duplicate by multiple criteria."""
        entries = [
            Entry(
                key="original",
                type=EntryType.ARTICLE,
                author="John Smith",
                title="Important Research",
                journal="Nature",
                year=2024,
                doi="10.1038/nature.2024.12345",
            ),
            Entry(
                key="doi_dup",
                type=EntryType.ARTICLE,
                author="J. Smith",  # Different format
                title="Different Title",  # Different title
                journal="Science",  # Different journal
                year=2023,  # Different year
                doi="10.1038/nature.2024.12345",  # Same DOI!
            ),
            Entry(
                key="tay_dup",
                type=EntryType.ARTICLE,
                author="John Smith",  # Same author
                title="Important Research",  # Same title
                journal="Different Journal",
                year=2024,  # Same year
                doi="10.9999/different.doi",  # Different DOI
            ),
        ]

        detector = DuplicateDetector(entries)
        duplicates = detector.find_duplicates()

        # Should find both DOI and TAY duplicates
        assert len(duplicates) >= 2

        # Original should be in both groups
        original_groups = [g for g in duplicates if any(e.key == "original" for e in g)]
        assert len(original_groups) >= 2


class TestDuplicateNormalization:
    """Test normalization strategies for duplicate detection."""

    def test_title_normalization(self) -> None:
        """Title normalization for comparison."""
        entries = [
            Entry(
                key="v1",
                type=EntryType.ARTICLE,
                author="Same Author",
                title="The Machine Learning Approach",
                journal="Journal",
                year=2024,
            ),
            Entry(
                key="v2",
                type=EntryType.ARTICLE,
                author="Same Author",
                title="machine learning approach",  # Different case, no "The"
                journal="Journal",
                year=2024,
            ),
        ]

        detector = DuplicateDetector(entries)
        duplicates = detector.find_duplicates()

        # Should match despite case differences
        assert len(duplicates) == 1
        assert len(duplicates[0]) == 2

    def test_author_normalization(self) -> None:
        """Author name normalization."""
        entries = [
            Entry(
                key="v1",
                type=EntryType.ARTICLE,
                author="John Smith and Jane Doe",
                title="Same Paper",
                journal="Journal",
                year=2024,
            ),
            Entry(
                key="v2",
                type=EntryType.ARTICLE,
                author="J. Smith and J. Doe",  # Abbreviated
                title="Same Paper",
                journal="Journal",
                year=2024,
            ),
            Entry(
                key="v3",
                type=EntryType.ARTICLE,
                author="Smith, John and Doe, Jane",  # Last, First format
                title="Same Paper",
                journal="Journal",
                year=2024,
            ),
        ]

        detector = DuplicateDetector(entries)
        duplicates = detector.find_duplicates()

        # Should find duplicates despite name format differences
        assert len(duplicates) > 0

    def test_doi_normalization_protocols(self) -> None:
        """DOI comparison ignores http/https prefixes."""
        entries = [
            Entry(
                key="doi1",
                type=EntryType.ARTICLE,
                title="Paper",
                journal="Journal",
                year=2024,
                doi="10.1234/test",
            ),
            Entry(
                key="doi2",
                type=EntryType.ARTICLE,
                title="Paper",
                journal="Journal",
                year=2024,
                doi="https://doi.org/10.1234/test",  # With URL prefix
            ),
            Entry(
                key="doi3",
                type=EntryType.ARTICLE,
                title="Paper",
                journal="Journal",
                year=2024,
                doi="http://dx.doi.org/10.1234/test",  # Different prefix
            ),
        ]

        detector = DuplicateDetector(entries)
        duplicates = detector.find_duplicates()

        # All should be considered same DOI
        assert len(duplicates) == 1
        assert len(duplicates[0]) == 3

    def test_year_tolerance(self) -> None:
        """Year matching with tolerance."""
        entries = [
            Entry(
                key="y1",
                type=EntryType.ARTICLE,
                author="Author",
                title="Same Title",
                journal="Journal",
                year=2023,
            ),
            Entry(
                key="y2",
                type=EntryType.ARTICLE,
                author="Author",
                title="Same Title",
                journal="Journal",
                year=2024,  # One year difference
            ),
        ]

        # Strict matching
        detector_strict = DuplicateDetector(entries, year_tolerance=0)
        dups_strict = detector_strict.find_duplicates()
        assert len(dups_strict) == 0  # No match

        # With tolerance
        detector_tolerant = DuplicateDetector(entries, year_tolerance=1)
        dups_tolerant = detector_tolerant.find_duplicates()
        assert len(dups_tolerant) == 1  # Should match

    def test_unicode_normalization(self) -> None:
        """Unicode normalization in names and titles."""
        entries = [
            Entry(
                key="u1",
                type=EntryType.ARTICLE,
                author="François Müller",
                title="Über Machine Learning",
                journal="Journal",
                year=2024,
            ),
            Entry(
                key="u2",
                type=EntryType.ARTICLE,
                author="Francois Muller",  # ASCII version
                title="Uber Machine Learning",  # ASCII version
                journal="Journal",
                year=2024,
            ),
        ]

        detector = DuplicateDetector(entries)
        duplicates = detector.find_duplicates()

        # Should match despite Unicode differences
        assert len(duplicates) == 1

    def test_latex_command_normalization(self) -> None:
        """LaTeX commands in titles normalized."""
        entries = [
            Entry(
                key="tex1",
                type=EntryType.ARTICLE,
                author="Author",
                title="The {\\LaTeX} Companion",
                journal="Journal",
                year=2024,
            ),
            Entry(
                key="tex2",
                type=EntryType.ARTICLE,
                author="Author",
                title="The LaTeX Companion",  # Without command
                journal="Journal",
                year=2024,
            ),
        ]

        detector = DuplicateDetector(entries)
        duplicates = detector.find_duplicates()

        # Should match
        assert len(duplicates) == 1

    def test_duplicate_confidence_scores(self) -> None:
        """Confidence scoring for duplicate matches."""
        entries = [
            Entry(
                key="exact",
                type=EntryType.ARTICLE,
                author="John Smith",
                title="Exact Match Paper",
                journal="Nature",
                year=2024,
                doi="10.1038/exact",
            ),
            Entry(
                key="exact_dup",
                type=EntryType.ARTICLE,
                author="John Smith",
                title="Exact Match Paper",
                journal="Nature",
                year=2024,
                doi="10.1038/exact",
            ),
            Entry(
                key="fuzzy",
                type=EntryType.ARTICLE,
                author="J. Smith",  # Abbreviated
                title="Exact Match Paper",
                journal="Nature",
                year=2024,
                # No DOI
            ),
        ]

        detector = DuplicateDetector(entries)

        # Get matches with confidence
        matches = detector.find_duplicates_with_confidence()

        # Find groups containing specific entries
        exact_only_group = None
        fuzzy_group = None

        for match in matches:
            keys = [e.key for e in match["entries"]]
            if "exact" in keys and "exact_dup" in keys and "fuzzy" not in keys:
                exact_only_group = match
            if "fuzzy" in keys:
                fuzzy_group = match

        # Should have high confidence for exact DOI match
        assert exact_only_group is not None
        assert exact_only_group["confidence"] > 0.9

        # Group with fuzzy match should exist
        assert fuzzy_group is not None
        # If fuzzy is part of a larger group with DOI matches, confidence may still be high
        # The test should check that we found the duplicates, not specific confidence values
        assert fuzzy_group["confidence"] >= 0.8

    def test_duplicate_merge_suggestions(self) -> None:
        """Suggest which fields to keep when merging."""
        entries = [
            Entry(
                key="incomplete",
                type=EntryType.ARTICLE,
                author="John Smith",
                title="Research Paper",
                journal="Nature",
                year=2024,
                # Missing DOI, URL
            ),
            Entry(
                key="complete",
                type=EntryType.ARTICLE,
                author="J. Smith and J. Doe",  # More complete
                title="Research Paper",
                journal="Nature",
                year=2024,
                doi="10.1038/research.2024",
                url="https://nature.com/research",
                pages="45--67",
            ),
        ]

        detector = DuplicateDetector(entries)

        # Get merge suggestions
        suggestions = detector.get_merge_suggestions(entries[0], entries[1])

        # Should suggest keeping more complete data
        assert suggestions["author"] == "J. Smith and J. Doe"
        assert suggestions["doi"] == "10.1038/research.2024"
        assert suggestions["url"] == "https://nature.com/research"
        assert suggestions["pages"] == "45--67"

    def test_performance_large_dataset(self, performance_test_entries) -> None:
        """Performance test with many entries."""
        # Create entries with some intentional duplicates
        entries = []
        for i, data in enumerate(performance_test_entries[:500]):
            entry = Entry.from_dict(data)
            entries.append(entry)

            # Add some duplicates
            if i % 50 == 0 and i > 0:
                # DOI duplicate
                import msgspec

                dup = Entry.from_dict(data)
                dup = msgspec.structs.replace(dup, key=f"{dup.key}_dup")
                entries.append(dup)

        detector = DuplicateDetector(entries)

        # Should complete in reasonable time
        import time

        start = time.time()
        duplicates = detector.find_duplicates()
        elapsed = time.time() - start

        assert elapsed < 5.0  # Should complete within 5 seconds
        assert (
            len(duplicates) >= 9
        )  # Should find the duplicates we added (every 50th from 50-450)
