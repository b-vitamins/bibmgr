"""Tests for BibTeX title processing according to TameTheBeast rules.

This module tests title case changes, brace protection, special characters,
and title purification for sorting.
"""

from bibmgr.core.titles import TitleProcessor


class TestTitleCaseChanges:
    """Test title case changes according to BibTeX rules."""

    def test_title_case_mode(self) -> None:
        """Title case mode: first letter uppercase, rest lowercase."""
        # Simple title
        result = TitleProcessor.change_case("THE QUICK BROWN FOX", mode="t")
        assert result == "The quick brown fox"

        # Already title case
        result = TitleProcessor.change_case("The Quick Brown Fox", mode="t")
        assert result == "The quick brown fox"

        # With punctuation
        result = TitleProcessor.change_case("HELLO, WORLD!", mode="t")
        assert result == "Hello, world!"

    def test_lowercase_mode(self) -> None:
        """Lowercase mode: all lowercase except protected."""
        result = TitleProcessor.change_case("THE QUICK BROWN FOX", mode="l")
        assert result == "the quick brown fox"

        # Mixed case
        result = TitleProcessor.change_case("The Quick Brown Fox", mode="l")
        assert result == "the quick brown fox"

    def test_uppercase_mode(self) -> None:
        """Uppercase mode: all uppercase except protected."""
        result = TitleProcessor.change_case("the quick brown fox", mode="u")
        assert result == "THE QUICK BROWN FOX"

        # Mixed case
        result = TitleProcessor.change_case("The Quick Brown Fox", mode="u")
        assert result == "THE QUICK BROWN FOX"

    def test_empty_title(self) -> None:
        """Empty title should remain empty."""
        assert TitleProcessor.change_case("", mode="t") == ""
        assert TitleProcessor.change_case("", mode="l") == ""
        assert TitleProcessor.change_case("", mode="u") == ""

    def test_first_letter_detection(self) -> None:
        """Title case should find first letter, not first character."""
        # Starting with punctuation - H is first letter
        result = TitleProcessor.change_case("...HELLO WORLD", mode="t")
        assert result == "...Hello world"

        # Starting with numbers - A is first letter
        result = TitleProcessor.change_case("123 ABC DEF", mode="t")
        assert result == "123 Abc def"

        # Starting with spaces - H is first letter
        result = TitleProcessor.change_case("   HELLO WORLD", mode="t")
        assert result == "   Hello world"

    def test_multiple_sentences_title_case(self) -> None:
        """Title case only capitalizes first letter of entire title."""
        result = TitleProcessor.change_case("FIRST SENTENCE. SECOND SENTENCE", mode="t")
        assert result == "First sentence. second sentence"

        # Not first letter of each sentence
        result = TitleProcessor.change_case("HELLO. HOW ARE YOU?", mode="t")
        assert result == "Hello. how are you?"


class TestBraceProtection:
    """Test brace protection in case changes."""

    def test_simple_brace_protection(self) -> None:
        """Characters at brace depth > 0 are protected."""
        # Protected word
        result = TitleProcessor.change_case("The {TCP} Protocol", mode="l")
        assert result == "the {TCP} protocol"

        # Multiple protected
        result = TitleProcessor.change_case("The {TCP} and {UDP} Protocols", mode="l")
        assert result == "the {TCP} and {UDP} protocols"

    def test_nested_braces(self) -> None:
        """Nested braces increase depth."""
        # Nested braces
        result = TitleProcessor.change_case("The {{Very Important}} Word", mode="l")
        assert result == "the {{Very Important}} word"

        # Mixed nesting
        result = TitleProcessor.change_case("A {B {C} D} E", mode="l")
        assert result == "a {B {C} D} e"

    def test_brace_depth_calculation(self) -> None:
        """Brace depth must be calculated correctly."""
        # Test at various positions
        title = "A {B C} D"
        assert TitleProcessor.get_brace_depth(title, 0) == 0  # Before 'A'
        assert TitleProcessor.get_brace_depth(title, 2) == 0  # Before '{'
        assert TitleProcessor.get_brace_depth(title, 3) == 1  # After '{', before 'B'
        assert TitleProcessor.get_brace_depth(title, 5) == 1  # At 'C'
        assert TitleProcessor.get_brace_depth(title, 7) == 0  # After '}'

    def test_unmatched_braces(self) -> None:
        """Unmatched braces should not cause negative depth."""
        # Extra closing brace
        result = TitleProcessor.change_case("A } B", mode="l")
        assert result == "a } b"

        # Unclosed brace - everything after is protected
        result = TitleProcessor.change_case("A { B C", mode="l")
        assert result == "a { B C"

    def test_special_characters_at_depth_0(self) -> None:
        """Special characters at depth 0 are treated specially."""
        # Special character at depth 0
        result = TitleProcessor.change_case("The {\\LaTeX} System", mode="l")
        assert result == "the {\\LaTeX} system"

        # Should detect this as special char
        assert TitleProcessor.is_special_char("The {\\LaTeX} System", 4)

    def test_protection_in_different_modes(self) -> None:
        """Protection works in all case modes."""
        title = "The {IEEE} Standard"

        # Title case
        assert TitleProcessor.change_case(title, mode="t") == "The {IEEE} standard"

        # Lowercase
        assert TitleProcessor.change_case(title, mode="l") == "the {IEEE} standard"

        # Uppercase
        assert TitleProcessor.change_case(title, mode="u") == "THE {IEEE} STANDARD"

    def test_partial_word_protection(self) -> None:
        """Partial word protection with braces."""
        # Part of word protected
        result = TitleProcessor.change_case("The \\TeX{book}", mode="l")
        assert result == "the \\tex{book}"

        # Multiple parts
        result = TitleProcessor.change_case("{BI}B{\\TeX}", mode="l")
        assert result == "{BI}b{\\TeX}"


