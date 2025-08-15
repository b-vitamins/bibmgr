"""Tests for search and query CLI commands.

This module comprehensively tests search functionality including:
- Basic text search across all fields
- Field-specific searches (author:, title:, year:, etc.)
- Advanced query syntax (AND, OR, NOT, wildcards, fuzzy)
- Search result formatting and highlighting
- Faceted search and filtering
- Similar entries discovery
- Search suggestions and corrections
"""

from unittest.mock import Mock, patch

from bibmgr.search.results import (
    Facet,
    FacetValue,
    SearchMatch,
    SearchResultCollection,
    SearchStatistics,
    SearchSuggestion,
)


class TestSearchCommand:
    """Test the 'bib search' command."""

    def test_search_basic_query(
        self, cli_runner, mock_search_engine, populated_repository
    ):
        """Test basic search across all fields."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            with patch(
                "bibmgr.cli.commands.search.get_repository",
                return_value=populated_repository,
            ):
                result = cli_runner.invoke(["search", "quantum"])

        assert_exit_success(result)
        assert_output_contains(result, "doe2024", "Quantum Computing Advances")
        assert_output_contains(result, "1 result")

    def test_search_no_results(self, cli_runner, populated_repository):
        """Test search with no results."""
        # Create a mock SearchService (not SearchEngine)
        from bibmgr.search import SearchService

        mock_search_service = Mock(spec=SearchService)

        mock_search_service.search.return_value = SearchResultCollection(
            query="nonexistent",
            matches=[],
            total=0,
            facets=[],
            suggestions=[
                SearchSuggestion(
                    suggestion="existent",
                    suggestion_type="spell",
                    confidence=0.8,
                    description="Did you mean: existent?",
                )
            ],
            statistics=SearchStatistics(total_results=1, search_time_ms=5),
        )

        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_service,
        ):
            with patch(
                "bibmgr.cli.commands.search.get_repository",
                return_value=populated_repository,
            ):
                result = cli_runner.invoke(["search", "nonexistent"])

        assert_exit_success(result)
        assert_output_contains(result, "No results found", "Did you mean")

    def test_search_field_specific(self, cli_runner, mock_search_engine):
        """Test field-specific search."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            result = cli_runner.invoke(["search", "author:Doe"])

        assert_exit_success(result)
        assert mock_search_engine.search.called
        call_args = mock_search_engine.search.call_args
        assert call_args[0][0] == "author:Doe"

    def test_search_boolean_operators(self, cli_runner, mock_search_engine):
        """Test search with boolean operators."""
        mock_search_engine.search.return_value = SearchResultCollection(
            query="quantum AND computing",
            matches=[
                SearchMatch(
                    entry_key="doe2024",
                    score=0.95,
                    highlights={
                        "title": [
                            "<mark>Quantum</mark> <mark>Computing</mark> Advances"
                        ]
                    },
                )
            ],
            total=1,
            facets=[],
            suggestions=[],
            statistics=SearchStatistics(total_results=0, search_time_ms=10),
        )

        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            result = cli_runner.invoke(["search", "quantum AND computing"])

        assert_exit_success(result)
        assert_output_contains(result, "quantum AND computing")

    def test_search_with_highlighting(
        self, cli_runner, mock_search_engine, populated_repository
    ):
        """Test search with result highlighting."""
        mock_search_engine.search.return_value = SearchResultCollection(
            query="quantum",
            matches=[
                SearchMatch(
                    entry_key="doe2024",
                    score=0.95,
                    highlights={
                        "title": ["<mark>Quantum</mark> Computing Advances"],
                        "abstract": [
                            "Recent advances in <mark>quantum</mark> computing..."
                        ],
                    },
                )
            ],
            total=1,
            facets=[],
            suggestions=[],
            statistics=SearchStatistics(total_results=0, search_time_ms=10),
        )

        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            with patch(
                "bibmgr.cli.commands.search.get_repository",
                return_value=populated_repository,
            ):
                result = cli_runner.invoke(
                    ["search", "quantum", "--format", "detailed"]
                )

        assert_exit_success(result)
        # Should show highlighted snippets - Title field exists, Abstract highlight shown if entry has abstract
        assert_output_contains(result, "Title:", "...Quantum Computing Advances...")

    def test_search_with_limit(self, cli_runner, mock_search_engine):
        """Test search with result limit."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            cli_runner.invoke(["search", "quantum", "--limit", "5"])

        assert mock_search_engine.search.called
        call_kwargs = mock_search_engine.search.call_args[1]
        assert call_kwargs.get("limit") == 5

    def test_search_with_offset(self, cli_runner, mock_search_engine):
        """Test search with pagination offset."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            cli_runner.invoke(["search", "quantum", "--offset", "10"])

        assert mock_search_engine.search.called
        call_kwargs = mock_search_engine.search.call_args[1]
        assert call_kwargs.get("offset") == 10

    def test_search_sorted_by_year(self, cli_runner, mock_search_engine):
        """Test search results sorted by year."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            result = cli_runner.invoke(["search", "quantum", "--sort", "year"])

        assert_exit_success(result)
        # Results should be sorted by year

    def test_search_sorted_by_relevance(self, cli_runner, mock_search_engine):
        """Test search results sorted by relevance (default)."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            result = cli_runner.invoke(["search", "quantum", "--sort", "relevance"])

        assert_exit_success(result)

    def test_search_with_facets(self, cli_runner, populated_repository):
        """Test search with faceted results."""
        # Create a mock SearchService
        from bibmgr.search import SearchService

        mock_search_service = Mock(spec=SearchService)

        # Return search results with facets but no matches
        mock_search_service.search.return_value = SearchResultCollection(
            query="machine learning",
            matches=[],
            total=0,  # No matches to display
            facets=[
                Facet(
                    field="year",
                    display_name="Publication Year",
                    values=[
                        FacetValue(value="2024", count=10),
                        FacetValue(value="2023", count=8),
                        FacetValue(value="2022", count=7),
                    ],
                ),
                Facet(
                    field="type",
                    display_name="Entry Type",
                    values=[
                        FacetValue(value="article", count=15),
                        FacetValue(value="inproceedings", count=10),
                    ],
                ),
            ],
            suggestions=[],
            statistics=SearchStatistics(total_results=0, search_time_ms=15),
        )

        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_service,
        ):
            with patch(
                "bibmgr.cli.commands.search.get_repository",
                return_value=populated_repository,
            ):
                result = cli_runner.invoke(["search", "machine learning"])

        assert_exit_success(result)
        # Should show "No results" but still display facets
        assert_output_contains(result, "No results found")
        assert_output_contains(
            result,
            "Refine by:",
            "Publication Year",
            "2024 (10)",
            "2023 (8)",
            "Entry Type",
            "article (15)",  # Value as stored, not display value
        )

    def test_search_output_formats(self, cli_runner, mock_search_engine):
        """Test different output formats for search results."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            # Table format (default)
            result = cli_runner.invoke(["search", "quantum", "--format", "table"])
            assert_exit_success(result)

            # List format
            result = cli_runner.invoke(["search", "quantum", "--format", "list"])
            assert_exit_success(result)

            # Detailed format
            result = cli_runner.invoke(["search", "quantum", "--format", "detailed"])
            assert_exit_success(result)

    def test_search_export_results(
        self, cli_runner, mock_search_engine, populated_repository, tmp_path
    ):
        """Test exporting search results to file."""
        output_file = tmp_path / "results.bib"

        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            with patch(
                "bibmgr.cli.commands.search.get_repository",
                return_value=populated_repository,
            ):
                result = cli_runner.invoke(
                    [
                        "search",
                        "quantum",
                        "--export",
                        str(output_file),
                        "--export-format",
                        "bibtex",
                    ]
                )

        assert_exit_success(result)
        assert_output_contains(result, "Exported 1 results")
        # Verify file was created
        assert output_file.exists()

    def test_search_no_highlighting(self, cli_runner, mock_search_engine):
        """Test search with highlighting disabled."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            cli_runner.invoke(["search", "quantum", "--no-highlight"])

        assert mock_search_engine.search.called
        call_kwargs = mock_search_engine.search.call_args[1]
        assert call_kwargs.get("highlight_results") is False

    def test_search_wildcard_query(self, cli_runner, mock_search_engine):
        """Test search with wildcard patterns."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            result = cli_runner.invoke(["search", "quant*"])

        assert_exit_success(result)
        assert mock_search_engine.search.called

    def test_search_phrase_query(self, cli_runner, mock_search_engine):
        """Test search with exact phrase."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            result = cli_runner.invoke(["search", '"quantum computing"'])

        assert_exit_success(result)
        assert mock_search_engine.search.called

    def test_search_range_query(self, cli_runner, mock_search_engine):
        """Test search with range queries."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            result = cli_runner.invoke(["search", "year:2020..2024"])

        assert_exit_success(result)

    def test_search_fuzzy_query(self, cli_runner, populated_repository):
        """Test search with fuzzy matching."""
        # Create a mock SearchService
        from bibmgr.search import SearchService

        mock_search_service = Mock(spec=SearchService)

        mock_search_service.search.return_value = SearchResultCollection(
            query="machne~",
            matches=[
                SearchMatch(
                    entry_key="smith2023",
                    score=0.85,
                    highlights={"title": ["<mark>Machine</mark> Learning for Climate"]},
                )
            ],
            total=1,
            facets=[],
            suggestions=[
                SearchSuggestion(
                    suggestion="machine",
                    suggestion_type="spell",
                    confidence=0.9,
                    description="Showing results for: machine",
                )
            ],
            statistics=SearchStatistics(total_results=5, search_time_ms=12),
        )

        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_service,
        ):
            with patch(
                "bibmgr.cli.commands.search.get_repository",
                return_value=populated_repository,
            ):
                result = cli_runner.invoke(["search", "machne~"])

        assert_exit_success(result)
        assert_output_contains(result, "smith2023")  # Should show result
        assert_output_contains(
            result, "Showing results for: machine"
        )  # Should show suggestion


class TestFindCommand:
    """Test the 'bib find' advanced query builder command."""

    def test_find_interactive_mode(self, cli_runner, mock_search_engine):
        """Test interactive query builder."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            # Simulate building a query interactively
            user_input = "\n".join(
                [
                    "1",  # Add field condition
                    "author",  # Field
                    "contains",  # Operator
                    "Doe",  # Value
                    "3",  # Add another condition
                    "year",  # Field
                    ">=",  # Operator
                    "2020",  # Value
                    "5",  # Execute search
                ]
            )
            result = cli_runner.invoke(["find"], input=user_input)

        assert_exit_success(result)
        assert_output_contains(result, "Query Builder", "Add field condition")

    def test_find_with_preset_filters(self, cli_runner, mock_search_engine):
        """Test find with command-line filters."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            result = cli_runner.invoke(
                ["find", "--author", "Doe", "--year", "2024", "--type", "article"]
            )

        assert_exit_success(result)

    def test_find_recent_entries(self, cli_runner, mock_search_engine):
        """Test finding recent entries."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            result = cli_runner.invoke(["find", "--recent", "30"])

        assert_exit_success(result)
        assert_output_contains(result, "Recent entries")

    def test_find_by_tags(self, cli_runner, mock_search_engine):
        """Test finding entries by tags."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            result = cli_runner.invoke(
                ["find", "--tag", "quantum", "--tag", "important"]
            )

        assert_exit_success(result)

    def test_find_unread_entries(self, cli_runner, mock_search_engine):
        """Test finding unread entries."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            result = cli_runner.invoke(["find", "--unread"])

        assert_exit_success(result)

    def test_find_by_rating(self, cli_runner, mock_search_engine):
        """Test finding entries by rating."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            result = cli_runner.invoke(["find", "--min-rating", "4"])

        assert_exit_success(result)

    def test_find_save_query(self, cli_runner, mock_search_engine):
        """Test saving a query for reuse."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            result = cli_runner.invoke(
                ["find", "--author", "Doe", "--save-as", "doe-papers"]
            )

        assert_exit_success(result)
        assert_output_contains(result, "Query saved as 'doe-papers'")


