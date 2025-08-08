"""Pytest fixtures for storage module tests."""

from datetime import datetime
from pathlib import Path

import pytest

from bibmgr.core.models import Entry, EntryType
from bibmgr.storage.backend import FileSystemStorage
from bibmgr.storage.parser import BibtexParser
from bibmgr.storage.sidecar import EntryMetadata, MetadataSidecar, Note
from bibmgr.storage.system import StorageSystem


@pytest.fixture
def parser_factory():
    """Factory for creating parser instances."""

    def _factory():
        return BibtexParser()

    return _factory


@pytest.fixture
def storage_factory():
    """Factory for creating storage instances."""

    def _factory(path: Path):
        return FileSystemStorage(path)

    return _factory


@pytest.fixture
def sidecar_factory():
    """Factory for creating sidecar instances."""

    def _factory(path: Path):
        return MetadataSidecar(path)

    return _factory


@pytest.fixture
def storage_system():
    """Factory for creating complete storage system."""

    def _factory(path: Path):
        return StorageSystem(path)

    return _factory


@pytest.fixture
def entry_factory():
    """Factory for creating Entry instances."""

    def _factory(
        key: str = "test",
        type: str = "article",
        title: str = "Test Title",
        author: str = "Test Author",
        year: int = 2024,
        **kwargs,
    ) -> Entry:
        entry_type = EntryType(type.lower()) if isinstance(type, str) else type
        return Entry(
            key=key, type=entry_type, title=title, author=author, year=year, **kwargs
        )

    return _factory


@pytest.fixture
def metadata_factory():
    """Factory for creating EntryMetadata instances."""

    def _factory(
        key: str = "test",
        notes: str | None = None,
        tags: list[str] | None = None,
        rating: int | None = None,
        reading_status: str | None = None,
        **kwargs,
    ) -> EntryMetadata:
        return EntryMetadata(
            key=key,
            notes=notes,
            tags=tags,
            rating=rating,
            reading_status=reading_status,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            **kwargs,
        )

    return _factory


@pytest.fixture
def note_factory():
    """Factory for creating Note instances."""

    def _factory(
        id: str = "note1",
        entry_key: str = "test",
        content: str = "Test note content",
        type: str = "general",
        **kwargs,
    ) -> Note:
        return Note(
            id=id,
            entry_key=entry_key,
            content=content,
            type=type,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            **kwargs,
        )

    return _factory


@pytest.fixture
def sample_entries(entry_factory):
    """Create a set of sample entries."""
    return [
        entry_factory(
            key=f"entry{i}",
            title=f"Title {i}",
            author=f"Author {i}",
            year=2020 + i,
            journal=f"Journal {i % 3}",
        )
        for i in range(10)
    ]
