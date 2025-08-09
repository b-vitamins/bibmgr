"""Tests for BibTeX cross-reference resolution.

This module tests cross-reference handling, field inheritance,
and proper ordering constraints according to BibTeX rules.
"""

from typing import Any

from bibmgr.core.crossref import CrossRefResolver
from bibmgr.core.fields import EntryType
from bibmgr.core.models import Entry


class TestCrossRefResolver:
    """Test cross-reference resolution functionality."""

    def test_basic_crossref_resolution(
        self, crossref_entries: list[dict[str, Any]]
    ) -> None:
        """Basic cross-reference resolution."""
        # Create entries
        entries_dict = {}
        for data in crossref_entries:
            entry = Entry.from_dict(data)
            entries_dict[entry.key] = entry

        resolver = CrossRefResolver(entries_dict)

        # Resolve chapter1
        chapter1 = entries_dict["chapter1"]
        resolved = resolver.resolve_entry(chapter1)

        # Should inherit from parent
        assert resolved.publisher == "MIT Press"
        assert resolved.year == 2024

        # Should keep own fields
        assert resolved.author == "Yann LeCun"
        assert resolved.title == "Introduction to Neural Networks"

    def test_min_crossrefs_threshold(self) -> None:
        """Parent inclusion based on crossref count."""
        book = Entry(
            key="mainbook",
            type=EntryType.BOOK,
            editor="Editor Name",
            title="Main Book",
            publisher="Publisher",
            year=2024,
        )

        # Create chapters that reference the book
        chapters = []
        for i in range(5):
            chapter = Entry(
                key=f"chapter{i}",
                type=EntryType.INBOOK,
                author=f"Author {i}",
                title=f"Chapter {i}",
                chapter=str(i),
                crossref="mainbook",
            )
            chapters.append(chapter)

        entries_dict = {"mainbook": book}
        for ch in chapters:
            entries_dict[ch.key] = ch

        # Default threshold is 2
        resolver = CrossRefResolver(entries_dict, min_crossrefs=2)

        # Book is referenced 5 times, should be included
        assert resolver.should_include_parent("mainbook")

        # With higher threshold
        resolver_high = CrossRefResolver(entries_dict, min_crossrefs=10)
        assert not resolver_high.should_include_parent("mainbook")

    def test_no_field_inheritance_if_present(self) -> None:
        """Fields already present in child should not be overridden."""
        parent = Entry(
            key="parent",
            type=EntryType.BOOK,
            editor="Parent Editor",
            title="Parent Title",
            publisher="Parent Publisher",
            year=2023,
            series="Parent Series",
        )

        child = Entry(
            key="child",
            type=EntryType.INBOOK,
            author="Child Author",
            title="Child Title",
            chapter="1",
            publisher="Child Publisher",  # Has own publisher
            year=2024,  # Has own year
            crossref="parent",
        )

        entries_dict = {"parent": parent, "child": child}
        resolver = CrossRefResolver(entries_dict)

        resolved = resolver.resolve_entry(child)

        # Should keep child's values
        assert resolved.publisher == "Child Publisher"
        assert resolved.year == 2024

        # Should inherit missing fields
        assert resolved.editor == "Parent Editor"
        assert resolved.series == "Parent Series"

    def test_inheritable_fields_list(self) -> None:
        """Only specific fields should be inheritable."""
        parent = Entry(
            key="parent",
            type=EntryType.PROCEEDINGS,
            editor="Conference Editors",
            title="Conference Proceedings",
            year=2024,
            publisher="ACM",
            address="New York",
            month="jul",
            organization="ACM",
            volume="42",
            series="ICSE",
            # Non-inheritable fields
            doi="10.1145/12345",
            isbn="978-0-123456-78-9",
            url="https://example.com",
        )

        child = Entry(
            key="child",
            type=EntryType.INPROCEEDINGS,
            author="Paper Author",
            title="Paper Title",
            crossref="parent",
        )

        entries_dict = {"parent": parent, "child": child}
        resolver = CrossRefResolver(entries_dict)

        resolved = resolver.resolve_entry(child)

        # Should inherit these
        assert resolved.year == 2024
        assert resolved.publisher == "ACM"
        assert resolved.editor == "Conference Editors"
        assert resolved.booktitle == "Conference Proceedings"  # Special case

        # Should NOT inherit these
        assert resolved.doi is None
        assert resolved.isbn is None
        assert resolved.url is None

    def test_booktitle_special_handling(self) -> None:
        """Parent's title becomes child's booktitle for certain types."""
        proceedings = Entry(
            key="icse2024",
            type=EntryType.PROCEEDINGS,
            title="Proceedings of ICSE 2024",
            year=2024,
            editor="Conference Chairs",
        )

        paper = Entry(
            key="mypaper",
            type=EntryType.INPROCEEDINGS,
            author="Author Name",
            title="My Paper Title",
            crossref="icse2024",
        )

        entries_dict = {"icse2024": proceedings, "mypaper": paper}
        resolver = CrossRefResolver(entries_dict)

        resolved = resolver.resolve_entry(paper)

        # Parent's title should become child's booktitle
        assert resolved.booktitle == "Proceedings of ICSE 2024"
        assert resolved.title == "My Paper Title"  # Keep own title

    def test_missing_crossref_parent(self) -> None:
        """Handle missing cross-referenced parent gracefully."""
        entry = Entry(
            key="orphan",
            type=EntryType.INBOOK,
            author="Author",
            title="Chapter Title",
            chapter="5",
            crossref="nonexistent",
        )

        resolver = CrossRefResolver({"orphan": entry})
        resolved = resolver.resolve_entry(entry)

        # Should return entry unchanged
        assert resolved == entry

    def test_no_crossref_returns_same(self) -> None:
        """Entry without crossref returns unchanged."""
        entry = Entry(
            key="standalone",
            type=EntryType.ARTICLE,
            author="Author",
            title="Title",
            journal="Journal",
            year=2024,
        )

        resolver = CrossRefResolver({"standalone": entry})
        resolved = resolver.resolve_entry(entry)

        # Should be same object (no changes needed)
        assert resolved is entry

    def test_crossref_count_accuracy(self) -> None:
        """Cross-reference counting should be accurate."""
        book = Entry(key="book1", type=EntryType.BOOK, title="Book", year=2024)

        entries = {"book1": book}

        # Add some chapters
        for i in range(3):
            entries[f"ch{i}"] = Entry(
                key=f"ch{i}",
                type=EntryType.INBOOK,
                title=f"Chapter {i}",
                crossref="book1",
            )

        # Add entry with different crossref
        entries["other"] = Entry(
            key="other",
            type=EntryType.INBOOK,
            title="Other",
            crossref="book2",
        )

        resolver = CrossRefResolver(entries)

        # Should count correctly
        assert resolver.crossref_counts["book1"] == 3
        assert resolver.crossref_counts.get("book2", 0) == 1


