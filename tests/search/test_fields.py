"""Tests for field configuration system."""

import pytest

from bibmgr.search.indexing.fields import (
    FieldConfiguration,
    FieldDefinition,
    FieldType,
)


class TestFieldType:
    """Test FieldType enum."""

    def test_field_type_values(self):
        """FieldType should have expected values."""
        assert FieldType.TEXT.value == "text"
        assert FieldType.KEYWORD.value == "keyword"
        assert FieldType.NUMERIC.value == "numeric"
        assert FieldType.DATE.value == "date"
        assert FieldType.BOOLEAN.value == "boolean"
        assert FieldType.STORED.value == "stored"

    def test_field_type_from_string(self):
        """FieldType should be creatable from string."""
        assert FieldType("text") == FieldType.TEXT
        assert FieldType("keyword") == FieldType.KEYWORD
        assert FieldType("numeric") == FieldType.NUMERIC


class TestFieldDefinition:
    """Test FieldDefinition dataclass."""

    def test_create_minimal_field_definition(self):
        """Create field definition with minimal parameters."""
        field = FieldDefinition("title", FieldType.TEXT)

        assert field.name == "title"
        assert field.field_type == FieldType.TEXT
        assert field.indexed is True
        assert field.stored is True
        assert field.analyzed is True
        assert field.boost == 1.0
        assert field.analyzer is None

    def test_create_full_field_definition(self):
        """Create field definition with all parameters."""
        field = FieldDefinition(
            name="custom_field",
            field_type=FieldType.KEYWORD,
            indexed=False,
            stored=True,
            analyzed=False,
            boost=2.5,
            analyzer="custom",
        )

        assert field.name == "custom_field"
        assert field.field_type == FieldType.KEYWORD
        assert field.indexed is False
        assert field.stored is True
        assert field.analyzed is False
        assert field.boost == 2.5
        assert field.analyzer == "custom"

    def test_text_field_defaults(self):
        """Text fields should have appropriate defaults."""
        field = FieldDefinition("content", FieldType.TEXT)

        assert field.indexed is True
        assert field.analyzed is True
        assert field.stored is True

    def test_keyword_field_defaults(self):
        """Keyword fields should have appropriate defaults."""
        field = FieldDefinition("tags", FieldType.KEYWORD)

        assert field.indexed is True
        assert field.analyzed is True  # Can be analyzed for normalization
        assert field.stored is True

    def test_numeric_field_defaults(self):
        """Numeric fields should have appropriate defaults."""
        field = FieldDefinition("year", FieldType.NUMERIC)

        assert field.indexed is True
        assert field.analyzed is True
        assert field.stored is True


