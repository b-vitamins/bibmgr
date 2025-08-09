"""BibTeX format encoding and decoding.

This module provides classes for converting between Entry objects and
BibTeX format text. The implementation follows standard BibTeX conventions
for field formatting, special character escaping, and entry structure.

Key components:
- BibtexEncoder: Converts Entry objects to BibTeX format
- BibtexDecoder: Parses BibTeX text into Entry dictionaries
"""

import re
from typing import TYPE_CHECKING, Any

from .fields import ALL_FIELDS

if TYPE_CHECKING:
    from .models import Entry


class BibtexEncoder:
    """Encode Entry objects to BibTeX format.

    Handles special character escaping and field ordering to produce
    properly formatted BibTeX entries. Braces are preserved as they
    have semantic meaning in BibTeX (case protection).
    """

    SPECIAL_CHARS = {
        "\\": "\\\\",
        "$": "\\$",
        "&": "\\&",
        "#": "\\#",
        "_": "\\_",
        "%": "\\%",
        "~": "\\~{}",
        "^": "\\^{}",
    }

    FIELD_ORDER = [
        "author",
        "editor",
        "title",
        "booktitle",
        "journal",
        "volume",
        "number",
        "pages",
        "chapter",
        "edition",
        "series",
        "publisher",
        "address",
        "organization",
        "institution",
        "school",
        "year",
        "month",
        "type",
        "note",
        "key",
        "crossref",
        "doi",
        "url",
        "isbn",
        "issn",
        "abstract",
        "keywords",
    ]

    def escape(self, text: str) -> str:
        """Escape special LaTeX characters for BibTeX.

        Args:
            text: Text to escape.

        Returns:
            Text with special characters escaped.
        """
        if not text:
            return text

        result = text
        for char, escaped in self.SPECIAL_CHARS.items():
            result = result.replace(char, escaped)
        return result

    def protect_case(self, text: str) -> str:
        """Wrap text in braces to protect from case changes."""
        return f"{{{text}}}"

    def encode_entry(self, entry: "Entry") -> str:
        """Encode a single entry to BibTeX format.

        Args:
            entry: Entry to encode.

        Returns:
            BibTeX formatted string.
        """
        lines = [f"@{entry.type.value}{{{entry.key},"]

        data = entry.to_dict()

        for field in ["id", "added", "modified", "tags", "type", "key"]:
            data.pop(field, None)

        custom_fields = data.pop("custom", None) or {}

        if "type_" in data:
            data["type"] = data.pop("type_")

        data.update(custom_fields)

        sorted_fields = []
        for field in self.FIELD_ORDER:
            if field in data:
                sorted_fields.append((field, data.pop(field)))

        for field, value in sorted(data.items()):
            sorted_fields.append((field, value))

        for field, value in sorted_fields:
            if value is None:
                continue

            if field == "keywords" and isinstance(value, list | tuple):
                value = ", ".join(value)
            elif field == "year":
                lines.append(f"    {field} = {{{value}}},")
                continue
            elif field == "month":
                if value.isdigit() or value in [
                    "jan",
                    "feb",
                    "mar",
                    "apr",
                    "may",
                    "jun",
                    "jul",
                    "aug",
                    "sep",
                    "oct",
                    "nov",
                    "dec",
                ]:
                    lines.append(f"    {field} = {value},")
                    continue

            escaped_value = self.escape(str(value))
            lines.append(f"    {field} = {{{escaped_value}}},")

        if lines[-1].endswith(","):
            lines[-1] = lines[-1][:-1]

        lines.append("}")
        return "\n".join(lines)


class BibtexDecoder:
    """Parse BibTeX format into Entry dictionaries.

    Handles nested braces, @string definitions, and various field
    value formats (quoted strings, braced values, unquoted values).
    Supports up to 3 levels of brace nesting for complex field values.
    """

    ENTRY_PATTERN = re.compile(
        r"@(\w+)\s*\{([^,]+),\s*((?:[^{}]|{(?:[^{}]|{(?:[^{}]|{(?:[^{}]|{[^{}]*})*})*})*})*)\s*\}",
        re.DOTALL | re.MULTILINE,
    )

    STRING_PATTERN = re.compile(
        r'@string\s*\{\s*(\w+)\s*=\s*"([^"]*?)"\s*\}',
        re.IGNORECASE | re.MULTILINE,
    )

    FIELD_PATTERN = re.compile(
        r'(\w+)\s*=\s*(?:"([^"]*?)"|{((?:[^{}]|{(?:[^{}]|{(?:[^{}]|{[^{}]*})*})*})*)}|([^,}]+?))\s*(?:,|$)',
        re.MULTILINE,
    )

    UNESCAPE_MAP = {
        "\\\\": "\\",  # Backslash
        "\\$": "$",
        "\\&": "&",
        "\\#": "#",
        "\\_": "_",
        "\\%": "%",
        "\\~{}": "~",
        "\\^{}": "^",
    }

    @classmethod
    def unescape(cls, text: str) -> str:
        """Unescape LaTeX special characters.

        Args:
            text: Text with escaped characters.

        Returns:
            Text with special characters unescaped.
        """
        if not text:
            return text

        result = text
        for escaped, char in sorted(cls.UNESCAPE_MAP.items(), key=len, reverse=True):
            result = result.replace(escaped, char)
        return result

    @classmethod
    def decode(cls, bibtex_str: str) -> list[dict[str, Any]]:
        """Decode BibTeX string to list of entry dictionaries.

        Handles comments, @string definitions, and various field formats.
        Converts specific fields (keywords, year) to appropriate types.

        Args:
            bibtex_str: BibTeX format string.

        Returns:
            List of dictionaries representing parsed entries.
        """
        entries = []

        bibtex_str = bibtex_str.replace(r"\%", "\x00PERCENT\x00")
        bibtex_str = re.sub(r"%.*$", "", bibtex_str, flags=re.MULTILINE)
        bibtex_str = bibtex_str.replace("\x00PERCENT\x00", r"\%")

        bibtex_str = cls.STRING_PATTERN.sub("", bibtex_str)

        for match in cls.ENTRY_PATTERN.finditer(bibtex_str):
            entry_type = match.group(1).lower()
            entry_key = match.group(2).strip()
            fields_str = match.group(3)

            fields = {"type": entry_type, "key": entry_key}
            custom_fields = {}

            for field_match in cls.FIELD_PATTERN.finditer(fields_str):
                field_name = field_match.group(1).lower()
                value = (
                    field_match.group(2)
                    or field_match.group(3)
                    or field_match.group(4)
                    or ""
                ).strip()

                value = cls.unescape(value)

                if field_name == "keywords":
                    value = [k.strip() for k in value.split(",")]
                elif field_name == "year":
                    try:
                        value = int(value)
                    except ValueError:
                        pass

                if field_name == "type":
                    field_name = "type_"

                if field_name in ALL_FIELDS or field_name == "type_":
                    fields[field_name] = value
                else:
                    custom_fields[field_name] = value

            if custom_fields:
                fields["custom"] = custom_fields

            entries.append(fields)

        return entries
