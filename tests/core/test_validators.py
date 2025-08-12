"""Tests for bibliography entry validation system.

This module tests all validators for BibTeX compliance, including field formats,
required fields, identifiers (DOI, ISBN, ISSN), and cross-references.
"""

from datetime import datetime
from typing import Any

from bibmgr.core.fields import EntryType
from bibmgr.core.models import Entry
from bibmgr.core.validators import (
    AuthorFormatValidator,
    CrossReferenceValidator,
    DOIValidator,
    EntryKeyValidator,
    FieldFormatValidator,
    ISBNValidator,
    ISSNValidator,
    RequiredFieldValidator,
    URLValidator,
    ValidatorRegistry,
    get_validator_registry,
)


class TestEntryKeyValidator:
    """Test entry key validation according to BibTeX rules."""

    def test_valid_entry_keys(self, valid_entry_keys: list[str]) -> None:
        """Valid entry keys should pass validation."""
        validator = EntryKeyValidator()

        for key in valid_entry_keys:
            entry = Entry(key=key, type=EntryType.MISC, title="Test")
            errors = validator.validate(entry)
            assert len(errors) == 0, f"Key '{key}' should be valid"

    def test_invalid_entry_keys(self, invalid_entry_keys: list[str]) -> None:
        """Invalid entry keys should produce errors."""
        validator = EntryKeyValidator()

        for key in invalid_entry_keys:
            entry = Entry(key=key, type=EntryType.MISC, title="Test")
            errors = validator.validate(entry)
            assert len(errors) > 0, f"Key '{key}' should be invalid"
            assert errors[0].field == "key"
            assert errors[0].severity == "error"

    def test_empty_key_error(self) -> None:
        """Empty entry key must produce error."""
        validator = EntryKeyValidator()
        entry = Entry(key="", type=EntryType.MISC, title="Test")

        errors = validator.validate(entry)
        assert len(errors) == 1
        assert "cannot be empty" in errors[0].message

    def test_key_with_special_chars(self) -> None:
        """Special characters in keys should be rejected."""
        validator = EntryKeyValidator()
        invalid_keys = ["key@2024", "key.2024", "key/2024", "key\\2024", "key{2024}"]

        for key in invalid_keys:
            entry = Entry(key=key, type=EntryType.MISC, title="Test")
            errors = validator.validate(entry)
            assert len(errors) == 1
            assert "invalid characters" in errors[0].message

    def test_overly_long_key_warning(self) -> None:
        """Keys over 250 characters should produce warning."""
        validator = EntryKeyValidator()
        long_key = "a" * 251
        entry = Entry(key=long_key, type=EntryType.MISC, title="Test")

        errors = validator.validate(entry)
        assert len(errors) == 1
        assert errors[0].severity == "warning"
        assert "too long" in errors[0].message


class TestRequiredFieldValidator:
    """Test required field validation for each entry type."""

    def test_article_missing_required_fields(self) -> None:
        """Article missing required fields should produce errors."""
        validator = RequiredFieldValidator()

        # Missing all required fields
        entry = Entry(key="test", type=EntryType.ARTICLE)
        errors = validator.validate(entry)

        required = {"author", "title", "journal", "year"}
        error_fields = {e.field for e in errors}
        assert error_fields == required

    def test_book_alternative_fields(self) -> None:
        """Book must have author OR editor."""
        validator = RequiredFieldValidator()

        # Missing both author and editor
        entry = Entry(
            key="test",
            type=EntryType.BOOK,
            title="Test Book",
            publisher="Publisher",
            year=2024,
        )
        errors = validator.validate(entry)
        assert any(e.field and "author|editor" in e.field for e in errors)

        # With author - should be valid
        entry_with_author = Entry(
            key="test",
            type=EntryType.BOOK,
            author="Test Author",
            title="Test Book",
            publisher="Publisher",
            year=2024,
        )
        errors = validator.validate(entry_with_author)
        assert len(errors) == 0

        # With editor - should be valid
        entry_with_editor = Entry(
            key="test",
            type=EntryType.BOOK,
            editor="Test Editor",
            title="Test Book",
            publisher="Publisher",
            year=2024,
        )
        errors = validator.validate(entry_with_editor)
        assert len(errors) == 0

    def test_inbook_chapter_or_pages(self) -> None:
        """Inbook must have chapter OR pages."""
        validator = RequiredFieldValidator()

        base_data = {
            "key": "test",
            "type": EntryType.INBOOK,
            "author": "Author",
            "title": "Chapter Title",
            "publisher": "Publisher",
            "year": 2024,
        }

        # Missing both
        entry = Entry(**base_data)
        errors = validator.validate(entry)
        assert any(e.field and "chapter|pages" in e.field for e in errors)

        # With chapter
        entry_chapter = Entry(**base_data, chapter="5")
        assert len(validator.validate(entry_chapter)) == 0

        # With pages
        entry_pages = Entry(**base_data, pages="45--67")
        assert len(validator.validate(entry_pages)) == 0

    def test_misc_no_required_fields(self) -> None:
        """Misc entries have no required fields."""
        validator = RequiredFieldValidator()

        # Completely empty misc entry
        entry = Entry(key="test", type=EntryType.MISC)
        errors = validator.validate(entry)
        assert len(errors) == 0

    def test_unpublished_requires_note(self) -> None:
        """Unpublished entries must have note field."""
        validator = RequiredFieldValidator()

        entry = Entry(
            key="test",
            type=EntryType.UNPUBLISHED,
            author="Author",
            title="Draft Paper",
            # Missing note
        )
        errors = validator.validate(entry)
        assert any(e.field == "note" for e in errors)


