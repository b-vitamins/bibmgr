"""Comprehensive tests for duplicate detection and merging."""

from typing import Any

import pytest

from bibmgr.core.models import Entry, EntryType
from bibmgr.operations.duplicates import (
    AuthorNormalizer,
    DuplicateDetector,
    DuplicateIndex,
    EntryMerger,
    MatchType,
    MergeStrategy,
    StringSimilarity,
    TitleNormalizer,
)


class TestSimilarityMetrics:
    """Test string similarity algorithms."""

    def test_exact_match(self):
        """Test exact string matching."""
        sim = StringSimilarity(algorithm="exact")

        assert sim.compute("hello", "hello") == 1.0
        assert sim.compute("hello", "Hello") == 0.0  # Case sensitive
        assert sim.compute("hello", "world") == 0.0
        assert sim.compute("", "") == 1.0
        assert sim.compute("", "text") == 0.0

    def test_levenshtein_distance(self):
        """Test Levenshtein distance similarity."""
        sim = StringSimilarity(algorithm="levenshtein")

        assert sim.compute("hello", "hello") == 1.0
        assert sim.compute("hello", "hallo") > 0.7  # One substitution
        assert sim.compute("hello", "hell") > 0.7  # One deletion
        assert sim.compute("hello", "helloo") > 0.8  # One insertion
        assert sim.compute("hello", "world") < 0.3  # Very different
        assert sim.compute("", "test") == 0.0
        assert sim.compute("test", "") == 0.0

    def test_jaccard_similarity(self):
        """Test Jaccard index for token sets."""
        sim = StringSimilarity(algorithm="jaccard")

        assert sim.compute("machine learning", "machine learning") == 1.0
        assert (
            sim.compute("machine learning", "learning machine") == 1.0
        )  # Order doesn't matter
        # deep learning = {deep, learning}, machine learning = {machine, learning}
        # Intersection = {learning}, Union = {deep, machine, learning}
        # Jaccard = 1/3 ≈ 0.333
        assert abs(sim.compute("deep learning", "machine learning") - 0.333) < 0.01
        assert sim.compute("hello world", "foo bar") == 0.0  # No common words

    def test_ngram_similarity(self):
        """Test n-gram based similarity."""
        sim = StringSimilarity(algorithm="ngram", n=2)

        assert sim.compute("hello", "hello") == 1.0
        # hello bigrams: he, el, ll, lo (4)
        # hallo bigrams: ha, al, ll, lo (4)
        # Common: ll, lo (2)
        # Union: he, el, ll, lo, ha, al (6)
        # Similarity = 2/6 = 0.333
        assert abs(sim.compute("hello", "hallo") - 0.333) < 0.01
        assert sim.compute("ab", "ba") == 0.0  # No bigram matches

    def test_custom_similarity(self):
        """Test custom similarity function."""

        def custom_sim(s1: str, s2: str) -> float:
            return 1.0 if len(s1) == len(s2) else 0.0

        sim = StringSimilarity(custom_function=custom_sim)

        assert sim.compute("abc", "def") == 1.0  # Same length
        assert sim.compute("ab", "abc") == 0.0  # Different length


