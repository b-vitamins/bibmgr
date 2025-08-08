"""Integrated storage system bringing together all components.

Provides a unified interface for:
- BibTeX parsing and generation
- Entry storage with transactions
- Metadata and note management
- Import/export functionality
- Search across entries and metadata
"""

from __future__ import annotations

import hashlib
import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from bibmgr.core.models import Entry, EntryType
from bibmgr.storage.backend import FileSystemStorage, Transaction
from bibmgr.storage.parser import BibtexParser
from bibmgr.storage.sidecar import MetadataSidecar, EntryMetadata, Note


class StorageSystem:
    """Complete storage system integrating all components."""

    def __init__(self, data_dir: Path):
        """Initialize storage system."""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.parser = BibtexParser()
        self.storage = FileSystemStorage(self.data_dir / "storage")
        self.sidecar = MetadataSidecar(self.data_dir)

    # Entry management

    def create_entry(self, **kwargs) -> Entry:
        """Create a new entry."""
        # Ensure type is set
        if "type" not in kwargs:
            kwargs["type"] = EntryType.MISC
        elif isinstance(kwargs["type"], str):
            kwargs["type"] = EntryType(kwargs["type"].lower())

        return Entry(**kwargs)

    def validate_entry(self, entry: Entry) -> bool:
        """Validate an entry."""
        try:
            # Check required fields based on type
            if entry.type == EntryType.ARTICLE:
                return all([entry.author, entry.title, entry.journal, entry.year])
            elif entry.type == EntryType.BOOK:
                return all(
                    [
                        entry.author or entry.editor,
                        entry.title,
                        entry.publisher,
                        entry.year,
                    ]
                )
            else:
                return entry.title is not None
        except Exception:
            return False

    # Import/Export

    def import_file(self, path: Path, extract_metadata: bool = False) -> list[Entry]:
        """Import entries from BibTeX file."""
        entries = self.parser.parse_file(path)

        with self.storage.transaction() as txn:
            for entry in entries:
                txn.add(entry)

                if extract_metadata:
                    # Create initial metadata
                    metadata = EntryMetadata(key=entry.key)
                    self.sidecar.set_metadata(metadata)

        return entries

    def import_text(self, text: str, skip_invalid: bool = False) -> list[Entry]:
        """Import entries from BibTeX text."""
        entries = self.parser.parse(text)
        imported = []

        with self.storage.transaction() as txn:
            for entry in entries:
                if skip_invalid and not self.validate_entry(entry):
                    continue

                txn.add(entry)
                imported.append(entry)

        return imported

    def export_file(self, path: Path, include_metadata: bool = False) -> None:
        """Export entries to BibTeX file."""
        entries = self.storage.read_all()

        # Generate BibTeX
        lines = []
        for entry in entries:
            lines.append(self._entry_to_bibtex(entry))

            if include_metadata:
                metadata = self.sidecar.get_metadata(entry.key)
                if metadata and (metadata.tags or metadata.notes):
                    # Add as comment
                    lines.append(f"% Metadata for {entry.key}:")
                    if metadata.tags:
                        lines.append(f"% Tags: {', '.join(metadata.tags)}")
                    if metadata.notes:
                        lines.append(f"% Notes: {metadata.notes[:100]}...")

            lines.append("")

        # Write file
        path.write_text("\n".join(lines))

    def _entry_to_bibtex(self, entry: Entry) -> str:
        """Convert entry to BibTeX format."""
        lines = [f"@{entry.type.value}{{{entry.key},"]

        # Add fields
        fields = []
        if entry.author:
            fields.append(f'    author = "{entry.author}"')
        if entry.title:
            fields.append(f'    title = "{entry.title}"')
        if entry.journal:
            fields.append(f'    journal = "{entry.journal}"')
        if entry.booktitle:
            fields.append(f'    booktitle = "{entry.booktitle}"')
        if entry.publisher:
            fields.append(f'    publisher = "{entry.publisher}"')
        if entry.year:
            fields.append(f"    year = {entry.year}")
        if entry.volume:
            fields.append(f'    volume = "{entry.volume}"')
        if entry.number:
            fields.append(f'    number = "{entry.number}"')
        if entry.pages:
            fields.append(f'    pages = "{entry.pages}"')
        if entry.doi:
            fields.append(f'    doi = "{entry.doi}"')
        if entry.url:
            fields.append(f'    url = "{entry.url}"')

        lines.extend(fields)
        if fields:
            lines[-1] = lines[-1].rstrip(",")

        lines.append("}")
        return "\n".join(lines)

    # Search functionality

    def search(
        self,
        entry_filter: dict[str, Any] | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[Entry]:
        """Search entries with optional metadata filtering."""
        # Get entries matching entry filter
        if entry_filter:
            entries = self.storage.search(entry_filter)
        else:
            entries = self.storage.read_all()

        # Filter by metadata if needed
        if metadata_filter:
            filtered = []
            for entry in entries:
                metadata = self.sidecar.get_metadata(entry.key)
                if self._match_metadata(metadata, metadata_filter):
                    filtered.append(entry)
            entries = filtered

        return entries

    def _match_metadata(
        self, metadata: EntryMetadata | None, filter: dict[str, Any]
    ) -> bool:
        """Check if metadata matches filter."""
        if metadata is None:
            return False

        for field, value in filter.items():
            if field == "tags":
                if not metadata.tags:
                    return False
                if isinstance(value, str):
                    if value not in metadata.tags:
                        return False
                elif isinstance(value, dict) and "$contains" in value:
                    if value["$contains"] not in metadata.tags:
                        return False

            elif field == "rating":
                if isinstance(value, dict):
                    if "$gte" in value and (
                        metadata.rating is None or metadata.rating < value["$gte"]
                    ):
                        return False
                    if "$lte" in value and (
                        metadata.rating is None or metadata.rating > value["$lte"]
                    ):
                        return False
                elif metadata.rating != value:
                    return False

            elif field == "reading_status":
                if metadata.reading_status != value:
                    return False

        return True

    def full_text_search(self, query: str) -> list[Entry]:
        """Search across entries and notes."""
        query_lower = query.lower()
        results = []
        seen_keys = set()

        # Search entry content
        for entry in self.storage.read_all():
            if query_lower in (entry.title or "").lower():
                results.append(entry)
                seen_keys.add(entry.key)
            elif query_lower in (entry.abstract or "").lower():
                if entry.key not in seen_keys:
                    results.append(entry)
                    seen_keys.add(entry.key)

        # Search notes
        notes = self.sidecar.search_notes(query)
        for note in notes:
            if note.entry_key not in seen_keys:
                entry = self.storage.read(note.entry_key)
                if entry:
                    results.append(entry)
                    seen_keys.add(entry.key)

        return results

    # Note management

    def create_note(self, entry_key: str, content: str, **kwargs) -> Note:
        """Create a new note."""
        return Note(entry_key=entry_key, content=content, **kwargs)

    # Transaction support

    @contextmanager
    def begin_transaction(self) -> Iterator[Transaction]:
        """Begin a transaction."""
        with self.storage.transaction() as txn:
            yield txn

    # Backup and restore

    def backup(self, path: Path) -> None:
        """Create complete system backup."""
        if path.exists():
            shutil.rmtree(path)

        path.mkdir(parents=True)

        # Backup storage
        self.storage.backup(path / "storage")

        # Backup metadata
        self.sidecar.export(path / "metadata.json")

    def restore(self, path: Path) -> None:
        """Restore from backup."""
        if not path.exists():
            raise ValueError(f"Backup path does not exist: {path}")

        # Restore storage
        storage_backup = path / "storage"
        if storage_backup.exists():
            self.storage.restore(storage_backup)

        # Restore metadata
        metadata_backup = path / "metadata.json"
        if metadata_backup.exists():
            self.sidecar.import_from(metadata_backup)

    def backup_incremental(self, path: Path) -> None:
        """Create incremental backup (if supported)."""
        # For now, just do a full backup
        # Could be enhanced to only backup changed files
        self.backup(path)

    def restore_selective(self, path: Path, keys: list[str]) -> None:
        """Restore specific entries from backup."""
        # Create temporary storage to load backup
        temp_dir = Path("/tmp/bibmgr_restore_temp")
        temp_system = StorageSystem(temp_dir)
        temp_system.restore(path)

        # Copy selected entries
        with self.storage.transaction() as txn:
            for key in keys:
                entry = temp_system.storage.read(key)
                if entry:
                    txn.add(entry)

                metadata = temp_system.sidecar.get_metadata(key)
                if metadata:
                    self.sidecar.set_metadata(metadata)

        # Clean up
        shutil.rmtree(temp_dir)

    # System integrity

    def get_system_checksum(self) -> str:
        """Get checksum of entire system."""
        storage_checksum = self.storage.get_checksum()

        # Simple combination of checksums
        combined = f"{storage_checksum}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def validate_integrity(self) -> tuple[bool, list[str]]:
        """Validate system integrity."""
        errors = []

        # Validate storage
        storage_valid, storage_errors = self.storage.validate()
        if not storage_valid:
            errors.extend(f"Storage: {e}" for e in storage_errors)

        # Validate sidecar
        sidecar_valid, sidecar_errors = self.sidecar.validate()
        if not sidecar_valid:
            errors.extend(f"Sidecar: {e}" for e in sidecar_errors)

        # Check referential integrity
        storage_keys = set(self.storage.keys())

        for path in self.sidecar.entries_dir.glob("*.json"):
            key = path.stem
            if key not in storage_keys:
                errors.append(f"Orphaned metadata for non-existent entry: {key}")

        return len(errors) == 0, errors

    def cleanup_orphaned(self) -> None:
        """Clean up orphaned metadata."""
        storage_keys = set(self.storage.keys())

        for path in self.sidecar.entries_dir.glob("*.json"):
            key = path.stem
            if key not in storage_keys:
                self.sidecar.delete_metadata(key)

    # Migration support

    def migrate_format(self, target_version: str) -> None:
        """Migrate storage format to target version."""
        # Placeholder for format migration
        # Would implement actual migration logic based on versions
        pass

    def import_legacy(self, path: Path) -> Entry | None:
        """Import from legacy format."""
        # Placeholder for legacy import
        # Would handle old formats
        try:
            with open(path, "r") as f:
                data = json.load(f)

            # Convert old format
            if "year" in data and isinstance(data["year"], str):
                data["year"] = int(data["year"])

            return self.create_entry(**data)
        except Exception:
            return None
