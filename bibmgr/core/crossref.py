"""Cross-reference resolution system for BibTeX entries.

This module implements BibTeX cross-reference resolution, where entries
can inherit fields from other entries they reference. According to
TameTheBeast, cross-referenced entries must be defined after entries
containing the corresponding crossref field.

Key functionality:
- Field inheritance from parent entries
- Special handling for title->booktitle inheritance
- Entry ordering validation
- Minimum crossref count for parent inclusion
"""

from .fields import EntryType
from .models import Entry


class CrossRefResolver:
    """Resolve cross-references between bibliography entries.

    Handles field inheritance from parent entries and validates proper
    ordering of cross-referenced entries according to BibTeX rules.
    """

    def __init__(self, entries: dict[str, Entry], min_crossrefs: int = 2):
        """Initialize resolver with entries and minimum crossref threshold.

        Args:
            entries: Dictionary mapping entry keys to Entry objects.
            min_crossrefs: Minimum times an entry must be referenced to
                          be included as a parent (default: 2).
        """
        self.entries = entries
        self.min_crossrefs = min_crossrefs
        self.crossref_counts: dict[str, int] = {}
        self._count_crossrefs()

    def _count_crossrefs(self):
        """Count how many times each entry is cross-referenced."""
        for entry in self.entries.values():
            if entry.crossref:
                self.crossref_counts[entry.crossref] = (
                    self.crossref_counts.get(entry.crossref, 0) + 1
                )

    def should_include_parent(self, parent_key: str) -> bool:
        """Check if parent should be included based on crossref count."""
        return self.crossref_counts.get(parent_key, 0) >= self.min_crossrefs

    def resolve_entry(self, entry: Entry) -> Entry:
        """Resolve cross-references for a single entry.

        Inherits fields from the parent entry according to BibTeX rules.
        Child fields take precedence over inherited parent fields.

        Args:
            entry: Entry to resolve cross-references for.

        Returns:
            Entry with inherited fields from parent, or original if no parent.
        """
        if not entry.crossref or entry.crossref not in self.entries:
            return entry

        if entry.crossref == entry.key:
            return entry

        parent = self.entries[entry.crossref]

        inheritable_fields = {
            "booktitle",
            "editor",
            "publisher",
            "year",
            "series",
            "volume",
            "number",
            "organization",
            "address",
            "month",
        }

        updates = {}

        if parent.type in [EntryType.BOOK, EntryType.PROCEEDINGS] and entry.type in [
            EntryType.INBOOK,
            EntryType.INCOLLECTION,
            EntryType.INPROCEEDINGS,
        ]:
            if not entry.booktitle and parent.title:
                updates["booktitle"] = parent.title

        for field in inheritable_fields:
            if field == "booktitle":
                continue

            child_value = getattr(entry, field, None)
            parent_value = getattr(parent, field, None)

            if parent_value and not child_value:
                updates[field] = parent_value

        if updates:
            import msgspec

            return msgspec.structs.replace(entry, **updates)

        return entry

    def validate_order(self) -> list[tuple[str, str]]:
        """Validate that cross-referenced entries come before their targets.

        According to TameTheBeast: "cross-referenced entries must be defined
        after entries containing the corresponding crossref field". This means
        entries with crossref must appear BEFORE the entries they reference.

        Returns:
            List of (citing_key, cited_key) tuples for ordering violations.
        """
        violations = []
        seen = set()

        for key, entry in self.entries.items():
            if entry.crossref:
                if entry.crossref in self.entries:
                    if entry.crossref in seen:
                        violations.append((key, entry.crossref))
                else:
                    violations.append((key, entry.crossref))

            seen.add(key)

        return violations
