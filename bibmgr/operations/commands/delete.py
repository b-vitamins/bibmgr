"""Delete command with cascading support."""

from dataclasses import dataclass

from bibmgr.storage.events import EventBus, EventType
from bibmgr.storage.metadata import MetadataStore
from bibmgr.storage.repository import CollectionRepository, EntryRepository

from ..results import OperationResult, ResultStatus
from ..validators.preconditions import DeletePreconditions


@dataclass
class DeleteCommand:
    """Command to delete an entry."""

    key: str
    cascade: bool = False
    cascade_notes: bool = False
    cascade_metadata: bool = False
    cascade_files: bool = False
    force: bool = False


class DeleteHandler:
    """Handles entry deletion with cascading."""

    def __init__(
        self,
        repository: EntryRepository,
        collection_repository: CollectionRepository,
        metadata_store: MetadataStore,
        event_bus: EventBus,
    ):
        self.repository = repository
        self.collection_repository = collection_repository
        self.metadata_store = metadata_store
        self.event_bus = event_bus
        self.preconditions = DeletePreconditions()

    def execute(self, command: DeleteCommand) -> OperationResult:
        """Execute delete command."""
        violations = self.preconditions.check(command)
        if violations:
            return OperationResult(
                status=ResultStatus.VALIDATION_FAILED,
                entity_id=command.key,
                errors=violations,
                message="Precondition validation failed",
            )

        entry = self.repository.find(command.key)
        if not entry:
            return OperationResult(
                status=ResultStatus.NOT_FOUND,
                entity_id=command.key,
                message="Entry not found",
            )

        if not command.force:
            references = self._check_references(command.key)
            if references:
                return OperationResult(
                    status=ResultStatus.CONFLICT,
                    entity_id=command.key,
                    message="Entry has references",
                    data={"references": references},
                )

        cascaded = []

        try:
            if hasattr(self.repository, "transaction"):
                ctx_manager = self.repository.transaction()  # type: ignore
            else:
                from contextlib import nullcontext

                ctx_manager = nullcontext()

            with ctx_manager:
                collections = self._remove_from_collections(command.key)
                if collections:
                    cascaded.append(f"Removed from {len(collections)} collections")

                if command.cascade_metadata:
                    try:
                        self.metadata_store.delete_metadata(command.key)
                        cascaded.append("Deleted metadata")
                    except Exception:
                        pass

                if command.cascade_notes:
                    try:
                        notes = self.metadata_store.get_notes(command.key)
                        for note in notes:
                            self.metadata_store.delete_note(command.key, note.id)
                        if notes:
                            cascaded.append(f"Deleted {len(notes)} notes")
                    except Exception:
                        pass

                self.repository.delete(command.key)

                from datetime import datetime

                from bibmgr.storage.events import Event

                event = Event(
                    type=EventType.ENTRY_DELETED,
                    timestamp=datetime.now(),
                    data={
                        "entry": entry,
                        "entry_key": command.key,
                        "cascaded": cascaded,
                    },
                )
                self.event_bus.publish(event)

            return OperationResult(
                status=ResultStatus.SUCCESS,
                entity_id=command.key,
                message="Entry deleted successfully",
                data={"deleted_entry": entry, "cascaded": cascaded},
            )

        except Exception as e:
            return OperationResult(
                status=ResultStatus.ERROR,
                entity_id=command.key,
                message="Failed to delete entry",
                errors=[str(e)],
            )

    def _check_references(self, key: str) -> list[str]:
        """Check for references to this entry."""
        references = []

        all_entries = self.repository.find_all()
        for entry in all_entries:
            if hasattr(entry, "crossref") and entry.crossref == key:
                references.append(f"Cross-referenced by {entry.key}")

        return references

    def _remove_from_collections(self, key: str) -> list[str]:
        """Remove entry from all collections."""
        affected = []

        try:
            for collection in self.collection_repository.find_all():
                if collection.entry_keys and key in collection.entry_keys:
                    updated = collection.remove_entry(key)
                    self.collection_repository.save(updated)
                    affected.append(collection.name)
        except Exception:
            pass

        return affected
