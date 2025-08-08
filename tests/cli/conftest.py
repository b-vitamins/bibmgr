"""Pytest fixtures for CLI tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, List
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from bibmgr.core.models import Entry, EntryType


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_entry():
    """Create a sample bibliography entry."""
    return Entry(
        key="smith2020",
        type=EntryType.ARTICLE,
        title="Test Article",
        author="Smith, John and Doe, Jane",
        year=2020,
        journal="Test Journal",
        volume="10",
        pages="1-10",
        doi="10.1234/test",
        abstract="This is a test abstract.",
        keywords="test, sample",
    )


@pytest.fixture
def sample_entries():
    """Create a list of sample entries."""
    return [
        Entry(
            key="smith2020",
            type=EntryType.ARTICLE,
            title="Machine Learning Fundamentals",
            author="Smith, John and Doe, Jane",
            year=2020,
            journal="ML Journal",
            volume="10",
            pages="1-10",
            doi="10.1234/ml2020",
        ),
        Entry(
            key="jones2021",
            type=EntryType.INPROCEEDINGS,
            title="Deep Learning Applications",
            author="Jones, Alice and Brown, Bob",
            year=2021,
            booktitle="ICML 2021",
            pages="100-110",
            doi="10.1234/icml2021",
        ),
        Entry(
            key="wilson2019",
            type=EntryType.BOOK,
            title="Neural Networks: A Comprehensive Guide",
            author="Wilson, Carol",
            year=2019,
            publisher="Academic Press",
            isbn="978-0-12345-678-9",
        ),
        Entry(
            key="taylor2022",
            type=EntryType.ARTICLE,
            title="Attention Mechanisms in NLP",
            author="Taylor, David and Miller, Eve",
            year=2022,
            journal="NLP Quarterly",
            volume="15",
            number="3",
            pages="45-67",
        ),
        Entry(
            key="anderson2020",
            type=EntryType.PHDTHESIS,
            title="Reinforcement Learning in Robotics",
            author="Anderson, Frank",
            year=2020,
            school="MIT",
        ),
    ]


@pytest.fixture
def bibtex_content():
    """Sample BibTeX content for testing."""
    return """
@article{smith2020,
    title = {Machine Learning Fundamentals},
    author = {Smith, John and Doe, Jane},
    year = {2020},
    journal = {ML Journal},
    volume = {10},
    pages = {1-10},
    doi = {10.1234/ml2020}
}

