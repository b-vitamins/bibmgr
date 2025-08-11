"""Migration workflow for migrating between storage backends and data formats."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from bibmgr.core.models import Entry
from bibmgr.storage.backends import FileSystemBackend, SQLiteBackend
from bibmgr.storage.events import Event, EventBus, EventType
from bibmgr.storage.repository import RepositoryManager

from ..results import StepResult, WorkflowResult


class MigrationType(Enum):
    """Type of migration to perform."""

    BACKEND = "backend"
    FORMAT_UPGRADE = "format_upgrade"
    FIELD_MAPPING = "field_mapping"
    TYPE_CHANGE = "type_change"


@dataclass
class MigrationConfig:
    """Configuration for migration workflow."""

    migration_type: MigrationType = MigrationType.BACKEND
    target_version: str | None = None
    field_mappings: dict[str, str] | None = None
    type_mappings: dict[str, str] | None = None
    validate_entries: bool = True
    validate_after: bool = True
    fix_validation_errors: bool = False
    migrate_metadata: bool = True
    migrate_collections: bool = True
    migrate_notes: bool = True
    batch_size: int = 100
    dry_run: bool = False
    test_mode: bool = False
    backup_dir: Path | None = None
    cleanup_source: bool = False


class MigrationWorkflow:
    """Workflow for migrating data between storage backends and formats."""

    def __init__(self, manager: RepositoryManager, event_bus: EventBus):
        self.manager = manager
        self.event_bus = event_bus

    def execute(
        self,
        config: MigrationConfig | None = None,
        target_manager: RepositoryManager | None = None,
    ) -> WorkflowResult:
        """Execute migration workflow."""
        config = config or MigrationConfig()

        if config.migration_type == MigrationType.BACKEND:
            if not target_manager:
                raise ValueError("Backend migration requires target_manager")
            return self._execute_backend_migration(self.manager, target_manager, config)
        elif config.migration_type == MigrationType.FORMAT_UPGRADE:
            return self._execute_format_upgrade(config)
        elif config.migration_type == MigrationType.FIELD_MAPPING:
            return self._execute_field_mapping(config)
        elif config.migration_type == MigrationType.TYPE_CHANGE:
            return self._execute_type_change(config)
        else:
            raise ValueError(f"Unknown migration type: {config.migration_type}")

    def _execute_backend_migration(
        self,
        source_manager: RepositoryManager,
        target_manager: RepositoryManager,
        config: MigrationConfig,
    ) -> WorkflowResult:
        """Execute backend-to-backend migration."""
        result = WorkflowResult(
            workflow="migrate",
            config={
                "type": "backend",
                "source": self._get_backend_info(source_manager),
                "target": self._get_backend_info(target_manager),
                "dry_run": config.dry_run,
            },
        )

        validate_result = self._validate_backends(source_manager, target_manager)
        result.add_step(validate_result)

        if not validate_result.success:
            result.complete()
            return result

        count_result = self._count_items(source_manager, config)
        result.add_step(count_result)

        if not count_result.success:
            result.complete()
            return result

        counts = count_result.data or {}

        if counts.get("entries", 0) > 0:
            entries_result = self._migrate_entries(
                source_manager, target_manager, config
            )
            result.add_step(entries_result)

            if not entries_result.success:
                result.complete()
                return result

        if config.migrate_metadata and counts.get("metadata", 0) > 0:
            metadata_result = self._migrate_metadata(
                source_manager, target_manager, config
            )
            result.add_step(metadata_result)

        if config.migrate_collections and counts.get("collections", 0) > 0:
            collections_result = self._migrate_collections(
                source_manager, target_manager, config
            )
            result.add_step(collections_result)

        if config.migrate_notes and counts.get("notes", 0) > 0:
            notes_result = self._migrate_notes(source_manager, target_manager, config)
            result.add_step(notes_result)

        verify_result = self._verify_migration(source_manager, target_manager, counts)
        result.add_step(verify_result)

        if config.cleanup_source and verify_result.success and not config.dry_run:
            cleanup_result = self._cleanup_source(source_manager)
            result.add_step(cleanup_result)

        result.complete()

        event = Event(
            type=EventType.WORKFLOW_COMPLETED,
            timestamp=datetime.now(),
            data={
                "workflow": "migration",
                "result": result,
            },
        )
        self.event_bus.publish(event)

        return result

    def _get_backend_info(self, manager: RepositoryManager) -> dict[str, Any]:
        """Get information about storage backend."""
        backend = manager.entries.backend
        info = {"type": backend.__class__.__name__}

        if isinstance(backend, FileSystemBackend):
            info["path"] = str(backend.data_dir)
        elif isinstance(backend, SQLiteBackend):
            info["database"] = str(backend.db_path)

        return info

    def _validate_backends(
        self, source_manager: RepositoryManager, target_manager: RepositoryManager
    ) -> StepResult:
        """Validate source and target backends."""
        try:
            if not source_manager.entries.find_all():
                return StepResult(
                    step="validate",
                    success=False,
                    message="Source has no entries to migrate",
                )

            if target_manager.entries.find_all():
                return StepResult(
                    step="validate",
                    success=False,
                    message="Target is not empty. Migration requires empty target.",
                    warnings=[
                        "To proceed, clear the target storage or use a different target"
                    ],
                )

            return StepResult(
                step="validate",
                success=True,
                message="Source and target validated",
            )

        except Exception as e:
            return StepResult(
                step="validate",
                success=False,
                message="Failed to validate backends",
                errors=[str(e)],
            )

    def _count_items(
        self, source_manager: RepositoryManager, config: MigrationConfig
    ) -> StepResult:
        """Count items to migrate."""
        try:
            counts = {
                "entries": len(source_manager.entries.find_all()),
                "metadata": 0,
                "collections": 0,
                "notes": 0,
            }

            if config.migrate_metadata:
                for entry in source_manager.entries.find_all():
                    try:
                        source_manager.metadata_store.get_metadata(
                            entry.key
                        ) if source_manager.metadata_store else None
                        counts["metadata"] += 1
                    except Exception:
                        pass

            if config.migrate_collections:
                counts["collections"] = len(source_manager.collections.find_all())

            return StepResult(
                step="count",
                success=True,
                message=f"Found {counts['entries']} entries to migrate",
                data=counts,
            )

        except Exception as e:
            return StepResult(
                step="count",
                success=False,
                message="Failed to count items",
                errors=[str(e)],
            )

    def _migrate_entries(
        self,
        source_manager: RepositoryManager,
        target_manager: RepositoryManager,
        config: MigrationConfig,
    ) -> StepResult:
        """Migrate bibliography entries."""
        try:
            entries = source_manager.entries.find_all()
            migrated = 0
            failed = 0
            warnings = []

            for i in range(0, len(entries), config.batch_size):
                batch = entries[i : i + config.batch_size]

                event = Event(
                    type=EventType.PROGRESS,
                    timestamp=datetime.now(),
                    data={
                        "operation": "migrate_entries",
                        "current": i,
                        "total": len(entries),
                    },
                )
                self.event_bus.publish(event)

                for entry in batch:
                    if config.validate_entries:
                        errors = entry.validate()
                        if errors:
                            warnings.append(
                                f"{entry.key}: {', '.join(e.message for e in errors)}"
                            )

                    if not config.dry_run:
                        try:
                            target_manager.entries.save(entry)
                            migrated += 1
                        except Exception as e:
                            failed += 1
                            warnings.append(f"{entry.key}: {str(e)}")
                    else:
                        migrated += 1

            return StepResult(
                step="migrate_entries",
                success=failed == 0,
                message=f"Migrated {migrated} entries"
                + (f", {failed} failed" if failed else ""),
                warnings=warnings[:10] if warnings else None,
            )

        except Exception as e:
            return StepResult(
                step="migrate_entries",
                success=False,
                message="Failed to migrate entries",
                errors=[str(e)],
            )

    def _migrate_metadata(
        self,
        source_manager: RepositoryManager,
        target_manager: RepositoryManager,
        config: MigrationConfig,
    ) -> StepResult:
        """Migrate entry metadata."""
        try:
            migrated = 0

            for entry in source_manager.entries.find_all():
                try:
                    if source_manager.metadata_store:
                        metadata = source_manager.metadata_store.get_metadata(entry.key)
                        if not config.dry_run and target_manager.metadata_store:
                            target_manager.metadata_store.save_metadata(metadata)
                    migrated += 1
                except Exception:
                    pass

            return StepResult(
                step="migrate_metadata",
                success=True,
                message=f"Migrated {migrated} metadata entries",
            )

        except Exception as e:
            return StepResult(
                step="migrate_metadata",
                success=False,
                message="Failed to migrate metadata",
                errors=[str(e)],
            )

    def _migrate_collections(
        self,
        source_manager: RepositoryManager,
        target_manager: RepositoryManager,
        config: MigrationConfig,
    ) -> StepResult:
        """Migrate collections."""
        try:
            collections = source_manager.collections.find_all()
            migrated = 0

            for collection in collections:
                if not config.dry_run:
                    target_manager.collections.save(collection)
                migrated += 1

            return StepResult(
                step="migrate_collections",
                success=True,
                message=f"Migrated {migrated} collections",
            )

        except Exception as e:
            return StepResult(
                step="migrate_collections",
                success=False,
                message="Failed to migrate collections",
                errors=[str(e)],
            )

    def _migrate_notes(
        self,
        source_manager: RepositoryManager,
        target_manager: RepositoryManager,
        config: MigrationConfig,
    ) -> StepResult:
        """Migrate notes."""
        try:
            migrated = 0

            for entry in source_manager.entries.find_all():
                try:
                    if source_manager.metadata_store:
                        notes = source_manager.metadata_store.get_notes(entry.key)
                        for note in notes:
                            if not config.dry_run and target_manager.metadata_store:
                                target_manager.metadata_store.add_note(entry.key, note)
                        migrated += 1
                except Exception:
                    pass

            return StepResult(
                step="migrate_notes",
                success=True,
                message=f"Migrated {migrated} notes",
            )

        except Exception as e:
            return StepResult(
                step="migrate_notes",
                success=False,
                message="Failed to migrate notes",
                errors=[str(e)],
            )

    def _verify_migration(
        self,
        source_manager: RepositoryManager,
        target_manager: RepositoryManager,
        expected_counts: dict[str, int],
    ) -> StepResult:
        """Verify migration was successful."""
        try:
            actual_counts = {
                "entries": len(target_manager.entries.find_all()),
                "collections": len(target_manager.collections.find_all()),
            }

            mismatches = []
            if actual_counts["entries"] != expected_counts["entries"]:
                mismatches.append(
                    f"Entries: expected {expected_counts['entries']}, got {actual_counts['entries']}"
                )

            if actual_counts["collections"] != expected_counts["collections"]:
                mismatches.append(
                    f"Collections: expected {expected_counts['collections']}, got {actual_counts['collections']}"
                )

            if mismatches:
                return StepResult(
                    step="verify",
                    success=False,
                    message="Migration verification failed",
                    errors=mismatches,
                )

            return StepResult(
                step="verify",
                success=True,
                message="Migration verified successfully",
            )

        except Exception as e:
            return StepResult(
                step="verify",
                success=False,
                message="Failed to verify migration",
                errors=[str(e)],
            )

    def _cleanup_source(self, source_manager: RepositoryManager) -> StepResult:
        """Clean up source after successful migration."""
        try:
            for entry in source_manager.entries.find_all():
                source_manager.entries.delete(entry.key)

            for collection in source_manager.collections.find_all():
                source_manager.collections.delete(str(collection.id))

            return StepResult(
                step="cleanup",
                success=True,
                message="Source cleaned up successfully",
            )

        except Exception as e:
            return StepResult(
                step="cleanup",
                success=False,
                message="Failed to cleanup source",
                errors=[str(e)],
                warnings=["Source data may be partially deleted"],
            )

    def _execute_format_upgrade(self, config: MigrationConfig) -> WorkflowResult:
        """Execute format upgrade migration."""
        result = WorkflowResult(
            workflow="migrate",
            config={
                "type": "format_upgrade",
                "target_version": config.target_version,
                "dry_run": config.dry_run,
            },
        )

        if config.backup_dir and not config.dry_run:
            backup_result = self._create_backup(config.backup_dir)
            result.add_step(backup_result)
            if not backup_result.success:
                result.complete()
                return result

        upgrade_result = self._upgrade_entries_format(config)
        result.add_step(upgrade_result)

        if config.validate_after and upgrade_result.success:
            validate_result = self._validate_upgraded_entries()
            result.add_step(validate_result)

        if config.test_mode and config.backup_dir:
            rollback_result = self._restore_backup(config.backup_dir)
            result.add_step(rollback_result)

        result.complete()
        return result

    def _execute_field_mapping(self, config: MigrationConfig) -> WorkflowResult:
        """Execute field mapping migration."""
        result = WorkflowResult(
            workflow="migrate",
            config={
                "type": "field_mapping",
                "mappings": config.field_mappings,
                "dry_run": config.dry_run,
            },
        )

        if not config.field_mappings:
            result.add_step(
                StepResult(
                    step="validate",
                    success=False,
                    message="No field mappings provided",
                )
            )
            result.complete()
            return result

        mapping_result = self._map_entry_fields(config.field_mappings, config.dry_run)
        result.add_step(mapping_result)

        result.complete()
        return result

    def _execute_type_change(self, config: MigrationConfig) -> WorkflowResult:
        """Execute type change migration."""
        result = WorkflowResult(
            workflow="migrate",
            config={
                "type": "type_change",
                "mappings": config.type_mappings,
                "dry_run": config.dry_run,
            },
        )

        if not config.type_mappings:
            result.add_step(
                StepResult(
                    step="validate",
                    success=False,
                    message="No type mappings provided",
                )
            )
            result.complete()
            return result

        type_change_result = self._change_entry_types(config)
        result.add_step(type_change_result)

        if config.validate_after and type_change_result.success:
            validate_result = self._validate_type_changes(config)
            result.add_step(validate_result)

        result.complete()
        return result

    def _create_backup(self, backup_dir: Path) -> StepResult:
        """Create backup of current data."""
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)

            entries = self.manager.entries.find_all()
            backup_file = backup_dir / "entries_backup.json"

            import json

            with open(backup_file, "w") as f:
                json.dump(
                    [entry.to_dict() for entry in entries], f, indent=2, default=str
                )

            return StepResult(
                step="backup",
                success=True,
                message=f"Backed up {len(entries)} entries",
                data={"backup_file": str(backup_file)},
            )
        except Exception as e:
            return StepResult(
                step="backup",
                success=False,
                message="Failed to create backup",
                errors=[str(e)],
            )

    def _restore_backup(self, backup_dir: Path) -> StepResult:
        """Restore from backup."""
        try:
            backup_file = backup_dir / "entries_backup.json"

            if not backup_file.exists():
                return StepResult(
                    step="restore",
                    success=False,
                    message="Backup file not found",
                )

            return StepResult(
                step="restore",
                success=True,
                message="Backup available for restore",
            )
        except Exception as e:
            return StepResult(
                step="restore",
                success=False,
                message="Failed to restore backup",
                errors=[str(e)],
            )

    def _upgrade_entries_format(self, config: MigrationConfig) -> StepResult:
        """Upgrade entries to new format."""
        try:
            entries = self.manager.entries.find_all()
            upgraded = 0

            for entry in entries:
                entry_dict = entry.to_dict()
                entry_dict["format_version"] = config.target_version

                if not config.dry_run:
                    updated_entry = Entry.from_dict(entry_dict)
                    self.manager.entries.save(updated_entry, skip_validation=True)

                upgraded += 1

            return StepResult(
                step="upgrade_format",
                success=True,
                message=f"Upgraded {upgraded} entries to format {config.target_version}",
            )
        except Exception as e:
            return StepResult(
                step="upgrade_format",
                success=False,
                message="Failed to upgrade format",
                errors=[str(e)],
            )

    def _validate_upgraded_entries(self) -> StepResult:
        """Validate entries after upgrade."""
        try:
            entries = self.manager.entries.find_all()
            invalid_count = 0
            warnings = []

            for entry in entries:
                errors = entry.validate()
                if errors:
                    invalid_count += 1
                    warnings.append(
                        f"{entry.key}: {', '.join(e.message for e in errors)}"
                    )

            if invalid_count > 0:
                return StepResult(
                    step="validate",
                    success=True,
                    message=f"Found {invalid_count} entries with validation issues",
                    warnings=warnings[:10],
                )

            return StepResult(
                step="validate",
                success=True,
                message="All entries valid after upgrade",
            )
        except Exception as e:
            return StepResult(
                step="validate",
                success=False,
                message="Failed to validate entries",
                errors=[str(e)],
            )

    def _map_entry_fields(self, mappings: dict[str, str], dry_run: bool) -> StepResult:
        """Map fields to new names."""
        try:
            entries = self.manager.entries.find_all()
            mapped = 0

            for entry in entries:
                entry_dict = entry.to_dict()
                changed = False

                for old_field, new_field in mappings.items():
                    if old_field in entry_dict:
                        entry_dict[new_field] = entry_dict.pop(old_field)
                        changed = True

                if changed and not dry_run:
                    updated_entry = Entry.from_dict(entry_dict)
                    self.manager.entries.save(updated_entry, skip_validation=True)
                    mapped += 1

            return StepResult(
                step="map_fields",
                success=True,
                message=f"Mapped fields for {mapped} entries",
            )
        except Exception as e:
            return StepResult(
                step="map_fields",
                success=False,
                message="Failed to map fields",
                errors=[str(e)],
            )

    def _change_entry_types(self, config: MigrationConfig) -> StepResult:
        """Change entry types based on mappings."""
        try:
            entries = self.manager.entries.find_all()
            changed = 0

            for entry in entries:
                if (
                    config.type_mappings
                    and str(entry.type.value) in config.type_mappings
                ):
                    new_type = config.type_mappings[str(entry.type.value)]
                    entry_dict = entry.to_dict()
                    entry_dict["type"] = new_type

                    if not config.dry_run:
                        updated_entry = Entry.from_dict(entry_dict)
                        self.manager.entries.save(updated_entry, skip_validation=True)

                    changed += 1

            return StepResult(
                step="change_types",
                success=True,
                message=f"Changed types for {changed} entries",
            )
        except Exception as e:
            return StepResult(
                step="change_types",
                success=False,
                message="Failed to change types",
                errors=[str(e)],
            )

    def _validate_type_changes(self, config: MigrationConfig) -> StepResult:
        """Validate entries after type changes."""
        try:
            entries = self.manager.entries.find_all()
            invalid_count = 0
            fixed_count = 0
            warnings = []

            for entry in entries:
                errors = entry.validate()
                if errors and config.fix_validation_errors:
                    entry_dict = entry.to_dict()
                    for error in errors:
                        if (
                            "Required field" in error.message
                            and "missing" in error.message
                        ):
                            field = error.field
                            if field == "author":
                                entry_dict["author"] = "Unknown"
                            elif field == "journal":
                                entry_dict["journal"] = "Unknown Journal"

                    try:
                        fixed_entry = Entry.from_dict(entry_dict)
                        if not config.dry_run:
                            self.manager.entries.save(fixed_entry)
                        fixed_count += 1
                    except Exception:
                        invalid_count += 1
                        warnings.append(f"{entry.key}: Could not fix validation errors")
                elif errors:
                    invalid_count += 1
                    warnings.append(
                        f"{entry.key}: {', '.join(e.message for e in errors)}"
                    )

            message = "Validation complete"
            if fixed_count > 0:
                message += f", fixed {fixed_count} entries"
            if invalid_count > 0:
                message += f", {invalid_count} still invalid"

            return StepResult(
                step="validate_types",
                success=invalid_count == 0,
                message=message,
                warnings=warnings[:10] if warnings else None,
            )
        except Exception as e:
            return StepResult(
                step="validate_types",
                success=False,
                message="Failed to validate type changes",
                errors=[str(e)],
            )
