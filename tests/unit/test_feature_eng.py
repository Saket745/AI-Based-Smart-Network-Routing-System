"""Unit tests for feature engineering modules."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nroute.core.topology import Topology
from nroute.core.traffic import FlowRecord, TrafficMatrix
from nroute.ml.feature_eng import (
    create_congestion_labels,
    extract_anomaly_features,
    extract_congestion_features,
)


@pytest.fixture
def sample_topology() -> Topology:
    """Create a sample topology for testing."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    # A -> B: 50% util
    topo.add_edge("A", "B", bandwidth=1000.0, latency=5.0, utilization=0.5)
    # B -> C: 90% util
    topo.add_edge("B", "C", bandwidth=1000.0, latency=2.0, utilization=0.9)
    return topo


@pytest.fixture
def sample_traffic() -> TrafficMatrix:
    """Create a sample traffic matrix for testing."""
    flows = [
        FlowRecord(
            source="A",
            destination="B",
            bytes=1000,
            packets=10,
            duration=1.0,
            protocol="TCP",
            timestamp=100.0,
        ),
        FlowRecord(
            source="A",
            destination="C",
            bytes=500,
            packets=5,
            duration=1.0,
            protocol="UDP",
            timestamp=101.0,
        ),
    ]
    return TrafficMatrix(flows=flows)


def test_extract_congestion_features(sample_topology: Topology) -> None:
    """Test extraction of congestion features for links."""
    traffic_history: list[TrafficMatrix] = []
    df = extract_congestion_features(sample_topology, traffic_history, lag_ticks=3)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2  # Two edges: A->B and B->C
    assert "bandwidth" in df.columns
    assert "latency" in df.columns
    assert "utilization_t" in df.columns
    assert "neighbor_utilization_avg" in df.columns
    assert "utilization_t_1" in df.columns
    assert "utilization_t_2" in df.columns
    assert "utilization_t_3" in df.columns

    # Check specific values for A->B
    row_ab = df.loc["A->B"]
    assert row_ab["bandwidth"] == 1000.0
    assert row_ab["latency"] == 5.0
    assert row_ab["utilization_t"] == 0.5
    # B->C is neighbor of A->B (destination of A->B is B, B has edge to C)
    assert row_ab["neighbor_utilization_avg"] == 0.9

    # Check lag calculation (0.5 * 0.8^1 = 0.4, 0.5 * 0.8^2 = 0.32)
    assert pytest.approx(row_ab["utilization_t_1"]) == 0.4
    assert pytest.approx(row_ab["utilization_t_2"]) == 0.32

    # Check B->C
    row_bc = df.loc["B->C"]
    assert row_bc["utilization_t"] == 0.9
    # B->C has no outgoing neighbors from C in this topo
    assert row_bc["neighbor_utilization_avg"] == 0.0


def test_extract_congestion_features_no_history(sample_topology: Topology) -> None:
    """Test congestion features with zero lag ticks."""
    df = extract_congestion_features(sample_topology, [], lag_ticks=0)
    assert "utilization_t" in df.columns
    # Should not have lag columns
    assert "utilization_t_1" not in df.columns


def test_extract_anomaly_features(sample_traffic: TrafficMatrix) -> None:
    """Test extraction of anomaly features from traffic flows."""
    df = extract_anomaly_features(sample_traffic)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    cols = [
        "bytes_per_second",
        "packets_per_second",
        "flow_count",
        "avg_packet_size",
        "src_ip_entropy",
        "dst_ip_entropy",
        "protocol_entropy",
        "bytes_std",
    ]
    for col in cols:
        assert col in df.columns

    assert df.iloc[0]["flow_count"] == 2
    # total bytes = 1500
    # max_time = 101.0 + 1.0 = 102.0
    # min_time = 100.0
    # duration = 102.0 - 100.0 = 2.0
    # bytes/sec = 1500 / 2.0 = 750.0
    assert df.iloc[0]["bytes_per_second"] == 750.0
    assert df.iloc[0]["packets_per_second"] == 15 / 2.0
    assert df.iloc[0]["avg_packet_size"] == 1500 / 15


def test_extract_anomaly_features_empty() -> None:
    """Test anomaly features with empty traffic matrix."""
    tm = TrafficMatrix(flows=[])
    df = extract_anomaly_features(tm)
    assert len(df) == 1
    assert df.iloc[0]["flow_count"] == 0
    assert df.iloc[0]["bytes_per_second"] == 0.0
    assert df.iloc[0]["src_ip_entropy"] == 0.0


def test_extract_anomaly_features_single_flow() -> None:
    """Test anomaly features with a single flow (duration floor check)."""
    tm = TrafficMatrix(
        flows=[
            FlowRecord(
                source="A",
                destination="B",
                bytes=1000,
                packets=10,
                duration=0.1,
                protocol="TCP",
                timestamp=100.0,
            )
        ]
    )
    df = extract_anomaly_features(tm)
    # max_time = 100.1, min_time = 100.0, diff = 0.1. Duration floored at 1.0
    assert df.iloc[0]["bytes_per_second"] == 1000.0
    assert df.iloc[0]["src_ip_entropy"] == 0.0  # Only one source


def test_create_congestion_labels(sample_topology: Topology) -> None:
    """Test creation of binary congestion labels."""
    # A->B: 0.5, B->C: 0.9
    labels = create_congestion_labels(sample_topology, threshold=0.8)
    assert isinstance(labels, np.ndarray)
    assert len(labels) == 2
    # Assuming edge order is insertion order in NetworkX
    assert list(labels) == [0, 1]

    # Test different threshold
    labels_low = create_congestion_labels(sample_topology, threshold=0.4)
    assert list(labels_low) == [1, 1]


def test_extract_congestion_features_no_neighbors() -> None:
    """Test congestion features when a node has no outgoing edges."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    # A -> B, but B has no neighbors
    topo.add_edge("A", "B", utilization=0.5)

    df = extract_congestion_features(topo, [])
    assert df.loc["A->B"]["neighbor_utilization_avg"] == 0.0
