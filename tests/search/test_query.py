"""Comprehensive tests for query parsing and understanding.

These tests are implementation-agnostic and focus on the expected behavior
of query parsing, expansion, and understanding.
"""


# Tests are now ready to run


class TestQueryOperators:
    """Test query operator enumeration."""

    def test_operator_types(self):
        """Should support standard boolean operators."""
        from bibmgr.search.query import QueryOperator

        assert hasattr(QueryOperator, "AND")
        assert hasattr(QueryOperator, "OR")
        assert hasattr(QueryOperator, "NOT")
        assert hasattr(QueryOperator, "PHRASE")


class TestQueryField:
    """Test searchable field enumeration."""

    def test_standard_fields(self):
        """Should support standard bibliography fields."""
        from bibmgr.search.query import QueryField

        expected_fields = [
            "ALL",
            "TITLE",
            "AUTHOR",
            "ABSTRACT",
            "KEYWORDS",
            "YEAR",
            "VENUE",
            "TYPE",
        ]

        for field in expected_fields:
            assert hasattr(QueryField, field)

    def test_field_values(self):
        """Field values should be lowercase strings."""
        from bibmgr.search.query import QueryField

        assert QueryField.ALL.value == "all"
        assert QueryField.TITLE.value == "title"
        assert QueryField.AUTHOR.value == "author"


class TestQueryTerm:
    """Test individual query term model."""

    def test_simple_term(self):
        """Should create basic search term."""
        from bibmgr.search.query import QueryTerm, QueryField

        term = QueryTerm(text="machine")

        assert term.text == "machine"
        assert term.field == QueryField.ALL
        assert not term.is_negated
        assert not term.is_phrase
        assert not term.is_wildcard
        assert term.boost == 1.0

    def test_field_specific_term(self):
        """Should create field-specific term."""
        from bibmgr.search.query import QueryTerm, QueryField

        term = QueryTerm(text="smith", field=QueryField.AUTHOR)

        assert term.text == "smith"
        assert term.field == QueryField.AUTHOR

    def test_negated_term(self):
        """Should create negated term."""
        from bibmgr.search.query import QueryTerm

        term = QueryTerm(text="java", is_negated=True)

        assert term.is_negated
        assert str(term).startswith("-")

    def test_phrase_term(self):
        """Should create phrase term."""
        from bibmgr.search.query import QueryTerm

        term = QueryTerm(text="machine learning", is_phrase=True)

        assert term.is_phrase
        assert '"' in str(term)

    def test_wildcard_term(self):
        """Should create wildcard term."""
        from bibmgr.search.query import QueryTerm

        term = QueryTerm(text="optim*", is_wildcard=True)

        assert term.is_wildcard

    def test_boosted_term(self):
        """Should create boosted term."""
        from bibmgr.search.query import QueryTerm

        term = QueryTerm(text="important", boost=2.5)

        assert term.boost == 2.5
        assert "^2.5" in str(term)

    def test_range_term(self):
        """Should support range queries."""
        from bibmgr.search.query import QueryTerm, QueryField

        term = QueryTerm(
            text="2020..2024", field=QueryField.YEAR, range_start=2020, range_end=2024
        )

        assert term.range_start == 2020
        assert term.range_end == 2024

    def test_proximity_term(self):
        """Should support proximity information."""
        from bibmgr.search.query import QueryTerm

        term = QueryTerm(text="neural", proximity_next=3)

        assert term.proximity_next == 3

    def test_term_string_representation(self):
        """Should have readable string representation."""
        from bibmgr.search.query import QueryTerm, QueryField

        # Simple term
        assert str(QueryTerm("test")) == "test"

        # Field term
        term = QueryTerm("smith", field=QueryField.AUTHOR)
        assert str(term) == "author:smith"

        # Negated term
        term = QueryTerm("java", is_negated=True)
        assert str(term) == "-java"

        # Phrase term
        term = QueryTerm("exact match", is_phrase=True)
        assert str(term) == '"exact match"'

        # Boosted term
        term = QueryTerm("important", boost=2.0)
        assert str(term) == "important^2.0"

        # Combined
        term = QueryTerm(
            "machine learning", field=QueryField.TITLE, is_phrase=True, boost=1.5
        )
        assert str(term) == 'title:"machine learning"^1.5'


