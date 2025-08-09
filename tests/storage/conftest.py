"""Shared fixtures for storage tests.

This module provides common test fixtures used across storage tests,
following the same patterns as the core module tests.
"""

import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from bibmgr.core.models import Collection, Entry, EntryType


@pytest.fixture
def temp_dir():
    """Temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_entry():
    """A valid sample entry for testing."""
    return Entry(
        key="knuth1984",
        type=EntryType.BOOK,
        author="Donald E. Knuth",
        title="The TeXbook",
        publisher="Addison-Wesley",
        year=1984,
        isbn="0-201-13447-0",
        tags=("tex", "typesetting"),
    )


@pytest.fixture
def sample_article():
    """A valid article entry."""
    return Entry(
        key="turing1950",
        type=EntryType.ARTICLE,
        author="Alan M. Turing",
        title="Computing Machinery and Intelligence",
        journal="Mind",
        volume="59",
        number="236",
        pages="433--460",
        year=1950,
        doi="10.1093/mind/LIX.236.433",
    )


@pytest.fixture
def sample_entries():
    """Collection of diverse entries for testing."""
    return [
        Entry(
            key="knuth1984",
            type=EntryType.BOOK,
            author="Donald E. Knuth",
            title="The TeXbook",
            publisher="Addison-Wesley",
            year=1984,
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
            key="dijkstra1968",
            type=EntryType.ARTICLE,
            author="Edsger W. Dijkstra",
            title="Go To Statement Considered Harmful",
            journal="Communications of the ACM",
            year=1968,
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
            key="shannon1948",
            type=EntryType.ARTICLE,
            author="Claude E. Shannon",
            title="A Mathematical Theory of Communication",
            journal="Bell System Technical Journal",
            year=1948,
        ),
    ]


@pytest.fixture
def entry_with_all_fields():
    """Entry with all possible fields populated."""
    return Entry(
        key="complete2024",
        type=EntryType.ARTICLE,
        author="John Doe and Jane Smith",
        title="A Complete Example Entry",
        journal="Journal of Examples",
        volume="42",
        number="3",
        pages="123--456",
        year=2024,
        month="jan",
        doi="10.1234/example.2024",
        url="https://example.com/paper",
        abstract="This is an abstract with sufficient length to test text handling.",
        keywords=("example", "testing", "complete"),
        note="This is a note",
        address="New York, NY",
        publisher="Example Publishers",
        editor="Bob Editor",
        isbn="978-3-16-148410-0",
        issn="1234-5678",
        tags=("test", "complete"),
    )


@pytest.fixture
def sample_collection():
    """A sample collection for testing."""
    return Collection(
        name="Machine Learning Papers",
        description="Papers on ML topics",
        entry_keys=("turing1950", "shannon1948"),
        color="#FF5733",
        icon="brain",
    )


@pytest.fixture
def sample_smart_collection():
    """A smart (query-based) collection."""
    return Collection(
        name="Recent Papers",
        description="Papers from last 5 years",
        query="year >= 2019",
    )


@pytest.fixture
def nested_collections():
    """Hierarchical collection structure."""
    root_id = uuid.uuid4()
    child_id = uuid.uuid4()

    return [
        Collection(
            id=root_id,
            name="Computer Science",
            description="CS papers",
        ),
        Collection(
            id=child_id,
            name="Algorithms",
            description="Algorithm papers",
            parent_id=root_id,
        ),
        Collection(
            name="Machine Learning",
            description="ML papers",
            parent_id=root_id,
        ),
    ]


@pytest.fixture
def sample_metadata():
    """Sample metadata dictionary."""
    return {
        "entry_key": "knuth1984",
        "tags": ["classic", "typography"],
        "rating": 5,
        "read_status": "read",
        "importance": "high",
        "notes_count": 3,
    }


@pytest.fixture
def sample_note():
    """Sample note data."""
    return {
        "id": str(uuid.uuid4()),
        "entry_key": "knuth1984",
        "content": "This is a fascinating discussion of TeX's line breaking algorithm.",
        "note_type": "general",
        "page": 42,
        "created": datetime.now(),
        "modified": datetime.now(),
        "tags": ["algorithms", "typography"],
    }


@pytest.fixture
def bibtex_content():
    """Sample BibTeX content for import testing."""
    return """
