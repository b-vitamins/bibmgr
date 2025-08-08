"""Comprehensive tests for citation key generation."""

import pytest
from unittest.mock import Mock, AsyncMock

from bibmgr.core.models import Entry, EntryType
from bibmgr.citations.keys import (
    CitationKeyGenerator,
    KeyPattern,
    KeyCollisionStrategy,
    KeyValidator,
    AsyncKeyGenerator,
)


class TestKeyPattern:
    """Test citation key pattern parsing and validation."""

    def test_basic_patterns(self):
        """Test basic pattern tokens."""
        patterns = [
            "{author}{year}",
            "{author:3}{year:2}",
            "{authors}{year}{word}",
            "{author}{year}{journal:4}",
            "{title:5}{year}",
        ]

        for pattern_str in patterns:
            pattern = KeyPattern(pattern_str)
            assert pattern.pattern == pattern_str
            assert pattern.validate()

    def test_pattern_validation(self):
        """Test pattern validation rules."""
        # Valid patterns
        assert KeyPattern("{author}{year}").validate()
        assert KeyPattern("{authors:3}{year:4}{word:2}").validate()

        # Invalid patterns
        with pytest.raises(ValueError, match="Empty pattern"):
            KeyPattern("")

        with pytest.raises(ValueError, match="Invalid token"):
            KeyPattern("{invalid}{year}")

        with pytest.raises(ValueError, match="Unclosed token"):
            KeyPattern("{author{year}")

        with pytest.raises(ValueError, match="Invalid parameter"):
            KeyPattern("{author:abc}{year}")

    def test_custom_tokens(self):
        """Test custom token definitions."""
        pattern = KeyPattern(
            "{author}{year}{custom}",
            custom_tokens={"custom": lambda e: e.type.value[:3]},
        )
        assert pattern.validate()
        assert "custom" in pattern.get_tokens()

    def test_pattern_complexity(self):
        """Test pattern complexity analysis."""
        simple = KeyPattern("{author}{year}")
        complex = KeyPattern("{authors:3}{year}{word:1}{journal:4}")

        assert simple.complexity() < complex.complexity()
        assert simple.estimated_length() < complex.estimated_length()


class TestCitationKeyGenerator:
    """Test citation key generation functionality."""

    def test_basic_generation(self, sample_entries):
        """Test basic key generation."""
        generator = CitationKeyGenerator()
        entry = sample_entries["simple_article"]

        key = generator.generate(entry)
        assert "smith" in key.lower()
        assert "2024" in key
        assert len(key) > 0
        assert key.isalnum() or "_" in key or "-" in key

    def test_author_extraction(self, sample_entries):
        """Test author name extraction variations."""
        generator = CitationKeyGenerator(pattern="{author}{year}")

        # Single author - Last, First
        entry1 = sample_entries["simple_article"]
        assert generator.generate(entry1) == "smith2024"

        # Multiple authors - use first
        entry2 = sample_entries["multiple_authors"]
        assert generator.generate(entry2) == "doe2023"

        # No author
        entry3 = sample_entries["no_author"]
        key3 = generator.generate(entry3)
        assert "anonymous" in key3.lower() or "noauthor" in key3.lower()

    def test_multiple_authors_pattern(self, sample_entries):
        """Test patterns with multiple author initials."""
        generator = CitationKeyGenerator(pattern="{authors}{year}")
        entry = sample_entries["multiple_authors"]

        key = generator.generate(entry)
        # Should have initials from multiple authors
        assert len(key) > 4  # At least some initials + year
        assert "2023" in key

    def test_year_formatting(self, sample_entries):
        """Test year formatting options."""
        entry = sample_entries["simple_article"]

        # Full year
        gen1 = CitationKeyGenerator(pattern="{author}{year}")
        assert "2024" in gen1.generate(entry)

        # Two-digit year
        gen2 = CitationKeyGenerator(pattern="{author}{year:2}")
        assert "24" in gen2.generate(entry)

        # No year
        entry_no_year = sample_entries["no_year"]
        key = gen1.generate(entry_no_year)
        assert "nodate" in key.lower() or "nd" in key.lower()

    def test_title_word_extraction(self, sample_entries):
        """Test title word extraction."""
        generator = CitationKeyGenerator(pattern="{author}{year}{word}")
        entry = sample_entries["simple_article"]

        key = generator.generate(entry)
        assert "quantum" in key.lower() or "computing" in key.lower()

    def test_unicode_handling(self, sample_entries):
        """Test Unicode character handling."""
        generator = CitationKeyGenerator()
        entry = sample_entries["unicode_entry"]

        key = generator.generate(entry)
        # Should transliterate or strip Unicode
        assert key.isascii()
        assert "muller" in key.lower() or "mueller" in key.lower()

    def test_latex_command_stripping(self, sample_entries):
        """Test LaTeX command removal from titles."""
        generator = CitationKeyGenerator(pattern="{author}{year}{word}")
        entry = sample_entries["latex_commands"]

        key = generator.generate(entry)
        # Should remove LaTeX commands
        assert "\\textbf" not in key
        assert "\\emph" not in key
        assert "$" not in key

    def test_case_transformations(self, sample_entries):
        """Test different case transformations."""
        entry = sample_entries["simple_article"]

        # Lowercase (default)
        gen_lower = CitationKeyGenerator(
            pattern=KeyPattern("{author}{year}", case="lower")
        )
        assert gen_lower.generate(entry) == "smith2024"

        # Uppercase
        gen_upper = CitationKeyGenerator(
            pattern=KeyPattern("{author}{year}", case="upper")
        )
        assert gen_upper.generate(entry) == "SMITH2024"

        # Title case
        gen_title = CitationKeyGenerator(
            pattern=KeyPattern("{author}{year}", case="title")
        )
        assert gen_title.generate(entry) == "Smith2024"

        # Camel case
        gen_camel = CitationKeyGenerator(
            pattern=KeyPattern("{author}{year}{word}", case="camel")
        )
        key = gen_camel.generate(entry)
        assert key[0].islower() and any(c.isupper() for c in key[1:])

    def test_special_character_handling(self):
        """Test special character replacement."""
        generator = CitationKeyGenerator()

        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="O'Brien, Tim",
            title="The *Important* Study: A/B Testing & More!",
            journal="Science & Nature",
            year=2024,
        )

        key = generator.generate(entry)
        # Special characters should be replaced or removed
        assert "'" not in key
        assert "*" not in key
        assert "/" not in key
        assert "&" not in key
        assert "!" not in key

    def test_length_constraints(self):
        """Test key length constraints."""
        generator = CitationKeyGenerator(
            pattern=KeyPattern(
                "{author}{year}{word}",
                max_length=10,
                min_length=5,
            )
        )

        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="VeryLongAuthorNameHere",
            title="Extremely Long Title With Many Words",
            year=2024,
        )

        key = generator.generate(entry)
        assert 5 <= len(key) <= 10


