"""Shared fixtures for notes tests."""

from datetime import datetime, timedelta
from typing import Protocol
from uuid import uuid4

import pytest

from bibmgr.core.models import Entry, EntryType
from bibmgr.notes.manager import NoteManager
from bibmgr.notes.models import (
    Note,
    NoteType,
    NoteVersion,
    Priority,
    Quote,
    QuoteCategory,
    ReadingProgress,
    ReadingStatus,
)
from bibmgr.notes.storage import NoteStorage
from bibmgr.notes.templates import NoteTemplate


class NoteData(Protocol):
    """Protocol for note data."""

    id: str
    entry_key: str
    content: str
    type: str
    title: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    version: int


class QuoteData(Protocol):
    """Protocol for quote data."""

    id: str
    entry_key: str
    text: str
    page: int | None
    section: str | None
    category: str
    importance: int
    tags: list[str]
    created_at: datetime


class ProgressData(Protocol):
    """Protocol for reading progress data."""

    entry_key: str
    status: str
    priority: int
    current_page: int
    total_pages: int | None
    reading_time_minutes: int
    started_at: datetime | None
    finished_at: datetime | None


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_notes.db"


@pytest.fixture
def sample_note_data():
    """Create sample note data."""
    now = datetime.now()
    return {
        "id": str(uuid4()),
        "entry_key": "einstein1905",
        "content": "# Special Relativity\n\nE = mc²",
        "type": "summary",
        "title": "Special Relativity Notes",
        "tags": ["physics", "relativity"],
        "references": ["lorentz1904", "poincare1905"],
        "created_at": now,
        "updated_at": now,
        "version": 1,
    }


@pytest.fixture
def sample_quote_data():
    """Create sample quote data."""
    return {
        "id": str(uuid4()),
        "entry_key": "feynman1965",
        "text": "The first principle is that you must not fool yourself.",
        "page": 42,
        "section": "Chapter 3",
        "paragraph": 7,
        "category": "inspiration",
        "importance": 5,
        "tags": ["methodology", "philosophy"],
        "note": "Key insight on scientific method",
        "created_at": datetime.now(),
    }


@pytest.fixture
def sample_progress_data():
    """Create sample reading progress data."""
    return {
        "entry_key": "knuth1984",
        "status": "reading",
        "priority": 3,  # HIGH
        "current_page": 150,
        "total_pages": 700,
        "sections_read": 3,
        "sections_total": 12,
        "reading_time_minutes": 240,
        "session_count": 5,
        "started_at": datetime.now() - timedelta(days=7),
        "last_read_at": datetime.now() - timedelta(hours=2),
        "importance": 4,
        "difficulty": 5,
        "enjoyment": 4,
        "comprehension": 3,
    }


@pytest.fixture
def sample_template_data():
    """Create sample template data."""
    return {
        "name": "paper_review",
        "type": "critique",
        "title_template": "Review: {title}",
        "content_template": """## Review of {title}

**Authors**: {authors}
**Year**: {year}

### Summary
{summary}

### Strengths
-

### Weaknesses
-

### Verdict
""",
        "tags": ["review", "critique"],
        "description": "Template for paper reviews",
    }


@pytest.fixture
def multiple_notes_data():
    """Create data for multiple notes."""
    base_time = datetime.now()
    notes = []

    for i in range(5):
        notes.append(
            {
                "id": f"note-{i}",
                "entry_key": f"entry-{i % 2}",  # Two different entries
                "content": f"Content for note {i} with keyword-{i % 3}",
                "type": ["summary", "critique", "idea"][i % 3],
                "title": f"Note {i}",
                "tags": [f"tag-{i % 2}", f"tag-{i % 3}"],
                "created_at": base_time - timedelta(days=i),
                "updated_at": base_time - timedelta(days=i),
                "version": 1,
            }
        )

    return notes


@pytest.fixture
def multiple_quotes_data():
    """Create data for multiple quotes."""
    quotes = []

    for i in range(5):
        quotes.append(
            {
                "id": f"quote-{i}",
                "entry_key": f"entry-{i % 3}",
                "text": f"Important quote {i} about topic-{i % 2}",
                "page": 10 + i * 5,
                "category": ["finding", "methodology", "conclusion"][i % 3],
                "importance": (i % 5) + 1,
                "tags": [f"tag-{i % 2}"],
                "created_at": datetime.now(),
            }
        )

    return quotes


@pytest.fixture
def reading_list_data():
    """Create reading list data."""
    entries = []
    statuses = ["unread", "reading", "read", "skimmed", "to_reread"]
    priorities = [1, 2, 3, 4, 5]  # LOW to CRITICAL

    for i in range(10):
        entries.append(
            {
                "entry_key": f"paper-{i}",
                "status": statuses[i % len(statuses)],
                "priority": priorities[i % len(priorities)],
                "current_page": (i * 20) if i % 2 == 0 else 0,
                "total_pages": 200 if i % 3 == 0 else None,
                "reading_time_minutes": i * 30,
                "importance": (i % 5) + 1,
            }
        )

    return entries


