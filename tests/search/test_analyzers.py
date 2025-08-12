"""Tests for text analyzers and processing."""

import pytest

from bibmgr.search.indexing.analyzers import (
    AnalyzerConfig,
    SynonymExpander,
    TextProcessor,
)


class TestAnalyzerConfig:
    """Test AnalyzerConfig dataclass."""

    def test_default_config(self):
        """Default configuration should have sensible defaults."""
        config = AnalyzerConfig()

        assert config.lowercase is True
        assert config.remove_accents is True
        assert config.split_camelcase is True
        assert config.remove_stopwords is True
        assert config.stem is True
        assert config.min_token_length == 2
        assert config.max_token_length == 50

    def test_custom_config(self):
        """Custom configuration should override defaults."""
        config = AnalyzerConfig(
            lowercase=False,
            stem=False,
            min_token_length=3,
            max_token_length=20,
        )

        assert config.lowercase is False
        assert config.stem is False
        assert config.min_token_length == 3
        assert config.max_token_length == 20
        assert config.remove_accents is True
        assert config.split_camelcase is True

    def test_exact_config(self):
        """Exact analyzer config should preserve text."""
        config = AnalyzerConfig(
            lowercase=True,
            remove_accents=False,
            split_camelcase=False,
            remove_stopwords=False,
            stem=False,
        )

        assert config.lowercase is True
        assert config.remove_accents is False
        assert config.split_camelcase is False
        assert config.remove_stopwords is False
        assert config.stem is False

    def test_stopwords_initialization(self):
        """Stopwords should be initialized when remove_stopwords is True."""
        config = AnalyzerConfig(remove_stopwords=True)
        assert config.stopwords is not None
        assert len(config.stopwords) > 0
        assert "the" in config.stopwords

        config_no_stop = AnalyzerConfig(remove_stopwords=False)
        assert config_no_stop.stopwords is None


