"""Update command with field-level tracking."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from bibmgr.core.models import Entry
from bibmgr.storage.events import EventBus, EventType
from bibmgr.storage.repository import EntryRepository

from ..results import OperationResult, ResultStatus
from ..validators.preconditions import UpdatePreconditions


@dataclass
class UpdateCommand:
    """Command to update an entry."""

    key: str
    updates: dict[str, Any]
    validate: bool = True
    create_if_missing: bool = False
    track_changes: bool = True


@dataclass
class FieldChange:
    """Represents a field-level change."""

    field: str
    old_value: Any
    new_value: Any
    timestamp: datetime


class UpdateHandler:
    """Handles entry updates with change tracking."""

    def __init__(self, repository: EntryRepository, event_bus: EventBus):
        self.repository = repository
        self.event_bus = event_bus
        self.preconditions = UpdatePreconditions()

    def execute(self, command: UpdateCommand) -> OperationResult:
        """Execute update command."""
        violations = self.preconditions.check(command)
        if violations:
            return OperationResult(
                status=ResultStatus.VALIDATION_FAILED,
                entity_id=command.key,
                errors=violations,
                message="Precondition validation failed",
            )

        existing = self.repository.find(command.key)
        if not existing:
            if command.create_if_missing:
                from .create import CreateCommand, CreateHandler

                entry_data = {"key": command.key}
                entry_data.update(command.updates)

                try:
                    new_entry = Entry.from_dict(entry_data)
                    create_handler = CreateHandler(self.repository, self.event_bus)
                    create_command = CreateCommand(entry=new_entry)
                    return create_handler.execute(create_command)
                except Exception as e:
                    return OperationResult(
                        status=ResultStatus.ERROR,
                        entity_id=command.key,
                        message="Failed to create entry from updates",
                        errors=[str(e)],
                    )
            else:
                return OperationResult(
                    status=ResultStatus.NOT_FOUND,
                    entity_id=command.key,
                    message="Entry not found",
                )

        changes = []
        if command.track_changes:
            changes = self._calculate_changes(existing, command.updates)

        try:
            updated_data = existing.to_dict()

            for field, value in command.updates.items():
                if value is None:
                    updated_data.pop(field, None)
                else:
                    updated_data[field] = value

            updated_entry = Entry.from_dict(updated_data)

        except Exception as e:
            error_msg = str(e)
            if "Expected" in error_msg and "got" in error_msg:
                if command.validate:
                    from bibmgr.core.models import ValidationError

                    validation_errors = [
                        ValidationError(
                            field="year" if "year" in error_msg else "unknown",
                            message=error_msg,
                            severity="error",
                            entry_key=command.key,
                        )
                    ]
                    return OperationResult(
                        status=ResultStatus.VALIDATION_FAILED,
                        entity_id=command.key,
                        message="Update validation failed",
                        validation_errors=validation_errors,
                    )
                else:
                    return OperationResult(
                        status=ResultStatus.ERROR,
                        entity_id=command.key,
                        message="Cannot apply update: incompatible type",
                        errors=[str(e)],
                    )
            else:
                return OperationResult(
                    status=ResultStatus.ERROR,
                    entity_id=command.key,
                    message="Failed to apply updates",
                    errors=[str(e)],
                )

        if command.validate:
            validation_errors = updated_entry.validate()
            if validation_errors:
                return OperationResult(
                    status=ResultStatus.VALIDATION_FAILED,
                    entity_id=command.key,
                    validation_errors=validation_errors,
                    message="Validation failed after update",
                )

        try:
            self.repository.save(updated_entry)

            from bibmgr.storage.events import Event

            event = Event(
                type=EventType.ENTRY_UPDATED,
                timestamp=datetime.now(),
                data={
                    "old_entry": existing,
                    "new_entry": updated_entry,
                    "changes": changes,
                    "entry_key": command.key,
                },
            )
            self.event_bus.publish(event)

            return OperationResult(
                status=ResultStatus.SUCCESS,
                entity_id=command.key,
                message="Entry updated successfully",
                data={"entry": updated_entry, "changes": changes},
            )

        except Exception as e:
            return OperationResult(
                status=ResultStatus.ERROR,
                entity_id=command.key,
                message="Failed to save updated entry",
                errors=[str(e)],
            )

    def _calculate_changes(
        self, existing: Entry, updates: dict[str, Any]
    ) -> list[FieldChange]:
        """Calculate field-level changes."""
        changes = []
        existing_dict = existing.to_dict()

        for field, new_value in updates.items():
            old_value = existing_dict.get(field)

            if old_value != new_value:
                changes.append(
                    FieldChange(
                        field=field,
                        old_value=old_value,
                        new_value=new_value,
                        timestamp=datetime.now(),
                    )
                )

        return changes


class PatchHandler:
    """Handles partial updates using JSON Patch format."""

    def __init__(self, update_handler: UpdateHandler):
        self.update_handler = update_handler

    def execute(self, key: str, patches: list[dict[str, Any]]) -> OperationResult:
        """Apply JSON Patch operations."""
        updates = {}

        for patch in patches:
            op = patch.get("op")
            path = patch.get("path", "").lstrip("/")
            value = patch.get("value")

            if op == "add" or op == "replace":
                updates[path] = value
            elif op == "remove":
                updates[path] = None

        command = UpdateCommand(key=key, updates=updates, track_changes=True)

        return self.update_handler.execute(command)