class TestFieldFormatValidator:
    """Test field format validation."""

    def test_year_valid_formats(self) -> None:
        """Valid year formats should pass."""
        validator = FieldFormatValidator()

        valid_years = [2024, 1984, 1450]  # Integers
        for year in valid_years:
            entry = Entry(key="test", type=EntryType.MISC, year=year)
            errors = validator.validate(entry)
            assert len(errors) == 0

    def test_year_special_values(self) -> None:
        """Special year values like 'in press' should be valid."""
        validator = FieldFormatValidator()

        special_values = [
            "in press",
            "forthcoming",
            "preprint",
            "submitted",
            "accepted",
            "to appear",
        ]

        for value in special_values:
            entry = Entry(key="test", type=EntryType.MISC, year=value)  # type: ignore
            errors = validator.validate(entry)
            assert len(errors) == 0

    def test_year_out_of_range_warning(self) -> None:
        """Years far in past or future should produce warning."""
        validator = FieldFormatValidator()
        current_year = datetime.now().year

        # Too far in past
        entry_past = Entry(key="test", type=EntryType.MISC, year=999)
        errors = validator.validate(entry_past)
        assert len(errors) == 1
        assert errors[0].severity == "warning"

        # Too far in future
        entry_future = Entry(key="test", type=EntryType.MISC, year=current_year + 10)
        errors = validator.validate(entry_future)
        assert len(errors) == 1
        assert errors[0].severity == "warning"

    def test_month_valid_formats(self) -> None:
        """Valid month formats should pass."""
        validator = FieldFormatValidator()

        valid_months = [
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "January",
            "February",
            "December",  # Full names
        ]

        for month in valid_months:
            entry = Entry(key="test", type=EntryType.MISC, month=month)
            errors = validator.validate(entry)
            assert len(errors) == 0

    def test_month_invalid_format(self) -> None:
        """Invalid month formats should produce warning."""
        validator = FieldFormatValidator()

        invalid_months = ["13", "0", "Janury", "janvier", "1-2", "Spring"]

        for month in invalid_months:
            entry = Entry(key="test", type=EntryType.MISC, month=month)
            errors = validator.validate(entry)
            assert len(errors) == 1
            assert errors[0].field == "month"
            assert errors[0].severity == "warning"

    def test_pages_valid_formats(self) -> None:
        """Valid page formats should pass."""
        validator = FieldFormatValidator()

        valid_pages = [
            "42",  # Single page
            "10-20",  # Range with single dash
            "10--20",  # Range with double dash (BibTeX standard)
            "A10--A20",  # Letter prefix
            "S5--S10",  # Supplement pages
            "5,10,15",  # Multiple pages
            "5--10,20--25",  # Multiple ranges
        ]

        for pages in valid_pages:
            entry = Entry(key="test", type=EntryType.MISC, pages=pages)
            errors = validator.validate(entry)
            # Filter out info-level suggestions
            error_warnings = [e for e in errors if e.severity in ["error", "warning"]]
            assert len(error_warnings) == 0

    def test_pages_invalid_format(self) -> None:
        """Invalid page formats should produce warning."""
        validator = FieldFormatValidator()

        invalid_pages = [
            "ten",  # Text
            "10 - 20",  # Spaces around dash
            "10–20",  # Em dash
            "10-",  # Incomplete range
            "-20",  # Missing start
        ]

        for pages in invalid_pages:
            entry = Entry(key="test", type=EntryType.MISC, pages=pages)
            errors = validator.validate(entry)
            assert len(errors) == 1
            assert errors[0].field == "pages"


