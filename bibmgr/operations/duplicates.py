"""Duplicate detection and merging with optimized algorithms and indexing."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Callable, Any

import msgspec

from ..core.models import Entry

logger = logging.getLogger(__name__)


class MatchType(str, Enum):
    """Type of duplicate match found."""

    EXACT_KEY = "exact_key"
    DOI = "doi"
    TITLE = "title"
    AUTHOR = "author"
    COMBINED = "combined"


class MergeStrategy(str, Enum):
    """Strategy for merging duplicate entries."""

    UNION = "union"
    INTERSECTION = "intersection"
    PREFER_FIRST = "prefer_first"
    PREFER_NEWEST = "prefer_newest"
    CUSTOM = "custom"


@dataclass
class DuplicateMatch:
    """Represents a potential duplicate match."""

    entry1: Entry
    entry2: Entry
    score: float  # 0.0 to 1.0
    match_type: MatchType | list[MatchType]
    matching_fields: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Ensure match_type is a list."""
        if isinstance(self.match_type, MatchType):
            self.match_type = [self.match_type]


class SimilarityMetric(Protocol):
    """Protocol for similarity metrics."""

    def compute(self, s1: str, s2: str) -> float:
        """Compute similarity between two strings (0.0 to 1.0)."""
        ...


class StringSimilarity:
    """String similarity algorithms."""

    def __init__(
        self,
        algorithm: str = "levenshtein",
        n: int = 2,
        custom_function: Callable[[str, str], float] | None = None,
    ):
        """Initialize similarity metric.

        Args:
            algorithm: Algorithm to use (exact, levenshtein, jaccard, ngram)
            n: N-gram size for ngram algorithm
            custom_function: Custom similarity function
        """
        self.algorithm = algorithm
        self.n = n
        self.custom_function = custom_function

    def compute(self, s1: str, s2: str) -> float:
        """Compute similarity between two strings."""
        if self.custom_function:
            return self.custom_function(s1, s2)

        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        if self.algorithm == "exact":
            return 1.0 if s1 == s2 else 0.0
        elif self.algorithm == "levenshtein":
            return self._levenshtein_similarity(s1, s2)
        elif self.algorithm == "jaccard":
            return self._jaccard_similarity(s1, s2)
        elif self.algorithm == "ngram":
            return self._ngram_similarity(s1, s2, self.n)
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")

    def _levenshtein_similarity(self, s1: str, s2: str) -> float:
        """Compute normalized Levenshtein similarity."""
        len1, len2 = len(s1), len(s2)

        # Optimization for equal strings
        if s1 == s2:
            return 1.0

        # Create distance matrix
        dist = [[0] * (len2 + 1) for _ in range(len1 + 1)]

        # Initialize first row and column
        for i in range(len1 + 1):
            dist[i][0] = i
        for j in range(len2 + 1):
            dist[0][j] = j

        # Compute distances
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                dist[i][j] = min(
                    dist[i - 1][j] + 1,  # deletion
                    dist[i][j - 1] + 1,  # insertion
                    dist[i - 1][j - 1] + cost,  # substitution
                )

        # Normalize by max length
        max_len = max(len1, len2)
        return 1.0 - (dist[len1][len2] / max_len) if max_len > 0 else 1.0

    def _jaccard_similarity(self, s1: str, s2: str) -> float:
        """Compute Jaccard similarity of word sets."""
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())

        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _ngram_similarity(self, s1: str, s2: str, n: int) -> float:
        """Compute n-gram based similarity."""

        def get_ngrams(s: str, n: int) -> set[str]:
            """Get n-grams from string."""
            if len(s) < n:
                return {s}
            return {s[i : i + n] for i in range(len(s) - n + 1)}

        ngrams1 = get_ngrams(s1.lower(), n)
        ngrams2 = get_ngrams(s2.lower(), n)

        if not ngrams1 and not ngrams2:
            return 1.0
        if not ngrams1 or not ngrams2:
            return 0.0

        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)

        return intersection / union if union > 0 else 0.0


