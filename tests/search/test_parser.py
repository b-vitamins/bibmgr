"""Tests for query parser."""

import pytest

from bibmgr.search.query.parser import (
    BooleanOperator,
    BooleanQuery,
    FieldQuery,
    FuzzyQuery,
    PhraseQuery,
    QueryParser,
    QueryType,
    RangeQuery,
    TermQuery,
    WildcardQuery,
)


class TestQueryTypes:
    """Test query type enums."""

    def test_query_type_values(self):
        """Query types should have expected values."""
        assert QueryType.TERM.value == "term"
        assert QueryType.PHRASE.value == "phrase"
        assert QueryType.FIELD.value == "field"
        assert QueryType.BOOLEAN.value == "boolean"
        assert QueryType.WILDCARD.value == "wildcard"
        assert QueryType.FUZZY.value == "fuzzy"
        assert QueryType.RANGE.value == "range"

    def test_boolean_operator_values(self):
        """Boolean operators should have expected values."""
        assert BooleanOperator.AND.value == "AND"
        assert BooleanOperator.OR.value == "OR"
        assert BooleanOperator.NOT.value == "NOT"


class TestTermQuery:
    """Test TermQuery class."""

    def test_create_simple_term(self):
        """Create simple term query."""
        query = TermQuery(term="machine")

        assert query.term == "machine"
        assert query.boost == 1.0
        assert query.query_type == QueryType.TERM

    def test_create_boosted_term(self):
        """Create term with boost."""
        query = TermQuery(term="important", boost=2.5)

        assert query.term == "important"
        assert query.boost == 2.5

    def test_to_string_simple(self):
        """Convert simple term to string."""
        query = TermQuery(term="machine")
        assert query.to_string() == "machine"

    def test_to_string_boosted(self):
        """Convert boosted term to string."""
        query = TermQuery(term="important", boost=2.0)
        assert query.to_string() == "important^2.0"

    def test_get_terms(self):
        """Get terms from term query."""
        query = TermQuery(term="machine")
        assert query.get_terms() == ["machine"]


class TestPhraseQuery:
    """Test PhraseQuery class."""

    def test_create_simple_phrase(self):
        """Create simple phrase query."""
        query = PhraseQuery(phrase="machine learning")

        assert query.phrase == "machine learning"
        assert query.slop == 0
        assert query.boost == 1.0
        assert query.query_type == QueryType.PHRASE

    def test_create_phrase_with_slop(self):
        """Create phrase with slop."""
        query = PhraseQuery(phrase="machine learning", slop=2)

        assert query.phrase == "machine learning"
        assert query.slop == 2

    def test_create_boosted_phrase(self):
        """Create phrase with boost."""
        query = PhraseQuery(phrase="deep learning", boost=1.5)

        assert query.phrase == "deep learning"
        assert query.boost == 1.5

    def test_to_string_simple(self):
        """Convert simple phrase to string."""
        query = PhraseQuery(phrase="machine learning")
        assert query.to_string() == '"machine learning"'

    def test_to_string_with_slop(self):
        """Convert phrase with slop to string."""
        query = PhraseQuery(phrase="machine learning", slop=2)
        assert query.to_string() == '"machine learning"~2'

    def test_to_string_with_boost(self):
        """Convert boosted phrase to string."""
        query = PhraseQuery(phrase="machine learning", boost=2.0)
        assert query.to_string() == '"machine learning"^2.0'

    def test_to_string_with_slop_and_boost(self):
        """Convert phrase with slop and boost to string."""
        query = PhraseQuery(phrase="machine learning", slop=2, boost=1.5)
        assert query.to_string() == '"machine learning"~2^1.5'

    def test_get_terms(self):
        """Get terms from phrase query."""
        query = PhraseQuery(phrase="machine learning algorithms")
        assert query.get_terms() == ["machine", "learning", "algorithms"]


