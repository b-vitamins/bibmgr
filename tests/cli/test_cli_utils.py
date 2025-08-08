"""Tests for CLI utilities and helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from bibmgr.core.models import Entry, EntryType


class TestCLIConfig:
    """Test CLI configuration handling."""

    def test_load_default_config(self, isolated_cli_environment):
        """Test loading default configuration."""
        from bibmgr.cli import Config

        config = Config()
        assert config.database_path
        assert config.import_format == "bibtex"
        assert config.export_format == "bibtex"

    def test_load_config_from_file(self, isolated_cli_environment):
        """Test loading configuration from file."""
        from bibmgr.cli import Config

        config_data = {
            "database": {"path": "/custom/path.db"},
            "import": {"default_format": "json"},
            "export": {"default_format": "csv"},
        }

        config_file = isolated_cli_environment["config_file"]
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        config = Config()
        assert "/custom/path.db" in str(config.database_path)
        assert config.import_format == "json"
        assert config.export_format == "csv"

    def test_config_from_env_vars(self, monkeypatch, isolated_cli_environment):
        """Test configuration from environment variables."""
        from bibmgr.cli import Config

        monkeypatch.setenv("BIBMGR_DATABASE", "/env/path.db")
        monkeypatch.setenv("BIBMGR_FORMAT", "json")

        config = Config()
        assert "/env/path.db" in str(config.database_path)

    def test_config_precedence(self, monkeypatch, isolated_cli_environment):
        """Test configuration precedence (env > file > default)."""
        from bibmgr.cli import Config

        # Set file config
        config_data = {"database": {"path": "/file/path.db"}}
        config_file = isolated_cli_environment["config_file"]
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        # Set env var (should override file)
        monkeypatch.setenv("BIBMGR_DATABASE", "/env/path.db")

        config = Config()
        assert "/env/path.db" in str(config.database_path)


class TestCLIFormatters:
    """Test output formatters."""

    def test_format_entry_table(self, sample_entry):
        """Test formatting entry as table."""
        from bibmgr.cli.formatters import format_entry_table

        output = format_entry_table(sample_entry)
        assert "smith2020" in output
        assert "Test Article" in output
        assert "Smith, John" in output
        assert "2020" in output

    def test_format_entry_bibtex(self, sample_entry):
        """Test formatting entry as BibTeX."""
        from bibmgr.cli.formatters import format_entry_bibtex

        output = format_entry_bibtex(sample_entry)
        assert "@article{smith2020" in output.lower()
        assert "title = {Test Article}" in output
        assert "author = {Smith, John and Doe, Jane}" in output
        assert "year = {2020}" in output

    def test_format_entry_json(self, sample_entry):
        """Test formatting entry as JSON."""
        from bibmgr.cli.formatters import format_entry_json

        output = format_entry_json(sample_entry)
        data = json.loads(output)
        assert data["key"] == "smith2020"
        assert data["type"] == "article"
        assert data["title"] == "Test Article"

    def test_format_entry_yaml(self, sample_entry):
        """Test formatting entry as YAML."""
        from bibmgr.cli.formatters import format_entry_yaml

        output = format_entry_yaml(sample_entry)
        assert "key: smith2020" in output
        assert "type: article" in output
        assert "title: Test Article" in output

    def test_format_entries_list(self, sample_entries):
        """Test formatting multiple entries as list."""
        from bibmgr.cli.formatters import format_entries_list

        output = format_entries_list(sample_entries, format="compact")
        for entry in sample_entries:
            assert entry.key in output

    def test_format_stats_table(self):
        """Test formatting statistics as table."""
        from bibmgr.cli.formatters import format_stats_table

        stats = {
            "total": 100,
            "by_type": {"article": 60, "book": 30, "misc": 10},
            "by_year": {2020: 20, 2021: 30, 2022: 50},
        }

        output = format_stats_table(stats)
        assert "100" in output
        assert "article" in output
        assert "60" in output


class TestCLIValidators:
    """Test input validators."""

    def test_validate_entry_key(self):
        """Test entry key validation."""
        from bibmgr.cli.validators import validate_entry_key

        assert validate_entry_key("valid2023")
        assert validate_entry_key("smith-2023")
        assert validate_entry_key("author_et_al_2023")

        with pytest.raises(ValueError):
            validate_entry_key("")

        with pytest.raises(ValueError):
            validate_entry_key("invalid key")  # Space not allowed

        with pytest.raises(ValueError):
            validate_entry_key("@invalid")  # Special char not allowed

    def test_validate_entry_type(self):
        """Test entry type validation."""
        from bibmgr.cli.validators import validate_entry_type

        assert validate_entry_type("article") == EntryType.ARTICLE
        assert validate_entry_type("BOOK") == EntryType.BOOK
        assert validate_entry_type("InProceedings") == EntryType.INPROCEEDINGS

        with pytest.raises(ValueError):
            validate_entry_type("invalid_type")

    def test_validate_year(self):
        """Test year validation."""
        from bibmgr.cli.validators import validate_year

        assert validate_year("2023") == 2023
        assert validate_year(2023) == 2023

        with pytest.raises(ValueError):
            validate_year("invalid")

        with pytest.raises(ValueError):
            validate_year(1500)  # Too old

        with pytest.raises(ValueError):
            validate_year(3000)  # Future

    def test_validate_file_path(self, temp_dir):
        """Test file path validation."""
        from bibmgr.cli.validators import validate_file_path

        existing_file = temp_dir / "exists.txt"
        existing_file.write_text("content")

        assert validate_file_path(str(existing_file), must_exist=True)
        assert validate_file_path("/new/file.txt", must_exist=False)

        with pytest.raises(ValueError):
            validate_file_path("/nonexistent.txt", must_exist=True)

    def test_validate_format(self):
        """Test format validation."""
        from bibmgr.cli.validators import validate_format

        assert validate_format("bibtex", ["bibtex", "json"]) == "bibtex"
        assert validate_format("JSON", ["bibtex", "json"]) == "json"

        with pytest.raises(ValueError):
            validate_format("invalid", ["bibtex", "json"])


class TestCLIHelpers:
    """Test CLI helper functions."""

    def test_parse_field_assignments(self):
        """Test parsing field assignments."""
        from bibmgr.cli.helpers import parse_field_assignments

        fields = [
            "title=New Title",
            "year=2023",
            "author=Smith, J.",
        ]

        result = parse_field_assignments(fields)
        assert result["title"] == "New Title"
        assert result["year"] == "2023"
        assert result["author"] == "Smith, J."

        # Test with equals in value
        fields = ["abstract=This = that"]
        result = parse_field_assignments(fields)
        assert result["abstract"] == "This = that"

    def test_parse_filter_query(self):
        """Test parsing filter queries."""
        from bibmgr.cli.helpers import parse_filter_query

        query = "type:article year:2020..2023 author:Smith"
        filters = parse_filter_query(query)

        assert filters["type"] == "article"
        assert filters["year"] == range(2020, 2024)
        assert filters["author"] == "Smith"

        # Test with quoted values
        query = 'title:"machine learning" tag:important'
        filters = parse_filter_query(query)
        assert filters["title"] == "machine learning"
        assert filters["tag"] == "important"

    def test_confirm_action(self, cli_runner):
        """Test action confirmation."""
        from bibmgr.cli.helpers import confirm_action

        # Test yes
        with patch("click.confirm", return_value=True):
            assert confirm_action("Delete?") is True

        # Test no
        with patch("click.confirm", return_value=False):
            assert confirm_action("Delete?") is False

        # Test force mode
        assert confirm_action("Delete?", force=True) is True

    def test_handle_error(self, capsys):
        """Test error handling."""
        from bibmgr.cli.helpers import handle_error

        # Test with exit
        with pytest.raises(SystemExit):
            handle_error("Critical error", exit_code=1)

        captured = capsys.readouterr()
        assert "Critical error" in captured.err

        # Test without exit
        handle_error("Warning", exit_code=None)
        captured = capsys.readouterr()
        assert "Warning" in captured.err

    def test_load_entries_from_file(self, temp_dir):
        """Test loading entries from various formats."""
        from bibmgr.cli.helpers import load_entries_from_file

        # JSON format
        json_file = temp_dir / "entries.json"
        json_data = [
            {"key": "test1", "type": "article", "title": "Test 1"},
            {"key": "test2", "type": "book", "title": "Test 2"},
        ]
        with open(json_file, "w") as f:
            json.dump(json_data, f)

        entries = load_entries_from_file(json_file, format="json")
        assert len(entries) == 2
        assert entries[0].key == "test1"

        # BibTeX format
        bib_file = temp_dir / "entries.bib"
        bib_content = """
        @article{test3,
            title = {Test 3},
            author = {Author},
            year = {2023}
        }
        """
        bib_file.write_text(bib_content)

        with patch("bibmgr.cli.helpers.BibtexParser") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser.parse.return_value = [
                Entry(key="test3", type=EntryType.ARTICLE, title="Test 3")
            ]
            mock_parser_class.return_value = mock_parser
            entries = load_entries_from_file(bib_file, format="bibtex")
            assert len(entries) == 1
            assert entries[0].key == "test3"

    def test_save_entries_to_file(self, temp_dir, sample_entries):
        """Test saving entries to various formats."""
        from bibmgr.cli.helpers import save_entries_to_file

        # JSON format
        json_file = temp_dir / "output.json"
        save_entries_to_file(sample_entries, json_file, format="json")
        assert json_file.exists()

        with open(json_file) as f:
            data = json.load(f)
            assert len(data) == len(sample_entries)

        # BibTeX format
        bib_file = temp_dir / "output.bib"
        save_entries_to_file(sample_entries, bib_file, format="bibtex")
        assert bib_file.exists()
        content = bib_file.read_text()
        assert "@article" in content.lower()

    def test_filter_entries(self, sample_entries):
        """Test filtering entries."""
        from bibmgr.cli.helpers import filter_entries

        # Filter by type
        filtered = filter_entries(sample_entries, type="article")
        assert all(e.type == EntryType.ARTICLE for e in filtered)

        # Filter by year
        filtered = filter_entries(sample_entries, year=2020)
        assert all(e.year == 2020 for e in filtered)

        # Filter by author
        filtered = filter_entries(sample_entries, author="Smith")
        assert all("Smith" in e.author for e in filtered if e.author)

        # Multiple filters
        filtered = filter_entries(
            sample_entries,
            type="article",
            year=2020,
        )
        assert all(e.type == EntryType.ARTICLE and e.year == 2020 for e in filtered)

    def test_sort_entries(self, sample_entries):
        """Test sorting entries."""
        from bibmgr.cli.helpers import sort_entries

        # Sort by year
        sorted_entries = sort_entries(sample_entries, by="year")
        years = [e.year for e in sorted_entries if e.year is not None]
        assert years == sorted(years)

        # Sort by title
        sorted_entries = sort_entries(sample_entries, by="title")
        titles = [e.title for e in sorted_entries if e.title is not None]
        assert titles == sorted(titles)

        # Sort by key (default)
        sorted_entries = sort_entries(sample_entries, by="key")
        keys = [e.key for e in sorted_entries]
        assert keys == sorted(keys)

        # Reverse sort
        sorted_entries = sort_entries(sample_entries, by="year", reverse=True)
        years = [e.year for e in sorted_entries if e.year is not None]
        assert years == sorted(years, reverse=True)


class TestCLIProgress:
    """Test progress indicators."""

    def test_progress_bar(self):
        """Test progress bar display."""
        from bibmgr.cli.progress import ProgressBar

        with patch("bibmgr.cli.progress.Progress") as mock_progress:
            with ProgressBar(total=100, description="Processing") as bar:
                bar.update(50)
                bar.complete()

            assert mock_progress.called

    def test_spinner(self):
        """Test spinner display."""
        from bibmgr.cli.progress import Spinner

        with patch("bibmgr.cli.progress.Console") as mock_console:
            mock_status = MagicMock()
            mock_console.return_value.status.return_value = mock_status

            with Spinner("Loading..."):
                pass

            assert mock_console.return_value.status.called

    def test_batch_progress(self):
        """Test batch operation progress."""
        from bibmgr.cli.progress import BatchProgress

        items = list(range(10))
        processed = []

        with patch("bibmgr.cli.progress.Progress"):
            with BatchProgress(items, description="Processing") as progress:
                for item in progress:
                    processed.append(item)

        assert processed == items


class TestCLIOutput:
    """Test output handling."""

    def test_print_success(self, capsys):
        """Test success message."""
        from bibmgr.cli.output import print_success

        print_success("Operation completed")
        captured = capsys.readouterr()
        assert "Operation completed" in captured.out

    def test_print_error(self, capsys):
        """Test error message."""
        from bibmgr.cli.output import print_error

        print_error("Operation failed")
        captured = capsys.readouterr()
        assert "Operation failed" in captured.err or "Operation failed" in captured.out

    def test_print_warning(self, capsys):
        """Test warning message."""
        from bibmgr.cli.output import print_warning

        print_warning("Potential issue")
        captured = capsys.readouterr()
        assert "Potential issue" in captured.out

    def test_print_table(self, capsys, sample_entries):
        """Test table output."""
        from bibmgr.cli.output import print_table

        headers = ["Key", "Title", "Year"]
        rows = [[e.key, e.title[:30], str(e.year)] for e in sample_entries]

        print_table(headers, rows)
        captured = capsys.readouterr()

        assert "Key" in captured.out
        assert "Title" in captured.out
        for entry in sample_entries:
            assert entry.key in captured.out

    def test_print_json(self, capsys):
        """Test JSON output."""
        from bibmgr.cli.output import print_json

        data = {"key": "value", "number": 42}
        print_json(data)

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == data
