"""Comprehensive tests for bibliography entry validators.

Tests define expected behavior of validation without implementation dependencies.
"""

from datetime import datetime


class TestRequiredFieldsValidator:
    """Test required fields validation."""

    def test_article_required_fields(self):
        """Article should require author, title, journal, and year."""
        from bibmgr.core import Entry, EntryType, RequiredFieldsValidator

        validator = RequiredFieldsValidator()

        # Valid article with all required fields
        valid_entry = Entry(
            key="valid2024",
            type=EntryType.ARTICLE,
            author="John Smith",
            title="Important Research",
            journal="Nature",
            year=2024,
        )
        errors = validator.validate(valid_entry)
        assert len(errors) == 0

        # Missing all required fields
        invalid_entry = Entry(key="invalid", type=EntryType.ARTICLE)
        errors = validator.validate(invalid_entry)
        error_fields = {e.field for e in errors}
        assert "author" in error_fields
        assert "title" in error_fields
        assert "journal" in error_fields
        assert "year" in error_fields

        # Missing only some fields
        partial_entry = Entry(
            key="partial", type=EntryType.ARTICLE, title="Only Title", year=2024
        )
        errors = validator.validate(partial_entry)
        error_fields = {e.field for e in errors}
        assert "author" in error_fields
        assert "journal" in error_fields
        assert "title" not in error_fields
        assert "year" not in error_fields

    def test_book_author_or_editor(self):
        """Book should require either author or editor plus title, publisher, year."""
        from bibmgr.core import Entry, EntryType, RequiredFieldsValidator

        validator = RequiredFieldsValidator()

        # Valid with author
        book_with_author = Entry(
            key="book1",
            type=EntryType.BOOK,
            author="Book Author",
            title="Book Title",
            publisher="Publisher",
            year=2024,
        )
        errors = validator.validate(book_with_author)
        assert len(errors) == 0

        # Valid with editor instead of author
        book_with_editor = Entry(
            key="book2",
            type=EntryType.BOOK,
            editor="Book Editor",
            title="Edited Book",
            publisher="Publisher",
            year=2024,
        )
        errors = validator.validate(book_with_editor)
        assert len(errors) == 0

        # Invalid - neither author nor editor
        book_without_both = Entry(
            key="book3",
            type=EntryType.BOOK,
            title="Title",
            publisher="Publisher",
            year=2024,
        )
        errors = validator.validate(book_without_both)
        assert any(
            "author" in e.field.lower() or "editor" in e.field.lower() for e in errors
        )

    def test_inbook_chapter_or_pages(self):
        """Inbook should require either chapter or pages."""
        from bibmgr.core import Entry, EntryType, RequiredFieldsValidator

        validator = RequiredFieldsValidator()

        # Valid with chapter
        with_chapter = Entry(
            key="inbook1",
            type=EntryType.INBOOK,
            author="Author",
            title="Chapter Title",
            publisher="Publisher",
            year=2024,
            chapter="5",
        )
        errors = validator.validate(with_chapter)
        assert len(errors) == 0

        # Valid with pages
        with_pages = Entry(
            key="inbook2",
            type=EntryType.INBOOK,
            author="Author",
            title="Section Title",
            publisher="Publisher",
            year=2024,
            pages="50--75",
        )
        errors = validator.validate(with_pages)
        assert len(errors) == 0

        # Invalid - neither chapter nor pages
        without_both = Entry(
            key="inbook3",
            type=EntryType.INBOOK,
            author="Author",
            title="Title",
            publisher="Publisher",
            year=2024,
        )
        errors = validator.validate(without_both)
        assert any(
            "chapter" in e.field.lower() or "pages" in e.field.lower() for e in errors
        )

    def test_misc_no_required(self):
        """Misc type should have no required fields."""
        from bibmgr.core import Entry, EntryType, RequiredFieldsValidator

        validator = RequiredFieldsValidator()

        # Completely empty misc entry
        minimal = Entry(key="misc", type=EntryType.MISC)
        errors = validator.validate(minimal)
        required_errors = [
            e
            for e in errors
            if e.severity == "error" and "required" in e.message.lower()
        ]
        assert len(required_errors) == 0

    def test_conference_fields(self):
        """Conference should require author, title, booktitle, year."""
        from bibmgr.core import Entry, EntryType, RequiredFieldsValidator

        validator = RequiredFieldsValidator()

        valid_conf = Entry(
            key="conf2024",
            type=EntryType.CONFERENCE,
            author="Speaker",
            title="Talk Title",
            booktitle="Conference Proceedings",
            year=2024,
        )
        errors = validator.validate(valid_conf)
        assert len(errors) == 0

        invalid_conf = Entry(
            key="conf_bad", type=EntryType.CONFERENCE, title="Only Title"
        )
        errors = validator.validate(invalid_conf)
        error_fields = {e.field for e in errors}
        assert "author" in error_fields
        assert "booktitle" in error_fields
        assert "year" in error_fields


