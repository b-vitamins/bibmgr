"""External editor integration for the CLI.

Provides functions for opening text in external editors.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import click


def get_editor() -> str:
    """Get the preferred text editor.

    Returns:
        Editor command
    """
    # Check environment variables
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")

    # Fall back to common editors
    if not editor:
        for cmd in ["nvim", "vim", "nano", "emacs", "code", "subl", "atom"]:
            if shutil.which(cmd):
                editor = cmd
                break

    return editor or "vi"


def open_in_editor(
    text: str = "",
    suffix: str = ".txt",
    editor: str | None = None,
) -> str:
    """Open text in external editor.

    Args:
        text: Initial text content
        suffix: File suffix for syntax highlighting
        editor: Editor command (defaults to get_editor())

    Returns:
        Edited text

    Raises:
        click.ClickException: If editor fails
    """
    if editor is None:
        editor = get_editor()

    # Create temporary file
    with tempfile.NamedTemporaryFile(
        mode="w+",
        suffix=suffix,
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(text)
        f.flush()
        temp_path = f.name

    try:
        # Open editor
        result = subprocess.call([editor, temp_path])

        if result != 0:
            raise click.ClickException(
                f"Editor '{editor}' exited with error code {result}"
            )

        # Read result
        with open(temp_path, encoding="utf-8") as f:
            return f.read()
    finally:
        # Clean up
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def edit_file(file_path: Path, editor: str | None = None) -> None:
    """Open a file in the external editor.

    Args:
        file_path: Path to file to edit
        editor: Editor command (defaults to get_editor())

    Raises:
        click.ClickException: If editor fails
    """
    if editor is None:
        editor = get_editor()

    result = subprocess.call([editor, str(file_path)])

    if result != 0:
        raise click.ClickException(f"Editor '{editor}' exited with error code {result}")


def edit_bibtex_entry(entry_text: str, editor: str | None = None) -> str:
    """Edit a BibTeX entry in external editor.

    Args:
        entry_text: BibTeX entry text
        editor: Editor command

    Returns:
        Edited BibTeX text
    """
    return open_in_editor(entry_text, suffix=".bib", editor=editor)


def edit_yaml_config(config_text: str, editor: str | None = None) -> str:
    """Edit YAML configuration in external editor.

    Args:
        config_text: YAML configuration text
        editor: Editor command

    Returns:
        Edited YAML text
    """
    return open_in_editor(config_text, suffix=".yaml", editor=editor)


def edit_note(note_text: str = "", editor: str | None = None) -> str:
    """Edit a note in external editor.

    Args:
        note_text: Initial note text
        editor: Editor command

    Returns:
        Edited note text
    """
    # Add helpful header
    template = f"""# Enter your note below. Lines starting with '#' will be removed.
# Save and exit to continue.

{note_text}
"""

    edited = open_in_editor(template, suffix=".md", editor=editor)

    # Remove comment lines
    lines = edited.split("\n")
    content_lines = [line for line in lines if not line.strip().startswith("#")]

    return "\n".join(content_lines).strip()