@pytest.fixture
def version_history_data():
    """Create version history data."""
    base_time = datetime.now()
    versions = []

    contents = [
        "Initial version",
        "Added methodology section",
        "Revised conclusions",
        "Final edits and formatting",
    ]

    for i, content in enumerate(contents):
        versions.append(
            {
                "version": i + 1,
                "content": content,
                "created_at": base_time + timedelta(hours=i * 2),
                "change_summary": f"Version {i + 1}: {content[:20]}",
            }
        )

    return versions


@pytest.fixture
def bulk_operation_data():
    """Create data for bulk operations."""
    note_ids = [f"bulk-note-{i}" for i in range(10)]
    return {
        "note_ids": note_ids,
        "add_tags": ["processed", "reviewed"],
        "remove_tags": ["draft", "pending"],
    }


@pytest.fixture
def concurrent_operations():
    """Create data for testing concurrent operations."""
    return {
        "operations": [
            {"type": "create", "entry_key": "entry1", "content": "Note 1"},
            {"type": "create", "entry_key": "entry2", "content": "Note 2"},
            {"type": "update", "note_id": "note-1", "content": "Updated 1"},
            {"type": "delete", "note_id": "note-2"},
            {"type": "create", "entry_key": "entry3", "content": "Note 3"},
        ],
        "expected_count": 2,  # After all operations
    }


@pytest.fixture
def search_test_data():
    """Create data for search testing."""
    return {
        "notes": [
            {
                "id": "search-1",
                "content": "Quantum mechanics and wave functions",
                "type": "summary",
                "tags": ["physics", "quantum"],
            },
            {
                "id": "search-2",
                "content": "Classical mechanics differs from quantum theory",
                "type": "critique",
                "tags": ["physics", "classical"],
            },
            {
                "id": "search-3",
                "content": "Statistical mechanics and thermodynamics",
                "type": "methodology",
                "tags": ["physics", "statistics"],
            },
        ],
        "queries": [
            {"text": "quantum", "expected_ids": ["search-1", "search-2"]},
            {"text": "mechanics", "expected_ids": ["search-1", "search-2", "search-3"]},
            {"text": "wave", "expected_ids": ["search-1"]},
        ],
    }


@pytest.fixture
def template_validation_data():
    """Create data for template validation testing."""
    return {
        "valid_template": {
            "name": "valid",
            "type": "summary",
            "title_template": "Summary: {title}",
            "content_template": "Entry: {entry_key}\nDate: {date}",
            "tags": ["summary"],
            "description": "Valid template",
        },
        "invalid_templates": [
            {
                "name": "",  # Empty name
                "type": "summary",
                "title_template": "Title",
                "content_template": "Content",
            },
            {
                "name": "missing_type",
                # Missing type field
                "title_template": "Title",
                "content_template": "Content",
            },
            {
                "name": "invalid_type",
                "type": "invalid_type",  # Invalid note type
                "title_template": "Title",
                "content_template": "Content",
            },
        ],
    }


@pytest.fixture
def performance_test_data():
    """Create data for performance testing."""
    # Large dataset for performance testing
    notes = []
    for i in range(1000):
        notes.append(
            {
                "id": f"perf-note-{i}",
                "entry_key": f"entry-{i % 100}",
                "content": f"Content {i} " * 100,  # ~100 words per note
                "type": ["summary", "critique", "idea"][i % 3],
                "tags": [f"tag-{j}" for j in range(i % 5)],
                "version": 1,
            }
        )

    return {
        "notes": notes,
        "batch_size": 100,
        "expected_time_ms": 1000,  # Should complete within 1 second
    }


@pytest.fixture
def error_scenarios():
    """Create error scenario test data."""
    return {
        "duplicate_id": {
            "note1": {"id": "dup-id", "entry_key": "e1", "content": "Content 1"},
            "note2": {"id": "dup-id", "entry_key": "e2", "content": "Content 2"},
        },
        "invalid_entry_key": {
            "note": {"id": "test", "entry_key": None, "content": "Content"},
        },
        "oversized_content": {
            "note": {"id": "big", "entry_key": "e1", "content": "x" * 10_000_000},
        },
        "invalid_version": {
            "note_id": "nonexistent",
            "version": 999,
        },
        "circular_reference": {
            "note": {"id": "circ", "entry_key": "e1", "references": ["circ"]},
        },
    }


# Factory fixtures


