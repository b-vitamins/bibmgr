"""File integrity checking for bibliography entries.

Implements async-capable file verification:
- PDF file structure and metadata validation
- Text extraction capability checking
- Backup verification
- File path validation
- Checksum verification
"""

from __future__ import annotations

import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import msgspec

from bibmgr.quality.validators import ValidationResult, ValidationSeverity


@dataclass
class FileIssue:
    """An issue with a file."""

    entry_key: str
    file_path: str
    issue_type: str
    message: str
    suggestion: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_string(self) -> str:
        """Format as human-readable string."""
        parts = [f"[{self.issue_type}] {self.entry_key}: {self.message}"]
        if self.file_path:
            parts.append(f" ({self.file_path})")
        if self.suggestion:
            parts.append(f"\n  → {self.suggestion}")
        return "".join(parts)


class IntegrityReport(msgspec.Struct, frozen=True, kw_only=True):
    """Report of file integrity check results."""

    total_files: int
    valid_files: int
    missing_files: list[FileIssue] = msgspec.field(default_factory=list)
    corrupted_files: list[FileIssue] = msgspec.field(default_factory=list)
    permission_issues: list[FileIssue] = msgspec.field(default_factory=list)
    path_issues: list[FileIssue] = msgspec.field(default_factory=list)
    backup_status: dict[str, Any] = msgspec.field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        """Check if report contains issues."""
        return bool(
            self.missing_files
            or self.corrupted_files
            or self.permission_issues
            or self.path_issues
        )

    @property
    def integrity_score(self) -> float:
        """Calculate integrity score."""
        if self.total_files == 0:
            return 100.0
        return (self.valid_files / self.total_files) * 100

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "File Integrity Report",
            f"Total files: {self.total_files}",
            f"Valid files: {self.valid_files}",
            f"Integrity score: {self.integrity_score:.1f}%",
        ]

        if self.missing_files:
            lines.append(f"\nMissing files: {len(self.missing_files)}")
            for issue in self.missing_files[:3]:
                lines.append(f"  - {issue.entry_key}: {issue.file_path}")
            if len(self.missing_files) > 3:
                lines.append(f"  ... and {len(self.missing_files) - 3} more")

        if self.corrupted_files:
            lines.append(f"\nCorrupted files: {len(self.corrupted_files)}")

        if self.permission_issues:
            lines.append(f"\nPermission issues: {len(self.permission_issues)}")

        if self.path_issues:
            lines.append(f"\nPath issues: {len(self.path_issues)}")

        if self.backup_status:
            lines.append("\nBackup status:")
            for key, value in self.backup_status.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)


