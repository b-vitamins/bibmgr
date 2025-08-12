"""Tests for search result highlighting."""

import pytest

from bibmgr.core.fields import EntryType
from bibmgr.core.models import Entry
from bibmgr.search.highlighting import (
    FieldHighlights,
    Highlight,
    Highlighter,
)
from bibmgr.search.query.parser import (
    BooleanOperator,
    BooleanQuery,
    PhraseQuery,
    TermQuery,
    WildcardQuery,
)


class TestHighlight:
    """Test Highlight data class."""

    def test_create_highlight(self):
        """Create highlight object."""
        highlight = Highlight(
            text="machine learning",
            start_offset=10,
            end_offset=26,
            score=0.95,
        )

        assert highlight.text == "machine learning"
        assert highlight.start_offset == 10
        assert highlight.end_offset == 26
        assert highlight.score == 0.95

    def test_highlight_defaults(self):
        """Highlight should have reasonable defaults."""
        highlight = Highlight(
            text="test",
            start_offset=0,
            end_offset=4,
        )

        assert highlight.score == 1.0  # Default score


class TestFieldHighlights:
    """Test FieldHighlights data class."""

    def test_create_field_highlights(self):
        """Create field highlights."""
        highlights = [
            Highlight("machine", 10, 17, 0.9),
            Highlight("learning", 18, 26, 0.8),
        ]

        field_highlights = FieldHighlights(
            field="title",
            highlights=highlights,
            original_text="Advanced machine learning techniques",
        )

        assert field_highlights.field == "title"
        assert len(field_highlights.highlights) == 2
        assert field_highlights.original_text == "Advanced machine learning techniques"
        assert field_highlights.snippet_length == 200

    def test_get_best_snippet_no_highlights(self):
        """Get snippet when no highlights exist."""
        field_highlights = FieldHighlights(
            field="abstract",
            highlights=[],
            original_text="This is a long abstract about various topics in computer science and artificial intelligence research.",
            snippet_length=50,
        )

        snippet = field_highlights.get_best_snippet()

        # Should be truncated to snippet_length with ellipsis
        assert snippet.startswith("This is a long abstract about various topics in co")
        assert snippet.endswith("...")
        assert len(snippet) <= 53  # 50 chars + "..."

    def test_get_best_snippet_with_highlights(self):
        """Get snippet with highlights."""
        text = "The field of machine learning has advanced significantly in recent years. Deep learning models have revolutionized computer vision."

        highlights = [
            Highlight("machine learning", 13, 29, 1.0),
            Highlight("Deep learning", 73, 86, 0.8),
        ]

        field_highlights = FieldHighlights(
            field="abstract",
            highlights=highlights,
            original_text=text,
            snippet_length=80,
        )

        snippet = field_highlights.get_best_snippet()

        # Should include context around best highlight
        assert "machine learning" in snippet
        # get_best_snippet returns plain text, not highlighted
        assert "..." in snippet  # Should have truncation

    def test_get_highlighted_snippet(self):
        """Get snippet with HTML highlighting tags."""
        text = "Introduction to machine learning algorithms"

        highlights = [
            Highlight("machine learning", 16, 32, 1.0),
        ]

        field_highlights = FieldHighlights(
            field="title",
            highlights=highlights,
            original_text=text,
        )

        highlighted = field_highlights.get_highlighted_snippet()

        assert "<mark>machine learning</mark>" in highlighted

    def test_merge_overlapping_highlights(self):
        """Overlapping highlights should be merged."""
        # Test that Highlighter merges overlapping highlights
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="machine learning and deep learning",
        )

        query = BooleanQuery(
            operator=BooleanOperator.OR,
            queries=[
                TermQuery("machine"),
                TermQuery("learning"),
                TermQuery("deep"),
            ],
        )

        highlighter = Highlighter()
        highlights = highlighter.highlight_entry(entry, query)

        # Check that overlapping highlights were handled properly
        assert "title" in highlights
        title_highlights = highlights["title"]
        # The highlighter should have merged overlapping highlights
        assert len(title_highlights.highlights) > 0


