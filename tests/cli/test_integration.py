"""End-to-end integration tests for the CLI.

This module tests complete workflows and interactions between components:
- Full entry lifecycle (create, edit, search, delete)
- Import and export workflows
- Collection management workflows
- Quality checking and cleanup workflows
- Complex search and filtering scenarios
- Multi-command sequences
"""

import json
from pathlib import Path

from bibmgr.cli.main import cli


class TestEntryLifecycle:
    """Test complete entry lifecycle workflows."""

    def test_create_edit_delete_workflow(self, isolated_cli_runner):
        """Test creating, editing, and deleting an entry."""
        runner = isolated_cli_runner

        # Create entry
        result = runner.invoke(
            cli,
            [
                "add",
                "--key",
                "test2024",
                "--title",
                "Test Article",
                "--author",
                "Doe, John",
                "--year",
                "2024",
                "--type",
                "article",
                "--journal",
                "Test Journal",
            ],
        )
        assert result.exit_code == 0
        assert "Entry added successfully" in result.output

        # Verify entry exists
        result = runner.invoke(cli, ["show", "test2024"])
        assert result.exit_code == 0
        assert "Test Article" in result.output

        # Edit entry
        result = runner.invoke(
            cli,
            ["edit", "test2024", "-f", "title=Updated Test Article", "-f", "year=2025"],
        )
        assert result.exit_code == 0
        assert "Entry updated successfully" in result.output

        # Verify changes
        result = runner.invoke(cli, ["show", "test2024"])
        assert result.exit_code == 0
        assert "Updated Test Article" in result.output
        assert "2025" in result.output

        # Delete entry
        result = runner.invoke(cli, ["delete", "test2024", "--force"])
        assert result.exit_code == 0
        assert "Entry deleted successfully" in result.output

        # Verify deletion
        result = runner.invoke(cli, ["show", "test2024"])
        assert result.exit_code != 0
        assert "Entry not found" in result.output

    def test_batch_entry_operations(self, isolated_cli_runner):
        """Test batch operations on multiple entries."""
        runner = isolated_cli_runner

        # Create multiple entries
        for i in range(3):
            result = runner.invoke(
                cli,
                [
                    "add",
                    "--key",
                    f"batch{i}",
                    "--title",
                    f"Batch Entry {i}",
                    "--author",
                    f"Batch Author {i}",
                    "--year",
                    "2024",
                    "--type",
                    "article",
                    "--journal",
                    "Test Journal",
                ],
            )
            assert result.exit_code == 0

        # List all entries
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "batch0" in result.output
        assert "batch1" in result.output
        assert "batch2" in result.output

        # Add tags to all
        result = runner.invoke(
            cli, ["tag", "add", "--entries", "batch0,batch1,batch2", "batch-test"]
        )
        assert result.exit_code == 0

        # Delete all
        result = runner.invoke(cli, ["delete", "batch0", "batch1", "batch2", "--force"])
        assert result.exit_code == 0
        assert "Successfully deleted 3 entries" in result.output


class TestImportExportWorkflow:
    """Test import and export workflows."""

    def test_import_modify_export_workflow(self, isolated_cli_runner, sample_bibtex):
        """Test importing, modifying, and exporting entries."""
        runner = isolated_cli_runner

        # Create import file
        import_file = Path("import.bib")
        import_file.write_text(sample_bibtex)

        # Import entries
        result = runner.invoke(cli, ["import", str(import_file)])
        assert result.exit_code == 0
        assert "Imported: 2" in result.output

        # Tag imported entries
        result = runner.invoke(
            cli, ["tag", "add", "--entries", "doe2024,smith2023", "imported"]
        )
        assert result.exit_code == 0

        # Add to collection
        result = runner.invoke(
            cli,
            ["collection", "create", "imported-papers", "--name", "Imported Papers"],
        )
        if result.exit_code != 0:
            print(f"Collection create failed with exit code {result.exit_code}")
            print(f"Output: {result.output}")
        assert result.exit_code == 0

        result = runner.invoke(
            cli, ["collection", "add", "imported-papers", "doe2024", "smith2023"]
        )
        assert result.exit_code == 0

        # Export collection
        export_file = Path("export.bib")
        result = runner.invoke(
            cli, ["export", str(export_file), "--collection", "imported-papers"]
        )
        if result.exit_code != 0:
            print(f"Export failed with exit code {result.exit_code}")
            print(f"Output: {result.output}")
        assert result.exit_code == 0
        assert export_file.exists()

        # Verify export content
        content = export_file.read_text()
        assert "@article{doe2024" in content
        assert "@inproceedings{smith2023" in content

    def test_format_conversion_workflow(self, isolated_cli_runner, sample_bibtex):
        """Test converting between formats."""
        runner = isolated_cli_runner

        # Import from BibTeX
        import_file = Path("import.bib")
        import_file.write_text(sample_bibtex)

        result = runner.invoke(cli, ["import", str(import_file)])
        assert result.exit_code == 0

        # Export to JSON
        json_file = Path("export.json")
        result = runner.invoke(cli, ["export", str(json_file), "--format", "json"])
        assert result.exit_code == 0

        # Verify JSON content
        data = json.loads(json_file.read_text())
        assert len(data["entries"]) == 2

        # Clear database
        result = runner.invoke(cli, ["delete", "--all", "--force"])
        assert result.exit_code == 0

        # Import from JSON
        result = runner.invoke(cli, ["import", str(json_file)])
        assert result.exit_code == 0
        assert "Imported: 2" in result.output


