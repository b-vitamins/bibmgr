"""Merge policies for combining entries."""

from collections.abc import Callable
from enum import Enum
from typing import Any

from bibmgr.core.models import Entry
from bibmgr.core.validators import ValidationError


class MergeStrategy(Enum):
    """Strategy for merging field values."""

    UNION = "union"
    INTERSECTION = "intersection"
    PREFER_FIRST = "prefer_first"
    PREFER_NEWEST = "prefer_newest"
    PREFER_COMPLETE = "prefer_complete"
    SMART = "smart"
    CUSTOM = "custom"


class FieldMergeRule:
    """Rule for merging a specific field."""

    def __init__(
        self,
        field: str,
        strategy: MergeStrategy,
        custom_merger: Callable | None = None,
    ):
        self.field = field
        self.strategy = strategy
        self.custom_merger = custom_merger

    def merge(self, values: list[Any]) -> Any:
        """Merge field values according to strategy."""
        values = [v for v in values if v is not None]

        if not values:
            return None

        if len(values) == 1:
            return values[0]

        if self.strategy == MergeStrategy.PREFER_FIRST:
            return values[0]

        elif self.strategy == MergeStrategy.PREFER_NEWEST:
            return values[-1]

        elif self.strategy == MergeStrategy.PREFER_COMPLETE:
            if isinstance(values[0], str):
                return max(values, key=len)
            elif isinstance(values[0], list):
                return max(values, key=len)
            else:
                return values[0]

        elif self.strategy == MergeStrategy.UNION:
            if isinstance(values[0], list | tuple):
                result = []
                for v in values:
                    result.extend(v)
                return list(dict.fromkeys(result))
            elif isinstance(values[0], str):
                return max(values, key=len)
            else:
                return values[0]

        elif self.strategy == MergeStrategy.INTERSECTION:
            if isinstance(values[0], list | tuple):
                result = set(values[0])
                for v in values[1:]:
                    result &= set(v)
                return list(result)
            else:
                return values[0] if all(v == values[0] for v in values) else None

        elif self.strategy == MergeStrategy.CUSTOM:
            if self.custom_merger:
                return self.custom_merger(values)
            else:
                return values[0]

        else:
            return values[0]


class MergePolicy:
    """Policy for merging entries."""

    def __init__(self):
        self.field_rules = {
            "key": FieldMergeRule("key", MergeStrategy.PREFER_FIRST),
            "doi": FieldMergeRule("doi", MergeStrategy.PREFER_FIRST),
            "author": FieldMergeRule("author", MergeStrategy.SMART),
            "editor": FieldMergeRule("editor", MergeStrategy.SMART),
            "title": FieldMergeRule("title", MergeStrategy.PREFER_COMPLETE),
            "journal": FieldMergeRule("journal", MergeStrategy.PREFER_COMPLETE),
            "booktitle": FieldMergeRule("booktitle", MergeStrategy.PREFER_COMPLETE),
            "publisher": FieldMergeRule("publisher", MergeStrategy.PREFER_COMPLETE),
            "year": FieldMergeRule("year", MergeStrategy.PREFER_FIRST),
            "month": FieldMergeRule("month", MergeStrategy.PREFER_COMPLETE),
            "keywords": FieldMergeRule("keywords", MergeStrategy.UNION),
            "tags": FieldMergeRule("tags", MergeStrategy.UNION),
            "abstract": FieldMergeRule("abstract", MergeStrategy.PREFER_COMPLETE),
            "note": FieldMergeRule("note", MergeStrategy.PREFER_COMPLETE),
            "pages": FieldMergeRule("pages", MergeStrategy.SMART),
            "added": FieldMergeRule("added", MergeStrategy.PREFER_FIRST),
            "modified": FieldMergeRule("modified", MergeStrategy.PREFER_NEWEST),
        }

        self.smart_mergers = {
            "author": self._merge_authors,
            "editor": self._merge_authors,
            "pages": self._merge_pages,
        }

    def merge_entries(
        self,
        entries: list[Entry],
        target_key: str | None = None,
        strategy: MergeStrategy = MergeStrategy.SMART,
    ) -> Entry:
        """Merge multiple entries according to policy."""
        if not entries:
            raise ValueError("No entries to merge")

        if len(entries) == 1:
            return entries[0]

        entries.sort(key=lambda e: e.added)

        if not target_key:
            target_key = self.select_target_key(entries)

        field_values = {}
        all_fields = set()

        for entry in entries:
            entry_dict = entry.to_dict()
            all_fields.update(entry_dict.keys())

            for field, value in entry_dict.items():
                if field not in field_values:
                    field_values[field] = []
                field_values[field].append(value)

        merged_data = {"key": target_key}

        for field in all_fields:
            if field == "key":
                continue

            values = field_values.get(field, [])

            if strategy == MergeStrategy.SMART and field in self.field_rules:
                rule = self.field_rules[field]
                if rule.strategy == MergeStrategy.SMART and field in self.smart_mergers:
                    merged_value = self.smart_mergers[field](values)
                else:
                    merged_value = rule.merge(values)
            else:
                rule = FieldMergeRule(field, strategy)
                merged_value = rule.merge(values)

            if merged_value is not None:
                merged_data[field] = merged_value

        return Entry.from_dict(merged_data)

    def select_target_key(self, entries: list[Entry]) -> str:
        """Select the best key to use for merged entry."""
        entries_by_completeness = sorted(
            entries,
            key=lambda e: len([v for v in e.to_dict().values() if v]),
            reverse=True,
        )

        return entries_by_completeness[0].key

    def fix_validation_errors(
        self, entry: Entry, errors: list[ValidationError]
    ) -> Entry:
        """Fix validation errors in merged entry."""
        updates = {}

        for error in errors:
            if error.field == "author" and not entry.author:
                if entry.editor:
                    updates["author"] = entry.editor

            elif error.field == "year" and not entry.year:
                if entry.note and "in press" in entry.note.lower():
                    updates["year"] = "in press"

        if updates:
            data = entry.to_dict()
            data.update(updates)
            return Entry.from_dict(data)

        return entry

    def _merge_authors(self, values: list[str]) -> str:
        """Smart merge for author/editor fields."""
        if not values:
            return ""

        all_authors = []
        for value in values:
            if value:
                authors = [a.strip() for a in value.split(" and ")]
                all_authors.extend(authors)

        author_groups = {}
        for author in all_authors:
            if "," in author:
                last_name = author.split(",")[0].strip().lower()
            else:
                parts = author.split()
                last_name = parts[-1].lower() if parts else ""

            if last_name not in author_groups:
                author_groups[last_name] = []
            author_groups[last_name].append(author)

        unique_authors = []
        for last_name, variants in author_groups.items():
            variants.sort(key=len, reverse=True)
            unique_authors.append(variants[0])

        return " and ".join(unique_authors)

    def _merge_pages(self, values: list[str]) -> str:
        """Smart merge for page ranges."""
        if not values:
            return ""

        values = [v for v in values if v]
        if not values:
            return ""

        all_pages = []
        for value in values:
            if value:
                if "--" in value:
                    parts = value.split("--")
                elif "-" in value:
                    parts = value.split("-")
                elif "," in value:
                    parts = value.split(",")
                else:
                    parts = [value]

                for part in parts:
                    try:
                        all_pages.append(int(part.strip()))
                    except ValueError:
                        pass

        if not all_pages:
            return max(values, key=len)

        min_page = min(all_pages)
        max_page = max(all_pages)

        if min_page == max_page:
            return str(min_page)
        else:
            return f"{min_page}--{max_page}"
