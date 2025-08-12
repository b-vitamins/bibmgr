"""Tests for citation formatting in operations."""

import pytest

from bibmgr.core.models import Entry, EntryType
from bibmgr.operations.formatters import CitationFormatter


class TestCitationFormatter:
    """Test citation formatting."""

    @pytest.fixture
    def article_entry(self):
        """Create test article entry."""
        return Entry(
            key="smith2023",
            type=EntryType.ARTICLE,
            title="Deep Learning Advances",
            author="Smith, John and Doe, Jane",
            journal="Nature Machine Intelligence",
            volume="5",
            number="3",
            pages="123--145",
            year=2023,
            doi="10.1038/s42256-023-00001-9",
        )

    @pytest.fixture
    def book_entry(self):
        """Create test book entry."""
        return Entry(
            key="johnson2022",
            type=EntryType.BOOK,
            title="Machine Learning Fundamentals",
            author="Johnson, Alice",
            publisher="MIT Press",
            year=2022,
            isbn="978-0-262-04482-0",
        )

    @pytest.fixture
    def conference_entry(self):
        """Create test conference paper entry."""
        return Entry(
            key="lee2023",
            type=EntryType.INPROCEEDINGS,
            title="Efficient Transformers for Vision",
            author="Lee, David and Park, Sarah",
            booktitle="Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition",
            pages="1234--1243",
            year=2023,
            address="Vancouver, Canada",
        )

    def test_apa_format(self, article_entry, book_entry):
        """Test APA citation format."""
        formatter = CitationFormatter(style="apa")

        # Article
        apa_article = formatter.format(article_entry)
        assert "Smith, J., & Doe, J. (2023)" in apa_article
        assert "Deep Learning Advances" in apa_article
        assert "Nature Machine Intelligence" in apa_article
        assert "5(3), 123-145" in apa_article
        assert "https://doi.org/10.1038/s42256-023-00001-9" in apa_article

        # Book
        apa_book = formatter.format(book_entry)
        assert "Johnson, A. (2022)" in apa_book
        assert "Machine Learning Fundamentals" in apa_book
        assert "MIT Press" in apa_book

    def test_mla_format(self, article_entry, book_entry):
        """Test MLA citation format."""
        formatter = CitationFormatter(style="mla")

        # Article
        mla_article = formatter.format(article_entry)
        assert "Smith, John, and Jane Doe" in mla_article
        assert '"Deep Learning Advances"' in mla_article
        assert "Nature Machine Intelligence" in mla_article
        assert "vol. 5, no. 3" in mla_article
        assert "pp. 123-145" in mla_article

        # Book
        mla_book = formatter.format(book_entry)
        assert "Johnson, Alice" in mla_book
        assert "Machine Learning Fundamentals" in mla_book
        assert "MIT Press, 2022" in mla_book

    def test_chicago_format(self, article_entry, book_entry):
        """Test Chicago citation format."""
        formatter = CitationFormatter(style="chicago")

        # Article
        chicago_article = formatter.format(article_entry)
        assert "Smith, John, and Jane Doe" in chicago_article
        assert '"Deep Learning Advances."' in chicago_article
        assert "Nature Machine Intelligence" in chicago_article
        assert "5, no. 3 (2023)" in chicago_article

        # Book
        chicago_book = formatter.format(book_entry)
        assert "Johnson, Alice" in chicago_book
        assert "Machine Learning Fundamentals" in chicago_book
        assert "MIT Press, 2022" in chicago_book

    def test_bibtex_format(self, article_entry, conference_entry):
        """Test BibTeX citation format."""
        formatter = CitationFormatter(style="bibtex")

        # Article
        bibtex = formatter.format(article_entry)
        assert "@article{smith2023," in bibtex
        assert "  author = {Smith, John and Doe, Jane}," in bibtex
        assert "  title = {Deep Learning Advances}," in bibtex
        assert "  journal = {Nature Machine Intelligence}," in bibtex
        assert "  volume = {5}," in bibtex
        assert "  number = {3}," in bibtex
        assert "  pages = {123--145}," in bibtex
        assert "  year = {2023}," in bibtex
        assert "  doi = {10.1038/s42256-023-00001-9}," in bibtex

        # Conference
        conf_bibtex = formatter.format(conference_entry)
        assert "@inproceedings{lee2023," in conf_bibtex
        assert (
            "  booktitle = {Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition},"
            in conf_bibtex
        )

    def test_custom_format(self, article_entry):
        """Test custom citation format."""
        formatter = CitationFormatter(
            style="custom", template="{authors} ({year}). {title}. {journal}."
        )

        custom = formatter.format(article_entry)
        assert (
            custom
            == "Smith, John and Doe, Jane (2023). Deep Learning Advances. Nature Machine Intelligence."
        )

    def test_format_with_missing_fields(self):
        """Test formatting with missing fields."""
        entry = Entry(
            key="test2023",
            type=EntryType.MISC,
            title="Test Entry",
            year=2023,
        )

        formatter = CitationFormatter(style="apa")
        result = formatter.format(entry)
        assert "Test Entry" in result
        assert "2023" in result
        assert result.endswith(".")

    def test_multiple_authors_formatting(self):
        """Test formatting with different numbers of authors."""
        # Three authors
        entry = Entry(
            key="test2023",
            type=EntryType.ARTICLE,
            title="Test Article",
            author="Smith, John and Doe, Jane and Brown, Bob",
            journal="Test Journal",
            year=2023,
        )

        apa_formatter = CitationFormatter(style="apa")
        apa = apa_formatter.format(entry)
        assert "Smith, J., Doe, J., & Brown, B." in apa

        mla_formatter = CitationFormatter(style="mla")
        mla = mla_formatter.format(entry)
        assert "Smith, John, et al." in mla  # MLA uses et al. for 3+ authors

    def test_special_characters_in_title(self):
        """Test formatting titles with special characters."""
        entry = Entry(
            key="test2023",
            type=EntryType.ARTICLE,
            title="Machine Learning: A Review & Analysis",
            author="Smith, John",
            journal="AI Review",
            year=2023,
        )

        formatter = CitationFormatter(style="apa")
        result = formatter.format(entry)
        assert "Machine Learning: A Review & Analysis" in result

    def test_format_thesis_entries(self):
        """Test formatting thesis entries."""
        phd_entry = Entry(
            key="smith2023",
            type=EntryType.PHDTHESIS,
            title="Advanced Machine Learning Techniques",
            author="Smith, John",
            school="MIT",
            year=2023,
        )

        formatter = CitationFormatter(style="apa")
        result = formatter.format(phd_entry)
        assert "Smith, J. (2023)" in result
        assert "Advanced Machine Learning Techniques" in result
        assert "[Doctoral dissertation, MIT]" in result

    def test_format_with_url(self):
        """Test formatting entries with URLs."""
        entry = Entry(
            key="test2023",
            type=EntryType.MISC,
            title="Online Resource",
            author="Smith, John",
            year=2023,
            url="https://example.com/resource",
        )

        formatter = CitationFormatter(style="apa")
        result = formatter.format(entry)
        assert "https://example.com/resource" in result

    def test_conference_paper_formatting(self, conference_entry):
        """Test conference paper specific formatting."""
        formatter = CitationFormatter(style="apa")
        result = formatter.format(conference_entry)

        assert "Lee, D., & Park, S. (2023)" in result
        assert "Efficient Transformers for Vision" in result
        assert "Proceedings of the IEEE Conference" in result
        assert "1234-1243" in result
        assert "Vancouver, Canada" in result

    def test_custom_template_placeholders(self):
        """Test custom templates with various placeholders."""
        entry = Entry(
            key="test2023",
            type=EntryType.ARTICLE,
            title="Test Article",
            author="Smith, John",
            journal="Nature",
            volume="500",
            pages="123--145",
            year=2023,
            doi="10.1038/nature12345",
        )

        templates = [
            ("{authors} - {title}", "Smith, John - Test Article"),
            ("{title} ({year})", "Test Article (2023)"),
            ("{journal} {volume}:{pages}", "Nature 500:123--145"),
            ("DOI: {doi}", "DOI: 10.1038/nature12345"),
        ]

        for template, expected in templates:
            formatter = CitationFormatter(style="custom", template=template)
            assert formatter.format(entry) == expected

    def test_format_error_handling(self):
        """Test error handling in formatting."""
        formatter = CitationFormatter(style="invalid_style")

        entry = Entry(
            key="test2023",
            type=EntryType.ARTICLE,
            title="Test",
            year=2023,
        )

        with pytest.raises(ValueError, match="Unsupported citation style"):
            formatter.format(entry)

        # Custom format without template
        formatter = CitationFormatter(style="custom")
        with pytest.raises(ValueError, match="No template provided"):
            formatter.format(entry)
