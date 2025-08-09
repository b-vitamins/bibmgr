"""Tests for query language and query builder.

This module tests the query system that provides a clean, composable
interface for searching entries with support for various operators
and conditions.
"""

from datetime import datetime, timedelta

from bibmgr.core.models import Entry, EntryType


class TestCondition:
    """Test individual query conditions."""

    def test_equality_operator(self):
        """Equality operator matches exact values."""
        from bibmgr.storage.query import Condition, Operator

        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test", year=2020)

        cond = Condition("year", Operator.EQ, 2020)
        assert cond.matches(entry) is True

        cond = Condition("year", Operator.EQ, 2021)
        assert cond.matches(entry) is False

        cond = Condition("doi", Operator.EQ, None)
        assert cond.matches(entry) is True  # doi is None

    def test_inequality_operator(self):
        """Inequality operator matches different values."""
        from bibmgr.storage.query import Condition, Operator

        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test", year=2020)

        cond = Condition("year", Operator.NE, 2021)
        assert cond.matches(entry) is True

        cond = Condition("year", Operator.NE, 2020)
        assert cond.matches(entry) is False

    def test_comparison_operators(self):
        """Comparison operators work with comparable values."""
        from bibmgr.storage.query import Condition, Operator

        entry = Entry(key="test", type=EntryType.MISC, title="Test", year=2020)

        assert Condition("year", Operator.GT, 2019).matches(entry) is True
        assert Condition("year", Operator.GT, 2020).matches(entry) is False
        assert Condition("year", Operator.GT, 2021).matches(entry) is False

        assert Condition("year", Operator.GTE, 2019).matches(entry) is True
        assert Condition("year", Operator.GTE, 2020).matches(entry) is True
        assert Condition("year", Operator.GTE, 2021).matches(entry) is False

        assert Condition("year", Operator.LT, 2021).matches(entry) is True
        assert Condition("year", Operator.LT, 2020).matches(entry) is False
        assert Condition("year", Operator.LT, 2019).matches(entry) is False

        assert Condition("year", Operator.LTE, 2021).matches(entry) is True
        assert Condition("year", Operator.LTE, 2020).matches(entry) is True
        assert Condition("year", Operator.LTE, 2019).matches(entry) is False

    def test_string_operators(self):
        """String operators work with text fields."""
        from bibmgr.storage.query import Condition, Operator

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Introduction to Machine Learning",
            author="John Smith and Jane Doe",
        )

        assert Condition("title", Operator.CONTAINS, "Machine").matches(entry) is True
        assert Condition("title", Operator.CONTAINS, "Deep").matches(entry) is False
        assert Condition("author", Operator.CONTAINS, "Smith").matches(entry) is True

        assert (
            Condition("title", Operator.STARTS_WITH, "Introduction").matches(entry)
            is True
        )
        assert (
            Condition("title", Operator.STARTS_WITH, "Machine").matches(entry) is False
        )

        assert Condition("title", Operator.ENDS_WITH, "Learning").matches(entry) is True
        assert Condition("title", Operator.ENDS_WITH, "Machine").matches(entry) is False

    def test_regex_operator(self):
        """Regex operator matches patterns."""
        from bibmgr.storage.query import Condition, Operator

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Pattern Recognition 2020",
            doi="10.1234/journal.2020.123",
        )

        assert Condition("title", Operator.MATCHES, r"\d{4}").matches(entry) is True
        assert Condition("title", Operator.MATCHES, r"^\d{4}").matches(entry) is False

        doi_pattern = r"10\.\d{4}/[\w.]+\.\d{4}\.\d+"
        assert Condition("doi", Operator.MATCHES, doi_pattern).matches(entry) is True

    def test_collection_operators(self):
        """IN and NOT_IN operators work with collections."""
        from bibmgr.storage.query import Condition, Operator

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Test",
            year=2020,
            keywords=("machine learning", "ai", "neural networks"),
        )

        valid_years = [2019, 2020, 2021]
        assert Condition("year", Operator.IN, valid_years).matches(entry) is True
        assert Condition("year", Operator.IN, [2019, 2021]).matches(entry) is False

        assert Condition("year", Operator.NOT_IN, [2019, 2021]).matches(entry) is True
        assert Condition("year", Operator.NOT_IN, valid_years).matches(entry) is False

    def test_type_coercion(self):
        """Operators handle type coercion appropriately."""
        from bibmgr.storage.query import Condition, Operator

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Test Article",
            volume="10",  # String that looks like number
        )

        assert (
            Condition("year", Operator.CONTAINS, "20").matches(entry) is False
        )  # year is None

        assert Condition("year", Operator.GT, 2020).matches(entry) is False

    def test_invalid_field_access(self):
        """Accessing non-existent fields returns False gracefully."""
        from bibmgr.storage.query import Condition, Operator

        entry = Entry(key="test", type=EntryType.MISC, title="Test")

        cond = Condition("nonexistent", Operator.EQ, "value")
        assert cond.matches(entry) is False

        cond = Condition("nonexistent", Operator.EQ, None)
        assert cond.matches(entry) is True  # Treats missing as None


