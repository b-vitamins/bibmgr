"""Interactive prompts and input validation for the CLI.

Provides various prompt types with validation and styling.
"""

import os
import subprocess
import tempfile
from collections.abc import Callable
from typing import TypeVar

from rich.prompt import Confirm, IntPrompt, Prompt

T = TypeVar("T")


def text_prompt(
    prompt: str,
    default: str | None = None,
    password: bool = False,
    show_default: bool = True,
) -> str:
    """Prompt for text input.

    Args:
        prompt: Prompt message
        default: Default value
        password: Hide input for passwords
        show_default: Show default value in prompt

    Returns:
        User input
    """
    result = Prompt.ask(
        prompt,
        default=default,
        password=password,
        show_default=show_default,
    )

    # Handle empty string when default is provided (for test compatibility)
    if result == "" and default is not None:
        return default

    return result or ""


def choice_prompt(
    prompt: str,
    choices: list[str],
    default: str | None = None,
    show_choices: bool = True,
) -> str:
    """Prompt for choice from list.

    Args:
        prompt: Prompt message
        choices: List of valid choices
        default: Default choice
        show_choices: Show choices in prompt

    Returns:
        Selected choice
    """
    result = Prompt.ask(
        prompt,
        choices=choices,
        default=default,
        show_choices=show_choices,
    )
    return result or ""


def confirm_prompt(
    prompt: str,
    default: bool = False,
) -> bool:
    """Prompt for confirmation.

    Args:
        prompt: Prompt message
        default: Default value

    Returns:
        True if confirmed
    """
    return Confirm.ask(prompt, default=default)


def integer_prompt(
    prompt: str,
    default: int | None = None,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    """Prompt for integer input.

    Args:
        prompt: Prompt message
        default: Default value
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        Integer value
    """
    # Rich's IntPrompt doesn't support min/max directly,
    # so we implement validation
    while True:
        value = IntPrompt.ask(prompt, default=default)

        if value is None:
            continue

        if min_value is not None and value < min_value:
            print(f"[red]Value must be at least {min_value}[/red]")
            continue

        if max_value is not None and value > max_value:
            print(f"[red]Value must be at most {max_value}[/red]")
            continue

        return value


def validated_prompt(
    prompt: str,
    validator: Callable[[str], T],
    default: str | None = None,
    error_message: str = "Invalid input",
) -> T:
    """Prompt with custom validation.

    Args:
        prompt: Prompt message
        validator: Validation function that returns validated value or raises ValueError
        default: Default value
        error_message: Error message for validation failures

    Returns:
        Validated value
    """
    while True:
        value = text_prompt(prompt, default=default)

        try:
            return validator(value)
        except ValueError as e:
            error_msg = str(e) if str(e) else error_message
            print(f"[red]{error_msg}[/red]")


def multiline_prompt(
    prompt: str,
    default: str | None = None,
    editor: str | None = None,
) -> str:
    """Prompt for multiline text using external editor.

    Args:
        prompt: Prompt message
        default: Default text
        editor: Editor command (defaults to $EDITOR)

    Returns:
        Multiline text
    """
    # Show prompt
    print(f"[cyan]{prompt}[/cyan]")
    print("[dim]Press Enter to open editor...[/dim]")
    try:
        input()
    except EOFError:
        # Handle non-interactive mode (like in tests)
        pass

    # Open editor
    text = open_editor(default or "", editor)
    return text


def open_editor(text: str = "", editor: str | None = None) -> str:
    """Open external editor for text input.

    Args:
        text: Initial text
        editor: Editor command

    Returns:
        Edited text
    """
    # Determine editor
    if not editor:
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"

    # Create temporary file
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as f:
        f.write(text)
        f.flush()
        temp_path = f.name

    try:
        # Open editor
        subprocess.call([editor, temp_path])

        # Read result
        with open(temp_path) as f:
            return f.read()
    finally:
        # Clean up
        os.unlink(temp_path)
