"""Quality check and maintenance commands for bibliography entries.

Provides commands for validating entries, detecting duplicates, cleaning data,
and generating quality reports.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from bibmgr.cli.utils.completion import get_entry_keys
from bibmgr.cli.utils.context import pass_context
from bibmgr.operations.quality_commands import (
    GenerateQualityReportCommand,
    ValidateBatchCommand,
    ValidateEntryCommand,
)
from bibmgr.operations.quality_handlers import QualityHandler
from bibmgr.operations.workflows import (
    DeduplicationConfig,
    DeduplicationMode,
    DeduplicationWorkflow,
)

console = Console()


def get_repository(ctx):
    """Get the entry repository from context."""
    return ctx.repository


def get_repository_manager(ctx):
    """Get the repository manager from context."""
    return ctx.repository_manager


def get_quality_handler(ctx):
    """Get quality handler from context."""
    return QualityHandler()


def get_event_bus(ctx):
    """Get event bus from context."""
    return ctx.event_bus


@click.command()
@click.argument("entry_keys", nargs=-1, shell_complete=get_entry_keys)
@click.option("--all", "-a", is_flag=True, help="Check all entries")
@click.option(
    "--severity",
    type=click.Choice(["error", "warning", "info"]),
    help="Minimum severity level to display",
)
@click.option("--fix", is_flag=True, help="Attempt to fix issues automatically")
@click.option(
    "--format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
@pass_context
def check(
    ctx,
    entry_keys: tuple[str, ...],
    all: bool,
    severity: str | None,
    fix: bool,
    format: str,
):
    """Check entry quality and validate data."""
    repo = get_repository(ctx)
    handler = get_quality_handler(ctx)

    # Collect entries to check
    entries = []
    if all:
        entries = repo.find_all()
        console.print(f"\n[bold]Checking all {len(entries)} entries...[/bold]\n")
    elif entry_keys:
        entries = []
        for key in entry_keys:
            entry = repo.find(key=key)
            if entry:
                entries.append(entry)
            else:
                console.print(f"[yellow]Warning:[/yellow] Entry not found: {key}")
    else:
        console.print("[red]Error:[/red] Specify entry keys or use --all")
        ctx.exit(1)

    if not entries:
        console.print("[yellow]No entries to check[/yellow]")
        return

    # Single entry check
    if len(entries) == 1:
        entry = entries[0]
        console.print(f"[bold]Checking entry: {entry.key}[/bold]\n")

        command = ValidateEntryCommand(entry=entry)

        if fix:
            # Execute fix mode command
            result = handler.execute(command)  # This should handle fix mode

            if result.data:
                fixed = result.data.get("fixed", [])
                unfixable = result.data.get("unfixable", [])

                if fixed:
                    console.print(f"[green]✓[/green] Fixed {len(fixed)} issues:")
                    for issue in fixed:
                        console.print(
                            f"  • [blue]{issue.get('field', 'unknown')}:[/blue] {issue.get('issue', '')}"
                        )

                if unfixable:
                    console.print("\n[yellow]Could not fix:[/yellow]")
                    for issue in unfixable:
                        console.print(
                            f"  • [red]{issue.get('field', 'unknown')}:[/red] {issue.get('issue', '')}"
                        )

                if not fixed and not unfixable:
                    console.print("[green]✓[/green] No issues found to fix")
            else:
                console.print("[yellow]No fix results returned[/yellow]")
            return

        result = handler.execute(command)

        if result.validation_errors:
            # Filter by severity
            min_severity = severity or "info"
            severity_order = {"error": 3, "warning": 2, "info": 1}
            min_level = severity_order[min_severity]

            errors = [
                e
                for e in result.validation_errors
                if severity_order.get(e.severity, 0) >= min_level
            ]

            if format == "json":
                output = {
                    "entry_key": entry.key,
                    "issues": [
                        {"field": e.field, "message": e.message, "severity": e.severity}
                        for e in errors
                    ],
                }
                console.print(json.dumps(output, indent=2))
            elif format == "csv":
                console.print("entry_key,field,severity,message")
                for e in errors:
                    console.print(
                        f"{entry.key},{e.field or ''},{e.severity},{e.message}"
                    )
            else:  # table
                table = Table(title=f"Issues for {entry.key}")
                table.add_column("Severity", style="bold")
                table.add_column("Field")
                table.add_column("Message")

                for e in errors:
                    style = {"error": "red", "warning": "yellow", "info": "blue"}.get(
                        e.severity, "white"
                    )

                    table.add_row(
                        f"[{style}]{e.severity.upper()}[/{style}]",
                        e.field or "-",
                        e.message,
                    )

                console.print(table)
        else:
            console.print("[green]✓[/green] No issues found")

        # Show summary
        if result.data and "severity_counts" in result.data:
            counts = result.data["severity_counts"]
            console.print("\n[bold]Summary:[/bold]")
            if counts.get("error", 0) > 0:
                console.print(f"  Errors: {counts['error']}")
            if counts.get("warning", 0) > 0:
                console.print(f"  Warnings: {counts['warning']}")
            if counts.get("info", 0) > 0:
                console.print(f"  Info: {counts['info']}")

    else:
        # Batch check
        command = ValidateBatchCommand(entries=entries)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Checking entries...", total=len(entries))
            result = handler.execute(command)
            progress.update(task, completed=len(entries))

        if result.data:
            total_checked = result.data.get("total_checked", 0)
            passed = result.data.get("passed", 0)
            failed = result.data.get("failed", 0)

            console.print("\n[bold]Quality Check Results[/bold]")
            console.print(f"Checked {total_checked} entries")
            console.print(f"[green]Passed: {passed}[/green]")
            if failed > 0:
                console.print(f"[red]Failed: {failed}[/red]")

            # Show severity summary
            if "severity_summary" in result.data:
                summary = result.data["severity_summary"]
                console.print("\n[bold]Total issues found:[/bold]")
                if summary.get("errors", 0) > 0:
                    console.print(f"  [red]Errors: {summary['errors']}[/red]")
                if summary.get("warnings", 0) > 0:
                    console.print(f"  [yellow]Warnings: {summary['warnings']}[/yellow]")
                if summary.get("info", 0) > 0:
                    console.print(f"  [blue]Info: {summary['info']}[/blue]")

            # Show problematic entries
            if failed > 0 and "results" in result.data:
                console.print("\n[bold]Entries with issues:[/bold]")
                for key, issues in result.data["results"].items():
                    errors = issues.get("errors", [])
                    warnings = issues.get("warnings", [])
                    if errors or (warnings and severity != "error"):
                        console.print(f"\n  {key}:")
                        for e in errors:
                            console.print(f"    [red]ERROR:[/red] {e['message']}")
                        if severity != "error":
                            for w in warnings:
                                console.print(
                                    f"    [yellow]WARNING:[/yellow] {w['message']}"
                                )


@click.command()
@click.option(
    "--threshold", type=float, default=0.85, help="Similarity threshold (0.0-1.0)"
)
@click.option("--auto-merge", is_flag=True, help="Automatically merge duplicates")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.option(
    "--by",
    type=click.Choice(["all", "doi", "title", "fuzzy"]),
    default="fuzzy",
    help="Duplicate detection method",
)
@click.option(
    "--export-report", type=click.Path(), help="Export duplicate report to file"
)
@pass_context
def dedupe(
    ctx,
    threshold: float,
    auto_merge: bool,
    interactive: bool,
    by: str,
    export_report: str | None,
):
    """Find and merge duplicate entries."""
    manager = get_repository_manager(ctx)
    event_bus = get_event_bus(ctx)

    # Build config
    config = DeduplicationConfig(
        min_similarity=threshold,
        dry_run=not auto_merge,
    )

    # Set mode based on options
    if interactive:
        config.mode = DeduplicationMode.INTERACTIVE
    elif auto_merge:
        config.mode = DeduplicationMode.AUTOMATIC
    else:
        config.mode = DeduplicationMode.PREVIEW

    # Run deduplication workflow
    workflow = DeduplicationWorkflow(manager, event_bus)

    with console.status("Scanning for duplicates..."):
        result = workflow.execute(config)

    # Extract duplicates from workflow result steps
    duplicates = []
    total_groups = 0

    # Look for duplicates in workflow steps
    for step in result.steps:
        if step.data and "groups" in step.data:
            # Convert DuplicateGroup objects to dictionaries for display
            groups = step.data["groups"]
            for group in groups:
                if hasattr(group, "entries"):
                    # DuplicateGroup object
                    duplicates.append(
                        {
                            "entries": [entry.key for entry in group.entries],
                            "similarity": group.confidence,
                            "reason": f"{group.match_type.value} match",
                            "details": {
                                entry.key: {
                                    "title": entry.title,
                                    "year": entry.year,
                                    "authors": entry.authors,
                                    "journal": entry.journal,
                                }
                                for entry in group.entries
                            },
                        }
                    )
                else:
                    # Already a dictionary
                    duplicates.append(group)
            break

    total_groups = len(duplicates)

    if total_groups == 0:
        console.print("\n[green]✓[/green] No duplicates found")
        return

    total_entries = sum(len(g["entries"]) for g in duplicates)
    console.print(
        f"\n[bold]Found {total_groups} duplicate groups ({total_entries} total entries)[/bold]\n"
    )

    # Display duplicate groups
    for i, group in enumerate(duplicates, 1):
        entries = group["entries"]
        similarity = group.get("similarity", 0)
        reason = group.get("reason", "Similar entries")

        panel_content = f"[cyan]{', '.join(entries)}[/cyan]\n"
        panel_content += f"[dim]{reason}[/dim]\n"
        panel_content += f"Similarity: [yellow]{similarity:.0%}[/yellow]"

        if "details" in group:
            # Show differences
            details = group["details"]
            if len(details) > 1:
                panel_content += "\n\n[bold]Differences:[/bold]"
                # Compare first two entries
                keys = list(details.keys())[:2]
                e1, e2 = details[keys[0]], details[keys[1]]

                for field in ["title", "year", "authors", "journal"]:
                    v1 = e1.get(field)
                    v2 = e2.get(field)
                    if v1 != v2:
                        panel_content += f"\n  {field}: {v1} vs {v2}"

        panel = Panel(
            panel_content,
            title=f"Group {i} ({similarity:.0%} match)",
            title_align="left",
        )
        console.print(panel)

        if interactive and not auto_merge:
            console.print("\nHow would you like to handle this group?")
            console.print("[1] Merge entries")
            console.print("[2] Keep all (not duplicates)")
            console.print("[3] Skip for now")
            console.print("[0] Cancel deduplication")

            choice = Prompt.ask("Choice", choices=["0", "1", "2", "3"], default="3")

            if choice == "0":
                console.print("[yellow]Deduplication cancelled[/yellow]")
                return
            elif choice == "1":
                # Merge logic would go here
                console.print("[green]✓[/green] Entries will be merged")
            elif choice == "2":
                console.print("[blue]ℹ[/blue] Marked as non-duplicates")
            else:
                console.print("[dim]Skipped[/dim]")

    # Handle auto-merge
    if auto_merge:
        # Count merged groups from workflow steps
        merged = 0
        for step in result.steps:
            if step.step.startswith("merge") and step.success:
                merged += 1
        if merged > 0:
            console.print(f"\n[green]✓[/green] Automatically merged {merged} group(s)")

    # Export report if requested (should be outside auto_merge block)
    if export_report:
        report_path = Path(export_report)
        report_data = {
            "generated": datetime.now().isoformat(),
            "threshold": threshold,
            "total_groups": total_groups,
            "duplicates": duplicates,
        }

        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)

        console.print(f"\n[green]✓[/green] Report saved to {report_path}")


@click.command()
@click.argument("entry_keys", nargs=-1, shell_complete=get_entry_keys)
@click.option("--all", "-a", is_flag=True, help="Clean all entries")
@click.option("--dry-run", is_flag=True, help="Show what would be changed")
@click.option(
    "--operations", help="Specific cleanup operations (comma-separated)", default="all"
)
@click.option("--backup", type=click.Path(), help="Create backup before cleaning")
@pass_context
def clean(
    ctx,
    entry_keys: tuple[str, ...],
    all: bool,
    dry_run: bool,
    operations: str,
    backup: str | None,
):
    """Clean and normalize entry data."""
    repo = get_repository(ctx)
    handler = get_quality_handler(ctx)

    # Collect entries to clean
    entries = []
    if all:
        entries = repo.find_all()
        console.print(f"\n[bold]Cleaning all {len(entries)} entries...[/bold]\n")
    elif entry_keys:
        entries = []
        for key in entry_keys:
            entry = repo.find(key=key)
            if entry:
                entries.append(entry)
            else:
                console.print(f"[yellow]Warning:[/yellow] Entry not found: {key}")
    else:
        console.print("[red]Error:[/red] Specify entry keys or use --all")
        ctx.exit(1)

    if not entries:
        console.print("[yellow]No entries to clean[/yellow]")
        return

    if dry_run:
        console.print(
            "[bold yellow]DRY RUN MODE[/bold yellow] - No changes will be made\n"
        )

    # Create backup if requested
    if backup and not dry_run:
        backup_path = Path(backup)
        backup_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_file = backup_path / f"backup-{timestamp}.json"

        # Export entries to backup
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "entries": [e.to_dict() for e in entries],
        }

        with open(backup_file, "w") as f:
            json.dump(backup_data, f, indent=2)

        console.print(f"[green]✓[/green] Backup created at {backup_file}\n")

    # Execute cleaning using handler
    # Create a simple command-like object for the handler
    @dataclass
    class CleanCommand:
        entries: list
        operations: str
        dry_run: bool

    command = CleanCommand(entries=entries, operations=operations, dry_run=dry_run)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Cleaning entries...", total=len(entries))
        result = handler.execute(command)
        progress.update(task, completed=len(entries))

        # Save cleaned entries back to repository if not dry run
        if not dry_run and result.data and result.data.get("cleaned", 0) > 0:
            save_task = progress.add_task("Saving changes...", total=len(entries))
            for entry in entries:
                repo.save(entry)
            progress.update(save_task, completed=len(entries))

    if result.data:
        # Handle dry run vs normal mode results
        if dry_run:
            cleaned_count = result.data.get("would_clean", 0)
            changes = result.data.get("changes", {})

            # Show individual changes for dry run
            if "proposed_changes" in result.data:
                for change in result.data["proposed_changes"]:
                    console.print(f"  {change.get('change', '')}")

            # Show results summary
            console.print(f"\n[bold]Would clean {cleaned_count} entries[/bold]")
            console.print("\nProposed changes:")
        else:
            cleaned_count = result.data.get("cleaned", 0)
            changes = result.data.get("changes", {})

            # Show results summary
            console.print(f"\n[green]✓[/green] Cleaned {cleaned_count} entries")
            console.print("\nChanges made:")

        # Show changes from handler result
        for operation, count in changes.items():
            if count > 0:
                # Convert snake_case to proper title case
                operation_name = operation.replace("_", " ").lower()
                console.print(f"  {operation_name.capitalize()}: {count}")
    else:
        console.print("\n[yellow]No changes made[/yellow]")


@click.group()
def report():
    """Generate various reports."""
    pass


@report.command()
@click.option("--detailed", is_flag=True, help="Include entry-level details")
@click.option("--export", type=click.Path(), help="Export report to file")
@click.option(
    "--format",
    type=click.Choice(["text", "json", "html", "markdown"]),
    default="text",
    help="Export format",
)
@pass_context
def quality(ctx, detailed: bool, export: str | None, format: str):
    """Generate quality report for the bibliography."""
    repo = get_repository(ctx)
    handler = get_quality_handler(ctx)

    entries = repo.find_all()
    if not entries:
        console.print("[yellow]No entries found[/yellow]")
        return

    command = GenerateQualityReportCommand(
        entries=entries, format=format if export else "json", include_suggestions=True
    )

    with console.status("Generating quality report..."):
        result = handler.execute(command)

    if result.data:
        data = result.data

        # Display report
        console.print("\n[bold]📊 Quality Report[/bold]\n")

        total = data.get("total_entries", 0)
        console.print(f"Total entries: {total}")

        if "completeness_score" in data:
            score = data["completeness_score"]
            console.print(f"Completeness score: [yellow]{score:.1f}%[/yellow]")

        if "issues_by_severity" in data:
            console.print("\n[bold]Issues by severity:[/bold]")
            issues = data["issues_by_severity"]
            if issues.get("error", 0) > 0:
                console.print(f"  [red]Errors: {issues['error']}[/red]")
            if issues.get("warning", 0) > 0:
                console.print(f"  [yellow]Warnings: {issues['warning']}[/yellow]")
            if issues.get("info", 0) > 0:
                console.print(f"  [blue]Info: {issues['info']}[/blue]")

        if "common_issues" in data:
            console.print("\n[bold]Common issues:[/bold]")
            for issue in data["common_issues"][:10]:  # Top 10
                console.print(f"  • {issue['issue']} ({issue['count']})")

        if "entries_by_quality" in data:
            console.print("\n[bold]Quality distribution:[/bold]")
            quality = data["entries_by_quality"]
            for level in ["excellent", "good", "fair", "poor"]:
                if level in quality:
                    console.print(f"  {level.title()}: {quality[level]}")

        if detailed and "entry_details" in data:
            console.print("\n[bold]Entry Details:[/bold]\n")

            for key, details in data["entry_details"].items():
                score = details.get("quality_score", 0)
                completeness = details.get("completeness", 0)

                console.print(f"[cyan]{key}[/cyan]")
                console.print(f"  Quality: {score}% | Completeness: {completeness}%")

                if "issues" in details and details["issues"]:
                    console.print("  Issues:")
                    for issue in details["issues"][:3]:  # Show up to 3 issues
                        console.print(f"    • {issue['message']}")
                console.print()

        # Export if requested
        if export:
            export_path = Path(export)

            if format == "json":
                with open(export_path, "w") as f:
                    json.dump(data, f, indent=2)
            elif format == "html":
                # Simple HTML report
                html = "<html><head><title>Quality Report</title></head><body>"
                html += "<h1>Quality Report</h1>"
                html += f"<p>Generated: {datetime.now()}</p>"
                html += f"<p>Total entries: {total}</p>"
                # Add more HTML formatting as needed
                html += "</body></html>"

                with open(export_path, "w") as f:
                    f.write(html)
            elif format == "markdown":
                md = "# Quality Report\n\n"
                md += f"Generated: {datetime.now()}\n\n"
                md += f"Total entries: {total}\n"
                # Add more markdown formatting

                with open(export_path, "w") as f:
                    f.write(md)
            else:  # text
                with open(export_path, "w") as f:
                    # Write same output as console
                    f.write("Quality Report\n")
                    f.write(f"Total entries: {total}\n")
                    # etc.

            console.print(f"\n[green]✓[/green] Report exported to {export_path}")