@book{knuth1984,
    author = {Donald E. Knuth},
    title = {The {TeX}book},
    publisher = {Addison-Wesley},
    year = 1984,
    isbn = {0-201-13447-0}
}

@article{turing1950,
    author = {Alan M. Turing},
    title = {Computing Machinery and Intelligence},
    journal = {Mind},
    volume = {59},
    number = {236},
    pages = {433--460},
    year = 1950,
    doi = {10.1093/mind/LIX.236.433}
}

% This is a comment
@misc{example2024,
    author = {Test Author},
    title = {Test Entry},
    year = 2024,
    note = {For testing}
}
"""


@pytest.fixture
def invalid_bibtex():
    """Invalid BibTeX for error testing."""
    return """
@article{missing_fields,
    title = {Only Title}
}

@book{invalid_year,
    author = {Some Author},
    title = {Some Title},
    publisher = {Publisher},
    year = {not a year}
}

@invalidtype{bad_type,
    author = {Author},
    title = {Title}
}
"""


@pytest.fixture
def json_export_data():
    """Sample JSON export format."""
    return {
        "version": "1.0",
        "entries": [
            {
                "key": "knuth1984",
                "type": "book",
                "author": "Donald E. Knuth",
                "title": "The TeXbook",
                "publisher": "Addison-Wesley",
                "year": 1984,
            },
            {
                "key": "turing1950",
                "type": "article",
                "author": "Alan M. Turing",
                "title": "Computing Machinery and Intelligence",
                "journal": "Mind",
                "year": 1950,
            },
        ],
    }


@pytest.fixture
def mock_backend():
    """Mock storage backend for testing."""

    class MockBackend:
        def __init__(self):
            self.data = {}
            self.closed = False
            self.transaction_depth = 0

        def initialize(self):
            pass

        def read(self, key: str) -> dict[str, Any] | None:
            return self.data.get(key)

        def write(self, key: str, data: dict[str, Any]) -> None:
            self.data[key] = data

        def delete(self, key: str) -> bool:
            if key in self.data:
                del self.data[key]
                return True
            return False

        def exists(self, key: str) -> bool:
            return key in self.data

        def keys(self) -> list[str]:
            return list(self.data.keys())

        def clear(self) -> None:
            self.data.clear()

        def close(self) -> None:
            self.closed = True

        def supports_transactions(self) -> bool:
            return True

        @contextmanager
        def begin_transaction(self):
            self.transaction_depth += 1
            yield
            self.transaction_depth -= 1

    return MockBackend()


@pytest.fixture
def event_recorder():
    """Records events for testing event system."""

    class EventRecorder:
        def __init__(self):
            self.events = []

        def record(self, event):
            self.events.append(event)

        def clear(self):
            self.events.clear()

        def get_events_of_type(self, event_type):
            return [e for e in self.events if e.type == event_type]

        def has_event(self, event_type, **data):
            for event in self.events:
                if event.type != event_type:
                    continue

                matches = True
                for key, value in data.items():
                    if event.data.get(key) != value:
                        matches = False
                        break

                if matches:
                    return True

            return False

    return EventRecorder()


@pytest.fixture
def performance_entries():
    """Large collection of entries for performance testing."""
    entries = []
    for i in range(1000):
        entries.append(
            Entry(
                key=f"entry{i:04d}",
                type=EntryType.ARTICLE,
                author=f"Author {i // 10}",
                title=f"Paper Title {i}",
                journal=f"Journal {i % 5}",
                year=2000 + (i % 24),
                pages=f"{i}--{i + 10}",
                doi=f"10.1234/paper.{i}",
                abstract=f"Abstract for paper {i} " * 20,  # Realistic length
                keywords=tuple(f"keyword{j}" for j in range(i % 5)),
            )
        )
    return entries
