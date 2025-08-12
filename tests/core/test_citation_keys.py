"""Tests for citation key generation in core models."""

from bibmgr.core.models import Entry, EntryType, generate_citation_key


class TestCitationKeyGeneration:
    """Test citation key generation."""

    def test_article_key_generation(self):
        """Test key generation for articles."""
        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            title="Deep Learning for Computer Vision",
            author="Smith, John and Doe, Jane",
            year=2023,
        )

        # Default format: FirstAuthorYear
        assert generate_citation_key(entry) == "smith2023"

        # With suffix for duplicates
        assert generate_citation_key(entry, suffix="a") == "smith2023a"

        # Custom format
        assert generate_citation_key(entry, format="{author1}_{year}") == "smith_2023"

    def test_book_key_generation(self):
        """Test key generation for books."""
        entry = Entry(
            key="temp",
            type=EntryType.BOOK,
            title="Machine Learning Fundamentals",
            author="Johnson, Alice",
            year=2022,
        )

        assert generate_citation_key(entry) == "johnson2022"

    def test_inproceedings_key_generation(self):
        """Test key generation for conference papers."""
        entry = Entry(
            key="temp",
            type=EntryType.INPROCEEDINGS,
            title="Neural Networks at Scale",
            author="Lee, David and Park, Sarah and Kim, Michael",
            year=2023,
            booktitle="NeurIPS",
        )

        # Include venue
        assert (
            generate_citation_key(entry, format="{author1}{year}{venue}")
            == "lee2023neurips"
        )

    def test_key_generation_edge_cases(self):
        """Test edge cases in key generation."""
        # No author
        entry = Entry(
            key="temp",
            type=EntryType.MISC,
            title="Anonymous Report",
            year=2023,
        )
        assert generate_citation_key(entry) == "anonymous2023"

        # No year
        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            title="Timeless Article",
            author="Smith, John",
        )
        assert generate_citation_key(entry) == "smith"

        # Special characters in author
        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            title="Test Article",
            author="O'Brien, Patrick",
            year=2023,
        )
        assert generate_citation_key(entry) == "obrien2023"

    def test_custom_key_formats(self):
        """Test custom citation key formats."""
        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            title="Test Article",
            author="Smith, John and Doe, Jane",
            year=2023,
            journal="Nature",
        )

        formats = [
            ("{author1}{year}", "smith2023"),
            ("{author1}_{author2}_{year}", "smith_doe_2023"),
            ("{year}_{author1}", "2023_smith"),
            ("{author1}{year}{journal}", "smith2023nature"),
            ("{AUTHOR1}{year}", "SMITH2023"),  # Uppercase
        ]

        for fmt, expected in formats:
            assert generate_citation_key(entry, format=fmt) == expected

    def test_author_name_formats(self):
        """Test different author name formats."""
        # Last, First format
        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            title="Test",
            author="von Neumann, John",
            year=2023,
        )
        assert generate_citation_key(entry) == "vonneumann2023"

        # First Last format
        entry2 = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            title="Test",
            author="John von Neumann",
            year=2023,
        )
        assert generate_citation_key(entry2) == "vonneumann2023"

        # Multiple authors with mixed formats
        entry3 = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            title="Test",
            author="Smith, John and Jane Doe and Brown, Bob",
            year=2023,
        )
        assert (
            generate_citation_key(entry3, format="{author1}_{author2}_{author3}_{year}")
            == "smith_doe_brown_2023"
        )

    def test_venue_abbreviations(self):
        """Test venue/journal abbreviation."""
        entry = Entry(
            key="temp",
            type=EntryType.INPROCEEDINGS,
            title="Test",
            author="Smith, John",
            year=2023,
            booktitle="International Conference on Machine Learning",
        )

        assert (
            generate_citation_key(entry, format="{author1}{year}{venue}")
            == "smith2023icml"
        )

        # Test with journal
        entry2 = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            title="Test",
            author="Smith, John",
            year=2023,
            journal="Proceedings of the National Academy of Sciences",
        )
        assert (
            generate_citation_key(entry2, format="{author1}{year}{journal}")
            == "smith2023pnas"
        )

    def test_collaboration_names(self):
        """Test collaboration/group author names."""
        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            title="Test",
            author="{ATLAS Collaboration}",
            year=2023,
        )

        assert generate_citation_key(entry) == "atlascollaboration2023"

        # With other authors
        entry2 = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            title="Test",
            author="{CMS Collaboration} and Smith, John",
            year=2023,
        )
        assert (
            generate_citation_key(entry2, format="{author1}_{author2}_{year}")
            == "cmscollaboration_smith_2023"
        )

    def test_empty_format_placeholders(self):
        """Test handling of empty placeholders."""
        entry = Entry(
            key="temp",
            type=EntryType.MISC,
            title="Test",
            author="Smith, John",
            year=2023,
        )

        # Format with missing field
        assert (
            generate_citation_key(entry, format="{author1}{year}{journal}")
            == "smith2023"
        )  # journal placeholder removed

        # Format with only missing fields
        assert generate_citation_key(entry, format="{venue}{journal}") == ""

    def test_unicode_author_names(self):
        """Test Unicode characters in author names."""
        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            title="Test",
            author="Müller, Hans and Gödel, Kurt",
            year=2023,
        )

        # Unicode characters should be handled
        assert generate_citation_key(entry) == "muller2023"

        # Test format with multiple authors
        assert (
            generate_citation_key(entry, format="{author1}_{author2}_{year}")
            == "muller_godel_2023"
        )
