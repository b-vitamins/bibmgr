"""BibTeX parser with full feature support and format preservation.

Features:
- Complete BibTeX syntax support
- Format preservation for round-trip editing
- Robust error recovery
- Streaming support for large files
- Clean architecture without hacks
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, TextIO

from bibmgr.core.models import Entry, EntryType


class TokenType(Enum):
    """BibTeX token types."""

    AT = auto()
    ENTRY_TYPE = auto()
    STRING_DEF = auto()
    COMMENT = auto()
    PREAMBLE = auto()
    LBRACE = auto()
    RBRACE = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    EQUALS = auto()
    CONCAT = auto()
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    WHITESPACE = auto()
    NEWLINE = auto()
    LINE_COMMENT = auto()
    EOF = auto()


@dataclass
class Token:
    """A lexical token with position and raw text."""

    type: TokenType
    value: str
    line: int
    column: int
    raw: str = ""  # Original text including whitespace

    def __str__(self) -> str:
        return f"{self.type.name}({self.value!r}) at {self.line}:{self.column}"


@dataclass
class ParseError(Exception):
    """Parse error with detailed location."""

    message: str
    line: int
    column: int
    severity: str = "error"  # error, warning, info
    context: str | None = None

    def __str__(self) -> str:
        prefix = f"[{self.severity.upper()}]" if self.severity != "error" else ""
        location = f"Line {self.line}, column {self.column}"
        base = f"{prefix} {location}: {self.message}"
        if self.context:
            return f"{base}\n  {self.context}"
        return base


@dataclass
class FormatMetadata:
    """Metadata for format preservation."""

    original_text: str
    comments: list[tuple[int, str]]  # (line, comment_text)
    entry_formats: dict[str, dict[str, Any]]  # Formatting per entry
    string_defs: dict[str, str]  # String definitions
    preambles: list[str]  # Preamble contents

    def __init__(self):
        self.original_text = ""
        self.comments = []
        self.entry_formats = {}
        self.string_defs = {}
        self.preambles = []


class BibtexLexer:
    """Lexical analyzer for BibTeX with format preservation."""

    def __init__(self, text: str, preserve_format: bool = False):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.preserve_format = preserve_format
        self.tokens: list[Token] = []

    def current_char(self) -> str | None:
        if self.pos >= len(self.text):
            return None
        return self.text[self.pos]

    def peek_char(self, offset: int = 1) -> str | None:
        pos = self.pos + offset
        if pos >= len(self.text):
            return None
        return self.text[pos]

    def advance(self, count: int = 1) -> str:
        result = ""
        for _ in range(count):
            if self.pos >= len(self.text):
                break
            char = self.text[self.pos]
            result += char
            self.pos += 1
            if char == "\n":
                self.line += 1
                self.column = 1
            else:
                self.column += 1
        return result

    def read_until(self, predicate) -> str:
        start = self.pos
        while self.current_char() and predicate(self.current_char()):
            self.advance()
        return self.text[start : self.pos]

    def read_whitespace(self) -> Token:
        line, column = self.line, self.column
        ws = self.read_until(lambda c: c.isspace() and c != "\n")
        return Token(TokenType.WHITESPACE, ws, line, column, ws)

    def read_line_comment(self) -> Token:
        line, column = self.line, self.column
        self.advance()  # Skip %
        comment = self.read_until(lambda c: c != "\n")
        return Token(TokenType.LINE_COMMENT, comment, line, column, "%" + comment)

    def read_identifier(self) -> str:
        return self.read_until(lambda c: c.isalnum() or c in "_-:./")

    def read_number(self) -> str:
        return self.read_until(str.isdigit)

    def read_quoted_string(self) -> tuple[str, str]:
        """Read quoted string, returning (value, raw)."""
        raw = self.advance()  # Opening quote
        value = ""

        while self.current_char() and self.current_char() != '"':
            if self.current_char() == "\\":
                # Preserve backslash for LaTeX commands
                char = self.current_char()
                if char:
                    value += char
                raw += self.advance()
                if self.current_char():
                    char = self.advance()
                    raw += char
                    value += char
            else:
                char = self.advance()
                raw += char
                value += char

        if self.current_char() == '"':
            raw += self.advance()

        return value, raw

    def read_braced_string(self) -> tuple[str, str]:
        """Read braced string with balanced braces."""
        raw = self.advance()  # Opening brace
        value = ""
        depth = 1

        while self.current_char() and depth > 0:
            char = self.current_char()
            if (
                not char
            ):  # Should not happen after while check, but satisfy type checker
                break

            if char == "{":
                depth += 1
                value += char
                raw += self.advance()
            elif char == "}":
                depth -= 1
                if depth > 0:
                    value += char
                raw += self.advance()
            elif char == "\\":
                raw += self.advance()
                if self.current_char():
                    next_char = self.advance()
                    raw += next_char
                    if next_char:
                        value += "\\" + next_char
            else:
                value += char
                raw += self.advance()

        return value, raw

    def tokenize(self) -> list[Token]:
        """Tokenize input, optionally preserving format."""
        tokens = []

        while self.pos < len(self.text):
            # Track position
            line, column = self.line, self.column
            char = self.current_char()

            if char is None:
                break

            # Handle different token types
            if char.isspace():
                if char == "\n":
                    raw = self.advance()
                    if self.preserve_format:
                        tokens.append(Token(TokenType.NEWLINE, "\n", line, column, raw))
                elif self.preserve_format:
                    tokens.append(self.read_whitespace())
                else:
                    self.read_whitespace()  # Skip but don't store

            elif char == "%":
                comment = self.read_line_comment()
                if self.preserve_format:
                    tokens.append(comment)

            elif char == "@":
                raw = self.advance()
                tokens.append(Token(TokenType.AT, "@", line, column, raw))

                # Read entry type or command
                char = self.current_char()
                if char and char.isalpha():
                    ident_start = self.pos
                    identifier = self.read_identifier().lower()
                    ident_raw = self.text[ident_start : self.pos]

                    if identifier == "string":
                        tokens.append(
                            Token(
                                TokenType.STRING_DEF,
                                identifier,
                                line,
                                column + 1,
                                ident_raw,
                            )
                        )
                    elif identifier == "comment":
                        tokens.append(
                            Token(
                                TokenType.COMMENT,
                                identifier,
                                line,
                                column + 1,
                                ident_raw,
                            )
                        )
                    elif identifier == "preamble":
                        tokens.append(
                            Token(
                                TokenType.PREAMBLE,
                                identifier,
                                line,
                                column + 1,
                                ident_raw,
                            )
                        )
                    else:
                        tokens.append(
                            Token(
                                TokenType.ENTRY_TYPE,
                                identifier,
                                line,
                                column + 1,
                                ident_raw,
                            )
                        )

            elif char == "{":
                raw = self.advance()
                tokens.append(Token(TokenType.LBRACE, "{", line, column, raw))

            elif char == "}":
                raw = self.advance()
                tokens.append(Token(TokenType.RBRACE, "}", line, column, raw))

            elif char == "(":
                raw = self.advance()
                tokens.append(Token(TokenType.LPAREN, "(", line, column, raw))

            elif char == ")":
                raw = self.advance()
                tokens.append(Token(TokenType.RPAREN, ")", line, column, raw))

            elif char == ",":
                raw = self.advance()
                tokens.append(Token(TokenType.COMMA, ",", line, column, raw))

            elif char == "=":
                raw = self.advance()
                tokens.append(Token(TokenType.EQUALS, "=", line, column, raw))

            elif char == "#":
                raw = self.advance()
                tokens.append(Token(TokenType.CONCAT, "#", line, column, raw))

            elif char == '"':
                value, raw = self.read_quoted_string()
                tokens.append(Token(TokenType.STRING, value, line, column, raw))

            elif char.isdigit():
                num_start = self.pos
                number = self.read_number()
                num_raw = self.text[num_start : self.pos]
                tokens.append(Token(TokenType.NUMBER, number, line, column, num_raw))

            elif char.isalpha() or char in "_":
                id_start = self.pos
                identifier = self.read_identifier()
                id_raw = self.text[id_start : self.pos]
                tokens.append(
                    Token(TokenType.IDENTIFIER, identifier, line, column, id_raw)
                )

            else:
                # Preserve other characters (like -, ., /) as single-char identifiers
                # This allows field values to contain these characters
                char_token = Token(TokenType.IDENTIFIER, char, line, column, char)
                tokens.append(char_token)
                self.advance()

        tokens.append(Token(TokenType.EOF, "", self.line, self.column, ""))
        return tokens


class BibtexParser:
    """BibTeX parser with error recovery and format preservation."""

    def __init__(self):
        self.tokens: list[Token] = []
        self.pos = 0
        self.entries: list[Entry] = []
        self.errors: list[ParseError] = []
        self.string_defs: dict[str, str] = {}
        self.metadata: FormatMetadata | None = None
        self._entry_cache: dict[str, Entry] = {}

    def current_token(self) -> Token:
        if self.pos >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[self.pos]

    def peek_token(self, offset: int = 1) -> Token:
        pos = self.pos + offset
        if pos >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[pos]

    def advance(self) -> Token:
        token = self.current_token()
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return token

    def skip_whitespace(self):
        """Skip whitespace and comments, preserving if needed."""
        while self.current_token().type in {
            TokenType.WHITESPACE,
            TokenType.NEWLINE,
            TokenType.LINE_COMMENT,
        }:
            if self.metadata and self.current_token().type == TokenType.LINE_COMMENT:
                token = self.current_token()
                self.metadata.comments.append((token.line, token.value))
            self.advance()

    def expect(self, token_type: TokenType) -> Token:
        """Expect a specific token type."""
        self.skip_whitespace()
        token = self.current_token()
        if token.type != token_type:
            self.error(
                f"Expected {token_type.name}, got {token.type.name}", severity="error"
            )
            return token
        return self.advance()

    def error(self, message: str, severity: str = "error", recover: bool = True):
        """Record parse error."""
        token = self.current_token()
        error = ParseError(message, token.line, token.column, severity)
        self.errors.append(error)

        if recover and severity == "error":
            self.recover()

    def recover(self):
        """Recover from parse error by finding next entry."""
        depth = 0
        while self.current_token().type != TokenType.EOF:
            token = self.current_token()

            if token.type == TokenType.LBRACE or token.type == TokenType.LPAREN:
                depth += 1
            elif token.type == TokenType.RBRACE or token.type == TokenType.RPAREN:
                depth -= 1
                if depth == 0:
                    self.advance()
                    break
            elif token.type == TokenType.AT and depth == 0:
                # Found start of next entry
                break

            self.advance()

    def parse(self, text: str) -> list[Entry]:
        """Parse BibTeX text."""
        self.entries = []
        self.errors = []
        self.string_defs = {}
        self._entry_cache = {}

        lexer = BibtexLexer(text, preserve_format=False)
        self.tokens = lexer.tokenize()
        self.pos = 0

        while self.current_token().type != TokenType.EOF:
            self.skip_whitespace()
            token = self.current_token()

            if token.type == TokenType.AT:
                self.advance()
                self.parse_at_command()
            elif token.type == TokenType.EOF:
                break
            else:
                self.advance()

        return self.entries

    def parse_with_preservation(self, text: str) -> tuple[list[Entry], FormatMetadata]:
        """Parse BibTeX preserving formatting information."""
        self.metadata = FormatMetadata()
        self.metadata.original_text = text

        lexer = BibtexLexer(text, preserve_format=True)
        self.tokens = lexer.tokenize()
        self.pos = 0

        self.entries = []
        self.errors = []
        self.string_defs = {}

        while self.current_token().type != TokenType.EOF:
            token = self.current_token()

            if token.type == TokenType.AT:
                self.advance()
                self.parse_at_command()
            elif token.type in {TokenType.WHITESPACE, TokenType.NEWLINE}:
                self.advance()
            elif token.type == TokenType.LINE_COMMENT:
                self.metadata.comments.append((token.line, token.value))
                self.advance()
            elif token.type == TokenType.EOF:
                break
            else:
                self.advance()

        return self.entries, self.metadata

    def parse_at_command(self):
        """Parse @ command (entry, string, comment, preamble)."""
        token = self.current_token()

        if token.type == TokenType.ENTRY_TYPE:
            self.parse_entry()
        elif token.type == TokenType.STRING_DEF:
            self.parse_string_def()
        elif token.type == TokenType.COMMENT:
            self.parse_comment()
        elif token.type == TokenType.PREAMBLE:
            self.parse_preamble()
        else:
            self.error(f"Unexpected token after @: {token.type.name}")

    def parse_entry(self):
        """Parse bibliography entry."""
        entry_token = self.advance()
        entry_type_str = entry_token.value.lower()

        # Map to EntryType
        try:
            entry_type = EntryType(entry_type_str)
        except ValueError:
            # Unknown type - use MISC
            entry_type = EntryType.MISC
            self.error(f"Unknown entry type: {entry_type_str}", severity="warning")

        self.skip_whitespace()

        # Get opening delimiter
        delimiter = self.current_token()
        if delimiter.type not in {TokenType.LBRACE, TokenType.LPAREN}:
            self.error("Expected { or ( after entry type")
            return

        closing = (
            TokenType.RBRACE if delimiter.type == TokenType.LBRACE else TokenType.RPAREN
        )
        self.advance()

        self.skip_whitespace()

        # Get citation key
        if self.current_token().type != TokenType.IDENTIFIER:
            # Handle missing key
            if self.current_token().type == TokenType.COMMA:
                # Key is missing, generate one
                key = f"entry_{len(self.entries) + 1}"
                self.error(
                    "Missing citation key, using generated key", severity="warning"
                )
            else:
                self.error("Expected citation key")
                return
        else:
            key = self.advance().value

        # Check for duplicate key
        if key in self._entry_cache:
            self.error(f"Duplicate key: {key}", severity="warning")

        self.skip_whitespace()

        # Expect comma
        if self.current_token().type == TokenType.COMMA:
            self.advance()
        else:
            self.error("Expected comma after citation key", severity="warning")

        # Parse fields
        fields = self.parse_fields(closing)

        # Create entry
        try:
            entry = Entry(key=key, type=entry_type, **self.process_fields(fields))
            self.entries.append(entry)
            self._entry_cache[key] = entry

        except Exception as e:
            self.error(f"Failed to create entry: {e}", recover=False)

    def parse_fields(self, closing: TokenType) -> dict[str, str]:
        """Parse entry fields."""
        fields = {}

        while True:
            self.skip_whitespace()

            if self.current_token().type == closing:
                self.advance()
                break
            elif self.current_token().type == TokenType.EOF:
                self.error("Unexpected end of file in entry")
                break

            # Get field name
            if self.current_token().type != TokenType.IDENTIFIER:
                if self.current_token().type == TokenType.COMMA:
                    self.advance()
                    continue
                self.error(f"Expected field name, got {self.current_token().type.name}")
                break

            field_name = self.advance().value.lower()

            self.skip_whitespace()

            # Expect equals
            if self.current_token().type != TokenType.EQUALS:
                self.error(f"Expected = after field name '{field_name}'")
                continue
            self.advance()

            self.skip_whitespace()

            # Parse field value
            value = self.parse_field_value()
            if value is not None:
                fields[field_name] = value

            self.skip_whitespace()

            # Check for comma or closing
            if self.current_token().type == TokenType.COMMA:
                self.advance()
            elif self.current_token().type == closing:
                continue  # Will break on next iteration
            else:
                self.error("Expected comma or closing delimiter", severity="warning")

        return fields

    def parse_field_value(self) -> str | None:
        """Parse field value with concatenation support."""
        parts = []

        while True:
            token = self.current_token()

            if token.type == TokenType.STRING:
                parts.append(token.value)
                self.advance()

            elif token.type == TokenType.NUMBER:
                parts.append(token.value)
                self.advance()

            elif token.type == TokenType.IDENTIFIER:
                # Could be string reference
                if token.value in self.string_defs:
                    parts.append(self.string_defs[token.value])
                else:
                    parts.append(token.value)
                self.advance()

            elif token.type == TokenType.LBRACE:
                # Braced value
                value, _ = self.read_braced_value()
                parts.append(value)

            else:
                break

            self.skip_whitespace()

            # Check for concatenation
            if self.current_token().type == TokenType.CONCAT:
                self.advance()
                self.skip_whitespace()
            else:
                break

        if parts:
            return "".join(parts)
        return None

    def read_braced_value(self) -> tuple[str, str]:
        """Read braced field value."""
        if self.current_token().type != TokenType.LBRACE:
            return "", ""

        raw_parts = []
        value_parts = []
        depth = 0

        while self.current_token().type != TokenType.EOF:
            token = self.current_token()

            if token.type == TokenType.LBRACE:
                depth += 1
                if depth > 1:
                    value_parts.append(token.value)
                raw_parts.append(token.raw)

            elif token.type == TokenType.RBRACE:
                depth -= 1
                if depth > 0:
                    value_parts.append(token.value)
                raw_parts.append(token.raw)
                if depth == 0:
                    self.advance()
                    break

            else:
                # For identifiers, check if we need spacing
                if (
                    token.type == TokenType.IDENTIFIER
                    and len(token.value) > 1
                    and value_parts
                ):
                    # Multi-char identifier needs space before it
                    last = value_parts[-1] if value_parts else ""
                    if last and last[-1].isalnum():
                        value_parts.append(" ")
                value_parts.append(token.value)
                raw_parts.append(token.raw if token.raw else token.value)

            self.advance()

        return "".join(value_parts), "".join(raw_parts)

    def parse_string_def(self):
        """Parse @string definition."""
        self.advance()  # Skip 'string'
        self.skip_whitespace()

        # Get delimiter
        delimiter = self.current_token()
        if delimiter.type not in {TokenType.LBRACE, TokenType.LPAREN}:
            self.error("Expected { or ( after @string")
            return

        closing = (
            TokenType.RBRACE if delimiter.type == TokenType.LBRACE else TokenType.RPAREN
        )
        self.advance()

        self.skip_whitespace()

        # Get name
        if self.current_token().type != TokenType.IDENTIFIER:
            self.error("Expected string name")
            return

        name = self.advance().value

        self.skip_whitespace()

        # Expect equals
        if self.current_token().type != TokenType.EQUALS:
            self.error("Expected = after string name")
            return
        self.advance()

        self.skip_whitespace()

        # Get value
        value = self.parse_field_value()
        if value:
            self.string_defs[name] = value
            if self.metadata:
                self.metadata.string_defs[name] = value

        self.skip_whitespace()

        # Expect closing
        if self.current_token().type == closing:
            self.advance()

    def parse_comment(self):
        """Parse @comment block."""
        self.advance()  # Skip 'comment'
        self.skip_block()

    def parse_preamble(self):
        """Parse @preamble block."""
        self.advance()  # Skip 'preamble'

        # Store preamble content if preserving
        if self.metadata:
            content = self.read_block_content()
            if content:
                self.metadata.preambles.append(content)
        else:
            self.skip_block()

    def skip_block(self):
        """Skip a block (comment or preamble)."""
        self.skip_whitespace()

        if self.current_token().type in {TokenType.LBRACE, TokenType.LPAREN}:
            opening = self.current_token().type
            closing = (
                TokenType.RBRACE if opening == TokenType.LBRACE else TokenType.RPAREN
            )
            self.advance()

            depth = 1
            while self.current_token().type != TokenType.EOF and depth > 0:
                if self.current_token().type == opening:
                    depth += 1
                elif self.current_token().type == closing:
                    depth -= 1
                self.advance()

    def read_block_content(self) -> str:
        """Read content of a block for preservation."""
        self.skip_whitespace()

        if self.current_token().type in {TokenType.LBRACE, TokenType.LPAREN}:
            opening = self.current_token().type
            closing = (
                TokenType.RBRACE if opening == TokenType.LBRACE else TokenType.RPAREN
            )
            self.advance()

            parts = []
            depth = 1

            while self.current_token().type != TokenType.EOF and depth > 0:
                token = self.current_token()

                if token.type == opening:
                    depth += 1
                    if depth > 1:
                        parts.append(token.value)
                elif token.type == closing:
                    depth -= 1
                    if depth > 0:
                        parts.append(token.value)
                else:
                    parts.append(token.value)

                self.advance()

            return "".join(parts)

        return ""

    def process_fields(self, fields: dict[str, str]) -> dict[str, Any]:
        """Process fields for Entry creation."""
        processed = {}

        for key, value in fields.items():
            # Convert year to int
            if key == "year":
                try:
                    processed["year"] = int(value)
                except ValueError:
                    # Extract year from string
                    import re

                    match = re.search(r"\d{4}", value)
                    if match:
                        processed["year"] = int(match.group())
                    else:
                        processed["year"] = None
            else:
                processed[key] = value

        return processed

    def parse_file(self, path: Path) -> list[Entry]:
        """Parse BibTeX file."""
        try:
            with open(path, encoding="utf-8") as f:
                return self.parse(f.read())
        except UnicodeDecodeError:
            # Try with latin-1
            try:
                with open(path, encoding="latin-1") as f:
                    return self.parse(f.read())
            except Exception as e:
                raise ParseError(f"Failed to read file: {e}", 0, 0)
        except Exception as e:
            raise ParseError(f"Failed to read file: {e}", 0, 0)

    def parse_stream(self, stream: TextIO) -> Iterator[Entry]:
        """Parse BibTeX from stream, yielding entries as found."""
        buffer = ""
        in_entry = False
        brace_depth = 0

        for line in stream:
            buffer += line

            # Track entry boundaries
            if "@" in line and not in_entry:
                in_entry = True
                brace_depth = 0

            if in_entry:
                brace_depth += line.count("{") - line.count("}")

                # Complete entry found
                if brace_depth == 0 and "{" in buffer:
                    entries = self.parse(buffer)
                    for entry in entries:
                        yield entry
                    buffer = ""
                    in_entry = False

        # Parse any remaining buffer
        if buffer.strip():
            entries = self.parse(buffer)
            for entry in entries:
                yield entry
