"""Field configuration for search indexing."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FieldType(Enum):
    """Types of searchable fields."""

    TEXT = "text"
    KEYWORD = "keyword"
    NUMERIC = "numeric"
    DATE = "date"
    BOOLEAN = "boolean"
    STORED = "stored"


@dataclass
class FieldDefinition:
    """Definition of a searchable field."""

    name: str
    field_type: FieldType
    indexed: bool = True
    stored: bool = True
    analyzed: bool = True
    boost: float = 1.0
    analyzer: str | None = None


class FieldConfiguration:
    """Manages field configuration for indexing and searching."""

    DEFAULT_FIELDS = {
        "title": FieldDefinition("title", FieldType.TEXT, boost=2.0),
        "abstract": FieldDefinition("abstract", FieldType.TEXT, boost=1.0),
        "author": FieldDefinition("author", FieldType.TEXT, boost=1.5),
        "editor": FieldDefinition("editor", FieldType.TEXT, boost=1.2),
        "note": FieldDefinition("note", FieldType.TEXT, boost=0.5),
        "journal": FieldDefinition("journal", FieldType.KEYWORD, boost=1.0),
        "booktitle": FieldDefinition("booktitle", FieldType.KEYWORD, boost=1.0),
        "publisher": FieldDefinition("publisher", FieldType.KEYWORD, boost=0.8),
        "series": FieldDefinition("series", FieldType.KEYWORD, boost=0.8),
        "school": FieldDefinition("school", FieldType.KEYWORD, boost=0.8),
        "institution": FieldDefinition("institution", FieldType.KEYWORD, boost=0.8),
        "organization": FieldDefinition("organization", FieldType.KEYWORD, boost=0.8),
        "keywords": FieldDefinition("keywords", FieldType.KEYWORD, boost=1.2),
        "tags": FieldDefinition("tags", FieldType.KEYWORD, boost=1.0),
        "entry_type": FieldDefinition("entry_type", FieldType.KEYWORD),
        "key": FieldDefinition("key", FieldType.KEYWORD, analyzed=False),
        "doi": FieldDefinition("doi", FieldType.KEYWORD, analyzed=False),
        "isbn": FieldDefinition("isbn", FieldType.KEYWORD, analyzed=False),
        "issn": FieldDefinition("issn", FieldType.KEYWORD, analyzed=False),
        "url": FieldDefinition("url", FieldType.KEYWORD, analyzed=False),
        "year": FieldDefinition("year", FieldType.NUMERIC),
        "volume": FieldDefinition("volume", FieldType.NUMERIC),
        "number": FieldDefinition("number", FieldType.NUMERIC),
        "chapter": FieldDefinition("chapter", FieldType.NUMERIC),
        "added": FieldDefinition("added", FieldType.DATE),
        "modified": FieldDefinition("modified", FieldType.DATE),
        "content": FieldDefinition("content", FieldType.TEXT, stored=False, boost=0.8),
        "search_text": FieldDefinition("search_text", FieldType.TEXT, stored=False),
        "author_list": FieldDefinition("author_list", FieldType.STORED, indexed=False),
        "editor_list": FieldDefinition("editor_list", FieldType.STORED, indexed=False),
    }

    def __init__(self, custom_config: dict[str, Any] | None = None):
        """Initialize field configuration.

        Args:
            custom_config: Optional custom configuration to override defaults
        """
        self.fields = {
            name: FieldDefinition(
                name=field.name,
                field_type=field.field_type,
                indexed=field.indexed,
                stored=field.stored,
                analyzed=field.analyzed,
                boost=field.boost,
                analyzer=field.analyzer,
            )
            for name, field in self.DEFAULT_FIELDS.items()
        }

        self.enable_fuzzy = True
        self.enable_stemming = True
        self.enable_synonyms = True

        if custom_config:
            self._apply_custom_config(custom_config)

    def _apply_custom_config(self, config: dict[str, Any]) -> None:
        """Apply custom field configuration."""
        self.enable_fuzzy = config.get("enable_fuzzy", self.enable_fuzzy)
        self.enable_stemming = config.get("enable_stemming", self.enable_stemming)
        self.enable_synonyms = config.get("enable_synonyms", self.enable_synonyms)

        for field_name, field_config in config.get("fields", {}).items():
            if field_name in self.fields:
                field_def = self.fields[field_name]

                self.fields[field_name] = FieldDefinition(
                    name=field_name,
                    field_type=field_def.field_type,
                    indexed=field_config.get("indexed", field_def.indexed),
                    stored=field_config.get("stored", field_def.stored),
                    analyzed=field_config.get("analyzed", field_def.analyzed),
                    boost=field_config.get("boost", field_def.boost),
                    analyzer=field_config.get("analyzer", field_def.analyzer),
                )
            else:
                field_type_str = field_config.get("type", "text")
                try:
                    field_type = FieldType(field_type_str)
                except ValueError:
                    raise ValueError(f"Invalid field type: {field_type_str}")

                self.fields[field_name] = FieldDefinition(
                    name=field_name,
                    field_type=field_type,
                    indexed=field_config.get("indexed", True),
                    stored=field_config.get("stored", True),
                    analyzed=field_config.get("analyzed", True),
                    boost=field_config.get("boost", 1.0),
                    analyzer=field_config.get("analyzer"),
                )

    def get_field(self, name: str) -> FieldDefinition | None:
        """Get field definition by name.

        Args:
            name: Field name

        Returns:
            Copy of FieldDefinition if found, None otherwise
        """
        field = self.fields.get(name)
        if field:
            return FieldDefinition(
                name=field.name,
                field_type=field.field_type,
                indexed=field.indexed,
                stored=field.stored,
                analyzed=field.analyzed,
                boost=field.boost,
                analyzer=field.analyzer,
            )
        return None

    def should_process(self, field: str) -> bool:
        """Check if field should undergo text processing.

        Args:
            field: Field name

        Returns:
            True if field should be analyzed/processed
        """
        field_def = self.fields.get(field)
        return field_def is not None and field_def.analyzed

    def get_analyzer(self, field: str) -> str | None:
        """Get the analyzer configuration for a field.

        Args:
            field: Field name

        Returns:
            Analyzer name if specified, None for default
        """
        field_def = self.fields.get(field)
        return field_def.analyzer if field_def else None

    def get_searchable_fields(self) -> list[str]:
        """Get list of fields that can be searched.

        Returns:
            List of field names that are indexed and searchable
        """
        return [
            name
            for name, field in self.fields.items()
            if field.indexed and field.field_type in [FieldType.TEXT, FieldType.KEYWORD]
        ]

    def get_facet_fields(self) -> list[str]:
        """Get fields suitable for faceted search.

        Returns:
            List of field names that work well for faceting
        """
        return [
            name
            for name, field in self.fields.items()
            if field.field_type == FieldType.KEYWORD and field.indexed
        ]

    def get_numeric_fields(self) -> list[str]:
        """Get fields that support numeric queries.

        Returns:
            List of numeric field names
        """
        return [
            name
            for name, field in self.fields.items()
            if field.field_type == FieldType.NUMERIC and field.indexed
        ]

    def get_date_fields(self) -> list[str]:
        """Get fields that support date queries.

        Returns:
            List of date field names
        """
        return [
            name
            for name, field in self.fields.items()
            if field.field_type == FieldType.DATE and field.indexed
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary format.

        Returns:
            Dictionary representation of the configuration
        """
        return {
            "fields": {
                name: {
                    "type": field.field_type.value,
                    "indexed": field.indexed,
                    "stored": field.stored,
                    "analyzed": field.analyzed,
                    "boost": field.boost,
                    "analyzer": field.analyzer,
                }
                for name, field in self.fields.items()
            },
            "enable_fuzzy": self.enable_fuzzy,
            "enable_stemming": self.enable_stemming,
            "enable_synonyms": self.enable_synonyms,
        }
