"""Query parser for search queries."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class QueryType(Enum):
    """Types of search queries."""

    TERM = "term"
    PHRASE = "phrase"
    FIELD = "field"
    BOOLEAN = "boolean"
    WILDCARD = "wildcard"
    FUZZY = "fuzzy"
    RANGE = "range"


class BooleanOperator(Enum):
    """Boolean operators for query combination."""

    AND = "AND"
    OR = "OR"
    NOT = "NOT"


@dataclass
class ParsedQuery(ABC):
    """Base class for parsed query objects."""

    @property
    @abstractmethod
    def query_type(self) -> QueryType:
        """Get the query type."""
        pass

    @abstractmethod
    def to_string(self) -> str:
        """Convert query back to string representation."""
        pass

    @abstractmethod
    def get_terms(self) -> list[str]:
        """Get all search terms from the query."""
        pass


@dataclass
class TermQuery(ParsedQuery):
    """Simple term query."""

    term: str
    boost: float = 1.0

    @property
    def query_type(self) -> QueryType:
        return QueryType.TERM

    def to_string(self) -> str:
        if self.boost != 1.0:
            return f"{self.term}^{self.boost}"
        return self.term

    def get_terms(self) -> list[str]:
        return [self.term]


@dataclass
class PhraseQuery(ParsedQuery):
    """Exact phrase query."""

    phrase: str
    slop: int = 0
    boost: float = 1.0

    @property
    def query_type(self) -> QueryType:
        return QueryType.PHRASE

    def to_string(self) -> str:
        result = f'"{self.phrase}"'
        if self.slop > 0:
            result += f"~{self.slop}"
        if self.boost != 1.0:
            result += f"^{self.boost}"
        return result

    def get_terms(self) -> list[str]:
        return self.phrase.split()


@dataclass
class FieldQuery(ParsedQuery):
    """Field-specific query."""

    field: str
    query: ParsedQuery

    @property
    def query_type(self) -> QueryType:
        return QueryType.FIELD

    def to_string(self) -> str:
        return f"{self.field}:{self.query.to_string()}"

    def get_terms(self) -> list[str]:
        return self.query.get_terms()


@dataclass
class BooleanQuery(ParsedQuery):
    """Boolean combination of queries."""

    operator: BooleanOperator
    queries: list[ParsedQuery]
    minimum_should_match: int | None = None

    @property
    def query_type(self) -> QueryType:
        return QueryType.BOOLEAN

    def to_string(self) -> str:
        if not self.queries:
            return ""

        query_strings = [q.to_string() for q in self.queries]

        if self.operator == BooleanOperator.NOT:
            if len(self.queries) == 2:
                return f"{query_strings[0]} NOT {query_strings[1]}"
            else:
                return f"NOT {query_strings[0]}"
        else:
            op_str = f" {self.operator.value} "
            return f"({op_str.join(query_strings)})"

    def get_terms(self) -> list[str]:
        terms = []
        for query in self.queries:
            terms.extend(query.get_terms())
        return terms


@dataclass
class WildcardQuery(ParsedQuery):
    """Wildcard pattern query."""

    pattern: str
    boost: float = 1.0

    @property
    def query_type(self) -> QueryType:
        return QueryType.WILDCARD

    def to_string(self) -> str:
        if self.boost != 1.0:
            return f"{self.pattern}^{self.boost}"
        return self.pattern

    def get_terms(self) -> list[str]:
        parts = re.split(r"[*?]", self.pattern)
        return [part for part in parts if part]


@dataclass
class FuzzyQuery(ParsedQuery):
    """Fuzzy/approximate match query."""

    term: str
    max_edits: int = 2
    prefix_length: int = 0
    boost: float = 1.0

    @property
    def query_type(self) -> QueryType:
        return QueryType.FUZZY

    def to_string(self) -> str:
        result = f"{self.term}~"
        if self.max_edits != 2:
            result += str(self.max_edits)
        if self.boost != 1.0:
            result += f"^{self.boost}"
        return result

    def get_terms(self) -> list[str]:
        return [self.term]


@dataclass
class RangeQuery(ParsedQuery):
    """Range query for numeric or date fields."""

    field: str
    start: str | int | float | None
    end: str | int | float | None
    include_start: bool = True
    include_end: bool = True
    boost: float = 1.0

    @property
    def query_type(self) -> QueryType:
        return QueryType.RANGE

    def to_string(self) -> str:
        start_bracket = "[" if self.include_start else "{"
        end_bracket = "]" if self.include_end else "}"

        start_val = "*" if self.start is None else str(self.start)
        end_val = "*" if self.end is None else str(self.end)

        result = f"{self.field}:{start_bracket}{start_val} TO {end_val}{end_bracket}"
        if self.boost != 1.0:
            result += f"^{self.boost}"
        return result

    def get_terms(self) -> list[str]:
        terms = []
        if self.start is not None:
            terms.append(str(self.start))
        if self.end is not None:
            terms.append(str(self.end))
        return terms


class QueryParser:
    """Parser for search query strings."""

    def __init__(self):
        self.field_pattern = re.compile(r"(\w+):")
        self.phrase_pattern = re.compile(r'"([^"]*)"(?:~(\d+))?(?:\^([\d.]+))?')
        self.fuzzy_pattern = re.compile(r"(\w+)~(\d+)?(?:\^([\d.]+))?")
        self.range_pattern = re.compile(
            r"(\w+):([\[{])([^TO]*?)\s+TO\s+([^}\]]*?)([\]}])(?:\^([\d.]+))?"
        )
        self.wildcard_pattern = re.compile(r"\w*[*?]\w*")
        self.boost_pattern = re.compile(r"\^([\d.]+)$")
        self.boolean_pattern = re.compile(r"\b(AND|OR|NOT)\b", re.IGNORECASE)

    def parse(self, query_string: str) -> ParsedQuery:
        """Parse a query string into a structured query.

        Args:
            query_string: Raw query string from user

        Returns:
            ParsedQuery object representing the query
        """
        if not query_string or not query_string.strip():
            return TermQuery("")

        query_string = query_string.strip()

        boolean_query = self._parse_boolean_query(query_string)
        if boolean_query:
            return boolean_query

        range_query = self._parse_range_query(query_string)
        if range_query:
            return range_query

        field_query = self._parse_field_query(query_string)
        if field_query:
            return field_query

        phrase_query = self._parse_phrase_query(query_string)
        if phrase_query:
            return phrase_query

        fuzzy_query = self._parse_fuzzy_query(query_string)
        if fuzzy_query:
            return fuzzy_query

        if self.wildcard_pattern.search(query_string):
            return self._parse_wildcard_query(query_string)

        return self._parse_term_query(query_string)

    def _parse_boolean_query(self, query_string: str) -> BooleanQuery | None:
        """Parse boolean query with AND, OR, NOT operators."""
        operators = list(self.boolean_pattern.finditer(query_string))

        if not operators:
            return None

        if len(operators) == 1 and operators[0].group(1).upper() == "NOT":
            not_match = operators[0]
            before_not = query_string[: not_match.start()].strip()
            after_not = query_string[not_match.end() :].strip()

            queries = []
            if before_not:
                queries.append(self.parse(before_not))
            if after_not:
                queries.append(self.parse(after_not))

            if queries:
                return BooleanQuery(BooleanOperator.NOT, queries)

        first_op = operators[0]
        operator = BooleanOperator(first_op.group(1).upper())

        left_part = query_string[: first_op.start()].strip()
        right_part = query_string[first_op.end() :].strip()

        if left_part and right_part:
            left_query = self.parse(left_part)
            right_query = self.parse(right_part)
            return BooleanQuery(operator, [left_query, right_query])

        return None

    def _parse_field_query(self, query_string: str) -> FieldQuery | None:
        """Parse field-specific query like 'title:machine learning'."""
        match = self.field_pattern.match(query_string)
        if not match:
            return None

        field = match.group(1)

        if field.lower() in ["http", "https", "ftp", "ftps", "file", "mailto"]:
            return None

        field_value = query_string[match.end() :].strip()

        if field_value:
            subquery = self.parse(field_value)
            return FieldQuery(field, subquery)

        return None

    def _parse_range_query(self, query_string: str) -> RangeQuery | None:
        """Parse range query like 'year:[2020 TO 2023]'."""
        match = self.range_pattern.search(query_string)
        if not match:
            return None

        field = match.group(1)
        start_bracket = match.group(2)
        start_value = match.group(3).strip()
        end_value = match.group(4).strip()
        end_bracket = match.group(5)
        boost_str = match.group(6)

        start = None if start_value == "*" else self._parse_range_value(start_value)
        end = None if end_value == "*" else self._parse_range_value(end_value)

        include_start = start_bracket == "["
        include_end = end_bracket == "]"

        boost = float(boost_str) if boost_str else 1.0

        return RangeQuery(field, start, end, include_start, include_end, boost)

    def _parse_phrase_query(self, query_string: str) -> PhraseQuery | None:
        """Parse phrase query like '"machine learning"~2^1.5'."""
        match = self.phrase_pattern.search(query_string)
        if not match:
            return None

        phrase = match.group(1)
        slop = int(match.group(2)) if match.group(2) else 0
        boost = float(match.group(3)) if match.group(3) else 1.0

        return PhraseQuery(phrase, slop, boost)

    def _parse_fuzzy_query(self, query_string: str) -> FuzzyQuery | None:
        """Parse fuzzy query like 'learning~2^1.5'."""
        match = self.fuzzy_pattern.search(query_string)
        if not match:
            return None

        term = match.group(1)
        max_edits = int(match.group(2)) if match.group(2) else 2
        boost = float(match.group(3)) if match.group(3) else 1.0

        return FuzzyQuery(term, max_edits, 0, boost)

    def _parse_wildcard_query(self, query_string: str) -> WildcardQuery:
        """Parse wildcard query like 'learn*'."""
        boost = 1.0
        pattern = query_string

        boost_match = self.boost_pattern.search(query_string)
        if boost_match:
            boost = float(boost_match.group(1))
            pattern = query_string[: boost_match.start()]

        return WildcardQuery(pattern, boost)

    def _parse_term_query(self, query_string: str) -> TermQuery:
        """Parse simple term query, possibly with boost."""
        boost = 1.0
        term = query_string

        boost_match = self.boost_pattern.search(query_string)
        if boost_match:
            boost = float(boost_match.group(1))
            term = query_string[: boost_match.start()]

        return TermQuery(term.strip(), boost)

    def _parse_range_value(self, value: str) -> int | float | str:
        """Parse range value, trying to detect numeric values."""
        try:
            return int(value)
        except ValueError:
            pass

        try:
            return float(value)
        except ValueError:
            pass

        return value

    def extract_field_queries(self, query: ParsedQuery) -> dict[str, list[ParsedQuery]]:
        """Extract all field queries from a parsed query.

        Args:
            query: Parsed query to analyze

        Returns:
            Dictionary mapping field names to lists of queries for that field
        """
        field_queries = {}

        def collect_field_queries(q: ParsedQuery):
            if isinstance(q, FieldQuery):
                if q.field not in field_queries:
                    field_queries[q.field] = []
                field_queries[q.field].append(q.query)
            elif isinstance(q, BooleanQuery):
                for subquery in q.queries:
                    collect_field_queries(subquery)

        collect_field_queries(query)
        return field_queries

    def get_query_complexity(self, query: ParsedQuery) -> int:
        """Calculate complexity score for a query.

        Args:
            query: Parsed query to analyze

        Returns:
            Complexity score (higher = more complex)
        """
        if isinstance(query, TermQuery):
            return 1
        elif isinstance(query, PhraseQuery):
            return len(query.phrase.split())
        elif isinstance(query, FieldQuery):
            return 1 + self.get_query_complexity(query.query)
        elif isinstance(query, BooleanQuery):
            return sum(self.get_query_complexity(q) for q in query.queries)
        elif isinstance(query, WildcardQuery):
            return 3
        elif isinstance(query, FuzzyQuery):
            return 5
        elif isinstance(query, RangeQuery):
            return 2
        else:
            return 1

    def validate_query(self, query: ParsedQuery) -> list[str]:
        """Validate a parsed query and return any issues.

        Args:
            query: Parsed query to validate

        Returns:
            List of validation error messages
        """
        errors = []

        def validate_recursive(q: ParsedQuery):
            if isinstance(q, TermQuery):
                if not q.term.strip():
                    errors.append("Empty term in query")
            elif isinstance(q, PhraseQuery):
                if not q.phrase.strip():
                    errors.append("Empty phrase in query")
            elif isinstance(q, FieldQuery):
                if not q.field.strip():
                    errors.append("Empty field name in field query")
                validate_recursive(q.query)
            elif isinstance(q, BooleanQuery):
                if len(q.queries) < 2 and q.operator != BooleanOperator.NOT:
                    errors.append(
                        f"Boolean {q.operator.value} query needs at least 2 subqueries"
                    )
                for subquery in q.queries:
                    validate_recursive(subquery)
            elif isinstance(q, FuzzyQuery):
                if q.max_edits < 0 or q.max_edits > 2:
                    errors.append("Fuzzy query max_edits must be 0-2")
            elif isinstance(q, RangeQuery):
                if not q.field.strip():
                    errors.append("Range query missing field name")

        validate_recursive(query)
        return errors
