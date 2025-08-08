"""Shared fixtures for citation tests."""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from bibmgr.core.models import Entry, EntryType


@pytest.fixture
def sample_entries():
    """Provide diverse sample entries for testing."""
    return {
        "simple_article": Entry(
            key="smith2024",
            type=EntryType.ARTICLE,
            author="Smith, John",
            title="Quantum Computing Advances",
            journal="Nature",
            volume="123",
            pages="45--67",
            year=2024,
            doi="10.1038/nature.2024.123",
        ),
        "multiple_authors": Entry(
            key="doe2023",
            type=EntryType.ARTICLE,
            author="Doe, Jane and Johnson, Bob and Williams, Alice and Brown, Charlie and Davis, Eve and Miller, Frank",
            title="Collaborative Research in Machine Learning",
            journal="Science",
            volume="456",
            number="7",
            pages="234--256",
            year=2023,
        ),
        "book_entry": Entry(
            key="knuth1997",
            type=EntryType.BOOK,
            author="Knuth, Donald E.",
            title="The Art of Computer Programming",
            publisher="Addison-Wesley",
            address="Boston",
            edition="3",
            year=1997,
            isbn="978-0-201-89683-1",
        ),
        "conference_paper": Entry(
            key="lee2024",
            type=EntryType.INPROCEEDINGS,
            author="Lee, Kim and Park, Jin",
            title="Neural Architecture Search: A Survey",
            booktitle="Proceedings of the International Conference on Machine Learning",
            pages="123--134",
            year=2024,
            address="Vienna, Austria",
            month="7",
        ),
        "thesis_entry": Entry(
            key="johnson2023",
            type=EntryType.PHDTHESIS,
            author="Johnson, Sarah",
            title="Advanced Techniques in Natural Language Processing",
            school="MIT",
            year=2023,
            address="Cambridge, MA",
        ),
        "online_resource": Entry(
            key="mozilla2024",
            type=EntryType.MISC,
            author="Mozilla Foundation",
            title="Web Documentation",
            year=2024,
            url="https://developer.mozilla.org",
            note="Accessed: 2024-01-15",
        ),
        "no_author": Entry(
            key="anon2024",
            type=EntryType.MISC,
            title="Anonymous Report on Climate Change",
            year=2024,
            publisher="Unknown Publisher",
        ),
        "no_year": Entry(
            key="timeless",
            type=EntryType.MISC,
            author="Eternal, Author",
            title="Timeless Wisdom",
            note="Date unknown",
        ),
        "unicode_entry": Entry(
            key="müller2024",
            type=EntryType.ARTICLE,
            author="Müller, Jürgen and Françoise, René and 北京, 李",
            title="Cross-Cultural Collaboration in Science: Études et Recherches",
            journal="International Journal of Science",
            year=2024,
            volume="89",
            pages="12--34",
        ),
        "latex_commands": Entry(
            key="math2024",
            type=EntryType.ARTICLE,
            author="Einstein, Albert",
            title="The \\textbf{Theory} of \\emph{Everything}: $E=mc^2$ and Beyond",
            journal="Physical Review",
            year=2024,
            abstract="This paper discusses \\LaTeX{} formatting and math: $\\alpha + \\beta$",
        ),
    }


@pytest.fixture
def entry_provider(sample_entries):
    """Provide a mock entry provider for testing."""

    class MockEntryProvider:
        def __init__(self, entries):
            self.entries = entries
            self.call_count = 0
            # Create a lookup map by Entry.key for citation lookups
            self._by_key = {entry.key: entry for entry in entries.values()}

        def get_entry(self, key: str) -> Entry | None:
            self.call_count += 1
            # Look up by Entry.key field, not dictionary key
            return self._by_key.get(key)

        def get_entries(self, keys: list[str]) -> list[Entry]:
            self.call_count += 1
            if not keys:  # Return all entries if keys is empty
                return list(self.entries.values())
            # Look up by Entry.key field
            return [e for k in keys if (e := self._by_key.get(k))]

        def exists(self, key: str) -> bool:
            # Check by Entry.key field for collision detection
            return key in self._by_key or key in self.entries

    return MockEntryProvider(sample_entries)


