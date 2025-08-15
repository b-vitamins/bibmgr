"""Handlers for quality check operations."""

import json
from datetime import datetime
from typing import Any

from ..core.models import Entry, ValidationError
from ..core.validators import ValidatorRegistry
from .results import OperationResult, ResultStatus


class QualityHandler:
    """Handler for quality check operations."""

    def __init__(self):
        """Initialize quality handler."""
        self.validator_registry = ValidatorRegistry()

    def execute(self, command: Any) -> OperationResult:
        """Execute a quality command.

        Args:
            command: Command to execute

        Returns:
            Operation result
        """
        command_type = type(command).__name__

        if command_type == "ValidateEntryCommand":
            return self._handle_validate_entry(command)
        elif command_type == "ValidateBatchCommand":
            return self._handle_validate_batch(command)
        elif command_type == "CheckConsistencyCommand":
            return self._handle_check_consistency(command)
        elif command_type == "GenerateQualityReportCommand":
            return self._handle_generate_report(command)
        elif command_type == "CleanCommand":
            return self._handle_clean_command(command)
        else:
            return OperationResult(
                status=ResultStatus.ERROR, message=f"Unknown command: {command_type}"
            )

    def _handle_validate_entry(self, command) -> OperationResult:
        """Handle validate entry command."""
        entry = command.entry

        # Validate entry
        issues = self.validator_registry.validate(entry)

        # Count errors and warnings
        error_count = sum(1 for issue in issues if issue.severity == "error")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        info_count = sum(1 for issue in issues if issue.severity == "info")

        if error_count > 0:
            return OperationResult(
                status=ResultStatus.VALIDATION_FAILED,
                message=f"Entry '{entry.key}' has {error_count} validation errors",
                entity_id=entry.key,
                data={
                    "issues": issues,
                    "error_count": error_count,
                    "warning_count": warning_count,
                    "info_count": info_count,
                },
                validation_errors=issues,
            )
        elif warning_count > 0:
            return OperationResult(
                status=ResultStatus.SUCCESS,
                message=f"Entry '{entry.key}' is valid with {warning_count} warnings",
                entity_id=entry.key,
                data={
                    "issues": issues,
                    "error_count": 0,
                    "warning_count": warning_count,
                    "info_count": info_count,
                },
                warnings=[
                    issue.message for issue in issues if issue.severity == "warning"
                ],
            )
        else:
            return OperationResult(
                status=ResultStatus.SUCCESS,
                message=f"Entry '{entry.key}' is valid",
                entity_id=entry.key,
                data={
                    "issues": [],
                    "error_count": 0,
                    "warning_count": 0,
                    "info_count": info_count,
                },
            )

    def _handle_validate_batch(self, command) -> OperationResult:
        """Handle validate batch command."""
        entries = command.entries
        stop_on_error = command.stop_on_error

        if not entries:
            return OperationResult(
                status=ResultStatus.SUCCESS,
                message="No entries to validate",
                data={
                    "total_entries": 0,
                    "valid_entries": 0,
                    "entries_with_errors": 0,
                    "entries_with_warnings": 0,
                    "all_issues": [],
                },
            )

        total_entries = len(entries)
        valid_entries = 0
        entries_with_errors = 0
        entries_with_warnings = 0
        all_issues = []

        for entry in entries:
            issues = self.validator_registry.validate(entry)

            if issues:
                all_issues.extend(issues)

                error_count = sum(1 for issue in issues if issue.severity == "error")
                warning_count = sum(
                    1 for issue in issues if issue.severity == "warning"
                )

                if error_count > 0:
                    entries_with_errors += 1

                    if stop_on_error:
                        return OperationResult(
                            status=ResultStatus.VALIDATION_FAILED,
                            message=f"Validation stopped at entry '{entry.key}' due to errors",
                            data={
                                "total_entries": total_entries,
                                "valid_entries": valid_entries,
                                "entries_with_errors": entries_with_errors + 1,
                                "entries_with_warnings": entries_with_warnings,
                                "all_issues": all_issues,
                                "stopped_at": entry.key,
                            },
                        )
                elif warning_count > 0:
                    entries_with_warnings += 1
                    valid_entries += 1
                else:
                    valid_entries += 1
            else:
                valid_entries += 1

        return OperationResult(
            status=ResultStatus.SUCCESS,
            message=f"Validated {total_entries} entries: {valid_entries} valid, {entries_with_errors} with errors",
            data={
                "total_entries": total_entries,
                "valid_entries": valid_entries,
                "entries_with_errors": entries_with_errors,
                "entries_with_warnings": entries_with_warnings,
                "all_issues": all_issues,
            },
        )

    def _handle_check_consistency(self, command) -> OperationResult:
        """Handle check consistency command."""
        entries = command.entries
        check_duplicates = command.check_duplicates
        check_crossrefs = command.check_crossrefs

        duplicates = []
        missing_crossrefs = []
        has_issues = False

        if check_duplicates:
            # Find potential duplicates
            duplicates = self._find_duplicates(entries)
            if duplicates:
                has_issues = True

        if check_crossrefs:
            # Check cross-references
            missing_crossrefs = self._check_crossrefs(entries)
            if missing_crossrefs:
                has_issues = True

        return OperationResult(
            status=ResultStatus.SUCCESS,
            message="Consistency check completed",
            data={
                "duplicates": duplicates,
                "duplicate_count": len(duplicates),
                "missing_crossrefs": missing_crossrefs,
                "missing_crossref_count": len(missing_crossrefs),
                "has_issues": has_issues,
            },
        )

    def _find_duplicates(self, entries: list[Entry]) -> list[dict[str, Any]]:
        """Find potential duplicate entries."""
        duplicates = []

        # Group by title and author
        title_author_map: dict[tuple[str, str], list[Entry]] = {}

        for entry in entries:
            if entry.title and entry.author:
                key = (entry.title.lower().strip(), entry.author.lower().strip())
                if key not in title_author_map:
                    title_author_map[key] = []
                title_author_map[key].append(entry)

        # Find groups with multiple entries
        for (title, author), group in title_author_map.items():
            if len(group) > 1:
                duplicates.append(
                    {
                        "title": title,
                        "author": author,
                        "entries": [e.key for e in group],
                        "count": len(group),
                    }
                )

        return duplicates

    def _check_crossrefs(self, entries: list[Entry]) -> list[dict[str, Any]]:
        """Check cross-references."""
        missing = []

        # Build set of available keys
        available_keys = {entry.key for entry in entries}

        # Check each entry's crossref
        for entry in entries:
            if hasattr(entry, "crossref") and entry.crossref:
                if entry.crossref not in available_keys:
                    missing.append(
                        {
                            "entry_key": entry.key,
                            "missing_crossref": entry.crossref,
                        }
                    )

        return missing

    def _handle_generate_report(self, command) -> OperationResult:
        """Handle generate quality report command."""
        entries = command.entries
        format = command.format
        include_consistency = command.include_consistency
        include_suggestions = command.include_suggestions

        # Validate format
        supported_formats = ["json", "markdown", "html"]
        if format not in supported_formats:
            return OperationResult(
                status=ResultStatus.ERROR,
                message=f"Unknown report format: {format}",
                errors=[f"Supported formats: {', '.join(supported_formats)}"],
            )

        # Generate metrics
        metrics = self._calculate_metrics(entries)

        # Validate all entries
        validation_results = []
        all_suggestions = []

        for entry in entries:
            issues = self.validator_registry.validate(entry)
            validation_results.append(
                {
                    "entry_key": entry.key,
                    "issues": issues,
                    "error_count": sum(1 for i in issues if i.severity == "error"),
                    "warning_count": sum(1 for i in issues if i.severity == "warning"),
                }
            )

            # Extract suggestions from info-level issues
            if include_suggestions:
                for issue in issues:
                    if issue.severity == "info":
                        all_suggestions.append(
                            {
                                "entry_key": entry.key,
                                "field": issue.field,
                                "suggestion": issue.message,
                            }
                        )

        # Generate consistency report if requested
        consistency_report = None
        if include_consistency:
            consistency_result = self._handle_check_consistency(
                type(
                    "Command",
                    (),
                    {
                        "entries": entries,
                        "check_duplicates": True,
                        "check_crossrefs": True,
                    },
                )()
            )
            consistency_report = consistency_result.data

        # Build report
        report = {
            "generated_at": datetime.now().isoformat(),
            "metrics": metrics,
            "validation_results": validation_results,
        }

        if consistency_report:
            report["consistency_report"] = consistency_report

        if include_suggestions:
            report["suggestions"] = all_suggestions

        # Format report
        if format == "json":
            formatted = json.dumps(report, indent=2, default=str)
        elif format == "markdown":
            formatted = self._format_report_markdown(report)
        else:  # html
            formatted = self._format_report_html(report)

        return OperationResult(
            status=ResultStatus.SUCCESS,
            message=f"Quality report generated in {format} format",
            data={
                "report": report,
                "formatted": formatted,
            },
        )

    def _calculate_metrics(self, entries: list[Entry]) -> dict[str, Any]:
        """Calculate quality metrics for entries."""
        total_entries = len(entries)

        if total_entries == 0:
            return {
                "total_entries": 0,
                "valid_entries": 0,
                "entries_with_errors": 0,
                "entries_with_warnings": 0,
                "quality_score": 100.0,
            }

        valid_entries = 0
        entries_with_errors = 0
        entries_with_warnings = 0

        for entry in entries:
            issues = self.validator_registry.validate(entry)
            error_count = sum(1 for i in issues if i.severity == "error")
            warning_count = sum(1 for i in issues if i.severity == "warning")

            if error_count > 0:
                entries_with_errors += 1
            elif warning_count > 0:
                entries_with_warnings += 1
                valid_entries += 1
            else:
                valid_entries += 1

        # Calculate quality score (0-100)
        quality_score = (valid_entries / total_entries) * 100.0

        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "entries_with_errors": entries_with_errors,
            "entries_with_warnings": entries_with_warnings,
            "quality_score": round(quality_score, 2),
        }

    def _format_report_markdown(self, report: dict[str, Any]) -> str:
        """Format report as Markdown."""
        lines = []

        lines.append("# Quality Report")
        lines.append("")
        lines.append(f"Generated at: {report['generated_at']}")
        lines.append("")

        # Metrics
        metrics = report["metrics"]
        lines.append("## Metrics")
        lines.append("")
        lines.append(f"- Total entries: {metrics['total_entries']}")
        lines.append(f"- Valid entries: {metrics['valid_entries']}")
        lines.append(f"- Entries with errors: {metrics['entries_with_errors']}")
        lines.append(f"- Entries with warnings: {metrics['entries_with_warnings']}")
        lines.append(f"- Quality score: {metrics['quality_score']}%")
        lines.append("")

        # Validation results
        if report["validation_results"]:
            lines.append("## Validation Results")
            lines.append("")

            for result in report["validation_results"]:
                if result["error_count"] > 0 or result["warning_count"] > 0:
                    lines.append(f"### {result['entry_key']}")
                    lines.append(f"- Errors: {result['error_count']}")
                    lines.append(f"- Warnings: {result['warning_count']}")
                    lines.append("")

        # Consistency
        if "consistency_report" in report:
            consistency = report["consistency_report"]
            lines.append("## Consistency Report")
            lines.append("")

            if consistency["duplicate_count"] > 0:
                lines.append(
                    f"Found {consistency['duplicate_count']} potential duplicates"
                )
                lines.append("")

            if consistency["missing_crossref_count"] > 0:
                lines.append(
                    f"Found {consistency['missing_crossref_count']} missing cross-references"
                )
                lines.append("")

        # Suggestions
        if "suggestions" in report and report["suggestions"]:
            lines.append("## Suggestions")
            lines.append("")

            for suggestion in report["suggestions"]:
                lines.append(f"- {suggestion['entry_key']}: {suggestion['suggestion']}")
            lines.append("")

        return "\n".join(lines)

    def _format_report_html(self, report: dict[str, Any]) -> str:
        """Format report as HTML."""
        # Simple HTML formatting
        html = f"""
        <html>
        <head>
            <title>Quality Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2, h3 {{ color: #333; }}
                .metric {{ margin: 10px 0; }}
                .error {{ color: red; }}
                .warning {{ color: orange; }}
                .success {{ color: green; }}
            </style>
        </head>
        <body>
            <h1>Quality Report</h1>
            <p>Generated at: {report["generated_at"]}</p>

            <h2>Metrics</h2>
            <div class="metric">Total entries: {report["metrics"]["total_entries"]}</div>
            <div class="metric">Valid entries: {report["metrics"]["valid_entries"]}</div>
            <div class="metric error">Entries with errors: {report["metrics"]["entries_with_errors"]}</div>
            <div class="metric warning">Entries with warnings: {report["metrics"]["entries_with_warnings"]}</div>
            <div class="metric">Quality score: {report["metrics"]["quality_score"]}%</div>
        </body>
        </html>
        """

        return html.strip()

    def _handle_clean_command(self, command) -> OperationResult:
        """Handle clean command."""
        entries = command.entries
        dry_run = command.dry_run

        if not entries:
            return OperationResult(
                status=ResultStatus.SUCCESS,
                message="No entries to clean",
                data={"cleaned": 0, "changes": {}},
            )

        cleaned_count = 0
        changes = {
            "whitespace_cleaned": 0,
            "title_capitalized": 0,
            "pages_formatted": 0,
            "author_formatted": 0,
        }
        proposed_changes = []

        for i, entry in enumerate(entries):
            entry_changes = []
            modified = False
            new_data = entry.to_dict()

            # Clean title whitespace and capitalize
            if hasattr(entry, "title") and entry.title:
                original_title = entry.title
                # Clean whitespace
                cleaned_title = " ".join(original_title.split())
                # Capitalize first letter if not already
                if cleaned_title and cleaned_title[0].islower():
                    cleaned_title = cleaned_title[0].upper() + cleaned_title[1:]

                if cleaned_title != original_title:
                    if not dry_run:
                        new_data["title"] = cleaned_title
                    entry_changes.append(
                        f"Title: '{original_title}' → '{cleaned_title}'"
                    )
                    changes["whitespace_cleaned"] += 1
                    if cleaned_title != " ".join(original_title.split()):
                        changes["title_capitalized"] += 1
                    modified = True

            # Format pages (change - to --)
            if hasattr(entry, "pages") and entry.pages:
                original_pages = entry.pages
                # Replace single dash with double dash for page ranges
                import re

                cleaned_pages = re.sub(r"(\d+)-(\d+)", r"\1--\2", original_pages)

                if cleaned_pages != original_pages:
                    if not dry_run:
                        new_data["pages"] = cleaned_pages
                    entry_changes.append(
                        f"Pages: '{original_pages}' → '{cleaned_pages}'"
                    )
                    changes["pages_formatted"] += 1
                    modified = True

            # Format author names (basic cleaning)
            if hasattr(entry, "author") and entry.author:
                original_author = entry.author
                # Clean whitespace
                cleaned_author = " ".join(original_author.split())

                if cleaned_author != original_author:
                    if not dry_run:
                        new_data["author"] = cleaned_author
                    entry_changes.append(
                        f"Author: '{original_author}' → '{cleaned_author}'"
                    )
                    changes["author_formatted"] += 1
                    modified = True

            if modified:
                cleaned_count += 1
                if dry_run:
                    proposed_changes.extend(
                        [f"{entry.key}: {change}" for change in entry_changes]
                    )
                else:
                    # Create new entry with cleaned data and replace in list
                    from ..core.models import Entry

                    entries[i] = Entry.from_dict(new_data)

        if dry_run:
            return OperationResult(
                status=ResultStatus.SUCCESS,
                message=f"Would clean {cleaned_count} entries",
                data={
                    "would_clean": cleaned_count,
                    "changes": changes,
                    "proposed_changes": proposed_changes,
                },
            )
        else:
            return OperationResult(
                status=ResultStatus.SUCCESS,
                message=f"Cleaned {cleaned_count} entries",
                data={"cleaned": cleaned_count, "changes": changes},
            )


# Create aliases for consistency
ValidationResult = ValidationError
ValidationSeverity = None  # We use string severity in ValidationError
