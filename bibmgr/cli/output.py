"""CLI output utilities."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import click
from rich.console import Console
from rich.table import Table


# Global console instance
console = Console()


def print_success(message: str) -> None:
    """Print success message.

    Args:
        message: Success message
    """
    assert console is not None  # console is always initialized
    console.print(f"✅ {message}", style="green")


def print_error(message: str, err: bool = True) -> None:
    """Print error message.

    Args:
        message: Error message
        err: Write to stderr
    """
    # Rich Console handles stderr differently
    error_console = Console(stderr=True) if err else console
    assert error_console is not None
    error_console.print(f"❌ {message}", style="red")


def print_warning(message: str) -> None:
    """Print warning message.

    Args:
        message: Warning message
    """
    assert console is not None  # console is always initialized
    console.print(f"⚠️  {message}", style="yellow")


def print_info(message: str) -> None:
    """Print info message.

    Args:
        message: Info message
    """
    assert console is not None  # console is always initialized
    console.print(f"ℹ️  {message}", style="cyan")


def print_table(
    headers: List[str], rows: List[List[str]], title: Optional[str] = None
) -> None:
    """Print a table.

    Args:
        headers: Table headers
        rows: Table rows
        title: Optional table title
    """
    table = Table(title=title) if title else Table()

    for header in headers:
        table.add_column(header)

    for row in rows:
        table.add_row(*[str(cell) for cell in row])

    assert console is not None  # console is always initialized
    console.print(table)


def print_json(data: Any, indent: int = 2) -> None:
    """Print JSON data.

    Args:
        data: Data to print as JSON
        indent: JSON indentation
    """
    json_str = json.dumps(data, indent=indent, default=str)
    print(json_str)


def print_list(items: List[str], bullet: str = "•", indent: int = 2) -> None:
    """Print a bulleted list.

    Args:
        items: List items
        bullet: Bullet character
        indent: Indentation spaces
    """
    indent_str = " " * indent
    for item in items:
        assert console is not None  # console is always initialized
        console.print(f"{indent_str}{bullet} {item}")


def print_dict(data: Dict[str, Any], indent: int = 0) -> None:
    """Print a dictionary as key-value pairs.

    Args:
        data: Dictionary to print
        indent: Indentation level
    """
    indent_str = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            assert console is not None  # console is always initialized
            console.print(f"{indent_str}{key}:")
            print_dict(value, indent + 2)
        elif isinstance(value, list):
            assert console is not None  # console is always initialized
            console.print(f"{indent_str}{key}:")
            for item in value:
                assert console is not None  # console is always initialized
                console.print(f"{indent_str}  - {item}")
        else:
            assert console is not None  # console is always initialized
            console.print(f"{indent_str}{key}: {value}")


def print_progress(current: int, total: int, description: Optional[str] = None) -> None:
    """Print progress indicator.

    Args:
        current: Current progress
        total: Total items
        description: Optional description
    """
    percentage = (current / total * 100) if total > 0 else 0
    desc = f"{description}: " if description else ""
    assert console is not None  # console is always initialized
    console.print(f"{desc}[{current}/{total}] {percentage:.1f}%")


def confirm(message: str, default: bool = False, abort: bool = False) -> bool:
    """Ask for confirmation.

    Args:
        message: Confirmation message
        default: Default answer
        abort: Abort on no

    Returns:
        True if confirmed
    """
    result = click.confirm(message, default=default, abort=abort)
    return result


def prompt(
    message: str,
    default: Optional[str] = None,
    hide_input: bool = False,
    type: Optional[type] = None,
) -> Any:
    """Prompt for input.

    Args:
        message: Prompt message
        default: Default value
        hide_input: Hide input (for passwords)
        type: Value type for conversion

    Returns:
        User input
    """
    return click.prompt(message, default=default, hide_input=hide_input, type=type)


def choose(message: str, choices: List[str], default: Optional[str] = None) -> str:
    """Choose from options.

    Args:
        message: Prompt message
        choices: List of choices
        default: Default choice

    Returns:
        Selected choice
    """
    return click.prompt(message, type=click.Choice(choices), default=default)


def pager(text: str) -> None:
    """Display text in a pager.

    Args:
        text: Text to display
    """
    click.echo_via_pager(text)


def clear() -> None:
    """Clear the screen."""
    click.clear()


class OutputContext:
    """Context manager for output settings."""

    def __init__(
        self, quiet: bool = False, verbose: bool = False, no_color: bool = False
    ):
        """Initialize output context.

        Args:
            quiet: Suppress non-error output
            verbose: Show verbose output
            no_color: Disable colors
        """
        self.quiet = quiet
        self.verbose = verbose
        self.no_color = no_color
        self._original_console = None

    def __enter__(self):
        """Enter context."""
        global console
        self._original_console = console

        if self.no_color:
            console = Console(no_color=True)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        global console
        console = self._original_console

    def print(self, message: str, **kwargs) -> None:
        """Print with context settings.

        Args:
            message: Message to print
            **kwargs: Additional print arguments
        """
        if not self.quiet:
            assert console is not None  # console is always initialized
            console.print(message, **kwargs)

    def debug(self, message: str) -> None:
        """Print debug message.

        Args:
            message: Debug message
        """
        if self.verbose:
            assert console is not None  # console is always initialized
            console.print(f"[dim]DEBUG: {message}[/dim]")
