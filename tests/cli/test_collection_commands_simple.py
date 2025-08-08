"""Simplified tests for CLI collection commands (stubs)."""

from __future__ import annotations


class TestCollectionCommandsStubs:
    """Test that collection command stubs return expected error."""

    def test_collection_create_stub(self, cli_runner):
        """Test collection create returns not implemented."""
        from bibmgr.cli import cli

        result = cli_runner.invoke(
            cli,
            [
                "collection",
                "create",
                "test",
                "--description",
                "Test collection",
            ],
        )

        assert result.exit_code != 0
        assert "not yet implemented" in result.output.lower()

    def test_collection_list_stub(self, cli_runner):
        """Test collection list returns not implemented."""
        from bibmgr.cli import cli

        result = cli_runner.invoke(cli, ["collection", "list"])

        assert result.exit_code != 0
        assert "not yet implemented" in result.output.lower()

    def test_tag_add_stub(self, cli_runner):
        """Test tag add returns not implemented."""
        from bibmgr.cli import cli

        result = cli_runner.invoke(cli, ["tag", "add", "test-tag", "entry1", "entry2"])

        assert result.exit_code != 0
        assert "not yet implemented" in result.output.lower()

    def test_tag_list_stub(self, cli_runner):
        """Test tag list returns not implemented."""
        from bibmgr.cli import cli

        result = cli_runner.invoke(cli, ["tag", "list"])

        assert result.exit_code != 0
        assert "not yet implemented" in result.output.lower()

    def test_search_stub(self, cli_runner):
        """Test search returns not implemented."""
        from bibmgr.cli import cli

        result = cli_runner.invoke(cli, ["search", "test query"])

        assert result.exit_code != 0
        assert "not yet implemented" in result.output.lower()