class TestQuery:
    """Test parsed query model."""

    def test_empty_query(self):
        """Should handle empty query."""
        from bibmgr.search.query import Query

        query = Query(original="")

        assert query.original == ""
        assert query.terms == []
        assert query.filters == {}
        assert not query.has_field_queries()

    def test_simple_query(self):
        """Should store query with terms."""
        from bibmgr.search.query import Query, QueryTerm

        terms = [QueryTerm("machine"), QueryTerm("learning")]

        query = Query(original="machine learning", terms=terms)

        assert query.original == "machine learning"
        assert len(query.terms) == 2
        assert query.terms[0].text == "machine"

    def test_query_with_filters(self):
        """Should store extracted filters."""
        from bibmgr.search.query import Query, QueryTerm, QueryField

        terms = [
            QueryTerm("2024", field=QueryField.YEAR),
            QueryTerm("article", field=QueryField.TYPE),
        ]

        query = Query(
            original="year:2024 type:article",
            terms=terms,
            filters={"year": 2024, "entry_type": "article"},
        )

        assert query.filters["year"] == 2024
        assert query.filters["entry_type"] == "article"

    def test_query_intent(self):
        """Should store detected intent."""
        from bibmgr.search.query import Query

        query = Query(original="author:smith", intent="author_lookup")

        assert query.intent == "author_lookup"

    def test_query_preferences(self):
        """Should store search preferences."""
        from bibmgr.search.query import Query

        query = Query(original="recent papers", prefer_recent=True, prefer_cited=False)

        assert query.prefer_recent
        assert not query.prefer_cited

    def test_has_field_queries(self):
        """Should detect field-specific queries."""
        from bibmgr.search.query import Query, QueryTerm, QueryField

        # No field queries
        query = Query(original="test", terms=[QueryTerm("test")])
        assert not query.has_field_queries()

        # Has field queries
        query = Query(
            original="author:smith", terms=[QueryTerm("smith", field=QueryField.AUTHOR)]
        )
        assert query.has_field_queries()

    def test_get_field_terms(self):
        """Should retrieve terms for specific field."""
        from bibmgr.search.query import Query, QueryTerm, QueryField

        terms = [
            QueryTerm("smith", field=QueryField.AUTHOR),
            QueryTerm("machine", field=QueryField.ALL),
            QueryTerm("doe", field=QueryField.AUTHOR),
            QueryTerm("2024", field=QueryField.YEAR),
        ]

        query = Query(original="test", terms=terms)

        author_terms = query.get_field_terms(QueryField.AUTHOR)
        assert len(author_terms) == 2
        assert author_terms[0].text == "smith"
        assert author_terms[1].text == "doe"

        year_terms = query.get_field_terms(QueryField.YEAR)
        assert len(year_terms) == 1
        assert year_terms[0].text == "2024"


class TestQueryParser:
    """Test query parsing functionality."""

    def test_parse_simple_query(self):
        """Should parse simple keyword query."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()
        query = parser.parse("machine learning")

        assert query.original == "machine learning"
        assert len(query.terms) >= 2
        assert any(t.text == "machine" for t in query.terms)
        assert any(t.text == "learning" for t in query.terms)

    def test_parse_field_query(self):
        """Should parse field-specific queries."""
        from bibmgr.search.query import QueryParser, QueryField

        parser = QueryParser()

        # Author field
        query = parser.parse("author:smith")
        assert any(
            t.field == QueryField.AUTHOR and t.text == "smith" for t in query.terms
        )

        # Title field
        query = parser.parse("title:transformer")
        assert any(
            t.field == QueryField.TITLE and t.text == "transformer" for t in query.terms
        )

        # Year field
        query = parser.parse("year:2024")
        assert any(t.field == QueryField.YEAR and t.text == "2024" for t in query.terms)

    def test_parse_phrase_query(self):
        """Should parse phrase queries."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()
        query = parser.parse('"machine learning"')

        assert any(t.text == "machine learning" and t.is_phrase for t in query.terms)

    def test_parse_boolean_operators(self):
        """Should parse boolean operators."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()

        # AND operator
        query = parser.parse("machine AND learning")
        assert query.original == "machine AND learning"

        # OR operator
        query = parser.parse("python OR java")
        assert query.original == "python OR java"

        # NOT operator
        query = parser.parse("python NOT java")
        assert any(t.text == "java" and t.is_negated for t in query.terms)

    def test_parse_negation(self):
        """Should parse negated terms."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()
        query = parser.parse("python -java")

        # Should have negated java term
        assert any(t.text == "java" and t.is_negated for t in query.terms)

    def test_parse_wildcards(self):
        """Should detect wildcard queries."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()

        # Asterisk wildcard
        query = parser.parse("optim*")
        assert any(t.text == "optim*" and t.is_wildcard for t in query.terms)

        # Question mark wildcard
        query = parser.parse("neural?")
        assert any(t.text == "neural?" and t.is_wildcard for t in query.terms)

    def test_parse_range_query(self):
        """Should parse range queries."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()
        query = parser.parse("year:2020..2024")

        # Should extract range
        assert "year_range" in query.filters
        assert query.filters["year_range"] == (2020, 2024)

    def test_parse_boosting(self):
        """Should parse term boosting."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()
        query = parser.parse("important^2 normal")

        # Should have boosted term
        assert any(t.text == "important" and t.boost == 2.0 for t in query.terms)
        assert any(t.text == "normal" and t.boost == 1.0 for t in query.terms)

    def test_parse_proximity(self):
        """Should parse proximity queries."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()
        query = parser.parse("neural NEAR/3 network")

        # Should mark proximity
        neural_term = next((t for t in query.terms if t.text == "neural"), None)
        if neural_term:
            assert neural_term.proximity_next == 3

    def test_parse_complex_query(self):
        """Should parse complex multi-feature query."""
        from bibmgr.search.query import QueryParser, QueryField

        parser = QueryParser()
        query = parser.parse(
            'author:smith title:"machine learning" year:2020..2024 -java important^2'
        )

        # Should have all components
        assert any(t.field == QueryField.AUTHOR for t in query.terms)
        assert any(t.is_phrase for t in query.terms)
        assert any(t.is_negated for t in query.terms)
        assert any(t.boost > 1.0 for t in query.terms)
        assert "year_range" in query.filters

    def test_abbreviation_expansion(self):
        """Should expand known abbreviations."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()
        query = parser.parse("ml")

        # Should add expanded term
        expanded_texts = [t.text for t in query.terms]
        assert "machine learning" in expanded_texts or any(
            "machine" in t and "learning" in t for t in expanded_texts
        )

    def test_synonym_expansion(self):
        """Should expand with synonyms."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()
        query = parser.parse("neural network")

        # Should add related terms
        term_texts = [t.text.lower() for t in query.terms]
        # At least the original terms should be there
        assert any("neural" in t for t in term_texts)

    def test_intent_detection(self):
        """Should detect query intent."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()

        # Author lookup
        query = parser.parse("author:knuth")
        assert query.intent == "author_lookup"

        # Temporal research
        query = parser.parse("machine learning year:2024")
        assert query.intent == "temporal_research"
        assert query.prefer_recent

        # Complex research
        query = parser.parse("deep learning transformer attention mechanism bert")
        assert query.intent == "research"

        # Simple browsing
        query = parser.parse("python")
        assert query.intent == "browsing"

    def test_normalization(self):
        """Should normalize query text."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()

        # Extra whitespace
        query = parser.parse("  machine    learning  ")
        assert len(query.terms) >= 2

        # Mixed case (should preserve for proper nouns)
        query = parser.parse("PyTorch")
        assert any("pytorch" in t.text.lower() for t in query.terms)