class TestNormalizers:
    """Test text normalization for better matching."""

    def test_title_normalization(self):
        """Test title normalization rules."""
        norm = TitleNormalizer()

        # LaTeX command removal
        assert norm.normalize("The \\textbf{Quantum} Theory") == "the quantum theory"
        assert norm.normalize("\\emph{Machine} Learning") == "machine learning"

        # Special character handling
        assert norm.normalize("AI: A Modern Approach") == "ai a modern approach"
        assert norm.normalize("C++ Programming") == "c programming"

        # Whitespace normalization
        assert norm.normalize("  Multiple   Spaces  ") == "multiple spaces"
        assert norm.normalize("Line\nBreak") == "line break"

        # Subtitle handling
        assert norm.normalize("Main Title: A Subtitle") == "main title a subtitle"

        # Common abbreviations
        assert norm.normalize("Proc. of the Conf.") == "proceedings of the conference"

    def test_author_normalization(self):
        """Test author name normalization."""
        norm = AuthorNormalizer()

        # Name format variations
        assert norm.normalize("John Doe") == "doe j"
        assert norm.normalize("Doe, John") == "doe j"
        assert norm.normalize("Doe, John A.") == "doe j a"
        assert norm.normalize("John A. Doe") == "doe j a"

        # Multiple authors
        authors = norm.normalize_list("John Doe and Jane Smith")
        assert authors == ["doe j", "smith j"]

        authors = norm.normalize_list("Doe, J. and Smith, J.")
        assert authors == ["doe j", "smith j"]

        # Special characters
        assert norm.normalize("O'Brien, Patrick") == "obrien p"
        assert norm.normalize("García-López, María") == "garcialopez m"

        # Jr, Sr, III handling
        assert norm.normalize("Martin Luther King Jr.") == "king m l"
        assert norm.normalize("John Doe III") == "doe j"

    def test_author_list_parsing(self):
        """Test parsing of author lists."""
        norm = AuthorNormalizer()

        # Different separators
        authors = norm.normalize_list("John Doe and Jane Smith and Bob Johnson")
        assert len(authors) == 3

        authors = norm.normalize_list("John Doe, Jane Smith, Bob Johnson")
        assert len(authors) == 3

        # Mixed formats
        authors = norm.normalize_list("Doe, John and Smith, Jane")
        assert authors == ["doe j", "smith j"]

        # Et al. handling
        authors = norm.normalize_list("John Doe et al.")
        assert authors == ["doe j", "et al"]


