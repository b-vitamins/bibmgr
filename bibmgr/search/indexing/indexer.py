"""Entry indexer for converting bibliography entries to searchable documents."""

import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from ...core.models import Entry as BibEntry
from .analyzers import AnalyzerManager
from .fields import FieldConfiguration


class EntryIndexer:
    """Converts bibliography entries into indexed documents for search."""

    def __init__(
        self,
        field_config: FieldConfiguration | None = None,
        analyzer_manager: AnalyzerManager | None = None,
    ):
        """Initialize entry indexer.

        Args:
            field_config: Field configuration for indexing behavior
            analyzer_manager: Text analyzer manager
        """
        self.field_config = field_config or FieldConfiguration()
        self.analyzer_manager = analyzer_manager or AnalyzerManager()

    def index_entry(self, entry: BibEntry) -> dict[str, Any]:
        """Convert a bibliography entry into an indexed document.

        Args:
            entry: Bibliography entry to index

        Returns:
            Dictionary representing the indexed document
        """
        doc = {
            "key": entry.key,
            "entry_type": entry.type.value
            if hasattr(entry.type, "value")
            else str(entry.type).lower(),
        }

        entry_fields = self._extract_entry_fields(entry)

        search_text_parts = []
        for field_name, field_value in entry_fields.items():
            field_def = self.field_config.get_field(field_name)

            if field_def:
                if not field_def.indexed:
                    continue

            doc[field_name] = field_value

            if field_name in [
                "title",
                "author",
                "abstract",
                "keywords",
                "journal",
                "booktitle",
                "note",
            ]:
                search_text_parts.append(str(field_value))

            if (
                field_def
                and field_def.analyzed
                and self.field_config.should_process(field_name)
            ):
                analyzed_tokens = self.analyzer_manager.analyze_field(
                    field_name, str(field_value)
                )

                if analyzed_tokens:
                    doc[f"{field_name}_analyzed"] = " ".join(analyzed_tokens)

        if search_text_parts:
            doc["search_text"] = " ".join(search_text_parts)

        self._add_derived_fields(doc, entry)

        self._add_metadata(doc, entry)

        return doc

    def index_entries(self, entries: list[BibEntry]) -> list[dict[str, Any]]:
        """Convert multiple bibliography entries into indexed documents.

        Args:
            entries: List of bibliography entries to index

        Returns:
            List of indexed documents
        """
        return [self.index_entry(entry) for entry in entries]

    def _extract_entry_fields(self, entry: BibEntry) -> dict[str, Any]:
        """Extract all fields from an entry.

        Args:
            entry: Bibliography entry

        Returns:
            Dictionary of field names to values
        """
        fields = {}

        field_names = [
            "title",
            "author",
            "year",
            "journal",
            "volume",
            "number",
            "pages",
            "month",
            "note",
            "publisher",
            "series",
            "address",
            "edition",
            "booktitle",
            "chapter",
            "editor",
            "howpublished",
            "institution",
            "organization",
            "school",
            "abstract",
            "keywords",
            "doi",
            "isbn",
            "issn",
            "url",
            "eprint",
            "archiveprefix",
            "primaryclass",
        ]

        for field_name in field_names:
            if hasattr(entry, field_name):
                value = getattr(entry, field_name)
                if value is not None and value != "":
                    fields[field_name] = value

        return fields

    def _add_derived_fields(self, doc: dict[str, Any], entry: BibEntry) -> None:
        """Add derived fields for enhanced searching.

        Args:
            doc: Document being built
            entry: Source bibliography entry
        """
        if "search_text" in doc:
            doc["content"] = doc["search_text"]

            analyzed_content = self.analyzer_manager.analyze_field(
                "content", doc["search_text"]
            )
            if analyzed_content:
                doc["content_analyzed"] = " ".join(analyzed_content)

        if "author" in doc:
            doc["author_list"] = self._parse_authors(doc["author"])

        if "editor" in doc:
            doc["editor_list"] = self._parse_authors(doc["editor"])

        if hasattr(entry, "year") and entry.year is not None:
            doc["year"] = entry.year

        for field in ["volume", "number", "chapter"]:
            if field in doc and doc[field]:
                try:
                    value_str = str(doc[field]).split("-")[0].strip()
                    doc[field] = int(value_str)
                except (ValueError, TypeError):
                    pass

        if "keywords" in doc and doc["keywords"]:
            keyword_list = []

            if isinstance(doc["keywords"], list):
                for kw in doc["keywords"]:
                    if isinstance(kw, str):
                        kw = kw.strip()
                        if kw:
                            keyword_list.append(kw)
            else:
                for kw in re.split(r"[,;]+", str(doc["keywords"])):
                    kw = kw.strip()
                    if kw:
                        keyword_list.append(kw)

            if keyword_list:
                doc["keywords_list"] = keyword_list

    def _add_metadata(self, doc: dict[str, Any], entry: BibEntry) -> None:
        """Add indexing metadata to document.

        Args:
            doc: Document being built
            entry: Source bibliography entry
        """
        now = datetime.now()
        doc["indexed_at"] = now.isoformat()

        if hasattr(entry, "modified") and entry.modified:
            doc["modified"] = entry.modified.isoformat()
        elif hasattr(entry, "added") and entry.added:
            doc["modified"] = entry.added.isoformat()
        else:
            doc["modified"] = now.isoformat()

        if hasattr(entry, "added") and entry.added:
            doc["added"] = entry.added.isoformat()
        else:
            doc["added"] = now.isoformat()

        text_length = 0
        for field, value in doc.items():
            if isinstance(value, str) and not field.endswith("_analyzed"):
                text_length += len(value)

        doc["_text_length"] = text_length

        field_count = len([f for f in doc.keys() if not f.startswith("_")])
        doc["_field_count"] = field_count

    def _parse_authors(self, author_string: str) -> list[str]:
        """Parse author string into list of author names.

        Args:
            author_string: Raw author string from BibTeX

        Returns:
            List of author names as strings
        """
        if not author_string or not author_string.strip():
            return []

        authors = []

        normalized = re.sub(
            r"(\s+and\s+)(\s*and\s*)+", " and ", author_string, flags=re.IGNORECASE
        )

        author_parts = re.split(r"\s+and\s+", normalized, flags=re.IGNORECASE)

        for author_part in author_parts:
            author_part = author_part.strip()
            if author_part:
                authors.append(author_part)

        return authors

    def validate_document(self, doc: dict[str, Any]) -> list[str]:
        """Validate an indexed document and return any issues.

        Args:
            doc: Indexed document to validate

        Returns:
            List of validation error messages
        """
        errors = []

        if "key" not in doc:
            errors.append("Document missing required 'key' field")
        elif not doc["key"]:
            errors.append("Document has empty 'key' field")

        if "entry_type" not in doc:
            errors.append("Document missing required 'entry_type' field")

        if "year" in doc:
            if not isinstance(doc["year"], int):
                errors.append("Field 'year' must be integer")

        for field_name, value in doc.items():
            if field_name.endswith("_analyzed") and not value:
                errors.append(f"Empty analyzed field: {field_name}")

        return errors

    def should_index_field(self, field_name: str) -> bool:
        """Check if a field should be included in the index.

        Args:
            field_name: Name of the field

        Returns:
            True if field should be indexed
        """
        field_def = self.field_config.get_field(field_name)
        return field_def is not None and field_def.indexed

    def get_field_analyzer(self, field_name: str) -> str:
        """Get the analyzer name for a field.

        Args:
            field_name: Name of the field

        Returns:
            Analyzer name to use for the field
        """
        analyzer_name = self.field_config.get_analyzer(field_name)
        if analyzer_name:
            return analyzer_name

        field_analyzers = self.analyzer_manager.field_analyzers
        return field_analyzers.get(field_name, "standard")


