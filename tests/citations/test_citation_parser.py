"""Comprehensive tests for citation parsing and processing."""

import re
from unittest.mock import Mock

import pytest

from bibmgr.citations.parser import (
    AsyncCitationProcessor,
    BibLaTeXParser,
    Citation,
    CitationCommand,
    CitationExtractor,
    CitationParser,
    CitationProcessor,
    LaTeXParser,
    MarkdownParser,
    ParserRegistry,
)


class TestCitation:
    """Test Citation data structure."""

    def test_citation_creation(self):
        """Test creating citation objects."""
        cite = Citation(
            command=CitationCommand.CITE,
            keys=["smith2024", "doe2023"],
            prefix="see",
            suffix="p. 42",
            start_pos=10,
            end_pos=35,
        )

        assert cite.command == CitationCommand.CITE
        assert cite.keys == ["smith2024", "doe2023"]
        assert cite.prefix == "see"
        assert cite.suffix == "p. 42"
        assert cite.start_pos == 10
        assert cite.end_pos == 35

    def test_citation_properties(self):
        """Test citation property methods."""
        # Parenthetical citation
        cite1 = Citation(CitationCommand.CITEP, ["key1"])
        assert cite1.is_parenthetical
        assert not cite1.is_textual
        assert not cite1.is_author_only

        # Textual citation
        cite2 = Citation(CitationCommand.CITET, ["key2"])
        assert not cite2.is_parenthetical
        assert cite2.is_textual
        assert not cite2.is_author_only

        # Author-only citation
        cite3 = Citation(CitationCommand.CITEAUTHOR, ["key3"])
        assert not cite3.is_parenthetical
        assert not cite3.is_textual
        assert cite3.is_author_only

    def test_citation_equality(self):
        """Test citation equality comparison."""
        cite1 = Citation(CitationCommand.CITE, ["key1"], start_pos=0, end_pos=10)
        cite2 = Citation(CitationCommand.CITE, ["key1"], start_pos=0, end_pos=10)
        cite3 = Citation(CitationCommand.CITE, ["key2"], start_pos=0, end_pos=10)

        assert cite1 == cite2
        assert cite1 != cite3

    def test_citation_string_representation(self):
        """Test citation string representation."""
        cite = Citation(
            CitationCommand.CITE,
            ["smith2024"],
            prefix="see",
            suffix="p. 42",
        )

        str_repr = str(cite)
        assert "cite" in str_repr.lower()
        assert "smith2024" in str_repr

        # LaTeX reconstruction
        latex = cite.to_latex()
        assert r"\cite" in latex
        assert "smith2024" in latex
        assert "see" in latex
        assert "p. 42" in latex