class TestQuery:
    """Test query composition with multiple conditions."""

    def test_empty_query_matches_all(self):
        """Empty query matches all entries."""
        from bibmgr.storage.query import Operator, Query

        query = Query(conditions=[], operator=Operator.AND)
        entry = Entry(key="test", type=EntryType.MISC, title="Test")

        assert query.matches(entry) is True

    def test_and_query(self):
        """AND query requires all conditions to match."""
        from bibmgr.storage.query import Condition, Operator, Query

        query = Query(
            conditions=[
                Condition("type", Operator.EQ, EntryType.ARTICLE),
                Condition("year", Operator.GT, 2000),
                Condition("title", Operator.CONTAINS, "Machine"),
            ],
            operator=Operator.AND,
        )

        entry1 = Entry(
            key="match",
            type=EntryType.ARTICLE,
            title="Machine Learning",
            year=2020,
        )
        assert query.matches(entry1) is True

        entry2 = Entry(
            key="fail",
            type=EntryType.BOOK,
            title="Machine Learning",
            year=2020,
        )
        assert query.matches(entry2) is False

        entry3 = Entry(
            key="fail2",
            type=EntryType.ARTICLE,
            title="Machine Learning",
            year=1999,
        )
        assert query.matches(entry3) is False

    def test_or_query(self):
        """OR query requires at least one condition to match."""
        from bibmgr.storage.query import Condition, Operator, Query

        query = Query(
            conditions=[
                Condition("author", Operator.CONTAINS, "Knuth"),
                Condition("author", Operator.CONTAINS, "Turing"),
                Condition("author", Operator.CONTAINS, "Dijkstra"),
            ],
            operator=Operator.OR,
        )

        entry1 = Entry(
            key="knuth",
            type=EntryType.BOOK,
            author="Donald E. Knuth",
            title="The Art of Computer Programming",
        )
        assert query.matches(entry1) is True

        entry2 = Entry(
            key="turing",
            type=EntryType.ARTICLE,
            author="Alan M. Turing",
            title="Computing Machinery",
        )
        assert query.matches(entry2) is True

        entry3 = Entry(
            key="other",
            type=EntryType.ARTICLE,
            author="Claude Shannon",
            title="Information Theory",
        )
        assert query.matches(entry3) is False

    def test_not_query(self):
        """NOT query inverts the result."""
        from bibmgr.storage.query import Condition, Operator, Query

        query = Query(
            conditions=[Condition("type", Operator.EQ, EntryType.BOOK)],
            operator=Operator.NOT,
        )

        article = Entry(key="a", type=EntryType.ARTICLE, title="Article")
        book = Entry(key="b", type=EntryType.BOOK, title="Book")

        assert query.matches(article) is True  # NOT book
        assert query.matches(book) is False  # NOT book

        query = Query(
            conditions=[
                Condition("type", Operator.EQ, EntryType.ARTICLE),
                Condition("year", Operator.GT, 2020),
            ],
            operator=Operator.NOT,
        )

        new_article = Entry(key="na", type=EntryType.ARTICLE, title="New", year=2021)
        old_article = Entry(key="oa", type=EntryType.ARTICLE, title="Old", year=2019)

        assert query.matches(new_article) is False  # Matches both conditions
        assert query.matches(old_article) is True  # Doesn't match year condition

    def test_nested_queries(self):
        """Queries can be nested for complex logic."""
        from bibmgr.storage.query import Condition, Operator, Query

        # (type = article AND year > 2020) OR (type = book AND publisher = "Springer")
        article_query = Query(
            conditions=[
                Condition("type", Operator.EQ, EntryType.ARTICLE),
                Condition("year", Operator.GT, 2020),
            ],
            operator=Operator.AND,
        )

        book_query = Query(
            conditions=[
                Condition("type", Operator.EQ, EntryType.BOOK),
                Condition("publisher", Operator.EQ, "Springer"),
            ],
            operator=Operator.AND,
        )

        combined_query = Query(
            conditions=[article_query, book_query],
            operator=Operator.OR,
        )

        entry1 = Entry(
            key="article",
            type=EntryType.ARTICLE,
            title="Recent Article",
            year=2022,
        )
        assert combined_query.matches(entry1) is True

        entry2 = Entry(
            key="book",
            type=EntryType.BOOK,
            title="Springer Book",
            publisher="Springer",
            year=2019,
        )
        assert combined_query.matches(entry2) is True

        entry3 = Entry(
            key="old",
            type=EntryType.ARTICLE,
            title="Old Article",
            year=2019,
        )
        assert combined_query.matches(entry3) is False


