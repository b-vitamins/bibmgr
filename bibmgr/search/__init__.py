"""Modern search engine for bibliography management.

This module provides a fast, feature-rich search engine designed
specifically for academic bibliography search with a CLI-first approach.
"""

# Import only what's implemented so far
from bibmgr.search.models import SearchResult, SearchHit, Entry, EntryType

__all__ = [
    "SearchResult",
    "SearchHit",
    "Entry",
    "EntryType",
]

# These will be added as we implement them
# from bibmgr.search.engine import SearchEngine
# from bibmgr.search.query import Query, QueryParser
