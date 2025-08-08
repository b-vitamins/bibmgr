"""Query parsing and understanding with natural language support."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from rapidfuzz import fuzz, process


class QueryOperator(Enum):
    """Boolean operators for query composition."""

    AND = auto()
    OR = auto()
    NOT = auto()
    PHRASE = auto()  # Exact phrase match


class QueryField(str, Enum):
    """Searchable fields with special handling."""

    ALL = "all"
    TITLE = "title"
    AUTHOR = "author"
    ABSTRACT = "abstract"
    KEYWORDS = "keywords"
    YEAR = "year"
    VENUE = "venue"
    TYPE = "type"


@dataclass
class QueryTerm:
    """A single term in a parsed query."""

    text: str
    field: QueryField = QueryField.ALL
    operator: QueryOperator | None = None
    is_negated: bool = False
    is_phrase: bool = False
    is_wildcard: bool = False
    boost: float = 1.0

    # For range queries
    range_start: Any = None
    range_end: Any = None

    # For proximity search
    proximity_next: int | None = None  # Distance to next term

    def __str__(self) -> str:
        """String representation for debugging."""
        prefix = "-" if self.is_negated else ""
        field_prefix = f"{self.field.value}:" if self.field != QueryField.ALL else ""
        quotes = '"' if self.is_phrase else ""
        boost_suffix = f"^{self.boost}" if self.boost != 1.0 else ""
        return f"{prefix}{field_prefix}{quotes}{self.text}{quotes}{boost_suffix}"


@dataclass
class Query:
    """Parsed and analyzed search query."""

    original: str
    terms: list[QueryTerm] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)

    # Query understanding
    intent: str | None = None  # browsing, lookup, research
    domain_terms: list[str] = field(default_factory=list)

    # Scoring preferences
    prefer_recent: bool = False
    prefer_cited: bool = False

    def has_field_queries(self) -> bool:
        """Check if query has field-specific terms."""
        return any(t.field != QueryField.ALL for t in self.terms)

    def get_field_terms(self, field: QueryField) -> list[QueryTerm]:
        """Get all terms for a specific field."""
        return [t for t in self.terms if t.field == field]


class QueryParser:
    """Advanced query parser with natural language understanding."""

    # Common CS abbreviations and expansions
    ABBREVIATIONS = {
        "ml": "machine learning",
        "dl": "deep learning",
        "ai": "artificial intelligence",
        "nlp": "natural language processing",
        "cv": "computer vision",
        "rl": "reinforcement learning",
        "gan": "generative adversarial network",
        "lstm": "long short term memory",
        "cnn": "convolutional neural network",
        "rnn": "recurrent neural network",
        "bert": "bidirectional encoder representations transformers",
        "gpt": "generative pretrained transformer",
        "hci": "human computer interaction",
        "os": "operating system",
        "db": "database",
        "ds": "distributed systems",
    }

    # Synonyms for query expansion
    SYNONYMS = {
        "neural network": ["deep learning", "neural net", "ann"],
        "machine learning": ["ml", "statistical learning", "pattern recognition"],
        "optimization": ["optimisation", "optimal", "minimize", "maximize"],
        "algorithm": ["method", "approach", "technique", "procedure"],
        "performance": ["speed", "efficiency", "fast", "quick"],
        "accuracy": ["precision", "recall", "f1", "error rate"],
    }

    # Domain-specific boosting
    FIELD_BOOSTS = {
        QueryField.TITLE: 2.0,
        QueryField.AUTHOR: 1.5,
        QueryField.KEYWORDS: 1.5,
        QueryField.ABSTRACT: 1.0,
        QueryField.VENUE: 1.2,
    }

    def parse(self, query_string: str) -> Query:
        """Parse a query string into structured Query object.

        Supports:
        - Field queries: author:knuth title:"art of programming"
        - Boolean: machine learning AND neural networks
        - Negation: python -java
        - Wildcards: optim*
        - Phrases: "exact phrase match"
        - Ranges: year:2020..2024
        - Boosting: important^2 normal
        """
        query = Query(original=query_string)

        # Normalize and tokenize
        normalized = self._normalize(query_string)
        tokens = self._tokenize(normalized)

        # Parse tokens into terms
        query.terms = self._parse_tokens(tokens)

        # Extract filters
        query.filters = self._extract_filters(query.terms)

        # Understand query intent
        query.intent = self._detect_intent(query)

        # Expand with synonyms and abbreviations
        self._expand_query(query)

        return query

    def _normalize(self, text: str) -> str:
        """Normalize query text."""
        # Preserve structure but clean up
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize while preserving structure."""
        # Pattern matches:
        # - field:"quoted value"
        # - "quoted strings"
        # - field:value
        # - operators (AND, OR, NOT)
        # - NEAR/n
        # - words
        pattern = r'[a-z]+:"[^"]*"|"[^"]*"|[a-z]+:[^\s]+|AND|OR|NOT|NEAR/\d+|\S+'
        return re.findall(pattern, text, re.IGNORECASE)

    def _parse_tokens(self, tokens: list[str]) -> list[QueryTerm]:
        """Parse tokens into QueryTerm objects."""
        terms = []
        i = 0

        while i < len(tokens):
            token = tokens[i]

            # Check for operators
            if token.upper() in {"AND", "OR", "NOT"}:
                if token.upper() == "NOT" and i + 1 < len(tokens):
                    # NOT modifies next term
                    i += 1
                    term = self._parse_single_term(tokens[i])
                    term.is_negated = True
                    terms.append(term)
                # AND/OR handled by search engine
                i += 1
                continue

            # Check for NEAR operator
            if token.upper().startswith("NEAR/"):
                # Extract distance
                try:
                    distance = int(token.split("/")[1])
                    # Mark previous and next terms as proximity pair
                    if terms and i + 1 < len(tokens):
                        terms[-1].proximity_next = distance
                except (ValueError, IndexError):
                    pass
                i += 1
                continue

            # Check for negation prefix
            if token.startswith("-") and len(token) > 1:
                term = self._parse_single_term(token[1:])
                term.is_negated = True
                terms.append(term)
                i += 1
                continue

            # Parse as term
            term = self._parse_single_term(token)
            terms.append(term)
            i += 1

        return terms

    def _parse_single_term(self, token: str) -> QueryTerm:
        """Parse a single token into a QueryTerm."""
        term = QueryTerm(text=token)

        # Check for field query (before phrase check)
        if ":" in token and not token.startswith("http"):
            field_name, value = token.split(":", 1)
            field_name_upper = field_name.upper()

            # Map field name to QueryField enum
            if field_name_upper in QueryField.__members__:
                term.field = QueryField[field_name_upper]
                term.text = value

                # Check if value is quoted (phrase)
                if value.startswith('"') and value.endswith('"'):
                    term.text = value[1:-1]
                    term.is_phrase = True

                # Apply field boost
                term.boost = self.FIELD_BOOSTS.get(term.field, 1.0)

                # Check for wildcard
                if "*" in term.text or "?" in term.text:
                    term.is_wildcard = True

                # Check for boost in the value
                if "^" in term.text and not term.is_phrase:
                    parts = term.text.split("^")
                    if len(parts) == 2 and parts[1].replace(".", "").isdigit():
                        term.text = parts[0]
                        term.boost = float(parts[1])

                return term

        # Check for phrase (quoted)
        if token.startswith('"') and token.endswith('"'):
            term.text = token[1:-1]
            term.is_phrase = True
            return term

        # Check for wildcard
        if "*" in term.text or "?" in term.text:
            term.is_wildcard = True

        # Check for boost
        if "^" in term.text:
            parts = term.text.split("^")
            if len(parts) == 2 and parts[1].replace(".", "").isdigit():
                term.text = parts[0]
                term.boost = float(parts[1])

        return term

    def _extract_filters(self, terms: list[QueryTerm]) -> dict[str, Any]:
        """Extract filters from query terms."""
        filters = {}

        for term in terms:
            # Year range detection
            if term.field == QueryField.YEAR:
                if ".." in term.text:
                    start, end = term.text.split("..")
                    filters["year_range"] = (int(start), int(end))
                elif term.text.isdigit():
                    filters["year"] = int(term.text)

            # Type filter
            elif term.field == QueryField.TYPE:
                filters["entry_type"] = term.text.lower()

        return filters

    def _detect_intent(self, query: Query) -> str:
        """Detect the search intent from query structure."""
        # Simple heuristics for intent detection

        if len(query.terms) == 1 and query.terms[0].field == QueryField.AUTHOR:
            return "author_lookup"

        if any(t.field == QueryField.YEAR for t in query.terms):
            query.prefer_recent = True
            return "temporal_research"

        if len(query.terms) > 3:
            return "research"  # Complex research query

        return "browsing"  # General browsing

    def _expand_query(self, query: Query) -> None:
        """Expand query with synonyms and abbreviations."""
        expanded = []

        for term in query.terms:
            if term.field != QueryField.ALL:
                continue  # Don't expand field-specific queries

            text_lower = term.text.lower()

            # Check abbreviations
            if text_lower in self.ABBREVIATIONS:
                expansion = self.ABBREVIATIONS[text_lower]
                # Add expanded term with lower boost
                exp_term = QueryTerm(text=expansion, boost=0.7)
                expanded.append(exp_term)

            # Check synonyms
            for main_term, synonyms in self.SYNONYMS.items():
                if text_lower == main_term:
                    for syn in synonyms:
                        exp_term = QueryTerm(text=syn, boost=0.7)
                        expanded.append(exp_term)
                elif text_lower in synonyms:
                    exp_term = QueryTerm(text=main_term, boost=0.7)
                    expanded.append(exp_term)

        # Add expanded terms to query
        query.terms.extend(expanded)


class QuerySuggester:
    """Suggest query completions and corrections."""

    def __init__(self, vocabulary: set[str] | None = None):
        """Initialize with optional vocabulary."""
        self.vocabulary = vocabulary or set()
        self.query_history: list[str] = []

    def suggest_corrections(self, query: str) -> list[tuple[str, float]]:
        """Suggest spelling corrections using fuzzy matching."""
        if not self.vocabulary:
            return []

        words = query.split()
        corrections = []

        for word in words:
            if word.lower() not in self.vocabulary:
                # Find close matches
                matches = process.extract(
                    word, self.vocabulary, scorer=fuzz.ratio, limit=3
                )
                corrections.extend(matches)

        return corrections

    def suggest_completions(self, partial: str) -> list[str]:
        """Suggest query completions based on history."""
        if not self.query_history:
            return []

        # Find queries starting with partial
        completions = [
            q for q in self.query_history if q.lower().startswith(partial.lower())
        ]

        # Sort by frequency/recency (simple version - just return first 5)
        return completions[:5]
