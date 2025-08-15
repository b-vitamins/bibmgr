"""Progress indicators and tracking for the CLI.

Provides progress bars, spinners, and status tracking for long-running operations.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


def create_progress_bar(
    show_percentage: bool = True,
    show_speed: bool = False,
    show_time: bool = True,
) -> Progress:
    """Create a progress bar with custom columns.

    Args:
        show_percentage: Show completion percentage
        show_speed: Show processing speed
        show_time: Show elapsed/remaining time

    Returns:
        Configured Progress instance
    """
    columns = [
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
    ]

    if show_percentage:
        columns.append(TextColumn("[progress.percentage]{task.percentage:>3.0f}%"))

    columns.extend(
        [
            TextColumn("•"),
            MofNCompleteColumn(),
        ]
    )

    if show_time:
        columns.extend(
            [
                TextColumn("•"),
                TimeElapsedColumn(),
                TextColumn("•"),
                TimeRemainingColumn(),
            ]
        )

    return Progress(*columns)


@contextmanager
def progress_bar(
    description: str,
    total: int | None = None,
    auto_refresh: bool = True,
) -> Iterator[Callable]:
    """Context manager for a progress bar.

    Args:
        description: Task description
        total: Total number of steps
        auto_refresh: Auto-refresh display

    Yields:
        Update function that advances the progress
    """
    progress = create_progress_bar()

    with progress:
        task = progress.add_task(description, total=total)

        def update(advance: int = 1, description: str | None = None):
            if description:
                progress.update(task, description=description)
            progress.update(task, advance=advance)

        yield update


@contextmanager
def spinner(description: str) -> Iterator[None]:
    """Context manager for an indeterminate spinner.

    Args:
        description: Task description

    Yields:
        None
    """
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        transient=True,
    )

    with progress:
        progress.add_task(description, total=None)
        yield


class MultiProgress:
    """Manage multiple concurrent progress tasks."""

    def __init__(self):
        """Initialize multi-progress manager."""
        self.progress = create_progress_bar()
        self.tasks = {}

    def add_task(self, description: str, total: int) -> TaskID:
        """Add a new progress task.

        Args:
            description: Task description
            total: Total steps

        Returns:
            Task ID
        """
        task_id = self.progress.add_task(description, total=total)
        self.tasks[task_id] = {
            "description": description,
            "total": total,
            "completed": 0,
        }
        return task_id

    def update(self, task_id: TaskID, advance: int = 1) -> None:
        """Update task progress.

        Args:
            task_id: Task ID
            advance: Steps to advance
        """
        self.progress.update(task_id, advance=advance)
        self.tasks[task_id]["completed"] += advance

    def get_progress(self, task_id: TaskID) -> float:
        """Get task progress as fraction.

        Args:
            task_id: Task ID

        Returns:
            Progress fraction (0.0 to 1.0)
        """
        task = self.tasks[task_id]
        return task["completed"] / task["total"] if task["total"] > 0 else 0.0

    def __enter__(self):
        """Enter context manager."""
        self.progress.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        return self.progress.__exit__(exc_type, exc_val, exc_tb)


class StatusProgress:
    """Progress with changing status messages."""

    def __init__(self):
        """Initialize status progress."""
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("[dim]{task.fields[status]}"),
        )
        self.tasks = {}

    def add_task(self, description: str, total: int) -> TaskID:
        """Add a new task.

        Args:
            description: Task description
            total: Total steps

        Returns:
            Task ID
        """
        task_id = self.progress.add_task(description, total=total, status="Starting...")
        self.tasks[task_id] = {
            "description": description,
            "total": total,
            "completed": 0,
            "status": "Starting...",
        }
        return task_id

    def update_status(self, task_id: TaskID, status: str) -> None:
        """Update task status message.

        Args:
            task_id: Task ID
            status: New status message
        """
        self.progress.update(task_id, status=status)
        self.tasks[task_id]["status"] = status

    def advance(self, task_id: TaskID, advance: int = 1) -> None:
        """Advance task progress.

        Args:
            task_id: Task ID
            advance: Steps to advance
        """
        self.progress.update(task_id, advance=advance)
        self.tasks[task_id]["completed"] += advance

    def get_status(self, task_id: TaskID) -> str:
        """Get current task status.

        Args:
            task_id: Task ID

        Returns:
            Status message
        """
        return self.tasks[task_id]["status"]

    def __enter__(self):
        """Enter context manager."""
        self.progress.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        return self.progress.__exit__(exc_type, exc_val, exc_tb)