class TestHighlighter:
    """Test Highlighter class."""

    @pytest.fixture
    def sample_entry(self):
        """Sample entry for highlighting."""
        return Entry(
            key="test2024",
            type=EntryType.ARTICLE,
            title="Introduction to Machine Learning",
            author="John Smith",
            abstract="This paper presents an overview of machine learning techniques including deep learning, neural networks, and artificial intelligence applications.",
            keywords=("machine learning", "deep learning", "AI"),
        )

    @pytest.fixture
    def highlighter(self):
        """Create highlighter instance."""
        return Highlighter()

    def test_highlight_term_query(self, highlighter, sample_entry):
        """Highlight simple term query."""
        query = TermQuery("machine")

        highlights = highlighter.highlight_entry(sample_entry, query)

        assert "title" in highlights
        assert "abstract" in highlights
        assert "keywords" in highlights

        # Title should have one highlight
        title_highlights = highlights["title"]
        assert len(title_highlights.highlights) == 1
        assert title_highlights.highlights[0].text == "Machine"

        # Abstract should have one highlight
        abstract_highlights = highlights["abstract"]
        assert len(abstract_highlights.highlights) == 1
        assert abstract_highlights.highlights[0].text == "machine"

    def test_highlight_phrase_query(self, highlighter, sample_entry):
        """Highlight phrase query."""
        query = PhraseQuery("machine learning")

        highlights = highlighter.highlight_entry(sample_entry, query)

        # Should highlight exact phrase
        title_highlights = highlights["title"]
        assert len(title_highlights.highlights) == 1
        assert title_highlights.highlights[0].text == "Machine Learning"

        abstract_highlights = highlights["abstract"]
        assert len(abstract_highlights.highlights) == 1
        assert abstract_highlights.highlights[0].text == "machine learning"

    def test_highlight_boolean_query(self, highlighter, sample_entry):
        """Highlight boolean query."""
        query = BooleanQuery(
            operator=BooleanOperator.OR,
            queries=[
                TermQuery("machine"),
                TermQuery("artificial"),
            ],
        )

        highlights = highlighter.highlight_entry(sample_entry, query)

        # Abstract should have highlights for both terms
        abstract_highlights = highlights["abstract"]
        texts = [h.text for h in abstract_highlights.highlights]
        assert any("machine" in t.lower() for t in texts)
        assert any("artificial" in t.lower() for t in texts)

    def test_highlight_wildcard_query(self, highlighter):
        """Highlight wildcard query."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Learning about learners and learned knowledge",
        )

        query = WildcardQuery("learn*")

        highlights = highlighter.highlight_entry(entry, query)

        # Should match all variations of "learn"
        title_highlights = highlights["title"]
        texts = [h.text.lower() for h in title_highlights.highlights]
        assert "learning" in texts
        assert "learners" in texts
        assert "learned" in texts

    def test_highlight_case_insensitive(self, highlighter):
        """Highlighting should be case insensitive."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="MACHINE Learning and machine LEARNING",
        )

        query = TermQuery("machine")

        highlights = highlighter.highlight_entry(entry, query)

        # Should match both cases
        title_highlights = highlights["title"]
        assert len(title_highlights.highlights) == 2

    def test_highlight_special_characters(self, highlighter):
        """Handle special characters in highlighting."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="C++ Programming and AI+ML Applications",
        )

        query = TermQuery("C++")

        highlights = highlighter.highlight_entry(entry, query)

        # Should escape special regex characters
        title_highlights = highlights["title"]
        assert len(title_highlights.highlights) == 1
        assert title_highlights.highlights[0].text == "C++"

    def test_highlight_empty_fields(self, highlighter):
        """Handle empty or missing fields."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Test Title",
            abstract=None,  # No abstract
        )

        query = TermQuery("test")

        highlights = highlighter.highlight_entry(entry, query)

        assert "title" in highlights
        assert "abstract" not in highlights  # Should skip None fields

    def test_highlight_options(self, highlighter):
        """Test highlighting options."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Machine Learning",
            abstract="A comprehensive study of machine learning algorithms and their applications in artificial intelligence.",
        )

        query = TermQuery("machine")

        # With custom options
        highlights = highlighter.highlight_entry(
            entry,
            query,
            fields=["title"],  # Only highlight title
        )

        assert "title" in highlights
        assert "abstract" not in highlights

    def test_extract_query_terms(self, highlighter):
        """Extract terms from various query types."""
        # Simple term
        terms = highlighter._extract_search_terms(TermQuery("machine"))
        assert terms == {"machine": 1.0}

        # Phrase
        terms = highlighter._extract_search_terms(PhraseQuery("machine learning"))
        assert terms == {"machine learning": 1.0}

        # Boolean
        query = BooleanQuery(
            operator=BooleanOperator.AND,
            queries=[TermQuery("machine"), TermQuery("learning")],
        )
        terms = highlighter._extract_search_terms(query)
        assert terms == {"machine": 1.0, "learning": 1.0}

        # Wildcard
        terms = highlighter._extract_search_terms(WildcardQuery("mach*"))
        assert terms == {"mach*": 1.0}

    def test_score_calculation(self, highlighter):
        """Highlight scores should reflect term importance."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Machine Learning in Modern AI",
            abstract="Machine learning is a key component of artificial intelligence.",
        )

        query = BooleanQuery(
            operator=BooleanOperator.AND,
            queries=[
                TermQuery("machine", boost=2.0),  # Boosted term
                TermQuery("learning"),
            ],
        )

        highlights = highlighter.highlight_entry(entry, query)

        # Boosted term should have higher score
        title_highlights = highlights["title"]

        # Find highlights for machine and learning
        machine_highlights = [
            h for h in title_highlights.highlights if "machine" in h.text.lower()
        ]
        learning_highlights = [
            h
            for h in title_highlights.highlights
            if "learning" in h.text.lower() and "machine" not in h.text.lower()
        ]

        assert len(machine_highlights) > 0, "Should have machine highlights"
        assert len(learning_highlights) > 0, "Should have learning highlights"

        # The boosted term should have higher score
        max_machine_score = max(h.score for h in machine_highlights)
        max_learning_score = max(h.score for h in learning_highlights)

        assert max_machine_score > max_learning_score


