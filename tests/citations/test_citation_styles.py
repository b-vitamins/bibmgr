"""Comprehensive tests for citation style formatting."""

from unittest.mock import Mock

import pytest

from bibmgr.citations.styles import (
    APAStyle,
    AuthorFormatter,
    ChicagoStyle,
    CitationStyle,
    CSLStyle,
    DateFormatter,
    FormattingCache,
    IEEEStyle,
    MLAStyle,
    StyleOptions,
    StyleRegistry,
    TitleFormatter,
    validate_doi,
    validate_url,
)
from bibmgr.core.models import Entry, EntryType


class TestStyleOptions:
    """Test citation style configuration options."""

    def test_default_options(self):
        """Test default style options."""
        options = StyleOptions()

        assert options.et_al_min == 3
        assert options.et_al_use_first == 1
        assert options.use_italics is True
        assert options.use_quotes is False
        assert options.include_doi is True
        assert options.include_url is False
        assert options.page_prefix == "pp."
        assert options.name_delimiter == ", "

    def test_custom_options(self):
        """Test custom style options."""
        options = StyleOptions(
            et_al_min=6,
            et_al_use_first=3,
            use_italics=False,
            use_quotes=True,
            include_doi=False,
            include_url=True,
        )

        assert options.et_al_min == 6
        assert options.et_al_use_first == 3
        assert options.use_italics is False
        assert options.use_quotes is True

    def test_options_validation(self):
        """Test validation of style options."""
        # Invalid et_al configuration
        with pytest.raises(ValueError, match="et_al_use_first.*et_al_min"):
            StyleOptions(et_al_min=3, et_al_use_first=5)

        # Empty page prefix should be allowed (used by APA style)
        opts = StyleOptions(page_prefix="")
        assert opts.page_prefix == ""

    def test_options_merge(self):
        """Test merging style options."""
        base = StyleOptions(et_al_min=3, include_doi=True)
        override = StyleOptions(et_al_min=6, include_url=True)

        merged = base.merge(override)
        assert merged.et_al_min == 6
        assert merged.include_doi is True
        assert merged.include_url is True


class TestAuthorFormatter:
    """Test author name formatting."""

    def test_single_author_formats(self):
        """Test different single author formats."""
        formatter = AuthorFormatter()

        # Last, First
        assert formatter.format("Smith, John", "last-first") == "Smith, J."
        assert formatter.format("Smith, John David", "last-first") == "Smith, J. D."

        # First Last
        assert formatter.format("Smith, John", "first-last") == "J. Smith"
        assert formatter.format("Smith, John David", "first-last") == "J. D. Smith"

        # Last only
        assert formatter.format("Smith, John", "last-only") == "Smith"

        # Full name
        assert formatter.format("Smith, John David", "full") == "Smith, John David"

    def test_multiple_authors(self):
        """Test formatting multiple authors."""
        formatter = AuthorFormatter()

        authors = ["Smith, John", "Doe, Jane", "Johnson, Bob"]

        # Default formatting
        result = formatter.format_multiple(authors)
        assert "Smith" in result
        assert "Doe" in result
        assert "Johnson" in result

        # With et al.
        result = formatter.format_multiple(authors, et_al_min=3, et_al_use_first=1)
        assert "Smith" in result
        assert "et al." in result
        assert "Doe" not in result

    def test_and_separator(self):
        """Test different 'and' separators."""
        formatter = AuthorFormatter()

        authors = ["Smith, John", "Doe, Jane"]

        # Ampersand
        result = formatter.format_multiple(authors, and_sep="&")
        assert "&" in result

        # Word 'and'
        result = formatter.format_multiple(authors, and_sep="and")
        assert " and " in result

    def test_organization_authors(self):
        """Test formatting organization names."""
        formatter = AuthorFormatter()

        # Organization in braces
        assert (
            formatter.format("{World Health Organization}", "last-first")
            == "World Health Organization"
        )

        # Corporate author
        assert formatter.format("{Google Inc.}", "last-first") == "Google Inc."

    def test_unicode_authors(self):
        """Test Unicode author names."""
        formatter = AuthorFormatter()

        # Unicode names
        assert formatter.format("Müller, Jürgen", "last-first") == "Müller, J."
        assert formatter.format("李, 明", "last-first") == "李, 明"

        # Transliteration option
        formatter_ascii = AuthorFormatter(transliterate=True)
        assert formatter_ascii.format("Müller, Jürgen", "last-first") == "Mueller, J."

    def test_hyphenated_names(self):
        """Test hyphenated author names."""
        formatter = AuthorFormatter()

        assert formatter.format("Smith-Jones, Mary", "last-first") == "Smith-Jones, M."
        assert (
            formatter.format("Smith-Jones, Mary-Anne", "last-first")
            == "Smith-Jones, M.-A."
        )

    def test_suffix_handling(self):
        """Test author name suffixes."""
        formatter = AuthorFormatter()

        assert (
            formatter.format("King, Martin Luther, Jr.", "last-first")
            == "King, M. L., Jr."
        )
        assert formatter.format("Smith, John, III", "last-first") == "Smith, J., III"