class TestLaTeXParser:
    """Test LaTeX citation parsing."""

    def test_parse_simple_cite(self):
        """Test parsing simple \\cite commands."""
        parser = LaTeXParser()

        text = r"According to \cite{smith2024}, the results are significant."
        citations = parser.parse(text)

        assert len(citations) == 1
        cite = citations[0]
        assert cite.command == CitationCommand.CITE
        assert cite.keys == ["smith2024"]
        assert cite.prefix is None
        assert cite.suffix is None

    def test_parse_multiple_keys(self):
        """Test parsing citations with multiple keys."""
        parser = LaTeXParser()

        text = r"Previous work \cite{smith2024, doe2023, johnson2024} shows..."
        citations = parser.parse(text)

        assert len(citations) == 1
        assert citations[0].keys == ["smith2024", "doe2023", "johnson2024"]

    def test_parse_with_options(self):
        """Test parsing citations with optional arguments."""
        parser = LaTeXParser()

        # Suffix only
        text1 = r"See \cite[p. 42]{smith2024} for details."
        citations = parser.parse(text1)
        assert citations[0].suffix == "p. 42"
        assert citations[0].prefix is None

        # Prefix and suffix
        text2 = r"Compare \cite[see][pp. 1-10]{doe2023} with..."
        citations = parser.parse(text2)
        assert citations[0].prefix == "see"
        assert citations[0].suffix == "pp. 1-10"

    def test_parse_natbib_commands(self):
        """Test parsing natbib citation commands."""
        parser = LaTeXParser()

        commands = {
            r"\citep{key}": CitationCommand.CITEP,
            r"\citet{key}": CitationCommand.CITET,
            r"\citealt{key}": CitationCommand.CITEALT,
            r"\citealp{key}": CitationCommand.CITEALP,
            r"\citeauthor{key}": CitationCommand.CITEAUTHOR,
            r"\citeyear{key}": CitationCommand.CITEYEAR,
            r"\citeyearpar{key}": CitationCommand.CITEYEARPAR,
        }

        for latex, expected_cmd in commands.items():
            citations = parser.parse(latex)
            assert len(citations) == 1
            assert citations[0].command == expected_cmd

    def test_parse_starred_variants(self):
        """Test parsing starred citation variants."""
        parser = LaTeXParser()

        text = r"Use \cite*{smith2024} and \citep*{doe2023}."
        citations = parser.parse(text)

        assert len(citations) == 2
        assert citations[0].starred is True
        assert citations[1].starred is True

    def test_parse_positions(self):
        """Test tracking citation positions in text."""
        parser = LaTeXParser()

        text = r"First \cite{smith2024} then \cite{doe2023} finally."
        citations = parser.parse(text)

        assert len(citations) == 2
        assert citations[0].start_pos < citations[0].end_pos
        assert citations[1].start_pos > citations[0].end_pos

        # Extract original text
        assert (
            text[citations[0].start_pos : citations[0].end_pos] == r"\cite{smith2024}"
        )

    def test_parse_escaped_citations(self):
        """Test handling escaped citations."""
        parser = LaTeXParser()

        # Escaped backslash - should not parse
        text = r"This is not a citation: \\cite{smith2024}"
        citations = parser.parse(text)
        assert len(citations) == 0

    def test_parse_nested_braces(self):
        """Test handling nested braces in citations."""
        parser = LaTeXParser()

        text = r"\cite[see \emph{also}][p. 42]{smith2024}"
        citations = parser.parse(text)

        assert len(citations) == 1
        assert citations[0].prefix == r"see \emph{also}"
        assert citations[0].suffix == "p. 42"

    def test_parse_whitespace_handling(self):
        """Test whitespace handling in citations."""
        parser = LaTeXParser()

        text = r"\cite{ smith2024 , doe2023 , johnson2024 }"
        citations = parser.parse(text)

        assert len(citations) == 1
        # Keys should be trimmed
        assert citations[0].keys == ["smith2024", "doe2023", "johnson2024"]


class TestBibLaTeXParser:
    """Test BibLaTeX citation parsing."""

    def test_parse_biblatex_commands(self):
        """Test parsing BibLaTeX-specific commands."""
        parser = BibLaTeXParser()

        commands = {
            r"\parencite{key}": CitationCommand.PARENCITE,
            r"\textcite{key}": CitationCommand.TEXTCITE,
            r"\autocite{key}": CitationCommand.AUTOCITE,
            r"\footcite{key}": CitationCommand.FOOTCITE,
            r"\smartcite{key}": CitationCommand.SMARTCITE,
            r"\supercite{key}": CitationCommand.SUPERCITE,
            r"\cites{key}": CitationCommand.CITES,
            r"\fullcite{key}": CitationCommand.FULLCITE,
        }

        for latex, expected_cmd in commands.items():
            citations = parser.parse(latex)
            assert len(citations) == 1
            assert citations[0].command == expected_cmd

    def test_parse_multicite_commands(self):
        """Test parsing multicite commands."""
        parser = BibLaTeXParser()

        # Multiple citation groups
        text = r"\cites{smith2024}{doe2023}{johnson2024}"
        citations = parser.parse(text)

        assert len(citations) == 1
        assert citations[0].command == CitationCommand.CITES
        assert len(citations[0].keys) == 3

    def test_parse_with_prenote_postnote(self):
        """Test parsing with prenote and postnote."""
        parser = BibLaTeXParser()

        text = r"\textcite[see][42]{smith2024}"
        citations = parser.parse(text)

        assert citations[0].prefix == "see"
        assert citations[0].suffix == "42"

    def test_parse_complex_arguments(self):
        """Test parsing complex BibLaTeX arguments."""
        parser = BibLaTeXParser()

        # Named arguments
        text = r"\cite[prenote={see also}][postnote={pp. 1-10}]{smith2024}"
        citations = parser.parse(text)

        assert citations[0].prefix == "see also"
        assert citations[0].suffix == "pp. 1-10"

    def test_parse_cite_field_commands(self):
        """Test field-specific cite commands."""
        parser = BibLaTeXParser()

        text = r"\citetitle{smith2024} by \citeauthor{smith2024} (\citeyear{smith2024})"
        citations = parser.parse(text)

        assert len(citations) == 3
        assert citations[0].command == CitationCommand.CITETITLE
        assert citations[1].command == CitationCommand.CITEAUTHOR
        assert citations[2].command == CitationCommand.CITEYEAR


