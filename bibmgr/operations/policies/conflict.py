"""Conflict resolution policies for operations."""

from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from bibmgr.core.models import Entry
from bibmgr.storage.repository import EntryRepository


class ConflictResolution(Enum):
    """Conflict resolution strategies."""

    SKIP = "skip"
    REPLACE = "replace"
    RENAME = "rename"
    MERGE = "merge"
    ASK = "ask"
    FAIL = "fail"


class ConflictDecision:
    """Decision made by conflict policy."""

    def __init__(
        self,
        action: str,
        new_key: str | None = None,
        reason: str | None = None,
    ):
        self.action = action
        self.new_key = new_key
        self.reason = reason


class ConflictResolver(Protocol):
    """Protocol for conflict resolution."""

    def resolve(
        self, new_entry: Entry, existing_entry: Entry, context: dict[str, Any]
    ) -> ConflictDecision:
        """Resolve conflict between entries."""
        ...


class ConflictPolicy:
    """Policy for handling conflicts during operations."""

    def __init__(
        self,
        default_resolution: ConflictResolution = ConflictResolution.ASK,
        custom_resolver: ConflictResolver | None = None,
    ):
        self.default_resolution = default_resolution
        self.custom_resolver = custom_resolver

        self.rules = [
            lambda new, old: ConflictDecision(
                "replace", reason="New entry has more data"
            )
            if len(new.to_dict()) > len(old.to_dict())
            else None,
            lambda new, old: ConflictDecision("merge", reason="Same DOI")
            if new.doi and new.doi == old.doi
            else None,
            lambda new, old: ConflictDecision("skip", reason="Existing entry is recent")
            if (datetime.now() - old.added).days < 1
            else None,
        ]

    def resolve(
        self,
        new_entry: Entry,
        existing_entry: Entry,
        strategy: ConflictResolution | None = None,
        context: dict[str, Any] | None = None,
    ) -> ConflictDecision:
        """Resolve conflict between entries."""
        strategy = strategy or self.default_resolution
        context = context or {}

        if self.custom_resolver:
            decision = self.custom_resolver.resolve(new_entry, existing_entry, context)
            if decision:
                return decision

        if strategy == ConflictResolution.ASK:
            for rule in self.rules:
                decision = rule(new_entry, existing_entry)
                if decision:
                    return decision

        if strategy == ConflictResolution.SKIP:
            return ConflictDecision("skip")

        elif strategy == ConflictResolution.REPLACE:
            return ConflictDecision("replace")

        elif strategy == ConflictResolution.RENAME:
            new_key = self._generate_unique_key(
                new_entry.key, context.get("repository")
            )
            return ConflictDecision("rename", new_key=new_key)

        elif strategy == ConflictResolution.MERGE:
            return ConflictDecision("merge")

        elif strategy == ConflictResolution.FAIL:
            return ConflictDecision("fail", reason="Conflict not allowed")

        else:
            return ConflictDecision("ask")

    def _generate_unique_key(
        self, base_key: str, repository: EntryRepository | None
    ) -> str:
        """Generate unique key based on base key."""
        if not repository:
            return f"{base_key}_alt"

        for suffix in "abcdefghijklmnopqrstuvwxyz":
            candidate = f"{base_key}{suffix}"
            if not repository.exists(candidate):
                return candidate

        for i in range(1, 1000):
            candidate = f"{base_key}_{i}"
            if not repository.exists(candidate):
                return candidate

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{base_key}_{timestamp}"
