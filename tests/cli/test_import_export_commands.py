"""Tests for import and export CLI commands.

This module comprehensively tests import/export functionality including:
- Importing from various formats (BibTeX, RIS, JSON)
- Exporting to various formats
- Format detection and validation
- Duplicate handling during import
- Batch operations and progress tracking
- Error handling and recovery
"""

from unittest.mock import Mock, patch

from bibmgr.operations.results import OperationResult, ResultStatus
from bibmgr.operations.workflows import ExportFormat, ImportFormat


def create_mock_workflow_result(
    status=ResultStatus.SUCCESS,
    message="Import completed",
    imported=0,
    skipped=0,
    errors=0,
    entries=None,
):
    """Create a mock workflow result matching CLI expectations."""
    mock_result = Mock()

    # WorkflowResult interface properties
    mock_result.success = status == ResultStatus.SUCCESS
    mock_result.partial_success = status == ResultStatus.PARTIAL_SUCCESS
    mock_result.successful_entities = entries or []
    mock_result.failed_steps = []

    # get_summary method
    def get_summary():
        return {
            "imported": imported,
            "skipped": skipped,
            "failed_steps": errors,
        }

    mock_result.get_summary = get_summary

    # Legacy OperationResult interface (for compatibility)
    mock_result.status = status
    mock_result.message = message
    mock_result.data = {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
    }
    if entries:
        mock_result.data["entries"] = entries
    mock_result.errors = []
    return mock_result


def create_mock_export_result(
    status=ResultStatus.SUCCESS,
    message="Export completed",
    exported=0,
    format="bibtex",
    content=None,
    entries=None,
):
    """Create a mock export workflow result matching CLI expectations."""
    mock_result = Mock()

    # WorkflowResult interface properties
    mock_result.success = status == ResultStatus.SUCCESS
    mock_result.partial_success = status == ResultStatus.PARTIAL_SUCCESS
    mock_result.successful_entities = entries or []
    mock_result.failed_steps = []

    # get_summary method
    def get_summary():
        summary = {
            "exported": exported,
            "format": format,
            "failed_steps": 0,
        }
        if content:
            summary["content"] = content
        return summary

    mock_result.get_summary = get_summary

    # Legacy OperationResult interface (for compatibility)
    mock_result.status = status
    mock_result.message = message
    mock_result.data = {
        "exported": exported,
        "format": format,
    }
    if content:
        mock_result.data["content"] = content
    mock_result.errors = []
    return mock_result


