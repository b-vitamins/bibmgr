"""Tests for the ranking module."""

from datetime import datetime, timedelta
from math import log

import pytest

from bibmgr.core import Entry, EntryType
from bibmgr.search.backends.base import SearchMatch
from bibmgr.search.ranking import (
    BM25Ranker,
    BoostingRanker,
    CompoundRanker,
    FieldWeights,
    RankingAlgorithm,
    RecencyRanker,
    ScoringContext,
    TFIDFRanker,
    compute_bm25_score,
    compute_tfidf_score,
)


class TestRankingAlgorithms:
    """Test base ranking algorithm functionality."""

    def test_ranking_algorithm_interface(self):
        """Test that RankingAlgorithm defines proper interface."""
        # Should be an abstract base class - verify it has abstract methods
        assert hasattr(RankingAlgorithm, "__abstractmethods__")
        assert len(RankingAlgorithm.__abstractmethods__) > 0

        # Verify the abstract methods
        assert "score" in RankingAlgorithm.__abstractmethods__
        assert "rank" in RankingAlgorithm.__abstractmethods__

        # Concrete implementation should work
        class SimpleRanker(RankingAlgorithm):
            def score(self, match, query_terms, context):
                return 1.0

            def rank(self, matches, query_terms, context):
                for match in matches:
                    match.score = self.score(match, query_terms, context)
                return sorted(matches, key=lambda m: m.score, reverse=True)

        ranker = SimpleRanker()
        assert ranker is not None


