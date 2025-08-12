"""Ranking algorithms for search results.

This module provides various ranking algorithms including BM25, TF-IDF,
and custom scoring functions to order search results by relevance.
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from .backends.base import SearchMatch


@dataclass
class FieldWeights:
    """Field-specific weight configuration for ranking."""

    def __init__(self, weights: dict[str, float] | None = None):
        """Initialize field weights.

        Args:
            weights: Dict mapping field names to weight multipliers
        """
        # Default weights
        self.weights = {
            "title": 2.0,
            "abstract": 1.0,
            "keywords": 1.5,
            "author": 1.2,
            "journal": 0.8,
            "booktitle": 0.8,
            "note": 0.5,
        }

        # Apply custom weights
        if weights:
            self.weights.update(weights)

    def get_weight(self, field: str) -> float:
        """Get weight for a field."""
        return self.weights.get(field, 1.0)


@dataclass
class ScoringContext:
    """Context information needed for scoring calculations."""

    total_docs: int
    avg_doc_length: float
    doc_frequencies: dict[str, int] = field(default_factory=dict)
    field_lengths: dict[str, float] = field(default_factory=dict)
    query_time_ms: int | None = None


class RankingAlgorithm(ABC):
    """Abstract base class for ranking algorithms."""

    @abstractmethod
    def score(
        self, match: SearchMatch, query_terms: list[str], context: ScoringContext
    ) -> float:
        """Calculate relevance score for a match.

        Args:
            match: Search match to score
            query_terms: List of query terms
            context: Scoring context with collection statistics

        Returns:
            Relevance score (higher is better)
        """
        pass

    @abstractmethod
    def rank(
        self,
        matches: list[SearchMatch],
        query_terms: list[str],
        context: ScoringContext,
    ) -> list[SearchMatch]:
        """Rank matches by relevance.

        Args:
            matches: List of matches to rank
            query_terms: List of query terms
            context: Scoring context

        Returns:
            List of matches sorted by relevance (highest first)
        """
        pass


def compute_bm25_score(
    term_freq: int,
    doc_freq: int,
    doc_length: int,
    avg_length: float,
    total_docs: int,
    k1: float = 1.2,
    b: float = 0.75,
) -> float:
    """Compute BM25 score for a term in a document.

    Args:
        term_freq: Frequency of term in document
        doc_freq: Number of documents containing term
        doc_length: Length of document
        avg_length: Average document length in collection
        total_docs: Total number of documents
        k1: Term frequency saturation parameter
        b: Length normalization parameter

    Returns:
        BM25 score for the term
    """
    # IDF component with protection against negative log
    numerator = total_docs - doc_freq + 0.5
    denominator = doc_freq + 0.5

    # Ensure we don't take log of negative or zero
    if numerator <= 0 or denominator <= 0:
        idf = 0.0
    else:
        idf = math.log(numerator / denominator)

    # TF component with length normalization
    if avg_length <= 0:
        avg_length = 1.0  # Prevent division by zero

    denominator = term_freq + k1 * (1 - b + b * (doc_length / avg_length))
    if denominator <= 0:
        tf_component = 0.0
    else:
        tf_component = (term_freq * (k1 + 1)) / denominator

    return idf * tf_component


def compute_tfidf_score(
    term_freq: int, doc_freq: int, total_docs: int, doc_length: int
) -> float:
    """Compute TF-IDF score for a term in a document.

    Args:
        term_freq: Frequency of term in document
        doc_freq: Number of documents containing term
        total_docs: Total number of documents
        doc_length: Length of document

    Returns:
        TF-IDF score for the term
    """
    # TF component (normalized by document length)
    tf = term_freq / doc_length if doc_length > 0 else 0

    # IDF component
    idf = math.log(total_docs / doc_freq) if doc_freq > 0 else 0

    return tf * idf


class BM25Ranker(RankingAlgorithm):
    """BM25 ranking algorithm implementation."""

    def __init__(
        self,
        k1: float = 1.2,
        b: float = 0.75,
        field_weights: FieldWeights | None = None,
    ):
        """Initialize BM25 ranker.

        Args:
            k1: Term frequency saturation parameter
            b: Length normalization parameter
            field_weights: Field-specific weights
        """
        self.k1 = k1
        self.b = b
        self.field_weights = field_weights or FieldWeights()

    def score(
        self, match: SearchMatch, query_terms: list[str], context: ScoringContext
    ) -> float:
        """Calculate BM25 score for a match."""
        if not match.entry:
            return 0.0

        total_score = 0.0

        for term in query_terms:
            term_lower = term.lower()

            doc_freq = context.doc_frequencies.get(term_lower, 1)

            field_scores = {}

            if match.entry.title:
                tf = match.entry.title.lower().count(term_lower)
                if tf > 0:
                    field_length = len(match.entry.title.split())
                    field_scores["title"] = compute_bm25_score(
                        tf,
                        doc_freq,
                        field_length,
                        context.field_lengths.get("title", 10),
                        context.total_docs,
                        self.k1,
                        self.b,
                    )

            if match.entry.abstract:
                tf = match.entry.abstract.lower().count(term_lower)
                if tf > 0:
                    field_length = len(match.entry.abstract.split())
                    field_scores["abstract"] = compute_bm25_score(
                        tf,
                        doc_freq,
                        field_length,
                        context.field_lengths.get("abstract", 100),
                        context.total_docs,
                        self.k1,
                        self.b,
                    )

            # Keywords field
            if match.entry.keywords:
                keyword_text = " ".join(match.entry.keywords).lower()
                tf = keyword_text.count(term_lower)
                if tf > 0:
                    field_length = len(keyword_text.split())
                    field_scores["keywords"] = compute_bm25_score(
                        tf,
                        doc_freq,
                        field_length,
                        context.field_lengths.get("keywords", 5),
                        context.total_docs,
                        self.k1,
                        self.b,
                    )

            # Apply field weights and sum
            for field_name, score in field_scores.items():
                weight = self.field_weights.get_weight(field_name)
                total_score += score * weight

        return total_score

    def rank(
        self,
        matches: list[SearchMatch],
        query_terms: list[str],
        context: ScoringContext,
    ) -> list[SearchMatch]:
        """Rank matches using BM25."""
        # Score each match
        for match in matches:
            match.score = self.score(match, query_terms, context)

        # Sort by score descending
        return sorted(matches, key=lambda m: m.score, reverse=True)


class TFIDFRanker(RankingAlgorithm):
    """TF-IDF ranking algorithm implementation."""

    def __init__(self, field_weights: FieldWeights | None = None):
        """Initialize TF-IDF ranker.

        Args:
            field_weights: Field-specific weights
        """
        self.field_weights = field_weights or FieldWeights()

    def score(
        self, match: SearchMatch, query_terms: list[str], context: ScoringContext
    ) -> float:
        """Calculate TF-IDF score for a match."""
        if not match.entry:
            return 0.0

        total_score = 0.0

        for term in query_terms:
            term_lower = term.lower()

            # Get document frequency
            doc_freq = context.doc_frequencies.get(term_lower, 1)

            field_scores = {}

            if match.entry.title:
                tf = match.entry.title.lower().count(term_lower)
                if tf > 0:
                    field_length = len(match.entry.title.split())
                    field_scores["title"] = compute_tfidf_score(
                        tf, doc_freq, context.total_docs, field_length
                    )

            if match.entry.abstract:
                tf = match.entry.abstract.lower().count(term_lower)
                if tf > 0:
                    field_length = len(match.entry.abstract.split())
                    field_scores["abstract"] = compute_tfidf_score(
                        tf, doc_freq, context.total_docs, field_length
                    )

            # Apply field weights
            for field_name, score in field_scores.items():
                weight = self.field_weights.get_weight(field_name)
                total_score += score * weight

        return total_score

    def rank(
        self,
        matches: list[SearchMatch],
        query_terms: list[str],
        context: ScoringContext,
    ) -> list[SearchMatch]:
        """Rank matches using TF-IDF."""
        for match in matches:
            match.score = self.score(match, query_terms, context)

        return sorted(matches, key=lambda m: m.score, reverse=True)


class BoostingRanker(RankingAlgorithm):
    """Ranker that applies custom boost functions to base scores."""

    def __init__(self, base_ranker: RankingAlgorithm, boost_function):
        """Initialize boosting ranker.

        Args:
            base_ranker: Base ranking algorithm
            boost_function: Function(match, query, context) -> boost_factor
        """
        self.base_ranker = base_ranker
        self.boost_function = boost_function

    def score(
        self, match: SearchMatch, query_terms: list[str], context: ScoringContext
    ) -> float:
        """Calculate boosted score."""
        base_score = self.base_ranker.score(match, query_terms, context)
        boost = self.boost_function(match, query_terms, context)
        return base_score * boost

    def rank(
        self,
        matches: list[SearchMatch],
        query_terms: list[str],
        context: ScoringContext,
    ) -> list[SearchMatch]:
        """Rank with boosting."""
        for match in matches:
            match.score = self.score(match, query_terms, context)

        return sorted(matches, key=lambda m: m.score, reverse=True)


class RecencyRanker(RankingAlgorithm):
    """Ranker that prioritizes recent documents."""

    def __init__(
        self,
        base_ranker: RankingAlgorithm,
        decay_rate: float = 0.1,
        reference_date: datetime | None = None,
    ):
        """Initialize recency ranker.

        Args:
            base_ranker: Base ranking algorithm
            decay_rate: Score decay per year (0-1)
            reference_date: Reference date for recency calculation
        """
        self.base_ranker = base_ranker
        self.decay_rate = decay_rate
        self.reference_date = reference_date or datetime.now()

    def score(
        self, match: SearchMatch, query_terms: list[str], context: ScoringContext
    ) -> float:
        """Calculate recency-adjusted score."""
        base_score = self.base_ranker.score(match, query_terms, context)

        if not match.entry:
            return base_score

        # Calculate age factor
        age_factor = 1.0

        # Try to get date from entry
        entry_date = None
        if hasattr(match.entry, "added") and match.entry.added:
            entry_date = match.entry.added
        elif hasattr(match.entry, "year") and match.entry.year:
            # Use publication year as approximation
            try:
                entry_date = datetime(match.entry.year, 1, 1)
            except (ValueError, TypeError):
                pass

        if entry_date and isinstance(entry_date, datetime):
            # Calculate years difference
            years_old = (self.reference_date - entry_date).days / 365.25

            # Apply exponential decay
            age_factor = (1 - self.decay_rate) ** years_old

        return base_score * age_factor

    def rank(
        self,
        matches: list[SearchMatch],
        query_terms: list[str],
        context: ScoringContext,
    ) -> list[SearchMatch]:
        """Rank with recency adjustment."""
        for match in matches:
            match.score = self.score(match, query_terms, context)

        return sorted(matches, key=lambda m: m.score, reverse=True)


class CompoundRanker(RankingAlgorithm):
    """Combines multiple ranking algorithms with weights."""

    def __init__(
        self,
        rankers: list[tuple[RankingAlgorithm, float]],
        fallback_on_error: bool = False,
    ):
        """Initialize compound ranker.

        Args:
            rankers: List of (ranker, weight) tuples
            fallback_on_error: Whether to continue with other rankers on error
        """
        self.rankers = rankers
        self.fallback_on_error = fallback_on_error

        # Normalize weights
        total_weight = sum(weight for _, weight in rankers)
        self.rankers = [(ranker, weight / total_weight) for ranker, weight in rankers]

    def score(
        self, match: SearchMatch, query_terms: list[str], context: ScoringContext
    ) -> float:
        """Calculate weighted combination of scores."""
        total_score = 0.0

        for ranker, weight in self.rankers:
            try:
                score = ranker.score(match, query_terms, context)
                total_score += score * weight
            except Exception:
                if not self.fallback_on_error:
                    raise
                # Continue with other rankers

        return total_score

    def rank(
        self,
        matches: list[SearchMatch],
        query_terms: list[str],
        context: ScoringContext,
    ) -> list[SearchMatch]:
        """Rank using weighted combination."""
        for match in matches:
            match.score = self.score(match, query_terms, context)

        return sorted(matches, key=lambda m: m.score, reverse=True)
