"""JSON format importer for data exchange."""

import json
from pathlib import Path
from typing import Any

from bibmgr.core.models import Entry, EntryType
from bibmgr.core.validators import ValidatorRegistry


class JsonImporter:
    """Import entries from JSON format."""

    def __init__(self, validate: bool = True):
        self.validate = validate
        self.validator_registry = ValidatorRegistry()

    def import_file(self, path: Path) -> tuple[list[Entry], list[str]]:
        """Import from JSON file."""
        try:
            with open(path) as f:
                data = json.load(f)

            if isinstance(data, list):
                return self._import_entries(data)
            elif isinstance(data, dict) and "entries" in data:
                return self._import_entries(data["entries"])
            else:
                return [], [
                    "Invalid JSON format: expected array or object with 'entries'"
                ]

        except json.JSONDecodeError as e:
            return [], [f"Invalid JSON: {e}"]
        except Exception as e:
            return [], [f"Failed to read file: {e}"]

    def _import_entries(
        self, data: list[dict[str, Any]]
    ) -> tuple[list[Entry], list[str]]:
        """Import list of entry dictionaries."""
        entries = []
        errors = []

        for i, entry_data in enumerate(data):
            try:
                if "key" not in entry_data:
                    errors.append(f"Entry {i}: missing 'key' field")
                    continue

                if "type" not in entry_data:
                    entry_data["type"] = "misc"

                if isinstance(entry_data["type"], str):
                    try:
                        entry_data["type"] = EntryType(entry_data["type"].lower())
                    except ValueError:
                        errors.append(
                            f"Entry {entry_data['key']}: invalid type '{entry_data['type']}'"
                        )
                        continue

                entry = Entry.from_dict(entry_data)

                if self.validate:
                    validation_errors = self.validator_registry.validate(entry)
                    error_messages = [
                        e.message for e in validation_errors if e.severity == "error"
                    ]

                    if error_messages:
                        errors.append(
                            f"Entry {entry.key}: " + "; ".join(error_messages)
                        )
                        continue

                entries.append(entry)

            except Exception as e:
                errors.append(f"Entry {i}: {e}")

        return entries, errors

    def export_entries(self, entries: list[Entry], path: Path) -> None:
        """Export entries to JSON format."""
        data = {"version": "1.0", "entries": [entry.to_dict() for entry in entries]}

        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