class TitleNormalizer:
    """Normalize titles for better matching."""

    # Common abbreviations to expand
    ABBREVIATIONS = {
        "proc": "proceedings",
        "conf": "conference",
        "intl": "international",
        "natl": "national",
        "trans": "transactions",
        "j": "journal",
    }

    def normalize(self, title: str) -> str:
        """Normalize a title for comparison."""
        if not title:
            return ""

        # Remove LaTeX commands
        title = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", title)
        title = re.sub(r"\\[a-zA-Z]+", "", title)

        # Convert to lowercase
        title = title.lower()

        # Remove special characters but keep spaces
        title = re.sub(r"[^\w\s]", " ", title)

        # Expand abbreviations
        words = title.split()
        words = [self.ABBREVIATIONS.get(w, w) for w in words]
        title = " ".join(words)

        # Normalize whitespace
        title = re.sub(r"\s+", " ", title)

        return title.strip()


class AuthorNormalizer:
    """Normalize author names for better matching."""

    def normalize(self, author: str) -> str:
        """Normalize a single author name."""
        if not author:
            return ""

        # Remove accents and special characters except commas and periods
        import unicodedata

        author = unicodedata.normalize("NFKD", author)
        author = "".join(c for c in author if unicodedata.category(c) != "Mn")
        author = re.sub(r"[^\w\s,.]", "", author)

        # Handle "Last, First" format
        if "," in author:
            parts = author.split(",", 1)
            if len(parts) == 2:
                last, first = parts
                author = f"{first.strip()} {last.strip()}"

        # Remove Jr, Sr, III, etc.
        author = re.sub(r"\b(jr|sr|iii|ii|iv)\b\.?", "", author, flags=re.IGNORECASE)

        # Convert to lowercase
        author = author.lower().strip()

        # Extract initials and last name
        parts = author.split()
        if parts:
            # Take first letter of all but last part, and full last part
            if len(parts) > 1:
                initials = " ".join(p[0] for p in parts[:-1])
                return f"{parts[-1]} {initials}"
            else:
                return parts[0]

        return ""

    def normalize_list(self, authors: str) -> list[str]:
        """Normalize a list of authors."""
        if not authors:
            return []

        # Split by 'and' or commas (but not commas within names)
        if " and " in authors:
            author_list = authors.split(" and ")
        elif "," in authors and authors.count(",") > 1:
            # Multiple commas might indicate list of authors
            author_list = [a.strip() for a in authors.split(",")]
        else:
            author_list = [authors]

        # Handle et al.
        normalized = []
        for author in author_list:
            author = author.strip()
            # Check for et al at the end
            if "et al" in author.lower():
                # Split on et al and process author before it
                parts = re.split(r"\s+et\s+al\.?", author, flags=re.IGNORECASE)
                if parts[0].strip():
                    norm = self.normalize(parts[0].strip())
                    if norm:
                        normalized.append(norm)
                normalized.append("et al")
            elif author.lower() in ["others"]:
                normalized.append("et al")
            else:
                norm = self.normalize(author)
                if norm:
                    normalized.append(norm)

        return normalized