class TestSimilarCommand:
    """Test the 'bib similar' command."""

    def test_similar_entries(
        self, cli_runner, mock_search_engine, populated_repository
    ):
        """Test finding similar entries."""
        mock_search_engine.more_like_this.return_value = SearchResultCollection(
            query="more_like:doe2024",
            matches=[
                SearchMatch(entry_key="smith2023", score=0.85),
                SearchMatch(entry_key="jones2022", score=0.75),
            ],
            total=2,
            facets=[],
            suggestions=[],
            statistics=SearchStatistics(total_results=2, search_time_ms=20),
        )

        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            with patch(
                "bibmgr.cli.commands.search.get_repository",
                return_value=populated_repository,
            ):
                result = cli_runner.invoke(["similar", "doe2024"])

        assert_exit_success(result)
        assert_output_contains(result, "Similar to: doe2024", "smith2023", "jones2022")
        assert mock_search_engine.more_like_this.called

    def test_similar_with_limit(
        self, cli_runner, mock_search_engine, populated_repository
    ):
        """Test finding similar entries with limit."""
        # Set up mock to return some results
        mock_search_engine.more_like_this.return_value = SearchResultCollection(
            query="more_like:doe2024",
            matches=[SearchMatch(entry_key="smith2023", score=0.85)],
            total=1,
            facets=[],
            suggestions=[],
            statistics=SearchStatistics(total_results=0, search_time_ms=10),
        )

        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            with patch(
                "bibmgr.cli.commands.search.get_repository",
                return_value=populated_repository,
            ):
                cli_runner.invoke(["similar", "doe2024", "--limit", "5"])

        assert mock_search_engine.more_like_this.called
        call_args = mock_search_engine.more_like_this.call_args
        # Check that limit=5 was passed
        assert call_args[0][0] == "doe2024"  # entry key
        assert call_args[1]["limit"] == 5  # limit as keyword arg

    def test_similar_with_min_score(
        self, cli_runner, mock_search_engine, populated_repository
    ):
        """Test finding similar entries with minimum score threshold."""
        # Set up mock to return some results
        mock_search_engine.more_like_this.return_value = SearchResultCollection(
            query="more_like:doe2024",
            matches=[SearchMatch(entry_key="smith2023", score=0.85)],
            total=1,
            facets=[],
            suggestions=[],
            statistics=SearchStatistics(total_results=0, search_time_ms=10),
        )

        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            with patch(
                "bibmgr.cli.commands.search.get_repository",
                return_value=populated_repository,
            ):
                cli_runner.invoke(["similar", "doe2024", "--min-score", "0.8"])

        assert mock_search_engine.more_like_this.called
        call_args = mock_search_engine.more_like_this.call_args
        assert call_args[0][2] == 0.8  # min_score

    def test_similar_nonexistent_entry(
        self, cli_runner, mock_search_engine, entry_repository
    ):
        """Test similar command with nonexistent entry."""
        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            with patch(
                "bibmgr.cli.commands.search.get_repository",
                return_value=entry_repository,
            ):
                result = cli_runner.invoke(["similar", "nonexistent"])

        assert_exit_failure(result)
        assert_output_contains(result, "Entry not found")

    def test_similar_no_results(
        self, cli_runner, mock_search_engine, populated_repository
    ):
        """Test when no similar entries are found."""
        mock_search_engine.more_like_this.return_value = SearchResultCollection(
            query="more_like:unique2024",
            matches=[],
            total=0,
            facets=[],
            suggestions=[],
            statistics=SearchStatistics(total_results=0, search_time_ms=15),
        )

        with patch(
            "bibmgr.cli.commands.search.get_search_service",
            return_value=mock_search_engine,
        ):
            with patch(
                "bibmgr.cli.commands.search.get_repository",
                return_value=populated_repository,
            ):
                result = cli_runner.invoke(["similar", "doe2024"])

        assert_exit_success(result)
        assert_output_contains(result, "No similar entries found")


# Test helpers
def assert_exit_success(result):
    """Assert CLI command exited successfully."""
    assert result.exit_code == 0, f"Command failed: {result.output}"


def assert_exit_failure(result, expected_code=1):
    """Assert CLI command failed with expected code."""
    assert result.exit_code == expected_code, (
        f"Expected exit code {expected_code}, got {result.exit_code}: {result.output}"
    )


def assert_output_contains(result, *expected):
    """Assert CLI output contains expected strings."""
    for text in expected:
        assert text in result.output, f"Expected '{text}' in output:\n{result.output}"


def assert_output_not_contains(result, *unexpected):
    """Assert CLI output does not contain strings."""
    for text in unexpected:
        assert text not in result.output, (
            f"Unexpected '{text}' in output:\n{result.output}"
        )
