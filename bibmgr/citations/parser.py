"""Citation parsing with full LaTeX and BibLaTeX support."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from bibmgr.core.models import Entry


class CitationCommand(Enum):
    """Citation command types."""

    # Standard LaTeX
    CITE = "cite"

    # Natbib
    CITEP = "citep"
    CITET = "citet"
    CITEALT = "citealt"
    CITEALP = "citealp"
    CITEAUTHOR = "citeauthor"
    CITEYEAR = "citeyear"
    CITEYEARPAR = "citeyearpar"

    # BibLaTeX
    PARENCITE = "parencite"
    TEXTCITE = "textcite"
    AUTOCITE = "autocite"
    FOOTCITE = "footcite"
    SMARTCITE = "smartcite"
    SUPERCITE = "supercite"
    CITES = "cites"
    FULLCITE = "fullcite"
    CITETITLE = "citetitle"

    # Markdown
    MARKDOWN_CITE = "markdown_cite"
    MARKDOWN_PARENS = "markdown_parens"

    # Custom
    CUSTOM = "custom"


@dataclass
class Citation:
    """A parsed citation reference."""

    command: CitationCommand
    keys: list[str]
    prefix: str | None = None
    suffix: str | None = None
    starred: bool = False
    start_pos: int = 0
    end_pos: int = 0
    suppress_author: bool = False
    in_note: bool = False
    locators: list[str] = field(default_factory=list)

    @property
    def is_parenthetical(self) -> bool:
        """Check if citation should be in parentheses."""
        return self.command in {
            CitationCommand.CITE,
            CitationCommand.CITEP,
            CitationCommand.CITEALP,
            CitationCommand.PARENCITE,
            CitationCommand.MARKDOWN_PARENS,
        }

    @property
    def is_textual(self) -> bool:
        """Check if citation is textual."""
        return self.command in {
            CitationCommand.CITET,
            CitationCommand.CITEALT,
            CitationCommand.TEXTCITE,
        }

    @property
    def is_author_only(self) -> bool:
        """Check if citation shows author only."""
        return self.command == CitationCommand.CITEAUTHOR

    def __eq__(self, other):
        """Check equality."""
        if not isinstance(other, Citation):
            return False
        return (
            self.command == other.command
            and self.keys == other.keys
            and self.start_pos == other.start_pos
            and self.end_pos == other.end_pos
        )

    def __str__(self):
        """String representation."""
        keys_str = ", ".join(self.keys)
        return f"{self.command.value}({keys_str})"

    def to_latex(self):
        """Convert back to LaTeX format."""
        cmd = f"\\{self.command.value}"
        if self.starred:
            cmd += "*"

        # Add optional arguments
        if self.prefix and self.suffix:
            cmd += f"[{self.prefix}][{self.suffix}]"
        elif self.suffix:
            cmd += f"[{self.suffix}]"

        # Add keys
        cmd += "{" + ", ".join(self.keys) + "}"

        return cmd


@dataclass
class CitationContext:
    """Context around a citation."""

    citation: Citation
    line_number: int
    before: str
    after: str


class EntryProvider(Protocol):
    """Protocol for retrieving bibliography entries."""

    def get_entry(self, key: str) -> Entry | None:
        """Get entry by citation key."""
        ...

    def get_entries(self, keys: list[str]) -> list[Entry]:
        """Get multiple entries by keys."""
        ...


class LaTeXParser:
    """Parse LaTeX citations."""

    # Standard LaTeX and natbib commands
    COMMANDS = {
        "cite",
        "citep",
        "citet",
        "citealt",
        "citealp",
        "citeauthor",
        "citeyear",
        "citeyearpar",
    }

    def parse(self, text: str) -> list[Citation]:
        """Parse LaTeX citations from text."""
        citations = []

        # Skip commented lines
        lines = text.split("\n")
        active_text = []
        for line in lines:
            # Remove comments
            if "%" in line:
                comment_pos = line.index("%")
                # Check if escaped
                if comment_pos == 0 or line[comment_pos - 1] != "\\":
                    line = line[:comment_pos]
            active_text.append(line)
        text = "\n".join(active_text)

        # Pattern for LaTeX citations (negative lookbehind for escaped backslash)
        pattern = (
            r"(?<!\\)\\(" + "|".join(self.COMMANDS) + r")(\*?)"
            r"(?:\[([^\]]*)\])?(?:\[([^\]]*)\])?\{([^}]+)\}"
        )

        for match in re.finditer(pattern, text):
            command_str = match.group(1)
            starred = bool(match.group(2))
            prefix = match.group(3)
            suffix = match.group(4)
            keys_str = match.group(5)

            # Handle optional arguments
            if suffix is None and prefix is not None:
                # Only one optional argument = suffix
                suffix = prefix
                prefix = None

            # Handle named arguments (BibLaTeX style)
            if prefix and "=" in prefix:
                # Extract value from named argument like "prenote={value}"
                if "{" in prefix and "}" in prefix:
                    start = prefix.index("{") + 1
                    end = prefix.rindex("}")
                    prefix = prefix[start:end]
                else:
                    # Just take the part after =
                    prefix = prefix.split("=", 1)[1]

            if suffix and "=" in suffix:
                # Extract value from named argument like "postnote={value}"
                if "{" in suffix and "}" in suffix:
                    start = suffix.index("{") + 1
                    end = suffix.rindex("}")
                    suffix = suffix[start:end]
                else:
                    # Just take the part after =
                    suffix = suffix.split("=", 1)[1]

            # Parse keys
            keys = [k.strip() for k in keys_str.split(",") if k.strip()]

            # Create citation
            try:
                command = CitationCommand(command_str)
            except ValueError:
                command = CitationCommand.CITE

            citation = Citation(
                command=command,
                keys=keys,
                prefix=prefix,
                suffix=suffix,
                starred=starred,
                start_pos=match.start(),
                end_pos=match.end(),
            )
            citations.append(citation)

        return citations


class BibLaTeXParser(LaTeXParser):
    """Parse BibLaTeX citations."""

    # Extended BibLaTeX commands
    COMMANDS = LaTeXParser.COMMANDS | {
        "parencite",
        "textcite",
        "autocite",
        "footcite",
        "smartcite",
        "supercite",
        "cites",
        "fullcite",
        "citetitle",
    }

    def parse(self, text: str) -> list[Citation]:
        """Parse BibLaTeX citations."""
        citations = super().parse(text)

        # Handle multicite commands like \cites{key1}{key2}{key3}
        # Only match when there are multiple groups (2+)
        multicite_pattern = (
            r"(?<!\\)\\cites(?:\[[^\]]*\])?(?:\[[^\]]*\])?(\{[^}]+\})(\{[^}]+\})+"
        )

        for match in re.finditer(multicite_pattern, text):
            # Remove any single-group \cites from parent parse
            citations = [
                c
                for c in citations
                if not (
                    c.command == CitationCommand.CITES and c.start_pos == match.start()
                )
            ]

            # Extract all key groups
            key_pattern = r"\{([^}]+)\}"
            key_matches = re.findall(key_pattern, match.group(0))

            if key_matches:
                all_keys = []
                for key_group in key_matches:
                    keys = [k.strip() for k in key_group.split(",") if k.strip()]
                    all_keys.extend(keys)

                citation = Citation(
                    command=CitationCommand.CITES,
                    keys=all_keys,
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
                citations.append(citation)

        return citations


class MarkdownParser:
    """Parse Markdown/Pandoc citations."""

    def parse(self, text: str) -> list[Citation]:
        """Parse Markdown citations."""
        citations = []

        # Pattern for [@key] style citations (including optional - for suppressed author)
        # Exclude footnotes (those preceded by ^)
        bracketed_pattern = r"(?<!\\)(?<!\^)\[(-?@[^]]+)\]"

        for match in re.finditer(bracketed_pattern, text):
            content = match.group(1)

            # Check for suppressed author (starts with @- or just -)
            suppress_author = False
            if content.startswith("@-"):
                suppress_author = True
                content = "@" + content[2:]  # Remove the dash
            elif content.startswith("-@"):
                suppress_author = True
                content = content[1:]  # Remove the dash, keep @

            # Extract keys and locators
            key_pattern = r"@([\w:-]+)(?:\s*,\s*([^;@]+))?"
            keys = []
            locators = []

            for key_match in re.finditer(key_pattern, content):
                keys.append(key_match.group(1))
                if key_match.group(2):
                    locators.append(key_match.group(2).strip())

            if keys:
                citation = Citation(
                    command=CitationCommand.MARKDOWN_PARENS,
                    keys=keys,
                    suppress_author=suppress_author,
                    locators=locators,
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
                citations.append(citation)

        # Pattern for simple @key citations (not inside brackets)
        simple_pattern = r"(?<!\\)(?<!\[)@([\w:-]+)(?:\s*\[([^\]]+)\])?"

        for match in re.finditer(simple_pattern, text):
            # Check if this @ is inside brackets (already handled above)
            pos = match.start()
            # Find if we're inside any bracketed citation
            inside_brackets = False
            for cite in citations:
                if cite.command == CitationCommand.MARKDOWN_PARENS:
                    if cite.start_pos <= pos < cite.end_pos:
                        inside_brackets = True
                        break

            if not inside_brackets:
                key = match.group(1)
                locator = match.group(2)

                citation = Citation(
                    command=CitationCommand.MARKDOWN_CITE,
                    keys=[key],
                    suffix=locator,
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
                citations.append(citation)

        # Pattern for footnote citations
        footnote_pattern = r"\^\[([^]]*@[\w:-]+[^]]*)\]"

        for match in re.finditer(footnote_pattern, text):
            content = match.group(1)

            # Extract keys from footnote
            key_pattern = r"@([\w:-]+)"
            keys = re.findall(key_pattern, content)

            if keys:
                citation = Citation(
                    command=CitationCommand.MARKDOWN_CITE,
                    keys=keys,
                    in_note=True,
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
                citations.append(citation)

        return citations


class ParserRegistry:
    """Registry of citation parsers."""

    def __init__(self):
        """Initialize with default parsers."""
        self._parsers = {
            "latex": LaTeXParser(),
            "biblatex": BibLaTeXParser(),
            "markdown": MarkdownParser(),
        }

        # Aliases
        self._aliases = {
            "tex": "latex",
            "md": "markdown",
        }

    def __contains__(self, name: str) -> bool:
        """Check if parser is registered."""
        name = name.lower()
        return name in self._parsers or name in self._aliases

    def get(self, name: str):
        """Get parser by name."""
        name = name.lower()

        if name in self._aliases:
            name = self._aliases[name]

        if name not in self._parsers:
            raise ValueError(f"Unknown parser: {name}")

        return self._parsers[name]

    def register(self, name: str, parser) -> None:
        """Register custom parser."""
        self._parsers[name.lower()] = parser

    def list_parsers(self) -> list[str]:
        """List available parsers."""
        return list(self._parsers.keys())


class CitationParser:
    """Generic citation parser with format detection."""

    def __init__(self):
        """Initialize parser."""
        self.registry = ParserRegistry()
        self._custom_parsers = {}

    def parse(self, text: str, format: str = "auto") -> list[Citation]:
        """Parse citations from text.

        Args:
            text: Source text
            format: Format (latex, markdown, auto)

        Returns:
            List of parsed citations
        """
        if format == "auto":
            format = self._detect_format(text)

        if format == "auto":
            # Try all parsers and combine results
            citations = []
            for parser_name in ["latex", "markdown"]:
                parser = self.registry.get(parser_name)
                citations.extend(parser.parse(text))
            return citations

        # Use specific parser
        if format in self._custom_parsers:
            parser = self._custom_parsers[format]
        else:
            parser = self.registry.get(format)

        return parser.parse(text)

    def register_parser(self, name: str, parser) -> None:
        """Register custom parser."""
        self._custom_parsers[name] = parser

    def _detect_format(self, text: str) -> str:
        """Auto-detect text format."""
        has_latex = bool(re.search(r"\\cite[a-z]*\{", text))
        has_markdown = bool(
            re.search(r"(?<!\\)@[\w:-]+", text) or re.search(r"\[@[\w:-]+", text)
        )

        # If both formats present, return auto to use all parsers
        if has_latex and has_markdown:
            return "auto"
        elif has_latex:
            return "latex"
        elif has_markdown:
            return "markdown"

        return "auto"


class CitationProcessor:
    """Process citations and generate formatted output."""

    def __init__(
        self,
        entry_provider: EntryProvider,
        style=None,  # CitationStyle
    ):
        """Initialize processor."""
        self.entry_provider = entry_provider
        self.style = style
        self.parser = CitationParser()

        if not self.style:
            from bibmgr.citations.styles import APAStyle

            self.style = APAStyle()

    def process(
        self,
        text: str,
        format: str = "auto",
        replace: bool = True,
    ) -> str:
        """Process citations in text."""
        citations = self.parser.parse(text, format)

        if not citations or not replace:
            return text

        # Sort by position (reverse) to replace from end
        citations.sort(key=lambda c: c.start_pos, reverse=True)

        result = text
        for citation in citations:
            formatted = self._format_citation(citation)
            result = (
                result[: citation.start_pos] + formatted + result[citation.end_pos :]
            )

        return result

    def _format_citation(self, citation: Citation) -> str:
        """Format a single citation."""
        # Get entries
        entries = self.entry_provider.get_entries(citation.keys)
        if not entries:
            # Return placeholder for missing entries
            return f"[{', '.join(citation.keys)}]"

        # Format based on command type
        if citation.is_author_only:
            # Author only
            if len(entries) == 1:
                return self._format_author_only(entries[0])
            else:
                return self._format_multiple_authors(entries)

        elif citation.command == CitationCommand.CITEYEAR:
            # Year only
            years = [str(e.year) if e.year else "n.d." for e in entries]
            return ", ".join(years)

        elif citation.command == CitationCommand.CITEYEARPAR:
            # Year in parentheses
            years = [str(e.year) if e.year else "n.d." for e in entries]
            return f"({', '.join(years)})"

        elif citation.is_textual:
            # Textual citation
            return self._format_textual(entries, citation)

        else:
            # Parenthetical citation
            return self._format_parenthetical(entries, citation)

    def _format_author_only(self, entry: Entry) -> str:
        """Format author names only."""
        if not entry.author:
            return "Anonymous"

        authors = entry.authors_list
        if not authors:
            return "Anonymous"

        if len(authors) == 1:
            return self._get_last_name(authors[0])
        elif len(authors) == 2:
            return f"{self._get_last_name(authors[0])} and {self._get_last_name(authors[1])}"
        else:
            names = [self._get_last_name(a) for a in authors[:-1]]
            return f"{', '.join(names)}, and {self._get_last_name(authors[-1])}"

    def _format_multiple_authors(self, entries: list[Entry]) -> str:
        """Format multiple author sets."""
        author_sets = [self._format_author_only(e) for e in entries]
        return "; ".join(author_sets)

    def _format_textual(self, entries: list[Entry], citation: Citation) -> str:
        """Format textual citation."""
        if len(entries) == 1:
            entry = entries[0]
            author = self._format_author_only(entry)
            year = str(entry.year) if entry.year else "n.d."

            if citation.suffix:
                return f"{author} ({year}, {citation.suffix})"
            else:
                return f"{author} ({year})"
        else:
            # Multiple entries
            parts = []
            for entry in entries:
                author = self._format_author_only(entry)
                year = str(entry.year) if entry.year else "n.d."
                parts.append(f"{author} ({year})")
            return "; ".join(parts)

    def _format_parenthetical(self, entries: list[Entry], citation: Citation) -> str:
        """Format parenthetical citation."""
        formatted_entries = []

        for entry in entries:
            if not self.style:
                from bibmgr.citations.styles import APAStyle

                self.style = APAStyle()
            result = self.style.format_inline(entry)
            # Remove outer parentheses if present
            if result.startswith("(") and result.endswith(")"):
                result = result[1:-1]
            formatted_entries.append(result)

        content = "; ".join(formatted_entries)

        # Add prefix/suffix if present
        if citation.prefix:
            content = f"{citation.prefix}, {content}"
        if citation.suffix:
            content = f"{content}, {citation.suffix}"

        return f"({content})"

    def _get_last_name(self, author: str) -> str:
        """Extract last name from author string."""
        if "," in author:
            return author.split(",")[0].strip()
        else:
            parts = author.strip().split()
            return parts[-1] if parts else author

    def extract_keys(self, text: str, format: str = "auto") -> set[str]:
        """Extract all cited keys from text."""
        citations = self.parser.parse(text, format)
        keys = set()
        for citation in citations:
            keys.update(citation.keys)
        return keys

    def get_contexts(
        self,
        text: str,
        lines_before: int = 2,
        lines_after: int = 2,
    ) -> list[CitationContext]:
        """Get citation contexts."""
        citations = self.parser.parse(text)
        lines = text.split("\n")
        contexts = []

        for citation in citations:
            # Find line containing citation
            char_count = 0
            line_num = 0

            for i, line in enumerate(lines):
                if char_count <= citation.start_pos < char_count + len(line) + 1:
                    line_num = i
                    break
                char_count += len(line) + 1

            # Get context lines
            start = max(0, line_num - lines_before)
            end = min(len(lines), line_num + lines_after + 1)

            context = CitationContext(
                citation=citation,
                line_number=line_num + 1,
                before="\n".join(lines[start:line_num]),
                after="\n".join(lines[line_num + 1 : end]),
            )
            contexts.append(context)

        return contexts


class CitationExtractor:
    """Extract and analyze citations from documents."""

    def __init__(self):
        """Initialize extractor."""
        self.parser = CitationParser()

    def extract_all(self, text: str) -> list[Citation]:
        """Extract all citations from document."""
        return self.parser.parse(text)

    def group_by_type(self, text: str) -> dict[CitationCommand, list[Citation]]:
        """Group citations by command type."""
        citations = self.extract_all(text)
        groups = {}

        for citation in citations:
            if citation.command not in groups:
                groups[citation.command] = []
            groups[citation.command].append(citation)

        return groups

    def find_undefined(
        self,
        text: str,
        entry_provider: EntryProvider,
    ) -> set[str]:
        """Find undefined citation keys."""
        citations = self.extract_all(text)
        undefined = set()

        for citation in citations:
            for key in citation.keys:
                if not entry_provider.get_entry(key):
                    undefined.add(key)

        return undefined

    def find_duplicates(self, text: str) -> dict[str, int]:
        """Find duplicate citations."""
        citations = self.extract_all(text)
        counts = {}

        for citation in citations:
            for key in citation.keys:
                counts[key] = counts.get(key, 0) + 1

        # Return only duplicates
        return {k: v for k, v in counts.items() if v > 1}

    def get_statistics(self, text: str) -> dict:
        """Get citation statistics."""
        citations = self.extract_all(text)

        # Count unique keys
        all_keys = set()
        for citation in citations:
            all_keys.update(citation.keys)

        # Count by type
        type_counts = {}
        for citation in citations:
            cmd = citation.command.value.upper()
            type_counts[cmd] = type_counts.get(cmd, 0) + 1

        return {
            "total_citations": len(citations),
            "unique_keys": len(all_keys),
            "citation_types": type_counts,
        }


class AsyncCitationProcessor:
    """Asynchronous citation processor."""

    def __init__(
        self,
        entry_provider: EntryProvider,
        style=None,
    ):
        """Initialize async processor."""
        self.sync_processor = CitationProcessor(entry_provider, style)

    async def process_async(self, text: str, **kwargs) -> str:
        """Process citations asynchronously."""
        # Simulate async processing
        await asyncio.sleep(0)  # Yield control
        return self.sync_processor.process(text, **kwargs)

    async def process_batch(self, documents: list[str]) -> list[str]:
        """Process multiple documents concurrently."""
        tasks = [self.process_async(doc) for doc in documents]
        return await asyncio.gather(*tasks)
