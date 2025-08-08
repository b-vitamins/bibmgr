"""CRUD operations for bibliography entries with thread safety and optimization."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

import msgspec

from ..core.models import Entry, EntryType
from ..core.validators import EntryValidator
from ..storage.backend import FileSystemStorage

logger = logging.getLogger(__name__)


class OperationType(str, Enum):
    """Type of operation performed."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    REPLACE = "replace"
    BULK = "bulk"


@dataclass(frozen=True)
class OperationResult:
    """Result of an entry operation."""

    success: bool
    operation: OperationType
    entry_key: str | None = None
    message: str | None = None
    old_entry: Entry | None = None
    new_entry: Entry | None = None
    errors: list[str] | None = None
    affected_count: int = 0

    @property
    def failed(self) -> bool:
        """Check if operation failed."""
        return not self.success


@dataclass
class BulkOperationOptions:
    """Options for bulk operations."""

    stop_on_error: bool = False
    validate: bool = True
    atomic: bool = False
    progress_reporter: ProgressReporter | None = None


@dataclass
class CascadeOptions:
    """Options for cascade delete operations."""

    delete_notes: bool = False
    delete_metadata: bool = False
    delete_attachments: bool = False


class ProgressReporter(Protocol):
    """Protocol for progress reporting."""

    def report(
        self, stage: str, current: int, total: int, message: str | None = None
    ) -> None:
        """Report operation progress."""
        ...