class TestSpecialCharacters:
    """Test special character handling in titles."""

    def test_special_character_detection(self) -> None:
        """Special chars: '{' at depth 0 followed by '\\' ."""
        title = "Using {\\LaTeX} for Typesetting"

        # Position of { before \LaTeX
        assert TitleProcessor.is_special_char(title, 6)

        # Other positions are not special
        assert not TitleProcessor.is_special_char(title, 0)
        assert not TitleProcessor.is_special_char(title, 5)

    def test_special_chars_in_case_change(self) -> None:
        """Special characters should be processed correctly."""
        # Lowercase mode
        result = TitleProcessor.change_case(
            "The {\\LaTeX} and {\\BibTeX} Systems", mode="l"
        )
        assert result == "the {\\LaTeX} and {\\BibTeX} systems"

        # The commands inside stay unchanged
        result = TitleProcessor.change_case("{\\TeX}Book", mode="l")
        assert result == "{\\TeX}book"

    def test_lowercase_special_char_content(self) -> None:
        """Text in special chars (not commands) should change case."""
        # Text after command should change
        result = TitleProcessor._lowercase_special("{\\emph Hello World}")
        assert result == "{\\emph hello world}"

        # Just text
        result = TitleProcessor._lowercase_special("{HELLO}")
        assert result == "{hello}"

        # Command preserved
        result = TitleProcessor._lowercase_special("{\\LaTeX}")
        assert result == "{\\LaTeX}"

    def test_special_latex_commands(self) -> None:
        """Common LaTeX commands in titles."""
        commands = [
            ("{\\TeX}", "{\\TeX}"),
            ("{\\LaTeX}", "{\\LaTeX}"),
            ("{\\BibTeX}", "{\\BibTeX}"),
            ("{\\emph{important}}", "{\\emph{important}}"),
            ("{\\textbf{Bold}}", "{\\textbf{bold}}"),
        ]

        for original, expected in commands:
            result = TitleProcessor.change_case(f"The {original} System", mode="l")
            assert result == f"the {expected} system"

    def test_accented_characters(self) -> None:
        """Accented characters using LaTeX commands."""
        # Various accents
        result = TitleProcessor.change_case("Andr{\\'e} R{\\`e}gnier", mode="l")
        assert result == "andr{\\'e} r{\\`e}gnier"

        # Umlaut
        result = TitleProcessor.change_case('G{\\"o}del', mode="l")
        assert result == 'g{\\"o}del'

        # Special o
        result = TitleProcessor.change_case("Erd{\\H o}s", mode="l")
        assert result == "erd{\\H o}s"


