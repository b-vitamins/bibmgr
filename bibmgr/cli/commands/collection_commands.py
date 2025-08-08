"""Collection management commands."""

from __future__ import annotations

import click

from ..helpers import handle_error


@click.group()
def collection():
    """Manage collections."""
    pass


@collection.command(name="create")
@click.argument("name")
@click.option("--description", "-d", help="Collection description")
@click.option("--query", "-q", help="Smart collection query")
@click.pass_context
def collection_create(ctx, name, description, query):
    """Create a new collection."""
    handle_error("Collection create not yet implemented")


@collection.command(name="list")
@click.pass_context
def collection_list(ctx):
    """List all collections."""
    handle_error("Collection list not yet implemented")


@collection.command(name="show")
@click.argument("name")
@click.pass_context
def collection_show(ctx, name):
    """Show collection details."""
    handle_error("Collection show not yet implemented")


@collection.command(name="add")
@click.argument("collection_name")
@click.argument("keys", nargs=-1)
@click.pass_context
def collection_add(ctx, collection_name, keys):
    """Add entries to a collection."""
    handle_error("Collection add not yet implemented")


@collection.command(name="remove")
@click.argument("collection_name")
@click.argument("keys", nargs=-1)
@click.pass_context
def collection_remove(ctx, collection_name, keys):
    """Remove entries from a collection."""
    handle_error("Collection remove not yet implemented")


@collection.command(name="delete")
@click.argument("name")
@click.pass_context
def collection_delete(ctx, name):
    """Delete a collection."""
    handle_error("Collection delete not yet implemented")


@collection.command(name="rename")
@click.argument("old_name")
@click.argument("new_name")
@click.pass_context
def collection_rename(ctx, old_name, new_name):
    """Rename a collection."""
    handle_error("Collection rename not yet implemented")


@collection.command(name="merge")
@click.argument("source1")
@click.argument("source2")
@click.option("--into", required=True, help="Target collection name")
@click.pass_context
def collection_merge(ctx, source1, source2, into):
    """Merge collections."""
    handle_error("Collection merge not yet implemented")


@collection.command(name="copy")
@click.argument("source")
@click.argument("target")
@click.pass_context
def collection_copy(ctx, source, target):
    """Copy a collection."""
    handle_error("Collection copy not yet implemented")


@collection.command(name="stats")
@click.argument("name")
@click.pass_context
def collection_stats(ctx, name):
    """Show collection statistics."""
    handle_error("Collection stats not yet implemented")
