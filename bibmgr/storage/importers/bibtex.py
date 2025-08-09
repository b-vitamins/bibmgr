"""BibTeX importer using the core module's parser."""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from bibmgr.core.bibtex import BibtexDecoder
from bibmgr.core.models import Entry
from bibmgr.core.validators import ValidatorRegistry

if TYPE_CHECKING:
    from . import ImportStrategy


class BibtexImporter:
    """Import entries from BibTeX format."""

    def __init__(
        self, validate: bool = True, strategy: Optional["ImportStrategy"] = None
    ):
        from . import ImportStrategy

        self.validate = validate
        self.strategy = strategy if strategy is not None else ImportStrategy.OVERWRITE
        self.decoder = BibtexDecoder()
        self.validator_registry = ValidatorRegistry()

    def import_file(self, path: Path) -> tuple[list[Entry], list[str]]:
        """Import from BibTeX file.

        Returns:
            Tuple of (entries, errors)
        """
        try:
            content = path.read_text(encoding="utf-8")
            return self.import_text(content)
        except Exception as e:
            return [], [f"Failed to read file: {e}"]

    def import_text(self, text: str) -> tuple[list[Entry], list[str]]:
        """Import from BibTeX text.

        Returns:
            Tuple of (entries, errors)
        """
        from . import ImportStrategy

        entries = []
        errors = []
        seen_keys: dict[str, Entry] = {}

        try:
            entry_dicts = self.decoder.decode(text)

            for entry_dict in entry_dicts:
                try:
                    entry = Entry.from_dict(entry_dict)

                    if self.validate:
                        validation_errors = self.validator_registry.validate(entry)

                        error_messages = [
                            e.message
                            for e in validation_errors
                            if e.severity == "error"
                        ]

                        if error_messages:
                            errors.append(
                                f"Entry {entry.key}: " + "; ".join(error_messages)
                            )
                            continue

                    if entry.key in seen_keys:
                        if self.strategy == ImportStrategy.SKIP_DUPLICATES:
                            errors.append(f"Entry {entry.key}: Skipped duplicate")
                            continue
                        elif self.strategy == ImportStrategy.OVERWRITE:
                            entries = [e for e in entries if e.key != entry.key]
                            entries.append(entry)
                            seen_keys[entry.key] = entry
                        elif self.strategy == ImportStrategy.RENAME_DUPLICATES:
                            original_key = entry.key
                            counter = 1
                            while f"{original_key}_{counter}" in seen_keys:
                                counter += 1

                            entry_dict = entry.to_dict()
                            entry_dict["key"] = f"{original_key}_{counter}"
                            renamed_entry = Entry.from_dict(entry_dict)

                            entries.append(renamed_entry)
                            seen_keys[renamed_entry.key] = renamed_entry
                        elif self.strategy == ImportStrategy.MERGE_DUPLICATES:
                            existing = seen_keys[entry.key]
                            merged_dict = existing.to_dict()
                            new_dict = entry.to_dict()

                            for field, value in new_dict.items():
                                if value is not None and field not in [
                                    "added",
                                    "modified",
                                ]:
                                    merged_dict[field] = value

                            merged_entry = Entry.from_dict(merged_dict)
                            entries = [
                                e if e.key != entry.key else merged_entry
                                for e in entries
                            ]
                            seen_keys[entry.key] = merged_entry
                    else:
                        entries.append(entry)
                        seen_keys[entry.key] = entry

                except Exception as e:
                    entry_key = entry_dict.get("key", "unknown")
                    errors.append(f"Entry {entry_key}: Failed to process - {e}")

        except Exception as e:
            errors.append(f"Failed to parse BibTeX: {e}")

        return entries, errors

    def import_batch(self, paths: list[Path]) -> tuple[list[Entry], list[str]]:
        """Import from multiple files."""
        all_entries = []
        all_errors = []

        for path in paths:
            entries, errors = self.import_file(path)
            all_entries.extend(entries)
            all_errors.extend(errors)

        return all_entries, all_errors

    def export_entries(self, entries: list[Entry], path: Path) -> None:
        """Export entries to BibTeX format."""
        from bibmgr.core.bibtex import BibtexEncoder

        encoder = BibtexEncoder()

        bibtex_entries = []
        for entry in entries:
            bibtex_entries.append(encoder.encode_entry(entry))

        bibtex_content = "\n\n".join(bibtex_entries)

        with open(path, "w", encoding="utf-8") as f:
            f.write(bibtex_content)
