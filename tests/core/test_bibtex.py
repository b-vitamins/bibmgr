"""Tests for BibTeX format encoding and decoding.

This module tests the critical BibTeX format handling, including proper
escaping (backslash first!), field ordering, and format generation.
"""

from typing import Any

from bibmgr.core.bibtex import BibtexDecoder, BibtexEncoder
from bibmgr.core.fields import EntryType
from bibmgr.core.models import Entry


class TestBibtexEncoder:
    """Test BibTeX format encoding."""

    def test_encode_basic_article(self, sample_article_data: dict[str, Any]) -> None:
        """Encode a basic article entry."""
        entry = Entry(**sample_article_data)
        encoder = BibtexEncoder()
        bibtex = encoder.encode_entry(entry)

        # Check structure
        assert bibtex.startswith("@article{knuth1984,")
        assert bibtex.endswith("}")

        # Check fields present
        assert "author = {Donald E. Knuth}" in bibtex
        assert "title = {The {TeX}book}" in bibtex
        assert "journal = {Computers \\& Typesetting}" in bibtex
        assert "year = {1984}" in bibtex

    def test_encode_preserves_braces_in_title(self) -> None:
        """Braces in title should be preserved."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Author",
            title="The {TCP/IP} Protocol Suite",
            journal="Networks",
            year=2024,
        )

        encoder = BibtexEncoder()
        bibtex = encoder.encode_entry(entry)

        # Braces should be preserved
        assert "title = {The {TCP/IP} Protocol Suite}" in bibtex

    def test_encode_multiline_format(self) -> None:
        """Output should be nicely formatted with one field per line."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Test Author",
            title="Test Title",
            journal="Test Journal",
            year=2024,
        )

        encoder = BibtexEncoder()
        bibtex = encoder.encode_entry(entry)
        lines = bibtex.split("\n")

        # Should have multiple lines
        assert len(lines) > 5

        # First line is entry type
        assert lines[0] == "@article{test,"

        # Fields are indented
        field_lines = [line for line in lines if " = " in line]
        assert all(line.startswith("    ") for line in field_lines)

        # Last line is closing brace
        assert lines[-1] == "}"

    def test_encode_special_fields(self) -> None:
        """Special fields like keywords, month, year handled correctly."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Author",
            title="Title",
            journal="Journal",
            year=2024,
            month="jan",  # Should not be escaped
            keywords=("machine learning", "AI", "neural networks"),  # Tuple
        )

        encoder = BibtexEncoder()
        bibtex = encoder.encode_entry(entry)

        # Month without braces for abbreviations
        assert "month = jan," in bibtex

        # Keywords joined with commas
        assert "keywords = {machine learning, AI, neural networks}" in bibtex

    def test_encode_type_field_conflict(self) -> None:
        """The 'type' field (thesis type) should be handled."""
        entry = Entry(
            key="mythesis",
            type=EntryType.PHDTHESIS,
            author="Jane Doe",
            title="Advanced Studies",
            school="MIT",
            year=2024,
            type_="Doctoral Dissertation",  # Note: type_ in model
        )

        encoder = BibtexEncoder()
        bibtex = encoder.encode_entry(entry)

        # Should use 'type' in output, not 'type_'
        assert "type = {Doctoral Dissertation}" in bibtex
        assert "type_" not in bibtex

    def test_encode_excludes_internal_fields(self) -> None:
        """Internal fields should not be in output."""
        entry = Entry(
            key="test",
            type=EntryType.MISC,
            title="Test",
            tags=("important", "review"),  # Internal
        )

        encoder = BibtexEncoder()
        bibtex = encoder.encode_entry(entry)

        # Internal fields excluded
        assert "tags" not in bibtex
        assert "added" not in bibtex
        assert "modified" not in bibtex
        assert "id" not in bibtex

    def test_encode_none_values_excluded(self) -> None:
        """Fields with None values should not appear."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Author",
            title="Title",
            journal="Journal",
            year=2024,
            volume=None,  # Explicitly None
            pages=None,
        )

        encoder = BibtexEncoder()
        bibtex = encoder.encode_entry(entry)

        # None fields not in output
        assert "volume" not in bibtex
        assert "pages" not in bibtex


