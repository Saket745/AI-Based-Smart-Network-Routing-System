"""Unit tests for the nroute topology CLI commands."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from click.testing import CliRunner

from nroute.cli.topology_cmd import topology_cmd
from nroute.core.topology import Topology
from nroute.exceptions import TopologyError


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def topo_file(tmp_path: Path) -> str:
    """Create a dummy topology file to satisfy click.Path(exists=True)."""
    p = tmp_path / "topo.json"
    p.write_text("{}")
    return str(p)


@pytest.fixture
def mock_topology() -> MagicMock:
    """Create a mock topology for testing."""
    topo = MagicMock()
    topo.node_count = 10
    topo.edge_count = 20
    topo.nodes = [str(i) for i in range(10)]
    topo.edges = [(str(i), str((i + 1) % 10)) for i in range(10)]

    topo.graph.nodes = [str(i) for i in range(10)]
    topo.graph.degree.side_effect = lambda n: 2
    topo.get_node.return_value = {"status": "up", "type": "router"}
    topo.get_edge.return_value = {"status": "up"}

    return topo


class TestTopologyGenerateCLI:
    """Tests for `nroute topology generate` command."""

    @pytest.mark.parametrize(
        "topo_type, nodes, extra_args",
        [
            ("random", 10, ["--edge-prob", "0.5"]),
            ("scale-free", 15, []),
            ("small-world", 20, ["--k", "4", "--rewire-prob", "0.2"]),
            ("fat-tree", 4, ["--k", "4"]),
        ],
    )
    @patch("nroute.cli.topology_cmd.TopologyGenerator")
    def test_generate_success_stdout(
        self,
        mock_gen: MagicMock,
        topo_type: str,
        nodes: int,
        extra_args: list[str],
        runner: CliRunner,
        mock_topology: MagicMock,
    ) -> None:
        """Test generating various topologies and printing to stdout."""
        if topo_type == "random":
            mock_gen.random.return_value = mock_topology
        elif topo_type == "scale-free":
            mock_gen.scale_free.return_value = mock_topology
        elif topo_type == "small-world":
            mock_gen.small_world.return_value = mock_topology
        elif topo_type == "fat-tree":
            mock_gen.fat_tree.return_value = mock_topology

        args = ["generate", "--type", topo_type, "--nodes", str(nodes), *extra_args]
        result = runner.invoke(topology_cmd, args, obj={"seed": 42})

        assert result.exit_code == 0
        assert f"{topo_type} Topology" in result.output
        assert "Nodes" in result.output
        assert "Edges" in result.output

    @patch("nroute.cli.topology_cmd.TopologyGenerator.random")
    def test_generate_save_to_file(
        self,
        mock_random: MagicMock,
        runner: CliRunner,
        mock_topology: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test generating a topology and saving it to a file."""
        mock_random.return_value = mock_topology
        out_file = tmp_path / "custom_topo.json"

        result = runner.invoke(
            topology_cmd,
            ["generate", "--type", "random", "--output", str(out_file)],
            obj={"seed": 123},
        )

        assert result.exit_code == 0
        assert "Topology saved to" in result.output
<<<<<<< HEAD
        assert str(out_file) in result.output.replace("\n", "").replace("\r", "")
=======
        assert str(out_file.name) in result.output
        assert out_file.name in result.output
>>>>>>> b20fea97ab29a08784bcf12c878384b3ab936144
        mock_topology.save.assert_called_once_with(str(out_file))

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
        assert output_file.exists()

    @patch("nroute.cli.topology_cmd.TopologyGenerator.random")
    def test_generate_topology_error(self, mock_random: MagicMock, runner: CliRunner) -> None:
        """Test handling of TopologyError during generation."""
        mock_random.side_effect = TopologyError("Generation failed")

        result = runner.invoke(topology_cmd, ["generate", "--type", "random"], obj={"seed": 1})

        assert result.exit_code != 0
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

    def test_generate_invalid_type(self, runner: CliRunner) -> None:
        """Test providing an invalid topology type."""
        result = runner.invoke(topology_cmd, ["generate", "--type", "invalid"])
        assert result.exit_code != 0
        assert "Invalid value for '--type'" in result.output


class TestTopologyShowCLI:
    """Tests for `nroute topology show` command."""

    @patch("nroute.cli.topology_cmd.Topology.load")
    def test_show_success(
        self, mock_load: MagicMock, runner: CliRunner, topo_file: str, mock_topology: MagicMock
    ) -> None:
        """Test showing a topology summary from a file."""
        mock_load.return_value = mock_topology

        result = runner.invoke(topology_cmd, ["show", "--file", topo_file])

        assert result.exit_code == 0
<<<<<<< HEAD
=======
        assert "Topology" in result.output
>>>>>>> b20fea97ab29a08784bcf12c878384b3ab936144
        assert "Topology:" in result.output
        assert "Nodes" in result.output
        assert "10" in result.output
        mock_load.assert_called_once_with(topo_file)

    def test_show_json_success(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test showing a topology summary in JSON format."""
        topo = Topology()
        topo.add_node("A", type="router")
        topo.add_node("B", type="host")
        topo.add_edge("A", "B", latency=10.0)
        filepath = tmp_path / "test_topo.json"
        topo.save(str(filepath))

        result = runner.invoke(
            topology_cmd,
            ["show", "--file", str(filepath)],
            obj={"output_format": "json"},
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["nodes"] == 2
        assert data["edges"] == 1
        assert data["node_types"]["router"] == 1
        assert data["node_types"]["host"] == 1

    def test_show_missing_file(self, runner: CliRunner) -> None:
        """Test show command without mandatory --file option."""
        result = runner.invoke(topology_cmd, ["show"])
        assert result.exit_code != 0
        assert "Missing option '--file'" in result.output

    def test_show_file_not_found(self, runner: CliRunner) -> None:
        """Test showing a non-existent topology file."""
        result = runner.invoke(
            topology_cmd,
            ["show", "--file", "non_existent.json"],
        )
        assert result.exit_code != 0
        assert "does not exist" in result.output

    @patch("nroute.cli.topology_cmd.Topology.load")
    def test_show_load_fail(self, mock_load: MagicMock, runner: CliRunner, topo_file: str) -> None:
        """Test failure when topology file cannot be loaded."""
        mock_load.side_effect = Exception("Invalid JSON")

        result = runner.invoke(topology_cmd, ["show", "--file", topo_file])

        assert result.exit_code != 0
        assert "Failed to load topology: Invalid JSON" in result.output

    @patch("nroute.cli.topology_cmd.Topology.load")
    def test_show_load_error_json(
        self, mock_load: MagicMock, runner: CliRunner, tmp_path: Path
    ) -> None:
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
