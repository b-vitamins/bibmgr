"""Color themes and styles for the CLI.

Defines color schemes and style mappings for consistent visual presentation.
"""

from rich.theme import Theme

# Theme definitions
THEMES = {
    "professional": {
        # Base colors
        "primary": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "info": "magenta",
        "muted": "dim",
        "accent": "cyan",
        # Status colors
        "status.read": "green",
        "status.reading": "yellow",
        "status.unread": "dim white",
        # Entry type colors
        "type.article": "cyan",
        "type.book": "blue",
        "type.inproceedings": "magenta",
        "type.incollection": "purple",
        "type.phdthesis": "bright_blue",
        "type.mastersthesis": "bright_blue",
        "type.techreport": "yellow",
        "type.manual": "bright_magenta",
        "type.misc": "white",
        # UI element colors
        "table.header": "bold cyan",
        "table.border": "dim",
        "table.row_odd": "none",
        "table.row_even": "dim",
        "panel.border": "blue",
        "panel.title": "bold blue",
        "prompt": "cyan",
        "prompt.choices": "dim cyan",
        # Message styles
        "message.success": "bold green",
        "message.error": "bold red",
        "message.warning": "bold yellow",
        "message.info": "bold blue",
        # Field styles
        "field.label": "bold",
        "field.value": "none",
        "field.missing": "dim italic",
        "field.highlight": "bold yellow",
    },
    "minimal": {
        # Minimal theme with fewer colors
        "primary": "white",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "info": "blue",
        "muted": "dim",
        "accent": "white",
        # Status colors
        "status.read": "green",
        "status.reading": "yellow",
        "status.unread": "dim",
        # Entry types all same color
        "type.article": "white",
        "type.book": "white",
        "type.inproceedings": "white",
        # UI elements
        "table.header": "bold",
        "table.border": "dim",
        "panel.border": "white",
        "prompt": "white",
    },
}


def get_theme(name: str = "professional") -> Theme:
    """Get a theme by name.

    Args:
        name: Theme name

    Returns:
        Rich Theme instance
    """
    theme_dict = THEMES.get(name, THEMES["professional"])
    return Theme(theme_dict)


def get_entry_type_style(entry_type: str) -> str:
    """Get style for an entry type.

    Args:
        entry_type: Entry type name

    Returns:
        Style string
    """
    theme = THEMES["professional"]  # Use default theme
    style_key = f"type.{entry_type.lower()}"
    return theme.get(style_key, theme.get("type.misc", "white"))


def get_status_style(status: str) -> str:
    """Get style for a read status.

    Args:
        status: Read status (read, reading, unread)

    Returns:
        Style string
    """
    theme = THEMES["professional"]  # Use default theme
    style_key = f"status.{status.lower()}"
    return theme.get(style_key, theme.get("status.unread", "dim white"))


def apply_theme(console, theme_name: str = "professional") -> None:
    """Apply a theme to a console.

    Args:
        console: Rich Console instance
        theme_name: Name of theme to apply
    """
    theme = get_theme(theme_name)
    # Update the console's theme stack instead of replacing theme
    console.push_theme(theme)
