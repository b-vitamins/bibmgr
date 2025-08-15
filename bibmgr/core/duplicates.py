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
            if entry.title and entry.author and entry.year:
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
        """Normalize text for comparison."""
        # Convert to lowercase
        text = text.lower()

        # Remove LaTeX commands
        text = re.sub(r"\\[a-zA-Z]+\*?", "", text)

        # Remove braces
        text = text.replace("{", "").replace("}", "")

        # Normalize Unicode to ASCII
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))

        # Remove articles
        text = re.sub(r"\b(the|a|an)\b", "", text)

        # Remove punctuation
        text = re.sub(r"[^\w\s]", " ", text)

        # Collapse spaces
        text = " ".join(text.split())

        return text

    def _normalize_author(self, author: str) -> str:
        """Normalize author name for comparison, handling initials."""
        if not author:
            return ""

        # First apply basic text normalization
        normalized = self._normalize_text(author)

        # Handle author name variations
        # Split by common delimiters (comma, and, &)
        author_parts = re.split(r"[,&]|\sand\s", normalized)

        normalized_parts = []
        for part in author_parts:
            part = part.strip()
            if not part:
                continue

            # Split into words
            words = part.split()
            if len(words) >= 2:
                # Assume format like "Smith John" or "John Smith"
                # Extract surname (longest word typically)
                surname = max(words, key=len)
                # Extract initials from other words
                initials = []
                for word in words:
                    if word != surname:
                        if len(word) == 1:
                            # Already an initial
                            initials.append(word)
                        elif len(word) > 1:
                            # Take first letter as initial
                            initials.append(word[0])

                # Create normalized form: "surname initial1 initial2"
                if initials:
                    normalized_parts.append(f"{surname} {' '.join(sorted(initials))}")
                else:
                    normalized_parts.append(surname)
            else:
                # Single word, keep as is
                normalized_parts.append(part)

        return " ".join(normalized_parts)

    def _make_tay_key(self, entry: Entry) -> str:
        """Make normalized title-author-year key."""
        # Normalize title
        title = self._normalize_text(entry.title or "")

        # Normalize authors with special handling for initials
        authors = self._normalize_author(entry.author or "")

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
        for key, entries in self.title_author_year_map.items():
            if len(entries) > 1:
                group_keys = frozenset(e.key for e in entries)
                if group_keys not in seen:
                    duplicates.append(entries)
                    seen.add(group_keys)

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
            key = self._make_tay_key(entry)
            tay_dups = self.title_author_year_map.get(key, [])
            other_dups = [e for e in tay_dups if e.key != entry.key]
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