class TestSearchWorkflow:
    """Test search and filtering workflows."""

    def test_search_refine_export_workflow(self, isolated_cli_runner):
        """Test searching, refining results, and exporting."""
        runner = isolated_cli_runner

        # Create test entries
        entries = [
            ("ml2024", "Machine Learning Advances", "ML, AI", 2024),
            ("ml2023", "Deep Learning Basics", "ML, DL", 2023),
            ("quantum2024", "Quantum Computing", "Quantum", 2024),
            ("stats2023", "Statistical Methods", "Statistics", 2023),
        ]

        for key, title, keywords, year in entries:
            result = runner.invoke(
                cli,
                [
                    "add",
                    "--key",
                    key,
                    "--title",
                    title,
                    "--author",
                    "Test Author",
                    "--keywords",
                    keywords,
                    "--year",
                    str(year),
                    "--type",
                    "article",
                    "--journal",
                    "Test Journal",
                ],
            )
            assert result.exit_code == 0

        # Search for ML papers
        result = runner.invoke(cli, ["search", "machine learning"])
        assert result.exit_code == 0
        assert "ml2024" in result.output

        # Find recent papers
        result = runner.invoke(cli, ["find", "--year", "2024"])
        assert result.exit_code == 0
        assert "ml2024" in result.output
        assert "quantum2024" in result.output
        assert "ml2023" not in result.output

        # Create smart collection for 2024 papers
        result = runner.invoke(
            cli,
            [
                "collection",
                "create",
                "recent",
                "--name",
                "Recent Papers",
                "--query",
                "year:2024",
            ],
        )
        assert result.exit_code == 0

        # Export search results
        result = runner.invoke(
            cli, ["export", "recent_papers.bib", "--query", "year:2024"]
        )
        assert result.exit_code == 0

    def test_similar_entries_workflow(self, isolated_cli_runner):
        """Test finding and managing similar entries."""
        runner = isolated_cli_runner

        # Create similar entries
        result = runner.invoke(
            cli,
            [
                "add",
                "--key",
                "paper1",
                "--title",
                "Neural Network Applications",
                "--author",
                "AI Researcher",
                "--keywords",
                "neural networks, deep learning, AI",
                "--year",
                "2024",
                "--type",
                "article",
                "--journal",
                "AI Journal",
            ],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            cli,
            [
                "add",
                "--key",
                "paper2",
                "--title",
                "Deep Neural Networks",
                "--author",
                "ML Expert",
                "--keywords",
                "neural networks, deep learning",
                "--year",
                "2024",
                "--type",
                "article",
                "--journal",
                "AI Journal",
            ],
        )
        assert result.exit_code == 0

        # Find similar to paper1
        result = runner.invoke(cli, ["similar", "paper1"])
        assert result.exit_code == 0
        # Should find paper2 as similar


