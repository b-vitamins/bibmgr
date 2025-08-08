"""Citation key generation with pattern support and collision handling."""

from __future__ import annotations

import asyncio
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Protocol

from bibmgr.core.models import Entry


class KeyCollisionStrategy(Enum):
    """Strategies for handling key collisions."""

    APPEND_LETTER = auto()  # smith2024 -> smith2024a, smith2024b
    APPEND_NUMBER = auto()  # smith2024 -> smith2024_1, smith2024_2
    APPEND_WORD = auto()  # smith2024 -> smith2024_quantum
    INTERACTIVE = auto()  # Ask user for new key
    FAIL = auto()  # Raise error on collision


@dataclass
class KeyPattern:
    """Citation key generation pattern.

    Supported tokens:
    - {author} or {author:N} - First N characters of first author's last name
    - {authors} or {authors:N} - First letter of each author's last name (max N)
    - {year} or {year:2} - Full year or last 2 digits
    - {title} or {title:N} - First N characters of first significant word
    - {word} or {word:N} - Nth significant word from title
    - {journal} or {journal:N} - First N characters of journal name
    - {custom} - Custom token via custom_tokens dict
    """

    pattern: str
    case: str = "lower"  # lower, upper, title, camel
    separator: str = ""  # Separator between components
    min_length: int = 3
    max_length: int = 30
    min_author_chars: int = 2
    max_author_chars: int = 20
    min_title_chars: int = 3
    custom_tokens: dict[str, Callable[[Entry], str]] = field(default_factory=dict)

    def __post_init__(self):
        """Validate pattern on initialization."""
        if not self.pattern:
            raise ValueError("Empty pattern not allowed")

        # Check for unclosed braces first
        if self.pattern.count("{") != self.pattern.count("}"):
            raise ValueError("Unclosed token in pattern")

        # Validate tokens
        tokens = self.get_tokens()
        valid_tokens = {"author", "authors", "year", "title", "word", "journal"}
        valid_tokens.update(self.custom_tokens.keys())

        for token in tokens:
            base_token = token.split(":")[0]
            if base_token not in valid_tokens:
                raise ValueError(f"Invalid token: {{{token}}}")

        # Validate parameters in tokens
        for token in tokens:
            if ":" in token:
                parts = token.split(":", 1)
                if len(parts) != 2:
                    continue
                try:
                    int(parts[1])
                except ValueError:
                    raise ValueError(f"Invalid parameter in token: {{{token}}}")

    def get_tokens(self) -> list[str]:
        """Extract all tokens from pattern."""
        return re.findall(r"\{([^}]+)\}", self.pattern)

    def validate(self) -> bool:
        """Validate pattern structure."""
        try:
            self.__post_init__()
            return True
        except ValueError:
            return False

    def complexity(self) -> int:
        """Calculate pattern complexity score."""
        score = len(self.get_tokens())
        if self.custom_tokens:
            score += len(self.custom_tokens)
        return score

    def estimated_length(self) -> int:
        """Estimate typical key length from pattern."""
        length = 0
        for token in self.get_tokens():
            if token.startswith("author"):
                length += 5
            elif token.startswith("authors"):
                length += 3
            elif token.startswith("year"):
                length += 4 if ":2" not in token else 2
            elif token.startswith("title") or token.startswith("word"):
                length += 6
            elif token.startswith("journal"):
                length += 4
        return min(max(length, self.min_length), self.max_length)


class KeyExistsChecker(Protocol):
    """Protocol for checking if a key exists."""

    def exists(self, key: str) -> bool:
        """Check if key exists in storage."""
        ...


