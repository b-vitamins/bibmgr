"""Shared fixtures and test utilities for operations module tests."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from bibmgr.core.builders import CollectionBuilder, EntryBuilder
from bibmgr.core.fields import EntryType
from bibmgr.core.models import Entry
from bibmgr.storage.backends.memory import MemoryBackend
from bibmgr.storage.events import Event, EventBus, EventType
from bibmgr.storage.metadata import EntryMetadata, MetadataStore, Note
from bibmgr.storage.repository import (
    CollectionRepository,
    EntryRepository,
    RepositoryManager,
)

MINIMAL_ENTRY_DATA = {
    "key": "minimal2024",
    "type": EntryType.MISC,
    "title": "A Minimal Entry",
    "year": 2024,
}

COMPLETE_ARTICLE_DATA = {
    "key": "smith2024neural",
    "type": EntryType.ARTICLE,
    "author": "Smith, John and Doe, Jane and Brown, Alice",
    "title": "Neural Networks for {BibTeX} Processing: A Comprehensive Study",
    "journal": "Journal of Machine Learning Research",
    "year": 2024,
    "volume": "25",
    "number": "3",
    "pages": "123--456",
    "month": "mar",
    "doi": "10.1234/jmlr.2024.0123",
    "url": "https://jmlr.org/papers/v25/smith24a.html",
    "abstract": "We present a comprehensive study of neural networks for BibTeX processing.",
    "keywords": ["neural networks", "bibtex", "machine learning"],
}

COMPLETE_BOOK_DATA = {
    "key": "knuth1984texbook",
    "type": EntryType.BOOK,
    "author": "Knuth, Donald E.",
    "title": "The {TeXbook}",
    "publisher": "Addison-Wesley",
    "year": 1984,
    "address": "Reading, Massachusetts",
    "edition": "1st",
    "isbn": "0-201-13447-0",
    "note": "The definitive guide to TeX",
}

DUPLICATE_ENTRY_SETS = [
    [
        {
            "key": "alice2023study",
            "type": EntryType.ARTICLE,
            "author": "Alice, A.",
            "title": "A Study",
            "journal": "Nature",
            "year": 2023,
            "doi": "10.1038/nature.2023.1234",
        },
        {
            "key": "alice2023nature",
            "type": EntryType.ARTICLE,
            "author": "Alice, Amy",
            "title": "A Study of Machine Learning",
            "journal": "Nature",
            "year": 2023,
            "doi": "10.1038/nature.2023.1234",
        },
    ],
    [
        {
            "key": "bob2022analysis",
            "type": EntryType.INPROCEEDINGS,
            "author": "Bob, B. and Charlie, C.",
            "title": "Analysis of Deep Learning Models",
            "booktitle": "Proceedings of ICML",
            "year": 2022,
        },
        {
            "key": "bob2022icml",
            "type": EntryType.INPROCEEDINGS,
            "author": "Bob, Brian and Charlie, Charles",
            "title": "Analysis of Deep Learning Models",
            "booktitle": "ICML 2022",
            "year": 2022,
            "pages": "100--110",
        },
    ],
]

INVALID_ENTRY_DATA = [
    {
        "key": "missing_author",
        "type": EntryType.ARTICLE,
        "title": "Missing Author",
        "journal": "Some Journal",
        "year": 2024,
    },
    {
        "key": "invalid_year",
        "type": EntryType.ARTICLE,
        "author": "Test, T.",
        "title": "Invalid Year",
        "journal": "Journal",
        "year": "not_a_year",
    },
    {
        "key": "invalid_doi",
        "type": EntryType.ARTICLE,
        "author": "Test, T.",
        "title": "Invalid DOI",
        "journal": "Journal",
        "year": 2024,
        "doi": "not-a-valid-doi",
    },
]


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def memory_backend():
    """Create a memory storage backend."""
    return MemoryBackend()


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


@pytest.fixture
def entry_repository(memory_backend):
    """Create an entry repository with memory backend."""
    return EntryRepository(memory_backend)


@pytest.fixture
def collection_repository(memory_backend):
    """Create a collection repository with memory backend."""
    return CollectionRepository(memory_backend)


@pytest.fixture
def metadata_store(temp_dir):
    """Create a metadata store."""
    return MetadataStore(temp_dir)


@pytest.fixture
def repository_manager(memory_backend):
    """Create a repository manager with all repositories."""
    return RepositoryManager(memory_backend)


@pytest.fixture
def minimal_entry():
    """Create a minimal valid entry."""
    return Entry.from_dict(MINIMAL_ENTRY_DATA)


@pytest.fixture
def complete_article():
    """Create a complete article entry."""
    return Entry.from_dict(COMPLETE_ARTICLE_DATA)


@pytest.fixture
def complete_book():
    """Create a complete book entry."""
    return Entry.from_dict(COMPLETE_BOOK_DATA)


@pytest.fixture
def duplicate_entries():
    """Create sets of duplicate entries for testing."""
    return [
        [Entry.from_dict(data) for data in entry_set]
        for entry_set in DUPLICATE_ENTRY_SETS
    ]


@pytest.fixture
def invalid_entries():
    """Create invalid entries for error testing."""
    entries = []
    for data in INVALID_ENTRY_DATA:
        try:
            entries.append(Entry.from_dict(data))
        except Exception:
            entries.append(data)
    return entries


@pytest.fixture
def sample_entries():
    """Create a diverse set of sample entries."""
    return [
        EntryBuilder()
        .key("smith2020")
        .type(EntryType.ARTICLE)
        .author("Smith, John")
        .title("Machine Learning Advances")
        .journal("Nature")
        .year(2020)
        .build(),
        EntryBuilder()
        .key("doe2021")
        .type(EntryType.BOOK)
        .author("Doe, Jane")
        .title("Deep Learning")
        .custom_field("publisher", "MIT Press")
        .year(2021)
        .build(),
        EntryBuilder()
        .key("conf2022")
        .type(EntryType.INPROCEEDINGS)
        .author("Brown, Bob")
        .title("Neural Networks")
        .custom_field("booktitle", "ICML 2022")
        .year(2022)
        .build(),
        EntryBuilder()
        .key("tech2023")
        .type(EntryType.TECHREPORT)
        .author("White, Alice")
        .title("AI Report")
        .custom_field("institution", "Stanford")
        .year(2023)
        .build(),
        EntryBuilder()
        .key("phd2024")
        .type(EntryType.PHDTHESIS)
        .author("Green, Charlie")
        .title("Quantum Computing")
        .custom_field("school", "MIT")
        .year(2024)
        .build(),
    ]


@pytest.fixture
def sample_collections():
    """Create sample collections."""
    return [
        CollectionBuilder()
        .name("Research Papers")
        .description("Active research papers")
        .color("#FF0000")
        .add_entry_keys("smith2020", "doe2021")
        .build(),
        CollectionBuilder()
        .name("Conference Papers")
        .description("Papers from conferences")
        .smart_filter("type", "=", "inproceedings")
        .build(),
        CollectionBuilder()
        .name("2024 Reading List")
        .description("Papers to read in 2024")
        .add_entry_keys("tech2023", "phd2024")
        .build(),
    ]


@pytest.fixture
def sample_metadata():
    """Create sample metadata entries."""
    return [
        EntryMetadata(
            entry_key="smith2020",
            tags={"machine-learning", "neural-networks"},
            rating=5,
            read_status="read",
            read_date=datetime.now() - timedelta(days=30),
            importance="high",
        ),
        EntryMetadata(
            entry_key="doe2021",
            tags={"deep-learning", "textbook"},
            rating=4,
            read_status="reading",
            importance="normal",
        ),
        EntryMetadata(
            entry_key="conf2022",
            tags={"conference", "neural-networks"},
            read_status="unread",
            importance="low",
        ),
    ]


@pytest.fixture
def sample_notes():
    """Create sample notes."""
    return [
        Note(
            entry_key="smith2020",
            content="Excellent introduction to transformer architectures",
            note_type="summary",
            page=15,
            tags=["transformers", "attention"],
        ),
        Note(
            entry_key="smith2020",
            content="'Attention is all you need' - key insight",
            note_type="quote",
            page=23,
            tags=["quote"],
        ),
        Note(
            entry_key="doe2021",
            content="Chapter 3 has great examples",
            note_type="general",
            tags=["examples"],
        ),
    ]


@pytest.fixture
def bibtex_content():
    """Sample BibTeX content for import testing."""
    return """
