"""Message formatting utilities for the CLI.

Provides functions for formatting success, error, warning, and info messages.
"""

from rich.console import Console

from .widgets import StatusIcon


def success_message(console: Console, message: str) -> None:
    """Display a success message.

    Args:
        console: Rich console instance
        message: Success message text
    """
    console.print(f"{StatusIcon.SUCCESS} {message}", style="green")


def error_message(console: Console, message: str) -> None:
    """Display an error message.

    Args:
        console: Rich console instance
        message: Error message text
    """
    console.print(f"{StatusIcon.ERROR} {message}", style="red")


def warning_message(console: Console, message: str) -> None:
    """Display a warning message.

    Args:
        console: Rich console instance
        message: Warning message text
    """
    console.print(f"{StatusIcon.WARNING} {message}", style="yellow")


def info_message(console: Console, message: str) -> None:
    """Display an info message.

    Args:
        console: Rich console instance
        message: Info message text
    """
    console.print(f"{StatusIcon.INFO} {message}", style="blue")
