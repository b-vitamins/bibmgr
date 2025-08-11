"""Tests for operation result types.

This module tests the result classes that provide rich information about
operation outcomes including status, errors, and performance metrics.
"""

from datetime import datetime
from uuid import UUID

from bibmgr.core.validators import ValidationError

from ..operations.conftest import create_entry_with_data


class TestResultStatus:
    """Test ResultStatus enum functionality."""

    def test_status_success_check(self):
        """Test is_success method for different statuses."""
        from bibmgr.operations.results import ResultStatus

        # Success statuses
        assert ResultStatus.SUCCESS.is_success()
        assert ResultStatus.PARTIAL_SUCCESS.is_success()
        assert ResultStatus.DRY_RUN.is_success()

        # Failure statuses
        assert not ResultStatus.VALIDATION_FAILED.is_success()
        assert not ResultStatus.NOT_FOUND.is_success()
        assert not ResultStatus.CONFLICT.is_success()
        assert not ResultStatus.ERROR.is_success()
        assert not ResultStatus.TRANSACTION_FAILED.is_success()
        assert not ResultStatus.CANCELLED.is_success()

    def test_status_failure_check(self):
        """Test is_failure method for different statuses."""
        from bibmgr.operations.results import ResultStatus

        # Failure statuses
        assert ResultStatus.VALIDATION_FAILED.is_failure()
        assert ResultStatus.NOT_FOUND.is_failure()
        assert ResultStatus.CONFLICT.is_failure()
        assert ResultStatus.ERROR.is_failure()
        assert ResultStatus.TRANSACTION_FAILED.is_failure()
        assert ResultStatus.CANCELLED.is_failure()

        # Success statuses
        assert not ResultStatus.SUCCESS.is_failure()
        assert not ResultStatus.PARTIAL_SUCCESS.is_failure()
        assert not ResultStatus.DRY_RUN.is_failure()


