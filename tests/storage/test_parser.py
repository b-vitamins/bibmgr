"""Comprehensive tests for BibTeX parser functionality.

Tests parser capabilities including:
- Standard BibTeX entries
- String definitions and concatenation
- Comments and preambles
- Error recovery and reporting
- Format preservation
- Large file handling
- Edge cases and malformed input
"""

import io
import tempfile
from pathlib import Path
from typing import Any, Protocol

import pytest


class BibtexParser(Protocol):
    """Protocol for BibTeX parser interface."""

    def parse(self, text: str) -> list[Any]:
        """Parse BibTeX text and return entries."""
        ...

    def parse_file(self, path: Path) -> list[Any]:
        """Parse a BibTeX file."""
        ...

    def parse_with_preservation(self, text: str) -> tuple[list[Any], dict[str, Any]]:
        """Parse while preserving formatting and comments."""
        ...

    @property
    def errors(self) -> list[Any]:
        """Get parsing errors."""
        ...


class Entry(Protocol):
    """Protocol for bibliography entry."""

    key: str
    type: str
    title: str | None
    author: str | None
    year: int | None

    def to_bibtex(self) -> str:
        """Convert to BibTeX format."""
        ...


@pytest.fixture
def sample_bibtex():
    """Sample BibTeX content for testing."""
    return """
    @string{ACM = "ACM Press"}
    @string{YEAR = "2024"}

    % This is a comment
    @article{smith2024neural,
        author = {John Smith and Jane Doe},
        title = {Neural Networks for {NLP}},
        journal = {Machine Learning Review},
        year = YEAR,
        volume = {42},
        pages = {123--145},
        doi = {10.1234/mlr.2024.042}
    }

    @book{knuth1984tex,
        author = {Donald E. Knuth},
        title = {The {TeX}book},
        publisher = ACM,
        year = {1984},
        isbn = {0-201-13447-0}
    }

    @comment{This is a block comment that should be preserved}

    @inproceedings{lee2023attention,
        author = "Lee, " # "S." # " and Park, K.",
        title = "Attention is All You Need: " # "Revisited",
        booktitle = "Proceedings of NeurIPS",
        year = 2023
    }
    """


@pytest.fixture
def malformed_bibtex():
    """Malformed BibTeX for error recovery testing."""
    return """
    @article{good1,
        author = "Good Author",
        title = "Good Title",
        journal = "Journal",
        year = 2024
    }

    @article{missing_comma
        author = "Missing Comma"
        title = "No Comma Between Fields"
        year = 2024
    }

    @article{unclosed,
        author = "Unclosed Entry",
        title = "Missing closing brace"
        journal = "Test"

    @article{good2,
        author = "Another Good",
        title = "Should Parse",
        journal = "Journal",
        year = 2024
    }

    @article{,  % Missing key
        author = "No Key",
        title = "Entry without key"
    }
    """