class TestDuplicateDetection:
    """Test duplicate entry detection."""

    def test_exact_key_duplicate(self, duplicate_entries):
        """Test detection of exact key matches."""
        detector = DuplicateDetector()

        # Create two entries with same key
        entries = [
            Entry(
                key="same",
                type=EntryType.ARTICLE,
                title="First",
                author="Author A",
                journal="J1",
                year=2023,
            ),
            Entry(
                key="same",
                type=EntryType.ARTICLE,
                title="Second",
                author="Author B",
                journal="J2",
                year=2023,
            ),
        ]

        matches = detector.find_duplicates(entries)

        assert len(matches) == 1
        assert MatchType.EXACT_KEY in matches[0].match_type
        assert matches[0].score == 1.0

    def test_doi_duplicate(self, duplicate_entries):
        """Test DOI-based duplicate detection."""
        detector = DuplicateDetector()

        matches = detector.find_duplicates(duplicate_entries)

        # Find DOI matches
        doi_matches = [m for m in matches if MatchType.DOI in m.match_type]
        assert len(doi_matches) >= 1
        assert doi_matches[0].score == 1.0

    def test_doi_normalization(self):
        """Test DOI normalization for matching."""
        detector = DuplicateDetector()

        entries = [
            Entry(
                key="p1",
                type=EntryType.ARTICLE,
                title="Paper 1",
                author="A1",
                journal="J1",
                year=2023,
                doi="10.1234/test",
            ),
            Entry(
                key="p2",
                type=EntryType.ARTICLE,
                title="Paper 2",
                author="A2",
                journal="J2",
                year=2023,
                doi="https://doi.org/10.1234/test",
            ),  # With URL prefix
            Entry(
                key="p3",
                type=EntryType.ARTICLE,
                title="Paper 3",
                author="A3",
                journal="J3",
                year=2023,
                doi="DOI:10.1234/test",
            ),  # With DOI: prefix
        ]

        matches = detector.find_duplicates(entries)

        # All three should match each other
        assert len(matches) >= 2  # At least 2 pairs match

    def test_title_similarity_duplicate(self):
        """Test title-based duplicate detection."""
        detector = DuplicateDetector(title_threshold=0.8)

        entries = [
            Entry(
                key="p1",
                type=EntryType.ARTICLE,
                title="Machine Learning for Climate Prediction",
                author="Smith, J.",
                journal="Nature",
                year=2023,
            ),
            Entry(
                key="p2",
                type=EntryType.ARTICLE,
                title="Machine Learning for Climate Predictions",  # Plural
                author="Smith, J.",
                journal="Nature",
                year=2023,
            ),
            Entry(
                key="p3",
                type=EntryType.ARTICLE,
                title="Deep Learning Applications",  # Different
                author="Jones, B.",
                journal="Science",
                year=2023,
            ),
        ]

        matches = detector.find_duplicates(entries)

        # p1 and p2 should match
        title_matches = [m for m in matches if MatchType.TITLE in m.match_type]
        assert len(title_matches) >= 1
        assert title_matches[0].score > 0.8

        # p3 should not match others
        for match in matches:
            assert "p3" not in {match.entry1.key, match.entry2.key} or match.score < 0.5

    def test_author_similarity_duplicate(self):
        """Test author-based duplicate detection."""
        detector = DuplicateDetector(author_threshold=0.6)

        entries = [
            Entry(
                key="p1",
                type=EntryType.ARTICLE,
                title="Similar Paper Title",
                author="John Doe and Jane Smith",
                journal="J1",
                year=2023,
            ),
            Entry(
                key="p2",
                type=EntryType.ARTICLE,
                title="Similar Paper Title",
                author="J. Doe and J. Smith",
                journal="J2",
                year=2023,
            ),  # Abbreviated
            Entry(
                key="p3",
                type=EntryType.ARTICLE,
                title="Different Title",
                author="Smith, Jane and Doe, John",
                journal="J3",
                year=2023,
            ),  # Reordered
            Entry(
                key="p4",
                type=EntryType.ARTICLE,
                title="Paper 4",
                author="Alice Johnson",
                journal="J4",
                year=2023,
            ),  # Different
        ]

        matches = detector.find_duplicates(entries)

        # p1 and p2 should match (same title, similar authors)
        assert len(matches) >= 1
        # Check that p4 is not matched with others
        p4_matches = [m for m in matches if "p4" in {m.entry1.key, m.entry2.key}]
        assert len(p4_matches) == 0

    def test_combined_similarity(self):
        """Test combined field similarity for fuzzy matching."""
        detector = DuplicateDetector(combined_threshold=0.6)

        entries = [
            Entry(
                key="original",
                type=EntryType.ARTICLE,
                title="Machine Learning Study",
                author="John Doe",
                journal="AI Journal",
                year=2023,
            ),
            Entry(
                key="similar",
                type=EntryType.ARTICLE,
                title="Machine Learning Studies",  # Similar title
                author="J. Doe",  # Similar author
                journal="AI Journal",  # Same journal
                year=2023,
            ),  # Same year
            Entry(
                key="different",
                type=EntryType.ARTICLE,
                title="Quantum Computing",
                author="Bob Smith",
                journal="Physics Review",
                year=2022,
            ),
        ]

        matches = detector.find_duplicates(entries)

        # Original and similar should match - they have very similar titles, similar authors, same journal and year
        # Either title match or combined match should be found
        assert len(matches) >= 1  # At least one match between original and similar
        relevant_match = [
            m
            for m in matches
            if {"original", "similar"} == {m.entry1.key, m.entry2.key}
        ]
        assert len(relevant_match) == 1
        assert relevant_match[0].score > 0.6

    def test_duplicate_groups(self):
        """Test grouping of duplicate entries."""
        detector = DuplicateDetector()

        entries = [
            Entry(
                key="v1",
                type=EntryType.ARTICLE,
                title="Paper",
                author="Author",
                journal="J",
                year=2023,
                doi="10.1234/paper",
            ),
            Entry(
                key="v2",
                type=EntryType.ARTICLE,
                title="Paper",
                author="Author",
                journal="J",
                year=2023,
                doi="10.1234/paper",
            ),
            Entry(
                key="v3",
                type=EntryType.ARTICLE,
                title="Paper",
                author="Author",
                journal="J",
                year=2023,
                doi="10.1234/paper",
            ),
        ]

        groups = detector.find_duplicate_groups(entries)

        # All three should be in one group
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_performance_with_index(self):
        """Test performance optimization with indexing."""
        # Create many entries
        entries = []
        for i in range(100):
            entries.append(
                Entry(
                    key=f"entry{i}",
                    type=EntryType.ARTICLE,
                    title=f"Title {i % 10}",  # Some duplicates
                    author=f"Author {i % 20}",
                    journal=f"Journal {i % 5}",
                    year=2020 + (i % 4),
                )
            )

        # Use indexed detector for better performance
        detector = DuplicateDetector(use_index=True)

        # This should be fast even with many entries
        matches = detector.find_duplicates(entries)

        # Should find some duplicates based on similar titles
        assert len(matches) > 0