class TestQueryBuilder:
    """Test the fluent query builder interface."""

    def test_simple_where_clause(self):
        """QueryBuilder creates simple where conditions."""
        from bibmgr.storage.query import Condition, Operator, QueryBuilder

        query = QueryBuilder().where("year", "=", 2020).build()

        assert len(query.conditions) == 1
        condition = query.conditions[0]
        assert isinstance(condition, Condition)
        assert condition.field == "year"
        assert condition.operator == Operator.EQ
        assert condition.value == 2020

    def test_multiple_where_clauses(self):
        """Multiple where clauses create AND query."""
        from bibmgr.storage.query import Operator, QueryBuilder

        query = (
            QueryBuilder()
            .where("type", "=", "article")
            .where("year", ">", 2020)
            .where("author", "contains", "Smith")
            .build()
        )

        assert len(query.conditions) == 3
        assert query.operator == Operator.AND

    def test_convenience_methods(self):
        """Convenience methods create appropriate queries."""
        from bibmgr.storage.query import Condition, QueryBuilder

        query = QueryBuilder().where_type("article").build()
        condition = query.conditions[0]
        assert isinstance(condition, Condition)
        assert condition.field == "type"
        assert condition.value == "article"

        query = QueryBuilder().where_year(2020).build()
        condition = query.conditions[0]
        assert isinstance(condition, Condition)
        assert condition.field == "year"
        assert condition.value == 2020

        query = QueryBuilder().where_year_range(2020, 2023).build()
        assert len(query.conditions) == 2
        condition0 = query.conditions[0]
        condition1 = query.conditions[1]
        assert isinstance(condition0, Condition) and isinstance(condition1, Condition)
        assert condition0.value == 2020  # GTE
        assert condition1.value == 2023  # LTE

        query = QueryBuilder().where_author_contains("Knuth").build()
        condition = query.conditions[0]
        assert isinstance(condition, Condition)
        assert condition.field == "author"
        assert condition.value == "Knuth"

        query = QueryBuilder().where_has_doi().build()
        condition = query.conditions[0]
        assert isinstance(condition, Condition)
        assert condition.field == "doi"
        assert condition.value is None
        assert condition.operator.value == "!="

    def test_or_where_conversion(self):
        """or_where converts query to OR mode."""
        from bibmgr.storage.query import Operator, QueryBuilder

        query = (
            QueryBuilder()
            .where("author", "contains", "Knuth")
            .or_where("author", "contains", "Turing")
            .or_where("author", "contains", "Dijkstra")
            .build()
        )

        assert query.operator == Operator.OR
        assert len(query.conditions) == 3

    def test_where_not(self):
        """where_not creates NOT conditions."""
        from bibmgr.storage.query import Operator, QueryBuilder

        query = QueryBuilder().where_not("type", "=", "misc").build()

        assert len(query.conditions) == 1
        not_query = query.conditions[0]
        assert isinstance(not_query, type(query))  # It's a Query
        assert not_query.operator == Operator.NOT

    def test_complex_query_building(self):
        """Complex queries can be built fluently."""
        from bibmgr.storage.query import QueryBuilder

        query = (
            QueryBuilder()
            .where("type", "=", "article")
            .where_year_range(2020, 2024)
            .where("keywords", "contains", "machine learning")
            .where_not("title", "contains", "survey")
            .build()
        )

        entry = Entry(
            key="ml2023",
            type=EntryType.ARTICLE,
            title="Deep Learning for Image Recognition",
            year=2023,
            keywords=("machine learning", "computer vision"),
        )
        assert query.matches(entry) is True

        survey = Entry(
            key="survey2023",
            type=EntryType.ARTICLE,
            title="A Survey of Machine Learning Methods",
            year=2023,
            keywords=("machine learning", "survey"),
        )
        assert query.matches(survey) is False


