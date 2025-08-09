"""Tests for import/export functionality.

This module tests the importers and exporters that handle various
bibliography formats (BibTeX, JSON, RIS, etc.) using the core module's
parsing capabilities.
"""

import json
from pathlib import Path
from unittest.mock import patch

from bibmgr.core.models import Entry, EntryType


class TestBibtexImporter:
    """Test BibTeX import functionality."""

    def test_import_valid_bibtex(self, bibtex_content):
        """Valid BibTeX entries are imported correctly."""
        from bibmgr.storage.importers import BibtexImporter

        importer = BibtexImporter(validate=False)
        entries, errors = importer.import_text(bibtex_content)

        assert len(entries) == 3
        assert len(errors) == 0

        knuth = next(e for e in entries if e.key == "knuth1984")
        assert knuth.type == EntryType.BOOK
        assert knuth.author == "Donald E. Knuth"
        assert knuth.title == "The {TeX}book"  # Braces preserved
        assert knuth.year == 1984

        turing = next(e for e in entries if e.key == "turing1950")
        assert turing.type == EntryType.ARTICLE
        assert turing.journal == "Mind"
        assert turing.doi == "10.1093/mind/LIX.236.433"

    def test_import_with_validation(self, bibtex_content):
        """Import with validation filters invalid entries."""
        from bibmgr.storage.importers import BibtexImporter

        importer = BibtexImporter(validate=True)
        entries, errors = importer.import_text(bibtex_content)

        assert len(entries) == 3
        assert len(errors) == 0

    def test_import_invalid_bibtex(self, invalid_bibtex):
        """Invalid BibTeX entries produce errors."""
        from bibmgr.storage.importers import BibtexImporter

        importer = BibtexImporter(validate=True)
        entries, errors = importer.import_text(invalid_bibtex)

        assert len(entries) < 3  # Not all entries imported
        assert len(errors) > 0

        error_text = "\n".join(errors)
        assert "missing_fields" in error_text
        assert "required" in error_text.lower()

    def test_import_from_file(self, temp_dir, bibtex_content):
        """Import from BibTeX file works correctly."""
        from bibmgr.storage.importers import BibtexImporter

        bib_file = temp_dir / "test.bib"
        bib_file.write_text(bibtex_content)

        importer = BibtexImporter()
        entries, errors = importer.import_file(bib_file)

        assert len(entries) == 3
        assert len(errors) == 0

    def test_import_nonexistent_file(self, temp_dir):
        """Import from non-existent file produces error."""
        from bibmgr.storage.importers import BibtexImporter

        importer = BibtexImporter()
        entries, errors = importer.import_file(temp_dir / "nonexistent.bib")

        assert len(entries) == 0
        assert len(errors) == 1
        assert "Failed to read file" in errors[0]

    def test_import_batch(self, temp_dir, bibtex_content):
        """Batch import from multiple files."""
        from bibmgr.storage.importers import BibtexImporter

        file1 = temp_dir / "file1.bib"
        file2 = temp_dir / "file2.bib"

        file1.write_text(
            "@article{test1, title={Test 1}, author={Author 1}, journal={Journal 1}, year=2020}"
        )
        file2.write_text(
            "@book{test2, title={Test 2}, author={Author 2}, publisher={Publisher 2}, year=2021}"
        )

        importer = BibtexImporter()
        entries, errors = importer.import_batch([file1, file2])

        assert len(entries) == 2
        assert len(errors) == 0
        assert {e.key for e in entries} == {"test1", "test2"}

    def test_import_handles_special_characters(self):
        """Import correctly handles BibTeX special characters."""
        from bibmgr.storage.importers import BibtexImporter

        bibtex = r"""
        @article{special2024,
            author = {Smith, A. and M\"uller, B.},
            title = {100\% Success with \LaTeX{}},
            journal = {IEEE Computer \& Society},
            year = 2024
        }
        """

        importer = BibtexImporter(validate=False)
        entries, errors = importer.import_text(bibtex)

        assert len(entries) == 1
        assert len(errors) == 0

        entry = entries[0]
        assert (
            entry.author and 'M\\"uller' in entry.author
        )  # \" is NOT converted by decoder
        assert entry.title and "100% Success" in entry.title  # \% converted to %
        assert entry.title and "\\LaTeX{}" in entry.title  # LaTeX commands preserved
        assert (
            entry.journal and "Computer & Society" in entry.journal
        )  # \& converted to &

    def test_import_error_reporting(self):
        """Import provides detailed error information."""
        from bibmgr.storage.importers import BibtexImporter

        bibtex = """
        @article{valid, title={Valid}, author={A}, journal={J}, year=2020}

        @article{invalid1, title={Only Title}}

        @book{invalid2, author={Author}, title={Title}, year={not a number}}
        """

        importer = BibtexImporter(validate=True)
        entries, errors = importer.import_text(bibtex)

        assert len(entries) == 1
        assert entries[0].key == "valid"

        assert len(errors) >= 2
        assert any("invalid1" in e for e in errors)
        assert any("invalid2" in e for e in errors)


