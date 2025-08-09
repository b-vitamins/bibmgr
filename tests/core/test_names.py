"""Tests for BibTeX author name parsing according to TameTheBeast rules.

This module tests the three BibTeX name formats, von particle detection,
name formatting, and special cases like corporate authors.
"""

from bibmgr.core.names import NameFormatter, NameParser, ParsedName


class TestNameParser:
    """Test name parsing according to BibTeX's three formats."""

    def test_format_0_first_von_last(self) -> None:
        """Format 0: First von Last (no commas)."""
        # Simple case
        parsed = NameParser.parse("Donald E. Knuth")
        assert parsed.first == ["Donald", "E."]
        assert parsed.von == []
        assert parsed.last == ["Knuth"]
        assert parsed.jr == []

        # Multiple first names
        parsed = NameParser.parse("John Jacob Jingleheimer Schmidt")
        assert parsed.first == ["John", "Jacob", "Jingleheimer"]
        assert parsed.last == ["Schmidt"]

        # With von particle
        parsed = NameParser.parse("Ludwig van Beethoven")
        assert parsed.first == ["Ludwig"]
        assert parsed.von == ["van"]
        assert parsed.last == ["Beethoven"]

    def test_format_1_von_last_first(self) -> None:
        """Format 1: von Last, First (one comma)."""
        # Simple case
        parsed = NameParser.parse("Knuth, Donald E.")
        assert parsed.first == ["Donald", "E."]
        assert parsed.von == []
        assert parsed.last == ["Knuth"]
        assert parsed.jr == []

        # With von particle
        parsed = NameParser.parse("van Beethoven, Ludwig")
        assert parsed.first == ["Ludwig"]
        assert parsed.von == ["van"]
        assert parsed.last == ["Beethoven"]

        # Multiple last names
        parsed = NameParser.parse("Garcia Lopez, Maria")
        assert parsed.first == ["Maria"]
        assert parsed.von == []
        assert parsed.last == ["Garcia", "Lopez"]

    def test_format_2_von_last_jr_first(self) -> None:
        """Format 2: von Last, Jr, First (two commas)."""
        # With Jr
        parsed = NameParser.parse("King, Jr., Martin Luther")
        assert parsed.first == ["Martin", "Luther"]
        assert parsed.von == []
        assert parsed.last == ["King"]
        assert parsed.jr == ["Jr."]

        # With von and Jr
        parsed = NameParser.parse("de la Cruz, III, Jose Maria")
        assert parsed.first == ["Jose", "Maria"]
        assert parsed.von == ["de", "la"]
        assert parsed.last == ["Cruz"]
        assert parsed.jr == ["III"]

        # Roman numeral
        parsed = NameParser.parse("Smith, IV, John Paul")
        assert parsed.first == ["John", "Paul"]
        assert parsed.last == ["Smith"]
        assert parsed.jr == ["IV"]

    def test_too_many_commas(self) -> None:
        """More than 2 commas: everything after 2nd comma is first name."""
        parsed = NameParser.parse("Last, Jr., First, Extra, More")
        assert parsed.von == []
        assert parsed.last == ["Last"]
        assert parsed.jr == ["Jr."]
        assert parsed.first == ["First,", "Extra,", "More"]  # All as first

    def test_empty_name(self) -> None:
        """Empty name returns empty ParsedName."""
        parsed = NameParser.parse("")
        assert parsed.is_empty()
        assert parsed.first == []
        assert parsed.von == []
        assert parsed.last == []
        assert parsed.jr == []

    def test_whitespace_only_name(self) -> None:
        """Whitespace-only name returns empty ParsedName."""
        parsed = NameParser.parse("   \n\t  ")
        assert parsed.is_empty()

    def test_single_word_name(self) -> None:
        """Single word is treated as last name."""
        parsed = NameParser.parse("Madonna")
        assert parsed.first == []
        assert parsed.von == []
        assert parsed.last == ["Madonna"]
        assert parsed.jr == []

    def test_tokenization_preserves_braces(self) -> None:
        """Tokenization should preserve braced groups."""
        parsed = NameParser.parse("{Barnes and Noble}")
        assert parsed.first == []
        assert parsed.last == ["{Barnes and Noble}"]

        # With other tokens
        parsed = NameParser.parse("The {LaTeX} {Project Team}")
        assert parsed.first == ["The", "{LaTeX}"]
        assert parsed.last == ["{Project Team}"]

    def test_hyphenated_names(self) -> None:
        """Hyphenated names should be handled correctly."""
        parsed = NameParser.parse("Jean-Paul Sartre")
        assert parsed.first == ["Jean-Paul"]
        assert parsed.last == ["Sartre"]

        # In last name
        parsed = NameParser.parse("Mary Garcia-Lopez")
        assert parsed.first == ["Mary"]
        assert parsed.last == ["Garcia-Lopez"]

    def test_apostrophe_names(self) -> None:
        """Names with apostrophes should be handled."""
        parsed = NameParser.parse("Patrick O'Brien")
        assert parsed.first == ["Patrick"]
        assert parsed.last == ["O'Brien"]

        # Format 1
        parsed = NameParser.parse("O'Brien, Patrick")
        assert parsed.first == ["Patrick"]
        assert parsed.last == ["O'Brien"]


