"""Search functionality for bibliography management.

This module provides full-text search, faceted search, query parsing,
and result highlighting for bibliography entries.

Main components:
- SearchEngine: Core search orchestrator
- SearchService: High-level service with entry caching
- Query parsing with field-specific searches
- Multiple backends (Memory, Whoosh)
- Result highlighting and ranking
"""

from .backends import (
    BackendResult,
    IndexError,
    QueryError,
    SearchBackend,
    SearchError,
    SearchQuery,
)
from .backends.base import SearchMatch
from .backends.memory import MemoryBackend
from .engine import (
    SearchEngine,
    SearchEngineBuilder,
    SearchService,
    create_default_engine,
    create_memory_engine,
)
from .facets import (
    DateHistogramFacet,
    FacetAggregator,
    FacetConfiguration,
    FacetExtractor,
    FacetFilter,
    FacetType,
    RangeFacet,
    TermsFacet,
)
from .highlighting import (
    FieldHighlights,
    Highlight,
    Highlighter,
    SnippetGenerator,
)
from .indexing import (
    AnalyzerManager,
    AuthorAnalyzer,
    EntryIndexer,
    FieldConfiguration,
    FieldDefinition,
    FieldType,
    IndexingPipeline,
    KeywordAnalyzer,
    SimpleAnalyzer,
    SpellChecker,
    StandardAnalyzer,
    StemmingAnalyzer,
    TextAnalyzer,
)
from .query import (
    BooleanQuery,
    FieldQuery,
    FuzzyQuery,
    ParsedQuery,
    PhraseQuery,
    QueryExpander,
    QueryParser,
    QuerySuggestion,
    RangeQuery,
    TermQuery,
    WildcardQuery,
)
from .ranking import (
    BM25Ranker,
    BoostingRanker,
    CompoundRanker,
    FieldWeights,
    RankingAlgorithm,
    RecencyRanker,
    ScoringContext,
    TFIDFRanker,
    compute_bm25_score,
    compute_tfidf_score,
)
from .results import (
    Facet,
    FacetValue,
    SearchResultCollection,
    SearchStatistics,
    SearchSuggestion,
    SortOrder,
    create_empty_results,
    merge_result_collections,
)

__all__ = [
    # Main classes
    "SearchEngine",
    "SearchEngineBuilder",
    "SearchService",
    "create_default_engine",
    "create_memory_engine",
    # Query parsing
    "QueryParser",
    "QueryExpander",
    "ParsedQuery",
    "TermQuery",
    "PhraseQuery",
    "FieldQuery",
    "BooleanQuery",
    "WildcardQuery",
    "FuzzyQuery",
    "RangeQuery",
    "QuerySuggestion",
    # Results
    "SearchMatch",
    "SearchResultCollection",
    "SearchStatistics",
    "SearchSuggestion",
    "SortOrder",
    "Facet",
    "FacetValue",
    "create_empty_results",
    "merge_result_collections",
    # Highlighting
    "Highlight",
    "FieldHighlights",
    "Highlighter",
    "SnippetGenerator",
    # Indexing
    "EntryIndexer",
    "IndexingPipeline",
    "FieldConfiguration",
    "FieldDefinition",
    "FieldType",
    "TextAnalyzer",
    "SimpleAnalyzer",
    "StandardAnalyzer",
    "StemmingAnalyzer",
    "KeywordAnalyzer",
    "AuthorAnalyzer",
    "AnalyzerManager",
    "SpellChecker",
    # Backends
    "SearchBackend",
    "SearchQuery",
    "BackendResult",
    "SearchError",
    "IndexError",
    "QueryError",
    "MemoryBackend",
    # Ranking
    "RankingAlgorithm",
    "BM25Ranker",
    "TFIDFRanker",
    "BoostingRanker",
    "RecencyRanker",
    "CompoundRanker",
    "FieldWeights",
    "ScoringContext",
    "compute_bm25_score",
    "compute_tfidf_score",
    # Faceting
    "FacetConfiguration",
    "FacetExtractor",
    "FacetAggregator",
    "FacetFilter",
    "FacetType",
    "TermsFacet",
    "RangeFacet",
    "DateHistogramFacet",
]

__version__ = "1.0.0"