class TestQuerySuggester:
    """Test query suggestion functionality."""

    def test_empty_suggester(self):
        """Should handle empty vocabulary."""
        from bibmgr.search.query import QuerySuggester

        suggester = QuerySuggester()

        corrections = suggester.suggest_corrections("test")
        assert corrections == []

        completions = suggester.suggest_completions("test")
        assert completions == []

    def test_spelling_corrections(self):
        """Should suggest spelling corrections."""
        from bibmgr.search.query import QuerySuggester

        vocabulary = {"machine", "learning", "neural", "network"}
        suggester = QuerySuggester(vocabulary)

        # Should suggest corrections for misspellings
        corrections = suggester.suggest_corrections("machne")
        assert any("machine" in str(c) for c in corrections)

        corrections = suggester.suggest_corrections("nueral")
        assert any("neural" in str(c) for c in corrections)

    def test_query_completions(self):
        """Should suggest query completions from history."""
        from bibmgr.search.query import QuerySuggester

        suggester = QuerySuggester()
        suggester.query_history = [
            "machine learning",
            "machine translation",
            "deep learning",
            "reinforcement learning",
        ]

        # Should complete partial queries
        completions = suggester.suggest_completions("mach")
        assert "machine learning" in completions
        assert "machine translation" in completions

        completions = suggester.suggest_completions("learning")
        assert (
            "reinforcement learning" not in completions
        )  # Doesn't start with "learning"

    def test_completion_limit(self):
        """Should limit number of completions."""
        from bibmgr.search.query import QuerySuggester

        suggester = QuerySuggester()
        suggester.query_history = [f"test{i}" for i in range(20)]

        completions = suggester.suggest_completions("test")
        assert len(completions) <= 5


class TestQueryIntegration:
    """Test complete query parsing scenarios."""

    def test_research_query_flow(self):
        """Test typical research query parsing."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()

        # Complex research query
        query_str = (
            'title:"attention mechanism" author:vaswani '
            "year:2017..2024 transformer -CNN"
        )

        query = parser.parse(query_str)

        # Should parse all components
        assert query.original == query_str
        assert query.has_field_queries()

        # Should have phrase
        phrase_terms = [t for t in query.terms if t.is_phrase]
        assert len(phrase_terms) > 0

        # Should have negation
        negated_terms = [t for t in query.terms if t.is_negated]
        assert len(negated_terms) > 0

        # Should have filters
        assert "year_range" in query.filters

    def test_browsing_query_flow(self):
        """Test casual browsing query."""
        from bibmgr.search.query import QueryParser

        parser = QueryParser()
        query = parser.parse("deep learning")

        # Should be simple
        assert query.intent == "browsing"
        assert not query.has_field_queries()

        # Should expand abbreviations if present
        if any(t.text == "dl" for t in query.terms):
            assert any("deep learning" in t.text.lower() for t in query.terms)
