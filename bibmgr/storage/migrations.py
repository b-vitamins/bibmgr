"""Data migration support for moving between storage backends.

This module provides utilities for migrating data between different
storage backends, with progress tracking and error handling.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from bibmgr.storage.backends.base import BaseBackend
from bibmgr.storage.events import Event, EventBus, EventType
from bibmgr.storage.metadata import MetadataStore
from bibmgr.storage.repository import CollectionRepository, EntryRepository


@dataclass
class MigrationStats:
    """Statistics for a migration operation."""

    started_at: datetime
    completed_at: datetime | None = None
    total_entries: int = 0
    migrated_entries: int = 0
    failed_entries: int = 0
    total_collections: int = 0
    migrated_collections: int = 0
    failed_collections: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float | None:
        """Get migration duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        total = self.total_entries + self.total_collections
        if total == 0:
            return 100.0
        migrated = self.migrated_entries + self.migrated_collections
        return (migrated / total) * 100.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "duration": self.duration,
            "total_entries": self.total_entries,
            "migrated_entries": self.migrated_entries,
            "failed_entries": self.failed_entries,
            "total_collections": self.total_collections,
            "migrated_collections": self.migrated_collections,
            "failed_collections": self.failed_collections,
            "success_rate": self.success_rate,
            "errors": self.errors,
        }


class MigrationManager:
    """Manages data migration between storage backends."""

    def __init__(self, event_bus: EventBus | None = None):
        self.event_bus = event_bus or EventBus()
        self._progress_callback: Callable[[int, int], None] | None = None

    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        """Set a callback for progress updates (current, total)."""
        self._progress_callback = callback

    def _report_progress(self, current: int, total: int) -> None:
        """Report progress to callback if set."""
        if self._progress_callback:
            self._progress_callback(current, total)

    def migrate_entries(
        self,
        source_backend: BaseBackend,
        target_backend: BaseBackend,
        batch_size: int = 100,
    ) -> MigrationStats:
        """Migrate entries between backends."""
        stats = MigrationStats(started_at=datetime.now())

        source_repo = EntryRepository(source_backend)
        target_repo = EntryRepository(target_backend)

        all_keys = source_backend.keys()
        stats.total_entries = len(all_keys)

        for i in range(0, len(all_keys), batch_size):
            batch_keys = all_keys[i : i + batch_size]

            for key in batch_keys:
                try:
                    entry = source_repo.find(key)
                    if entry:
                        target_repo.save(entry)
                        stats.migrated_entries += 1
                    else:
                        stats.failed_entries += 1
                        stats.errors.append(f"Entry {key}: Not found in source")

                except Exception as e:
                    stats.failed_entries += 1
                    stats.errors.append(f"Entry {key}: {str(e)}")

            processed = min(i + batch_size, len(all_keys))
            self._report_progress(processed, len(all_keys))

        stats.completed_at = datetime.now()

        if self.event_bus:
            self.event_bus.publish(
                Event(
                    type=EventType.INDEX_REBUILT,
                    timestamp=stats.completed_at,
                    data={"migration_stats": stats.to_dict()},
                )
            )

        return stats

    def migrate_collections(
        self, source_backend: BaseBackend, target_backend: BaseBackend
    ) -> MigrationStats:
        """Migrate collections between backends."""
        stats = MigrationStats(started_at=datetime.now())

        source_repo = CollectionRepository(source_backend)
        target_repo = CollectionRepository(target_backend)

        collections = source_repo.find_all()
        stats.total_collections = len(collections)

        for i, collection in enumerate(collections):
            try:
                target_repo.save(collection)
                stats.migrated_collections += 1
            except Exception as e:
                stats.failed_collections += 1
                stats.errors.append(f"Collection {collection.id}: {str(e)}")

            self._report_progress(i + 1, len(collections))

        stats.completed_at = datetime.now()
        return stats

    def migrate_metadata(self, source_dir: Path, target_dir: Path) -> MigrationStats:
        """Migrate metadata between storage directories."""
        stats = MigrationStats(started_at=datetime.now())

        source_store = MetadataStore(source_dir)
        target_store = MetadataStore(target_dir)

        entry_keys = list(source_store._metadata_cache.keys())
        stats.total_entries = len(entry_keys)

        for i, key in enumerate(entry_keys):
            try:
                metadata = source_store.get_metadata(key)
                target_store.save_metadata(metadata)

                notes = source_store.get_notes(key)
                for note in notes:
                    target_store.add_note(note)

                stats.migrated_entries += 1

            except Exception as e:
                stats.failed_entries += 1
                stats.errors.append(f"Metadata {key}: {str(e)}")

            self._report_progress(i + 1, len(entry_keys))

        stats.completed_at = datetime.now()
        return stats

    def migrate_all(
        self,
        source_backend: BaseBackend,
        target_backend: BaseBackend,
        source_data_dir: Path | None = None,
        target_data_dir: Path | None = None,
    ) -> dict[str, MigrationStats]:
        """Perform complete migration including metadata."""
        results = {}

        print("Migrating entries...")
        results["entries"] = self.migrate_entries(source_backend, target_backend)

        print("Migrating collections...")
        results["collections"] = self.migrate_collections(
            source_backend, target_backend
        )

        if source_data_dir and target_data_dir:
            print("Migrating metadata...")
            results["metadata"] = self.migrate_metadata(
                source_data_dir, target_data_dir
            )

        return results

    def verify_migration(
        self, source_backend: BaseBackend, target_backend: BaseBackend
    ) -> dict[str, Any]:
        """Verify that migration was successful."""
        source_keys = set(source_backend.keys())
        target_keys = set(target_backend.keys())

        results = {
            "source_count": len(source_keys),
            "target_count": len(target_keys),
            "missing_in_target": list(source_keys - target_keys),
            "extra_in_target": list(target_keys - source_keys),
            "verification_passed": source_keys == target_keys,
        }

        sample_keys = list(source_keys)[:10]
        differences = []

        for key in sample_keys:
            source_data = source_backend.read(key)
            target_data = target_backend.read(key)

            if source_data != target_data:
                differences.append(
                    {"key": key, "source": source_data, "target": target_data}
                )

        results["sample_differences"] = differences

        return results


