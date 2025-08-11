"""Import workflow using existing infrastructure."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from bibmgr.core.duplicates import DuplicateDetector
from bibmgr.core.models import Entry
from bibmgr.storage.events import Event, EventBus, EventType
from bibmgr.storage.importers import BibtexImporter, JsonImporter, RisImporter
from bibmgr.storage.repository import RepositoryManager

from ..commands import CreateCommand, CreateHandler, MergeHandler, UpdateHandler
from ..policies import ConflictPolicy, ConflictResolution
from ..results import StepResult, WorkflowResult


class ImportFormat(Enum):
    """Supported import formats."""

    BIBTEX = "bibtex"
    RIS = "ris"
    JSON = "json"
    AUTO = "auto"


@dataclass
class ImportWorkflowConfig:
    """Configuration for import workflow."""

    validate: bool = True
    check_duplicates: bool = True
    conflict_resolution: ConflictResolution = ConflictResolution.ASK
    merge_duplicates: bool = False
    update_existing: bool = False
    dry_run: bool = False
    tags: list[str] | None = None
    collection: str | None = None


class ImportWorkflow:
    """Orchestrates the complete import process."""

    def __init__(
        self,
        manager: RepositoryManager,
        event_bus: EventBus,
        conflict_policy: ConflictPolicy | None = None,
    ):
        self.manager = manager
        self.event_bus = event_bus
        self.conflict_policy = conflict_policy or ConflictPolicy()

        self.create_handler = CreateHandler(manager.entries, event_bus)
        self.update_handler = UpdateHandler(manager.entries, event_bus)
        self.merge_handler = MergeHandler(manager.entries, event_bus)

        self.importers = {
            ImportFormat.BIBTEX: BibtexImporter(),
            ImportFormat.RIS: RisImporter(),
            ImportFormat.JSON: JsonImporter(),
        }

    def execute(
        self,
        source: Path | str,
        format: ImportFormat = ImportFormat.AUTO,
        config: ImportWorkflowConfig | None = None,
    ) -> WorkflowResult:
        """Execute import workflow."""
        config = config or ImportWorkflowConfig()

        result = WorkflowResult(workflow="import", source=str(source))

        if format == ImportFormat.AUTO:
            format = self._detect_format(source)

        parse_result = self._parse_file(source, format, config)
        result.add_step(parse_result)

        if not parse_result.success:
            result.complete()
            return result

        entries: list[Entry] = (
            parse_result.data.get("entries", []) if parse_result.data else []
        )

        for i, entry in enumerate(entries):
            event = Event(
                type=EventType.PROGRESS,
                timestamp=datetime.now(),
                data={
                    "operation": "import",
                    "current": i + 1,
                    "total": len(entries),
                    "entity_id": entry.key,
                },
            )
            self.event_bus.publish(event)

            if config.check_duplicates:
                duplicate_result = self._check_duplicate(entry, config)
                if duplicate_result.data and duplicate_result.data.get("duplicate"):
                    existing_entry = duplicate_result.data["duplicate"]
                    if config.merge_duplicates and existing_entry:
                        merge_result = self._merge_duplicate(
                            entry, existing_entry, config
                        )
                        result.add_step(merge_result)
                        continue
                    elif config.update_existing and existing_entry:
                        update_result = self._update_existing(
                            entry, existing_entry, config
                        )
                        result.add_step(update_result)
                        continue

            if self.manager.entries.exists(entry.key):
                existing = self.manager.entries.find(entry.key)
                if existing:
                    resolution = self.conflict_policy.resolve(
                        entry,
                        existing,
                        config.conflict_resolution,
                    )

                    if resolution.action == "skip":
                        result.add_step(
                            StepResult(
                                step="skip_entry",
                                success=True,
                                entity_id=entry.key,
                                message="Skipped due to conflict",
                            )
                        )
                        continue
                    elif resolution.action == "replace":
                        update_result = self._update_existing(entry, existing, config)
                        result.add_step(update_result)
                        continue
                    elif resolution.action == "rename":
                        entry = Entry.from_dict(
                            {**entry.to_dict(), "key": resolution.new_key}
                        )

            create_result = self._create_entry(entry, config)
            result.add_step(create_result)

        if config.tags or config.collection:
            post_result = self._post_process(result.successful_entities, config)
            result.add_step(post_result)

        result.complete()

        event = Event(
            type=EventType.WORKFLOW_COMPLETED,
            timestamp=datetime.now(),
            data={
                "workflow": "import",
                "source": str(source),
                "format": format.value,
                "result": result,
            },
        )
        self.event_bus.publish(event)

        return result

    def _detect_format(self, source: Path | str) -> ImportFormat:
        """Auto-detect file format."""
        path = Path(source)

        ext = path.suffix.lower()
        if ext in [".bib", ".bibtex"]:
            return ImportFormat.BIBTEX
        elif ext == ".ris":
            return ImportFormat.RIS
        elif ext == ".json":
            return ImportFormat.JSON

        try:
            content = path.read_text()[:1000]
            if "@article" in content or "@book" in content:
                return ImportFormat.BIBTEX
            elif "TY  -" in content:
                return ImportFormat.RIS
            elif "{" in content and '"key"' in content:
                return ImportFormat.JSON
        except Exception:
            pass

        return ImportFormat.BIBTEX

    def _parse_file(
        self,
        source: Path | str,
        format: ImportFormat,
        config: ImportWorkflowConfig,
    ) -> StepResult:
        """Parse file using appropriate importer."""
        try:
            importer = self.importers[format]
            entries, errors = importer.import_file(Path(source))

            if errors and not entries:
                return StepResult(
                    step="parse",
                    success=False,
                    message="Failed to parse file",
                    errors=errors,
                )

            return StepResult(
                step="parse",
                success=True,
                message=f"Parsed {len(entries)} entries",
                data={"entries": entries},
                warnings=errors if errors else None,
            )

        except Exception as e:
            return StepResult(
                step="parse",
                success=False,
                message="Failed to parse file",
                errors=[str(e)],
            )

    def _check_duplicate(
        self, entry: Entry, config: ImportWorkflowConfig
    ) -> StepResult:
        """Check for duplicates of entry."""
        all_entries = self.manager.entries.find_all()

        temp_entries = all_entries + [entry]
        detector = DuplicateDetector(temp_entries)
        duplicate_groups = detector.find_duplicates()

        duplicates = []
        for group in duplicate_groups:
            if any(e.key == entry.key for e in group):
                duplicates = [e for e in group if e.key != entry.key]
                break

        if duplicates:
            return StepResult(
                step="check_duplicate",
                success=True,
                entity_id=entry.key,
                message=f"Found {len(duplicates)} potential duplicates",
                data={
                    "duplicate": duplicates[0],
                    "all_duplicates": duplicates,
                },
            )

        return StepResult(
            step="check_duplicate",
            success=True,
            entity_id=entry.key,
            message="No duplicates found",
            data={"duplicate": None},
        )

    def _create_entry(self, entry: Entry, config: ImportWorkflowConfig) -> StepResult:
        """Create new entry."""
        command = CreateCommand(
            entry=entry, force=not config.validate, dry_run=config.dry_run
        )

        result = self.create_handler.execute(command)

        return StepResult(
            step="create",
            success=result.status.is_success(),
            entity_id=entry.key,
            message=result.message,
            errors=result.errors,
        )

    def _update_existing(
        self, new_entry: Entry, existing_entry: Entry, config: ImportWorkflowConfig
    ) -> StepResult:
        """Update existing entry with new data."""
        from ..commands import UpdateCommand

        updates = {}
        new_data = new_entry.to_dict()
        existing_data = existing_entry.to_dict()

        for field, value in new_data.items():
            if field not in ["key", "added", "modified"]:
                if value != existing_data.get(field):
                    updates[field] = value

        if not updates:
            return StepResult(
                step="update",
                success=True,
                entity_id=existing_entry.key,
                message="No changes needed",
            )

        command = UpdateCommand(
            key=existing_entry.key, updates=updates, validate=config.validate
        )

        result = self.update_handler.execute(command)

        return StepResult(
            step="update",
            success=result.status.is_success(),
            entity_id=existing_entry.key,
            message=result.message,
            errors=result.errors,
            data={"updates": updates},
        )

    def _merge_duplicate(
        self, new_entry: Entry, existing_entry: Entry, config: ImportWorkflowConfig
    ) -> StepResult:
        """Merge new entry with existing duplicate."""
        from ..commands import MergeCommand

        temp_key = f"{new_entry.key}_import_temp"
        temp_entry = Entry.from_dict({**new_entry.to_dict(), "key": temp_key})

        if not config.dry_run:
            self.manager.entries.save(temp_entry)

        command = MergeCommand(
            source_keys=[existing_entry.key, temp_key],
            target_key=existing_entry.key,
            delete_sources=True,
        )

        result = self.merge_handler.execute(command)

        if not config.dry_run and not result.status.is_success():
            try:
                self.manager.entries.delete(temp_key)
            except Exception:
                pass

        return StepResult(
            step="merge",
            success=result.status.is_success(),
            entity_id=existing_entry.key,
            message=result.message,
            errors=result.errors,
        )

    def _post_process(
        self, entry_keys: list[str], config: ImportWorkflowConfig
    ) -> StepResult:
        """Apply tags and add to collection."""
        try:
            if config.tags and self.manager.metadata_store:
                for key in entry_keys:
                    metadata = self.manager.metadata_store.get_metadata(key)
                    metadata.add_tags(*config.tags)
                    self.manager.metadata_store.save_metadata(metadata)

            if config.collection:
                all_collections = self.manager.collections.find_all()
                matching = [c for c in all_collections if c.name == config.collection]
                if matching:
                    collection = matching[0]
                    for key in entry_keys:
                        collection = collection.add_entry(key)
                    self.manager.collections.save(collection)

            return StepResult(
                step="post_process",
                success=True,
                message="Applied tags and collection",
            )

        except Exception as e:
            return StepResult(
                step="post_process",
                success=False,
                message="Failed to apply post-processing",
                errors=[str(e)],
            )