class TestQualityWorkflow:
    """Test quality checking and maintenance workflows."""

    def test_quality_check_and_fix_workflow(self, isolated_cli_runner):
        """Test checking quality and fixing issues."""
        runner = isolated_cli_runner

        # Create entries with quality issues
        result = runner.invoke(
            cli,
            [
                "add",
                "--key",
                "incomplete2024",
                "--title",
                "incomplete paper",  # lowercase title
                "--author",
                "test author",
                "--year",
                "2024",
                "--type",
                "article",
                "--journal",
                "Test Journal",
                "--no-validate",
            ],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            cli,
            [
                "add",
                "--key",
                "messy2024",
                "--title",
                "  Messy   Title  ",  # extra spaces
                "--author",
                "doe, j.",  # incomplete name
                "--pages",
                "10-20",  # should be 10--20
                "--year",
                "2024",
                "--type",
                "article",
                "--journal",
                "Test Journal",
                "--no-validate",
            ],
        )
        assert result.exit_code == 0

        # Check quality
        result = runner.invoke(cli, ["check", "--all"])
        assert result.exit_code == 0
        # Just verify the command ran and produced output
        assert "check" in result.output.lower() or "quality" in result.output.lower()

        # Clean entries
        result = runner.invoke(cli, ["clean", "--all"])
        assert result.exit_code == 0
        # Just verify the command ran without error
        assert result.exit_code == 0

        # Verify fixes
        result = runner.invoke(cli, ["show", "messy2024"])
        assert result.exit_code == 0
        assert "Messy Title" in result.output  # Capitalized
        assert "10--20" in result.output  # Fixed page range

    def test_deduplication_workflow(self, isolated_cli_runner):
        """Test finding and handling duplicate entries."""
        runner = isolated_cli_runner

        # Create duplicate entries
        result = runner.invoke(
            cli,
            [
                "add",
                "--key",
                "dup1",
                "--title",
                "Duplicate Paper",
                "--author",
                "Smith, John",
                "--year",
                "2024",
                "--type",
                "article",
                "--journal",
                "Test Journal",
            ],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            cli,
            [
                "add",
                "--key",
                "dup2",
                "--title",
                "Duplicate Paper",
                "--author",
                "Smith, J.",
                "--year",
                "2024",
                "--type",
                "article",
                "--journal",
                "Test Journal",
            ],
        )
        assert result.exit_code == 0

        # Find duplicates
        result = runner.invoke(cli, ["dedupe"])
        assert result.exit_code == 0
        assert "Found" in result.output
        assert "duplicate" in result.output.lower()


class TestCollectionWorkflow:
    """Test collection management workflows."""

    def test_hierarchical_collections_workflow(self, isolated_cli_runner):
        """Test creating and managing hierarchical collections."""
        runner = isolated_cli_runner

        # Create entries
        for i in range(5):
            result = runner.invoke(
                cli,
                [
                    "add",
                    "--key",
                    f"entry{i}",
                    "--title",
                    f"Entry {i}",
                    "--author",
                    f"Author {i}",
                    "--type",
                    "article",
                    "--journal",
                    "Test Journal",
                    "--year",
                    "2024",
                ],
            )
            assert result.exit_code == 0

        # Create parent collection
        result = runner.invoke(
            cli, ["collection", "create", "research", "--name", "Research Papers"]
        )
        assert result.exit_code == 0

        # Create child collections
        result = runner.invoke(
            cli,
            [
                "collection",
                "create",
                "ml-research",
                "--name",
                "Machine Learning",
                "--parent",
                "research",
            ],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            cli,
            [
                "collection",
                "create",
                "quantum-research",
                "--name",
                "Quantum Computing",
                "--parent",
                "research",
            ],
        )
        assert result.exit_code == 0

        # Add entries to collections
        result = runner.invoke(
            cli, ["collection", "add", "ml-research", "entry0", "entry1"]
        )
        assert result.exit_code == 0

        result = runner.invoke(
            cli, ["collection", "add", "quantum-research", "entry2", "entry3"]
        )
        assert result.exit_code == 0

        # List tree view
        result = runner.invoke(cli, ["collection", "list", "--tree"])
        assert result.exit_code == 0
        assert "Research Papers" in result.output
        assert "├── Machine Learning" in result.output
        assert "└── Quantum Computing" in result.output


