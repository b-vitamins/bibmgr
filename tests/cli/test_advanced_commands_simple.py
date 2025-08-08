"""Simplified tests for CLI advanced commands (stubs)."""

from __future__ import annotations


class TestAdvancedCommandsStubs:
    """Test that advanced command stubs return expected error."""

    def test_import_command_stub(self, cli_runner, json_entries_file):
        """Test import command returns not implemented."""
        from bibmgr.cli import cli

        result = cli_runner.invoke(
            cli,
            [
                "import",
                str(json_entries_file),
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        assert "not yet implemented" in result.output.lower()

    def test_dedupe_command_stub(self, cli_runner):
        """Test dedupe command returns not implemented."""
        from bibmgr.cli import cli

        result = cli_runner.invoke(cli, ["dedupe"])

        assert result.exit_code != 0
        assert "not yet implemented" in result.output.lower()

    def test_validate_command_stub(self, cli_runner):
        """Test validate command returns not implemented."""
        from bibmgr.cli import cli

        result = cli_runner.invoke(cli, ["validate"])

        assert result.exit_code != 0
        assert "not yet implemented" in result.output.lower()

    def test_stats_command_stub(self, cli_runner):
        """Test stats command returns not implemented."""
        from bibmgr.cli import cli

        result = cli_runner.invoke(cli, ["stats"])

        assert result.exit_code != 0
        assert "not yet implemented" in result.output.lower()

    def test_export_command_stub(self, cli_runner, temp_dir):
        """Test export command returns not implemented."""
        from bibmgr.cli import cli

        output_file = temp_dir / "export.bib"
        result = cli_runner.invoke(
            cli,
            [
                "export",
                str(output_file),
                "--format",
                "bibtex",
            ],
        )

        assert result.exit_code != 0
        assert "not yet implemented" in result.output.lower()
