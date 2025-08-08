"""Report generation in multiple formats.

Supports:
- JSON for machine processing
- HTML for web viewing
- Markdown for documentation
- CSV for spreadsheet analysis
"""

from __future__ import annotations

import csv
import html
import io
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from bibmgr.quality.engine import QualityReport
from bibmgr.quality.validators import ValidationSeverity


class ReportFormatter(ABC):
    """Abstract base class for report formatters."""

    @abstractmethod
    def format(self, report: QualityReport) -> str:
        """Format a quality report.

        Args:
            report: Quality report to format

        Returns:
            Formatted report as string
        """
        pass

    def save(self, report: QualityReport, path: Path) -> None:
        """Save formatted report to file.

        Args:
            report: Quality report to save
            path: Output file path
        """
        content = self.format(report)
        path.write_text(content, encoding="utf-8")


class JSONReporter(ReportFormatter):
    """Generate JSON reports."""

    def __init__(self, indent: int = 2, include_metadata: bool = True):
        """Initialize JSON reporter.

        Args:
            indent: Indentation level for pretty printing
            include_metadata: Whether to include extra metadata
        """
        self.indent = indent
        self.include_metadata = include_metadata

    def format(self, report: QualityReport) -> str:
        """Format report as JSON."""
        data = {
            "timestamp": report.timestamp.isoformat(),
            "metrics": {
                "total_entries": report.metrics.total_entries,
                "valid_entries": report.metrics.valid_entries,
                "entries_with_errors": report.metrics.entries_with_errors,
                "entries_with_warnings": report.metrics.entries_with_warnings,
                "quality_score": report.metrics.quality_score,
                "field_completeness": report.metrics.field_completeness,
                "common_issues": report.metrics.common_issues,
            },
            "has_errors": report.has_errors,
        }

        # Add validation results
        if report.validation_results:
            data["validation_results"] = {}
            for entry_key, results in report.validation_results.items():
                issues = []
                for r in results:
                    if not r.is_valid or r.severity != ValidationSeverity.INFO:
                        issue = {
                            "field": r.field,
                            "severity": r.severity.name,
                            "message": r.message,
                            "is_valid": r.is_valid,
                        }
                        if r.suggestion:
                            issue["suggestion"] = r.suggestion
                        if self.include_metadata and r.metadata:
                            issue["metadata"] = r.metadata
                        issues.append(issue)

                if issues:
                    data["validation_results"][entry_key] = issues

        # Add consistency report
        if report.consistency_report:
            consistency_data: dict[str, Any] = {
                "total_entries": report.consistency_report.total_entries,
                "issue_count": len(report.consistency_report.issues),
                "orphaned_count": len(report.consistency_report.orphaned_entries),
                "duplicate_groups": len(report.consistency_report.duplicate_groups),
                "broken_references": len(report.consistency_report.broken_references),
                "citation_loops": len(report.consistency_report.citation_loops),
            }

            if self.include_metadata:
                consistency_data["orphaned_entries"] = (
                    report.consistency_report.orphaned_entries
                )
                consistency_data["duplicate_groups"] = (
                    report.consistency_report.duplicate_groups
                )

            data["consistency"] = consistency_data

        # Add integrity report
        if report.integrity_report:
            data["integrity"] = {
                "total_files": report.integrity_report.total_files,
                "valid_files": report.integrity_report.valid_files,
                "integrity_score": report.integrity_report.integrity_score,
                "missing_files": len(report.integrity_report.missing_files),
                "corrupted_files": len(report.integrity_report.corrupted_files),
                "permission_issues": len(report.integrity_report.permission_issues),
            }

        # Add cache stats
        if report.cache_stats:
            data["cache_stats"] = report.cache_stats

        return json.dumps(data, indent=self.indent, ensure_ascii=False)


