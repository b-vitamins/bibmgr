"""Main CLI entry point."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from .commands import (
    entry_commands,
    advanced_commands,
    collection_commands,
    tag_commands,
    search_commands,
)
from .config import get_config
from .output import console, OutputContext


@click.group()
@click.version_option()
@click.option("--config", type=click.Path(), help="Config file path")
@click.option("--quiet", "-q", is_flag=True, help="Suppress output")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--no-color", is_flag=True, help="Disable colors")
@click.option("--debug", is_flag=True, help="Debug mode")
@click.pass_context
def cli(
    ctx: click.Context,
    config: Optional[str],
    quiet: bool,
    verbose: bool,
    no_color: bool,
    debug: bool,
):
    """Bibliography management with rich CLI interface."""
    # Set up context
    ctx.ensure_object(dict)
    ctx.obj["quiet"] = quiet
    ctx.obj["verbose"] = verbose
    ctx.obj["no_color"] = no_color
    ctx.obj["debug"] = debug

    # Load configuration
    if config:
        config_path = Path(config)
        if config_path.exists():
            from .config import Config

            ctx.obj["config"] = Config(config_path)
        else:
            if not quiet:
                assert console is not None  # console is always initialized
                console.print(f"Config file not found: {config}", style="yellow")
            ctx.obj["config"] = get_config()
    else:
        ctx.obj["config"] = get_config()

    # Set up output context
    ctx.obj["output"] = OutputContext(quiet=quiet, verbose=verbose, no_color=no_color)


# Register command groups
cli.add_command(entry_commands.add)
cli.add_command(entry_commands.edit)
cli.add_command(entry_commands.delete)
cli.add_command(entry_commands.show)
cli.add_command(entry_commands.list_entries)

cli.add_command(advanced_commands.import_entries)
cli.add_command(advanced_commands.dedupe)
cli.add_command(advanced_commands.validate)
cli.add_command(advanced_commands.stats)
cli.add_command(advanced_commands.export_entries)

cli.add_command(collection_commands.collection)
cli.add_command(tag_commands.tag)
cli.add_command(search_commands.search)


def main():
    """Main entry point."""
    try:
        cli()
    except Exception as e:
        if "--debug" in sys.argv or "-v" in sys.argv:
            raise
        else:
            assert console is not None  # console is always initialized
            console.print(f"Error: {e}", style="red")
            sys.exit(1)


if __name__ == "__main__":
    main()
