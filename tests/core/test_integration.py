"""Integration tests for the core module.

This module tests complete workflows and BibTeX compliance
across all core components working together.
"""

from typing import Any

from bibmgr.core.bibtex import BibtexDecoder, BibtexEncoder
from bibmgr.core.builders import CollectionBuilder, EntryBuilder
from bibmgr.core.crossref import CrossRefResolver
from bibmgr.core.duplicates import DuplicateDetector
from bibmgr.core.fields import EntryType, FieldRequirements
from bibmgr.core.models import Entry
from bibmgr.core.sorting import LabelGenerator, SortKeyGenerator
from bibmgr.core.strings import StringRegistry
from bibmgr.core.validators import ValidatorRegistry


class TestFullWorkflow:
    """Test complete workflows using all components."""

    def test_parse_validate_encode_cycle(self) -> None:
        """Full cycle: parse → validate → modify → encode."""
        # Original BibTeX
        original_bibtex = """@article{knuth1984,
    author = {Donald E. Knuth},
    title = {The {TeX}book},
    journal = {Computers \\& Typesetting},
    year = {1984},
    volume = {A},
    publisher = {Addison-Wesley}
}

@inproceedings{lamport1994,
    author = {Leslie Lamport},
    title = {{LaTeX}: A Document Preparation System},
    booktitle = {Conference Proceedings},
    year = {1994},
    pages = {1--10}
}"""

        # 1. Parse
        entries_data = BibtexDecoder.decode(original_bibtex)
        assert len(entries_data) == 2

        # 2. Create Entry objects
        entries = [Entry.from_dict(data) for data in entries_data]

        # 3. Validate
        validator = ValidatorRegistry()
        for entry in entries:
            errors = validator.validate(entry)
            assert len(errors) == 0  # Should be valid

        # 4. Modify using builder
        modified = (
            EntryBuilder.from_entry(entries[0])
            .doi("10.1234/test")
            .keywords(["typesetting", "tex"])
            .build()
        )
        entries[0] = modified

        # 5. Encode back
        encoder = BibtexEncoder()
        encoded = "\n\n".join(encoder.encode_entry(e) for e in entries)

        # 6. Verify round-trip
        reparsed = BibtexDecoder.decode(encoded)
        assert len(reparsed) == 2
        assert reparsed[0]["doi"] == "10.1234/test"
        assert reparsed[0]["keywords"] == ["typesetting", "tex"]

    def test_crossref_resolution_workflow(self) -> None:
        """Workflow with cross-references."""
        # Create a book and chapters
        book = Entry(
            key="aibook2024",
            type=EntryType.BOOK,
            editor="AI Editors",
            title="Advances in AI",
            publisher="AI Press",
            year=2024,
            series="AI Series",
            volume="42",
        )

        chapters = [
            Entry(
                key="ch1",
                type=EntryType.INBOOK,
                author="Chapter 1 Author",
                title="Introduction to AI",
                chapter="1",
                pages="1--20",
                crossref="aibook2024",
            ),
            Entry(
                key="ch2",
                type=EntryType.INBOOK,
                author="Chapter 2 Author",
                title="Machine Learning Basics",
                chapter="2",
                pages="21--50",
                crossref="aibook2024",
            ),
        ]

        # Create entries dict
        all_entries = {"aibook2024": book}
        for ch in chapters:
            all_entries[ch.key] = ch

        # Resolve cross-references
        resolver = CrossRefResolver(all_entries)
        resolved_chapters = [resolver.resolve_entry(ch) for ch in chapters]

        # Verify inheritance
        for ch in resolved_chapters:
            assert ch.publisher == "AI Press"
            assert ch.year == 2024
            assert ch.series == "AI Series"

        # Generate sort keys
        sort_gen = SortKeyGenerator(style="plain")
        sorted_entries = sorted(
            [book] + resolved_chapters, key=lambda e: sort_gen.generate(e)
        )

        # Book should come after chapters (BibTeX order)
        assert sorted_entries[-1].key == "aibook2024"

    def test_duplicate_detection_workflow(self, sample_entries: list[Entry]) -> None:
        """Workflow for finding and handling duplicates."""
        # Create some duplicates
        entries = list(sample_entries)

        # Add DOI duplicate
        dup1 = EntryBuilder.from_entry(entries[0]).key("dup1").build()
        entries.append(dup1)

        # Add title/author/year duplicate
        dup2 = (
            EntryBuilder()
            .key("dup2")
            .type(entries[1].type)
            .author(entries[1].author)
            .title(entries[1].title)
            .journal("Different Journal")
            .year(entries[1].year)
            .build()
        )
        entries.append(dup2)

        # Detect duplicates
        detector = DuplicateDetector(entries)
        duplicate_groups = detector.find_duplicates()

        assert len(duplicate_groups) >= 1

        # Handle duplicates - merge or mark
        for group in duplicate_groups:
            # Could merge fields, prefer most complete entry
            complete = max(
                group, key=lambda e: len([v for v in e.to_dict().values() if v])
            )
            # Mark others as duplicates (in a real implementation,
            # we'd create new entries with updated tags)
            for entry in group:
                if entry != complete:
                    # Entry is immutable, so we'd need to rebuild it
                    pass

    def test_string_expansion_workflow(self) -> None:
        """Workflow with string abbreviations."""
        # BibTeX with @string definitions
        bibtex = """@string{LNCS = "Lecture Notes in Computer Science"}
@string{IEEE = "Institute of Electrical and Electronics Engineers"}

@article{test2024,
    author = {Test Author},
    title = {Test Paper},
    journal = IEEE # " Transactions on Software Engineering",
    year = {2024},
    month = jan,
    series = LNCS
}"""

        # Parse string definitions
        registry = StringRegistry()
        lines = bibtex.split("\n")
        for line in lines:
            if line.strip().startswith("@string"):
                result = registry.parse_string_definition(line)
                if result:
                    key, value = result
                    registry.add_string(key, value)

        # Parse entries
        entries_data = BibtexDecoder.decode(bibtex)
        assert len(entries_data) == 1

        # Expand strings in fields
        entry_data = entries_data[0]
        for field, value in entry_data.items():
            if isinstance(value, str):
                entry_data[field] = registry.expand(value)

        # Create entry
        entry = Entry.from_dict(entry_data)

        # Verify expansion
        assert "Institute of Electrical" in entry.journal
        assert entry.series == "Lecture Notes in Computer Science"
        assert entry.month == "January"  # Predefined month expanded

    def test_collection_building_workflow(self, sample_entries: list[Entry]) -> None:
        """Workflow for building and organizing collections."""
        # Create hierarchy
        root = CollectionBuilder().name("Library").build()

        cs = CollectionBuilder().name("Computer Science").parent(root).build()

        # Smart collections
        recent = (
            CollectionBuilder()
            .name("Recent Papers")
            .parent(cs)
            .smart_filter("year", ">=", 2020)
            .build()
        )

        ml = (
            CollectionBuilder()
            .name("Machine Learning")
            .parent(cs)
            .smart_filter("keywords", "contains", "machine learning")
            .build()
        )

        # Manual collection
        (
            CollectionBuilder()
            .name("Favorites")
            .parent(root)
            .add_entries(sample_entries[:3])
            .build()
        )

        # Test collection operations
        assert len(root.children) == 2
        assert len(cs.children) == 2

        # Test smart collection matching
        for entry in sample_entries:
            if entry.year and entry.year >= 2020:
                assert recent.matches_entry(entry)

            if entry.keywords and any(
                "machine learning" in k.lower() for k in entry.keywords
            ):
                assert ml.matches_entry(entry)

    def test_bibliography_generation_workflow(self) -> None:
        """Complete bibliography generation workflow."""
        # Create entries
        entries = [
            Entry(
                key="smith2023",
                type=EntryType.ARTICLE,
                author="John Smith and Jane Doe",
                title="Advanced Machine Learning Techniques",
                journal="Journal of AI Research",
                year=2023,
                volume="42",
                pages="100--120",
                doi="10.1234/jair.2023.42",
            ),
            Entry(
                key="doe2024",
                type=EntryType.INPROCEEDINGS,
                author="Jane Doe",
                title="Neural Networks for NLP",
                booktitle="Proceedings of ACL 2024",
                year=2024,
                pages="50--65",
            ),
            Entry(
                key="brown2023",
                type=EntryType.BOOK,
                author="Alice Brown",
                title="Deep Learning Fundamentals",
                publisher="Tech Press",
                year=2023,
                edition="2nd",
            ),
        ]

        # Generate sort keys and labels
        sort_gen = SortKeyGenerator(style="plain")
        label_gen = LabelGenerator(style="alpha")

        # Process entries
        processed = []
        for entry in entries:
            sort_key = sort_gen.generate(entry)
            label = label_gen.generate(entry)
            processed.append((sort_key, label, entry))

        # Sort bibliography
        processed.sort(key=lambda x: x[0])

        # Generate BibTeX
        encoder = BibtexEncoder()
        bibliography = []

        for _, label, entry in processed:
            bibtex = encoder.encode_entry(entry)
            bibliography.append(f"% Label: [{label}]\n{bibtex}")

        full_bib = "\n\n".join(bibliography)

        # Verify output
        assert "[Bro23]" in full_bib  # Brown 2023
        assert "[Doe24]" in full_bib  # Doe 2024
        assert "[SD23]" in full_bib  # Smith & Doe 2023

    def test_validation_and_correction_workflow(self) -> None:
        """Workflow for validating and correcting entries."""
        # Create entries with various issues
        entries = [
            # Missing required field
            Entry(
                key="missing",
                type=EntryType.ARTICLE,
                author="Author",
                title="Title",
                # Missing journal and year
            ),
            # Invalid DOI format
            Entry(
                key="baddoi",
                type=EntryType.ARTICLE,
                author="Author",
                title="Title",
                journal="Journal",
                year=2024,
                doi="not-a-valid-doi",
            ),
            # Invalid characters in key
            Entry(
                key="bad key!",
                type=EntryType.MISC,
                title="Title",
            ),
        ]

        validator = ValidatorRegistry()

        # Validate and collect errors
        all_errors = {}
        for entry in entries:
            errors = validator.validate(entry)
            if errors:
                all_errors[entry.key] = errors

        assert len(all_errors) == 3

        # Attempt corrections
        corrected = []
        for entry in entries:
            if entry.key in all_errors:
                # Use builder to fix
                builder = EntryBuilder.from_entry(entry)

                # Fix key
                if any(
                    "Invalid entry key" in e.message
                    or "invalid characters" in e.message
                    for e in all_errors.get(entry.key, [])
                ):
                    builder.key(entry.key.replace(" ", "_").replace("!", ""))

                # Add missing fields
                if entry.type == EntryType.ARTICLE:
                    if not entry.journal:
                        builder.journal("Unknown Journal")
                    if not entry.year:
                        builder.year(2024)

                # Fix DOI
                if entry.doi and not entry.doi.startswith("10."):
                    builder.clear_field("doi")

                corrected.append(builder.build())
            else:
                corrected.append(entry)

        # Re-validate
        for i, entry in enumerate(corrected):
            errors = validator.validate(entry)
            # Should have fewer errors than the original
            original_key = entries[i].key
            assert len(errors) < len(all_errors.get(original_key, []))


