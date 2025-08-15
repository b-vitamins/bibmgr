"""Duplicate entry detection system."""

import re
import unicodedata
from typing import Any

from .models import Entry, ValidationError


class DuplicateDetector:
    """Detect duplicate entries."""

    def __init__(self, entries: list[Entry], year_tolerance: int = 0):
        self.entries = entries
        self.year_tolerance = year_tolerance
        self.doi_map: dict[str, list[Entry]] = {}
        self.title_author_year_map: dict[str, list[Entry]] = {}
        self._build_maps()

    def _build_maps(self):
        """Build lookup maps for duplicate detection."""
        for entry in self.entries:
            # DOI duplicates
            if entry.doi:
                doi_normalized = self._normalize_doi(entry.doi)
                if doi_normalized:  # Don't add empty normalized DOIs
                    self.doi_map.setdefault(doi_normalized, []).append(entry)

            # Title-Author-Year duplicates
            if entry.title and entry.author and entry.year and self.year_tolerance == 0:
                key = self._make_tay_key(entry)
                self.title_author_year_map.setdefault(key, []).append(entry)

    def _normalize_doi(self, doi: str) -> str:
        """Normalize DOI for comparison."""
        if not doi:
            return ""

        # Convert to lowercase and strip whitespace
        doi = doi.lower().strip()

        # Remove common URL prefixes
        prefixes = [
            "https://doi.org/",
            "http://doi.org/",
            "https://dx.doi.org/",
            "http://dx.doi.org/",
            "doi:",
        ]

        for prefix in prefixes:
            if doi.startswith(prefix):
                doi = doi[len(prefix) :]
                break

        return doi

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for robust comparison.

        - Convert to lowercase
        - Handle LaTeX commands
        - Normalize Unicode to ASCII
        - Remove articles and punctuation
        """
        # Convert to lowercase
        text = text.lower()

        # Handle common LaTeX commands
        latex_replacements = {
            r"\{\\latex\}": "latex",
            r"\\latex": "latex",
            r"\{\\tex\}": "tex",
            r"\\tex": "tex",
        }

        for pattern, replacement in latex_replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Remove other LaTeX commands
        text = re.sub(r"\{\\[a-zA-Z]+\*?\}", " ", text)  # {\command}
        text = re.sub(r"\\[a-zA-Z]+\*?\s*\{\}", " ", text)  # \command{}
        text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)  # \command

        # Remove braces
        text = text.replace("{", "").replace("}", "")

        # Normalize Unicode
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))

        # Remove articles
        text = re.sub(r"\b(the|a|an)\b", "", text)

        # Remove punctuation
        text = re.sub(r"[^\w\s]", " ", text)

        # Normalize whitespace
        text = " ".join(text.split())

        return text

    def _normalize_authors(self, authors: str) -> str:
        """
        Normalize author names for comparison.

        Extract and sort last names to handle:
        - Different name orders
        - Abbreviations
        - Multiple authors
        """
        # Split authors first (before normalization to preserve structure)
        author_list = re.split(r"\s+and\s+", authors)

        # Extract last names
        last_names = []
        for author in author_list:
            author = author.strip()
            if not author:
                continue

            # Check if it's "Last, First" format
            if "," in author:
                # Split by comma and take the first part as last name
                parts = author.split(",", 1)
                last_name = parts[0].strip()
            else:
                # "First Last" format - take the last word
                words = author.split()
                if not words:
                    continue

                # Skip common suffixes
                suffixes = {
                    "jr",
                    "sr",
                    "ii",
                    "iii",
                    "iv",
                    "v",
                    "phd",
                    "md",
                    "Jr",
                    "Sr",
                    "II",
                    "III",
                    "IV",
                    "V",
                    "PhD",
                    "MD",
                }

                # Work backwards to find last name
                last_name = None
                for i in range(len(words) - 1, -1, -1):
                    word = words[i]
                    if word not in suffixes and len(word) > 1:
                        last_name = word
                        break

                # If we couldn't find a suitable last name, use the last word
                if not last_name and words:
                    last_name = words[-1]

            if last_name:
                # Normalize the last name
                last_name = self._normalize_text(last_name)
                if last_name:  # Only add non-empty normalized names
                    last_names.append(last_name)

        # Sort for consistent ordering
        last_names.sort()

        return " ".join(last_names)

    def _make_tay_key(self, entry: Entry) -> str:
        """Make normalized title-author-year key."""
        # Normalize title
        title = self._normalize_text(entry.title or "")

        # Normalize authors with special handling for initials
        authors = self._normalize_authors(entry.author or "")

        # Handle year tolerance
        if self.year_tolerance > 0 and entry.year:
            # Create a year range key
            year_base = (
                entry.year // (self.year_tolerance + 1) * (self.year_tolerance + 1)
            )
            year_str = f"{year_base}-{year_base + self.year_tolerance}"
        else:
            year_str = str(entry.year)

        return f"{title}|{authors}|{year_str}"

    def find_duplicates(self) -> list[list[Entry]]:
        """Find groups of duplicate entries."""
        duplicates = []
        seen = set()

        # Check DOI duplicates
        for doi, entries in self.doi_map.items():
            if len(entries) > 1:
                group_keys = frozenset(e.key for e in entries)
                if group_keys not in seen:
                    duplicates.append(entries)
                    seen.add(group_keys)

        # Check title-author-year duplicates
        if self.year_tolerance == 0:
            # Exact year matching - use pre-built index
            for key, entries in self.title_author_year_map.items():
                if len(entries) > 1:
                    group_keys = frozenset(e.key for e in entries)
                    if group_keys not in seen:
                        duplicates.append(entries)
                        seen.add(group_keys)
        else:
            # Year tolerance - need custom grouping
            self._find_tay_duplicates_with_tolerance(duplicates, seen)

        return duplicates

    def validate_entry(self, entry: Entry) -> list[ValidationError]:
        """Check if entry has duplicates."""
        errors = []

        # Check DOI duplicates
        if entry.doi:
            doi_normalized = self._normalize_doi(entry.doi)
            if doi_normalized:
                doi_dups = self.doi_map.get(doi_normalized, [])
                other_dups = [e for e in doi_dups if e.key != entry.key]
                if other_dups:
                    errors.append(
                        ValidationError(
                            field="doi",
                            message=f"Duplicate DOI found in entries: {', '.join(e.key for e in other_dups)}",
                            severity="warning",
                            entry_key=entry.key,
                        )
                    )

        # Check title-author-year duplicates
        if entry.title and entry.author and entry.year:
            if self.year_tolerance == 0:
                # Use index for exact matching
                key = self._make_tay_key(entry)
                tay_dups = self.title_author_year_map.get(key, [])
                other_dups = [e for e in tay_dups if e.key != entry.key]
            else:
                # Manual search with tolerance
                other_dups = self._find_tay_matches_with_tolerance(entry)
                
            if other_dups:
                errors.append(
                    ValidationError(
                        field=None,
                        message=f"Possible duplicate (same title/author/year) in entries: {', '.join(e.key for e in other_dups)}",
                        severity="info",
                        entry_key=entry.key,
                    )
                )

        return errors

    def find_duplicates_with_confidence(self) -> list[dict[str, Any]]:
        """Find duplicates with confidence scores."""
        results = []

        # First get all duplicate groups
        duplicate_groups = self.find_duplicates()

        for group in duplicate_groups:
            # Calculate confidence based on matching criteria
            confidence = 0.0

            # Check if all have same DOI
            dois = [self._normalize_doi(e.doi) for e in group if e.doi]
            if dois and all(d == dois[0] for d in dois):
                confidence = 0.95  # Very high confidence for DOI match

            # Check title/author/year match
            if all(e.title and e.author and e.year for e in group):
                # All have required fields
                keys = [self._make_tay_key(e) for e in group]
                if all(k == keys[0] for k in keys):
                    # Exact normalized match
                    if confidence == 0:
                        confidence = 0.8
                    else:
                        confidence = min(1.0, confidence + 0.1)
                else:
                    # Partial match - need more sophisticated comparison
                    confidence = max(confidence, 0.6)

            results.append({"entries": group, "confidence": confidence})

        return results

    def get_merge_suggestions(self, entry1: Entry, entry2: Entry) -> dict[str, Any]:
        """Suggest which fields to keep when merging duplicates."""
        suggestions = {}

        # Get all field names from both entries
        all_fields = set()
        for field in dir(entry1):
            if not field.startswith("_") and hasattr(entry2, field):
                all_fields.add(field)

        # Compare each field
        for field in all_fields:
            val1 = getattr(entry1, field, None)
            val2 = getattr(entry2, field, None)

            # Skip special fields
            if field in ["key", "id", "added", "modified"]:
                continue

            # Prefer non-empty over empty
            if val2 and not val1:
                suggestions[field] = val2
            elif val1 and not val2:
                suggestions[field] = val1
            elif val1 and val2:
                # Both have values
                if field == "author":
                    # Prefer more complete author list
                    if len(str(val2)) > len(str(val1)):
                        suggestions[field] = val2
                    else:
                        suggestions[field] = val1
                elif field in ["doi", "url", "isbn", "issn"]:
                    # Prefer the second one for identifiers (assumed more complete)
                    suggestions[field] = val2
                elif field == "abstract":
                    # Prefer longer abstract
                    if len(str(val2)) > len(str(val1)):
                        suggestions[field] = val2
                    else:
                        suggestions[field] = val1
                else:
                    # Default to second entry
                    suggestions[field] = val2

        return suggestions

    def _find_tay_duplicates_with_tolerance(
        self, duplicates: list[list[Entry]], seen_groups: set[frozenset[str]]
    ) -> None:
        """Find title-author-year duplicates with year tolerance."""
        # Group by title and author only
        ta_groups: dict[str, list[Entry]] = {}

        for entry in self.entries:
            if entry.title and entry.author and entry.year:
                title = self._normalize_text(entry.title)
                authors = self._normalize_authors(entry.author)
                ta_key = f"{title}|{authors}"
                ta_groups.setdefault(ta_key, []).append(entry)

        # Check each group for year proximity
        for entries in ta_groups.values():
            if len(entries) < 2:
                continue

            # Group by year tolerance using union-find approach
            year_groups = self._group_by_year_tolerance(entries)

            # Add groups with 2+ entries
            for group in year_groups:
                if len(group) > 1:
                    group_keys = frozenset(e.key for e in group)
                    if group_keys not in seen_groups:
                        duplicates.append(group)
                        seen_groups.add(group_keys)

    def _group_by_year_tolerance(self, entries: list[Entry]) -> list[list[Entry]]:
        """Group entries by year tolerance using connected components."""
        if not entries:
            return []

        # Build adjacency list
        n = len(entries)
        adjacent = [set() for _ in range(n)]

        for i in range(n):
            for j in range(i + 1, n):
                # Year fields are guaranteed to exist by caller
                year_i = entries[i].year
                year_j = entries[j].year
                assert year_i is not None
                assert year_j is not None
                if abs(year_i - year_j) <= self.year_tolerance:
                    adjacent[i].add(j)
                    adjacent[j].add(i)

        # Find connected components
        visited = [False] * n
        components = []

        for i in range(n):
            if not visited[i]:
                component = []
                self._dfs(i, visited, adjacent, component, entries)
                components.append(component)

        return components

    def _dfs(
        self,
        node: int,
        visited: list[bool],
        adjacent: list[set[int]],
        component: list[Entry],
        entries: list[Entry],
    ) -> None:
        """Depth-first search for connected components."""
        visited[node] = True
        component.append(entries[node])

        for neighbor in adjacent[node]:
            if not visited[neighbor]:
                self._dfs(neighbor, visited, adjacent, component, entries)

    def _find_tay_matches_with_tolerance(self, target: Entry) -> list[Entry]:
        """Find entries matching title/author/year with tolerance."""
        matches = []

        # These are guaranteed by the caller
        assert target.title is not None
        assert target.author is not None
        assert target.year is not None

        target_title = self._normalize_text(target.title)
        target_authors = self._normalize_authors(target.author)

        for entry in self.entries:
            if entry.key == target.key:
                continue

            if entry.title and entry.author and entry.year:
                if (
                    self._normalize_text(entry.title) == target_title
                    and self._normalize_authors(entry.author) == target_authors
                    and abs(entry.year - target.year) <= self.year_tolerance
                ):
                    matches.append(entry)

        return matches
