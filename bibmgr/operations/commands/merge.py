"""Merge command for handling duplicates."""

from dataclasses import dataclass
from typing import Any

from bibmgr.core.duplicates import DuplicateDetector
from bibmgr.storage.events import EventBus, EventType
from bibmgr.storage.repository import EntryRepository

from ..policies.merge import MergePolicy, MergeStrategy
from ..results import OperationResult, ResultStatus
from ..validators.preconditions import MergePreconditions


@dataclass
class MergeCommand:
    """Command to merge duplicate entries."""

    source_keys: list[str]
    target_key: str | None = None
    strategy: str = "SMART"
    custom_rules: dict[str, Any] | None = None
    delete_sources: bool = True


class MergeHandler:
    """Handles entry merging with configurable strategies."""

    def __init__(
        self,
        repository: EntryRepository,
        event_bus: EventBus,
        merge_policy=None,
    ):
        self.repository = repository
        self.event_bus = event_bus
        self.merge_policy = merge_policy or MergePolicy()
        self.preconditions = MergePreconditions()

    def execute(self, command: MergeCommand) -> OperationResult:
        """Execute merge operation."""
        violations = self.preconditions.check(command)
        if violations:
            return OperationResult(
                status=ResultStatus.VALIDATION_FAILED,
                message="Precondition validation failed",
                errors=violations,
            )

        source_entries = []
        for key in command.source_keys:
            entry = self.repository.find(key)
            if not entry:
                return OperationResult(
                    status=ResultStatus.NOT_FOUND,
                    entity_id=key,
                    message=f"Source entry not found: {key}",
                )
            source_entries.append(entry)

        if len(source_entries) < 2:
            return OperationResult(
                status=ResultStatus.VALIDATION_FAILED,
                message="At least 2 entries required for merge",
            )

        if command.target_key:
            target_entry = self.repository.find(command.target_key)
            if target_entry and target_entry.key not in command.source_keys:
                return OperationResult(
                    status=ResultStatus.CONFLICT,
                    entity_id=command.target_key,
                    message="Target key already exists",
                )
        else:
            if self.merge_policy:
                command.target_key = self.merge_policy.select_target_key(source_entries)
            else:
                command.target_key = source_entries[0].key

        try:
            strategy = MergeStrategy.SMART
            if hasattr(MergeStrategy, command.strategy):
                strategy = MergeStrategy[command.strategy]

            if strategy == MergeStrategy.CUSTOM and command.custom_rules:
                from ..policies.merge import FieldMergeRule, MergePolicy

                custom_policy = MergePolicy()

                if (
                    "prefer_field" in command.custom_rules
                    and "prefer_value" in command.custom_rules
                ):
                    field = command.custom_rules["prefer_field"]
                    prefer = command.custom_rules["prefer_value"]

                    if prefer == "newest" and field == "year":

                        def newest_year_merger(values):
                            return max(v for v in values if v is not None)

                        custom_policy.field_rules[field] = FieldMergeRule(
                            field, MergeStrategy.CUSTOM, newest_year_merger
                        )

                merged_entry = custom_policy.merge_entries(
                    entries=source_entries,
                    target_key=command.target_key,
                    strategy=MergeStrategy.SMART,
                )
            else:
                merged_entry = self.merge_policy.merge_entries(
                    entries=source_entries,
                    target_key=command.target_key,
                    strategy=strategy,
                )

            validation_errors = merged_entry.validate()
            if validation_errors:
                if self.merge_policy:
                    merged_entry = self.merge_policy.fix_validation_errors(
                        merged_entry, validation_errors
                    )
                    validation_errors = merged_entry.validate()

                if validation_errors:
                    return OperationResult(
                        status=ResultStatus.VALIDATION_FAILED,
                        entity_id=command.target_key,
                        message="Merged entry validation failed",
                        validation_errors=validation_errors,
                    )

            if hasattr(self.repository, "transaction"):
                ctx_manager = self.repository.transaction()  # type: ignore
            else:
                from contextlib import nullcontext

                ctx_manager = nullcontext()

            with ctx_manager:
                self.repository.save(merged_entry)

                deleted_keys = []
                if command.delete_sources:
                    for entry in source_entries:
                        if entry.key != merged_entry.key:
                            self.repository.delete(entry.key)
                            deleted_keys.append(entry.key)

                from datetime import datetime

                from bibmgr.storage.events import Event

                event = Event(
                    type=EventType.ENTRIES_MERGED,
                    timestamp=datetime.now(),
                    data={
                        "source_entries": source_entries,
                        "source_keys": command.source_keys,
                        "merged_entry": merged_entry,
                        "target_key": command.target_key,
                        "strategy": command.strategy,
                    },
                )
                self.event_bus.publish(event)

                return OperationResult(
                    status=ResultStatus.SUCCESS,
                    entity_id=merged_entry.key,
                    message=f"Merged {len(source_entries)} entries",
                    data={
                        "merged_entry": merged_entry,
                        "source_keys": command.source_keys,
                        "deleted_keys": deleted_keys,
                    },
                )

        except Exception as e:
            return OperationResult(
                status=ResultStatus.ERROR,
                message="Failed to merge entries",
                errors=[str(e)],
            )


class AutoMergeHandler:
    """Automatically detect and merge duplicates."""

    def __init__(
        self,
        repository: EntryRepository,
        merge_handler: MergeHandler,
        duplicate_detector: DuplicateDetector | None = None,
    ):
        self.repository = repository
        self.merge_handler = merge_handler
        self.duplicate_detector = duplicate_detector

    def execute(
        self,
        min_similarity: float = 0.85,
        strategy: str = "SMART",
        dry_run: bool = False,
    ) -> list[OperationResult]:
        """Find and merge all duplicates."""
        all_entries = self.repository.find_all()

        if not self.duplicate_detector:
            self.duplicate_detector = DuplicateDetector(all_entries)

        duplicate_groups = self.duplicate_detector.find_duplicates()

        results = []
        for group in duplicate_groups:
            if dry_run:
                results.append(
                    OperationResult(
                        status=ResultStatus.DRY_RUN,
                        message=f"Would merge {len(group)} entries",
                        data={"entries": [e.key for e in group]},
                    )
                )
            else:
                command = MergeCommand(
                    source_keys=[e.key for e in group], strategy=strategy
                )
                result = self.merge_handler.execute(command)
                results.append(result)

        return results