class HTMLReporter(ReportFormatter):
    """Generate HTML reports."""

    def __init__(self, include_css: bool = True, theme: str = "light"):
        """Initialize HTML reporter.

        Args:
            include_css: Whether to include inline CSS
            theme: Color theme (light or dark)
        """
        self.include_css = include_css
        self.theme = theme

    def format(self, report: QualityReport) -> str:
        """Format report as HTML."""
        parts = ["<!DOCTYPE html>\n<html>\n<head>"]
        parts.append('<meta charset="UTF-8">')
        parts.append("<title>Quality Report</title>")

        if self.include_css:
            parts.append(self._get_css())

        parts.append("</head>\n<body>")
        parts.append('<div class="container">')

        # Header
        parts.append("<h1>Quality Report</h1>")
        parts.append(
            f'<p class="timestamp">Generated: {report.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</p>'
        )

        # Overall status
        status_class = "success" if not report.has_errors else "error"
        status_text = "✓ No Errors" if not report.has_errors else "✗ Has Errors"
        parts.append(f'<div class="status {status_class}">{status_text}</div>')

        # Metrics section
        parts.append('<section class="metrics">')
        parts.append("<h2>Metrics</h2>")
        parts.append('<div class="metrics-grid">')

        # Key metrics
        metrics = [
            ("Total Entries", report.metrics.total_entries),
            ("Valid Entries", report.metrics.valid_entries),
            ("Quality Score", f"{report.metrics.quality_score:.1f}%"),
            ("Entries with Errors", report.metrics.entries_with_errors),
            ("Entries with Warnings", report.metrics.entries_with_warnings),
        ]

        for label, value in metrics:
            parts.append(
                f'<div class="metric"><span class="label">{label}:</span> '
                f'<span class="value">{value}</span></div>'
            )

        parts.append("</div>")  # metrics-grid

        # Field completeness
        if report.metrics.field_completeness:
            parts.append("<h3>Field Completeness</h3>")
            parts.append('<div class="progress-bars">')

            for field, pct in sorted(
                report.metrics.field_completeness.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                color = self._get_progress_color(pct)
                parts.append('<div class="progress-item">')
                parts.append(f'<span class="field-name">{field}:</span>')
                parts.append('<div class="progress-bar">')
                parts.append(
                    f'<div class="progress-fill" style="width: {pct:.1f}%; '
                    f'background-color: {color};"></div>'
                )
                parts.append("</div>")
                parts.append(f'<span class="percentage">{pct:.1f}%</span>')
                parts.append("</div>")

            parts.append("</div>")  # progress-bars

        parts.append("</section>")  # metrics

        # Issues section
        if report.validation_results:
            parts.append('<section class="issues">')
            parts.append("<h2>Validation Issues</h2>")

            # Group by severity
            by_severity = self._group_by_severity(report.validation_results)

            for severity in ["ERROR", "WARNING", "SUGGESTION", "INFO"]:
                if severity in by_severity:
                    count = len(by_severity[severity])
                    severity_class = severity.lower()
                    parts.append(f'<div class="severity-group {severity_class}">')
                    parts.append(f"<h3>{severity} ({count})</h3>")
                    parts.append("<ul>")

                    for entry_key, results in by_severity[severity][
                        :10
                    ]:  # Show first 10
                        for r in results:
                            msg = html.escape(r.message)
                            if r.suggestion:
                                msg += f" <em>({html.escape(r.suggestion)})</em>"
                            parts.append(
                                f"<li><strong>{html.escape(entry_key)}</strong> - "
                                f"{html.escape(r.field)}: {msg}</li>"
                            )

                    if count > 10:
                        parts.append(f"<li><em>... and {count - 10} more</em></li>")

                    parts.append("</ul>")
                    parts.append("</div>")

            parts.append("</section>")  # issues

        # Consistency section
        if report.consistency_report:
            parts.append('<section class="consistency">')
            parts.append("<h2>Consistency Check</h2>")

            consistency_items = [
                ("Orphaned Entries", len(report.consistency_report.orphaned_entries)),
                ("Duplicate Groups", len(report.consistency_report.duplicate_groups)),
                ("Broken References", len(report.consistency_report.broken_references)),
                ("Citation Loops", len(report.consistency_report.citation_loops)),
            ]

            parts.append("<ul>")
            for label, count in consistency_items:
                if count > 0:
                    parts.append(f"<li>{label}: {count}</li>")
            parts.append("</ul>")

            parts.append("</section>")

        # Integrity section
        if report.integrity_report:
            parts.append('<section class="integrity">')
            parts.append("<h2>File Integrity</h2>")
            parts.append(
                f"<p>Integrity Score: {report.integrity_report.integrity_score:.1f}%</p>"
            )

            integrity_items = [
                ("Missing Files", len(report.integrity_report.missing_files)),
                ("Corrupted Files", len(report.integrity_report.corrupted_files)),
                ("Permission Issues", len(report.integrity_report.permission_issues)),
            ]

            parts.append("<ul>")
            for label, count in integrity_items:
                if count > 0:
                    parts.append(f"<li>{label}: {count}</li>")
            parts.append("</ul>")

            parts.append("</section>")

        parts.append("</div>")  # container
        parts.append("</body>\n</html>")

        return "\n".join(parts)

    def _get_css(self) -> str:
        """Get CSS styles."""
        if self.theme == "dark":
            bg_color = "#1a1a1a"
            text_color = "#e0e0e0"
            border_color = "#333"
            success_color = "#4caf50"
            error_color = "#f44336"
            warning_color = "#ff9800"
        else:
            bg_color = "#ffffff"
            text_color = "#333333"
            border_color = "#ddd"
            success_color = "#4caf50"
            error_color = "#f44336"
            warning_color = "#ff9800"

        return f"""<style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background-color: {bg_color};
                color: {text_color};
                line-height: 1.6;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1, h2, h3 {{
                color: {text_color};
            }}
            .timestamp {{
                color: #666;
                font-style: italic;
            }}
            .status {{
                padding: 10px;
                border-radius: 5px;
                margin: 20px 0;
                font-weight: bold;
            }}
            .status.success {{
                background-color: {success_color}22;
                border: 1px solid {success_color};
                color: {success_color};
            }}
            .status.error {{
                background-color: {error_color}22;
                border: 1px solid {error_color};
                color: {error_color};
            }}
            .metrics-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }}
            .metric {{
                padding: 10px;
                background-color: {border_color}22;
                border-radius: 5px;
            }}
            .metric .label {{
                font-weight: bold;
            }}
            .metric .value {{
                color: #2196f3;
            }}
            .progress-item {{
                display: flex;
                align-items: center;
                margin: 10px 0;
                gap: 10px;
            }}
            .field-name {{
                min-width: 100px;
            }}
            .progress-bar {{
                flex: 1;
                height: 20px;
                background-color: {border_color};
                border-radius: 10px;
                overflow: hidden;
            }}
            .progress-fill {{
                height: 100%;
                transition: width 0.3s ease;
            }}
            .percentage {{
                min-width: 50px;
                text-align: right;
            }}
            .severity-group {{
                margin: 20px 0;
                padding: 15px;
                border-radius: 5px;
            }}
            .severity-group.error {{
                background-color: {error_color}11;
                border-left: 4px solid {error_color};
            }}
            .severity-group.warning {{
                background-color: {warning_color}11;
                border-left: 4px solid {warning_color};
            }}
            .severity-group.suggestion {{
                background-color: #2196f311;
                border-left: 4px solid #2196f3;
            }}
            .severity-group.info {{
                background-color: {border_color}22;
                border-left: 4px solid {border_color};
            }}
            section {{
                margin: 30px 0;
                padding: 20px;
                border: 1px solid {border_color};
                border-radius: 5px;
            }}
            ul {{
                margin: 10px 0;
                padding-left: 20px;
            }}
            li {{
                margin: 5px 0;
            }}
            em {{
                color: #666;
            }}
        </style>"""

    def _get_progress_color(self, percentage: float) -> str:
        """Get color for progress bar based on percentage."""
        if percentage >= 80:
            return "#4caf50"  # Green
        elif percentage >= 60:
            return "#8bc34a"  # Light green
        elif percentage >= 40:
            return "#ff9800"  # Orange
        else:
            return "#f44336"  # Red

    def _group_by_severity(
        self, validation_results: dict[str, list[Any]]
    ) -> dict[str, list[tuple]]:
        """Group validation results by severity."""
        by_severity = {}

        for entry_key, results in validation_results.items():
            for r in results:
                if not r.is_valid or r.severity != ValidationSeverity.INFO:
                    severity = r.severity.name
                    if severity not in by_severity:
                        by_severity[severity] = []
                    by_severity[severity].append((entry_key, [r]))

        return by_severity


class MarkdownReporter(ReportFormatter):
    """Generate Markdown reports."""

    def format(self, report: QualityReport) -> str:
        """Format report as Markdown."""
        lines = []

        # Header
        lines.append("# Quality Report")
        lines.append("")
        lines.append(f"**Generated:** {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Status
        if report.has_errors:
            lines.append("❌ **Status:** Has Errors")
        else:
            lines.append("✅ **Status:** No Errors")
        lines.append("")

        # Metrics
        lines.append("## Metrics")
        lines.append("")
        lines.append(f"- **Total Entries:** {report.metrics.total_entries}")
        lines.append(f"- **Valid Entries:** {report.metrics.valid_entries}")
        lines.append(f"- **Quality Score:** {report.metrics.quality_score:.1f}%")
        lines.append(f"- **Entries with Errors:** {report.metrics.entries_with_errors}")
        lines.append(
            f"- **Entries with Warnings:** {report.metrics.entries_with_warnings}"
        )
        lines.append("")

        # Field completeness table
        if report.metrics.field_completeness:
            lines.append("### Field Completeness")
            lines.append("")
            lines.append("| Field | Completeness |")
            lines.append("|-------|-------------|")

            for field, pct in sorted(
                report.metrics.field_completeness.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                bar = self._make_progress_bar(pct)
                lines.append(f"| {field} | {bar} {pct:.1f}% |")
            lines.append("")

        # Common issues
        if report.metrics.common_issues:
            lines.append("### Most Common Issues")
            lines.append("")

            sorted_issues = sorted(
                report.metrics.common_issues.items(), key=lambda x: x[1], reverse=True
            )[:10]

            for issue, count in sorted_issues:
                lines.append(f"- {issue}: {count}")
            lines.append("")

        # Validation issues
        if report.validation_results:
            lines.append("## Validation Issues")
            lines.append("")

            # Count by severity
            severity_counts = {}
            for results in report.validation_results.values():
                for r in results:
                    if not r.is_valid:
                        severity = r.severity.name
                        severity_counts[severity] = severity_counts.get(severity, 0) + 1

            if severity_counts:
                lines.append("### Summary by Severity")
                lines.append("")
                for severity in ["ERROR", "WARNING", "SUGGESTION", "INFO"]:
                    if severity in severity_counts:
                        lines.append(f"- **{severity}:** {severity_counts[severity]}")
                lines.append("")

            # Sample issues
            lines.append("### Sample Issues")
            lines.append("")

            shown = 0
            for entry_key, results in list(report.validation_results.items())[:5]:
                for r in results:
                    if not r.is_valid:
                        lines.append(f"- **{entry_key}** - {r.field}: {r.message}")
                        if r.suggestion:
                            lines.append(f"  - *Suggestion:* {r.suggestion}")
                        shown += 1
                        if shown >= 10:
                            break
                if shown >= 10:
                    break

            if len(report.validation_results) > 5:
                lines.append(
                    f"- *... and more issues in {len(report.validation_results)} entries*"
                )
            lines.append("")

        # Consistency report
        if report.consistency_report:
            lines.append("## Consistency Check")
            lines.append("")

            if report.consistency_report.orphaned_entries:
                lines.append(
                    f"- **Orphaned Entries:** {len(report.consistency_report.orphaned_entries)}"
                )
            if report.consistency_report.duplicate_groups:
                lines.append(
                    f"- **Duplicate Groups:** {len(report.consistency_report.duplicate_groups)}"
                )
            if report.consistency_report.broken_references:
                lines.append(
                    f"- **Broken References:** {len(report.consistency_report.broken_references)}"
                )
            if report.consistency_report.citation_loops:
                lines.append(
                    f"- **Citation Loops:** {len(report.consistency_report.citation_loops)}"
                )
            lines.append("")

        # Integrity report
        if report.integrity_report:
            lines.append("## File Integrity")
            lines.append("")
            lines.append(
                f"**Integrity Score:** {report.integrity_report.integrity_score:.1f}%"
            )
            lines.append("")
            lines.append(f"- Total Files: {report.integrity_report.total_files}")
            lines.append(f"- Valid Files: {report.integrity_report.valid_files}")

            if report.integrity_report.missing_files:
                lines.append(
                    f"- Missing Files: {len(report.integrity_report.missing_files)}"
                )
            if report.integrity_report.corrupted_files:
                lines.append(
                    f"- Corrupted Files: {len(report.integrity_report.corrupted_files)}"
                )
            if report.integrity_report.permission_issues:
                lines.append(
                    f"- Permission Issues: {len(report.integrity_report.permission_issues)}"
                )
            lines.append("")

        # Cache stats
        if report.cache_stats:
            lines.append("## Cache Statistics")
            lines.append("")
            lines.append(f"- **Hit Rate:** {report.cache_stats['hit_rate']:.1%}")
            lines.append(f"- **Cached Entries:** {report.cache_stats['size']}")
            lines.append(f"- **Hits:** {report.cache_stats['hits']}")
            lines.append(f"- **Misses:** {report.cache_stats['misses']}")
            lines.append("")

        return "\n".join(lines)

    def _make_progress_bar(self, percentage: float, width: int = 10) -> str:
        """Create a text progress bar."""
        filled = int(percentage / 100 * width)
        empty = width - filled
        return "█" * filled + "░" * empty


class CSVReporter(ReportFormatter):
    """Generate CSV reports."""

    def format(self, report: QualityReport) -> str:
        """Format report as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            ["entry_key", "field", "severity", "is_valid", "message", "suggestion"]
        )

        # Data rows
        for entry_key, results in report.validation_results.items():
            for r in results:
                if not r.is_valid or r.severity != ValidationSeverity.INFO:
                    writer.writerow(
                        [
                            entry_key,
                            r.field,
                            r.severity.name,
                            r.is_valid,
                            r.message,
                            r.suggestion or "",
                        ]
                    )

        # Add summary rows
        writer.writerow([])  # Empty row
        writer.writerow(["SUMMARY", "", "", "", "", ""])
        writer.writerow(
            ["Total Entries", str(report.metrics.total_entries), "", "", "", ""]
        )
        writer.writerow(
            ["Valid Entries", str(report.metrics.valid_entries), "", "", "", ""]
        )
        writer.writerow(
            ["Quality Score", f"{report.metrics.quality_score:.1f}%", "", "", "", ""]
        )
        writer.writerow(
            [
                "Entries with Errors",
                str(report.metrics.entries_with_errors),
                "",
                "",
                "",
                "",
            ]
        )
        writer.writerow(
            [
                "Entries with Warnings",
                str(report.metrics.entries_with_warnings),
                "",
                "",
                "",
                "",
            ]
        )

        return output.getvalue()
