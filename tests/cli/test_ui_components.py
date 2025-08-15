"""Tests for CLI UI components.

This module comprehensively tests UI components including:
- Console setup and themes
- Progress indicators and spinners
- Interactive prompts and validation
- Color schemes and styling
- Status indicators and icons
- Error and success messages
- Panels and layouts
"""

from io import StringIO
from unittest.mock import patch

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table


class TestConsoleSetup:
    """Test console configuration and themes."""

    def test_create_console_default(self):
        """Test creating console with default settings."""
        from bibmgr.cli.ui.console import create_console

        console = create_console()

        assert isinstance(console, Console)
        assert console.width == 120  # Default width
        assert console.is_terminal

    def test_create_console_with_theme(self):
        """Test creating console with custom theme."""
        from bibmgr.cli.ui.console import create_console

        console = create_console(theme_name="professional")

        assert hasattr(console, "theme")  # type: ignore[attr-defined]
        # Theme should have our custom styles
        theme = console.theme  # type: ignore[attr-defined]
        assert "success" in theme.styles  # type: ignore[attr-defined]
        assert "error" in theme.styles  # type: ignore[attr-defined]

    def test_console_width_configuration(self):
        """Test console width configuration."""
        from bibmgr.cli.ui.console import create_console

        # Test with custom width
        console = create_console(width=80)
        assert console.width == 80

        # Test with auto width
        console = create_console(width="auto")
        assert console.width > 0  # Should detect terminal width

    def test_console_output_capture(self, test_console):
        """Test capturing console output."""
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True)

        console.print("Test output", style="bold green")
        output = string_io.getvalue()

        assert "Test output" in output


class TestThemes:
    """Test color themes and styling."""

    def test_professional_theme(self):
        """Test professional theme colors."""
        from bibmgr.cli.ui.themes import THEMES

        theme = THEMES["professional"]

        assert "primary" in theme
        assert "success" in theme
        assert "error" in theme
        assert "warning" in theme
        assert "info" in theme

    def test_apply_theme_to_console(self, test_console):
        """Test applying theme to console."""
        from bibmgr.cli.ui.themes import apply_theme

        apply_theme(test_console, "professional")

        # Test styled output
        string_io = StringIO()
        test_console.file = string_io

        test_console.print("Success!", style="success")
        output = string_io.getvalue()

        assert "Success!" in output

    def test_theme_for_entry_types(self):
        """Test theme colors for entry types."""
        from bibmgr.cli.ui.themes import get_entry_type_style

        assert get_entry_type_style("article") == "cyan"
        assert get_entry_type_style("book") == "blue"
        assert get_entry_type_style("inproceedings") == "magenta"

    def test_theme_for_status_indicators(self):
        """Test theme colors for status indicators."""
        from bibmgr.cli.ui.themes import get_status_style

        assert get_status_style("read") == "green"
        assert get_status_style("reading") == "yellow"
        assert get_status_style("unread") == "dim white"


class TestProgressIndicators:
    """Test progress bars and spinners."""

    def test_create_progress_bar(self):
        """Test creating a progress bar."""
        from bibmgr.cli.ui.progress import create_progress_bar

        progress = create_progress_bar()

        assert isinstance(progress, Progress)
        task = progress.add_task("Test task", total=100)

        # Update progress
        progress.update(task, advance=50)
        assert progress.tasks[0].completed == 50

    def test_progress_context_manager(self):
        """Test progress bar as context manager."""
        from bibmgr.cli.ui.progress import progress_bar

        with progress_bar("Processing", total=10) as update:
            for i in range(10):
                update(1)

    def test_indeterminate_progress(self):
        """Test indeterminate progress spinner."""
        from bibmgr.cli.ui.progress import spinner

        with spinner("Loading..."):
            # Simulate work
            import time

            time.sleep(0.01)

    def test_multi_progress_tasks(self):
        """Test multiple concurrent progress tasks."""
        from bibmgr.cli.ui.progress import MultiProgress

        mp = MultiProgress()

        task1 = mp.add_task("Task 1", total=100)
        task2 = mp.add_task("Task 2", total=50)

        mp.update(task1, advance=25)
        mp.update(task2, advance=10)

        assert mp.get_progress(task1) == 0.25
        assert mp.get_progress(task2) == 0.20

    def test_progress_with_status_updates(self):
        """Test progress with changing status messages."""
        from bibmgr.cli.ui.progress import StatusProgress

        sp = StatusProgress()
        task = sp.add_task("Import", total=100)

        sp.update_status(task, "Reading file...")
        sp.advance(task, 25)

        sp.update_status(task, "Validating entries...")
        sp.advance(task, 50)

        assert sp.get_status(task) == "Validating entries..."