class TestTextProcessor:
    """Test TextProcessor class."""

    @pytest.fixture
    def processor(self):
        """Create a text processor for testing."""
        return TextProcessor()

    def test_predefined_configs(self):
        """Processor should have predefined configurations."""
        assert "default" in TextProcessor.CONFIGS
        assert "exact" in TextProcessor.CONFIGS
        assert "keyword" in TextProcessor.CONFIGS

        default_config = TextProcessor.CONFIGS["default"]
        assert default_config.lowercase is True
        assert default_config.stem is True

        exact_config = TextProcessor.CONFIGS["exact"]
        assert exact_config.stem is False
        assert exact_config.remove_stopwords is False

    def test_process_basic_text_with_stemming(self, processor):
        """Basic text processing with stemming should work correctly."""
        text = "Machine Learning and Artificial Intelligence"
        result = processor.process(text)

        assert "machin" in result
        assert "learn" in result
        assert "artifici" in result
        assert "intellig" in result

        assert "and" not in result

        assert isinstance(result, str)

    def test_process_without_stemming(self, processor):
        """Processing without stemming should preserve word forms."""
        text = "Machine Learning"

        result = processor.process(text, "exact")

        assert "machine" in result
        assert "learning" in result

    def test_process_with_config(self, processor):
        """Processing with specific config should work."""
        text = "Machine Learning"

        default_result = processor.process(text, "default")

        exact_result = processor.process(text, "exact")

        assert default_result != exact_result
        assert "machin" in default_result
        assert "machine" in exact_result

    def test_lowercase_processing(self, processor):
        """Lowercase processing should work correctly."""
        text = "MACHINE Learning MiXeD CaSe"
        result = processor.process(text)

        assert result.lower() == result
        assert "machin" in result
        assert "learn" in result

    def test_accent_removal(self, processor):
        """Accent removal should work correctly."""
        text = "café résumé naïve"
        result = processor.process(text)

        assert "cafe" in result or "caf" in result
        assert "resum" in result
        assert "naiv" in result

    def test_camelcase_splitting(self, processor):
        """CamelCase splitting should work correctly."""
        text = "MachineLearning DeepLearning NeuralNetwork"
        result = processor.process(text)

        assert "machin" in result
        assert "learn" in result
        assert "deep" in result
        assert "neural" in result
        assert "network" in result

    def test_full_processing_pipeline(self, processor):
        """Full text processing pipeline test."""
        text = "machine-learning, neural_networks & computer.vision"
        result = processor.process(text)

        assert "machin" in result
        assert "learn" in result
        assert "neural" in result
        assert "network" in result
        assert "comput" in result
        assert "vision" in result

    def test_stopword_removal(self, processor):
        """Stop words should be removed."""
        text = "the quick brown fox and the lazy dog"
        result = processor.process(text)

        assert "quick" in result
        assert "brown" in result
        assert "fox" in result
        assert "lazi" in result
        assert "dog" in result

        assert "the" not in result
        assert "and" not in result

    def test_length_filtering(self, processor):
        """Tokens should be filtered by length."""
        text = "a bb ccc dddd eeeee"
        result = processor.process(text)

        # Short tokens should be removed (min_length=2 by default)
        assert "a" not in result

        # Tokens >= 2 chars should remain
        assert "bb" in result
        assert "ccc" in result
        assert "dddd" in result
        assert "eeeee" in result or "eeee" in result  # May be stemmed

    def test_stemming(self, processor):
        """Stemming should reduce words to roots."""
        text = "running runner runs jumped jumping"
        result = processor.process(text)

        # Should have stemmed forms
        words = result.split()

        # All run variants should stem similarly
        assert any("run" in w for w in words)
        assert any("jump" in w for w in words)

        # Some basic stemming should occur
        assert len(set(words)) < 5  # Fewer unique stems than original words

    def test_no_stemming_config(self, processor):
        """Exact config should not apply stemming."""
        text = "running runner runs"

        # With stemming
        stemmed = processor.process(text, "default")

        # Without stemming
        exact = processor.process(text, "exact")

        # Should be different
        assert stemmed != exact
        assert "running" in exact
        assert "runner" in exact
        assert "runs" in exact

    def test_unicode_handling(self, processor):
        """Unicode text should be handled properly."""
        text = "Müller François Пётр 北京大学"
        result = processor.process(text)

        # Should not crash and produce some output
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_text(self, processor):
        """Empty text should be handled gracefully."""
        result = processor.process("")
        assert result == ""

        result = processor.process("   ")
        assert result == ""

    def test_tokenize_method(self, processor):
        """tokenize() should return raw tokens without processing."""
        text = "Machine-Learning, Neural_Networks & Computer.Vision!"
        tokens = processor.tokenize(text)

        # Should return raw tokens (not processed)
        expected_tokens = [
            "Machine",
            "Learning",
            "Neural",
            "Networks",
            "Computer",
            "Vision",
        ]

        for token in expected_tokens:
            assert token in tokens

    def test_ngram_generation(self, processor):
        """N-gram generation should work for fuzzy matching."""
        text = "machine learning"
        ngrams = processor.generate_ngrams(text)

        assert isinstance(ngrams, str)
        assert len(ngrams) > 0

        # Should contain 3-grams
        ngram_list = ngrams.split()
        assert len(ngram_list) > 0

        # Each n-gram should be 3 characters
        for ngram in ngram_list:
            assert len(ngram) == 3

    def test_ngram_different_n(self, processor):
        """N-gram generation with different n values."""
        text = "machine"

        ngrams_3 = processor.generate_ngrams(text, n=3)
        ngrams_2 = processor.generate_ngrams(text, n=2)

        # Should have different counts
        count_3 = len(ngrams_3.split())
        count_2 = len(ngrams_2.split())

        # 2-grams should be more numerous
        assert count_2 > count_3

    def test_keyword_extraction(self, processor):
        """Keyword extraction should identify important terms."""
        text = """
        Machine learning is a method of data analysis that automates analytical
        model building. Machine learning algorithms build mathematical models
        based on training data in order to make predictions or decisions.
        """

        keywords = processor.extract_keywords(text)

        assert isinstance(keywords, list)
        assert len(keywords) > 0
        assert len(keywords) <= 10  # Default max

        # Should include important stemmed terms
        keywords_str = " ".join(keywords)
        # At least some of these stemmed forms should appear
        assert any(
            term in keywords_str for term in ["machin", "learn", "data", "model"]
        )

    def test_keyword_extraction_frequency(self, processor):
        """Keywords should be ordered by frequency."""
        text = "machine machine machine learning learning data"

        keywords = processor.extract_keywords(text, max_keywords=5)

        # "machin" (stemmed from "machine") should appear first (most frequent)
        assert len(keywords) > 0
        assert "machin" == keywords[0]  # Most frequent should be first

    def test_remove_accents_private_method(self, processor):
        """_remove_accents should work correctly."""
        text = "café résumé naïve"
        result = processor._remove_accents(text)

        assert result == "cafe resume naive"

    def test_split_camelcase_private_method(self, processor):
        """_split_camelcase should work correctly."""
        text = "MachineLearning"
        result = processor._split_camelcase(text)

        assert result == "Machine Learning"

        # Multiple words
        text = "DeepNeuralNetwork"
        result = processor._split_camelcase(text)

        assert result == "Deep Neural Network"

    def test_tokenize_private_method(self, processor):
        """_tokenize should extract word tokens."""
        text = "machine-learning, neural_networks & computer.vision!"
        tokens = processor._tokenize(text)

        expected_tokens = [
            "machine",
            "learning",
            "neural",
            "networks",
            "computer",
            "vision",
        ]

        for token in expected_tokens:
            assert token in tokens

    def test_stem_private_method(self, processor):
        """_stem should perform Porter stemming."""
        # Test common suffixes
        assert processor._stem("running") == "runn"
        assert processor._stem("jumped") == "jump"
        assert processor._stem("happiness") == "happi"  # -ness removal
        assert processor._stem("computation") == "comput"  # -tion removal

        # Test plurals
        assert processor._stem("cats") == "cat"
        assert processor._stem("boxes") == "box"
        assert processor._stem("flies") == "fli"  # Porter stems to 'fli'

        # Words too short should not be stemmed
        assert processor._stem("cat") == "cat"  # Too short to stem
        assert processor._stem("is") == "is"
        assert processor._stem("a") == "a"

    def test_processor_consistency(self, processor):
        """Same input should produce same output."""
        text = "Machine Learning and Artificial Intelligence"

        result1 = processor.process(text)
        result2 = processor.process(text)

        assert result1 == result2

    def test_different_configs_produce_different_results(self, processor):
        """Different configs should produce different results."""
        text = "MachineLearning is GREAT!"

        default_result = processor.process(text, "default")
        exact_result = processor.process(text, "exact")
        keyword_result = processor.process(text, "keyword")

        # Default vs exact should differ (stemming)
        assert default_result != exact_result

        # Keyword processes but doesn't stem
        assert keyword_result != default_result


