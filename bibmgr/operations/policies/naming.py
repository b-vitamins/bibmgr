"""Key naming policies for generating unique keys."""

import re
from datetime import datetime

from bibmgr.core.models import Entry
from bibmgr.storage.repository import EntryRepository


class KeyNamingPolicy:
    """Policy for generating entry keys."""

    def __init__(
        self,
        style: str = "author_year",
        max_length: int = 50,
        allowed_chars: str = r"[a-zA-Z0-9_-]",
    ):
        self.style = style
        self.max_length = max_length
        self.allowed_chars = allowed_chars

    def generate_key(self, entry: Entry) -> str:
        """Generate a key for an entry."""
        if self.style == "author_year":
            return self._author_year_key(entry)
        elif self.style == "author_title_year":
            return self._author_title_year_key(entry)
        elif self.style == "title_year":
            return self._title_year_key(entry)
        elif self.style == "numeric":
            return self._numeric_key(entry)
        else:
            return self._author_year_key(entry)

    def generate_alternative(
        self, base_key: str, repository: EntryRepository | None = None
    ) -> str:
        """Generate alternative key when conflict exists."""
        if not repository:
            return f"{base_key}_alt"

        for suffix in "abcdefghijklmnopqrstuvwxyz":
            candidate = f"{base_key}{suffix}"
            if not repository.exists(candidate):
                return candidate

        for i in range(2, 100):
            candidate = f"{base_key}{i}"
            if not repository.exists(candidate):
                return candidate

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{base_key}_{timestamp}"

    def validate_key(self, key: str) -> list[str]:
        """Validate a key against policy."""
        errors = []

        if not key:
            errors.append("Key cannot be empty")

        if len(key) > self.max_length:
            errors.append(f"Key too long (max {self.max_length} chars)")

        if not re.match(f"^{self.allowed_chars}+$", key):
            errors.append("Key contains invalid characters")

        return errors

    def sanitize_key(self, key: str) -> str:
        """Sanitize a key to meet policy requirements."""
        key = re.sub(f"[^{self.allowed_chars[1:-1]}]", "_", key)

        if len(key) > self.max_length:
            key = key[: self.max_length]

        key = key.strip("_")

        key = re.sub(r"_+", "_", key)

        return key

    def _author_year_key(self, entry: Entry) -> str:
        """Generate author_year style key."""
        parts = []

        if entry.author:
            authors = entry.author.split(" and ")
            if authors:
                first_author = authors[0].strip()
                if "," in first_author:
                    last_name = first_author.split(",")[0].strip()
                else:
                    words = first_author.split()
                    last_name = words[-1] if words else ""

                if last_name:
                    last_name = re.sub(r"[^\w]", "", last_name)
                    parts.append(last_name.lower())

        if entry.year:
            parts.append(str(entry.year))

        if len(parts) == 1 and entry.year and not entry.author:
            parts.insert(0, entry.type.value)

        if not parts:
            parts = [entry.type.value, datetime.now().strftime("%Y%m%d")]

        key = "_".join(parts)
        return self.sanitize_key(key)

    def _author_title_year_key(self, entry: Entry) -> str:
        """Generate author_title_year style key."""
        parts = []

        if entry.author:
            authors = entry.author.split(" and ")
            if authors:
                first_author = authors[0].strip()
                if "," in first_author:
                    last_name = first_author.split(",")[0].strip()
                else:
                    words = first_author.split()
                    last_name = words[-1] if words else ""

                if last_name:
                    last_name = re.sub(r"[^\w]", "", last_name)
                    parts.append(last_name.lower())

        if entry.title:
            stop_words = {"the", "a", "an", "of", "in", "on", "at", "to", "for"}
            words = entry.title.lower().split()
            significant_words = [w for w in words if w not in stop_words and len(w) > 3]

            if significant_words:
                first_word = re.sub(r"[^\w]", "", significant_words[0])
                if first_word:
                    parts.append(first_word)

        if entry.year:
            parts.append(str(entry.year))

        if not parts:
            parts = [entry.type.value, datetime.now().strftime("%Y%m%d")]

        key = "_".join(parts)
        return self.sanitize_key(key)

    def _title_year_key(self, entry: Entry) -> str:
        """Generate title_year style key."""
        parts = []

        if entry.title:
            words = entry.title.lower().split()
            significant_words = [re.sub(r"[^\w]", "", w) for w in words if len(w) > 3][
                :3
            ]

            if significant_words:
                parts.append("_".join(significant_words))

        if entry.year:
            parts.append(str(entry.year))

        if not parts:
            parts = [entry.type.value, datetime.now().strftime("%Y%m%d")]

        key = "_".join(parts)
        return self.sanitize_key(key)

    def _numeric_key(self, entry: Entry) -> str:
        """Generate numeric style key."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        key = f"{entry.type.value}_{timestamp}"
        return self.sanitize_key(key)