class TestFieldFormatValidator:
    """Test field format validation."""

    def test_doi_format(self):
        """Should validate DOI format (10.xxxx/yyyy)."""
        from bibmgr.core import Entry, EntryType, FieldFormatValidator

        validator = FieldFormatValidator()

        # Valid DOI
        valid = Entry(key="doi1", type=EntryType.MISC, doi="10.1038/nature12373")
        errors = validator.validate(valid)
        doi_errors = [e for e in errors if e.field == "doi"]
        assert len(doi_errors) == 0

        # Invalid DOI
        invalid = Entry(key="doi2", type=EntryType.MISC, doi="not-a-doi")
        errors = validator.validate(invalid)
        doi_errors = [e for e in errors if e.field == "doi"]
        assert len(doi_errors) > 0
        assert any("DOI" in e.message for e in doi_errors)

    def test_isbn_format_and_checksum(self):
        """Should validate ISBN format and checksum."""
        from bibmgr.core import Entry, EntryType, FieldFormatValidator

        validator = FieldFormatValidator()

        # Valid ISBN-10 (fake but correct format)
        isbn10 = Entry(
            key="isbn10",
            type=EntryType.BOOK,
            title="Book",
            publisher="Pub",
            year=2024,
            isbn="0123456789",
        )
        errors = validator.validate(isbn10)
        # Will check format and checksum

        # Valid ISBN-13
        isbn13 = Entry(
            key="isbn13",
            type=EntryType.BOOK,
            title="Book",
            publisher="Pub",
            year=2024,
            isbn="9780123456789",
        )
        errors = validator.validate(isbn13)
        # Will check format and checksum

        # Invalid ISBN (too short)
        invalid = Entry(
            key="isbn_bad",
            type=EntryType.BOOK,
            title="Book",
            publisher="Pub",
            year=2024,
            isbn="123",
        )
        errors = validator.validate(invalid)
        isbn_errors = [e for e in errors if e.field == "isbn"]
        assert len(isbn_errors) > 0

    def test_issn_format(self):
        """Should validate ISSN format (XXXX-XXXX)."""
        from bibmgr.core import Entry, EntryType, FieldFormatValidator

        validator = FieldFormatValidator()

        # Valid ISSN
        valid = Entry(
            key="issn1",
            type=EntryType.ARTICLE,
            author="A",
            title="T",
            journal="J",
            year=2024,
            issn="1234-5678",
        )
        errors = validator.validate(valid)
        issn_errors = [e for e in errors if e.field == "issn"]
        assert len(issn_errors) == 0

        # Invalid ISSN
        invalid = Entry(
            key="issn2",
            type=EntryType.ARTICLE,
            author="A",
            title="T",
            journal="J",
            year=2024,
            issn="invalid",
        )
        errors = validator.validate(invalid)
        issn_errors = [e for e in errors if e.field == "issn"]
        assert len(issn_errors) > 0

    def test_url_format(self):
        """Should validate URL format."""
        from bibmgr.core import Entry, EntryType, FieldFormatValidator

        validator = FieldFormatValidator()

        # Valid URLs
        valid_urls = [
            "https://example.com",
            "http://example.com/path",
            "https://example.com/path?query=value",
            "ftp://ftp.example.com/file.pdf",
        ]

        for url in valid_urls:
            entry = Entry(key="url", type=EntryType.MISC, url=url)
            errors = validator.validate(entry)
            url_errors = [e for e in errors if e.field == "url"]
            assert len(url_errors) == 0, f"Valid URL rejected: {url}"

        # Invalid URLs
        invalid_urls = [
            "not-a-url",
            "example.com",  # Missing protocol
            "://example.com",  # Missing protocol name
            "http://",  # Missing domain
        ]

        for url in invalid_urls:
            entry = Entry(key="url", type=EntryType.MISC, url=url)
            errors = validator.validate(entry)
            url_errors = [e for e in errors if e.field == "url"]
            assert len(url_errors) > 0, f"Invalid URL accepted: {url}"

    def test_page_range_format(self):
        """Should validate page range format (use -- not -)."""
        from bibmgr.core import Entry, EntryType, FieldFormatValidator

        validator = FieldFormatValidator()

        # Correct format with double dash
        correct = Entry(
            key="pages1",
            type=EntryType.ARTICLE,
            author="A",
            title="T",
            journal="J",
            year=2024,
            pages="10--20",
        )
        errors = validator.validate(correct)
        page_errors = [e for e in errors if e.field == "pages"]
        assert len(page_errors) == 0

        # Wrong format with single dash
        wrong = Entry(
            key="pages2",
            type=EntryType.ARTICLE,
            author="A",
            title="T",
            journal="J",
            year=2024,
            pages="10-20",
        )
        errors = validator.validate(wrong)
        page_errors = [e for e in errors if e.field == "pages"]
        assert len(page_errors) > 0
        assert any("--" in e.message for e in page_errors)

        # Single page is valid
        single = Entry(
            key="pages3",
            type=EntryType.ARTICLE,
            author="A",
            title="T",
            journal="J",
            year=2024,
            pages="42",
        )
        errors = validator.validate(single)
        page_errors = [e for e in errors if e.field == "pages"]
        assert len(page_errors) == 0

    def test_year_validation(self):
        """Should validate year is reasonable."""
        from bibmgr.core import Entry, EntryType, FieldFormatValidator

        validator = FieldFormatValidator()
        current_year = datetime.now().year

        # Valid year
        valid = Entry(key="year1", type=EntryType.MISC, year=2024)
        errors = validator.validate(valid)
        year_errors = [e for e in errors if e.field == "year"]
        assert len(year_errors) == 0

        # Too old (before printing press ~1450)
        too_old = Entry(key="year2", type=EntryType.MISC, year=1400)
        errors = validator.validate(too_old)
        year_errors = [e for e in errors if e.field == "year"]
        assert len(year_errors) > 0

        # Too far future
        future = Entry(key="year3", type=EntryType.MISC, year=current_year + 10)
        errors = validator.validate(future)
        year_errors = [e for e in errors if e.field == "year"]
        assert len(year_errors) > 0

    def test_month_validation(self):
        """Should validate month format."""
        from bibmgr.core import Entry, EntryType, FieldFormatValidator

        validator = FieldFormatValidator()

        # Valid month formats
        valid_months = [
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
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]

        for month in valid_months:
            entry = Entry(key="month", type=EntryType.MISC, month=month)
            errors = validator.validate(entry)
            month_errors = [e for e in errors if e.field == "month"]
            assert len(month_errors) == 0, f"Valid month rejected: {month}"

        # Invalid months
        invalid_months = ["13", "0", "Month", "invalid"]

        for month in invalid_months:
            entry = Entry(key="month", type=EntryType.MISC, month=month)
            errors = validator.validate(entry)
            month_errors = [e for e in errors if e.field == "month"]
            assert len(month_errors) > 0, f"Invalid month accepted: {month}"