class TestDateFormatter:
    """Test date formatting."""

    def test_year_formatting(self):
        """Test year formatting."""
        formatter = DateFormatter()

        entry = Mock(year=2024)
        assert formatter.format_year(entry) == "2024"

        entry_no_year = Mock(year=None)
        assert formatter.format_year(entry_no_year) == "n.d."

    def test_month_formatting(self):
        """Test month formatting."""
        formatter = DateFormatter()

        # Numeric months
        assert formatter.format_month("1") == "January"
        assert formatter.format_month("12") == "December"

        # Abbreviated
        assert formatter.format_month("1", abbreviate=True) == "Jan."
        assert formatter.format_month("12", abbreviate=True) == "Dec."

        # Already named
        assert formatter.format_month("January") == "January"
        assert formatter.format_month("jan") == "January"

    def test_full_date_formatting(self):
        """Test complete date formatting."""
        formatter = DateFormatter()

        entry = Mock(year=2024, month="3", day="15")

        # Default format
        assert formatter.format_date(entry) == "March 15, 2024"

        # ISO format
        assert formatter.format_date(entry, format="iso") == "2024-03-15"

        # Custom format
        assert (
            formatter.format_date(entry, format="{day} {month} {year}")
            == "15 March 2024"
        )

    def test_date_ranges(self):
        """Test date range formatting."""
        formatter = DateFormatter()

        assert formatter.format_range("2023", "2024") == "2023–2024"
        assert (
            formatter.format_range("January", "March", year="2024")
            == "January–March 2024"
        )


class TestTitleFormatter:
    """Test title formatting."""

    def test_case_transformations(self):
        """Test title case transformations."""
        formatter = TitleFormatter()

        title = "The Quick Brown Fox Jumps Over the Lazy Dog"

        # Sentence case
        assert (
            formatter.format(title, case="sentence")
            == "The quick brown fox jumps over the lazy dog"
        )

        # Title case
        assert (
            formatter.format(title, case="title")
            == "The Quick Brown Fox Jumps Over the Lazy Dog"
        )

        # Upper case
        assert (
            formatter.format(title, case="upper")
            == "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"
        )

        # Lower case
        assert (
            formatter.format(title, case="lower")
            == "the quick brown fox jumps over the lazy dog"
        )

    def test_preserve_acronyms(self):
        """Test preserving acronyms in title case."""
        formatter = TitleFormatter()

        title = "NASA and IEEE Standards for XML Processing"
        result = formatter.format(title, case="sentence", preserve_acronyms=True)

        assert "NASA" in result  # Should preserve
        assert "IEEE" in result  # Should preserve
        assert "XML" in result  # Should preserve

    def test_latex_command_handling(self):
        """Test LaTeX commands in titles."""
        formatter = TitleFormatter()

        title = r"The \textbf{Important} \emph{Study} of \LaTeX{}"

        # Strip commands
        clean = formatter.format(title, strip_latex=True)
        assert "\\textbf" not in clean
        assert "Important" in clean

        # Preserve commands
        preserved = formatter.format(title, strip_latex=False)
        assert "\\textbf{Important}" in preserved

    def test_quote_and_italic_formatting(self):
        """Test adding quotes or italics."""
        formatter = TitleFormatter()

        title = "Test Article"

        # Add quotes
        quoted = formatter.format(title, quotes=True)
        assert quoted == '"Test Article"'

        # Add italics (markdown style)
        italic = formatter.format(title, italics=True)
        assert italic == "*Test Article*"

        # Both (quotes take precedence)
        both = formatter.format(title, quotes=True, italics=True)
        assert both == '"Test Article"'


