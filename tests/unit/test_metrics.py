from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from pydantic import ValidationError

from nroute.core.metrics import MetricsCollectionResult, RouteMetrics, SimulationMetrics
from nroute.core.topology import Topology
from nroute.exceptions import SimulationError


def _get_topo(small_graph_data: dict[str, Any]) -> Topology:
    """Helper to convert test fixture graph data schema to Topology.from_dict structure."""
    edges = []
    for edge in small_graph_data.get("edges", []):
        edges.append(
            {
                "source": edge.get("src"),
                "target": edge.get("dst"),
                "bandwidth": edge.get("bandwidth"),
                "latency": edge.get("latency"),
                "jitter": edge.get("jitter"),
                "packet_loss": edge.get("packet_loss"),
                "utilization": edge.get("utilization"),
                "status": edge.get("status"),
            }
        )
    data = {"nodes": small_graph_data.get("nodes", []), "edges": edges}
    return Topology.from_dict(data)


def test_route_metrics_init() -> None:
    """Test basic initialization of RouteMetrics."""
    metrics = RouteMetrics(
        path=["A", "B", "D"],
        total_latency=15.0,
        total_hops=2,
        bottleneck_bandwidth=1000.0,
        bottleneck_utilization=0.1,
    )
    assert metrics.path == ["A", "B", "D"]
    assert metrics.total_latency == 15.0
    assert metrics.total_hops == 2
    assert metrics.bottleneck_bandwidth == 1000.0
    assert metrics.bottleneck_utilization == 0.1


def test_route_metrics_validation() -> None:
    """Test Pydantic validation for RouteMetrics."""
    with pytest.raises(ValidationError):
        RouteMetrics(
            path=["A"],
            total_latency=-1.0,  # Should be >= 0
            total_hops=0,
            bottleneck_bandwidth=100.0,
            bottleneck_utilization=0.0,
        )


def test_route_metrics_from_path(small_graph_data: dict[str, Any]) -> None:
    """Test RouteMetrics.from_path factory method."""
    topo = _get_topo(small_graph_data)
    path = ["A", "B", "D"]
    metrics = RouteMetrics.from_path(topo, path)

    assert metrics.path == path
    # A->B (10ms, 1000Mbps, 0.0 util), B->D (5ms, 1000Mbps, 0.0 util)
    assert metrics.total_latency == 15.0
    assert metrics.total_hops == 2
    assert metrics.bottleneck_bandwidth == 1000.0
    assert metrics.bottleneck_utilization == 0.0

    # Test alternative path A -> C -> E -> D
    # A->C (15ms, 500Mbps, 0.0), C->E (7ms, 500Mbps, 0.0), E->D (3ms, 800Mbps, 0.0)
    path2 = ["A", "C", "E", "D"]
    metrics2 = RouteMetrics.from_path(topo, path2)
    assert metrics2.total_latency == 25.0
    assert metrics2.total_hops == 3
    assert metrics2.bottleneck_bandwidth == 500.0


def test_route_metrics_from_path_missing_edge(small_graph_data: dict[str, Any]) -> None:
    """Test RouteMetrics.from_path with missing edges in path."""
    topo = _get_topo(small_graph_data)
    # A and D are not connected directly
    path = ["A", "D"]
    metrics = RouteMetrics.from_path(topo, path)

    assert metrics.path == path
    assert metrics.total_latency == 0.0  # Exception caught in loop
    assert metrics.total_hops == 1
    assert metrics.bottleneck_bandwidth == float("inf")


def test_simulation_metrics_init() -> None:
    """Test basic initialization of SimulationMetrics."""
    metrics = SimulationMetrics(
        tick=1,
        timestamp=1.0,
        throughput=100.0,
        avg_latency=5.0,
        packet_loss_rate=0.01,
        avg_utilization=0.4,
        reroute_count=2,
        active_flows=10,
    )
    assert metrics.tick == 1
    assert metrics.throughput == 100.0


def test_metrics_collection_result_helpers() -> None:
    """Test analysis helpers in MetricsCollectionResult."""
    results = [
        SimulationMetrics(
            tick=0,
            timestamp=0.0,
            throughput=100.0,
            avg_latency=10.0,
            packet_loss_rate=0.0,
            avg_utilization=0.2,
            reroute_count=0,
            active_flows=5,
        ),
        SimulationMetrics(
            tick=1,
            timestamp=1.0,
            throughput=200.0,
            avg_latency=20.0,
            packet_loss_rate=0.1,
            avg_utilization=0.4,
            reroute_count=5,
            active_flows=10,
        ),
    ]
    collection = MetricsCollectionResult(results=results)

    assert collection.mean_latency() == 15.0
    assert collection.total_throughput() == 300.0
    assert collection.mean_throughput() == 150.0
    assert collection.peak_utilization() == 0.4


def test_metrics_collection_empty() -> None:
    """Test MetricsCollectionResult helpers with empty results."""
    collection = MetricsCollectionResult()
    assert collection.mean_latency() == 0.0
    assert collection.total_throughput() == 0.0
    assert collection.mean_throughput() == 0.0
    assert collection.peak_utilization() == 0.0


def test_metrics_collection_to_dataframe() -> None:
    """Test conversion to pandas DataFrame."""
    results = [
        SimulationMetrics(
            tick=0,
            timestamp=0.0,
            throughput=100.0,
            avg_latency=10.0,
            packet_loss_rate=0.0,
            avg_utilization=0.2,
            reroute_count=0,
            active_flows=5,
        )
    ]
    collection = MetricsCollectionResult(results=results)
    df = collection.to_dataframe()

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df.iloc[0]["throughput"] == 100.0

    # Test empty collection to dataframe
    empty_df = MetricsCollectionResult().to_dataframe()
    assert isinstance(empty_df, pd.DataFrame)
    assert len(empty_df) == 0
    assert "throughput" in empty_df.columns


def test_metrics_collection_export(tmp_output_dir: Path) -> None:
    """Test export to JSON and CSV."""
    results = [
        SimulationMetrics(
            tick=0,
            timestamp=0.0,
            throughput=100.0,
            avg_latency=10.0,
            packet_loss_rate=0.0,
            avg_utilization=0.2,
            reroute_count=0,
            active_flows=5,
        )
    ]
    collection = MetricsCollectionResult(results=results)

    json_path = tmp_output_dir / "metrics.json"
    collection.to_json(json_path)
    assert json_path.exists()
    with open(json_path) as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["tick"] == 0

    csv_path = tmp_output_dir / "metrics.csv"
    collection.to_csv(csv_path)
    assert csv_path.exists()
    df = pd.read_csv(csv_path)
    assert len(df) == 1
    assert df.iloc[0]["tick"] == 0


def test_metrics_collection_export_error() -> None:
    """Test error handling during export."""
    collection = MetricsCollectionResult()
    # Invalid path (e.g., using a directory as a filename or empty path)
    with pytest.raises(SimulationError):
        collection.to_json("")

    with pytest.raises(SimulationError):
        collection.to_csv("")
