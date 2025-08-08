"""Storage backend with atomic operations, caching, and performance optimizations.

Features:
- Atomic transactions with rollback
- Thread-safe concurrent access
- Bulk operations for performance
- LRU caching for frequently accessed entries
- Data integrity with checksums
- Incremental backups
- Search functionality
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import threading
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import msgspec

from bibmgr.core.models import Collection, Entry, Tag


class StorageError(Exception):
    """Base exception for storage errors."""

    pass


class TransactionError(StorageError):
    """Transaction-related errors."""

    pass


class IntegrityError(StorageError):
    """Data integrity errors."""

    pass


class LRUCache:
    """Simple LRU cache implementation."""

    def __init__(self, max_size: int = 1000):
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
        self.lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                self.hits += 1
                return self.cache[key]
            self.misses += 1
            return None

    def put(self, key: str, value: Any) -> None:
        with self.lock:
            if key in self.cache:
                # Update and move to end
                self.cache.move_to_end(key)
            else:
                # Add new entry
                if len(self.cache) >= self.max_size:
                    # Remove least recently used
                    self.cache.popitem(last=False)
            self.cache[key] = value

    def invalidate(self, key: str) -> None:
        with self.lock:
            self.cache.pop(key, None)

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()

    def stats(self) -> dict[str, int | float]:
        with self.lock:
            total = self.hits + self.misses
            hit_rate = self.hits / total if total > 0 else 0
            return {
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "size": len(self.cache),
            }


class Transaction:
    """Transaction for atomic operations."""

    def __init__(self, storage: FileSystemStorage):
        self.storage = storage
        self.operations: list[tuple[str, Any]] = []
        self.locks: set[str] = set()
        self.committed = False
        self.rolled_back = False
        self._backup_path: Path | None = None

    def add(self, entry: Entry) -> None:
        """Add entry in transaction."""
        if self.committed or self.rolled_back:
            raise TransactionError("Transaction already completed")

        self.operations.append(("add", entry))
        self.locks.add(entry.key)

    def update(self, entry: Entry) -> None:
        """Update entry in transaction."""
        if self.committed or self.rolled_back:
            raise TransactionError("Transaction already completed")

        self.operations.append(("update", entry))
        self.locks.add(entry.key)

    def delete(self, key: str) -> None:
        """Delete entry in transaction."""
        if self.committed or self.rolled_back:
            raise TransactionError("Transaction already completed")

        self.operations.append(("delete", key))
        self.locks.add(key)

    def commit(self) -> None:
        """Commit transaction atomically."""
        if self.committed or self.rolled_back:
            raise TransactionError("Transaction already completed")

        # Create backup for rollback
        self._backup_path = self.storage._create_backup()

        try:
            # Acquire all locks in sorted order to prevent deadlock
            acquired_locks = []
            for key in sorted(self.locks):
                if self.storage._acquire_lock(key, timeout=5.0):
                    acquired_locks.append(key)
                else:
                    # Release acquired locks and fail
                    for lock_key in acquired_locks:
                        self.storage._release_lock(lock_key)
                    raise TransactionError(f"Failed to acquire lock for {key}")

            try:
                # Apply operations
                for op_type, data in self.operations:
                    if op_type == "add":
                        self.storage._write_entry(data, skip_lock=True)
                    elif op_type == "update":
                        if not self.storage._entry_exists(data.key):
                            raise IntegrityError(
                                f"Cannot update non-existent entry: {data.key}"
                            )
                        self.storage._write_entry(data, skip_lock=True)
                    elif op_type == "delete":
                        self.storage._delete_entry(data, skip_lock=True)

                # Update index
                self.storage._save_index()
                self.committed = True

            finally:
                # Release locks
                for key in acquired_locks:
                    self.storage._release_lock(key)

        except Exception as e:
            # Restore from backup
            if self._backup_path and self._backup_path.exists():
                self.storage._restore_from_backup(self._backup_path)
            raise TransactionError(f"Transaction failed: {e}") from e

        finally:
            # Clean up backup on success
            if self.committed and self._backup_path and self._backup_path.exists():
                shutil.rmtree(self._backup_path)

    def rollback(self) -> None:
        """Rollback transaction."""
        if self.committed or self.rolled_back:
            raise TransactionError("Transaction already completed")

        self.operations.clear()
        self.locks.clear()
        self.rolled_back = True


class FileSystemStorage:
    """File system storage with caching and concurrent access support.

    Directory structure:
    data_dir/
        entries/
            {key}.msgpack    # Binary entry files for performance
        collections/
            {id}.json        # Collection definitions
        tags/
            index.json       # Tag index
        index.json           # Main entry index
        checksum.json        # Checksums for integrity
        lock/                # Lock files for concurrent access
    """

    def __init__(self, data_dir: Path, cache_size: int = 1000):
        self.data_dir = Path(data_dir)
        self.entries_dir = self.data_dir / "entries"
        self.collections_dir = self.data_dir / "collections"
        self.tags_dir = self.data_dir / "tags"
        self.lock_dir = self.data_dir / "lock"

        # Create directory structure
        self.entries_dir.mkdir(parents=True, exist_ok=True)
        self.collections_dir.mkdir(parents=True, exist_ok=True)
        self.tags_dir.mkdir(parents=True, exist_ok=True)
        self.lock_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.index_path = self.data_dir / "index.json"
        self.checksum_path = self.data_dir / "checksum.json"
        self.index: dict[str, dict] = self._load_index()
        self.checksums: dict[str, str] = self._load_checksums()

        # Cache for performance
        self.cache = LRUCache(cache_size)

        # Locks for concurrent access
        self._locks: dict[str, threading.RLock] = {}
        self._lock_mutex = threading.RLock()

        # Msgspec encoder/decoder
        self.encoder = msgspec.msgpack.Encoder()
        self.decoder = msgspec.msgpack.Decoder(Entry)

    def _load_index(self) -> dict[str, dict]:
        """Load entry index."""
        if self.index_path.exists():
            try:
                with open(self.index_path) as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                return {}
        return {}

    def _save_index(self) -> None:
        """Save entry index atomically."""
        with self._lock_mutex:
            temp_path = self.index_path.with_suffix(".tmp")
            try:
                with open(temp_path, "w") as f:
                    json.dump(self.index, f, indent=2, sort_keys=True)
                temp_path.replace(self.index_path)
            except OSError as e:
                if temp_path.exists():
                    temp_path.unlink()
                raise StorageError(f"Failed to save index: {e}") from e

    def _load_checksums(self) -> dict[str, str]:
        """Load file checksums."""
        if self.checksum_path.exists():
            try:
                with open(self.checksum_path) as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                return {}
        return {}

    def _save_checksums(self) -> None:
        """Save file checksums."""
        with self._lock_mutex:
            temp_path = self.checksum_path.with_suffix(".tmp")
            try:
                with open(temp_path, "w") as f:
                    json.dump(self.checksums, f, indent=2, sort_keys=True)
                temp_path.replace(self.checksum_path)
            except OSError as e:
                if temp_path.exists():
                    temp_path.unlink()
                raise StorageError(f"Failed to save checksums: {e}") from e

    def _calculate_checksum(self, data: bytes) -> str:
        """Calculate SHA256 checksum."""
        return hashlib.sha256(data).hexdigest()

    def _entry_path(self, key: str) -> Path:
        """Get path for entry file."""
        # Sanitize key for filesystem
        safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        return self.entries_dir / f"{safe_key}.msgpack"

    def _entry_exists(self, key: str) -> bool:
        """Check if entry file exists."""
        return self._entry_path(key).exists()

    def _acquire_lock(self, key: str, timeout: float = 5.0) -> bool:
        """Acquire lock for entry."""
        with self._lock_mutex:
            if key not in self._locks:
                self._locks[key] = threading.RLock()
            lock = self._locks[key]

        return lock.acquire(timeout=timeout)

    def _release_lock(self, key: str) -> None:
        """Release lock for entry."""
        with self._lock_mutex:
            if key in self._locks:
                try:
                    self._locks[key].release()
                except RuntimeError:
                    pass  # Not acquired by this thread

    def _write_entry(self, entry: Entry, skip_lock: bool = False) -> None:
        """Write entry to disk with integrity checks."""
        if entry is None:
            raise StorageError("Entry cannot be None")
        if not skip_lock and not self._acquire_lock(entry.key):
            raise StorageError(f"Failed to acquire lock for {entry.key}")

        try:
            path = self._entry_path(entry.key)
            data = self.encoder.encode(entry)
            checksum = self._calculate_checksum(data)

            # Write atomically
            temp_path = path.with_suffix(".tmp")
            try:
                with open(temp_path, "wb") as f:
                    f.write(data)
                temp_path.replace(path)
            except OSError as e:
                raise StorageError(f"Failed to write entry {entry.key}: {e}") from e

            # Update index with lock
            with self._lock_mutex:
                self.index[entry.key] = {
                    "type": entry.type.value,
                    "title": entry.title,
                    "year": entry.year,
                    "authors": entry.author.split(" and ") if entry.author else [],
                    "modified": datetime.now().isoformat(),
                    "checksum": checksum,
                }

                # Update checksum
                self.checksums[entry.key] = checksum

            # Update cache
            self.cache.put(entry.key, entry)

        finally:
            if not skip_lock:
                self._release_lock(entry.key)

    def _delete_entry(self, key: str, skip_lock: bool = False) -> bool:
        """Delete entry from disk."""
        if not skip_lock and not self._acquire_lock(key):
            raise StorageError(f"Failed to acquire lock for {key}")

        try:
            path = self._entry_path(key)
            if path.exists():
                try:
                    path.unlink()
                except OSError as e:
                    raise StorageError(f"Failed to delete entry {key}: {e}") from e

                with self._lock_mutex:
                    self.index.pop(key, None)
                    self.checksums.pop(key, None)
                self.cache.invalidate(key)
                return True
            return False

        finally:
            if not skip_lock:
                self._release_lock(key)

    def _create_backup(self) -> Path | None:
        """Create backup of data directory."""
        if not self.data_dir.exists():
            return None

        try:
            backup_dir = Path(tempfile.mkdtemp(prefix="bibmgr_backup_"))
            backup_path = backup_dir / "backup"
            shutil.copytree(self.data_dir, backup_path)
            return backup_path
        except OSError as e:
            raise StorageError(f"Failed to create backup: {e}") from e

    def _restore_from_backup(self, backup_path: Path) -> None:
        """Restore from backup."""
        if not backup_path.exists():
            raise StorageError(f"Backup path does not exist: {backup_path}")

        try:
            # Clear current data
            if self.data_dir.exists():
                shutil.rmtree(self.data_dir)

            # Restore from backup
            shutil.copytree(backup_path, self.data_dir)

            # Reload index and checksums
            self.index = self._load_index()
            self.checksums = self._load_checksums()

            # Clear cache
            self.cache.clear()

        except OSError as e:
            raise StorageError(f"Failed to restore from backup: {e}") from e

    # Public API

    def read(self, key: str) -> Entry | None:
        """Read single entry."""
        # Check cache first
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        path = self._entry_path(key)
        if not path.exists():
            return None

        try:
            with open(path, "rb") as f:
                data = f.read()

            # Verify checksum
            if key in self.checksums:
                expected = self.checksums[key]
                actual = self._calculate_checksum(data)
                if expected != actual:
                    raise IntegrityError(f"Checksum mismatch for {key}")

            entry = self.decoder.decode(data)

            # Update cache
            self.cache.put(key, entry)

            return entry

        except (OSError, msgspec.DecodeError) as e:
            raise StorageError(f"Failed to read entry {key}: {e}") from e

    def read_all(self) -> list[Entry]:
        """Read all entries."""
        entries = []
        for key in self.index:
            entry = self.read(key)
            if entry:
                entries.append(entry)
        return entries

    def read_batch(self, keys: list[str]) -> dict[str, Entry | None]:
        """Read multiple entries efficiently."""
        results = {}
        for key in keys:
            results[key] = self.read(key)
        return results

    def write(self, entry: Entry) -> None:
        """Write single entry."""
        self._write_entry(entry)
        self._save_index()
        self._save_checksums()

    def write_batch(self, entries: list[Entry]) -> None:
        """Write multiple entries efficiently."""
        for entry in entries:
            self._write_entry(entry)
        self._save_index()
        self._save_checksums()

    def update(self, entry: Entry) -> bool:
        """Update existing entry."""
        if not self.exists(entry.key):
            return False
        self.write(entry)
        return True

    def update_batch(self, entries: list[Entry]) -> dict[str, bool]:
        """Update multiple entries efficiently."""
        results = {}
        for entry in entries:
            if self.exists(entry.key):
                self._write_entry(entry)
                results[entry.key] = True
            else:
                results[entry.key] = False

        self._save_index()
        self._save_checksums()
        return results

    def delete(self, key: str) -> bool:
        """Delete single entry."""
        result = self._delete_entry(key)
        if result:
            self._save_index()
            self._save_checksums()
        return result

    def delete_batch(self, keys: list[str]) -> dict[str, bool]:
        """Delete multiple entries efficiently."""
        results = {}
        for key in keys:
            results[key] = self._delete_entry(key)

        self._save_index()
        self._save_checksums()
        return results

    def exists(self, key: str) -> bool:
        """Check if entry exists."""
        return key in self.index

    def count(self) -> int:
        """Get total number of entries."""
        return len(self.index)

    def keys(self) -> list[str]:
        """Get all entry keys."""
        return list(self.index.keys())

    def clear(self) -> None:
        """Remove all entries."""
        for key in list(self.index.keys()):
            self._delete_entry(key)

        self.index.clear()
        self.checksums.clear()
        self.cache.clear()

        self._save_index()
        self._save_checksums()

    @contextmanager
    def transaction(self) -> Iterator[Transaction]:
        """Start a transaction."""
        txn = Transaction(self)
        try:
            yield txn
            # Auto-commit if no exception
            if not txn.committed and not txn.rolled_back:
                txn.commit()
        except Exception:
            # Auto-rollback on exception
            if not txn.committed and not txn.rolled_back:
                txn.rollback()
            raise

    def get_checksum(self) -> str:
        """Get overall data checksum."""
        # Calculate from index for efficiency, excluding timestamps
        clean_index = {}
        for key, info in self.index.items():
            clean_info = {k: v for k, v in info.items() if k != "modified"}
            clean_index[key] = clean_info
        index_str = json.dumps(clean_index, sort_keys=True)
        return hashlib.sha256(index_str.encode()).hexdigest()

    def validate(self) -> tuple[bool, list[str]]:
        """Validate data integrity."""
        errors = []

        # Check each entry
        for key in self.index:
            path = self._entry_path(key)

            # Check file exists
            if not path.exists():
                errors.append(f"Missing file for entry: {key}")
                continue

            # Check checksum
            if key in self.checksums:
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    actual = self._calculate_checksum(data)
                    expected = self.checksums[key]

                    if actual != expected:
                        errors.append(f"Checksum mismatch for entry: {key}")

                except OSError as e:
                    errors.append(f"Cannot read entry {key}: {e}")
            else:
                errors.append(f"Missing checksum for entry: {key}")

        # Check for orphaned files
        for path in self.entries_dir.glob("*.msgpack"):
            key = path.stem
            # Reverse the sanitization (approximate)
            if key not in self.index:
                errors.append(f"Orphaned file: {path.name}")

        return len(errors) == 0, errors

    def optimize(self) -> None:
        """Optimize storage for performance."""
        # Rebuild index from files
        new_index = {}
        new_checksums = {}

        for path in self.entries_dir.glob("*.msgpack"):
            try:
                with open(path, "rb") as f:
                    data = f.read()

                entry = self.decoder.decode(data)
                checksum = self._calculate_checksum(data)

                new_index[entry.key] = {
                    "type": entry.type.value,
                    "title": entry.title,
                    "year": entry.year,
                    "authors": entry.author.split(" and ") if entry.author else [],
                    "modified": datetime.now().isoformat(),
                    "checksum": checksum,
                }
                new_checksums[entry.key] = checksum

            except Exception:
                pass  # Skip corrupted entries

        self.index = new_index
        self.checksums = new_checksums
        self._save_index()
        self._save_checksums()

        # Clear cache to force reload
        self.cache.clear()

    def backup(self, path: Path) -> None:
        """Create backup at specified path."""
        if path.exists():
            shutil.rmtree(path)

        try:
            shutil.copytree(self.data_dir, path)
        except OSError as e:
            raise StorageError(f"Failed to create backup: {e}") from e

    def restore(self, path: Path) -> None:
        """Restore from backup."""
        if not path.exists():
            raise StorageError(f"Backup path does not exist: {path}")

        self._restore_from_backup(path)

    @contextmanager
    def lock(self, key: str, timeout: float = 5.0) -> Iterator[None]:
        """Acquire lock for entry."""
        if not self._acquire_lock(key, timeout):
            raise StorageError(f"Failed to acquire lock for {key}")
        try:
            yield
        finally:
            self._release_lock(key)

    def search(self, query: dict[str, Any]) -> list[Entry]:
        """Search entries by criteria."""
        results = []

        for key, info in self.index.items():
            # Simple field matching
            match = True

            for field, value in query.items():
                if field == "type":
                    if info.get("type") != value:
                        match = False
                        break
                elif field == "year":
                    if isinstance(value, dict):
                        # Range query
                        year = info.get("year")
                        if year is None:
                            match = False
                            break
                        if "$gte" in value and year < value["$gte"]:
                            match = False
                            break
                        if "$lte" in value and year > value["$lte"]:
                            match = False
                            break
                    elif info.get("year") != value:
                        match = False
                        break
                elif field == "title":
                    if isinstance(value, dict) and "$regex" in value:
                        # Regex search
                        import re

                        pattern = value["$regex"]
                        if not re.search(pattern, info.get("title", ""), re.IGNORECASE):
                            match = False
                            break
                    elif value not in info.get("title", ""):
                        match = False
                        break
                elif field == "author":
                    # Search in authors list
                    authors_str = " ".join(info.get("authors", []))
                    if isinstance(value, dict) and "$regex" in value:
                        import re

                        pattern = value["$regex"]
                        if not re.search(pattern, authors_str, re.IGNORECASE):
                            match = False
                            break
                    elif isinstance(value, str) and value not in authors_str:
                        match = False
                        break
                elif field == "journal" and value:
                    # Load entry to check journal field
                    entry = self.read(key)
                    if not entry or not entry.journal or value not in entry.journal:
                        match = False
                        break
                elif field == "$and":
                    # Handle $and operator
                    for sub_query in value:
                        sub_match = True
                        for sub_field, sub_value in sub_query.items():
                            if sub_field == "year" and isinstance(sub_value, dict):
                                year = info.get("year")
                                if "$gte" in sub_value and (
                                    not year or year < sub_value["$gte"]
                                ):
                                    sub_match = False
                                    break
                            elif (
                                sub_field == "author"
                                and isinstance(sub_value, dict)
                                and "$regex" in sub_value
                            ):
                                import re

                                authors_str = " ".join(info.get("authors", []))
                                if not re.search(
                                    sub_value["$regex"], authors_str, re.IGNORECASE
                                ):
                                    sub_match = False
                                    break
                        if not sub_match:
                            match = False
                            break

            if match:
                entry = self.read(key)
                if entry:
                    results.append(entry)

        return results

    def iterate(self) -> Iterator[Entry]:
        """Iterate over entries lazily."""
        for key in self.index:
            entry = self.read(key)
            if entry:
                yield entry

    # Collection management

    def save_collection(self, collection: Collection) -> None:
        """Save collection definition."""
        path = self.collections_dir / f"{collection.id}.json"

        try:
            # Convert to dict
            data = asdict(collection)

            # Atomic write
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(path)

        except OSError as e:
            raise StorageError(f"Failed to save collection: {e}") from e

    def load_collection(self, collection_id: str) -> Collection | None:
        """Load collection by ID."""
        path = self.collections_dir / f"{collection_id}.json"
        if not path.exists():
            return None

        try:
            with open(path) as f:
                data = json.load(f)
            return Collection(**data)
        except (OSError, json.JSONDecodeError, TypeError):
            return None

    def list_collections(self) -> list[Collection]:
        """List all collections."""
        collections = []
        for path in self.collections_dir.glob("*.json"):
            collection = self.load_collection(path.stem)
            if collection:
                collections.append(collection)
        return collections

    def delete_collection(self, collection_id: str) -> bool:
        """Delete collection."""
        path = self.collections_dir / f"{collection_id}.json"
        if path.exists():
            try:
                path.unlink()
                return True
            except OSError:
                return False
        return False

    # Tag management

    def save_tags(self, tags: list[Tag]) -> None:
        """Save tag index."""
        path = self.tags_dir / "index.json"

        try:
            # Convert to list of dicts
            data = [asdict(tag) for tag in tags]

            # Atomic write
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(path)

        except OSError as e:
            raise StorageError(f"Failed to save tags: {e}") from e

    def load_tags(self) -> list[Tag]:
        """Load all tags."""
        path = self.tags_dir / "index.json"
        if not path.exists():
            return []

        try:
            with open(path) as f:
                data = json.load(f)
            return [Tag(**item) for item in data]
        except (OSError, json.JSONDecodeError, TypeError):
            return []
