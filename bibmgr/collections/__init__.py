"""Collection and organization system for bibliography entries.

This package provides:
- Collection management with hierarchical organization
- Smart collections with saved queries
- Tag management with hierarchical paths
- Collection statistics and analytics
"""

from .models import (
    Collection,
    SmartCollection,
    CollectionStats,
    CollectionQuery,
    CollectionPredicate,
    PredicateOperator,
)
from .manager import CollectionManager
from .tags import TagManager, TagHierarchy

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
