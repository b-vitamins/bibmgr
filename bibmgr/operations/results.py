"""Result types for operations with rich information."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from bibmgr.core.validators import ValidationError


class ResultStatus(Enum):
    """Status of an operation result."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    VALIDATION_FAILED = "validation_failed"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    ERROR = "error"
    DRY_RUN = "dry_run"
    TRANSACTION_FAILED = "transaction_failed"
    CANCELLED = "cancelled"

    def is_success(self) -> bool:
        """Check if status indicates success."""
        return self in [self.SUCCESS, self.PARTIAL_SUCCESS, self.DRY_RUN]

    def is_failure(self) -> bool:
        """Check if status indicates failure."""
        return not self.is_success()


@dataclass
class OperationResult:
    """Result of a single operation."""

    status: ResultStatus
    message: str
    entity_id: str | None = None
    operation_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.now)

    # Error information
    errors: list[str] | None = None
    validation_errors: list[ValidationError] | None = None

    # Additional data
    data: dict[str, Any] | None = None
    suggestions: dict[str, Any] | None = None
    warnings: list[str] | None = None

    # Performance metrics
    duration_ms: int | None = None

    @property
    def success(self) -> bool:
        """Check if the operation succeeded."""
        return self.status.is_success()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "status": self.status.value,
            "message": self.message,
            "entity_id": self.entity_id,
            "operation_id": str(self.operation_id),
            "timestamp": self.timestamp.isoformat(),
        }

        if self.errors:
            result["errors"] = self.errors

        if self.validation_errors:
            result["validation_errors"] = [
                {"field": e.field, "message": e.message, "severity": e.severity}
                for e in self.validation_errors
            ]

        if self.data:
            result["data"] = self.data

        if self.suggestions:
            result["suggestions"] = self.suggestions

        if self.warnings:
            result["warnings"] = self.warnings

        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms

        return result


@dataclass
class BulkOperationResult:
    """Result of a bulk operation."""

    total: int
    successful: int
    failed: int
    results: list[OperationResult]

    operation_id: UUID = field(default_factory=uuid4)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total == 0:
            return 1.0
        return self.successful / self.total

    @property
    def all_success(self) -> bool:
        """Check if all operations succeeded."""
        return self.failed == 0

    @property
    def partial_success(self) -> bool:
        """Check if some operations succeeded."""
        return self.successful > 0 and self.failed > 0

    def get_failed_results(self) -> list[OperationResult]:
        """Get only failed results."""
        return [r for r in self.results if r.status.is_failure()]

    def get_successful_results(self) -> list[OperationResult]:
        """Get only successful results."""
        return [r for r in self.results if r.status.is_success()]

    def complete(self) -> None:
        """Mark bulk operation as complete."""
        self.completed_at = datetime.now()


@dataclass
class StepResult:
    """Result of a workflow step."""

    step: str
    success: bool
    message: str

    entity_id: str | None = None
    errors: list[str] | None = None
    warnings: list[str] | None = None
    data: dict[str, Any] | None = None

    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: int | None = None


@dataclass
class WorkflowResult:
    """Result of a complete workflow."""

    workflow: str
    steps: list[StepResult] = field(default_factory=list)

    workflow_id: UUID = field(default_factory=uuid4)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    # Metadata
    source: str | None = None
    config: dict[str, Any] | None = None

    @property
    def success(self) -> bool:
        """Check if workflow succeeded."""
        return all(step.success for step in self.steps)

    @property
    def partial_success(self) -> bool:
        """Check if workflow partially succeeded."""
        successes = sum(1 for step in self.steps if step.success)
        return 0 < successes < len(self.steps)

    @property
    def failed_steps(self) -> list[StepResult]:
        """Get failed steps."""
        return [step for step in self.steps if not step.success]

    @property
    def successful_entities(self) -> list[str]:
        """Get IDs of successfully processed entities."""
        return [
            step.entity_id for step in self.steps if step.success and step.entity_id
        ]

    def add_step(self, step: StepResult) -> None:
        """Add a step result."""
        self.steps.append(step)

    def complete(self) -> None:
        """Mark workflow as complete."""
        self.completed_at = datetime.now()

    def get_summary(self) -> dict[str, Any]:
        """Get workflow summary."""
        return {
            "workflow": self.workflow,
            "workflow_id": str(self.workflow_id),
            "success": self.success,
            "total_steps": len(self.steps),
            "successful_steps": sum(1 for s in self.steps if s.success),
            "failed_steps": sum(1 for s in self.steps if not s.success),
            "duration_ms": int(
                (self.completed_at - self.started_at).total_seconds() * 1000
            )
            if self.completed_at
            else None,
            "entities_processed": len(self.successful_entities),
        }


@dataclass
class ProgressUpdate:
    """Progress update for long-running operations."""

    operation: str
    current: int
    total: int
    message: str | None = None
    entity_id: str | None = None

    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total == 0:
            return 100.0
        return (self.current / self.total) * 100

    @property
    def remaining(self) -> int:
        """Calculate remaining items."""
        return max(0, self.total - self.current)