class TestSynonymExpander:
    """Test SynonymExpander class."""

    @pytest.fixture
    def expander(self):
        """Create a synonym expander for testing."""
        return SynonymExpander()

    def test_default_synonyms(self, expander):
        """Should have default academic synonyms."""
        assert "ml" in expander.synonyms
        assert "ai" in expander.synonyms
        assert "nn" in expander.synonyms
        assert "nlp" in expander.synonyms

        # Check expansions
        assert "machine learning" in expander.synonyms["ml"]
        assert "artificial intelligence" in expander.synonyms["ai"]
        assert "neural network" in expander.synonyms["nn"]

    def test_custom_synonyms(self):
        """Custom synonyms should be added."""
        custom_synonyms = {
            "db": ["database", "data base"],
            "xyz": ["test expansion"],
        }

        expander = SynonymExpander(custom_synonyms)

        # Should have both default and custom
        assert "ml" in expander.synonyms  # Default
        assert "db" in expander.synonyms  # Override default with custom
        assert "xyz" in expander.synonyms  # New custom

    def test_reverse_mapping(self, expander):
        """Reverse mapping should work for synonym lookup."""
        assert "machine learning" in expander.reverse_synonyms
        assert expander.reverse_synonyms["machine learning"] == "ml"

        assert "artificial intelligence" in expander.reverse_synonyms
        assert expander.reverse_synonyms["artificial intelligence"] == "ai"

    def test_expand_simple_term(self, expander):
        """Simple term expansion should work."""
        text = "ml applications"
        result = expander.expand(text)

        # Should expand ml to include synonyms
        assert "OR" in result
        assert "machine learning" in result.lower()

    def test_expand_phrase(self, expander):
        """Multi-word phrase expansion should work."""
        text = "machine learning techniques"
        result = expander.expand(text)

        # Should expand the phrase
        assert "OR" in result
        assert "ml" in result.lower()

    def test_expand_multiple_terms(self, expander):
        """Multiple expandable terms should work."""
        text = "ml and ai research"
        result = expander.expand(text)

        # Should expand both terms
        assert "machine learning" in result.lower()
        assert "artificial intelligence" in result.lower()

    def test_expand_no_matches(self, expander):
        """Text with no expandable terms should remain unchanged."""
        text = "computer science research"
        result = expander.expand(text)

        # Should be unchanged
        assert result == text

    def test_expand_case_insensitive(self, expander):
        """Expansion should be case insensitive."""
        text1 = "ML applications"
        text2 = "ml applications"
        text3 = "Ml applications"

        result1 = expander.expand(text1)
        result2 = expander.expand(text2)
        result3 = expander.expand(text3)

        # Should all expand similarly
        assert "machine learning" in result1.lower()
        assert "machine learning" in result2.lower()
        assert "machine learning" in result3.lower()

    def test_expand_with_context(self, expander):
        """Expansion should work in context."""
        text = "Recent advances in ml and nlp"
        result = expander.expand(text)

        # Should expand both abbreviations
        assert "machine learning" in result.lower()
        assert "natural language processing" in result.lower()

    def test_expand_already_expanded(self, expander):
        """Already expanded terms should be handled correctly."""
        text = "machine learning and ml"
        result = expander.expand(text)

        # Should handle both the full term and abbreviation
        assert isinstance(result, str)
        assert len(result) > 0
        assert result.count("OR") >= 1

    def test_expand_performance(self, expander):
        """Expansion should be reasonably fast."""
        import time

        # Long text with many terms
        text = " ".join(["ml", "ai", "nlp", "cv"] * 100)

        start_time = time.time()
        result = expander.expand(text)
        end_time = time.time()

        # Should complete quickly
        assert end_time - start_time < 1.0  # Less than 1 second
        assert isinstance(result, str)

    def test_expand_empty_text(self, expander):
        """Empty text should be handled gracefully."""
        assert expander.expand("") == ""
        assert expander.expand("   ") == "   "

    def test_get_synonyms_method(self, expander):
        """get_synonyms should return all synonyms for a term."""
        # Test abbreviation
        synonyms = expander.get_synonyms("ml")
        assert "machine learning" in synonyms

        # Test full form
        synonyms = expander.get_synonyms("machine learning")
        assert "ml" in synonyms

        # Test non-existent term
        synonyms = expander.get_synonyms("xyz")
        assert synonyms == []

    def test_custom_synonyms_override(self):
        """Custom synonyms should override defaults."""
        custom_synonyms = {
            "ml": ["machine language"],  # Different from default
        }

        expander = SynonymExpander(custom_synonyms)

        # Should use custom definition
        assert expander.synonyms["ml"] == ["machine language"]
        assert "machine learning" not in expander.synonyms["ml"]

    def test_bidirectional_expansion(self, expander):
        """Both abbreviations and full terms should be expandable."""
        # Abbreviation to full term
        result1 = expander.expand("ml")
        assert "machine learning" in result1.lower()

        # Full term to abbreviation
        result2 = expander.expand("machine learning")
        assert "ml" in result2.lower()