@pytest.fixture
def csl_style_apa():
    """Provide APA CSL style definition."""
    return {
        "info": {
            "title": "American Psychological Association 7th edition",
            "id": "apa",
            "version": "1.0",
        },
        "citation": {
            "layout": {
                "prefix": "(",
                "suffix": ")",
                "delimiter": "; ",
            },
            "author": {
                "form": "short",
                "and": "&",
                "delimiter": ", ",
                "et-al-min": 3,
                "et-al-use-first": 1,
            },
            "year": {
                "prefix": ", ",
            },
        },
        "bibliography": {
            "layout": {
                "suffix": ".",
            },
            "author": {
                "form": "long",
                "and": "&",
                "delimiter": ", ",
                "delimiter-precedes-last": "always",
                "initialize-with": ". ",
                "name-as-sort-order": "first",
            },
            "year": {
                "prefix": " (",
                "suffix": ")",
            },
            "title": {
                "text-case": "sentence",
                "font-style": "normal",
            },
            "container-title": {
                "font-style": "italic",
            },
        },
    }


@pytest.fixture
def csl_style_custom():
    """Provide custom CSL style for testing."""
    return {
        "info": {
            "title": "Custom Test Style",
            "id": "custom-test",
            "version": "1.0",
        },
        "citation": {
            "layout": {
                "prefix": "[",
                "suffix": "]",
                "delimiter": ", ",
            },
            "author": {
                "form": "short",
                "and": "and",
                "et-al-min": 2,
                "et-al-use-first": 1,
            },
            "year": {
                "prefix": " ",
                "suffix": "",
            },
        },
        "bibliography": {
            "sort": {
                "key": "author year title",
            },
            "layout": {
                "suffix": "",
            },
            "author": {
                "form": "long",
                "and": "and",
                "delimiter": "; ",
                "initialize-with": "",
                "name-as-sort-order": "all",
            },
            "year": {
                "prefix": " ",
                "suffix": ". ",
            },
            "title": {
                "quotes": True,
                "text-case": "title",
            },
        },
    }


@pytest.fixture
def latex_document():
    """Provide sample LaTeX document with various citation commands."""
    return r"""
\documentclass{article}
\begin{document}

\section{Introduction}
According to \cite{smith2024}, quantum computing is advancing rapidly.
Recent work by \citet{doe2023} demonstrates collaborative approaches.
As shown in \citep{knuth1997}, classical algorithms remain important.

\section{Literature Review}
\citeauthor{lee2024} presented their findings at ICML.
The work was published in \citeyear{johnson2023}.
Multiple studies \cite{smith2024,doe2023,knuth1997} confirm this.

\section{Advanced Citations}
See \cite[p.~45]{smith2024} for details.
Compare \cite[see][chapter 3]{knuth1997} with recent work.
\citealt{doe2023} provides an alternative view.
Year in parentheses: \citeyearpar{smith2024}.

\section{BibLaTeX Commands}
Modern citations use \parencite{lee2024} for parenthetical.
Textual citations use \textcite{johnson2023} format.
Footnotes can use \footcite{mozilla2024} for references.
Smart citations with \smartcite{smith2024} adapt to context.
Multiple pre/post: \cite[see][pp. 1--10]{doe2023}.

\end{document}
"""


@pytest.fixture
def markdown_document():
    """Provide sample Markdown document with citations."""
    return """
# Research Paper

## Introduction
According to @smith2024, quantum computing is advancing rapidly.
Recent collaborative work [@doe2023] shows promising results.
Multiple citations are supported [@smith2024; @knuth1997; @lee2024].

## Complex Citations
See @smith2024 [p. 45] for specific details.
Parenthetical citation with prefix [-@johnson2023].
Composite citations work well [@smith2024; see also @doe2023, pp. 23-45].

## Unicode Support
International collaboration [@müller2024] is essential.
Mathematical concepts [@math2024] require special handling.
"""


@pytest.fixture
def bibtex_file():
    """Provide sample BibTeX file for testing."""
    return """
@article{smith2024,
  author = {Smith, John},
  title = {Quantum Computing Advances},
  journal = {Nature},
  volume = {123},
  pages = {45--67},
  year = {2024},
  doi = {10.1038/nature.2024.123}
}

@book{knuth1997,
  author = {Knuth, Donald E.},
  title = {The Art of Computer Programming},
  publisher = {Addison-Wesley},
  address = {Boston},
  edition = {3},
  year = {1997},
  isbn = {978-0-201-89683-1}
}

@inproceedings{lee2024,
  author = {Lee, Kim and Park, Jin},
  title = {Neural Architecture Search: A Survey},
  booktitle = {Proceedings of the International Conference on Machine Learning},
  pages = {123--134},
  year = {2024},
  address = {Vienna, Austria},
  month = {July}
}
"""