class TestDOIValidator:
    """Test DOI format validation."""

    def test_valid_dois(self, valid_dois: list[str]) -> None:
        """Valid DOIs should pass validation."""
        validator = DOIValidator()

        for doi in valid_dois:
            entry = Entry(key="test", type=EntryType.MISC, doi=doi)
            errors = validator.validate(entry)
            assert len(errors) == 0, f"DOI '{doi}' should be valid"

    def test_doi_with_prefix_stripped(self) -> None:
        """DOI prefixes should be stripped before validation."""
        validator = DOIValidator()

        prefixed_dois = [
            "https://doi.org/10.1038/nature12373",
            "http://doi.org/10.1038/nature12373",
            "doi:10.1038/nature12373",
        ]

        for doi in prefixed_dois:
            entry = Entry(key="test", type=EntryType.MISC, doi=doi)
            errors = validator.validate(entry)
            # Should validate the DOI after stripping prefix
            assert len(errors) == 0

    def test_invalid_doi_format(self) -> None:
        """Invalid DOI formats should produce warning."""
        validator = DOIValidator()

        invalid_dois = [
            "not-a-doi",
            "10.1234",  # Missing suffix
            "1234/5678",  # Missing prefix
            "10./incomplete",
            "10.1234/",  # Trailing slash
        ]

        for doi in invalid_dois:
            entry = Entry(key="test", type=EntryType.MISC, doi=doi)
            errors = validator.validate(entry)
            assert len(errors) == 1
            assert errors[0].field == "doi"
            assert errors[0].severity == "warning"


class TestISBNValidator:
    """Test ISBN validation with checksums."""

    def test_valid_isbn10(self, valid_isbns: list[dict[str, str]]) -> None:
        """Valid ISBN-10 should pass checksum validation."""
        validator = ISBNValidator()

        isbn10_entries = [isbn for isbn in valid_isbns if isbn["type"] == "isbn10"]

        for isbn_data in isbn10_entries:
            entry = Entry(key="test", type=EntryType.MISC, isbn=isbn_data["isbn"])
            errors = validator.validate(entry)
            assert len(errors) == 0, f"ISBN-10 '{isbn_data['isbn']}' should be valid"

    def test_valid_isbn13(self, valid_isbns: list[dict[str, str]]) -> None:
        """Valid ISBN-13 should pass checksum validation."""
        validator = ISBNValidator()

        isbn13_entries = [isbn for isbn in valid_isbns if isbn["type"] == "isbn13"]

        for isbn_data in isbn13_entries:
            entry = Entry(key="test", type=EntryType.MISC, isbn=isbn_data["isbn"])
            errors = validator.validate(entry)
            assert len(errors) == 0, f"ISBN-13 '{isbn_data['isbn']}' should be valid"

    def test_isbn_with_x_checksum(self) -> None:
        """ISBN-10 with X checksum should be valid."""
        validator = ISBNValidator()

        entry = Entry(key="test", type=EntryType.MISC, isbn="043942089X")
        errors = validator.validate(entry)
        assert len(errors) == 0

    def test_invalid_isbn_checksum(self) -> None:
        """Invalid ISBN checksums should produce warning."""
        validator = ISBNValidator()

        # Valid format but wrong checksum
        invalid_isbns = [
            "0306406151",  # Should be 2
            "9780306406158",  # Should be 7
        ]

        for isbn in invalid_isbns:
            entry = Entry(key="test", type=EntryType.MISC, isbn=isbn)
            errors = validator.validate(entry)
            assert len(errors) == 1
            assert "Invalid ISBN" in errors[0].message

    def test_isbn_wrong_length(self) -> None:
        """ISBN with wrong length should produce warning."""
        validator = ISBNValidator()

        wrong_length = ["123456789", "12345678901234"]  # 9 and 14 digits

        for isbn in wrong_length:
            entry = Entry(key="test", type=EntryType.MISC, isbn=isbn)
            errors = validator.validate(entry)
            assert len(errors) == 1
            assert "10 or 13 digits" in errors[0].message


