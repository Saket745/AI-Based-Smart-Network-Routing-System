"""Unit tests for the nroute simulate CLI commands."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nroute.cli.simulate_cmd import simulate_cmd


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def topo_file(tmp_path: Any) -> str:
    """Create a dummy topology file to satisfy click.Path(exists=True)."""
    p = tmp_path / "topo.json"
    p.write_text("{}")
    return str(p)


@pytest.fixture
def mock_topology() -> MagicMock:
    """Create a mock topology."""
    topo = MagicMock()
    topo.node_count = 3
    topo.edge_count = 3
    return topo


class TestSimulateCLI:
    """Tests for `nroute simulate` commands."""

    @patch("nroute.cli.simulate_cmd.Topology.load")
    @patch("nroute.cli.simulate_cmd.get_router")
    @patch("nroute.cli.simulate_cmd.SimulationEngine")
    def test_run_sim_success(
        self,
        mock_engine_cls: MagicMock,
        mock_get_router: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test successful simulation run."""
        mock_topo_load.return_value = mock_topology
        mock_router = MagicMock()
        mock_get_router.return_value = mock_router

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.results = []
        mock_result.total_throughput.return_value = 100.0
        mock_result.mean_latency.return_value = 10.0
        mock_engine.run.return_value = mock_result
        mock_engine_cls.return_value = mock_engine

        result = runner.invoke(
            simulate_cmd,
            [
                "run",
                "--topology",
                topo_file,
                "--algorithm",
                "dijkstra",
                "--duration",
                "10",
            ],
        )

        assert result.exit_code == 0
        assert "Running simulation: DIJKSTRA" in result.output
        assert "Simulation Results" in result.output
        mock_get_router.assert_called_once_with(
            "dijkstra", topology=mock_topology, allow_unsafe=False
        )

    @patch("nroute.cli.simulate_cmd.Topology.load")
    @patch("nroute.cli.simulate_cmd.get_router")
    @patch("nroute.cli.simulate_cmd.SimulationEngine")
    def test_compare_success(
        self,
        mock_engine_cls: MagicMock,
        mock_get_router: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test successful algorithm comparison."""
        mock_topo_load.return_value = mock_topology
        mock_router = MagicMock()
        mock_get_router.return_value = mock_router

        mock_result = MagicMock()
        mock_result.results = []
        mock_result.total_throughput.return_value = 100.0
        mock_result.mean_latency.return_value = 10.0

        mock_engine = MagicMock()
        mock_engine.run.return_value = mock_result
        mock_engine_cls.return_value = mock_engine

        result = runner.invoke(
            simulate_cmd,
            [
                "compare",
                "--topology",
                topo_file,
                "--algorithms",
                "dijkstra,ecmp",
                "--duration",
                "10",
            ],
        )

        assert result.exit_code == 0
        assert "Comparing algorithms: DIJKSTRA, ECMP" in result.output
        assert "Algorithm Comparison" in result.output
        assert mock_get_router.call_count == 2

    @patch("nroute.cli.simulate_cmd.Topology.load")
    def test_run_sim_json_output(
        self,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test simulation run with JSON output."""
        mock_topo_load.return_value = mock_topology

        with (
            patch("nroute.cli.simulate_cmd.get_router"),
            patch("nroute.cli.simulate_cmd.SimulationEngine") as mock_engine_cls,
        ):
            mock_result = MagicMock()
            mock_result.results = []
            mock_result.total_throughput.return_value = 100.0
            mock_result.mean_latency.return_value = 10.0
            mock_engine = MagicMock()
            mock_engine.run.return_value = mock_result
            mock_engine_cls.return_value = mock_engine

            # Passing output_format via context obj
            result = runner.invoke(
                simulate_cmd, ["run", "--topology", topo_file], obj={"output_format": "json"}
            )

            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["algorithm"] == "dijkstra"
            assert data["total_throughput"] == 100.0

    @patch("nroute.cli.simulate_cmd.Topology.load")
    def test_compare_too_few_algorithms(
        self, mock_topo_load: MagicMock, runner: CliRunner, topo_file: str
    ) -> None:
        """Test failure when fewer than 2 algorithms are provided for comparison."""
        result = runner.invoke(
            simulate_cmd,
            ["compare", "--topology", topo_file, "--algorithms", "dijkstra"],
        )
        assert result.exit_code != 0
        assert "Please provide at least 2 algorithms" in result.output