class TestBibTeXCompliance:
    """Test compliance with BibTeX standards from TameTheBeast."""

    def test_entry_type_requirements(self) -> None:
        """All entry types have correct required fields."""
        validator = ValidatorRegistry()

        for entry_type in EntryType:
            # Create minimal entry
            entry = Entry(
                key="test",
                type=entry_type,
            )

            errors = validator.validate(entry)

            # Should have errors for missing required fields
            requirements = FieldRequirements.REQUIREMENTS.get(entry_type, {})
            required = requirements.get("required", set())
            if required:
                assert len(errors) > 0

                # Check all required fields reported
                missing_fields = {
                    e.field for e in errors if "required" in e.message.lower()
                }
                # Handle alternative requirements
                for req_set in required:
                    if isinstance(req_set, tuple):
                        # At least one from the tuple should be reported
                        assert any(f in missing_fields for f in req_set)

    def test_special_character_handling(
        self, bibtex_special_chars: dict[str, str]
    ) -> None:
        """Special characters handled correctly."""
        encoder = BibtexEncoder()

        # Test each special character
        for char, expected in bibtex_special_chars.items():
            # Create entry with special char
            entry = Entry(
                key="test",
                type=EntryType.MISC,
                title=f"Title with {char} character",
                note=f"Note with {char} too",
            )

            encoded = encoder.encode_entry(entry)

            # Should be escaped
            assert expected in encoded

            # Should round-trip correctly
            decoded = BibtexDecoder.decode(encoded)
            assert len(decoded) == 1
            # After decoding, might have the escaped version

    def test_name_format_compliance(self) -> None:
        """Name formats comply with BibTeX rules."""
        from bibmgr.core.names import NameParser

        parser = NameParser()

        # Test three BibTeX name formats
        test_cases = [
            # Format 0: First von Last
            ("Ludwig van Beethoven", "Ludwig", "van", "Beethoven", ""),
            # Format 1: von Last, First
            ("van Beethoven, Ludwig", "Ludwig", "van", "Beethoven", ""),
            # Format 2: von Last, Jr, First
            ("Smith, Jr., John", "John", "", "Smith", "Jr."),
        ]

        for name, first, von, last, jr in test_cases:
            parsed = parser.parse(name)
            assert " ".join(parsed.first) == first
            assert " ".join(parsed.von) == von
            assert " ".join(parsed.last) == last
            assert " ".join(parsed.jr) == jr

    def test_month_abbreviations(self) -> None:
        """Month abbreviations work correctly."""
        registry = StringRegistry()

        # All months should be predefined
        months = [
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
        ]

        for month in months:
            expanded = registry.expand(month)
            assert expanded != month  # Should expand
            assert expanded[0].isupper()  # Capitalized

    def test_crossref_ordering_constraint(self) -> None:
        """Cross-referenced entries must come after citing entries."""
        entries = {
            "proceedings": Entry(
                key="proceedings",
                type=EntryType.PROCEEDINGS,
                title="Conference 2024",
                year=2024,
            ),
            "paper1": Entry(
                key="paper1",
                type=EntryType.INPROCEEDINGS,
                author="Author",
                title="Paper",
                crossref="proceedings",
            ),
        }

        resolver = CrossRefResolver(entries)
        violations = resolver.validate_order()

        # Current order violates constraint
        assert len(violations) > 0

        # Reverse order should be valid
        reversed_entries = {k: entries[k] for k in reversed(entries.keys())}
        resolver2 = CrossRefResolver(reversed_entries)
        violations2 = resolver2.validate_order()
        assert len(violations2) == 0

    def test_field_value_formats(self) -> None:
        """Field values formatted correctly."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            author="Author Name",
            title="Article Title with {Protected} Text",
            journal="Journal Name",
            year=2024,
            pages="10--20",  # En-dash
            month="jan",  # Abbreviation
        )

        encoder = BibtexEncoder()
        encoded = encoder.encode_entry(entry)

        # Check formatting
        assert "pages = {10--20}" in encoded
        assert "month = jan" in encoded  # No braces for month abbrev
        assert "{Protected}" in encoded  # Preserved protection

    def test_entry_key_constraints(self) -> None:
        """Entry keys follow BibTeX rules."""
        from bibmgr.core.validators import EntryKeyValidator

        validator = EntryKeyValidator()

        # Valid keys
        valid_keys = ["simple", "with123", "with_underscore", "MixedCase", "with-dash"]
        for key in valid_keys:
            errors = validator.validate(Entry(key=key, type=EntryType.MISC))
            assert len(errors) == 0

        # Invalid keys
        invalid_keys = ["with space", "with.dot", ""]
        for key in invalid_keys:
            errors = validator.validate(Entry(key=key, type=EntryType.MISC))
            assert len(errors) > 0

        # Keys starting with digits are now valid (for DOI-based keys)
        errors = validator.validate(Entry(key="123start", type=EntryType.MISC))
        assert len(errors) == 0

    def test_title_case_protection(self) -> None:
        """Title case changes respect brace protection."""
        from bibmgr.core.titles import TitleProcessor

        # Test cases
        cases = [
            ("the {TCP/IP} protocol", "t", "The {TCP/IP} protocol"),
            ("the {TCP/IP} protocol", "l", "the {TCP/IP} protocol"),
            ("{IEEE} conference", "t", "{IEEE} conference"),
            ("machine {Learning} basics", "t", "Machine {Learning} basics"),
        ]

        for original, mode, expected in cases:
            result = TitleProcessor.change_case(original, mode)
            assert result == expected

    def test_brace_depth_handling(self) -> None:
        """Nested braces handled correctly."""
        entry = Entry(
            key="test",
            type=EntryType.MISC,
            title="Title with {Nested {Braces} Here}",
            note="Note with {Multiple {Levels {Deep}}}",
        )

        encoder = BibtexEncoder()
        encoded = encoder.encode_entry(entry)

        # Braces should be preserved
        assert "{Nested {Braces} Here}" in encoded
        assert "{Multiple {Levels {Deep}}}" in encoded

        # Should decode correctly
        decoded = BibtexDecoder.decode(encoded)
        assert decoded[0]["title"] == "Title with {Nested {Braces} Here}"

    def test_comprehensive_bibliography(
        self, crossref_entries: list[dict[str, Any]]
    ) -> None:
        """Test with a comprehensive bibliography."""
        # Parse all entries
        entries = [Entry.from_dict(data) for data in crossref_entries]
        entries_dict = {e.key: e for e in entries}

        # Validate all
        validator = ValidatorRegistry()
        for entry in entries:
            errors = validator.validate(entry)
            # Should be valid or have known issues
            for error in errors:
                # Cross-references might not resolve yet, or fields might be missing that will be inherited
                has_crossref = hasattr(entry, "crossref") and entry.crossref
                if has_crossref:
                    # For entries with crossref, we allow missing fields that can be inherited
                    # or consistency errors that will be resolved after inheritance
                    inheritable_fields = {
                        "year",
                        "publisher",
                        "editor",
                        "series",
                        "volume",
                        "booktitle",
                    }
                    is_crossref_related = (
                        error.field and "crossref" in error.field.lower()
                    ) or "Cross" in error.message
                    is_inheritable = error.field in inheritable_fields
                    is_consistency_issue = (
                        error.severity == "info" or error.severity == "warning"
                    ) and (
                        "without journal or book" in error.message
                        or "specified without" in error.message
                    )
                    assert is_crossref_related or is_inheritable or is_consistency_issue
                else:
                    # For entries without crossref, any error is a real problem
                    assert (
                        error.field and "crossref" in error.field.lower()
                    ) or "Cross" in error.message

        # Resolve cross-references
        resolver = CrossRefResolver(entries_dict)
        resolved = [resolver.resolve_entry(e) for e in entries]

        # Generate bibliography
        sort_gen = SortKeyGenerator(style="alpha")
        label_gen = LabelGenerator(style="alpha")
        encoder = BibtexEncoder()

        bibliography = []
        for entry in sorted(resolved, key=lambda e: sort_gen.generate(e)):
            label = label_gen.generate(entry)
            bibtex = encoder.encode_entry(entry)
            bibliography.append((label, bibtex))

        # Should have valid bibliography
        assert len(bibliography) == len(entries)

        # Check labels are unique
        labels = [item[0] for item in bibliography]
        assert len(labels) == len(set(labels))
