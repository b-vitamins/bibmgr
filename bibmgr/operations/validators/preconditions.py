"""Precondition validators for operations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class Precondition(Protocol):
    """Protocol for precondition checks."""

    def check(self, context: Any) -> list[str]:
        """Check precondition and return violations."""
        ...


@dataclass
class CreatePreconditions:
    """Preconditions for create operations."""

    def check(self, command: Any) -> list[str]:
        """Check create preconditions."""
        violations = []

        if not command.entry:
            violations.append("Entry cannot be None")
            return violations

        if not command.entry.key:
            violations.append("Entry key is required")

        if not command.entry.type:
            violations.append("Entry type is required")

        return violations


@dataclass
class UpdatePreconditions:
    """Preconditions for update operations."""

    def check(self, command: Any) -> list[str]:
        """Check update preconditions."""
        violations = []

        if not command.key:
            violations.append("Entry key is required")

        if not command.updates:
            violations.append("No updates provided")

        protected_fields = {"key", "added"}
        for field in protected_fields:
            if field in command.updates:
                violations.append(f"Cannot update protected field: {field}")

        return violations


@dataclass
class DeletePreconditions:
    """Preconditions for delete operations."""

    def check(self, command: Any) -> list[str]:
        """Check delete preconditions."""
        violations = []

        if not command.key:
            violations.append("Entry key is required")

        return violations


@dataclass
class MergePreconditions:
    """Preconditions for merge operations."""

    def check(self, command: Any) -> list[str]:
        """Check merge preconditions."""
        violations = []

        if not command.source_keys:
            violations.append("No source keys provided")
        elif len(command.source_keys) < 2:
            violations.append("At least 2 entries required for merge")

        if len(set(command.source_keys)) != len(command.source_keys):
            violations.append("Duplicate keys in source list")

        return violations


@dataclass
class ImportPreconditions:
    """Preconditions for import operations."""

    def check(self, context: dict[str, Any]) -> list[str]:
        """Check import preconditions."""
        violations = []

        source = context.get("source")
        if not source:
            violations.append("Import source is required")
            return violations

        path = Path(source)
        if not path.exists():
            violations.append(f"Import file does not exist: {source}")

        elif not path.is_file():
            violations.append(f"Import source is not a file: {source}")

        elif path.stat().st_size == 0:
            violations.append(f"Import file is empty: {source}")

        return violations


class ValidatorChain:
    """Chain multiple validators together."""

    def __init__(self, validators: list[Precondition]):
        self.validators = validators

    def check(self, context: Any) -> list[str]:
        """Run all validators and collect violations."""
        all_violations = []
        for validator in self.validators:
            violations = validator.check(context)
            all_violations.extend(violations)
        return all_violations


class OperationValidator:
    """Main validator for operations."""

    def validate_preconditions(self, command: Any) -> bool:
        """Validate preconditions for a command."""
        validator_map = {
            "CreateCommand": CreatePreconditions(),
            "UpdateCommand": UpdatePreconditions(),
            "DeleteCommand": DeletePreconditions(),
            "MergeCommand": MergePreconditions(),
        }

        command_type = command.__class__.__name__
        validator = validator_map.get(command_type)

        if validator:
            violations = validator.check(command)
            return len(violations) == 0

        return True

    def validate_postconditions(
        self, command: Any, result: Any, context: dict[str, Any]
    ) -> bool:
        """Validate postconditions after operation."""
        return True