@pytest.fixture
def note_factory():
    """Factory for creating Note instances."""

    def _create_note(**kwargs):
        # Convert string type to enum if needed
        if "type" in kwargs and isinstance(kwargs["type"], str):
            kwargs["type"] = NoteType(kwargs["type"])

        # Provide defaults for required fields
        if "id" not in kwargs:
            kwargs["id"] = str(uuid4())
        if "entry_key" not in kwargs:
            kwargs["entry_key"] = "test-entry"
        if "content" not in kwargs:
            kwargs["content"] = "Test content"

        return Note(**kwargs)

    return _create_note


@pytest.fixture
def quote_factory():
    """Factory for creating Quote instances."""

    def _create_quote(**kwargs):
        # Convert string category to enum if needed
        if "category" in kwargs and isinstance(kwargs["category"], str):
            kwargs["category"] = QuoteCategory(kwargs["category"])

        # Provide defaults for required fields
        if "id" not in kwargs:
            kwargs["id"] = str(uuid4())
        if "entry_key" not in kwargs:
            kwargs["entry_key"] = "test-entry"
        if "text" not in kwargs:
            kwargs["text"] = "Test quote text"

        return Quote(**kwargs)

    return _create_quote


@pytest.fixture
def progress_factory():
    """Factory for creating ReadingProgress instances."""

    def _create_progress(**kwargs):
        # Convert string status to enum if needed
        if "status" in kwargs and isinstance(kwargs["status"], str):
            kwargs["status"] = ReadingStatus(kwargs["status"])

        # Convert int priority to enum if needed
        if "priority" in kwargs and isinstance(kwargs["priority"], int):
            kwargs["priority"] = Priority(kwargs["priority"])

        # Provide default for required field
        if "entry_key" not in kwargs:
            kwargs["entry_key"] = "test-entry"

        return ReadingProgress(**kwargs)

    return _create_progress


@pytest.fixture
def version_factory():
    """Factory for creating NoteVersion instances."""

    def _create_version(**kwargs):
        # Provide defaults for required fields
        if "note_id" not in kwargs:
            kwargs["note_id"] = str(uuid4())
        if "version" not in kwargs:
            kwargs["version"] = 1
        if "content" not in kwargs:
            kwargs["content"] = "Version content"
        if "content_hash" not in kwargs:
            import hashlib

            kwargs["content_hash"] = hashlib.sha256(
                kwargs["content"].encode()
            ).hexdigest()[:16]
        if "created_at" not in kwargs:
            kwargs["created_at"] = datetime.now()

        return NoteVersion(**kwargs)

    return _create_version


@pytest.fixture
def template_factory():
    """Factory for creating NoteTemplate instances."""

    def _create_template(**kwargs):
        # Convert string type to enum if needed
        if "type" in kwargs and isinstance(kwargs["type"], str):
            kwargs["type"] = NoteType(kwargs["type"])

        # Provide defaults for required fields
        if "name" not in kwargs:
            kwargs["name"] = "test-template"
        if "type" not in kwargs:
            kwargs["type"] = NoteType.GENERAL
        if "title_template" not in kwargs:
            kwargs["title_template"] = "Title: {title}"
        if "content_template" not in kwargs:
            kwargs["content_template"] = "Content: {content}"
        if "tags" not in kwargs:
            kwargs["tags"] = []
        if "description" not in kwargs:
            kwargs["description"] = "Test template"

        return NoteTemplate(**kwargs)

    return _create_template


@pytest.fixture
def entry_factory():
    """Factory for creating Entry instances for testing."""

    def _create_entry(**kwargs):
        # Provide defaults for required fields
        if "key" not in kwargs:
            kwargs["key"] = "test-key"
        if "type" not in kwargs:
            kwargs["type"] = EntryType.ARTICLE

        return Entry(**kwargs)

    return _create_entry


@pytest.fixture
def storage_factory():
    """Factory for creating NoteStorage instances."""

    def _create_storage(db_path):
        return NoteStorage(db_path)

    return _create_storage


@pytest.fixture
def storage(temp_db_path):
    """Create a NoteStorage instance with temporary database."""
    storage = NoteStorage(temp_db_path)
    yield storage
    storage.close()


@pytest.fixture
def manager(temp_db_path):
    """Create a NoteManager instance with temporary database."""
    storage = NoteStorage(temp_db_path)
    manager = NoteManager(storage)
    yield manager
    storage.close()


@pytest.fixture
def note_type_enum():
    """Provide NoteType enum for tests."""
    return NoteType


@pytest.fixture
def reading_status_enum():
    """Provide ReadingStatus enum for tests."""
    return ReadingStatus


@pytest.fixture
def priority_enum():
    """Provide Priority enum for tests."""
    return Priority


@pytest.fixture
def quote_category_enum():
    """Provide QuoteCategory enum for tests."""
    return QuoteCategory


@pytest.fixture
def benchmark():
    """Simple benchmark fixture for performance tests."""
    import time

    class Benchmark:
        def __init__(self):
            self.stats = {}

        def __call__(self, func, *args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            end = time.perf_counter()
            self.stats["mean"] = end - start
            return result

    return Benchmark()