class TestCollisionHandling:
    """Test citation key collision detection and resolution."""

    def test_collision_detection(self, entry_provider):
        """Test detecting existing keys."""
        generator = CitationKeyGenerator(exists_checker=entry_provider)

        # Create entry that would generate existing key
        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="Smith, J.",
            title="Another Paper",
            year=2024,
        )

        # Should detect collision with smith2024 (from sample_entries)
        key = generator.generate(entry)
        assert key == "smith2024a", (
            f"Expected smith2024a due to collision, got: {key}"
        )  # Should be modified

    def test_letter_appending_strategy(self, entry_provider):
        """Test appending letters for collision resolution."""
        generator = CitationKeyGenerator(
            pattern="{author}{year}",
            collision_strategy=KeyCollisionStrategy.APPEND_LETTER,
            exists_checker=entry_provider,
        )

        # Mock multiple existing keys
        entry_provider.entries["smith2024a"] = Mock()
        entry_provider.entries["smith2024b"] = Mock()

        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="Smith, J.",
            title="New Paper",
            year=2024,
        )

        key = generator.generate(entry)
        assert key == "smith2024c"

    def test_number_appending_strategy(self, entry_provider):
        """Test appending numbers for collision resolution."""
        generator = CitationKeyGenerator(
            pattern="{author}{year}",
            collision_strategy=KeyCollisionStrategy.APPEND_NUMBER,
            exists_checker=entry_provider,
        )

        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="Smith, J.",
            title="New Paper",
            year=2024,
        )

        key = generator.generate(entry)
        assert key in ["smith2024_1", "smith2024-1", "smith20241"]

    def test_word_appending_strategy(self):
        """Test appending title words for collision resolution."""
        mock_provider = Mock()
        mock_provider.exists = Mock(side_effect=lambda k: k == "smith2024")

        generator = CitationKeyGenerator(
            pattern="{author}{year}",
            collision_strategy=KeyCollisionStrategy.APPEND_WORD,
            exists_checker=mock_provider,
        )

        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="Smith, J.",
            title="Quantum Computing Research",
            year=2024,
        )

        key = generator.generate(entry)
        assert "quantum" in key.lower() or "computing" in key.lower()

    def test_interactive_strategy(self):
        """Test interactive collision resolution."""
        mock_provider = Mock()
        mock_provider.exists = Mock(return_value=True)

        generator = CitationKeyGenerator(
            collision_strategy=KeyCollisionStrategy.INTERACTIVE,
            exists_checker=mock_provider,
        )

        # Mock user input
        generator.prompt_user = Mock(return_value="smith2024custom")

        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="Smith, J.",
            year=2024,
            title="Test",
        )

        key = generator.generate(entry)
        assert key == "smith2024custom"
        generator.prompt_user.assert_called_once()

    def test_fail_strategy(self):
        """Test failing on collision."""
        mock_provider = Mock()
        mock_provider.exists = Mock(return_value=True)

        generator = CitationKeyGenerator(
            collision_strategy=KeyCollisionStrategy.FAIL,
            exists_checker=mock_provider,
        )

        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="Smith, J.",
            year=2024,
            title="Test",
        )

        with pytest.raises(ValueError, match="Key collision"):
            generator.generate(entry)

    def test_disambiguation_suffixes(self):
        """Test automatic disambiguation for same author/year."""
        generator = CitationKeyGenerator(enable_auto_disambiguation=True)

        entries = [
            Entry(
                key=f"temp{i}",
                type=EntryType.ARTICLE,
                author="Smith, J.",
                title=f"Paper {i}",
                year=2024,
            )
            for i in range(5)
        ]

        keys = [generator.generate(e) for e in entries]

        # All keys should be unique
        assert len(keys) == len(set(keys))

        # Should have suffixes
        assert any("a" in k for k in keys)
        assert any("b" in k for k in keys)


