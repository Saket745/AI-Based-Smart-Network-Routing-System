"""Unit tests for the nroute simulate CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nroute.cli.simulate_cmd import simulate_cmd


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
    """Create a mock topology."""
    topo = MagicMock()
    topo.node_count = 5
    topo.edge_count = 7
    return topo


@pytest.fixture
def mock_sim_result() -> MagicMock:
    """Create a mock simulation result."""
    result = MagicMock()

    tick_metric = MagicMock()
    tick_metric.tick = 0
    tick_metric.throughput = 100.0
    tick_metric.avg_latency = 10.0
    tick_metric.packet_loss_rate = 0.01
    tick_metric.reroute_count = 2
    tick_metric.avg_utilization = 0.5

    result.results = [tick_metric]
    result.total_throughput.return_value = 100.0
    result.mean_latency.return_value = 10.0
    return result


class TestSimulateRunCLI:
    """Tests for `nroute simulate run` command."""

    @patch("nroute.cli.simulate_cmd.Topology.load")
    @patch("nroute.cli.simulate_cmd.get_router")
    @patch("nroute.cli.simulate_cmd.SimulationEngine")
    def test_run_success(
        self,
        mock_engine_cls: MagicMock,
        mock_get_router: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
        mock_sim_result: MagicMock,
    ) -> None:
        """Test successful simulation run with default parameters."""
        mock_topo_load.return_value = mock_topology
        mock_engine = MagicMock()
        mock_engine.run.return_value = mock_sim_result
        mock_engine_cls.return_value = mock_engine

        result = runner.invoke(
            simulate_cmd,
            ["run", "--topology", topo_file],
            obj={"seed": 42},
        )

        assert result.exit_code == 0
        assert "Running simulation: DIJKSTRA" in result.output
        assert "Simulation Results" in result.output
        assert "Total Throughput" in result.output
        mock_topo_load.assert_called_once_with(topo_file)
        mock_get_router.assert_called_once()
        mock_engine.run.assert_called_once()

    @patch("nroute.cli.simulate_cmd.Topology.load")
    def test_run_topology_load_fail(
        self, mock_topo_load: MagicMock, runner: CliRunner, topo_file: str
    ) -> None:
        """Test failure when topology cannot be loaded."""
        mock_topo_load.side_effect = Exception("Invalid JSON")

        result = runner.invoke(
            simulate_cmd,
            ["run", "--topology", topo_file],
            obj={},
        )

        assert result.exit_code != 0
        assert "Failed to load topology: Invalid JSON" in result.output

    @patch("nroute.cli.simulate_cmd.Topology.load")
    @patch("nroute.cli.simulate_cmd.get_router")
    @patch("nroute.cli.simulate_cmd.SimulationEngine")
    def test_run_simulation_error(
        self,
        mock_engine_cls: MagicMock,
        mock_get_router: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test handling of SimulationError."""
        from nroute.exceptions import SimulationError

        mock_topo_load.return_value = mock_topology
        mock_engine = MagicMock()
        mock_engine.run.side_effect = SimulationError("Sim failed")
        mock_engine_cls.return_value = mock_engine

        result = runner.invoke(
            simulate_cmd,
            ["run", "--topology", topo_file],
            obj={},
        )

        assert result.exit_code != 0
        assert "Simulation error: Sim failed" in result.output

    @patch("nroute.cli.simulate_cmd.Topology.load")
    @patch("nroute.cli.simulate_cmd.SimulationEngine")
    @patch("nroute.utils.loader.load_custom_class")
    def test_run_custom_router(
        self,
        mock_load_custom: MagicMock,
        mock_engine_cls: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
        mock_sim_result: MagicMock,
    ) -> None:
        """Test simulation with a custom router."""
        mock_topo_load.return_value = mock_topology
        mock_engine = MagicMock()
        mock_engine.run.return_value = mock_sim_result
        mock_engine_cls.return_value = mock_engine

        class MyRouter:
            def __init__(self, topology=None):
                pass

        mock_load_custom.return_value = MyRouter

        result = runner.invoke(
            simulate_cmd,
            [
                "run",
                "--topology",
                topo_file,
                "--algorithm",
                "custom",
                "--custom-router",
                "pkg.mod:MyRouter",
            ],
            obj={},
        )

        assert result.exit_code == 0
        mock_load_custom.assert_called_once()
        assert "Running simulation: CUSTOM" in result.output

    @patch("nroute.cli.simulate_cmd.Topology.load")
    @patch("nroute.cli.simulate_cmd.get_router")
    @patch("nroute.cli.simulate_cmd.SimulationEngine")
    def test_run_with_output(
        self,
        mock_engine_cls: MagicMock,
        mock_get_router: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
        mock_sim_result: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test simulation run with metrics output to a file."""
        mock_topo_load.return_value = mock_topology
        mock_engine = MagicMock()
        mock_engine.run.return_value = mock_sim_result
        mock_engine_cls.return_value = mock_engine

        output_file = tmp_path / "metrics.json"

        result = runner.invoke(
            simulate_cmd,
            ["run", "--topology", topo_file, "--output", str(output_file)],
            obj={},
        )

        assert result.exit_code == 0
        assert "Metrics saved to" in result.output
        assert str(output_file) in result.output
        assert output_file.exists()

        # Verify JSON content
        data = json.loads(output_file.read_text())
        assert data["algorithm"] == "dijkstra"
        assert data["total_throughput"] == 100.0
        assert len(data["ticks"]) == 1

    @patch("nroute.cli.simulate_cmd.Topology.load")
    @patch("nroute.cli.simulate_cmd.get_router")
    @patch("nroute.cli.simulate_cmd.SimulationEngine")
    @patch("nroute.visualization.LiveSimulationConsole")
    def test_run_visualize(
        self,
        mock_visualizer_cls: MagicMock,
        mock_engine_cls: MagicMock,
        mock_get_router: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
        mock_sim_result: MagicMock,
    ) -> None:
        """Test simulation run with visualization enabled."""
        mock_topo_load.return_value = mock_topology
        mock_visualizer = MagicMock()
        mock_visualizer.run.return_value = mock_sim_result
        mock_visualizer_cls.return_value = mock_visualizer

        result = runner.invoke(
            simulate_cmd,
            ["run", "--topology", topo_file, "--visualize"],
            obj={},
        )

        assert result.exit_code == 0
        assert "Initializing real-time console visualization..." in result.output
        mock_visualizer.run.assert_called_once()


class TestSimulateCompareCLI:
    """Tests for `nroute simulate compare` command."""

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
        mock_sim_result: MagicMock,
    ) -> None:
        """Test successful comparison of multiple algorithms."""
        mock_topo_load.return_value = mock_topology
        mock_engine = MagicMock()
        mock_engine.run.return_value = mock_sim_result
        mock_engine_cls.return_value = mock_engine

        result = runner.invoke(
            simulate_cmd,
            ["compare", "--topology", topo_file, "--algorithms", "dijkstra,ecmp"],
            obj={},
        )

        assert result.exit_code == 0
        assert "Comparing algorithms: DIJKSTRA, ECMP" in result.output
        assert "Algorithm Comparison" in result.output
        assert "Total Throughput" in result.output
        assert mock_get_router.call_count == 2
        assert mock_engine.run.call_count == 2

    @patch("nroute.cli.simulate_cmd.Topology.load")
    def test_compare_too_few_algorithms(
        self, mock_topo_load: MagicMock, runner: CliRunner, topo_file: str
    ) -> None:
        """Test failure when fewer than 2 algorithms are provided."""
        result = runner.invoke(
            simulate_cmd,
            ["compare", "--topology", topo_file, "--algorithms", "dijkstra"],
            obj={},
        )

        assert result.exit_code != 0
        assert "Please provide at least 2 algorithms to compare" in result.output

    @patch("nroute.cli.simulate_cmd.Topology.load")
    @patch("nroute.cli.simulate_cmd.get_router")
    @patch("nroute.cli.simulate_cmd.SimulationEngine")
    def test_compare_partial_failure(
        self,
        mock_engine_cls: MagicMock,
        mock_get_router: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
        mock_sim_result: MagicMock,
    ) -> None:
        """Test comparison when one algorithm fails."""
        mock_topo_load.return_value = mock_topology

        # First call (dijkstra) succeeds, second (ecmp) fails
        mock_engine_success = MagicMock()
        mock_engine_success.run.return_value = mock_sim_result

        mock_engine_fail = MagicMock()
        mock_engine_fail.run.side_effect = Exception("ECMP failed")

        mock_engine_cls.side_effect = [mock_engine_success, mock_engine_fail]

        result = runner.invoke(
            simulate_cmd,
            ["compare", "--topology", topo_file, "--algorithms", "dijkstra,ecmp"],
            obj={},
        )

        assert result.exit_code == 0
        assert "ECMP failed" in result.output
        assert "FAILED" in result.output or "ERR" in result.output

    @patch("nroute.cli.simulate_cmd.Topology.load")
    @patch("nroute.cli.simulate_cmd.get_router")
    @patch("nroute.cli.simulate_cmd.SimulationEngine")
    def test_compare_with_output(
        self,
        mock_engine_cls: MagicMock,
        mock_get_router: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
        mock_sim_result: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test comparison with output file."""
        mock_topo_load.return_value = mock_topology
        mock_engine = MagicMock()
        mock_engine.run.return_value = mock_sim_result
        mock_engine_cls.return_value = mock_engine

        output_file = tmp_path / "comparison.json"

        result = runner.invoke(
            simulate_cmd,
            [
                "compare",
                "--topology",
                topo_file,
                "--algorithms",
                "dijkstra,ecmp",
                "--output",
                str(output_file),
            ],
            obj={},
        )

        assert result.exit_code == 0
        assert "Comparison saved to" in result.output
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        assert "dijkstra" in data
        assert "ecmp" in data
        assert data["dijkstra"]["total_throughput"] == 100.0

    @patch("nroute.cli.simulate_cmd.Topology.load")
    @patch("nroute.cli.simulate_cmd.SimulationEngine")
    @patch("nroute.utils.loader.load_custom_class")
    def test_compare_custom_router(
        self,
        mock_load_custom: MagicMock,
        mock_engine_cls: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        mock_topology: MagicMock,
        mock_sim_result: MagicMock,
    ) -> None:
        """Test comparison including a custom router."""
        mock_topo_load.return_value = mock_topology
        mock_engine = MagicMock()
        mock_engine.run.return_value = mock_sim_result
        mock_engine_cls.return_value = mock_engine

        class MyRouter:
            def __init__(self, topology=None):
                pass

        mock_load_custom.return_value = MyRouter

        result = runner.invoke(
            simulate_cmd,
            [
                "compare",
                "--topology",
                topo_file,
                "--algorithms",
                "dijkstra,custom",
                "--custom-router",
                "pkg.mod:MyRouter",
            ],
            obj={},
        )

        assert result.exit_code == 0
        assert mock_load_custom.call_count == 1
        assert "Comparing algorithms: DIJKSTRA, CUSTOM" in result.output
