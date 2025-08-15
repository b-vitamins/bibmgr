"""Pytest configuration and fixtures for CLI tests.

This module provides comprehensive fixtures for testing the CLI module,
including isolated file systems, mock repositories, and CLI runners.
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner
from rich.console import Console

from bibmgr.core.models import Collection, Entry, EntryType
from bibmgr.operations.results import OperationResult, ResultStatus
from bibmgr.search.results import SearchResultCollection
from bibmgr.storage.backends.memory import MemoryBackend
from bibmgr.storage.events import EventBus
from bibmgr.storage.metadata import EntryMetadata, MetadataStore, Note
from bibmgr.storage.repository import (
    CollectionRepository,
    EntryRepository,
    RepositoryManager,
)


# Test data fixtures
@pytest.fixture
def sample_bibtex():
    """Sample BibTeX content for testing."""
    return """
@article{doe2024,
    title = {Quantum Computing Advances},
    author = {Doe, John and Smith, Jane},
    journal = {Nature Quantum},
    year = {2024},
    volume = {12},
    pages = {1--10},
    doi = {10.1038/s41567-024-0001},
    abstract = {Recent advances in quantum computing...}
}

@inproceedings{smith2023,
    title = {Machine Learning for Climate},
    author = {Smith, Jane},
    booktitle = {NeurIPS 2023},
    year = {2023},
    pages = {100--110}
}
"""


@pytest.fixture
def sample_entries():
    """Sample entries for testing."""
    return [
        Entry(
            key="doe2024",
            type=EntryType.ARTICLE,
            title="Quantum Computing Advances",
            author="Doe, John and Smith, Jane",
            journal="Nature Quantum",
            year=2024,
            volume="12",
            pages="1--10",
            doi="10.1038/s41567-024-0001",
            abstract="Recent advances in quantum computing...",
        ),
        Entry(
            key="smith2023",
            type=EntryType.INPROCEEDINGS,
            title="Machine Learning for Climate",
            author="Smith, Jane",
            booktitle="NeurIPS 2023",
            year=2023,
            pages="100--110",
        ),
        Entry(
            key="jones2022",
            type=EntryType.BOOK,
            title="Advanced Algorithms",
            author="Jones, Alice",
            publisher="MIT Press",
            year=2022,
        ),
    ]


@pytest.fixture
def sample_collections():
    """Sample collections for testing."""
    return [
        Collection(
            id="phd-research",  # type: ignore
            name="PhD Research",
            description="Core papers for dissertation",
            entry_keys=("doe2024", "smith2023"),
        ),
        Collection(
            id="to-read",  # type: ignore
            name="To Read",
            description="Papers to read",
            query='read_status:"unread"',
        ),
    ]


# CLI runner fixtures
@pytest.fixture
def cli_runner():
    """Click CLI test runner with custom invoke method."""

    class BibmgrCliRunner(CliRunner):
        def invoke(self, args, **kwargs):  # type: ignore
            """Custom invoke that handles our CLI structure."""
            from unittest.mock import patch

            from bibmgr.cli.main import cli

            # Mock the storage path to use a temporary directory to avoid initialization issues
            with patch(
                "bibmgr.cli.main.get_storage_path",
                return_value=Path("/tmp/test_bibmgr"),
            ):
                # If args is a list (our test format), pass it directly
                if isinstance(args, list):
                    return super().invoke(cli, args, **kwargs)
                else:
                    # Otherwise pass through normally
                    return super().invoke(args, **kwargs)

    return BibmgrCliRunner()


@pytest.fixture
def isolated_cli_runner(tmp_path):
    """CLI runner with isolated filesystem and storage."""
    from unittest.mock import patch

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create isolated storage directory within the test filesystem
        storage_path = tmp_path / "bibmgr_storage"

        # Mock storage path to use our isolated directory (but allow backend initialization)
        with patch("bibmgr.cli.main.get_storage_path", return_value=storage_path):
            yield runner


# Console fixtures
@pytest.fixture
def test_console():
    """Rich console for capturing output."""
    return Console(
        force_terminal=True,
        width=120,
        height=40,
        legacy_windows=False,
        _environ={"TERM": "xterm-256color"},
    )


@pytest.fixture
def capture_console(test_console):
    """Capture console output for assertions."""
    from io import StringIO

    string_io = StringIO()
    test_console.file = string_io

    def get_output():
        return string_io.getvalue()

    test_console.get_output = get_output
    return test_console


# Repository fixtures
@pytest.fixture
def memory_backend():
    """In-memory storage backend."""
    return MemoryBackend()


@pytest.fixture
def entry_repository(memory_backend):
    """Entry repository with memory backend."""
    return EntryRepository(memory_backend)


@pytest.fixture
def collection_repository(memory_backend):
    """Collection repository with memory backend."""
    return CollectionRepository(memory_backend)


@pytest.fixture
def repository_manager(memory_backend):
    """Repository manager with memory backend."""
    return RepositoryManager(memory_backend)


@pytest.fixture
def populated_repository(entry_repository, sample_entries):
    """Repository populated with sample entries."""
    for entry in sample_entries:
        entry_repository.save(entry)
    return entry_repository


# Event system fixtures
@pytest.fixture
def event_bus():
    """Event bus for testing."""
    return EventBus()


# Metadata fixtures
@pytest.fixture
def metadata_store(tmp_path):
    """Metadata store for testing."""
    return MetadataStore(tmp_path / "metadata")


@pytest.fixture
def sample_metadata():
    """Sample metadata for testing."""
    return EntryMetadata(
        entry_key="doe2024",
        tags={"quantum", "computing", "important"},
        rating=5,
        read_status="read",
        read_date=datetime(2024, 1, 15),
        importance="high",
        notes_count=2,
    )


@pytest.fixture
def sample_notes():
    """Sample notes for testing."""
    return [
        Note(
            entry_key="doe2024",
            content="Key breakthrough in error correction",
            note_type="general",
            tags=["important", "breakthrough"],
        ),
        Note(
            entry_key="doe2024",
            content="Quantum supremacy is not just about speed",
            note_type="quote",
            page=5,
            tags=["quote"],
        ),
    ]


# Search fixtures
@pytest.fixture
def mock_search_engine():
    """Mock search engine for testing."""
    from bibmgr.search.engine import SearchEngine

    engine = Mock(spec=SearchEngine)

    # Default search behavior
    def mock_search(query, **kwargs):
        from bibmgr.search.results import SearchMatch

        # Simple mock: return entries that contain the query
        if query == "quantum":
            matches = [
                SearchMatch(
                    entry_key="doe2024",
                    score=0.95,
                    highlights={"title": ["<mark>Quantum</mark> Computing Advances"]},
                )
            ]
        elif query == "machine learning":
            matches = [
                SearchMatch(
                    entry_key="smith2023",
                    score=0.90,
                    highlights={"title": ["<mark>Machine Learning</mark> for Climate"]},
                )
            ]
        else:
            matches = []

        return SearchResultCollection(
            query=query,
            matches=matches,
            total=len(matches),
            facets=[],  # type: ignore[arg-type]
            suggestions=[],
            statistics=None,  # type: ignore[arg-type]
        )

    engine.search.side_effect = mock_search
    return engine


# Operation mocks
@pytest.fixture
def mock_create_handler():
    """Mock create handler for testing."""
    handler = Mock()

    def mock_execute(command):
        # Success by default
        return OperationResult(
            status=ResultStatus.SUCCESS,
            message=f"Entry '{command.entry.key}' created successfully",
            entity_id=command.entry.key,
        )

    handler.execute.side_effect = mock_execute
    return handler


@pytest.fixture
def mock_update_handler():
    """Mock update handler for testing."""
    handler = Mock()

    def mock_execute(command):
        return OperationResult(
            status=ResultStatus.SUCCESS,
            message=f"Entry '{command.key}' updated successfully",
            entity_id=command.key,
        )

    handler.execute.side_effect = mock_execute
    return handler


@pytest.fixture
def mock_delete_handler():
    """Mock delete handler for testing."""
    handler = Mock()

    def mock_execute(command):
        return OperationResult(
            status=ResultStatus.SUCCESS,
            message=f"Entry '{command.key}' deleted successfully",
            entity_id=command.key,
        )

    handler.execute.side_effect = mock_execute
    return handler


# Import/Export fixtures
@pytest.fixture
def temp_bibtex_file(tmp_path, sample_bibtex):
    """Temporary BibTeX file for testing."""
    file_path = tmp_path / "test.bib"
    file_path.write_text(sample_bibtex)
    return file_path


@pytest.fixture
def temp_json_file(tmp_path, sample_entries):
    """Temporary JSON file for testing."""
    file_path = tmp_path / "test.json"
    data = {"entries": [entry.to_dict() for entry in sample_entries]}
    file_path.write_text(json.dumps(data, indent=2))
    return file_path


# Configuration fixtures
@pytest.fixture
def test_config():
    """Test configuration."""
    return {
        "storage": {
            "backend": "memory",
            "path": "~/.local/share/bibmgr",
        },
        "search": {
            "backend": "memory",
            "expand_queries": True,
            "enable_highlighting": True,
        },
        "display": {
            "theme": "professional",
            "console_width": 120,
            "use_pager": "never",
        },
        "editor": {
            "command": "vim",
        },
        "defaults": {
            "entry_type": "article",
            "validate_on_import": True,
            "export_format": "bibtex",
        },
    }


@pytest.fixture
def mock_config_file(tmp_path, test_config):
    """Mock configuration file."""
    import yaml

    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(test_config))
    return config_file


# Context fixtures
@pytest.fixture
def cli_context(
    entry_repository, collection_repository, mock_search_engine, test_console
):
    """CLI context for testing."""
    from unittest.mock import Mock

    from bibmgr.cli.main import Context
    from bibmgr.storage.events import EventBus
    from bibmgr.storage.metadata import MetadataStore
    from bibmgr.storage.repository import RepositoryManager

    # Create mock objects for required parameters
    repository_manager = Mock(spec=RepositoryManager)
    metadata_store = Mock(spec=MetadataStore)
    event_bus = Mock(spec=EventBus)

    context = Context(
        repository_manager=repository_manager,
        repository=entry_repository,
        collection_repository=collection_repository,
        search_service=mock_search_engine,
        metadata_store=metadata_store,
        console=test_console,
        event_bus=event_bus,
    )
    return context


# Patching fixtures
@pytest.fixture
def mock_get_repository(entry_repository):
    """Mock get_repository function."""
    with patch("bibmgr.cli.commands.entry.get_repository") as mock:
        mock.return_value = entry_repository
        yield mock


@pytest.fixture
def mock_get_search_service(mock_search_engine):
    """Mock get_search_service function."""
    with patch("bibmgr.cli.commands.search.get_search_service") as mock:
        mock.return_value = mock_search_engine
        yield mock


@pytest.fixture
def mock_editor():
    """Mock external editor."""
    with patch("bibmgr.cli.utils.editor.open_in_editor") as mock:

        def mock_edit(content):
            # Simulate editing by adding a comment
            return content + "\n% Edited"

        mock.side_effect = mock_edit
        yield mock


# Validation helpers
def assert_exit_success(result):
    """Assert CLI command exited successfully."""
    assert result.exit_code == 0, f"Command failed: {result.output}"


def assert_exit_failure(result, expected_code=1):
    """Assert CLI command failed with expected code."""
    assert result.exit_code == expected_code, (
        f"Expected exit code {expected_code}, got {result.exit_code}: {result.output}"
    )


def assert_output_contains(result, *expected):
    """Assert CLI output contains expected strings."""
    for text in expected:
        assert text in result.output, f"Expected '{text}' in output:\n{result.output}"


def assert_output_not_contains(result, *unexpected):
    """Assert CLI output does not contain strings."""
    for text in unexpected:
        assert text not in result.output, (
            f"Unexpected '{text}' in output:\n{result.output}"
        )


# Export test helpers
pytest.assert_exit_success = assert_exit_success  # type: ignore[attr-defined]
pytest.assert_exit_failure = assert_exit_failure  # type: ignore[attr-defined]
pytest.assert_output_contains = assert_output_contains  # type: ignore[attr-defined]
pytest.assert_output_not_contains = assert_output_not_contains  # type: ignore[attr-defined]