class TestFieldQuery:
    """Test FieldQuery class."""

    def test_create_field_term_query(self):
        """Create field query with term."""
        term_query = TermQuery(term="smith")
        query = FieldQuery(field="author", query=term_query)

        assert query.field == "author"
        assert query.query == term_query
        assert query.query_type == QueryType.FIELD

    def test_create_field_phrase_query(self):
        """Create field query with phrase."""
        phrase_query = PhraseQuery(phrase="machine learning")
        query = FieldQuery(field="title", query=phrase_query)

        assert query.field == "title"
        assert query.query == phrase_query

    def test_to_string_field_term(self):
        """Convert field term query to string."""
        term_query = TermQuery(term="smith")
        query = FieldQuery(field="author", query=term_query)
        assert query.to_string() == "author:smith"

    def test_to_string_field_phrase(self):
        """Convert field phrase query to string."""
        phrase_query = PhraseQuery(phrase="machine learning")
        query = FieldQuery(field="title", query=phrase_query)
        assert query.to_string() == 'title:"machine learning"'

    def test_get_terms(self):
        """Get terms from field query."""
        term_query = TermQuery(term="smith")
        query = FieldQuery(field="author", query=term_query)
        assert query.get_terms() == ["smith"]


class TestBooleanQuery:
    """Test BooleanQuery class."""

    def test_create_and_query(self):
        """Create AND boolean query."""
        q1 = TermQuery(term="machine")
        q2 = TermQuery(term="learning")
        query = BooleanQuery(operator=BooleanOperator.AND, queries=[q1, q2])

        assert query.operator == BooleanOperator.AND
        assert len(query.queries) == 2
        assert query.query_type == QueryType.BOOLEAN

    def test_create_or_query(self):
        """Create OR boolean query."""
        q1 = TermQuery(term="machine")
        q2 = TermQuery(term="computer")
        query = BooleanQuery(operator=BooleanOperator.OR, queries=[q1, q2])

        assert query.operator == BooleanOperator.OR
        assert len(query.queries) == 2

    def test_create_not_query(self):
        """Create NOT boolean query."""
        q1 = TermQuery(term="machine")
        q2 = TermQuery(term="spam")
        query = BooleanQuery(operator=BooleanOperator.NOT, queries=[q1, q2])

        assert query.operator == BooleanOperator.NOT
        assert len(query.queries) == 2

    def test_to_string_and(self):
        """Convert AND query to string."""
        q1 = TermQuery(term="machine")
        q2 = TermQuery(term="learning")
        query = BooleanQuery(operator=BooleanOperator.AND, queries=[q1, q2])
        assert query.to_string() == "(machine AND learning)"

    def test_to_string_or(self):
        """Convert OR query to string."""
        q1 = TermQuery(term="machine")
        q2 = TermQuery(term="computer")
        query = BooleanQuery(operator=BooleanOperator.OR, queries=[q1, q2])
        assert query.to_string() == "(machine OR computer)"

    def test_to_string_not_binary(self):
        """Convert binary NOT query to string."""
        q1 = TermQuery(term="machine")
        q2 = TermQuery(term="spam")
        query = BooleanQuery(operator=BooleanOperator.NOT, queries=[q1, q2])
        assert query.to_string() == "machine NOT spam"

    def test_to_string_not_unary(self):
        """Convert unary NOT query to string."""
        q1 = TermQuery(term="spam")
        query = BooleanQuery(operator=BooleanOperator.NOT, queries=[q1])
        assert query.to_string() == "NOT spam"

    def test_to_string_empty(self):
        """Convert empty boolean query to string."""
        query = BooleanQuery(operator=BooleanOperator.AND, queries=[])
        assert query.to_string() == ""

    def test_get_terms(self):
        """Get terms from boolean query."""
        q1 = TermQuery(term="machine")
        q2 = TermQuery(term="learning")
        q3 = TermQuery(term="algorithms")
        query = BooleanQuery(operator=BooleanOperator.AND, queries=[q1, q2, q3])
        assert query.get_terms() == ["machine", "learning", "algorithms"]

    def test_nested_boolean(self):
        """Test nested boolean queries."""
        inner = BooleanQuery(
            operator=BooleanOperator.OR,
            queries=[TermQuery("machine"), TermQuery("deep")],
        )
        outer = BooleanQuery(
            operator=BooleanOperator.AND, queries=[inner, TermQuery("learning")]
        )

        assert outer.to_string() == "((machine OR deep) AND learning)"
        assert outer.get_terms() == ["machine", "deep", "learning"]