class KeyValidator:
    """Validates and sanitizes citation keys."""

    def __init__(
        self,
        min_length: int = 3,
        max_length: int = 50,
        pattern: str | None = None,
    ):
        """Initialize validator.

        Args:
            min_length: Minimum key length
            max_length: Maximum key length
            pattern: Optional regex pattern for validation
        """
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = pattern or r"^[a-zA-Z][a-zA-Z0-9_-]*$"
        self._regex = re.compile(self.pattern)

    def is_valid(self, key: str) -> bool:
        """Check if key is valid."""
        if not key:
            return False
        if len(key) < self.min_length or len(key) > self.max_length:
            return False
        if not key.isascii():
            return False
        return bool(self._regex.match(key))

    def sanitize(self, key: str) -> str:
        """Sanitize key to make it valid."""
        if not key:
            return "unknown"

        # Transliterate Unicode to ASCII
        key = self._transliterate(key)

        # Replace invalid characters
        key = re.sub(r"[^a-zA-Z0-9_-]", "_", key)

        # Ensure starts with letter
        if key and not key[0].isalpha():
            key = "k" + key

        # Apply length constraints
        if len(key) < self.min_length:
            key = key + "_" * (self.min_length - len(key))
        elif len(key) > self.max_length:
            key = key[: self.max_length]

        return key

    def _transliterate(self, text: str) -> str:
        """Transliterate Unicode to ASCII."""
        # Common replacements first (before normalization)
        replacements = {
            "ä": "ae",
            "ö": "oe",
            "ü": "ue",
            "Ä": "Ae",
            "Ö": "Oe",
            "Ü": "Ue",
            "ß": "ss",
            "æ": "ae",
            "ø": "o",
            "å": "a",
            "Æ": "AE",
            "Ø": "O",
            "Å": "A",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        # Normalize and remove remaining accents
        nfd = unicodedata.normalize("NFD", text)
        ascii_text = "".join(char for char in nfd if unicodedata.category(char) != "Mn")

        return ascii_text


class CitationKeyGenerator:
    """Generates citation keys from patterns with collision handling."""

    # Common stopwords to filter from titles
    STOPWORDS = {
        "a",
        "an",
        "and",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
        "about",
        "after",
        "before",
        "between",
        "during",
        "through",
        "under",
        "over",
        "into",
        "onto",
    }

    def __init__(
        self,
        pattern: KeyPattern | str = "{author}{year}",
        collision_strategy: KeyCollisionStrategy = KeyCollisionStrategy.APPEND_LETTER,
        exists_checker: KeyExistsChecker | None = None,
        enable_auto_disambiguation: bool = False,
    ):
        """Initialize key generator.

        Args:
            pattern: Pattern for key generation
            collision_strategy: How to handle collisions
            exists_checker: Check if key exists in storage
            enable_auto_disambiguation: Auto-disambiguate same author/year
        """
        if isinstance(pattern, str):
            pattern = KeyPattern(pattern)

        self.pattern = pattern
        self.collision_strategy = collision_strategy
        self.exists_checker = exists_checker
        self.enable_auto_disambiguation = enable_auto_disambiguation
        self.validator = KeyValidator(
            min_length=pattern.min_length,
            max_length=pattern.max_length,
        )

        # Track generated keys for auto-disambiguation
        self._generated_keys: dict[str, int] = {}

        # For interactive mode
        self.prompt_user: Callable[[str, Entry], str] | None = None

    def generate(self, entry: Entry) -> str:
        """Generate citation key for entry.

        Args:
            entry: Bibliography entry

        Returns:
            Generated citation key, guaranteed unique if exists_checker provided
        """
        base_key = self._generate_base_key(entry)

        # Apply case transformation
        base_key = self._apply_case(base_key)

        # Auto-disambiguation if enabled
        if self.enable_auto_disambiguation:
            base_key = self._auto_disambiguate(base_key)

        # Handle collisions if checker provided
        if self.exists_checker:
            key = self._resolve_collision(base_key, entry)
        else:
            key = base_key

        # Validate and sanitize
        if not self.validator.is_valid(key):
            key = self.validator.sanitize(key)

        return key

    def _generate_base_key(self, entry: Entry) -> str:
        """Generate base key from pattern and entry."""
        key = self.pattern.pattern

        # Process each token
        components = []
        last_end = 0

        # Find and replace tokens while tracking components
        import re

        for match in re.finditer(r"\{([^}]+)\}", self.pattern.pattern):
            # Add any literal text before the token
            if match.start() > last_end:
                literal = self.pattern.pattern[last_end : match.start()]
                if literal:
                    components.append(literal)

            # Process the token
            token = match.group(1)
            replacement = self._process_token(token, entry)
            if replacement:
                components.append(replacement)

            last_end = match.end()

        # Add any remaining literal text
        if last_end < len(self.pattern.pattern):
            literal = self.pattern.pattern[last_end:]
            if literal:
                components.append(literal)

        # Join components with separator for case processing
        if self.pattern.case in ["camel", "title"] and self.pattern.separator == "":
            # Use temporary separator for case processing
            key = "_".join(components)
        else:
            key = self.pattern.separator.join(components)

        return key

    def _process_token(self, token: str, entry: Entry) -> str:
        """Process a single pattern token."""
        # Parse token and parameter
        parts = token.split(":", 1)
        base_token = parts[0]
        param = int(parts[1]) if len(parts) > 1 else None

        # Check custom tokens first
        if base_token in self.pattern.custom_tokens:
            return self.pattern.custom_tokens[base_token](entry)

        # Standard tokens
        match base_token:
            case "author":
                return self._extract_author(entry, param)
            case "authors":
                return self._extract_authors(entry, param)
            case "year":
                return self._extract_year(entry, param)
            case "title":
                return self._extract_title(entry, param)
            case "word":
                return self._extract_word(entry, param)
            case "journal":
                return self._extract_journal(entry, param)
            case _:
                return ""

    def _extract_author(self, entry: Entry, chars: int | None = None) -> str:
        """Extract author information."""
        if not entry.author:
            return "anonymous"

        authors = entry.authors_list
        if not authors:
            return "anonymous"

        first_author = authors[0]

        # Handle organization authors
        if first_author.startswith("{") and first_author.endswith("}"):
            org = first_author[1:-1]
            # Use acronym if possible
            words = org.split()
            if len(words) > 1:
                acronym = "".join(w[0] for w in words if w[0].isupper())
                if acronym:
                    return acronym.lower()
            return words[0].lower() if words else "org"

        # Extract last name
        if "," in first_author:
            last_name = first_author.split(",")[0].strip()
        else:
            parts = first_author.strip().split()
            last_name = parts[-1] if parts else "anonymous"

        # Transliterate Unicode to ASCII first
        last_name = self.validator._transliterate(last_name)

        # Clean and apply constraints
        last_name = re.sub(r"[^a-zA-Z-]", "", last_name)

        if chars:
            last_name = last_name[:chars]
        else:
            last_name = last_name[: self.pattern.max_author_chars]

        return last_name

    def _extract_authors(self, entry: Entry, count: int | None = None) -> str:
        """Extract multiple authors' initials."""
        if not entry.author:
            return ""

        authors = entry.authors_list
        if not authors:
            return ""

        if count:
            authors = authors[:count]

        initials = []
        for author in authors:
            if author.startswith("{") and author.endswith("}"):
                # Organization
                org = author[1:-1]
                initial = "".join(w[0] for w in org.split() if w)[:1]
            elif "," in author:
                last_name = author.split(",")[0].strip()
                initial = last_name[0] if last_name else ""
            else:
                parts = author.strip().split()
                initial = parts[-1][0] if parts else ""

            if initial:
                initials.append(initial.lower())

        return "".join(initials)

    def _extract_year(self, entry: Entry, digits: int | None = None) -> str:
        """Extract year information."""
        if not entry.year:
            return "nd"  # no date

        year_str = str(entry.year)

        if digits == 2:
            return year_str[-2:]
        else:
            return year_str

    def _extract_title(self, entry: Entry, chars: int | None = None) -> str:
        """Extract title information."""
        if not entry.title:
            return ""

        # Clean title
        title = self._clean_text(entry.title)

        # Get first significant word
        words = title.split()
        for word in words:
            if (
                word.lower() not in self.STOPWORDS
                and len(word) >= self.pattern.min_title_chars
            ):
                if chars:
                    return word[:chars]
                return word

        # Fallback to first word
        if words:
            return words[0][:chars] if chars else words[0]
        return ""

    def _extract_word(self, entry: Entry, position: int | None = None) -> str:
        """Extract significant word from title."""
        if not entry.title:
            return ""

        # Clean title
        title = self._clean_text(entry.title)

        # Get significant words
        words = [
            w
            for w in title.split()
            if w.lower() not in self.STOPWORDS
            and len(w) >= self.pattern.min_title_chars
            and not w.isdigit()
        ]

        if not words:
            return ""

        # Get word at position (1-indexed)
        if position and 0 < position <= len(words):
            return words[position - 1]
        else:
            return words[0]

    def _extract_journal(self, entry: Entry, chars: int | None = None) -> str:
        """Extract journal information."""
        if not entry.journal:
            return ""

        # Clean journal name
        journal = self._clean_text(entry.journal)

        words = journal.split()
        if not words:
            return ""

        # Check for common abbreviations
        if all(w.isupper() and len(w) <= 4 for w in words[:3]):
            # Looks like an acronym (e.g., "IEEE Trans.")
            return "".join(words[:2]).lower()

        # Use first word
        result = words[0]
        if chars:
            result = result[:chars]
        else:
            result = result[:4]

        return result

    def _clean_text(self, text: str) -> str:
        """Clean text for key generation."""
        # Remove LaTeX commands
        text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
        text = re.sub(r"\\[a-zA-Z]+", "", text)

        # Remove math mode
        text = re.sub(r"\$[^$]*\$", "", text)

        # Remove special characters but keep hyphens
        text = re.sub(r"[^a-zA-Z0-9\s-]", "", text)

        return text

    def _apply_case(self, key: str) -> str:
        """Apply case transformation to key."""
        match self.pattern.case:
            case "lower":
                return key.lower()
            case "upper":
                return key.upper()
            case "title":
                # Capitalize first letter of each component
                # If we added underscores for processing, remove them
                if "_" in key and self.pattern.separator == "":
                    parts = key.split("_")
                    return "".join(p.capitalize() for p in parts)
                else:
                    parts = re.split(r"([_-])", key)
                    return "".join(
                        p.capitalize() if p not in "_-" else p for p in parts
                    )
            case "camel":
                # camelCase
                parts = re.split(r"[_-]", key)
                if parts:
                    result = parts[0].lower() + "".join(
                        p.capitalize() for p in parts[1:]
                    )
                    return result
                return key
            case _:
                return key

    def _auto_disambiguate(self, base_key: str) -> str:
        """Auto-disambiguate keys for same author/year."""
        if base_key not in self._generated_keys:
            # First occurrence of this base key
            self._generated_keys[base_key] = 1
            return base_key

        # Already exists, add suffix based on occurrence count
        count = self._generated_keys[base_key]
        self._generated_keys[base_key] = count + 1

        # Generate suffix: first duplicate gets 'a', second gets 'b', etc.
        suffix = chr(ord("a") + count - 1)
        return f"{base_key}{suffix}"

    def _resolve_collision(self, base_key: str, entry: Entry) -> str:
        """Resolve key collision using configured strategy."""
        if not self.exists_checker or not self.exists_checker.exists(base_key):
            return base_key

        match self.collision_strategy:
            case KeyCollisionStrategy.APPEND_LETTER:
                for suffix in "abcdefghijklmnopqrstuvwxyz":
                    candidate = f"{base_key}{suffix}"
                    if not self.exists_checker.exists(candidate):
                        return candidate
                # Fallback to numbers
                return self._append_number(base_key)

            case KeyCollisionStrategy.APPEND_NUMBER:
                return self._append_number(base_key)

            case KeyCollisionStrategy.APPEND_WORD:
                words = self._get_title_words(entry)
                for word in words[1:]:  # Skip first (likely already used)
                    candidate = f"{base_key}_{word.lower()}"
                    if not self.exists_checker.exists(candidate):
                        return candidate
                # Fallback to numbers
                return self._append_number(base_key)

            case KeyCollisionStrategy.INTERACTIVE:
                if self.prompt_user:
                    return self.prompt_user(base_key, entry)
                # Fallback to letter appending
                return self._resolve_collision_with_strategy(
                    base_key, entry, KeyCollisionStrategy.APPEND_LETTER
                )

            case KeyCollisionStrategy.FAIL:
                raise ValueError(f"Key collision: {base_key} already exists")

            case _:
                return base_key

    def _append_number(self, base_key: str) -> str:
        """Append number to make key unique."""
        for i in range(1, 1000):
            candidate = f"{base_key}_{i}"
            if not self.exists_checker or not self.exists_checker.exists(candidate):
                return candidate
        raise ValueError(f"Cannot find unique key for {base_key}")

    def _get_title_words(self, entry: Entry) -> list[str]:
        """Get significant words from title."""
        if not entry.title:
            return []

        title = self._clean_text(entry.title)

        words = [
            w
            for w in title.split()
            if w.lower() not in self.STOPWORDS
            and len(w) >= self.pattern.min_title_chars
            and not w.isdigit()
        ]

        return words

    def _resolve_collision_with_strategy(
        self,
        base_key: str,
        entry: Entry,
        strategy: KeyCollisionStrategy,
    ) -> str:
        """Resolve collision with specific strategy."""
        old_strategy = self.collision_strategy
        self.collision_strategy = strategy
        try:
            return self._resolve_collision(base_key, entry)
        finally:
            self.collision_strategy = old_strategy


class AsyncKeyGenerator:
    """Asynchronous citation key generator."""

    def __init__(
        self,
        pattern: KeyPattern | str = "{author}{year}",
        collision_strategy: KeyCollisionStrategy = KeyCollisionStrategy.APPEND_LETTER,
        exists_checker: Any | None = None,  # AsyncKeyExistsChecker
    ):
        """Initialize async key generator."""
        self.sync_generator = CitationKeyGenerator(pattern, collision_strategy, None)
        self.exists_checker = exists_checker
        self.collision_strategy = collision_strategy

    async def generate_async(self, entry: Entry) -> str:
        """Generate key asynchronously."""
        base_key = self.sync_generator._generate_base_key(entry)
        base_key = self.sync_generator._apply_case(base_key)

        if self.exists_checker:
            key = await self._resolve_collision_async(base_key, entry)
        else:
            key = base_key

        if not self.sync_generator.validator.is_valid(key):
            key = self.sync_generator.validator.sanitize(key)

        return key

    async def generate_batch(self, entries: list[Entry]) -> list[str]:
        """Generate keys for multiple entries concurrently."""
        tasks = [self.generate_async(entry) for entry in entries]
        return await asyncio.gather(*tasks)

    async def _resolve_collision_async(self, base_key: str, entry: Entry) -> str:
        """Resolve collision asynchronously."""
        if not self.exists_checker:
            return base_key
        if not await self.exists_checker.exists(base_key):
            return base_key

        match self.collision_strategy:
            case KeyCollisionStrategy.APPEND_LETTER:
                for suffix in "abcdefghijklmnopqrstuvwxyz":
                    candidate = f"{base_key}{suffix}"
                    if self.exists_checker and not await self.exists_checker.exists(
                        candidate
                    ):
                        return candidate
                return await self._append_number_async(base_key)

            case KeyCollisionStrategy.APPEND_NUMBER:
                return await self._append_number_async(base_key)

            case KeyCollisionStrategy.APPEND_WORD:
                words = self.sync_generator._get_title_words(entry)
                for word in words[1:]:
                    candidate = f"{base_key}_{word.lower()}"
                    if self.exists_checker and not await self.exists_checker.exists(
                        candidate
                    ):
                        return candidate
                return await self._append_number_async(base_key)

            case KeyCollisionStrategy.FAIL:
                raise ValueError(f"Key collision: {base_key} already exists")

            case _:
                return base_key

    async def _append_number_async(self, base_key: str) -> str:
        """Append number asynchronously."""
        if not self.exists_checker:
            return f"{base_key}_1"
        for i in range(1, 1000):
            candidate = f"{base_key}_{i}"
            if not await self.exists_checker.exists(candidate):
                return candidate
        raise ValueError(f"Cannot find unique key for {base_key}")
