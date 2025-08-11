"""Deduplication workflow for finding and merging duplicates."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from bibmgr.core.duplicates import DuplicateDetector
from bibmgr.core.models import Entry
from bibmgr.storage.events import Event, EventBus, EventType
from bibmgr.storage.repository import RepositoryManager

from ..commands import MergeCommand, MergeHandler
from ..policies import MergeStrategy
from ..results import StepResult, WorkflowResult


class MatchType(Enum):
    """Type of duplicate match."""

    DOI = "doi"
    EXACT_KEY = "exact_key"
    TITLE_AUTHOR_YEAR = "title_author_year"
    FUZZY = "fuzzy"


@dataclass
class DuplicateGroup:
    """Group of duplicate entries."""

    entries: list[Entry]
    match_type: MatchType
    confidence: float


class DeduplicationMode(Enum):
    """Deduplication operation modes."""

    AUTOMATIC = "automatic"
    INTERACTIVE = "interactive"
    PREVIEW = "preview"
    SELECTIVE = "selective"


@dataclass
class DeduplicationRule:
    """Rule for automatic deduplication."""

    match_type: MatchType
    min_similarity: float
    action: str
    merge_strategy: MergeStrategy = MergeStrategy.SMART


@dataclass
class DeduplicationConfig:
    """Configuration for deduplication workflow."""

    mode: DeduplicationMode = DeduplicationMode.INTERACTIVE
    min_similarity: float = 0.85
    match_types: list[MatchType] | None = None
    rules: list[DeduplicationRule] | None = None
    merge_strategy: MergeStrategy = MergeStrategy.SMART
    dry_run: bool = False
    batch_size: int = 100


class DeduplicationWorkflow:
    """Workflow for finding and merging duplicate entries."""

    def __init__(self, manager: RepositoryManager, event_bus: EventBus):
        self.manager = manager
        self.event_bus = event_bus
        self.merge_handler = MergeHandler(manager.entries, event_bus)

    def execute(self, config: DeduplicationConfig | None = None) -> WorkflowResult:
        """Execute deduplication workflow."""
        config = config or DeduplicationConfig()

        result = WorkflowResult(
            workflow="deduplicate",
            config={
                "mode": config.mode.value,
                "min_similarity": config.min_similarity,
                "dry_run": config.dry_run,
            },
        )

        index_result = self._build_index()
        result.add_step(index_result)

        if not index_result.success:
            result.complete()
            return result

        detect_result = self._detect_duplicates(config)
        result.add_step(detect_result)

        if not detect_result.success:
            result.complete()
            return result

        duplicate_groups = (
            detect_result.data.get("groups", []) if detect_result.data else []
        )

        if not duplicate_groups:
            result.add_step(
                StepResult(step="complete", success=True, message="No duplicates found")
            )
            result.complete()
            return result

        if config.mode == DeduplicationMode.PREVIEW:
            preview_result = self._preview_duplicates(duplicate_groups)
            result.add_step(preview_result)

        elif config.mode == DeduplicationMode.AUTOMATIC:
            merge_results = self._merge_all_duplicates(duplicate_groups, config)
            for r in merge_results:
                result.add_step(r)

        elif config.mode == DeduplicationMode.SELECTIVE:
            process_results = self._process_with_rules(duplicate_groups, config)
            for r in process_results:
                result.add_step(r)

        else:
            result.add_step(
                StepResult(
                    step="interactive",
                    success=True,
                    message="Interactive mode requires UI",
                    data={"groups": duplicate_groups},
                )
            )

        summary_result = self._create_summary(result)
        result.add_step(summary_result)

        result.complete()

        event = Event(
            type=EventType.WORKFLOW_COMPLETED,
            timestamp=datetime.now(),
            data={
                "workflow": "deduplication",
                "result": result,
            },
        )
        self.event_bus.publish(event)

        return result

    def _build_index(self) -> StepResult:
        """Build index for duplicate detection."""
        try:
            entries = self.manager.entries.find_all()

            return StepResult(
                step="build_index",
                success=True,
                message=f"Indexed {len(entries)} entries",
                data={"entry_count": len(entries)},
            )

        except Exception as e:
            return StepResult(
                step="build_index",
                success=False,
                message="Failed to build index",
                errors=[str(e)],
            )

    def _detect_duplicates(self, config: DeduplicationConfig) -> StepResult:
        """Detect duplicate groups."""
        try:
            entries = self.manager.entries.find_all()
            detector = DuplicateDetector(entries)

            duplicate_lists = detector.find_duplicates()

            groups = []
            for dup_list in duplicate_lists:
                if len(dup_list) >= 2:
                    match_type = self._determine_match_type(dup_list)
                    confidence = self._calculate_confidence(dup_list, match_type)

                    if confidence >= config.min_similarity:
                        groups.append(
                            DuplicateGroup(
                                entries=dup_list,
                                match_type=match_type,
                                confidence=confidence,
                            )
                        )

            groups.sort(key=lambda g: g.confidence, reverse=True)

            return StepResult(
                step="detect_duplicates",
                success=True,
                message=f"Found {len(groups)} duplicate groups",
                data={
                    "groups": groups,
                    "total_duplicates": sum(len(g.entries) for g in groups),
                },
            )

        except Exception as e:
            return StepResult(
                step="detect_duplicates",
                success=False,
                message="Failed to detect duplicates",
                errors=[str(e)],
            )

    def _preview_duplicates(self, groups: list[DuplicateGroup]) -> StepResult:
        """Create preview of duplicates."""
        preview_data = []

        for group in groups:
            preview_data.append(
                {
                    "entries": [e.key for e in group.entries],
                    "match_type": group.match_type.value,
                    "confidence": group.confidence,
                    "suggested_action": self._suggest_action(group),
                }
            )

        return StepResult(
            step="preview",
            success=True,
            message=f"Preview of {len(groups)} duplicate groups",
            data={"preview": preview_data},
        )

    def _merge_all_duplicates(
        self, groups: list[DuplicateGroup], config: DeduplicationConfig
    ) -> list[StepResult]:
        """Merge all duplicate groups automatically."""
        results = []

        for i, group in enumerate(groups):
            event = Event(
                type=EventType.PROGRESS,
                timestamp=datetime.now(),
                data={
                    "operation": "merge_duplicates",
                    "current": i + 1,
                    "total": len(groups),
                },
            )
            self.event_bus.publish(event)

            if group.confidence < config.min_similarity:
                results.append(
                    StepResult(
                        step="merge_group",
                        success=True,
                        message="Skipped low confidence group",
                        data={"confidence": group.confidence},
                    )
                )
                continue

            command = MergeCommand(
                source_keys=[e.key for e in group.entries],
                strategy=config.merge_strategy.value,
            )

            if config.dry_run:
                results.append(
                    StepResult(
                        step="merge_group",
                        success=True,
                        message=f"Would merge {len(group.entries)} entries",
                        data={"keys": [e.key for e in group.entries]},
                    )
                )
            else:
                merge_result = self.merge_handler.execute(command)
                results.append(
                    StepResult(
                        step="merge_group",
                        success=merge_result.status.is_success(),
                        entity_id=merge_result.entity_id,
                        message=merge_result.message,
                        errors=merge_result.errors,
                    )
                )

        return results

    def _process_with_rules(
        self, groups: list[DuplicateGroup], config: DeduplicationConfig
    ) -> list[StepResult]:
        """Process duplicates using configured rules."""
        results = []

        for group in groups:
            rule = self._find_matching_rule(group, config.rules)

            if not rule or rule.action == "skip":
                results.append(
                    StepResult(
                        step="apply_rule",
                        success=True,
                        message="Skipped by rule",
                        data={"group": [e.key for e in group.entries]},
                    )
                )
                continue

            if rule.action == "merge":
                command = MergeCommand(
                    source_keys=[e.key for e in group.entries],
                    strategy=rule.merge_strategy.value,
                )

                merge_result = self.merge_handler.execute(command)
                results.append(
                    StepResult(
                        step="apply_rule",
                        success=merge_result.status.is_success(),
                        entity_id=merge_result.entity_id,
                        message=f"Merged by rule: {merge_result.message}",
                        errors=merge_result.errors,
                    )
                )

            elif rule.action == "ask":
                results.append(
                    StepResult(
                        step="apply_rule",
                        success=True,
                        message="Requires user decision",
                        data={
                            "group": [e.key for e in group.entries],
                            "action": "ask",
                        },
                    )
                )

        return results

    def _find_matching_rule(
        self, group: DuplicateGroup, rules: list[DeduplicationRule] | None
    ) -> DeduplicationRule | None:
        """Find first matching rule for a duplicate group."""
        if not rules:
            return None

        for rule in rules:
            if (
                rule.match_type == group.match_type
                and group.confidence >= rule.min_similarity
            ):
                return rule

        return None

    def _suggest_action(self, group: DuplicateGroup) -> str:
        """Suggest action for a duplicate group."""
        if group.match_type == MatchType.DOI:
            return "merge"
        elif group.match_type == MatchType.EXACT_KEY:
            return "merge"
        elif group.confidence > 0.95:
            return "merge"
        elif group.confidence > 0.85:
            return "review"
        else:
            return "skip"

    def _create_summary(self, result: WorkflowResult) -> StepResult:
        """Create summary of deduplication results."""
        merged = sum(
            1 for step in result.steps if step.step == "merge_group" and step.success
        )

        skipped = sum(
            1
            for step in result.steps
            if step.step in ["merge_group", "apply_rule"]
            and step.message.startswith("Skipped")
        )

        failed = sum(1 for step in result.steps if not step.success)

        return StepResult(
            step="summary",
            success=True,
            message="Deduplication complete",
            data={
                "groups_processed": len(
                    [s for s in result.steps if s.step in ["merge_group", "apply_rule"]]
                ),
                "groups_merged": merged,
                "groups_skipped": skipped,
                "failures": failed,
            },
        )

    def _determine_match_type(self, entries: list[Entry]) -> MatchType:
        """Determine the type of match between entries."""
        if len(entries) < 2:
            return MatchType.FUZZY

        if all(e.key == entries[0].key for e in entries[1:]):
            return MatchType.EXACT_KEY

        if entries[0].doi and all(e.doi == entries[0].doi for e in entries[1:]):
            return MatchType.DOI

        if (
            entries[0].title
            and entries[0].author
            and entries[0].year
            and all(
                e.title == entries[0].title
                and e.author == entries[0].author
                and e.year == entries[0].year
                for e in entries[1:]
            )
        ):
            return MatchType.TITLE_AUTHOR_YEAR

        return MatchType.FUZZY

    def _calculate_confidence(
        self, entries: list[Entry], match_type: MatchType
    ) -> float:
        """Calculate confidence score for duplicate group."""
        if match_type == MatchType.DOI:
            return 1.0
        elif match_type == MatchType.EXACT_KEY:
            return 0.95
        elif match_type == MatchType.TITLE_AUTHOR_YEAR:
            return 0.9
        else:
            if len(entries) < 2:
                return 0.0

            common_fields = 0
            total_fields = 0

            entry1_dict = entries[0].to_dict()
            entry2_dict = entries[1].to_dict()

            for field in ["title", "author", "year", "journal", "booktitle"]:
                if field in entry1_dict and field in entry2_dict:
                    total_fields += 1
                    if entry1_dict[field] == entry2_dict[field]:
                        common_fields += 1

            return common_fields / total_fields if total_fields > 0 else 0.5