class TestAPAStyle:
    """Test APA citation style."""

    def test_inline_citation(self, sample_entries):
        """Test APA inline citations."""
        style = APAStyle()

        # Single author
        entry = sample_entries["simple_article"]
        assert style.format_inline(entry) == "(Smith, 2024)"

        # Multiple authors
        entry = sample_entries["multiple_authors"]
        result = style.format_inline(entry)
        assert result == "(Doe et al., 2023)"

        # No author
        entry = sample_entries["no_author"]
        result = style.format_inline(entry)
        assert "Anonymous" in result or "n.a." in result

        # No year
        entry = sample_entries["no_year"]
        result = style.format_inline(entry)
        assert "n.d." in result

    def test_bibliography_article(self, sample_entries):
        """Test APA bibliography for articles."""
        style = APAStyle()
        entry = sample_entries["simple_article"]

        result = style.format_bibliography(entry)

        # Check components
        assert "Smith, J." in result
        assert "(2024)" in result
        assert "Quantum computing advances" in result  # Sentence case
        assert "Nature" in result  # Italicized
        assert "123" in result  # Volume
        assert "45–67" in result or "45--67" in result  # Pages
        assert "https://doi.org/10.1038/nature.2024.123" in result

    def test_bibliography_book(self, sample_entries):
        """Test APA bibliography for books."""
        style = APAStyle()
        entry = sample_entries["book_entry"]

        result = style.format_bibliography(entry)

        assert "Knuth, D. E." in result
        assert "(1997)" in result
        assert "The art of computer programming" in result  # Sentence case
        assert "(3rd ed.)" in result  # Edition
        assert "Addison-Wesley" in result

    def test_bibliography_conference(self, sample_entries):
        """Test APA bibliography for conference papers."""
        style = APAStyle()
        entry = sample_entries["conference_paper"]

        result = style.format_bibliography(entry)

        assert "Lee, K., & Park, J." in result
        assert "(2024, July)" in result  # Month included
        assert "Neural architecture search" in result
        assert "Proceedings" in result
        assert "123–134" in result or "123--134" in result

    def test_sort_order(self, sample_entries):
        """Test APA sort order."""
        style = APAStyle()
        entries = [
            sample_entries["simple_article"],
            sample_entries["multiple_authors"],
            sample_entries["book_entry"],
        ]

        sorted_entries = style.sort_entries(entries)

        # Should be alphabetical by author, then year
        assert sorted_entries[0].author and sorted_entries[0].author.startswith(
            "Doe"
        )  # Doe, 2023
        assert sorted_entries[1].author and sorted_entries[1].author.startswith(
            "Knuth"
        )  # Knuth, 1997
        assert sorted_entries[2].author and sorted_entries[2].author.startswith(
            "Smith"
        )  # Smith, 2024


class TestMLAStyle:
    """Test MLA citation style."""

    def test_inline_citation(self, sample_entries):
        """Test MLA inline citations."""
        style = MLAStyle()

        # Author only (no year in MLA inline)
        entry = sample_entries["simple_article"]
        assert style.format_inline(entry) == "(Smith)"

        # Multiple authors
        entry = sample_entries["multiple_authors"]
        result = style.format_inline(entry)
        assert result == "(Doe et al.)"

    def test_bibliography_article(self, sample_entries):
        """Test MLA bibliography for articles."""
        style = MLAStyle()
        entry = sample_entries["simple_article"]

        result = style.format_bibliography(entry)

        # MLA format: Author. "Title." Journal, vol. #, no. #, Year, pp. #-#.
        assert "Smith, John." in result or "Smith, J." in result
        assert '"Quantum Computing Advances."' in result  # Quoted
        assert "Nature" in result  # Italicized
        assert "vol. 123" in result
        assert "2024" in result
        assert "pp. 45-67" in result or "pp. 45–67" in result

    def test_bibliography_book(self, sample_entries):
        """Test MLA bibliography for books."""
        style = MLAStyle()
        entry = sample_entries["book_entry"]

        result = style.format_bibliography(entry)

        assert "Knuth, Donald E." in result or "Knuth, D. E." in result
        assert "The Art of Computer Programming" in result  # Italicized, title case
        assert "3rd ed." in result
        assert "Addison-Wesley" in result
        assert "1997" in result


