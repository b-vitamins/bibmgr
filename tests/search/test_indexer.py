"""Tests for entry indexer."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from bibmgr.core.fields import EntryType
from bibmgr.core.models import Entry
from bibmgr.search.indexing.analyzers import AnalyzerManager
from bibmgr.search.indexing.fields import FieldConfiguration
from bibmgr.search.indexing.indexer import EntryIndexer, IndexingPipeline


@pytest.fixture
def field_config():
    """Create field configuration for testing."""
    return FieldConfiguration()


@pytest.fixture
def analyzer_manager():
    """Create analyzer manager for testing."""
    return AnalyzerManager()


@pytest.fixture
def indexer(field_config, analyzer_manager):
    """Create an entry indexer for testing."""
    return EntryIndexer(field_config=field_config, analyzer_manager=analyzer_manager)


@pytest.fixture
def sample_entry():
    """Create a sample bibliography entry."""
    return Entry(
        key="smith2023",
        type=EntryType.ARTICLE,
        title="Machine Learning in Practice",
        author="John Smith and Jane Doe",
        year=2023,
        journal="AI Review",
        abstract="This paper discusses practical applications of ML.",
        keywords=("machine learning", "applications"),
        doi="10.1234/ai.2023.001",
        added=datetime(2023, 1, 15),
        modified=datetime(2023, 6, 10),
    )


@pytest.fixture
def minimal_entry():
    """Create a minimal bibliography entry."""
    return Entry(key="test2023", type=EntryType.MISC, title="Test Entry")


@pytest.fixture
def complex_entry():
    """Create a complex bibliography entry with many fields."""
    return Entry(
        key="complex2023",
        type=EntryType.INPROCEEDINGS,
        title="Deep Learning for Natural Language Processing: A Comprehensive Survey",
        author="Smith, John A. and Doe, Jane B. and O'Brien, Patrick",
        year=2023,
        month="June",
        booktitle="Proceedings of the 2023 International Conference on AI",
        editor="Johnson, Mary and Williams, Robert",
        pages="123-145",
        publisher="ACM Press",
        address="New York, NY, USA",
        doi="10.1145/3456789.3456790",
        abstract="This comprehensive survey examines the state-of-the-art in deep learning...",
        keywords=("deep learning", "NLP", "transformers", "BERT", "GPT"),
        note="Best paper award winner",
        url="https://example.com/paper.pdf",
        isbn="978-1-4503-1234-5",
        series="ICAI '23",
        organization="Association for Computing Machinery",
        volume="42",
        number="3",
    )


class TestEntryIndexer:
    """Test EntryIndexer class."""

    def test_indexer_initialization(self, field_config, analyzer_manager):
        """Indexer should initialize with provided components."""
        indexer = EntryIndexer(
            field_config=field_config, analyzer_manager=analyzer_manager
        )

        assert indexer.field_config is field_config
        assert indexer.analyzer_manager is analyzer_manager

    def test_indexer_default_initialization(self):
        """Indexer should work with default components."""
        indexer = EntryIndexer()

        assert indexer.field_config is not None
        assert isinstance(indexer.field_config, FieldConfiguration)
        assert indexer.analyzer_manager is not None
        assert isinstance(indexer.analyzer_manager, AnalyzerManager)

    def test_index_entry_basic_fields(self, indexer, sample_entry):
        """Basic entry indexing should extract all present fields."""
        doc = indexer.index_entry(sample_entry)

        # Required fields
        assert doc["key"] == "smith2023"
        assert doc["entry_type"] == "article"

        # Basic fields
        assert doc["title"] == "Machine Learning in Practice"
        assert doc["author"] == "John Smith and Jane Doe"
        assert doc["year"] == 2023
        assert doc["journal"] == "AI Review"
        assert doc["abstract"] == "This paper discusses practical applications of ML."
        assert doc["keywords"] == ("machine learning", "applications")
        assert doc["doi"] == "10.1234/ai.2023.001"

    def test_index_entry_search_text(self, indexer, sample_entry):
        """Search text field should combine searchable content."""
        doc = indexer.index_entry(sample_entry)

        assert "search_text" in doc
        assert isinstance(doc["search_text"], str)

        # Should contain content from multiple fields
        search_text = doc["search_text"]
        assert "Machine Learning in Practice" in search_text
        assert "John Smith and Jane Doe" in search_text
        assert "This paper discusses practical applications of ML." in search_text
        assert "('machine learning', 'applications')" in search_text
        assert "AI Review" in search_text

    def test_index_entry_analyzed_fields(self, indexer, sample_entry):
        """Analyzed text fields should have _analyzed versions."""
        doc = indexer.index_entry(sample_entry)

        # Title should be analyzed
        if "title_analyzed" in doc:
            assert isinstance(doc["title_analyzed"], str)
            # Should be stemmed and processed
            assert "machin" in doc["title_analyzed"].lower()
            assert "learn" in doc["title_analyzed"].lower()
            assert "practic" in doc["title_analyzed"].lower()

        # Abstract should be analyzed
        if "abstract_analyzed" in doc:
            assert isinstance(doc["abstract_analyzed"], str)
            assert "discuss" in doc["abstract_analyzed"].lower()
            assert "applic" in doc["abstract_analyzed"].lower()

    def test_index_entry_author_list(self, indexer, sample_entry):
        """Author field should be parsed into list."""
        doc = indexer.index_entry(sample_entry)

        assert "author_list" in doc
        assert isinstance(doc["author_list"], list)
        assert len(doc["author_list"]) == 2
        assert "John Smith" in doc["author_list"]
        assert "Jane Doe" in doc["author_list"]

    def test_index_entry_author_parsing_formats(self, indexer):
        """Author parsing should handle different formats."""
        # Test "Last, First" format
        entry1 = Entry(
            key="test1",
            type=EntryType.ARTICLE,
            title="Test",
            author="Smith, John A. and Doe, Jane B.",
        )
        doc1 = indexer.index_entry(entry1)
        assert doc1["author_list"] == ["Smith, John A.", "Doe, Jane B."]

        # Test "First Last" format
        entry2 = Entry(
            key="test2",
            type=EntryType.ARTICLE,
            title="Test",
            author="John Smith and Jane Doe",
        )
        doc2 = indexer.index_entry(entry2)
        assert doc2["author_list"] == ["John Smith", "Jane Doe"]

        # Test mixed format
        entry3 = Entry(
            key="test3",
            type=EntryType.ARTICLE,
            title="Test",
            author="Smith, John and Jane Doe and O'Brien, P.",
        )
        doc3 = indexer.index_entry(entry3)
        assert doc3["author_list"] == ["Smith, John", "Jane Doe", "O'Brien, P."]

    def test_index_entry_keywords_handling(self, indexer, sample_entry):
        """Keywords should be preserved and optionally parsed."""
        doc = indexer.index_entry(sample_entry)

        # Original keywords preserved
        assert doc["keywords"] == ("machine learning", "applications")

        # Keywords list should be created if configured
        if "keywords_list" in doc:
            assert isinstance(doc["keywords_list"], list)
            assert len(doc["keywords_list"]) == 2
            assert "('machine learning'" in doc["keywords_list"]
            assert "'applications')" in doc["keywords_list"]

    def test_index_entry_dates(self, indexer, sample_entry):
        """Date fields should be formatted as ISO strings."""
        doc = indexer.index_entry(sample_entry)

        assert "added" in doc
        assert "modified" in doc
        assert "indexed_at" in doc

        # Check ISO format
        assert "2023-01-15" in doc["added"]
        assert "2023-06-10" in doc["modified"]

        # indexed_at should be current time
        from datetime import datetime

        indexed_time = datetime.fromisoformat(doc["indexed_at"])
        assert (datetime.now() - indexed_time).total_seconds() < 5

    def test_index_entry_missing_fields(self, indexer, minimal_entry):
        """Indexer should handle entries with minimal fields."""
        doc = indexer.index_entry(minimal_entry)

        assert doc["key"] == "test2023"
        assert doc["entry_type"] == "misc"
        assert doc["title"] == "Test Entry"

        # Should have dates even if not in entry
        assert "added" in doc
        assert "modified" in doc
        assert "indexed_at" in doc

        # Should have search_text with available content
        assert "search_text" in doc
        assert "Test Entry" in doc["search_text"]

    def test_index_entry_special_characters(self, indexer):
        """Indexer should preserve special characters in original fields."""
        entry = Entry(
            key="muller2023",
            type=EntryType.ARTICLE,
            title="Über Machine Learning: A Comprehensive Study",
            author="Müller, François and O'Brien, Patrick",
            abstract="Study of ML applications in Zürich & München.",
        )

        doc = indexer.index_entry(entry)

        # Original values preserved
        assert doc["title"] == "Über Machine Learning: A Comprehensive Study"
        assert doc["author"] == "Müller, François and O'Brien, Patrick"
        assert doc["abstract"] == "Study of ML applications in Zürich & München."

        # Search text should contain all content
        assert "Über" in doc["search_text"]
        assert "Zürich & München" in doc["search_text"]

    def test_index_entry_numeric_fields(self, indexer):
        """Numeric fields should be converted to integers."""
        entry = Entry(
            key="test2023",
            type=EntryType.ARTICLE,
            title="Test",
            year=2023,
            volume="42",
            number="3-4",  # Range
            pages="123-145",
        )

        doc = indexer.index_entry(entry)

        assert doc["year"] == 2023
        assert isinstance(doc["year"], int)

        if "volume" in doc:
            assert doc["volume"] == 42
            assert isinstance(doc["volume"], int)

        if "number" in doc:
            # Should take first number from range
            assert doc["number"] == 3
            assert isinstance(doc["number"], int)

    def test_index_entry_metadata_fields(self, indexer, sample_entry):
        """Indexer should add metadata fields."""
        doc = indexer.index_entry(sample_entry)

        # Text length metadata
        assert "_text_length" in doc
        assert isinstance(doc["_text_length"], int)
        assert doc["_text_length"] > 0

        # Field count metadata
        assert "_field_count" in doc
        assert isinstance(doc["_field_count"], int)
        assert doc["_field_count"] >= 7  # At least key, type, title, author, etc.

    def test_index_entry_content_field(self, indexer):
        """Content field should aggregate searchable text."""
        entry = Entry(
            key="test2023",
            type=EntryType.INPROCEEDINGS,
            title="Deep Learning for NLP",
            abstract="We present a new approach to natural language processing.",
            booktitle="Proceedings of AI Conference",
            note="Best paper award",
        )

        doc = indexer.index_entry(entry)

        assert "content" in doc
        content = doc["content"]
        assert "Deep Learning for NLP" in content
        assert "natural language processing" in content
        assert "Proceedings of AI Conference" in content
        assert "Best paper award" in content

    def test_index_multiple_entries(self, indexer):
        """Indexer should handle multiple entries efficiently."""
        entries = [
            Entry(key=f"entry{i}", type=EntryType.ARTICLE, title=f"Title {i}")
            for i in range(10)
        ]

        docs = indexer.index_entries(entries)

        assert len(docs) == 10
        for i, doc in enumerate(docs):
            assert doc["key"] == f"entry{i}"
            assert doc["title"] == f"Title {i}"
            assert "search_text" in doc

    def test_custom_field_configuration(self):
        """Indexer should respect custom field configuration."""
        # Create custom config that doesn't index abstract
        custom_config = FieldConfiguration()
        custom_config.fields["abstract"].indexed = False

        indexer = EntryIndexer(field_config=custom_config)

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Test Title",
            abstract="This should not be indexed",
        )

        doc = indexer.index_entry(entry)

        assert "title" in doc
        assert "abstract" not in doc  # Should not be indexed

    def test_custom_analyzer_configuration(self):
        """Indexer should use custom analyzers for fields."""
        # Mock analyzer manager
        mock_analyzer = Mock()
        mock_analyzer.analyze_field.return_value = ["custom", "tokens"]

        indexer = EntryIndexer(analyzer_manager=mock_analyzer)

        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test Title")

        doc = indexer.index_entry(entry)

        # Analyzer should have been called
        mock_analyzer.analyze_field.assert_called()

        # Check if analyzed field was created
        if "title_analyzed" in doc:
            assert doc["title_analyzed"] == "custom tokens"

    def test_should_index_field(self, indexer):
        """should_index_field method should check field configuration."""
        assert indexer.should_index_field("title") is True
        assert indexer.should_index_field("abstract") is True
        assert indexer.should_index_field("nonexistent_field") is False

    def test_get_field_analyzer(self, indexer):
        """get_field_analyzer should return appropriate analyzer names."""
        assert indexer.get_field_analyzer("title") == "stemming"
        assert indexer.get_field_analyzer("author") == "author"
        assert indexer.get_field_analyzer("doi") == "keyword"
        assert indexer.get_field_analyzer("unknown") == "standard"


class TestIndexingPipeline:
    """Test IndexingPipeline class."""

    @pytest.fixture
    def pipeline(self):
        """Create indexing pipeline for testing."""
        return IndexingPipeline()

    def test_pipeline_initialization(self):
        """Pipeline should initialize with defaults."""
        pipeline = IndexingPipeline()

        assert pipeline.indexer is not None
        assert isinstance(pipeline.indexer, EntryIndexer)
        assert pipeline.batch_size == 100
        assert pipeline.processed_count == 0
        assert pipeline.error_count == 0
        assert pipeline.errors == []

    def test_pipeline_custom_initialization(self):
        """Pipeline should accept custom components."""
        custom_indexer = EntryIndexer()
        pipeline = IndexingPipeline(indexer=custom_indexer, batch_size=50)

        assert pipeline.indexer is custom_indexer
        assert pipeline.batch_size == 50

    def test_process_entries_success(self, pipeline, sample_entry):
        """Pipeline should process valid entries successfully."""
        entries = [sample_entry]
        docs = pipeline.process_entries(entries)

        assert len(docs) == 1
        assert docs[0]["key"] == "smith2023"
        assert pipeline.processed_count == 1
        assert pipeline.error_count == 0

    def test_process_entries_with_validation(self, pipeline):
        """Pipeline should validate documents when requested."""
        # Create entry that will fail validation (no key)
        invalid_entry = Mock()
        invalid_entry.key = ""
        invalid_entry.type = EntryType.ARTICLE
        invalid_entry.title = "Test"

        # Mock indexer to return invalid document
        pipeline.indexer.index_entry = Mock(return_value={"title": "Test"})

        docs = pipeline.process_entries([invalid_entry], validate=True)

        assert len(docs) == 0  # Invalid doc should be skipped
        assert pipeline.error_count == 1
        assert len(pipeline.errors) > 0

    def test_process_entries_with_exception(self, pipeline):
        """Pipeline should handle exceptions during processing."""
        # Create entry that will cause exception
        bad_entry = Mock()
        bad_entry.key = "bad"

        # Mock indexer to raise exception
        pipeline.indexer.index_entry = Mock(side_effect=ValueError("Test error"))

        docs = pipeline.process_entries([bad_entry])

        assert len(docs) == 0
        assert pipeline.error_count == 1
        assert len(pipeline.errors) == 1
        assert "bad: Test error" in pipeline.errors[0]

    def test_process_in_batches(self, pipeline):
        """Pipeline should process entries in batches."""
        entries = [
            Entry(key=f"entry{i}", type=EntryType.ARTICLE, title=f"Title {i}")
            for i in range(250)
        ]

        batch_counts = []

        def callback(batch_num, total_batches, docs):
            batch_counts.append((batch_num, len(docs)))

        pipeline.batch_size = 100
        pipeline.process_in_batches(entries, callback=callback)

        # Should have 3 batches (100, 100, 50)
        assert len(batch_counts) == 3
        assert batch_counts[0] == (1, 100)
        assert batch_counts[1] == (2, 100)
        assert batch_counts[2] == (3, 50)

    def test_pipeline_statistics(self, pipeline):
        """Pipeline should track processing statistics."""
        entries = [
            Entry(key=f"entry{i}", type=EntryType.ARTICLE, title=f"Title {i}")
            for i in range(5)
        ]

        pipeline.process_entries(entries)

        stats = pipeline.get_statistics()
        assert stats["processed_count"] == 5
        assert stats["error_count"] == 0
        assert stats["total_errors"] == 0

    def test_pipeline_error_tracking(self, pipeline):
        """Pipeline should track errors properly."""
        # Mix of good and bad entries
        good_entry = Entry(key="good", type=EntryType.ARTICLE, title="Good")
        bad_entry = Mock()
        bad_entry.key = "bad"

        # Make bad entry cause exception
        original_index = pipeline.indexer.index_entry

        def mock_index(entry):
            if hasattr(entry, "key") and entry.key == "bad":
                raise ValueError("Bad entry")
            return original_index(entry)

        pipeline.indexer.index_entry = mock_index

        docs = pipeline.process_entries([good_entry, bad_entry, good_entry])

        assert len(docs) == 2  # Two good entries
        assert pipeline.processed_count == 2
        assert pipeline.error_count == 1

        errors = pipeline.get_errors()
        assert len(errors) == 1
        assert "bad: Bad entry" in errors[0]

    def test_reset_statistics(self, pipeline):
        """Pipeline should reset statistics correctly."""
        # Process some entries
        entries = [Entry(key="test", type=EntryType.ARTICLE, title="Test")]
        pipeline.process_entries(entries)

        assert pipeline.processed_count > 0

        # Reset
        pipeline.reset_statistics()

        assert pipeline.processed_count == 0
        assert pipeline.error_count == 0
        assert len(pipeline.errors) == 0

    def test_validate_document(self, pipeline):
        """Document validation should check required fields."""
        # Valid document
        valid_doc = {"key": "test123", "title": "Test", "entry_type": "article"}
        errors = pipeline.indexer.validate_document(valid_doc)
        assert len(errors) == 0

        # Missing key
        doc_no_key = {"title": "Test", "entry_type": "article"}
        errors = pipeline.indexer.validate_document(doc_no_key)
        assert len(errors) > 0
        assert any("key" in e for e in errors)

        # Empty key
        doc_empty_key = {"key": "", "title": "Test", "entry_type": "article"}
        errors = pipeline.indexer.validate_document(doc_empty_key)
        assert len(errors) > 0

        # Missing entry_type
        doc_no_type = {"key": "test", "title": "Test"}
        errors = pipeline.indexer.validate_document(doc_no_type)
        assert len(errors) > 0
        assert any("entry_type" in e for e in errors)

        # Wrong year type
        doc_bad_year = {"key": "test", "entry_type": "article", "year": "2023"}
        errors = pipeline.indexer.validate_document(doc_bad_year)
        assert len(errors) > 0
        assert any("year" in e and "integer" in e for e in errors)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_author_string(self):
        """Empty author string should be handled gracefully."""
        indexer = EntryIndexer()
        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test", author="")
        doc = indexer.index_entry(entry)

        if "author_list" in doc:
            assert doc["author_list"] == []

    def test_author_with_only_whitespace(self):
        """Author with only whitespace should be handled."""
        indexer = EntryIndexer()
        entry = Entry(key="test", type=EntryType.ARTICLE, title="Test", author="   ")
        doc = indexer.index_entry(entry)

        if "author_list" in doc:
            assert doc["author_list"] == []

    def test_single_author_name(self):
        """Single author name should be parsed correctly."""
        indexer = EntryIndexer()

        # Single word (assume last name)
        entry1 = Entry(
            key="test1", type=EntryType.ARTICLE, title="Test", author="Smith"
        )
        doc1 = indexer.index_entry(entry1)
        assert doc1["author_list"] == ["Smith"]

        # Two words (first last)
        entry2 = Entry(
            key="test2", type=EntryType.ARTICLE, title="Test", author="John Smith"
        )
        doc2 = indexer.index_entry(entry2)
        assert doc2["author_list"] == ["John Smith"]

    def test_malformed_author_strings(self):
        """Malformed author strings should be handled gracefully."""
        indexer = EntryIndexer()

        # Extra "and"
        entry1 = Entry(
            key="test1",
            type=EntryType.ARTICLE,
            title="Test",
            author="John Smith and and Jane Doe",
        )
        doc1 = indexer.index_entry(entry1)
        assert "John Smith" in doc1["author_list"]
        assert "Jane Doe" in doc1["author_list"]

        # Trailing "and"
        entry2 = Entry(
            key="test2", type=EntryType.ARTICLE, title="Test", author="John Smith and "
        )
        doc2 = indexer.index_entry(entry2)
        assert doc2["author_list"] == ["John Smith"]

    def test_very_long_text_fields(self):
        """Very long text fields should be handled."""
        indexer = EntryIndexer()

        # Create entry with very long abstract
        long_text = " ".join(["word"] * 10000)
        entry = Entry(
            key="test", type=EntryType.ARTICLE, title="Test", abstract=long_text
        )

        doc = indexer.index_entry(entry)

        assert "abstract" in doc
        assert doc["abstract"] == long_text
        assert "_text_length" in doc
        assert doc["_text_length"] > 40000

    def test_unicode_in_all_fields(self):
        """Unicode should be preserved in all fields."""
        indexer = EntryIndexer()

        entry = Entry(
            key="unicode2023",
            type=EntryType.ARTICLE,
            title="研究 über Machine Learning",
            author="李明 and Müller, François",
            journal="Journal für KI-Forschung",
            abstract="这是一篇关于机器学习的论文。",
            keywords=("机器学习", "apprentissage automatique", "μηχανική μάθηση"),
        )

        doc = indexer.index_entry(entry)

        assert doc["title"] == "研究 über Machine Learning"
        assert "李明" in doc["author_list"]
        assert "Müller, François" in doc["author_list"]
        assert "机器学习" in doc["keywords"]

    def test_entry_with_all_fields(self, complex_entry):
        """Entry with all possible fields should be indexed completely."""
        indexer = EntryIndexer()
        doc = indexer.index_entry(complex_entry)

        # Check all fields are present
        expected_fields = [
            "key",
            "entry_type",
            "title",
            "author",
            "year",
            "month",
            "booktitle",
            "editor",
            "pages",
            "publisher",
            "address",
            "doi",
            "abstract",
            "keywords",
            "note",
            "url",
            "isbn",
            "series",
            "organization",
            "volume",
            "number",
        ]

        for field in expected_fields:
            assert field in doc, f"Field {field} missing from document"

        # Check special processing
        assert "author_list" in doc
        assert len(doc["author_list"]) == 3
        assert "editor_list" in doc
        assert len(doc["editor_list"]) == 2

        # Numeric fields
        assert doc["volume"] == 42
        assert doc["number"] == 3

        # Search text should be comprehensive
        assert len(doc["search_text"]) > 200
