"""Tests for BibTeX field definitions and entry type specifications.

This module tests the fields.py implementation according to TameTheBeast manual.
All 14 standard entry types and their field requirements are verified.
"""

from bibmgr.core.fields import (
    ALL_FIELDS,
    COMPAT_FIELDS,
    MODERN_FIELDS,
    STANDARD_FIELDS,
    EntryType,
    FieldRequirements,
)


class TestEntryTypes:
    """Test BibTeX entry type definitions."""

    def test_all_standard_entry_types_defined(self) -> None:
        """All 14 standard BibTeX entry types must be defined."""
        standard_types = {
            "article",
            "book",
            "booklet",
            "conference",
            "inbook",
            "incollection",
            "inproceedings",
            "manual",
            "mastersthesis",
            "misc",
            "phdthesis",
            "proceedings",
            "techreport",
            "unpublished",
        }

        defined_types = {entry_type.value for entry_type in EntryType}

        for std_type in standard_types:
            assert std_type in defined_types, f"Standard type '{std_type}' not defined"

    def test_conference_is_alias_for_inproceedings(self) -> None:
        """Conference must be an alias for inproceedings."""
        assert EntryType.CONFERENCE.value == "conference"
        assert EntryType.INPROCEEDINGS.value == "inproceedings"

        # Requirements should be handled identically
        conf_reqs = FieldRequirements.get_requirements(EntryType.CONFERENCE)
        inproc_reqs = FieldRequirements.get_requirements(EntryType.INPROCEEDINGS)
        assert conf_reqs == inproc_reqs

    def test_modern_entry_types_included(self) -> None:
        """Modern entry types should be available."""
        modern_types = [
            "online",
            "electronic",
            "patent",
            "software",
            "dataset",
            "thesis",
        ]
        defined_types = {entry_type.value for entry_type in EntryType}

        for modern_type in modern_types:
            assert modern_type in defined_types, (
                f"Modern type '{modern_type}' not defined"
            )

    def test_entry_type_values_are_lowercase(self) -> None:
        """All entry type values must be lowercase."""
        for entry_type in EntryType:
            assert entry_type.value == entry_type.value.lower()

    def test_entry_type_enum_is_unique(self) -> None:
        """Entry type values must be unique."""
        values = [entry_type.value for entry_type in EntryType]
        assert len(values) == len(set(values))


class TestFieldRequirements:
    """Test field requirements for each entry type."""

    def test_article_required_fields(self) -> None:
        """Article must require author, title, journal, year."""
        reqs = FieldRequirements.get_requirements(EntryType.ARTICLE)
        assert reqs["required"] == {"author", "title", "journal", "year"}

    def test_book_alternative_required_fields(self) -> None:
        """Book must require author OR editor."""
        reqs = FieldRequirements.get_requirements(EntryType.BOOK)
        assert "author|editor" in reqs["required"]
        assert "title" in reqs["required"]
        assert "publisher" in reqs["required"]
        assert "year" in reqs["required"]

    def test_inbook_multiple_alternatives(self) -> None:
        """Inbook must have chapter OR pages requirement."""
        reqs = FieldRequirements.get_requirements(EntryType.INBOOK)
        assert "chapter|pages" in reqs["required"]
        assert "author|editor" in reqs["required"]

    def test_misc_no_required_fields(self) -> None:
        """Misc entry type has no required fields."""
        reqs = FieldRequirements.get_requirements(EntryType.MISC)
        assert reqs["required"] == set()

    def test_unpublished_requires_note(self) -> None:
        """Unpublished must require note field."""
        reqs = FieldRequirements.get_requirements(EntryType.UNPUBLISHED)
        assert "note" in reqs["required"]
        assert "author" in reqs["required"]
        assert "title" in reqs["required"]

    def test_mastersthesis_vs_phdthesis_requirements(self) -> None:
        """Master's and PhD thesis have identical requirements."""
        masters_reqs = FieldRequirements.get_requirements(EntryType.MASTERSTHESIS)
        phd_reqs = FieldRequirements.get_requirements(EntryType.PHDTHESIS)

        assert masters_reqs["required"] == phd_reqs["required"]
        assert masters_reqs["required"] == {"author", "title", "school", "year"}

    def test_proceedings_does_not_require_author(self) -> None:
        """Proceedings should not require author field."""
        reqs = FieldRequirements.get_requirements(EntryType.PROCEEDINGS)
        assert "author" not in reqs["required"]
        assert "title" in reqs["required"]
        assert "year" in reqs["required"]

    def test_optional_fields_include_modern_fields(self) -> None:
        """Optional fields should include modern fields like DOI, URL."""
        reqs = FieldRequirements.get_requirements(EntryType.ARTICLE)
        optional = reqs["optional"]

        # Modern fields should be available as optional
        assert "doi" in optional
        assert "url" in optional

    def test_unknown_entry_type_returns_defaults(self) -> None:
        """Unknown entry types should return safe defaults."""

        # Create a fake entry type
        class FakeType:
            value = "fake_type"

        reqs = FieldRequirements.get_requirements(FakeType)  # type: ignore
        assert reqs["required"] == set()
        assert reqs["optional"] == ALL_FIELDS

    def test_all_standard_types_have_requirements(self) -> None:
        """All standard entry types must have defined requirements."""
        for entry_type in EntryType:
            reqs = FieldRequirements.get_requirements(entry_type)
            assert isinstance(reqs, dict)
            assert "required" in reqs
            assert "optional" in reqs
            assert isinstance(reqs["required"], set)
            assert isinstance(reqs["optional"], set)


