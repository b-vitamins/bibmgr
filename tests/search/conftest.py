"""Shared fixtures for search module tests."""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from bibmgr.core.fields import EntryType
from bibmgr.core.models import Entry
from bibmgr.storage.events import EventBus
from bibmgr.storage.repository import EntryRepository


@pytest.fixture
def temp_index_dir():
    """Temporary directory for search index files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_entries_for_search() -> list[Entry]:
    """Sample entries with diverse content for search testing."""
    return [
        Entry(
            key="knuth1984",
            type=EntryType.ARTICLE,
            author="Donald E. Knuth",
            title="The TeXbook",
            journal="Computers & Typesetting",
            year=1984,
            abstract="A comprehensive guide to TeX typesetting system",
            keywords=("tex", "typesetting", "documentation"),
            tags=("classic", "reference"),
        ),
        Entry(
            key="lamport1994",
            type=EntryType.BOOK,
            author="Leslie Lamport",
            title="LaTeX: A Document Preparation System",
            publisher="Addison-Wesley",
            year=1994,
            abstract="The definitive guide to LaTeX document preparation",
            keywords=("latex", "typesetting", "documentation"),
            isbn="0201529831",
        ),
        Entry(
            key="turing1950",
            type=EntryType.ARTICLE,
            author="Alan M. Turing",
            title="Computing Machinery and Intelligence",
            journal="Mind",
            year=1950,
            volume="59",
            number="236",
            pages="433--460",
            abstract="Can machines think? This paper introduces the Turing Test",
            keywords=("artificial intelligence", "turing test", "philosophy"),
            doi="10.1093/mind/LIX.236.433",
        ),
        Entry(
            key="shannon1948",
            type=EntryType.ARTICLE,
            author="Claude E. Shannon",
            title="A Mathematical Theory of Communication",
            journal="Bell System Technical Journal",
            year=1948,
            abstract="Foundation of information theory and digital communication",
            keywords=("information theory", "communication", "entropy"),
        ),
        Entry(
            key="mccarthy2006",
            type=EntryType.INPROCEEDINGS,
            author="John McCarthy",
            title="Recursive Functions of Symbolic Expressions",
            booktitle="History of Lisp",
            year=2006,  # Republished
            abstract="The original paper introducing LISP programming language",
            keywords=("lisp", "functional programming", "ai"),
        ),
        Entry(
            key="berners-lee1989",
            type=EntryType.TECHREPORT,
            author="Tim Berners-Lee",
            title="Information Management: A Proposal",
            institution="CERN",
            year=1989,
            abstract="The original proposal for the World Wide Web",
            keywords=("www", "web", "hypertext", "internet"),
            url="https://www.w3.org/History/1989/proposal.html",
        ),
        Entry(
            key="goodfellow2016",
            type=EntryType.BOOK,
            author="Ian Goodfellow and Yoshua Bengio and Aaron Courville",
            title="Deep Learning",
            publisher="MIT Press",
            year=2016,
            abstract="Comprehensive textbook on deep learning and neural networks",
            keywords=("deep learning", "neural networks", "machine learning", "ai"),
            isbn="0262035618",
        ),
        Entry(
            key="vaswani2017",
            type=EntryType.INPROCEEDINGS,
            author="Ashish Vaswani and Noam Shazeer and Niki Parmar and Jakob Uszkoreit",
            title="Attention Is All You Need",
            booktitle="Advances in Neural Information Processing Systems",
            year=2017,
            abstract="Introducing the Transformer architecture for NLP",
            keywords=("transformer", "attention", "nlp", "deep learning"),
            tags=("breakthrough", "influential"),
        ),
        Entry(
            key="lecun1998",
            type=EntryType.ARTICLE,
            author="Yann LeCun and Léon Bottou and Yoshua Bengio and Patrick Haffner",
            title="Gradient-based learning applied to document recognition",
            journal="Proceedings of the IEEE",
            year=1998,
            volume="86",
            number="11",
            pages="2278--2324",
            abstract="Convolutional neural networks for image recognition",
            keywords=(
                "cnn",
                "convolutional neural networks",
                "computer vision",
                "mnist",
            ),
        ),
        Entry(
            key="page1999",
            type=EntryType.TECHREPORT,
            author="Lawrence Page and Sergey Brin and Rajeev Motwani and Terry Winograd",
            title="The PageRank Citation Ranking: Bringing Order to the Web",
            institution="Stanford InfoLab",
            year=1999,
            abstract="The algorithm behind Google search engine ranking",
            keywords=("pagerank", "search", "web", "graph algorithms"),
        ),
    ]


@pytest.fixture
def search_queries() -> list[dict[str, Any]]:
    """Sample search queries with expected behavior."""
    return [
        # Simple text queries
        {"query": "machine learning", "description": "Simple text search"},
        {"query": "deep learning", "description": "Exact phrase"},
        {"query": '"neural networks"', "description": "Quoted phrase"},
        # Field-specific queries
        {"query": "author:knuth", "description": "Author field search"},
        {"query": "year:2016", "description": "Exact year"},
        {"query": "year:2015..2020", "description": "Year range"},
        {"query": "journal:Nature", "description": "Journal search"},
        {"query": 'title:"deep learning"', "description": "Title phrase search"},
        # Boolean queries
        {"query": "machine AND learning", "description": "AND operator"},
        {"query": "tex OR latex", "description": "OR operator"},
        {"query": "neural NOT convolutional", "description": "NOT operator"},
        {"query": "(machine OR deep) AND learning", "description": "Grouped boolean"},
        # Wildcard queries
        {"query": "learn*", "description": "Prefix wildcard"},
        {"query": "*learning", "description": "Suffix wildcard"},
        {"query": "ne?ral", "description": "Single char wildcard"},
        # Fuzzy queries
        {"query": "nueral~", "description": "Fuzzy search"},
        {"query": "machne~2", "description": "Fuzzy with distance"},
        # Boost queries
        {"query": "learning^2.0", "description": "Term boosting"},
        {"query": "title:learning^3.0 abstract:learning", "description": "Field boost"},
        # Complex queries
        {
            "query": 'author:"Yoshua Bengio" AND (deep OR neural) AND year:2010..2020',
            "description": "Complex multi-field query",
        },
        {
            "query": "keywords:ai -keywords:philosophy",
            "description": "Exclude specific keyword",
        },
    ]


@pytest.fixture
def field_config() -> dict[str, Any]:
    """Sample field configuration for search indexing."""
    return {
        "fields": {
            "title": {"boost": 2.0, "analyzer": "default"},
            "author": {"boost": 1.5, "analyzer": "exact"},
            "abstract": {"boost": 1.0, "analyzer": "default"},
            "keywords": {"boost": 1.2, "analyzer": "keyword"},
            "journal": {"boost": 1.0, "analyzer": "exact"},
            "year": {"type": "numeric"},
        },
        "enable_fuzzy": True,
        "enable_stemming": True,
        "enable_synonyms": True,
    }


@pytest.fixture
def synonym_config() -> dict[str, list[str]]:
    """Synonym configuration for query expansion."""
    return {
        "ml": ["machine learning", "machinelearning"],
        "ai": ["artificial intelligence", "artificialintelligence"],
        "nn": ["neural network", "neuralnetwork"],
        "nlp": ["natural language processing"],
        "cv": ["computer vision"],
        "cnn": ["convolutional neural network"],
        "rnn": ["recurrent neural network"],
    }


@pytest.fixture
def mock_repository(sample_entries_for_search):
    """Mock entry repository for testing."""
    repo = Mock(spec=EntryRepository)

    # Create a dictionary for quick lookup
    entries_dict = {entry.key: entry for entry in sample_entries_for_search}

    # Mock find method
    repo.find.side_effect = lambda key: entries_dict.get(key)

    # Mock find_all method
    repo.find_all.return_value = sample_entries_for_search

    # Mock count method
    repo.count.return_value = len(sample_entries_for_search)

    return repo


@pytest.fixture
def mock_event_bus():
    """Mock event bus for testing."""
    bus = Mock(spec=EventBus)
    bus.subscribers = {}

    def subscribe(event_type, handler):
        if event_type not in bus.subscribers:
            bus.subscribers[event_type] = []
        bus.subscribers[event_type].append(handler)

    def publish(event):
        if event.type in bus.subscribers:
            for handler in bus.subscribers[event.type]:
                handler(event)

    bus.subscribe.side_effect = subscribe
    bus.publish.side_effect = publish

    return bus


@pytest.fixture
def search_backend_config():
    """Configuration for search backend testing."""
    return {
        "index_dir": None,  # Will be set to temp_index_dir
        "analyzer": "default",
        "scoring": "BM25F",
        "cache_enabled": False,  # Disable for testing
    }


@pytest.fixture
def sample_text_content() -> list[dict[str, str | list[str]]]:
    """Sample text content for analyzer testing."""
    return [
        {
            "text": "Machine Learning and Artificial Intelligence",
            "field": "title",
            "expected_tokens": ["machine", "learning", "artificial", "intelligence"],
        },
        {
            "text": "The quick brown fox jumps over the lazy dog",
            "field": "abstract",
            "expected_tokens": ["quick", "brown", "fox", "jumps", "lazy", "dog"],
        },
        {
            "text": "deep-learning, neural-networks, computer-vision",
            "field": "keywords",
            "expected_tokens": ["deep-learning", "neural-networks", "computer-vision"],
        },
        {
            "text": "Bengio, Yoshua and LeCun, Yann",
            "field": "author",
            "expected_tokens": ["bengio", "yoshua", "lecun", "yann"],
        },
        {
            "text": "IEEE Transactions on Pattern Analysis",
            "field": "journal",
            "expected_tokens": ["ieee transactions on pattern analysis"],
        },
    ]


@pytest.fixture
def sample_highlights() -> list[dict[str, Any]]:
    """Sample data for highlighting tests."""
    return [
        {
            "text": "Machine learning is a subset of artificial intelligence",
            "terms": ["machine", "learning"],
            "expected": [
                "<mark>Machine</mark> <mark>learning</mark> is a subset of artificial intelligence"
            ],
        },
        {
            "text": "Deep learning uses neural networks with multiple layers",
            "terms": ["deep learning", "neural"],
            "expected": [
                "<mark>Deep learning</mark> uses <mark>neural</mark> networks with multiple layers"
            ],
        },
        {
            "text": "The transformer architecture revolutionized NLP",
            "terms": ["transformer"],
            "expected": [
                "The <mark>transformer</mark> architecture revolutionized NLP"
            ],
        },
    ]


@pytest.fixture
def query_parse_cases() -> list[dict[str, Any]]:
    """Test cases for query parsing."""
    return [
        # Simple terms
        {
            "input": "machine learning",
            "expected_terms": [("machine", None), ("learning", None)],
            "expected_operator": "AND",
        },
        # Field queries
        {
            "input": "author:bengio",
            "expected_terms": [("bengio", "author")],
            "expected_operator": None,
        },
        # Phrase queries
        {
            "input": '"deep learning"',
            "expected_terms": [("deep learning", None)],
            "expected_phrase": True,
        },
        # Boolean operators
        {
            "input": "machine AND learning",
            "expected_terms": [("machine", None), ("learning", None)],
            "expected_operator": "AND",
        },
        {
            "input": "tex OR latex",
            "expected_terms": [("tex", None), ("latex", None)],
            "expected_operator": "OR",
        },
        {
            "input": "neural NOT convolutional",
            "expected_terms": [("neural", None)],
            "expected_not_terms": [("convolutional", None)],
        },
        # Wildcards
        {
            "input": "learn*",
            "expected_terms": [("learn*", None)],
            "expected_wildcard": True,
        },
        # Fuzzy
        {
            "input": "nueral~",
            "expected_terms": [("nueral", None)],
            "expected_fuzzy": True,
        },
        # Boost
        {
            "input": "learning^2.0",
            "expected_terms": [("learning", None)],
            "expected_boost": 2.0,
        },
        # Complex
        {
            "input": 'author:"Yoshua Bengio" AND year:2016',
            "expected_terms": [("Yoshua Bengio", "author"), ("2016", "year")],
            "expected_operator": "AND",
        },
    ]


@pytest.fixture
def performance_entries(request) -> list[Entry]:
    """Generate large number of entries for performance testing."""
    count = getattr(request, "param", 1000)
    entries = []

    for i in range(count):
        entries.append(
            Entry(
                key=f"perf_{i:06d}",
                type=EntryType.ARTICLE,
                author=f"Author {i % 100} and Coauthor {i % 50}",
                title=f"Performance Test Article {i}: "
                + " ".join([f"word{j}" for j in range(i % 20)]),
                journal=f"Journal {i % 10}",
                year=2000 + (i % 25),
                volume=str(i % 50),
                pages=f"{i}--{i + 10}",
                abstract="This is a test abstract " * (i % 50),
                keywords=tuple(f"keyword{j}" for j in range(i % 5)),
                doi=f"10.1234/test.{i}",
            )
        )

    return entries


@pytest.fixture
def search_result_factory():
    """Factory for creating search results."""

    def create_result(entry: Entry, score: float = 1.0, highlights: dict | None = None):
        from bibmgr.search.backends.base import SearchMatch

        return SearchMatch(
            entry_key=entry.key,
            entry=entry,
            score=score,
            highlights=highlights or {},
        )

    return create_result


@pytest.fixture
def mock_search_backend():
    """Mock search backend for testing."""
    from unittest.mock import Mock

    backend = Mock()
    backend.index = Mock()
    backend.index_batch = Mock()
    backend.search = Mock()
    backend.delete = Mock()
    backend.clear = Mock()
    backend.commit = Mock()
    backend.get_statistics = Mock(
        return_value={
            "total_documents": 0,
            "index_size_mb": 0.0,
            "fields": [],
        }
    )
    backend.suggest = Mock(return_value=[])

    return backend