class TestVonParticleDetection:
    """Test von particle detection (lowercase = von)."""

    def test_simple_von_particles(self) -> None:
        """Common von particles should be detected."""
        test_cases = [
            ("Ludwig van Beethoven", ["van"], ["Beethoven"]),
            ("Charles de Gaulle", ["de"], ["Gaulle"]),
            ("John von Neumann", ["von"], ["Neumann"]),
            ("Maria de la Cruz", ["de", "la"], ["Cruz"]),
            ("Vincent van Gogh", ["van"], ["Gogh"]),
        ]

        for name, expected_von, expected_last in test_cases:
            parsed = NameParser.parse(name)
            assert parsed.von == expected_von, f"Failed for {name}"
            assert parsed.last == expected_last, f"Failed for {name}"

    def test_multiple_von_particles(self) -> None:
        """Multiple consecutive von particles."""
        parsed = NameParser.parse("Maria de los Angeles Garcia")
        assert parsed.first == ["Maria"]
        assert parsed.von == ["de", "los"]
        assert parsed.last == ["Angeles", "Garcia"]

        # All lowercase before last
        parsed = NameParser.parse("Jan van den Berg")
        assert parsed.first == ["Jan"]
        assert parsed.von == ["van", "den"]
        assert parsed.last == ["Berg"]

    def test_von_requires_lowercase(self) -> None:
        """Uppercase words are not von particles."""
        parsed = NameParser.parse("John Van Beethoven")
        assert parsed.first == ["John", "Van"]  # Van is uppercase
        assert parsed.von == []
        assert parsed.last == ["Beethoven"]

        # Mixed case
        parsed = NameParser.parse("John De la Cruz")
        assert parsed.first == ["John", "De"]  # De is uppercase
        assert parsed.von == ["la"]
        assert parsed.last == ["Cruz"]

    def test_von_in_format_1(self) -> None:
        """Von detection in format 1 (one comma)."""
        parsed = NameParser.parse("von Neumann, John")
        assert parsed.first == ["John"]
        assert parsed.von == ["von"]
        assert parsed.last == ["Neumann"]

        # Multiple von particles
        parsed = NameParser.parse("van der Waals, Johannes")
        assert parsed.first == ["Johannes"]
        assert parsed.von == ["van", "der"]
        assert parsed.last == ["Waals"]

    def test_all_lowercase_names_follow_bibtex_rules(self) -> None:
        """All lowercase names follow standard BibTeX von detection rules."""
        # According to TameTheBeast, "jean de la fontaine" gives First: empty, von: jean de la, Last: fontaine
        parsed = NameParser.parse("john smith")  # All lowercase
        assert parsed.first == []
        assert parsed.von == ["john"]
        assert parsed.last == ["smith"]

        # More complex example from TameTheBeast manual
        parsed = NameParser.parse("jean de la fontaine")
        assert parsed.first == []
        assert parsed.von == ["jean", "de", "la"]
        assert parsed.last == ["fontaine"]

    def test_braced_lowercase_not_von(self) -> None:
        """Braced lowercase words are not von particles."""
        parsed = NameParser.parse("John {von} Neumann")
        assert parsed.first == ["John", "{von}"]  # Braced, so not von
        assert parsed.von == []
        assert parsed.last == ["Neumann"]

    def test_special_chars_ignored_for_case(self) -> None:
        """Special characters are ignored when determining case."""
        # Starting with special char, then lowercase
        parsed = NameParser.parse("Jean d'Arc")
        assert parsed.first == ["Jean"]
        assert parsed.von == []  # d'Arc starts with lowercase but is last
        assert parsed.last == ["d'Arc"]