class IndexingPipeline:
    """Pipeline for processing and indexing bibliography entries."""

    def __init__(self, indexer: EntryIndexer | None = None, batch_size: int = 100):
        """Initialize indexing pipeline.

        Args:
            indexer: Entry indexer to use
            batch_size: Number of entries to process in each batch
        """
        self.indexer = indexer or EntryIndexer()
        self.batch_size = batch_size
        self.processed_count = 0
        self.error_count = 0
        self.errors: list[str] = []

    def process_entries(
        self, entries: list[BibEntry], validate: bool = True
    ) -> list[dict[str, Any]]:
        """Process multiple entries through the indexing pipeline.

        Args:
            entries: Bibliography entries to process
            validate: Whether to validate documents after indexing

        Returns:
            List of processed documents ready for backend indexing
        """
        documents = []

        for entry in entries:
            try:
                doc = self.indexer.index_entry(entry)

                if validate:
                    validation_errors = self.indexer.validate_document(doc)
                    if validation_errors:
                        self.error_count += 1
                        self.errors.extend(
                            [
                                f"Entry {entry.key}: {error}"
                                for error in validation_errors
                            ]
                        )
                        continue

                documents.append(doc)
                self.processed_count += 1

            except Exception as e:
                self.error_count += 1
                error_msg = f"Entry {entry.key}: {str(e)}"
                self.errors.append(error_msg)

        return documents

    def process_in_batches(
        self,
        entries: list[BibEntry],
        callback: Callable[[int, int, list], None] | None = None,
    ) -> None:
        """Process entries in batches with optional progress callback.

        Args:
            entries: Bibliography entries to process
            callback: Optional callback function called after each batch
                     callback(batch_num, batch_count, documents)
        """
        total_batches = (len(entries) + self.batch_size - 1) // self.batch_size

        for batch_num in range(total_batches):
            start_idx = batch_num * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(entries))

            batch_entries = entries[start_idx:end_idx]
            batch_documents = self.process_entries(batch_entries)

            if callback:
                callback(batch_num + 1, total_batches, batch_documents)

    def get_statistics(self) -> dict[str, int]:
        """Get processing statistics.

        Returns:
            Dictionary with processing counts
        """
        return {
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "total_errors": len(self.errors),
        }

    def get_errors(self) -> list[str]:
        """Get list of processing errors.

        Returns:
            List of error messages
        """
        return self.errors.copy()

    def reset_statistics(self) -> None:
        """Reset processing statistics."""
        self.processed_count = 0
        self.error_count = 0
        self.errors.clear()