class TestDuplicateIndex:
    """Test duplicate detection index for performance."""

    def test_index_creation(self, sample_entries):
        """Test creating index from entries."""
        index = DuplicateIndex()
        index.build(sample_entries)

        # Index should have entries indexed by various fields
        assert len(index) == len(sample_entries)

    def test_index_lookup_by_doi(self):
        """Test fast lookup by DOI."""
        index = DuplicateIndex()

        entries = [
            Entry(
                key="p1",
                type=EntryType.ARTICLE,
                title="Paper 1",
                author="A1",
                journal="J1",
                year=2023,
                doi="10.1234/test",
            ),
            Entry(
                key="p2",
                type=EntryType.ARTICLE,
                title="Paper 2",
                author="A2",
                journal="J2",
                year=2023,
                doi="10.5678/other",
            ),
        ]

        index.build(entries)

        # Lookup by DOI
        matches = index.find_by_doi("10.1234/test")
        assert len(matches) == 1
        assert matches[0].key == "p1"

        # Normalized DOI lookup
        matches = index.find_by_doi("https://doi.org/10.1234/test")
        assert len(matches) == 1

    def test_index_lookup_by_title(self):
        """Test fast lookup by normalized title."""
        index = DuplicateIndex()

        entries = [
            Entry(
                key="p1",
                type=EntryType.ARTICLE,
                title="Machine Learning",
                author="A1",
                journal="J1",
                year=2023,
            ),
            Entry(
                key="p2",
                type=EntryType.ARTICLE,
                title="Deep Learning",
                author="A2",
                journal="J2",
                year=2023,
            ),
        ]

        index.build(entries)

        # Lookup by title
        matches = index.find_by_title("Machine Learning")
        assert len(matches) == 1
        assert matches[0].key == "p1"

        # Normalized title lookup
        matches = index.find_by_title("MACHINE LEARNING")
        assert len(matches) == 1

    def test_index_update(self):
        """Test updating index with new entries."""
        index = DuplicateIndex()

        entry1 = Entry(
            key="p1",
            type=EntryType.ARTICLE,
            title="Paper 1",
            author="A1",
            journal="J1",
            year=2023,
        )
        entry2 = Entry(
            key="p2",
            type=EntryType.ARTICLE,
            title="Paper 2",
            author="A2",
            journal="J2",
            year=2023,
        )

        index.add(entry1)
        assert len(index) == 1

        index.add(entry2)
        assert len(index) == 2

        index.remove(entry1)
        assert len(index) == 1