class TestSearchFunctions:
    """Test convenience search functions."""

    def test_search_entries(self, sample_entries):
        """search_entries filters entries using query."""
        from bibmgr.storage.query import QueryBuilder, search_entries

        query = QueryBuilder().where("year", "<", 1970).build()
        results = search_entries(sample_entries, query)

        assert len(results) == 3  # Turing 1950, Dijkstra 1968, Shannon 1948
        assert all(e.year and e.year < 1970 for e in results)

    def test_recent_entries(self):
        """recent_entries finds recently added entries."""
        from bibmgr.storage.query import recent_entries

        now = datetime.now()
        entries = [
            Entry(
                key="new",
                type=EntryType.MISC,
                title="New",
                added=now - timedelta(days=5),
            ),
            Entry(
                key="old",
                type=EntryType.MISC,
                title="Old",
                added=now - timedelta(days=35),
            ),
            Entry(
                key="ancient",
                type=EntryType.MISC,
                title="Ancient",
                added=now - timedelta(days=365),
            ),
        ]

        recent = recent_entries(entries)
        assert len(recent) == 1
        assert recent[0].key == "new"

        recent = recent_entries(entries, days=40)
        assert len(recent) == 2
        assert {e.key for e in recent} == {"new", "old"}

    def test_unread_entries(self):
        """unread_entries filters by reading status."""
        from bibmgr.storage.query import unread_entries

        entries = [
            Entry(key="unread1", type=EntryType.MISC, title="Unread 1"),
            Entry(key="read1", type=EntryType.MISC, title="Read 1"),
            Entry(key="unread2", type=EntryType.MISC, title="Unread 2"),
        ]

        class MockMetadataStore:
            def get_metadata(self, key):
                class Metadata:
                    def __init__(self, key):
                        self.read_status = "read" if key == "read1" else "unread"

                return Metadata(key)

        metadata_store = MockMetadataStore()
        unread = unread_entries(entries, metadata_store)

        assert len(unread) == 2
        assert {e.key for e in unread} == {"unread1", "unread2"}


class TestQueryPerformance:
    """Test query performance with large datasets."""

    def test_query_performance_scaling(self, performance_entries):
        """Queries perform well with many entries."""
        import time

        from bibmgr.storage.query import QueryBuilder, search_entries

        query = (
            QueryBuilder()
            .where("year", ">=", 2010)
            .where("year", "<=", 2020)
            .where("journal", "contains", "Journal 2")
            .build()
        )

        start = time.time()
        results = search_entries(performance_entries, query)
        duration = time.time() - start

        assert duration < 0.1  # 100ms
        assert len(results) > 0

        for entry in results:
            assert entry.year and 2010 <= entry.year <= 2020
            assert entry.journal and "Journal 2" in entry.journal

    def test_or_query_performance(self, performance_entries):
        """OR queries with many conditions perform well."""
        import time

        from bibmgr.storage.query import QueryBuilder, search_entries

        builder = QueryBuilder()
        builder.where("author", "=", "Author 0")
        for i in range(1, 20):
            builder.or_where("author", "=", f"Author {i}")

        query = builder.build()

        start = time.time()
        results = search_entries(performance_entries, query)
        duration = time.time() - start

        assert duration < 0.2  # 200ms
        assert len(results) == 200  # 20 authors × 10 entries each

        contains_builder = QueryBuilder()
        contains_builder.where("title", "contains", "Paper")  # Should match all entries
        contains_query = contains_builder.build()

        contains_results = search_entries(performance_entries, contains_query)
        assert len(contains_results) == 1000  # All entries have "Paper" in title
