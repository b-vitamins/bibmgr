"""In-memory storage backend for testing."""

from contextlib import contextmanager
from copy import deepcopy
from typing import Any

from .base import BaseBackend


class MemoryBackend(BaseBackend):
    """In-memory storage backend for testing purposes."""

    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}
        self._transaction_data: dict[str, dict[str, Any]] | None = None
        self._in_transaction = False

    def initialize(self) -> None:
        """Initialize the backend (no-op for memory)."""
        pass

    def read(self, key: str) -> dict[str, Any] | None:
        """Read data by key."""
        data = self._get_data()
        if key in data:
            return deepcopy(data[key])
        return None

    def write(self, key: str, data: dict[str, Any]) -> None:
        """Write data with key."""
        self._get_data()[key] = deepcopy(data)

    def delete(self, key: str) -> bool:
        """Delete data by key."""
        data = self._get_data()
        if key in data:
            del data[key]
            return True
        return False

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._get_data()

    def keys(self) -> list[str]:
        """Get all keys."""
        return list(self._get_data().keys())

    def clear(self) -> None:
        """Clear all data."""
        self._get_data().clear()

    def close(self) -> None:
        """Close backend (no-op for memory)."""
        pass

    def supports_transactions(self) -> bool:
        """Memory backend supports transactions."""
        return True

    @contextmanager
    def begin_transaction(self):
        """Begin a transaction."""
        if self._in_transaction:
            raise RuntimeError("Already in a transaction")

        self._in_transaction = True
        self._transaction_data = deepcopy(self._data)

        try:
            yield
            self._commit()
        except Exception:
            self._rollback()
            raise

    def _get_data(self) -> dict[str, dict[str, Any]]:
        """Get the active data store."""
        if self._in_transaction and self._transaction_data is not None:
            return self._transaction_data
        return self._data

    def _commit(self) -> None:
        """Commit the transaction."""
        if not self._in_transaction:
            raise RuntimeError("Not in a transaction")

        if self._transaction_data is not None:
            self._data = self._transaction_data
        self._transaction_data = None
        self._in_transaction = False

    def _rollback(self) -> None:
        """Rollback the transaction."""
        if not self._in_transaction:
            raise RuntimeError("Not in a transaction")

        self._transaction_data = None
        self._in_transaction = False

    def get_size(self) -> int:
        """Get the number of stored items."""
        return len(self._data)

    def get_memory_usage(self) -> int:
        """Estimate memory usage in bytes."""
        import sys

        total = 0
        for key, value in self._data.items():
            total += sys.getsizeof(key)
            total += sys.getsizeof(value)
        return total
