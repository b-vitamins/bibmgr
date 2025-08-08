"""Citation style formatting with CSL support."""

from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from bibmgr.core.models import Entry, EntryType


@dataclass
class StyleOptions:
    """Configuration options for citation styles."""

    # Et al. rules
    et_al_min: int = 3
    et_al_use_first: int = 1

    # Formatting
    use_italics: bool = True
    use_quotes: bool = False
    include_doi: bool = True
    include_url: bool = False

    # Separators
    name_delimiter: str = ", "
    and_separator: str = "&"

    # Page formatting
    page_prefix: str = "pp."
    page_separator: str = "–"  # en-dash

    # Date formatting
    date_format: str = "year"  # year, month-year, full

    # Title formatting
    title_case: str = "sentence"  # sentence, title, preserve
    preserve_acronyms: bool = True

    def __post_init__(self):
        """Validate options."""
        if self.et_al_use_first > self.et_al_min:
            raise ValueError("et_al_use_first must be <= et_al_min")

    def merge(self, other: StyleOptions) -> StyleOptions:
        """Merge with another options object, other takes precedence."""
        merged_dict = {**self.__dict__, **other.__dict__}
        return StyleOptions(**merged_dict)


class CitationStyle(Protocol):
    """Protocol for citation styles."""

    def format_inline(self, entry: Entry, **kwargs) -> str:
        """Format inline citation."""
        ...

    def format_bibliography(self, entry: Entry, **kwargs) -> str:
        """Format bibliography entry."""
        ...

    def sort_entries(self, entries: list[Entry]) -> list[Entry]:
        """Sort entries for bibliography."""
        ...


class AuthorFormatter:
    """Formats author names according to style rules."""

    def __init__(self, transliterate: bool = False):
        """Initialize formatter."""
        self.transliterate = transliterate

    def format(
        self,
        author: str,
        format: str = "last-first",
        initialize: bool = True,
    ) -> str:
        """Format a single author name.

        Args:
            author: Author name string
            format: Format style (last-first, first-last, last-only, full)
            initialize: Whether to use initials

        Returns:
            Formatted author name
        """
        # Handle organization authors
        if author.startswith("{") and author.endswith("}"):
            return author[1:-1]

        # Apply transliteration if requested
        if self.transliterate:
            author = self._transliterate(author)

        # Parse name components
        if "," in author:
            # "Last, First Middle" format
            parts = author.split(",", 1)
            last = parts[0].strip()
            first_middle = parts[1].strip() if len(parts) > 1 else ""

            # Check for suffix
            suffix = ""
            for suf in ["Jr.", "Sr.", "III", "IV", "II"]:
                if first_middle.endswith(f", {suf}") or first_middle.endswith(
                    f" {suf}"
                ):
                    suffix = suf
                    first_middle = first_middle.replace(f", {suf}", "").replace(
                        f" {suf}", ""
                    )
                    break
        else:
            # "First Middle Last" format
            parts = author.strip().split()
            if not parts:
                return author

            # Check for suffix
            suffix = ""
            if parts[-1] in ["Jr.", "Sr.", "III", "IV", "II", "Jr", "Sr"]:
                suffix = parts[-1]
                if not suffix.endswith(".") and suffix in ["Jr", "Sr"]:
                    suffix += "."
                parts = parts[:-1]

            last = parts[-1] if parts else ""
            first_middle = " ".join(parts[:-1]) if len(parts) > 1 else ""

        # Apply transliteration if needed
        if self.transliterate:
            last = self._transliterate(last)
            first_middle = self._transliterate(first_middle)

        # Format according to style
        match format:
            case "last-first":
                if initialize and first_middle:
                    initials = self._get_initials(first_middle)
                    result = f"{last}, {initials}"
                elif first_middle:
                    result = f"{last}, {first_middle}"
                else:
                    result = last
                if suffix:
                    result += f", {suffix}"
                return result

            case "first-last":
                if initialize and first_middle:
                    initials = self._get_initials(first_middle)
                    result = f"{initials} {last}"
                elif first_middle:
                    result = f"{first_middle} {last}"
                else:
                    result = last
                if suffix:
                    result += f", {suffix}"
                return result

            case "last-only":
                return last

            case "full":
                if first_middle:
                    result = f"{last}, {first_middle}"
                else:
                    result = last
                if suffix:
                    result += f", {suffix}"
                return result

            case _:
                return author

    def format_multiple(
        self,
        authors: list[str],
        format: str = "last-first",
        and_sep: str = "&",
        delimiter: str = ", ",
        et_al_min: int = 99,
        et_al_use_first: int = 1,
    ) -> str:
        """Format multiple authors."""
        if not authors:
            return ""

        # Apply et al. rules
        if len(authors) >= et_al_min:
            shown = authors[:et_al_use_first]
            formatted = [self.format(a, format) for a in shown]
            result = delimiter.join(formatted)
            return f"{result} et al."

        # Format all authors
        formatted = [self.format(a, format) for a in authors]

        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            # For APA style, need comma before ampersand
            if delimiter == ", " and and_sep == "&":
                return f"{formatted[0]}, {and_sep} {formatted[1]}"
            else:
                return f"{formatted[0]} {and_sep} {formatted[1]}"
        else:
            # Oxford comma before 'and'
            return (
                f"{delimiter.join(formatted[:-1])}{delimiter}{and_sep} {formatted[-1]}"
            )

    def _get_initials(self, name: str) -> str:
        """Get initials from name."""
        # Check if this is a CJK name (Chinese, Japanese, Korean)
        is_cjk = any(
            "\u4e00" <= c <= "\u9fff"  # CJK Unified Ideographs
            or "\u3400" <= c <= "\u4dbf"  # CJK Extension A
            or "\uac00" <= c <= "\ud7af"  # Hangul Syllables
            or "\u3040" <= c <= "\u309f"  # Hiragana
            or "\u30a0" <= c <= "\u30ff"  # Katakana
            for c in name
        )

        if is_cjk:
            # For CJK names, return the full given name without periods
            return name

        # Handle hyphenated names
        parts = name.replace("-", " - ").split()
        initials = []

        for part in parts:
            if part == "-":
                initials.append("-")
            elif part:
                initial = part[0].upper()
                initials.append(f"{initial}.")

        # Clean up hyphens
        result = " ".join(initials)
        result = result.replace(" - ", "-")
        return result

    def _transliterate(self, text: str) -> str:
        """Transliterate Unicode to ASCII."""
        if not text:
            return text

        # First apply German and special character replacements
        replacements = {
            "ä": "ae",
            "ö": "oe",
            "ü": "ue",
            "Ä": "Ae",
            "Ö": "Oe",
            "Ü": "Ue",
            "ß": "ss",
            "æ": "ae",
            "ø": "o",
        }

        result = text
        for old, new in replacements.items():
            result = result.replace(old, new)

        # Then normalize and remove remaining accents
        nfd = unicodedata.normalize("NFD", result)
        ascii_text = "".join(char for char in nfd if unicodedata.category(char) != "Mn")

        return ascii_text


