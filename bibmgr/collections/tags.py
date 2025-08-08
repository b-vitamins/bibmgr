"""Tag management with hierarchical organization.

This module implements:
- Hierarchical tag paths (e.g., "ml/nlp/bert")
- Tag operations (CRUD, merge, rename)
- Tag statistics and co-occurrence analysis
- Tag suggestions and clouds
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import msgspec

from bibmgr.core.models import Tag


class TagStats(msgspec.Struct, frozen=True):
    """Statistics for a tag."""

    path: str
    count: int = 0
    children: list[str] = msgspec.field(default_factory=list)
    co_occurring: dict[str, int] = msgspec.field(default_factory=dict)
    last_used: datetime | None = None

    def to_summary(self) -> str:
        """Generate human-readable summary.

        Returns:
            Summary string
        """
        lines = [
            f"Tag: {self.path}",
            f"Usage count: {self.count}",
        ]

        if self.children:
            lines.append(f"Children: {', '.join(self.children)}")

        if self.co_occurring:
            top_cooccur = sorted(
                self.co_occurring.items(), key=lambda x: x[1], reverse=True
            )[:5]
            if top_cooccur:
                lines.append("\nFrequently co-occurs with:")
                for tag, count in top_cooccur:
                    lines.append(f"  {tag}: {count}")

        if self.last_used:
            lines.append(f"\nLast used: {self.last_used.strftime('%Y-%m-%d')}")

        return "\n".join(lines)


class TagHierarchy:
    """Manages hierarchical tag structure."""

    def __init__(self):
        """Initialize tag hierarchy."""
        self.tags: dict[str, Tag] = {}
        self.children: dict[str, set[str]] = defaultdict(set)
        self.usage_count: dict[str, int] = Counter()
        self.co_occurrence: dict[str, Counter] = defaultdict(Counter)

    def add_tag(
        self, path: str, color: str | None = None, description: str | None = None
    ) -> Tag:
        """Add a tag to the hierarchy.

        Args:
            path: Tag path (e.g., "ml/nlp/bert")
            color: Optional color code
            description: Optional description

        Returns:
            Created or existing tag
        """
        if path in self.tags:
            return self.tags[path]

        tag = Tag(path=path, color=color, description=description)
        self.tags[path] = tag

        # Update hierarchy
        parts = path.split("/")
        if len(parts) > 1:
            parent_path = "/".join(parts[:-1])
            self.children[parent_path].add(path)

            # Ensure parent exists
            if parent_path not in self.tags:
                self.add_tag(parent_path)

        return tag

    def get_tag(self, path: str) -> Tag | None:
        """Get a tag by path.

        Args:
            path: Tag path

        Returns:
            Tag or None if not found
        """
        return self.tags.get(path)

    def get_children(self, path: str) -> list[str]:
        """Get children of a tag.

        Args:
            path: Parent tag path

        Returns:
            List of child tag paths
        """
        return sorted(self.children.get(path, set()))

    def get_descendants(self, path: str) -> list[str]:
        """Get all descendants of a tag.

        Args:
            path: Ancestor tag path

        Returns:
            List of descendant tag paths
        """
        descendants = []
        children = self.get_children(path)

        for child in children:
            descendants.append(child)
            descendants.extend(self.get_descendants(child))

        return descendants

    def get_ancestors(self, path: str) -> list[str]:
        """Get ancestors of a tag.

        Args:
            path: Tag path

        Returns:
            List of ancestor tag paths
        """
        ancestors = []
        parts = path.split("/")

        for i in range(1, len(parts)):
            ancestor = "/".join(parts[:i])
            ancestors.append(ancestor)

        return ancestors

    def rename_tag(self, old_path: str, new_path: str) -> bool:
        """Rename a tag and all its descendants.

        Args:
            old_path: Current tag path
            new_path: New tag path

        Returns:
            True if renamed successfully
        """
        if old_path not in self.tags:
            return False

        # Get all affected tags
        affected = [old_path] + self.get_descendants(old_path)

        # Create mapping of old to new paths
        path_mapping = {}
        for tag_path in affected:
            if tag_path == old_path:
                path_mapping[tag_path] = new_path
            else:
                # Replace prefix
                relative = tag_path[len(old_path) :]
                path_mapping[tag_path] = new_path + relative

        # Update tags
        new_tags = {}
        for old, new in path_mapping.items():
            tag = self.tags[old]
            new_tag = Tag(path=new, color=tag.color, description=tag.description)
            new_tags[new] = new_tag

        # Remove old tags
        for old in path_mapping:
            del self.tags[old]

        # Add new tags
        self.tags.update(new_tags)

        # Rebuild hierarchy
        self._rebuild_hierarchy()

        return True

    def merge_tags(self, source_path: str, target_path: str) -> bool:
        """Merge one tag into another.

        Args:
            source_path: Tag to merge from
            target_path: Tag to merge into

        Returns:
            True if merged successfully
        """
        if source_path not in self.tags or target_path not in self.tags:
            return False

        # Update usage counts
        self.usage_count[target_path] += self.usage_count.get(source_path, 0)

        # Merge co-occurrence data
        for tag, count in self.co_occurrence.get(source_path, {}).items():
            if tag != target_path:  # Don't self-reference
                self.co_occurrence[target_path][tag] += count

        # Move children
        for child in self.get_children(source_path):
            # Reparent child to target
            new_child_path = target_path + "/" + child.split("/")[-1]
            self.rename_tag(child, new_child_path)

        # Delete source
        del self.tags[source_path]
        if source_path in self.usage_count:
            del self.usage_count[source_path]
        if source_path in self.co_occurrence:
            del self.co_occurrence[source_path]

        self._rebuild_hierarchy()

        return True

    def delete_tag(self, path: str, cascade: bool = False) -> bool:
        """Delete a tag.

        Args:
            path: Tag path to delete
            cascade: Whether to delete descendants

        Returns:
            True if deleted successfully
        """
        if path not in self.tags:
            return False

        if cascade:
            # Delete all descendants
            for descendant in self.get_descendants(path):
                del self.tags[descendant]
                if descendant in self.usage_count:
                    del self.usage_count[descendant]
                if descendant in self.co_occurrence:
                    del self.co_occurrence[descendant]

        # Delete the tag
        del self.tags[path]
        if path in self.usage_count:
            del self.usage_count[path]
        if path in self.co_occurrence:
            del self.co_occurrence[path]

        self._rebuild_hierarchy()

        return True

    def _rebuild_hierarchy(self) -> None:
        """Rebuild the children mapping from current tags."""
        self.children.clear()

        for path in self.tags:
            parts = path.split("/")
            if len(parts) > 1:
                parent_path = "/".join(parts[:-1])
                self.children[parent_path].add(path)

    def record_usage(self, tags: list[str]) -> None:
        """Record tag usage for statistics.

        Args:
            tags: List of tags used together
        """
        for tag in tags:
            # Ensure tag exists
            if tag not in self.tags:
                self.add_tag(tag)

            # Update usage count
            self.usage_count[tag] += 1

            # Update co-occurrence
            for other_tag in tags:
                if other_tag != tag:
                    self.co_occurrence[tag][other_tag] += 1

    def get_stats(self, path: str) -> TagStats | None:
        """Get statistics for a tag.

        Args:
            path: Tag path

        Returns:
            Tag statistics or None
        """
        if path not in self.tags:
            return None

        return TagStats(
            path=path,
            count=self.usage_count.get(path, 0),
            children=self.get_children(path),
            co_occurring=dict(self.co_occurrence.get(path, {})),
        )

    def get_tag_cloud(self, min_count: int = 1) -> dict[str, int]:
        """Get tag cloud data.

        Args:
            min_count: Minimum usage count

        Returns:
            Dictionary of tag paths to counts
        """
        return {
            tag: count for tag, count in self.usage_count.items() if count >= min_count
        }

    def suggest_tags(self, existing_tags: list[str], limit: int = 5) -> list[str]:
        """Suggest related tags based on co-occurrence.

        Args:
            existing_tags: Currently selected tags
            limit: Maximum suggestions

        Returns:
            List of suggested tag paths
        """
        suggestions = Counter()

        for tag in existing_tags:
            if tag in self.co_occurrence:
                for co_tag, count in self.co_occurrence[tag].items():
                    if co_tag not in existing_tags:
                        suggestions[co_tag] += count

        # Sort by score and return top suggestions
        return [tag for tag, _ in suggestions.most_common(limit)]


class TagManager:
    """Manages tags for bibliography entries."""

    def __init__(self, base_path: Path):
        """Initialize tag manager.

        Args:
            base_path: Base directory for tag storage
        """
        self.base_path = Path(base_path)
        self.tags_file = self.base_path / "tags.json"
        self.hierarchy = TagHierarchy()

        # Load existing tags
        self._load_tags()

    def _load_tags(self) -> None:
        """Load tags from disk."""
        if not self.tags_file.exists():
            return

        try:
            data = json.loads(self.tags_file.read_text())

            # Load tags
            for tag_data in data.get("tags", []):
                self.hierarchy.add_tag(
                    path=tag_data["path"],
                    color=tag_data.get("color"),
                    description=tag_data.get("description"),
                )

            # Load usage counts
            self.hierarchy.usage_count = Counter(data.get("usage_count", {}))

            # Load co-occurrence data
            for tag, co_data in data.get("co_occurrence", {}).items():
                self.hierarchy.co_occurrence[tag] = Counter(co_data)

        except Exception:
            pass

    def _save_tags(self) -> None:
        """Save tags to disk."""
        data = {
            "tags": [
                {
                    "path": tag.path,
                    "color": tag.color,
                    "description": tag.description,
                }
                for tag in self.hierarchy.tags.values()
            ],
            "usage_count": dict(self.hierarchy.usage_count),
            "co_occurrence": {
                tag: dict(counts)
                for tag, counts in self.hierarchy.co_occurrence.items()
            },
        }

        # Write atomically
        temp_file = self.tags_file.with_suffix(".tmp")
        temp_file.write_text(json.dumps(data, indent=2))
        temp_file.replace(self.tags_file)

    def add_tag(
        self, path: str, color: str | None = None, description: str | None = None
    ) -> Tag:
        """Add a new tag.

        Args:
            path: Tag path
            color: Optional color
            description: Optional description

        Returns:
            Created tag
        """
        tag = self.hierarchy.add_tag(path, color, description)
        self._save_tags()
        return tag

    def update_tag(
        self,
        path: str,
        color: str | None = None,
        description: str | None = None,
    ) -> Tag | None:
        """Update a tag.

        Args:
            path: Tag path
            color: New color
            description: New description

        Returns:
            Updated tag or None
        """
        tag = self.hierarchy.get_tag(path)
        if not tag:
            return None

        updated = Tag(
            path=path,
            color=color if color is not None else tag.color,
            description=description if description is not None else tag.description,
        )

        self.hierarchy.tags[path] = updated
        self._save_tags()

        return updated

    def delete_tag(self, path: str, cascade: bool = False) -> bool:
        """Delete a tag.

        Args:
            path: Tag path
            cascade: Whether to delete descendants

        Returns:
            True if deleted
        """
        result = self.hierarchy.delete_tag(path, cascade)
        if result:
            self._save_tags()
        return result

    def rename_tag(self, old_path: str, new_path: str) -> bool:
        """Rename a tag.

        Args:
            old_path: Current path
            new_path: New path

        Returns:
            True if renamed
        """
        result = self.hierarchy.rename_tag(old_path, new_path)
        if result:
            self._save_tags()
        return result

    def merge_tags(self, source: str, target: str) -> bool:
        """Merge tags.

        Args:
            source: Source tag path
            target: Target tag path

        Returns:
            True if merged
        """
        result = self.hierarchy.merge_tags(source, target)
        if result:
            self._save_tags()
        return result

    def tag_entry(self, entry_key: str, tags: list[str]) -> None:
        """Record that an entry was tagged.

        Args:
            entry_key: Entry key
            tags: Tags applied
        """
        self.hierarchy.record_usage(tags)
        self._save_tags()

    def get_all_tags(self) -> list[Tag]:
        """Get all tags.

        Returns:
            List of all tags
        """
        return sorted(self.hierarchy.tags.values(), key=lambda t: t.path)

    def get_tag_tree(self) -> dict[str, Any]:
        """Get tag hierarchy as tree structure.

        Returns:
            Tree structure dictionary
        """
        tree = {}

        # Build tree from paths
        for path in sorted(self.hierarchy.tags.keys()):
            parts = path.split("/")
            current = tree

            for i, part in enumerate(parts):
                if part not in current:
                    current[part] = {
                        "_path": "/".join(parts[: i + 1]),
                        "_tag": self.hierarchy.tags["/".join(parts[: i + 1])],
                        "_children": {},
                    }
                current = current[part]["_children"]

        return tree

    def export_tags(self, format: str = "json") -> str:
        """Export tags.

        Args:
            format: Export format

        Returns:
            Exported content
        """
        if format == "json":
            return json.dumps(
                {
                    "tags": [
                        {
                            "path": tag.path,
                            "color": tag.color,
                            "description": tag.description,
                            "count": self.hierarchy.usage_count.get(tag.path, 0),
                        }
                        for tag in self.get_all_tags()
                    ]
                },
                indent=2,
            )

        elif format == "text":
            lines = []
            for tag in self.get_all_tags():
                indent = "  " * (tag.path.count("/"))
                name = tag.path.split("/")[-1]
                count = self.hierarchy.usage_count.get(tag.path, 0)
                lines.append(f"{indent}{name} ({count})")
            return "\n".join(lines)

        else:
            return ""
