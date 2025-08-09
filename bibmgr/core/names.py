"""Author name parsing according to BibTeX rules."""

import re
from dataclasses import dataclass


@dataclass
class ParsedName:
    """Parsed name components."""

    first: list[str]
    von: list[str]
    last: list[str]
    jr: list[str]

    def is_empty(self) -> bool:
        """Check if name is empty."""
        return not any([self.first, self.von, self.last, self.jr])

    def format(self, pattern: str) -> str:
        """
        Format name according to BibTeX pattern.

        Pattern examples:
        - "{ff }{vv }{ll}{, jj}" -> First von Last, Jr
        - "{vv }{ll}, {f.}" -> von Last, F.
        - "{l}" -> Last initials only
        """
        if self.is_empty():
            return ""

        result = pattern

        # Process all patterns in order
        # Match any pattern like {prefix<code><custom_sep><suffix>}
        # Examples: {ff }, {, jj}, {f.}, {f{.} }, etc.
        pattern_re = re.compile(r"\{([^{}]*?)([fvlj])([fvlj])?(\{[^}]*\})?([^}]*)\}")

        offset = 0
        for match in pattern_re.finditer(pattern):
            prefix = match.group(1)  # e.g., ", " in {, jj}
            code = match.group(2)  # f, v, l, or j
            double_code = match.group(3)  # second f in ff, if present
            custom_sep = match.group(4)  # e.g., {.} in {f{.}}
            suffix = match.group(5)  # e.g., " " in {f. }

            # Determine which name list to use
            if code == "f":
                names = self.first
            elif code == "v":
                names = self.von
            elif code == "l":
                names = self.last
            else:  # j
                names = self.jr

            # Check if this is full (ff) or abbreviated (f)
            is_full = bool(double_code)

            if not names:
                # Empty component - remove entire pattern unless it's just a space
                if suffix == " " and not prefix:
                    replacement = " "
                else:
                    replacement = ""
            elif is_full:
                # Full names - join with spaces by default
                if suffix == " ":
                    # Trailing space pattern
                    replacement = prefix + " ".join(names) + " "
                else:
                    # No trailing space or other suffix
                    replacement = prefix + " ".join(names) + suffix
            else:
                # Abbreviated names
                if code == "f":
                    # First names need special handling for hyphens
                    abbrevs = []
                    for name in names:
                        if "-" in name:
                            # Hyphenated: "Jean-Paul" -> "J.-P."
                            parts = name.split("-")
                            abbrev = "-".join(p[0].upper() + "." for p in parts if p)
                            abbrevs.append(abbrev)
                        else:
                            # Simple name
                            abbrevs.append(name[0].upper())

                    # Determine how to join abbreviations
                    if custom_sep:
                        # Custom separator like {-} or {.}
                        sep = custom_sep[1:-1]
                        if sep == ".":
                            # {f{.}} means "use . between with space"
                            joined = ". ".join(abbrevs)
                            if not joined.endswith("."):
                                joined += "."
                            replacement = prefix + joined + suffix
                        else:
                            # {f{-}} means "use - between"
                            replacement = prefix + sep.join(abbrevs) + suffix
                    elif suffix == ".":
                        # {f.} means "use . between with no space"
                        replacement = prefix + ".".join(abbrevs) + "."
                    elif suffix == ". ":
                        # {f. } means "use . between with space"
                        joined = ". ".join(abbrevs)
                        if not joined.endswith("."):
                            joined += "."
                        replacement = prefix + joined + " "
                    else:
                        # {f} means just initials
                        replacement = prefix + "".join(abbrevs) + suffix
                else:
                    # von, last, jr - just concatenate initials
                    initials = "".join(name[0].upper() for name in names if name)
                    replacement = prefix + initials + suffix

            # Replace in result, adjusting for offset
            result = (
                result[: match.start() + offset]
                + replacement
                + result[match.end() + offset :]
            )
            offset += len(replacement) - (match.end() - match.start())

        # Clean up
        result = re.sub(r"\s*,\s*$", "", result)  # Trailing comma
        result = re.sub(r"\s+", " ", result)  # Multiple spaces
        return result.strip()