class PDFValidator:
    """Validates PDF files with structure and metadata checking."""

    def __init__(
        self,
        check_structure: bool = False,
        check_text_extraction: bool = False,
    ):
        """Initialize PDF validator.

        Args:
            check_structure: Whether to validate PDF structure
            check_text_extraction: Whether to check text extraction capability
        """
        self.check_structure = check_structure
        self.check_text_extraction = check_text_extraction

        # PDF magic bytes
        self.pdf_header = b"%PDF-"
        self.pdf_footer = b"%%EOF"

    def validate(self, file_path: Path) -> ValidationResult:
        """Validate a PDF file.

        Args:
            file_path: Path to PDF file

        Returns:
            Validation result with metadata
        """
        if not file_path.exists():
            return ValidationResult(
                field="pdf",
                value=str(file_path),
                is_valid=False,
                message="File does not exist",
                severity=ValidationSeverity.ERROR,
            )

        if not file_path.is_file():
            return ValidationResult(
                field="pdf",
                value=str(file_path),
                is_valid=False,
                message="Path is not a file",
                severity=ValidationSeverity.ERROR,
            )

        # Basic checks
        size = file_path.stat().st_size
        if size == 0:
            return ValidationResult(
                field="pdf",
                value=str(file_path),
                is_valid=False,
                message="File is empty",
                severity=ValidationSeverity.ERROR,
            )

        if size < 100:  # Minimum reasonable PDF size
            return ValidationResult(
                field="pdf",
                value=str(file_path),
                is_valid=False,
                message=f"File too small ({size} bytes)",
                severity=ValidationSeverity.ERROR,
            )

        metadata: dict[str, Any] = {"size": size}

        try:
            # Check PDF magic bytes
            with open(file_path, "rb") as f:
                # Check header
                header = f.read(8)
                if not header.startswith(self.pdf_header):
                    return ValidationResult(
                        field="pdf",
                        value=str(file_path),
                        is_valid=False,
                        message="Not a PDF file (invalid header)",
                        severity=ValidationSeverity.ERROR,
                    )

                # Extract version
                if len(header) >= 8:
                    version = header[5:8].decode("ascii", errors="ignore")
                    metadata["version"] = version.strip()

                # Check footer
                f.seek(max(0, size - 1024))
                footer = f.read()
                if self.pdf_footer not in footer:
                    return ValidationResult(
                        field="pdf",
                        value=str(file_path),
                        is_valid=False,
                        message="PDF file may be truncated (missing EOF marker)",
                        severity=ValidationSeverity.WARNING,
                        metadata=metadata,
                    )

                # Structure check
                if self.check_structure:
                    structure_info = self._check_structure(file_path)
                    metadata["structure"] = structure_info

                    if not structure_info.get("valid", False):
                        return ValidationResult(
                            field="pdf",
                            value=str(file_path),
                            is_valid=False,
                            message="Invalid PDF structure",
                            severity=ValidationSeverity.WARNING,
                            metadata=metadata,
                        )

                # Text extraction check
                if self.check_text_extraction:
                    text_info = self._check_text_extraction(file_path)
                    metadata["text_extractable"] = text_info.get("extractable", False)
                    metadata["pages"] = text_info.get("pages", 0)

            return ValidationResult(
                field="pdf",
                value=str(file_path),
                is_valid=True,
                message="Valid PDF file",
                severity=ValidationSeverity.INFO,
                metadata=metadata,
            )

        except PermissionError:
            return ValidationResult(
                field="pdf",
                value=str(file_path),
                is_valid=False,
                message="Permission denied",
                severity=ValidationSeverity.ERROR,
            )
        except Exception as e:
            return ValidationResult(
                field="pdf",
                value=str(file_path),
                is_valid=False,
                message=f"Error reading file: {e}",
                severity=ValidationSeverity.ERROR,
            )

    def _check_structure(self, file_path: Path) -> dict[str, Any]:
        """Check PDF internal structure."""
        info: dict[str, Any] = {"valid": False}

        try:
            with open(file_path, "rb") as f:
                content = f.read()

                # Look for basic PDF objects
                has_catalog = (
                    b"/Type /Catalog" in content or b"/Type/Catalog" in content
                )
                has_pages = b"/Type /Pages" in content or b"/Type/Pages" in content
                has_xref = b"xref" in content
                has_trailer = b"trailer" in content

                info["has_catalog"] = has_catalog
                info["has_pages"] = has_pages
                info["has_xref"] = has_xref
                info["has_trailer"] = has_trailer

                # Basic structure is valid if all required elements present
                info["valid"] = all([has_catalog, has_pages, has_xref, has_trailer])

                # Try to count pages
                page_count = content.count(b"/Type /Page") + content.count(
                    b"/Type/Page"
                )
                info["page_count"] = page_count

        except Exception as e:
            info["error"] = str(e)

        return info

    def _check_text_extraction(self, file_path: Path) -> dict[str, Any]:
        """Check if text can be extracted from PDF."""
        info: dict[str, Any] = {"extractable": False, "pages": 0}

        try:
            with open(file_path, "rb") as f:
                content = f.read()

                # Simple heuristic: look for text stream markers
                has_text_streams = b"BT" in content and b"ET" in content
                has_font_refs = b"/Font" in content

                info["extractable"] = has_text_streams and has_font_refs

                # Count pages (simple heuristic)
                page_count = content.count(b"/Type /Page") + content.count(
                    b"/Type/Page"
                )
                # Subtract Pages objects
                page_count -= content.count(b"/Type /Pages") + content.count(
                    b"/Type/Pages"
                )
                info["pages"] = max(0, page_count)

        except Exception as e:
            info["error"] = str(e)

        return info

    def check_readable(self, file_path: Path) -> bool:
        """Check if file is readable."""
        try:
            with open(file_path, "rb") as f:
                f.read(1)
            return True
        except Exception:
            return False