class TestAuthorFormatValidator:
    """Test author/editor format validation."""

    def test_author_separator(self):
        """Should use 'and' to separate authors, not semicolon."""
        from bibmgr.core import Entry, EntryType, AuthorFormatValidator

        validator = AuthorFormatValidator()

        # Correct separator
        correct = Entry(
            key="auth1", type=EntryType.MISC, author="John Smith and Jane Doe"
        )
        errors = validator.validate(correct)
        assert not any("semicolon" in e.message.lower() for e in errors)

        # Wrong separator
        wrong = Entry(key="auth2", type=EntryType.MISC, author="John Smith; Jane Doe")
        errors = validator.validate(wrong)
        assert any("semicolon" in e.message.lower() for e in errors)
        assert any("and" in e.message for e in errors)

    def test_et_al_warning(self):
        """Should warn about 'et al.' usage."""
        from bibmgr.core import Entry, EntryType, AuthorFormatValidator

        validator = AuthorFormatValidator()

        entry = Entry(key="etal", type=EntryType.MISC, author="Smith et al.")
        errors = validator.validate(entry)
        assert any("et al" in e.message.lower() for e in errors)
        assert any("and others" in e.message for e in errors)

    def test_empty_author_detection(self):
        """Should detect empty author entries."""
        from bibmgr.core import Entry, EntryType, AuthorFormatValidator

        validator = AuthorFormatValidator()

        # Double 'and' creates empty author
        entry = Entry(
            key="empty", type=EntryType.MISC, author="John Smith and  and Jane Doe"
        )
        errors = validator.validate(entry)
        assert any("empty" in e.message.lower() for e in errors)

    def test_too_many_commas(self):
        """Should warn about too many commas in author name."""
        from bibmgr.core import Entry, EntryType, AuthorFormatValidator

        validator = AuthorFormatValidator()

        # Normal Last, First format is OK
        normal = Entry(
            key="normal", type=EntryType.MISC, author="Smith, John and Doe, Jane"
        )
        errors = validator.validate(normal)
        comma_errors = [e for e in errors if "comma" in e.message.lower()]
        assert len(comma_errors) == 0

        # Too many commas
        too_many = Entry(
            key="commas", type=EntryType.MISC, author="Smith, Jr., John, PhD"
        )
        errors = validator.validate(too_many)
        assert any("comma" in e.message.lower() for e in errors)

    def test_editor_field_validation(self):
        """Should validate editor field same as author."""
        from bibmgr.core import Entry, EntryType, AuthorFormatValidator

        validator = AuthorFormatValidator()

        # Editor with wrong separator
        entry = Entry(
            key="editor",
            type=EntryType.BOOK,
            editor="Editor One; Editor Two",
            title="Book",
            publisher="Pub",
            year=2024,
        )
        errors = validator.validate(entry)
        editor_errors = [e for e in errors if e.field == "editor"]
        assert len(editor_errors) > 0
        assert any("semicolon" in e.message.lower() for e in editor_errors)


