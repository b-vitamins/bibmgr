"""Tests for query expander."""

from unittest.mock import Mock

import pytest

from bibmgr.search.indexing.analyzers import SpellChecker, SynonymExpander
from bibmgr.search.query.expander import QueryExpander, QuerySuggestion
from bibmgr.search.query.parser import (
    BooleanOperator,
    BooleanQuery,
    FieldQuery,
    FuzzyQuery,
    ParsedQuery,
    PhraseQuery,
    TermQuery,
    WildcardQuery,
)


class TestQueryExpander:
    """Test QueryExpander class."""

    @pytest.fixture
    def spell_checker(self):
        """Create a mock spell checker."""
        checker = Mock(spec=SpellChecker)
        # Mock suggest to return empty by default
        checker.suggest.return_value = []
        return checker

    @pytest.fixture
    def synonym_expander(self):
        """Create a mock synonym expander with test data."""
        expander = Mock(spec=SynonymExpander)
        expander.synonyms = {
            "ml": ["machine learning"],
            "ai": ["artificial intelligence"],
            "dl": ["deep learning"],
            "db": ["database"],
            "cs": ["computer science"],
        }
        expander.reverse_synonyms = {
            "machine learning": "ml",
            "artificial intelligence": "ai",
            "deep learning": "dl",
            "database": "db",
            "computer science": "cs",
        }
        return expander

    @pytest.fixture
    def expander(self, spell_checker, synonym_expander):
        """Create query expander with mocked components."""
        return QueryExpander(
            spell_checker=spell_checker, synonym_expander=synonym_expander
        )

    def test_expander_initialization(self):
        """Expander should initialize with default components."""
        expander = QueryExpander()

        assert expander.spell_checker is not None
        assert expander.synonym_expander is not None
        assert expander.field_expansions is not None
        assert expander.expansion_boosts is not None

        # Check default field expansions
        assert "title" in expander.field_expansions
        assert "author" in expander.field_expansions
        assert "venue" in expander.field_expansions
        assert "content" in expander.field_expansions

    def test_expander_custom_components(self, spell_checker, synonym_expander):
        """Expander should accept custom components."""
        expander = QueryExpander(
            spell_checker=spell_checker, synonym_expander=synonym_expander
        )

        assert expander.spell_checker is spell_checker
        assert expander.synonym_expander is synonym_expander

    def test_expand_query_no_expansion(self, expander):
        """Query expansion with all options disabled should return original."""
        query = TermQuery("testing")

        expanded = expander.expand_query(
            query, expand_synonyms=False, expand_fields=False, correct_spelling=False
        )

        assert expanded is query

    def test_expand_synonym_single_term(self, expander):
        """Single term with synonym should be expanded."""
        query = TermQuery("ml")

        expanded = expander.expand_query(
            query, expand_synonyms=True, expand_fields=False, correct_spelling=False
        )

        assert isinstance(expanded, BooleanQuery)
        assert expanded.operator == BooleanOperator.OR
        assert len(expanded.queries) == 2

        # Check original and synonym
        terms = [q.term for q in expanded.queries if isinstance(q, TermQuery)]
        assert "ml" in terms
        assert "machine learning" in terms

    def test_expand_synonym_preserves_boost(self, expander):
        """Synonym expansion should adjust boost values."""
        query = TermQuery("ml", boost=2.0)

        expanded = expander.expand_query(
            query, expand_synonyms=True, expand_fields=False, correct_spelling=False
        )

        assert isinstance(expanded, BooleanQuery)

        # Original term keeps full boost
        original = next(
            q for q in expanded.queries if isinstance(q, TermQuery) and q.term == "ml"
        )
        assert isinstance(original, TermQuery)
        assert original.boost == 2.0

        # Synonym gets reduced boost
        synonym = next(
            q
            for q in expanded.queries
            if isinstance(q, TermQuery) and q.term == "machine learning"
        )
        assert isinstance(synonym, TermQuery)
        assert synonym.boost == 2.0 * 0.7

    def test_expand_phrase_synonym(self, expander):
        """Phrase queries with synonyms should be expanded."""
        query = PhraseQuery("artificial intelligence")

        # Add phrase to synonyms
        expander.synonym_expander.synonyms["artificial intelligence"] = ["ai"]

        expanded = expander.expand_query(
            query, expand_synonyms=True, expand_fields=False, correct_spelling=False
        )

        assert isinstance(expanded, BooleanQuery)
        assert expanded.operator == BooleanOperator.OR
        assert len(expanded.queries) == 2

        # Check phrases
        phrases = [q.phrase for q in expanded.queries if isinstance(q, PhraseQuery)]
        assert "artificial intelligence" in phrases
        assert "ai" in phrases

    def test_expand_field_query(self, expander):
        """Field queries should expand to related fields."""
        query = FieldQuery("title", TermQuery("learning"))

        expanded = expander.expand_query(
            query, expand_synonyms=False, expand_fields=True, correct_spelling=False
        )

        assert isinstance(expanded, BooleanQuery)
        assert expanded.operator == BooleanOperator.OR

        # Should expand title to title and abstract
        field_queries = [q for q in expanded.queries if isinstance(q, FieldQuery)]
        fields = [q.field for q in field_queries]
        assert "title" in fields
        assert "abstract" in fields

    def test_expand_field_query_boost_adjustment(self, expander):
        """Field expansion should adjust boost values."""
        query = FieldQuery("title", TermQuery("learning", boost=2.0))

        expanded = expander.expand_query(
            query, expand_synonyms=False, expand_fields=True, correct_spelling=False
        )

        assert isinstance(expanded, BooleanQuery)

        # Check boost adjustments
        for field_query in expanded.queries:
            if isinstance(field_query, FieldQuery):
                term_query = field_query.query
                assert isinstance(term_query, TermQuery)
                if field_query.field == "title":
                    assert term_query.boost == 2.0 * 1.0  # Full boost
                elif field_query.field == "abstract":
                    assert term_query.boost == 2.0 * 0.5  # Reduced boost

    def test_expand_boolean_query(self, expander):
        """Boolean queries should expand recursively."""
        query = BooleanQuery(
            BooleanOperator.AND, [TermQuery("ml"), TermQuery("research")]
        )

        expanded = expander.expand_query(
            query, expand_synonyms=True, expand_fields=False, correct_spelling=False
        )

        assert isinstance(expanded, BooleanQuery)
        assert expanded.operator == BooleanOperator.AND

        # At least one child should be expanded
        has_expansion = any(
            isinstance(q, BooleanQuery) and q.operator == BooleanOperator.OR
            for q in expanded.queries
        )
        assert has_expansion

    def test_spelling_correction_single_term(self, expander):
        """Spelling correction should create OR query with suggestions."""
        query = TermQuery("machne")  # Misspelled "machine"

        # Mock spell checker to return correction
        expander.spell_checker.suggest.return_value = ["machine"]

        expanded = expander.expand_query(
            query, expand_synonyms=False, expand_fields=False, correct_spelling=True
        )

        assert isinstance(expanded, BooleanQuery)
        assert expanded.operator == BooleanOperator.OR
        assert len(expanded.queries) == 2

        # Check original and corrected
        terms = [q.term for q in expanded.queries if isinstance(q, TermQuery)]
        assert "machne" in terms
        assert "machine" in terms

    def test_spelling_correction_phrase(self, expander):
        """Spelling correction should work on phrases."""
        query = PhraseQuery("machne learning")  # Misspelled "machine"

        # Mock spell checker
        def mock_suggest(term, count):
            if term == "machne":
                return ["machine"]
            return []

        expander.spell_checker.suggest.side_effect = mock_suggest

        expanded = expander.expand_query(
            query, expand_synonyms=False, expand_fields=False, correct_spelling=True
        )

        assert isinstance(expanded, BooleanQuery)
        assert expanded.operator == BooleanOperator.OR

        # Check phrases
        phrases = [q.phrase for q in expanded.queries if isinstance(q, PhraseQuery)]
        assert "machne learning" in phrases
        assert "machine learning" in phrases

    def test_suggest_corrections_spelling(self, expander):
        """Should generate spelling correction suggestions."""
        query = TermQuery("machne")

        # Mock spell checker
        expander.spell_checker.suggest.return_value = ["machine"]

        suggestions = expander.suggest_corrections(query)

        assert len(suggestions) > 0
        spelling_suggestions = [
            s for s in suggestions if s.suggestion_type == "spelling"
        ]
        assert len(spelling_suggestions) > 0

        suggestion = spelling_suggestions[0]
        assert "machine" in suggestion.suggested_query
        assert suggestion.confidence == 0.8

    def test_suggest_corrections_synonyms(self, expander):
        """Should generate synonym suggestions."""
        query = TermQuery("ml")

        suggestions = expander.suggest_corrections(query)

        synonym_suggestions = [s for s in suggestions if s.suggestion_type == "synonym"]
        assert len(synonym_suggestions) > 0

        suggestion = synonym_suggestions[0]
        assert "machine learning" in suggestion.suggested_query
        assert suggestion.confidence == 0.7

    def test_suggest_corrections_field_expansion(self, expander):
        """Should generate field expansion suggestions."""
        query = FieldQuery("title", TermQuery("learning"))

        suggestions = expander.suggest_corrections(query)

        expansion_suggestions = [
            s for s in suggestions if s.suggestion_type == "expansion"
        ]
        assert len(expansion_suggestions) > 0

        suggestion = expansion_suggestions[0]
        assert "abstract" in suggestion.suggested_query
        assert suggestion.confidence == 0.6

    def test_relax_query_level_1(self, expander):
        """Level 1 relaxation should convert AND to OR."""
        query = BooleanQuery(
            BooleanOperator.AND, [TermQuery("machine"), TermQuery("learning")]
        )

        relaxed = expander.relax_query(query, relaxation_level=1)

        assert isinstance(relaxed, BooleanQuery)
        assert relaxed.operator == BooleanOperator.OR

    def test_relax_query_level_2(self, expander):
        """Level 2 relaxation should add fuzzy matching."""
        query = TermQuery("machine")

        relaxed = expander.relax_query(query, relaxation_level=2)

        assert isinstance(relaxed, BooleanQuery)
        assert relaxed.operator == BooleanOperator.OR

        # Should have original and fuzzy query
        has_fuzzy = any(isinstance(q, FuzzyQuery) for q in relaxed.queries)
        assert has_fuzzy

    def test_relax_query_level_3(self, expander):
        """Level 3 relaxation should add wildcard expansion."""
        query = TermQuery("machine")

        relaxed = expander.relax_query(query, relaxation_level=3)

        # Should have wildcard patterns
        # Level 3 applies all relaxations
        def has_wildcard(q):
            if isinstance(q, WildcardQuery):
                return True
            if isinstance(q, BooleanQuery):
                return any(has_wildcard(subq) for subq in q.queries)
            return False

        assert has_wildcard(relaxed)

    def test_relax_query_no_relaxation(self, expander):
        """Level 0 relaxation should return original query."""
        query = TermQuery("machine")

        relaxed = expander.relax_query(query, relaxation_level=0)

        assert relaxed is query

    def test_add_synonym_mapping(self, expander):
        """Should allow adding custom synonym mappings."""
        expander.add_synonym_mapping(
            "gpu", ["graphics processing unit", "graphics card"]
        )

        assert "gpu" in expander.synonym_expander.synonyms
        assert "graphics processing unit" in expander.synonym_expander.synonyms["gpu"]
        assert "graphics card" in expander.synonym_expander.synonyms["gpu"]

        # Check reverse mapping
        assert (
            expander.synonym_expander.reverse_synonyms["graphics processing unit"]
            == "gpu"
        )

    def test_add_field_expansion(self, expander):
        """Should allow adding custom field expansions."""
        expander.add_field_expansion(
            "keywords",
            ["keywords", "tags", "categories"],
            {"keywords": 1.0, "tags": 0.8, "categories": 0.6},
        )

        assert "keywords" in expander.field_expansions
        assert expander.field_expansions["keywords"] == [
            "keywords",
            "tags",
            "categories",
        ]
        assert expander.expansion_boosts["keywords"]["tags"] == 0.8

    def test_add_field_expansion_default_boosts(self, expander):
        """Should generate default boosts if not provided."""
        expander.add_field_expansion("custom", ["field1", "field2", "field3"])

        assert "custom" in expander.expansion_boosts
        boosts = expander.expansion_boosts["custom"]
        assert boosts["field1"] == 1.0
        assert boosts["field2"] == 0.8
        assert boosts["field3"] == 0.6

    def test_complex_query_expansion(self, expander):
        """Complex queries should be expanded correctly."""
        # (ml AND research) OR (ai AND applications)
        query = BooleanQuery(
            BooleanOperator.OR,
            [
                BooleanQuery(
                    BooleanOperator.AND, [TermQuery("ml"), TermQuery("research")]
                ),
                BooleanQuery(
                    BooleanOperator.AND, [TermQuery("ai"), TermQuery("applications")]
                ),
            ],
        )

        expanded = expander.expand_query(query, expand_synonyms=True)

        assert isinstance(expanded, BooleanQuery)
        assert expanded.operator == BooleanOperator.OR

        # Structure should be preserved but terms expanded
        def count_terms(q):
            if isinstance(q, TermQuery):
                return 1
            elif isinstance(q, BooleanQuery):
                return sum(count_terms(subq) for subq in q.queries)
            elif isinstance(q, FieldQuery):
                return count_terms(q.query)
            else:
                return 0

        # Should have more terms after expansion
        original_count = count_terms(query)
        expanded_count = count_terms(expanded)
        assert expanded_count > original_count

    def test_wildcard_not_expanded(self, expander):
        """Wildcard queries should not be synonym-expanded."""
        query = WildcardQuery("mach*")

        expanded = expander.expand_query(query, expand_synonyms=True)

        # Should remain a wildcard query
        assert isinstance(expanded, WildcardQuery)
        assert expanded.pattern == "mach*"

    def test_fuzzy_not_expanded(self, expander):
        """Fuzzy queries should not be synonym-expanded."""
        query = FuzzyQuery("machine", max_edits=2)

        expanded = expander.expand_query(query, expand_synonyms=True)

        # Should remain a fuzzy query
        assert isinstance(expanded, FuzzyQuery)
        assert expanded.term == "machine"


