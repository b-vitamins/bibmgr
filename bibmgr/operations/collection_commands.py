"""Command classes for collection operations."""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class CreateCollectionCommand:
    """Command to create a new collection."""

    name: str
    description: str | None = None
    tags: list[str] | None = None


@dataclass
class AddToCollectionCommand:
    """Command to add entries to a collection."""

    collection_id: UUID | str
    entry_keys: list[str]


@dataclass
class RemoveFromCollectionCommand:
    """Command to remove entries from a collection."""

    collection_id: UUID | str
    entry_keys: list[str]


@dataclass
class MergeCollectionsCommand:
    """Command to merge multiple collections."""

    source_ids: list[UUID | str]
    target_name: str
    description: str | None = None
    combine_tags: bool = False
    delete_sources: bool = True
