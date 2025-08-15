"""Pagination utilities for the CLI.

Provides pagination for large result sets.
"""

from typing import Generic, TypeVar

T = TypeVar("T")


class PaginatedOutput(Generic[T]):
    """Paginated output for large result sets."""

    def __init__(self, items: list[T], page_size: int = 20):
        """Initialize paginated output.

        Args:
            items: List of items to paginate
            page_size: Items per page
        """
        self.items = items
        self.page_size = page_size
        self.current_page = 0

    @property
    def total_pages(self) -> int:
        """Get total number of pages.

        Returns:
            Total pages
        """
        return (len(self.items) + self.page_size - 1) // self.page_size

    @property
    def total_items(self) -> int:
        """Get total number of items.

        Returns:
            Total items
        """
        return len(self.items)

    def get_page(self, page: int) -> list[T]:
        """Get items for a specific page.

        Args:
            page: Page number (0-based)

        Returns:
            List of items for the page
        """
        start = page * self.page_size
        end = start + self.page_size
        return self.items[start:end]

    def next_page(self) -> bool:
        """Move to next page.

        Returns:
            True if moved to next page
        """
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            return True
        return False

    def prev_page(self) -> bool:
        """Move to previous page.

        Returns:
            True if moved to previous page
        """
        if self.current_page > 0:
            self.current_page -= 1
            return True
        return False

    def goto_page(self, page: int) -> bool:
        """Go to specific page.

        Args:
            page: Page number (0-based)

        Returns:
            True if page exists
        """
        if 0 <= page < self.total_pages:
            self.current_page = page
            return True
        return False

    def get_current_page(self) -> list[T]:
        """Get items for current page.

        Returns:
            List of items
        """
        return self.get_page(self.current_page)


def format_pagination_controls(
    current_page: int,
    total_pages: int,
    total_items: int,
) -> str:
    """Format pagination controls for display.

    Args:
        current_page: Current page (1-based for display)
        total_pages: Total number of pages
        total_items: Total number of items

    Returns:
        Formatted pagination controls
    """
    controls = []

    # Page info
    controls.append(f"Page {current_page} of {total_pages}")
    controls.append(f"({total_items} items)")

    # Navigation hints
    nav_parts = []
    if current_page > 1:
        nav_parts.append("[cyan]Previous[/cyan]")
    if current_page < total_pages:
        nav_parts.append("[cyan]Next[/cyan]")

    if nav_parts:
        controls.append(" | ".join(nav_parts))

    return " • ".join(controls)