class TestImportCommand:
    """Test the 'bib import' command."""

    def test_import_bibtex_file(self, cli_runner, repository_manager, temp_bibtex_file):
        """Test importing a BibTeX file."""
        workflow = Mock()
        workflow.execute.return_value = create_mock_workflow_result(
            imported=2, entries=["doe2024", "smith2023"]
        )

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_event_bus", return_value=Mock()
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.ImportWorkflow",
                    return_value=workflow,
                ):
                    result = cli_runner.invoke(["import", str(temp_bibtex_file)])

        assert_exit_success(result)
        assert_output_contains(result, "Import completed", "Imported: 2")

        # Verify workflow was called with correct format
        workflow.execute.assert_called_once()
        call_args = workflow.execute.call_args[0]
        assert call_args[0] == temp_bibtex_file
        assert call_args[1] == ImportFormat.AUTO  # Default when not specified

    def test_import_json_file(self, cli_runner, repository_manager, temp_json_file):
        """Test importing a JSON file."""
        workflow = Mock()
        workflow.execute.return_value = create_mock_workflow_result(imported=3)

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_event_bus", return_value=Mock()
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.ImportWorkflow",
                    return_value=workflow,
                ):
                    result = cli_runner.invoke(["import", str(temp_json_file)])

        assert_exit_success(result)
        assert (
            workflow.execute.call_args[0][1] == ImportFormat.AUTO
        )  # Default when not specified

    def test_import_with_format_override(
        self, cli_runner, repository_manager, tmp_path
    ):
        """Test importing with explicit format specification."""
        # Create file with ambiguous extension
        file_path = tmp_path / "data.txt"
        file_path.write_text("@article{test2024, title={Test}}")

        workflow = Mock()
        workflow.execute.return_value = create_mock_workflow_result(imported=1)

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_event_bus", return_value=Mock()
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.ImportWorkflow",
                    return_value=workflow,
                ):
                    result = cli_runner.invoke(
                        ["import", str(file_path), "--format", "bibtex"]
                    )

        assert_exit_success(result)
        assert workflow.execute.call_args[0][1] == ImportFormat.BIBTEX

    def test_import_no_validation(
        self, cli_runner, repository_manager, temp_bibtex_file
    ):
        """Test importing without validation."""
        workflow = Mock()
        workflow.execute.return_value = create_mock_workflow_result(imported=2)

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_event_bus", return_value=Mock()
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.ImportWorkflow",
                    return_value=workflow,
                ):
                    result = cli_runner.invoke(
                        ["import", str(temp_bibtex_file), "--no-validate"]
                    )

        assert_exit_success(result)
        config = workflow.execute.call_args[0][2]  # Third argument is config
        assert config.validate is False

    def test_import_with_duplicate_handling(
        self, cli_runner, repository_manager, temp_bibtex_file
    ):
        """Test import with duplicate entry handling."""
        workflow = Mock()
        mock_result = create_mock_workflow_result(
            status=ResultStatus.PARTIAL_SUCCESS,
            message="Import completed with duplicates",
            imported=1,
            skipped=1,
            entries=["smith2023"],  # 1 successfully imported entry
        )
        # Add duplicates to both data and summary
        mock_result.data["duplicates"] = ["doe2024"]
        original_get_summary = mock_result.get_summary

        def get_summary_with_duplicates():
            summary = original_get_summary()
            summary["duplicates"] = ["doe2024"]
            return summary

        mock_result.get_summary = get_summary_with_duplicates
        workflow.execute.return_value = mock_result

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_event_bus", return_value=Mock()
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.ImportWorkflow",
                    return_value=workflow,
                ):
                    result = cli_runner.invoke(
                        ["import", str(temp_bibtex_file), "--on-duplicate", "skip"]
                    )

        assert_exit_success(result)
        assert_output_contains(result, "Skipped: 1", "Duplicates:")

    def test_import_merge_duplicates(
        self, cli_runner, repository_manager, temp_bibtex_file
    ):
        """Test importing with duplicate merging."""
        workflow = Mock()
        mock_result = create_mock_workflow_result(imported=1, entries=["doe2024"])
        mock_result.data["merged"] = 1
        # Add merged to summary
        original_get_summary = mock_result.get_summary

        def get_summary_with_merged():
            summary = original_get_summary()
            summary["merged"] = 1
            return summary

        mock_result.get_summary = get_summary_with_merged
        workflow.execute.return_value = mock_result

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_event_bus", return_value=Mock()
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.ImportWorkflow",
                    return_value=workflow,
                ):
                    result = cli_runner.invoke(
                        ["import", str(temp_bibtex_file), "--on-duplicate", "merge"]
                    )

        assert_exit_success(result)
        assert_output_contains(result, "Merged: 1")

    def test_import_with_collection(
        self, cli_runner, repository_manager, temp_bibtex_file, collection_repository
    ):
        """Test importing entries and adding to collection."""
        workflow = Mock()
        mock_result = create_mock_workflow_result(
            imported=2, entries=["doe2024", "smith2023"]
        )
        workflow.execute.return_value = mock_result

        collection_handler = Mock()
        collection_handler.add_entries.return_value = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Added to collection",
        )

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_event_bus", return_value=Mock()
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.ImportWorkflow",
                    return_value=workflow,
                ):
                    with patch(
                        "bibmgr.cli.commands.import_export.get_collection_handler",
                        return_value=collection_handler,
                    ):
                        result = cli_runner.invoke(
                            [
                                "import",
                                str(temp_bibtex_file),
                                "--add-to-collection",
                                "my-collection",
                            ]
                        )

        assert_exit_success(result)
        assert_output_contains(result, "Added 2 entries to collection")
        collection_handler.add_entries.assert_called_once()

    def test_import_with_tags(
        self, cli_runner, repository_manager, temp_bibtex_file, metadata_store
    ):
        """Test importing entries and adding tags."""
        workflow = Mock()
        mock_result = create_mock_workflow_result(
            imported=2, entries=["doe2024", "smith2023"]
        )
        workflow.execute.return_value = mock_result

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_event_bus", return_value=Mock()
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.ImportWorkflow",
                    return_value=workflow,
                ):
                    with patch(
                        "bibmgr.cli.commands.import_export.get_metadata_store",
                        return_value=metadata_store,
                    ):
                        result = cli_runner.invoke(
                            [
                                "import",
                                str(temp_bibtex_file),
                                "--tag",
                                "imported",
                                "--tag",
                                "2024-batch",
                            ]
                        )

        assert_exit_success(result)
        assert_output_contains(result, "Tagged 2 entries")

        # Verify tags were added
        for key in ["doe2024", "smith2023"]:
            metadata = metadata_store.get_metadata(key)
            assert "imported" in metadata.tags
            assert "2024-batch" in metadata.tags

    def test_import_directory(self, cli_runner, repository_manager, tmp_path):
        """Test importing all files from a directory."""
        # Create multiple BibTeX files
        (tmp_path / "file1.bib").write_text("@article{entry1, title={Entry 1}}")
        (tmp_path / "file2.bib").write_text("@article{entry2, title={Entry 2}}")
        (tmp_path / "ignore.txt").write_text("Not a bib file")

        workflow = Mock()
        workflow.execute.side_effect = [
            create_mock_workflow_result(imported=1),
            create_mock_workflow_result(imported=1),
        ]

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_event_bus", return_value=Mock()
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.ImportWorkflow",
                    return_value=workflow,
                ):
                    result = cli_runner.invoke(["import", str(tmp_path)])

        assert_exit_success(result)
        assert_output_contains(result, "Found 2 files to import", "Total imported: 2")

    def test_import_with_progress(
        self, cli_runner, repository_manager, temp_bibtex_file
    ):
        """Test import with progress tracking."""
        workflow = Mock()

        # Simulate progress updates
        def execute_with_progress(path, format, config):
            # Would normally publish progress events
            mock_result = create_mock_workflow_result(imported=2)
            mock_result.steps = [
                OperationResult(ResultStatus.SUCCESS, "Parsed file"),
                OperationResult(ResultStatus.SUCCESS, "Validated entries"),
                OperationResult(ResultStatus.SUCCESS, "Imported entries"),
            ]
            return mock_result

        workflow.execute.side_effect = execute_with_progress

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_event_bus", return_value=Mock()
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.ImportWorkflow",
                    return_value=workflow,
                ):
                    result = cli_runner.invoke(["import", str(temp_bibtex_file)])

        assert_exit_success(result)

    def test_import_error_handling(self, cli_runner, repository_manager, tmp_path):
        """Test import error handling."""
        bad_file = tmp_path / "bad.bib"
        bad_file.write_text("@article{bad, title=}")  # Invalid BibTeX

        workflow = Mock()
        mock_result = create_mock_workflow_result(
            status=ResultStatus.ERROR, message="Import failed", imported=0, errors=1
        )
        mock_result.errors = ["Failed to parse BibTeX: Unexpected end of input"]
        # Create mock failed steps
        from unittest.mock import Mock as MockStep

        failed_step = MockStep()
        failed_step.message = "Failed to parse BibTeX: Unexpected end of input"
        failed_step.errors = ["Failed to parse BibTeX: Unexpected end of input"]
        mock_result.failed_steps = [failed_step]
        workflow.execute.return_value = mock_result

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_event_bus", return_value=Mock()
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.ImportWorkflow",
                    return_value=workflow,
                ):
                    result = cli_runner.invoke(["import", str(bad_file)])

        assert_exit_failure(result)
        assert_output_contains(result, "Import failed", "Failed to parse")