class TestQuerySuggestion:
    """Test QuerySuggestion dataclass."""

    def test_suggestion_creation(self):
        """Should create suggestion with all fields."""
        suggestion = QuerySuggestion(
            original_query="machne learning",
            suggested_query="machine learning",
            suggestion_type="spelling",
            confidence=0.9,
            explanation="Did you mean 'machine'?",
        )

        assert suggestion.original_query == "machne learning"
        assert suggestion.suggested_query == "machine learning"
        assert suggestion.suggestion_type == "spelling"
        assert suggestion.confidence == 0.9
        assert suggestion.explanation == "Did you mean 'machine'?"

    def test_suggestion_comparison(self):
        """Suggestions should be sortable by confidence."""
        suggestions = [
            QuerySuggestion("a", "b", "spelling", 0.5, "test"),
            QuerySuggestion("c", "d", "synonym", 0.8, "test"),
            QuerySuggestion("e", "f", "expansion", 0.3, "test"),
        ]

        sorted_suggestions = sorted(
            suggestions, key=lambda x: x.confidence, reverse=True
        )

        assert sorted_suggestions[0].confidence == 0.8
        assert sorted_suggestions[1].confidence == 0.5
        assert sorted_suggestions[2].confidence == 0.3


class TestIntegration:
    """Integration tests for query expansion."""

    def test_full_expansion_pipeline(self):
        """Test complete expansion with real components."""
        expander = QueryExpander()

        # Complex query with multiple expansion opportunities
        query = BooleanQuery(
            BooleanOperator.AND,
            [FieldQuery("title", TermQuery("ml")), TermQuery("research")],
        )

        expanded = expander.expand_query(query)

        # Should be expanded but maintain structure
        assert isinstance(expanded, BooleanQuery)
        assert expanded.operator == BooleanOperator.AND

    def test_real_world_query(self):
        """Test with realistic search query."""
        expander = QueryExpander()

        # User searching for machine learning papers
        query = BooleanQuery(
            BooleanOperator.AND,
            [
                FieldQuery("title", PhraseQuery("machine learning")),
                FieldQuery("year", TermQuery("2023")),
                TermQuery("neural networks"),
            ],
        )

        expanded = expander.expand_query(query)
        suggestions = expander.suggest_corrections(query, max_suggestions=5)

        # Should produce valid expanded query
        assert expanded is not None
        assert isinstance(expanded, ParsedQuery)

        # Should generate suggestions
        assert isinstance(suggestions, list)
        assert all(isinstance(s, QuerySuggestion) for s in suggestions)