class TestNameFormatter:
    """Test name formatting with BibTeX patterns."""

    def test_format_patterns_full_names(self) -> None:
        """Test formatting with full name patterns."""
        parsed = ParsedName(first=["Donald", "E."], von=[], last=["Knuth"], jr=[])

        # Standard patterns
        assert parsed.format("{ff }{vv }{ll}{, jj}") == "Donald E. Knuth"
        assert parsed.format("{ll}, {ff}") == "Knuth, Donald E."
        assert parsed.format("{ll}") == "Knuth"

    def test_format_patterns_abbreviated(self) -> None:
        """Test formatting with abbreviated patterns."""
        parsed = ParsedName(first=["Donald", "Ervin"], von=[], last=["Knuth"], jr=[])

        # Abbreviated first names
        assert parsed.format("{f. }{ll}") == "D. E. Knuth"
        assert parsed.format("{ll}, {f.}") == "Knuth, D.E."

        # Custom separator
        assert parsed.format("{f{.} }{ll}") == "D. E. Knuth"
        assert parsed.format("{f{-}}{ll}") == "D-EKnuth"

    def test_format_with_von_particles(self) -> None:
        """Test formatting names with von particles."""
        parsed = ParsedName(first=["Ludwig"], von=["van"], last=["Beethoven"], jr=[])

        assert parsed.format("{ff }{vv }{ll}") == "Ludwig van Beethoven"
        assert parsed.format("{vv }{ll}, {ff}") == "van Beethoven, Ludwig"
        assert parsed.format("{ll}, {ff}") == "Beethoven, Ludwig"  # No von

    def test_format_with_jr(self) -> None:
        """Test formatting names with Jr."""
        parsed = ParsedName(
            first=["Martin", "Luther"], von=[], last=["King"], jr=["Jr."]
        )

        assert parsed.format("{ff }{ll}{, jj}") == "Martin Luther King, Jr."
        assert parsed.format("{ll}, {jj}, {ff}") == "King, Jr., Martin Luther"
        assert parsed.format("{ll}, {ff}") == "King, Martin Luther"  # No Jr

    def test_format_empty_components(self) -> None:
        """Test formatting with missing components."""
        # Only last name
        parsed = ParsedName(first=[], von=[], last=["Madonna"], jr=[])
        assert parsed.format("{ff }{vv }{ll}{, jj}") == "Madonna"
        assert parsed.format("{f. }{ll}") == "Madonna"

        # Empty name
        parsed = ParsedName(first=[], von=[], last=[], jr=[])
        assert parsed.format("{ff }{vv }{ll}{, jj}") == ""

    def test_format_hyphenated_abbreviated(self) -> None:
        """Test abbreviated hyphenated names."""
        parsed = ParsedName(first=["Jean-Paul"], von=[], last=["Sartre"], jr=[])

        assert parsed.format("{f. }{ll}") == "J.-P. Sartre"
        assert parsed.format("{f{.}}{ll}") == "J.-P.Sartre"

    def test_format_initials_only(self) -> None:
        """Test formatting to get initials only."""
        parsed = ParsedName(
            first=["John", "Ronald", "Reuel"], von=[], last=["Tolkien"], jr=[]
        )

        assert parsed.format("{f}{l}") == "JRRT"
        assert parsed.format("{f.}{l.}") == "J.R.R.T."


