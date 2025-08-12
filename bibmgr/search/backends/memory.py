"""In-memory search backend for testing and lightweight scenarios."""

import re
import sys
from collections import defaultdict
from typing import Any

from .base import BackendResult, SearchBackend, SearchMatch, SearchQuery


class MemoryBackend(SearchBackend):
    """In-memory search backend implementation."""

    def __init__(self):
        self.documents: dict[str, dict[str, Any]] = {}
        self.term_index: dict[str, set[str]] = defaultdict(set)
        self.field_values: dict[str, dict[Any, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )

    def index(self, entry_key: str, fields: dict[str, Any]) -> None:
        """Index a single document in memory."""
        if entry_key in self.documents:
            old_doc = self.documents[entry_key]
            self._remove_document_terms(entry_key, old_doc)
            self._remove_field_values(entry_key, old_doc)

        self.documents[entry_key] = fields.copy()
        self._index_document_terms(entry_key, fields)
        self._index_field_values(entry_key, fields)

    def index_batch(self, documents: list[dict[str, Any]]) -> None:
        """Index multiple documents efficiently."""
        for doc in documents:
            if "key" in doc:
                self.index(doc["key"], doc)

    def search(self, query: SearchQuery) -> BackendResult:
        """Execute search query using in-memory indexes."""
        import time

        start_time = time.time()

        if query.query is None:
            matches = []
        elif isinstance(query.query, str):
            matches = self._search_text_query(query.query, query.fields)
        else:
            matches = self._search_parsed_query(query.query, query.fields)

        if query.filters:
            matches = self._apply_filters(matches, query.filters)

        matches.sort(key=lambda x: x[1], reverse=True)

        total = len(matches)
        paginated = matches[query.offset : query.offset + query.limit]

        results = []
        for entry_key, score in paginated:
            search_match = SearchMatch(entry_key=entry_key, score=score)

            if query.highlight:
                highlights = self._generate_highlights(
                    entry_key, query.query, query.fields
                )
                if highlights:
                    search_match.highlights = highlights

            results.append(search_match)

        facets = None
        if query.facet_fields:
            facets = self._compute_facets(
                [key for key, _ in matches], query.facet_fields
            )

        took_ms = int((time.time() - start_time) * 1000)

        return BackendResult(
            results=results, total=total, facets=facets, took_ms=took_ms
        )

    def delete(self, entry_key: str) -> bool:
        """Delete document from memory indexes."""
        if entry_key not in self.documents:
            return False

        doc = self.documents.pop(entry_key)
        self._remove_document_terms(entry_key, doc)
        self._remove_field_values(entry_key, doc)
        return True

    def clear(self) -> None:
        """Clear all documents from memory."""
        self.documents.clear()
        self.term_index.clear()
        self.field_values.clear()

    def commit(self) -> None:
        """No-op for memory backend (changes are immediate)."""
        pass

    def get_statistics(self) -> dict[str, Any]:
        """Get memory backend statistics."""
        return {
            "total_documents": len(self.documents),
            "total_terms": len(self.term_index),
            "memory_usage_mb": self._estimate_memory_usage() / (1024 * 1024),
        }

    def suggest(self, prefix: str, field: str, limit: int) -> list[str]:
        """Get suggestions based on indexed field values."""
        suggestions = []
        prefix_lower = prefix.lower()

        # Look through field values
        if field in self.field_values:
            for value in self.field_values[field]:
                if isinstance(value, str) and value.lower().startswith(prefix_lower):
                    suggestions.append(value)
                    if len(suggestions) >= limit:
                        break

        return suggestions[:limit]

    def _search_text_query(
        self, query_text: str, fields: list[str]
    ) -> list[tuple[str, float]]:
        """Search using simple text query."""
        if not query_text.strip():
            return []

        if " AND " in query_text:
            return self._search_and_query(query_text, fields)
        elif " OR " in query_text:
            return self._search_or_query(query_text, fields)
        elif " NOT " in query_text:
            return self._search_not_query(query_text, fields)

        if (
            ":" in query_text
            and "[" in query_text
            and " TO " in query_text
            and "]" in query_text
        ):
            return self._search_range_query(query_text, fields)

        query_text = query_text.lower()

        if ":" in query_text:
            field_queries = self._parse_field_queries(query_text)
            if field_queries:
                return self._search_field_queries(field_queries)

        if query_text.startswith('"') and query_text.endswith('"'):
            phrase = query_text[1:-1]
            return self._search_phrase(phrase, fields)

        if "*" in query_text or "?" in query_text:
            return self._search_wildcard(query_text, fields)

        terms = query_text.split()
        return self._search_terms(terms, fields)

    def _search_terms(
        self, terms: list[str], fields: list[str]
    ) -> list[tuple[str, float]]:
        """Search for terms in specified fields (AND logic by default)."""
        if not terms:
            return []

        doc_sets = []
        for term in terms:
            term_lower = term.lower()
            matching_docs = set()

            if term_lower in self.term_index:
                matching_docs.update(self.term_index[term_lower])

            doc_sets.append(matching_docs)

        if not doc_sets:
            return []

        common_docs = doc_sets[0]
        for doc_set in doc_sets[1:]:
            common_docs = common_docs.intersection(doc_set)

        doc_scores = {}
        for doc_key in common_docs:
            if doc_key in self.documents:
                total_score = 0.0
                for term in terms:
                    score = self._calculate_term_score(doc_key, term, fields)
                    total_score += score
                doc_scores[doc_key] = total_score

        return [(key, score) for key, score in doc_scores.items()]

    def _search_phrase(self, phrase: str, fields: list[str]) -> list[tuple[str, float]]:
        """Search for exact phrase."""
        matches = []
        phrase_lower = phrase.lower()

        for doc_key, doc in self.documents.items():
            score = 0.0

            for field in fields or doc.keys():
                if field in doc and doc[field]:
                    field_text = str(doc[field]).lower()
                    if phrase_lower in field_text:
                        field_score = self._get_field_boost(field)
                        score += field_score

            if score > 0:
                matches.append((doc_key, score))

        return matches

    def _search_wildcard(
        self, pattern: str, fields: list[str]
    ) -> list[tuple[str, float]]:
        """Search using wildcard patterns."""
        regex_pattern = pattern.replace("*", ".*").replace("?", ".")
        regex = re.compile(regex_pattern, re.IGNORECASE)

        matches = []

        for doc_key, doc in self.documents.items():
            score = 0.0

            for field in fields or doc.keys():
                if field in doc and doc[field]:
                    field_text = str(doc[field])
                    if regex.search(field_text):
                        score += self._get_field_boost(field)

            if score > 0:
                matches.append((doc_key, score))

        return matches

    def _search_and_query(
        self, query_text: str, fields: list[str]
    ) -> list[tuple[str, float]]:
        """Handle AND queries."""
        parts = query_text.split(" AND ")

        if len(parts) < 2:
            return []

        terms = []
        for part in parts:
            terms.extend(part.strip().split())

        return self._search_terms(terms, fields)

    def _search_or_query(
        self, query_text: str, fields: list[str]
    ) -> list[tuple[str, float]]:
        """Handle OR queries."""
        parts = query_text.split(" OR ")

        if len(parts) < 2:
            return []

        all_terms = []
        for part in parts:
            all_terms.extend(part.strip().split())

        doc_scores = defaultdict(float)

        for term in all_terms:
            term_lower = term.lower()

            if term_lower in self.term_index:
                for doc_key in self.term_index[term_lower]:
                    if doc_key in self.documents:
                        score = self._calculate_term_score(doc_key, term, fields)
                        doc_scores[doc_key] += score

        return [(key, score) for key, score in doc_scores.items()]

    def _search_not_query(
        self, query_text: str, fields: list[str]
    ) -> list[tuple[str, float]]:
        """Handle NOT queries."""
        parts = query_text.split(" NOT ")
        if len(parts) != 2:
            return []

        positive_term, negative_term = parts

        positive_matches = dict(self._search_text_query(positive_term.strip(), fields))
        negative_matches = self._search_text_query(negative_term.strip(), fields)
        negative_keys = set(key for key, _ in negative_matches)

        filtered_matches = [
            (key, score)
            for key, score in positive_matches.items()
            if key not in negative_keys
        ]

        return filtered_matches

    def _search_range_query(
        self, query_text: str, fields: list[str]
    ) -> list[tuple[str, float]]:
        """Handle range queries like field:[start TO end]."""
        import re

        pattern = r"(\w+):\[(.+?)\s+TO\s+(.+?)\]"
        match = re.match(pattern, query_text)

        if not match:
            return []

        field_name = match.group(1)
        start_value = match.group(2).strip()
        end_value = match.group(3).strip()

        try:
            start_num = float(start_value) if start_value != "*" else None
            end_num = float(end_value) if end_value != "*" else None

            matches = []
            for doc_key, doc in self.documents.items():
                if field_name in doc:
                    field_value = doc[field_name]

                    try:
                        num_value = float(field_value)

                        in_range = True
                        if start_num is not None and num_value < start_num:
                            in_range = False
                        if end_num is not None and num_value > end_num:
                            in_range = False

                        if in_range:
                            if start_num is not None and end_num is not None:
                                range_size = end_num - start_num
                                distance_from_start = num_value - start_num
                                score = 1.0 + (
                                    0.5
                                    * (
                                        1.0
                                        - abs(
                                            2 * distance_from_start / range_size - 1.0
                                        )
                                    )
                                )
                            else:
                                score = 1.0

                            matches.append((doc_key, score))

                    except (ValueError, TypeError):
                        pass

            return matches

        except ValueError:
            return []

    def _parse_field_queries(self, query_text: str) -> dict[str, str]:
        """Parse field:value queries."""
        field_queries = {}

        # Simple field query parsing
        parts = query_text.split()
        for part in parts:
            if ":" in part:
                field, value = part.split(":", 1)
                field_queries[field] = value

        return field_queries

    def _search_field_queries(
        self, field_queries: dict[str, str]
    ) -> list[tuple[str, float]]:
        """Search using field-specific queries."""
        matches = []

        for doc_key, doc in self.documents.items():
            score = 0.0

            for field, value in field_queries.items():
                if field in doc and doc[field]:
                    field_value = str(doc[field]).lower()
                    query_value = value.lower()

                    # Handle range queries for year
                    if field == "year" and ".." in query_value:
                        try:
                            start, end = query_value.split("..")
                            doc_year = doc[field]
                            if int(start) <= doc_year <= int(end):
                                score += 1.0
                        except (ValueError, TypeError):
                            pass
                    # Exact or partial match
                    elif query_value in field_value:
                        score += self._get_field_boost(field)

            if score > 0:
                matches.append((doc_key, score))

        return matches

    def _calculate_term_score(
        self, doc_key: str, term: str, fields: list[str]
    ) -> float:
        """Calculate BM25-like score for term in document."""
        doc = self.documents[doc_key]
        score = 0.0
        term_lower = term.lower()

        for field in fields or doc.keys():
            if field in doc and doc[field]:
                field_text = str(doc[field]).lower()

                # Term frequency in field
                tf = field_text.count(term_lower)
                if tf > 0:
                    # Simple BM25-like scoring
                    field_boost = self._get_field_boost(field)
                    # Normalize by field length
                    field_length = len(field_text.split())
                    tf_score = tf / (tf + 1.2 * (0.25 + 0.75 * field_length / 100))
                    score += tf_score * field_boost

        return score

    def _get_field_boost(self, field: str) -> float:
        """Get boost factor for field."""
        boost_map = {
            "title": 2.0,
            "author": 1.5,
            "keywords": 1.2,
            "abstract": 1.0,
            "journal": 1.0,
            "note": 0.5,
        }
        return boost_map.get(field, 0.8)

    def _apply_filters(
        self, matches: list[tuple[str, float]], filters: dict[str, Any]
    ) -> list[tuple[str, float]]:
        """Apply filters to search results."""
        if not filters:
            return matches

        filtered = []
        for doc_key, score in matches:
            doc = self.documents.get(doc_key)
            if not doc:
                continue

            include = True
            for field, filter_value in filters.items():
                if field not in doc:
                    include = False
                    break

                doc_value = doc[field]
                if isinstance(filter_value, list):
                    if doc_value not in filter_value:
                        include = False
                        break
                else:
                    if doc_value != filter_value:
                        include = False
                        break

            if include:
                filtered.append((doc_key, score))

        return filtered

    def _generate_highlights(
        self, entry_key: str, query: Any, fields: list[str]
    ) -> dict[str, list[str]] | None:
        """Generate simple highlights for search results."""
        doc = self.documents.get(entry_key)
        if not doc:
            return None

        if isinstance(query, str):
            terms = query.lower().split()
        else:
            return None

        highlights = {}

        for field in fields or doc.keys():
            if field in doc and doc[field]:
                field_text = str(doc[field])
                highlighted = self._highlight_text(field_text, terms)
                if highlighted != field_text:
                    highlights[field] = [highlighted]

        return highlights if highlights else None

    def _highlight_text(self, text: str, terms: list[str]) -> str:
        """Add simple highlighting to text."""
        highlighted = text

        for term in terms:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            highlighted = pattern.sub(f"<mark>{term}</mark>", highlighted)

        return highlighted

    def _search_parsed_query(
        self, parsed_query: Any, fields: list[str]
    ) -> list[tuple[str, float]]:
        """Search using pre-parsed query object."""
        from ..query.parser import (
            BooleanOperator,
            BooleanQuery,
            FieldQuery,
            FuzzyQuery,
            PhraseQuery,
            RangeQuery,
            TermQuery,
            WildcardQuery,
        )

        if isinstance(parsed_query, TermQuery):
            terms = parsed_query.term.split()
            return self._search_terms(terms, fields)

        elif isinstance(parsed_query, PhraseQuery):
            return self._search_phrase(parsed_query.phrase, fields)

        elif isinstance(parsed_query, FieldQuery):
            return self._search_parsed_query(parsed_query.query, [parsed_query.field])

        elif isinstance(parsed_query, BooleanQuery):
            if parsed_query.operator == BooleanOperator.AND:
                if not parsed_query.queries:
                    return []

                result_sets = []
                for subq in parsed_query.queries:
                    subq_matches = self._search_parsed_query(subq, fields)
                    result_dict = {doc_key: score for doc_key, score in subq_matches}
                    result_sets.append(result_dict)

                if not result_sets:
                    return []

                common_keys = set(result_sets[0].keys())
                for result_dict in result_sets[1:]:
                    common_keys = common_keys.intersection(set(result_dict.keys()))

                final_results = []
                for doc_key in common_keys:
                    total_score = sum(
                        result_dict.get(doc_key, 0) for result_dict in result_sets
                    )
                    final_results.append((doc_key, total_score))

                return final_results

            elif parsed_query.operator == BooleanOperator.OR:
                doc_scores = defaultdict(float)
                for subq in parsed_query.queries:
                    subq_matches = self._search_parsed_query(subq, fields)
                    for doc_key, score in subq_matches:
                        doc_scores[doc_key] += score
                return [(key, score) for key, score in doc_scores.items()]

            elif parsed_query.operator == BooleanOperator.NOT:
                if len(parsed_query.queries) >= 2:
                    pos_matches = dict(
                        self._search_parsed_query(parsed_query.queries[0], fields)
                    )
                    neg_matches = self._search_parsed_query(
                        parsed_query.queries[1], fields
                    )
                    neg_keys = set(key for key, _ in neg_matches)
                    return [(k, v) for k, v in pos_matches.items() if k not in neg_keys]
                else:
                    return []

        elif isinstance(parsed_query, WildcardQuery):
            return self._search_wildcard(parsed_query.pattern, fields)

        elif isinstance(parsed_query, FuzzyQuery):
            return self._search_terms([parsed_query.term], fields)

        elif isinstance(parsed_query, RangeQuery):
            matches = []
            field_name = parsed_query.field
            start_value = parsed_query.start
            end_value = parsed_query.end
            include_start = parsed_query.include_start
            include_end = parsed_query.include_end

            for doc_key, doc in self.documents.items():
                if field_name in doc and doc[field_name] is not None:
                    field_value = doc[field_name]

                    # Convert to comparable type
                    try:
                        if isinstance(field_value, int | float):
                            doc_value = field_value
                        else:
                            doc_value = float(field_value)

                        # Check if value is in range
                        in_range = True

                        if start_value is not None:
                            try:
                                start_numeric = (
                                    float(start_value)
                                    if not isinstance(start_value, int | float)
                                    else start_value
                                )
                                if include_start:
                                    in_range = in_range and doc_value >= start_numeric
                                else:
                                    in_range = in_range and doc_value > start_numeric
                            except (ValueError, TypeError):
                                in_range = False

                        if end_value is not None:
                            try:
                                end_numeric = (
                                    float(end_value)
                                    if not isinstance(end_value, int | float)
                                    else end_value
                                )
                                if include_end:
                                    in_range = in_range and doc_value <= end_numeric
                                else:
                                    in_range = in_range and doc_value < end_numeric
                            except (ValueError, TypeError):
                                in_range = False

                        if in_range:
                            score = 1.0
                            matches.append((doc_key, score))

                    except (ValueError, TypeError):
                        continue

            return matches

        return []

    def _compute_facets(
        self, doc_keys: list[str], facet_fields: list[str]
    ) -> dict[str, list[tuple[str, int]]]:
        """Compute facets for the given documents."""
        facets = {}

        for field in facet_fields:
            value_counts = defaultdict(int)

            for doc_key in doc_keys:
                doc = self.documents.get(doc_key)
                if doc and field in doc and doc[field] is not None:
                    value = str(doc[field])
                    value_counts[value] += 1

            sorted_values = sorted(
                value_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]

            facets[field] = sorted_values

        return facets

    def _index_document_terms(self, entry_key: str, fields: dict[str, Any]) -> None:
        """Index terms from document fields."""
        for field, value in fields.items():
            if value is not None:
                text = str(value).lower()
                terms = re.findall(r"\w+", text)

                for term in terms:
                    self.term_index[term].add(entry_key)

    def _index_field_values(self, entry_key: str, fields: dict[str, Any]) -> None:
        """Index field values for faceting."""
        for field, value in fields.items():
            if value is not None:
                try:
                    self.field_values[field][value].add(entry_key)
                except TypeError:
                    if isinstance(value, list):
                        for item in value:
                            try:
                                self.field_values[field][str(item)].add(entry_key)
                            except TypeError:
                                pass
                    else:
                        str_value = str(value)
                        self.field_values[field][str_value].add(entry_key)

    def _remove_document_terms(self, entry_key: str, fields: dict[str, Any]) -> None:
        """Remove document terms from index."""
        for field, value in fields.items():
            if value is not None:
                text = str(value).lower()
                terms = re.findall(r"\w+", text)

                for term in terms:
                    if term in self.term_index:
                        self.term_index[term].discard(entry_key)
                        if not self.term_index[term]:
                            del self.term_index[term]

    def _remove_field_values(self, entry_key: str, fields: dict[str, Any]) -> None:
        """Remove field values from faceting index."""
        for field, value in fields.items():
            if value is not None and field in self.field_values:
                try:
                    if value in self.field_values[field]:
                        self.field_values[field][value].discard(entry_key)
                        if not self.field_values[field][value]:
                            del self.field_values[field][value]
                except TypeError:
                    # If unhashable, handle like in indexing
                    if isinstance(value, list):
                        for item in value:
                            try:
                                str_item = str(item)
                                if str_item in self.field_values[field]:
                                    self.field_values[field][str_item].discard(
                                        entry_key
                                    )
                                    if not self.field_values[field][str_item]:
                                        del self.field_values[field][str_item]
                            except TypeError:
                                pass
                    else:
                        str_value = str(value)
                        if str_value in self.field_values[field]:
                            self.field_values[field][str_value].discard(entry_key)
                            if not self.field_values[field][str_value]:
                                del self.field_values[field][str_value]

    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage in bytes."""
        size = 0

        size += sys.getsizeof(self.documents)
        for doc in self.documents.values():
            size += sys.getsizeof(doc)
            for key, value in doc.items():
                size += sys.getsizeof(key) + sys.getsizeof(value)

        size += sys.getsizeof(self.term_index)
        for term, doc_set in self.term_index.items():
            size += sys.getsizeof(term) + sys.getsizeof(doc_set)

        size += sys.getsizeof(self.field_values)

        return size
