"""Unit tests for the nroute CLI main module."""

from __future__ import annotations

from click.testing import CliRunner

from nroute.cli import cli as package_cli
from nroute.cli.main import __all__, cli


def test_main_reexports_root_cli() -> None:
    """Verify nroute.cli.main re-exports the package root Click command."""
    assert cli is package_cli
    assert __all__ == ["cli"]


def test_main_cli_help() -> None:
    """Verify the re-exported CLI can execute its root help command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "nroute - AI-Based Smart Network Routing System." in result.output
    assert "--version" in result.output
