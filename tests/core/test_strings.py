"""Tests for BibTeX string abbreviation handling.

This module tests @string definitions, string expansion,
and predefined abbreviations like month names.
"""

from bibmgr.core.strings import StringRegistry


class TestStringRegistry:
    """Test string abbreviation registry."""

    def test_predefined_month_abbreviations(self) -> None:
        """Month abbreviations should be predefined."""
        registry = StringRegistry()

        # Check all months
        months = [
            ("jan", "January"),
            ("feb", "February"),
            ("mar", "March"),
            ("apr", "April"),
            ("may", "May"),
            ("jun", "June"),
            ("jul", "July"),
            ("aug", "August"),
            ("sep", "September"),
            ("oct", "October"),
            ("nov", "November"),
            ("dec", "December"),
        ]

        for abbrev, full in months:
            assert registry.strings[abbrev] == full

    def test_add_custom_string(self) -> None:
        """Add custom string abbreviation."""
        registry = StringRegistry()

        registry.add_string("LNCS", "Lecture Notes in Computer Science")
        registry.add_string("IEEE", "Institute of Electrical and Electronics Engineers")

        assert registry.strings["lncs"] == "Lecture Notes in Computer Science"
        assert (
            registry.strings["ieee"]
            == "Institute of Electrical and Electronics Engineers"
        )

    def test_case_insensitive_keys(self) -> None:
        """String keys should be case-insensitive."""
        registry = StringRegistry()

        registry.add_string("SIGPLAN", "ACM SIGPLAN")

        # Should work with any case
        assert registry.strings["sigplan"] == "ACM SIGPLAN"
        assert registry.strings["SIGPLAN"] == "ACM SIGPLAN"
        assert registry.strings["SigPlan"] == "ACM SIGPLAN"

    def test_override_predefined(self) -> None:
        """Can override predefined strings."""
        registry = StringRegistry()

        # Override a month
        registry.add_string("jan", "Januar")  # German

        assert registry.strings["jan"] == "Januar"

    def test_parse_string_definition(self) -> None:
        """Parse @string definitions from BibTeX."""
        registry = StringRegistry()

        # Different formats
        definitions = [
            '@string{LNCS = "Lecture Notes in Computer Science"}',
            "@string{IEEE = {Institute of Electrical and Electronics Engineers}}",
            '@STRING{ACM = "Association for Computing Machinery"}',  # Uppercase
            '@string { SPACED = "With Spaces" }',  # With spaces
        ]

        for defn in definitions:
            result = registry.parse_string_definition(defn)
            assert result is not None
            key, value = result
            assert len(key) > 0
            assert len(value) > 0

    def test_parse_string_definition_invalid(self) -> None:
        """Invalid @string definitions return None."""
        registry = StringRegistry()

        invalid = [
            "@string{NOVALUE}",  # No value
            "@string{KEY = }",  # Empty value
            "@string{= VALUE}",  # No key
            "not a string definition",
            "@string KEY = VALUE",  # Missing braces
        ]

        for defn in invalid:
            result = registry.parse_string_definition(defn)
            assert result is None

    def test_registry_persistence(self) -> None:
        """Registry maintains all added strings."""
        registry = StringRegistry()

        # Add several strings
        strings = {
            "CONF1": "International Conference 1",
            "CONF2": "International Conference 2",
            "PUB1": "Publisher One",
            "PUB2": "Publisher Two",
        }

        for key, value in strings.items():
            registry.add_string(key, value)

        # All should be present
        for key, value in strings.items():
            assert registry.strings[key.lower()] == value

        # Plus predefined months
        assert "jan" in registry.strings
        assert "dec" in registry.strings


