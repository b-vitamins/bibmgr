"""Storage layer for notes with concurrent safety and optimizations.

This module provides SQLite-based storage with:
- Thread-safe operations with proper locking
- Batch operations with transaction optimization
- Full-text search using FTS5
- Version tracking and history
- Automatic corruption detection and recovery attempts
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from bibmgr.notes.exceptions import (
    OptimisticLockError,
    StorageError,
)
from bibmgr.notes.models import (
    Note,
    NoteType,
    NoteVersion,
    Priority,
    Quote,
    QuoteCategory,
    ReadingProgress,
    ReadingStatus,
)


class NoteStorage:
    """SQLite-based storage for notes with concurrent safety."""

    # Lock timeout in seconds
    LOCK_TIMEOUT = 30.0

    # Maximum content size (10 MB)
    MAX_CONTENT_SIZE = 10 * 1024 * 1024

    def __init__(self, db_path: Path | str):
        """Initialize storage with database path.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Thread-local storage for connections
        self._local = threading.local()

        # Write lock for concurrent write safety
        self._write_lock = threading.RLock()

        # Initialize schema
        self.initialize()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path,
                timeout=self.LOCK_TIMEOUT,
                isolation_level=None,  # Autocommit mode
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self._local.conn.execute("PRAGMA foreign_keys = ON")
            # Optimize for concurrent access
            self._local.conn.execute("PRAGMA journal_mode = WAL")
            self._local.conn.execute("PRAGMA synchronous = NORMAL")

        return self._local.conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database transactions.

        Yields:
            Database connection in transaction
        """
        conn = self._get_connection()

        try:
            conn.execute("BEGIN")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def initialize(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()

        with self._write_lock:
            # Notes table
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    entry_key TEXT NOT NULL,
                    type TEXT NOT NULL,
                    title TEXT,
                    content TEXT NOT NULL,
                    tags TEXT,  -- JSON array
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    content_hash TEXT,
                    CHECK (length(content) <= {self.MAX_CONTENT_SIZE})
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notes_entry
                ON notes(entry_key)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notes_type
                ON notes(type)
            """)

            # Note references table (separate for normalization)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS note_references (
                    note_id TEXT NOT NULL,
                    reference_id TEXT NOT NULL,
                    PRIMARY KEY (note_id, reference_id),
                    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
                )
            """)

            # Note versions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS note_versions (
                    note_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    change_summary TEXT,
                    changed_by TEXT,
                    PRIMARY KEY (note_id, version),
                    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
                )
            """)

            # Quotes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    id TEXT PRIMARY KEY,
                    entry_key TEXT NOT NULL,
                    text TEXT NOT NULL,
                    page INTEGER,
                    section TEXT,
                    paragraph INTEGER,
                    context TEXT,
                    category TEXT NOT NULL,
                    importance INTEGER NOT NULL CHECK (importance BETWEEN 1 AND 5),
                    tags TEXT,  -- JSON array
                    note TEXT,
                    created_at TEXT NOT NULL,
                    highlighted_at TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_quotes_entry
                ON quotes(entry_key)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_quotes_category
                ON quotes(category)
            """)

            # Reading progress table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reading_progress (
                    entry_key TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    current_page INTEGER NOT NULL DEFAULT 0,
                    total_pages INTEGER,
                    sections_read INTEGER NOT NULL DEFAULT 0,
                    sections_total INTEGER,
                    reading_time_minutes INTEGER NOT NULL DEFAULT 0,
                    session_count INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT,
                    finished_at TEXT,
                    last_read_at TEXT,
                    importance INTEGER NOT NULL DEFAULT 3,
                    difficulty INTEGER NOT NULL DEFAULT 3,
                    enjoyment INTEGER NOT NULL DEFAULT 3,
                    comprehension INTEGER NOT NULL DEFAULT 3
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_progress_status
                ON reading_progress(status)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_progress_priority
                ON reading_progress(priority)
            """)

            # Full-text search table
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                    note_id UNINDEXED,
                    content,
                    title,
                    tags,
                    tokenize='porter unicode61'
                )
            """)

    # Note operations

    def add_note(self, note: Note) -> None:
        """Add a new note to storage.

        Args:
            note: Note to add

        Raises:
            StorageError: If note with same ID exists
        """
        self._get_connection()

        with self._write_lock:
            try:
                with self.transaction() as txn:
                    # Insert note
                    txn.execute(
                        """
                        INSERT INTO notes (
                            id, entry_key, type, title, content, tags,
                            created_at, updated_at, version, content_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            note.id,
                            note.entry_key,
                            note.type.value,
                            note.title,
                            note.content,
                            json.dumps(list(note.tags)),
                            note.created_at.isoformat(),
                            note.updated_at.isoformat(),
                            note.version,
                            note.content_hash,
                        ),
                    )

                    # Insert references
                    for ref in note.references:
                        txn.execute(
                            """
                            INSERT INTO note_references (note_id, reference_id)
                            VALUES (?, ?)
                        """,
                            (note.id, ref),
                        )

                    # Add to FTS index
                    txn.execute(
                        """
                        INSERT INTO notes_fts (note_id, content, title, tags)
                        VALUES (?, ?, ?, ?)
                    """,
                        (
                            note.id,
                            note.content,
                            note.title or "",
                            " ".join(note.tags),
                        ),
                    )

            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    raise StorageError(f"Note with ID {note.id} already exists")
                elif "CHECK constraint failed" in str(e):
                    raise StorageError(
                        f"Content size exceeds maximum of {self.MAX_CONTENT_SIZE} bytes"
                    )
                else:
                    raise StorageError(f"Database integrity error: {e}")

    def get_note(self, note_id: str) -> Note | None:
        """Get note by ID.

        Args:
            note_id: Note ID

        Returns:
            Note or None if not found
        """
        conn = self._get_connection()

        cursor = conn.execute(
            """
            SELECT * FROM notes WHERE id = ?
        """,
            (note_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        # Get references
        ref_cursor = conn.execute(
            """
            SELECT reference_id FROM note_references
            WHERE note_id = ?
        """,
            (note_id,),
        )

        references = [r["reference_id"] for r in ref_cursor]

        return self._row_to_note(row, references)

    def update_note(
        self,
        note: Note,
        change_summary: str | None = None,
        changed_by: str | None = None,
    ) -> None:
        """Update existing note with optimistic locking.

        Args:
            note: Updated note
            change_summary: Optional change summary
            changed_by: Optional user identifier

        Raises:
            OptimisticLockError: If version conflict detected
        """
        self._get_connection()

        with self._write_lock:
            # Get current version for optimistic locking
            current = self.get_note(note.id)
            if not current:
                # Note doesn't exist, silently return
                return

            if current.version != note.version - 1:
                raise OptimisticLockError(
                    note.id,
                    note.version - 1,
                    current.version,
                )

            try:
                with self.transaction() as txn:
                    # Save current version to history
                    txn.execute(
                        """
                        INSERT INTO note_versions (
                            note_id, version, content, content_hash,
                            created_at, change_summary, changed_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            current.id,
                            current.version,
                            current.content,
                            current.content_hash,
                            current.updated_at.isoformat(),
                            change_summary,
                            changed_by,
                        ),
                    )

                    # Update note
                    txn.execute(
                        """
                        UPDATE notes SET
                            type = ?, title = ?, content = ?, tags = ?,
                            updated_at = ?, version = ?, content_hash = ?
                        WHERE id = ?
                    """,
                        (
                            note.type.value,
                            note.title,
                            note.content,
                            json.dumps(list(note.tags)),
                            note.updated_at.isoformat(),
                            note.version,
                            note.content_hash,
                            note.id,
                        ),
                    )

                    # Update references
                    txn.execute(
                        """
                        DELETE FROM note_references WHERE note_id = ?
                    """,
                        (note.id,),
                    )

                    for ref in note.references:
                        txn.execute(
                            """
                            INSERT INTO note_references (note_id, reference_id)
                            VALUES (?, ?)
                        """,
                            (note.id, ref),
                        )

                    # Update FTS index
                    txn.execute(
                        """
                        DELETE FROM notes_fts WHERE note_id = ?
                    """,
                        (note.id,),
                    )

                    txn.execute(
                        """
                        INSERT INTO notes_fts (note_id, content, title, tags)
                        VALUES (?, ?, ?, ?)
                    """,
                        (
                            note.id,
                            note.content,
                            note.title or "",
                            " ".join(note.tags),
                        ),
                    )

                    # Save new version metadata
                    if change_summary or changed_by:
                        txn.execute(
                            """
                            INSERT OR REPLACE INTO note_versions (
                                note_id, version, content, content_hash,
                                created_at, change_summary, changed_by
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                note.id,
                                note.version,
                                note.content,
                                note.content_hash,
                                note.updated_at.isoformat(),
                                change_summary,
                                changed_by,
                            ),
                        )

            except sqlite3.Error as e:
                raise StorageError(f"Failed to update note: {e}")

    def delete_note(self, note_id: str) -> bool:
        """Delete note by ID.

        Args:
            note_id: Note ID

        Returns:
            True if deleted, False if not found
        """
        self._get_connection()

        with self._write_lock:
            with self.transaction() as txn:
                # Delete from FTS first
                txn.execute(
                    """
                    DELETE FROM notes_fts WHERE note_id = ?
                """,
                    (note_id,),
                )

                # Delete note (cascades to references and versions)
                cursor = txn.execute(
                    """
                    DELETE FROM notes WHERE id = ?
                """,
                    (note_id,),
                )

                return cursor.rowcount > 0

    def get_notes_for_entry(self, entry_key: str) -> list[Note]:
        """Get all notes for an entry.

        Args:
            entry_key: Entry key

        Returns:
            List of notes sorted by creation date
        """
        conn = self._get_connection()

        cursor = conn.execute(
            """
            SELECT * FROM notes
            WHERE entry_key = ?
            ORDER BY created_at DESC
        """,
            (entry_key,),
        )

        notes = []
        for row in cursor:
            # Get references for each note
            ref_cursor = conn.execute(
                """
                SELECT reference_id FROM note_references
                WHERE note_id = ?
            """,
                (row["id"],),
            )

            references = [r["reference_id"] for r in ref_cursor]
            notes.append(self._row_to_note(row, references))

        return notes

    def search_notes(
        self,
        query: str,
        type: NoteType | None = None,
        tags: list[str] | None = None,
    ) -> list[Note]:
        """Search notes using full-text search.

        Args:
            query: Search query
            type: Optional note type filter
            tags: Optional tag filter

        Returns:
            List of matching notes ranked by relevance
        """
        conn = self._get_connection()

        # Build FTS query
        fts_query = query.replace('"', '""')  # Escape quotes

        # Search using FTS
        cursor = conn.execute(
            """
            SELECT DISTINCT n.*, rank
            FROM notes n
            JOIN notes_fts f ON n.id = f.note_id
            WHERE notes_fts MATCH ?
            ORDER BY rank
        """,
            (fts_query,),
        )

        notes = []
        for row in cursor:
            # Get references
            ref_cursor = conn.execute(
                """
                SELECT reference_id FROM note_references
                WHERE note_id = ?
            """,
                (row["id"],),
            )

            references = [r["reference_id"] for r in ref_cursor]
            note = self._row_to_note(row, references)

            # Apply filters
            if type and note.type != type:
                continue

            if tags:
                tag_set = set(tags)
                if not tag_set.intersection(note.tags):
                    continue

            notes.append(note)

        return notes

    # Quote operations

    def add_quote(self, quote: Quote) -> None:
        """Add a new quote.

        Args:
            quote: Quote to add
        """
        conn = self._get_connection()

        with self._write_lock:
            try:
                conn.execute(
                    """
                    INSERT INTO quotes (
                        id, entry_key, text, page, section, paragraph,
                        context, category, importance, tags, note,
                        created_at, highlighted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        quote.id,
                        quote.entry_key,
                        quote.text,
                        quote.page,
                        quote.section,
                        quote.paragraph,
                        quote.context,
                        quote.category.value,
                        quote.importance,
                        json.dumps(list(quote.tags)),
                        quote.note,
                        quote.created_at.isoformat(),
                        quote.highlighted_at.isoformat()
                        if quote.highlighted_at
                        else None,
                    ),
                )

            except sqlite3.IntegrityError as e:
                raise StorageError(f"Failed to add quote: {e}")

    def get_quote(self, quote_id: str) -> Quote | None:
        """Get quote by ID.

        Args:
            quote_id: Quote ID

        Returns:
            Quote or None if not found
        """
        conn = self._get_connection()

        cursor = conn.execute(
            """
            SELECT * FROM quotes WHERE id = ?
        """,
            (quote_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return self._row_to_quote(row)

    def delete_quote(self, quote_id: str) -> bool:
        """Delete quote by ID.

        Args:
            quote_id: Quote ID

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()

        with self._write_lock:
            cursor = conn.execute(
                """
                DELETE FROM quotes WHERE id = ?
            """,
                (quote_id,),
            )

            return cursor.rowcount > 0

    def get_quotes_for_entry(self, entry_key: str) -> list[Quote]:
        """Get all quotes for an entry.

        Args:
            entry_key: Entry key

        Returns:
            List of quotes sorted by page number
        """
        conn = self._get_connection()

        cursor = conn.execute(
            """
            SELECT * FROM quotes
            WHERE entry_key = ?
            ORDER BY page, paragraph
        """,
            (entry_key,),
        )

        return [self._row_to_quote(row) for row in cursor]

    def search_quotes(
        self,
        query: str | None = None,
        tags: list[str] | None = None,
        category: QuoteCategory | None = None,
    ) -> list[Quote]:
        """Search quotes.

        Args:
            query: Optional text search query
            tags: Optional tag filter
            category: Optional category filter

        Returns:
            List of matching quotes
        """
        conn = self._get_connection()

        conditions = []
        params = []

        if query:
            conditions.append("text LIKE ?")
            params.append(f"%{query}%")

        if category:
            conditions.append("category = ?")
            params.append(category.value)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor = conn.execute(
            f"SELECT * FROM quotes WHERE {where_clause} ORDER BY created_at DESC",
            params,
        )

        quotes = []
        for row in cursor:
            quote = self._row_to_quote(row)

            # Apply tag filter
            if tags:
                tag_set = set(tags)
                if not tag_set.intersection(quote.tags):
                    continue

            quotes.append(quote)

        return quotes

    # Progress operations

    def add_progress(self, progress: ReadingProgress) -> None:
        """Add or update reading progress.

        Args:
            progress: Reading progress
        """
        conn = self._get_connection()

        with self._write_lock:
            conn.execute(
                """
                INSERT OR REPLACE INTO reading_progress (
                    entry_key, status, priority, current_page, total_pages,
                    sections_read, sections_total, reading_time_minutes,
                    session_count, started_at, finished_at, last_read_at,
                    importance, difficulty, enjoyment, comprehension
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    progress.entry_key,
                    progress.status.value,
                    progress.priority.value,
                    progress.current_page,
                    progress.total_pages,
                    progress.sections_read,
                    progress.sections_total,
                    progress.reading_time_minutes,
                    progress.session_count,
                    progress.started_at.isoformat() if progress.started_at else None,
                    progress.finished_at.isoformat() if progress.finished_at else None,
                    progress.last_read_at.isoformat()
                    if progress.last_read_at
                    else None,
                    progress.importance,
                    progress.difficulty,
                    progress.enjoyment,
                    progress.comprehension,
                ),
            )

    def get_progress(self, entry_key: str) -> ReadingProgress | None:
        """Get reading progress for entry.

        Args:
            entry_key: Entry key

        Returns:
            Reading progress or None if not found
        """
        conn = self._get_connection()

        cursor = conn.execute(
            """
            SELECT * FROM reading_progress WHERE entry_key = ?
        """,
            (entry_key,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return self._row_to_progress(row)

    def update_progress(self, progress: ReadingProgress) -> None:
        """Update reading progress.

        Args:
            progress: Updated reading progress
        """
        self.add_progress(progress)  # INSERT OR REPLACE

    def delete_progress(self, entry_key: str) -> bool:
        """Delete reading progress.

        Args:
            entry_key: Entry key

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()

        with self._write_lock:
            cursor = conn.execute(
                """
                DELETE FROM reading_progress WHERE entry_key = ?
            """,
                (entry_key,),
            )

            return cursor.rowcount > 0

    def get_reading_list(
        self,
        status: str | None = None,
        min_priority: int | None = None,
    ) -> list[ReadingProgress]:
        """Get reading list with filters.

        Args:
            status: Optional status filter
            min_priority: Optional minimum priority

        Returns:
            List of reading progress entries
        """
        conn = self._get_connection()

        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)

        if min_priority:
            conditions.append("priority >= ?")
            params.append(min_priority)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        cursor = conn.execute(
            f"SELECT * FROM reading_progress{where_clause} "
            f"ORDER BY priority DESC, entry_key",
            params,
        )

        return [self._row_to_progress(row) for row in cursor]

    # Version operations

    def get_note_versions(self, note_id: str) -> list[NoteVersion]:
        """Get all versions of a note.

        Args:
            note_id: Note ID

        Returns:
            List of versions in chronological order
        """
        conn = self._get_connection()

        # Get historical versions
        cursor = conn.execute(
            """
            SELECT * FROM note_versions
            WHERE note_id = ?
            ORDER BY version
        """,
            (note_id,),
        )

        versions = []
        for row in cursor:
            versions.append(
                NoteVersion(
                    note_id=row["note_id"],
                    version=row["version"],
                    content=row["content"],
                    content_hash=row["content_hash"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    change_summary=row["change_summary"],
                    changed_by=row["changed_by"],
                )
            )

        # Add current version if exists and not already in history
        current = self.get_note(note_id)
        if current:
            # Check if current version is already in history with metadata
            if not versions or versions[-1].version != current.version:
                versions.append(
                    NoteVersion(
                        note_id=current.id,
                        version=current.version,
                        content=current.content,
                        content_hash=current.content_hash,
                        created_at=current.updated_at,
                        change_summary=None,
                        changed_by=None,
                    )
                )

        return versions

    def get_note_at_version(self, note_id: str, version: int) -> Note | None:
        """Get specific version of a note.

        Args:
            note_id: Note ID
            version: Version number

        Returns:
            Note at that version or None if not found
        """
        conn = self._get_connection()

        # Check if it's the current version
        current = self.get_note(note_id)
        if current and current.version == version:
            return current

        # Get from history
        cursor = conn.execute(
            """
            SELECT * FROM note_versions
            WHERE note_id = ? AND version = ?
        """,
            (note_id, version),
        )

        row = cursor.fetchone()
        if not row:
            return None

        # Need base note info
        if not current:
            return None

        # Create note with historical content
        return Note(
            id=note_id,
            entry_key=current.entry_key,
            content=row["content"],
            type=current.type,
            title=current.title,
            tags=list(current.tags),
            references=list(current.references),
            created_at=current.created_at,
            updated_at=datetime.fromisoformat(row["created_at"]),
            version=row["version"],
        )

    # Batch operations

    def batch_add_notes(self, notes: list[Note]) -> None:
        """Add multiple notes in a single transaction.

        Args:
            notes: List of notes to add

        Raises:
            StorageError: If any note fails to add
        """
        with self._write_lock:
            with self.transaction() as txn:
                for note in notes:
                    # Add each note
                    txn.execute(
                        """
                        INSERT INTO notes (
                            id, entry_key, type, title, content, tags,
                            created_at, updated_at, version, content_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            note.id,
                            note.entry_key,
                            note.type.value,
                            note.title,
                            note.content,
                            json.dumps(list(note.tags)),
                            note.created_at.isoformat(),
                            note.updated_at.isoformat(),
                            note.version,
                            note.content_hash,
                        ),
                    )

                    # Add references
                    for ref in note.references:
                        txn.execute(
                            """
                            INSERT INTO note_references (note_id, reference_id)
                            VALUES (?, ?)
                        """,
                            (note.id, ref),
                        )

                    # Add to FTS
                    txn.execute(
                        """
                        INSERT INTO notes_fts (note_id, content, title, tags)
                        VALUES (?, ?, ?, ?)
                    """,
                        (
                            note.id,
                            note.content,
                            note.title or "",
                            " ".join(note.tags),
                        ),
                    )

    def batch_update_notes(self, notes: list[Note]) -> None:
        """Update multiple notes in a single transaction.

        Args:
            notes: List of notes to update
        """
        with self._write_lock:
            with self.transaction() as txn:
                for note in notes:
                    # Get current for version history
                    cursor = txn.execute(
                        """
                        SELECT * FROM notes WHERE id = ?
                    """,
                        (note.id,),
                    )

                    current_row = cursor.fetchone()
                    if not current_row:
                        continue

                    # Save to history
                    txn.execute(
                        """
                        INSERT INTO note_versions (
                            note_id, version, content, content_hash,
                            created_at, change_summary, changed_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            note.id,
                            current_row["version"],
                            current_row["content"],
                            current_row["content_hash"],
                            current_row["updated_at"],
                            "Batch update",
                            None,
                        ),
                    )

                    # Update note
                    txn.execute(
                        """
                        UPDATE notes SET
                            type = ?, title = ?, content = ?, tags = ?,
                            updated_at = ?, version = ?, content_hash = ?
                        WHERE id = ?
                    """,
                        (
                            note.type.value,
                            note.title,
                            note.content,
                            json.dumps(list(note.tags)),
                            note.updated_at.isoformat(),
                            note.version,
                            note.content_hash,
                            note.id,
                        ),
                    )

                    # Update FTS
                    txn.execute(
                        """
                        DELETE FROM notes_fts WHERE note_id = ?
                    """,
                        (note.id,),
                    )

                    txn.execute(
                        """
                        INSERT INTO notes_fts (note_id, content, title, tags)
                        VALUES (?, ?, ?, ?)
                    """,
                        (
                            note.id,
                            note.content,
                            note.title or "",
                            " ".join(note.tags),
                        ),
                    )

    def batch_delete_notes(self, note_ids: list[str]) -> int:
        """Delete multiple notes in a single transaction.

        Args:
            note_ids: List of note IDs to delete

        Returns:
            Number of notes deleted
        """
        with self._write_lock:
            with self.transaction() as txn:
                count = 0
                for note_id in note_ids:
                    # Delete from FTS
                    txn.execute(
                        """
                        DELETE FROM notes_fts WHERE note_id = ?
                    """,
                        (note_id,),
                    )

                    # Delete note
                    cursor = txn.execute(
                        """
                        DELETE FROM notes WHERE id = ?
                    """,
                        (note_id,),
                    )

                    count += cursor.rowcount

                return count

    # Statistics

    def get_statistics(self) -> dict[str, int]:
        """Get storage statistics.

        Returns:
            Dictionary of statistics
        """
        conn = self._get_connection()

        stats = {}

        # Count notes
        cursor = conn.execute("SELECT COUNT(*) FROM notes")
        stats["total_notes"] = cursor.fetchone()[0]

        # Count entries with notes
        cursor = conn.execute("SELECT COUNT(DISTINCT entry_key) FROM notes")
        stats["entries_with_notes"] = cursor.fetchone()[0]

        # Count quotes
        cursor = conn.execute("SELECT COUNT(*) FROM quotes")
        stats["total_quotes"] = cursor.fetchone()[0]

        # Count reading progress
        cursor = conn.execute("""
            SELECT status, COUNT(*) FROM reading_progress
            GROUP BY status
        """)

        stats["entries_in_progress"] = 0
        stats["entries_completed"] = 0

        for row in cursor:
            if row["status"] == ReadingStatus.READING.value:
                stats["entries_in_progress"] = row[1]
            elif row["status"] == ReadingStatus.READ.value:
                stats["entries_completed"] = row[1]

        return stats

    # Helper methods

    def _row_to_note(self, row: sqlite3.Row, references: list[str]) -> Note:
        """Convert database row to Note object."""
        return Note(
            id=row["id"],
            entry_key=row["entry_key"],
            content=row["content"],
            type=NoteType(row["type"]),
            title=row["title"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            references=references,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            version=row["version"],
        )

    def _row_to_quote(self, row: sqlite3.Row) -> Quote:
        """Convert database row to Quote object."""
        return Quote(
            id=row["id"],
            entry_key=row["entry_key"],
            text=row["text"],
            page=row["page"],
            section=row["section"],
            paragraph=row["paragraph"],
            context=row["context"],
            category=QuoteCategory(row["category"]),
            importance=row["importance"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            note=row["note"],
            created_at=datetime.fromisoformat(row["created_at"]),
            highlighted_at=datetime.fromisoformat(row["highlighted_at"])
            if row["highlighted_at"]
            else None,
        )

    def _row_to_progress(self, row: sqlite3.Row) -> ReadingProgress:
        """Convert database row to ReadingProgress object."""
        return ReadingProgress(
            entry_key=row["entry_key"],
            status=ReadingStatus(row["status"]),
            priority=Priority(row["priority"]),
            current_page=row["current_page"],
            total_pages=row["total_pages"],
            sections_read=row["sections_read"],
            sections_total=row["sections_total"],
            reading_time_minutes=row["reading_time_minutes"],
            session_count=row["session_count"],
            started_at=datetime.fromisoformat(row["started_at"])
            if row["started_at"]
            else None,
            finished_at=datetime.fromisoformat(row["finished_at"])
            if row["finished_at"]
            else None,
            last_read_at=datetime.fromisoformat(row["last_read_at"])
            if row["last_read_at"]
            else None,
            importance=row["importance"],
            difficulty=row["difficulty"],
            enjoyment=row["enjoyment"],
            comprehension=row["comprehension"],
        )

    def create_note(self, **kwargs) -> Note:
        """Helper to create a Note instance for testing."""
        return Note(**kwargs)