class TestFieldInheritance:
    """Test field inheritance rules."""

    def test_inheritance_rules_by_type(self) -> None:
        """Different entry types have different inheritance rules."""
        book = Entry(
            key="book",
            type=EntryType.BOOK,
            editor="Book Editor",
            title="Book Title",
            publisher="Publisher",
            year=2024,
            series="{Lecture Notes in Computer Science}",
            volume="1234",
        )

        # INBOOK inherits from BOOK
        inbook = Entry(
            key="chapter",
            type=EntryType.INBOOK,
            author="Chapter Author",
            title="Chapter Title",
            chapter="5",
            crossref="book",
        )

        entries = {"book": book, "chapter": inbook}
        resolver = CrossRefResolver(entries)
        resolved = resolver.resolve_entry(inbook)

        # Should inherit these fields
        assert resolved.publisher == "Publisher"
        assert resolved.year == 2024
        assert resolved.series == "{Lecture Notes in Computer Science}"
        assert resolved.editor == "Book Editor"

    def test_incollection_inheritance(self) -> None:
        """INCOLLECTION inherits from BOOK differently."""
        book = Entry(
            key="collected",
            type=EntryType.BOOK,
            editor="Collection Editor",
            title="Essay Collection",
            publisher="Publisher",
            year=2024,
            address="London",
        )

        essay = Entry(
            key="essay1",
            type=EntryType.INCOLLECTION,
            author="Essay Author",
            title="Essay Title",
            pages="45--67",
            crossref="collected",
        )

        entries = {"collected": book, "essay1": essay}
        resolver = CrossRefResolver(entries)
        resolved = resolver.resolve_entry(essay)

        # Should get booktitle from parent's title
        assert resolved.booktitle == "Essay Collection"
        assert resolved.editor == "Collection Editor"
        assert resolved.publisher == "Publisher"

    def test_inproceedings_from_proceedings(self) -> None:
        """INPROCEEDINGS inherits from PROCEEDINGS."""
        proceedings = Entry(
            key="conf2024",
            type=EntryType.PROCEEDINGS,
            title="2024 International Conference",
            editor="Program Committee",
            year=2024,
            organization="IEEE",
            publisher="IEEE Press",
            address="Paris",
        )

        paper = Entry(
            key="paper1",
            type=EntryType.INPROCEEDINGS,
            author="Paper Authors",
            title="Our Paper",
            pages="123--134",
            crossref="conf2024",
        )

        entries = {"conf2024": proceedings, "paper1": paper}
        resolver = CrossRefResolver(entries)
        resolved = resolver.resolve_entry(paper)

        # Check inheritance
        assert resolved.booktitle == "2024 International Conference"
        assert resolved.year == 2024
        assert resolved.organization == "IEEE"
        assert resolved.publisher == "IEEE Press"

    def test_field_combination_not_override(self) -> None:
        """Some fields might need special combination logic."""
        parent = Entry(
            key="parent",
            type=EntryType.BOOK,
            editor="Main Editor",
            title="Book Title",
            publisher="Publisher",
            year=2024,
            note="Book note",
        )

        child = Entry(
            key="child",
            type=EntryType.INBOOK,
            author="Chapter Author",
            title="Chapter Title",
            chapter="3",
            note="Chapter note",  # Has own note
            crossref="parent",
        )

        entries = {"parent": parent, "child": child}
        resolver = CrossRefResolver(entries)
        resolved = resolver.resolve_entry(child)

        # Should keep child's note (no combination)
        assert resolved.note == "Chapter note"

    def test_empty_parent_fields_not_inherited(self) -> None:
        """Empty/None parent fields should not override child fields."""
        parent = Entry(
            key="parent",
            type=EntryType.BOOK,
            title="Book",
            publisher="",  # Empty
            year=2024,
            series=None,  # None
        )

        child = Entry(
            key="child",
            type=EntryType.INBOOK,
            title="Chapter",
            chapter="1",
            publisher="Child Publisher",
            series="Child Series",
            crossref="parent",
        )

        entries = {"parent": parent, "child": child}
        resolver = CrossRefResolver(entries)
        resolved = resolver.resolve_entry(child)

        # Should keep child's non-empty values
        assert resolved.publisher == "Child Publisher"
        assert resolved.series == "Child Series"


