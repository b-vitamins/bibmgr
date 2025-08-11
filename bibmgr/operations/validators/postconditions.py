"""Postcondition validators for operations."""

from dataclasses import dataclass
from typing import Any, Protocol


class Postcondition(Protocol):
    """Protocol for postcondition checks."""

    def check(self, context: dict[str, Any]) -> list[str]:
        """Check postcondition and return violations."""
        ...


@dataclass
class CreatePostconditions:
    """Postconditions for create operations."""

    def check(self, context: dict[str, Any]) -> list[str]:
        """Check create postconditions."""
        violations = []

        entry = context.get("entry")
        repository = context.get("repository")

        if not entry or not repository:
            violations.append("Missing required context for postcondition check")
            return violations

        saved_entry = repository.find(entry.key)
        if not saved_entry:
            violations.append(f"Entry {entry.key} not found in repository after create")

        elif saved_entry.to_dict() != entry.to_dict():
            violations.append("Saved entry differs from created entry")

        return violations


@dataclass
class UpdatePostconditions:
    """Postconditions for update operations."""

    def check(self, context: dict[str, Any]) -> list[str]:
        """Check update postconditions."""
        violations = []

        key = context.get("key")
        updates = context.get("updates", {})
        repository = context.get("repository")

        if not key or not repository:
            violations.append("Missing required context for postcondition check")
            return violations

        updated_entry = repository.find(key)
        if not updated_entry:
            violations.append(f"Entry {key} not found after update")
            return violations

        entry_dict = updated_entry.to_dict()
        for field, expected_value in updates.items():
            if expected_value is None:
                if field in entry_dict:
                    violations.append(f"Field {field} was not removed")
            else:
                actual_value = entry_dict.get(field)
                if actual_value != expected_value:
                    violations.append(
                        f"Field {field} has value {actual_value}, expected {expected_value}"
                    )

        return violations


@dataclass
class DeletePostconditions:
    """Postconditions for delete operations."""

    def check(self, context: dict[str, Any]) -> list[str]:
        """Check delete postconditions."""
        violations = []

        key = context.get("key")
        repository = context.get("repository")

        if not key or not repository:
            violations.append("Missing required context for postcondition check")
            return violations

        if repository.exists(key):
            violations.append(f"Entry {key} still exists after delete")

        return violations


@dataclass
class MergePostconditions:
    """Postconditions for merge operations."""

    def check(self, context: dict[str, Any]) -> list[str]:
        """Check merge postconditions."""
        violations = []

        source_keys = context.get("source_keys", [])
        target_key = context.get("target_key")
        delete_sources = context.get("delete_sources", True)
        repository = context.get("repository")

        if not source_keys or not target_key or not repository:
            violations.append("Missing required context for postcondition check")
            return violations

        if not repository.exists(target_key):
            violations.append(f"Target entry {target_key} not found after merge")

        if delete_sources:
            for key in source_keys:
                if key != target_key and repository.exists(key):
                    violations.append(
                        f"Source entry {key} still exists after merge with delete_sources=True"
                    )

        return violations