class TestPrompts:
    """Test interactive prompts and input validation."""

    def test_text_prompt(self):
        """Test basic text prompt."""
        from bibmgr.cli.ui.prompts import text_prompt

        with patch("rich.prompt.Prompt.ask", return_value="test input"):
            result = text_prompt("Enter text")
            assert result == "test input"

    def test_text_prompt_with_default(self):
        """Test text prompt with default value."""
        from bibmgr.cli.ui.prompts import text_prompt

        with patch("rich.prompt.Prompt.ask", return_value=""):
            result = text_prompt("Enter text", default="default value")
            assert result == "default value"

    def test_choice_prompt(self):
        """Test choice prompt."""
        from bibmgr.cli.ui.prompts import choice_prompt

        with patch("rich.prompt.Prompt.ask", return_value="option1"):
            result = choice_prompt(
                "Select option", choices=["option1", "option2", "option3"]
            )
            assert result == "option1"

    def test_confirm_prompt(self):
        """Test confirmation prompt."""
        from bibmgr.cli.ui.prompts import confirm_prompt

        with patch("rich.prompt.Confirm.ask", return_value=True):
            result = confirm_prompt("Are you sure?")
            assert result is True

    def test_integer_prompt(self):
        """Test integer input prompt."""
        from bibmgr.cli.ui.prompts import integer_prompt

        with patch("rich.prompt.IntPrompt.ask", return_value=42):
            result = integer_prompt("Enter number", min_value=1, max_value=100)
            assert result == 42

    def test_prompt_with_validation(self):
        """Test prompt with custom validation."""
        from bibmgr.cli.ui.prompts import validated_prompt

        def validate_email(value):
            if "@" not in value:
                raise ValueError("Invalid email")
            return value

        with patch("rich.prompt.Prompt.ask", return_value="test@example.com"):
            result = validated_prompt("Enter email", validator=validate_email)
            assert result == "test@example.com"

    def test_multiline_prompt(self):
        """Test multiline text input."""
        from bibmgr.cli.ui.prompts import multiline_prompt

        with patch(
            "bibmgr.cli.ui.prompts.open_editor", return_value="Line 1\nLine 2\nLine 3"
        ):
            with patch("builtins.input", return_value=""):
                result = multiline_prompt("Enter text")
                assert result == "Line 1\nLine 2\nLine 3"


class TestStatusIndicators:
    """Test status indicators and icons."""

    def test_status_icons(self):
        """Test status icon rendering."""
        from bibmgr.cli.ui.widgets import StatusIcon

        assert StatusIcon.SUCCESS == "[green]✓[/green]"
        assert StatusIcon.ERROR == "[red]✗[/red]"
        assert StatusIcon.WARNING == "[yellow]⚠[/yellow]"
        assert StatusIcon.INFO == "[blue]ℹ[/blue]"

    def test_read_status_indicators(self):
        """Test read status indicators."""
        from bibmgr.cli.ui.widgets import get_read_status_icon

        assert get_read_status_icon("read") == "[green]●[/green]"
        assert get_read_status_icon("reading") == "[yellow]◐[/yellow]"
        assert get_read_status_icon("unread") == "[dim]○[/dim]"

    def test_rating_display(self):
        """Test rating star display."""
        from bibmgr.cli.ui.widgets import format_rating

        assert format_rating(5) == "[yellow]★★★★★[/yellow]"
        assert format_rating(3) == "[yellow]★★★[/yellow][dim]☆☆[/dim]"
        assert format_rating(0) == "[dim]☆☆☆☆☆[/dim]"

    def test_entry_type_badges(self):
        """Test entry type badge formatting."""
        from bibmgr.cli.ui.widgets import format_entry_type_badge

        badge = format_entry_type_badge("article")
        assert "[cyan]" in badge
        assert "Article" in badge or "article" in badge

    def test_collection_type_indicators(self):
        """Test collection type indicators."""
        from bibmgr.cli.ui.widgets import get_collection_icon

        assert get_collection_icon("manual") == "📁"
        assert get_collection_icon("smart") == "🔍"