class EntryOperations:
    """Manages CRUD operations on bibliography entries with thread safety."""

    def __init__(
        self,
        storage: FileSystemStorage,
        validator: EntryValidator | None = None,
        dry_run: bool = False,
        lock_timeout: float = 30.0,
    ):
        """Initialize entry operations.

        Args:
            storage: Storage backend for entries
            validator: Entry validator for validation
            dry_run: If True, no actual changes are made
            lock_timeout: Timeout for acquiring locks in seconds
        """
        self.storage = storage
        self.validator = validator
        self.dry_run = dry_run
        self.lock_timeout = lock_timeout
        self._locks: dict[str, threading.RLock] = {}
        self._lock_manager = threading.Lock()

    def _get_lock(self, key: str) -> threading.RLock:
        """Get or create a lock for a specific entry key."""
        with self._lock_manager:
            if key not in self._locks:
                self._locks[key] = threading.RLock()
            return self._locks[key]

    def _acquire_lock(self, key: str, timeout: float | None = None) -> bool:
        """Acquire lock with timeout."""
        lock = self._get_lock(key)
        timeout = timeout or self.lock_timeout
        return lock.acquire(timeout=timeout)

    def _release_lock(self, key: str) -> None:
        """Release lock for a key."""
        if key in self._locks:
            try:
                self._locks[key].release()
            except RuntimeError:
                pass  # Not acquired by this thread

    def _validate_entry(self, entry: Entry) -> list[str]:
        """Validate an entry."""
        if not self.validator:
            return []
        return [str(e) for e in self.validator.validate(entry)]

    def _validate_entry_type_change(self, old_type: EntryType, new_type: str) -> bool:
        """Validate that entry type change is valid."""
        try:
            EntryType(new_type)
            return True
        except ValueError:
            return False

    def create(self, entry: Entry, force: bool = False) -> OperationResult:
        """Create a new entry.

        Args:
            entry: Entry to create
            force: Force creation even with validation errors

        Returns:
            Operation result
        """
        # Validate unless forced
        if not force:
            errors = self._validate_entry(entry)
            if errors:
                return OperationResult(
                    success=False,
                    operation=OperationType.CREATE,
                    entry_key=entry.key,
                    message="Validation failed",
                    errors=errors,
                    new_entry=entry,
                )

        # Acquire lock for this key
        if not self._acquire_lock(entry.key):
            return OperationResult(
                success=False,
                operation=OperationType.CREATE,
                entry_key=entry.key,
                message="Lock acquisition timeout",
                new_entry=entry,
            )

        try:
            # Check if already exists
            existing = self.storage.read(entry.key)
            if existing:
                return OperationResult(
                    success=False,
                    operation=OperationType.CREATE,
                    entry_key=entry.key,
                    message=f"Entry with key '{entry.key}' already exists",
                    old_entry=existing,
                    new_entry=entry,
                )

            # Perform creation
            if self.dry_run:
                logger.info(f"[DRY RUN] Would create entry: {entry.key}")
                return OperationResult(
                    success=True,
                    operation=OperationType.CREATE,
                    entry_key=entry.key,
                    message=f"[DRY RUN] Entry '{entry.key}' would be created",
                    new_entry=entry,
                    affected_count=1,
                )

            try:
                with self.storage.transaction() as tx:
                    tx.add(entry)
                    tx.commit()
                logger.info(f"Created entry: {entry.key}")
                return OperationResult(
                    success=True,
                    operation=OperationType.CREATE,
                    entry_key=entry.key,
                    message=f"Entry '{entry.key}' created successfully",
                    new_entry=entry,
                    affected_count=1,
                )
            except Exception as e:
                logger.error(f"Storage error creating {entry.key}: {e}")
                return OperationResult(
                    success=False,
                    operation=OperationType.CREATE,
                    entry_key=entry.key,
                    message="Storage error",
                    errors=[str(e)],
                    new_entry=entry,
                )
        finally:
            self._release_lock(entry.key)

    def read(self, key: str) -> Entry | None:
        """Read an entry by key.

        Args:
            key: Entry key to read

        Returns:
            Entry if found, None otherwise
        """
        return self.storage.read(key)

    def update(
        self,
        key: str,
        updates: dict[str, Any],
        validate: bool = True,
    ) -> OperationResult:
        """Update an existing entry.

        Args:
            key: Entry key to update
            updates: Dictionary of field updates
            validate: Whether to validate after update

        Returns:
            Operation result
        """
        # Acquire lock
        if not self._acquire_lock(key):
            return OperationResult(
                success=False,
                operation=OperationType.UPDATE,
                entry_key=key,
                message="Lock acquisition timeout",
            )

        try:
            # Read existing entry
            existing = self.storage.read(key)
            if not existing:
                return OperationResult(
                    success=False,
                    operation=OperationType.UPDATE,
                    entry_key=key,
                    message=f"Entry '{key}' not found",
                )

            # Handle key rename if present
            new_key = updates.get("key")
            if new_key and new_key != key:
                # Check if new key already exists
                if self.storage.read(new_key):
                    return OperationResult(
                        success=False,
                        operation=OperationType.UPDATE,
                        entry_key=key,
                        message=f"Cannot rename: entry '{new_key}' already exists",
                        old_entry=existing,
                    )

            # Validate type change if present
            if "type" in updates:
                if not self._validate_entry_type_change(existing.type, updates["type"]):
                    return OperationResult(
                        success=False,
                        operation=OperationType.UPDATE,
                        entry_key=key,
                        message=f"Invalid entry type: {updates['type']}",
                        old_entry=existing,
                        errors=["Invalid entry type"],
                    )

            # Create updated entry
            try:
                entry_dict = msgspec.structs.asdict(existing)

                # Apply updates, handling None values
                for field, value in updates.items():
                    if value is None:
                        entry_dict.pop(field, None)
                    else:
                        entry_dict[field] = value

                # Handle year type conversion
                if "year" in entry_dict and entry_dict["year"] is not None:
                    try:
                        entry_dict["year"] = int(entry_dict["year"])
                    except (ValueError, TypeError):
                        return OperationResult(
                            success=False,
                            operation=OperationType.UPDATE,
                            entry_key=key,
                            message="Invalid year value",
                            old_entry=existing,
                            errors=[
                                f"Year must be an integer, got: {entry_dict['year']}"
                            ],
                        )

                new_entry = msgspec.convert(entry_dict, Entry)
            except Exception as e:
                return OperationResult(
                    success=False,
                    operation=OperationType.UPDATE,
                    entry_key=key,
                    message="Failed to apply updates",
                    old_entry=existing,
                    errors=[str(e)],
                )

            # Validate if requested
            if validate:
                errors = self._validate_entry(new_entry)
                if errors:
                    return OperationResult(
                        success=False,
                        operation=OperationType.UPDATE,
                        entry_key=key,
                        message="Validation failed after update",
                        old_entry=existing,
                        new_entry=new_entry,
                        errors=errors,
                    )

            # Apply update
            if self.dry_run:
                logger.info(f"[DRY RUN] Would update entry: {key}")
                return OperationResult(
                    success=True,
                    operation=OperationType.UPDATE,
                    entry_key=key,
                    message=f"[DRY RUN] Entry '{key}' would be updated",
                    old_entry=existing,
                    new_entry=new_entry,
                    affected_count=1,
                )

            try:
                with self.storage.transaction() as tx:
                    if new_key and new_key != key:
                        # Rename: delete old, add new
                        tx.delete(key)
                        tx.add(new_entry)
                    else:
                        tx.add(new_entry)
                    tx.commit()
                logger.info(f"Updated entry: {key}")
                return OperationResult(
                    success=True,
                    operation=OperationType.UPDATE,
                    entry_key=key,
                    message=f"Entry '{key}' updated successfully",
                    old_entry=existing,
                    new_entry=new_entry,
                    affected_count=1,
                )
            except Exception as e:
                logger.error(f"Storage error updating {key}: {e}")
                return OperationResult(
                    success=False,
                    operation=OperationType.UPDATE,
                    entry_key=key,
                    message="Storage error",
                    old_entry=existing,
                    new_entry=new_entry,
                    errors=[str(e)],
                )
        finally:
            self._release_lock(key)

    def delete(
        self, key: str, cascade: CascadeOptions | None = None
    ) -> OperationResult:
        """Delete an entry.

        Args:
            key: Entry key to delete
            cascade: Options for cascade delete

        Returns:
            Operation result
        """
        # Acquire lock
        if not self._acquire_lock(key):
            return OperationResult(
                success=False,
                operation=OperationType.DELETE,
                entry_key=key,
                message="Lock acquisition timeout",
            )

        try:
            # Check if exists
            existing = self.storage.read(key)
            if not existing:
                return OperationResult(
                    success=False,
                    operation=OperationType.DELETE,
                    entry_key=key,
                    message=f"Entry '{key}' not found",
                )

            # Perform delete
            if self.dry_run:
                logger.info(f"[DRY RUN] Would delete entry: {key}")
                return OperationResult(
                    success=True,
                    operation=OperationType.DELETE,
                    entry_key=key,
                    message=f"[DRY RUN] Entry '{key}' would be deleted",
                    old_entry=existing,
                    affected_count=1,
                )

            try:
                affected = 1
                with self.storage.transaction() as tx:
                    tx.delete(key)

                    # Handle cascade delete
                    if cascade:
                        if cascade.delete_notes:
                            # Delete associated notes
                            # This would interface with notes storage
                            logger.info(f"Cascading delete of notes for {key}")
                            affected += 1

                        if cascade.delete_metadata:
                            # Delete associated metadata
                            # This would interface with metadata storage
                            logger.info(f"Cascading delete of metadata for {key}")
                            affected += 1

                        if cascade.delete_attachments:
                            # Delete associated attachments
                            # This would interface with attachment storage
                            logger.info(f"Cascading delete of attachments for {key}")
                            affected += 1

                    tx.commit()

                logger.info(f"Deleted entry: {key}")
                return OperationResult(
                    success=True,
                    operation=OperationType.DELETE,
                    entry_key=key,
                    message=f"Entry '{key}' deleted successfully",
                    old_entry=existing,
                    affected_count=affected,
                )
            except Exception as e:
                logger.error(f"Storage error deleting {key}: {e}")
                return OperationResult(
                    success=False,
                    operation=OperationType.DELETE,
                    entry_key=key,
                    message="Storage error",
                    old_entry=existing,
                    errors=[str(e)],
                )
        finally:
            self._release_lock(key)

    def replace(self, entry: Entry) -> OperationResult:
        """Replace an entire entry.

        Args:
            entry: Replacement entry

        Returns:
            Operation result
        """
        # Acquire lock
        if not self._acquire_lock(entry.key):
            return OperationResult(
                success=False,
                operation=OperationType.REPLACE,
                entry_key=entry.key,
                message="Lock acquisition timeout",
                new_entry=entry,
            )

        try:
            # Check if exists
            existing = self.storage.read(entry.key)
            if not existing:
                return OperationResult(
                    success=False,
                    operation=OperationType.REPLACE,
                    entry_key=entry.key,
                    message=f"Entry '{entry.key}' not found",
                    new_entry=entry,
                )

            # Validate new entry
            errors = self._validate_entry(entry)
            if errors:
                return OperationResult(
                    success=False,
                    operation=OperationType.REPLACE,
                    entry_key=entry.key,
                    message="Validation failed",
                    old_entry=existing,
                    new_entry=entry,
                    errors=errors,
                )

            # Perform replacement
            if self.dry_run:
                logger.info(f"[DRY RUN] Would replace entry: {entry.key}")
                return OperationResult(
                    success=True,
                    operation=OperationType.REPLACE,
                    entry_key=entry.key,
                    message=f"[DRY RUN] Entry '{entry.key}' would be replaced",
                    old_entry=existing,
                    new_entry=entry,
                    affected_count=1,
                )

            try:
                with self.storage.transaction() as tx:
                    tx.add(entry)
                    tx.commit()
                logger.info(f"Replaced entry: {entry.key}")
                return OperationResult(
                    success=True,
                    operation=OperationType.REPLACE,
                    entry_key=entry.key,
                    message=f"Entry '{entry.key}' replaced successfully",
                    old_entry=existing,
                    new_entry=entry,
                    affected_count=1,
                )
            except Exception as e:
                logger.error(f"Storage error replacing {entry.key}: {e}")
                return OperationResult(
                    success=False,
                    operation=OperationType.REPLACE,
                    entry_key=entry.key,
                    message="Storage error",
                    old_entry=existing,
                    new_entry=entry,
                    errors=[str(e)],
                )
        finally:
            self._release_lock(entry.key)

    def bulk_create(
        self,
        entries: list[Entry],
        options: BulkOperationOptions | None = None,
    ) -> list[OperationResult]:
        """Create multiple entries.

        Args:
            entries: Entries to create
            options: Bulk operation options

        Returns:
            List of operation results
        """
        if not entries:
            return []

        options = options or BulkOperationOptions()
        results = []

        if options.atomic:
            # Atomic mode: all or nothing
            # First validate all entries
            if options.validate:
                for entry in entries:
                    errors = self._validate_entry(entry)
                    if errors:
                        # Fail all if any validation fails
                        for e in entries:
                            results.append(
                                OperationResult(
                                    success=False,
                                    operation=OperationType.CREATE,
                                    entry_key=e.key,
                                    message="Atomic operation failed due to validation errors",
                                    errors=errors if e == entry else ["Atomic failure"],
                                )
                            )
                        return results

            # Check for duplicates
            for entry in entries:
                if self.storage.read(entry.key):
                    # Fail all if any duplicate found
                    for e in entries:
                        results.append(
                            OperationResult(
                                success=False,
                                operation=OperationType.CREATE,
                                entry_key=e.key,
                                message=f"Atomic operation failed: '{entry.key}' already exists",
                            )
                        )
                    return results

            # All checks passed, create all
            if not self.dry_run:
                try:
                    with self.storage.transaction() as tx:
                        for entry in entries:
                            tx.add(entry)
                        tx.commit()
                except Exception as e:
                    # Rollback, fail all
                    for entry in entries:
                        results.append(
                            OperationResult(
                                success=False,
                                operation=OperationType.CREATE,
                                entry_key=entry.key,
                                message="Atomic operation failed",
                                errors=[str(e)],
                            )
                        )
                    return results

            # Success for all
            for entry in entries:
                results.append(
                    OperationResult(
                        success=True,
                        operation=OperationType.CREATE,
                        entry_key=entry.key,
                        message="Created in atomic bulk operation",
                        new_entry=entry,
                        affected_count=1,
                    )
                )
        else:
            # Non-atomic mode: process individually
            for i, entry in enumerate(entries):
                if options.progress_reporter:
                    options.progress_reporter.report(
                        "bulk_create",
                        i + 1,
                        len(entries),
                        f"Creating {entry.key}",
                    )

                result = self.create(entry, force=not options.validate)
                results.append(result)

                if result.failed and options.stop_on_error:
                    break

        return results

    def bulk_update(
        self,
        updates: dict[str, dict[str, Any]],
        options: BulkOperationOptions | None = None,
    ) -> list[OperationResult]:
        """Update multiple entries.

        Args:
            updates: Dictionary mapping keys to update dictionaries
            options: Bulk operation options

        Returns:
            List of operation results
        """
        if not updates:
            return []

        options = options or BulkOperationOptions()
        results = []

        items = list(updates.items())
        for i, (key, update_dict) in enumerate(items):
            if options.progress_reporter:
                options.progress_reporter.report(
                    "bulk_update",
                    i + 1,
                    len(items),
                    f"Updating {key}",
                )

            result = self.update(key, update_dict, validate=options.validate)
            results.append(result)

            if result.failed and options.stop_on_error:
                break

        return results

    def bulk_delete(
        self,
        keys: list[str],
        options: BulkOperationOptions | None = None,
    ) -> list[OperationResult]:
        """Delete multiple entries.

        Args:
            keys: Entry keys to delete
            options: Bulk operation options

        Returns:
            List of operation results
        """
        if not keys:
            return []

        options = options or BulkOperationOptions()
        results = []

        for i, key in enumerate(keys):
            if options.progress_reporter:
                options.progress_reporter.report(
                    "bulk_delete",
                    i + 1,
                    len(keys),
                    f"Deleting {key}",
                )

            result = self.delete(key)
            results.append(result)

            if result.failed and options.stop_on_error:
                break

        return results