class TestExportCommand:
    """Test the 'bib export' command."""

    def test_export_all_entries(
        self, cli_runner, populated_repository, tmp_path, repository_manager
    ):
        """Test exporting all entries."""
        output_file = tmp_path / "export.bib"

        workflow = Mock()
        workflow.execute.return_value = create_mock_export_result(
            exported=3, entries=["entry1", "entry2", "entry3"]
        )

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_repository",
                return_value=populated_repository,
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.get_event_bus",
                    return_value=Mock(),
                ):
                    with patch(
                        "bibmgr.cli.commands.import_export.ExportWorkflow",
                        return_value=workflow,
                    ):
                        result = cli_runner.invoke(["export", str(output_file)])

        assert_exit_success(result)
        assert_output_contains(result, "Exported 3 entries")

    def test_export_specific_entries(
        self, cli_runner, populated_repository, tmp_path, repository_manager
    ):
        """Test exporting specific entries by key."""
        output_file = tmp_path / "export.bib"

        workflow = Mock()
        workflow.execute.return_value = create_mock_export_result(
            exported=2, entries=["doe2024", "smith2023"]
        )

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_repository",
                return_value=populated_repository,
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.get_event_bus",
                    return_value=Mock(),
                ):
                    with patch(
                        "bibmgr.cli.commands.import_export.ExportWorkflow",
                        return_value=workflow,
                    ):
                        result = cli_runner.invoke(
                            ["export", str(output_file), "--keys", "doe2024,smith2023"]
                        )

        assert_exit_success(result)
        assert_output_contains(result, "Exported 2 entries")

        # Verify correct keys were passed
        assert workflow.execute.call_args[1]["entry_keys"] == ["doe2024", "smith2023"]

    def test_export_with_format(
        self, cli_runner, populated_repository, tmp_path, repository_manager
    ):
        """Test exporting in different formats."""
        # Test JSON export
        json_file = tmp_path / "export.json"
        workflow = Mock()
        workflow.execute.return_value = create_mock_export_result(exported=3)

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_repository",
                return_value=populated_repository,
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.get_event_bus",
                    return_value=Mock(),
                ):
                    with patch(
                        "bibmgr.cli.commands.import_export.ExportWorkflow",
                        return_value=workflow,
                    ):
                        result = cli_runner.invoke(
                            ["export", str(json_file), "--format", "json"]
                        )

        assert_exit_success(result)
        config = workflow.execute.call_args[1]["config"]
        assert config.format == ExportFormat.JSON

    def test_export_from_collection(
        self,
        cli_runner,
        populated_repository,
        collection_repository,
        sample_collections,
        tmp_path,
        repository_manager,
    ):
        """Test exporting entries from a collection."""
        collection = sample_collections[0]  # Has doe2024, smith2023
        collection_repository.save(collection)

        output_file = tmp_path / "export.bib"

        workflow = Mock()
        workflow.execute.return_value = create_mock_export_result(exported=2)

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_repository",
                return_value=populated_repository,
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.get_event_bus",
                    return_value=Mock(),
                ):
                    with patch(
                        "bibmgr.cli.commands.import_export.get_collection_repository",
                        return_value=collection_repository,
                    ):
                        with patch(
                            "bibmgr.cli.commands.import_export.ExportWorkflow",
                            return_value=workflow,
                        ):
                            result = cli_runner.invoke(
                                [
                                    "export",
                                    str(output_file),
                                    "--collection",
                                    "PhD Research",
                                ]
                            )

        assert_exit_success(result)
        assert_output_contains(result, "Exporting from collection: PhD Research")

        assert set(workflow.execute.call_args[1]["entry_keys"]) == {
            "doe2024",
            "smith2023",
        }

    def test_export_with_query(
        self,
        cli_runner,
        populated_repository,
        mock_search_engine,
        tmp_path,
        repository_manager,
    ):
        """Test exporting entries matching a search query."""
        from bibmgr.search.results import (
            SearchMatch,
            SearchResultCollection,
            SearchStatistics,
        )

        # Configure search results - override the side_effect from conftest.py
        mock_search_engine.search.side_effect = None
        mock_search_engine.search.return_value = SearchResultCollection(
            query="year:2024",
            matches=[
                SearchMatch(entry_key="doe2024", score=1.0),
            ],
            total=1,
            facets=[],
            suggestions=[],
            statistics=SearchStatistics(total_results=1, search_time_ms=5),
        )

        output_file = tmp_path / "export.bib"

        workflow = Mock()
        workflow.execute.return_value = create_mock_export_result(exported=1)

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_repository",
                return_value=populated_repository,
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.get_event_bus",
                    return_value=Mock(),
                ):
                    with patch(
                        "bibmgr.cli.commands.import_export.get_search_service",
                        return_value=mock_search_engine,
                    ):
                        with patch(
                            "bibmgr.cli.commands.import_export.ExportWorkflow",
                            return_value=workflow,
                        ):
                            result = cli_runner.invoke(
                                ["export", str(output_file), "--query", "year:2024"]
                            )

        # The test should exit with code 0 since matches were found
        assert result.exit_code == 0
        assert_output_contains(result, "Found 1 entries matching query")

    def test_export_with_filters(
        self, cli_runner, populated_repository, tmp_path, repository_manager
    ):
        """Test exporting with field filters."""
        output_file = tmp_path / "export.bib"

        workflow = Mock()
        workflow.execute.return_value = create_mock_export_result(exported=1)

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_repository",
                return_value=populated_repository,
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.get_event_bus",
                    return_value=Mock(),
                ):
                    with patch(
                        "bibmgr.cli.commands.import_export.ExportWorkflow",
                        return_value=workflow,
                    ):
                        result = cli_runner.invoke(
                            [
                                "export",
                                str(output_file),
                                "--type",
                                "article",
                                "--year",
                                "2024",
                            ]
                        )

        assert_exit_success(result)

    def test_export_append_mode(
        self, cli_runner, populated_repository, tmp_path, repository_manager
    ):
        """Test appending to existing export file."""
        output_file = tmp_path / "export.bib"
        output_file.write_text("% Existing content\n")

        workflow = Mock()
        workflow.execute.return_value = create_mock_export_result(exported=3)

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_repository",
                return_value=populated_repository,
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.get_event_bus",
                    return_value=Mock(),
                ):
                    with patch(
                        "bibmgr.cli.commands.import_export.ExportWorkflow",
                        return_value=workflow,
                    ):
                        result = cli_runner.invoke(
                            ["export", str(output_file), "--append"]
                        )

        assert_exit_success(result)
        # Append is handled at the export implementation level, not in config

    def test_export_overwrite_protection(
        self, cli_runner, populated_repository, tmp_path, repository_manager
    ):
        """Test export prevents overwriting without confirmation."""
        output_file = tmp_path / "export.bib"
        output_file.write_text("% Important existing data")

        workflow = Mock()
        workflow.execute.return_value = create_mock_export_result(exported=3)

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_repository",
                return_value=populated_repository,
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.get_event_bus",
                    return_value=Mock(),
                ):
                    with patch(
                        "bibmgr.cli.commands.import_export.ExportWorkflow",
                        return_value=workflow,
                    ):
                        # User says no to overwrite
                        result = cli_runner.invoke(
                            ["export", str(output_file)], input="n\n"
                        )

        assert_exit_success(result)
        assert_output_contains(result, "already exists", "cancelled")
        workflow.execute.assert_not_called()

    def test_export_stdout(self, cli_runner, populated_repository, repository_manager):
        """Test exporting to stdout."""
        workflow = Mock()
        workflow.execute.return_value = create_mock_export_result(
            exported=3,
            content="@article{doe2024,\n  title={Test}\n}\n",
            entries=["doe2024", "smith2023", "jones2022"],
        )

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_repository",
                return_value=populated_repository,
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.get_event_bus",
                    return_value=Mock(),
                ):
                    with patch(
                        "bibmgr.cli.commands.import_export.ExportWorkflow",
                        return_value=workflow,
                    ):
                        result = cli_runner.invoke(["export", "-"])

        assert_exit_success(result)
        assert_output_contains(result, "@article{doe2024")

    def test_export_empty_result(
        self, cli_runner, entry_repository, tmp_path, repository_manager
    ):
        """Test exporting when no entries match criteria."""
        output_file = tmp_path / "export.bib"

        workflow = Mock()
        workflow.execute.return_value = create_mock_export_result(
            exported=0, message="No entries to export"
        )

        with patch(
            "bibmgr.cli.commands.import_export.get_repository_manager",
            return_value=repository_manager,
        ):
            with patch(
                "bibmgr.cli.commands.import_export.get_repository",
                return_value=entry_repository,
            ):
                with patch(
                    "bibmgr.cli.commands.import_export.get_event_bus",
                    return_value=Mock(),
                ):
                    with patch(
                        "bibmgr.cli.commands.import_export.ExportWorkflow",
                        return_value=workflow,
                    ):
                        result = cli_runner.invoke(
                            ["export", str(output_file), "--type", "nonexistent"]
                        )

        assert_exit_success(result)
        assert_output_contains(result, "No entries exported")


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
