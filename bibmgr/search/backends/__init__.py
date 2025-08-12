"""Search backend implementations."""

from .base import (
    BackendResult,
    IndexError,
    QueryError,
    SearchBackend,
    SearchError,
    SearchMatch,
    SearchQuery,
)

__all__ = [
    "BackendResult",
    "SearchBackend",
    "SearchError",
    "SearchMatch",
    "SearchQuery",
    "IndexError",
    "QueryError",
]