@inproceedings{jones2021,
    title = {Deep Learning Applications},
    author = {Jones, Alice and Brown, Bob},
    year = {2021},
    booktitle = {ICML 2021},
    pages = {100-110}
}
"""


@pytest.fixture
def json_entries_file(temp_dir, sample_entries):
    """Create a JSON file with sample entries."""
    file_path = temp_dir / "entries.json"
    data = [
        {
            "key": e.key,
            "type": e.type.value,
            "title": e.title,
            "author": e.author,
            "year": e.year,
            "journal": getattr(e, "journal", None),
            "booktitle": getattr(e, "booktitle", None),
            "publisher": getattr(e, "publisher", None),
            "school": getattr(e, "school", None),
            "volume": getattr(e, "volume", None),
            "number": getattr(e, "number", None),
            "pages": getattr(e, "pages", None),
            "doi": getattr(e, "doi", None),
            "isbn": getattr(e, "isbn", None),
        }
        for e in sample_entries
    ]
    # Remove None values
    data = [{k: v for k, v in d.items() if v is not None} for d in data]

    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

    return file_path


@pytest.fixture
def bibtex_file(temp_dir, bibtex_content):
    """Create a BibTeX file for testing."""
    file_path = temp_dir / "bibliography.bib"
    file_path.write_text(bibtex_content)
    return file_path


@pytest.fixture
def mock_storage():
    """Create a mock storage backend."""
    storage = MagicMock()
    storage.get = MagicMock(return_value=None)
    storage.read = MagicMock(return_value=None)  # Add read method
    storage.read_all = MagicMock(return_value=[])  # Add read_all method
    storage.add = MagicMock(return_value=True)
    storage.update = MagicMock(return_value=True)
    storage.delete = MagicMock(return_value=True)
    storage.list = MagicMock(return_value=[])
    storage.search = MagicMock(return_value=[])
    storage.exists = MagicMock(return_value=False)
    return storage


@pytest.fixture
def mock_operations():
    """Create a mock operations handler."""
    from bibmgr.operations.crud import OperationResult, OperationType

    ops = MagicMock()

    # Create mock results
    success_result = OperationResult(
        success=True, operation=OperationType.CREATE, message="Success"
    )

    ops.add = MagicMock(return_value=success_result)
    ops.create = MagicMock(return_value=success_result)
    ops.update = MagicMock(
        return_value=OperationResult(
            success=True, operation=OperationType.UPDATE, message="Success"
        )
    )
    ops.delete = MagicMock(
        return_value=OperationResult(
            success=True, operation=OperationType.DELETE, message="Success"
        )
    )
    ops.bulk_add = MagicMock(return_value={"added": 0, "skipped": 0})
    ops.bulk_update = MagicMock(return_value={"updated": 0, "failed": 0})
    ops.bulk_delete = MagicMock(return_value={"deleted": 0, "failed": 0})
    return ops


@pytest.fixture
def mock_validator():
    """Create a mock validator."""
    validator = MagicMock()
    validator.validate = MagicMock(return_value={"valid": True, "errors": []})
    validator.validate_field = MagicMock(return_value=True)
    validator.check_required = MagicMock(return_value=[])
    validator.check_consistency = MagicMock(return_value=[])
    return validator


@pytest.fixture
def mock_importer():
    """Create a mock importer."""
    importer = MagicMock()
    importer.import_bibtex = MagicMock(return_value=[])
    importer.import_json = MagicMock(return_value=[])
    importer.import_ris = MagicMock(return_value=[])
    importer.detect_format = MagicMock(return_value="bibtex")
    return importer


@pytest.fixture
def mock_exporter():
    """Create a mock exporter."""
    exporter = MagicMock()
    exporter.export_bibtex = MagicMock(return_value="")
    exporter.export_json = MagicMock(return_value="")
    exporter.export_csv = MagicMock(return_value="")
    exporter.export_ris = MagicMock(return_value="")
    return exporter


@pytest.fixture
def mock_duplicate_detector():
    """Create a mock duplicate detector."""
    detector = MagicMock()
    detector.find_duplicates = MagicMock(return_value=[])
    detector.find_similar = MagicMock(return_value=[])
    detector.merge_entries = MagicMock(return_value=None)
    return detector


@pytest.fixture
def mock_collection_manager():
    """Create a mock collection manager."""
    manager = MagicMock()
    manager.create = MagicMock(return_value={"id": "1", "name": "Test"})
    manager.get = MagicMock(return_value=None)
    manager.list = MagicMock(return_value=[])
    manager.add_entries = MagicMock(return_value=0)
    manager.remove_entries = MagicMock(return_value=0)
    manager.delete = MagicMock(return_value=True)
    return manager


@pytest.fixture
def mock_tag_manager():
    """Create a mock tag manager."""
    manager = MagicMock()
    manager.add_tag = MagicMock(return_value=True)
    manager.remove_tag = MagicMock(return_value=True)
    manager.get_tags = MagicMock(return_value=[])
    manager.get_entries_with_tag = MagicMock(return_value=[])
    manager.suggest_tags = MagicMock(return_value=[])
    manager.rename_tag = MagicMock(return_value=True)
    return manager


@pytest.fixture
def mock_quality_engine():
    """Create a mock quality engine."""
    engine = MagicMock()
    engine.check_entry = MagicMock(return_value=[])
    engine.check_all = MagicMock(return_value={"errors": [], "warnings": []})
    engine.fix_issues = MagicMock(return_value=0)
    engine.generate_report = MagicMock(return_value="")
    return engine


@pytest.fixture
def mock_search_engine():
    """Create a mock search engine."""
    engine = MagicMock()
    engine.search = MagicMock(return_value={"hits": [], "total": 0})
    engine.index_entry = MagicMock(return_value=True)
    engine.index_entries = MagicMock(return_value=0)
    engine.clear_index = MagicMock(return_value=True)
    engine.get_stats = MagicMock(return_value={})
    return engine


@pytest.fixture
def isolated_cli_environment(monkeypatch, temp_dir):
    """Create an isolated environment for CLI testing."""
    # Set up temporary home directory
    home_dir = temp_dir / "home"
    home_dir.mkdir()

    config_dir = home_dir / ".config" / "bibmgr"
    config_dir.mkdir(parents=True)

    data_dir = home_dir / ".local" / "share" / "bibmgr"
    data_dir.mkdir(parents=True)

    cache_dir = home_dir / ".cache" / "bibmgr"
    cache_dir.mkdir(parents=True)

    # Set environment variables
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home_dir / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home_dir / ".local" / "share"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home_dir / ".cache"))

    # Create default config
    config_file = config_dir / "config.json"
    config = {
        "database": {
            "path": str(data_dir / "bibliography.db"),
            "backup": True,
        },
        "import": {
            "default_format": "bibtex",
            "merge_duplicates": False,
        },
        "export": {
            "default_format": "bibtex",
            "include_abstract": True,
        },
        "validation": {
            "strict": False,
            "auto_fix": False,
        },
    }

    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)

    return {
        "home": home_dir,
        "config_dir": config_dir,
        "data_dir": data_dir,
        "cache_dir": cache_dir,
        "config_file": config_file,
    }


@pytest.fixture
def cli_config():
    """Create a CLI configuration dictionary."""
    return {
        "verbose": False,
        "quiet": False,
        "no_color": True,
        "format": "table",
        "page_size": 20,
        "confirm": False,
        "dry_run": False,
    }


@pytest.fixture
def capture_output():
    """Capture and parse CLI output."""

    class OutputCapture:
        def __init__(self):
            self.lines = []
            self.tables = []
            self.json_data = None

        def parse(self, output: str):
            self.lines = output.strip().split("\n")

            # Try to parse as JSON
            try:
                self.json_data = json.loads(output)
            except (json.JSONDecodeError, ValueError):
                pass

            # Extract tables (simple heuristic)
            in_table = False
            current_table = []
            for line in self.lines:
                if "─" in line or "│" in line:
                    in_table = True
                    current_table.append(line)
                elif in_table and line.strip() == "":
                    if current_table:
                        self.tables.append(current_table)
                    current_table = []
                    in_table = False
                elif in_table:
                    current_table.append(line)

            if current_table:
                self.tables.append(current_table)

            return self

        def has_text(self, text: str) -> bool:
            return any(text in line for line in self.lines)

        def get_json(self) -> Any:
            return self.json_data

        def get_tables(self) -> List[List[str]]:
            return self.tables

    return OutputCapture()
