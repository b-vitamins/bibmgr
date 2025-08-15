"""Tests for CLI output formatters.

This module comprehensively tests formatting functionality including:
- Table formatting for entries
- BibTeX output formatting
- JSON/YAML serialization
- Markdown table generation
- Citation formatting (APA, IEEE, etc.)
- Custom formatting templates
"""

import json
from io import StringIO

import yaml
from rich.console import Console
from rich.table import Table

from bibmgr.core.models import Entry, EntryType


class TestTableFormatter:
    """Test table formatting for entries."""

    def test_format_entries_table_basic(self, sample_entries, test_console):
        """Test basic table formatting of entries."""
        from bibmgr.cli.formatters.table import format_entries_table

        table = format_entries_table(sample_entries)

        # Capture output
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True)
        console.print(table)
        output = string_io.getvalue()

        assert "doe2024" in output
        assert "Quantum Computing" in output
        assert "Advances" in output
        assert "smith2023" in output
        assert "Machine Learning for" in output
        assert "Climate" in output

    def test_format_entries_table_with_fields(self, sample_entries):
        """Test table formatting with specific fields."""
        from bibmgr.cli.formatters.table import format_entries_table

        table = format_entries_table(
            sample_entries, fields=["key", "title", "year"], show_index=True
        )

        assert isinstance(table, Table)
        assert len(table.columns) == 4  # index + 3 fields

    def test_format_entries_table_empty(self):
        """Test table formatting with no entries."""
        from bibmgr.cli.formatters.table import format_entries_table

        table = format_entries_table([])

        string_io = StringIO()
        console = Console(file=string_io)
        console.print(table)
        output = string_io.getvalue()

        assert "No entries" in output or len(output.strip()) == 0

    def test_format_entry_details(self, sample_entries):
        """Test detailed entry formatting."""
        from bibmgr.cli.formatters.table import format_entry_details

        panel = format_entry_details(sample_entries[0])

        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True)
        console.print(panel)
        output = string_io.getvalue()

        assert "doe2024" in output
        assert "Type" in output
        assert "article" in output
        assert "Title" in output
        assert "Quantum Computing Advances" in output

    def test_format_search_results_table(self, sample_entries):
        """Test search results table formatting."""
        from bibmgr.cli.formatters.table import format_search_results
        from bibmgr.search.results import SearchMatch

        matches = [
            SearchMatch(
                entry_key="doe2024",
                score=0.95,
                highlights={"title": ["<mark>Quantum</mark> Computing"]},
                entry=sample_entries[0],
            ),
            SearchMatch(
                entry_key="smith2023",
                score=0.85,
                highlights={"title": ["Machine <mark>Learning</mark>"]},
                entry=sample_entries[1],
            ),
        ]

        table = format_search_results(matches)

        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True)
        console.print(table)
        output = string_io.getvalue()

        assert "95%" in output or "0.95" in output
        assert "85%" in output or "0.85" in output
        assert "doe2024" in output

    def test_format_collections_table(self, sample_collections):
        """Test collections table formatting."""
        from bibmgr.cli.formatters.table import format_collections_table

        table = format_collections_table(sample_collections)

        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True)
        console.print(table)
        output = string_io.getvalue()

        assert "PhD Research" in output
        assert "To Read" in output
        assert "Manual" in output
        assert "Smart" in output


class TestBibTeXFormatter:
    """Test BibTeX output formatting."""

    def test_format_entry_bibtex(self, sample_entries):
        """Test single entry BibTeX formatting."""
        from bibmgr.cli.formatters.bibtex import format_entry_bibtex

        bibtex = format_entry_bibtex(sample_entries[0])

        assert "@article{doe2024," in bibtex
        assert "title = {Quantum Computing Advances}" in bibtex
        assert "author = {Doe, John and Smith, Jane}" in bibtex
        assert "year = {2024}" in bibtex
        assert "}" in bibtex

    def test_format_entries_bibtex(self, sample_entries):
        """Test multiple entries BibTeX formatting."""
        from bibmgr.cli.formatters.bibtex import format_entries_bibtex

        bibtex = format_entries_bibtex(sample_entries)

        assert "@article{doe2024," in bibtex
        assert "@inproceedings{smith2023," in bibtex
        assert "@book{jones2022," in bibtex

    def test_format_bibtex_with_all_fields(self):
        """Test BibTeX formatting with all possible fields."""
        from bibmgr.cli.formatters.bibtex import format_entry_bibtex

        entry = Entry(
            key="complete2024",
            type=EntryType.ARTICLE,
            title="Complete Entry",
            author="Doe, John and Smith, Jane",
            journal="Test Journal",
            year=2024,
            volume="10",
            number="3",
            pages="100--110",
            doi="10.1000/test",
            url="https://example.com",
            abstract="This is the abstract",
            keywords=("test", "complete", "entry"),
            month="jan",
            note="Additional notes",
        )

        bibtex = format_entry_bibtex(entry)

        assert "volume = {10}" in bibtex
        assert "number = {3}" in bibtex
        assert "pages = {100--110}" in bibtex
        assert "doi = {10.1000/test}" in bibtex
        assert "keywords = {test, complete, entry}" in bibtex

    def test_format_bibtex_escaping(self):
        """Test BibTeX special character escaping."""
        from bibmgr.cli.formatters.bibtex import format_entry_bibtex

        entry = Entry(
            key="special2024",
            type=EntryType.ARTICLE,
            title="Title with {Braces} & Special Characters",
            author="O'Connor, Pat",
            journal="Test & Example Journal",
            year=2024,
        )

        bibtex = format_entry_bibtex(entry)

        # Check proper escaping
        assert "Title with {Braces} & Special Characters" in bibtex
        assert "O'Connor, Pat" in bibtex

    def test_parse_bibtex_entry(self):
        """Test parsing BibTeX back to entry data."""
        from bibmgr.cli.formatters.bibtex import parse_bibtex_entry

        bibtex = """
        @article{test2024,
            title = {Test Article},
            author = {Doe, John},
            year = {2024},
            journal = {Test Journal}
        }
        """

        data = parse_bibtex_entry(bibtex)

        assert data["key"] == "test2024"
        assert data["type"] == "article"
        assert data["title"] == "Test Article"
        assert data["author"] == "Doe, John"
        assert data["year"] == "2024"


