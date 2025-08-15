"""Output formatters for the CLI.

This module provides various formatters for displaying bibliography data
in different formats including tables, BibTeX, JSON, Markdown, and more.
"""

from .bibtex import (
    format_entries_bibtex,
    format_entry_bibtex,
    parse_bibtex_entry,
)
from .citation import (
    format_citation,
    format_citations,
)
from .csv import (
    format_entries_csv,
)
from .json import (
    format_entries_json,
    format_entry_json,
    format_search_results_json,
)
from .markdown import (
    format_collections_markdown,
    format_entries_markdown,
    format_entry_markdown,
)
from .table import (
    format_collections_table,
    format_entries_table,
    format_entry_details,
    format_entry_table,
    format_search_results,
)
from .template import (
    format_entries_with_template,
    format_with_template,
)
from .yaml import (
    format_entries_yaml,
    format_entry_yaml,
)

__all__ = [
    # Table formatters
    "format_entries_table",
    "format_entry_details",
    "format_search_results",
    "format_collections_table",
    "format_entry_table",
    # BibTeX formatters
    "format_entry_bibtex",
    "format_entries_bibtex",
    "parse_bibtex_entry",
    # JSON formatters
    "format_entry_json",
    "format_entries_json",
    "format_search_results_json",
    # Markdown formatters
    "format_entry_markdown",
    "format_entries_markdown",
    "format_collections_markdown",
    # Citation formatters
    "format_citation",
    "format_citations",
    # CSV formatters
    "format_entries_csv",
    # Template formatters
    "format_with_template",
    "format_entries_with_template",
    # YAML formatters
    "format_entry_yaml",
    "format_entries_yaml",
]
