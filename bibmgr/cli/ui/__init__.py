"""UI components for the CLI.

This module provides Rich-based UI components including:
- Console setup with themes
- Progress indicators and spinners
- Interactive prompts
- Status widgets and badges
- Message formatting
- Panel layouts
- Pagination controls
"""

from .console import create_console, get_default_console
from .messages import (
    error_message,
    info_message,
    success_message,
    warning_message,
)
from .pagination import PaginatedOutput, format_pagination_controls
from .panels import (
    create_entry_panel,
    create_error_panel,
    create_nested_panel,
    create_summary_panel,
)
from .progress import (
    MultiProgress,
    StatusProgress,
    create_progress_bar,
    progress_bar,
    spinner,
)
from .prompts import (
    choice_prompt,
    confirm_prompt,
    integer_prompt,
    multiline_prompt,
    open_editor,
    text_prompt,
    validated_prompt,
)
from .themes import (
    THEMES,
    apply_theme,
    get_entry_type_style,
    get_status_style,
    get_theme,
)
from .widgets import (
    CheckboxList,
    SelectionMenu,
    StatusIcon,
    TreeView,
    format_entry_type_badge,
    format_rating,
    get_collection_icon,
    get_read_status_icon,
)

__all__ = [
    # Console
    "create_console",
    "get_default_console",
    # Messages
    "success_message",
    "error_message",
    "warning_message",
    "info_message",
    # Panels
    "create_entry_panel",
    "create_error_panel",
    "create_summary_panel",
    "create_nested_panel",
    # Pagination
    "PaginatedOutput",
    "format_pagination_controls",
    # Progress
    "create_progress_bar",
    "progress_bar",
    "spinner",
    "MultiProgress",
    "StatusProgress",
    # Prompts
    "text_prompt",
    "choice_prompt",
    "confirm_prompt",
    "integer_prompt",
    "validated_prompt",
    "multiline_prompt",
    "open_editor",
    # Themes
    "THEMES",
    "get_theme",
    "get_entry_type_style",
    "get_status_style",
    "apply_theme",
    # Widgets
    "StatusIcon",
    "get_read_status_icon",
    "format_rating",
    "format_entry_type_badge",
    "get_collection_icon",
    "SelectionMenu",
    "CheckboxList",
    "TreeView",
]