class TestJsonImporter:
    """Test JSON import/export functionality."""

    def test_import_json_array(self):
        """Import from JSON array format."""
        from bibmgr.storage.importers import JsonImporter

        json_data = [
            {
                "key": "entry1",
                "type": "article",
                "title": "First Article",
                "author": "Author One",
                "journal": "Journal One",
                "year": 2020,
            },
            {
                "key": "entry2",
                "type": "book",
                "title": "First Book",
                "author": "Author Two",
                "publisher": "Publisher",
                "year": 2021,
            },
        ]

        importer = JsonImporter(validate=False)
        entries, errors = importer._import_entries(json_data)

        assert len(entries) == 2
        assert len(errors) == 0
        assert entries[0].key == "entry1"
        assert entries[1].key == "entry2"

    def test_import_json_object_format(self, json_export_data):
        """Import from JSON object with metadata."""
        from bibmgr.storage.importers import JsonImporter

        importer = JsonImporter(validate=False)

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(json_export_data)
            )

            entries, errors = importer.import_file(Path("test.json"))

        assert len(entries) == 2
        assert len(errors) == 0

    def test_import_validates_entries(self):
        """JSON import validates entries when requested."""
        from bibmgr.storage.importers import JsonImporter

        json_data = [
            {
                "key": "valid",
                "type": "article",
                "title": "Valid Article",
                "author": "Author",
                "journal": "Journal",
                "year": 2020,
            },
            {
                "key": "invalid",
                "type": "article",
                "title": "Missing Required Fields",
            },
        ]

        importer = JsonImporter(validate=True)
        entries, errors = importer._import_entries(json_data)

        assert len(entries) == 1
        assert entries[0].key == "valid"
        assert len(errors) == 1
        assert "invalid" in errors[0]

    def test_import_handles_missing_key(self):
        """Import handles entries without keys."""
        from bibmgr.storage.importers import JsonImporter

        json_data = [
            {
                "type": "misc",
                "title": "No Key Entry",
            }
        ]

        importer = JsonImporter()
        entries, errors = importer._import_entries(json_data)

        assert len(entries) == 0
        assert len(errors) == 1
        assert "missing 'key'" in errors[0]

    def test_import_defaults_type_to_misc(self):
        """Import defaults missing type to misc."""
        from bibmgr.storage.importers import JsonImporter

        json_data = [
            {
                "key": "test",
                "title": "No Type Entry",
            }
        ]

        importer = JsonImporter(validate=False)
        entries, errors = importer._import_entries(json_data)

        assert len(entries) == 1
        assert entries[0].type == EntryType.MISC

    def test_import_invalid_type(self):
        """Import handles invalid entry types."""
        from bibmgr.storage.importers import JsonImporter

        json_data = [
            {
                "key": "test",
                "type": "invalid_type",
                "title": "Invalid Type",
            }
        ]

        importer = JsonImporter()
        entries, errors = importer._import_entries(json_data)

        assert len(entries) == 0
        assert len(errors) == 1
        assert "invalid type" in errors[0]

    def test_export_entries_to_json(self, sample_entries, temp_dir):
        """Export entries to JSON format."""
        from bibmgr.storage.importers import JsonImporter

        output_file = temp_dir / "export.json"

        importer = JsonImporter()
        importer.export_entries(sample_entries, output_file)

        with open(output_file) as f:
            data = json.load(f)

        assert data["version"] == "1.0"
        assert len(data["entries"]) == len(sample_entries)

        first = data["entries"][0]
        assert first["key"] == sample_entries[0].key
        assert first["type"] == sample_entries[0].type.value

    def test_json_preserves_all_fields(self, entry_with_all_fields, temp_dir):
        """JSON export preserves all entry fields."""
        from bibmgr.storage.importers import JsonImporter

        output_file = temp_dir / "complete.json"

        importer = JsonImporter()
        importer.export_entries([entry_with_all_fields], output_file)

        imported, errors = importer.import_file(output_file)

        assert len(imported) == 1
        assert len(errors) == 0

        original = entry_with_all_fields
        imported_entry = imported[0]

        assert imported_entry.key == original.key
        assert imported_entry.title == original.title
        assert imported_entry.abstract == original.abstract
        assert imported_entry.doi == original.doi
        assert imported_entry.keywords == original.keywords

    def test_json_handles_datetime_serialization(self):
        """JSON export handles datetime fields."""
        from datetime import datetime

        from bibmgr.storage.importers import JsonImporter

        entry = Entry(
            key="test",
            type=EntryType.MISC,
            title="Test",
            added=datetime.now(),
            modified=datetime.now(),
        )

        JsonImporter()

        entry_dict = entry.to_dict()
        json_str = json.dumps({"entries": [entry_dict]}, default=str)

        data = json.loads(json_str)
        assert data["entries"][0]["added"] is not None