class TestWildcardQuery:
    """Test WildcardQuery class."""

    def test_create_simple_wildcard(self):
        """Create simple wildcard query."""
        query = WildcardQuery(pattern="learn*")

        assert query.pattern == "learn*"
        assert query.boost == 1.0
        assert query.query_type == QueryType.WILDCARD

    def test_create_boosted_wildcard(self):
        """Create wildcard with boost."""
        query = WildcardQuery(pattern="*ing", boost=1.5)

        assert query.pattern == "*ing"
        assert query.boost == 1.5

    def test_to_string_simple(self):
        """Convert simple wildcard to string."""
        query = WildcardQuery(pattern="learn*")
        assert query.to_string() == "learn*"

    def test_to_string_boosted(self):
        """Convert boosted wildcard to string."""
        query = WildcardQuery(pattern="learn*", boost=2.0)
        assert query.to_string() == "learn*^2.0"

    def test_get_terms(self):
        """Get terms from wildcard query."""
        query = WildcardQuery(pattern="mac*ine")
        assert query.get_terms() == ["mac", "ine"]

        query2 = WildcardQuery(pattern="*learning*")
        assert query2.get_terms() == ["learning"]

        query3 = WildcardQuery(pattern="te?t")
        assert query3.get_terms() == ["te", "t"]


class TestFuzzyQuery:
    """Test FuzzyQuery class."""

    def test_create_simple_fuzzy(self):
        """Create simple fuzzy query."""
        query = FuzzyQuery(term="machne")

        assert query.term == "machne"
        assert query.max_edits == 2
        assert query.prefix_length == 0
        assert query.boost == 1.0
        assert query.query_type == QueryType.FUZZY

    def test_create_fuzzy_with_max_edits(self):
        """Create fuzzy with custom max edits."""
        query = FuzzyQuery(term="machne", max_edits=1)

        assert query.term == "machne"
        assert query.max_edits == 1

    def test_create_fuzzy_with_prefix(self):
        """Create fuzzy with prefix length."""
        query = FuzzyQuery(term="machne", max_edits=2, prefix_length=3)

        assert query.term == "machne"
        assert query.prefix_length == 3

    def test_to_string_default(self):
        """Convert default fuzzy to string."""
        query = FuzzyQuery(term="machne")
        assert query.to_string() == "machne~"

    def test_to_string_with_edits(self):
        """Convert fuzzy with custom edits to string."""
        query = FuzzyQuery(term="machne", max_edits=1)
        assert query.to_string() == "machne~1"

    def test_to_string_with_boost(self):
        """Convert boosted fuzzy to string."""
        query = FuzzyQuery(term="machne", boost=1.5)
        assert query.to_string() == "machne~^1.5"

    def test_get_terms(self):
        """Get terms from fuzzy query."""
        query = FuzzyQuery(term="machne")
        assert query.get_terms() == ["machne"]


