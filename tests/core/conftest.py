"""Shared fixtures for core module tests.

This module provides test data based on TameTheBeast manual examples
and real-world BibTeX entries for comprehensive testing.
"""

from typing import Any

import pytest

from bibmgr.core.fields import EntryType


@pytest.fixture
def valid_entry_keys() -> list[str]:
    """Valid BibTeX entry keys."""
    return [
        "smith2024",
        "smith_2024",
        "smith-2024",
        "smith:2024",
        "SmithJones2024",
        "10_1038_nature12373",  # DOI-based key
        "RFC-8259",
        "ISO-8601-2019",
    ]


@pytest.fixture
def invalid_entry_keys() -> list[str]:
    """Invalid BibTeX entry keys."""
    return [
        "",  # Empty
        "smith 2024",  # Space
        "smith@2024",  # @ symbol
        "smith.2024",  # Period
        "smith/2024",  # Slash
        "smith\\2024",  # Backslash
        "smith{2024}",  # Braces
        "smith&jones",  # Ampersand
        "smith#2024",  # Hash
        "café2024",  # Non-ASCII
    ]


@pytest.fixture
def sample_article_data() -> dict[str, Any]:
    """Sample article entry data."""
    return {
        "key": "knuth1984",
        "type": EntryType.ARTICLE,
        "author": "Donald E. Knuth",
        "title": "The {TeX}book",
        "journal": "Computers & Typesetting",
        "year": 1984,
        "volume": "A",
        "pages": "1--483",
        "doi": "10.1137/1028001",
    }


@pytest.fixture
def sample_book_data() -> dict[str, Any]:
    """Sample book entry data."""
    return {
        "key": "latex2e",
        "type": EntryType.BOOK,
        "author": "Leslie Lamport",
        "title": "{LaTeX}: A Document Preparation System",
        "publisher": "Addison-Wesley",
        "year": 1994,
        "edition": "2nd",
        "isbn": "0-201-52983-1",
        "address": "Reading, Massachusetts",
    }


@pytest.fixture
def sample_inproceedings_data() -> dict[str, Any]:
    """Sample inproceedings entry data."""
    return {
        "key": "turing1950",
        "type": EntryType.INPROCEEDINGS,
        "author": "Alan M. Turing",
        "title": "Computing Machinery and Intelligence",
        "booktitle": "Mind",
        "year": 1950,
        "volume": "59",
        "number": "236",
        "pages": "433--460",
        "month": "oct",
    }


@pytest.fixture
def complex_author_names() -> list[str]:
    """Complex author names for testing parsing."""
    return [
        # Standard formats
        "Donald E. Knuth",
        "Leslie Lamport",
        "Alan M. Turing",
        # Von particles
        "Ludwig van Beethoven",
        "Charles de Gaulle",
        "John von Neumann",
        "Maria de los Angeles",
        # Jr/Sr
        "Martin Luther King, Jr.",
        "John Smith, III",
        "James Brown, Sr.",
        # Complex von + Jr
        "von Last, Jr, First",
        "de la Cruz, Jr., Maria",
        # Corporate authors
        "{Barnes and Noble}",
        "{The {LaTeX} Project Team}",
        "{European Union}",
        # Unicode names
        "François Müller",
        "José García-López",
        "Пётр Иванов",
        "北京大学",
        # Special cases
        "others",  # BibTeX keyword
        "Jean-Paul Sartre",  # Hyphenated first
        "O'Brien, Patrick",  # Apostrophe
        "van den Berg, Johannes",  # Multiple von particles
    ]


@pytest.fixture
def title_test_cases() -> list[dict[str, str]]:
    """Title test cases for case protection and special characters."""
    return [
        {
            "input": "An Introduction to {LaTeX}",
            "title_case": "An introduction to {LaTeX}",
            "lowercase": "an introduction to {LaTeX}",
            "purified": "An Introduction to LaTeX",
        },
        {
            "input": "The {TeX}book and {\\LaTeX} Companion",
            "title_case": "The {TeX}book and {\\LaTeX} companion",
            "lowercase": "the {TeX}book and {\\LaTeX} companion",
            "purified": "The TeXbook and  Companion",  # {\LaTeX} is special char, removed
        },
        {
            "input": "{IEEE} Transactions on {VLSI} Systems",
            "title_case": "{IEEE} transactions on {VLSI} systems",
            "lowercase": "{IEEE} transactions on {VLSI} systems",
            "purified": "IEEE Transactions on VLSI Systems",
        },
        {
            "input": r"Schr{\"o}dinger's Cat: A {\LaTeX} Example",
            "title_case": r"Schr{\"o}dinger's cat: a {\LaTeX} example",
            "lowercase": r"schr{\"o}dinger's cat: a {\LaTeX} example",
            "purified": "Schrodingers Cat A  Example",
        },
    ]