class TestSpecialNameCases:
    """Test special name cases and edge cases."""

    def test_corporate_authors(self) -> None:
        """Corporate authors in braces should be kept as-is."""
        parsed = NameParser.parse("{Barnes and Noble}")
        assert parsed.last == ["{Barnes and Noble}"]
        assert parsed.format("{ll}") == "{Barnes and Noble}"

        # Complex corporate
        parsed = NameParser.parse("{The {LaTeX} Project Team}")
        assert parsed.last == ["{The {LaTeX} Project Team}"]

    def test_others_keyword(self) -> None:
        """'others' is a special BibTeX keyword."""
        parsed = NameParser.parse("others")
        assert parsed.last == ["others"]

        # In list context
        names = ["John Smith", "Jane Doe", "others"]
        for name in names:
            parsed = NameParser.parse(name)
            assert not parsed.is_empty()

    def test_unicode_names(self, complex_author_names: list[str]) -> None:
        """Unicode names should be handled correctly."""
        unicode_names = [
            "François Müller",
            "José García-López",
            "Пётр Иванов",
            "北京大学",
        ]

        for name in unicode_names:
            parsed = NameParser.parse(name)
            assert not parsed.is_empty()
            # Should be able to format
            formatted = parsed.format("{ff }{vv }{ll}")
            assert len(formatted) > 0

    def test_special_latex_chars_in_names(self) -> None:
        """Names with LaTeX special characters."""
        parsed = NameParser.parse("Paul {\\`E}rd{\\H o}s")
        assert parsed.first == ["Paul"]
        assert parsed.last == ["{\\`E}rd{\\H o}s"]

        # Should preserve special chars in formatting
        formatted = parsed.format("{ff }{ll}")
        assert "{\\`E}rd{\\H o}s" in formatted

    def test_abbreviate_special_names(self) -> None:
        """Test abbreviation of special names."""
        # Protected names
        name = "{\\relax Ch}ristopher"
        abbrev = NameFormatter.abbreviate(name)
        assert abbrev == "Ch."  # Extracts protected content

        # Regular hyphenated
        abbrev = NameFormatter.abbreviate("Jean-Paul")
        assert abbrev == "J.-P."

        # Empty
        abbrev = NameFormatter.abbreviate("")
        assert abbrev == ""

    def test_name_with_tilde(self) -> None:
        """Names with ~ (non-breaking space) should be handled."""
        parsed = NameParser.parse("Donald~E. Knuth")
        # Tilde treated as separator
        assert parsed.first == ["Donald", "E."]
        assert parsed.last == ["Knuth"]

    def test_consecutive_separators(self) -> None:
        """Multiple consecutive separators should be handled."""
        parsed = NameParser.parse("John    Paul   Smith")  # Multiple spaces
        assert parsed.first == ["John", "Paul"]
        assert parsed.last == ["Smith"]

        # Mixed separators - tilde is a separator per TameTheBeast
        parsed = NameParser.parse("John~ ~Paul")
        # With 2 tokens in "First Last" format: First=["John"], Last=["Paul"]
        assert parsed.first == ["John"]
        assert parsed.last == ["Paul"]

    def test_edge_case_all_lowercase(self) -> None:
        """All lowercase name follows BibTeX von detection rules."""
        parsed = NameParser.parse("bell hooks")  # Real author who uses lowercase
        # According to BibTeX rules, lowercase words go to von (except the last)
        assert parsed.first == []
        assert parsed.von == ["bell"]
        assert parsed.last == ["hooks"]  # Last word is always last name

    def test_edge_case_numbers_in_names(self) -> None:
        """Names with numbers (e.g., organizations)."""
        parsed = NameParser.parse("3M Corporation")
        assert parsed.first == ["3M"]
        assert parsed.last == ["Corporation"]

        # In braces
        parsed = NameParser.parse("{3M Corporation}")
        assert parsed.last == ["{3M Corporation}"]
