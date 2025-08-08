"""Shared fixtures for operations tests."""

import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from bibmgr.core.models import Entry, EntryType
from bibmgr.storage.backend import FileSystemStorage


@pytest.fixture
def temp_storage() -> Iterator[FileSystemStorage]:
    """Provide temporary storage backend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield FileSystemStorage(Path(tmpdir))


@pytest.fixture
def sample_entries() -> list[Entry]:
    """Provide sample entries for testing."""
    return [
        Entry(
            key="knuth1984",
            type=EntryType.BOOK,
            title="The TeXbook",
            author="Donald E. Knuth",
            publisher="Addison-Wesley",
            year=1984,
        ),
        Entry(
            key="turing1936",
            type=EntryType.ARTICLE,
            title="On Computable Numbers",
            author="Alan M. Turing",
            journal="Proceedings of the London Mathematical Society",
            year=1936,
            volume="42",
            pages="230-265",
        ),
        Entry(
            key="shannon1948",
            type=EntryType.ARTICLE,
            title="A Mathematical Theory of Communication",
            author="Claude E. Shannon",
            journal="Bell System Technical Journal",
            year=1948,
            volume="27",
            pages="379-423",
            doi="10.1002/j.1538-7305.1948.tb01338.x",
        ),
        Entry(
            key="vonneumann1945",
            type=EntryType.TECHREPORT,
            title="First Draft of a Report on the EDVAC",
            author="John von Neumann",
            institution="Moore School of Electrical Engineering",
            year=1945,
        ),
        Entry(
            key="dijkstra1968",
            type=EntryType.ARTICLE,
            title="Go To Statement Considered Harmful",
            author="Edsger W. Dijkstra",
            journal="Communications of the ACM",
            year=1968,
            volume="11",
            number="3",
            pages="147-148",
        ),
    ]


@pytest.fixture
def duplicate_entries() -> list[Entry]:
    """Provide entries with various duplicate scenarios."""
    return [
        # Original entry
        Entry(
            key="paper2023",
            type=EntryType.ARTICLE,
            title="Machine Learning for Climate Prediction",
            author="Jane Smith and John Doe",
            journal="Nature Climate Change",
            year=2023,
            doi="10.1038/s41558-023-01234",
        ),
        # Same DOI, different metadata
        Entry(
            key="paper2023_dup1",
            type=EntryType.ARTICLE,
            title="ML for Climate Prediction",  # Abbreviated title
            author="J. Smith and J. Doe",  # Abbreviated authors
            journal="Nature Climate Change",
            year=2023,
            doi="10.1038/s41558-023-01234",  # Same DOI
        ),
        # Similar title, same authors
        Entry(
            key="paper2023_dup2",
            type=EntryType.ARTICLE,
            title="Machine Learning for Climate Predictions",  # Slight variation
            author="Jane Smith and John Doe",
            journal="Nature Climate",  # Abbreviated journal
            year=2023,
        ),
        # Different paper entirely
        Entry(
            key="other2022",
            type=EntryType.ARTICLE,
            title="Deep Learning in Biology",
            author="Alice Johnson",
            journal="Science",
            year=2022,
            doi="10.1126/science.abc1234",
        ),
    ]


@pytest.fixture
def bibtex_content() -> str:
    """Provide sample BibTeX content for import testing."""
    return """
@article{einstein1905,
    title = {On the Electrodynamics of Moving Bodies},
    author = {Albert Einstein},
    journal = {Annalen der Physik},
    year = {1905},
    volume = {17},
    pages = {891-921}
}

@book{feynman1965,
    title = {The Feynman Lectures on Physics},
    author = {Richard P. Feynman and Robert B. Leighton and Matthew Sands},
    publisher = {Addison-Wesley},
    year = {1965},
    address = {Reading, MA}
}

@inproceedings{berners-lee1991,
    title = {WorldWideWeb: Proposal for a HyperText Project},
    author = {Tim Berners-Lee and Robert Cailliau},
    booktitle = {CERN Internal Report},
    year = {1991},
    organization = {CERN}
}

@misc{satoshi2008,
    title = {Bitcoin: A Peer-to-Peer Electronic Cash System},
    author = {Satoshi Nakamoto},
    year = {2008},
    howpublished = {\\url{https://bitcoin.org/bitcoin.pdf}}
}
"""


@pytest.fixture
def invalid_bibtex_content() -> str:
    """Provide invalid BibTeX content for error testing."""
    return """
@article{missing_fields,
    title = {Entry with Missing Required Fields}
}

@book{invalid_year,
    title = {Book with Invalid Year},
    author = {Test Author},
    publisher = {Test Publisher},
    year = {not_a_year}
}

@article{unclosed_brace,
    title = {Entry with unclosed brace,
    author = {Test Author},
    journal = {Test Journal}

@article{duplicate_key,
    title = {First Entry},
    author = {Author One},
    journal = {Journal One},
    year = {2023}
}

@article{duplicate_key,
    title = {Second Entry with Same Key},
    author = {Author Two},
    journal = {Journal Two},
    year = {2023}
}
"""


@pytest.fixture
def mock_validator():
    """Mock validator for testing."""

    class MockValidator:
        def __init__(self, should_fail: bool = False):
            self.should_fail = should_fail
            self.validated_entries = []

        def validate(self, entry: Entry) -> list[str]:
            self.validated_entries.append(entry)
            if self.should_fail:
                return [f"Validation failed for {entry.key}"]
            return []

    return MockValidator


@pytest.fixture
def mock_progress_reporter():
    """Mock progress reporter for testing."""

    class MockProgressReporter:
        def __init__(self):
            self.reports = []

        def report(
            self, stage: Any, current: int, total: int, message: str | None = None
        ):
            self.reports.append(
                {"stage": stage, "current": current, "total": total, "message": message}
            )

    return MockProgressReporter
