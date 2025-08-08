"""Consistency checks across bibliography entries.

Implements optimized algorithms for:
- Cross-reference validation
- Duplicate detection with fuzzy matching
- Orphan entry detection
- Citation loop detection
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

import msgspec

from bibmgr.quality.validators import ValidationSeverity


@dataclass
class ConsistencyIssue:
    """A consistency issue found in the bibliography."""

    issue_type: str
    severity: ValidationSeverity
    entries: list[str]  # Entry keys involved
    message: str
    suggestion: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation."""
        return self.to_string()

    def to_string(self) -> str:
        """Format as human-readable string."""
        severity_str = self.severity.name
        entries_str = ", ".join(self.entries[:3])
        if len(self.entries) > 3:
            entries_str += f", ... ({len(self.entries)} total)"

        parts = [f"[{severity_str}] {self.issue_type}"]
        parts.append(f" ({entries_str})")
        parts.append(f": {self.message}")

        if self.suggestion:
            parts.append(f"\n  → {self.suggestion}")

        return "".join(parts)


class ConsistencyReport(msgspec.Struct, frozen=True, kw_only=True):
    """Report of consistency check results."""

    total_entries: int
    issues: list[ConsistencyIssue] = msgspec.field(default_factory=list)
    orphaned_entries: list[str] = msgspec.field(default_factory=list)
    duplicate_groups: list[list[str]] = msgspec.field(default_factory=list)
    broken_references: dict[str, list[str]] = msgspec.field(default_factory=dict)
    citation_loops: list[list[str]] = msgspec.field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if report contains errors."""
        return any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if report contains warnings."""
        return any(
            issue.severity == ValidationSeverity.WARNING for issue in self.issues
        )

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "Consistency Report",
            f"Total entries: {self.total_entries}",
            f"Issues found: {len(self.issues)}",
        ]

        if self.orphaned_entries:
            lines.append(f"Orphaned entries: {len(self.orphaned_entries)}")

        if self.duplicate_groups:
            lines.append(f"Duplicate groups: {len(self.duplicate_groups)}")

        if self.broken_references:
            lines.append(f"Broken references: {len(self.broken_references)}")

        if self.citation_loops:
            lines.append(f"Citation loops: {len(self.citation_loops)}")

        # Group issues by severity
        by_severity = defaultdict(int)
        for issue in self.issues:
            by_severity[issue.severity.name] += 1

        if by_severity:
            lines.append("\nIssues by severity:")
            for severity in ["ERROR", "WARNING", "INFO", "SUGGESTION"]:
                if severity in by_severity:
                    lines.append(f"  {severity}: {by_severity[severity]}")

        return "\n".join(lines)


class CrossReferenceValidator:
    """Validates cross-references between entries."""

    def validate(self, entries: list[Any]) -> list[ConsistencyIssue]:
        """Check cross-references are valid.

        Args:
            entries: List of entries to check

        Returns:
            List of issues found
        """
        issues = []
        entry_keys = {entry.key for entry in entries}

        for entry in entries:
            if hasattr(entry, "crossref") and entry.crossref:
                if entry.crossref not in entry_keys:
                    issues.append(
                        ConsistencyIssue(
                            issue_type="broken_crossref",
                            severity=ValidationSeverity.ERROR,
                            entries=[entry.key],
                            message=f"Cross-reference to non-existent entry: {entry.crossref}",
                            suggestion=f"Remove crossref or add entry {entry.crossref}",
                            metadata={"missing_ref": entry.crossref},
                        )
                    )

        return issues

    def detect_loops(self, entries: list[Any]) -> list[list[str]]:
        """Detect circular cross-references using Tarjan's algorithm.

        Args:
            entries: List of entries to check

        Returns:
            List of loops found (each loop is a list of keys)
        """
        # Build adjacency list
        graph = {}
        for entry in entries:
            if hasattr(entry, "crossref") and entry.crossref:
                graph[entry.key] = entry.crossref

        # Tarjan's strongly connected components algorithm
        index_counter = [0]
        stack = []
        lowlinks = {}
        index = {}
        on_stack = {}
        loops = []

        def strongconnect(node):
            index[node] = index_counter[0]
            lowlinks[node] = index_counter[0]
            index_counter[0] += 1
            on_stack[node] = True
            stack.append(node)

            # Consider successors
            if node in graph:
                successor = graph[node]
                if successor not in index:
                    strongconnect(successor)
                    lowlinks[node] = min(lowlinks[node], lowlinks[successor])
                elif on_stack.get(successor, False):
                    lowlinks[node] = min(lowlinks[node], index[successor])

            # If node is a root node, pop the stack and create SCC
            if lowlinks[node] == index[node]:
                component = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    component.append(w)
                    if w == node:
                        break

                # Only report actual loops (more than 1 element)
                if len(component) > 1:
                    # Normalize the loop (start with smallest key)
                    component.sort()
                    loops.append(component)

        # Find all SCCs
        for node in graph:
            if node not in index:
                strongconnect(node)

        return loops


