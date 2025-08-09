"""Tests for BibTeX sorting and label generation.

This module tests sort key generation for different bibliography styles
and label generation for numeric and alpha styles.
"""

from bibmgr.core.fields import EntryType
from bibmgr.core.models import Entry
from bibmgr.core.sorting import LabelGenerator, SortKeyGenerator


class TestSortKeyGeneration:
    """Test sort key generation for bibliography ordering."""

    def test_plain_sort_key_basic(self) -> None:
        """Plain style: author, year, title."""
        generator = SortKeyGenerator(style="plain")

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Donald E. Knuth",
            title="The Art of Computer Programming",
            journal="Journal",
            year=1968,
        )

        sort_key = generator.generate(entry)

        # Should contain author last name, year, title
        assert "knuth" in sort_key.lower()
        assert "donald" in sort_key.lower()
        assert "1968" in sort_key
        assert "art" in sort_key.lower()
        assert "computer" in sort_key.lower()

    def test_plain_sort_key_multiple_authors(self) -> None:
        """Plain style with multiple authors."""
        generator = SortKeyGenerator(style="plain")

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Jane Doe and John Smith and Alice Brown",
            title="Collaborative Work",
            journal="Journal",
            year=2024,
        )

        sort_key = generator.generate(entry)

        # Should have all author names
        assert "doe" in sort_key.lower()
        assert "jane" in sort_key.lower()
        assert "smith" in sort_key.lower()
        assert "brown" in sort_key.lower()

    def test_plain_sort_key_no_author(self) -> None:
        """Plain style without author."""
        generator = SortKeyGenerator(style="plain")

        entry = Entry(
            key="test",
            type=EntryType.PROCEEDINGS,
            editor="Conference Editors",
            title="Conference Proceedings",
            year=2024,
        )

        sort_key = generator.generate(entry)

        # Should still have year and title
        assert "2024" in sort_key
        assert "conference" in sort_key.lower()
        assert "proceedings" in sort_key.lower()

    def test_plain_sort_key_no_year(self) -> None:
        """Plain style without year uses 9999."""
        generator = SortKeyGenerator(style="plain")

        entry = Entry(
            key="test",
            type=EntryType.UNPUBLISHED,
            author="Author Name",
            title="Draft Paper",
            note="Unpublished",
        )

        sort_key = generator.generate(entry)

        # Should use 9999 for missing year
        assert "9999" in sort_key

    def test_alpha_sort_key(self) -> None:
        """Alpha style uses label + year."""
        generator = SortKeyGenerator(style="alpha")

        entry = Entry(
            key="knuth68",
            type=EntryType.ARTICLE,
            author="Donald E. Knuth",
            title="The Art of Computer Programming",
            journal="Journal",
            year=1968,
        )

        sort_key = generator.generate(entry)

        # Should have label components
        assert "knu" in sort_key.lower()  # First 3 letters of Knuth
        assert "1968" in sort_key

    def test_sort_key_purification(self) -> None:
        """Sort keys should have purified text."""
        generator = SortKeyGenerator(style="plain")

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="François Müller",
            title="The {LaTeX} Companion: A Guide",
            journal="Journal",
            year=2024,
        )

        sort_key = generator.generate(entry)

        # Should purify special characters and LaTeX
        # François -> Francois, {LaTeX} -> LaTeX
        assert "latex" in sort_key.lower()
        assert "companion" in sort_key.lower()
        # Purification removes non-ASCII
        assert "ç" not in sort_key

    def test_sort_key_consistency(self) -> None:
        """Same entry should always generate same sort key."""
        generator = SortKeyGenerator(style="plain")

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Test Author",
            title="Test Title",
            journal="Test Journal",
            year=2024,
        )

        key1 = generator.generate(entry)
        key2 = generator.generate(entry)

        assert key1 == key2

    def test_sort_order_by_author(self) -> None:
        """Entries should sort correctly by author."""
        generator = SortKeyGenerator(style="plain")

        entries = [
            Entry(
                key="c",
                type=EntryType.ARTICLE,
                author="Charles Darwin",
                title="Title",
                journal="J",
                year=2024,
            ),
            Entry(
                key="a",
                type=EntryType.ARTICLE,
                author="Albert Einstein",
                title="Title",
                journal="J",
                year=2024,
            ),
            Entry(
                key="b",
                type=EntryType.ARTICLE,
                author="Barbara McClintock",
                title="Title",
                journal="J",
                year=2024,
            ),
        ]

        # Generate sort keys
        keys = [(generator.generate(e), e.key) for e in entries]
        keys.sort()

        # Check order by last name
        ordered_ids = [k[1] for k in keys]
        assert ordered_ids == ["c", "a", "b"]  # Darwin, Einstein, McClintock

    def test_sort_order_by_year(self) -> None:
        """Entries with same author sort by year."""
        generator = SortKeyGenerator(style="plain")

        entries = [
            Entry(
                key="new",
                type=EntryType.ARTICLE,
                author="Same Author",
                title="New Paper",
                journal="J",
                year=2024,
            ),
            Entry(
                key="old",
                type=EntryType.ARTICLE,
                author="Same Author",
                title="Old Paper",
                journal="J",
                year=2020,
            ),
            Entry(
                key="mid",
                type=EntryType.ARTICLE,
                author="Same Author",
                title="Mid Paper",
                journal="J",
                year=2022,
            ),
        ]

        # Generate sort keys
        keys = [(generator.generate(e), e.key) for e in entries]
        keys.sort()

        # Check chronological order
        ordered_ids = [k[1] for k in keys]
        assert ordered_ids == ["old", "mid", "new"]

    def test_sort_order_by_title(self) -> None:
        """Entries with same author and year sort by title."""
        generator = SortKeyGenerator(style="plain")

        entries = [
            Entry(
                key="c",
                type=EntryType.ARTICLE,
                author="Author",
                title="Zebra",
                journal="J",
                year=2024,
            ),
            Entry(
                key="a",
                type=EntryType.ARTICLE,
                author="Author",
                title="Apple",
                journal="J",
                year=2024,
            ),
            Entry(
                key="b",
                type=EntryType.ARTICLE,
                author="Author",
                title="Banana",
                journal="J",
                year=2024,
            ),
        ]

        # Generate sort keys
        keys = [(generator.generate(e), e.key) for e in entries]
        keys.sort()

        # Check alphabetical order by title
        ordered_ids = [k[1] for k in keys]
        assert ordered_ids == ["a", "b", "c"]  # Apple, Banana, Zebra


