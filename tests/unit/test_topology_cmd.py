"""Unit tests for the nroute topology CLI commands."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nroute.cli.topology_cmd import topology_cmd
from nroute.core.topology import Topology
from nroute.exceptions import TopologyError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


class TestTopologyGenerateCLI:
    """Tests for `nroute topology generate` command."""

    @pytest.mark.parametrize("topo_type", ["random", "scale-free", "small-world", "fat-tree"])
    def test_generate_success_stdout(self, runner: CliRunner, topo_type: str) -> None:
        """Test generating various topologies to stdout summary."""
        result = runner.invoke(
            topology_cmd,
            ["generate", "--type", topo_type, "--nodes", "10", "--k", "4"],
        )
        assert result.exit_code == 0
        assert "Topology" in result.output
        assert "Nodes" in result.output
        if topo_type != "fat-tree":
            assert "10" in result.output

    def test_generate_random_with_options(self, runner: CliRunner) -> None:
        """Test random topology generation with specific options."""
        result = runner.invoke(
            topology_cmd,
            ["generate", "--type", "random", "--nodes", "15", "--edge-prob", "0.5", "--seed", "42"],
        )
        assert result.exit_code == 0
        assert "Nodes" in result.output
        assert "15" in result.output

    def test_generate_save_to_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test generating and saving a topology to a file."""
        output_file = tmp_path / "topo.json"
        result = runner.invoke(
            topology_cmd,
            ["generate", "--type", "random", "--nodes", "5", "--output", str(output_file)],
        )
        assert result.exit_code == 0
        assert "Topology saved to" in result.output
        assert "topo.json" in result.output
        assert output_file.exists()

        # Verify it's a valid JSON topology
        topo = Topology.load(str(output_file))
        assert topo.node_count == 5

    def test_generate_json_output(self, runner: CliRunner) -> None:
        """Test generating topology with JSON output format."""
        result = runner.invoke(
            topology_cmd,
            ["generate", "--type", "random", "--nodes", "5"],
            obj={"output_format": "json"},
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 5

    def test_generate_json_output_to_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test generating topology with JSON output format and saving to file."""
        output_file = tmp_path / "topo.json"
        result = runner.invoke(
            topology_cmd,
            ["generate", "--type", "random", "--nodes", "5", "--output", str(output_file)],
            obj={"output_format": "json"},
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "success"
        assert data["file"] == str(output_file)
        assert data["nodes"] == 5
        assert output_file.exists()

    def test_generate_invalid_type(self, runner: CliRunner) -> None:
        """Test generation with an invalid topology type."""
        # Click Choice should catch this before it reaches our logic
        result = runner.invoke(
            topology_cmd,
            ["generate", "--type", "invalid"],
        )
        assert result.exit_code != 0
        assert "Invalid value for '--type'" in result.output

    @patch("nroute.cli.topology_cmd.TopologyGenerator.random")
    def test_generate_error_handling(self, mock_gen: MagicMock, runner: CliRunner) -> None:
        """Test handling of TopologyError during generation."""
        mock_gen.side_effect = TopologyError("Generation failed")
        result = runner.invoke(
            topology_cmd,
            ["generate", "--type", "random"],
        )
        assert result.exit_code == 1
        assert "Topology error: Generation failed" in result.output

    @patch("nroute.cli.topology_cmd.TopologyGenerator.random")
    def test_generate_error_handling_json(self, mock_gen: MagicMock, runner: CliRunner) -> None:
        """Test handling of TopologyError during generation with JSON output."""
        mock_gen.side_effect = TopologyError("Generation failed")
        result = runner.invoke(
            topology_cmd,
            ["generate", "--type", "random"],
            obj={"output_format": "json"},
        )
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error"] == "Generation failed"


class TestTopologyShowCLI:
    """Tests for `nroute topology show` command."""

    @pytest.fixture
    def sample_topo_file(self, tmp_path: Path) -> str:
        topo = Topology()
        topo.add_node("A", type="router")
        topo.add_node("B", type="host")
        topo.add_edge("A", "B", latency=10.0)
        filepath = tmp_path / "test_topo.json"
        topo.save(str(filepath))
        return str(filepath)

    def test_show_success(self, runner: CliRunner, sample_topo_file: str) -> None:
        """Test showing a topology summary."""
        result = runner.invoke(
            topology_cmd,
            ["show", "--file", sample_topo_file],
        )
        assert result.exit_code == 0
        assert "Topology: " in result.output
        assert "Nodes" in result.output
        assert "Edges" in result.output
        assert "Node Types" in result.output
        assert "router" in result.output
        assert "host" in result.output

    def test_show_json_success(self, runner: CliRunner, sample_topo_file: str) -> None:
        """Test showing a topology summary in JSON format."""
        result = runner.invoke(
            topology_cmd,
            ["show", "--file", sample_topo_file],
            obj={"output_format": "json"},
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["nodes"] == 2
        assert data["edges"] == 1
        assert data["node_types"]["router"] == 1
        assert data["node_types"]["host"] == 1

    def test_show_file_not_found(self, runner: CliRunner) -> None:
        """Test showing a non-existent topology file."""
        result = runner.invoke(
            topology_cmd,
            ["show", "--file", "non_existent.json"],
        )
        assert result.exit_code != 0
        assert "does not exist" in result.output

    @patch("nroute.cli.topology_cmd.Topology.load")
    def test_show_load_error(self, mock_load: MagicMock, runner: CliRunner, tmp_path: Path) -> None:
        """Test handling of errors when loading a topology."""
        # Create an empty file to pass Click's exists=True check
        p = tmp_path / "bad.json"
        p.write_text("invalid")

        mock_load.side_effect = Exception("Load failed")
        result = runner.invoke(
            topology_cmd,
            ["show", "--file", str(p)],
        )
        assert result.exit_code == 1
        assert "Failed to load topology: Load failed" in result.output

    @patch("nroute.cli.topology_cmd.Topology.load")
    def test_show_load_error_json(self, mock_load: MagicMock, runner: CliRunner, tmp_path: Path) -> None:
        """Test handling of errors when loading a topology with JSON output."""
        p = tmp_path / "bad.json"
        p.write_text("invalid")

        mock_load.side_effect = Exception("Load failed")
        result = runner.invoke(
            topology_cmd,
            ["show", "--file", str(p)],
            obj={"output_format": "json"},
        )
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error"] == "Load failed"