class TestRangeQuery:
    """Test RangeQuery class."""

    def test_create_inclusive_range(self):
        """Create inclusive range query."""
        query = RangeQuery(field="year", start=2020, end=2023)

        assert query.field == "year"
        assert query.start == 2020
        assert query.end == 2023
        assert query.include_start is True
        assert query.include_end is True
        assert query.query_type == QueryType.RANGE

    def test_create_exclusive_range(self):
        """Create exclusive range query."""
        query = RangeQuery(
            field="year", start=2020, end=2023, include_start=False, include_end=False
        )

        assert query.include_start is False
        assert query.include_end is False

    def test_create_open_ended_range(self):
        """Create open-ended range query."""
        query1 = RangeQuery(field="year", start=2020, end=None)
        assert query1.start == 2020
        assert query1.end is None

        query2 = RangeQuery(field="year", start=None, end=2023)
        assert query2.start is None
        assert query2.end == 2023

    def test_to_string_inclusive(self):
        """Convert inclusive range to string."""
        query = RangeQuery(field="year", start=2020, end=2023)
        assert query.to_string() == "year:[2020 TO 2023]"

    def test_to_string_exclusive(self):
        """Convert exclusive range to string."""
        query = RangeQuery(
            field="year", start=2020, end=2023, include_start=False, include_end=False
        )
        assert query.to_string() == "year:{2020 TO 2023}"

    def test_to_string_mixed_bounds(self):
        """Convert mixed bounds range to string."""
        query = RangeQuery(
            field="year", start=2020, end=2023, include_start=True, include_end=False
        )
        assert query.to_string() == "year:[2020 TO 2023}"

    def test_to_string_open_ended(self):
        """Convert open-ended range to string."""
        query1 = RangeQuery(field="year", start=2020, end=None)
        assert query1.to_string() == "year:[2020 TO *]"

        query2 = RangeQuery(field="year", start=None, end=2023)
        assert query2.to_string() == "year:[* TO 2023]"

    def test_to_string_with_boost(self):
        """Convert boosted range to string."""
        query = RangeQuery(field="year", start=2020, end=2023, boost=2.0)
        assert query.to_string() == "year:[2020 TO 2023]^2.0"

    def test_get_terms(self):
        """Get terms from range query."""
        query = RangeQuery(field="year", start=2020, end=2023)
        assert query.get_terms() == ["2020", "2023"]

        query2 = RangeQuery(field="year", start=None, end=2023)
        assert query2.get_terms() == ["2023"]


