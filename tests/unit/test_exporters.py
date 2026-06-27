"""Unit tests for topology and metrics exporters and the export CLI command."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from nroute.cli.export_cmd import export_cmd
from nroute.core.metrics import MetricsCollectionResult, SimulationMetrics
from nroute.core.topology import Topology
from nroute.visualization.exporters import MetricsExporter, TopologyExporter

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def sample_topology() -> Topology:
    """Create a sample topology for testing."""
    topo = Topology()
    topo.add_node("A", type="router", capacity=1000.0)
    topo.add_node("B", type="host", capacity=100.0)
    topo.add_edge("A", "B", bandwidth=100.0, latency=5.0)
    return topo


@pytest.fixture
def sample_metrics() -> MetricsCollectionResult:
    """Create sample simulation metrics for testing."""
    metrics = [
        SimulationMetrics(
            tick=0,
            timestamp=0.0,
            throughput=100.0,
            avg_latency=5.0,
            packet_loss_rate=0.0,
            avg_utilization=0.1,
            reroute_count=0,
            active_flows=2,
        ),
        SimulationMetrics(
            tick=1,
            timestamp=1.0,
            throughput=110.0,
            avg_latency=6.0,
            packet_loss_rate=0.01,
            avg_utilization=0.12,
            reroute_count=1,
            active_flows=3,
        ),
    ]
    return MetricsCollectionResult(results=metrics)


def test_topology_exporter_json(sample_topology: Topology, tmp_path: Path) -> None:
    """Test exporting topology to JSON."""
    out_path = tmp_path / "topo.json"
    TopologyExporter.to_json(sample_topology, out_path)

    assert out_path.exists()
    with open(out_path, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1


def test_topology_exporter_graphml(sample_topology: Topology, tmp_path: Path) -> None:
    """Test exporting topology to GraphML."""
    out_path = tmp_path / "topo.graphml"
    TopologyExporter.to_graphml(sample_topology, out_path)

    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "<graphml" in content
    assert 'id="A"' in content
    assert 'id="B"' in content


def test_topology_exporter_csv(sample_topology: Topology, tmp_path: Path) -> None:
    """Test exporting topology to CSV (nodes & edges)."""
    out_base = tmp_path / "topo.csv"
    TopologyExporter.to_csv(sample_topology, out_base)

    nodes_csv = tmp_path / "topo_nodes.csv"
    edges_csv = tmp_path / "topo_edges.csv"

    assert nodes_csv.exists()
    assert edges_csv.exists()

    nodes_content = nodes_csv.read_text(encoding="utf-8")
    edges_content = edges_csv.read_text(encoding="utf-8")

    assert "node_id,type,capacity,status,location" in nodes_content
    assert (
        "source,target,bandwidth,latency,jitter,packet_loss,utilization,weight,status"
        in edges_content
    )


def test_metrics_exporter_json(
    sample_metrics: MetricsCollectionResult, tmp_path: Path
) -> None:
    """Test exporting metrics to JSON."""
    out_path = tmp_path / "metrics.json"
    MetricsExporter.to_json(sample_metrics, out_path)

    assert out_path.exists()
    with open(out_path, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 2
    assert data[0]["tick"] == 0
    assert data[1]["active_flows"] == 3


def test_metrics_exporter_csv(
    sample_metrics: MetricsCollectionResult, tmp_path: Path
) -> None:
    """Test exporting metrics to CSV."""
    out_path = tmp_path / "metrics.csv"
    MetricsExporter.to_csv(sample_metrics, out_path)

    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert (
        "tick,timestamp,throughput,avg_latency,packet_loss_rate,avg_utilization,reroute_count,active_flows"
        in content
    )


def test_cli_export_topology(sample_topology: Topology, tmp_path: Path) -> None:
    """Test CLI command to export topology."""
    runner = CliRunner()
    in_path = tmp_path / "input_topo.json"
    sample_topology.save(in_path)

    out_path = tmp_path / "output_topo.graphml"

    result = runner.invoke(
        export_cmd,
        [
            "--type",
            "topology",
            "--format",
            "graphml",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ],
    )

    assert result.exit_code == 0
    assert "Successfully exported topology to GraphML" in result.output
    assert out_path.exists()


def test_cli_export_metrics(
    sample_metrics: MetricsCollectionResult, tmp_path: Path
) -> None:
    """Test CLI command to export metrics."""
    runner = CliRunner()
    in_path = tmp_path / "input_metrics.json"
    sample_metrics.to_json(in_path)

    out_path = tmp_path / "output_metrics.csv"

    result = runner.invoke(
        export_cmd,
        [
            "--type",
            "metrics",
            "--format",
            "csv",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ],
    )

    assert result.exit_code == 0
    assert "Successfully exported metrics to CSV" in result.output
    assert out_path.exists()


def test_cli_export_invalid_format(
    sample_metrics: MetricsCollectionResult, tmp_path: Path
) -> None:
    """Test CLI command errors for invalid combinations."""
    runner = CliRunner()
    in_path = tmp_path / "input_metrics.json"
    sample_metrics.to_json(in_path)

    out_path = tmp_path / "output_metrics.graphml"

    result = runner.invoke(
        export_cmd,
        [
            "--type",
            "metrics",
            "--format",
            "graphml",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ],
    )

    assert result.exit_code != 0
    assert "GraphML format is not supported for simulation metrics" in result.output
