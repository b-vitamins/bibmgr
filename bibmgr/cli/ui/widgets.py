"""Custom UI widgets for the CLI.

Provides various widgets for displaying status, ratings, badges, and interactive elements.
"""

from typing import Any


class StatusIcon:
    """Status icon constants."""

    SUCCESS = "[green]✓[/green]"
    ERROR = "[red]✗[/red]"
    WARNING = "[yellow]⚠[/yellow]"
    INFO = "[blue]ℹ[/blue]"
    SPINNER = "[cyan]●[/cyan]"


def get_read_status_icon(status: str) -> str:
    """Get icon for read status.

    Args:
        status: Read status (read, reading, unread)

    Returns:
        Formatted icon string
    """
    icons = {
        "read": "[green]●[/green]",
        "reading": "[yellow]◐[/yellow]",
        "unread": "[dim]○[/dim]",
    }
    return icons.get(status.lower(), icons["unread"])


def format_rating(rating: int, max_rating: int = 5) -> str:
    """Format rating as stars.

    Args:
        rating: Current rating
        max_rating: Maximum rating

    Returns:
        Formatted star string
    """
    filled = min(rating, max_rating)
    empty = max_rating - filled

    stars = ""
    if filled > 0:
        stars = "[yellow]" + "★" * filled + "[/yellow]"
    if empty > 0:
        stars += "[dim]" + "☆" * empty + "[/dim]"

    return stars


def format_entry_type_badge(entry_type: str) -> str:
    """Format entry type as colored badge.

    Args:
        entry_type: Entry type name

    Returns:
        Formatted badge string
    """
    from .themes import get_entry_type_style

    style = get_entry_type_style(entry_type)
    return f"[{style}]{entry_type.title()}[/{style}]"


def get_collection_icon(collection_type: str) -> str:
    """Get icon for collection type.

    Args:
        collection_type: Collection type (manual, smart)

    Returns:
        Icon character
    """
    icons = {
        "manual": "📁",
        "smart": "🔍",
        "default": "📂",
    }
    return icons.get(collection_type.lower(), icons["default"])


class SelectionMenu:
    """Interactive selection menu widget."""

    def __init__(self, title: str, options: list[str]):
        """Initialize selection menu.

        Args:
            title: Menu title
            options: List of options
        """
        self.title = title
        self.options = options
        self.selected_index = 0

    def get_selection(self) -> int:
        """Get selected index (mock implementation).

        Returns:
            Selected index
        """
        # In real implementation, this would handle keyboard input
        return self.selected_index

    def show(self) -> str:
        """Show menu and return selected option.

        Returns:
            Selected option
        """
        index = self.get_selection()
        return self.options[index]


class CheckboxList:
    """Checkbox list widget."""

    def __init__(
        self,
        title: str,
        options: list[str],
        selected: list[int] | None = None,
    ):
        """Initialize checkbox list.

        Args:
            title: List title
            options: List of options
            selected: Initially selected indices
        """
        self.title = title
        self.options = options
        self.selected = set(selected or [])

    def is_selected(self, index: int) -> bool:
        """Check if item is selected.

        Args:
            index: Item index

        Returns:
            True if selected
        """
        return index in self.selected

    def toggle(self, index: int) -> None:
        """Toggle item selection.

        Args:
            index: Item index
        """
        if index in self.selected:
            self.selected.remove(index)
        else:
            self.selected.add(index)

    def get_selected(self) -> list[str]:
        """Get selected items.

        Returns:
            List of selected items
        """
        return [self.options[i] for i in sorted(self.selected)]


class TreeView:
    """Tree view widget for hierarchical data."""

    def __init__(self):
        """Initialize tree view."""
        self.nodes: dict[str, dict[str, Any]] = {}
        self.root_nodes: list[str] = []

    def add_node(
        self,
        node_id: str,
        label: str,
        parent: str | None = None,
    ) -> None:
        """Add node to tree.

        Args:
            node_id: Node identifier
            label: Node label
            parent: Parent node ID
        """
        self.nodes[node_id] = {
            "label": label,
            "parent": parent,
            "children": [],
        }

        if parent:
            if parent in self.nodes:
                self.nodes[parent]["children"].append(node_id)
        else:
            self.root_nodes.append(node_id)

    def render(self) -> str:
        """Render tree as string.

        Returns:
            Tree representation
        """
        lines = []

        def render_node(node_id: str, prefix: str = "", is_last: bool = True):
            node = self.nodes[node_id]

            # Add current node
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{node['label']}")

            # Add children
            children = node["children"]
            for i, child_id in enumerate(children):
                extension = "    " if is_last else "│   "
                is_last_child = i == len(children) - 1
                render_node(child_id, prefix + extension, is_last_child)

        # Render root nodes
        for i, root_id in enumerate(self.root_nodes):
            if i > 0:
                lines.append("")  # Empty line between roots
            lines.append(self.nodes[root_id]["label"])

            # Render children of root
            children = self.nodes[root_id]["children"]
            for j, child_id in enumerate(children):
                is_last = j == len(children) - 1
                render_node(child_id, "", is_last)

        return "\n".join(lines)
