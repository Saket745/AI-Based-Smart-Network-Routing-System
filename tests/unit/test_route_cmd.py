"""Unit tests for the nroute route CLI commands."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import nroute.cli.route_cmd
from nroute.exceptions import RoutingError

# In Python 3.10+, nroute.cli.route_cmd might refer to the Click group
# because of how it's imported in nroute/cli/__init__.py.
# We explicitly get the module from sys.modules to patch its attributes.
import nroute.cli.route_cmd as route_cmd_mod
if not isinstance(route_cmd_mod, type(sys)):
    route_cmd_mod = sys.modules["nroute.cli.route_cmd"]

route_cmd = route_cmd_mod.route_cmd


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

    def test_compute_success(
        self,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test successful route computation with default algorithm."""
        with patch.object(route_cmd_mod.Topology, "load", return_value=mock_topology), \
             patch.object(route_cmd_mod, "get_router") as mock_get_router, \
             patch.object(route_cmd_mod.RouteMetrics, "from_path") as mock_metrics_from_path:

            mock_router = MagicMock()
            mock_router.compute_path.return_value = ["A", "B"]
            mock_get_router.return_value = mock_router

            mock_metrics = MagicMock()
            mock_metrics.total_hops = 1
            mock_metrics.total_latency = 10.5
            mock_metrics.bottleneck_bandwidth = 1000.0
            mock_metrics.bottleneck_utilization = 0.25
            mock_metrics_from_path.return_value = mock_metrics

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

    def test_compute_topology_load_fail(
        self, runner: CliRunner, topo_file: str
    ) -> None:
        """Test failure when topology cannot be loaded."""
        with patch.object(route_cmd_mod.Topology, "load", side_effect=Exception("File not found")):
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

    def test_compute_invalid_nodes(
        self,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test failure when source or destination nodes are missing."""
        with patch.object(route_cmd_mod.Topology, "load", return_value=mock_topology):
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

    def test_compute_routing_error(
        self,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test handling of RoutingError."""
        with patch.object(route_cmd_mod.Topology, "load", return_value=mock_topology), \
             patch.object(route_cmd_mod, "get_router") as mock_get_router:

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

    def test_compute_custom_router(
        self,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test route computation with a custom router class."""
        with patch.object(route_cmd_mod.Topology, "load", return_value=mock_topology), \
             patch("nroute.utils.loader.load_custom_class") as mock_load_custom, \
             patch.object(route_cmd_mod.RouteMetrics, "from_path") as mock_metrics_from_path:

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
            mock_metrics_from_path.return_value = mock_metrics

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

    def test_compute_custom_without_option(
        self, runner: CliRunner, topo_file: str
    ) -> None:
        """Test failure when algorithm is 'custom' but --custom-router is missing."""
        with patch.object(route_cmd_mod.Topology, "load", return_value=MagicMock(nodes=["A", "B"])):
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

    def test_compute_general_exception(
        self,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test handling of general exceptions during computation."""
        with patch.object(route_cmd_mod.Topology, "load", return_value=mock_topology), \
             patch.object(route_cmd_mod, "get_router") as mock_get_router:

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

    def test_compute_hop_breakdown_error(
        self,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test that hop breakdown handles edge data retrieval errors gracefully."""
        with patch.object(route_cmd_mod.Topology, "load", return_value=mock_topology), \
             patch.object(route_cmd_mod, "get_router") as mock_get_router, \
             patch.object(route_cmd_mod.RouteMetrics, "from_path") as mock_metrics_from_path:

            mock_router = MagicMock()
            mock_router.compute_path.return_value = ["A", "B"]
            mock_get_router.return_value = mock_router

            mock_metrics = MagicMock()
            mock_metrics.total_hops = 1
            mock_metrics.total_latency = 10.0
            mock_metrics.bottleneck_bandwidth = 100.0
            mock_metrics.bottleneck_utilization = 0.1
            mock_metrics_from_path.return_value = mock_metrics

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
