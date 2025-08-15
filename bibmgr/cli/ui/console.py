"""Console setup and configuration for the CLI.

Provides functions to create and configure Rich console instances
with custom themes and settings.
"""

from rich.console import Console

from .themes import get_theme


def create_console(
    width: int | str | None = None,
    theme_name: str = "professional",
    force_terminal: bool = True,
    legacy_windows: bool = False,
) -> Console:
    """Create a configured Rich console.

    Args:
        width: Console width (int for fixed, "auto" for terminal width)
        theme_name: Name of theme to apply
        force_terminal: Force terminal mode for colors
        legacy_windows: Use legacy Windows mode

    Returns:
        Configured Console instance
    """
    # Handle width configuration
    if width == "auto":
        console_width = None  # Let Rich auto-detect
    elif width is None:
        console_width = 120  # Default width
    else:
        console_width = int(width) if isinstance(width, str) else width

    # Get theme
    theme = get_theme(theme_name)

    # Create console
    console = Console(
        width=console_width,
        theme=theme,
        force_terminal=force_terminal,
        legacy_windows=legacy_windows,
        soft_wrap=True,
        markup=True,
        emoji=True,
        highlight=True,
    )

    # Store theme as public attribute for tests
    console.theme = theme  # type: ignore

    return console


def get_default_console() -> Console:
    """Get the default console instance.

    Returns:
        Default Console instance
    """
    return create_console()