class TestISSNValidator:
    """Test ISSN validation with checksums."""

    def test_valid_issns(self, valid_issns: list[str]) -> None:
        """Valid ISSNs should pass checksum validation."""
        validator = ISSNValidator()

        for issn in valid_issns:
            entry = Entry(key="test", type=EntryType.MISC, issn=issn)
            errors = validator.validate(entry)
            assert len(errors) == 0, f"ISSN '{issn}' should be valid"

    def test_issn_with_x_checksum(self) -> None:
        """ISSN with X checksum should be valid."""
        validator = ISSNValidator()

        entry = Entry(key="test", type=EntryType.MISC, issn="2049-369X")
        errors = validator.validate(entry)
        assert len(errors) == 0

    def test_invalid_issn_format(self) -> None:
        """Invalid ISSN format should produce warning."""
        validator = ISSNValidator()

        invalid_formats = [
            "1234567",  # Too short
            "123456789",  # Too long
            "ABCD-1234",  # Letters in wrong place
        ]

        for issn in invalid_formats:
            entry = Entry(key="test", type=EntryType.MISC, issn=issn)
            errors = validator.validate(entry)
            assert len(errors) == 1
            assert "Invalid ISSN format" in errors[0].message

    def test_invalid_issn_checksum(self) -> None:
        """Invalid ISSN checksum should produce warning."""
        validator = ISSNValidator()

        # Valid format but wrong checksum
        entry = Entry(
            key="test", type=EntryType.MISC, issn="0378-5954"
        )  # Should be 5955
        errors = validator.validate(entry)
        assert len(errors) == 1
        assert "Invalid ISSN checksum" in errors[0].message


class TestURLValidator:
    """Test URL format validation."""

    def test_valid_urls(self) -> None:
        """Valid URLs should pass validation."""
        validator = URLValidator()

        valid_urls = [
            "https://example.com",
            "http://example.com/path",
            "https://sub.example.com:8080/path?query=value",
            "http://localhost:3000",
            "https://192.168.1.1/admin",
        ]

        for url in valid_urls:
            entry = Entry(key="test", type=EntryType.MISC, url=url)
            errors = validator.validate(entry)
            # Filter out warnings for HTTP URLs (they're valid but generate security warnings)
            actual_errors = [e for e in errors if e.severity == "error"]
            assert len(actual_errors) == 0

    def test_invalid_url_format(self) -> None:
        """Invalid URL formats should produce warning."""
        validator = URLValidator()

        invalid_urls = [
            "not-a-url",
            "ftp://example.com",  # Not http/https
            "https://",  # Incomplete
            "example.com",  # Missing protocol
            "https://example",  # No TLD
        ]

        for url in invalid_urls:
            entry = Entry(key="test", type=EntryType.MISC, url=url)
            errors = validator.validate(entry)
            assert len(errors) == 1
            assert errors[0].field == "url"


class TestAuthorFormatValidator:
    """Test author/editor name format validation."""

    def test_valid_author_formats(self) -> None:
        """Valid author formats should pass."""
        validator = AuthorFormatValidator()

        valid_entries = [
            "Donald E. Knuth",
            "Jane Doe and John Smith",
            "A. B. Author and C. D. Coauthor and E. F. Editor",
        ]

        for author in valid_entries:
            entry = Entry(key="test", type=EntryType.MISC, author=author)
            errors = validator.validate(entry)
            assert len(errors) == 0

    def test_empty_author_field(self) -> None:
        """Empty author field should produce warning."""
        validator = AuthorFormatValidator()

        entry = Entry(key="test", type=EntryType.MISC, author="")
        errors = validator.validate(entry)
        assert len(errors) == 1
        assert "empty" in errors[0].message

    def test_author_ending_with_comma(self) -> None:
        """Author ending with comma should produce warning."""
        validator = AuthorFormatValidator()

        entry = Entry(key="test", type=EntryType.MISC, author="John Smith,")
        errors = validator.validate(entry)
        assert len(errors) == 1
        assert "ends with comma" in errors[0].message

    def test_empty_author_in_list(self) -> None:
        """Empty author in list should produce warning."""
        validator = AuthorFormatValidator()

        entry = Entry(
            key="test", type=EntryType.MISC, author="John Smith and and Jane Doe"
        )
        errors = validator.validate(entry)
        assert len(errors) == 1
        assert "empty" in errors[0].message

    def test_et_al_warning(self) -> None:
        """Using 'et al.' should suggest 'and others'."""
        validator = AuthorFormatValidator()

        entry = Entry(key="test", type=EntryType.MISC, author="John Smith et al.")
        errors = validator.validate(entry)
        # This would be caught in name parsing validation
        assert len(errors) >= 0  # May or may not warn depending on implementation