class TestQueryParser:
    """Test QueryParser class."""

    @pytest.fixture
    def parser(self):
        """Create query parser for testing."""
        return QueryParser()

    # Empty and whitespace queries
    def test_parse_empty_query(self, parser):
        """Empty query should return empty term."""
        result = parser.parse("")

        assert isinstance(result, TermQuery)
        assert result.term == ""

    def test_parse_whitespace_query(self, parser):
        """Whitespace-only query should return empty term."""
        result = parser.parse("   \t\n  ")

        assert isinstance(result, TermQuery)
        assert result.term == ""

    # Simple term queries
    def test_parse_single_term(self, parser):
        """Single term should parse as TermQuery."""
        result = parser.parse("machine")

        assert isinstance(result, TermQuery)
        assert result.term == "machine"
        assert result.boost == 1.0

    def test_parse_term_with_boost(self, parser):
        """Term with boost should parse correctly."""
        result = parser.parse("important^2.5")

        assert isinstance(result, TermQuery)
        assert result.term == "important"
        assert result.boost == 2.5

    def test_parse_multiple_terms_as_phrase(self, parser):
        """Multiple terms without operators default to implicit AND query."""
        result = parser.parse("machine learning")

        # Without AND/OR, treated as implicit AND of terms
        assert isinstance(result, BooleanQuery)
        assert result.operator == BooleanOperator.AND
        assert len(result.queries) == 2
        assert isinstance(result.queries[0], TermQuery)
        assert result.queries[0].term == "machine"
        assert isinstance(result.queries[1], TermQuery)
        assert result.queries[1].term == "learning"

    # Phrase queries
    def test_parse_simple_phrase(self, parser):
        """Quoted phrase should parse as PhraseQuery."""
        result = parser.parse('"machine learning"')

        assert isinstance(result, PhraseQuery)
        assert result.phrase == "machine learning"
        assert result.slop == 0
        assert result.boost == 1.0

    def test_parse_phrase_with_slop(self, parser):
        """Phrase with slop should parse correctly."""
        result = parser.parse('"machine learning"~3')

        assert isinstance(result, PhraseQuery)
        assert result.phrase == "machine learning"
        assert result.slop == 3

    def test_parse_phrase_with_boost(self, parser):
        """Phrase with boost should parse correctly."""
        result = parser.parse('"deep learning"^1.5')

        assert isinstance(result, PhraseQuery)
        assert result.phrase == "deep learning"
        assert result.boost == 1.5

    def test_parse_phrase_with_slop_and_boost(self, parser):
        """Phrase with slop and boost should parse correctly."""
        result = parser.parse('"neural networks"~2^2.0')

        assert isinstance(result, PhraseQuery)
        assert result.phrase == "neural networks"
        assert result.slop == 2
        assert result.boost == 2.0

    def test_parse_empty_phrase(self, parser):
        """Empty phrase should parse correctly."""
        result = parser.parse('""')

        assert isinstance(result, PhraseQuery)
        assert result.phrase == ""

    # Field queries
    def test_parse_field_term(self, parser):
        """Field with term should parse as FieldQuery."""
        result = parser.parse("author:smith")

        assert isinstance(result, FieldQuery)
        assert result.field == "author"
        assert isinstance(result.query, TermQuery)
        assert result.query.term == "smith"

    def test_parse_field_phrase(self, parser):
        """Field with phrase should parse correctly."""
        result = parser.parse('title:"machine learning"')

        assert isinstance(result, FieldQuery)
        assert result.field == "title"
        assert isinstance(result.query, PhraseQuery)
        assert result.query.phrase == "machine learning"

    def test_parse_field_with_boost(self, parser):
        """Field query with boost should parse correctly."""
        result = parser.parse("title:important^2.0")

        assert isinstance(result, FieldQuery)
        assert result.field == "title"
        assert isinstance(result.query, TermQuery)
        assert result.query.term == "important"
        assert result.query.boost == 2.0

    def test_parse_field_wildcard(self, parser):
        """Field with wildcard should parse correctly."""
        result = parser.parse("author:smi*")

        assert isinstance(result, FieldQuery)
        assert result.field == "author"
        assert isinstance(result.query, WildcardQuery)
        assert result.query.pattern == "smi*"

    # Boolean queries
    def test_parse_simple_and(self, parser):
        """Simple AND query should parse correctly."""
        result = parser.parse("machine AND learning")

        assert isinstance(result, BooleanQuery)
        assert result.operator == BooleanOperator.AND
        assert len(result.queries) == 2
        assert all(isinstance(q, TermQuery) for q in result.queries)
        # Type-safe access to TermQuery attributes
        q0 = result.queries[0]
        q1 = result.queries[1]
        assert isinstance(q0, TermQuery) and q0.term == "machine"
        assert isinstance(q1, TermQuery) and q1.term == "learning"

    def test_parse_simple_or(self, parser):
        """Simple OR query should parse correctly."""
        result = parser.parse("machine OR computer")

        assert isinstance(result, BooleanQuery)
        assert result.operator == BooleanOperator.OR
        assert len(result.queries) == 2

    def test_parse_simple_not(self, parser):
        """Simple NOT query should parse correctly."""
        result = parser.parse("machine NOT spam")

        assert isinstance(result, BooleanQuery)
        assert result.operator == BooleanOperator.NOT
        assert len(result.queries) == 2

    def test_parse_unary_not(self, parser):
        """Unary NOT query should parse correctly."""
        result = parser.parse("NOT spam")

        assert isinstance(result, BooleanQuery)
        assert result.operator == BooleanOperator.NOT
        assert len(result.queries) == 1
        # Type-safe access to TermQuery attribute
        q0 = result.queries[0]
        assert isinstance(q0, TermQuery) and q0.term == "spam"

    def test_parse_case_insensitive_operators(self, parser):
        """Boolean operators should be case insensitive."""
        queries = [
            "machine AND learning",
            "machine and learning",
            "machine And learning",
        ]

        for query in queries:
            result = parser.parse(query)
            assert isinstance(result, BooleanQuery)
            assert result.operator == BooleanOperator.AND

    def test_parse_complex_boolean(self, parser):
        """Complex boolean expressions should parse."""
        result = parser.parse("machine AND learning OR neural")

        # Should parse left-to-right
        assert isinstance(result, BooleanQuery)
        # The exact structure depends on precedence rules

    # Wildcard queries
    def test_parse_prefix_wildcard(self, parser):
        """Prefix wildcard should parse correctly."""
        result = parser.parse("learn*")

        assert isinstance(result, WildcardQuery)
        assert result.pattern == "learn*"

    def test_parse_suffix_wildcard(self, parser):
        """Suffix wildcard should parse correctly."""
        result = parser.parse("*ing")

        assert isinstance(result, WildcardQuery)
        assert result.pattern == "*ing"

    def test_parse_infix_wildcard(self, parser):
        """Infix wildcard should parse correctly."""
        result = parser.parse("ma*ine")

        assert isinstance(result, WildcardQuery)
        assert result.pattern == "ma*ine"

    def test_parse_single_char_wildcard(self, parser):
        """Single character wildcard should parse correctly."""
        result = parser.parse("te?t")

        assert isinstance(result, WildcardQuery)
        assert result.pattern == "te?t"

    def test_parse_wildcard_with_boost(self, parser):
        """Wildcard with boost should parse correctly."""
        result = parser.parse("learn*^1.5")

        assert isinstance(result, WildcardQuery)
        assert result.pattern == "learn*"
        assert result.boost == 1.5

    # Fuzzy queries
    def test_parse_simple_fuzzy(self, parser):
        """Simple fuzzy query should parse correctly."""
        result = parser.parse("machne~")

        assert isinstance(result, FuzzyQuery)
        assert result.term == "machne"
        assert result.max_edits == 2

    def test_parse_fuzzy_with_distance(self, parser):
        """Fuzzy with edit distance should parse correctly."""
        result = parser.parse("machne~1")

        assert isinstance(result, FuzzyQuery)
        assert result.term == "machne"
        assert result.max_edits == 1

    def test_parse_fuzzy_with_boost(self, parser):
        """Fuzzy with boost should parse correctly."""
        result = parser.parse("machne~2^1.5")

        assert isinstance(result, FuzzyQuery)
        assert result.term == "machne"
        assert result.max_edits == 2
        assert result.boost == 1.5

    # Range queries
    def test_parse_inclusive_range(self, parser):
        """Inclusive range should parse correctly."""
        result = parser.parse("year:[2020 TO 2023]")

        assert isinstance(result, RangeQuery)
        assert result.field == "year"
        assert result.start == 2020
        assert result.end == 2023
        assert result.include_start is True
        assert result.include_end is True

    def test_parse_exclusive_range(self, parser):
        """Exclusive range should parse correctly."""
        result = parser.parse("year:{2020 TO 2023}")

        assert isinstance(result, RangeQuery)
        assert result.field == "year"
        assert result.start == 2020
        assert result.end == 2023
        assert result.include_start is False
        assert result.include_end is False

    def test_parse_open_range(self, parser):
        """Open-ended range should parse correctly."""
        result1 = parser.parse("year:[2020 TO *]")
        assert isinstance(result1, RangeQuery)
        assert result1.start == 2020
        assert result1.end is None

        result2 = parser.parse("year:[* TO 2023]")
        assert isinstance(result2, RangeQuery)
        assert result2.start is None
        assert result2.end == 2023

    def test_parse_string_range(self, parser):
        """String range should parse correctly."""
        result = parser.parse("author:[A TO M]")

        assert isinstance(result, RangeQuery)
        assert result.field == "author"
        assert result.start == "A"
        assert result.end == "M"

    # Complex queries
    def test_parse_mixed_query_types(self, parser):
        """Mixed query types should parse correctly."""
        result = parser.parse('author:smith AND title:"machine learning"')

        assert isinstance(result, BooleanQuery)
        assert result.operator == BooleanOperator.AND
        assert len(result.queries) == 2
        assert isinstance(result.queries[0], FieldQuery)
        assert isinstance(result.queries[1], FieldQuery)

    def test_parse_nested_boolean(self, parser):
        """Nested boolean queries should work."""
        # Note: Without parentheses support, this will be left-to-right
        result = parser.parse("machine OR deep AND learning")

        assert isinstance(result, BooleanQuery)
        # Structure depends on parser precedence

    # Edge cases
    def test_parse_special_characters(self, parser):
        """Special characters should be handled."""
        queries = [
            "C++",
            "test@email.com",
            "machine-learning",
            "3.14159",
        ]

        for query in queries:
            result = parser.parse(query)
            assert result is not None

    def test_parse_unicode(self, parser):
        """Unicode should be handled correctly."""
        result = parser.parse("café")

        assert isinstance(result, TermQuery)
        assert result.term == "café"

    def test_parse_empty_field(self, parser):
        """Empty field value should be handled."""
        result = parser.parse("author:")

        # Should not parse as field query without value
        assert result is not None

    # Utility methods
    def test_extract_field_queries(self, parser):
        """Extract field queries should work correctly."""
        query = parser.parse('author:smith AND title:"machine learning"')
        field_queries = parser.extract_field_queries(query)

        assert "author" in field_queries
        assert "title" in field_queries
        assert len(field_queries["author"]) == 1
        assert len(field_queries["title"]) == 1

    def test_get_query_complexity(self, parser):
        """Query complexity calculation should work."""
        simple = parser.parse("machine")
        assert parser.get_query_complexity(simple) == 1

        phrase = parser.parse('"machine learning algorithms"')
        assert parser.get_query_complexity(phrase) == 3

        wildcard = parser.parse("learn*")
        assert parser.get_query_complexity(wildcard) == 3

        fuzzy = parser.parse("machne~")
        assert parser.get_query_complexity(fuzzy) == 5

        boolean = parser.parse("machine AND learning")
        assert parser.get_query_complexity(boolean) == 2

    def test_validate_query(self, parser):
        """Query validation should detect issues."""
        # Valid query
        valid = parser.parse("machine learning")
        errors = parser.validate_query(valid)
        assert len(errors) == 0

        # Empty term
        empty = TermQuery(term="")
        errors = parser.validate_query(empty)
        assert len(errors) > 0
        assert any("Empty term" in e for e in errors)

        # Invalid fuzzy distance
        invalid_fuzzy = FuzzyQuery(term="test", max_edits=3)
        errors = parser.validate_query(invalid_fuzzy)
        assert len(errors) > 0
        assert any("max_edits" in e for e in errors)


class TestParserEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def parser(self):
        """Create query parser for testing."""
        return QueryParser()

    def test_malformed_queries(self, parser):
        """Malformed queries should not crash."""
        malformed = [
            "AND machine",  # Leading operator
            "machine AND",  # Trailing operator
            "AND AND",  # Only operators
            "machine AND AND learning",  # Double operator
            'title:"unclosed quote',  # Unclosed quote
            "year:[2020 TO",  # Incomplete range
            "~fuzzy",  # Leading fuzzy
            "^2.0",  # Only boost
        ]

        for query in malformed:
            # Should not raise exception
            result = parser.parse(query)
            assert result is not None

    def test_extreme_values(self, parser):
        """Extreme values should be handled."""
        # Very long query
        long_query = " ".join(["term"] * 1000)
        result = parser.parse(long_query)
        assert result is not None

        # Very high boost
        result = parser.parse("term^999999.99")
        assert isinstance(result, TermQuery)
        assert result.boost == 999999.99

        # Large fuzzy distance
        result = parser.parse("term~999")
        assert isinstance(result, FuzzyQuery)
        # Should be clamped or handled appropriately

    def test_nested_quotes(self, parser):
        """Nested quotes should be handled."""
        result = parser.parse('"phrase with "nested" quotes"')

        # Should handle somehow
        assert result is not None

    def test_mixed_quote_types(self, parser):
        """Mixed quote types should be handled."""
        result = parser.parse('"mixed\' quotes"')

        assert isinstance(result, PhraseQuery)
        assert result.phrase == "mixed' quotes"

    def test_escaped_characters(self, parser):
        """Escaped characters should be handled."""
        # Common escape sequences
        queries = [
            r"test\*",  # Escaped wildcard
            r"test\?",  # Escaped single char wildcard
            r"test\~",  # Escaped fuzzy
            r"test\^",  # Escaped boost
        ]

        for query in queries:
            result = parser.parse(query)
            assert result is not None

    def test_numeric_terms(self, parser):
        """Numeric terms should be handled."""
        result = parser.parse("42")
        assert isinstance(result, TermQuery)
        assert result.term == "42"

        result = parser.parse("3.14159")
        assert isinstance(result, TermQuery)
        assert result.term == "3.14159"

    def test_date_ranges(self, parser):
        """Date ranges should be parsed."""
        result = parser.parse("date:[2023-01-01 TO 2023-12-31]")

        assert isinstance(result, RangeQuery)
        assert result.field == "date"
        assert result.start == "2023-01-01"
        assert result.end == "2023-12-31"

    def test_mixed_case_fields(self, parser):
        """Mixed case field names should work."""
        result = parser.parse("Title:test")

        assert isinstance(result, FieldQuery)
        assert result.field == "Title"

    def test_field_with_underscore(self, parser):
        """Fields with underscores should work."""
        result = parser.parse("custom_field:value")

        assert isinstance(result, FieldQuery)
        assert result.field == "custom_field"

    def test_url_parsing(self, parser):
        """URLs should be parsed as terms."""
        result = parser.parse("https://example.com/path")

        assert isinstance(result, TermQuery)
        assert "example.com" in result.term

    def test_email_parsing(self, parser):
        """Email addresses should be parsed as terms."""
        result = parser.parse("user@example.com")

        assert isinstance(result, TermQuery)
        assert result.term == "user@example.com"