class NameParser:
    """Parse author names according to BibTeX rules."""

    @staticmethod
    def parse(name: str) -> ParsedName:
        """
        Parse name according to BibTeX's three formats.

        Format determined by comma count:
        - 0 commas: "First von Last"
        - 1 comma: "von Last, First"
        - 2 commas: "von Last, Jr, First"
        """
        name = name.strip()
        if not name:
            return ParsedName([], [], [], [])

        comma_count = name.count(",")

        if comma_count == 0:
            return NameParser._parse_first_von_last(name)
        elif comma_count == 1:
            return NameParser._parse_von_last_first(name)
        elif comma_count == 2:
            return NameParser._parse_von_last_jr_first(name)
        else:
            # Too many commas - treat everything after 2nd comma as first name
            parts = name.split(",", 2)
            return NameParser._parse_von_last_jr_first(",".join(parts))

    @staticmethod
    def _tokenize(name: str) -> list[str]:
        """Split name into tokens, preserving braced groups."""
        tokens = []
        current = []
        brace_level = 0

        for char in name:
            if char == "{":
                brace_level += 1
                current.append(char)
            elif char == "}":
                brace_level -= 1
                current.append(char)
            elif char in " \t\n~" and brace_level == 0:
                if current:
                    tokens.append("".join(current))
                    current = []
                if char == "~":
                    tokens.append(char)
            else:
                current.append(char)

        if current:
            tokens.append("".join(current))

        # Remove empty tokens but preserve separators
        result = []
        for token in tokens:
            if token and token != "~":
                result.append(token)

        return result

    @staticmethod
    def _starts_with_lowercase(word: str) -> bool:
        """
        Check if word starts with lowercase letter.

        BibTeX rules:
        - {X} at start means NOT lowercase (braced words are not von)
        - Special chars ignored
        - First real letter determines case
        """
        # Braced words are not considered lowercase for von detection
        if word.startswith("{") and word.endswith("}"):
            return False

        # Find first letter
        for char in word:
            if char.isalpha():
                return char.islower()

        # No letters found
        return False

    @staticmethod
    def _parse_first_von_last(name: str) -> ParsedName:
        """Parse 'First von Last' format."""
        tokens = NameParser._tokenize(name)

        if not tokens:
            return ParsedName([], [], [], [])

        # Last name must have at least one token
        if len(tokens) == 1:
            return ParsedName([], [], tokens, [])

        # Find von part - continuous sequence of lowercase-starting words
        # that doesn't include the last word
        von_start = None
        von_end = None

        for i in range(len(tokens) - 1):  # -1 to ensure Last has at least one
            if NameParser._starts_with_lowercase(tokens[i]):
                if von_start is None:
                    von_start = i
                von_end = i
            elif von_start is not None:
                # Uppercase after lowercase - end of von
                break

        if von_start is not None and von_end is not None:
            first = tokens[:von_start]
            von = tokens[von_start : von_end + 1]
            last = tokens[von_end + 1 :]
        else:
            # No von part found
            first = tokens[:-1]
            von = []
            last = tokens[-1:]

        return ParsedName(first, von, last, [])

    @staticmethod
    def _parse_von_last_first(name: str) -> ParsedName:
        """Parse 'von Last, First' format."""
        parts = name.split(",", 1)
        if len(parts) != 2:
            return ParsedName([], [], [name.strip()], [])

        von_last = parts[0].strip()
        first = parts[1].strip()

        # Parse von Last part
        tokens = NameParser._tokenize(von_last)

        if not tokens:
            return ParsedName(NameParser._tokenize(first), [], [], [])

        # Last name is at least the last token
        von_end = -1
        for i in range(len(tokens) - 1):
            if NameParser._starts_with_lowercase(tokens[i]):
                von_end = i

        if von_end >= 0:
            von = tokens[: von_end + 1]
            last = tokens[von_end + 1 :]
        else:
            von = []
            last = tokens

        return ParsedName(NameParser._tokenize(first), von, last, [])

    @staticmethod
    def _parse_von_last_jr_first(name: str) -> ParsedName:
        """Parse 'von Last, Jr, First' format."""
        parts = name.split(",", 2)
        if len(parts) != 3:
            # Fall back to simpler format
            return NameParser._parse_von_last_first(name)

        von_last = parts[0].strip()
        jr = parts[1].strip()
        first = parts[2].strip()

        # Parse von Last part (same as above)
        tokens = NameParser._tokenize(von_last)

        if not tokens:
            return ParsedName(
                NameParser._tokenize(first), [], [], NameParser._tokenize(jr)
            )

        von_end = -1
        for i in range(len(tokens) - 1):
            if NameParser._starts_with_lowercase(tokens[i]):
                von_end = i

        if von_end >= 0:
            von = tokens[: von_end + 1]
            last = tokens[von_end + 1 :]
        else:
            von = []
            last = tokens

        return ParsedName(
            NameParser._tokenize(first), von, last, NameParser._tokenize(jr)
        )


class NameFormatter:
    """Format parsed names for output."""

    @staticmethod
    def abbreviate(name: str) -> str:
        """Abbreviate a first name, handling special cases."""
        if not name:
            return ""

        # Handle special case like {\relax Ch}ristopher
        if name.startswith("{") and "}" in name:
            end_brace = name.index("}")
            inner = name[1:end_brace]
            if inner.startswith("\\"):
                # LaTeX command - skip it
                parts = inner.split(None, 1)
                if len(parts) > 1:
                    return parts[1] + "."
            # Return the content inside braces
            return inner + "."

        # Handle hyphenated names
        if "-" in name:
            parts = name.split("-")
            return "-".join(p[0].upper() + "." if p else "" for p in parts)

        # Simple case
        return name[0].upper() + "."