class TestTitlePurification:
    """Test title purification for sorting."""

    def test_purify_removes_latex_commands(self) -> None:
        """Purify should handle LaTeX commands per TTB rules."""
        # Standalone TeX commands - backslash removed per TTB
        assert TitleProcessor.purify("The \\TeX book") == "The TeX book"
        assert TitleProcessor.purify("Bib\\TeX") == "BibTeX"
        assert TitleProcessor.purify("An \\emph{important} word") == "An  word"

        # Commands with stars
        assert TitleProcessor.purify("\\section*{Introduction}") == ""

    def test_purify_special_latex_conversions(self) -> None:
        """Special LaTeX commands should be converted."""
        # Special conversions from SPECIAL_LATEX_COMMANDS
        assert TitleProcessor.purify("\\oe uvre") == "oeuvre"
        assert TitleProcessor.purify("\\AE sop") == "AEsop"
        assert TitleProcessor.purify("na\\i ve") == "naive"
        assert TitleProcessor.purify("\\ss-Bahn") == "ss Bahn"
        assert TitleProcessor.purify("\\o sterreich") == "osterreich"

    def test_purify_removes_braces(self) -> None:
        """Purify should remove all braces."""
        assert TitleProcessor.purify("{TCP}") == "TCP"
        assert TitleProcessor.purify("The {IEEE} Standard") == "The IEEE Standard"
        assert TitleProcessor.purify("{{nested}}") == "nested"

    def test_purify_non_alphanumeric(self) -> None:
        """Non-alphanumeric handling per TTB: hyphens/tildes become space, others removed."""
        # Punctuation - removed (not replaced with space)
        assert TitleProcessor.purify("Hello, World!") == "Hello World"
        assert TitleProcessor.purify("TCP/IP") == "TCPIP"
        assert TitleProcessor.purify("C++") == "C"

        # Special chars - removed
        assert TitleProcessor.purify("A&B") == "AB"
        assert TitleProcessor.purify("50%") == "50"

        # Hyphens and tildes - replaced with space
        assert TitleProcessor.purify("TCP-IP") == "TCP IP"
        assert TitleProcessor.purify("A~B") == "A B"

    def test_purify_preserves_spaces(self) -> None:
        """Spaces should be preserved per TTB (not collapsed)."""
        assert TitleProcessor.purify("The   Quick   Brown") == "The   Quick   Brown"
        # Leading/trailing spaces are trimmed by strip()
        assert TitleProcessor.purify("  Leading spaces") == "Leading spaces"
        assert TitleProcessor.purify("Trailing spaces  ") == "Trailing spaces"

    def test_purify_empty_result(self) -> None:
        """Purify can result in empty string."""
        assert TitleProcessor.purify("") == ""
        assert TitleProcessor.purify("{}") == ""
        assert TitleProcessor.purify("\\LaTeX") == "LaTeX"  # Backslash removed per TTB
        assert TitleProcessor.purify("{\\LaTeX}") == ""  # Special character removed
        assert TitleProcessor.purify("!!!") == ""

    def test_purify_unicode(self) -> None:
        """Purify should normalize unicode to ASCII for sorting."""
        # Unicode letters should be normalized to ASCII equivalents
        assert TitleProcessor.purify("Émile Zola") == "Emile Zola"
        assert TitleProcessor.purify("François") == "Francois"
        assert TitleProcessor.purify("Müller") == "Muller"
        assert TitleProcessor.purify("naïve") == "naive"

        # Non-Latin scripts are removed (no ASCII equivalent)
        assert TitleProcessor.purify("Москва") == ""
        assert TitleProcessor.purify("北京") == ""
        assert TitleProcessor.purify("Hello 世界") == "Hello"

        # Unicode dashes become space (like hyphens), other punctuation removed
        assert TitleProcessor.purify("Hello—World") == "Hello World"  # em dash
        assert TitleProcessor.purify("«quotes»") == "quotes"  # guillemets removed

    def test_protect_capitals(self) -> None:
        """Protect specific words from case changes."""
        # Single word
        result = TitleProcessor.protect_capitals("The latex companion", ["LaTeX"])
        assert result == "The {LaTeX} companion"

        # Multiple words
        result = TitleProcessor.protect_capitals(
            "Introduction to ieee and acm standards", ["IEEE", "ACM"]
        )
        assert result == "Introduction to {IEEE} and {ACM} standards"

        # Case insensitive matching
        result = TitleProcessor.protect_capitals("The LATEX system", ["LaTeX"])
        assert result == "The {LaTeX} system"

        # Word boundaries
        result = TitleProcessor.protect_capitals("LaTeXnical writing", ["LaTeX"])
        assert result == "LaTeXnical writing"  # Not at word boundary

    def test_complex_title_examples(
        self, title_test_cases: list[dict[str, str]]
    ) -> None:
        """Test complex real-world title examples."""
        for case in title_test_cases:
            # Title case
            result = TitleProcessor.change_case(case["input"], mode="t")
            assert result == case["title_case"]

            # Lowercase
            result = TitleProcessor.change_case(case["input"], mode="l")
            assert result == case["lowercase"]

            # Purified
            result = TitleProcessor.purify(case["input"])
            assert result == case["purified"]
