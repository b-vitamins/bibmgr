"""Sort key and label generation for BibTeX entries.

Provides functionality for generating sort keys to order bibliography
entries and creating citation labels for different bibliography styles.
Supports plain (author-year-title) and alpha (abbreviated labels) styles.

Key components:
- SortKeyGenerator: Creates sort keys for bibliography ordering
- LabelGenerator: Creates citation labels (e.g., [Knu84], [1])
"""

import re

from .models import Entry
from .names import NameParser
from .titles import TitleProcessor


class SortKeyGenerator:
    """Generate sort keys for bibliography entries.

    Sort keys determine the order of entries in the bibliography.
    Different styles use different sorting criteria:
    - plain: author, year, title (with crossref entries first)
    - alpha: label (without year), year
    """

    def __init__(self, style: str = "plain"):
        """Initialize with bibliography style.

        Args:
            style: Bibliography style (plain, alpha, etc.)
        """
        self.style = style

    def generate(self, entry: Entry) -> str:
        """Generate sort key for an entry.

        Args:
            entry: Bibliography entry.

        Returns:
            Sort key string for ordering.
        """
        if self.style == "alpha":
            return self._alpha_sort_key(entry)
        else:
            return self._plain_sort_key(entry)

    def _plain_sort_key(self, entry: Entry) -> str:
        """Generate plain style sort key: author, year, title.

        The sort key contains:
        0. Crossref prefix (entries with crossref sort first)
        1. Author last names (purified)
        2. Author first names (purified)
        3. Year (or 9999 if missing)
        4. Title (purified)

        All components are lowercase for case-insensitive sorting.
        """
        parts = []

        if entry.crossref:
            parts.append("0")
        else:
            parts.append("1")

        if entry.author:
            name_parser = NameParser()
            authors = re.split(r"\s+and\s+", entry.author, flags=re.IGNORECASE)

            for author in authors:
                parsed = name_parser.parse(author)

                for part in parsed.last:
                    purified = TitleProcessor.purify(part)
                    if purified:
                        parts.append(purified)

                for part in parsed.first:
                    purified = TitleProcessor.purify(part)
                    if purified:
                        parts.append(purified)

        if entry.year:
            parts.append(str(entry.year).zfill(4))
        else:
            parts.append("9999")

        if entry.title:
            purified_title = TitleProcessor.purify(entry.title)
            if purified_title:
                parts.append(purified_title)

        return " ".join(parts).lower()

    def _alpha_sort_key(self, entry: Entry) -> str:
        """Generate alpha style sort key: label (without year) + year.

        Uses the alpha label but separates the year component
        for proper chronological sorting within same author group.
        """
        # Generate label
        label_gen = LabelGenerator("alpha")
        label = label_gen.generate(entry)

        # Extract label without year (last 2-3 characters)
        # Labels end with 2 digits for year or ?? for missing year
        # Some may have a suffix letter (e.g., "Knu84a")
        match = re.match(r"^(.+?)(\d{2}|\?\?)([a-z]?)$", label)
        if match:
            label_prefix = match.group(1)
            letter_suffix = match.group(3)
        else:
            # Fallback
            label_prefix = label
            letter_suffix = ""

        # Use full year for sorting
        if entry.year:
            year = str(entry.year).zfill(4)
        else:
            year = "9999"

        # Include letter suffix in sort key
        return f"{label_prefix} {year} {letter_suffix}".strip().lower()


class LabelGenerator:
    """Generate labels for bibliography entries.

    Labels are used in citations (e.g., [1], [Knu84]).
    Different styles generate different label formats:
    - numeric: Sequential numbers
    - alpha: Author initials + year
    - plain: Uses numeric style
    """

    def __init__(self, style: str = "numeric"):
        """Initialize with label style.

        Args:
            style: Label style (numeric, alpha, plain, etc.)
        """
        self.style = style
        self.numeric_labels: dict[str, int] = {}
        self.alpha_counts: dict[str, int] = {}
        self.next_number = 1

    def generate(self, entry: Entry) -> str:
        """Generate label for an entry.

        Args:
            entry: Bibliography entry

        Returns:
            Label string for citations
        """
        if self.style == "alpha":
            return self._alpha_label(entry)
        elif self.style == "numeric" or self.style == "plain":
            return self._numeric_label(entry)
        else:
            # Unknown style - use entry key
            return entry.key

    def _numeric_label(self, entry: Entry) -> str:
        """Generate numeric label.

        Each unique entry gets a sequential number.
        The same entry always gets the same number.
        """
        if entry.key not in self.numeric_labels:
            self.numeric_labels[entry.key] = self.next_number
            self.next_number += 1
        return str(self.numeric_labels[entry.key])

    def _alpha_label(self, entry: Entry) -> str:
        """Generate alpha-style label.

        Format depends on number of authors:
        - Single author: First 3 letters of last name + year (Knu84)
        - Two authors: First letter of each last name + year (DS24)
        - Three authors: First letter of each last name + year (BDE24)
        - Four+ authors: First 3 initials + '+' + year (OTT+24)

        Duplicates get letter suffixes (a, b, c, ...)
        """
        base_label = ""

        if entry.author:
            name_parser = NameParser()
            # Split authors
            authors = re.split(r"\s+and\s+", entry.author, flags=re.IGNORECASE)

            if len(authors) == 1:
                # Single author: first 3 letters of last name
                parsed = name_parser.parse(authors[0])
                if parsed.last:
                    # Use the main last name part
                    last_name = " ".join(parsed.last)
                    if last_name:
                        # Take first 3 characters, capitalize first
                        base_label = last_name[:3].capitalize()
                        # Ensure exactly 3 characters
                        if len(base_label) < 3:
                            base_label = base_label.ljust(
                                3, base_label[-1] if base_label else "X"
                            )

            elif len(authors) <= 3:
                # 2-3 authors: first letter of each last name
                initials = []
                for author in authors:
                    parsed = name_parser.parse(author)
                    if parsed.last:
                        last_name = " ".join(parsed.last)
                        if last_name:
                            initials.append(last_name[0].upper())
                base_label = "".join(initials)

            else:
                # 4+ authors: first 3 initials + '+'
                initials = []
                for author in authors[:3]:
                    parsed = name_parser.parse(author)
                    if parsed.last:
                        last_name = " ".join(parsed.last)
                        if last_name:
                            initials.append(last_name[0].upper())
                base_label = "".join(initials) + "+"

        elif entry.editor:
            # Use "Ed" for editor-only entries
            base_label = "Ed"

        else:
            # Use first 3 letters of key, uppercase
            base_label = entry.key[:3].upper()
            if len(base_label) < 3:
                # Pad with last character if too short
                base_label = base_label.ljust(3, base_label[-1] if base_label else "X")

        # Add year (last 2 digits)
        if entry.year:
            year_str = str(entry.year)[-2:]
        else:
            year_str = "??"

        # Combine base and year
        label = base_label + year_str

        # Handle duplicates by adding suffix
        if label in self.alpha_counts:
            # This is a duplicate
            self.alpha_counts[label] += 1
            # Add letter suffix (a, b, c, ...)
            # First duplicate gets 'a', second gets 'b', etc.
            suffix = chr(ord("a") + self.alpha_counts[label] - 2)
            label = f"{label}{suffix}"
        else:
            # First occurrence - no suffix needed
            self.alpha_counts[label] = 1

        return label
