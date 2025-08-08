"""Tag management commands."""

from __future__ import annotations

import click

from ..helpers import handle_error


@click.group()
def tag():
    """Manage tags."""
    pass


@tag.command(name="add")
@click.argument("tag_name")
@click.argument("keys", nargs=-1)
@click.pass_context
def tag_add(ctx, tag_name, keys):
    """Add tags to entries."""
    handle_error("Tag add not yet implemented")


@tag.command(name="remove")
@click.argument("tag_name")
@click.argument("keys", nargs=-1)
@click.pass_context
def tag_remove(ctx, tag_name, keys):
    """Remove tags from entries."""
    handle_error("Tag remove not yet implemented")


@tag.command(name="list")
@click.option("--tree", is_flag=True, help="Show as hierarchy")
@click.pass_context
def tag_list(ctx, tree):
    """List all tags."""
    handle_error("Tag list not yet implemented")


@tag.command(name="show")
@click.argument("tag_name")
@click.pass_context
def tag_show(ctx, tag_name):
    """Show tag details with entries."""
    handle_error("Tag show not yet implemented")


@tag.command(name="rename")
@click.argument("old_name")
@click.argument("new_name")
@click.pass_context
def tag_rename(ctx, old_name, new_name):
    """Rename a tag."""
    handle_error("Tag rename not yet implemented")


@tag.command(name="merge")
@click.argument("tag1")
@click.argument("tag2")
@click.option("--into", required=True, help="Target tag name")
@click.pass_context
def tag_merge(ctx, tag1, tag2, into):
    """Merge tags."""
    handle_error("Tag merge not yet implemented")


@tag.command(name="delete")
@click.argument("tag_name")
@click.pass_context
def tag_delete(ctx, tag_name):
    """Delete a tag."""
    handle_error("Tag delete not yet implemented")


@tag.command(name="suggest")
@click.argument("key")
@click.pass_context
def tag_suggest(ctx, key):
    """Suggest tags for an entry."""
    handle_error("Tag suggest not yet implemented")


@tag.command(name="auto")
@click.option("--threshold", "-t", default=0.8, help="Suggestion threshold")
@click.option("--apply", is_flag=True, help="Apply suggestions")
@click.pass_context
def tag_auto(ctx, threshold, apply):
    """Automatically apply suggested tags."""
    handle_error("Tag auto not yet implemented")


@tag.command(name="stats")
@click.pass_context
def tag_stats(ctx):
    """Show tag statistics."""
    handle_error("Tag stats not yet implemented")


@tag.command(name="clean")
@click.pass_context
def tag_clean(ctx):
    """Clean unused tags."""
    handle_error("Tag clean not yet implemented")