class TestRisImporter:
    """Test RIS format import functionality."""

    def test_import_basic_ris(self):
        """Import basic RIS format entries."""
        from bibmgr.storage.importers import RisImporter

        ris_content = """TY  - JOUR
AU  - Smith, John
AU  - Doe, Jane
TI  - A Test Article
JO  - Test Journal
PY  - 2020
VL  - 42
IS  - 3
SP  - 123
EP  - 145
DO  - 10.1234/test.2020.1
ER  -

TY  - BOOK
AU  - Johnson, Bob
TI  - Test Book
PB  - Test Publisher
PY  - 2021
ER  -
"""

        importer = RisImporter()
        entries, errors = importer.import_text(ris_content)

        assert len(entries) == 2
        assert len(errors) == 0

        article = entries[0]
        assert article.type == EntryType.ARTICLE
        assert (
            article.author == "Smith, John and Doe, Jane"
        )  # RIS format is Last, First
        assert article.title == "A Test Article"
        assert article.journal == "Test Journal"
        assert article.year == 2020
        assert article.volume == "42"
        assert article.pages == "123--145"
        assert article.doi == "10.1234/test.2020.1"

        book = entries[1]
        assert book.type == EntryType.BOOK
        assert book.author == "Johnson, Bob"  # RIS format is Last, First
        assert book.publisher == "Test Publisher"

    def test_ris_type_mapping(self):
        """RIS types map correctly to BibTeX types."""
        from bibmgr.storage.importers import RisImporter

        type_tests = [
            ("JOUR", EntryType.ARTICLE),
            ("BOOK", EntryType.BOOK),
            ("CHAP", EntryType.INBOOK),
            ("CONF", EntryType.INPROCEEDINGS),
            ("THES", EntryType.PHDTHESIS),
            ("RPRT", EntryType.TECHREPORT),
            ("UNPB", EntryType.UNPUBLISHED),
            ("GEN", EntryType.MISC),
        ]

        for ris_type, expected_type in type_tests:
            ris = f"""TY  - {ris_type}
TI  - Test Entry
ER  -
"""
            importer = RisImporter(validate=False)
            entries, errors = importer.import_text(ris)

            assert len(entries) == 1
            assert entries[0].type == expected_type

    def test_ris_multiline_fields(self):
        """RIS handles multi-line fields correctly."""
        from bibmgr.storage.importers import RisImporter

        ris_content = """TY  - JOUR
AU  - Author One
AU  - Author Two
AU  - Author Three
TI  - This is a very long title that might
      span multiple lines in the RIS file
AB  - This is an abstract with multiple paragraphs.

      Second paragraph here.
      Third line of the abstract.
ER  -
"""

        importer = RisImporter(validate=False)
        entries, errors = importer.import_text(ris_content)

        assert len(entries) == 1
        entry = entries[0]

        assert entry.author == "Author One and Author Two and Author Three"

        assert entry.title and "very long title" in entry.title
        assert entry.title and "multiple lines" in entry.title

        assert entry.abstract and "multiple paragraphs" in entry.abstract
        assert entry.abstract and "Second paragraph" in entry.abstract

    def test_ris_error_handling(self):
        """RIS importer handles malformed entries."""
        from bibmgr.storage.importers import RisImporter

        ris_content = """TY  - JOUR
TI  - Missing End Record

TY  - BOOK
AU  - Valid Author
TI  - Valid Title
ER  -

Invalid line without tag
TY  -
TI  - No type specified
ER  -
"""

        importer = RisImporter(validate=False)
        entries, errors = importer.import_text(ris_content)

        assert len(entries) >= 1
        assert any(e.title == "Valid Title" for e in entries)

        assert len(errors) > 0


