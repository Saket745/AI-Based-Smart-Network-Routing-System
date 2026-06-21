"""Unit tests for the metrics models."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from nroute.core.metrics import MetricsCollectionResult, RouteMetrics, SimulationMetrics
from nroute.core.topology import Topology
from nroute.exceptions import SimulationError

if TYPE_CHECKING:
    from pathlib import Path


def test_route_metrics_from_path(small_graph_data: dict[str, Any]) -> None:
    """Test creating RouteMetrics from a path and topology."""
    edges = []
    for edge in small_graph_data.get("edges", []):
        edges.append(
            {
                "source": edge.get("src"),
                "target": edge.get("dst"),
                "bandwidth": edge.get("bandwidth"),
                "latency": edge.get("latency"),
                "utilization": edge.get("utilization"),
            }
        )
    topo = Topology.from_dict({"nodes": small_graph_data.get("nodes", []), "edges": edges})

    path = ["A", "B", "D"]
    metrics = RouteMetrics.from_path(topo, path)

    assert metrics.path == path
    # A->B latency=10, B->D latency=5 => 15
    assert metrics.total_latency == 15.0
    assert metrics.total_hops == 2
    # A->B bw=1000, B->D bw=1000 => 1000
    assert metrics.bottleneck_bandwidth == 1000.0
    assert metrics.bottleneck_utilization == 0.0


def test_metrics_collection_result_helpers() -> None:
    """Test helper methods in MetricsCollectionResult."""
    m1 = SimulationMetrics(
        tick=0,
        timestamp=0.0,
        throughput=10.0,
        avg_latency=50.0,
        packet_loss_rate=0.01,
        avg_utilization=0.2,
        reroute_count=0,
        active_flows=5,
    )
    m2 = SimulationMetrics(
        tick=1,
        timestamp=1.0,
        throughput=20.0,
        avg_latency=60.0,
        packet_loss_rate=0.02,
        avg_utilization=0.4,
        reroute_count=1,
        active_flows=10,
    )

    result = MetricsCollectionResult(results=[m1, m2])

    assert result.mean_latency() == 55.0
    assert result.total_throughput() == 30.0
    assert result.mean_throughput() == 15.0
    assert result.peak_utilization() == 0.4

    df = result.to_dataframe()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == [
        "tick",
        "timestamp",
        "throughput",
        "avg_latency",
        "packet_loss_rate",
        "avg_utilization",
        "reroute_count",
        "active_flows",
    ]


def test_metrics_collection_result_empty() -> None:
    """Test helpers with empty results."""
    result = MetricsCollectionResult(results=[])
    assert result.mean_latency() == 0.0
    assert result.mean_throughput() == 0.0
    assert result.peak_utilization() == 0.0
    df = result.to_dataframe()
    assert len(df) == 0


def test_metrics_export(tmp_path: Path) -> None:
    """Test exporting metrics to JSON and CSV."""
    m1 = SimulationMetrics(
        tick=0,
        timestamp=0.0,
        throughput=10.0,
        avg_latency=50.0,
        packet_loss_rate=0.01,
        avg_utilization=0.2,
        reroute_count=0,
        active_flows=5,
    )
    result = MetricsCollectionResult(results=[m1])

    json_path = tmp_path / "metrics.json"
    csv_path = tmp_path / "metrics.csv"

    result.to_json(json_path)
    assert json_path.exists()
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["tick"] == 0

    result.to_csv(csv_path)
    assert csv_path.exists()
    df = pd.read_csv(csv_path)
    assert len(df) == 1
    assert df.iloc[0]["tick"] == 0


def test_metrics_export_error() -> None:
    """Test handling of export errors."""
    m1 = SimulationMetrics(
        tick=0,
        timestamp=0.0,
        throughput=10.0,
        avg_latency=50.0,
        packet_loss_rate=0.01,
        avg_utilization=0.2,
        reroute_count=0,
        active_flows=5,
    )
    result = MetricsCollectionResult(results=[m1])

    with pytest.raises(SimulationError, match="Failed to export metrics"):
        result.to_json("/nonexistent/directory/metrics.json")

    with pytest.raises(SimulationError, match="Failed to export metrics"):
        result.to_csv("/nonexistent/directory/metrics.csv")