class TestCrossRefOrdering:
    """Test cross-reference ordering constraints."""

    def test_validate_order_detects_forward_refs(self) -> None:
        """Detect when target comes before citing entry (wrong order)."""
        # In BibTeX, entries with crossref must come BEFORE their targets
        # This test has WRONG order: target comes first
        entries = {
            "proceedings1": Entry(
                key="proceedings1",
                type=EntryType.PROCEEDINGS,
                title="Conference",
                year=2024,
            ),
            "paper1": Entry(
                key="paper1",
                type=EntryType.INPROCEEDINGS,
                author="Author",
                title="Paper",
                crossref="proceedings1",  # Backward reference (wrong)
            ),
        }

        resolver = CrossRefResolver(entries)
        violations = resolver.validate_order()

        # Should detect the violation
        assert len(violations) == 1
        assert violations[0] == ("paper1", "proceedings1")

    def test_validate_order_accepts_backward_refs(self) -> None:
        """Correct order: citing entry before target."""
        # In BibTeX, entries with crossref must come BEFORE their targets
        # This test has CORRECT order: citing entry first, target after
        entries = {
            "paper1": Entry(
                key="paper1",
                type=EntryType.INPROCEEDINGS,
                author="Author",
                title="Paper",
                crossref="proceedings1",  # Forward reference (correct)
            ),
            "proceedings1": Entry(
                key="proceedings1",
                type=EntryType.PROCEEDINGS,
                title="Conference",
                year=2024,
            ),
        }

        resolver = CrossRefResolver(entries)
        violations = resolver.validate_order()

        # Should have no violations
        assert len(violations) == 0

    def test_multiple_papers_same_proceedings(self) -> None:
        """Multiple papers can reference same proceedings."""
        entries = {
            "paper1": Entry(
                key="paper1",
                type=EntryType.INPROCEEDINGS,
                title="Paper 1",
                crossref="conf",
            ),
            "paper2": Entry(
                key="paper2",
                type=EntryType.INPROCEEDINGS,
                title="Paper 2",
                crossref="conf",
            ),
            "conf": Entry(
                key="conf",
                type=EntryType.PROCEEDINGS,
                title="Conference",
                year=2024,
            ),
        }

        resolver = CrossRefResolver(entries)
        violations = resolver.validate_order()

        # Both are correct order (papers before proceedings)
        assert len(violations) == 0

    def test_deep_crossref_chain(self) -> None:
        """Handle chain of cross-references."""
        # BibTeX doesn't support transitive crossrefs, but test ordering
        entries = {
            "a": Entry(key="a", type=EntryType.MISC, crossref="b"),
            "b": Entry(key="b", type=EntryType.MISC, crossref="c"),
            "c": Entry(key="c", type=EntryType.MISC, title="Root"),
        }

        resolver = CrossRefResolver(entries)
        violations = resolver.validate_order()

        # All are correct order (entries with crossref before targets)
        assert len(violations) == 0

    def test_self_reference_detection(self) -> None:
        """Entry should not reference itself."""
        entries = {
            "self": Entry(
                key="self",
                type=EntryType.MISC,
                title="Self Reference",
                crossref="self",  # Self-reference!
            ),
        }

        resolver = CrossRefResolver(entries)

        # Resolve should handle gracefully
        resolved = resolver.resolve_entry(entries["self"])
        assert resolved == entries["self"]  # No changes

    def test_missing_crossref_in_validation(self) -> None:
        """Missing crossref target in order validation."""
        entries = {
            "orphan": Entry(
                key="orphan",
                type=EntryType.INBOOK,
                title="Orphaned Chapter",
                crossref="nonexistent",
            ),
        }

        resolver = CrossRefResolver(entries)
        violations = resolver.validate_order()

        # Should detect reference to non-existent entry
        assert len(violations) == 1
        assert violations[0] == ("orphan", "nonexistent")

    def test_complex_bibliography_ordering(
        self, crossref_entries: list[dict[str, Any]]
    ) -> None:
        """Test ordering in a realistic bibliography."""
        # Create entries dict maintaining order
        entries = {}
        for data in crossref_entries:
            entry = Entry.from_dict(data)
            entries[entry.key] = entry

        resolver = CrossRefResolver(entries)
        violations = resolver.validate_order()

        # chapter1 and chapter2 both reference mlbook2024
        # mlbook2024 comes first in the fixture, which is WRONG order
        # Chapters (with crossref) should come before the book they reference
        assert len(violations) == 2
        assert ("chapter1", "mlbook2024") in violations
        assert ("chapter2", "mlbook2024") in violations

    def test_get_proper_order(self) -> None:
        """Get correct ordering for entries with crossrefs."""
        {
            "ch1": Entry(key="ch1", type=EntryType.INBOOK, crossref="book"),
            "ch2": Entry(key="ch2", type=EntryType.INBOOK, crossref="book"),
            "book": Entry(key="book", type=EntryType.BOOK, title="Book"),
            "article": Entry(key="article", type=EntryType.ARTICLE, title="Article"),
        }

        # A method to get proper order would ensure:
        # 1. Entries without crossref can go anywhere
        # 2. Cross-referenced entries come after all entries that reference them

        # This is a topological sort problem
        # Expected order: book must come after ch1 and ch2
        # article can be anywhere
