"""Unit tests for the nroute route CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nroute.cli.route_cmd import route_cmd
from nroute.exceptions import RoutingError


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
    """Create a mock topology."""
    topo = MagicMock()
    topo.nodes = ["A", "B", "C"]
    topo.get_edge.return_value = {
        "latency": 10.5,
        "bandwidth": 1000,
        "utilization": 0.25,
        "status": "up",
    }
    return topo


class TestRouteComputeCLI:
    """Tests for `nroute route compute` command."""

    @patch("nroute.cli.route_cmd.Topology.load")
    @patch("nroute.cli.route_cmd.get_router")
    @patch("nroute.cli.route_cmd.RouteMetrics.from_path")
    def test_compute_success(
        self,
        mock_metrics_cls: MagicMock,
        mock_get_router: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test successful route computation with default algorithm."""
        mock_topo_load.return_value = mock_topology
        mock_router = MagicMock()
        mock_router.compute_path.return_value = ["A", "B"]
        mock_get_router.return_value = mock_router

        mock_metrics = MagicMock()
        mock_metrics.total_hops = 1
        mock_metrics.total_latency = 10.5
        mock_metrics.bottleneck_bandwidth = 1000.0
        mock_metrics.bottleneck_utilization = 0.25
        mock_metrics_cls.return_value = mock_metrics

        result = runner.invoke(
            route_cmd,
            [
                "compute",
                "--topology",
                topo_file,
                "--source",
                "A",
                "--destination",
                "B",
            ],
        )

        assert result.exit_code == 0
        assert "Route: A -> B" in result.output
        assert "Path: A -> B" in result.output
        assert "10.50 ms" in result.output
        assert "1000 Mbps" in result.output
        mock_get_router.assert_called_once_with("dijkstra", topology=mock_topology)

    @patch("nroute.cli.route_cmd.Topology.load")
    def test_compute_topology_load_fail(
        self, mock_topo_load: MagicMock, runner: CliRunner, topo_file: str
    ) -> None:
        """Test failure when topology cannot be loaded."""
        mock_topo_load.side_effect = Exception("File not found")

        result = runner.invoke(
            route_cmd,
            [
                "compute",
                "--topology",
                topo_file,
                "--source",
                "A",
                "--destination",
                "B",
            ],
        )

        assert result.exit_code != 0
        assert "Failed to load topology" in result.output

    @patch("nroute.cli.route_cmd.Topology.load")
    def test_compute_invalid_nodes(
        self,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test failure when source or destination nodes are missing."""
        mock_topo_load.return_value = mock_topology

        # Invalid source
        result = runner.invoke(
            route_cmd,
            [
                "compute",
                "--topology",
                topo_file,
                "--source",
                "Z",
                "--destination",
                "B",
            ],
        )
        assert result.exit_code == 1
        assert "Source node 'Z' not found" in result.output

        # Invalid destination
        result = runner.invoke(
            route_cmd,
            [
                "compute",
                "--topology",
                topo_file,
                "--source",
                "A",
                "--destination",
                "Z",
            ],
        )
        assert result.exit_code == 1
        assert "Destination node 'Z' not found" in result.output

    @patch("nroute.cli.route_cmd.Topology.load")
    @patch("nroute.cli.route_cmd.get_router")
    def test_compute_routing_error(
        self,
        mock_get_router: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test handling of RoutingError."""
        mock_topo_load.return_value = mock_topology
        mock_router = MagicMock()
        mock_router.compute_path.side_effect = RoutingError("No path found")
        mock_get_router.return_value = mock_router

        result = runner.invoke(
            route_cmd,
            [
                "compute",
                "--topology",
                topo_file,
                "--source",
                "A",
                "--destination",
                "B",
            ],
        )

        assert result.exit_code != 0
        assert "Routing error: No path found" in result.output

    @patch("nroute.cli.route_cmd.Topology.load")
    @patch("nroute.utils.loader.load_custom_class")
    @patch("nroute.cli.route_cmd.RouteMetrics.from_path")
    def test_compute_custom_router(
        self,
        mock_metrics_cls: MagicMock,
        mock_load_custom: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test route computation with a custom router class."""
        mock_topo_load.return_value = mock_topology

        class FakeRouter:
            def __init__(self, topology=None):
                self.topology = topology

            def compute_path(self, topo, s, d, weight=None):
                return [s, d]

        mock_load_custom.return_value = FakeRouter
        mock_metrics = MagicMock()
        mock_metrics.total_hops = 1
        mock_metrics.total_latency = 5.0
        mock_metrics.bottleneck_bandwidth = 500.0
        mock_metrics.bottleneck_utilization = 0.5
        mock_metrics_cls.return_value = mock_metrics

        result = runner.invoke(
            route_cmd,
            [
                "compute",
                "--topology",
                topo_file,
                "--algorithm",
                "custom",
                "--custom-router",
                "my_mod.MyRouter",
                "--source",
                "A",
                "--destination",
                "B",
            ],
        )

        assert result.exit_code == 0
        assert "Path: A -> B" in result.output
        mock_load_custom.assert_called_once()

    @patch("nroute.cli.route_cmd.Topology.load")
    def test_compute_custom_without_option(
        self, mock_topo_load: MagicMock, runner: CliRunner, topo_file: str
    ) -> None:
        """Test failure when algorithm is 'custom' but --custom-router is missing."""
        mock_topo_load.return_value = MagicMock(nodes=["A", "B"])
        result = runner.invoke(
            route_cmd,
            [
                "compute",
                "--topology",
                topo_file,
                "--algorithm",
                "custom",
                "--source",
                "A",
                "--destination",
                "B",
            ],
        )

        assert result.exit_code != 0
        assert "Option '--custom-router' is required" in result.output

    @patch("nroute.cli.route_cmd.Topology.load")
    @patch("nroute.cli.route_cmd.get_router")
    def test_compute_general_exception(
        self,
        mock_get_router: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test handling of general exceptions during computation."""
        mock_topo_load.return_value = mock_topology
        mock_router = MagicMock()
        mock_router.compute_path.side_effect = Exception("Unknown error")
        mock_get_router.return_value = mock_router

        result = runner.invoke(
            route_cmd,
            [
                "compute",
                "--topology",
                topo_file,
                "--source",
                "A",
                "--destination",
                "B",
            ],
        )

        assert result.exit_code == 1
        assert "Failed to compute route: Unknown error" in result.output

    @patch("nroute.cli.route_cmd.Topology.load")
    @patch("nroute.cli.route_cmd.get_router")
    @patch("nroute.cli.route_cmd.RouteMetrics.from_path")
    def test_compute_hop_breakdown_error(
        self,
        mock_metrics_cls: MagicMock,
        mock_get_router: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test that hop breakdown handles edge data retrieval errors gracefully."""
        mock_topo_load.return_value = mock_topology
        mock_router = MagicMock()
        mock_router.compute_path.return_value = ["A", "B"]
        mock_get_router.return_value = mock_router

        mock_metrics = MagicMock()
        mock_metrics.total_hops = 1
        mock_metrics.total_latency = 10.0
        mock_metrics.bottleneck_bandwidth = 100.0
        mock_metrics.bottleneck_utilization = 0.1
        mock_metrics_cls.return_value = mock_metrics

        # Make topo.get_edge fail for the breakdown
        mock_topology.get_edge.side_effect = Exception("Edge error")

        result = runner.invoke(
            route_cmd,
            [
                "compute",
                "--topology",
                topo_file,
                "--source",
                "A",
                "--destination",
                "B",
            ],
        )

        assert result.exit_code == 0
        assert "?" in result.output  # Should show '?' for latency/bandwidth/etc.