class DuplicateDetector:
    """Detects duplicate entries using optimized algorithms."""

    def __init__(
        self,
        check_doi: bool = True,
        check_title: bool = True,
        title_threshold: float = 0.8,
        use_fuzzy: bool = True,
    ):
        """Initialize duplicate detector.

        Args:
            check_doi: Whether to check DOI duplicates
            check_title: Whether to check title similarity
            title_threshold: Similarity threshold for titles (0-1)
            use_fuzzy: Whether to use fuzzy matching for titles
        """
        self.check_doi = check_doi
        self.check_title = check_title
        self.title_threshold = title_threshold
        self.use_fuzzy = use_fuzzy

    def find_duplicates(self, entries: list[Any]) -> list[list[str]]:
        """Find duplicate entry groups using optimized algorithms.

        Args:
            entries: List of entries to check

        Returns:
            List of duplicate groups (each group is a list of keys)
        """
        duplicates = []
        processed = set()

        # Check DOI duplicates (O(n) with hash map)
        if self.check_doi:
            doi_duplicates = self._find_doi_duplicates(entries)
            for group in doi_duplicates:
                duplicates.append(group)
                processed.update(group)

        # Check title similarity (optimized with blocking)
        if self.check_title:
            title_duplicates = self._find_title_duplicates(
                [e for e in entries if e.key not in processed]
            )
            duplicates.extend(title_duplicates)

        return duplicates

    def _find_doi_duplicates(self, entries: list[Any]) -> list[list[str]]:
        """Find entries with duplicate DOIs."""
        doi_map = defaultdict(list)

        for entry in entries:
            if hasattr(entry, "doi") and entry.doi:
                # Normalize DOI
                doi = self._normalize_doi(entry.doi)
                if doi:
                    doi_map[doi].append(entry.key)

        return [keys for keys in doi_map.values() if len(keys) > 1]

    def _normalize_doi(self, doi: str) -> str | None:
        """Normalize DOI for comparison."""
        if not doi:
            return None

        doi = doi.lower().strip()
        # Remove common prefixes
        for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
            if doi.startswith(prefix):
                doi = doi[len(prefix) :]
                break

        return doi

    def _find_title_duplicates(self, entries: list[Any]) -> list[list[str]]:
        """Find entries with similar titles using blocking and fuzzy matching."""
        if not self.use_fuzzy:
            return self._find_exact_title_duplicates(entries)

        # Create blocks based on title hashes for efficiency
        blocks = self._create_title_blocks(entries)
        duplicates = []

        # Check within each block
        for block_entries in blocks.values():
            if len(block_entries) < 2:
                continue

            # Check pairs within block
            groups = self._find_similar_in_block(block_entries)
            duplicates.extend(groups)

        return duplicates

    def _find_exact_title_duplicates(self, entries: list[Any]) -> list[list[str]]:
        """Find entries with exactly matching titles."""
        title_map = defaultdict(list)

        for entry in entries:
            if hasattr(entry, "title") and entry.title:
                # Normalize title
                normalized = self._normalize_title(entry.title)
                if normalized:
                    title_map[normalized].append(entry.key)

        return [keys for keys in title_map.values() if len(keys) > 1]

    def _create_title_blocks(self, entries: list[Any]) -> dict[str, list[Any]]:
        """Create blocks of potentially similar titles using LSH."""
        blocks = defaultdict(list)

        for entry in entries:
            if hasattr(entry, "title") and entry.title:
                # Create multiple hash signatures for blocking
                signatures = self._get_title_signatures(entry.title)
                for sig in signatures:
                    blocks[sig].append(entry)

        return blocks

    def _get_title_signatures(self, title: str) -> list[str]:
        """Get hash signatures for title blocking."""
        normalized = self._normalize_title(title)
        if not normalized:
            return []

        signatures = []

        # Signature 1: First 3 characters
        if len(normalized) >= 3:
            signatures.append(normalized[:3])

        # Signature 2: Hash of sorted words (for reordered titles)
        words = sorted(normalized.split())
        if words:
            word_hash = hashlib.md5(" ".join(words[:3]).encode()).hexdigest()[:8]
            signatures.append(word_hash)

        # Signature 3: Length bucket
        length_bucket = f"len_{len(normalized) // 10}"
        signatures.append(length_bucket)

        return signatures

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        if not title:
            return ""

        # Convert to lowercase and strip
        normalized = title.lower().strip()

        # Remove punctuation and extra spaces
        import string

        translator = str.maketrans("", "", string.punctuation)
        normalized = normalized.translate(translator)
        normalized = " ".join(normalized.split())

        return normalized

    def _find_similar_in_block(self, entries: list[Any]) -> list[list[str]]:
        """Find similar titles within a block."""
        groups = []
        processed = set()

        for i, entry1 in enumerate(entries):
            if entry1.key in processed:
                continue

            if not hasattr(entry1, "title") or not entry1.title:
                continue

            similar = [entry1.key]

            for entry2 in entries[i + 1 :]:
                if entry2.key in processed:
                    continue

                if not hasattr(entry2, "title") or not entry2.title:
                    continue

                similarity = self._calculate_similarity(entry1.title, entry2.title)
                if similarity >= self.title_threshold:
                    similar.append(entry2.key)
                    processed.add(entry2.key)

            if len(similar) > 1:
                groups.append(similar)
                processed.update(similar)

        return groups

    def _calculate_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles."""
        t1 = self._normalize_title(title1)
        t2 = self._normalize_title(title2)

        if not t1 or not t2:
            return 0.0

        if t1 == t2:
            return 1.0

        # Use SequenceMatcher for fuzzy matching
        return SequenceMatcher(None, t1, t2).ratio()


class OrphanDetector:
    """Detects orphaned entries not referenced anywhere."""

    def find_orphans(
        self,
        entries: list[Any],
        collections: list[Any] | None = None,
        cited_keys: set[str] | None = None,
    ) -> list[str]:
        """Find orphaned entries efficiently.

        Args:
            entries: List of all entries
            collections: Optional list of collections
            cited_keys: Optional set of cited entry keys

        Returns:
            List of orphaned entry keys
        """
        all_keys = {entry.key for entry in entries}
        referenced = set()

        # Check cross-references
        for entry in entries:
            if hasattr(entry, "crossref") and entry.crossref:
                referenced.add(entry.crossref)

        # Check collections
        if collections:
            for collection in collections:
                if hasattr(collection, "entry_keys"):
                    referenced.update(collection.entry_keys)

        # Check citations
        if cited_keys:
            referenced.update(cited_keys)

        # Find orphans (entries not referenced anywhere)
        orphans = all_keys - referenced

        # Don't count entries that reference others as orphans
        # (they are part of the reference chain)
        for entry in entries:
            if entry.key in orphans:
                if hasattr(entry, "crossref") and entry.crossref:
                    orphans.discard(entry.key)

        return sorted(orphans)


class ConsistencyChecker:
    """Main consistency checker coordinating all checks."""

    def __init__(
        self,
        check_crossrefs: bool = True,
        check_duplicates: bool = True,
        check_orphans: bool = True,
        duplicate_threshold: float = 0.8,
    ):
        """Initialize consistency checker.

        Args:
            check_crossrefs: Whether to check cross-references
            check_duplicates: Whether to check for duplicates
            check_orphans: Whether to check for orphans
            duplicate_threshold: Threshold for title similarity
        """
        self.check_crossrefs = check_crossrefs
        self.check_duplicates = check_duplicates
        self.check_orphans = check_orphans

        self.crossref_validator = CrossReferenceValidator()
        self.duplicate_detector = DuplicateDetector(title_threshold=duplicate_threshold)
        self.orphan_detector = OrphanDetector()

    def check(
        self,
        entries: list[Any],
        collections: list[Any] | None = None,
        cited_keys: set[str] | None = None,
    ) -> ConsistencyReport:
        """Run all consistency checks.

        Args:
            entries: List of entries to check
            collections: Optional list of collections
            cited_keys: Optional set of cited keys

        Returns:
            Consistency report
        """
        issues = []

        # Check cross-references
        if self.check_crossrefs:
            crossref_issues = self.crossref_validator.validate(entries)
            issues.extend(crossref_issues)

            # Check for loops
            loops = self.crossref_validator.detect_loops(entries)
            for loop in loops:
                issues.append(
                    ConsistencyIssue(
                        issue_type="citation_loop",
                        severity=ValidationSeverity.ERROR,
                        entries=loop,
                        message="Circular cross-reference detected",
                        suggestion="Remove one of the cross-references to break the loop",
                        metadata={"loop_path": " → ".join(loop)},
                    )
                )

        # Check duplicates
        duplicate_groups = []
        if self.check_duplicates:
            duplicate_groups = self.duplicate_detector.find_duplicates(entries)
            for group in duplicate_groups:
                # Determine duplicate type
                dup_type = self._determine_duplicate_type(entries, group)

                issues.append(
                    ConsistencyIssue(
                        issue_type="duplicate_entries",
                        severity=ValidationSeverity.WARNING,
                        entries=group,
                        message=f"Potential duplicate entries detected ({dup_type})",
                        suggestion="Review and merge or differentiate these entries",
                        metadata={"duplicate_type": dup_type},
                    )
                )

        # Check orphans
        orphans = []
        if self.check_orphans:
            orphans = self.orphan_detector.find_orphans(
                entries, collections, cited_keys
            )

            if orphans:
                # Group into single issue if many orphans
                if len(orphans) > 10:
                    issues.append(
                        ConsistencyIssue(
                            issue_type="orphaned_entries",
                            severity=ValidationSeverity.INFO,
                            entries=orphans[:10],  # Show first 10
                            message=f"{len(orphans)} entries are not referenced anywhere",
                            suggestion="Consider organizing orphaned entries into collections",
                            metadata={"total_orphans": len(orphans)},
                        )
                    )
                else:
                    for orphan in orphans:
                        issues.append(
                            ConsistencyIssue(
                                issue_type="orphaned_entry",
                                severity=ValidationSeverity.INFO,
                                entries=[orphan],
                                message="Entry is not referenced in any collection or citation",
                                suggestion="Add to a collection or remove if not needed",
                            )
                        )

        # Build broken references map
        broken_refs = {}
        for issue in issues:
            if issue.issue_type == "broken_crossref":
                entry_key = issue.entries[0]
                ref_key = issue.metadata.get("missing_ref")
                if ref_key:
                    if entry_key not in broken_refs:
                        broken_refs[entry_key] = []
                    broken_refs[entry_key].append(ref_key)

        # Get citation loops
        citation_loops = []
        for issue in issues:
            if issue.issue_type == "citation_loop":
                citation_loops.append(issue.entries)

        return ConsistencyReport(
            total_entries=len(entries),
            issues=issues,
            orphaned_entries=orphans,
            duplicate_groups=duplicate_groups,
            broken_references=broken_refs,
            citation_loops=citation_loops,
        )

    def _determine_duplicate_type(self, entries: list[Any], group: list[str]) -> str:
        """Determine the type of duplication."""
        # Get the entries in the group
        entry_map = {e.key: e for e in entries}
        group_entries = [entry_map[key] for key in group if key in entry_map]

        if len(group_entries) < 2:
            return "unknown"

        # Check if DOIs match
        dois = [
            getattr(e, "doi", None)
            for e in group_entries
            if hasattr(e, "doi") and e.doi
        ]
        if len(dois) >= 2 and len(set(dois)) == 1:
            return "same DOI"

        # Check if titles match
        titles = [e.title for e in group_entries if hasattr(e, "title") and e.title]
        if len(titles) >= 2:
            # Check if exact match
            normalized = [t.lower().strip() for t in titles if t]
            if len(set(normalized)) == 1:
                return "same title"
            else:
                return "similar title"

        return "other"