class DuplicateIndex:
    """Index for fast duplicate detection."""

    def __init__(self):
        """Initialize the index."""
        self._by_doi: dict[str, list[Entry]] = defaultdict(list)
        self._by_title: dict[str, list[Entry]] = defaultdict(list)
        self._by_key: dict[str, Entry] = {}
        self._title_normalizer = TitleNormalizer()
        self._size = 0

    def __len__(self) -> int:
        """Return number of entries in index."""
        return self._size

    def build(self, entries: list[Entry]) -> None:
        """Build index from list of entries."""
        self.clear()
        for entry in entries:
            self.add(entry)

    def clear(self) -> None:
        """Clear the index."""
        self._by_doi.clear()
        self._by_title.clear()
        self._by_key.clear()
        self._size = 0

    def add(self, entry: Entry) -> None:
        """Add an entry to the index."""
        # Index by key
        self._by_key[entry.key] = entry

        # Index by DOI
        if entry.doi:
            normalized_doi = self._normalize_doi(entry.doi)
            self._by_doi[normalized_doi].append(entry)

        # Index by normalized title
        if entry.title:
            normalized_title = self._title_normalizer.normalize(entry.title)
            self._by_title[normalized_title].append(entry)

        self._size += 1

    def remove(self, entry: Entry) -> None:
        """Remove an entry from the index."""
        # Remove from key index
        if entry.key in self._by_key:
            del self._by_key[entry.key]
            self._size -= 1

        # Remove from DOI index
        if entry.doi:
            normalized_doi = self._normalize_doi(entry.doi)
            if normalized_doi in self._by_doi:
                self._by_doi[normalized_doi] = [
                    e for e in self._by_doi[normalized_doi] if e.key != entry.key
                ]
                if not self._by_doi[normalized_doi]:
                    del self._by_doi[normalized_doi]

        # Remove from title index
        if entry.title:
            normalized_title = self._title_normalizer.normalize(entry.title)
            if normalized_title in self._by_title:
                self._by_title[normalized_title] = [
                    e for e in self._by_title[normalized_title] if e.key != entry.key
                ]
                if not self._by_title[normalized_title]:
                    del self._by_title[normalized_title]

    def find_by_doi(self, doi: str) -> list[Entry]:
        """Find entries by DOI."""
        normalized = self._normalize_doi(doi)
        return self._by_doi.get(normalized, [])

    def find_by_title(self, title: str) -> list[Entry]:
        """Find entries by normalized title."""
        normalized = self._title_normalizer.normalize(title)
        return self._by_title.get(normalized, [])

    def _normalize_doi(self, doi: str) -> str:
        """Normalize DOI for indexing."""
        # Remove common prefixes
        doi = re.sub(r"^https?://doi\.org/", "", doi)
        doi = re.sub(r"^doi:", "", doi, flags=re.IGNORECASE)
        return doi.lower().strip()