def format_ordinal(number: int | str) -> str:
    """Format number as ordinal (1st, 2nd, 3rd, etc.)."""
    try:
        n = int(str(number))
    except (ValueError, TypeError):
        # Not a number, return as-is
        return str(number)

    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")

    return f"{n}{suffix}"


class DateFormatter:
    """Formats dates according to style rules."""

    MONTHS = {
        "1": "January",
        "2": "February",
        "3": "March",
        "4": "April",
        "5": "May",
        "6": "June",
        "7": "July",
        "8": "August",
        "9": "September",
        "10": "October",
        "11": "November",
        "12": "December",
    }

    MONTHS_ABBR = {
        "1": "Jan.",
        "2": "Feb.",
        "3": "Mar.",
        "4": "Apr.",
        "5": "May",
        "6": "Jun.",
        "7": "Jul.",
        "8": "Aug.",
        "9": "Sep.",
        "10": "Oct.",
        "11": "Nov.",
        "12": "Dec.",
    }

    # Map month abbreviations to full names
    MONTH_ABBR_TO_FULL = {
        "jan": "January",
        "feb": "February",
        "mar": "March",
        "apr": "April",
        "may": "May",
        "jun": "June",
        "jul": "July",
        "aug": "August",
        "sep": "September",
        "oct": "October",
        "nov": "November",
        "dec": "December",
        # With periods
        "jan.": "January",
        "feb.": "February",
        "mar.": "March",
        "apr.": "April",
        "may.": "May",
        "jun.": "June",
        "jul.": "July",
        "aug.": "August",
        "sep.": "September",
        "oct.": "October",
        "nov.": "November",
        "dec.": "December",
    }

    # Map full names to abbreviations
    MONTH_FULL_TO_ABBR = {
        "january": "Jan.",
        "february": "Feb.",
        "march": "Mar.",
        "april": "Apr.",
        "may": "May",
        "june": "Jun.",
        "july": "Jul.",
        "august": "Aug.",
        "september": "Sep.",
        "october": "Oct.",
        "november": "Nov.",
        "december": "Dec.",
    }

    def format_year(self, entry: Entry, no_date: str = "n.d.") -> str:
        """Format year."""
        if entry.year:
            return str(entry.year)
        return no_date

    def format_month(
        self,
        month: str,
        abbreviate: bool = False,
    ) -> str:
        """Format month name."""
        if not month:
            return ""

        month_lower = month.lower().strip()

        # Check if it's a month abbreviation
        if month_lower in self.MONTH_ABBR_TO_FULL:
            full_name = self.MONTH_ABBR_TO_FULL[month_lower]
            if abbreviate:
                return self.MONTH_FULL_TO_ABBR[full_name.lower()]
            return full_name

        # Check if it's already a full month name
        if month_lower in self.MONTH_FULL_TO_ABBR:
            if abbreviate:
                return self.MONTH_FULL_TO_ABBR[month_lower]
            return month.capitalize()

        # Check if it's a numeric month
        if month_lower in self.MONTHS:
            if abbreviate:
                return self.MONTHS_ABBR[month_lower]
            return self.MONTHS[month_lower]

        # Default: return as-is
        return month

    def format_date(
        self,
        entry: Entry,
        format: str = "default",
    ) -> str:
        """Format complete date."""
        if not entry.year:
            return "n.d."

        year = str(entry.year)
        month = (
            self.format_month(entry.month)
            if hasattr(entry, "month") and entry.month
            else ""
        )
        day = (
            str(getattr(entry, "day", ""))
            if hasattr(entry, "day") and getattr(entry, "day", None)
            else ""
        )

        match format:
            case "iso":
                # YYYY-MM-DD
                if month:
                    month_num = entry.month if hasattr(entry, "month") else "01"
                    day_num = (
                        getattr(entry, "day", "01")
                        if hasattr(entry, "day") and getattr(entry, "day", None)
                        else "01"
                    )
                    return f"{year}-{month_num:0>2}-{day_num:0>2}"
                return year

            case "full":
                # Month DD, YYYY
                if month and day:
                    return f"{month} {day}, {year}"
                elif month:
                    return f"{month} {year}"
                return year

            case _:
                # Check if it's a custom format string
                if "{" in format and "}" in format:
                    # Custom format string like "{day} {month} {year}"
                    result = format
                    result = result.replace("{year}", year)
                    result = result.replace("{month}", month if month else "")
                    result = result.replace("{day}", day if day else "")
                    return result.strip()

                # Default format
                if month and day:
                    return f"{month} {day}, {year}"
                elif month:
                    return f"{month} {year}"
                return year

    def format_range(
        self,
        start: str,
        end: str,
        year: str | None = None,
    ) -> str:
        """Format date range."""
        if year:
            return f"{start}–{end} {year}"
        return f"{start}–{end}"


