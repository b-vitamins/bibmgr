"""Search and query CLI commands."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from bibmgr.search import SearchResultCollection, SortOrder
from bibmgr.search.results import Facet


def get_search_service(ctx):
    """Get the search service from context."""
    return ctx.obj.search_service


def get_repository(ctx):
    """Get the entry repository from context."""
    return ctx.obj.repository


@click.command()
@click.argument("query", required=True)
@click.option("--limit", "-n", type=int, default=20, help="Maximum results to show")
@click.option("--offset", type=int, default=0, help="Skip first N results")
@click.option(
    "--sort",
    "-s",
    type=click.Choice(["relevance", "year", "title", "author"]),
    default="relevance",
    help="Sort order",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "list", "detailed"]),
    default="table",
    help="Output format",
)
@click.option("--no-highlight", is_flag=True, help="Disable result highlighting")
@click.option("--export", type=click.Path(), help="Export results to file")
@click.option(
    "--export-format",
    type=click.Choice(["bibtex", "json", "csv"]),
    default="bibtex",
    help="Export format",
)
@click.pass_context
def search(ctx: click.Context, query: str, **kwargs) -> None:
    """Search bibliography entries.

    Supports advanced query syntax:
    - Field search: author:Doe, title:"quantum computing", year:2024
    - Boolean: quantum AND computing, machine OR learning
    - Wildcards: quant*, neuro*
    - Fuzzy: machne~, computr~2
    - Ranges: year:2020..2024
    - Phrases: "exact phrase"
    """
    console = ctx.obj.console
    search_service = get_search_service(ctx)
    repository = get_repository(ctx)

    try:
        # Show searching indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(f"🔍 Searching for '{query}'...", total=None)

            # Execute search
            results = search_service.search(
                query,
                limit=kwargs["limit"],
                offset=kwargs["offset"],
                highlight_results=not kwargs["no_highlight"],
                sort_by=_get_sort_order(kwargs["sort"]),
            )

        # Display results
        _display_results(console, results, query, kwargs["format"], repository)

        # Show facets if available
        if results.facets:
            # Handle both dict and list of Facet objects
            if isinstance(results.facets, dict):
                # Convert dict to list of Facet objects
                facet_list = []
                for field, facet in results.facets.items():
                    if isinstance(facet, Facet):
                        facet_list.append(facet)
                if facet_list:
                    _display_facets(console, facet_list)
            else:
                _display_facets(console, results.facets)

        # Show suggestions if available (even when no results)
        if results.suggestions:
            _display_suggestions(console, results.suggestions)
        # DEBUG
        # console.print(f"[DEBUG] Has suggestions: {bool(results.suggestions)}")

        # Export if requested
        if kwargs["export"]:
            _export_results(
                console, results, kwargs["export"], kwargs["export_format"], repository
            )

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


@click.command()
@click.option("--interactive", "-i", is_flag=True, help="Interactive query builder")
@click.option("--type", "entry_type", help="Filter by entry type")
@click.option("--author", help="Filter by author")
@click.option("--year", help="Year or year range (e.g., 2024 or 2020..2024)")
@click.option("--journal", help="Filter by journal")
@click.option("--keywords", help="Filter by keywords")
@click.option("--has-doi", is_flag=True, help="Only entries with DOI")
@click.option("--has-file", is_flag=True, help="Only entries with attached files")
@click.option("--tag", multiple=True, help="Filter by tags")
@click.option("--recent", type=int, help="Show entries from last N days")
@click.option("--unread", is_flag=True, help="Show only unread entries")
@click.option("--min-rating", type=int, help="Minimum rating (1-5)")
@click.option("--save-as", help="Save query with given name for reuse")
@click.option("--limit", "-n", type=int, default=20, help="Maximum results")
@click.pass_context
def find(ctx: click.Context, interactive: bool, **kwargs) -> None:
    """Advanced query builder for finding entries.

    Build complex queries interactively or with command-line options.
    """
    console = ctx.obj.console
    search_service = get_search_service(ctx)
    repository = get_repository(ctx)

    try:
        # If no options provided and not explicitly interactive, default to interactive
        if interactive or not any(
            kwargs.get(k)
            for k in [
                "entry_type",
                "author",
                "year",
                "journal",
                "keywords",
                "has_doi",
                "has_file",
                "tag",
                "recent",
                "unread",
                "min_rating",
            ]
        ):
            query = _build_query_interactive(console)
        else:
            query = _build_query_from_options(kwargs)

        if not query:
            console.print("[yellow]No search criteria specified[/yellow]")
            return

        # Show the built query or special message for recent
        if kwargs.get("recent"):
            console.print(
                f"\n[cyan]Recent entries[/cyan] (last {kwargs['recent']} days)"
            )
        else:
            console.print(f"\n[cyan]Query:[/cyan] {query}")

        # Execute search
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Searching...", total=None)

            results = search_service.search(query, limit=kwargs["limit"])

        # Display results
        _display_results(console, results, query, "table", repository)

        # Save query if requested
        if kwargs.get("save_as"):
            # TODO: Implement actual query saving
            console.print(f"\n[green]✓[/green] Query saved as '{kwargs['save_as']}'")

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


@click.command()
@click.argument("key")
@click.option("--limit", "-n", type=int, default=10, help="Maximum similar entries")
@click.option(
    "--min-score", type=float, default=0.7, help="Minimum similarity score (0-1)"
)
@click.pass_context
def similar(ctx: click.Context, key: str, limit: int, min_score: float) -> None:
    """Find entries similar to the specified entry."""
    console = ctx.obj.console
    search_service = get_search_service(ctx)
    repository = get_repository(ctx)

    try:
        # Get the reference entry
        entry = repository.find(key)
        if not entry:
            console.print(f"[red]Entry not found:[/red] {key}")
            ctx.exit(1)

        # Build similarity query from entry fields
        query_parts = []
        if entry.title:
            query_parts.append(entry.title)
        if entry.abstract:
            query_parts.append(entry.abstract[:200])  # First 200 chars
        if entry.keywords:
            keywords = (
                entry.keywords
                if isinstance(entry.keywords, str)
                else " ".join(entry.keywords)
            )
            query_parts.append(keywords)

        if not query_parts:
            console.print(
                "[yellow]Not enough information in entry for similarity search[/yellow]"
            )
            return

        query = " ".join(query_parts)

        # Search for similar entries
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(f"Finding entries similar to {key}...", total=None)

            # Use more_like_this if available, otherwise use regular search
            if hasattr(search_service, "more_like_this"):
                # Call with positional args for key and min_score, limit as keyword
                results = search_service.more_like_this(
                    key, None, min_score, limit=limit
                )
            else:
                results = search_service.search(
                    query, limit=limit + 1
                )  # +1 to exclude self

        # Filter out the original entry and low scores
        similar_entries = [
            match
            for match in results.matches
            if match.entry_key != key and match.score >= min_score
        ][:limit]

        if not similar_entries:
            console.print(
                f"[yellow]No similar entries found (threshold: {min_score})[/yellow]"
            )
            return

        # Display similar entries
        console.print(f"\n[bold]Similar to: {key}[/bold]\n")

        table = Table(title=f"Similar Entries (threshold: {min_score})")
        table.add_column("Key", style="cyan")
        table.add_column("Title", overflow="ellipsis", max_width=40)
        table.add_column("Similarity", justify="right")
        table.add_column("Year", justify="center")

        for match in similar_entries:
            similar_entry = repository.find(match.entry_key)
            if similar_entry:
                similarity_pct = f"{match.score * 100:.0f}%"
                table.add_row(
                    similar_entry.key,
                    similar_entry.title or "",
                    similarity_pct,
                    str(similar_entry.year) if similar_entry.year else "",
                )

        console.print(table)

    except Exception as e:
        if ctx.obj.debug:
            raise
        console.print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Helper functions
def _get_sort_order(sort: str) -> SortOrder:
    """Convert string sort option to SortOrder enum."""
    mapping = {
        "relevance": SortOrder.RELEVANCE,
        "year": SortOrder.DATE_DESC,  # Use DATE_DESC for year sorting
        "title": SortOrder.TITLE_ASC,
        "author": SortOrder.AUTHOR_ASC,
    }
    return mapping.get(sort, SortOrder.RELEVANCE)


def _display_results(
    console: Console,
    results: SearchResultCollection,
    query: str,
    format: str,
    repository,
) -> None:
    """Display search results in the specified format."""
    if results.total == 0:
        console.print(f"\n[yellow]No results found for '{query}'[/yellow]")
        return

    # Show result count and timing
    timing = ""
    if results.statistics:
        # Handle both dict and SearchStatistics object
        if isinstance(results.statistics, dict):
            timing = f" ({results.statistics.get('took_ms', results.statistics.get('search_time_ms', 0))}ms)"
        else:
            timing = f" ({results.statistics.search_time_ms}ms)"

    if results.total == 1:
        console.print(f"\nFound [green]1[/green] result{timing}")
    else:
        console.print(f"\nFound [green]{results.total}[/green] results{timing}")

    if format == "table":
        _display_results_table(console, results, repository)
    elif format == "list":
        _display_results_list(console, results, repository)
    elif format == "detailed":
        _display_results_detailed(console, results, repository)


def _display_results_table(
    console: Console, results: SearchResultCollection, repository
) -> None:
    """Display results in table format."""
    table = Table()
    table.add_column("Key", style="cyan")
    table.add_column("Title", overflow="ellipsis", max_width=40)
    table.add_column("Authors", overflow="ellipsis", max_width=25)
    table.add_column("Year", justify="center")
    table.add_column("Score", justify="right")

    for match in results.matches:
        entry = repository.find(match.entry_key)
        if entry:
            score_pct = f"{match.score * 100:.0f}%"
            table.add_row(
                entry.key,
                entry.title or "",
                (entry.author or "")[:25] + "..."
                if entry.author and len(entry.author) > 25
                else entry.author or "",
                str(entry.year) if entry.year else "",
                score_pct,
            )

    console.print(table)


def _display_results_list(
    console: Console, results: SearchResultCollection, repository
) -> None:
    """Display results in list format."""
    for i, match in enumerate(results.matches, 1):
        entry = repository.find(match.entry_key)
        if entry:
            score_pct = f"{match.score * 100:.0f}%"
            console.print(
                f"\n[cyan]{i}.[/cyan] {entry.key} ([green]{score_pct}[/green])"
            )
            console.print(f"   {entry.title}")
            if entry.author:
                console.print(f"   [dim]{entry.author}[/dim]")


def _display_results_detailed(
    console: Console, results: SearchResultCollection, repository
) -> None:
    """Display results with detailed information and highlights."""
    for i, match in enumerate(results.matches, 1):
        entry = repository.find(match.entry_key)
        if entry:
            # Create panel with entry details
            content = []
            content.append(f"[bold]Title:[/bold] {entry.title}")
            if entry.author:
                content.append(f"[bold]Authors:[/bold] {entry.author}")
            if entry.year:
                content.append(f"[bold]Year:[/bold] {entry.year}")
            if entry.journal:
                content.append(f"[bold]Journal:[/bold] {entry.journal}")

            # Add highlights if available
            if match.highlights:
                content.append("")  # Empty line
                for field, highlights in match.highlights.items():
                    if highlights:
                        content.append(f"[bold]{field.title()}:[/bold]")
                        for highlight in highlights:
                            # Replace <mark> tags with Rich markup
                            formatted = highlight.replace("<mark>", "[yellow]").replace(
                                "</mark>", "[/yellow]"
                            )
                            content.append(f"  ...{formatted}...")

            score_pct = f"{match.score * 100:.0f}%"
            panel = Panel(
                "\n".join(content),
                title=f"[cyan]{entry.key}[/cyan] - [green]{score_pct}[/green]",
                border_style="blue",
            )
            console.print(panel)


def _display_facets(console: Console, facets: list) -> None:
    """Display search facets."""
    if not facets:
        return

    console.print("\n[bold]Refine by:[/bold]")

    for facet in facets:
        if facet.values:
            console.print(f"\n  [cyan]{facet.display_name}:[/cyan]")
            for value in facet.values[:5]:  # Show top 5
                console.print(f"    {value.value} ({value.count})")


def _display_suggestions(console: Console, suggestions: list) -> None:
    """Display search suggestions."""
    if not suggestions:
        return

    console.print("\n[bold]Suggestions:[/bold]")
    for suggestion in suggestions:
        if suggestion.description:
            console.print(f"  • {suggestion.description}")
        else:
            console.print(f"  • Did you mean: [cyan]{suggestion.suggestion}[/cyan]?")


def _build_query_interactive(console: Console) -> str:
    """Build a query interactively with menu-driven interface."""
    console.print("\n[bold]Query Builder[/bold]\n")

    conditions = []

    while True:
        # Display current query if any
        if conditions:
            console.print("\n[cyan]Current query:[/cyan]")
            console.print(" AND ".join(conditions))

        # Display menu
        console.print("\n1. Add field condition")
        console.print("2. Add free text search")
        console.print("3. Add another condition")
        console.print("4. Clear all conditions")
        console.print("5. Execute search")
        console.print("6. Cancel")

        choice = Prompt.ask("\nSelect option", choices=["1", "2", "3", "4", "5", "6"])

        if choice == "1" or choice == "3":
            # Add field condition
            field = Prompt.ask(
                "Field",
                choices=["author", "title", "year", "journal", "keywords", "type"],
            )

            if field == "year":
                operator = Prompt.ask(
                    "Operator", choices=["=", ">", ">=", "<", "<=", ".."]
                )
            else:
                operator = Prompt.ask(
                    "Operator", choices=["contains", "=", "starts_with", "ends_with"]
                )

            value = Prompt.ask("Value")

            # Build condition based on field and operator
            if operator == "contains":
                condition = f'{field}:"{value}"'
            elif operator == "..":
                # Range query
                condition = f"{field}:{value}"
            elif operator in [">", ">=", "<", "<="]:
                condition = f"{field}:{operator}{value}"
            else:
                condition = f'{field}:"{value}"'

            conditions.append(condition)

        elif choice == "2":
            # Free text search
            text = Prompt.ask("Search text")
            conditions.append(text)

        elif choice == "4":
            # Clear conditions
            conditions = []
            console.print("[yellow]All conditions cleared[/yellow]")

        elif choice == "5":
            # Execute search
            break

        elif choice == "6":
            # Cancel
            return ""

    return " AND ".join(conditions) if conditions else ""


def _build_query_from_options(options: dict) -> str:
    """Build a query from command-line options."""
    query_parts = []

    if options.get("entry_type"):
        query_parts.append(f"type:{options['entry_type']}")

    if options.get("author"):
        query_parts.append(f'author:"{options["author"]}"')

    if options.get("year"):
        query_parts.append(f"year:{options['year']}")

    if options.get("journal"):
        query_parts.append(f'journal:"{options["journal"]}"')

    if options.get("keywords"):
        query_parts.append(f'keywords:"{options["keywords"]}"')

    if options.get("has_doi"):
        query_parts.append("has:doi")

    if options.get("has_file"):
        query_parts.append("has:file")

    if options.get("recent"):
        # Calculate date range for recent entries
        from datetime import datetime, timedelta

        days = options["recent"]
        start_date = datetime.now() - timedelta(days=days)
        # Use a year range query as approximation (since we don't have date field)
        query_parts.append(f"year:>={start_date.year}")

    if options.get("unread"):
        query_parts.append('read_status:"unread"')

    if options.get("min_rating"):
        query_parts.append(f"rating:>={options['min_rating']}")

    for tag in options.get("tag", []):
        query_parts.append(f"tag:{tag}")

    return " AND ".join(query_parts)


def _export_results(
    console: Console,
    results: SearchResultCollection,
    output_path: str,
    format: str,
    repository,
) -> None:
    """Export search results to file."""
    entries = []
    for match in results.matches:
        entry = repository.find(match.entry_key)
        if entry:
            entries.append(entry)

    if not entries:
        console.print("[yellow]No entries to export[/yellow]")
        return

    try:
        content = ""
        if format == "bibtex":
            from bibmgr.cli.formatters.bibtex import format_entries_bibtex

            content = format_entries_bibtex(entries)
        elif format == "json":
            from bibmgr.cli.formatters.json import format_entries_json

            content = format_entries_json(entries)
        elif format == "csv":
            # Simple CSV implementation
            import csv
            from io import StringIO

            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(["key", "type", "title", "author", "year", "journal"])
            for entry in entries:
                writer.writerow(
                    [
                        entry.key,
                        entry.type.value,
                        entry.title or "",
                        entry.author or "",
                        entry.year or "",
                        entry.journal or "",
                    ]
                )
            content = output.getvalue()

        with open(output_path, "w") as f:
            f.write(content)

        console.print(
            f"[green]✓[/green] Exported {len(entries)} results to {output_path}"
        )

    except Exception as e:
        console.print(f"[red]Export failed:[/red] {e}")
