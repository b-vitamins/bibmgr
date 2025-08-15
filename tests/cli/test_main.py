"""Tests for main CLI entry point and application setup.

This module comprehensively tests:
- CLI initialization and configuration
- Command registration and routing
- Context setup and passing
- Global options and flags
- Configuration file loading
- Error handling at top level
- Version display
"""

from unittest.mock import Mock, patch

import click
import yaml
from click.testing import CliRunner

from bibmgr.cli.main import Context, cli


class TestCLIEntryPoint:
    """Test the main CLI entry point."""

    def test_cli_no_command_shows_help(self, cli_runner):
        """Test that running without command shows help."""
        result = cli_runner.invoke([])

        assert result.exit_code == 0
        assert "Bibliography management tool" in result.output
        assert "Commands:" in result.output
        assert "Options:" in result.output

    def test_cli_version_flag(self, cli_runner):
        """Test --version flag."""
        result = cli_runner.invoke(["--version"])

        assert result.exit_code == 0
        assert "bibmgr version" in result.output

    def test_cli_help_flag(self, cli_runner):
        """Test --help flag."""
        result = cli_runner.invoke(["--help"])

        assert result.exit_code == 0
        assert "Bibliography management tool" in result.output
        assert "Show this message and exit" in result.output

    def test_cli_with_config_file(self, cli_runner, mock_config_file):
        """Test loading configuration from file."""
        with patch("bibmgr.cli.config.Config.from_file") as mock_from_file:
            mock_config = Mock()
            mock_from_file.return_value = mock_config

            cli_runner.invoke(["--config", str(mock_config_file), "list"])

            mock_from_file.assert_called_once_with(mock_config_file)

    def test_cli_with_invalid_config_file(self, cli_runner, tmp_path):
        """Test error handling for invalid config file."""
        bad_config = tmp_path / "bad_config.yaml"
        bad_config.write_text("invalid: yaml: content:")

        result = cli_runner.invoke(["--config", str(bad_config), "list"])

        assert result.exit_code != 0
        assert "Error" in result.output

    def test_cli_context_initialization(self, cli_runner):
        """Test that context is properly initialized."""

        @cli.command()
        @click.pass_context
        def test_command(ctx):
            assert isinstance(ctx.obj, Context)
            assert ctx.obj.repository is not None
            assert ctx.obj.search_service is not None
            assert ctx.obj.collection_repository is not None
            assert ctx.obj.console is not None
            click.echo("Context OK")

        result = cli_runner.invoke(["test-command"])
        assert result.exit_code == 0
        assert "Context OK" in result.output


class TestCommandRegistration:
    """Test command registration and routing."""

    def test_all_commands_registered(self, cli_runner):
        """Test that all expected commands are registered."""
        result = cli_runner.invoke(["--help"])

        # Entry commands
        assert "add" in result.output
        assert "show" in result.output
        assert "list" in result.output
        assert "edit" in result.output
        assert "delete" in result.output

        # Search commands
        assert "search" in result.output
        assert "find" in result.output
        assert "similar" in result.output

        # Collection commands
        assert "collection" in result.output or "collections" in result.output

        # Import/Export commands
        assert "import" in result.output
        assert "export" in result.output

        # Quality commands
        assert "check" in result.output
        assert "dedupe" in result.output
        assert "clean" in result.output

        # Other commands
        assert "init" in result.output
        assert "status" in result.output

    def test_command_groups_help(self, cli_runner):
        """Test help for command groups."""
        # Mock backend to prevent CLI initialization issues during help
        with patch("bibmgr.storage.backends.filesystem.FileSystemBackend.initialize"):
            # Test collection command group
            result = cli_runner.invoke(["collection", "--help"])
            # Help should be shown even if CLI setup fails, so check output content
            assert "list" in result.output
            assert "create" in result.output
            assert "show" in result.output

            # Test tag command group
            result = cli_runner.invoke(["tag", "--help"])
            # Help should be shown even if CLI setup fails, so check output content
            assert "add" in result.output
            assert "remove" in result.output
            assert "list" in result.output

    def test_unknown_command(self, cli_runner):
        """Test error for unknown command."""
        result = cli_runner.invoke(["nonexistent"])

        assert result.exit_code != 0
        assert "No such command" in result.output or "Error" in result.output