class TitleFormatter:
    """Formats titles according to style rules."""

    # Common acronyms to preserve
    ACRONYMS = {
        "NASA",
        "IEEE",
        "ACM",
        "MIT",
        "IBM",
        "XML",
        "HTML",
        "CSS",
        "API",
        "SQL",
        "JSON",
        "URL",
        "URI",
        "DOI",
        "DNA",
        "RNA",
        "ATP",
        "GDP",
        "USA",
        "UK",
        "EU",
        "WHO",
        "UN",
        "NATO",
        "UNESCO",
        "UNICEF",
    }

    # Words not to capitalize in title case
    LOWERCASE_WORDS = {
        "a",
        "an",
        "and",
        "as",
        "at",
        "but",
        "by",
        "for",
        "from",
        "in",
        "nor",
        "of",
        "on",
        "or",
        "so",
        "the",
        "to",
        "up",
        "with",
        "yet",
    }

    def format(
        self,
        title: str,
        case: str = "preserve",
        quotes: bool = False,
        italics: bool = False,
        strip_latex: bool = True,
        preserve_acronyms: bool = True,
    ) -> str:
        """Format title according to style rules."""
        if not title:
            return ""

        # Strip LaTeX commands if requested
        if strip_latex:
            title = self._strip_latex(title)

        # Apply case transformation
        title = self._apply_case(title, case, preserve_acronyms)

        # Add quotes or italics
        if quotes:
            title = f'"{title}"'
        elif italics:
            title = f"*{title}*"

        return title

    def _strip_latex(self, text: str) -> str:
        """Remove LaTeX commands from text."""
        # Remove commands with arguments
        text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
        # Remove standalone commands
        text = re.sub(r"\\[a-zA-Z]+", "", text)
        # Remove math mode
        text = re.sub(r"\$[^$]*\$", "", text)
        return text

    def _apply_case(
        self,
        title: str,
        case: str,
        preserve_acronyms: bool,
    ) -> str:
        """Apply case transformation."""
        if not title:
            return ""
        match case:
            case "sentence":
                # First word capitalized, rest lowercase
                if preserve_acronyms:
                    words = title.split()
                    if words:
                        result = []
                        for i, word in enumerate(words):
                            # Check if word is an acronym (case-insensitive)
                            if word.upper() in self.ACRONYMS:
                                result.append(word.upper())
                            elif i == 0:
                                result.append(word.capitalize())
                            else:
                                result.append(word.lower())
                        return " ".join(result)
                else:
                    return title[0].upper() + title[1:].lower() if title else ""

            case "title":
                # Title case with smart capitalization
                words = title.split()
                result = []

                for i, word in enumerate(words):
                    # Preserve acronyms
                    if preserve_acronyms and word.upper() in self.ACRONYMS:
                        result.append(word.upper())
                    # Don't capitalize small words (except first/last)
                    elif i == 0 or i == len(words) - 1:
                        result.append(word.capitalize())
                    elif word.lower() in self.LOWERCASE_WORDS:
                        result.append(word.lower())
                    else:
                        result.append(word.capitalize())

                return " ".join(result)

            case "upper":
                return title.upper()

            case "lower":
                return title.lower()

            case "preserve" | _:
                return title

        # Should never reach here but pyright needs explicit return
        return title