class TestFieldConfiguration:
    """Test FieldConfiguration class."""

    def test_default_configuration(self):
        """Default configuration should include standard bibliography fields."""
        config = FieldConfiguration()

        # Standard fields should be present
        assert "title" in config.fields
        assert "author" in config.fields
        assert "abstract" in config.fields
        assert "year" in config.fields
        assert "journal" in config.fields
        assert "keywords" in config.fields
        assert "doi" in config.fields

    def test_field_types_correct(self):
        """Default fields should have correct types."""
        config = FieldConfiguration()

        # Text fields
        assert config.fields["title"].field_type == FieldType.TEXT
        assert config.fields["abstract"].field_type == FieldType.TEXT
        assert config.fields["author"].field_type == FieldType.TEXT

        # Keyword fields
        assert config.fields["keywords"].field_type == FieldType.KEYWORD
        assert config.fields["journal"].field_type == FieldType.KEYWORD
        assert config.fields["doi"].field_type == FieldType.KEYWORD

        # Numeric fields
        assert config.fields["year"].field_type == FieldType.NUMERIC
        assert config.fields["volume"].field_type == FieldType.NUMERIC

        # Date fields
        assert config.fields["added"].field_type == FieldType.DATE
        assert config.fields["modified"].field_type == FieldType.DATE

    def test_boost_values(self):
        """Important fields should have higher boost values."""
        config = FieldConfiguration()

        # Title should have highest boost
        assert config.fields["title"].boost > config.fields["abstract"].boost
        assert config.fields["title"].boost > config.fields["note"].boost

        # Author should have higher boost than abstract
        assert config.fields["author"].boost > config.fields["abstract"].boost

    def test_analyzed_fields(self):
        """Text fields should be analyzed, IDs should not."""
        config = FieldConfiguration()

        # Should be analyzed
        assert config.fields["title"].analyzed is True
        assert config.fields["abstract"].analyzed is True
        assert config.fields["author"].analyzed is True

        # Should not be analyzed
        assert config.fields["doi"].analyzed is False
        assert config.fields["isbn"].analyzed is False
        assert config.fields["key"].analyzed is False

    def test_custom_configuration(self):
        """Custom configuration should override defaults."""
        custom_config = {
            "fields": {
                "title": {"boost": 5.0, "analyzer": "custom"},
                "custom_field": {
                    "type": "text",
                    "boost": 1.5,
                    "indexed": True,
                    "stored": False,
                },
            }
        }

        config = FieldConfiguration(custom_config)

        # Title should be updated
        assert config.fields["title"].boost == 5.0
        assert config.fields["title"].analyzer == "custom"

        # Custom field should be added
        assert "custom_field" in config.fields
        assert config.fields["custom_field"].field_type == FieldType.TEXT
        assert config.fields["custom_field"].boost == 1.5
        assert config.fields["custom_field"].stored is False

    def test_configuration_options(self):
        """Configuration options should be settable."""
        custom_config = {
            "enable_fuzzy": False,
            "enable_stemming": False,
            "enable_synonyms": False,
        }

        config = FieldConfiguration(custom_config)

        assert config.enable_fuzzy is False
        assert config.enable_stemming is False
        assert config.enable_synonyms is False

    def test_get_field(self):
        """get_field should return field definition."""
        config = FieldConfiguration()

        title_field = config.get_field("title")
        assert title_field is not None
        assert title_field.name == "title"
        assert title_field.field_type == FieldType.TEXT

        # Non-existent field
        assert config.get_field("nonexistent") is None

    def test_should_process(self):
        """should_process should check if field needs text processing."""
        config = FieldConfiguration()

        # Text fields should be processed
        assert config.should_process("title") is True
        assert config.should_process("abstract") is True

        # Non-analyzed fields should not be processed
        assert config.should_process("doi") is False
        assert config.should_process("isbn") is False

        # Non-existent fields should not be processed
        assert config.should_process("nonexistent") is False

    def test_get_analyzer(self):
        """get_analyzer should return field analyzer."""
        config = FieldConfiguration()

        # Fields without specific analyzer should return None
        assert config.get_analyzer("title") is None
        assert config.get_analyzer("abstract") is None

        # Non-existent field should return None
        assert config.get_analyzer("nonexistent") is None

        # Custom analyzer
        custom_config = {"fields": {"title": {"analyzer": "stemming"}}}
        config_custom = FieldConfiguration(custom_config)
        assert config_custom.get_analyzer("title") == "stemming"

    def test_get_searchable_fields(self):
        """get_searchable_fields should return indexed text/keyword fields."""
        config = FieldConfiguration()

        searchable = config.get_searchable_fields()

        # Should include text fields
        assert "title" in searchable
        assert "abstract" in searchable
        assert "author" in searchable

        # Should include keyword fields
        assert "keywords" in searchable
        assert "journal" in searchable

        # Should not include non-indexed or non-searchable fields
        # (All default fields are indexed, so this tests the logic)
        assert all(config.fields[field].indexed for field in searchable)
        assert all(
            config.fields[field].field_type in [FieldType.TEXT, FieldType.KEYWORD]
            for field in searchable
        )

    def test_get_facet_fields(self):
        """get_facet_fields should return keyword fields suitable for faceting."""
        config = FieldConfiguration()

        facet_fields = config.get_facet_fields()

        # Should include keyword fields
        assert "keywords" in facet_fields
        assert "journal" in facet_fields
        assert "publisher" in facet_fields
        assert "entry_type" in facet_fields

        # Should not include text fields
        assert "title" not in facet_fields
        assert "abstract" not in facet_fields

        # All facet fields should be keyword type
        assert all(
            config.fields[field].field_type == FieldType.KEYWORD
            for field in facet_fields
        )

    def test_to_dict(self):
        """to_dict should serialize configuration."""
        config = FieldConfiguration()

        data = config.to_dict()

        assert isinstance(data, dict)
        assert "fields" in data
        assert "enable_fuzzy" in data
        assert "enable_stemming" in data
        assert "enable_synonyms" in data

        # Field data should be serializable
        fields_data = data["fields"]
        assert isinstance(fields_data, dict)

        # Check title field serialization
        title_data = fields_data["title"]
        assert title_data["type"] == "text"
        assert title_data["boost"] == 2.0
        assert title_data["indexed"] is True
        assert title_data["stored"] is True
        assert title_data["analyzed"] is True

    def test_from_dict_roundtrip(self):
        """Configuration should survive to_dict/from_dict roundtrip."""
        original_config = FieldConfiguration(
            {
                "fields": {
                    "title": {"boost": 3.0, "analyzer": "custom"},
                },
                "enable_fuzzy": False,
            }
        )

        # Serialize and deserialize
        data = original_config.to_dict()
        new_config = FieldConfiguration(data)

        # Should be equivalent
        assert new_config.fields["title"].boost == 3.0
        assert new_config.fields["title"].analyzer == "custom"
        assert new_config.enable_fuzzy is False

    def test_field_hierarchy(self):
        """Custom fields should override defaults properly."""
        custom_config = {
            "fields": {
                "title": {
                    "boost": 10.0,  # Override default
                    "analyzer": "custom",  # Add analyzer
                    # Other properties should keep defaults
                },
            }
        }

        config = FieldConfiguration(custom_config)
        title_field = config.fields["title"]

        # Should have custom values
        assert title_field.boost == 10.0
        assert title_field.analyzer == "custom"

        # Should keep defaults
        assert title_field.field_type == FieldType.TEXT
        assert title_field.indexed is True
        assert title_field.stored is True
        assert title_field.analyzed is True

    def test_invalid_field_type(self):
        """Invalid field types should be handled gracefully."""
        custom_config = {
            "fields": {
                "invalid_field": {
                    "type": "invalid_type",
                }
            }
        }

        # Should raise ValueError or handle gracefully
        with pytest.raises((ValueError, TypeError)):
            FieldConfiguration(custom_config)

    def test_field_validation(self):
        """Field definitions should be validated."""
        # Valid configuration
        valid_config = {
            "fields": {
                "valid_field": {
                    "type": "text",
                    "boost": 1.5,
                    "indexed": True,
                }
            }
        }

        config = FieldConfiguration(valid_config)
        assert "valid_field" in config.fields

    def test_boost_value_validation(self):
        """Boost values should be positive numbers."""
        config = FieldConfiguration()

        # Default boost should be positive
        assert config.fields["title"].boost > 0
        assert config.fields["abstract"].boost > 0

        # Test custom boost
        custom_config = {
            "fields": {
                "custom_field": {
                    "type": "text",
                    "boost": 2.5,
                }
            }
        }

        config_custom = FieldConfiguration(custom_config)
        assert config_custom.fields["custom_field"].boost == 2.5

    def test_special_fields(self):
        """Special fields should be configured correctly."""
        config = FieldConfiguration()

        # Key field should be exact match
        key_field = config.fields["key"]
        assert key_field.field_type == FieldType.KEYWORD
        assert key_field.analyzed is False

        # Search text field should be stored=False (derived field)
        search_field = config.fields["search_text"]
        assert search_field.field_type == FieldType.TEXT
        assert search_field.stored is False

    def test_configuration_immutability(self):
        """Field configuration should be immutable after creation."""
        config = FieldConfiguration()
        original_boost = config.fields["title"].boost

        # Modifying the field should not affect the original
        field = config.get_field("title")
        if field is not None:
            field.boost = 999.0

        # Original should be unchanged
        assert config.fields["title"].boost == original_boost

    def test_field_inheritance(self):
        """Field definitions should support inheritance patterns."""

        # Extended configuration
        extended_config = {
            "fields": {
                "base_field": {
                    "boost": 2.0,  # Override boost
                    # Inherit other properties
                },
                "new_field": {
                    "type": "keyword",
                },
            }
        }

        config = FieldConfiguration(extended_config)

        base_field = config.fields["base_field"]
        assert base_field.boost == 2.0  # Overridden
        assert base_field.field_type == FieldType.TEXT  # Default
        assert base_field.indexed is True  # Default