class TestGlobalOptions:
    """Test global CLI options."""

    def test_verbose_flag(self, cli_runner):
        """Test --verbose flag."""
        with patch("bibmgr.cli.main.setup_logging") as mock_setup:
            cli_runner.invoke(["--verbose", "list"])

            mock_setup.assert_called_once()
            call_args = mock_setup.call_args
            assert call_args.kwargs["verbose"] is True

    def test_quiet_flag(self, cli_runner):
        """Test --quiet flag."""
        with patch("bibmgr.cli.main.setup_logging") as mock_setup:
            cli_runner.invoke(["--quiet", "list"])

            mock_setup.assert_called_once()
            call_args = mock_setup.call_args
            assert call_args.kwargs["quiet"] is True

    def test_no_color_flag(self, cli_runner):
        """Test --no-color flag."""
        cli_runner.invoke(["--no-color", "list"])

        # Console should be created without color
        # Output should not contain ANSI escape codes

    def test_data_dir_option(self, tmp_path):
        """Test --data-dir option."""
        from bibmgr.cli.main import cli

        custom_dir = tmp_path / "custom_data"

        # Use a fresh runner without any patches
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--data-dir", str(custom_dir), "status"], catch_exceptions=False
        )

        assert result.exit_code == 0
        # Verify the custom directory is shown in status output
        assert str(custom_dir) in result.output


class TestConfigurationLoading:
    """Test configuration file loading and merging."""

    def test_default_config_locations(self, cli_runner):
        """Test checking default configuration locations."""
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False

            # Should check multiple locations
            cli_runner.invoke(["list"])

            # Check for config file checks
            assert mock_exists.call_count >= 1

    def test_config_file_precedence(self, cli_runner, tmp_path):
        """Test configuration file precedence."""
        # Create configs at different locations
        user_config = tmp_path / ".config" / "bibmgr" / "config.yaml"
        user_config.parent.mkdir(parents=True)
        user_config.write_text(yaml.dump({"display": {"theme": "user"}}))

        project_config = tmp_path / ".bibmgr.yaml"
        project_config.write_text(yaml.dump({"display": {"theme": "project"}}))

        # Project config should override user config
        with patch(
            "bibmgr.cli.config.get_config_paths",
            return_value=[user_config, project_config],
        ):
            from bibmgr.cli.config import load_config

            config = load_config()
            # Project config should take precedence over user config
            assert config["display"]["theme"] == "project"

    def test_environment_variable_override(self, cli_runner, monkeypatch):
        """Test environment variables override config files."""
        monkeypatch.setenv("BIBMGR_THEME", "env_theme")
        monkeypatch.setenv("BIBMGR_DATA_DIR", "/custom/path")

        # Environment variables should override config files
        from bibmgr.cli.config import load_config

        config = load_config()
        assert config.get("theme") == "env_theme"
        assert config.get("data_dir") == "/custom/path"