class BaseStyle:
    """Base class for citation styles."""

    def __init__(self, options: StyleOptions | None = None):
        """Initialize style with options."""
        self.options = options or self._get_default_options()
        self.author_formatter = AuthorFormatter()
        self.date_formatter = DateFormatter()
        self.title_formatter = TitleFormatter()
        self._number_map: dict[str, int] = {}

    def _get_default_options(self) -> StyleOptions:
        """Get default options for this style."""
        return StyleOptions()

    def format_inline(
        self,
        entry: Entry,
        disambiguate: str | None = None,
        **kwargs,
    ) -> str:
        """Format inline citation."""
        raise NotImplementedError

    def format_bibliography(
        self,
        entry: Entry,
        number: int | None = None,
        **kwargs,
    ) -> str:
        """Format bibliography entry."""
        raise NotImplementedError

    def sort_entries(self, entries: list[Entry]) -> list[Entry]:
        """Sort entries for bibliography."""
        return sorted(entries, key=self._get_sort_key)

    def _get_sort_key(self, entry: Entry) -> tuple:
        """Get sort key for entry."""
        # Default: author, year, title
        author = self._get_first_author_last(entry)
        year = entry.year or 9999
        title = entry.title or ""
        return (author.lower(), year, title.lower())

    def _get_first_author_last(self, entry: Entry) -> str:
        """Get first author's last name."""
        if not entry.author:
            return "zzz"

        authors = entry.authors_list
        if not authors:
            return "zzz"

        return self.author_formatter.format(authors[0], "last-only")

    def _format_pages(self, pages: str | None) -> str:
        """Format page range."""
        if not pages:
            return ""

        # Handle different separators
        pages = pages.replace("--", "–")
        pages = pages.replace("-", "–")

        if self.options.page_prefix:
            return f"{self.options.page_prefix} {pages}"
        else:
            return pages

    def _format_doi(self, doi: str | None) -> str:
        """Format DOI."""
        if not doi or not self.options.include_doi:
            return ""

        if not doi.startswith("http"):
            doi = f"https://doi.org/{doi}"

        return doi

    def _format_url(self, url: str | None) -> str:
        """Format URL."""
        if not url or not self.options.include_url:
            return ""

        return url


class APAStyle(BaseStyle):
    """APA (American Psychological Association) citation style."""

    def _get_default_options(self) -> StyleOptions:
        """APA default options."""
        return StyleOptions(
            et_al_min=3,
            et_al_use_first=1,
            and_separator="&",
            title_case="sentence",
            include_doi=True,
            page_prefix="",
        )

    def format_inline(
        self,
        entry: Entry,
        disambiguate: str | None = None,
        **kwargs,
    ) -> str:
        """Format APA inline citation."""
        # Format authors
        if not entry.author:
            authors = "Anonymous"
        else:
            author_list = entry.authors_list
            if len(author_list) == 1:
                authors = self.author_formatter.format(author_list[0], "last-only")
            elif len(author_list) == 2:
                a1 = self.author_formatter.format(author_list[0], "last-only")
                a2 = self.author_formatter.format(author_list[1], "last-only")
                authors = f"{a1} & {a2}"
            else:
                # 3+ authors
                if len(author_list) > self.options.et_al_min:
                    first = self.author_formatter.format(author_list[0], "last-only")
                    authors = f"{first} et al."
                else:
                    # List all
                    formatted = [
                        self.author_formatter.format(a, "last-only")
                        for a in author_list[:-1]
                    ]
                    last = self.author_formatter.format(author_list[-1], "last-only")
                    authors = f"{', '.join(formatted)}, & {last}"

        # Format year
        year = self.date_formatter.format_year(entry)
        if disambiguate:
            year += disambiguate

        return f"({authors}, {year})"

    def format_bibliography(
        self,
        entry: Entry,
        number: int | None = None,
        **kwargs,
    ) -> str:
        """Format APA bibliography entry."""
        parts = []

        # Authors
        if entry.author:
            authors = self.author_formatter.format_multiple(
                entry.authors_list,
                format="last-first",
                and_sep="&",
                et_al_min=self.options.et_al_min,
                et_al_use_first=self.options.et_al_use_first,
            )
            parts.append(authors)
        else:
            parts.append("Anonymous")

        # Year (with month for conference papers)
        if (
            entry.type in [EntryType.INPROCEEDINGS, EntryType.CONFERENCE]
            and entry.month
        ):
            month = self.date_formatter.format_month(entry.month)
            year = f"({self.date_formatter.format_year(entry)}, {month})"
        else:
            year = f"({self.date_formatter.format_year(entry)})"
        parts.append(year)

        # Title
        if entry.title:
            title = self.title_formatter.format(
                entry.title,
                case="sentence",
                italics=(entry.type == EntryType.BOOK),
            )
            parts.append(title)

        # Type-specific formatting
        match entry.type:
            case EntryType.ARTICLE:
                if entry.journal:
                    journal = f"*{entry.journal}*"
                    parts.append(journal)

                if entry.volume:
                    vol = str(entry.volume)
                    if entry.number:
                        vol += f"({entry.number})"
                    parts.append(vol)

                if entry.pages:
                    parts.append(entry.pages)

            case EntryType.BOOK:
                if entry.edition:
                    parts.append(f"({format_ordinal(entry.edition)} ed.)")

                if entry.publisher:
                    location = f"{entry.address}: " if entry.address else ""
                    parts.append(f"{location}{entry.publisher}")

            case EntryType.INPROCEEDINGS | EntryType.CONFERENCE:
                if entry.booktitle:
                    parts.append(f"In *{entry.booktitle}*")

                if entry.pages:
                    parts.append(f"(pp. {entry.pages})")

                if entry.publisher or entry.address:
                    location = f"{entry.address}: " if entry.address else ""
                    publisher = entry.publisher or ""
                    parts.append(f"{location}{publisher}".strip())

        # DOI
        doi = self._format_doi(entry.doi)
        if doi:
            parts.append(doi)

        # Join parts with smart period handling
        result = ""
        for i, part in enumerate(parts):
            if i > 0:
                # Add separator, but avoid double periods
                if result.endswith(".") and not result.endswith(".."):
                    result += " "
                else:
                    result += ". "
            result += part

        if not result.endswith("."):
            result += "."

        return result


