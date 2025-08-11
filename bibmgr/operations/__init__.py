"""Operations module for bibliography management.

This module provides high-level operations for managing bibliography entries
including CRUD operations, import/export workflows, deduplication, and more.

The module is organized into:

- commands/: Command pattern implementation for atomic operations
- workflows/: Complex multi-step workflows
- policies/: Business rules and strategies
- validators/: Operation validation logic
- results.py: Rich result types for operation outcomes

All operations integrate with the storage layer through the repository pattern
and publish events for real-time tracking.
"""

# Commands
from .commands import (
    BulkCreateHandler,
    CreateCommand,
    CreateHandler,
    DeleteCommand,
    DeleteHandler,
    FieldChange,
    MergeCommand,
    MergeHandler,
    PatchHandler,
    UpdateCommand,
    UpdateHandler,
)

# Policies
from .policies import (
    ConflictDecision,
    ConflictPolicy,
    ConflictResolution,
    FieldMergeRule,
    KeyNamingPolicy,
    MergePolicy,
    MergeStrategy,
)

# Results
from .results import (
    BulkOperationResult,
    OperationResult,
    ProgressUpdate,
    ResultStatus,
    StepResult,
    WorkflowResult,
)

# Validators
from .validators import (
    CreatePostconditions,
    CreatePreconditions,
    DeletePostconditions,
    DeletePreconditions,
    MergePostconditions,
    MergePreconditions,
    UpdatePostconditions,
    UpdatePreconditions,
)

# Workflows
from .workflows import (
    DeduplicationConfig,
    DeduplicationMode,
    DeduplicationRule,
    DeduplicationWorkflow,
    ExportFormat,
    ExportWorkflow,
    ExportWorkflowConfig,
    ImportFormat,
    ImportWorkflow,
    ImportWorkflowConfig,
    MigrationConfig,
    MigrationWorkflow,
)

__all__ = [
    # Commands
    "CreateCommand",
    "CreateHandler",
    "BulkCreateHandler",
    "UpdateCommand",
    "UpdateHandler",
    "FieldChange",
    "PatchHandler",
    "DeleteCommand",
    "DeleteHandler",
    "MergeCommand",
    "MergeHandler",
    # Workflows
    "ImportFormat",
    "ImportWorkflow",
    "ImportWorkflowConfig",
    "ExportFormat",
    "ExportWorkflow",
    "ExportWorkflowConfig",
    "DeduplicationMode",
    "DeduplicationRule",
    "DeduplicationConfig",
    "DeduplicationWorkflow",
    "MigrationConfig",
    "MigrationWorkflow",
    # Results
    "ResultStatus",
    "OperationResult",
    "BulkOperationResult",
    "StepResult",
    "WorkflowResult",
    "ProgressUpdate",
    # Policies
    "ConflictResolution",
    "ConflictDecision",
    "ConflictPolicy",
    "MergeStrategy",
    "FieldMergeRule",
    "MergePolicy",
    "KeyNamingPolicy",
    # Validators
    "CreatePreconditions",
    "UpdatePreconditions",
    "DeletePreconditions",
    "MergePreconditions",
    "CreatePostconditions",
    "UpdatePostconditions",
    "DeletePostconditions",
    "MergePostconditions",
]
