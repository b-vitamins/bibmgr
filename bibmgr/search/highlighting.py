"""Search result highlighting and snippet generation."""

import re
from dataclasses import dataclass

from ..core.models import Entry as BibEntry
from .query.parser import (
    BooleanQuery,
    FieldQuery,
    FuzzyQuery,
    ParsedQuery,
    PhraseQuery,
    TermQuery,
    WildcardQuery,
)


@dataclass
class Highlight:
    """Individual highlight fragment."""

    text: str
    start_offset: int
    end_offset: int
    score: float = 1.0  # Relevance score of this highlight


@dataclass
class FieldHighlights:
    """Highlights for a specific field."""

    field: str
    highlights: list[Highlight]
    original_text: str
    snippet_length: int = 200

    def get_best_snippet(self) -> str:
        """Get the best highlighted snippet for display."""
        if not self.highlights:
            text = self.original_text[: self.snippet_length]
            if len(self.original_text) > self.snippet_length:
                text += "..."
            return text

        best_highlight = max(self.highlights, key=lambda h: h.score)

        start = max(0, best_highlight.start_offset - self.snippet_length // 2)
        end = min(len(self.original_text), start + self.snippet_length)

        if end == len(self.original_text) and end - start < self.snippet_length:
            start = max(0, end - self.snippet_length)

        snippet = self.original_text[start:end]

        if start > 0:
            snippet = "..." + snippet
        if end < len(self.original_text):
            snippet = snippet + "..."

        return snippet

    def get_highlighted_snippet(self, highlight_tag: str = "mark") -> str:
        """Get snippet with HTML highlighting tags."""
        if len(self.original_text) <= self.snippet_length:
            return self._apply_highlights_to_text(self.original_text, highlight_tag)

        snippet_text = self.get_best_snippet()
        clean_snippet = snippet_text.strip("...")
        snippet_start_in_original = self.original_text.find(clean_snippet)

        if snippet_start_in_original == -1:
            return snippet_text

        snippet_end_in_original = snippet_start_in_original + len(clean_snippet)
        snippet_highlights = []

        for h in self.highlights:
            if (
                h.start_offset >= snippet_start_in_original
                and h.end_offset <= snippet_end_in_original
            ):
                adjusted_highlight = Highlight(
                    text=h.text,
                    start_offset=h.start_offset - snippet_start_in_original,
                    end_offset=h.end_offset - snippet_start_in_original,
                    score=h.score,
                )
                snippet_highlights.append(adjusted_highlight)

        highlighted_snippet = self._apply_highlights_to_text(
            clean_snippet, highlight_tag, snippet_highlights
        )

        if snippet_text.startswith("..."):
            highlighted_snippet = "..." + highlighted_snippet
        if snippet_text.endswith("..."):
            highlighted_snippet = highlighted_snippet + "..."

        return highlighted_snippet

    def _apply_highlights_to_text(
        self, text: str, highlight_tag: str, highlights: list[Highlight] | None = None
    ) -> str:
        """Apply highlights to text with HTML tags."""
        if highlights is None:
            highlights = self.highlights

        if not highlights:
            return text

        sorted_highlights = sorted(
            highlights, key=lambda h: h.start_offset, reverse=True
        )

        result = text
        for highlight in sorted_highlights:
            if 0 <= highlight.start_offset < len(
                result
            ) and highlight.end_offset <= len(result):
                highlighted_text = f"<{highlight_tag}>{result[highlight.start_offset : highlight.end_offset]}</{highlight_tag}>"
                result = (
                    result[: highlight.start_offset]
                    + highlighted_text
                    + result[highlight.end_offset :]
                )

        return result


class Highlighter:
    """Generates highlights for search results."""

    def __init__(
        self,
        max_highlights_per_field: int = 3,
        snippet_length: int = 200,
        highlight_tag: str = "mark",
    ):
        """Initialize highlighter.

        Args:
            max_highlights_per_field: Maximum highlights to generate per field
            snippet_length: Length of text snippets
            highlight_tag: HTML tag to use for highlights
        """
        self.max_highlights_per_field = max_highlights_per_field
        self.snippet_length = snippet_length
        self.highlight_tag = highlight_tag

    def highlight_entry(
        self, entry: BibEntry, query: ParsedQuery, fields: list[str] | None = None
    ) -> dict[str, FieldHighlights]:
        """Generate highlights for an entry based on a query.

        Args:
            entry: Bibliography entry to highlight
            query: Parsed search query
            fields: Optional list of fields to highlight (default: all text fields)

        Returns:
            Dictionary mapping field names to their highlights
        """
        if fields is None:
            fields = ["title", "abstract", "author", "keywords", "note"]

        search_terms = self._extract_search_terms(query)
        field_highlights = {}

        for field_name in fields:
            field_value = getattr(entry, field_name, None)
            if field_value is not None:
                field_text = str(field_value)
                highlights = self._find_highlights(field_text, search_terms)

                if highlights:
                    field_highlights[field_name] = FieldHighlights(
                        field=field_name,
                        highlights=highlights,
                        original_text=field_text,
                        snippet_length=self.snippet_length,
                    )

        return field_highlights

    def highlight_text(
        self, text: str, query: ParsedQuery, field_name: str = "text"
    ) -> FieldHighlights:
        """Highlight a single text field.

        Args:
            text: Text to highlight
            query: Parsed search query
            field_name: Name of the field for context

        Returns:
            FieldHighlights object
        """
        search_terms = self._extract_search_terms(query)
        highlights = self._find_highlights(text, search_terms)

        return FieldHighlights(
            field=field_name,
            highlights=highlights,
            original_text=text,
            snippet_length=self.snippet_length,
        )

    def _extract_search_terms(self, query: ParsedQuery) -> dict[str, float]:
        """Extract search terms from parsed query with their boost values."""
        terms = {}

        def extract_terms_recursive(q: ParsedQuery):
            if isinstance(q, TermQuery):
                terms[q.term.lower()] = q.boost
            elif isinstance(q, PhraseQuery):
                terms[q.phrase.lower()] = q.boost
            elif isinstance(q, FieldQuery):
                extract_terms_recursive(q.query)
            elif isinstance(q, BooleanQuery):
                for subquery in q.queries:
                    extract_terms_recursive(subquery)
            elif isinstance(q, WildcardQuery):
                terms[q.pattern.lower()] = q.boost
            elif isinstance(q, FuzzyQuery):
                terms[q.term.lower()] = q.boost

        extract_terms_recursive(query)
        return terms

    def _find_highlights(
        self, text: str, search_terms: dict[str, float]
    ) -> list[Highlight]:
        """Find highlight positions in text for given search terms with boost values."""
        if not text or not search_terms:
            return []

        text_lower = text.lower()
        highlights = []

        wildcard_patterns = {
            term: boost
            for term, boost in search_terms.items()
            if "*" in term or "?" in term
        }
        regular_terms = {
            term: boost
            for term, boost in search_terms.items()
            if term not in wildcard_patterns
        }

        for term, boost in regular_terms.items():
            if not term.strip():
                continue

            if " " in term:
                highlights.extend(
                    self._find_phrase_highlights(text, text_lower, term, boost)
                )
            else:
                highlights.extend(
                    self._find_term_highlights(text, text_lower, term, boost)
                )

        for pattern, boost in wildcard_patterns.items():
            highlights.extend(
                self._find_wildcard_highlights(text, text_lower, pattern, boost)
            )

        highlights = self._merge_overlapping_highlights(highlights)
        highlights.sort(key=lambda h: h.start_offset)

        return highlights[: self.max_highlights_per_field]

    def _find_phrase_highlights(
        self, text: str, text_lower: str, phrase: str, boost: float = 1.0
    ) -> list[Highlight]:
        """Find highlights for phrase queries."""
        highlights = []
        phrase_lower = phrase.lower()

        start = 0
        while True:
            pos = text_lower.find(phrase_lower, start)
            if pos == -1:
                break

            end_pos = pos + len(phrase)
            actual_text = text[pos:end_pos]

            highlight = Highlight(
                text=actual_text,
                start_offset=pos,
                end_offset=end_pos,
                score=2.0 * boost,
            )
            highlights.append(highlight)
            start = pos + 1

        return highlights

    def _find_term_highlights(
        self, text: str, text_lower: str, term: str, boost: float = 1.0
    ) -> list[Highlight]:
        """Find highlights for single term queries."""
        highlights = []
        term_lower = term.lower()

        word_pattern = r"\b" + re.escape(term_lower) + r"\b"
        for match in re.finditer(word_pattern, text_lower):
            actual_text = text[match.start() : match.end()]
            highlight = Highlight(
                text=actual_text,
                start_offset=match.start(),
                end_offset=match.end(),
                score=1.5 * boost,
            )
            highlights.append(highlight)

        if not highlights:
            start = 0
            while True:
                pos = text_lower.find(term_lower, start)
                if pos == -1:
                    break

                end_pos = pos + len(term)
                actual_text = text[pos:end_pos]

                highlight = Highlight(
                    text=actual_text,
                    start_offset=pos,
                    end_offset=end_pos,
                    score=1.0 * boost,
                )
                highlights.append(highlight)
                start = pos + 1

        return highlights

    def _find_wildcard_highlights(
        self, text: str, text_lower: str, pattern: str, boost: float = 1.0
    ) -> list[Highlight]:
        """Find highlights for wildcard patterns."""
        highlights = []
        pattern_lower = pattern.lower()

        regex_pattern = pattern_lower.replace("*", "\\w*").replace("?", "\\w")
        regex_pattern = r"\b" + regex_pattern + r"\b"

        try:
            for match in re.finditer(regex_pattern, text_lower):
                actual_text = text[match.start() : match.end()]
                highlight = Highlight(
                    text=actual_text,
                    start_offset=match.start(),
                    end_offset=match.end(),
                    score=1.3 * boost,
                )
                highlights.append(highlight)
        except re.error:
            prefix = pattern_lower.rstrip("*?")
            if prefix:
                start = 0
                while True:
                    pos = text_lower.find(prefix, start)
                    if pos == -1:
                        break

                    end_pos = pos + len(prefix)
                    while end_pos < len(text_lower) and text_lower[end_pos].isalnum():
                        end_pos += 1

                    actual_text = text[pos:end_pos]
                    highlight = Highlight(
                        text=actual_text,
                        start_offset=pos,
                        end_offset=end_pos,
                        score=1.3 * boost,
                    )
                    highlights.append(highlight)
                    start = pos + 1

        return highlights

    def _merge_overlapping_highlights(
        self, highlights: list[Highlight]
    ) -> list[Highlight]:
        """Merge overlapping or adjacent highlights."""
        if not highlights:
            return []

        sorted_highlights = sorted(highlights, key=lambda h: h.start_offset)
        merged = []
        current = sorted_highlights[0]

        for next_highlight in sorted_highlights[1:]:
            if next_highlight.start_offset < current.end_offset:
                merged_text = current.text
                if next_highlight.end_offset > current.end_offset:
                    max(current.end_offset, next_highlight.end_offset)

                current = Highlight(
                    text=merged_text,
                    start_offset=current.start_offset,
                    end_offset=max(current.end_offset, next_highlight.end_offset),
                    score=max(current.score, next_highlight.score),
                )
            else:
                merged.append(current)
                current = next_highlight

        merged.append(current)
        return merged

    def create_snippet(
        self, text: str, highlights: list[Highlight], max_length: int | None = None
    ) -> str:
        """Create a text snippet containing the most relevant highlights.

        Args:
            text: Original text
            highlights: List of highlights in the text
            max_length: Maximum length of snippet (default: use instance setting)

        Returns:
            Text snippet with context around highlights
        """
        if max_length is None:
            max_length = self.snippet_length

        if not highlights:
            snippet = text[:max_length]
            if len(text) > max_length:
                snippet += "..."
            return snippet

        best_start, best_end = self._find_best_highlight_cluster(highlights, max_length)

        actual_start = max(0, best_start - (max_length - (best_end - best_start)) // 2)
        actual_end = min(len(text), actual_start + max_length)

        if actual_end == len(text) and actual_end - actual_start < max_length:
            actual_start = max(0, actual_end - max_length)

        snippet = text[actual_start:actual_end]

        if actual_start > 0:
            snippet = "..." + snippet
        if actual_end < len(text):
            snippet = snippet + "..."

        return snippet

    def _find_best_highlight_cluster(
        self, highlights: list[Highlight], max_length: int
    ) -> tuple[int, int]:
        """Find the best cluster of highlights within max_length characters."""
        if not highlights:
            return (0, 0)

        if len(highlights) == 1:
            h = highlights[0]
            return (h.start_offset, h.end_offset)

        best_score = 0
        best_start = highlights[0].start_offset
        best_end = highlights[0].end_offset

        for i, start_highlight in enumerate(highlights):
            window_start = start_highlight.start_offset
            window_end = window_start + max_length

            window_highlights = [
                h
                for h in highlights
                if h.start_offset < window_end and h.end_offset > window_start
            ]

            window_score = sum(h.score for h in window_highlights)

            if window_score > best_score:
                best_score = window_score
                best_start = window_start
                best_end = min(window_end, max(h.end_offset for h in window_highlights))

        return (best_start, best_end)

    def apply_html_highlighting(
        self, text: str, highlights: list[Highlight], tag: str | None = None
    ) -> str:
        """Apply HTML highlighting tags to text.

        Args:
            text: Original text
            highlights: List of highlights to apply
            tag: HTML tag name (default: use instance setting)

        Returns:
            Text with HTML highlighting tags applied
        """
        if tag is None:
            tag = self.highlight_tag

        if not highlights:
            return text

        sorted_highlights = sorted(
            highlights, key=lambda h: h.start_offset, reverse=True
        )

        result = text
        for highlight in sorted_highlights:
            start = highlight.start_offset
            end = highlight.end_offset

            if start >= 0 and end <= len(result) and start < end:
                highlighted_text = f"<{tag}>{result[start:end]}</{tag}>"
                result = result[:start] + highlighted_text + result[end:]

        return result


class SnippetGenerator:
    """Specialized class for generating contextual snippets."""

    def __init__(self, snippet_length: int = 200):
        """Initialize snippet generator.

        Args:
            snippet_length: Default length for generated snippets
        """
        self.snippet_length = snippet_length

    def generate_snippet(
        self, text: str, query_terms: set[str], max_length: int | None = None
    ) -> str:
        """Generate a snippet showing context around matching terms.

        Args:
            text: Source text
            query_terms: Set of search terms to find
            max_length: Maximum snippet length

        Returns:
            Contextual snippet
        """
        if max_length is None:
            max_length = self.snippet_length

        if not text or not query_terms:
            return text[:max_length] + ("..." if len(text) > max_length else "")

        term_positions = []
        text_lower = text.lower()

        for term in query_terms:
            term_lower = term.lower()
            start = 0
            while True:
                pos = text_lower.find(term_lower, start)
                if pos == -1:
                    break
                term_positions.append((pos, pos + len(term), len(term)))
                start = pos + 1

        if not term_positions:
            return text[:max_length] + ("..." if len(text) > max_length else "")

        term_positions.sort()

        best_window = self._find_optimal_window(term_positions, max_length)

        start_pos = max(
            0, best_window[0] - (max_length - best_window[1] + best_window[0]) // 2
        )
        end_pos = min(len(text), start_pos + max_length)

        if end_pos == len(text):
            start_pos = max(0, end_pos - max_length)

        snippet = text[start_pos:end_pos]

        if start_pos > 0:
            snippet = "..." + snippet
        if end_pos < len(text):
            snippet = snippet + "..."

        return snippet

    def _find_optimal_window(
        self, term_positions: list[tuple[int, int, int]], max_length: int
    ) -> tuple[int, int]:
        """Find the optimal window containing the most/best term matches."""
        if not term_positions:
            return (0, 0)

        if len(term_positions) == 1:
            pos = term_positions[0]
            return (pos[0], pos[1])

        best_score = 0
        best_window = (term_positions[0][0], term_positions[0][1])

        for i, (start_pos, _, _) in enumerate(term_positions):
            window_end = start_pos + max_length

            window_terms = [
                pos
                for pos in term_positions
                if pos[1] > start_pos and pos[0] < window_end
            ]

            score = len(window_terms) + sum(pos[2] for pos in window_terms) * 0.1

            if score > best_score:
                best_score = score
                if window_terms:
                    best_window = (
                        window_terms[0][0],
                        min(window_end, window_terms[-1][1]),
                    )
                else:
                    best_window = (
                        start_pos,
                        min(len(term_positions), start_pos + max_length),
                    )

        return best_window