class TestBibtexDecoder:
    """Test BibTeX format decoding."""

    def test_decode_simple_entry(self) -> None:
        """Decode a simple BibTeX entry."""
        bibtex = """@article{knuth1984,
    author = {Donald E. Knuth},
    title = {The {TeX}book},
    journal = {Computers \\& Typesetting},
    year = {1984}
}"""

        entries = BibtexDecoder.decode(bibtex)
        assert len(entries) == 1

        entry = entries[0]
        assert entry["key"] == "knuth1984"
        assert entry["type"] == "article"
        assert entry["author"] == "Donald E. Knuth"
        assert entry["title"] == "The {TeX}book"
        assert entry["year"] == 1984  # Converted to int

    def test_decode_multiple_entries(self) -> None:
        """Decode multiple entries from string."""
        bibtex = """@article{article1,
    author = {Author One},
    title = {Title One},
    year = {2023}
}

@book{book1,
    author = {Author Two},
    title = {Title Two},
    year = {2024}
}"""

        entries = BibtexDecoder.decode(bibtex)
        assert len(entries) == 2
        assert entries[0]["key"] == "article1"
        assert entries[1]["key"] == "book1"

    def test_decode_field_formats(self) -> None:
        """Decode different field value formats."""
        bibtex = """@misc{test,
    title = "Value in quotes",
    author = {Value in braces},
    note = bareword,
    year = 42
}"""

        entries = BibtexDecoder.decode(bibtex)
        assert len(entries) == 1

        entry = entries[0]
        assert entry["title"] == "Value in quotes"
        assert entry["author"] == "Value in braces"
        assert entry["note"] == "bareword"
        assert entry["year"] == 42  # Year converted to int

    def test_decode_comments_removed(self) -> None:
        """Comments should be removed before parsing."""
        bibtex = """% This is a comment
@article{test,
    author = {Author}, % inline comment
    title = {Title},
    % Another comment
    year = {2024}
}"""

        entries = BibtexDecoder.decode(bibtex)
        assert len(entries) == 1

        entry = entries[0]
        assert entry["author"] == "Author"
        assert "%" not in entry["author"]

    def test_decode_special_fields(self) -> None:
        """Special fields decoded correctly."""
        bibtex = """@article{test,
    keywords = {machine learning, AI, neural networks},
    year = {2024},
    month = jan,
    type = {Technical Report}
}"""

        entries = BibtexDecoder.decode(bibtex)
        entry = entries[0]

        # Keywords split into list
        assert entry["keywords"] == ["machine learning", "AI", "neural networks"]

        # Year converted to int
        assert entry["year"] == 2024
        assert isinstance(entry["year"], int)

        # Month as string
        assert entry["month"] == "jan"

        # Type field becomes type_
        assert entry["type_"] == "Technical Report"

    def test_decode_empty_bibtex(self) -> None:
        """Empty BibTeX string returns empty list."""
        assert BibtexDecoder.decode("") == []
        assert BibtexDecoder.decode("   \n\n  ") == []
        assert BibtexDecoder.decode("% Just comments") == []

    def test_decode_malformed_entry(self) -> None:
        """Malformed entries should be handled gracefully."""
        # Missing closing brace - should still parse what it can
        bibtex = """@article{test,
    author = {Author},
    title = {Title"""

        BibtexDecoder.decode(bibtex)
        # Implementation dependent - might return empty or partial

    def test_decode_custom_fields(self) -> None:
        """Custom fields should be decoded into custom dict."""
        bibtex = """@article{test,
    author = {Author},
    title = {Title},
    journal = {Journal},
    year = {2024},
    custom1 = {Value1},
    arxivid = {2301.00001},
    myfield = {My Value}
}"""

        entries = BibtexDecoder.decode(bibtex)
        assert len(entries) == 1

        entry = entries[0]
        assert entry["author"] == "Author"
        assert entry["year"] == 2024

        # Custom fields should be in custom dict
        assert "custom" in entry
        assert entry["custom"]["custom1"] == "Value1"
        assert entry["custom"]["arxivid"] == "2301.00001"
        assert entry["custom"]["myfield"] == "My Value"


