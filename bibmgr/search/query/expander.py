"""Query expansion and spell checking for improved search recall.

This module provides query expansion capabilities including synonym expansion,
spell correction, and academic domain-specific enhancements to improve
search recall and handle user input variations.
"""

from dataclasses import dataclass

from ..indexing.analyzers import SpellChecker, SynonymExpander
from .parser import (
    BooleanOperator,
    BooleanQuery,
    FieldQuery,
    FuzzyQuery,
    ParsedQuery,
    PhraseQuery,
    TermQuery,
    WildcardQuery,
)


@dataclass
class QuerySuggestion:
    """Suggestion for query correction or expansion."""

    original_query: str
    suggested_query: str
    suggestion_type: str  # "spelling", "synonym", "expansion"
    confidence: float
    explanation: str


class QueryExpander:
    """Expands and corrects search queries for better recall.

    Provides functionality for:
    - Spell correction using dictionary and edit distance
    - Synonym expansion for academic terms
    - Query relaxation (AND -> OR for low results)
    - Field expansion (title -> title OR abstract)
    """

    def __init__(
        self,
        spell_checker: SpellChecker | None = None,
        synonym_expander: SynonymExpander | None = None,
    ):
        """Initialize query expander.

        Args:
            spell_checker: Optional custom spell checker
            synonym_expander: Optional custom synonym expander
        """
        self.spell_checker = spell_checker or SpellChecker()
        self.synonym_expander = synonym_expander or SynonymExpander()

        # Common field expansions for better recall
        self.field_expansions = {
            "title": ["title", "abstract"],
            "author": ["author", "editor"],
            "venue": ["journal", "booktitle", "publisher"],
            "content": ["title", "abstract", "keywords", "note"],
        }

        # Boost factors for expanded fields (original field gets 1.0)
        self.expansion_boosts = {
            "title": {"title": 1.0, "abstract": 0.5},
            "author": {"author": 1.0, "editor": 0.7},
            "venue": {"journal": 1.0, "booktitle": 0.9, "publisher": 0.6},
            "content": {"title": 1.0, "abstract": 0.8, "keywords": 0.6, "note": 0.4},
        }

    def expand_query(
        self,
        query: ParsedQuery,
        expand_synonyms: bool = True,
        expand_fields: bool = True,
        correct_spelling: bool = True,
    ) -> ParsedQuery:
        """Expand a query for better recall.

        Args:
            query: Original parsed query
            expand_synonyms: Whether to add synonym alternatives
            expand_fields: Whether to expand field queries to related fields
            correct_spelling: Whether to apply spelling correction

        Returns:
            Expanded query with better recall potential
        """
        expanded_query = query

        # Apply spelling correction first
        if correct_spelling:
            expanded_query = self._correct_spelling(expanded_query)

        # Expand synonyms
        if expand_synonyms:
            expanded_query = self._expand_synonyms(expanded_query)

        # Expand fields
        if expand_fields:
            expanded_query = self._expand_fields(expanded_query)

        return expanded_query

    def suggest_corrections(
        self, query: ParsedQuery, max_suggestions: int = 3
    ) -> list[QuerySuggestion]:
        """Generate suggestions for query improvement.

        Args:
            query: Query to suggest corrections for
            max_suggestions: Maximum number of suggestions

        Returns:
            List of query suggestions
        """
        suggestions = []

        # Get spelling suggestions
        spelling_suggestions = self._get_spelling_suggestions(query)
        suggestions.extend(spelling_suggestions)

        # Get synonym suggestions
        synonym_suggestions = self._get_synonym_suggestions(query)
        suggestions.extend(synonym_suggestions)

        # Get expansion suggestions
        expansion_suggestions = self._get_expansion_suggestions(query)
        suggestions.extend(expansion_suggestions)

        # Sort by confidence and limit
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        return suggestions[:max_suggestions]

    def relax_query(self, query: ParsedQuery, relaxation_level: int = 1) -> ParsedQuery:
        """Relax query constraints for broader results.

        Args:
            query: Query to relax
            relaxation_level: Level of relaxation (1=mild, 2=moderate, 3=aggressive)

        Returns:
            Relaxed query with broader matching
        """
        if relaxation_level <= 0:
            return query

        # Level 1: Convert AND to OR in boolean queries
        if relaxation_level >= 1:
            query = self._relax_boolean_operators(query)

        # Level 2: Add fuzzy matching to terms
        if relaxation_level >= 2:
            query = self._add_fuzzy_matching(query)

        # Level 3: Expand to wildcard patterns
        if relaxation_level >= 3:
            query = self._add_wildcard_expansion(query)

        return query

    def _correct_spelling(self, query: ParsedQuery) -> ParsedQuery:
        """Apply spelling correction to query terms."""
        if isinstance(query, TermQuery):
            corrections = self.spell_checker.suggest(query.term, 1)
            if corrections:
                # Create OR query with original and corrected terms
                original = TermQuery(query.term, query.boost * 1.0)
                corrected = TermQuery(corrections[0], query.boost * 0.8)
                return BooleanQuery(BooleanOperator.OR, [original, corrected])
            return query

        elif isinstance(query, PhraseQuery):
            terms = query.phrase.split()
            corrected_terms = []
            has_corrections = False

            for term in terms:
                corrections = self.spell_checker.suggest(term, 1)
                if corrections:
                    corrected_terms.append(corrections[0])
                    has_corrections = True
                else:
                    corrected_terms.append(term)

            if has_corrections:
                # Create OR query with original and corrected phrases
                original = PhraseQuery(query.phrase, query.slop, query.boost * 1.0)
                corrected = PhraseQuery(
                    " ".join(corrected_terms), query.slop, query.boost * 0.8
                )
                return BooleanQuery(BooleanOperator.OR, [original, corrected])
            return query

        elif isinstance(query, FieldQuery):
            corrected_subquery = self._correct_spelling(query.query)
            return FieldQuery(query.field, corrected_subquery)

        elif isinstance(query, BooleanQuery):
            corrected_queries = [self._correct_spelling(q) for q in query.queries]
            return BooleanQuery(
                query.operator, corrected_queries, query.minimum_should_match
            )

        return query

    def _expand_synonyms(self, query: ParsedQuery) -> ParsedQuery:
        """Add synonym alternatives to query terms."""
        if isinstance(query, TermQuery):
            term_lower = query.term.lower()
            if term_lower in self.synonym_expander.synonyms:
                # Create OR query with original term and synonyms
                queries = [TermQuery(query.term, query.boost)]

                for synonym in self.synonym_expander.synonyms[term_lower]:
                    synonym_query = TermQuery(synonym, query.boost * 0.7)
                    queries.append(synonym_query)

                if len(queries) > 1:
                    return BooleanQuery(BooleanOperator.OR, list(queries))
            return query

        elif isinstance(query, PhraseQuery):
            # Check if entire phrase is a known synonym
            phrase_lower = query.phrase.lower()
            if phrase_lower in self.synonym_expander.synonyms:
                queries = [PhraseQuery(query.phrase, query.slop, query.boost)]

                for synonym in self.synonym_expander.synonyms[phrase_lower]:
                    synonym_query = PhraseQuery(synonym, query.slop, query.boost * 0.7)
                    queries.append(synonym_query)

                if len(queries) > 1:
                    return BooleanQuery(BooleanOperator.OR, list(queries))
            return query

        elif isinstance(query, FieldQuery):
            expanded_subquery = self._expand_synonyms(query.query)
            return FieldQuery(query.field, expanded_subquery)

        elif isinstance(query, BooleanQuery):
            expanded_queries = [self._expand_synonyms(q) for q in query.queries]
            return BooleanQuery(
                query.operator, expanded_queries, query.minimum_should_match
            )

        return query

    def _expand_fields(self, query: ParsedQuery) -> ParsedQuery:
        """Expand field queries to related fields."""
        if isinstance(query, FieldQuery):
            field = query.field.lower()

            if field in self.field_expansions:
                expanded_fields = self.field_expansions[field]
                boosts = self.expansion_boosts.get(field, {})

                if len(expanded_fields) > 1:
                    # Create OR query across multiple fields
                    field_queries = []

                    for expanded_field in expanded_fields:
                        boost = boosts.get(expanded_field, 0.5)

                        # Adjust boost on the subquery
                        adjusted_query = self._adjust_query_boost(query.query, boost)
                        field_query = FieldQuery(expanded_field, adjusted_query)
                        field_queries.append(field_query)

                    return BooleanQuery(BooleanOperator.OR, field_queries)

            # Recursively expand the subquery
            expanded_subquery = self._expand_fields(query.query)
            return FieldQuery(query.field, expanded_subquery)

        elif isinstance(query, BooleanQuery):
            expanded_queries = [self._expand_fields(q) for q in query.queries]
            return BooleanQuery(
                query.operator, expanded_queries, query.minimum_should_match
            )

        return query

    def _adjust_query_boost(
        self, query: ParsedQuery, boost_factor: float
    ) -> ParsedQuery:
        """Adjust boost values in a query by a factor."""
        if isinstance(query, TermQuery):
            return TermQuery(query.term, query.boost * boost_factor)
        elif isinstance(query, PhraseQuery):
            return PhraseQuery(query.phrase, query.slop, query.boost * boost_factor)
        elif isinstance(query, FuzzyQuery):
            return FuzzyQuery(
                query.term,
                query.max_edits,
                query.prefix_length,
                query.boost * boost_factor,
            )
        elif isinstance(query, WildcardQuery):
            return WildcardQuery(query.pattern, query.boost * boost_factor)
        else:
            return query

    def _get_spelling_suggestions(self, query: ParsedQuery) -> list[QuerySuggestion]:
        """Generate spelling correction suggestions."""
        suggestions = []

        def collect_terms(q: ParsedQuery) -> list[str]:
            if isinstance(q, TermQuery):
                return [q.term]
            elif isinstance(q, PhraseQuery):
                return q.phrase.split()
            elif isinstance(q, FieldQuery):
                return collect_terms(q.query)
            elif isinstance(q, BooleanQuery):
                terms = []
                for subq in q.queries:
                    terms.extend(collect_terms(subq))
                return terms
            return []

        terms = collect_terms(query)
        for term in terms:
            corrections = self.spell_checker.suggest(term, 1)
            if corrections:
                suggestion = QuerySuggestion(
                    original_query=query.to_string(),
                    suggested_query=query.to_string().replace(term, corrections[0]),
                    suggestion_type="spelling",
                    confidence=0.8,
                    explanation=f"Did you mean '{corrections[0]}' instead of '{term}'?",
                )
                suggestions.append(suggestion)

        return suggestions

    def _get_synonym_suggestions(self, query: ParsedQuery) -> list[QuerySuggestion]:
        """Generate synonym expansion suggestions."""
        suggestions = []

        def collect_terms(q: ParsedQuery) -> list[str]:
            if isinstance(q, TermQuery):
                return [q.term]
            elif isinstance(q, PhraseQuery):
                return [q.phrase]
            elif isinstance(q, FieldQuery):
                return collect_terms(q.query)
            elif isinstance(q, BooleanQuery):
                terms = []
                for subq in q.queries:
                    terms.extend(collect_terms(subq))
                return terms
            return []

        terms = collect_terms(query)
        for term in terms:
            term_lower = term.lower()
            if term_lower in self.synonym_expander.synonyms:
                synonyms = self.synonym_expander.synonyms[term_lower][
                    :2
                ]  # Limit to first 2
                synonym_str = " OR ".join(synonyms)
                suggestion = QuerySuggestion(
                    original_query=query.to_string(),
                    suggested_query=query.to_string().replace(
                        term, f"({term} OR {synonym_str})"
                    ),
                    suggestion_type="synonym",
                    confidence=0.7,
                    explanation=f"Include related terms: {', '.join(synonyms)}",
                )
                suggestions.append(suggestion)

        return suggestions

    def _get_expansion_suggestions(self, query: ParsedQuery) -> list[QuerySuggestion]:
        """Generate field expansion suggestions."""
        suggestions = []

        if isinstance(query, FieldQuery):
            field = query.field.lower()
            if field in self.field_expansions:
                expanded_fields = self.field_expansions[field]
                if len(expanded_fields) > 1:
                    other_fields = [f for f in expanded_fields if f != field]
                    fields_str = " OR ".join(other_fields)
                    suggestion = QuerySuggestion(
                        original_query=query.to_string(),
                        suggested_query=f"({query.to_string()} OR {fields_str}:{query.query.to_string()})",
                        suggestion_type="expansion",
                        confidence=0.6,
                        explanation=f"Also search in: {', '.join(other_fields)}",
                    )
                    suggestions.append(suggestion)

        return suggestions

    def _relax_boolean_operators(self, query: ParsedQuery) -> ParsedQuery:
        """Convert AND operators to OR for broader matching."""
        if isinstance(query, BooleanQuery):
            if query.operator == BooleanOperator.AND:
                # Convert to OR
                relaxed_queries = [
                    self._relax_boolean_operators(q) for q in query.queries
                ]
                return BooleanQuery(BooleanOperator.OR, relaxed_queries)
            else:
                # Recursively relax subqueries
                relaxed_queries = [
                    self._relax_boolean_operators(q) for q in query.queries
                ]
                return BooleanQuery(
                    query.operator, relaxed_queries, query.minimum_should_match
                )

        elif isinstance(query, FieldQuery):
            relaxed_subquery = self._relax_boolean_operators(query.query)
            return FieldQuery(query.field, relaxed_subquery)

        return query

    def _add_fuzzy_matching(self, query: ParsedQuery) -> ParsedQuery:
        """Add fuzzy matching to term queries."""
        if isinstance(query, TermQuery):
            if len(query.term) >= 4:  # Only fuzzify longer terms
                fuzzy_query = FuzzyQuery(query.term, 1, 0, query.boost * 0.8)
                return BooleanQuery(BooleanOperator.OR, [query, fuzzy_query])
            return query

        elif isinstance(query, FieldQuery):
            fuzzified_subquery = self._add_fuzzy_matching(query.query)
            return FieldQuery(query.field, fuzzified_subquery)

        elif isinstance(query, BooleanQuery):
            fuzzified_queries = [self._add_fuzzy_matching(q) for q in query.queries]
            return BooleanQuery(
                query.operator, fuzzified_queries, query.minimum_should_match
            )

        return query

    def _add_wildcard_expansion(self, query: ParsedQuery) -> ParsedQuery:
        """Add wildcard patterns for very broad matching."""
        if isinstance(query, TermQuery):
            if len(query.term) >= 3:  # Only wildcardify reasonable-length terms
                wildcard_query = WildcardQuery(f"{query.term}*", query.boost * 0.6)
                return BooleanQuery(BooleanOperator.OR, [query, wildcard_query])
            return query

        elif isinstance(query, FieldQuery):
            wildcarded_subquery = self._add_wildcard_expansion(query.query)
            return FieldQuery(query.field, wildcarded_subquery)

        elif isinstance(query, BooleanQuery):
            wildcarded_queries = [
                self._add_wildcard_expansion(q) for q in query.queries
            ]
            return BooleanQuery(
                query.operator, wildcarded_queries, query.minimum_should_match
            )

        return query

    def add_synonym_mapping(self, term: str, synonyms: list[str]) -> None:
        """Add custom synonym mapping.

        Args:
            term: Base term
            synonyms: List of synonymous terms
        """
        term_lower = term.lower()
        # Update the synonym expander's synonyms
        self.synonym_expander.synonyms[term_lower] = synonyms

        # Rebuild reverse mapping
        self.synonym_expander.reverse_synonyms = {}
        for abbrev, expansions in self.synonym_expander.synonyms.items():
            for expansion in expansions:
                self.synonym_expander.reverse_synonyms[expansion] = abbrev

    def add_field_expansion(
        self,
        field: str,
        expanded_fields: list[str],
        boosts: dict[str, float] | None = None,
    ) -> None:
        """Add custom field expansion mapping.

        Args:
            field: Base field name
            expanded_fields: List of fields to expand to
            boosts: Optional boost values for expanded fields
        """
        self.field_expansions[field] = expanded_fields

        if boosts:
            self.expansion_boosts[field] = boosts
        else:
            # Default boost strategy: original=1.0, others decrease
            default_boosts = {}
            for i, expanded_field in enumerate(expanded_fields):
                if i == 0:
                    default_boosts[expanded_field] = 1.0
                else:
                    default_boosts[expanded_field] = 1.0 - (i * 0.2)
            self.expansion_boosts[field] = default_boosts