class TestMarkdownParser:
    """Test Markdown citation parsing."""

    def test_parse_simple_citation(self):
        """Test parsing simple @ citations."""
        parser = MarkdownParser()

        text = "According to @smith2024, the results are significant."
        citations = parser.parse(text)

        assert len(citations) == 1
        assert citations[0].keys == ["smith2024"]
        assert citations[0].command == CitationCommand.MARKDOWN_CITE

    def test_parse_bracketed_citation(self):
        """Test parsing bracketed citations."""
        parser = MarkdownParser()

        text = "The results [@smith2024] are significant."
        citations = parser.parse(text)

        assert len(citations) == 1
        assert citations[0].keys == ["smith2024"]
        assert citations[0].command == CitationCommand.MARKDOWN_PARENS

    def test_parse_multiple_citations(self):
        """Test parsing multiple citations."""
        parser = MarkdownParser()

        text = "Previous work [@smith2024; @doe2023; @johnson2024] shows..."
        citations = parser.parse(text)

        assert len(citations) == 1
        assert citations[0].keys == ["smith2024", "doe2023", "johnson2024"]

    def test_parse_with_locator(self):
        """Test parsing citations with locators."""
        parser = MarkdownParser()

        text = "See @smith2024 [p. 42] for details."
        citations = parser.parse(text)

        assert len(citations) == 1
        assert citations[0].keys == ["smith2024"]
        assert citations[0].suffix == "p. 42"

    def test_parse_suppressed_author(self):
        """Test parsing author-suppressed citations."""
        parser = MarkdownParser()

        text = "Smith [-@smith2024] found that..."
        citations = parser.parse(text)

        assert len(citations) == 1
        assert citations[0].suppress_author is True

    def test_parse_complex_citations(self):
        """Test parsing complex citation groups."""
        parser = MarkdownParser()

        text = "Compare [@smith2024, p. 30; @doe2023, ch. 2]"
        citations = parser.parse(text)

        assert len(citations) == 1
        assert len(citations[0].keys) == 2
        # Individual locators should be captured
        assert citations[0].locators == ["p. 30", "ch. 2"]

    def test_parse_escaped_citations(self):
        """Test handling escaped @ symbols."""
        parser = MarkdownParser()

        text = r"Email me \@smith2024 (not a citation)"
        citations = parser.parse(text)

        assert len(citations) == 0

    def test_parse_inline_note(self):
        """Test parsing inline notes with citations."""
        parser = MarkdownParser()

        text = "This is important^[@smith2024 provides evidence]."
        citations = parser.parse(text)

        assert len(citations) == 1
        assert citations[0].in_note is True


class TestCitationParser:
    """Test generic citation parser."""

    def test_auto_detect_format(self):
        """Test automatic format detection."""
        parser = CitationParser()

        # LaTeX format
        latex_text = r"See \cite{smith2024} for details."
        citations = parser.parse(latex_text)
        assert len(citations) == 1
        assert citations[0].command.name.startswith("CITE")

        # Markdown format
        md_text = "According to @smith2024, this is true."
        citations = parser.parse(md_text)
        assert len(citations) == 1
        assert citations[0].command.name.startswith("MARKDOWN")

    def test_explicit_format(self):
        """Test explicit format specification."""
        parser = CitationParser()

        # Force LaTeX parsing on ambiguous text
        text = "This could be either format"

        latex_citations = parser.parse(text, format="latex")
        md_citations = parser.parse(text, format="markdown")

        # Should return empty for non-matching format
        assert len(latex_citations) == 0
        assert len(md_citations) == 0

    def test_mixed_formats(self):
        """Test handling mixed format input."""
        parser = CitationParser()

        # Text with both LaTeX and Markdown citations
        text = r"LaTeX \cite{smith2024} and Markdown @doe2023 together."

        # Auto-detect should find both
        citations = parser.parse(text)
        assert len(citations) == 2

    def test_custom_parser_registration(self):
        """Test registering custom parsers."""
        parser = CitationParser()

        # Create custom parser
        class CustomParser:
            def parse(self, text):
                # Find [[key]] style citations
                pattern = r"\[\[(\w+)\]\]"
                matches = re.finditer(pattern, text)
                return [
                    Citation(
                        CitationCommand.CUSTOM,
                        [match.group(1)],
                        start_pos=match.start(),
                        end_pos=match.end(),
                    )
                    for match in matches
                ]

        parser.register_parser("custom", CustomParser())

        text = "Custom citation [[smith2024]] here."
        citations = parser.parse(text, format="custom")

        assert len(citations) == 1
        assert citations[0].keys == ["smith2024"]