class TestChicagoStyle:
    """Test Chicago citation style."""

    def test_inline_citation(self, sample_entries):
        """Test Chicago inline citations (author-date)."""
        style = ChicagoStyle()

        entry = sample_entries["simple_article"]
        assert style.format_inline(entry) == "(Smith 2024)"

        # Multiple authors
        entry = sample_entries["multiple_authors"]
        result = style.format_inline(entry)
        assert "Doe et al. 2023" in result

    def test_bibliography_article(self, sample_entries):
        """Test Chicago bibliography for articles."""
        style = ChicagoStyle(notes_bibliography=True)
        entry = sample_entries["simple_article"]

        result = style.format_bibliography(entry)

        # Chicago format: Author. "Title." Journal vol. # (Year): pages.
        assert "Smith, John." in result or "Smith, J." in result
        assert '"Quantum Computing Advances."' in result
        assert "*Nature* 123" in result  # Journal is italicized
        assert "(2024)" in result
        assert "45-67" in result or "45–67" in result

    def test_footnote_format(self, sample_entries):
        """Test Chicago footnote format."""
        style = ChicagoStyle(notes_bibliography=True)
        entry = sample_entries["book_entry"]

        result = style.format_footnote(entry, page="42")

        assert "Knuth" in result
        assert "Computer Programming" in result
        assert "42" in result  # Specific page


class TestIEEEStyle:
    """Test IEEE citation style."""

    def test_inline_citation_numbering(self):
        """Test IEEE numbered citations."""
        style = IEEEStyle()

        # IEEE uses numbers assigned during bibliography compilation
        entries = [Mock(key="a"), Mock(key="b"), Mock(key="c")]
        style.assign_numbers(entries)  # type: ignore[arg-type]

        assert style.format_inline(entries[0]) == "[1]"
        assert style.format_inline(entries[1]) == "[2]"
        assert style.format_inline(entries[2]) == "[3]"

    def test_bibliography_article(self, sample_entries):
        """Test IEEE bibliography for articles."""
        style = IEEEStyle()
        entry = sample_entries["simple_article"]

        result = style.format_bibliography(entry, number=1)

        # IEEE format: [1] J. Smith, "Title," Journal, vol. #, pp. #-#, Year.
        assert "[1]" in result
        assert "J. Smith" in result  # Initials first
        assert '"Quantum Computing Advances,"' in result
        assert "Nature" in result  # Italicized
        assert "vol. 123" in result
        assert "pp. 45-67" in result or "pp. 45–67" in result
        assert "2024" in result

    def test_bibliography_conference(self, sample_entries):
        """Test IEEE bibliography for conference papers."""
        style = IEEEStyle()
        entry = sample_entries["conference_paper"]

        result = style.format_bibliography(entry, number=1)

        assert "[1]" in result
        assert "K. Lee" in result
        assert "J. Park" in result  # Both authors with initials
        assert '"Neural Architecture Search: A Survey,"' in result
        assert "in *Proc." in result  # Booktitle is italicized
        assert "Vienna, Austria" in result
        assert "2024" in result  # Year

    def test_author_limit(self, sample_entries):
        """Test IEEE author limit (shows up to 6, then et al.)."""
        style = IEEEStyle()
        entry = sample_entries["multiple_authors"]

        result = style.format_bibliography(entry, number=1)

        # Should show all 6 authors
        assert "J. Doe" in result
        assert "F. Miller" in result
        # No et al. since we have exactly 6