@article{smith2020,
    author = {Smith, John and Doe, Jane},
    title = {Machine Learning Advances},
    journal = {Nature},
    year = {2020},
    volume = {583},
    pages = {100--110},
    doi = {10.1038/nature.2020.1234}
}

@book{knuth1984,
    author = {Knuth, Donald E.},
    title = {The {TeXbook}},
    publisher = {Addison-Wesley},
    year = {1984},
    isbn = {0-201-13447-0}
}

@inproceedings{conference2022,
    author = {Brown, Alice and Green, Bob},
    title = {Neural {Networks} for {NLP}},
    booktitle = {Proceedings of ACL 2022},
    year = {2022},
    pages = {45--56}
}
"""


@pytest.fixture
def ris_content():
    """Sample RIS content for import testing."""
    return """TY  - JOUR
AU  - Smith, John
AU  - Doe, Jane
TI  - Machine Learning Advances
JO  - Nature
PY  - 2020
VL  - 583
SP  - 100
EP  - 110
DO  - 10.1038/nature.2020.1234
ER  -

TY  - BOOK
AU  - Knuth, Donald E.
TI  - The TeXbook
PB  - Addison-Wesley
PY  - 1984
SN  - 0-201-13447-0
ER  -
"""


@pytest.fixture
def json_content():
    """Sample JSON content for import testing."""
    return """{
    "entries": [
        {
            "key": "smith2020",
            "type": "article",
            "author": "Smith, John and Doe, Jane",
            "title": "Machine Learning Advances",
            "journal": "Nature",
            "year": 2020,
            "volume": "583",
            "pages": "100--110",
            "doi": "10.1038/nature.2020.1234"
        },
        {
            "key": "knuth1984",
            "type": "book",
            "author": "Knuth, Donald E.",
            "title": "The TeXbook",
            "publisher": "Addison-Wesley",
            "year": 1984,
            "isbn": "0-201-13447-0"
        }
    ]
}"""


@pytest.fixture
def mock_event_handler():
    """Create a mock event handler for testing event publishing."""

    class MockEventHandler:
        def __init__(self):
            self.events: list[Event] = []

        def handle(self, event: Event) -> None:
            self.events.append(event)

        def get_events_by_type(self, event_type: EventType) -> list[Event]:
            return [e for e in self.events if e.type == event_type]

        def clear(self) -> None:
            self.events.clear()

    return MockEventHandler()


@pytest.fixture
def populated_repository(entry_repository, sample_entries):
    """Create a repository populated with sample entries."""
    for entry in sample_entries:
        entry_repository.save(entry)
    return entry_repository


@pytest.fixture
def conflicting_entry(complete_article):
    """Create an entry that conflicts with complete_article."""
    data = complete_article.to_dict()
    data.update(
        {
            "author": "Different, Author",
            "pages": "789--890",
            "note": "This is a different version",
        }
    )
    return Entry.from_dict(data)


class MockProgressReporter:
    """Mock progress reporter for testing."""

    def __init__(self):
        self.reports: list[dict[str, Any]] = []

    def report(
        self,
        stage: str,
        current: int,
        total: int,
        message: str | None = None,
    ) -> None:
        self.reports.append(
            {
                "stage": stage,
                "current": current,
                "total": total,
                "message": message,
                "timestamp": datetime.now(),
            }
        )

    def get_stage_reports(self, stage: str) -> list[dict[str, Any]]:
        return [r for r in self.reports if r["stage"] == stage]

    def get_last_report(self) -> dict[str, Any] | None:
        return self.reports[-1] if self.reports else None


@pytest.fixture
def progress_reporter():
    """Create a mock progress reporter."""
    return MockProgressReporter()


class MockConflictResolver:
    """Mock conflict resolver for testing."""

    def __init__(self, strategy: str = "skip"):
        self.strategy = strategy
        self.resolved_conflicts: list[dict[str, Any]] = []

    def resolve(
        self,
        new_entry: Entry,
        existing_entry: Entry,
        context: dict[str, Any],
    ) -> Any:
        self.resolved_conflicts.append(
            {
                "new": new_entry,
                "existing": existing_entry,
                "context": context,
                "strategy": self.strategy,
            }
        )

        class Decision:
            def __init__(self, action: str, new_key: str | None = None):
                self.action = action
                self.new_key = new_key

        if self.strategy == "rename":
            return Decision("rename", f"{new_entry.key}_resolved")
        else:
            return Decision(self.strategy)


@pytest.fixture
def conflict_resolver():
    """Create a mock conflict resolver."""
    return MockConflictResolver()


MERGE_TEST_CASES = [
    {
        "name": "merge_by_doi",
        "entries": [
            {
                "key": "entry1",
                "type": EntryType.ARTICLE,
                "author": "Smith, J.",
                "title": "Study",
                "journal": "Nature",
                "year": 2020,
                "doi": "10.1038/test",
            },
            {
                "key": "entry2",
                "type": EntryType.ARTICLE,
                "author": "Smith, John",
                "title": "A Complete Study",
                "journal": "Nature",
                "year": 2020,
                "doi": "10.1038/test",
                "pages": "1--10",
            },
        ],
        "expected_fields": {
            "author": "Smith, John",
            "title": "A Complete Study",
            "pages": "1--10",
        },
    },
    {
        "name": "merge_similar_titles",
        "entries": [
            {
                "key": "conf1",
                "type": EntryType.INPROCEEDINGS,
                "author": "Alice, A.",
                "title": "Neural Networks",
                "booktitle": "ICML",
                "year": 2023,
            },
            {
                "key": "conf2",
                "type": EntryType.INPROCEEDINGS,
                "author": "Alice, Amy",
                "title": "Neural Networks for NLP",
                "booktitle": "International Conference on Machine Learning",
                "year": 2023,
                "pages": "100--110",
            },
        ],
        "expected_fields": {
            "title": "Neural Networks for NLP",
            "booktitle": "International Conference on Machine Learning",
        },
    },
]


@pytest.fixture
def merge_test_cases():
    """Provide test cases for merge operations."""
    return MERGE_TEST_CASES


IMPORT_SCENARIOS = [
    {
        "name": "clean_import",
        "description": "Import entries with no conflicts",
        "has_conflicts": False,
        "has_duplicates": False,
        "expected_imported": 3,
        "expected_skipped": 0,
        "expected_failed": 0,
    },
    {
        "name": "with_conflicts",
        "description": "Import entries with key conflicts",
        "has_conflicts": True,
        "conflict_resolution": "rename",
        "expected_imported": 3,
        "expected_skipped": 0,
        "expected_failed": 0,
    },
    {
        "name": "with_duplicates",
        "description": "Import entries with content duplicates",
        "has_duplicates": True,
        "merge_duplicates": True,
        "expected_imported": 2,
        "expected_merged": 1,
        "expected_skipped": 0,
    },
    {
        "name": "validation_failures",
        "description": "Import entries with validation errors",
        "has_invalid": True,
        "expected_imported": 2,
        "expected_failed": 1,
    },
]


@pytest.fixture
def import_scenarios():
    """Provide import workflow test scenarios."""
    return IMPORT_SCENARIOS


def assert_entry_equal(
    actual: Entry, expected: Entry, ignore_fields: set[str] | None = None
):
    """Assert two entries are equal, optionally ignoring certain fields."""
    ignore_fields = ignore_fields or {"added", "modified"}

    actual_dict = actual.to_dict()
    expected_dict = expected.to_dict()

    for field in ignore_fields:
        actual_dict.pop(field, None)
        expected_dict.pop(field, None)

    assert actual_dict == expected_dict


def assert_result_success(result: Any, expected_message: str | None = None):
    """Assert an operation result indicates success."""
    assert hasattr(result, "status"), "Result must have status"
    assert result.status.is_success(), f"Expected success, got {result.status}"

    if expected_message:
        assert expected_message in result.message


def assert_result_failure(result: Any, expected_error: str | None = None):
    """Assert an operation result indicates failure."""
    assert hasattr(result, "status"), "Result must have status"
    assert result.status.is_failure(), f"Expected failure, got {result.status}"

    if expected_error:
        if hasattr(result, "errors") and result.errors:
            error_messages = " ".join(result.errors)
            assert expected_error in error_messages
        else:
            assert expected_error in result.message


def assert_events_published(event_bus: EventBus, expected_types: list[EventType]):
    """Assert specific event types were published."""
    history = event_bus.get_history()
    published_types = [event.type for event in history]

    for expected_type in expected_types:
        assert expected_type in published_types, (
            f"Expected {expected_type} event not found"
        )


def create_entry_with_data(**kwargs) -> Entry:
    """Create an entry with provided data, using defaults for missing fields."""
    data = {
        "key": kwargs.get("key", f"test_{uuid4().hex[:8]}"),
        "type": kwargs.get("type", EntryType.MISC),
        "title": kwargs.get("title", "Test Entry"),
        "year": kwargs.get("year", 2024),
    }
    data.update(kwargs)
    return Entry.from_dict(data)