class TestCrossReferenceValidator:
    """Test cross-reference validation."""

    def test_valid_crossref(self):
        """Should accept valid cross-references."""
        from bibmgr.core import Entry, EntryType, CrossReferenceValidator

        all_keys = {"mainbook", "chapter1", "chapter2"}
        validator = CrossReferenceValidator(all_keys)

        entry = Entry(
            key="chapter1",
            type=EntryType.INBOOK,
            crossref="mainbook",
            title="Chapter",
            chapter="1",
        )
        errors = validator.validate(entry)
        crossref_errors = [e for e in errors if e.field == "crossref"]
        assert len(crossref_errors) == 0

    def test_invalid_crossref(self):
        """Should detect references to non-existent entries."""
        from bibmgr.core import Entry, EntryType, CrossReferenceValidator

        all_keys = {"entry1", "entry2"}
        validator = CrossReferenceValidator(all_keys)

        entry = Entry(
            key="chapter",
            type=EntryType.INBOOK,
            crossref="nonexistent",
            title="Chapter",
            chapter="1",
        )
        errors = validator.validate(entry)
        assert any(
            e.field == "crossref" and "unknown" in e.message.lower() for e in errors
        )

    def test_self_reference(self):
        """Should detect self-references."""
        from bibmgr.core import Entry, EntryType, CrossReferenceValidator

        all_keys = {"self"}
        validator = CrossReferenceValidator(all_keys)

        entry = Entry(key="self", type=EntryType.MISC, crossref="self")
        errors = validator.validate(entry)
        assert any(
            e.field == "crossref" and "itself" in e.message.lower() for e in errors
        )

    def test_circular_reference(self):
        """Should detect circular references."""
        from bibmgr.core import Entry, EntryType, CrossReferenceValidator

        # Create circular reference chain
        entries = {
            "a": Entry(key="a", type=EntryType.MISC, crossref="b"),
            "b": Entry(key="b", type=EntryType.MISC, crossref="c"),
            "c": Entry(key="c", type=EntryType.MISC, crossref="a"),
        }

        validator = CrossReferenceValidator(set(entries.keys()))

        # Check circular reference detection
        for entry in entries.values():
            errors = validator.validate_circular(entry, entries)
            if entry.crossref:
                assert any("circular" in e.message.lower() for e in errors)

    def test_no_keys_provided(self):
        """Should handle when no key list is provided."""
        from bibmgr.core import Entry, EntryType, CrossReferenceValidator

        validator = CrossReferenceValidator()  # No keys

        entry = Entry(key="test", type=EntryType.MISC, crossref="other")
        errors = validator.validate(entry)
        assert any("cannot validate" in e.message.lower() for e in errors)


