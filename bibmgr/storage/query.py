"""Query language for searching bibliography entries.

Provides composable query building with support for field filtering,
logical operators, and backend optimization. Supports both programmatic
and fluent-style query construction.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Union

from bibmgr.core.models import Entry


class Operator(Enum):
    """Query operators."""

    # Comparison
    EQ = "="
    NE = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="

    # String
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"  # regex

    # Collection
    IN = "in"
    NOT_IN = "not_in"

    # Logical
    AND = "and"
    OR = "or"
    NOT = "not"


@dataclass
class Condition:
    """A single query condition."""

    field: str
    operator: Operator
    value: Any

    def matches(self, entry: Entry) -> bool:
        """Check if entry matches this condition."""
        try:
            field_value = getattr(entry, self.field, None)

            if field_value is None:
                return self.operator == Operator.EQ and self.value is None

            if self.operator == Operator.EQ:
                if hasattr(field_value, "value") and hasattr(self.value, "value"):
                    return field_value.value == self.value.value
                elif hasattr(field_value, "value"):
                    return field_value.value == self.value
                elif hasattr(self.value, "value"):
                    return field_value == self.value.value
                return field_value == self.value
            elif self.operator == Operator.NE:
                if hasattr(field_value, "value") and hasattr(self.value, "value"):
                    return field_value.value != self.value.value
                elif hasattr(field_value, "value"):
                    return field_value.value != self.value
                elif hasattr(self.value, "value"):
                    return field_value != self.value.value
                return field_value != self.value
            elif self.operator == Operator.GT:
                return field_value > self.value
            elif self.operator == Operator.GTE:
                return field_value >= self.value
            elif self.operator == Operator.LT:
                return field_value < self.value
            elif self.operator == Operator.LTE:
                return field_value <= self.value
            elif self.operator == Operator.CONTAINS:
                return str(self.value).lower() in str(field_value).lower()
            elif self.operator == Operator.STARTS_WITH:
                return str(field_value).lower().startswith(str(self.value).lower())
            elif self.operator == Operator.ENDS_WITH:
                return str(field_value).lower().endswith(str(self.value).lower())
            elif self.operator == Operator.IN:
                return field_value in self.value
            elif self.operator == Operator.NOT_IN:
                return field_value not in self.value
            elif self.operator == Operator.MATCHES:
                import re

                return bool(re.search(self.value, str(field_value)))

            return False

        except Exception:
            return False


@dataclass
class Query:
    """A query combining multiple conditions."""

    conditions: list[Union[Condition, "Query"]]
    operator: Operator = Operator.AND

    def matches(self, entry: Entry) -> bool:
        """Check if entry matches this query."""
        if not self.conditions:
            return True

        if self.operator == Operator.AND:
            return all(c.matches(entry) for c in self.conditions)
        elif self.operator == Operator.OR:
            return any(c.matches(entry) for c in self.conditions)
        elif self.operator == Operator.NOT:
            return not all(c.matches(entry) for c in self.conditions)

        return False

    def add(self, condition: Union[Condition, "Query"]) -> "Query":
        """Add a condition to this query."""
        self.conditions.append(condition)
        return self


class QueryBuilder:
    """Fluent interface for building queries."""

    def __init__(self):
        self.query = Query(conditions=[])

    def where(self, field: str, operator: str | Operator, value: Any) -> "QueryBuilder":
        """Add a where condition."""
        if isinstance(operator, str):
            operator = Operator(operator)

        self.query.add(Condition(field, operator, value))
        return self

    def where_type(self, entry_type: str) -> "QueryBuilder":
        """Filter by entry type."""
        return self.where("type", Operator.EQ, entry_type)

    def where_year(self, year: int) -> "QueryBuilder":
        """Filter by year."""
        return self.where("year", Operator.EQ, year)

    def where_year_range(self, start: int, end: int) -> "QueryBuilder":
        """Filter by year range."""
        self.where("year", Operator.GTE, start)
        self.where("year", Operator.LTE, end)
        return self

    def where_author_contains(self, author: str) -> "QueryBuilder":
        """Filter by author containing text."""
        return self.where("author", Operator.CONTAINS, author)

    def where_title_contains(self, title: str) -> "QueryBuilder":
        """Filter by title containing text."""
        return self.where("title", Operator.CONTAINS, title)

    def where_has_doi(self) -> "QueryBuilder":
        """Filter entries that have a DOI."""
        return self.where("doi", Operator.NE, None)

    def where_has_file(self) -> "QueryBuilder":
        """Filter entries that have a file."""
        return self.where("file", Operator.NE, None)

    def or_where(
        self, field: str, operator: str | Operator, value: Any
    ) -> "QueryBuilder":
        """Add an OR condition."""
        if self.query.operator != Operator.OR:
            if self.query.conditions:
                sub_query = Query(
                    conditions=self.query.conditions, operator=self.query.operator
                )
                self.query = Query(conditions=[sub_query], operator=Operator.OR)
            else:
                self.query.operator = Operator.OR

        if isinstance(operator, str):
            operator = Operator(operator)

        self.query.add(Condition(field, operator, value))
        return self

    def where_not(
        self, field: str, operator: str | Operator, value: Any
    ) -> "QueryBuilder":
        """Add a NOT condition."""
        if isinstance(operator, str):
            operator = Operator(operator)

        not_query = Query(
            conditions=[Condition(field, operator, value)], operator=Operator.NOT
        )
        self.query.add(not_query)
        return self

    def build(self) -> Query:
        """Build the final query."""
        return self.query


def search_entries(entries: list[Entry], query: Query) -> list[Entry]:
    """Search entries using a query."""
    return [entry for entry in entries if query.matches(entry)]


def recent_entries(entries: list[Entry], days: int = 30) -> list[Entry]:
    """Get entries added in the last N days."""
    from datetime import timedelta

    cutoff = datetime.now() - timedelta(days=days)

    query = QueryBuilder().where("added", Operator.GTE, cutoff).build()
    return search_entries(entries, query)


def unread_entries(entries: list[Entry], metadata_store) -> list[Entry]:
    """Get entries that haven't been read."""
    unread = []
    for entry in entries:
        metadata = metadata_store.get_metadata(entry.key)
        if metadata.read_status == "unread":
            unread.append(entry)
    return unread
