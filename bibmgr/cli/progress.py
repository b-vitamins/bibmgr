"""CLI progress indicators."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Iterable, Optional

from rich.console import Console
from rich.live import Live
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


class ProgressBar:
    """Progress bar for long operations."""

    def __init__(
        self,
        total: Optional[int] = None,
        description: str = "Processing",
        show_speed: bool = False,
        show_time: bool = True,
    ):
        """Initialize progress bar.

        Args:
            total: Total number of items (None for indeterminate)
            description: Task description
            show_speed: Show processing speed
            show_time: Show elapsed/remaining time
        """
        self.total = total
        self.description = description

        # Build columns
        columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        ]

        if show_time:
            columns.append(TimeElapsedColumn())
            if total is not None:
                columns.append(TimeRemainingColumn())

        self.progress = Progress(*columns)
        self.task_id: Optional[TaskID] = None
        self.console = Console()

    def __enter__(self):
        """Enter context."""
        self.progress.__enter__()
        self.task_id = self.progress.add_task(self.description, total=self.total)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        self.progress.__exit__(exc_type, exc_val, exc_tb)

    def update(self, advance: int = 1) -> None:
        """Update progress.

        Args:
            advance: Number of items to advance
        """
        if self.task_id is not None:
            self.progress.update(self.task_id, advance=advance)

    def set_description(self, description: str) -> None:
        """Update task description.

        Args:
            description: New description
        """
        if self.task_id is not None:
            self.progress.update(self.task_id, description=description)

    def complete(self) -> None:
        """Mark task as complete."""
        if self.task_id is not None:
            self.progress.update(self.task_id, completed=self.total)


class Spinner:
    """Spinner for indeterminate progress."""

    def __init__(self, message: str = "Processing..."):
        """Initialize spinner.

        Args:
            message: Spinner message
        """
        self.message = message
        self.console = Console()
        self._status = None

    def __enter__(self):
        """Enter context."""
        self._status = self.console.status(self.message)
        self._status.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        if self._status:
            self._status.__exit__(exc_type, exc_val, exc_tb)

    def update(self, message: str) -> None:
        """Update spinner message.

        Args:
            message: New message
        """
        if self._status:
            self._status.update(message)


class BatchProgress:
    """Progress tracker for batch operations."""

    def __init__(
        self,
        items: Iterable[Any],
        description: str = "Processing",
        show_item: bool = False,
    ):
        """Initialize batch progress.

        Args:
            items: Items to process
            description: Task description
            show_item: Show current item
        """
        self.items = list(items)
        self.description = description
        self.show_item = show_item
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.completed]{task.completed}/{task.total}"),
        )
        self.task_id: Optional[TaskID] = None

    def __enter__(self):
        """Enter context."""
        self.progress.__enter__()
        self.task_id = self.progress.add_task(self.description, total=len(self.items))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        self.progress.__exit__(exc_type, exc_val, exc_tb)

    def __iter__(self):
        """Iterate over items with progress."""
        for item in self.items:
            if self.show_item and self.task_id is not None:
                desc = f"{self.description}: {item}"
                self.progress.update(self.task_id, description=desc)

            yield item

            if self.task_id is not None:
                self.progress.update(self.task_id, advance=1)


@contextmanager
def progress_context(
    description: str = "Processing", transient: bool = True
) -> Generator[Progress, None, None]:
    """Create a progress context.

    Args:
        description: Initial description
        transient: Remove progress bar when done

    Yields:
        Progress instance
    """
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=transient,
    )

    with progress:
        progress.add_task(description, total=None)
        yield progress


@contextmanager
def live_display(
    initial_content: str = "", refresh_per_second: int = 4
) -> Generator[Live, None, None]:
    """Create a live display.

    Args:
        initial_content: Initial content to display
        refresh_per_second: Refresh rate

    Yields:
        Live display instance
    """
    console = Console()

    with Live(
        initial_content, console=console, refresh_per_second=refresh_per_second
    ) as live:
        yield live


class MultiProgress:
    """Track multiple concurrent tasks."""

    def __init__(self):
        """Initialize multi-progress tracker."""
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )
        self.tasks = {}

    def __enter__(self):
        """Enter context."""
        self.progress.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        self.progress.__exit__(exc_type, exc_val, exc_tb)

    def add_task(self, name: str, description: str, total: Optional[int] = None) -> str:
        """Add a new task.

        Args:
            name: Task name (identifier)
            description: Task description
            total: Total items (None for indeterminate)

        Returns:
            Task name
        """
        task_id = self.progress.add_task(description, total=total)
        self.tasks[name] = task_id
        return name

    def update(
        self, name: str, advance: int = 1, description: Optional[str] = None
    ) -> None:
        """Update a task.

        Args:
            name: Task name
            advance: Number of items to advance
            description: New description (optional)
        """
        if name in self.tasks:
            kwargs: dict[str, Any] = {"advance": advance}
            if description is not None:
                kwargs["description"] = description
            self.progress.update(self.tasks[name], **kwargs)

    def complete(self, name: str) -> None:
        """Mark a task as complete.

        Args:
            name: Task name
        """
        if name in self.tasks:
            task_id = self.tasks[name]
            task = self.progress.tasks[task_id]
            self.progress.update(task_id, completed=task.total)