class TestJSONFormatter:
    """Test JSON output formatting."""

    def test_format_entry_json(self, sample_entries):
        """Test single entry JSON formatting."""
        from bibmgr.cli.formatters.json import format_entry_json

        json_str = format_entry_json(sample_entries[0])
        data = json.loads(json_str)

        assert data["key"] == "doe2024"
        assert data["type"] == "article"
        assert data["title"] == "Quantum Computing Advances"
        assert data["year"] == 2024

    def test_format_entries_json(self, sample_entries):
        """Test multiple entries JSON formatting."""
        from bibmgr.cli.formatters.json import format_entries_json

        json_str = format_entries_json(sample_entries)
        data = json.loads(json_str)

        assert "entries" in data
        assert len(data["entries"]) == 3
        assert data["total"] == 3

    def test_format_json_with_metadata(self, sample_entries, sample_metadata):
        """Test JSON formatting with metadata included."""
        from bibmgr.cli.formatters.json import format_entry_json

        json_str = format_entry_json(
            sample_entries[0], include_metadata=True, metadata=sample_metadata
        )
        data = json.loads(json_str)

        assert "metadata" in data
        assert data["metadata"]["rating"] == 5
        assert "quantum" in data["metadata"]["tags"]

    def test_format_search_results_json(self):
        """Test search results JSON formatting."""
        from bibmgr.cli.formatters.json import format_search_results_json
        from bibmgr.search.results import (
            SearchMatch,
            SearchResultCollection,
            SearchStatistics,
        )

        results = SearchResultCollection(
            query="test",
            matches=[
                SearchMatch(entry_key="test1", score=0.9),
                SearchMatch(entry_key="test2", score=0.8),
            ],
            total=2,
            facets=[],
            suggestions=[],
            statistics=SearchStatistics(total_results=2, search_time_ms=10),
        )

        json_str = format_search_results_json(results)
        data = json.loads(json_str)

        assert data["query"] == "test"
        assert data["total"] == 2
        assert len(data["matches"]) == 2
        assert data["statistics"]["took_ms"] == 10


class TestMarkdownFormatter:
    """Test Markdown output formatting."""

    def test_format_entries_markdown_table(self, sample_entries):
        """Test Markdown table formatting."""
        from bibmgr.cli.formatters.markdown import format_entries_markdown

        markdown = format_entries_markdown(sample_entries)

        assert "| Key | Title | Authors | Year |" in markdown
        assert "|-----|-------|---------|------|" in markdown
        assert "| doe2024 | Quantum Computing Advances |" in markdown
        assert "| smith2023 | Machine Learning for Climate |" in markdown

    def test_format_entry_markdown(self, sample_entries):
        """Test single entry Markdown formatting."""
        from bibmgr.cli.formatters.markdown import format_entry_markdown

        markdown = format_entry_markdown(sample_entries[0])

        assert "# doe2024" in markdown
        assert "**Title:** Quantum Computing Advances" in markdown
        assert "**Authors:** Doe, John and Smith, Jane" in markdown
        assert "**Year:** 2024" in markdown

    def test_format_collections_markdown(self, sample_collections):
        """Test collections Markdown formatting."""
        from bibmgr.cli.formatters.markdown import format_collections_markdown

        markdown = format_collections_markdown(sample_collections)

        assert "# Collections" in markdown
        assert "## PhD Research" in markdown
        assert "Core papers for dissertation" in markdown
        assert "**Type:** Manual" in markdown
        assert "**Entries:** 2" in markdown