@pytest.fixture
def valid_dois() -> list[str]:
    """Valid DOI examples."""
    return [
        "10.1038/nature12373",
        "10.1145/2976749.2978313",
        "10.1109/5.771073",
        "10.1007/978-3-319-24277-4",
        "10.1016/j.cell.2016.06.028",
        "10.1371/journal.pone.0213047",
        "10.48550/arXiv.2303.08774",  # arXiv DOI
    ]


@pytest.fixture
def valid_isbns() -> list[dict[str, str]]:
    """Valid ISBN-10 and ISBN-13 examples with checksums."""
    return [
        {"isbn": "0306406152", "type": "isbn10"},
        {"isbn": "0-306-40615-2", "type": "isbn10"},
        {"isbn": "9780306406157", "type": "isbn13"},
        {"isbn": "978-0-306-40615-7", "type": "isbn13"},
        {"isbn": "0201529831", "type": "isbn10"},  # LaTeX book
        {"isbn": "978-0201529838", "type": "isbn13"},
        {"isbn": "043942089X", "type": "isbn10"},  # X checksum - Hitchhiker's Guide
    ]


@pytest.fixture
def valid_issns() -> list[str]:
    """Valid ISSN examples with checksums."""
    return [
        "0378-5955",  # Hearing Research
        "0028-0836",  # Nature
        "2049-369X",  # X checksum (corrected)
        "1476-4687",  # Nature (current)
        "0036-8075",  # Science
        "1095-9203",  # Science (online)
    ]


@pytest.fixture
def crossref_entries() -> list[dict[str, Any]]:
    """Entries with cross-references for testing."""
    return [
        {
            "key": "mlbook2024",
            "type": EntryType.BOOK,
            "editor": "Ian Goodfellow and Yoshua Bengio and Aaron Courville",
            "title": "Deep Learning",
            "publisher": "MIT Press",
            "year": 2024,
        },
        {
            "key": "chapter1",
            "type": EntryType.INBOOK,
            "author": "Yann LeCun",
            "title": "Introduction to Neural Networks",
            "chapter": "1",
            "pages": "1--30",
            "crossref": "mlbook2024",
        },
        {
            "key": "chapter2",
            "type": EntryType.INBOOK,
            "author": "Geoffrey Hinton",
            "title": "Backpropagation and Gradient Descent",
            "chapter": "2",
            "pages": "31--65",
            "crossref": "mlbook2024",
        },
    ]


@pytest.fixture
def duplicate_entries() -> list[dict[str, Any]]:
    """Entries that are duplicates by various criteria."""
    return [
        # Same DOI
        {
            "key": "smith2023a",
            "type": EntryType.ARTICLE,
            "author": "John Smith",
            "title": "Machine Learning Advances",
            "journal": "Nature",
            "year": 2023,
            "doi": "10.1038/nature.2023.12345",
        },
        {
            "key": "smith2023b",
            "type": EntryType.ARTICLE,
            "author": "J. Smith",  # Different format
            "title": "Machine Learning Advances",
            "journal": "Nature",
            "year": 2023,
            "doi": "10.1038/nature.2023.12345",  # Same DOI
        },
        # Same title/author/year
        {
            "key": "jones2024",
            "type": EntryType.INPROCEEDINGS,
            "author": "Alice Jones and Bob Brown",
            "title": "Quantum Computing Applications",
            "booktitle": "ICML 2024",
            "year": 2024,
        },
        {
            "key": "jones2024duplicate",
            "type": EntryType.INPROCEEDINGS,
            "author": "A. Jones and B. Brown",  # Abbreviated
            "title": "Quantum Computing Applications",  # Same
            "booktitle": "International Conference on Machine Learning",
            "year": 2024,
        },
    ]


@pytest.fixture
def bibtex_special_chars() -> dict[str, str]:
    """BibTeX special characters and their escaped versions."""
    return {
        "\\": "\\\\",  # Backslash first!
        "$": "\\$",
        "&": "\\&",
        "#": "\\#",
        "_": "\\_",
        "%": "\\%",
        "~": "\\~{}",
        "^": "\\^{}",
    }