class TestCitationProcessor:
    """Test citation processing."""

    def test_process_citations(self, entry_provider):
        """Test processing citations with formatting."""
        processor = CitationProcessor(entry_provider)

        text = r"According to \cite{smith2024}, this is true."
        result = processor.process(text)

        # Should replace citation with formatted text
        assert r"\cite{smith2024}" not in result
        assert "Smith" in result
        assert "2024" in result

    def test_process_missing_entries(self, entry_provider):
        """Test processing citations with missing entries."""
        processor = CitationProcessor(entry_provider)

        text = r"Unknown work \cite{nonexistent} is cited."
        result = processor.process(text)

        # Should handle missing entry gracefully
        assert "[nonexistent]" in result or "?" in result

    def test_process_with_style(self, entry_provider):
        """Test processing with specific citation style."""
        from bibmgr.citations.styles import APAStyle, MLAStyle

        processor_apa = CitationProcessor(entry_provider, style=APAStyle())
        processor_mla = CitationProcessor(entry_provider, style=MLAStyle())

        text = r"See \cite{smith2024} for details."

        result_apa = processor_apa.process(text)
        result_mla = processor_mla.process(text)

        # Different styles should produce different output
        assert result_apa != result_mla

    def test_process_complex_citations(self, entry_provider):
        """Test processing complex citations."""
        processor = CitationProcessor(entry_provider)

        text = r"Compare \cite[see][pp. 1-10]{smith2024} with \citet{doe2023}."
        result = processor.process(text)

        # Should handle both citations
        assert r"\cite" not in result
        assert r"\citet" not in result
        assert "Smith" in result
        assert "Doe" in result

    def test_extract_citation_keys(self, entry_provider):
        """Test extracting citation keys from text."""
        processor = CitationProcessor(entry_provider)

        text = r"""
        First \cite{smith2024}.
        Second \cite{doe2023, johnson2023}.
        Third \cite{smith2024}.  # Duplicate
        """

        keys = processor.extract_keys(text)

        assert keys == {"smith2024", "doe2023", "johnson2023"}

    def test_get_citation_context(self, entry_provider):
        """Test getting citation context."""
        processor = CitationProcessor(entry_provider)

        text = r"""Line 1
Line 2 with \cite{smith2024} citation.
Line 3
Line 4"""

        contexts = processor.get_contexts(text, lines_before=1, lines_after=1)

        assert len(contexts) == 1
        context = contexts[0]
        assert "Line 1" in context.before
        assert "Line 3" in context.after
        assert context.line_number == 2


class TestCitationExtractor:
    """Test citation extraction and analysis."""

    def test_extract_all_citations(self):
        """Test extracting all citations from document."""
        extractor = CitationExtractor()

        text = r"""
        \cite{smith2024}
        @doe2023
        \citep{johnson2024}
        [@lee2024]
        """

        citations = extractor.extract_all(text)
        assert len(citations) == 4

    def test_group_citations_by_type(self):
        """Test grouping citations by type."""
        extractor = CitationExtractor()

        text = r"""
        \cite{smith2024}
        \citet{doe2023}
        \citeauthor{johnson2024}
        \citeyear{lee2024}
        """

        groups = extractor.group_by_type(text)

        assert CitationCommand.CITE in groups
        assert CitationCommand.CITET in groups
        assert CitationCommand.CITEAUTHOR in groups
        assert CitationCommand.CITEYEAR in groups

    def test_find_undefined_citations(self, entry_provider):
        """Test finding undefined citations."""
        extractor = CitationExtractor()

        text = r"""
        \cite{smith2024}  # Exists
        \cite{nonexistent}  # Does not exist
        \cite{doe2023}  # Exists
        """

        undefined = extractor.find_undefined(text, entry_provider)

        assert "nonexistent" in undefined
        assert "smith2024" not in undefined

    def test_find_duplicate_citations(self):
        """Test finding duplicate citations."""
        extractor = CitationExtractor()

        text = r"""
        \cite{smith2024}
        Some text.
        \cite{smith2024}  # Duplicate
        \cite{doe2023}
        """

        duplicates = extractor.find_duplicates(text)

        assert "smith2024" in duplicates
        assert duplicates["smith2024"] == 2
        assert "doe2023" not in duplicates or duplicates["doe2023"] == 1

    def test_citation_statistics(self):
        """Test gathering citation statistics."""
        extractor = CitationExtractor()

        text = r"""
        \cite{smith2024}
        \citet{doe2023}
        \cite{smith2024}  # Duplicate
        @johnson2024
        """

        stats = extractor.get_statistics(text)

        assert stats["total_citations"] == 4
        assert stats["unique_keys"] == 3
        assert stats["citation_types"]["CITE"] == 2
        assert stats["citation_types"]["CITET"] == 1


