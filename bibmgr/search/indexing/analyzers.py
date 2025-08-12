"""Text analyzers for search indexing.

This module provides text analysis tools including tokenization, stemming,
synonym expansion, and normalization for bibliography entries.
"""

import re
import unicodedata
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass

from whoosh.lang.porter import stem as porter_stem
from whoosh.lang.stopwords import stoplists

try:
    import enchant

    ENCHANT_AVAILABLE = True
except ImportError:
    enchant = None  # type: ignore
    ENCHANT_AVAILABLE = False


@dataclass
class AnalyzerConfig:
    """Configuration for text analysis pipeline."""

    lowercase: bool = True
    remove_accents: bool = True
    split_camelcase: bool = True
    remove_stopwords: bool = True
    stem: bool = True
    min_token_length: int = 2
    max_token_length: int = 50
    stopwords: set[str] | None = None

    def __post_init__(self):
        """Initialize stopwords if not provided."""
        if self.stopwords is None and self.remove_stopwords:
            # Use Whoosh's English stopword list
            self.stopwords = set(stoplists["en"])


class TextProcessor:
    """Configurable text processing pipeline for search indexing.

    This class provides a flexible text processing pipeline that can be
    configured for different use cases (default search, exact match, etc).
    """

    # Predefined configurations
    CONFIGS = {
        "default": AnalyzerConfig(),
        "exact": AnalyzerConfig(
            lowercase=True,  # Still lowercase for case-insensitive search
            remove_accents=False,
            split_camelcase=False,
            remove_stopwords=False,
            stem=False,
        ),
        "keyword": AnalyzerConfig(
            lowercase=True,
            remove_accents=True,
            split_camelcase=False,
            remove_stopwords=False,
            stem=False,
            min_token_length=1,
        ),
    }

    def __init__(self, config: AnalyzerConfig | None = None):
        """Initialize processor with configuration.

        Args:
            config: Optional configuration, defaults to 'default' config
        """
        self.config = config or self.CONFIGS["default"]

    def process(self, text: str, config_name: str | None = None) -> str:
        """Process text through the configured pipeline.

        Args:
            text: Input text to process
            config_name: Optional config name to use instead of instance config

        Returns:
            Processed text with tokens joined by spaces
        """
        if not text:
            return ""

        # Use named config if provided
        config = (
            self.CONFIGS.get(config_name, self.config) if config_name else self.config
        )

        # Apply pre-tokenization transformations
        if config.split_camelcase:
            text = self._split_camelcase(text)

        if config.remove_accents:
            text = self._remove_accents(text)

        # Tokenize
        tokens = self._tokenize(text)

        # Process tokens
        processed_tokens = []
        for token in tokens:
            # Length filtering
            if (
                len(token) < config.min_token_length
                or len(token) > config.max_token_length
            ):
                continue

            # Lowercase
            if config.lowercase:
                token = token.lower()

            # Stop word removal
            if config.remove_stopwords and config.stopwords:
                if token.lower() in config.stopwords:
                    continue

            # Stemming
            if config.stem:
                token = self._stem(token)

            processed_tokens.append(token)

        return " ".join(processed_tokens)

    def tokenize(self, text: str) -> list[str]:
        """Just tokenize text without any processing.

        Args:
            text: Input text

        Returns:
            List of raw tokens
        """
        return self._tokenize(text)

    def generate_ngrams(self, text: str, n: int = 3) -> str:
        """Generate character n-grams for fuzzy matching.

        Args:
            text: Input text
            n: Size of n-grams (default 3)

        Returns:
            Space-separated n-grams
        """
        if not text or len(text) < n:
            return ""

        ngrams = []
        text = text.lower()

        # Generate n-grams for each word
        words = text.split()
        for word in words:
            if len(word) >= n:
                for i in range(len(word) - n + 1):
                    ngrams.append(word[i : i + n])

        return " ".join(ngrams)

    def extract_keywords(self, text: str, max_keywords: int = 10) -> list[str]:
        """Extract keywords based on frequency after processing.

        Args:
            text: Input text
            max_keywords: Maximum keywords to return

        Returns:
            List of keywords ordered by frequency
        """
        # Process with default config
        processed = self.process(text)
        if not processed:
            return []

        tokens = processed.split()
        freq_counter = Counter(tokens)

        return [term for term, _ in freq_counter.most_common(max_keywords)]

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into words.

        Splits on common punctuation and word boundaries.
        """
        # Replace common word separators with spaces
        text = re.sub(r'[-_,;.:!?&/\\(){}[\]"\'`~@#$%^*+=|<>]', " ", text)

        # Extract words (letters and numbers)
        tokens = re.findall(r"\w+", text)

        return tokens

    def _remove_accents(self, text: str) -> str:
        """Remove diacritical marks from text."""
        # Normalize to NFD (decomposed form)
        nfd = unicodedata.normalize("NFD", text)
        # Filter out combining characters (accents)
        return "".join(char for char in nfd if unicodedata.category(char) != "Mn")

    def _split_camelcase(self, text: str) -> str:
        """Split CamelCase words into separate words."""
        # Insert space before uppercase letters that follow lowercase
        result = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
        # Insert space before uppercase letters followed by lowercase
        result = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", result)
        return result

    def _stem(self, word: str) -> str:
        """Apply Porter stemming to a word.

        Uses Whoosh's Porter stemmer implementation.
        """
        if len(word) <= 3:
            return word

        stemmed = porter_stem(word)

        # Ensure we don't over-stem (keep at least 2 characters)
        if len(stemmed) >= 2:
            return stemmed
        return word


class SynonymExpander:
    """Expands queries with synonyms and related terms.

    Handles bidirectional synonym expansion for academic/technical terms.
    """

    # Default academic/CS synonyms
    DEFAULT_SYNONYMS = {
        "ml": ["machine learning"],
        "ai": ["artificial intelligence"],
        "nn": ["neural network"],
        "nlp": ["natural language processing"],
        "cv": ["computer vision"],
        "dl": ["deep learning"],
        "rl": ["reinforcement learning"],
        "gan": ["generative adversarial network"],
        "rnn": ["recurrent neural network"],
        "cnn": ["convolutional neural network"],
        "lstm": ["long short term memory"],
        "bert": ["bidirectional encoder representations from transformers"],
        "gpt": ["generative pretrained transformer"],
        "db": ["database"],
        "hci": ["human computer interaction"],
        "os": ["operating systems"],
        "algo": ["algorithms"],
        "ds": ["data structures"],
        "se": ["software engineering"],
    }

    def __init__(self, custom_synonyms: dict[str, list[str]] | None = None):
        """Initialize with default and optional custom synonyms.

        Args:
            custom_synonyms: Additional synonyms to add/override defaults
        """
        # Start with defaults
        self.synonyms = self.DEFAULT_SYNONYMS.copy()

        # Add/override with custom synonyms
        if custom_synonyms:
            self.synonyms.update(custom_synonyms)

        # Build reverse mapping for bidirectional expansion
        self.reverse_synonyms = {}
        for abbrev, expansions in self.synonyms.items():
            for expansion in expansions:
                self.reverse_synonyms[expansion] = abbrev

    def expand(self, text: str) -> str:
        """Expand text with synonyms using OR clauses.

        Args:
            text: Query text to expand

        Returns:
            Expanded query with OR clauses for synonyms
        """
        if not text:
            return ""

        # Handle whitespace-only text
        if not text.strip():
            return text

        text_lower = text.lower()
        words = text_lower.split()
        expanded_parts = []

        i = 0
        while i < len(words):
            expanded = False

            # Try multi-word phrases first (up to 5 words)
            for phrase_len in range(min(5, len(words) - i), 0, -1):
                phrase = " ".join(words[i : i + phrase_len])

                # Check if phrase has synonyms
                if phrase in self.synonyms:
                    # Expand abbreviation
                    expansions = [phrase] + self.synonyms[phrase]
                    expanded_parts.append("(" + " OR ".join(expansions) + ")")
                    i += phrase_len
                    expanded = True
                    break
                elif phrase in self.reverse_synonyms:
                    # Expand full form to include abbreviation
                    abbrev = self.reverse_synonyms[phrase]
                    expanded_parts.append(f"({phrase} OR {abbrev})")
                    i += phrase_len
                    expanded = True
                    break

            if not expanded:
                # No expansion found, keep original word
                expanded_parts.append(words[i])
                i += 1

        return " ".join(expanded_parts)

    def get_synonyms(self, term: str) -> list[str]:
        """Get all synonyms for a term.

        Args:
            term: Term to look up

        Returns:
            List of synonyms (empty if none found)
        """
        term_lower = term.lower()

        # Check both directions
        synonyms = []
        if term_lower in self.synonyms:
            synonyms.extend(self.synonyms[term_lower])
        if term_lower in self.reverse_synonyms:
            synonyms.append(self.reverse_synonyms[term_lower])

        return synonyms


# Analyzer implementations for Whoosh integration
class TextAnalyzer(ABC):
    """Abstract base class for text analyzers.

    These analyzers are designed to work with the search backend
    and return lists of tokens for indexing.
    """

    @abstractmethod
    def analyze(self, text: str) -> list[str]:
        """Analyze text and return list of tokens.

        Args:
            text: Input text to analyze

        Returns:
            List of analyzed tokens
        """
        pass


class SimpleAnalyzer(TextAnalyzer):
    """Basic analyzer with tokenization and lowercasing."""

    def __init__(self):
        self.processor = TextProcessor(
            AnalyzerConfig(
                lowercase=True,
                remove_accents=False,
                split_camelcase=False,
                remove_stopwords=False,
                stem=False,
            )
        )

    def analyze(self, text: str) -> list[str]:
        """Tokenize and lowercase text."""
        if not text:
            return []
        result = self.processor.process(text)
        return result.split() if result else []


class StandardAnalyzer(TextAnalyzer):
    """Standard analyzer with stopword removal."""

    def __init__(self):
        self.processor = TextProcessor(
            AnalyzerConfig(
                lowercase=True,
                remove_accents=True,
                split_camelcase=False,
                remove_stopwords=True,
                stem=False,
            )
        )

    def analyze(self, text: str) -> list[str]:
        """Standard text analysis pipeline."""
        if not text:
            return []
        result = self.processor.process(text)
        return result.split() if result else []


class StemmingAnalyzer(TextAnalyzer):
    """Analyzer with stemming support."""

    def __init__(self):
        self.processor = TextProcessor(
            AnalyzerConfig(
                lowercase=True,
                remove_accents=True,
                split_camelcase=True,
                remove_stopwords=True,
                stem=True,
            )
        )

    def analyze(self, text: str) -> list[str]:
        """Full text analysis with stemming."""
        if not text:
            return []
        result = self.processor.process(text)
        return result.split() if result else []


class KeywordAnalyzer(TextAnalyzer):
    """Treats entire input as single token (for exact matching)."""

    def analyze(self, text: str) -> list[str]:
        """Return text as single lowercase token."""
        if not text:
            return []
        return [text.lower().strip()]


class AuthorAnalyzer(TextAnalyzer):
    """Specialized analyzer for author names."""

    def analyze(self, text: str) -> list[str]:
        """Analyze author names handling common patterns."""
        if not text:
            return []

        # Split on 'and' or commas
        authors = re.split(r"\s+and\s+|,\s*", text)

        tokens = []
        for author in authors:
            author = author.strip()
            if not author:
                continue

            # Add full name as token
            tokens.append(author.lower())

            # Add individual name parts
            parts = author.split()
            for part in parts:
                # Remove punctuation
                clean_part = re.sub(r"[.,]", "", part).lower()
                if clean_part and len(clean_part) > 1:
                    tokens.append(clean_part)
                elif len(clean_part) == 1:
                    # Single character (initial)
                    tokens.append(clean_part)

        # Remove duplicates while preserving order
        seen = set()
        unique_tokens = []
        for token in tokens:
            if token not in seen:
                seen.add(token)
                unique_tokens.append(token)

        return unique_tokens


class AnalyzerManager:
    """Manages analyzers for different field types."""

    def __init__(self):
        """Initialize with default analyzers."""
        self.analyzers = {
            "simple": SimpleAnalyzer(),
            "standard": StandardAnalyzer(),
            "stemming": StemmingAnalyzer(),
            "keyword": KeywordAnalyzer(),
            "author": AuthorAnalyzer(),
        }

        # Default field mappings
        self.field_analyzers = {
            "title": "stemming",
            "abstract": "stemming",
            "keywords": "stemming",
            "note": "standard",
            "author": "author",
            "editor": "author",
            "journal": "keyword",
            "booktitle": "keyword",
            "publisher": "keyword",
            "series": "keyword",
            "school": "keyword",
            "institution": "keyword",
            "organization": "keyword",
            "doi": "keyword",
            "isbn": "keyword",
            "issn": "keyword",
            "url": "keyword",
        }

    def get_analyzer(self, field: str) -> TextAnalyzer:
        """Get analyzer for a field.

        Args:
            field: Field name

        Returns:
            Appropriate analyzer for the field
        """
        analyzer_name = self.field_analyzers.get(field, "standard")
        return self.analyzers.get(analyzer_name, self.analyzers["standard"])

    def analyze_field(self, field: str, text: str) -> list[str]:
        """Analyze text for a specific field.

        Args:
            field: Field name
            text: Text to analyze

        Returns:
            List of tokens
        """
        analyzer = self.get_analyzer(field)
        return analyzer.analyze(text)


class SpellChecker:
    """Spell checker using PyEnchant library.

    Provides spell checking and correction suggestions for search queries.
    Falls back gracefully if enchant is not available.
    """

    def __init__(self, language: str = "en_US", custom_words: list[str] | None = None):
        """Initialize spell checker.

        Args:
            language: Language code for spell checking (default: en_US)
            custom_words: List of custom words to add to dictionary
        """
        self.language = language
        self.dict = None

        if ENCHANT_AVAILABLE and enchant:
            try:
                self.dict = enchant.Dict(language)

                # Add custom words if provided
                if custom_words:
                    for word in custom_words:
                        self.add_word(word)

                # Add common CS/academic terms
                self._add_default_terms()
            except Exception:
                # Language not available, fall back to None
                self.dict = None

    def _add_default_terms(self):
        """Add common CS and academic terms to dictionary."""
        if not self.dict:
            return

        # Common CS terms that might not be in standard dictionaries
        cs_terms = [
            "bibtex",
            "latex",
            "doi",
            "isbn",
            "issn",
            "arxiv",
            "acm",
            "ieee",
            "dataset",
            "datasets",
            "metadata",
            "workflow",
            "workflows",
            "blockchain",
            "cryptocurrency",
            "backend",
            "frontend",
            "middleware",
            "microservice",
            "microservices",
            "api",
            "apis",
            "json",
            "xml",
            "sql",
            "nosql",
            "mongodb",
            "postgresql",
            "redis",
            "elasticsearch",
            "kubernetes",
            "docker",
            "containerization",
            "virtualization",
            "github",
            "gitlab",
            "bitbucket",
            "versioning",
            "refactoring",
            "unittest",
            "pytest",
            "debugging",
            "profiling",
            "benchmarking",
        ]

        for term in cs_terms:
            if not self.dict.check(term):
                self.dict.add(term)

    def check(self, word: str) -> bool:
        """Check if a word is spelled correctly.

        Args:
            word: Word to check

        Returns:
            True if word is correct or checker unavailable
        """
        if not self.dict:
            return True  # No checker available, assume correct

        return self.dict.check(word)

    def suggest(self, word: str, max_suggestions: int = 5) -> list[str]:
        """Get spelling suggestions for a word.

        Args:
            word: Misspelled word
            max_suggestions: Maximum number of suggestions

        Returns:
            List of suggested corrections
        """
        if not self.dict:
            return []

        suggestions = self.dict.suggest(word)
        return suggestions[:max_suggestions]

    def add_word(self, word: str) -> None:
        """Add a word to the personal dictionary.

        Args:
            word: Word to add
        """
        if self.dict and word:
            self.dict.add(word)

    def correct_query(self, query: str) -> tuple[str, list[str]]:
        """Correct spelling in a query string.

        Args:
            query: Query string to check

        Returns:
            Tuple of (corrected query, list of corrections made)
        """
        if not self.dict:
            return query, []

        words = query.split()
        corrected_words = []
        corrections = []

        for word in words:
            # Skip if it's a field query (contains :)
            if ":" in word:
                corrected_words.append(word)
                continue

            # Skip if it's already correct
            if self.check(word):
                corrected_words.append(word)
                continue

            # Get suggestions
            suggestions = self.suggest(word, 1)
            if suggestions:
                corrected_words.append(suggestions[0])
                corrections.append(f"{word} -> {suggestions[0]}")
            else:
                corrected_words.append(word)

        corrected_query = " ".join(corrected_words)
        return corrected_query, corrections