@pytest.fixture
def edge_case_entries() -> list[dict[str, Any]]:
    """Edge case entries for robustness testing."""
    return [
        # Empty required fields
        {
            "key": "empty_article",
            "type": EntryType.ARTICLE,
            "author": "",  # Empty
            "title": "",  # Empty
            "journal": "",  # Empty
            "year": None,  # None
        },
        # Very long content
        {
            "key": "long_abstract",
            "type": EntryType.ARTICLE,
            "author": "Test Author",
            "title": "Test Title",
            "journal": "Test Journal",
            "year": 2024,
            "abstract": "x" * 6000,  # Over 5000 char limit
        },
        # Many authors
        {
            "key": "many_authors",
            "type": EntryType.ARTICLE,
            "author": " and ".join([f"Author {i}" for i in range(150)]),
            "title": "Collaborative Research",
            "journal": "Science",
            "year": 2024,
        },
        # Unicode everywhere
        {
            "key": "unicode_entry",
            "type": EntryType.ARTICLE,
            "author": "François Müller and 北京大学",
            "title": "Unicode Test: αβγδ and 中文标题",
            "journal": "Журнал Науки",
            "year": 2024,
            "abstract": "Testing émojis 🎉 and symbols ∫∂∇",
        },
    ]


@pytest.fixture
def sample_collections() -> list[dict[str, Any]]:
    """Sample collection data for testing."""
    return [
        {
            "name": "Machine Learning",
            "description": "Papers on ML and AI",
            "entry_keys": ["smith2023a", "jones2024"],
            "color": "#FF6B6B",
            "icon": "brain",
        },
        {
            "name": "Recent Papers",
            "description": "Papers from last 2 years",
            "query": "year:2023..2024",  # Smart collection
            "color": "#4ECDC4",
            "icon": "calendar",
        },
        {
            "name": "Quantum Computing",
            "parent_name": "Physics",  # Nested collection
            "entry_keys": ["feynman1982", "shor1994"],
        },
    ]


@pytest.fixture
def string_definitions() -> dict[str, str]:
    """BibTeX string abbreviations."""
    return {
        # Month abbreviations (predefined)
        "jan": "January",
        "feb": "February",
        "dec": "December",
        # Custom abbreviations
        "LNCS": "Lecture Notes in Computer Science",
        "IEEE": "Institute of Electrical and Electronics Engineers",
        "ACM": "Association for Computing Machinery",
        "MIT": "Massachusetts Institute of Technology",
    }


@pytest.fixture
def performance_test_entries(request) -> list[dict[str, Any]]:
    """Generate large number of entries for performance testing."""
    count = getattr(request, "param", 1000)
    entries = []

    for i in range(count):
        entries.append(
            {
                "key": f"perf_test_{i}",
                "type": EntryType.ARTICLE,
                "author": f"Author {i % 100} and Coauthor {i % 50}",
                "title": f"Performance Test Article {i}: " + "word " * (i % 20),
                "journal": f"Journal {i % 10}",
                "year": 2020 + (i % 5),
                "volume": str(i % 50),
                "pages": f"{i}--{i + 10}",
                "doi": f"10.1234/test.{i}",
                "abstract": "Abstract content " * (i % 100),
                "keywords": [f"keyword{j}" for j in range(i % 5)],
            }
        )

    return entries


@pytest.fixture
def sample_entries() -> list[Any]:
    """Sample Entry objects for testing."""
    from bibmgr.core.models import Entry

    return [
        Entry(
            key="knuth1984",
            type=EntryType.ARTICLE,
            author="Donald E. Knuth",
            title="The TeXbook",
            journal="Computers & Typesetting",
            year=1984,
        ),
        Entry(
            key="lamport1994",
            type=EntryType.BOOK,
            author="Leslie Lamport",
            title="LaTeX: A Document Preparation System",
            publisher="Addison-Wesley",
            year=1994,
        ),
        Entry(
            key="turing1950",
            type=EntryType.ARTICLE,
            author="Alan M. Turing",
            title="Computing Machinery and Intelligence",
            journal="Mind",
            year=1950,
        ),
        Entry(
            key="shannon1948",
            type=EntryType.ARTICLE,
            author="Claude E. Shannon",
            title="A Mathematical Theory of Communication",
            journal="Bell System Technical Journal",
            year=1948,
        ),
        Entry(
            key="dijkstra1968",
            type=EntryType.ARTICLE,
            author="Edsger W. Dijkstra",
            title="Go To Statement Considered Harmful",
            journal="Communications of the ACM",
            year=1968,
        ),
    ]