class TestCitationFormatter:
    """Test citation formatting in various styles."""

    def test_format_citation_apa(self, sample_entries):
        """Test APA citation formatting."""
        from bibmgr.cli.formatters.citation import format_citation

        citation = format_citation(sample_entries[0], style="apa")

        assert "Doe, J., & Smith, J. (2024)" in citation
        assert "Quantum Computing Advances" in citation
        assert "Nature Quantum" in citation

    def test_format_citation_ieee(self, sample_entries):
        """Test IEEE citation formatting."""
        from bibmgr.cli.formatters.citation import format_citation

        citation = format_citation(sample_entries[0], style="ieee")

        assert "[1]" in citation or citation.startswith("J. Doe")
        assert '"Quantum Computing Advances,"' in citation
        assert "2024" in citation

    def test_format_citation_mla(self, sample_entries):
        """Test MLA citation formatting."""
        from bibmgr.cli.formatters.citation import format_citation

        citation = format_citation(sample_entries[0], style="mla")

        assert "Doe, John, and Jane Smith" in citation
        assert '"Quantum Computing Advances."' in citation
        assert "2024" in citation

    def test_format_citation_chicago(self, sample_entries):
        """Test Chicago citation formatting."""
        from bibmgr.cli.formatters.citation import format_citation

        citation = format_citation(sample_entries[0], style="chicago")

        assert "Doe, John, and Jane Smith" in citation
        assert '"Quantum Computing Advances."' in citation
        assert "Nature Quantum" in citation

    def test_format_citation_custom_template(self, sample_entries):
        """Test custom citation template formatting."""
        from bibmgr.cli.formatters.citation import format_citation

        template = "{author} ({year}). {title}. {journal}."
        citation = format_citation(sample_entries[0], template=template)

        assert (
            citation
            == "Doe, John and Smith, Jane (2024). Quantum Computing Advances. Nature Quantum."
        )

    def test_format_citations_list(self, sample_entries):
        """Test formatting multiple citations."""
        from bibmgr.cli.formatters.citation import format_citations

        citations = format_citations(sample_entries, style="apa")

        assert len(citations) == 3
        assert all(
            "(" in c and ")" in c for c in citations
        )  # APA uses parentheses for year


class TestYAMLFormatter:
    """Test YAML output formatting."""

    def test_format_entry_yaml(self, sample_entries):
        """Test single entry YAML formatting."""
        from bibmgr.cli.formatters.yaml import format_entry_yaml

        yaml_str = format_entry_yaml(sample_entries[0])
        data = yaml.safe_load(yaml_str)

        assert data["key"] == "doe2024"
        assert data["type"] == "article"
        assert data["title"] == "Quantum Computing Advances"

    def test_format_entries_yaml(self, sample_entries):
        """Test multiple entries YAML formatting."""
        from bibmgr.cli.formatters.yaml import format_entries_yaml

        yaml_str = format_entries_yaml(sample_entries)
        data = yaml.safe_load(yaml_str)

        assert "entries" in data
        assert len(data["entries"]) == 3


class TestCSVFormatter:
    """Test CSV output formatting."""

    def test_format_entries_csv(self, sample_entries):
        """Test CSV formatting of entries."""
        from bibmgr.cli.formatters.csv import format_entries_csv

        csv_output = format_entries_csv(sample_entries)

        lines = csv_output.strip().split("\n")
        assert len(lines) == 4  # header + 3 entries

        # Check header
        assert "key,type,title,author,year" in lines[0]

        # Check data
        assert "doe2024,article,Quantum Computing Advances" in csv_output
        assert "smith2023,inproceedings,Machine Learning for Climate" in csv_output

    def test_format_csv_with_custom_fields(self, sample_entries):
        """Test CSV formatting with specific fields."""
        from bibmgr.cli.formatters.csv import format_entries_csv

        csv_output = format_entries_csv(sample_entries, fields=["key", "title", "year"])

        lines = csv_output.strip().split("\n")
        header = lines[0]

        assert "key,title,year" == header
        assert "author" not in header


class TestTemplateFormatter:
    """Test custom template formatting."""

    def test_format_with_template(self, sample_entries):
        """Test formatting with custom template."""
        from bibmgr.cli.formatters.template import format_with_template

        template = "Entry: {key}\nTitle: {title}\nYear: {year}\n---"
        output = format_with_template(sample_entries[0], template)

        assert "Entry: doe2024" in output
        assert "Title: Quantum Computing Advances" in output
        assert "Year: 2024" in output

    def test_format_multiple_with_template(self, sample_entries):
        """Test formatting multiple entries with template."""
        from bibmgr.cli.formatters.template import format_entries_with_template

        template = "{key}: {title} ({year})"
        output = format_entries_with_template(sample_entries, template, separator="\n")

        lines = output.strip().split("\n")
        assert len(lines) == 3
        assert "doe2024: Quantum Computing Advances (2024)" in lines[0]