class TestISBNValidator:
    """Test ISBN checksum validation."""

    def test_isbn10_checksum(self):
        """Should validate ISBN-10 checksum."""
        from bibmgr.core import ISBNValidator

        validator = ISBNValidator()

        # Valid ISBN-10s
        assert validator.is_valid_isbn10("0306406152")
        assert validator.is_valid_isbn10("043942089X")  # X checksum

        # Invalid ISBN-10s
        assert not validator.is_valid_isbn10("0306406153")  # Wrong checksum
        assert not validator.is_valid_isbn10("123456789")  # Wrong length

    def test_isbn13_checksum(self):
        """Should validate ISBN-13 checksum."""
        from bibmgr.core import ISBNValidator

        validator = ISBNValidator()

        # Valid ISBN-13s
        assert validator.is_valid_isbn13("9780306406157")
        assert validator.is_valid_isbn13("9781234567897")

        # Invalid ISBN-13s
        assert not validator.is_valid_isbn13("9780306406158")  # Wrong checksum
        assert not validator.is_valid_isbn13("978030640615")  # Wrong length

    def test_isbn_with_hyphens(self):
        """Should handle ISBNs with hyphens."""
        from bibmgr.core import ISBNValidator

        validator = ISBNValidator()

        # Should strip hyphens and validate
        assert validator.is_valid_isbn("0-306-40615-2")
        assert validator.is_valid_isbn("978-0-306-40615-7")
        assert validator.is_valid_isbn("0-439-42089-X")


class TestISSNValidator:
    """Test ISSN validation."""

    def test_issn_format(self):
        """Should validate ISSN format."""
        from bibmgr.core import ISSNValidator

        validator = ISSNValidator()

        # Valid ISSNs
        assert validator.is_valid_issn("1234-5678")
        assert validator.is_valid_issn("0378-5955")

        # Invalid ISSNs
        assert not validator.is_valid_issn("12345678")  # No hyphen
        assert not validator.is_valid_issn("1234-567")  # Wrong length
        assert not validator.is_valid_issn("ABCD-5678")  # Letters

    def test_issn_structure(self):
        """Should validate ISSN structure."""
        from bibmgr.core import ISSNValidator

        validator = ISSNValidator()

        # Must be XXXX-XXXX format
        assert validator.is_valid_issn("0378-5955")
        assert not validator.is_valid_issn("378-5955")  # First part too short
        assert not validator.is_valid_issn("0378-595")  # Second part too short


