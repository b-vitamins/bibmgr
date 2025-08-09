"""SQLite storage backend for better performance and queries."""

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .base import BaseBackend


class SQLiteBackend(BaseBackend):
    """SQLite-based storage with full-text search support."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._transaction_active = threading.local()
        self.conn: sqlite3.Connection | None = sqlite3.connect(
            str(self.db_path), check_same_thread=False
        )
        self.connection.row_factory = sqlite3.Row
        self.initialize()

    @property
    def connection(self) -> sqlite3.Connection:
        """Get the connection, ensuring it exists."""
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")
        return self.conn

    def initialize(self) -> None:
        """Create database schema."""
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS entries (
                key TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_entries_type ON entries(type);
            CREATE INDEX IF NOT EXISTS idx_entries_created ON entries(created_at);
            CREATE INDEX IF NOT EXISTS idx_entries_updated ON entries(updated_at);
            CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                key UNINDEXED,
                title,
                author,
                abstract,
                keywords
            );
            CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
                INSERT INTO entries_fts(key, title, author, abstract, keywords)
                SELECT
                    NEW.key,
                    json_extract(NEW.data, '$.title'),
                    json_extract(NEW.data, '$.author'),
                    json_extract(NEW.data, '$.abstract'),
                    json_extract(NEW.data, '$.keywords')
                ;
            END;

            CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
                UPDATE entries_fts SET
                    title = json_extract(NEW.data, '$.title'),
                    author = json_extract(NEW.data, '$.author'),
                    abstract = json_extract(NEW.data, '$.abstract'),
                    keywords = json_extract(NEW.data, '$.keywords')
                WHERE key = NEW.key;
            END;

            CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
                DELETE FROM entries_fts WHERE key = OLD.key;
            END;
            CREATE TRIGGER IF NOT EXISTS entries_update_timestamp
            AFTER UPDATE ON entries
            BEGIN
                UPDATE entries SET updated_at = CURRENT_TIMESTAMP WHERE key = NEW.key;
            END;
        """)

        self.connection.commit()

    def read(self, key: str) -> dict[str, Any] | None:
        """Read entry from database."""
        with self._lock:
            cursor = self.connection.execute(
                "SELECT data FROM entries WHERE key = ?", (key,)
            )
            row = cursor.fetchone()

            if row:
                return json.loads(row["data"])
            return None

    def write(self, key: str, data: dict[str, Any]) -> None:
        """Write entry to database."""
        with self._lock:
            json_data = json.dumps(data, sort_keys=True)

            self.connection.execute(
                """
                INSERT INTO entries (key, type, data) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    type = excluded.type,
                    data = excluded.data
            """,
                (key, data.get("type", "misc"), json_data),
            )

            if not getattr(self._transaction_active, "active", False):
                self.connection.commit()

    def delete(self, key: str) -> bool:
        """Delete entry from database."""
        with self._lock:
            cursor = self.connection.execute(
                "DELETE FROM entries WHERE key = ?", (key,)
            )
            if not getattr(self._transaction_active, "active", False):
                self.connection.commit()
            return cursor.rowcount > 0

    def exists(self, key: str) -> bool:
        """Check if entry exists."""
        with self._lock:
            cursor = self.connection.execute(
                "SELECT 1 FROM entries WHERE key = ? LIMIT 1", (key,)
            )
            return cursor.fetchone() is not None

    def keys(self) -> list[str]:
        """Get all keys."""
        with self._lock:
            cursor = self.connection.execute("SELECT key FROM entries ORDER BY key")
            return [row["key"] for row in cursor]

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self.connection.execute("DELETE FROM entries")
            if not getattr(self._transaction_active, "active", False):
                self.connection.commit()

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.connection.close()
            self.conn = None

    def supports_transactions(self) -> bool:
        """SQLite supports transactions."""
        return True

    @contextmanager
    def begin_transaction(self) -> Iterator[None]:
        """Transaction context manager."""
        with self._lock:
            self._transaction_active.active = True
            in_transaction = self.connection.in_transaction

            if not in_transaction:
                self.connection.execute("BEGIN")

            try:
                yield
                if not in_transaction:
                    self.connection.commit()
            except Exception:
                if not in_transaction:
                    self.connection.rollback()
                raise
            finally:
                self._transaction_active.active = False

    def search(self, query: str) -> list[str]:
        """Full-text search across entries."""
        cursor = self.connection.execute(
            """
            SELECT key FROM entries_fts
            WHERE entries_fts MATCH ?
            ORDER BY rank
        """,
            (query,),
        )

        return [row["key"] for row in cursor]

    def query_entries(self, filters: dict[str, Any]) -> list[str]:
        """Query entries with filters."""
        conditions = []
        params = []

        for field, value in filters.items():
            if field == "type":
                conditions.append("type = ?")
                params.append(value)
            elif field == "year":
                conditions.append("json_extract(data, '$.year') = ?")
                params.append(value)
            elif field == "author":
                conditions.append("json_extract(data, '$.author') LIKE ?")
                params.append(f"%{value}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor = self.connection.execute(
            f"SELECT key FROM entries WHERE {where_clause} ORDER BY key", params
        )

        return [row["key"] for row in cursor]

    def get_statistics(self) -> dict[str, Any]:
        """Get database statistics."""
        stats = {}

        cursor = self.connection.execute("SELECT COUNT(*) as count FROM entries")
        stats["total_entries"] = cursor.fetchone()["count"]

        cursor = self.connection.execute("""
            SELECT type, COUNT(*) as count
            FROM entries
            GROUP BY type
            ORDER BY count DESC
        """)
        stats["by_type"] = {row["type"]: row["count"] for row in cursor}

        cursor = self.connection.execute("""
            SELECT json_extract(data, '$.year') as year, COUNT(*) as count
            FROM entries
            WHERE year IS NOT NULL
            GROUP BY year
            ORDER BY year DESC
        """)
        stats["by_year"] = {row["year"]: row["count"] for row in cursor}

        return stats