class TestEntryMerging:
    """Test merging of duplicate entries."""

    def test_merge_union_strategy(self):
        """Test union merge strategy."""
        merger = EntryMerger()

        entries = [
            Entry(
                key="p1",
                type=EntryType.ARTICLE,
                title="Paper",
                author="Author A",
                journal="Journal",
                year=2023,
            ),
            Entry(
                key="p2",
                type=EntryType.ARTICLE,
                title="Paper",
                author="Author A and Author B",
                journal="Journal",
                year=2023,
                doi="10.1234/test",
                pages="1-10",
            ),
        ]

        merged = merger.merge(entries, strategy=MergeStrategy.UNION)

        # Should keep most complete data
        assert merged.author == "Author A and Author B"  # More complete
        assert merged.doi == "10.1234/test"  # From p2
        assert merged.pages == "1-10"  # From p2

    def test_merge_intersection_strategy(self):
        """Test intersection merge strategy."""
        merger = EntryMerger()

        entries = [
            Entry(
                key="p1",
                type=EntryType.ARTICLE,
                title="Paper",
                author="Author",
                journal="Journal A",
                year=2023,
            ),
            Entry(
                key="p2",
                type=EntryType.ARTICLE,
                title="Paper",
                author="Author",
                journal="Journal B",
                year=2023,
            ),
        ]

        merged = merger.merge(entries, strategy=MergeStrategy.INTERSECTION)

        # Should keep only common fields
        assert merged.title == "Paper"
        assert merged.author == "Author"
        assert merged.year == 2023
        assert merged.journal is None  # Different values, not included

    def test_merge_prefer_first(self):
        """Test preferring first entry in conflicts."""
        merger = EntryMerger()

        entries = [
            Entry(
                key="p1",
                type=EntryType.ARTICLE,
                title="First Title",
                author="First Author",
                journal="J1",
                year=2022,
            ),
            Entry(
                key="p2",
                type=EntryType.ARTICLE,
                title="Second Title",
                author="Second Author",
                journal="J2",
                year=2023,
            ),
        ]

        merged = merger.merge(entries, strategy=MergeStrategy.PREFER_FIRST)

        assert merged.title == "First Title"
        assert merged.author == "First Author"
        assert merged.year == 2022

    def test_merge_prefer_newest(self):
        """Test preferring newest entry by year."""
        merger = EntryMerger()

        entries = [
            Entry(
                key="p1",
                type=EntryType.ARTICLE,
                title="Old Paper",
                author="Author",
                journal="J",
                year=2020,
            ),
            Entry(
                key="p2",
                type=EntryType.ARTICLE,
                title="New Paper",
                author="Author",
                journal="J",
                year=2023,
            ),
            Entry(
                key="p3",
                type=EntryType.ARTICLE,
                title="Middle Paper",
                author="Author",
                journal="J",
                year=2021,
            ),
        ]

        merged = merger.merge(entries, strategy=MergeStrategy.PREFER_NEWEST)

        assert merged.title == "New Paper"
        assert merged.year == 2023

    def test_merge_custom_resolver(self):
        """Test custom field resolver for merging."""

        def custom_resolver(field: str, values: list[Any]) -> Any:
            if field == "title":
                # Choose longest title
                return max(values, key=lambda x: len(x) if x else 0)
            elif field == "author":
                # Combine all authors
                all_authors = set()
                for v in values:
                    if v:
                        all_authors.update(v.split(" and "))
                return " and ".join(sorted(all_authors))
            else:
                return values[0]  # Default to first

        merger = EntryMerger()

        entries = [
            Entry(
                key="p1",
                type=EntryType.ARTICLE,
                title="Short",
                author="Author A",
                journal="J",
                year=2023,
            ),
            Entry(
                key="p2",
                type=EntryType.ARTICLE,
                title="Longer Title",
                author="Author B",
                journal="J",
                year=2023,
            ),
        ]

        merged = merger.merge(entries, custom_resolver=custom_resolver)

        assert merged.title == "Longer Title"
        assert (
            merged.author
            and "Author A" in merged.author
            and "Author B" in merged.author
        )

    def test_merge_empty_list(self):
        """Test merging empty list raises error."""
        merger = EntryMerger()

        with pytest.raises(ValueError, match="No entries to merge"):
            merger.merge([])

    def test_merge_single_entry(self):
        """Test merging single entry returns itself."""
        merger = EntryMerger()

        entry = Entry(
            key="p1",
            type=EntryType.ARTICLE,
            title="Paper",
            author="Author",
            journal="J",
            year=2023,
        )
        merged = merger.merge([entry])

        assert merged == entry

    def test_merge_preserves_required_fields(self):
        """Test merging preserves required fields."""
        merger = EntryMerger()

        entries = [
            Entry(
                key="p1",
                type=EntryType.ARTICLE,
                title="Paper",
                author="Author",
                journal="Journal A",
                year=2023,
            ),
            Entry(
                key="p2",
                type=EntryType.BOOK,
                title="Book",
                author="Author",
                publisher="Publisher",
                year=2023,
            ),
        ]

        merged = merger.merge(entries)

        # Should have a valid type and key
        assert merged.type in [EntryType.ARTICLE, EntryType.BOOK]
        assert merged.key is not None
