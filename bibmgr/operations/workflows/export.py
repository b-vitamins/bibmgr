"""Export workflow for exporting entries to various formats."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from bibmgr.core.models import Entry
from bibmgr.storage.events import Event, EventBus, EventType
from bibmgr.storage.query import Condition, Operator, Query
from bibmgr.storage.repository import RepositoryManager

from ..results import StepResult, WorkflowResult


class ExportFormat(Enum):
    """Supported export formats."""

    BIBTEX = "bibtex"
    RIS = "ris"
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass
class ExportWorkflowConfig:
    """Configuration for export workflow."""

    format: ExportFormat = ExportFormat.BIBTEX
    validate: bool = True
    sort_by: str | None = None
    sort_reverse: bool = False
    include_metadata: bool = False
    include_notes: bool = False
    pretty_print: bool = True
    encoding: str = "utf-8"
    dry_run: bool = False


class ExportWorkflow:
    """Orchestrates the export process."""

    def __init__(self, manager: RepositoryManager, event_bus: EventBus):
        self.manager = manager
        self.event_bus = event_bus

    def execute(
        self,
        destination: Path | str,
        query: str | None = None,
        entry_keys: list[str] | None = None,
        collection_name: str | None = None,
        config: ExportWorkflowConfig | None = None,
    ) -> WorkflowResult:
        """Execute export workflow."""
        config = config or ExportWorkflowConfig()

        result = WorkflowResult(
            workflow="export",
            config={
                "format": config.format.value,
                "destination": str(destination),
                "query": query,
                "collection": collection_name,
            },
        )

        collect_result = self._collect_entries(query, entry_keys, collection_name)
        result.add_step(collect_result)

        if not collect_result.success:
            result.complete()
            return result

        entries: list[Entry] = (
            collect_result.data.get("entries", []) if collect_result.data else []
        )

        if not entries:
            result.add_step(
                StepResult(step="export", success=True, message="No entries to export")
            )
            result.complete()
            return result

        if config.validate:
            validate_result = self._validate_entries(entries)
            result.add_step(validate_result)

            if not validate_result.success and not validate_result.warnings:
                result.complete()
                return result

            if validate_result.warnings:
                invalid_keys = set()
                for warning in validate_result.warnings:
                    key = warning.split(":")[0]
                    invalid_keys.add(key)

                entries = [e for e in entries if e.key not in invalid_keys]

                if not entries:
                    result.add_step(
                        StepResult(
                            step="export",
                            success=True,
                            message="All entries skipped due to validation errors",
                        )
                    )
                    result.complete()
                    return result

        if config.sort_by:
            entries = self._sort_entries(entries, config.sort_by, config.sort_reverse)

        if config.dry_run:
            result.add_step(
                StepResult(
                    step="export",
                    success=True,
                    message=f"Would export {len(entries)} entries to {config.format.value}",
                    data={"count": len(entries), "format": config.format.value},
                )
            )
            result.complete()
            return result

        if config.format == ExportFormat.BIBTEX:
            export_result = self._export_bibtex(entries, destination, config)
        elif config.format == ExportFormat.RIS:
            export_result = self._export_ris(entries, destination, config)
        elif config.format == ExportFormat.JSON:
            export_result = self._export_json(entries, destination, config)
        elif config.format == ExportFormat.CSV:
            export_result = self._export_csv(entries, destination, config)
        elif config.format == ExportFormat.MARKDOWN:
            export_result = self._export_markdown(entries, destination, config)
        else:
            export_result = StepResult(
                step="export",
                success=False,
                message=f"Unsupported format: {config.format.value}",
            )

        result.add_step(export_result)

        result.complete()

        if export_result.success:
            event = Event(
                type=EventType.WORKFLOW_COMPLETED,
                timestamp=datetime.now(),
                data={
                    "workflow": "export",
                    "destination": str(destination),
                    "format": config.format.value,
                    "entry_count": len(entries),
                },
            )
            self.event_bus.publish(event)

        return result

    def _collect_entries(
        self,
        query: str | None,
        entry_keys: list[str] | None,
        collection_name: str | None,
    ) -> StepResult:
        """Collect entries to export based on criteria."""
        try:
            entries = []

            if entry_keys:
                for key in entry_keys:
                    entry = self.manager.entries.find(key)
                    if entry:
                        entries.append(entry)
                    else:
                        return StepResult(
                            step="collect",
                            success=False,
                            message=f"Entry not found: {key}",
                        )

            elif collection_name:
                collections = self.manager.collections.find_by_name(collection_name)
                if not collections:
                    return StepResult(
                        step="collect",
                        success=False,
                        message=f"Collection not found: {collection_name}",
                    )

                collection = collections[0]
                for key in collection.entry_keys or []:
                    entry = self.manager.entries.find(key)
                    if entry:
                        entries.append(entry)

            elif query:
                parsed_query = self._parse_query(query)
                entries = list(self.manager.entries.search(parsed_query))

            else:
                entries = self.manager.entries.find_all()

            return StepResult(
                step="collect",
                success=True,
                message=f"Collected {len(entries)} entries",
                data={"entries": entries},
            )

        except Exception as e:
            return StepResult(
                step="collect",
                success=False,
                message="Failed to collect entries",
                errors=[str(e)],
            )

    def _validate_entries(self, entries: list[Entry]) -> StepResult:
        """Validate entries before export."""
        warnings = []
        invalid_count = 0

        for entry in entries:
            errors = entry.validate()
            if errors:
                invalid_count += 1
                warnings.append(f"{entry.key}: {', '.join(e.message for e in errors)}")

        if invalid_count > 0:
            return StepResult(
                step="validate",
                success=True,
                message=f"Found {invalid_count} entries with validation errors",
                warnings=warnings[:10],
            )

        return StepResult(step="validate", success=True, message="All entries valid")

    def _sort_entries(
        self, entries: list[Entry], sort_by: str, reverse: bool
    ) -> list[Entry]:
        """Sort entries by specified field."""

        def get_sort_key(entry):
            value = getattr(entry, sort_by, None)
            if value is None:
                return ""
            elif isinstance(value, list):
                return value[0] if value else ""
            else:
                return str(value).lower()

        return sorted(entries, key=get_sort_key, reverse=reverse)

    def _export_bibtex(
        self,
        entries: list[Entry],
        destination: Path | str,
        config: ExportWorkflowConfig,
    ) -> StepResult:
        """Export entries as BibTeX."""
        try:
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding=config.encoding) as f:
                for entry in entries:
                    f.write(f"@{entry.type.value}{{{entry.key},\n")

                    entry_dict = entry.to_dict()
                    for field, value in entry_dict.items():
                        if field in ["key", "type", "added", "modified"]:
                            continue
                        if value is not None:
                            if isinstance(value, list):
                                value = " and ".join(str(v) for v in value)
                            f.write(f"  {field} = {{{value}}},\n")

                    f.write("}\n\n")

            return StepResult(
                step="export",
                success=True,
                message=f"Exported {len(entries)} entries to BibTeX",
                data={"path": str(path), "count": len(entries)},
            )

        except Exception as e:
            return StepResult(
                step="export",
                success=False,
                message="Failed to export BibTeX",
                errors=[str(e)],
            )

    def _export_ris(
        self,
        entries: list[Entry],
        destination: Path | str,
        config: ExportWorkflowConfig,
    ) -> StepResult:
        """Export entries as RIS."""
        try:
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)

            type_map = {
                "article": "JOUR",
                "book": "BOOK",
                "inproceedings": "CPAPER",
                "incollection": "CHAP",
                "phdthesis": "THES",
                "mastersthesis": "THES",
                "techreport": "RPRT",
                "misc": "GEN",
            }

            with open(path, "w", encoding=config.encoding) as f:
                for entry in entries:
                    ris_type = type_map.get(entry.type.value, "GEN")
                    f.write(f"TY  - {ris_type}\n")

                    if entry.author:
                        for author in entry.author.split(" and "):
                            f.write(f"AU  - {author.strip()}\n")

                    if entry.title:
                        f.write(f"TI  - {entry.title}\n")

                    if entry.year:
                        f.write(f"PY  - {entry.year}\n")

                    if entry.journal:
                        f.write(f"JO  - {entry.journal}\n")

                    if entry.doi:
                        f.write(f"DO  - {entry.doi}\n")

                    if entry.abstract:
                        f.write(f"AB  - {entry.abstract}\n")

                    f.write("ER  - \n\n")

            return StepResult(
                step="export",
                success=True,
                message=f"Exported {len(entries)} entries to RIS",
                data={"path": str(path), "count": len(entries)},
            )

        except Exception as e:
            return StepResult(
                step="export",
                success=False,
                message="Failed to export RIS",
                errors=[str(e)],
            )

    def _export_json(
        self,
        entries: list[Entry],
        destination: Path | str,
        config: ExportWorkflowConfig,
    ) -> StepResult:
        """Export entries as JSON."""
        try:
            import json

            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Export entries without internal fields
            entries_data = []
            for entry in entries:
                entry_dict = entry.to_dict()
                # Remove internal fields that shouldn't be exported
                export_dict = {
                    k: v
                    for k, v in entry_dict.items()
                    if k not in ["added", "modified", "tags"]
                }
                entries_data.append(export_dict)

            # Always use structured format for JSON exports
            data = {"entries": entries_data, "total": len(entries)}

            if (
                config.include_metadata
                and hasattr(self.manager, "metadata_store")
                and self.manager.metadata_store
            ):
                metadata_dict = {}
                for entry in entries:
                    metadata = self.manager.metadata_store.get_metadata(entry.key)
                    metadata_dict[entry.key] = {
                        "tags": list(metadata.tags),
                        "rating": metadata.rating,
                        "read_status": metadata.read_status,
                        "read_date": metadata.read_date.isoformat()
                        if metadata.read_date
                        else None,
                        "importance": metadata.importance,
                        "notes_count": metadata.notes_count,
                    }

                data["metadata"] = metadata_dict

            with open(path, "w", encoding=config.encoding) as f:
                if config.pretty_print:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    json.dump(data, f, ensure_ascii=False)

            return StepResult(
                step="export",
                success=True,
                message=f"Exported {len(entries)} entries to JSON",
                data={"path": str(path), "count": len(entries)},
            )

        except Exception as e:
            return StepResult(
                step="export",
                success=False,
                message="Failed to export JSON",
                errors=[str(e)],
            )

    def _export_csv(
        self,
        entries: list[Entry],
        destination: Path | str,
        config: ExportWorkflowConfig,
    ) -> StepResult:
        """Export entries as CSV."""
        try:
            import csv

            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)

            fields = [
                "key",
                "type",
                "author",
                "title",
                "year",
                "journal",
                "booktitle",
                "publisher",
                "doi",
                "url",
                "abstract",
            ]

            with open(path, "w", newline="", encoding=config.encoding) as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()

                for entry in entries:
                    row = {}
                    for field in fields:
                        value = getattr(entry, field, None)
                        if value is not None:
                            if isinstance(value, list):
                                row[field] = "; ".join(str(v) for v in value)
                            else:
                                row[field] = str(value)
                        else:
                            row[field] = ""
                    writer.writerow(row)

            return StepResult(
                step="export",
                success=True,
                message=f"Exported {len(entries)} entries to CSV",
                data={"path": str(path), "count": len(entries)},
            )

        except Exception as e:
            return StepResult(
                step="export",
                success=False,
                message="Failed to export CSV",
                errors=[str(e)],
            )

    def _export_markdown(
        self,
        entries: list[Entry],
        destination: Path | str,
        config: ExportWorkflowConfig,
    ) -> StepResult:
        """Export entries as Markdown."""
        try:
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding=config.encoding) as f:
                f.write("# Bibliography Export\n\n")
                f.write(f"Generated with {len(entries)} entries\n\n")

                for entry in entries:
                    f.write(f"## {entry.key}\n\n")

                    f.write(f"**Type:** {entry.type.value}\n\n")

                    if entry.author:
                        f.write(f"**Authors:** {entry.author}\n\n")

                    if entry.title:
                        f.write(f"**Title:** {entry.title}\n\n")

                    if entry.year:
                        f.write(f"**Year:** {entry.year}\n\n")

                    if entry.journal:
                        f.write(f"**Journal:** {entry.journal}\n\n")
                    elif entry.booktitle:
                        f.write(f"**Book Title:** {entry.booktitle}\n\n")

                    if entry.publisher:
                        f.write(f"**Publisher:** {entry.publisher}\n\n")

                    if entry.doi:
                        f.write(
                            f"**DOI:** [{entry.doi}](https://doi.org/{entry.doi})\n\n"
                        )

                    if entry.url:
                        f.write(f"**URL:** [{entry.url}]({entry.url})\n\n")

                    if entry.abstract:
                        f.write("**Abstract:**\n\n")
                        f.write(f"> {entry.abstract}\n\n")

                    f.write("---\n\n")

            return StepResult(
                step="export",
                success=True,
                message=f"Exported {len(entries)} entries to Markdown",
                data={"path": str(path), "count": len(entries)},
            )

        except Exception as e:
            return StepResult(
                step="export",
                success=False,
                message="Failed to export Markdown",
                errors=[str(e)],
            )

    def _parse_query(self, query_string: str) -> Query:
        """Parse a simple query string into a Query object."""

        if ":" in query_string:
            parts = query_string.split(":", 1)
            field = parts[0].strip()
            value = parts[1].strip()

            if field in ["year", "volume", "number"]:
                try:
                    value = int(value)
                    return Query([Condition(field, Operator.EQ, value)])
                except ValueError:
                    if isinstance(value, str) and ".." in value:
                        start, end = value.split("..")
                        try:
                            start_val = int(start.strip())
                            end_val = int(end.strip())
                            return Query(
                                [
                                    Condition(field, Operator.GTE, start_val),
                                    Condition(field, Operator.LTE, end_val),
                                ],
                                Operator.AND,
                            )
                        except ValueError:
                            pass

            return Query([Condition(field, Operator.CONTAINS, value)])
        else:
            return Query(
                [
                    Condition("title", Operator.CONTAINS, query_string),
                    Condition("author", Operator.CONTAINS, query_string),
                ],
                Operator.OR,
            )