class BackupVerifier:
    """Verifies backup integrity."""

    def __init__(self, backup_dir: Path):
        """Initialize backup verifier.

        Args:
            backup_dir: Directory containing backups
        """
        self.backup_dir = Path(backup_dir)

    def verify_backup(self, backup_name: str) -> dict[str, Any]:
        """Verify a backup.

        Args:
            backup_name: Name of backup to verify

        Returns:
            Verification results
        """
        backup_path = self.backup_dir / backup_name

        if not backup_path.exists():
            return {"exists": False, "error": "Backup not found"}

        results = {
            "exists": True,
            "path": str(backup_path),
            "size": backup_path.stat().st_size,
            "modified": datetime.fromtimestamp(backup_path.stat().st_mtime).isoformat(),
        }

        # Check if it's a directory or archive
        if backup_path.is_dir():
            results["type"] = "directory"
            results["file_count"] = sum(
                1 for _ in backup_path.rglob("*") if _.is_file()
            )
        else:
            results["type"] = "archive"
            # Check archive type
            if backup_path.suffix == ".tar":
                results["format"] = "tar"
            elif backup_path.suffix in [".gz", ".tgz"]:
                results["format"] = "tar.gz"
            elif backup_path.suffix == ".zip":
                results["format"] = "zip"
            else:
                results["format"] = "unknown"

        return results

    def find_latest_backup(self) -> Path | None:
        """Find the most recent backup."""
        if not self.backup_dir.exists():
            return None

        backups = list(self.backup_dir.iterdir())
        if not backups:
            return None

        # Sort by modification time
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return backups[0]

    def check_backup_age(self) -> dict[str, Any]:
        """Check age of latest backup."""
        latest = self.find_latest_backup()

        if not latest:
            return {"has_backup": False, "message": "No backups found"}

        mtime = datetime.fromtimestamp(latest.stat().st_mtime)
        age = datetime.now() - mtime

        return {
            "has_backup": True,
            "latest_backup": latest.name,
            "modified": mtime.isoformat(),
            "age_days": age.days,
            "age_hours": age.total_seconds() / 3600,
            "is_recent": age.days < 7,
            "is_stale": age.days > 30,
        }


