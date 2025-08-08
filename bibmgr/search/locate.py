"""File location functionality for bibliography entries.

This module provides Unix locate-style file finding capabilities
for bibliography PDF files and attachments.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import Entry


@dataclass
class FileMatch:
    """A single file match from location search."""

    entry_key: str
    file_path: Path
    exists: bool
    size_bytes: int | None = None

    @property
    def basename(self) -> str:
        """Get the file basename."""
        return self.file_path.name

    @property
    def extension(self) -> str:
        """Get the file extension."""
        return self.file_path.suffix


@dataclass
class LocateResult:
    """Result of a file location search."""

    query: str
    matches: list[FileMatch]
    total_found: int
    missing_count: int

    @property
    def existing_files(self) -> list[FileMatch]:
        """Get only existing file matches."""
        return [m for m in self.matches if m.exists]

    @property
    def missing_files(self) -> list[FileMatch]:
        """Get only missing file matches."""
        return [m for m in self.matches if not m.exists]


@dataclass
class FileStatistics:
    """Statistics about files in the bibliography."""

    total_entries: int = 0
    entries_with_files: int = 0
    total_files: int = 0
    existing_files: int = 0
    missing_files: int = 0
    total_size_bytes: int = 0
    file_types: dict[str, int] = field(default_factory=dict)

    @property
    def average_size_bytes(self) -> float:
        """Calculate average file size."""
        if self.existing_files == 0:
            return 0.0
        return self.total_size_bytes / self.existing_files

    @property
    def missing_rate(self) -> float:
        """Calculate percentage of missing files."""
        if self.total_files == 0:
            return 0.0
        return (self.missing_files / self.total_files) * 100


class FileLocator:
    """Locate files associated with bibliography entries."""

    def __init__(self, base_paths: list[Path] | None = None):
        """Initialize file locator with search paths.

        Args:
            base_paths: List of base directories to search (default: common paths)
        """
        if base_paths is None:
            # Default search paths
            base_paths = [
                Path.home() / "documents",
                Path.home() / "Documents",
                Path.home() / "papers",
                Path.home() / "Papers",
                Path.home() / "bibliography",
                Path("/home/b/documents"),  # User's specific path
            ]

        # Filter to only existing paths
        self.base_paths = [p for p in base_paths if p.exists()]

        # Cache for file existence checks
        self._file_cache: dict[Path, bool] = {}

    def locate(
        self,
        pattern: str,
        entries: list[Entry],
        use_regex: bool = False,
        extensions: list[str] | None = None,
        check_existence: bool = True,
    ) -> LocateResult:
        """Locate files matching a pattern.

        Args:
            pattern: Glob or regex pattern to match
            entries: List of entries to search
            use_regex: Use regex instead of glob pattern
            extensions: List of file extensions to filter (e.g., ['.pdf', '.ps'])
            check_existence: Whether to check if files exist on disk

        Returns:
            LocateResult with matching files
        """
        matches = []

        for entry in entries:
            if entry.pdf_path:
                # Check extension filter first
                if extensions and entry.pdf_path.suffix.lower() not in [
                    e.lower() for e in extensions
                ]:
                    continue

                # Check if file matches pattern
                if self._matches_pattern(entry.pdf_path, pattern, use_regex):
                    # Check file existence if requested
                    if check_existence:
                        exists = self._check_exists(entry.pdf_path)
                        size = None
                        if exists:
                            try:
                                size = entry.pdf_path.stat().st_size
                            except OSError:
                                pass
                    else:
                        exists = False
                        size = None

                    match = FileMatch(
                        entry_key=entry.key,
                        file_path=entry.pdf_path,
                        exists=exists,
                        size_bytes=size,
                    )
                    matches.append(match)

        missing_count = sum(1 for m in matches if not m.exists)

        return LocateResult(
            query=pattern,
            matches=matches,
            total_found=len(matches),
            missing_count=missing_count,
        )

    def _matches_pattern(
        self,
        path: Path,
        pattern: str,
        use_regex: bool,
    ) -> bool:
        """Check if path matches pattern."""
        if use_regex:
            # Regex matching (case-insensitive)
            try:
                regex = re.compile(pattern, re.IGNORECASE)
                # Match against full path or just basename
                return bool(regex.search(str(path)) or regex.search(path.name))
            except re.error:
                return False
        else:
            # Glob matching
            # Check both full path and basename
            return fnmatch.fnmatch(str(path), pattern) or fnmatch.fnmatch(
                path.name, pattern
            )

    def _check_exists(self, path: Path) -> bool:
        """Check if file exists with caching."""
        if path not in self._file_cache:
            self._file_cache[path] = path.exists()
        return self._file_cache[path]

    def find_by_key(self, key: str, entries: list[Entry]) -> FileMatch | None:
        """Find file for a specific entry key.

        Args:
            key: Entry key to search for
            entries: List of entries

        Returns:
            FileMatch or None if not found
        """
        for entry in entries:
            if entry.key == key and entry.pdf_path:
                exists = self._check_exists(entry.pdf_path)
                size = None
                if exists:
                    try:
                        size = entry.pdf_path.stat().st_size
                    except OSError:
                        pass

                return FileMatch(
                    entry_key=key,
                    file_path=entry.pdf_path,
                    exists=exists,
                    size_bytes=size,
                )

        return None

    def find_by_basename(
        self,
        basename: str,
        entries: list[Entry],
    ) -> LocateResult:
        """Find files by exact basename match.

        Args:
            basename: Basename to search for
            entries: List of entries

        Returns:
            LocateResult with matching files
        """
        matches = []

        for entry in entries:
            if entry.pdf_path and entry.pdf_path.name == basename:
                exists = self._check_exists(entry.pdf_path)
                size = None
                if exists:
                    try:
                        size = entry.pdf_path.stat().st_size
                    except OSError:
                        pass

                match = FileMatch(
                    entry_key=entry.key,
                    file_path=entry.pdf_path,
                    exists=exists,
                    size_bytes=size,
                )
                matches.append(match)

        missing_count = sum(1 for m in matches if not m.exists)

        return LocateResult(
            query=basename,
            matches=matches,
            total_found=len(matches),
            missing_count=missing_count,
        )

    def find_orphaned_files(
        self,
        entries: list[Entry],
    ) -> list[Path]:
        """Find PDF files not linked to any entry.

        Args:
            entries: List of entries

        Returns:
            List of orphaned file paths
        """
        # Get all PDF files in base paths
        pdf_files = set()
        for base_path in self.base_paths:
            if base_path.exists():
                pdf_files.update(base_path.rglob("*.pdf"))

        # Get all linked files
        linked_files = set()
        for entry in entries:
            if entry.pdf_path:
                linked_files.add(entry.pdf_path)

        # Find orphans
        orphans = pdf_files - linked_files

        return sorted(orphans)

    def get_statistics(self, entries: list[Entry]) -> dict[str, Any]:
        """Calculate file statistics for entries.

        Args:
            entries: List of entries

        Returns:
            Dictionary of statistics
        """
        total_files = 0
        existing_files = 0
        missing_files = 0
        total_size_bytes = 0
        extensions = {}

        for entry in entries:
            if entry.pdf_path:
                total_files += 1

                # Check existence
                exists = self._check_exists(entry.pdf_path)
                if exists:
                    existing_files += 1

                    # Get file size
                    try:
                        size = entry.pdf_path.stat().st_size
                        total_size_bytes += size
                    except OSError:
                        pass

                    # Track file type
                    ext = entry.pdf_path.suffix.lower()
                    extensions[ext] = extensions.get(ext, 0) + 1
                else:
                    missing_files += 1

        # Convert to MB
        total_size_mb = total_size_bytes / (1024 * 1024)

        return {
            "total_files": total_files,
            "existing_files": existing_files,
            "missing_files": missing_files,
            "total_size_mb": total_size_mb,
            "extensions": extensions,
        }

    def verify_all(self, entries: list[Entry]) -> dict[str, list[FileMatch]]:
        """Verify all file paths in entries.

        Args:
            entries: List of entries to verify

        Returns:
            Dictionary with 'existing' and 'missing' file matches
        """
        existing = []
        missing = []

        for entry in entries:
            if entry.pdf_path:
                exists = self._check_exists(entry.pdf_path)
                size = None
                if exists:
                    try:
                        size = entry.pdf_path.stat().st_size
                    except OSError:
                        pass

                match = FileMatch(
                    entry_key=entry.key,
                    file_path=entry.pdf_path,
                    exists=exists,
                    size_bytes=size,
                )

                if exists:
                    existing.append(match)
                else:
                    missing.append(match)

        return {
            "existing": existing,
            "missing": missing,
        }