class TestLabelGeneration:
    """Test label generation for different bibliography styles."""

    def test_numeric_labels_sequential(self) -> None:
        """Numeric labels are sequential."""
        generator = LabelGenerator(style="numeric")

        entries = [
            Entry(key="a", type=EntryType.ARTICLE, title="A"),
            Entry(key="b", type=EntryType.ARTICLE, title="B"),
            Entry(key="c", type=EntryType.ARTICLE, title="C"),
        ]

        labels = [generator.generate(e) for e in entries]

        assert labels == ["1", "2", "3"]

    def test_numeric_labels_consistent(self) -> None:
        """Same entry always gets same numeric label."""
        generator = LabelGenerator(style="numeric")

        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test")

        label1 = generator.generate(entry)
        label2 = generator.generate(entry)

        assert label1 == label2
        assert label1 == "1"  # First entry

    def test_alpha_label_single_author(self) -> None:
        """Alpha label for single author: first 3 letters + year."""
        generator = LabelGenerator(style="alpha")

        entry = Entry(
            key="knuth84",
            type=EntryType.BOOK,
            author="Donald E. Knuth",
            title="The TeXbook",
            publisher="Addison-Wesley",
            year=1984,
        )

        label = generator.generate(entry)

        # Should be Knu84 (first 3 letters of last name + year)
        assert label == "Knu84"

    def test_alpha_label_two_authors(self) -> None:
        """Alpha label for two authors: first letters + year."""
        generator = LabelGenerator(style="alpha")

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Jane Doe and John Smith",
            title="Joint Paper",
            journal="Journal",
            year=2024,
        )

        label = generator.generate(entry)

        # Should be DS24 (first letters of last names + year)
        assert label == "DS24"

    def test_alpha_label_three_authors(self) -> None:
        """Alpha label for three authors: first letters + year."""
        generator = LabelGenerator(style="alpha")

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Alice Brown and Bob Davis and Carol Evans",
            title="Triple Paper",
            journal="Journal",
            year=2024,
        )

        label = generator.generate(entry)

        # Should be BDE24
        assert label == "BDE24"

    def test_alpha_label_many_authors(self) -> None:
        """Alpha label for 4+ authors: first 3 letters + + + year."""
        generator = LabelGenerator(style="alpha")

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Author One and Author Two and Author Three and Author Four",
            title="Big Collaboration",
            journal="Journal",
            year=2024,
        )

        label = generator.generate(entry)

        # Should be OTT+24 (first letters of first 3 + plus + year)
        assert label == "OTT+24"

    def test_alpha_label_no_author_uses_editor(self) -> None:
        """Alpha label uses editor if no author."""
        generator = LabelGenerator(style="alpha")

        entry = Entry(
            key="test",
            type=EntryType.PROCEEDINGS,
            editor="Conference Editors",
            title="Proceedings",
            year=2024,
        )

        label = generator.generate(entry)

        # Should use Ed for editor
        assert label == "Ed24"

    def test_alpha_label_no_author_no_editor(self) -> None:
        """Alpha label uses key if no author/editor."""
        generator = LabelGenerator(style="alpha")

        entry = Entry(
            key="manual2024",
            type=EntryType.MANUAL,
            title="Software Manual",
            organization="Company",
            year=2024,
        )

        label = generator.generate(entry)

        # Should use first 3 letters of key
        assert label == "MAN24"

    def test_alpha_label_no_year(self) -> None:
        """Alpha label uses ?? for missing year."""
        generator = LabelGenerator(style="alpha")

        entry = Entry(
            key="test",
            type=EntryType.UNPUBLISHED,
            author="Draft Author",
            title="Draft",
            note="Unpublished",
        )

        label = generator.generate(entry)

        # Should use ?? for missing year
        assert label.endswith("??")

    def test_alpha_label_duplicates(self) -> None:
        """Duplicate alpha labels get suffixes."""
        generator = LabelGenerator(style="alpha")

        # Two papers by Knuth in same year
        entry1 = Entry(
            key="knuth84a",
            type=EntryType.ARTICLE,
            author="Donald E. Knuth",
            title="First Paper",
            journal="Journal A",
            year=1984,
        )

        entry2 = Entry(
            key="knuth84b",
            type=EntryType.ARTICLE,
            author="Donald E. Knuth",
            title="Second Paper",
            journal="Journal B",
            year=1984,
        )

        label1 = generator.generate(entry1)
        label2 = generator.generate(entry2)

        # First should be Knu84, second should be Knu84a
        assert label1 == "Knu84"
        assert label2 == "Knu84a"

    def test_alpha_label_von_particles(self) -> None:
        """Alpha label handles von particles correctly."""
        generator = LabelGenerator(style="alpha")

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Ludwig van Beethoven",
            title="Composition",
            journal="Music Journal",
            year=1800,
        )

        label = generator.generate(entry)

        # Should use Beethoven, not van
        assert label == "Bee00"  # Last 2 digits of 1800

    def test_plain_style_uses_numeric(self) -> None:
        """Plain style should use numeric labels."""
        generator = LabelGenerator(style="plain")

        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test")

        label = generator.generate(entry)

        # Plain style uses numeric
        assert label == "1"

    def test_unknown_style_uses_key(self) -> None:
        """Unknown style falls back to entry key."""
        generator = LabelGenerator(style="unknown")

        entry = Entry(key="mykey", type=EntryType.ARTICLE, title="Test")

        label = generator.generate(entry)

        # Should use the entry key
        assert label == "mykey"

    def test_label_generation_performance(self, performance_test_entries) -> None:
        """Label generation should be efficient for many entries."""
        # Use fixture with configurable size
        generator = LabelGenerator(style="alpha")

        # Generate labels for all entries
        labels = []
        for entry_data in performance_test_entries[:100]:  # Test with 100
            entry = Entry.from_dict(entry_data)
            label = generator.generate(entry)
            labels.append(label)

        # Should generate unique labels
        assert len(labels) == 100
        # Most should be unique (some duplicates expected)
        assert len(set(labels)) > 90
