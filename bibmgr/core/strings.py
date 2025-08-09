"""String abbreviation support."""

import re


class StringRegistry:
    """Handle @string abbreviations."""

    # Predefined month abbreviations
    PREDEFINED_STRINGS = {
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
    }

    def __init__(self):
        # Use a case-insensitive dictionary
        self.strings = CaseInsensitiveDict(self.PREDEFINED_STRINGS.copy())

    def add_string(self, key: str, value: str):
        """Add a string abbreviation."""
        self.strings[key] = value

    def expand(self, text: str) -> str:
        """Expand string abbreviations in text."""
        if not text:
            return ""

        # Pattern to match:
        # 1. Unquoted words (potential abbreviations)
        # 2. "..." quoted strings (literals)
        # 3. {...} braced strings (literals) - including empty braces
        # 4. # concatenation operator
        pattern = r'(\w+)|"([^"]*)"|{([^{}]*(?:{[^{}]*}[^{}]*)*)}|\s*#\s*'

        parts = []
        last_end = 0

        for match in re.finditer(pattern, text):
            # Handle content between matches (should be whitespace)
            between = text[last_end : match.start()]
            if between and not between.isspace() and "#" not in between:
                # This shouldn't happen with our pattern, but handle it
                parts.append(between)

            if match.group(1):  # Word (potential abbreviation)
                abbrev = match.group(1)
                # Check if it's an abbreviation
                if abbrev.lower() in self.strings:
                    parts.append(self.strings[abbrev.lower()])
                else:
                    # Not an abbreviation, treat as literal
                    parts.append(abbrev)
            elif match.group(2) is not None:  # Quoted literal
                parts.append(match.group(2))
            elif match.group(3) is not None:  # Braced literal
                # Remove outer braces if present
                content = match.group(3)
                parts.append(content)
            elif "#" in match.group(0):  # Concatenation operator
                # Just skip it - concatenation happens by joining parts
                pass

            last_end = match.end()

        # Handle any remaining content
        if last_end < len(text):
            remaining = text[last_end:]
            if remaining and not remaining.isspace():
                parts.append(remaining)

        return "".join(parts)

    def parse_string_definition(self, definition: str) -> tuple[str, str] | None:
        """
        Parse a @string definition.

        Returns (key, value) or None if invalid.
        """
        # Match: @string{key = "value"} or @string{key = {value}}
        # Allow flexible whitespace and case-insensitive @STRING
        match = re.match(
            r'@string\s*\{\s*(\w+)\s*=\s*(?:"([^"]+)"|{([^}]+)})\s*\}',
            definition,
            re.IGNORECASE,
        )

        if match:
            key = match.group(1)
            value = match.group(2) if match.group(2) is not None else match.group(3)
            if value:  # Don't allow empty values
                return (key, value)

        return None


class CaseInsensitiveDict:
    """A dictionary with case-insensitive keys."""

    def __init__(self, initial_data=None):
        self._data = {}
        if initial_data:
            for key, value in initial_data.items():
                self[key] = value

    def __setitem__(self, key, value):
        """Set item with case-insensitive key."""
        self._data[key.lower()] = value

    def __getitem__(self, key):
        """Get item with case-insensitive key."""
        return self._data[key.lower()]

    def __contains__(self, key):
        """Check if key exists (case-insensitive)."""
        return key.lower() in self._data

    def get(self, key, default=None):
        """Get item with default value."""
        return self._data.get(key.lower(), default)

    def items(self):
        """Return items iterator."""
        return self._data.items()

    def keys(self):
        """Return keys iterator."""
        return self._data.keys()

    def values(self):
        """Return values iterator."""
        return self._data.values()
