"""Tests for quality check and maintenance CLI commands.

This module comprehensively tests quality functionality including:
- Entry validation (individual and batch)
- Duplicate detection and merging
- Data cleanup and normalization
- Quality reports and statistics
- Consistency checking
- Field completion suggestions
"""

from unittest.mock import Mock, patch

from bibmgr.core.models import ValidationError
from bibmgr.operations.results import OperationResult, ResultStatus


class TestCheckCommand:
    """Test the 'bib check' command for quality checking."""

    def test_check_single_entry(self, cli_runner, populated_repository):
        """Test checking quality of a single entry."""
        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Validation completed",
            validation_errors=[
                ValidationError("abstract", "Missing abstract", "warning"),
                ValidationError("doi", "Missing DOI", "info"),
            ],
            data={"severity_counts": {"error": 0, "warning": 1, "info": 1}},
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                result = cli_runner.invoke(["check", "doe2024"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "Checking entry: doe2024",
            "Missing abstract",
            "Missing DOI",
            "Warnings: 1",
            "Info: 1",
        )

    def test_check_multiple_entries(self, cli_runner, populated_repository):
        """Test checking multiple entries."""
        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Batch validation completed",
            data={
                "total_checked": 2,
                "passed": 1,
                "failed": 1,
                "results": {
                    "doe2024": {
                        "errors": [],
                        "warnings": [
                            {"field": "abstract", "message": "Missing abstract"}
                        ],
                    },
                    "smith2023": {
                        "errors": [
                            {"field": "journal", "message": "Missing required field"}
                        ],
                        "warnings": [],
                    },
                },
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                result = cli_runner.invoke(["check", "doe2024", "smith2023"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "Checked 2 entries",
            "Passed: 1",
            "Failed: 1",
        )

    def test_check_all_entries(self, cli_runner, populated_repository):
        """Test checking all entries in the repository."""
        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Repository check completed",
            data={
                "total_checked": 3,
                "passed": 2,
                "failed": 1,
                "severity_summary": {
                    "errors": 2,
                    "warnings": 5,
                    "info": 10,
                },
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                result = cli_runner.invoke(["check", "--all"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "Checking all 3 entries",
            "Passed: 2",
            "Failed: 1",
            "Total issues found:",
            "Errors: 2",
            "Warnings: 5",
        )

    def test_check_with_severity_filter(self, cli_runner, populated_repository):
        """Test checking with severity level filter."""
        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Validation completed",
            validation_errors=[
                ValidationError("year", "Invalid year", "error"),
                ValidationError("abstract", "Missing abstract", "warning"),
                ValidationError("keywords", "Consider adding keywords", "info"),
            ],
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                result = cli_runner.invoke(["check", "doe2024", "--severity", "error"])

        assert_exit_success(result)
        assert_output_contains(result, "Invalid year")
        assert_output_not_contains(
            result, "Missing abstract", "Consider adding keywords"
        )

    def test_check_fix_mode(self, cli_runner, populated_repository):
        """Test check with automatic fixing of issues."""
        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Fixed issues",
            data={
                "fixed": [
                    {"field": "title", "issue": "Fixed capitalization"},
                    {"field": "pages", "issue": "Normalized page range"},
                ],
                "unfixable": [
                    {"field": "doi", "issue": "Cannot automatically add DOI"},
                ],
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                result = cli_runner.invoke(["check", "doe2024", "--fix"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "Fixed 2 issues",
            "Fixed capitalization",
            "Normalized page range",
            "Could not fix:",
            "Cannot automatically add DOI",
        )

    def test_check_output_formats(self, cli_runner, populated_repository):
        """Test different output formats for check results."""
        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Validation completed",
            validation_errors=[
                ValidationError("abstract", "Missing abstract", "warning"),
            ],
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                # Table format (default)
                result = cli_runner.invoke(["check", "doe2024", "--format", "table"])
                assert_exit_success(result)

                # JSON format
                result = cli_runner.invoke(["check", "doe2024", "--format", "json"])
                assert_exit_success(result)
                assert "{" in result.output  # Valid JSON

                # CSV format
                result = cli_runner.invoke(["check", "doe2024", "--format", "csv"])
                assert_exit_success(result)
                assert "entry_key,field,severity,message" in result.output


class TestDedupeCommand:
    """Test the 'bib dedupe' command for duplicate detection."""

    def test_dedupe_find_duplicates(self, cli_runner, populated_repository):
        """Test finding duplicate entries."""
        workflow = Mock()
        workflow.execute.return_value = create_mock_workflow_result(
            status=ResultStatus.SUCCESS,
            message="Deduplication completed",
            data={
                "duplicates": [
                    {
                        "group_id": "1",
                        "entries": ["doe2024", "doe2024b"],
                        "similarity": 0.95,
                        "reason": "Same title and authors",
                    },
                    {
                        "group_id": "2",
                        "entries": ["smith2023", "smith2023a"],
                        "similarity": 0.88,
                        "reason": "Similar title and year",
                    },
                ],
                "total_groups": 2,
                "total_duplicates": 4,
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_repository_manager",
                return_value=Mock(),
            ):
                with patch(
                    "bibmgr.cli.commands.quality.get_event_bus", return_value=Mock()
                ):
                    with patch(
                        "bibmgr.cli.commands.quality.DeduplicationWorkflow",
                        return_value=workflow,
                    ):
                        result = cli_runner.invoke(["dedupe"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "Found 2 duplicate groups",
            "4 total entries",
            "doe2024, doe2024b",
            "Same title and authors",
            "Similarity: 95%",
        )

    def test_dedupe_auto_merge(self, cli_runner, populated_repository):
        """Test automatic merging of duplicates."""
        workflow = Mock()
        workflow.execute.return_value = create_mock_workflow_result(
            status=ResultStatus.SUCCESS,
            message="Deduplication completed",
            data={
                "duplicates": [{"group_id": "1", "entries": ["doe2024", "doe2024b"]}],
                "merged": 1,
                "skipped": 0,
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_repository_manager",
                return_value=Mock(),
            ):
                with patch(
                    "bibmgr.cli.commands.quality.get_event_bus", return_value=Mock()
                ):
                    with patch(
                        "bibmgr.cli.commands.quality.DeduplicationWorkflow",
                        return_value=workflow,
                    ):
                        result = cli_runner.invoke(["dedupe", "--auto-merge"])

        assert_exit_success(result)
        assert_output_contains(result, "Automatically merged 1 group")

    def test_dedupe_interactive_mode(self, cli_runner, populated_repository):
        """Test interactive duplicate resolution."""
        workflow = Mock()
        workflow.execute.return_value = create_mock_workflow_result(
            status=ResultStatus.SUCCESS,
            message="Deduplication completed",
            data={
                "duplicates": [
                    {
                        "group_id": "1",
                        "entries": ["doe2024", "doe2024b"],
                        "details": {
                            "doe2024": {"title": "Original Title", "year": 2024},
                            "doe2024b": {"title": "Original Title", "year": 2024},
                        },
                    }
                ],
                "resolutions": {"1": "merged"},
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_repository_manager",
                return_value=Mock(),
            ):
                with patch(
                    "bibmgr.cli.commands.quality.get_event_bus", return_value=Mock()
                ):
                    with patch(
                        "bibmgr.cli.commands.quality.DeduplicationWorkflow",
                        return_value=workflow,
                    ):
                        # User chooses to merge
                        result = cli_runner.invoke(
                            ["dedupe", "--interactive"], input="1\n"
                        )

        assert_exit_success(result)
        assert_output_contains(
            result, "How would you like to handle", "[1] Merge entries"
        )

    def test_dedupe_threshold(self, cli_runner, populated_repository):
        """Test deduplication with custom similarity threshold."""
        workflow = Mock()
        workflow.execute.return_value = create_mock_workflow_result(
            status=ResultStatus.SUCCESS,
            message="No duplicates found",
            data={"duplicates": [], "total_groups": 0},
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_repository_manager",
                return_value=Mock(),
            ):
                with patch(
                    "bibmgr.cli.commands.quality.get_event_bus", return_value=Mock()
                ):
                    with patch(
                        "bibmgr.cli.commands.quality.DeduplicationWorkflow",
                        return_value=workflow,
                    ):
                        result = cli_runner.invoke(["dedupe", "--threshold", "0.95"])

        assert_exit_success(result)
        assert_output_contains(result, "No duplicates found")

        # Verify threshold was passed to workflow
        workflow.execute.assert_called_once()
        config = workflow.execute.call_args[0][0]
        assert config.min_similarity == 0.95

    def test_dedupe_by_field(self, cli_runner, populated_repository):
        """Test finding duplicates by specific field."""
        workflow = Mock()
        workflow.execute.return_value = create_mock_workflow_result(
            status=ResultStatus.SUCCESS,
            message="Deduplication completed",
            data={
                "duplicates": [
                    {
                        "group_id": "1",
                        "entries": ["entry1", "entry2"],
                        "reason": "Same DOI",
                    }
                ],
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_repository_manager",
                return_value=Mock(),
            ):
                with patch(
                    "bibmgr.cli.commands.quality.get_event_bus", return_value=Mock()
                ):
                    with patch(
                        "bibmgr.cli.commands.quality.DeduplicationWorkflow",
                        return_value=workflow,
                    ):
                        result = cli_runner.invoke(["dedupe", "--by", "doi"])

        assert_exit_success(result)
        assert_output_contains(result, "Same DOI")

    def test_dedupe_export_report(self, cli_runner, populated_repository, tmp_path):
        """Test exporting deduplication report."""
        report_file = tmp_path / "duplicates.json"

        workflow = Mock()
        workflow.execute.return_value = create_mock_workflow_result(
            status=ResultStatus.SUCCESS,
            message="Deduplication completed",
            data={
                "duplicates": [
                    {"group_id": "1", "entries": ["doe2024", "doe2024b"]},
                ],
                "report_saved": str(report_file),
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_repository_manager",
                return_value=Mock(),
            ):
                with patch(
                    "bibmgr.cli.commands.quality.get_event_bus", return_value=Mock()
                ):
                    with patch(
                        "bibmgr.cli.commands.quality.DeduplicationWorkflow",
                        return_value=workflow,
                    ):
                        result = cli_runner.invoke(
                            ["dedupe", "--export-report", str(report_file)]
                        )

        assert_exit_success(result)
        assert_output_contains(result, "Report saved to")


class TestCleanCommand:
    """Test the 'bib clean' command for data cleanup."""

    def test_clean_all_entries(self, cli_runner, populated_repository):
        """Test cleaning all entries."""
        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Cleanup completed",
            data={
                "cleaned": 3,
                "changes": {
                    "normalized_names": 5,
                    "fixed_capitalization": 3,
                    "cleaned_whitespace": 10,
                    "normalized_pages": 2,
                },
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                result = cli_runner.invoke(["clean", "--all"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "Cleaned 3 entries",
            "Normalized names: 5",
            "Fixed capitalization: 3",
            "Cleaned whitespace: 10",
        )

    def test_clean_specific_entries(self, cli_runner, populated_repository):
        """Test cleaning specific entries."""
        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Cleanup completed",
            data={"cleaned": 2, "changes": {"total": 4}},
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                result = cli_runner.invoke(["clean", "doe2024", "smith2023"])

        assert_exit_success(result)
        assert_output_contains(result, "Cleaned 2 entries")

    def test_clean_dry_run(self, cli_runner, populated_repository):
        """Test clean in dry-run mode."""
        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Dry run completed",
            data={
                "would_clean": 3,
                "proposed_changes": [
                    {
                        "entry": "doe2024",
                        "field": "author",
                        "change": "Normalize 'Doe, J.' to 'Doe, John'",
                    },
                    {
                        "entry": "smith2023",
                        "field": "title",
                        "change": "Fix capitalization",
                    },
                ],
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                result = cli_runner.invoke(["clean", "--all", "--dry-run"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "DRY RUN MODE",
            "Would clean 3 entries",
            "Normalize 'Doe, J.' to 'Doe, John'",
            "Fix capitalization",
        )

    def test_clean_specific_operations(self, cli_runner, populated_repository):
        """Test running specific cleanup operations."""
        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Cleanup completed",
            data={"cleaned": 3, "changes": {"normalized_names": 5}},
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                result = cli_runner.invoke(
                    ["clean", "--all", "--operations", "normalize-names"]
                )

        assert_exit_success(result)
        assert_output_contains(result, "Normalized names: 5")

    def test_clean_with_backup(self, cli_runner, populated_repository, tmp_path):
        """Test clean with backup creation."""
        backup_dir = tmp_path / "backup"

        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Cleanup completed",
            data={
                "cleaned": 3,
                "backup_created": str(backup_dir / "backup-20240101-120000.json"),
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                result = cli_runner.invoke(
                    ["clean", "--all", "--backup", str(backup_dir)]
                )

        assert_exit_success(result)
        assert_output_contains(result, "Backup created")


class TestQualityReportCommand:
    """Test the 'bib report quality' command."""

    def test_quality_report_basic(self, cli_runner, populated_repository):
        """Test generating basic quality report."""
        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Report generated",
            data={
                "total_entries": 100,
                "issues_by_severity": {"error": 5, "warning": 20, "info": 50},
                "completeness_score": 85.5,
                "common_issues": [
                    {"issue": "Missing abstract", "count": 15},
                    {"issue": "Missing DOI", "count": 12},
                    {"issue": "Incomplete author names", "count": 8},
                ],
                "entries_by_quality": {
                    "excellent": 20,
                    "good": 50,
                    "fair": 25,
                    "poor": 5,
                },
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                result = cli_runner.invoke(["report", "quality"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "Quality Report",
            "Total entries: 100",
            "Completeness score: 85.5%",
            "Issues by severity:",
            "Errors: 5",
            "Common issues:",
            "Missing abstract (15)",
            "Quality distribution:",
            "Excellent: 20",
        )

    def test_quality_report_detailed(self, cli_runner, populated_repository):
        """Test generating detailed quality report."""
        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Detailed report generated",
            data={
                "total_entries": 3,
                "entry_details": {
                    "doe2024": {
                        "quality_score": 90,
                        "completeness": 95,
                        "issues": [
                            {"field": "keywords", "message": "Consider adding keywords"}
                        ],
                    },
                    "smith2023": {
                        "quality_score": 75,
                        "completeness": 80,
                        "issues": [
                            {"field": "abstract", "message": "Missing abstract"},
                            {"field": "doi", "message": "Missing DOI"},
                        ],
                    },
                },
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                result = cli_runner.invoke(["report", "quality", "--detailed"])

        assert_exit_success(result)
        assert_output_contains(
            result,
            "doe2024",
            "Quality: 90%",
            "smith2023",
            "Quality: 75%",
            "Missing abstract",
        )

    def test_quality_report_export(self, cli_runner, populated_repository, tmp_path):
        """Test exporting quality report to file."""
        report_file = tmp_path / "quality_report.html"

        handler = Mock()
        handler.execute.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Report exported",
            data={
                "report_path": str(report_file),
                "format": "html",
            },
        )

        with patch(
            "bibmgr.cli.commands.quality.get_repository",
            return_value=populated_repository,
        ):
            with patch(
                "bibmgr.cli.commands.quality.get_quality_handler", return_value=handler
            ):
                result = cli_runner.invoke(
                    [
                        "report",
                        "quality",
                        "--export",
                        str(report_file),
                        "--format",
                        "html",
                    ]
                )

        assert_exit_success(result)
        assert_output_contains(result, "Report exported to")


def create_mock_workflow_result(status=ResultStatus.SUCCESS, message="", data=None):
    """Create a mock workflow result matching CLI expectations."""
    mock_result = Mock()
    mock_result.status = status
    mock_result.message = message
    mock_result.data = data or {}
    mock_result.errors = []

    # For deduplication workflow, the command expects steps with groups data
    if data and "duplicates" in data:
        mock_step = Mock()
        mock_step.data = {
            "groups": [
                {
                    "entries": duplicate["entries"],
                    "similarity": duplicate.get("similarity", 0.9),
                    "reason": duplicate.get("reason", "Similar entries"),
                    "details": {
                        entry: {
                            "title": f"Title for {entry}",
                            "year": 2024,
                            "authors": f"Author of {entry}",
                            "journal": "Some Journal",
                        }
                        for entry in duplicate["entries"]
                    },
                }
                for duplicate in data["duplicates"]
            ]
        }
        mock_result.steps = [mock_step]
    else:
        mock_result.steps = []

    return mock_result


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