class FileIntegrityChecker:
    """Main file integrity checker with async support."""

    def __init__(
        self,
        base_path: Path | None = None,
        async_mode: bool = False,
        batch_size: int = 50,
        max_workers: int = 4,
    ):
        """Initialize integrity checker.

        Args:
            base_path: Base path for file resolution
            async_mode: Whether to enable async operations
            batch_size: Number of files to process in parallel
            max_workers: Maximum number of worker threads
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.async_mode = async_mode
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.pdf_validator = PDFValidator()
        self.executor = (
            ThreadPoolExecutor(max_workers=max_workers) if async_mode else None
        )

    def __del__(self):
        """Cleanup executor."""
        if self.executor:
            self.executor.shutdown(wait=False)

    def check_entry_files(self, entry: Any) -> list[FileIssue]:
        """Check files for a single entry.

        Args:
            entry: Entry to check

        Returns:
            List of file issues
        """
        issues = []

        # Check file field (BibTeX format)
        if hasattr(entry, "file") and entry.file:
            file_issues = self._check_bibtex_file_field(entry.key, entry.file)
            issues.extend(file_issues)

        # Check pdf field (direct path)
        if hasattr(entry, "pdf") and entry.pdf:
            pdf_issues = self._check_pdf_path(entry.key, entry.pdf)
            issues.extend(pdf_issues)

        return issues

    def _check_bibtex_file_field(
        self, entry_key: str, file_field: str
    ) -> list[FileIssue]:
        """Check BibTeX file field format.

        Args:
            entry_key: Entry key
            file_field: BibTeX file field value

        Returns:
            List of issues
        """
        issues = []

        # Parse BibTeX file field format
        # Format: :path:type or description:path:type
        parts = file_field.split(":")

        if len(parts) < 2:
            issues.append(
                FileIssue(
                    entry_key=entry_key,
                    file_path=file_field,
                    issue_type="invalid_format",
                    message="Invalid BibTeX file field format",
                    suggestion="Use format :path:type or description:path:type",
                )
            )
            return issues

        # Extract path
        if parts[0]:  # Has description
            path_str = parts[1] if len(parts) > 1 else ""
        else:  # No description
            path_str = parts[1] if len(parts) > 1 else parts[0]

        if not path_str:
            issues.append(
                FileIssue(
                    entry_key=entry_key,
                    file_path=file_field,
                    issue_type="empty_path",
                    message="Empty file path in file field",
                )
            )
            return issues

        # Check the path
        issues.extend(self._check_pdf_path(entry_key, path_str))

        return issues

    def _check_pdf_path(self, entry_key: str, path_str: str) -> list[FileIssue]:
        """Check a PDF file path.

        Args:
            entry_key: Entry key
            path_str: Path string

        Returns:
            List of issues
        """
        issues = []

        # Resolve path
        path = Path(path_str)
        if not path.is_absolute():
            path = self.base_path / path

        # Check existence
        if not path.exists():
            issues.append(
                FileIssue(
                    entry_key=entry_key,
                    file_path=str(path),
                    issue_type="missing_file",
                    message="PDF file not found",
                    suggestion=f"Check if file exists at: {path}",
                )
            )
            return issues

        # Check if it's a PDF
        if path.suffix.lower() != ".pdf":
            issues.append(
                FileIssue(
                    entry_key=entry_key,
                    file_path=str(path),
                    issue_type="wrong_type",
                    message=f"File is not a PDF (extension: {path.suffix})",
                    suggestion="Ensure file field points to a PDF",
                )
            )

        # Validate PDF
        result = self.pdf_validator.validate(path)
        if not result.is_valid:
            issues.append(
                FileIssue(
                    entry_key=entry_key,
                    file_path=str(path),
                    issue_type="corrupted_file",
                    message=f"PDF validation failed: {result.message}",
                    suggestion="Try opening the PDF to verify it's not corrupted",
                    metadata=result.metadata,
                )
            )

        # Check permissions
        if not self.pdf_validator.check_readable(path):
            issues.append(
                FileIssue(
                    entry_key=entry_key,
                    file_path=str(path),
                    issue_type="permission_denied",
                    message="Cannot read PDF file",
                    suggestion="Check file permissions",
                )
            )

        return issues

    def check_all_entries(self, entries: list[Any]) -> IntegrityReport:
        """Check files for all entries synchronously.

        Args:
            entries: List of entries to check

        Returns:
            Integrity report
        """
        all_issues = []
        total_files = 0
        valid_files = 0

        # Process in batches for efficiency
        for i in range(0, len(entries), self.batch_size):
            batch = entries[i : i + self.batch_size]

            for entry in batch:
                # Count files
                has_file = False
                file_count = 0

                if hasattr(entry, "file") and entry.file:
                    has_file = True
                    file_count += 1
                if hasattr(entry, "pdf") and entry.pdf:
                    has_file = True
                    file_count += 1

                total_files += file_count

                # Check files
                issues = self.check_entry_files(entry)
                all_issues.extend(issues)

                # Count valid files
                if has_file and not issues:
                    valid_files += file_count

        return self._create_report(all_issues, total_files, valid_files)

    async def check_all_entries_async(self, entries: list[Any]) -> IntegrityReport:
        """Check files for all entries asynchronously.

        Args:
            entries: List of entries to check

        Returns:
            Integrity report
        """
        if not self.async_mode:
            return self.check_all_entries(entries)

        all_issues = []
        total_files = 0
        valid_files = 0

        # Create tasks for batches
        tasks = []
        for i in range(0, len(entries), self.batch_size):
            batch = entries[i : i + self.batch_size]
            task = self._check_batch_async(batch)
            tasks.append(task)

        # Wait for all tasks
        results = await asyncio.gather(*tasks)

        # Aggregate results
        for batch_issues, batch_total, batch_valid in results:
            all_issues.extend(batch_issues)
            total_files += batch_total
            valid_files += batch_valid

        return self._create_report(all_issues, total_files, valid_files)

    async def _check_batch_async(
        self, batch: list[Any]
    ) -> tuple[list[FileIssue], int, int]:
        """Check a batch of entries asynchronously."""
        loop = asyncio.get_event_loop()

        # Run file checks in executor
        def check_batch():
            issues = []
            total = 0
            valid = 0

            for entry in batch:
                # Count files
                file_count = 0
                if hasattr(entry, "file") and entry.file:
                    file_count += 1
                if hasattr(entry, "pdf") and entry.pdf:
                    file_count += 1

                total += file_count

                # Check files
                entry_issues = self.check_entry_files(entry)
                issues.extend(entry_issues)

                # Count valid
                if file_count > 0 and not entry_issues:
                    valid += file_count

            return issues, total, valid

        return await loop.run_in_executor(self.executor, check_batch)

    def _create_report(
        self, all_issues: list[FileIssue], total_files: int, valid_files: int
    ) -> IntegrityReport:
        """Create integrity report from issues."""
        # Categorize issues
        missing = []
        corrupted = []
        permissions = []
        path_issues = []

        for issue in all_issues:
            if issue.issue_type == "missing_file":
                missing.append(issue)
            elif issue.issue_type == "corrupted_file":
                corrupted.append(issue)
            elif issue.issue_type == "permission_denied":
                permissions.append(issue)
            else:
                path_issues.append(issue)

        return IntegrityReport(
            total_files=total_files,
            valid_files=valid_files,
            missing_files=missing,
            corrupted_files=corrupted,
            permission_issues=permissions,
            path_issues=path_issues,
        )

    def compute_checksum(
        self, file_path: Path, algorithm: str = "sha256"
    ) -> str | None:
        """Compute checksum of a file.

        Args:
            file_path: Path to file
            algorithm: Hash algorithm (sha256, md5, etc.)

        Returns:
            Hex checksum or None if error
        """
        try:
            hasher = hashlib.new(algorithm)
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None
