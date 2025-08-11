"""Create command for bibliography entries."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from bibmgr.core.models import Entry
from bibmgr.storage.events import Event, EventBus, EventType
from bibmgr.storage.repository import EntryRepository

from ..results import OperationResult, ResultStatus
from ..validators.preconditions import CreatePreconditions


@dataclass
class CreateCommand:
    """Command to create a new entry."""

    entry: Entry | None
    force: bool = False
    dry_run: bool = False
    metadata: dict[str, Any] | None = None


class CreateHandler:
    """Handles entry creation with validation and events."""

    def __init__(
        self,
        repository: EntryRepository,
        event_bus: EventBus,
        naming_policy=None,
    ):
        self.repository = repository
        self.event_bus = event_bus
        self.naming_policy = naming_policy
        self.preconditions = CreatePreconditions()

    def execute(self, command: CreateCommand) -> OperationResult:
        """Execute create command."""
        if not command.force:
            violations = self.preconditions.check(command)
            if violations:
                return OperationResult(
                    status=ResultStatus.VALIDATION_FAILED,
                    entity_id=command.entry.key if command.entry else None,
                    errors=violations,
                    message="Entry validation failed",
                )

        if command.entry is None:
            return OperationResult(
                status=ResultStatus.VALIDATION_FAILED,
                entity_id=None,
                errors=["Entry cannot be None"],
                message="Entry validation failed",
            )

        if self.repository.exists(command.entry.key):
            new_key = None
            if self.naming_policy:
                new_key = self.naming_policy.generate_alternative(
                    command.entry.key, self.repository
                )

            return OperationResult(
                status=ResultStatus.CONFLICT,
                entity_id=command.entry.key,
                message="Entry already exists",
                suggestions={"alternative_key": new_key} if new_key else None,
            )

        validation_errors = command.entry.validate()
        if validation_errors and not command.force:
            return OperationResult(
                status=ResultStatus.VALIDATION_FAILED,
                entity_id=command.entry.key,
                validation_errors=validation_errors,
                message="Entry validation failed",
            )

        if command.dry_run:
            return OperationResult(
                status=ResultStatus.DRY_RUN,
                entity_id=command.entry.key,
                message="Entry would be created",
                data={"entry": command.entry},
            )

        try:
            self.repository.save(command.entry, skip_validation=command.force)

            event = Event(
                type=EventType.ENTRY_CREATED,
                timestamp=datetime.now(),
                data={
                    "entry": command.entry,
                    "entry_key": command.entry.key,
                    "metadata": command.metadata,
                },
            )
            self.event_bus.publish(event)

            return OperationResult(
                status=ResultStatus.SUCCESS,
                entity_id=command.entry.key,
                message="Entry created successfully",
                data={"entry": command.entry},
            )

        except Exception as e:
            return OperationResult(
                status=ResultStatus.ERROR,
                entity_id=command.entry.key,
                message="Failed to create entry",
                errors=[str(e)],
            )


class BulkCreateHandler:
    """Handles bulk creation with transactions and progress tracking."""

    def __init__(
        self,
        repository: EntryRepository,
        event_bus: EventBus,
        create_handler: CreateHandler,
    ):
        self.repository = repository
        self.event_bus = event_bus
        self.create_handler = create_handler

    def execute(
        self,
        entries: list[Entry],
        atomic: bool = False,
        stop_on_error: bool = False,
        dry_run: bool = False,
    ) -> list[OperationResult]:
        """Execute bulk create with transaction support."""
        results = []

        if atomic and not dry_run:
            if hasattr(self.repository, "__class__") and hasattr(
                self.repository.__class__, "__module__"
            ):
                temp_results = []
                saved_entries = []

                try:
                    for entry in entries:
                        command = CreateCommand(entry=entry, dry_run=False)
                        result = self.create_handler.execute(command)

                        if result.status != ResultStatus.SUCCESS:
                            for saved_key in saved_entries:
                                try:
                                    self.repository.delete(saved_key)
                                except Exception:
                                    pass

                            return [
                                OperationResult(
                                    status=ResultStatus.TRANSACTION_FAILED,
                                    entity_id=e.key,
                                    message=f"Atomic operation failed due to: {entry.key}",
                                )
                                for e in entries
                            ]

                        saved_entries.append(entry.key)
                        temp_results.append(result)

                    results.extend(temp_results)

                    event = Event(
                        type=EventType.BULK_CREATED,
                        timestamp=datetime.now(),
                        data={
                            "entries": entries,
                            "count": len(entries),
                        },
                    )
                    self.event_bus.publish(event)

                except Exception as e:
                    return [
                        OperationResult(
                            status=ResultStatus.TRANSACTION_FAILED,
                            entity_id=entry.key,
                            message=f"Transaction failed: {str(e)}",
                        )
                        for entry in entries
                    ]

        else:
            for i, entry in enumerate(entries):
                progress_event = Event(
                    type=EventType.PROGRESS,
                    timestamp=datetime.now(),
                    data={
                        "operation": "bulk_create",
                        "current": i + 1,
                        "total": len(entries),
                        "entity_id": entry.key,
                    },
                )
                self.event_bus.publish(progress_event)

                command = CreateCommand(entry=entry, dry_run=dry_run)
                result = self.create_handler.execute(command)
                results.append(result)

                if stop_on_error and result.status != ResultStatus.SUCCESS:
                    break

        return results