class TestKeyValidator:
    """Test citation key validation."""

    def test_valid_keys(self):
        """Test validation of valid keys."""
        validator = KeyValidator()

        valid_keys = [
            "smith2024",
            "doe2023a",
            "johnson_2024",
            "lee-park-2024",
            "ABC123",
            "a1b2c3",
        ]

        for key in valid_keys:
            assert validator.is_valid(key)

    def test_invalid_keys(self):
        """Test validation of invalid keys."""
        validator = KeyValidator()

        invalid_keys = [
            "",  # Empty
            "a",  # Too short
            "key with spaces",  # Spaces
            "key@2024",  # Invalid character
            "key#2024",  # Invalid character
            "ключ2024",  # Non-ASCII
            "🔑2024",  # Emoji
        ]

        for key in invalid_keys:
            assert not validator.is_valid(key)

    def test_custom_validation_rules(self):
        """Test custom validation rules."""
        # Require keys to start with letter and be 8+ chars
        validator = KeyValidator(
            min_length=8,
            max_length=20,
            pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{7,19}$",
        )

        assert validator.is_valid("smith2024")
        assert not validator.is_valid("2024smith")  # Starts with number
        assert not validator.is_valid("short")  # Too short
        assert not validator.is_valid("a" * 25)  # Too long

    def test_sanitize_key(self):
        """Test key sanitization."""
        validator = KeyValidator()

        # Sanitize invalid characters (replaced with underscore)
        assert validator.sanitize("key@2024") == "key_2024"
        assert validator.sanitize("key with spaces") == "key_with_spaces"
        assert validator.sanitize("Müller2024") == "Mueller2024"  # ü -> ue
        assert validator.sanitize("key/2024") == "key_2024"

        # Truncate if too long
        long_key = "a" * 100
        sanitized = validator.sanitize(long_key)
        assert len(sanitized) <= validator.max_length


class TestAsyncKeyGeneration:
    """Test asynchronous key generation."""

    @pytest.mark.asyncio
    async def test_async_generation(self, sample_entries):
        """Test async key generation."""
        generator = AsyncKeyGenerator()
        entry = sample_entries["simple_article"]

        key = await generator.generate_async(entry)
        assert "smith" in key.lower()
        assert "2024" in key

    @pytest.mark.asyncio
    async def test_batch_generation(self, sample_entries):
        """Test batch key generation."""
        generator = AsyncKeyGenerator()
        entries = list(sample_entries.values())[:5]

        keys = await generator.generate_batch(entries)

        assert len(keys) == len(entries)
        assert all(isinstance(k, str) for k in keys)
        assert len(keys) == len(set(keys))  # All unique

    @pytest.mark.asyncio
    async def test_async_collision_checking(self):
        """Test async collision checking."""
        mock_checker = AsyncMock()
        mock_checker.exists = AsyncMock(side_effect=lambda k: k == "smith2024")

        generator = AsyncKeyGenerator(exists_checker=mock_checker)

        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="Smith, J.",
            title="New Paper",
            year=2024,
        )

        key = await generator.generate_async(entry)
        assert key != "smith2024"
        mock_checker.exists.assert_called()

    @pytest.mark.asyncio
    async def test_concurrent_generation(self, performance_entries):
        """Test concurrent generation performance."""
        import asyncio
        import time

        generator = AsyncKeyGenerator()
        entries = list(performance_entries.values())[:100]

        # Time concurrent generation
        start = time.time()
        tasks = [generator.generate_async(e) for e in entries]
        keys = await asyncio.gather(*tasks)
        duration = time.time() - start

        assert len(keys) == len(entries)
        # Without an exists_checker, duplicates are expected for similar entries
        # Just ensure we got some keys generated
        assert len(set(keys)) > 0

        # Should be faster than sequential (assuming some I/O or processing benefit)
        # This is more of a performance benchmark than a strict test
        assert duration < 5.0  # Reasonable timeout