class TestCompositeValidator:
    """Test composite validator."""

    def test_combine_validators(self):
        """Should combine multiple validators."""
        from bibmgr.core import (
            Entry,
            EntryType,
            CompositeValidator,
            RequiredFieldsValidator,
            FieldFormatValidator,
        )

        validator = CompositeValidator(
            [RequiredFieldsValidator(), FieldFormatValidator()]
        )

        # Entry with multiple issues
        entry = Entry(
            key="multi",
            type=EntryType.ARTICLE,
            title="Only Title",  # Missing required fields
            pages="1-10",  # Wrong format
        )

        errors = validator.validate(entry)

        # Should find both types of errors
        assert any(e.field == "author" for e in errors)  # Required
        assert any(e.field == "journal" for e in errors)  # Required
        assert any(e.field == "year" for e in errors)  # Required
        assert any(e.field == "pages" and "--" in e.message for e in errors)  # Format

    def test_deduplicate_errors(self):
        """Should deduplicate identical errors."""
        from bibmgr.core import Entry, EntryType, CompositeValidator, ValidationError

        # Custom validator that produces duplicates
        class DuplicateValidator:
            def validate(self, entry):
                return [
                    ValidationError(
                        field="test", message="duplicate", severity="error"
                    ),
                    ValidationError(
                        field="test", message="duplicate", severity="error"
                    ),
                ]

        validator = CompositeValidator([DuplicateValidator(), DuplicateValidator()])

        entry = Entry(key="test", type=EntryType.MISC)
        errors = validator.validate(entry)

        # Should have only one of each duplicate
        duplicate_count = sum(
            1 for e in errors if e.field == "test" and e.message == "duplicate"
        )
        assert duplicate_count == 1

    def test_preserve_error_order(self):
        """Should preserve error order from validators."""
        from bibmgr.core import (
            Entry,
            EntryType,
            CompositeValidator,
            RequiredFieldsValidator,
            FieldFormatValidator,
        )

        validator = CompositeValidator(
            [RequiredFieldsValidator(), FieldFormatValidator()]
        )

        entry = Entry(key="order", type=EntryType.ARTICLE, title="Title")

        errors = validator.validate(entry)
        error_list = list(errors)

        # Required field errors should come before format errors
        required_indices = [
            i for i, e in enumerate(error_list) if "required" in e.message.lower()
        ]
        format_indices = [
            i for i, e in enumerate(error_list) if "format" in e.message.lower()
        ]

        if required_indices and format_indices:
            assert max(required_indices) < min(format_indices)


class TestValidatorFactory:
    """Test validator creation helpers."""

    def test_create_default_validator(self):
        """Should create validator with all standard checks."""
        from bibmgr.core import create_default_validator, Entry, EntryType

        validator = create_default_validator()

        # Entry with various issues
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Title",  # Missing required
            doi="invalid",  # Bad format
            author="Author1; Author2",  # Wrong separator
        )

        errors = validator.validate(entry)
        error_fields = {e.field for e in errors}

        # Should find all types of errors
        assert "journal" in error_fields  # Required
        assert "year" in error_fields  # Required
        assert "doi" in error_fields  # Format
        assert "author" in error_fields  # Separator

    def test_create_validator_with_keys(self):
        """Should create validator with cross-reference checking."""
        from bibmgr.core import create_default_validator, Entry, EntryType

        all_keys = {"book1", "chapter1"}
        validator = create_default_validator(all_keys=all_keys)

        # Valid cross-reference
        valid_ref = Entry(
            key="chapter1",
            type=EntryType.INBOOK,
            crossref="book1",
            title="Chapter",
            chapter="1",
            author="Author",
            publisher="Pub",
            year=2024,
        )
        errors = validator.validate(valid_ref)
        crossref_errors = [e for e in errors if e.field == "crossref"]
        assert len(crossref_errors) == 0

        # Invalid cross-reference
        invalid_ref = Entry(
            key="chapter2",
            type=EntryType.INBOOK,
            crossref="nonexistent",
            title="Chapter",
            chapter="2",
            author="Author",
            publisher="Pub",
            year=2024,
        )
        errors = validator.validate(invalid_ref)
        crossref_errors = [e for e in errors if e.field == "crossref"]
        assert len(crossref_errors) > 0

    def test_custom_validator_pipeline(self):
        """Should support custom validator pipelines."""
        from bibmgr.core import CompositeValidator, Entry, EntryType, ValidationError

        # Custom validator with specific rule
        class CustomValidator:
            def validate(self, entry):
                errors = []
                if entry.title and len(entry.title) < 5:
                    errors.append(
                        ValidationError(
                            field="title", message="Title too short", severity="warning"
                        )
                    )
                return errors

        validator = CompositeValidator([CustomValidator()])

        short_title = Entry(key="test", type=EntryType.MISC, title="Hi")
        errors = validator.validate(short_title)
        assert any(e.field == "title" and "short" in e.message for e in errors)

        long_title = Entry(
            key="test2", type=EntryType.MISC, title="This is a longer title"
        )
        errors = validator.validate(long_title)
        title_errors = [e for e in errors if e.field == "title"]
        assert len(title_errors) == 0
