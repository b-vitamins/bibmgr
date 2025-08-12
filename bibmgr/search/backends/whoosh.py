"""Whoosh search backend implementation."""

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from whoosh import fields as whoosh_fields
from whoosh.analysis import StandardAnalyzer as WhooshStandardAnalyzer
from whoosh.index import Index, create_in, exists_in, open_dir
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh.qparser import QueryParser as WhooshQueryParser
from whoosh.query import (
    And,
    Every,
    FuzzyTerm,
    Not,
    NumericRange,
    Or,
    Query,
    Term,
    Wildcard,
)
from whoosh.searching import Hit, Results
from whoosh.writing import IndexWriter

from ..indexing.fields import FieldConfiguration, FieldType
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
from .base import BackendResult, SearchBackend, SearchMatch, SearchQuery


class WhooshBackend(SearchBackend):
    """Whoosh-based search backend with persistent disk storage."""

    def __init__(
        self,
        index_dir: Path | None = None,
        field_config: FieldConfiguration | None = None,
        create_if_missing: bool = True,
    ):
        """Initialize Whoosh backend.

        Args:
            index_dir: Directory to store the search index
            field_config: Field configuration for schema definition
            create_if_missing: Whether to create index if it doesn't exist
        """
        self.index_dir = index_dir or Path.home() / ".cache" / "bibmgr" / "search_index"
        self.field_config = field_config or FieldConfiguration()
        self._index: Index | None = None
        self._schema_created = False
        self._writer: IndexWriter | None = None
        self._writer_lock = threading.Lock()

        self.index_dir.mkdir(parents=True, exist_ok=True)

        if create_if_missing or exists_in(str(self.index_dir)):
            self._initialize_index()

    def _initialize_index(self) -> None:
        """Initialize or open the Whoosh index."""
        schema = self._create_schema()

        if exists_in(str(self.index_dir)):
            self._index = open_dir(str(self.index_dir))
            if self._index.schema != schema:
                self._update_schema(schema)
        else:
            self._index = create_in(str(self.index_dir), schema)

        self._schema_created = True

    @property
    def schema(self) -> whoosh_fields.Schema | None:
        """Get the current schema."""
        return getattr(self._index, "schema", None) if self._index else None

    def _create_schema(self) -> whoosh_fields.Schema:
        """Create Whoosh schema based on field configuration."""
        schema_fields = {}

        # Add required fields - key must be ID for update_document to work
        schema_fields["key"] = whoosh_fields.ID(stored=True, unique=True)
        schema_fields["entry_type"] = whoosh_fields.KEYWORD(stored=True)

        # Add configured fields
        for field_name, field_def in self.field_config.fields.items():
            # Skip key field - already defined above with proper unique constraint
            if field_name == "key":
                continue

            if not field_def.indexed and not field_def.stored:
                continue

            if field_def.field_type == FieldType.TEXT:
                schema_fields[field_name] = whoosh_fields.TEXT(
                    stored=field_def.stored, analyzer=WhooshStandardAnalyzer()
                )
                if field_def.analyzed:
                    schema_fields[f"{field_name}_analyzed"] = whoosh_fields.TEXT(
                        stored=False, analyzer=WhooshStandardAnalyzer()
                    )

            elif field_def.field_type == FieldType.KEYWORD:
                schema_fields[field_name] = whoosh_fields.KEYWORD(
                    stored=field_def.stored, commas=True
                )

            elif field_def.field_type == FieldType.NUMERIC:
                schema_fields[field_name] = whoosh_fields.NUMERIC(
                    stored=field_def.stored
                )

            elif field_def.field_type == FieldType.DATE:
                schema_fields[field_name] = whoosh_fields.DATETIME(
                    stored=field_def.stored
                )

            elif field_def.field_type == FieldType.BOOLEAN:
                schema_fields[field_name] = whoosh_fields.BOOLEAN(
                    stored=field_def.stored
                )

            elif field_def.field_type == FieldType.STORED:
                schema_fields[field_name] = whoosh_fields.STORED()

        schema_fields["content"] = whoosh_fields.TEXT(stored=False)
        schema_fields["content_analyzed"] = whoosh_fields.TEXT(stored=False)

        return whoosh_fields.Schema(**schema_fields)

    def _update_schema(self, new_schema: whoosh_fields.Schema) -> None:
        """Update index schema if it has changed."""
        if self._index:
            self._index.close()

        import shutil

        if self.index_dir.exists():
            shutil.rmtree(self.index_dir)

        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._index = create_in(str(self.index_dir), new_schema)

    def index(self, entry_key: str, fields: dict[str, Any]) -> None:
        """Index a single document."""
        if not self._schema_created:
            self._initialize_index()

        if not self._index:
            raise RuntimeError("Index not initialized")

        doc = self._prepare_document(entry_key, fields)

        with self._writer_lock:
            if self._writer is None:
                self._writer = self._index.writer()

            writer = self._writer
            if writer is not None:
                writer.update_document(**doc)

    def index_batch(self, documents: list[dict[str, Any]]) -> None:
        """Index multiple documents efficiently."""
        if not self._schema_created:
            self._initialize_index()

        if not self._index:
            raise RuntimeError("Index not initialized")

        with self._writer_lock:
            if self._writer is None:
                self._writer = self._index.writer()

            writer = self._writer
            if writer is not None:
                for doc in documents:
                    entry_key = doc.get("key")
                    if entry_key:
                        prepared_doc = self._prepare_document(entry_key, doc)
                        writer.update_document(**prepared_doc)

    def search(self, query: SearchQuery) -> BackendResult:
        """Execute search query."""
        if not self._index:
            raise RuntimeError("Index not initialized")

        self.commit()

        import time

        start_time = time.time()

        whoosh_query = self._convert_query(query.query)

        with self._index.searcher() as searcher:
            filter_query = None
            if query.filters:
                filter_query = self._build_filter_query(query.filters)

            results: Results = searcher.search(
                whoosh_query,
                limit=query.offset + query.limit,
                filter=filter_query,
                scored=True,
            )

            matches = []
            for i, hit in enumerate(results[query.offset : query.offset + query.limit]):
                score = float(hit.score) if hit.score is not None else 0.0
                match = SearchMatch(entry_key=hit["key"], score=score)

                if query.highlight:
                    highlights = self._extract_highlights(hit, query.fields)
                    if highlights:
                        match.highlights = highlights

                matches.append(match)

            facets = None
            if query.facet_fields:
                facets = self._compute_facets(
                    searcher, whoosh_query, query.facet_fields, filter_query
                )

            took_ms = int((time.time() - start_time) * 1000)

            return BackendResult(
                results=matches, total=len(results), facets=facets, took_ms=took_ms
            )

    def delete(self, entry_key: str) -> bool:
        """Delete document from index."""
        if not self._index:
            return False

        with self._writer_lock:
            if self._writer is None:
                self._writer = self._index.writer()

            writer = self._writer
            if writer is not None:
                deleted_count = writer.delete_by_term("key", entry_key)
                return deleted_count > 0
            return False

    def clear(self) -> None:
        """Clear all documents from index."""
        if not self._index:
            return

        self.commit()

        with self._index.writer() as writer:
            writer.delete_by_query(Every())

    def commit(self) -> None:
        """Commit pending changes to index."""
        with self._writer_lock:
            if self._writer is not None:
                self._writer.commit()
                self._writer = None

    def get_statistics(self) -> dict[str, Any]:
        """Get index statistics."""
        if not self._index:
            return {"total_documents": 0}

        with self._index.searcher() as searcher:
            last_modified = self._get_last_modified()
            return {
                "total_documents": searcher.doc_count(),
                "index_size_mb": self._get_index_size_mb(),
                "index_path": str(self.index_dir),
                "schema_fields": len(getattr(self._index, "schema", {})),
                "fields": list(
                    getattr(getattr(self._index, "schema", None), "names", lambda: [])()
                ),
                "last_modified": last_modified.isoformat() if last_modified else None,
            }

    def suggest(self, prefix: str, field: str, limit: int) -> list[str]:
        """Get search suggestions for prefix."""
        if not self._index:
            return []

        suggestions = []

        with self._index.searcher() as searcher:
            from whoosh.support.levenshtein import distance

            field_terms = getattr(searcher, "field_terms", lambda f: [])
            for term_text in field_terms(field):
                if term_text.startswith(prefix.lower()):
                    suggestions.append(term_text)
                elif distance(prefix.lower(), term_text) <= 2:
                    suggestions.append(term_text)

                if len(suggestions) >= limit:
                    break

        return suggestions[:limit]

    def _prepare_document(
        self, entry_key: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        """Prepare document for Whoosh indexing."""
        doc: dict[str, Any] = {"key": entry_key}
        content_parts = []

        schema = getattr(self._index, "schema", {})
        for field_name, value in fields.items():
            if field_name in schema and value is not None:
                # Convert values to appropriate types
                field_def = schema[field_name]

                if isinstance(field_def, whoosh_fields.DATETIME):
                    if isinstance(value, str):
                        try:
                            from datetime import datetime

                            doc[field_name] = datetime.fromisoformat(
                                value.replace("Z", "+00:00")
                            )
                        except ValueError:
                            continue
                    else:
                        doc[field_name] = value

                elif isinstance(field_def, whoosh_fields.NUMERIC):
                    try:
                        doc[field_name] = (
                            float(value) if "." in str(value) else int(value)
                        )
                        if field_name == "year" and value:
                            content_parts.append(str(value))
                    except (ValueError, TypeError):
                        continue

                elif isinstance(field_def, whoosh_fields.BOOLEAN):
                    doc[field_name] = bool(value)

                else:
                    if isinstance(field_def, whoosh_fields.KEYWORD) and isinstance(
                        value, list
                    ):
                        doc[field_name] = ",".join(str(v) for v in value)
                    else:
                        doc[field_name] = str(value) if value is not None else ""

                    if (
                        isinstance(
                            field_def, whoosh_fields.TEXT | whoosh_fields.KEYWORD
                        )
                        and value
                        and field_name not in ["key", "entry_type"]
                    ):
                        if field_name in doc:
                            content_parts.append(doc[field_name])
                        else:
                            content_parts.append(str(value))

        if content_parts:
            doc["content"] = " ".join(content_parts)
            doc["content_analyzed"] = doc["content"]
        else:
            doc["content"] = ""
            doc["content_analyzed"] = ""

        schema = getattr(self._index, "schema", None)
        if schema:
            names_method = getattr(schema, "names", lambda: [])
            for field_name in names_method():
                if field_name not in doc:
                    field_def = schema[field_name] if field_name in schema else None
                    if field_def and isinstance(field_def, whoosh_fields.TEXT):
                        doc[field_name] = ""

        return doc

    def _convert_query(self, parsed_query: Any) -> Query:
        """Convert parsed query to Whoosh Query object."""
        if isinstance(parsed_query, str):
            searchable_fields = self.field_config.get_searchable_fields()
            if not searchable_fields:
                schema = getattr(self._index, "schema", None)
                if schema:
                    names_method = getattr(schema, "names", lambda: [])
                    searchable_fields = [
                        name
                        for name in names_method()
                        if isinstance(schema.get(name), whoosh_fields.TEXT)
                    ]
                else:
                    searchable_fields = []
            parser = MultifieldParser(
                searchable_fields, getattr(self._index, "schema", {}), group=OrGroup
            )
            return parser.parse(parsed_query)

        if isinstance(parsed_query, TermQuery):
            searchable_fields = self.field_config.get_searchable_fields()
            if len(searchable_fields) == 1:
                return Term(searchable_fields[0], parsed_query.term)
            else:
                terms = [Term(field, parsed_query.term) for field in searchable_fields]
                return Or(terms)

        elif isinstance(parsed_query, PhraseQuery):
            parser = WhooshQueryParser("content", getattr(self._index, "schema", {}))
            return parser.parse(f'"{parsed_query.phrase}"')

        elif isinstance(parsed_query, FieldQuery):
            field_query = self._convert_query(parsed_query.query)
            return self._retarget_query(field_query, parsed_query.field)

        elif isinstance(parsed_query, BooleanQuery):
            subqueries = [self._convert_query(q) for q in parsed_query.queries]

            if parsed_query.operator == BooleanOperator.AND:
                return And(subqueries)
            elif parsed_query.operator == BooleanOperator.OR:
                return Or(subqueries)
            elif parsed_query.operator == BooleanOperator.NOT:
                if len(subqueries) == 2:
                    return And([subqueries[0], Not(subqueries[1])])
                elif len(subqueries) == 1:
                    return Not(subqueries[0])

        elif isinstance(parsed_query, WildcardQuery):
            # Use wildcard query
            searchable_fields = self.field_config.get_searchable_fields()
            wildcards = [
                Wildcard(field, parsed_query.pattern) for field in searchable_fields
            ]
            return Or(wildcards) if len(wildcards) > 1 else wildcards[0]

        elif isinstance(parsed_query, FuzzyQuery):
            searchable_fields = self.field_config.get_searchable_fields()
            fuzzy_terms = [
                FuzzyTerm(field, parsed_query.term, maxdist=parsed_query.max_edits)
                for field in searchable_fields
            ]
            return Or(fuzzy_terms) if len(fuzzy_terms) > 1 else fuzzy_terms[0]

        elif isinstance(parsed_query, RangeQuery):
            schema = getattr(self._index, "schema", {})
            if parsed_query.field in schema:
                field_def = schema[parsed_query.field]
                if isinstance(field_def, whoosh_fields.NUMERIC):
                    return NumericRange(
                        parsed_query.field,
                        parsed_query.start,
                        parsed_query.end,
                        startexcl=not parsed_query.include_start,
                        endexcl=not parsed_query.include_end,
                    )

        if hasattr(parsed_query, "to_string"):
            query_str = parsed_query.to_string()
            parser = MultifieldParser(
                self.field_config.get_searchable_fields(),
                getattr(self._index, "schema", {}),
                group=OrGroup,
            )
            return parser.parse(query_str)

        return Term("key", "")

    def _retarget_query(self, query: Query, target_field: str) -> Query:
        """Retarget a query to search in specific field."""
        if hasattr(query, "fieldname"):
            setattr(query, "fieldname", target_field)
        return query

    def _build_filter_query(self, filters: dict[str, Any]) -> Query | None:
        """Build filter query from filter dictionary."""
        filter_queries = []

        schema = getattr(self._index, "schema", {})
        for field, value in filters.items():
            if field not in schema:
                continue

            if isinstance(value, list):
                term_queries = [Term(field, str(v)) for v in value]
                filter_queries.append(Or(term_queries))
            else:
                filter_queries.append(Term(field, str(value)))

        if len(filter_queries) == 1:
            return filter_queries[0]
        elif len(filter_queries) > 1:
            return And(filter_queries)

        return None

    def _extract_highlights(self, hit: Hit, fields: list[str]) -> dict[str, list[str]]:
        """Extract highlights from search hit."""
        highlights = {}

        hit_highlights = getattr(hit, "highlights", None)
        if hit_highlights:
            for field in fields:
                try:
                    if callable(hit_highlights):
                        highlight_text = hit_highlights(field)
                        if highlight_text:
                            highlights[field] = [highlight_text]
                    elif (
                        hasattr(hit_highlights, "__contains__")
                        and field in hit_highlights
                    ):
                        highlight_text = hit_highlights[field]
                        if highlight_text:
                            highlights[field] = [highlight_text]
                except (TypeError, KeyError, AttributeError):
                    continue

        return highlights

    def _compute_facets(
        self,
        searcher,
        query: Query,
        facet_fields: list[str],
        filter_query: Query | None = None,
    ) -> dict[str, list[tuple[str, int]]]:
        """Compute facets for search results."""
        facets = {}

        results = searcher.search(query, limit=None, filter=filter_query)

        schema = getattr(self._index, "schema", {})
        for field in facet_fields:
            if field not in schema:
                continue

            value_counts = {}
            for hit in results:
                if field in hit and hit[field] is not None:
                    value = str(hit[field])
                    value_counts[value] = value_counts.get(value, 0) + 1

            sorted_values = sorted(
                value_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]

            facets[field] = sorted_values

        return facets

    def _get_index_size_mb(self) -> float:
        """Calculate index size in MB."""
        total_size = 0

        try:
            for file_path in self.index_dir.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except OSError:
            pass

        return total_size / (1024 * 1024)

    def _get_index_size(self) -> int:
        """Calculate index size in bytes."""
        total_size = 0

        try:
            for file_path in self.index_dir.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except OSError:
            pass

        return total_size

    def _get_last_modified(self):
        """Get last modified time of index files."""
        from datetime import datetime

        latest_time = None

        try:
            for file_path in self.index_dir.rglob("*"):
                if file_path.is_file():
                    mtime = file_path.stat().st_mtime
                    if latest_time is None or mtime > latest_time:
                        latest_time = mtime
        except OSError:
            pass

        if latest_time:
            return datetime.fromtimestamp(latest_time)

        return None

    def close(self) -> None:
        """Close the index and release resources."""
        self.commit()

        if self._index:
            self._index.close()
            self._index = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def create_whoosh_backend(
    index_dir: Path | None = None, field_config: FieldConfiguration | None = None
) -> WhooshBackend:
    """Create a Whoosh backend with default configuration.

    Args:
        index_dir: Directory for index storage
        field_config: Field configuration

    Returns:
        Configured WhooshBackend instance
    """
    return WhooshBackend(
        index_dir=index_dir, field_config=field_config, create_if_missing=True
    )