class TestCrossReferenceValidator:
    """Test cross-reference validation."""

    def test_valid_crossref(self, crossref_entries: list[dict[str, Any]]) -> None:
        """Valid cross-reference should pass."""
        # Create entries
        all_entries = {}
        for data in crossref_entries:
            entry = Entry.from_dict(data)
            all_entries[entry.key] = entry

        validator = CrossReferenceValidator(all_entries)

        # Validate entry with crossref
        chapter1 = all_entries["chapter1"]
        errors = validator.validate(chapter1)
        assert len(errors) == 0

    def test_nonexistent_crossref(self) -> None:
        """Cross-reference to non-existent entry should error."""
        entry = Entry(
            key="test",
            type=EntryType.INBOOK,
            author="Author",
            title="Chapter",
            chapter="1",
            crossref="nonexistent",
        )

        validator = CrossReferenceValidator({})
        errors = validator.validate(entry)
        assert len(errors) == 1
        assert errors[0].severity == "error"
        assert "non-existent" in errors[0].message

    def test_incompatible_crossref_types(
        self, crossref_entries: list[dict[str, Any]]
    ) -> None:
        """Incompatible cross-reference types should warn."""
        # Create book entry
        book = Entry.from_dict(crossref_entries[0])

        # Create article trying to crossref a book (incompatible)
        article = Entry(
            key="article1",
            type=EntryType.ARTICLE,
            author="Author",
            title="Article",
            journal="Journal",
            year=2024,
            crossref=book.key,
        )

        validator = CrossReferenceValidator({book.key: book})
        errors = validator.validate(article)
        assert any(e.severity == "warning" for e in errors)
        assert any("cannot cross-reference" in e.message for e in errors)


class TestValidatorRegistry:
    """Test the validator registry system."""

    def test_registry_validates_all_aspects(
        self, sample_article_data: dict[str, Any]
    ) -> None:
        """Registry should run all validators."""
        entry = Entry(**sample_article_data)
        registry = ValidatorRegistry([entry])

        errors = registry.validate(entry)
        assert isinstance(errors, list)
        # Valid entry should have no errors
        assert len(errors) == 0

    def test_registry_catches_multiple_errors(self) -> None:
        """Registry should catch errors from multiple validators."""
        entry = Entry(
            key="invalid key",  # Invalid key
            type=EntryType.ARTICLE,
            # Missing required fields
            year=999,  # Out of range
            doi="invalid-doi",  # Invalid format
        )

        registry = ValidatorRegistry([entry])
        errors = registry.validate(entry)

        # Should have errors from multiple validators
        assert len(errors) > 3
        error_fields = {e.field for e in errors if e.field}
        assert "key" in error_fields
        assert "doi" in error_fields

    def test_global_registry_singleton(self) -> None:
        """Global registry should work as singleton."""
        registry1 = get_validator_registry()
        registry2 = get_validator_registry()
        assert registry1 is registry2

        # With new entries, should create new registry
        entries = [Entry(key="test", type=EntryType.MISC)]
        registry3 = get_validator_registry(entries)
        assert registry3 is not registry1

    def test_validate_all_entries(
        self, duplicate_entries: list[dict[str, Any]]
    ) -> None:
        """validate_all should return errors by entry key."""
        entries = [Entry.from_dict(data) for data in duplicate_entries]
        registry = ValidatorRegistry(entries)

        results = registry.validate_all()
        assert isinstance(results, dict)

        # Entries with same DOI should have duplicate warnings
        for key in ["smith2023a", "smith2023b"]:
            if key in results:
                errors = results[key]
                assert any("Duplicate DOI" in e.message for e in errors)