class MLAStyle(BaseStyle):
    """MLA (Modern Language Association) citation style."""

    def _get_default_options(self) -> StyleOptions:
        """MLA default options."""
        return StyleOptions(
            et_al_min=3,
            et_al_use_first=1,
            and_separator="and",
            title_case="title",
            use_quotes=True,
            include_url=True,
            page_prefix="pp.",
        )

    def format_inline(
        self,
        entry: Entry,
        disambiguate: str | None = None,
        **kwargs,
    ) -> str:
        """Format MLA inline citation (author only)."""
        if not entry.author:
            return "(Anonymous)"

        author_list = entry.authors_list
        if len(author_list) > self.options.et_al_min:
            first = self.author_formatter.format(author_list[0], "last-only")
            return f"({first} et al.)"
        else:
            first = self.author_formatter.format(author_list[0], "last-only")
            return f"({first})"

    def format_bibliography(
        self,
        entry: Entry,
        number: int | None = None,
        **kwargs,
    ) -> str:
        """Format MLA bibliography entry."""
        parts = []

        # Authors (special MLA format for multiple authors)
        if entry.author:
            authors = entry.authors_list
            if len(authors) == 1:
                author_str = self.author_formatter.format(authors[0], "last-first")
                # Add period if not already present
                if not author_str.endswith("."):
                    author_str += "."
                parts.append(author_str)
            elif len(authors) == 2:
                first = self.author_formatter.format(authors[0], "last-first")
                second = self.author_formatter.format(authors[1], "first-last")
                parts.append(f"{first}, and {second}.")
            else:
                # 3+ authors
                if len(authors) > self.options.et_al_min:
                    first = self.author_formatter.format(authors[0], "last-first")
                    parts.append(f"{first}, et al.")
                else:
                    first = self.author_formatter.format(authors[0], "last-first")
                    parts.append(f"{first}, et al.")

        # Title
        if entry.title:
            if entry.type == EntryType.ARTICLE:
                title = f'"{entry.title}."'
            else:
                title = f"*{entry.title}*."
            parts.append(title)

        # Container (journal, book, etc.)
        match entry.type:
            case EntryType.ARTICLE:
                if entry.journal:
                    parts.append(f"*{entry.journal}*,")

                if entry.volume:
                    vol = f"vol. {entry.volume},"
                    if entry.number:
                        vol += f" no. {entry.number},"
                    parts.append(vol)

                if entry.year:
                    parts.append(f"{entry.year},")

                if entry.pages:
                    pages = self._format_pages(entry.pages)
                    parts.append(f"{pages}.")

            case EntryType.BOOK:
                if entry.edition:
                    parts.append(f"{format_ordinal(entry.edition)} ed.,")

                if entry.publisher:
                    parts.append(f"{entry.publisher},")

                if entry.year:
                    parts.append(f"{entry.year}.")

        return " ".join(parts)


