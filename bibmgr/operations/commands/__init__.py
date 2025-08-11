"""Command pattern implementation for operations."""

from .create import BulkCreateHandler, CreateCommand, CreateHandler
from .delete import DeleteCommand, DeleteHandler
from .merge import AutoMergeHandler, MergeCommand, MergeHandler
from .update import FieldChange, PatchHandler, UpdateCommand, UpdateHandler

__all__ = [
    # Create
    "CreateCommand",
    "CreateHandler",
    "BulkCreateHandler",
    # Update
    "UpdateCommand",
    "UpdateHandler",
    "FieldChange",
    "PatchHandler",
    # Delete
    "DeleteCommand",
    "DeleteHandler",
    # Merge
    "MergeCommand",
    "MergeHandler",
    "AutoMergeHandler",
]
