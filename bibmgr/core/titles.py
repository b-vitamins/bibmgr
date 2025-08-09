"""Title field processing according to BibTeX rules."""

import re


class TitleProcessor:
    """Process titles according to BibTeX rules."""

    # Special LaTeX commands that convert to specific letters
    SPECIAL_LATEX_COMMANDS = {
        r"\i": "i",
        r"\j": "j",
        r"\oe": "oe",
        r"\OE": "OE",
        r"\ae": "ae",
        r"\AE": "AE",
        r"\aa": "aa",
        r"\AA": "AA",
        r"\o": "o",
        r"\O": "O",
        r"\l": "l",
        r"\L": "L",
        r"\ss": "ss",
    }

    @staticmethod
    def get_brace_depth(text: str, pos: int) -> int:
        """Calculate brace depth at a position."""
        depth = 0
        for i in range(min(pos, len(text))):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
        return max(0, depth)  # Never negative

    @staticmethod
    def is_special_char(text: str, pos: int) -> bool:
        """
        Check if position is start of a special character.

        Special char: '{' at depth 0 followed by '\'
        """
        if pos >= len(text) - 1:
            return False

        if text[pos] == "{" and TitleProcessor.get_brace_depth(text, pos) == 0:
            # Look for backslash after opening brace
            next_pos = pos + 1
            while next_pos < len(text) and text[next_pos] in " \t":
                next_pos += 1

            if next_pos < len(text) and text[next_pos] == "\\":
                return True

        return False

    @staticmethod
    def change_case(title: str, mode: str = "t") -> str:
        """
        Change case according to BibTeX rules.

        Modes:
        - 't': Title case (first letter uppercase, rest lower)
        - 'l': Lower case
        - 'u': Upper case

        Rules:
        - Characters at brace depth > 0 are protected
        - Special characters treated as depth 0
        """
        if not title:
            return title

        result = []
        i = 0
        first_letter_done = False

        while i < len(title):
            char = title[i]

            # Check for special character
            if TitleProcessor.is_special_char(title, i):
                # Find the closing brace
                brace_count = 1
                j = i + 1
                while j < len(title) and brace_count > 0:
                    if title[j] == "{":
                        brace_count += 1
                    elif title[j] == "}":
                        brace_count -= 1
                    j += 1

                # Process special character contents
                special = title[i:j]
                if mode == "l":
                    # Lowercase the text parts, preserve commands
                    processed = TitleProcessor._lowercase_special(special)
                elif mode == "u":
                    processed = TitleProcessor._uppercase_special(special)
                else:  # mode == 't'
                    processed = TitleProcessor._lowercase_special(special)

                result.append(processed)
                i = j
                continue

            # Regular character
            depth = TitleProcessor.get_brace_depth(title, i)

            if depth > 0:
                # Protected - don't change
                result.append(char)
                # But letters still count for "first letter done" in title case
                if mode == "t" and char.isalpha() and not first_letter_done:
                    first_letter_done = True
            else:
                # Apply case change
                if mode == "l":
                    result.append(char.lower())
                elif mode == "u":
                    result.append(char.upper())
                else:  # mode == 't'
                    if char.isalpha() and not first_letter_done:
                        result.append(char.upper())
                        first_letter_done = True
                    else:
                        result.append(char.lower())

            i += 1

        return "".join(result)

    @staticmethod
    def _lowercase_special(special: str) -> str:
        """Lowercase text in special character, preserving LaTeX commands."""
        # Extract command if any
        match = re.match(r"^{(\s*\\[a-zA-Z]+)(.*)}$", special, re.DOTALL)
        if match:
            command = match.group(1)
            rest = match.group(2)
            # Lowercase the rest, keep command
            return "{" + command + rest.lower() + "}"
        else:
            # No command, just lowercase contents
            return "{" + special[1:-1].lower() + "}"

    @staticmethod
    def _uppercase_special(special: str) -> str:
        """Uppercase text in special character, preserving LaTeX commands."""
        match = re.match(r"^{(\s*\\[a-zA-Z]+)(.*)}$", special, re.DOTALL)
        if match:
            command = match.group(1)
            rest = match.group(2)
            return "{" + command + rest.upper() + "}"
        else:
            return "{" + special[1:-1].upper() + "}"

    @staticmethod
    def purify(text: str) -> str:
        """
        Remove non-alphanumeric characters for sorting.

        Rules:
        - Unicode characters normalized to ASCII equivalents
        - Special LaTeX commands converted
        - Other LaTeX commands removed
        - Non-alphanumeric becomes space
        - Spaces preserved
        """
        if not text:
            return text

        result = text

        # Replace special LaTeX commands (they consume following space)
        # Use regex to match whole commands only
        for cmd, replacement in TitleProcessor.SPECIAL_LATEX_COMMANDS.items():
            # Escape the backslash for regex
            escaped_cmd = re.escape(cmd)
            # Match command followed by non-letter (space, brace, etc) or end of string
            result = re.sub(escaped_cmd + r"(?![a-zA-Z])\s?", replacement, result)

        # Handle special characters first (e.g., {\LaTeX} -> removed entirely)
        # Special character: { at depth 0 followed by \
        # Match { followed immediately by \ (no space between)
        result = re.sub(r"\{\\[a-zA-Z]+[^}]*\}", "", result)

        # Handle LaTeX commands
        # First, handle special cases where we just remove the backslash
        # Common TeX commands that should preserve their text
        for cmd in [r"\TeX", r"\LaTeX", r"\BibTeX", r"\MF", r"\MP"]:
            result = result.replace(cmd, cmd[1:])  # Remove backslash only

        # Then remove commands with braced arguments like \emph{...}
        result = re.sub(r"\\[a-zA-Z]+\*?\{[^{}]*\}", "", result)
        # Finally remove remaining standalone commands
        result = re.sub(r"\\[a-zA-Z]+\*?", "", result)

        # Remove braces
        result = result.replace("{", "").replace("}", "")

        # Replace hyphens and tildes with spaces (per TTB)
        # Also replace Unicode dashes (em dash, en dash) as they serve similar purpose
        result = result.replace("-", " ").replace("~", " ")
        result = result.replace("—", " ")  # em dash
        result = result.replace("–", " ")  # en dash

        # Normalize Unicode to ASCII
        # NFD normalization separates base characters from combining marks
        import unicodedata

        result = unicodedata.normalize("NFD", result)
        # Remove combining characters (accents, umlauts, etc.)
        result = "".join(c for c in result if not unicodedata.combining(c))

        # Remove non-ASCII characters (keep only ASCII)
        # This removes non-Latin scripts that have no ASCII equivalent
        result = "".join(c for c in result if ord(c) < 128)

        # Remove other non-alphanumeric characters
        # Now we only work with ASCII, so simple pattern
        result = re.sub(r"[^a-zA-Z0-9\s]", "", result)

        # Do NOT collapse multiple spaces - they are preserved per TTB

        return result.strip()

    @staticmethod
    def protect_capitals(title: str, words: list[str]) -> str:
        """
        Protect specified words from case changes.

        E.g., protect_capitals("The latex companion", ["LaTeX"])
        -> "The {LaTeX} companion"
        """
        result = title
        for word in words:
            # Use word boundaries to avoid partial matches
            pattern = r"\b" + re.escape(word) + r"\b"
            result = re.sub(pattern, "{" + word + "}", result, flags=re.IGNORECASE)

        return result