class ChicagoStyle(BaseStyle):
    """Chicago Manual of Style citation format."""

    def __init__(
        self, options: StyleOptions | None = None, notes_bibliography: bool = False
    ):
        """Initialize Chicago style."""
        super().__init__(options)
        self.notes_bibliography = notes_bibliography

    def _get_default_options(self) -> StyleOptions:
        """Chicago default options."""
        return StyleOptions(
            et_al_min=3,
            et_al_use_first=1,
            and_separator="and",
            title_case="title",
            use_quotes=True,
            include_doi=True,
        )

    def format_inline(
        self,
        entry: Entry,
        disambiguate: str | None = None,
        **kwargs,
    ) -> str:
        """Format Chicago inline citation (author-date style)."""
        if not entry.author:
            authors = "Anonymous"
        else:
            author_list = entry.authors_list
            if len(author_list) > self.options.et_al_min:
                first = self.author_formatter.format(author_list[0], "last-only")
                authors = f"{first} et al."
            else:
                first = self.author_formatter.format(author_list[0], "last-only")
                authors = first

        year = self.date_formatter.format_year(entry)
        if disambiguate:
            year += disambiguate

        return f"({authors} {year})"

    def format_bibliography(
        self,
        entry: Entry,
        number: int | None = None,
        **kwargs,
    ) -> str:
        """Format Chicago bibliography entry."""
        parts = []

        # Authors
        if entry.author:
            authors = self.author_formatter.format_multiple(
                entry.authors_list,
                format="last-first",
                and_sep="and",
                et_al_min=self.options.et_al_min,
            )
            # Add period if not already present
            if not authors.endswith("."):
                authors += "."
            parts.append(authors)

        # Title
        if entry.title:
            if entry.type == EntryType.ARTICLE:
                title = f'"{entry.title}."'
            else:
                title = f"*{entry.title}*."
            parts.append(title)

        # Type-specific
        match entry.type:
            case EntryType.ARTICLE:
                if entry.journal:
                    journal = f"*{entry.journal}*"
                    if entry.volume:
                        journal += f" {entry.volume}"
                        if entry.number:
                            journal += f", no. {entry.number}"
                    if entry.year:
                        journal += f" ({entry.year})"
                    if entry.pages:
                        # Format pages with en-dash
                        pages = entry.pages.replace("--", "–").replace("-", "–")
                        journal += f": {pages}"
                    parts.append(journal)

            case EntryType.BOOK:
                pub_info = []
                if entry.address:
                    pub_info.append(entry.address)
                if entry.publisher:
                    pub_info.append(entry.publisher)
                if entry.year:
                    pub_info.append(str(entry.year))

                if pub_info:
                    parts.append(": ".join(pub_info) + ".")

        # DOI
        doi = self._format_doi(entry.doi)
        if doi:
            parts.append(doi)

        return " ".join(parts)

    def format_footnote(self, entry: Entry, page: str | None = None) -> str:
        """Format Chicago footnote citation."""
        # Similar to bibliography but more compact
        result = self.format_bibliography(entry)

        if page:
            # Add specific page reference
            result = result.rstrip(".")
            result += f", {page}."

        return result


class IEEEStyle(BaseStyle):
    """IEEE citation style."""

    def _get_default_options(self) -> StyleOptions:
        """IEEE default options."""
        return StyleOptions(
            et_al_min=6,
            et_al_use_first=6,
            and_separator=",",  # IEEE uses commas between all authors
            title_case="preserve",
            use_quotes=True,
            page_prefix="pp.",
        )

    def assign_numbers(self, entries: list[Entry]) -> None:
        """Assign numbers to entries for IEEE style."""
        for i, entry in enumerate(entries, 1):
            self._number_map[entry.key] = i

    def format_inline(
        self,
        entry: Entry,
        disambiguate: str | None = None,
        **kwargs,
    ) -> str:
        """Format IEEE inline citation (numbered)."""
        if entry.key in self._number_map:
            return f"[{self._number_map[entry.key]}]"
        return "[?]"

    def format_bibliography(
        self,
        entry: Entry,
        number: int | None = None,
        **kwargs,
    ) -> str:
        """Format IEEE bibliography entry."""
        parts = []

        # Number
        if number:
            parts.append(f"[{number}]")

        # Authors (IEEE format: initials first)
        if entry.author:
            authors = []
            for author in entry.authors_list[:6]:  # IEEE shows up to 6
                formatted = self.author_formatter.format(
                    author, "first-last", initialize=True
                )
                authors.append(formatted)

            if len(entry.authors_list) > 6:
                authors.append("et al.")

            parts.append(", ".join(authors) + ",")

        # Title
        if entry.title:
            parts.append(f'"{entry.title},"')

        # Type-specific
        match entry.type:
            case EntryType.ARTICLE:
                if entry.journal:
                    parts.append(f"*{entry.journal}*,")

                if entry.volume:
                    vol = f"vol. {entry.volume},"
                    if entry.number:
                        vol = f"vol. {entry.volume}, no. {entry.number},"
                    parts.append(vol)

                if entry.pages:
                    pages = self._format_pages(entry.pages)
                    parts.append(f"{pages},")

                if entry.month and entry.year:
                    month = self.date_formatter.format_month(
                        entry.month, abbreviate=True
                    )
                    parts.append(f"{month} {entry.year}.")
                elif entry.year:
                    parts.append(f"{entry.year}.")

            case EntryType.INPROCEEDINGS | EntryType.CONFERENCE:
                if entry.booktitle:
                    # Abbreviate common IEEE conference terms
                    booktitle = entry.booktitle
                    booktitle = booktitle.replace("Proceedings of the", "Proc.")
                    booktitle = booktitle.replace("Proceedings of", "Proc.")
                    booktitle = booktitle.replace("Proceedings", "Proc.")
                    booktitle = booktitle.replace("Conference", "Conf.")
                    booktitle = booktitle.replace("International", "Int.")
                    parts.append(f"in *{booktitle}*,")

                if entry.address:
                    parts.append(f"{entry.address},")

                if entry.year:
                    parts.append(f"{entry.year},")

                if entry.pages:
                    pages = self._format_pages(entry.pages)
                    parts.append(f"{pages}.")

            case EntryType.BOOK:
                if entry.address:
                    parts.append(f"{entry.address}:")

                if entry.publisher:
                    parts.append(f"{entry.publisher},")

                if entry.year:
                    parts.append(f"{entry.year}.")

        return " ".join(parts)

    def sort_entries(self, entries: list[Entry]) -> list[Entry]:
        """IEEE doesn't sort - uses appearance order."""
        return entries  # Keep original order


