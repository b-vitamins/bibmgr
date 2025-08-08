"""Collection and organization system for bibliography entries.

This package provides:
- Collection management with hierarchical organization
- Smart collections with saved queries
- Tag management with hierarchical paths
- Collection statistics and analytics
"""

from .manager import CollectionManager
from .models import (
    Collection,
    CollectionPredicate,
    CollectionQuery,
    CollectionStats,
    PredicateOperator,
    SmartCollection,
)
from .tags import TagHierarchy, TagManager

__all__ = [
    # Models
    "Collection",
    "SmartCollection",
    "CollectionStats",
    "CollectionQuery",
    "CollectionPredicate",
    "PredicateOperator",
    # Managers
    "CollectionManager",
    "TagManager",
    "TagHierarchy",
]