class DuplicateDetector:
    """Detect duplicate entries using multiple strategies."""

    def __init__(
        self,
        title_threshold: float = 0.85,
        author_threshold: float = 0.7,
        combined_threshold: float = 0.7,
        use_index: bool = True,
    ):
        """Initialize duplicate detector.

        Args:
            title_threshold: Minimum similarity for title match
            author_threshold: Minimum similarity for author match
            combined_threshold: Minimum combined similarity
            use_index: Whether to use indexing for performance
        """
        self.title_threshold = title_threshold
        self.author_threshold = author_threshold
        self.combined_threshold = combined_threshold
        self.use_index = use_index

        self.title_normalizer = TitleNormalizer()
        self.author_normalizer = AuthorNormalizer()
        self.title_sim = StringSimilarity(algorithm="levenshtein")
        self.author_sim = StringSimilarity(algorithm="jaccard")

        self._index = DuplicateIndex() if use_index else None

    def check_duplicate(
        self, entry: Entry, existing_entries: list[Entry]
    ) -> Entry | None:
        """Check if entry is duplicate of existing entries.

        Args:
            entry: Entry to check
            existing_entries: List of existing entries to check against

        Returns:
            Existing entry if duplicate found, None otherwise
        """
        if not existing_entries:
            return None

        # Check against all existing entries
        matches = self._find_duplicates_pairwise([entry] + existing_entries)

        # Find matches involving our entry
        for match in matches:
            if match.entry1.key == entry.key:
                return match.entry2
            elif match.entry2.key == entry.key:
                return match.entry1

        return None

    def find_duplicates(self, entries: list[Entry]) -> list[DuplicateMatch]:
        """Find duplicate entries in a list.

        Args:
            entries: List of entries to check

        Returns:
            List of duplicate matches
        """
        matches = []

        # Build index if using indexing
        if self.use_index and self._index:
            self._index.build(entries)
            matches.extend(self._find_duplicates_with_index(entries))
        else:
            matches.extend(self._find_duplicates_pairwise(entries))

        # Remove duplicate matches
        seen = set()
        unique_matches = []
        for match in matches:
            pair = (
                min(match.entry1.key, match.entry2.key),
                max(match.entry1.key, match.entry2.key),
            )
            if pair not in seen:
                seen.add(pair)
                unique_matches.append(match)

        # Sort by score
        unique_matches.sort(key=lambda m: m.score, reverse=True)
        return unique_matches

    def _find_duplicates_with_index(self, entries: list[Entry]) -> list[DuplicateMatch]:
        """Find duplicates using index for performance."""
        matches = []

        for entry in entries:
            # Check DOI matches
            if entry.doi and self._index:
                doi_matches = self._index.find_by_doi(entry.doi)
                for match in doi_matches:
                    if match.key != entry.key:
                        matches.append(
                            DuplicateMatch(
                                entry1=entry,
                                entry2=match,
                                score=1.0,
                                match_type=MatchType.DOI,
                                matching_fields=["doi"],
                            )
                        )

            # Check title matches
            if entry.title and self._index:
                title_matches = self._index.find_by_title(entry.title)
                for match in title_matches:
                    if match.key != entry.key:
                        # Already found by DOI?
                        if any(m.entry2.key == match.key for m in matches):
                            continue

                        # Compute actual similarity
                        if match.title:
                            title_score = self.title_sim.compute(
                                self.title_normalizer.normalize(entry.title),
                                self.title_normalizer.normalize(match.title),
                            )
                        else:
                            title_score = 0.0

                        if title_score >= self.title_threshold:
                            matches.append(
                                DuplicateMatch(
                                    entry1=entry,
                                    entry2=match,
                                    score=title_score,
                                    match_type=MatchType.TITLE,
                                    matching_fields=["title"],
                                )
                            )

        return matches

    def _find_duplicates_pairwise(self, entries: list[Entry]) -> list[DuplicateMatch]:
        """Find duplicates using pairwise comparison."""
        matches = []

        for i, e1 in enumerate(entries):
            for e2 in entries[i + 1 :]:
                match = self._check_pair(e1, e2)
                if match:
                    matches.append(match)

        return matches

    def _check_pair(self, e1: Entry, e2: Entry) -> DuplicateMatch | None:
        """Check if two entries are duplicates."""
        # Exact key match
        if e1.key == e2.key:
            return DuplicateMatch(
                entry1=e1,
                entry2=e2,
                score=1.0,
                match_type=MatchType.EXACT_KEY,
                matching_fields=["key"],
            )

        # DOI match
        if e1.doi and e2.doi:
            doi1 = self._normalize_doi(e1.doi)
            doi2 = self._normalize_doi(e2.doi)
            if doi1 == doi2:
                return DuplicateMatch(
                    entry1=e1,
                    entry2=e2,
                    score=1.0,
                    match_type=MatchType.DOI,
                    matching_fields=["doi"],
                )

        # Title similarity
        if e1.title and e2.title:
            title_score = self.title_sim.compute(
                self.title_normalizer.normalize(e1.title),
                self.title_normalizer.normalize(e2.title),
            )

            if title_score >= self.title_threshold:
                matching_fields = ["title"]
                match_types = [MatchType.TITLE]

                # Check year match for higher confidence
                if e1.year and e2.year and e1.year == e2.year:
                    matching_fields.append("year")
                    title_score = min(title_score * 1.1, 1.0)

                return DuplicateMatch(
                    entry1=e1,
                    entry2=e2,
                    score=title_score,
                    match_type=match_types,
                    matching_fields=matching_fields,
                )

        # Author similarity
        if e1.author and e2.author:
            author_score = self._compute_author_similarity(e1.author, e2.author)

            if author_score >= self.author_threshold:
                # Also check title for combined match
                title_score = 0.0
                if e1.title and e2.title:
                    title_score = self.title_sim.compute(
                        self.title_normalizer.normalize(e1.title),
                        self.title_normalizer.normalize(e2.title),
                    )

                if title_score > 0.5:  # Some title similarity
                    combined_score = (author_score + title_score) / 2
                    return DuplicateMatch(
                        entry1=e1,
                        entry2=e2,
                        score=combined_score,
                        match_type=[MatchType.AUTHOR],
                        matching_fields=["author", "title"],
                    )

        # Combined similarity
        scores = []
        fields = []

        if e1.title and e2.title:
            title_score = self.title_sim.compute(
                self.title_normalizer.normalize(e1.title),
                self.title_normalizer.normalize(e2.title),
            )
            if title_score > 0.5:
                scores.append(title_score)
                fields.append("title")

        if e1.author and e2.author:
            author_score = self._compute_author_similarity(e1.author, e2.author)
            if author_score > 0.5:
                scores.append(author_score)
                fields.append("author")

        if e1.year and e2.year and e1.year == e2.year:
            scores.append(1.0)
            fields.append("year")

        if e1.journal and e2.journal:
            journal_score = self.title_sim.compute(
                e1.journal.lower(), e2.journal.lower()
            )
            if journal_score > 0.7:
                scores.append(journal_score)
                fields.append("journal")

        if scores and len(fields) >= 2:
            combined_score = sum(scores) / len(scores)
            if combined_score >= self.combined_threshold:
                return DuplicateMatch(
                    entry1=e1,
                    entry2=e2,
                    score=combined_score,
                    match_type=MatchType.COMBINED,
                    matching_fields=fields,
                )

        return None

    def _compute_author_similarity(self, authors1: str, authors2: str) -> float:
        """Compute similarity between author lists."""
        list1 = self.author_normalizer.normalize_list(authors1)
        list2 = self.author_normalizer.normalize_list(authors2)

        if not list1 or not list2:
            return 0.0

        # Count matching authors
        matches = 0
        for a1 in list1:
            for a2 in list2:
                if self._authors_match(a1, a2):
                    matches += 1
                    break

        # Jaccard-like score
        return matches / max(len(list1), len(list2))

    def _authors_match(self, a1: str, a2: str) -> bool:
        """Check if two normalized author names match."""
        if a1 == a2:
            return True

        # Check if one is abbreviation of other
        parts1 = a1.split()
        parts2 = a2.split()

        if len(parts1) == len(parts2) and len(parts1) >= 2:
            # Check last names match
            if parts1[0] == parts2[0]:
                # Check initials match
                for p1, p2 in zip(parts1[1:], parts2[1:]):
                    if p1[0] != p2[0]:
                        return False
                return True

        return False

    def _normalize_doi(self, doi: str) -> str:
        """Normalize DOI for comparison."""
        doi = re.sub(r"^https?://doi\.org/", "", doi)
        doi = re.sub(r"^doi:", "", doi, flags=re.IGNORECASE)
        return doi.lower().strip()

    def find_duplicate_groups(self, entries: list[Entry]) -> list[list[Entry]]:
        """Group entries that are duplicates of each other.

        Args:
            entries: List of entries to group

        Returns:
            List of duplicate groups
        """
        matches = self.find_duplicates(entries)

        # Build adjacency graph
        graph: dict[str, set[str]] = defaultdict(set)
        entry_map = {e.key: e for e in entries}

        for match in matches:
            graph[match.entry1.key].add(match.entry2.key)
            graph[match.entry2.key].add(match.entry1.key)

        # Find connected components
        visited = set()
        groups = []

        for entry in entries:
            if entry.key not in visited:
                group = self._dfs_group(entry.key, graph, entry_map, visited)
                if len(group) > 1:  # Only include actual duplicate groups
                    groups.append(group)

        return groups

    def _dfs_group(
        self,
        key: str,
        graph: dict[str, set[str]],
        entry_map: dict[str, Entry],
        visited: set[str],
    ) -> list[Entry]:
        """DFS to find connected component."""
        if key in visited or key not in entry_map:
            return []

        visited.add(key)
        group = [entry_map[key]]

        for neighbor in graph.get(key, []):
            group.extend(self._dfs_group(neighbor, graph, entry_map, visited))

        return group