class CSLStyle:
    """Citation style from CSL (Citation Style Language) definition."""

    def __init__(self, csl_data: dict):
        """Initialize from CSL data."""
        self.csl = csl_data
        self._validate_csl()

        self.info = self.csl.get("info", {})
        self.citation = self.csl.get("citation", {})
        self.bibliography = self.csl.get("bibliography", {})

        # Create formatters
        self.author_formatter = AuthorFormatter()
        self.date_formatter = DateFormatter()
        self.title_formatter = TitleFormatter()

    def _validate_csl(self):
        """Validate CSL definition."""
        if "info" not in self.csl:
            raise ValueError("Invalid CSL: missing 'info' section")
        if "id" not in self.csl["info"]:
            raise ValueError("Invalid CSL: missing style ID")

    @classmethod
    def from_file(cls, path: Path | str) -> CSLStyle:
        """Load CSL from file."""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            csl_data = json.load(f)
        return cls(csl_data)

    def format_inline(self, entry: Entry, **kwargs) -> str:
        """Format inline citation from CSL rules."""
        layout = self.citation.get("layout", {})
        prefix = layout.get("prefix", "(")
        suffix = layout.get("suffix", ")")
        layout.get("delimiter", ", ")

        # Format author
        author_rules = self.citation.get("author", {})
        if entry.author:
            authors = entry.authors_list
            et_al_min = author_rules.get("et-al-min", 3)
            et_al_use = author_rules.get("et-al-use-first", 1)

            if len(authors) > et_al_min:
                shown = authors[:et_al_use]
                author_text = self.author_formatter.format(shown[0], "last-only")
                author_text += " et al."
            else:
                author_text = self.author_formatter.format(authors[0], "last-only")
        else:
            author_text = "Anonymous"

        # Format year
        year_rules = self.citation.get("year", {})
        year_prefix = year_rules.get("prefix", " ")
        year_text = self.date_formatter.format_year(entry)

        return f"{prefix}{author_text}{year_prefix}{year_text}{suffix}"

    def format_bibliography(self, entry: Entry, **kwargs) -> str:
        """Format bibliography from CSL rules."""
        parts = []

        # Author
        if entry.author:
            author_rules = self.bibliography.get("author", {})
            form = author_rules.get("form", "long")
            and_sep = author_rules.get("and", "&")
            delimiter = author_rules.get("delimiter", ", ")

            format_style = "last-first" if form == "long" else "last-only"
            authors = self.author_formatter.format_multiple(
                entry.authors_list,
                format=format_style,
                and_sep=and_sep,
                delimiter=delimiter,
            )
            parts.append(authors)

        # Year
        year_rules = self.bibliography.get("year", {})
        year_prefix = year_rules.get("prefix", " ")
        year_suffix = year_rules.get("suffix", "")
        year = f"{year_prefix}{self.date_formatter.format_year(entry)}{year_suffix}"
        parts.append(year)

        # Title
        if entry.title:
            title_rules = self.bibliography.get("title", {})
            case = title_rules.get("text-case", "preserve")
            quotes = title_rules.get("quotes", False)
            italics = title_rules.get("font-style") == "italic"

            title = self.title_formatter.format(
                entry.title,
                case=case,
                quotes=quotes,
                italics=italics,
            )
            parts.append(title)

        # Container (journal, book, etc.)
        if entry.journal:
            container_rules = self.bibliography.get("container-title", {})
            italics = container_rules.get("font-style") == "italic"

            journal = f"*{entry.journal}*" if italics else entry.journal
            parts.append(journal)

        # Layout
        layout = self.bibliography.get("layout", {})
        suffix = layout.get("suffix", ".")

        result = " ".join(parts)
        if not result.endswith(suffix):
            result += suffix

        return result

    def sort_entries(self, entries: list[Entry]) -> list[Entry]:
        """Sort entries according to CSL rules."""
        sort_rules = self.bibliography.get("sort", {})
        sort_rules.get("key", "author year title")

        # Simple implementation - could be enhanced
        return sorted(
            entries,
            key=lambda e: (
                e.author or "zzz",
                e.year or 9999,
                e.title or "",
            ),
        )