class TestBM25Ranking:
    """Test BM25 ranking algorithm."""

    @pytest.fixture
    def bm25_ranker(self):
        """Create BM25 ranker with default parameters."""
        return BM25Ranker(k1=1.2, b=0.75)

    @pytest.fixture
    def scoring_context(self):
        """Create scoring context with document statistics."""
        return ScoringContext(
            total_docs=1000,
            avg_doc_length=150,
            doc_frequencies={
                "machine": 100,
                "learning": 150,
                "neural": 80,
                "network": 90,
                "deep": 70,
                "algorithm": 200,
            },
            field_lengths={
                "title": 10,
                "abstract": 100,
                "keywords": 5,
            },
        )

    def test_bm25_score_calculation(self):
        """Test BM25 score calculation."""
        # Test the pure BM25 scoring function
        score = compute_bm25_score(
            term_freq=3,  # Term appears 3 times
            doc_freq=100,  # Term appears in 100 docs
            doc_length=200,  # Document has 200 terms
            avg_length=150,  # Average doc length is 150
            total_docs=1000,  # Total 1000 documents
            k1=1.2,
            b=0.75,
        )

        # Score should be positive
        assert score > 0

        # Higher term frequency should increase score
        score_higher_tf = compute_bm25_score(5, 100, 200, 150, 1000, 1.2, 0.75)
        assert score_higher_tf > score

        # Rarer terms (lower doc freq) should score higher
        score_rare = compute_bm25_score(3, 10, 200, 150, 1000, 1.2, 0.75)
        assert score_rare > score

    def test_bm25_ranker_scoring(self, bm25_ranker, scoring_context):
        """Test BM25 ranker on search matches."""
        # Create test matches
        matches = [
            SearchMatch(
                entry_key="doc1",
                score=0.0,
                entry=Entry(
                    key="doc1",
                    type=EntryType.ARTICLE,
                    title="Machine Learning Algorithms",
                    abstract="Deep learning neural networks for machine learning.",
                ),
            ),
            SearchMatch(
                entry_key="doc2",
                score=0.0,
                entry=Entry(
                    key="doc2",
                    type=EntryType.ARTICLE,
                    title="Neural Network Theory",
                    abstract="Theory of neural networks and deep learning algorithms.",
                ),
            ),
            SearchMatch(
                entry_key="doc3",
                score=0.0,
                entry=Entry(
                    key="doc3",
                    type=EntryType.ARTICLE,
                    title="Learning Systems",
                    abstract="Various learning systems and algorithms.",
                ),
            ),
        ]

        # Rank for query "machine learning"
        query_terms = ["machine", "learning"]
        ranked = bm25_ranker.rank(matches, query_terms, scoring_context)

        # All should have scores
        assert all(m.score > 0 for m in ranked)

        # doc1 should rank highest (has both terms in title)
        assert ranked[0].entry_key == "doc1"

        # Scores should be in descending order
        scores = [m.score for m in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_bm25_field_weighting(self):
        """Test BM25 with field-specific weights."""
        field_weights = FieldWeights(
            {
                "title": 2.0,  # Title matches are twice as important
                "abstract": 1.0,
                "keywords": 1.5,
            }
        )

        ranker = BM25Ranker(k1=1.2, b=0.75, field_weights=field_weights)

        # Create matches where terms appear in different fields
        matches = [
            SearchMatch(
                entry_key="title_match",
                score=0.0,
                entry=Entry(
                    key="title_match",
                    type=EntryType.ARTICLE,
                    title="Machine Learning",  # Query terms in title
                    abstract="General computer science topics.",
                ),
            ),
            SearchMatch(
                entry_key="abstract_match",
                score=0.0,
                entry=Entry(
                    key="abstract_match",
                    type=EntryType.ARTICLE,
                    title="Computer Science",
                    abstract="Machine learning algorithms and techniques.",  # Query terms in abstract
                ),
            ),
        ]

        context = ScoringContext(
            total_docs=100,
            avg_doc_length=50,
            doc_frequencies={"machine": 20, "learning": 30},
        )

        ranked = ranker.rank(matches, ["machine", "learning"], context)

        # Title match should score higher due to field weight
        assert ranked[0].entry_key == "title_match"
        assert ranked[0].score > ranked[1].score


class TestTFIDFRanking:
    """Test TF-IDF ranking algorithm."""

    @pytest.fixture
    def tfidf_ranker(self):
        """Create TF-IDF ranker."""
        return TFIDFRanker()

    def test_tfidf_score_calculation(self):
        """Test TF-IDF score calculation."""
        # Test the pure TF-IDF scoring function
        score = compute_tfidf_score(
            term_freq=3,  # Term appears 3 times
            doc_freq=100,  # Term appears in 100 docs
            total_docs=1000,  # Total 1000 documents
            doc_length=200,  # Document has 200 terms
        )

        # Score should be positive
        assert score > 0

        # TF component
        tf = 3 / 200  # Term frequency / doc length

        # IDF component
        idf = log(1000 / 100)

        # Score should be TF * IDF
        expected = tf * idf
        assert abs(score - expected) < 0.001

    def test_tfidf_ranker_scoring(self, tfidf_ranker):
        """Test TF-IDF ranker on search matches."""
        matches = [
            SearchMatch(
                entry_key="doc1",
                score=0.0,
                entry=Entry(
                    key="doc1",
                    type=EntryType.ARTICLE,
                    title="Information Retrieval",
                    abstract="Information retrieval systems and algorithms.",
                ),
            ),
            SearchMatch(
                entry_key="doc2",
                score=0.0,
                entry=Entry(
                    key="doc2",
                    type=EntryType.ARTICLE,
                    title="Database Systems",
                    abstract="Information storage and retrieval in databases.",
                ),
            ),
        ]

        context = ScoringContext(
            total_docs=1000,
            avg_doc_length=100,
            doc_frequencies={"information": 200, "retrieval": 150},
        )

        ranked = tfidf_ranker.rank(matches, ["information", "retrieval"], context)

        # Both should have scores
        assert all(m.score > 0 for m in ranked)

        # doc1 should rank higher (both terms in title)
        assert ranked[0].entry_key == "doc1"


class TestBoostingRanker:
    """Test boosting ranker for custom score adjustments."""

    def test_field_boost_ranker(self):
        """Test ranker that boosts certain fields."""

        # Create ranker that boosts journal articles
        def journal_boost(match, query, context):
            if match.entry and match.entry.journal:
                return 1.5  # 50% boost
            return 1.0

        ranker = BoostingRanker(base_ranker=BM25Ranker(), boost_function=journal_boost)

        matches = [
            SearchMatch(
                entry_key="journal_article",
                score=0.0,
                entry=Entry(
                    key="journal_article",
                    type=EntryType.ARTICLE,
                    title="Machine Learning",
                    journal="ML Journal",
                ),
            ),
            SearchMatch(
                entry_key="conference_paper",
                score=0.0,
                entry=Entry(
                    key="conference_paper",
                    type=EntryType.INPROCEEDINGS,
                    title="Machine Learning",
                    booktitle="ML Conference",
                ),
            ),
        ]

        context = ScoringContext(total_docs=100, avg_doc_length=50)
        ranked = ranker.rank(matches, ["machine", "learning"], context)

        # Journal article should rank higher due to boost
        assert ranked[0].entry_key == "journal_article"

    def test_query_dependent_boost(self):
        """Test boost that depends on query terms."""

        # Boost documents that have all query terms in title
        def title_completeness_boost(match, query, context):
            if not match.entry:
                return 1.0

            title_lower = match.entry.title.lower()
            if all(term in title_lower for term in query):
                return 2.0  # Double score for complete title matches
            return 1.0

        ranker = BoostingRanker(
            base_ranker=TFIDFRanker(), boost_function=title_completeness_boost
        )

        matches = [
            SearchMatch(
                entry_key="partial_match",
                score=0.0,
                entry=Entry(
                    key="partial_match",
                    type=EntryType.ARTICLE,
                    title="Neural Networks",  # Only has "neural"
                    abstract="Deep neural networks for learning.",
                ),
            ),
            SearchMatch(
                entry_key="complete_match",
                score=0.0,
                entry=Entry(
                    key="complete_match",
                    type=EntryType.ARTICLE,
                    title="Deep Neural Networks",  # Has both terms
                    abstract="Introduction to networks.",
                ),
            ),
        ]

        context = ScoringContext(total_docs=100, avg_doc_length=50)
        ranked = ranker.rank(matches, ["deep", "neural"], context)

        # Complete match should rank higher
        assert ranked[0].entry_key == "complete_match"


class TestRecencyRanker:
    """Test recency-based ranking."""

    def test_recency_ranker(self):
        """Test ranker that prioritizes recent documents."""
        ranker = RecencyRanker(
            base_ranker=BM25Ranker(),
            decay_rate=0.1,  # 10% decay per year
            reference_date=datetime(2024, 1, 1),
        )

        now = datetime(2024, 1, 1)

        matches = [
            SearchMatch(
                entry_key="old_paper",
                score=0.0,
                entry=Entry(
                    key="old_paper",
                    type=EntryType.ARTICLE,
                    title="Machine Learning",
                    year=2020,
                    added=now - timedelta(days=1460),  # 4 years old
                ),
            ),
            SearchMatch(
                entry_key="new_paper",
                score=0.0,
                entry=Entry(
                    key="new_paper",
                    type=EntryType.ARTICLE,
                    title="Machine Learning",
                    year=2023,
                    added=now - timedelta(days=365),  # 1 year old
                ),
            ),
        ]

        context = ScoringContext(total_docs=100, avg_doc_length=50)
        ranked = ranker.rank(matches, ["machine", "learning"], context)

        # Newer paper should rank higher despite same content
        assert ranked[0].entry_key == "new_paper"

        # Score ratio should reflect decay
        # 3 year difference = 0.9^3 ≈ 0.729
        score_ratio = ranked[1].score / ranked[0].score
        assert 0.7 < score_ratio < 0.75


class TestCompoundRanker:
    """Test compound ranking with multiple algorithms."""

    def test_weighted_combination(self):
        """Test combining multiple rankers with weights."""
        ranker = CompoundRanker(
            [
                (BM25Ranker(), 0.7),  # 70% weight
                (TFIDFRanker(), 0.3),  # 30% weight
            ]
        )

        matches = [
            SearchMatch(
                entry_key="doc1",
                score=0.0,
                entry=Entry(
                    key="doc1",
                    type=EntryType.ARTICLE,
                    title="Information Retrieval",
                    abstract="Modern information retrieval techniques.",
                ),
            ),
            SearchMatch(
                entry_key="doc2",
                score=0.0,
                entry=Entry(
                    key="doc2",
                    type=EntryType.ARTICLE,
                    title="Search Algorithms",
                    abstract="Information retrieval and search algorithms.",
                ),
            ),
        ]

        context = ScoringContext(
            total_docs=1000,
            avg_doc_length=100,
            doc_frequencies={"information": 200, "retrieval": 150},
        )

        ranked = ranker.rank(matches, ["information", "retrieval"], context)

        # Both should have scores
        assert all(m.score > 0 for m in ranked)

        # Scores should be weighted combination
        # (Can't test exact values without running individual rankers)

    def test_fallback_ranking(self):
        """Test fallback when primary ranker fails."""

        # Create a failing ranker
        class FailingRanker(RankingAlgorithm):
            def score(self, match, query_terms, context):
                raise ValueError("Ranker failed")

            def rank(self, matches, query_terms, context):
                raise ValueError("Ranker failed")

        # Compound with fallback
        ranker = CompoundRanker(
            [
                (FailingRanker(), 0.9),
                (BM25Ranker(), 0.1),  # Fallback
            ],
            fallback_on_error=True,
        )

        matches = [
            SearchMatch(entry_key="doc1", score=0.0),
            SearchMatch(entry_key="doc2", score=0.0),
        ]

        context = ScoringContext(total_docs=100, avg_doc_length=50)

        # Should not raise, fallback to BM25
        ranked = ranker.rank(matches, ["test"], context)
        assert len(ranked) == 2


class TestRankingIntegration:
    """Test ranking integration with search engine."""

    def test_custom_ranker_in_search_engine(self):
        """Test using custom ranker in search engine."""
        from bibmgr.search import SearchEngineBuilder

        # Create simple in-memory repository
        class SimpleRepository:
            def __init__(self):
                self.entries = {}

            def add(self, entry):
                self.entries[entry.key] = entry

            def find(self, key):
                return self.entries.get(key)

        # Create custom ranker that prioritizes books
        class BookPriorityRanker(RankingAlgorithm):
            def score(self, match, query_terms, context):
                # Simple scoring: books get score 2.0, articles get 1.0
                if match.entry and match.entry.type == EntryType.BOOK:
                    return 2.0
                return 1.0

            def rank(self, matches, query_terms, context):
                for match in matches:
                    match.score = self.score(match, query_terms, context)
                return sorted(matches, key=lambda m: m.score, reverse=True)

        # Create repository and add entries
        repository = SimpleRepository()

        entries = [
            Entry(
                key="article1",
                type=EntryType.ARTICLE,
                title="Machine Learning Fundamentals",
                author="Smith, J.",
            ),
            Entry(
                key="book1",
                type=EntryType.BOOK,
                title="Machine Learning Textbook",
                author="Jones, A.",
            ),
        ]

        for entry in entries:
            repository.add(entry)

        # Create engine with custom ranker and repository
        engine = (
            SearchEngineBuilder()
            .with_ranker(BookPriorityRanker())
            .with_repository(repository)
            .build()
        )

        # Index entries
        engine.index_entries(entries)

        # Search
        results = engine.search("machine learning")

        # Verify we have matches
        assert len(results.matches) == 2

        # Book should rank higher due to custom ranker
        assert results.matches[0].entry_key == "book1"
        assert results.matches[0].score == 2.0
        assert results.matches[1].entry_key == "article1"
        assert results.matches[1].score == 1.0

    def test_field_specific_ranking(self):
        """Test ranking with field-specific scoring."""
        from bibmgr.search import (
            FieldConfiguration,
            FieldDefinition,
            FieldType,
            SearchEngine,
        )

        # Configure fields with different boosts
        field_config = FieldConfiguration()
        field_config.fields["title"] = FieldDefinition(
            name="title",
            field_type=FieldType.TEXT,
            boost=3.0,  # Triple weight for title
        )
        field_config.fields["abstract"] = FieldDefinition(
            name="abstract", field_type=FieldType.TEXT, boost=1.0
        )

        # Create engine with field-aware ranker
        engine = SearchEngine(field_config=field_config)
        engine.ranker = BM25Ranker(
            field_weights=FieldWeights(
                {
                    "title": 3.0,
                    "abstract": 1.0,
                }
            )
        )

        # Create test entries
        entries = [
            Entry(
                key="abstract_match",
                type=EntryType.ARTICLE,
                title="Unrelated Topic",
                abstract="Deep learning neural networks",  # Query match in abstract
            ),
            Entry(
                key="title_match",
                type=EntryType.ARTICLE,
                title="Neural Networks",  # Query match in title
                abstract="Unrelated content",
            ),
        ]

        engine.index_entries(entries)

        # Search
        results = engine.search("neural networks")

        # Title match should rank much higher
        assert results.matches[0].entry_key == "title_match"