class TestBasicParsing:
    """Test basic BibTeX parsing functionality."""

    def test_parse_simple_article(self, parser_factory):
        """Test parsing a simple article entry."""
        parser = parser_factory()
        text = """
        @article{test2024,
            author = "Test Author",
            title = "Test Title",
            journal = "Test Journal",
            year = 2024
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1

        entry = entries[0]
        assert entry.key == "test2024"
        assert entry.type.lower() == "article"
        assert entry.author == "Test Author"
        assert entry.title == "Test Title"
        assert entry.year == 2024

    def test_parse_multiple_entries(self, parser_factory):
        """Test parsing multiple entries."""
        parser = parser_factory()
        text = """
        @article{article1,
            title = "Article One",
            author = "Author A",
            journal = "Journal A",
            year = 2023
        }

        @book{book1,
            title = "Book One",
            author = "Author B",
            publisher = "Publisher",
            year = 2024
        }

        @misc{misc1,
            title = "Misc Entry",
            note = "Some note"
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 3

        keys = [e.key for e in entries]
        assert keys == ["article1", "book1", "misc1"]

        types = [e.type.lower() for e in entries]
        assert types == ["article", "book", "misc"]

    def test_parse_with_braces(self, parser_factory):
        """Test parsing entries with braced values."""
        parser = parser_factory()
        text = """
        @article{test,
            author = {John {von} Neumann},
            title = {Theory of {Self-Reproducing} Automata},
            journal = {{ACM} Computing Surveys}
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1

        entry = entries[0]
        # Should preserve inner braces
        assert "{von}" in entry.author or "von" in entry.author
        assert "{Self-Reproducing}" in entry.title or "Self-Reproducing" in entry.title

    def test_parse_with_quotes(self, parser_factory):
        """Test parsing entries with quoted values."""
        parser = parser_factory()
        text = """
        @article{test,
            author = "John Smith",
            title = "A Study of \\"Quotes\\" in Titles",
            journal = "Test Journal"
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1

        entry = entries[0]
        assert entry.author == "John Smith"
        assert '"Quotes"' in entry.title or '\\"Quotes\\"' in entry.title

    def test_parse_parentheses_delimiters(self, parser_factory):
        """Test parsing entries with parentheses instead of braces."""
        parser = parser_factory()
        text = """
        @article(test2024,
            author = "Test Author",
            title = "Test with Parens",
            year = 2024
        )
        """

        entries = parser.parse(text)
        assert len(entries) == 1
        assert entries[0].key == "test2024"


class TestStringDefinitions:
    """Test @string definition parsing and substitution."""

    def test_parse_string_definitions(self, parser_factory):
        """Test parsing and applying @string definitions."""
        parser = parser_factory()
        text = """
        @string{IEEE = "IEEE Computer Society"}
        @string{PROC = "Proceedings of the "}

        @article{test,
            author = "Author",
            title = "Title",
            journal = IEEE,
            year = 2024
        }

        @inproceedings{conf,
            author = "Presenter",
            title = "Conference Paper",
            booktitle = PROC # "International Conference",
            year = 2024
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 2

        # String substitution should work
        assert entries[0].journal == "IEEE Computer Society"
        assert "Proceedings of the" in entries[1].booktitle
        assert "International Conference" in entries[1].booktitle

    def test_recursive_string_definitions(self, parser_factory):
        """Test recursive string definitions."""
        parser = parser_factory()
        text = """
        @string{FIRST = "First"}
        @string{SECOND = FIRST # " Second"}
        @string{THIRD = SECOND # " Third"}

        @misc{test,
            title = THIRD,
            note = "Test"
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1
        assert entries[0].title == "First Second Third"

    def test_undefined_string_reference(self, parser_factory):
        """Test handling of undefined string references."""
        parser = parser_factory()
        text = """
        @article{test,
            author = "Author",
            title = "Title",
            journal = UNDEFINED_STRING,
            year = 2024
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1
        # Should either keep literal or handle gracefully
        assert entries[0].journal in ["UNDEFINED_STRING", None, ""]


class TestConcatenation:
    """Test string concatenation with # operator."""

    def test_simple_concatenation(self, parser_factory):
        """Test simple string concatenation."""
        parser = parser_factory()
        text = """
        @article{test,
            author = "First " # "Last",
            title = "Part 1" # ": " # "Part 2",
            year = 2024
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1

        entry = entries[0]
        assert entry.author == "First Last"
        assert entry.title == "Part 1: Part 2"

    def test_mixed_concatenation(self, parser_factory):
        """Test concatenation with mixed types."""
        parser = parser_factory()
        text = """
        @string{PREFIX = "Prefix: "}

        @article{test,
            title = PREFIX # "Main Title",
            author = "Name" # " " # {Surname},
            year = "20" # "24"
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1

        entry = entries[0]
        assert entry.title == "Prefix: Main Title"
        assert "Name" in entry.author and "Surname" in entry.author
        assert entry.year == 2024 or str(entry.year) == "2024"

    def test_number_concatenation(self, parser_factory):
        """Test concatenation with numbers."""
        parser = parser_factory()
        text = """
        @article{test,
            pages = 100 # "--" # 150,
            volume = 4 # 2,
            year = 2024
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1

        entry = entries[0]
        assert "100" in str(entry.pages) and "150" in str(entry.pages)
        assert str(entry.volume) in ["42", "4 2"]


class TestCommentsAndPreambles:
    """Test handling of comments and preambles."""

    def test_line_comments(self, parser_factory):
        """Test that line comments are handled correctly."""
        parser = parser_factory()
        text = """
        % This is a comment
        @article{test,
            % Comment inside entry
            author = "Author",  % End of line comment
            title = "Title",
            year = 2024
        }
        % Final comment
        """

        entries = parser.parse(text)
        assert len(entries) == 1
        assert entries[0].key == "test"

    def test_block_comments(self, parser_factory):
        """Test @comment blocks."""
        parser = parser_factory()
        text = """
        @comment{This is a block comment
            that spans multiple lines
            and contains @article{fake, title="Not parsed"}
        }

        @article{real,
            title = "Real Article",
            year = 2024
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1
        assert entries[0].key == "real"

    def test_preamble(self, parser_factory):
        """Test @preamble handling."""
        parser = parser_factory()
        text = """
        @preamble{"\\newcommand{\\noopsort}[1]{}"}

        @article{test,
            title = "Test",
            year = 2024
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1
        assert entries[0].key == "test"

    def test_format_preservation(self, parser_factory):
        """Test preservation of formatting and comments."""
        parser = parser_factory()
        text = """
        % Header comment
        @string{VAR = "Value"}

        @article{test,
            % Field comment
            author = "Author",
            title  = "Title",  % Note spacing
            year   = 2024      % Aligned
        }
        """

        entries, metadata = parser.parse_with_preservation(text)
        assert len(entries) == 1

        # Should preserve comments and formatting info
        assert hasattr(metadata, "comments") or hasattr(metadata, "original_text")
        # Either comments are stored or we can reconstruct original


class TestErrorHandling:
    """Test error handling and recovery."""

    def test_missing_comma(self, parser_factory):
        """Test recovery from missing comma between fields."""
        parser = parser_factory()
        text = """
        @article{test,
            author = "Author"
            title = "Title"
            year = 2024
        }
        """

        entries = parser.parse(text)
        # Should either parse with recovery or report error
        assert len(entries) <= 1
        if entries:
            assert entries[0].key == "test"
        assert len(parser.errors) > 0 or len(entries) == 1

    def test_unclosed_entry(self, parser_factory):
        """Test recovery from unclosed entry."""
        parser = parser_factory()
        text = """
        @article{unclosed,
            author = "Author",
            title = "Unclosed entry"

        @article{next,
            title = "Next entry",
            year = 2024
        }
        """

        entries = parser.parse(text)
        # Should recover and parse next entry
        keys = [e.key for e in entries]
        assert "next" in keys

    def test_missing_key(self, parser_factory):
        """Test handling of entry without key."""
        parser = parser_factory()
        text = """
        @article{,
            author = "No Key",
            title = "Entry without key"
        }

        @article{valid,
            title = "Valid entry",
            year = 2024
        }
        """

        entries = parser.parse(text)
        # Should handle missing key gracefully
        valid_keys = [e.key for e in entries if e.key]
        assert "valid" in valid_keys

    def test_invalid_entry_type(self, parser_factory):
        """Test handling of invalid entry type."""
        parser = parser_factory()
        text = """
        @invalidtype{test,
            author = "Author",
            title = "Title"
        }
        """

        entries = parser.parse(text)
        if entries:
            # Should either skip or convert to misc
            assert entries[0].type.lower() in ["misc", "invalidtype"]

    def test_duplicate_keys(self, parser_factory):
        """Test handling of duplicate keys."""
        parser = parser_factory()
        text = """
        @article{duplicate,
            title = "First",
            year = 2023
        }

        @article{duplicate,
            title = "Second",
            year = 2024
        }
        """

        entries = parser.parse(text)
        # Should handle duplicates (keep all, keep last, or report error)
        assert len(entries) >= 1
        if len(entries) == 2:
            assert entries[0].key == entries[1].key

    def test_malformed_recovery(self, parser_factory, malformed_bibtex):
        """Test recovery from multiple errors."""
        parser = parser_factory()
        entries = parser.parse(malformed_bibtex)

        # Should recover good entries
        keys = [e.key for e in entries]
        assert "good1" in keys
        assert "good2" in keys

        # Should report errors
        assert len(parser.errors) > 0


class TestSpecialCharacters:
    """Test handling of special characters and escaping."""

    def test_latex_commands(self, parser_factory):
        """Test preservation of LaTeX commands."""
        parser = parser_factory()
        text = r"""
        @article{test,
            author = "M\"uller, J. and Schr\"{o}dinger, E.",
            title = "The $\alpha$-$\beta$ Algorithm",
            journal = "Computer Science \& Mathematics",
            year = 2024
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1

        entry = entries[0]
        # Should preserve LaTeX commands
        assert "\\" in entry.author or "ü" in entry.author
        assert "$" in entry.title or "α" in entry.title or "alpha" in entry.title

    def test_unicode_characters(self, parser_factory):
        """Test handling of Unicode characters."""
        parser = parser_factory()
        text = """
        @article{test,
            author = "José García and 王明",
            title = "Machine Learning: A Survey—2024",
            journal = "AI & Society",
            year = 2024
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1

        entry = entries[0]
        assert "José" in entry.author or "Jose" in entry.author
        assert "王明" in entry.author or len(entry.author) > 10

    def test_special_bibtex_chars(self, parser_factory):
        """Test handling of special BibTeX characters."""
        parser = parser_factory()
        text = """
        @article{test,
            author = "Smith, Jr., John and {Barnes & Noble}",
            title = "10% improvement using #hashtags",
            note = "Available at: http://example.com/~user",
            year = 2024
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1

        entry = entries[0]
        assert "&" in entry.author or "and" in entry.author
        assert "%" in entry.title or "10" in entry.title
        assert "~" in entry.note or "user" in entry.note


class TestLargeFiles:
    """Test handling of large BibTeX files."""

    def test_large_file_parsing(self, parser_factory):
        """Test parsing a large BibTeX file."""
        parser = parser_factory()

        # Generate large BibTeX content
        entries_text = []
        for i in range(1000):
            entries_text.append(f"""
            @article{{entry{i:04d},
                author = "Author {i}",
                title = "Title {i}: A comprehensive study of topic {i % 10}",
                journal = "Journal {i % 5}",
                year = {2000 + (i % 25)},
                volume = {i % 100},
                pages = "{i * 10}--{i * 10 + 9}"
            }}
            """)

        text = "\n".join(entries_text)
        entries = parser.parse(text)

        assert len(entries) == 1000
        assert entries[0].key == "entry0000"
        assert entries[999].key == "entry0999"

    def test_streaming_parse(self, parser_factory):
        """Test streaming/incremental parsing if supported."""
        parser = parser_factory()

        # Check if parser supports streaming
        if hasattr(parser, "parse_stream"):
            text = """
            @article{first, title="First", year=2024}
            @article{second, title="Second", year=2024}
            """

            stream = io.StringIO(text)
            entries = list(parser.parse_stream(stream))
            assert len(entries) == 2


class TestFileOperations:
    """Test file-based parsing operations."""

    def test_parse_file(self, parser_factory, sample_bibtex):
        """Test parsing from file."""
        parser = parser_factory()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            f.write(sample_bibtex)
            filepath = Path(f.name)

        try:
            entries = parser.parse_file(filepath)
            assert len(entries) >= 3  # Has at least 3 entries

            keys = [e.key for e in entries]
            assert "smith2024neural" in keys
            assert "knuth1984tex" in keys

        finally:
            filepath.unlink()

    def test_parse_nonexistent_file(self, parser_factory):
        """Test parsing non-existent file."""
        parser = parser_factory()

        with pytest.raises((FileNotFoundError, IOError, Exception)):
            parser.parse_file(Path("/nonexistent/file.bib"))

    def test_parse_empty_file(self, parser_factory):
        """Test parsing empty file."""
        parser = parser_factory()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
            filepath = Path(f.name)

        try:
            entries = parser.parse_file(filepath)
            assert len(entries) == 0

        finally:
            filepath.unlink()

    def test_parse_different_encodings(self, parser_factory):
        """Test parsing files with different encodings."""
        parser = parser_factory()

        # UTF-8 with BOM
        text_utf8_bom = '\ufeff@article{test, title="Test", year=2024}'

        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8-sig", suffix=".bib", delete=False
        ) as f:
            f.write(text_utf8_bom)
            filepath = Path(f.name)

        try:
            entries = parser.parse_file(filepath)
            assert len(entries) == 1
            assert entries[0].key == "test"

        finally:
            filepath.unlink()


class TestRoundTrip:
    """Test round-trip parsing and generation."""

    def test_simple_round_trip(self, parser_factory):
        """Test parsing and regenerating simple entries."""
        parser = parser_factory()
        original = """@article{test,
    author = "John Smith",
    title = "Test Article",
    journal = "Test Journal",
    year = 2024
}"""

        entries = parser.parse(original)
        assert len(entries) == 1

        # If entry has to_bibtex method
        if hasattr(entries[0], "to_bibtex"):
            regenerated = entries[0].to_bibtex()

            # Parse regenerated to check equivalence
            reparsed = parser.parse(regenerated)
            assert len(reparsed) == 1
            assert reparsed[0].key == entries[0].key
            assert reparsed[0].title == entries[0].title

    def test_format_preserving_round_trip(self, parser_factory):
        """Test format-preserving round trip if supported."""
        parser = parser_factory()

        original = """% Important comment
@article{test,
    author  = "John Smith",     % Author comment
    title   = "Test Article",    % Title comment
    journal = "Test Journal",
    year    = 2024
}"""

        if hasattr(parser, "parse_with_preservation"):
            entries, metadata = parser.parse_with_preservation(original)

            # Should be able to reconstruct with comments
            if hasattr(parser, "reconstruct"):
                reconstructed = parser.reconstruct(entries, metadata)

                # Should preserve comments
                assert "Important comment" in reconstructed
                assert "Author comment" in reconstructed or original == reconstructed


class TestPerformance:
    """Test parser performance characteristics."""

    def test_parse_speed(self, parser_factory, benchmark):
        """Benchmark parsing speed."""
        parser = parser_factory()

        # Generate moderate-sized content
        entries = []
        for i in range(100):
            entries.append(f"""
            @article{{key{i},
                author = "Author {i}",
                title = "Title {i}",
                journal = "Journal",
                year = {2000 + i % 25}
            }}
            """)
        text = "\n".join(entries)

        # Benchmark parsing
        result = benchmark(parser.parse, text)
        assert len(result) == 100

    def test_memory_usage(self, parser_factory):
        """Test memory usage for large files."""
        parser = parser_factory()

        # Generate very large content
        huge_entry = '@article{huge, title="' + "x" * 1000000 + '", year=2024}'

        # Should handle without excessive memory
        entries = parser.parse(huge_entry)
        assert len(entries) == 1
        assert len(entries[0].title) > 100000


class TestEdgeCases:
    """Test edge cases and unusual input."""

    def test_empty_input(self, parser_factory):
        """Test parsing empty input."""
        parser = parser_factory()

        entries = parser.parse("")
        assert len(entries) == 0

        entries = parser.parse("   \n  \t  \n  ")
        assert len(entries) == 0

    def test_only_comments(self, parser_factory):
        """Test input with only comments."""
        parser = parser_factory()
        text = """
        % Just comments
        % More comments
        @comment{Block comment}
        % Final comment
        """

        entries = parser.parse(text)
        assert len(entries) == 0

    def test_unusual_keys(self, parser_factory):
        """Test entries with unusual keys."""
        parser = parser_factory()
        text = """
        @article{key-with-dash, title="Test", year=2024}
        @article{key.with.dots, title="Test", year=2024}
        @article{key_with_underscore, title="Test", year=2024}
        @article{key:with:colons, title="Test", year=2024}
        @article{CamelCaseKey, title="Test", year=2024}
        @article{123numeric, title="Test", year=2024}
        """

        entries = parser.parse(text)
        assert len(entries) >= 5  # At least most should parse

        keys = [e.key for e in entries]
        assert "key-with-dash" in keys or "key_with_underscore" in keys

    def test_empty_fields(self, parser_factory):
        """Test entries with empty fields."""
        parser = parser_factory()
        text = """
        @article{test,
            author = "",
            title = {},
            journal = "  ",
            note = ,
            year = 2024
        }
        """

        entries = parser.parse(text)
        if entries:
            entry = entries[0]
            # Empty fields should be handled gracefully
            assert entry.author in ["", None, "  "]

    def test_very_long_fields(self, parser_factory):
        """Test entries with very long field values."""
        parser = parser_factory()

        long_title = "A" * 10000
        text = f"""
        @article{{test,
            title = "{long_title}",
            author = "Author",
            year = 2024
        }}
        """

        entries = parser.parse(text)
        assert len(entries) == 1
        assert len(entries[0].title) == 10000

    def test_nested_braces(self, parser_factory):
        """Test deeply nested braces."""
        parser = parser_factory()
        text = """
        @article{test,
            title = {Level {One {Two {Three {Four}}}}},
            author = {{{{Deeply}} Nested}},
            year = 2024
        }
        """

        entries = parser.parse(text)
        assert len(entries) == 1
        assert "Level" in entries[0].title
        assert "Four" in entries[0].title or "Three" in entries[0].title

    def test_special_entry_types(self, parser_factory):
        """Test less common entry types."""
        parser = parser_factory()
        text = """
        @phdthesis{phd, author="Student", title="Thesis", school="University", year=2024}
        @mastersthesis{ms, author="Student", title="Thesis", school="College", year=2024}
        @techreport{tr, author="Author", title="Report", institution="Lab", year=2024}
        @unpublished{up, author="Author", title="Draft", note="In preparation", year=2024}
        @manual{man, title="Manual", organization="Company", year=2024}
        @online{web, author="Author", title="Web Article", url="http://example.com", year=2024}
        """

        entries = parser.parse(text)
        assert len(entries) >= 5  # Most should be recognized

        types = [e.type.lower() for e in entries]
        assert "phdthesis" in types or "misc" in types