class StyleRegistry:
    """Registry of available citation styles."""

    def __init__(self):
        """Initialize with built-in styles."""
        self._styles: dict[str, type[CitationStyle] | CitationStyle] = {
            "apa": APAStyle,
            "mla": MLAStyle,
            "chicago": ChicagoStyle,
            "ieee": IEEEStyle,
        }

        # Aliases
        self._aliases = {
            "apa7": "apa",
            "mla8": "mla",
            "mla9": "mla",
            "chicago17": "chicago",
        }

    def __contains__(self, name: str) -> bool:
        """Check if style is registered."""
        name = name.lower()
        return name in self._styles or name in self._aliases

    def get(self, name: str) -> CitationStyle:
        """Get style by name."""
        name = name.lower()

        # Check aliases
        if name in self._aliases:
            name = self._aliases[name]

        if name not in self._styles:
            raise ValueError(f"Unknown citation style: {name}")

        style_class = self._styles[name]
        if isinstance(style_class, type):
            return style_class()
        return style_class

    def register(self, name: str, style: CitationStyle | type[CitationStyle]) -> None:
        """Register custom style."""
        self._styles[name.lower()] = style

    def load_csl_directory(self, path: Path | str) -> None:
        """Load all CSL files from directory."""
        path = Path(path)
        for csl_file in path.glob("*.csl"):
            try:
                style = CSLStyle.from_file(csl_file)
                name = style.info.get("id", csl_file.stem)
                self.register(name, style)
            except Exception:
                continue  # Skip invalid files

    def list_styles(self, detailed: bool = False) -> list[str] | list[dict]:
        """List available styles."""
        if detailed:
            result = []
            for name in self._styles:
                style = self.get(name)
                info = {
                    "id": name,
                    "name": name.upper(),
                    "type": type(style).__name__,
                }
                result.append(info)
            return result
        else:
            return list(self._styles.keys())


class FormattingCache:
    """Cache for formatted citations."""

    def __init__(
        self,
        max_size: int = 1000,
        ttl: float = 3600,  # 1 hour
    ):
        """Initialize cache."""
        self.max_size = max_size
        self.ttl = ttl
        self._cache: dict[str, tuple[str, float]] = {}
        self._hits = 0
        self._misses = 0

    def _make_key(
        self,
        entry: Entry,
        style: CitationStyle,
        format_type: str,
    ) -> str:
        """Create cache key."""
        style_name = type(style).__name__
        return f"{entry.key}:{style_name}:{format_type}"

    def get_or_format(
        self,
        entry: Entry,
        style: CitationStyle,
        format_type: str,
        **kwargs,
    ) -> str:
        """Get from cache or format."""
        key = self._make_key(entry, style, format_type)

        # Check cache
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                self._hits += 1
                return value
            else:
                # Expired
                del self._cache[key]

        # Cache miss
        self._misses += 1

        # Format
        if format_type == "inline":
            value = style.format_inline(entry, **kwargs)
        else:
            value = style.format_bibliography(entry, **kwargs)

        # Store in cache
        self._add_to_cache(key, value)

        return value

    def _add_to_cache(self, key: str, value: str) -> None:
        """Add to cache with LRU eviction."""
        if len(self._cache) >= self.max_size:
            # Evict oldest
            oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        self._cache[key] = (value, time.time())

    def invalidate(self, entry_key: str) -> None:
        """Invalidate cache entries for a specific entry."""
        keys_to_remove = [k for k in self._cache if k.startswith(f"{entry_key}:")]
        for key in keys_to_remove:
            del self._cache[key]

    def clear(self) -> None:
        """Clear entire cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0,
            "size": len(self._cache),
        }


class CitationFormatter:
    """Main formatter that manages different citation styles."""

    def __init__(
        self,
        style: CitationStyle | str = "apa",
        cache: FormattingCache | None = None,
    ):
        """Initialize formatter."""
        if isinstance(style, str):
            registry = StyleRegistry()
            style = registry.get(style)

        self.style = style
        self.cache = cache or FormattingCache()

    def format_inline(self, entry: Entry, **kwargs) -> str:
        """Format inline citation."""
        if self.cache:
            return self.cache.get_or_format(entry, self.style, "inline", **kwargs)
        return self.style.format_inline(entry, **kwargs)

    def format_bibliography(self, entry: Entry, **kwargs) -> str:
        """Format bibliography entry."""
        if self.cache:
            return self.cache.get_or_format(entry, self.style, "bibliography", **kwargs)
        return self.style.format_bibliography(entry, **kwargs)

    def format_multiple(self, entries: list[Entry]) -> str:
        """Format multiple citations together."""
        if not entries:
            return ""

        # Sort by author and year
        sorted_entries = self.style.sort_entries(entries)

        # Format each
        citations = []
        for entry in sorted_entries:
            cite = self.format_inline(entry)
            # Remove parentheses for combining
            if cite.startswith("(") and cite.endswith(")"):
                cite = cite[1:-1]
            citations.append(cite)

        # Combine with semicolons
        return f"({'; '.join(citations)})"


# Validation functions
def validate_doi(doi: str) -> bool:
    """Validate DOI format."""
    if not doi:
        return False

    # Remove URL prefix if present
    if doi.startswith("https://doi.org/"):
        doi = doi[16:]
    elif doi.startswith("http://doi.org/"):
        doi = doi[15:]

    # Basic DOI pattern
    pattern = r"^10\.\d{4,}/[-._;()/:\w]+$"
    return bool(re.match(pattern, doi))


def validate_url(url: str) -> bool:
    """Validate URL format."""
    if not url:
        return False

    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def validate_author(author: str) -> bool:
    """Validate author name format."""
    if not author or not author.strip():
        return False

    # Organization author
    if author.startswith("{") and author.endswith("}"):
        return len(author) > 2

    # Must have at least one letter
    if not any(c.isalpha() for c in author):
        return False

    return True