class TestCSLStyle:
    """Test CSL (Citation Style Language) support."""

    def test_load_csl_style(self, csl_style_apa):
        """Test loading CSL style definition."""
        style = CSLStyle(csl_style_apa)

        assert style.info["id"] == "apa"
        assert style.info["title"] == "American Psychological Association 7th edition"

    def test_csl_inline_citation(self, csl_style_custom, sample_entries):
        """Test CSL inline citation formatting."""
        style = CSLStyle(csl_style_custom)
        entry = sample_entries["simple_article"]

        result = style.format_inline(entry)

        # Custom style uses brackets and 'and'
        assert "[Smith 2024]" == result

    def test_csl_bibliography(self, csl_style_custom, sample_entries):
        """Test CSL bibliography formatting."""
        style = CSLStyle(csl_style_custom)
        entry = sample_entries["simple_article"]

        result = style.format_bibliography(entry)

        # Custom style specifics
        assert "Smith" in result
        assert "2024." in result
        assert '"Quantum Computing Advances"' in result  # Quoted, title case

    def test_csl_from_file(self, temp_csl_dir):
        """Test loading CSL from file."""
        csl_file = temp_csl_dir / "apa.csl"
        style = CSLStyle.from_file(csl_file)

        assert style.info["id"] == "apa"

    def test_csl_validation(self):
        """Test CSL definition validation."""
        # Invalid CSL (missing required fields)
        invalid_csl = {"info": {"title": "Test"}}  # Missing 'id'

        with pytest.raises(ValueError, match="Invalid CSL"):
            CSLStyle(invalid_csl)

    def test_csl_fallback(self, sample_entries):
        """Test CSL fallback for missing elements."""
        minimal_csl = {
            "info": {"id": "minimal", "title": "Minimal"},
            "citation": {"layout": {}},
            "bibliography": {"layout": {}},
        }

        style = CSLStyle(minimal_csl)
        entry = sample_entries["simple_article"]

        # Should still produce some output
        result = style.format_bibliography(entry)
        assert "Smith" in result
        assert "2024" in result


class TestStyleRegistry:
    """Test citation style registry."""

    def test_builtin_styles(self):
        """Test registry of built-in styles."""
        registry = StyleRegistry()

        # Should have standard styles
        assert "apa" in registry
        assert "mla" in registry
        assert "chicago" in registry
        assert "ieee" in registry

    def test_register_custom_style(self):
        """Test registering custom style."""
        registry = StyleRegistry()

        custom_style = Mock(spec=CitationStyle)
        registry.register("custom", custom_style)

        assert "custom" in registry
        assert registry.get("custom") == custom_style

    def test_load_csl_styles(self, temp_csl_dir):
        """Test loading CSL styles from directory."""
        registry = StyleRegistry()
        registry.load_csl_directory(temp_csl_dir)

        # Should have loaded CSL files
        assert "apa" in registry  # From apa.csl
        assert "ieee" in registry  # From ieee.csl

    def test_style_aliases(self):
        """Test style name aliases."""
        registry = StyleRegistry()

        # Case insensitivity
        assert type(registry.get("APA")) is type(registry.get("apa"))

        # Common aliases
        assert type(registry.get("apa7")) is type(registry.get("apa"))
        assert type(registry.get("mla8")) is type(registry.get("mla"))

    def test_list_styles(self):
        """Test listing available styles."""
        registry = StyleRegistry()

        styles = registry.list_styles()
        assert "apa" in styles
        assert "mla" in styles

        # With descriptions
        detailed = registry.list_styles(detailed=True)
        assert any("APA" in str(s) for s in detailed)


class TestFormattingCache:
    """Test citation formatting cache."""

    def test_cache_basic(self, sample_entries):
        """Test basic caching functionality."""
        cache = FormattingCache(max_size=100)
        style = APAStyle()
        entry = sample_entries["simple_article"]

        # First call - cache miss
        result1 = cache.get_or_format(entry, style, "inline")
        assert cache.stats()["misses"] == 1

        # Second call - cache hit
        result2 = cache.get_or_format(entry, style, "inline")
        assert cache.stats()["hits"] == 1
        assert result1 == result2

    def test_cache_eviction(self, sample_entries):
        """Test cache eviction when full."""
        cache = FormattingCache(max_size=2)
        style = APAStyle()

        entries = list(sample_entries.values())[:3]

        # Fill cache
        cache.get_or_format(entries[0], style, "inline")
        cache.get_or_format(entries[1], style, "inline")

        # This should evict the first entry
        cache.get_or_format(entries[2], style, "inline")

        # First entry should be evicted
        cache.get_or_format(entries[0], style, "inline")
        assert cache.stats()["misses"] == 4  # Initial 3 + re-fetch

    def test_cache_invalidation(self, sample_entries):
        """Test cache invalidation."""
        cache = FormattingCache()
        style = APAStyle()
        entry = sample_entries["simple_article"]

        # Cache entry
        cache.get_or_format(entry, style, "inline")
        assert cache.stats()["hits"] == 0

        # Invalidate
        cache.invalidate(entry.key)

        # Should miss again
        cache.get_or_format(entry, style, "inline")
        assert cache.stats()["misses"] == 2

    def test_cache_different_styles(self, sample_entries):
        """Test caching with different styles."""
        cache = FormattingCache()
        entry = sample_entries["simple_article"]

        apa = APAStyle()
        mla = MLAStyle()

        # Same entry, different styles
        result_apa = cache.get_or_format(entry, apa, "inline")
        result_mla = cache.get_or_format(entry, mla, "inline")

        assert result_apa != result_mla
        assert cache.stats()["misses"] == 2  # Both are misses

    def test_cache_ttl(self, sample_entries):
        """Test cache time-to-live."""
        import time

        cache = FormattingCache(ttl=0.1)  # 100ms TTL
        style = APAStyle()
        entry = sample_entries["simple_article"]

        # Cache entry
        cache.get_or_format(entry, style, "inline")

        # Should hit immediately
        cache.get_or_format(entry, style, "inline")
        assert cache.stats()["hits"] == 1

        # Wait for expiration
        time.sleep(0.2)

        # Should miss after TTL
        cache.get_or_format(entry, style, "inline")
        assert cache.stats()["misses"] == 2