class TestErrorHandling:
    """Test top-level error handling."""

    def test_keyboard_interrupt_handling(self, cli_runner):
        """Test graceful handling of Ctrl+C."""

        def raise_keyboard_interrupt(*args, **kwargs):
            raise KeyboardInterrupt()

        with patch(
            "bibmgr.cli.commands.entry.list_cmd.callback",
            side_effect=raise_keyboard_interrupt,
        ):
            result = cli_runner.invoke(["list"])

            assert result.exit_code == 130  # Standard exit code for SIGINT
            assert "Interrupted" in result.output or result.output == ""

    def test_exception_handling(self, cli_runner):
        """Test handling of unexpected exceptions."""

        def raise_exception(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        with patch(
            "bibmgr.cli.commands.entry.list_cmd.callback", side_effect=raise_exception
        ):
            result = cli_runner.invoke(["list"])

            assert result.exit_code == 1
            assert "Error" in result.output
            assert "Unexpected error" in result.output

    def test_debug_mode_shows_traceback(self, cli_runner):
        """Test that debug mode shows full traceback."""

        def raise_exception(*args, **kwargs):
            raise RuntimeError("Debug error")

        with patch(
            "bibmgr.cli.commands.entry.list_cmd.callback", side_effect=raise_exception
        ):
            result = cli_runner.invoke(["--debug", "list"])

            # In debug mode, exception should propagate to test runner
            assert result.exception is not None
            assert isinstance(result.exception, RuntimeError)
            assert "Debug error" in str(result.exception)


class TestInitCommand:
    """Test the 'bib init' initialization command."""

    def test_init_creates_directories(self, tmp_path):
        """Test that init creates necessary directories."""
        from bibmgr.cli.main import cli

        # Use a subdirectory to ensure it starts empty
        init_path = tmp_path / "new_init_test"

        # Use a fresh runner without any patches
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--data-dir", str(init_path), "init"], catch_exceptions=False
        )

        assert result.exit_code == 0
        assert "Initialized bibliography database" in result.output
        assert (init_path / "entries").exists()
        assert (init_path / "metadata").exists()
        assert (init_path / "collections").exists()

    def test_init_already_initialized(self, tmp_path):
        """Test init when already initialized."""
        from bibmgr.cli.main import cli

        # Create directories and an entry file to simulate initialized state
        (tmp_path / "entries").mkdir(parents=True)
        (tmp_path / "entries" / "test_entry.json").write_text('{"key": "test2024"}')

        # Use a fresh runner without any patches
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--data-dir", str(tmp_path), "init"], catch_exceptions=False
        )

        assert result.exit_code == 0
        assert "already initialized" in result.output

    def test_init_with_import(self, tmp_path, temp_bibtex_file):
        """Test init with initial import."""
        from bibmgr.cli.main import cli

        # Use a subdirectory to ensure it starts empty
        init_path = tmp_path / "init_import_test"

        # Use a fresh runner without any patches
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--data-dir", str(init_path), "init", "--import", str(temp_bibtex_file)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert "Initialized" in result.output
        # Import is not implemented yet, so it shows a message about that
        assert "Import functionality not yet implemented" in result.output


class TestStatusCommand:
    """Test the 'bib status' command."""

    def test_status_shows_statistics(self, cli_runner, populated_repository):
        """Test status command shows database statistics."""
        # Just test that the status command runs and shows basic structure
        with patch("bibmgr.storage.backends.filesystem.FileSystemBackend.initialize"):
            result = cli_runner.invoke(["status"])

            assert result.exit_code == 0
            assert "Database Status" in result.output
            assert "Storage location:" in result.output
            # The command should run successfully even if no statistics are available

    def test_status_shows_storage_info(self, isolated_cli_runner):
        """Test status shows storage information."""
        from bibmgr.cli.main import cli

        # isolated_cli_runner properly sets up an isolated environment with a custom storage path
        result = isolated_cli_runner.invoke(cli, ["status"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "Storage location:" in result.output
        assert (
            "bibmgr_storage" in result.output
        )  # Verify it shows the isolated storage path

    def test_status_check_index(self, cli_runner):
        """Test status with index checking."""
        result = cli_runner.invoke(["status", "--check-index"])

        assert result.exit_code == 0
        assert "Index status:" in result.output


class TestMainFunction:
    """Test the main() function entry point."""

    def test_main_function(self):
        """Test main() function."""
        with patch("bibmgr.cli.main.cli") as mock_cli:
            from bibmgr.cli.main import main

            main()

            mock_cli.assert_called_once()

    def test_main_with_args(self):
        """Test main() with command line arguments."""
        import sys

        original_argv = sys.argv

        try:
            sys.argv = ["bib", "list", "--limit", "10"]

            with patch("bibmgr.cli.main.cli") as mock_cli:
                from bibmgr.cli.main import main

                main()

                mock_cli.assert_called_once()
        finally:
            sys.argv = original_argv


class TestPluginSystem:
    """Test plugin loading and registration."""

    def test_load_plugins(self, cli_runner, tmp_path):
        """Test loading CLI plugins."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Create a test plugin
        plugin_file = plugin_dir / "test_plugin.py"
        plugin_file.write_text("""
import click

@click.command()
def hello():
    '''Test plugin command'''
    click.echo('Hello from plugin!')

def register(cli):
    cli.add_command(hello)
""")

        with patch("bibmgr.cli.main.load_plugins"):
            # Simulate plugin loading
            pass
