"""Search commands."""

from __future__ import annotations

import click

from ..helpers import handle_error


@click.command()
@click.argument("query", nargs=-1)
@click.option("--type", help="Filter by type")
@click.option("--year", help="Filter by year or range")
@click.option("--author", help="Filter by author")
@click.option("--limit", "-l", default=20, help="Results per page")
@click.option("--page", "-p", default=1, help="Page number")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--explain", is_flag=True, help="Explain scoring")
@click.option("--export", type=click.Path(), help="Export results to file")
@click.pass_context
def search(ctx, query, type, year, author, limit, page, output_json, explain, export):
    """Search bibliography with natural language queries."""
    handle_error("Search command not yet implemented")