class TestAsyncCitationProcessor:
    """Test asynchronous citation processing."""

    @pytest.mark.asyncio
    async def test_async_process(self, entry_provider):
        """Test async citation processing."""
        processor = AsyncCitationProcessor(entry_provider)

        text = r"See \cite{smith2024} for details."
        result = await processor.process_async(text)

        assert r"\cite{smith2024}" not in result
        assert "Smith" in result

    @pytest.mark.asyncio
    async def test_batch_process(self, entry_provider):
        """Test batch processing multiple documents."""
        processor = AsyncCitationProcessor(entry_provider)

        documents = [
            r"First doc \cite{smith2024}.",
            r"Second doc \cite{doe2023}.",
            r"Third doc \cite{johnson2023}.",
        ]

        results = await processor.process_batch(documents)

        assert len(results) == 3
        assert all(r"\cite" not in r for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_processing(self, entry_provider, performance_entries):
        """Test concurrent processing performance."""
        import time

        # Add performance entries to provider
        entry_provider.entries.update(performance_entries)

        processor = AsyncCitationProcessor(entry_provider)

        # Create documents with many citations
        documents = [f"Document {i} with \\cite{{entry{i:04d}}}." for i in range(100)]

        start = time.time()
        results = await processor.process_batch(documents)
        duration = time.time() - start

        assert len(results) == 100
        # Should be reasonably fast
        assert duration < 5.0


class TestParserRegistry:
    """Test parser registry management."""

    def test_default_parsers(self):
        """Test default parser registration."""
        registry = ParserRegistry()

        assert "latex" in registry
        assert "biblatex" in registry
        assert "markdown" in registry

    def test_register_parser(self):
        """Test registering custom parser."""
        registry = ParserRegistry()

        custom_parser = Mock()
        registry.register("custom", custom_parser)

        assert "custom" in registry
        assert registry.get("custom") == custom_parser

    def test_parser_aliases(self):
        """Test parser aliases."""
        registry = ParserRegistry()

        # Common aliases
        assert registry.get("tex") == registry.get("latex")
        assert registry.get("md") == registry.get("markdown")

    def test_list_parsers(self):
        """Test listing available parsers."""
        registry = ParserRegistry()

        parsers = registry.list_parsers()
        assert "latex" in parsers
        assert "markdown" in parsers


class TestEdgeCases:
    """Test edge cases in citation parsing."""

    def test_empty_citation_keys(self):
        """Test handling empty citation keys."""
        parser = LaTeXParser()

        text = r"\cite{}"
        citations = parser.parse(text)

        # Should either skip or handle gracefully
        assert len(citations) == 0 or citations[0].keys == []

    def test_malformed_citations(self):
        """Test handling malformed citations."""
        parser = LaTeXParser()

        # Missing closing brace
        text1 = r"\cite{smith2024"
        citations1 = parser.parse(text1)
        assert len(citations1) == 0

        # Missing opening brace
        text2 = r"\cite smith2024}"
        citations2 = parser.parse(text2)
        assert len(citations2) == 0

    def test_very_long_key_lists(self):
        """Test handling very long key lists."""
        parser = LaTeXParser()

        # 100 keys
        keys = [f"key{i:03d}" for i in range(100)]
        text = r"\cite{" + ", ".join(keys) + "}"

        citations = parser.parse(text)
        assert len(citations) == 1
        assert len(citations[0].keys) == 100

    def test_unicode_in_citations(self):
        """Test Unicode in citation keys and text."""
        parser = LaTeXParser()

        text = r"\cite{müller2024, 李2023}"
        citations = parser.parse(text)

        assert len(citations) == 1
        assert "müller2024" in citations[0].keys
        assert "李2023" in citations[0].keys

    def test_citations_in_comments(self):
        """Test handling citations in comments."""
        parser = LaTeXParser()

        text = r"""
        Real citation \cite{smith2024}.
        % Commented citation \cite{doe2023}
        Another real \cite{johnson2024}.
        """

        citations = parser.parse(text)

        # Should not parse commented citations
        keys = [key for cite in citations for key in cite.keys]
        assert "smith2024" in keys
        assert "johnson2024" in keys
        assert "doe2023" not in keys

    def test_recursive_citations(self):
        """Test handling recursive/nested citations."""
        parser = LaTeXParser()

        # Citation in citation prefix (edge case)
        text = r"\cite[as noted in \cite{doe2023}]{smith2024}"
        citations = parser.parse(text)

        # Should handle the nesting appropriately
        assert len(citations) >= 1