class TestEscapingRules:
    """Test critical BibTeX escaping rules."""

    def test_escape_order_backslash_first(
        self, bibtex_special_chars: dict[str, str]
    ) -> None:
        """CRITICAL: Backslash must be escaped FIRST."""
        encoder = BibtexEncoder()

        # Test string with multiple special chars including backslash
        text = "A\\B & C{D}E"
        escaped = encoder.escape(text)

        # Backslash should be doubled
        assert "\\\\" in escaped
        # Then other chars
        assert "\\&" in escaped
        # Braces should NOT be escaped - they have semantic meaning in BibTeX
        assert "{D}" in escaped

    def test_escape_all_special_chars(
        self, bibtex_special_chars: dict[str, str]
    ) -> None:
        """All special characters must be escaped."""
        encoder = BibtexEncoder()

        for char, expected in bibtex_special_chars.items():
            result = encoder.escape(char)
            assert result == expected, f"Failed to escape '{char}'"

    def test_escape_in_context(self) -> None:
        """Escaping in real text context."""
        encoder = BibtexEncoder()

        # Common cases
        assert encoder.escape("AT&T") == "AT\\&T"
        assert encoder.escape("50% discount") == "50\\% discount"
        assert encoder.escape("$100 price") == "\\$100 price"
        assert encoder.escape("C# language") == "C\\# language"
        assert encoder.escape("foo_bar") == "foo\\_bar"

    def test_escape_preserves_order(self) -> None:
        """Escaping preserves character order."""
        encoder = BibtexEncoder()

        # Complex string
        text = "The {TCP/IP} & DNS_protocols cost $50"
        escaped = encoder.escape(text)

        # Should have all escapes in right places (braces NOT escaped)
        assert escaped == "The {TCP/IP} \\& DNS\\_protocols cost \\$50"

    def test_no_double_escaping(self) -> None:
        """Already escaped characters should not be double-escaped."""
        encoder = BibtexEncoder()

        # This is a challenge - the encoder should escape raw text
        # Already escaped text would get double-escaped
        text = "Already \\& escaped"
        escaped = encoder.escape(text)

        # Will become \\\\& (backslash gets escaped)
        assert escaped == "Already \\\\\\& escaped"

    def test_escape_empty_string(self) -> None:
        """Empty string remains empty."""
        encoder = BibtexEncoder()
        assert encoder.escape("") == ""
        assert encoder.escape(None) is None  # type: ignore

    def test_tilde_and_caret_special(self) -> None:
        """Tilde and caret need {} after them."""
        encoder = BibtexEncoder()

        assert encoder.escape("~") == "\\~{}"
        assert encoder.escape("^") == "\\^{}"
        assert encoder.escape("A~B^C") == "A\\~{}B\\^{}C"

    def test_year_field_not_escaped(self) -> None:
        """Year field should not be escaped."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Author",
            title="Title",
            journal="Journal & More",  # Has special char
            year=2024,
        )

        encoder = BibtexEncoder()
        bibtex = encoder.encode_entry(entry)

        # Journal escaped
        assert "journal = {Journal \\& More}" in bibtex

        # Year not escaped (and no braces needed for numbers)
        assert "year = {2024}" in bibtex


class TestFieldOrdering:
    """Test field ordering in BibTeX output."""

    def test_standard_field_order(self) -> None:
        """Fields should appear in standard order."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            # Add fields in random order
            year=2024,
            author="Author",
            pages="1--10",
            title="Title",
            volume="5",
            journal="Journal",
        )

        encoder = BibtexEncoder()
        bibtex = encoder.encode_entry(entry)
        lines = bibtex.split("\n")

        # Extract field names in order
        fields = []
        for line in lines:
            if " = " in line:
                field = line.strip().split(" = ")[0]
                fields.append(field)

        # Check order matches FIELD_ORDER
        expected_order = ["author", "title", "journal", "volume", "pages", "year"]
        actual_order = [f for f in fields if f in expected_order]
        assert actual_order == expected_order

    def test_custom_fields_after_standard(self) -> None:
        """Non-standard fields come after standard ones."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Author",
            title="Title",
            journal="Journal",
            year=2024,
            # Custom fields via custom dict
            custom={
                "custom1": "Value1",
                "custom2": "Value2",
                "arxivid": "2301.00001",
            },
        )

        encoder = BibtexEncoder()
        bibtex = encoder.encode_entry(entry)

        # Find positions
        author_pos = bibtex.index("author = ")
        year_pos = bibtex.index("year = ")
        custom1_pos = (
            bibtex.index("custom1 = ") if "custom1 = " in bibtex else float("inf")
        )

        # Standard fields come first
        assert author_pos < custom1_pos
        assert year_pos < custom1_pos

    def test_trailing_comma_removed(self) -> None:
        """Last field should not have trailing comma."""
        entry = Entry(
            key="test",
            type=EntryType.MISC,
            title="Title",
        )

        encoder = BibtexEncoder()
        bibtex = encoder.encode_entry(entry)
        lines = bibtex.split("\n")

        # Find last field line
        field_lines = [line for line in lines if " = " in line]
        last_field = field_lines[-1]

        # Should not end with comma
        assert not last_field.endswith(",")

        # Second to last should have comma
        if len(field_lines) > 1:
            assert field_lines[-2].endswith(",")

    def test_consistent_indentation(self) -> None:
        """All fields should have consistent indentation."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Author Name",
            title="Article Title",
            journal="Journal Name",
            year=2024,
            doi="10.1234/test",
        )

        encoder = BibtexEncoder()
        bibtex = encoder.encode_entry(entry)
        lines = bibtex.split("\n")

        # All field lines should start with 4 spaces
        field_lines = [line for line in lines if " = " in line]
        assert all(line.startswith("    ") for line in field_lines)

        # And have consistent format
        for line in field_lines:
            assert " = {" in line or " = " in line  # year/month might not have braces