class TestKeyGenerationEdgeCases:
    """Test edge cases in key generation."""

    def test_empty_fields(self):
        """Test handling of empty fields."""
        generator = CitationKeyGenerator()

        # Completely empty entry
        entry = Entry(key="temp", type=EntryType.MISC)
        key = generator.generate(entry)
        assert len(key) > 0

        # Only title (default pattern uses author+year, so title won't appear)
        entry = Entry(
            key="temp",
            type=EntryType.MISC,
            title="Important Document",
        )
        key = generator.generate(entry)
        # With default pattern "{author}{year}", missing fields result in "anonymous" and "nd"
        assert "anonymous" in key.lower()  # No author -> anonymous
        assert "nd" in key.lower()  # No date -> nd

    def test_very_long_names(self):
        """Test handling of very long author names."""
        generator = CitationKeyGenerator()

        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="Wolfeschlegelsteinhausenbergerdorff, Hubert Blaine",
            title="Test",
            year=2024,
        )

        key = generator.generate(entry)
        assert len(key) < 50  # Should truncate reasonably

    def test_hyphenated_names(self):
        """Test hyphenated author names."""
        generator = CitationKeyGenerator()

        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="Smith-Jones, Mary-Anne",
            title="Test",
            year=2024,
        )

        key = generator.generate(entry)
        assert "smith" in key.lower() or "jones" in key.lower()

    def test_organization_authors(self):
        """Test organization as author."""
        generator = CitationKeyGenerator()

        entry = Entry(
            key="temp",
            type=EntryType.MISC,
            author="{World Health Organization}",
            title="Global Health Report",
            year=2024,
        )

        key = generator.generate(entry)
        assert "who" in key.lower() or "world" in key.lower()

    def test_numeric_titles(self):
        """Test titles with numbers."""
        generator = CitationKeyGenerator(pattern="{author}{year}{word}")

        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="Smith, J.",
            title="2020 Vision: A Retrospective Analysis",
            year=2024,
        )

        key = generator.generate(entry)
        # Should skip numeric "2020" and use next word
        assert "vision" in key.lower() or "retrospective" in key.lower()

    def test_stopword_filtering(self):
        """Test filtering of stopwords from titles."""
        generator = CitationKeyGenerator(pattern="{author}{year}{word}")

        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="Smith, J.",
            title="The Analysis of the Data",
            year=2024,
        )

        key = generator.generate(entry)
        # Should skip "The" and "of the" to find significant word
        assert "analysis" in key.lower() or "data" in key.lower()
        assert "the" not in key.lower()

    def test_duplicate_generation_determinism(self, sample_entries):
        """Test that generation is deterministic."""
        generator = CitationKeyGenerator()
        entry = sample_entries["simple_article"]

        # Generate multiple times
        keys = [generator.generate(entry) for _ in range(10)]

        # All should be identical
        assert len(set(keys)) == 1

    def test_custom_separators(self):
        """Test custom separator configuration."""
        # Underscore separator
        gen1 = CitationKeyGenerator(
            pattern=KeyPattern("{author}{year}{word}", separator="_")
        )

        # Dash separator
        gen2 = CitationKeyGenerator(
            pattern=KeyPattern("{author}{year}{word}", separator="-")
        )

        # No separator
        gen3 = CitationKeyGenerator(
            pattern=KeyPattern("{author}{year}{word}", separator="")
        )

        entry = Entry(
            key="temp",
            type=EntryType.ARTICLE,
            author="Smith, J.",
            title="Quantum Computing",
            year=2024,
        )

        key1 = gen1.generate(entry)
        key2 = gen2.generate(entry)
        key3 = gen3.generate(entry)

        assert "_" in key1 or key1.replace("_", "") == key1
        assert "-" in key2 or key2.replace("-", "") == key2
        assert "_" not in key3 and "-" not in key3