class TestValidation:
    """Test validation functions."""

    def test_doi_validation(self):
        """Test DOI validation."""
        # Valid DOIs
        assert validate_doi("10.1038/nature.2024.123")
        assert validate_doi("10.1234/test")
        assert validate_doi("https://doi.org/10.1038/nature.2024.123")

        # Invalid DOIs
        assert not validate_doi("not-a-doi")
        assert not validate_doi("10.1038")  # Incomplete
        assert not validate_doi("")

    def test_url_validation(self):
        """Test URL validation."""
        # Valid URLs
        assert validate_url("https://example.com")
        assert validate_url("http://example.com/path")
        assert validate_url("https://example.com:8080/path?query=1")

        # Invalid URLs
        assert not validate_url("not-a-url")
        assert not validate_url("example.com")  # No protocol
        assert not validate_url("ftp://example.com")  # Not HTTP(S)
        assert not validate_url("")

    def test_author_validation(self):
        """Test author name validation."""
        from bibmgr.citations.styles import validate_author

        # Valid author formats
        assert validate_author("Smith, John")
        assert validate_author("Smith, J.")
        assert validate_author("John Smith")
        assert validate_author("{World Health Organization}")

        # Invalid formats
        assert not validate_author("")
        assert not validate_author("123")  # Just numbers
        assert not validate_author("   ")  # Just whitespace


class TestEdgeCases:
    """Test edge cases in citation formatting."""

    def test_missing_required_fields(self):
        """Test handling of missing required fields."""
        style = APAStyle()

        # Minimal entry
        entry = Entry(key="test", type=EntryType.MISC)

        result = style.format_bibliography(entry)
        assert "Anonymous" in result or "n.a." in result
        assert "n.d." in result

    def test_very_long_author_list(self):
        """Test handling very long author lists."""
        style = APAStyle()

        # 20 authors
        authors = " and ".join([f"Author{i}, Name{i}" for i in range(20)])
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author=authors,
            title="Test",
            year=2024,
        )

        result = style.format_inline(entry)
        assert "et al." in result
        assert "Author19" not in result  # Should be truncated

    def test_special_characters_in_titles(self):
        """Test special characters in titles."""
        style = APAStyle()

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Smith, J.",
            title='Testing & "Special" Characters: A Study',
            journal="Test Journal",
            year=2024,
        )

        result = style.format_bibliography(entry)
        assert "&" in result or "and" in result
        assert '"' in result or "'" in result

    def test_disambiguation(self):
        """Test author/year disambiguation."""
        style = APAStyle()

        # Same author, same year
        entry1 = Entry(
            key="smith2024a",
            type=EntryType.ARTICLE,
            author="Smith, J.",
            title="First Paper",
            year=2024,
        )

        entry2 = Entry(
            key="smith2024b",
            type=EntryType.ARTICLE,
            author="Smith, J.",
            title="Second Paper",
            year=2024,
        )

        result1 = style.format_inline(entry1, disambiguate="a")
        result2 = style.format_inline(entry2, disambiguate="b")

        assert "2024a" in result1
        assert "2024b" in result2