class BackupManager:
    """Manages backups of storage data."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.backup_dir = self.data_dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, backend: BaseBackend, name: str | None = None) -> Path:
        """Create a backup of the current storage."""
        if name is None:
            name = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

        backup_path = self.backup_dir / name
        backup_path.mkdir(parents=True, exist_ok=True)

        metadata = {
            "created_at": datetime.now().isoformat(),
            "entry_count": len(backend.keys()),
            "backend_type": backend.__class__.__name__,
        }

        with open(backup_path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        from bibmgr.storage.importers.json import JsonImporter
        from bibmgr.storage.repository import EntryRepository

        repo = EntryRepository(backend)
        entries = repo.find_all()

        exporter = JsonImporter()
        exporter.export_entries(entries, backup_path / "entries.json")

        return backup_path

    def list_backups(self) -> list[dict[str, Any]]:
        """List available backups."""
        backups = []

        for backup_dir in self.backup_dir.iterdir():
            if backup_dir.is_dir():
                metadata_file = backup_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file) as f:
                        metadata = json.load(f)

                    backups.append(
                        {
                            "name": backup_dir.name,
                            "path": str(backup_dir),
                            "created_at": metadata.get("created_at"),
                            "entry_count": metadata.get("entry_count"),
                            "size": sum(
                                f.stat().st_size for f in backup_dir.rglob("*")
                            ),
                        }
                    )

        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups

    def restore_backup(
        self, backup_name: str, target_backend: BaseBackend
    ) -> MigrationStats:
        """Restore from a backup."""
        backup_path = self.backup_dir / backup_name
        if not backup_path.exists():
            raise ValueError(f"Backup not found: {backup_name}")

        from bibmgr.storage.importers.json import JsonImporter
        from bibmgr.storage.repository import EntryRepository

        importer = JsonImporter()
        entries, errors = importer.import_file(backup_path / "entries.json")

        stats = MigrationStats(started_at=datetime.now())
        stats.total_entries = len(entries) + len(errors)

        repo = EntryRepository(target_backend)
        for entry in entries:
            try:
                repo.save(entry)
                stats.migrated_entries += 1
            except Exception as e:
                stats.failed_entries += 1
                stats.errors.append(f"Entry {entry.key}: {str(e)}")

        stats.failed_entries += len(errors)
        stats.errors.extend(errors)
        stats.completed_at = datetime.now()

        return stats