class TestQueryBuilder:
    """Test building queries programmatically."""

    def test_build_simple_term(self):
        """Build simple term query."""
        query = TermQuery(term="machine")

        assert query.to_string() == "machine"

    def test_build_complex_boolean(self):
        """Build complex boolean query."""
        q1 = FieldQuery(field="author", query=TermQuery("smith"))
        q2 = FieldQuery(field="title", query=PhraseQuery("machine learning"))
        q3 = FieldQuery(field="year", query=TermQuery("2023"))

        boolean_query = BooleanQuery(operator=BooleanOperator.AND, queries=[q1, q2, q3])

        result = boolean_query.to_string()
        assert "author:smith" in result
        assert 'title:"machine learning"' in result
        assert "year:2023" in result
        assert "AND" in result

    def test_build_nested_query(self):
        """Build nested query structure."""
        # (machine OR deep) AND learning NOT spam
        or_query = BooleanQuery(
            operator=BooleanOperator.OR,
            queries=[TermQuery("machine"), TermQuery("deep")],
        )

        and_query = BooleanQuery(
            operator=BooleanOperator.AND, queries=[or_query, TermQuery("learning")]
        )

        not_query = BooleanQuery(
            operator=BooleanOperator.NOT, queries=[and_query, TermQuery("spam")]
        )

        result = not_query.to_string()
        assert "machine OR deep" in result
        assert "learning" in result
        assert "NOT spam" in result

    def test_round_trip_parsing(self):
        """Query should survive round-trip parsing."""
        parser = QueryParser()

        # Create a query
        original = FieldQuery(
            field="title", query=PhraseQuery(phrase="machine learning", boost=2.0)
        )

        # Convert to string
        query_string = original.to_string()
        assert query_string == 'title:"machine learning"^2.0'

        # Parse back
        parsed = parser.parse(query_string)

        # Should be equivalent
        assert isinstance(parsed, FieldQuery)
        assert parsed.field == "title"
        assert isinstance(parsed.query, PhraseQuery)
        assert parsed.query.phrase == "machine learning"
        assert parsed.query.boost == 2.0