class TestFieldCategories:
    """Test field categorization and definitions."""

    def test_standard_fields_from_tamethebeast(self) -> None:
        """Standard fields must match TameTheBeast manual."""
        expected_standard = {
            "address",
            "author",
            "booktitle",
            "chapter",
            "crossref",
            "edition",
            "editor",
            "howpublished",
            "institution",
            "journal",
            "key",
            "month",
            "note",
            "number",
            "organization",
            "pages",
            "publisher",
            "school",
            "series",
            "title",
            "type",
            "volume",
            "year",
        }

        assert STANDARD_FIELDS == expected_standard

    def test_modern_fields_include_identifiers(self) -> None:
        """Modern fields must include DOI, URL, ISBN, ISSN."""
        identifiers = {"doi", "url", "isbn", "issn"}
        assert identifiers.issubset(MODERN_FIELDS)

    def test_modern_fields_include_arxiv_support(self) -> None:
        """Modern fields must support arXiv entries."""
        arxiv_fields = {"eprint", "archiveprefix", "primaryclass"}
        assert arxiv_fields.issubset(MODERN_FIELDS)

    def test_compatibility_fields_for_tools(self) -> None:
        """Compatibility fields for various BibTeX tools."""
        tool_fields = {"groups", "owner", "timestamp", "keywords"}
        for field in tool_fields:
            assert field in ALL_FIELDS

    def test_all_fields_is_union_of_categories(self) -> None:
        """ALL_FIELDS must be the union of all categories."""
        combined = STANDARD_FIELDS | MODERN_FIELDS | COMPAT_FIELDS
        assert ALL_FIELDS == combined

    def test_no_field_duplication_across_categories(self) -> None:
        """Fields should not be duplicated across categories."""
        # Standard and modern should not overlap
        assert STANDARD_FIELDS.isdisjoint(MODERN_FIELDS)

        # Keywords might be in both modern and compat, that's ok
        # But most fields should be unique
        overlap = STANDARD_FIELDS & COMPAT_FIELDS
        assert len(overlap) == 0

    def test_field_names_are_lowercase(self) -> None:
        """All field names must be lowercase."""
        for field in ALL_FIELDS:
            assert field == field.lower(), f"Field '{field}' is not lowercase"

    def test_special_field_type_vs_type_(self) -> None:
        """The 'type' field requires special handling due to Python keyword."""
        # This is handled in the model with type_
        assert "type" in STANDARD_FIELDS

    def test_month_field_is_standard(self) -> None:
        """Month field must be in standard fields."""
        assert "month" in STANDARD_FIELDS

    def test_crossref_field_is_standard(self) -> None:
        """Crossref field must be in standard fields for inheritance."""
        assert "crossref" in STANDARD_FIELDS