class TestImportExportRoundTrip:
    """Test that import/export preserves data."""

    def test_bibtex_round_trip(self, sample_entries, temp_dir):
        """BibTeX export/import preserves entry data."""
        from bibmgr.storage.importers import BibtexImporter

        importer = BibtexImporter(validate=False)
        output_file = temp_dir / "roundtrip.bib"
        importer.export_entries(sample_entries, output_file)

        importer = BibtexImporter(validate=False)
        imported, errors = importer.import_file(output_file)

        assert len(imported) == len(sample_entries)
        assert len(errors) == 0

        for original in sample_entries:
            imported_entry = next(e for e in imported if e.key == original.key)
            assert imported_entry.type == original.type
            assert imported_entry.title == original.title
            assert imported_entry.author == original.author
            assert imported_entry.year == original.year

    def test_json_round_trip(self, entry_with_all_fields, temp_dir):
        """JSON export/import preserves all fields."""
        from bibmgr.storage.importers import JsonImporter

        importer = JsonImporter()

        output_file = temp_dir / "roundtrip.json"
        importer.export_entries([entry_with_all_fields], output_file)

        imported, errors = importer.import_file(output_file)

        assert len(imported) == 1
        assert len(errors) == 0

        original_dict = entry_with_all_fields.to_dict()
        imported_dict = imported[0].to_dict()

        for d in [original_dict, imported_dict]:
            d.pop("added", None)
            d.pop("modified", None)

        assert original_dict == imported_dict


class TestImportStrategies:
    """Test different import strategies and options."""

    def test_skip_duplicates_strategy(self):
        """Import can skip duplicate entries."""
        from bibmgr.storage.importers import BibtexImporter, ImportStrategy

        bibtex = """
        @article{same_key,
            title = {First Version},
            author = {Author One},
            journal = {Journal},
            year = 2020
        }

        @article{same_key,
            title = {Second Version},
            author = {Author Two},
            journal = {Journal},
            year = 2021
        }
        """

        importer = BibtexImporter(
            validate=False, strategy=ImportStrategy.SKIP_DUPLICATES
        )
        entries, errors = importer.import_text(bibtex)

        assert len(entries) == 1
        assert entries[0].title == "First Version"
        assert len(errors) == 1
        assert "duplicate" in errors[0].lower()

    def test_merge_duplicates_strategy(self):
        """Import can merge duplicate entries."""
        from bibmgr.storage.importers import BibtexImporter, ImportStrategy

        bibtex = """
        @article{same_key,
            title = {Original Title},
            author = {Author},
            journal = {Journal},
            year = 2020
        }

        @article{same_key,
            title = {Updated Title},
            doi = {10.1234/new.doi},
            year = 2021
        }
        """

        importer = BibtexImporter(
            validate=False, strategy=ImportStrategy.MERGE_DUPLICATES
        )
        entries, errors = importer.import_text(bibtex)

        assert len(entries) == 1
        entry = entries[0]
        assert entry.title == "Updated Title"  # Later value
        assert entry.author == "Author"  # Preserved from first
        assert entry.doi == "10.1234/new.doi"  # New field
        assert entry.year == 2021  # Updated

    def test_rename_duplicates_strategy(self):
        """Import can rename duplicate entries."""
        from bibmgr.storage.importers import BibtexImporter, ImportStrategy

        bibtex = """
        @article{same_key,
            title = {First Article},
            author = {Author},
            journal = {Journal},
            year = 2020
        }

        @article{same_key,
            title = {Second Article},
            author = {Author},
            journal = {Journal},
            year = 2021
        }
        """

        importer = BibtexImporter(
            validate=False, strategy=ImportStrategy.RENAME_DUPLICATES
        )
        entries, errors = importer.import_text(bibtex)

        assert len(entries) == 2
        assert entries[0].key == "same_key"
        assert entries[1].key != "same_key"  # Renamed
        assert entries[1].key.startswith("same_key")  # Based on original
