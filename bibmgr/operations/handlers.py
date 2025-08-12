"""Handlers for collection operations."""

from typing import Any
from uuid import UUID

from ..storage.extensions.collections import CollectionExtension
from ..storage.repository import EntryRepository
from .results import OperationResult, ResultStatus


class CollectionHandler:
    """Handler for collection operations."""

    def __init__(self, storage: EntryRepository, extension: CollectionExtension):
        """Initialize collection handler.

        Args:
            storage: Entry repository for entries
            extension: Collection extension
        """
        self.storage = storage
        self.extension = extension

    def execute(self, command: Any) -> OperationResult:
        """Execute a collection command.

        Args:
            command: Command to execute

        Returns:
            Operation result
        """
        command_type = type(command).__name__

        if command_type == "CreateCollectionCommand":
            return self._handle_create_collection(command)
        elif command_type == "AddToCollectionCommand":
            return self._handle_add_to_collection(command)
        elif command_type == "RemoveFromCollectionCommand":
            return self._handle_remove_from_collection(command)
        elif command_type == "MergeCollectionsCommand":
            return self._handle_merge_collections(command)
        else:
            return OperationResult(
                status=ResultStatus.ERROR, message=f"Unknown command: {command_type}"
            )

    def _handle_create_collection(self, command) -> OperationResult:
        """Handle create collection command."""
        try:
            # Validate name
            if command.name is None:
                raise ValueError("Collection name cannot be None")
            if not command.name.strip():
                raise ValueError("Collection name cannot be empty")

            collection = self.extension.create_collection(
                name=command.name, description=command.description, tags=command.tags
            )

            return OperationResult(
                status=ResultStatus.SUCCESS,
                message=f"Collection '{command.name}' created successfully",
                entity_id=str(collection.id),
                data={"collection": collection},
            )
        except Exception as e:
            return OperationResult(
                status=ResultStatus.ERROR,
                message=f"Failed to create collection: {str(e)}",
            )

    def _handle_add_to_collection(self, command) -> OperationResult:
        """Handle add to collection command."""
        try:
            # Convert string to UUID if needed
            collection_id = command.collection_id
            if isinstance(collection_id, str):
                try:
                    collection_id = UUID(collection_id)
                except ValueError:
                    return OperationResult(
                        status=ResultStatus.ERROR,
                        message=f"Invalid collection ID: {collection_id}",
                    )

            # Check collection exists
            collection = self.extension.get_collection(collection_id)
            if not collection:
                return OperationResult(
                    status=ResultStatus.NOT_FOUND,
                    message=f"Collection not found: {collection_id}",
                )

            # Check which entries exist
            existing_keys = []
            missing_keys = []

            for key in command.entry_keys:
                if self.storage.exists(key):
                    existing_keys.append(key)
                else:
                    missing_keys.append(key)

            # Add existing entries
            if existing_keys:
                self.extension.add_to_collection(collection_id, existing_keys)

            return OperationResult(
                status=ResultStatus.SUCCESS
                if not missing_keys
                else ResultStatus.PARTIAL_SUCCESS,
                message=f"Added {len(existing_keys)} entries to collection",
                entity_id=str(collection_id),
                data={"added_count": len(existing_keys), "missing_keys": missing_keys},
                warnings=[f"{len(missing_keys)} entries not found"]
                if missing_keys
                else None,
            )
        except Exception as e:
            return OperationResult(
                status=ResultStatus.ERROR, message=f"Failed to add entries: {str(e)}"
            )

    def _handle_remove_from_collection(self, command) -> OperationResult:
        """Handle remove from collection command."""
        try:
            # Convert string to UUID if needed
            collection_id = command.collection_id
            if isinstance(collection_id, str):
                try:
                    collection_id = UUID(collection_id)
                except ValueError:
                    return OperationResult(
                        status=ResultStatus.ERROR,
                        message=f"Invalid collection ID: {collection_id}",
                    )

            # Check collection exists
            collection = self.extension.get_collection(collection_id)
            if not collection:
                return OperationResult(
                    status=ResultStatus.NOT_FOUND,
                    message=f"Collection not found: {collection_id}",
                )

            # Remove entries
            self.extension.remove_from_collection(collection_id, command.entry_keys)

            return OperationResult(
                status=ResultStatus.SUCCESS,
                message=f"Removed {len(command.entry_keys)} entries from collection",
                entity_id=str(collection_id),
            )
        except Exception as e:
            return OperationResult(
                status=ResultStatus.ERROR, message=f"Failed to remove entries: {str(e)}"
            )

    def _handle_merge_collections(self, command) -> OperationResult:
        """Handle merge collections command."""
        try:
            # Convert string IDs to UUIDs if needed
            source_ids = []
            for sid in command.source_ids:
                if isinstance(sid, str):
                    try:
                        source_ids.append(UUID(sid))
                    except ValueError:
                        return OperationResult(
                            status=ResultStatus.ERROR,
                            message=f"Invalid collection ID: {sid}",
                        )
                else:
                    source_ids.append(sid)

            # Get all source collections
            sources = []
            all_entries = set()
            all_tags = set()

            for source_id in source_ids:
                source = self.extension.get_collection(source_id)
                if not source:
                    return OperationResult(
                        status=ResultStatus.NOT_FOUND,
                        message=f"Source collection not found: {source_id}",
                    )
                sources.append(source)

                # Collect entries
                entries = self.extension.get_collection_entries(source_id)
                all_entries.update(entries)

                # Collect tags if requested
                if getattr(command, "combine_tags", False):
                    all_tags.update(source.tags)

            # Create merged collection
            merged = self.extension.create_collection(
                name=command.target_name,
                description=getattr(command, "description", None),
                tags=sorted(list(all_tags)) if all_tags else None,
            )

            # Add all entries
            if all_entries:
                self.extension.add_to_collection(merged.id, list(all_entries))

            # Delete source collections if requested
            if getattr(command, "delete_sources", True):
                for source_id in source_ids:
                    self.extension.delete_collection(source_id)

            return OperationResult(
                status=ResultStatus.SUCCESS,
                message=f"Merged {len(sources)} collections into '{command.target_name}'",
                entity_id=str(merged.id),
                data={
                    "collection": merged,
                    "entry_count": len(all_entries),
                    "sources_deleted": getattr(command, "delete_sources", True),
                },
            )
        except Exception as e:
            return OperationResult(
                status=ResultStatus.ERROR,
                message=f"Failed to merge collections: {str(e)}",
            )