class TestOperationResult:
    """Test OperationResult class."""

    def test_create_success_result(self):
        """Test creating a successful operation result."""
        from bibmgr.operations.results import OperationResult, ResultStatus

        result = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Operation completed successfully",
            entity_id="test123",
        )

        assert result.status == ResultStatus.SUCCESS
        assert result.message == "Operation completed successfully"
        assert result.entity_id == "test123"
        assert isinstance(result.operation_id, UUID)
        assert isinstance(result.timestamp, datetime)

    def test_create_failure_result_with_errors(self):
        """Test creating a failure result with error details."""
        from bibmgr.operations.results import OperationResult, ResultStatus

        result = OperationResult(
            status=ResultStatus.ERROR,
            message="Operation failed",
            entity_id="fail123",
            errors=["Database connection failed", "Timeout occurred"],
        )

        assert result.status.is_failure()
        assert result.errors is not None
        assert len(result.errors) == 2
        assert "Database connection failed" in result.errors

    def test_create_validation_failure_result(self):
        """Test creating a validation failure result."""
        from bibmgr.operations.results import OperationResult, ResultStatus

        validation_errors = [
            ValidationError(field="author", message="Required field", severity="error"),
            ValidationError(field="year", message="Invalid format", severity="error"),
        ]

        result = OperationResult(
            status=ResultStatus.VALIDATION_FAILED,
            message="Validation failed",
            entity_id="invalid123",
            validation_errors=validation_errors,
        )

        assert result.status == ResultStatus.VALIDATION_FAILED
        assert result.validation_errors is not None
        assert len(result.validation_errors) == 2
        assert result.validation_errors[0].field == "author"

    def test_result_with_data_and_suggestions(self):
        """Test result with additional data and suggestions."""
        from bibmgr.operations.results import OperationResult, ResultStatus

        entry = create_entry_with_data(key="test", title="Test Entry")

        result = OperationResult(
            status=ResultStatus.CONFLICT,
            message="Entry already exists",
            entity_id="test",
            data={"existing_entry": entry, "conflict_type": "key"},
            suggestions={"alternative_key": "test_2", "action": "rename"},
        )

        assert result.data is not None
        assert result.data["conflict_type"] == "key"
        assert result.suggestions is not None
        assert result.suggestions["alternative_key"] == "test_2"

    def test_result_with_warnings(self):
        """Test result with warnings."""
        from bibmgr.operations.results import OperationResult, ResultStatus

        result = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Operation completed with warnings",
            warnings=["Missing optional field 'abstract'", "Year might be incorrect"],
        )

        assert result.status.is_success()
        assert result.warnings is not None
        assert len(result.warnings) == 2

    def test_result_with_performance_metrics(self):
        """Test result with performance information."""
        from bibmgr.operations.results import OperationResult, ResultStatus

        result = OperationResult(
            status=ResultStatus.SUCCESS,
            message="Operation completed",
            duration_ms=1250,
        )

        assert result.duration_ms == 1250

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        from bibmgr.operations.results import OperationResult, ResultStatus

        validation_errors = [
            ValidationError(field="title", message="Too short", severity="warning")
        ]

        result = OperationResult(
            status=ResultStatus.PARTIAL_SUCCESS,
            message="Completed with issues",
            entity_id="test123",
            errors=["Minor error"],
            validation_errors=validation_errors,
            data={"processed": 10, "failed": 2},
            warnings=["Check data"],
            duration_ms=500,
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "partial_success"
        assert result_dict["message"] == "Completed with issues"
        assert result_dict["entity_id"] == "test123"
        assert len(result_dict["errors"]) == 1
        assert len(result_dict["validation_errors"]) == 1
        assert result_dict["validation_errors"][0]["field"] == "title"
        assert result_dict["data"]["processed"] == 10
        assert len(result_dict["warnings"]) == 1
        assert result_dict["duration_ms"] == 500
        assert "operation_id" in result_dict
        assert "timestamp" in result_dict


class TestBulkOperationResult:
    """Test BulkOperationResult class."""

    def test_create_bulk_result(self):
        """Test creating bulk operation result."""
        from bibmgr.operations.results import (
            BulkOperationResult,
            OperationResult,
            ResultStatus,
        )

        individual_results = [
            OperationResult(
                status=ResultStatus.SUCCESS,
                message="Created entry1",
                entity_id="entry1",
            ),
            OperationResult(
                status=ResultStatus.SUCCESS,
                message="Created entry2",
                entity_id="entry2",
            ),
            OperationResult(
                status=ResultStatus.ERROR,
                message="Failed to create entry3",
                entity_id="entry3",
            ),
        ]

        bulk_result = BulkOperationResult(
            total=3,
            successful=2,
            failed=1,
            results=individual_results,
        )

        assert bulk_result.total == 3
        assert bulk_result.successful == 2
        assert bulk_result.failed == 1
        assert len(bulk_result.results) == 3

    def test_bulk_result_success_rate(self):
        """Test calculating success rate."""
        from bibmgr.operations.results import BulkOperationResult

        # All successful
        result1 = BulkOperationResult(total=10, successful=10, failed=0, results=[])
        assert result1.success_rate == 1.0

        # Partial success
        result2 = BulkOperationResult(total=10, successful=7, failed=3, results=[])
        assert result2.success_rate == 0.7

        # All failed
        result3 = BulkOperationResult(total=10, successful=0, failed=10, results=[])
        assert result3.success_rate == 0.0

        # Empty operation
        result4 = BulkOperationResult(total=0, successful=0, failed=0, results=[])
        assert result4.success_rate == 1.0  # No failures

    def test_bulk_result_status_checks(self):
        """Test bulk result status check methods."""
        from bibmgr.operations.results import BulkOperationResult

        # All success
        result1 = BulkOperationResult(total=5, successful=5, failed=0, results=[])
        assert result1.all_success
        assert not result1.partial_success

        # Partial success
        result2 = BulkOperationResult(total=5, successful=3, failed=2, results=[])
        assert not result2.all_success
        assert result2.partial_success

        # All failed
        result3 = BulkOperationResult(total=5, successful=0, failed=5, results=[])
        assert not result3.all_success
        assert not result3.partial_success

    def test_bulk_result_filtering(self):
        """Test filtering results by status."""
        from bibmgr.operations.results import (
            BulkOperationResult,
            OperationResult,
            ResultStatus,
        )

        results = [
            OperationResult(status=ResultStatus.SUCCESS, message="OK 1"),
            OperationResult(status=ResultStatus.SUCCESS, message="OK 2"),
            OperationResult(status=ResultStatus.ERROR, message="Fail 1"),
            OperationResult(status=ResultStatus.VALIDATION_FAILED, message="Fail 2"),
            OperationResult(status=ResultStatus.SUCCESS, message="OK 3"),
        ]

        bulk_result = BulkOperationResult(
            total=5,
            successful=3,
            failed=2,
            results=results,
        )

        failed = bulk_result.get_failed_results()
        assert len(failed) == 2
        assert all(r.status.is_failure() for r in failed)

        successful = bulk_result.get_successful_results()
        assert len(successful) == 3
        assert all(r.status.is_success() for r in successful)

    def test_bulk_result_complete(self):
        """Test marking bulk operation as complete."""
        from bibmgr.operations.results import BulkOperationResult

        bulk_result = BulkOperationResult(total=10, successful=10, failed=0, results=[])

        assert bulk_result.completed_at is None

        bulk_result.complete()

        assert bulk_result.completed_at is not None
        assert bulk_result.completed_at > bulk_result.started_at


class TestStepResult:
    """Test StepResult for workflow steps."""

    def test_create_step_result(self):
        """Test creating workflow step result."""
        from bibmgr.operations.results import StepResult

        step_result = StepResult(
            step="import_parse",
            success=True,
            message="Parsed 100 entries",
            data={"entry_count": 100, "parse_time_ms": 250},
        )

        assert step_result.step == "import_parse"
        assert step_result.success
        assert step_result.message == "Parsed 100 entries"
        assert step_result.data is not None
        assert step_result.data["entry_count"] == 100
        assert isinstance(step_result.timestamp, datetime)

    def test_step_result_with_errors(self):
        """Test step result with errors."""
        from bibmgr.operations.results import StepResult

        step_result = StepResult(
            step="validation",
            success=False,
            message="Validation failed",
            entity_id="entry123",
            errors=["Missing required field", "Invalid format"],
        )

        assert not step_result.success
        assert step_result.entity_id == "entry123"
        assert step_result.errors is not None
        assert len(step_result.errors) == 2

    def test_step_result_with_warnings(self):
        """Test step result with warnings."""
        from bibmgr.operations.results import StepResult

        step_result = StepResult(
            step="import_complete",
            success=True,
            message="Import completed with warnings",
            warnings=["3 entries had missing abstracts", "2 entries had no keywords"],
        )

        assert step_result.success
        assert step_result.warnings is not None
        assert len(step_result.warnings) == 2

    def test_step_result_duration(self):
        """Test step result with duration."""
        from bibmgr.operations.results import StepResult

        step_result = StepResult(
            step="deduplicate",
            success=True,
            message="Found 5 duplicate groups",
            duration_ms=1500,
        )

        assert step_result.duration_ms == 1500


class TestWorkflowResult:
    """Test WorkflowResult for complete workflows."""

    def test_create_workflow_result(self):
        """Test creating workflow result."""
        from bibmgr.operations.results import WorkflowResult

        workflow_result = WorkflowResult(
            workflow="import",
            source="/path/to/file.bib",
        )

        assert workflow_result.workflow == "import"
        assert workflow_result.source == "/path/to/file.bib"
        assert isinstance(workflow_result.workflow_id, UUID)
        assert isinstance(workflow_result.started_at, datetime)
        assert workflow_result.completed_at is None
        assert len(workflow_result.steps) == 0

    def test_workflow_add_steps(self):
        """Test adding steps to workflow."""
        from bibmgr.operations.results import StepResult, WorkflowResult

        workflow_result = WorkflowResult(workflow="export")

        # Add steps
        step1 = StepResult(step="validate", success=True, message="Validation passed")
        step2 = StepResult(step="write", success=True, message="Wrote 50 entries")
        step3 = StepResult(step="verify", success=False, message="Verification failed")

        workflow_result.add_step(step1)
        workflow_result.add_step(step2)
        workflow_result.add_step(step3)

        assert len(workflow_result.steps) == 3
        assert workflow_result.steps[0].step == "validate"
        assert workflow_result.steps[2].success is False

    def test_workflow_success_status(self):
        """Test workflow success status calculation."""
        from bibmgr.operations.results import StepResult, WorkflowResult

        # All steps successful
        workflow1 = WorkflowResult(workflow="test1")
        workflow1.add_step(StepResult("s1", True, "OK"))
        workflow1.add_step(StepResult("s2", True, "OK"))
        assert workflow1.success
        assert not workflow1.partial_success

        # Some steps failed
        workflow2 = WorkflowResult(workflow="test2")
        workflow2.add_step(StepResult("s1", True, "OK"))
        workflow2.add_step(StepResult("s2", False, "Failed"))
        workflow2.add_step(StepResult("s3", True, "OK"))
        assert not workflow2.success
        assert workflow2.partial_success

        # All steps failed
        workflow3 = WorkflowResult(workflow="test3")
        workflow3.add_step(StepResult("s1", False, "Failed"))
        workflow3.add_step(StepResult("s2", False, "Failed"))
        assert not workflow3.success
        assert not workflow3.partial_success

    def test_workflow_failed_steps(self):
        """Test getting failed steps from workflow."""
        from bibmgr.operations.results import StepResult, WorkflowResult

        workflow = WorkflowResult(workflow="complex")

        workflow.add_step(StepResult("parse", True, "OK"))
        workflow.add_step(StepResult("validate", False, "Validation error"))
        workflow.add_step(StepResult("process", True, "OK"))
        workflow.add_step(StepResult("save", False, "IO error"))

        failed_steps = workflow.failed_steps

        assert len(failed_steps) == 2
        assert failed_steps[0].step == "validate"
        assert failed_steps[1].step == "save"

    def test_workflow_successful_entities(self):
        """Test getting successful entity IDs from workflow."""
        from bibmgr.operations.results import StepResult, WorkflowResult

        workflow = WorkflowResult(workflow="import")

        workflow.add_step(StepResult("import", True, "Imported", entity_id="entry1"))
        workflow.add_step(StepResult("import", True, "Imported", entity_id="entry2"))
        workflow.add_step(StepResult("import", False, "Failed", entity_id="entry3"))
        workflow.add_step(StepResult("import", True, "Imported", entity_id="entry4"))

        successful = workflow.successful_entities

        assert len(successful) == 3
        assert "entry1" in successful
        assert "entry2" in successful
        assert "entry4" in successful
        assert "entry3" not in successful

    def test_workflow_complete(self):
        """Test completing workflow."""
        from bibmgr.operations.results import WorkflowResult

        workflow = WorkflowResult(workflow="test")

        assert workflow.completed_at is None

        workflow.complete()

        assert workflow.completed_at is not None
        assert workflow.completed_at >= workflow.started_at

    def test_workflow_summary(self):
        """Test getting workflow summary."""
        from bibmgr.operations.results import StepResult, WorkflowResult

        workflow = WorkflowResult(
            workflow="deduplicate",
            config={"min_similarity": 0.8, "mode": "automatic"},
        )

        # Add steps
        workflow.add_step(StepResult("scan", True, "Found entries", entity_id="e1"))
        workflow.add_step(StepResult("merge", True, "Merged", entity_id="e2"))
        workflow.add_step(StepResult("merge", False, "Failed", entity_id="e3"))

        # Complete workflow
        workflow.complete()

        summary = workflow.get_summary()

        assert summary["workflow"] == "deduplicate"
        assert summary["total_steps"] == 3
        assert summary["successful_steps"] == 2
        assert summary["failed_steps"] == 1
        assert summary["entities_processed"] == 2
        assert summary["duration_ms"] is not None
        assert "workflow_id" in summary


class TestProgressUpdate:
    """Test ProgressUpdate for long operations."""

    def test_create_progress_update(self):
        """Test creating progress update."""
        from bibmgr.operations.results import ProgressUpdate

        progress = ProgressUpdate(
            operation="bulk_import",
            current=25,
            total=100,
            message="Processing entry 25 of 100",
            entity_id="entry25",
        )

        assert progress.operation == "bulk_import"
        assert progress.current == 25
        assert progress.total == 100
        assert progress.message == "Processing entry 25 of 100"
        assert progress.entity_id == "entry25"
        assert isinstance(progress.timestamp, datetime)

    def test_progress_percentage(self):
        """Test calculating progress percentage."""
        from bibmgr.operations.results import ProgressUpdate

        # Normal progress
        progress1 = ProgressUpdate("op", current=30, total=100)
        assert progress1.percentage == 30.0

        # Complete
        progress2 = ProgressUpdate("op", current=50, total=50)
        assert progress2.percentage == 100.0

        # Empty operation
        progress3 = ProgressUpdate("op", current=0, total=0)
        assert progress3.percentage == 100.0

    def test_progress_remaining(self):
        """Test calculating remaining items."""
        from bibmgr.operations.results import ProgressUpdate

        progress1 = ProgressUpdate("op", current=30, total=100)
        assert progress1.remaining == 70

        progress2 = ProgressUpdate("op", current=100, total=100)
        assert progress2.remaining == 0

        # Over 100% (shouldn't happen but handle gracefully)
        progress3 = ProgressUpdate("op", current=110, total=100)
        assert progress3.remaining == 0


class TestResultSerialization:
    """Test serializing results for storage/transmission."""

    def test_serialize_complex_result(self):
        """Test serializing complex operation result."""
        from bibmgr.operations.results import OperationResult, ResultStatus

        entry = create_entry_with_data(key="test", title="Test Entry")

        result = OperationResult(
            status=ResultStatus.PARTIAL_SUCCESS,
            message="Completed with issues",
            entity_id="test",
            errors=["Network timeout"],
            validation_errors=[
                ValidationError(
                    field="doi", message="Invalid format", severity="warning"
                )
            ],
            data={"entry": entry.to_dict(), "retries": 3},
            suggestions={"retry_after": 60},
            warnings=["Slow response"],
            duration_ms=5000,
        )

        # Convert to dict
        result_dict = result.to_dict()

        # Should be JSON serializable
        import json

        json_str = json.dumps(result_dict)
        assert json_str

        # Deserialize
        loaded = json.loads(json_str)
        assert loaded["status"] == "partial_success"
        assert loaded["entity_id"] == "test"
        assert len(loaded["errors"]) == 1
        assert loaded["data"]["retries"] == 3

    def test_serialize_workflow_result(self):
        """Test serializing workflow result."""
        from bibmgr.operations.results import StepResult, WorkflowResult

        workflow = WorkflowResult(
            workflow="import",
            source="/data/refs.bib",
            config={"validate": True, "merge_duplicates": False},
        )

        workflow.add_step(
            StepResult(
                "parse",
                True,
                "Parsed successfully",
                data={"entries": 50},
                duration_ms=100,
            )
        )

        workflow.add_step(
            StepResult(
                "validate",
                False,
                "Validation errors",
                errors=["Invalid entry at line 45"],
            )
        )

        workflow.complete()

        summary = workflow.get_summary()

        # Should be JSON serializable
        import json

        json_str = json.dumps(summary, default=str)
        assert json_str

        loaded = json.loads(json_str)
        assert loaded["workflow"] == "import"
        assert loaded["total_steps"] == 2
        assert loaded["successful_steps"] == 1
