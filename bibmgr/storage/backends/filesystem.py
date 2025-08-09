"""File system storage backend."""

import fcntl
import json
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from .base import CachedBackend


class FileSystemBackend(CachedBackend):
    """Simple file-based storage using JSON files."""

    def __init__(self, data_dir: Path, cache_size: int = 1000):
        super().__init__(cache_size)
        self.data_dir = Path(data_dir)
        self.entries_dir = self.data_dir / "entries"
        self.index_file = self.data_dir / "index.json"
        self._index: dict[str, str] = {}
        self._index_lock = threading.RLock()  # Allow re-entrant locking
        self.initialize()

    def initialize(self) -> None:
        """Create directory structure and load index."""
        self.entries_dir.mkdir(parents=True, exist_ok=True)
        self._load_index()
        if not self.index_file.exists():
            self._save_index()

    def _load_index(self) -> None:
        """Load the index mapping keys to filenames."""
        if self.index_file.exists():
            try:
                with open(self.index_file) as f:
                    self._index = json.load(f)
            except (OSError, json.JSONDecodeError):
                self._index = {}

    def _save_index(self) -> None:
        """Save the index atomically."""
        temp_fd, temp_path = tempfile.mkstemp(dir=self.data_dir, suffix=".tmp")
        try:
            with open(temp_fd, "w") as f:
                json.dump(self._index, f, indent=2, sort_keys=True)

            Path(temp_path).rename(self.index_file)
        except Exception:
            Path(temp_path).unlink(missing_ok=True)
            raise

    def _key_to_filename(self, key: str) -> str:
        """Convert key to safe filename."""
        safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        return f"{safe_key}.json"

    def _get_path(self, key: str) -> Path:
        """Get file path for key."""
        with self._index_lock:
            if key not in self._index:
                self._index[key] = self._key_to_filename(key)
            return self.entries_dir / self._index[key]

    def _read_impl(self, key: str) -> dict[str, Any] | None:
        """Read data from file."""
        with self._index_lock:
            if key not in self._index:
                return None

        path = self._get_path(key)
        if not path.exists():
            return None

        try:
            with open(path) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (OSError, json.JSONDecodeError):
            return None

    def _write_impl(self, key: str, data: dict[str, Any]) -> None:
        """Write data to file atomically."""
        path = self._get_path(key)

        temp_fd, temp_path = tempfile.mkstemp(dir=self.entries_dir, suffix=".tmp")
        try:
            with open(temp_fd, "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)

            Path(temp_path).rename(path)

            with self._index_lock:
                self._index[key] = path.name
                self._save_index()

        except Exception:
            Path(temp_path).unlink(missing_ok=True)
            raise

    def _delete_impl(self, key: str) -> bool:
        """Delete file."""
        with self._index_lock:
            if key not in self._index:
                return False

            path = self._get_path(key)
            try:
                path.unlink()
                del self._index[key]
                self._save_index()
                return True
            except OSError:
                return False

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        with self._index_lock:
            return key in self._index and self._get_path(key).exists()

    def keys(self) -> list[str]:
        """Get all keys."""
        valid_keys = []
        with self._index_lock:
            index_keys = list(self._index.keys())

        for key in index_keys:
            if self._get_path(key).exists():
                valid_keys.append(key)
        return valid_keys

    def clear(self) -> None:
        """Remove all entries."""
        for path in self.entries_dir.glob("*.json"):
            try:
                path.unlink()
            except OSError:
                pass

        with self._index_lock:
            self._index.clear()
            self._save_index()

        self._read_cache.cache_clear()

    def close(self) -> None:
        """No resources to close for filesystem backend."""
        pass

    def backup(self, backup_dir: Path) -> None:
        """Create a backup of the storage."""
        backup_dir.mkdir(parents=True, exist_ok=True)

        if self.data_dir.exists():
            shutil.copytree(self.data_dir, backup_dir / "data", dirs_exist_ok=True)

    def restore(self, backup_dir: Path) -> None:
        """Restore from backup."""
        backup_data = backup_dir / "data"
        if not backup_data.exists():
            raise ValueError(f"Backup data not found: {backup_data}")

        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)

        shutil.copytree(backup_data, self.data_dir)

        self._load_index()
        self._read_cache.cache_clear()