class TestMessageFormatting:
    """Test success, error, and info message formatting."""

    def test_success_message(self, test_console):
        """Test success message formatting."""
        from bibmgr.cli.ui.messages import success_message

        string_io = StringIO()
        test_console.file = string_io

        success_message(test_console, "Operation completed successfully")
        output = string_io.getvalue()

        assert "✓" in output
        assert "Operation completed successfully" in output

    def test_error_message(self, test_console):
        """Test error message formatting."""
        from bibmgr.cli.ui.messages import error_message

        string_io = StringIO()
        test_console.file = string_io

        error_message(test_console, "Something went wrong")
        output = string_io.getvalue()

        assert "✗" in output or "Error" in output
        assert "Something went wrong" in output

    def test_warning_message(self, test_console):
        """Test warning message formatting."""
        from bibmgr.cli.ui.messages import warning_message

        string_io = StringIO()
        test_console.file = string_io

        warning_message(test_console, "This might cause issues")
        output = string_io.getvalue()

        assert "⚠" in output or "Warning" in output
        assert "This might cause issues" in output

    def test_info_message(self, test_console):
        """Test info message formatting."""
        from bibmgr.cli.ui.messages import info_message

        string_io = StringIO()
        test_console.file = string_io

        info_message(test_console, "For your information")
        output = string_io.getvalue()

        assert "ℹ" in output or "Info" in output
        assert "For your information" in output


class TestPanelsAndLayouts:
    """Test panel layouts and formatting."""

    def test_entry_panel(self, sample_entries):
        """Test entry detail panel."""
        from bibmgr.cli.ui.panels import create_entry_panel

        panel = create_entry_panel(sample_entries[0])

        assert isinstance(panel, Panel)
        assert panel.title == "Entry: doe2024"

    def test_error_panel(self):
        """Test error panel with details."""
        from bibmgr.cli.ui.panels import create_error_panel

        panel = create_error_panel(
            "Validation Error",
            "Entry missing required fields",
            suggestions=["Add missing journal field", "Add missing year"],
        )

        assert isinstance(panel, Panel)
        assert panel.title and "Validation Error" in str(panel.title)  # type: ignore[operator]
        assert panel.border_style == "red"

    def test_summary_panel(self):
        """Test summary statistics panel."""
        from bibmgr.cli.ui.panels import create_summary_panel

        stats = {
            "Total Entries": 100,
            "Articles": 60,
            "Books": 25,
            "Conference Papers": 15,
        }

        panel = create_summary_panel("Repository Statistics", stats)

        assert isinstance(panel, Panel)
        assert panel.title and "Repository Statistics" in str(panel.title)  # type: ignore[operator]

    def test_nested_panels(self):
        """Test nested panel layouts."""
        from bibmgr.cli.ui.panels import create_nested_panel

        inner_content = Table()
        inner_content.add_column("Field")
        inner_content.add_column("Value")
        inner_content.add_row("Title", "Test")

        panel = create_nested_panel(
            inner_content, title="Entry Details", subtitle="doe2024"
        )

        assert isinstance(panel, Panel)


class TestInteractiveWidgets:
    """Test interactive UI widgets."""

    def test_selection_menu(self):
        """Test interactive selection menu."""
        from bibmgr.cli.ui.widgets import SelectionMenu

        menu = SelectionMenu(
            title="Select an option", options=["Option 1", "Option 2", "Option 3"]
        )

        with patch.object(menu, "get_selection", return_value=1):
            selected = menu.show()
            assert selected == "Option 2"

    def test_checkbox_list(self):
        """Test checkbox list widget."""
        from bibmgr.cli.ui.widgets import CheckboxList

        checklist = CheckboxList(
            title="Select items",
            options=["Item 1", "Item 2", "Item 3"],
            selected=[0, 2],  # Pre-select first and third
        )

        assert checklist.is_selected(0)
        assert not checklist.is_selected(1)
        assert checklist.is_selected(2)

    def test_tree_view(self):
        """Test tree view widget for collections."""
        from bibmgr.cli.ui.widgets import TreeView

        tree = TreeView()
        tree.add_node("root", "Root Collection")
        tree.add_node("child1", "Child 1", parent="root")
        tree.add_node("child2", "Child 2", parent="root")
        tree.add_node("grandchild", "Grandchild", parent="child1")

        output = tree.render()

        assert "Root Collection" in output
        assert "├── Child 1" in output
        assert "│   └── Grandchild" in output
        assert "└── Child 2" in output


class TestPagination:
    """Test pagination controls."""

    def test_paginated_output(self):
        """Test paginated output display."""
        from bibmgr.cli.ui.pagination import PaginatedOutput

        items = [f"Item {i}" for i in range(100)]

        paginator = PaginatedOutput(items, page_size=10)

        assert paginator.total_pages == 10
        assert len(paginator.get_page(0)) == 10
        assert paginator.get_page(0)[0] == "Item 0"
        assert paginator.get_page(9)[0] == "Item 90"

    def test_pagination_controls(self):
        """Test pagination control display."""
        from bibmgr.cli.ui.pagination import format_pagination_controls

        controls = format_pagination_controls(
            current_page=3, total_pages=10, total_items=95
        )

        assert "Page 3 of 10" in controls
        assert "95 items" in controls
        assert "Previous" in controls
        assert "Next" in controls