class EntryMerger:
    """Merge duplicate entries."""

    def merge(
        self,
        entries: list[Entry],
        strategy: MergeStrategy = MergeStrategy.UNION,
        custom_resolver: Callable[[str, list[Any]], Any] | None = None,
    ) -> Entry:
        """Merge multiple entries into one.

        Args:
            entries: Entries to merge
            strategy: Merge strategy
            custom_resolver: Custom field resolver function

        Returns:
            Merged entry

        Raises:
            ValueError: If no entries provided
        """
        if not entries:
            raise ValueError("No entries to merge")

        if len(entries) == 1:
            return entries[0]

        # Collect all field values
        field_values: dict[str, list[Any]] = defaultdict(list)

        for entry in entries:
            entry_dict = msgspec.structs.asdict(entry)
            for field_name, value in entry_dict.items():
                if value is not None:
                    if value not in field_values[field_name]:
                        field_values[field_name].append(value)

        # Resolve conflicts based on strategy
        resolved = {}

        for field_name, values in field_values.items():
            if len(values) == 1:
                resolved[field_name] = values[0]
            else:
                # Conflict resolution
                if custom_resolver:
                    resolved[field_name] = custom_resolver(field_name, values)
                elif strategy == MergeStrategy.UNION:
                    resolved[field_name] = self._resolve_union(field_name, values)
                elif strategy == MergeStrategy.INTERSECTION:
                    # Skip conflicting fields
                    continue
                elif strategy == MergeStrategy.PREFER_FIRST:
                    resolved[field_name] = values[0]
                elif strategy == MergeStrategy.PREFER_NEWEST:
                    resolved[field_name] = self._resolve_newest(
                        field_name, values, entries
                    )
                else:
                    resolved[field_name] = values[0]  # Default to first

        # Ensure required fields
        if "key" not in resolved:
            resolved["key"] = entries[0].key
        if "type" not in resolved:
            resolved["type"] = entries[0].type

        return msgspec.convert(resolved, Entry)

    def _resolve_union(self, field: str, values: list[Any]) -> Any:
        """Resolve field using union strategy."""
        if field in ["keywords", "tags"]:
            # Concatenate text fields
            all_items = []
            for v in values:
                if isinstance(v, str):
                    items = [i.strip() for i in v.split(";")]
                    all_items.extend(items)
            return "; ".join(sorted(set(all_items)))
        elif field == "author":
            # Prefer longer author list
            return max(values, key=lambda x: len(x) if x else 0)
        elif field == "pages":
            # For pages, prefer the most complete format (e.g. "1-20" over "1" or "20")
            # Don't concatenate page numbers
            for v in values:
                if v and "-" in str(v):
                    return v
            return values[0] if values else None
        else:
            # Default to first non-empty
            return next((v for v in values if v), values[0])

    def _resolve_newest(
        self,
        field: str,
        values: list[Any],
        entries: list[Entry],
    ) -> Any:
        """Resolve field by preferring newest entry."""
        # Find newest entry by year
        newest_idx = 0
        newest_year = 0

        for i, entry in enumerate(entries):
            if entry.year and entry.year > newest_year:
                newest_year = entry.year
                newest_idx = i

        # Get value from newest entry
        entry_dict = msgspec.structs.asdict(entries[newest_idx])
        return entry_dict.get(field, values[0])