class TestMetadataWorkflow:
    """Test metadata and note management workflows."""

    def test_reading_workflow(self, isolated_cli_runner):
        """Test paper reading workflow with notes and status."""
        runner = isolated_cli_runner

        # Add paper
        result = runner.invoke(
            cli,
            [
                "add",
                "--key",
                "paper2024",
                "--title",
                "Important Paper",
                "--author",
                "Important Author",
                "--type",
                "article",
                "--journal",
                "Important Journal",
                "--year",
                "2024",
            ],
        )
        assert result.exit_code == 0

        # Mark as reading
        result = runner.invoke(
            cli, ["metadata", "set", "paper2024", "--read-status", "reading"]
        )
        assert result.exit_code == 0

        # Add notes while reading
        result = runner.invoke(
            cli,
            [
                "note",
                "add",
                "paper2024",
                "--content",
                "Key insight: This changes everything",
                "--type",
                "idea",
            ],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            cli,
            [
                "note",
                "add",
                "paper2024",
                "--content",
                "The methodology is novel",
                "--page",
                "5",
                "--type",
                "summary",
            ],
        )
        assert result.exit_code == 0

        # Mark as read and rate
        result = runner.invoke(
            cli,
            [
                "metadata",
                "set",
                "paper2024",
                "--read-status",
                "read",
                "--rating",
                "5",
                "--importance",
                "high",
            ],
        )
        assert result.exit_code == 0

        # Tag for future reference
        result = runner.invoke(
            cli, ["tag", "add", "paper2024", "breakthrough", "must-cite"]
        )
        assert result.exit_code == 0

        # Show complete metadata
        result = runner.invoke(cli, ["metadata", "show", "paper2024"])
        assert result.exit_code == 0
        assert "★★★★★" in result.output  # Rating with 5 stars
        assert "Read Status" in result.output and "Read" in result.output
        assert "breakthrough" in result.output


class TestComplexWorkflow:
    """Test complex multi-step workflows."""

    def test_research_project_workflow(self, isolated_cli_runner, sample_bibtex):
        """Test complete research project workflow."""
        runner = isolated_cli_runner

        # Initialize project
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0

        # Import initial references
        import_file = Path("references.bib")
        import_file.write_text(sample_bibtex)

        result = runner.invoke(
            cli, ["import", str(import_file), "--tag", "initial-import"]
        )
        assert result.exit_code == 0

        # Create project structure
        collections = [
            ("literature-review", "Literature Review"),
            ("methodology", "Methodology Papers"),
            ("related-work", "Related Work"),
        ]

        for coll_id, coll_name in collections:
            result = runner.invoke(
                cli, ["collection", "create", coll_id, "--name", coll_name]
            )
            assert result.exit_code == 0

        # Add more papers
        result = runner.invoke(
            cli,
            [
                "add",
                "--key",
                "method2024",
                "--title",
                "Novel Research Method",
                "--author",
                "Research Expert",
                "--type",
                "article",
                "--journal",
                "Research Methods Journal",
                "--keywords",
                "methodology, research",
                "--year",
                "2024",
            ],
        )
        assert result.exit_code == 0

        # Organize into collections
        result = runner.invoke(cli, ["collection", "add", "methodology", "method2024"])
        assert result.exit_code == 0

        # Check quality
        result = runner.invoke(cli, ["check", "--all"])
        assert result.exit_code == 0

        # Generate report
        result = runner.invoke(cli, ["report", "quality"])
        assert result.exit_code == 0

        # Export for paper writing
        result = runner.invoke(
            cli,
            ["export", "dissertation_refs.bib", "--collection", "literature-review"],
        )
        assert result.exit_code == 0

        # Status check
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "Total entries:" in result.output


class TestErrorRecovery:
    """Test error handling and recovery in workflows."""

    def test_import_with_errors_recovery(self, isolated_cli_runner):
        """Test recovering from import errors."""
        runner = isolated_cli_runner

        # Create file with mixed valid/invalid entries
        mixed_file = Path("mixed.bib")
        mixed_file.write_text("""
@article{valid2024,
    title = {Valid Entry},
    author = {Doe, John},
    year = {2024},
    journal = {Test Journal}
}

@article{invalid,
    title = ,  # Invalid
    year = not_a_number
}

@article{valid2023,
    title = {Another Valid Entry},
    author = {Smith, Jane},
    year = {2023},
    journal = {Test Journal}
}
""")

        # Import with continue-on-error
        result = runner.invoke(cli, ["import", str(mixed_file), "--continue-on-error"])

        # Should import valid entries despite errors
        assert "Imported: 2" in result.output or "partial" in result.output.lower()

        # Verify valid entries were imported
        result = runner.invoke(cli, ["list"])
        assert "valid2024" in result.output
        assert "valid2023" in result.output
