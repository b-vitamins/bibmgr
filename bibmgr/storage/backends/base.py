"""Base storage backend interface."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


class BaseBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the backend."""
        pass

    @abstractmethod
    def read(self, key: str) -> dict[str, Any] | None:
        """Read data by key."""
        pass

    @abstractmethod
    def write(self, key: str, data: dict[str, Any]) -> None:
        """Write data with key."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete data by key."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass

    @abstractmethod
    def keys(self) -> list[str]:
        """Get all keys."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all data."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close backend connections."""
        pass

    def supports_transactions(self) -> bool:
        """Check if backend supports transactions."""
        return False

    @contextmanager
    def begin_transaction(self) -> Iterator[None]:
        """Begin a transaction (if supported)."""
        yield


class CachedBackend(BaseBackend):
    """Mixin for backends with caching support."""

    def __init__(self, cache_size: int = 1000):
        from functools import lru_cache

        # Use Python's built-in LRU cache
        self._read_cache = lru_cache(maxsize=cache_size)(self._read_impl)

    def read(self, key: str) -> dict[str, Any] | None:
        """Read with caching."""
        return self._read_cache(key)

    @abstractmethod
    def _read_impl(self, key: str) -> dict[str, Any] | None:
        """Actual read implementation."""
        pass

    def write(self, key: str, data: dict[str, Any]) -> None:
        """Write and invalidate cache."""
        self._write_impl(key, data)
        self._read_cache.cache_clear()

    @abstractmethod
    def _write_impl(self, key: str, data: dict[str, Any]) -> None:
        """Actual write implementation."""
        pass

    def delete(self, key: str) -> bool:
        """Delete and invalidate cache."""
        result = self._delete_impl(key)
        if result:
            self._read_cache.cache_clear()
        return result

    @abstractmethod
    def _delete_impl(self, key: str) -> bool:
        """Actual delete implementation."""
        pass