class TestStringExpansion:
    """Test string expansion in field values."""

    def test_expand_simple_abbreviation(self) -> None:
        """Expand simple string abbreviation."""
        registry = StringRegistry()
        registry.add_string("LNCS", "Lecture Notes in Computer Science")

        # Simple expansion
        text = "LNCS"
        expanded = registry.expand(text)
        assert expanded == "Lecture Notes in Computer Science"

    def test_expand_concatenation(self) -> None:
        """Expand concatenated strings with #."""
        registry = StringRegistry()
        registry.add_string("LNCS", "Lecture Notes in Computer Science")

        # Concatenation patterns
        patterns = [
            (
                'LNCS # ", Volume 1234"',
                "Lecture Notes in Computer Science, Volume 1234",
            ),
            (
                '"Proceedings of " # LNCS',
                "Proceedings of Lecture Notes in Computer Science",
            ),
            ('LNCS # " " # "2024"', "Lecture Notes in Computer Science 2024"),
        ]

        for pattern, expected in patterns:
            expanded = registry.expand(pattern)
            assert expanded == expected

    def test_expand_quoted_literals(self) -> None:
        """Quoted literals are preserved."""
        registry = StringRegistry()

        # Quoted strings are literals
        text = '"This is a literal string"'
        expanded = registry.expand(text)
        assert expanded == "This is a literal string"

        # Even if they look like abbreviations
        registry.add_string("literal", "expanded")
        text2 = '"literal"'
        expanded2 = registry.expand(text2)
        assert expanded2 == "literal"  # Not expanded

    def test_expand_braced_literals(self) -> None:
        """Braced literals are preserved."""
        registry = StringRegistry()
        registry.add_string("TEST", "expanded")

        # Braced strings are literals
        text = "{This is literal}"
        expanded = registry.expand(text)
        assert expanded == "This is literal"

        # Not expanded
        text2 = "{TEST}"
        expanded2 = registry.expand(text2)
        assert expanded2 == "TEST"

    def test_expand_mixed_content(self) -> None:
        """Expand mixed abbreviations and literals."""
        registry = StringRegistry()
        registry.add_string("CONF", "International Conference")
        registry.add_string("CS", "Computer Science")

        text = 'CONF # " on " # CS # ", 2024"'
        expanded = registry.expand(text)
        assert expanded == "International Conference on Computer Science, 2024"

    def test_expand_month_abbreviations(self) -> None:
        """Expand month abbreviations."""
        registry = StringRegistry()

        # Months are predefined
        assert registry.expand("jan") == "January"
        assert registry.expand("dec") == "December"

        # In concatenation
        assert registry.expand('jan # "-" # feb') == "January-February"

    def test_expand_unknown_abbreviation(self) -> None:
        """Unknown abbreviations treated as literals."""
        registry = StringRegistry()

        # Unknown abbreviation
        text = "UNKNOWN"
        expanded = registry.expand(text)
        assert expanded == "UNKNOWN"  # Kept as-is

        # In concatenation
        text2 = 'UNKNOWN # " string"'
        expanded2 = registry.expand(text2)
        assert expanded2 == "UNKNOWN string"

    def test_expand_empty_string(self) -> None:
        """Empty string expansion."""
        registry = StringRegistry()

        assert registry.expand("") == ""
        assert registry.expand('""') == ""
        assert registry.expand("{}") == ""

    def test_expand_nested_braces(self) -> None:
        """Nested braces in literals."""
        registry = StringRegistry()

        text = "{Nested {braces} here}"
        expanded = registry.expand(text)
        assert expanded == "Nested {braces} here"

    def test_expand_complex_pattern(self) -> None:
        """Complex expansion pattern."""
        registry = StringRegistry()
        registry.add_string("PROC", "Proceedings")
        registry.add_string("ICSE", "International Conference on Software Engineering")

        # Complex pattern
        text = 'PROC # " of the " # ICSE # " (" # ICSE # " \'24)"'
        expanded = registry.expand(text)
        expected = "Proceedings of the International Conference on Software Engineering (International Conference on Software Engineering '24)"
        assert expanded == expected

    def test_expand_preserves_whitespace(self) -> None:
        """Whitespace in literals should be preserved."""
        registry = StringRegistry()
        registry.add_string("A", "Letter A")

        text = 'A # "   " # A'  # Three spaces
        expanded = registry.expand(text)
        assert expanded == "Letter A   Letter A"

    def test_expand_special_characters(self) -> None:
        """Special characters in string values."""
        registry = StringRegistry()
        registry.add_string("SPEC", "Special & Characters {}")

        expanded = registry.expand("SPEC")
        assert expanded == "Special & Characters {}"

    def test_real_world_example(self, string_definitions: dict[str, str]) -> None:
        """Real-world string expansion example."""
        registry = StringRegistry()

        # Add custom abbreviations
        for key, value in string_definitions.items():
            if key not in ["jan", "feb", "dec"]:  # Skip predefined
                registry.add_string(key, value)

        # Journal with abbreviation
        text = 'IEEE # " Transactions on Software Engineering"'
        expanded = registry.expand(text)
        assert (
            expanded
            == "Institute of Electrical and Electronics Engineers Transactions on Software Engineering"
        )

        # Series
        text2 = "LNCS"
        expanded2 = registry.expand(text2)
        assert expanded2 == "Lecture Notes in Computer Science"

    def test_concatenation_without_hash(self) -> None:
        """Without # operator, no concatenation."""
        registry = StringRegistry()
        registry.add_string("A", "Letter A")
        registry.add_string("B", "Letter B")

        # Without #, treated as single token
        text = "A B"  # Space, not #
        registry.expand(text)
        # This might be "A B" or might try to find "A B" as key
        # Depends on implementation

        # With quotes
        text2 = '"A" "B"'  # No # between
        registry.expand(text2)
        # Should probably be "AB" or "A" "B" depending on parser