@pytest.fixture
def temp_csl_dir():
    """Provide temporary directory with CSL files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csl_dir = Path(tmpdir) / "csl"
        csl_dir.mkdir()

        # Write sample CSL files
        apa_csl = csl_dir / "apa.csl"
        apa_csl.write_text(
            json.dumps(
                {
                    "info": {"id": "apa", "title": "APA 7th"},
                    "citation": {"layout": {"prefix": "(", "suffix": ")"}},
                    "bibliography": {"sort": {"key": "author year"}},
                }
            )
        )

        ieee_csl = csl_dir / "ieee.csl"
        ieee_csl.write_text(
            json.dumps(
                {
                    "info": {"id": "ieee", "title": "IEEE"},
                    "citation": {"layout": {"prefix": "[", "suffix": "]"}},
                    "bibliography": {
                        "sort": {"key": "none"},
                        "layout": {"numbering": True},
                    },
                }
            )
        )

        yield csl_dir


@pytest.fixture
def localization_data():
    """Provide localization data for different languages."""
    return {
        "en": {
            "and": "and",
            "et-al": "et al.",
            "editor": "editor",
            "editors": "editors",
            "edition": "edition",
            "volume": "vol.",
            "number": "no.",
            "pages": "pp.",
            "page": "p.",
            "chapter": "ch.",
            "in": "In",
            "retrieved": "Retrieved",
            "from": "from",
            "accessed": "Accessed",
            "no-date": "n.d.",
            "no-author": "Anonymous",
            "january": "January",
            "february": "February",
            "march": "March",
            "april": "April",
            "may": "May",
            "june": "June",
            "july": "July",
            "august": "August",
            "september": "September",
            "october": "October",
            "november": "November",
            "december": "December",
        },
        "es": {
            "and": "y",
            "et-al": "y otros",
            "editor": "editor",
            "editors": "editores",
            "edition": "edición",
            "volume": "vol.",
            "number": "núm.",
            "pages": "pp.",
            "page": "p.",
            "chapter": "cap.",
            "in": "En",
            "retrieved": "Recuperado",
            "from": "de",
            "accessed": "Consultado",
            "no-date": "s.f.",
            "no-author": "Anónimo",
            "january": "enero",
            "february": "febrero",
            "march": "marzo",
            "april": "abril",
            "may": "mayo",
            "june": "junio",
            "july": "julio",
            "august": "agosto",
            "september": "septiembre",
            "october": "octubre",
            "november": "noviembre",
            "december": "diciembre",
        },
        "fr": {
            "and": "et",
            "et-al": "et al.",
            "editor": "éditeur",
            "editors": "éditeurs",
            "edition": "édition",
            "volume": "vol.",
            "number": "n°",
            "pages": "pp.",
            "page": "p.",
            "chapter": "chap.",
            "in": "Dans",
            "retrieved": "Récupéré",
            "from": "de",
            "accessed": "Consulté le",
            "no-date": "s.d.",
            "no-author": "Anonyme",
            "january": "janvier",
            "february": "février",
            "march": "mars",
            "april": "avril",
            "may": "mai",
            "june": "juin",
            "july": "juillet",
            "august": "août",
            "september": "septembre",
            "october": "octobre",
            "november": "novembre",
            "december": "décembre",
        },
    }


@pytest.fixture
def performance_entries():
    """Generate large number of entries for performance testing."""
    entries = {}
    for i in range(1000):
        entries[f"entry{i:04d}"] = Entry(
            key=f"entry{i:04d}",
            type=EntryType.ARTICLE,
            author=f"Author{i % 100}, Name{i % 50}",
            title=f"Article Title Number {i}: Performance Testing",
            journal=f"Journal {i % 20}",
            volume=str(i % 100),
            pages=f"{i}--{i + 10}",
            year=2020 + (i % 5),
            doi=f"10.1234/test.{i}",
        )
    return entries


@pytest.fixture
def mock_cache():
    """Provide a mock cache for testing caching functionality."""

    class MockCache:
        def __init__(self):
            self.data: dict[str, Any] = {}
            self.hits = 0
            self.misses = 0

        def get(self, key: str) -> Any | None:
            if key in self.data:
                self.hits += 1
                return self.data[key]
            self.misses += 1
            return None

        def set(self, key: str, value: Any, ttl: int = 3600) -> None:
            self.data[key] = value

        def clear(self) -> None:
            self.data.clear()
            self.hits = 0
            self.misses = 0

        def stats(self) -> dict:
            total = self.hits + self.misses
            return {
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": self.hits / total if total > 0 else 0,
                "size": len(self.data),
            }

    return MockCache()
