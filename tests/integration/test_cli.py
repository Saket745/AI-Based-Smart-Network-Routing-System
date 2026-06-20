"""Integration tests for the nroute CLI command suite."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
from click.testing import CliRunner

from nroute.cli import cli
from nroute.core.generators import TopologyGenerator


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def topo_file(tmp_path: Path) -> str:
    """Generate a small topology and save it to a temp file."""
    topo = TopologyGenerator.random(n_nodes=6, edge_prob=0.5, seed=42)
    filepath = str(tmp_path / "test_topo.json")
    topo.save(filepath)
    return filepath


# ── topology commands ────────────────────────────────────────


class TestTopologyCLI:
    """Tests for the `nroute topology` subcommands."""

    def test_topology_generate_to_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """topology generate --type random --output should create a valid JSON file."""
        output_path = str(tmp_path / "generated.json")
        result = runner.invoke(
            cli,
            [
                "topology",
                "generate",
                "--type",
                "random",
                "--nodes",
                "8",
                "--edge-prob",
                "0.4",
                "--seed",
                "42",
                "--output",
                output_path,
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert os.path.exists(output_path)
        # Verify it's valid JSON
        with open(output_path) as f:
            data = json.load(f)
        assert "nodes" in data
        assert "edges" in data

    def test_topology_generate_stdout(self, runner: CliRunner) -> None:
        """topology generate without --output should print a summary."""
        result = runner.invoke(
            cli,
            [
                "topology",
                "generate",
                "--type",
                "random",
                "--nodes",
                "5",
                "--edge-prob",
                "0.5",
                "--seed",
                "42",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "Nodes" in result.output
        assert "Edges" in result.output

    def test_topology_generate_fat_tree(self, runner: CliRunner, tmp_path: Path) -> None:
        """topology generate --type fat-tree should work."""
        output_path = str(tmp_path / "fat_tree.json")
        result = runner.invoke(
            cli,
            ["topology", "generate", "--type", "fat-tree", "--k", "4", "--output", output_path],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert os.path.exists(output_path)

    def test_topology_show(self, runner: CliRunner, topo_file: str) -> None:
        """topology show should display topology details."""
        result = runner.invoke(
            cli,
            ["topology", "show", "--file", topo_file],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "Nodes" in result.output

    def test_topology_show_missing_file(self, runner: CliRunner) -> None:
        """topology show with a nonexistent file should fail."""
        result = runner.invoke(
            cli,
            ["topology", "show", "--file", "/nonexistent/path.json"],
        )
        assert result.exit_code != 0


# ── route commands ───────────────────────────────────────────


class TestRouteCLI:
    """Tests for the `nroute route` subcommands."""

    def test_route_compute_dijkstra(self, runner: CliRunner, topo_file: str) -> None:
        """route compute should find a path between valid nodes."""
        result = runner.invoke(
            cli,
            [
                "route",
                "compute",
                "--topology",
                topo_file,
                "--algorithm",
                "dijkstra",
                "--source",
                "0",
                "--destination",
                "5",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "Path" in result.output or "Route" in result.output

    def test_route_compute_bellman_ford(self, runner: CliRunner, topo_file: str) -> None:
        """route compute with bellman-ford should work."""
        result = runner.invoke(
            cli,
            [
                "route",
                "compute",
                "--topology",
                topo_file,
                "--algorithm",
                "bellman-ford",
                "--source",
                "0",
                "--destination",
                "5",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0

    def test_route_compute_invalid_node(self, runner: CliRunner, topo_file: str) -> None:
        """route compute with invalid source should exit with error."""
        result = runner.invoke(
            cli,
            [
                "route",
                "compute",
                "--topology",
                topo_file,
                "--algorithm",
                "dijkstra",
                "--source",
                "NONEXISTENT",
                "--destination",
                "0",
            ],
        )
        assert result.exit_code != 0


# ── simulate commands ────────────────────────────────────────


class TestSimulateCLI:
    """Tests for the `nroute simulate` subcommands."""

    def test_simulate_run(self, runner: CliRunner, topo_file: str, tmp_path: Path) -> None:
        """simulate run should complete and optionally save metrics."""
        output_path = str(tmp_path / "sim_results.json")
        result = runner.invoke(
            cli,
            [
                "simulate",
                "run",
                "--topology",
                topo_file,
                "--algorithm",
                "dijkstra",
                "--duration",
                "10",
                "--seed",
                "42",
                "--output",
                output_path,
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert os.path.exists(output_path)
        with open(output_path) as f:
            data = json.load(f)
        assert "total_throughput" in data
        assert "mean_latency" in data

    def test_simulate_compare(self, runner: CliRunner, topo_file: str) -> None:
        """simulate compare should produce a comparison table."""
        result = runner.invoke(
            cli,
            [
                "simulate",
                "compare",
                "--topology",
                topo_file,
                "--algorithms",
                "dijkstra,bellman-ford",
                "--duration",
                "10",
                "--seed",
                "42",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "DIJKSTRA" in result.output
        assert "BELLMAN-FORD" in result.output

    def test_simulate_compare_too_few_algos(self, runner: CliRunner, topo_file: str) -> None:
        """simulate compare with only one algorithm should fail."""
        result = runner.invoke(
            cli,
            [
                "simulate",
                "compare",
                "--topology",
                topo_file,
                "--algorithms",
                "dijkstra",
                "--duration",
                "10",
            ],
        )
        assert result.exit_code != 0


# ── version and help ─────────────────────────────────────────


class TestCLIHelp:
    """Tests for global CLI options."""

    def test_version(self, runner: CliRunner) -> None:
        """--version should display the version."""
        result = runner.invoke(cli, ["--version"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self, runner: CliRunner) -> None:
        """--help should display usage information."""
        result = runner.invoke(cli, ["--help"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "nroute" in result.output
        assert "topology" in result.output
        assert "route" in result.output
        assert "simulate" in result.output
        assert "train" in result.output
        assert "predict" in result.output
        assert "detect" in result.output

    def test_no_args_shows_help(self, runner: CliRunner) -> None:
        """Running nroute with no args should show help."""
        result = runner.invoke(cli, [], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Usage" in result.output or "nroute" in result.output


# ── train commands ───────────────────────────────────────────


class TestTrainCLI:
    """Tests for the `nroute train` subcommands."""

    def test_train_congestion(self, runner: CliRunner, topo_file: str, tmp_path: Path) -> None:
        """train congestion should successfully output a joblib file."""
        output_path = str(tmp_path / "congestion.joblib")
        result = runner.invoke(
            cli,
            [
                "train",
                "congestion",
                "--topology",
                topo_file,
                "--model-type",
                "xgboost",
                "--output",
                output_path,
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert os.path.exists(output_path)

    def test_train_anomaly(self, runner: CliRunner, topo_file: str, tmp_path: Path) -> None:
        """train anomaly should successfully output a joblib file."""
        output_path = str(tmp_path / "anomaly.joblib")
        result = runner.invoke(
            cli,
            [
                "train",
                "anomaly",
                "--topology",
                topo_file,
                "--model-type",
                "isolation_forest",
                "--output",
                output_path,
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert os.path.exists(output_path)

    def test_train_rl(self, runner: CliRunner, topo_file: str, tmp_path: Path) -> None:
        """train rl should successfully save the RL model zip and metadata."""
        output_path = str(tmp_path / "rl_model")
        result = runner.invoke(
            cli,
            [
                "train",
                "rl",
                "--topology",
                topo_file,
                "--algorithm",
                "ppo",
                "--timesteps",
                "20",
                "--output",
                output_path,
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert os.path.exists(f"{output_path}.zip")
        assert os.path.exists(f"{output_path}.meta")


# ── predict commands ─────────────────────────────────────────


class TestPredictCLI:
    """Tests for the `nroute predict` subcommands."""

    def test_predict_congestion(self, runner: CliRunner, topo_file: str, tmp_path: Path) -> None:
        """predict congestion should read the topology and model, and print predictions."""
        # 1. Train the model first
        model_path = str(tmp_path / "congestion.joblib")
        runner.invoke(
            cli,
            [
                "train",
                "congestion",
                "--topology",
                topo_file,
                "--model-type",
                "xgboost",
                "--output",
                model_path,
            ],
            catch_exceptions=False,
        )
        assert os.path.exists(model_path)

        # 2. Run prediction
        result = runner.invoke(
            cli,
            ["predict", "congestion", "--topology", topo_file, "--model", model_path, "--allow-unsafe"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "Congestion Predictions" in result.output
        assert (
            "NORMAL" in result.output or "CONGESTED" in result.output or "AT RISK" in result.output
        )


# ── detect commands ──────────────────────────────────────────


class TestDetectCLI:
    """Tests for the `nroute detect` subcommands."""

    def test_detect_anomalies(self, runner: CliRunner, topo_file: str, tmp_path: Path) -> None:
        """detect anomalies should read the traffic features CSV and model, and print anomalies."""
        # 1. Train anomaly model
        model_path = str(tmp_path / "anomaly.joblib")
        runner.invoke(
            cli,
            [
                "train",
                "anomaly",
                "--topology",
                topo_file,
                "--model-type",
                "isolation_forest",
                "--output",
                model_path,
            ],
            catch_exceptions=False,
        )
        assert os.path.exists(model_path)

        # 2. Generate dummy traffic features CSV
        traffic_csv = tmp_path / "traffic.csv"
        import pandas as pd

        df = pd.DataFrame(
            {
                "bytes_per_second": [5000.0, 1000000.0],
                "packets_per_second": [50.0, 10000.0],
                "flow_count": [5, 100],
                "avg_packet_size": [500.0, 1500.0],
                "src_ip_entropy": [3.0, 0.5],
                "dst_port_entropy": [2.5, 0.2],
                "utilization": [0.2, 0.95],
                "latency_avg": [5.0, 150.0],
            }
        )
        df.to_csv(traffic_csv, index=False)

        # 3. Run detection
        result = runner.invoke(
            cli,
            ["detect", "anomalies", "--traffic", str(traffic_csv), "--model", model_path, "--allow-unsafe"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "Anomaly Detection Results" in result.output
