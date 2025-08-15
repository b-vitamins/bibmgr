"""Output paging utilities for the CLI.

Provides functions for paging long output using Rich and system pagers.
"""

import os
import shutil
import subprocess
import tempfile
from typing import Any

from rich.console import Console


def should_use_pager(
    output_lines: int,
    terminal_height: int,
    mode: str = "auto",
) -> bool:
    """Determine if pager should be used.

    Args:
        output_lines: Number of output lines
        terminal_height: Terminal height in lines
        mode: Pager mode (auto, always, never)

    Returns:
        True if pager should be used
    """
    if mode == "always":
        return True
    elif mode == "never":
        return False
    else:  # auto
        # Use pager if output exceeds 80% of terminal height
        return output_lines > int(terminal_height * 0.8)


def get_system_pager() -> str | None:
    """Get the system pager command.

    Returns:
        Pager command or None if not found
    """
    # Check PAGER environment variable
    pager = os.environ.get("PAGER")

    if pager:
        return pager

    # Try common pagers
    for cmd in ["less", "more", "most"]:
        if shutil.which(cmd):
            return cmd

    return None


def page_output(
    content: str,
    console: Console,
    use_rich_pager: bool = True,
) -> None:
    """Page output content.

    Args:
        content: Content to page
        console: Rich console instance
        use_rich_pager: Use Rich's built-in pager
    """
    if use_rich_pager:
        # Use Rich's built-in pager
        with console.pager():
            console.print(content)
    else:
        # Try system pager
        pager_cmd = get_system_pager()

        if pager_cmd:
            # Write to temporary file and open with pager
            with tempfile.NamedTemporaryFile(
                mode="w",
                delete=False,
                encoding="utf-8",
                suffix=".txt",
            ) as f:
                f.write(content)
                temp_path = f.name

            try:
                subprocess.call([pager_cmd, temp_path])
            finally:
                os.unlink(temp_path)
        else:
            # Fall back to simple print
            console.print(content)


def page_rich_output(
    renderable: Any,
    console: Console,
    force_pager: bool = False,
) -> None:
    """Page Rich renderable output.

    Args:
        renderable: Rich renderable object
        console: Rich console instance
        force_pager: Force use of pager
    """
    # Measure output height
    measurement = console.measure(renderable)
    output_height = measurement.minimum  # Approximate lines

    # Determine if paging needed
    terminal_height = console.height

    if force_pager or should_use_pager(output_height, terminal_height):
        with console.pager():
            console.print(renderable)
    else:
        console.print(renderable)


class SmartPager:
    """Smart pager that automatically decides whether to page."""

    def __init__(
        self,
        console: Console,
        mode: str = "auto",
        threshold: float = 0.8,
    ):
        """Initialize smart pager.

        Args:
            console: Rich console instance
            mode: Pager mode (auto, always, never)
            threshold: Screen percentage threshold for auto mode
        """
        self.console = console
        self.mode = mode
        self.threshold = threshold

    def page(self, content: Any) -> None:
        """Page content if needed.

        Args:
            content: Content to potentially page
        """
        if self.mode == "never":
            self.console.print(content)
            return

        if self.mode == "always":
            with self.console.pager():
                self.console.print(content)
            return

        # Auto mode - measure content
        if isinstance(content, str):
            lines = content.count("\n") + 1
        else:
            # For Rich renderables, estimate height
            measurement = self.console.measure(content)
            lines = measurement.minimum

        if lines > int(self.console.height * self.threshold):
            with self.console.pager():
                self.console.print(content)
        else:
            self.console.print(content)