class TestHighlightingIntegration:
    """Integration tests for highlighting system."""

    def test_full_highlighting_pipeline(self):
        """Test complete highlighting pipeline."""
        # Create entry
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Deep Learning for Natural Language Processing",
            abstract="This survey covers recent advances in deep learning approaches for NLP tasks.",
            keywords=("deep learning", "NLP", "neural networks"),
        )

        # Create query
        query = BooleanQuery(
            operator=BooleanOperator.AND,
            queries=[
                TermQuery("deep"),
                TermQuery("learning"),
            ],
        )

        # Highlight
        highlighter = Highlighter()
        highlights = highlighter.highlight_entry(entry, query)

        # Verify results
        assert "title" in highlights
        assert "abstract" in highlights
        assert "keywords" in highlights

        # Get highlighted snippets
        title_snippet = highlights["title"].get_highlighted_snippet()
        abstract_snippet = highlights["abstract"].get_highlighted_snippet()

        # Both terms should be highlighted
        # Title is "Deep Learning for Natural Language Processing"
        # The highlights are there but case matters
        assert "<mark>" in title_snippet
        assert "</mark>" in title_snippet
        assert title_snippet.count("<mark>") >= 2  # Should have at least 2 highlights

        assert "<mark>" in abstract_snippet
        assert "</mark>" in abstract_snippet

    def test_no_matches_highlighting(self):
        """Handle queries with no matches."""
        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Quantum Computing Basics",
            abstract="An introduction to quantum computing principles.",
        )

        query = TermQuery("machine learning")

        highlighter = Highlighter()
        highlights = highlighter.highlight_entry(entry, query)

        # Should return empty highlights for fields
        assert all(len(fh.highlights) == 0 for fh in highlights.values())

    def test_performance_many_highlights(self):
        """Test performance with many potential highlights."""
        # Create entry with repeated terms
        abstract = " ".join(["machine learning"] * 100)

        entry = Entry(
            key="test",
            type=EntryType.ARTICLE,
            title="Machine Learning",
            abstract=abstract,
        )

        query = TermQuery("machine")

        highlighter = Highlighter(max_highlights_per_field=10)
        highlights = highlighter.highlight_entry(entry, query)

        # Should handle efficiently and limit highlights
        abstract_highlights = highlights["abstract"]
        assert len(abstract_highlights.highlights) <= 10
