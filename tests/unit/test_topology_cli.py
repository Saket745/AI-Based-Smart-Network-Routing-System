"""Unit tests for the nroute topology CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nroute.cli.topology_cmd import topology_cmd
from nroute.exceptions import TopologyError


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def topo_file(tmp_path) -> str:
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

    # Mock node and edge data for _print_topology_summary
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
        # Setup mock generator to return our mock topology
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

        # Verify the correct generator method was called
        if topo_type == "random":
            mock_gen.random.assert_called_once()
        elif topo_type == "scale-free":
            mock_gen.scale_free.assert_called_once()
        elif topo_type == "small-world":
            mock_gen.small_world.assert_called_once()
        elif topo_type == "fat-tree":
            mock_gen.fat_tree.assert_called_once()

    @patch("nroute.cli.topology_cmd.TopologyGenerator.random")
    def test_generate_save_to_file(
        self,
        mock_random: MagicMock,
        runner: CliRunner,
        mock_topology: MagicMock,
        tmp_path,
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
        assert str(out_file) in result.output
        mock_topology.save.assert_called_once_with(str(out_file))

    @patch("nroute.cli.topology_cmd.TopologyGenerator.random")
    def test_generate_topology_error(
        self, mock_random: MagicMock, runner: CliRunner
    ) -> None:
        """Test handling of TopologyError during generation."""
        mock_random.side_effect = TopologyError("Generation failed")

        result = runner.invoke(
            topology_cmd, ["generate", "--type", "random"], obj={"seed": 1}
        )

        assert result.exit_code != 0
        assert "Topology error: Generation failed" in result.output

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
        assert f"Topology: {topo_file}" in result.output
        assert "Nodes" in result.output
        assert "10" in result.output
        mock_load.assert_called_once_with(topo_file)

    @patch("nroute.cli.topology_cmd.Topology.load")
    def test_show_load_fail(
        self, mock_load: MagicMock, runner: CliRunner, topo_file: str
    ) -> None:
        """Test failure when topology file cannot be loaded."""
        mock_load.side_effect = Exception("Invalid JSON")

        result = runner.invoke(topology_cmd, ["show", "--file", topo_file])

        assert result.exit_code != 0
        assert "Failed to load topology: Invalid JSON" in result.output

    def test_show_missing_file(self, runner: CliRunner) -> None:
        """Test show command without mandatory --file option."""
        result = runner.invoke(topology_cmd, ["show"])
        assert result.exit_code != 0
        assert "Missing option '--file'" in result.output
