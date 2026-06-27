"""Unit tests for feature engineering helpers."""

import numpy as np
import pandas as pd
import pytest

from nroute.core.traffic import FlowRecord, TrafficMatrix
from nroute.ml.feature_eng import (
    create_congestion_labels,
    extract_anomaly_features,
    extract_congestion_features,
)


@pytest.fixture
def sample_traffic() -> TrafficMatrix:
    """Fixture for a sample TrafficMatrix."""
    flows = [
        FlowRecord(
            source="10.0.0.1",
            destination="10.0.0.2",
            bytes=1000,
            packets=10,
            duration=1.0,
            protocol="TCP",
            timestamp=100.0,
        ),
        FlowRecord(
            source="10.0.0.1",
            destination="10.0.0.3",
            bytes=2000,
            packets=20,
            duration=2.0,
            protocol="UDP",
            timestamp=101.0,
        ),
        FlowRecord(
            source="10.0.0.2",
            destination="10.0.0.3",
            bytes=500,
            packets=5,
            duration=0.5,
            protocol="TCP",
            timestamp=102.0,
        ),
    ]
    return TrafficMatrix(flows=flows)


def test_extract_anomaly_features_empty():
    """Test extract_anomaly_features with an empty TrafficMatrix."""
    traffic = TrafficMatrix(flows=[])
    df = extract_anomaly_features(traffic)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df.iloc[0]["flow_count"] == 0
    assert df.iloc[0]["bytes_per_second"] == 0.0
    assert df.iloc[0]["packets_per_second"] == 0.0


def test_extract_anomaly_features_basic(sample_traffic):
    """Test extract_anomaly_features with a sample TrafficMatrix."""
    df = extract_anomaly_features(sample_traffic)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1

    row = df.iloc[0]
    assert row["flow_count"] == 3

    # Total bytes = 1000 + 2000 + 500 = 3500
    # Total packets = 10 + 20 + 5 = 35
    # Max time = max(100+1, 101+2, 102+0.5) = max(101, 103, 102.5) = 103
    # Min time = min(100, 101, 102) = 100
    # Duration = 103 - 100 = 3.0

    assert row["bytes_per_second"] == pytest.approx(3500 / 3.0)
    assert row["packets_per_second"] == pytest.approx(35 / 3.0)
    assert row["avg_packet_size"] == pytest.approx(3500 / 35)

    # Entropy calculations:
    # Sources: ["10.0.0.1", "10.0.0.1", "10.0.0.2"]
    # Counts: {"10.0.0.1": 2, "10.0.0.2": 1}
    # Probabilities: {2/3, 1/3}
    # Entropy: -(2/3 * log2(2/3) + 1/3 * log2(1/3))
    expected_entropy = -(2 / 3 * np.log2(2 / 3) + 1 / 3 * np.log2(1 / 3))
    assert row["src_ip_entropy"] == pytest.approx(expected_entropy)

    # Destinations: ["10.0.0.2", "10.0.0.3", "10.0.0.3"]
    # Same as sources entropy
    assert row["dst_ip_entropy"] == pytest.approx(expected_entropy)

    # Protocols: ["TCP", "UDP", "TCP"]
    # Same as sources entropy
    assert row["protocol_entropy"] == pytest.approx(expected_entropy)

    # Bytes std
    expected_std = np.std([1000, 2000, 500])
    assert row["bytes_std"] == pytest.approx(expected_std)


def test_extract_anomaly_features_single_flow():
    """Test extract_anomaly_features with a single flow."""
    flow = FlowRecord(
        source="10.0.0.1",
        destination="10.0.0.2",
        bytes=1000,
        packets=10,
        duration=1.0,
        protocol="TCP",
        timestamp=100.0,
    )
    traffic = TrafficMatrix(flows=[flow])
    df = extract_anomaly_features(traffic)

    row = df.iloc[0]
    assert row["flow_count"] == 1
    assert row["src_ip_entropy"] == 0.0
    assert row["dst_ip_entropy"] == 0.0
    assert row["protocol_entropy"] == 0.0
    assert row["bytes_std"] == 0.0


def test_extract_anomaly_features_zero_packets():
    """Test extract_anomaly_features with flows having zero packets."""
    flow = FlowRecord(
        source="10.0.0.1",
        destination="10.0.0.2",
        bytes=1000,
        packets=0,
        duration=1.0,
        protocol="TCP",
        timestamp=100.0,
    )
    traffic = TrafficMatrix(flows=[flow])
    df = extract_anomaly_features(traffic)

    row = df.iloc[0]
    assert row["avg_packet_size"] == 0.0


def test_extract_congestion_features_basic():
    """Test extract_congestion_features with a sample Topology."""
    from nroute.core.topology import Topology

    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    topo.add_edge("A", "B", bandwidth=1000.0, latency=5.0, utilization=0.5)
    topo.add_edge("B", "C", bandwidth=2000.0, latency=10.0, utilization=0.2)

    df = extract_congestion_features(topo, [], lag_ticks=2)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "A->B" in df.index
    assert "B->C" in df.index

    # Check A->B features
    row_ab = df.loc["A->B"]
    assert row_ab["bandwidth"] == 1000.0
    assert row_ab["latency"] == 5.0
    assert row_ab["utilization_t"] == 0.5
    # Lags for A->B: 0.5 * 0.8^1 = 0.4, 0.5 * 0.8^2 = 0.32
    assert row_ab["utilization_t_1"] == pytest.approx(0.4)
    assert row_ab["utilization_t_2"] == pytest.approx(0.32)
    # Neighbor of B is C, which has utilization 0.2 (for edge B->C)
    # Wait, the code says:
    # for _, neighbor_data in topology.graph[v].items():
    #     neighbor_utils.append(float(neighbor_data.get("utilization", 0.0)))
    # For A->B, v is B. neighbors of B in directed graph are nodes it has edges TO.
    # So neighbor is C, edge B->C has utilization 0.2.
    assert row_ab["neighbor_utilization_avg"] == pytest.approx(0.2)


def test_extract_congestion_features_no_neighbors():
    """Test extract_congestion_features when a node has no outgoing edges."""
    from nroute.core.topology import Topology

    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_edge("A", "B", utilization=0.5)
    # B has no outgoing edges

    df = extract_congestion_features(topo, [])
    row_ab = df.loc["A->B"]
    assert row_ab["neighbor_utilization_avg"] == 0.0


def test_create_congestion_labels_basic():
    """Test create_congestion_labels with a sample Topology."""
    from nroute.core.topology import Topology

    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_edge("A", "B", utilization=0.9)
    topo.add_edge("B", "A", utilization=0.5)

    labels = create_congestion_labels(topo, threshold=0.8)

    # Order depends on topo.graph.edges(data=True)
    # Expected: [1, 0] if (A,B) then (B,A)
    assert len(labels) == 2
    assert (labels == np.array([1, 0])).all() or (labels == np.array([0, 1])).all()


def test_extract_congestion_features_empty():
    """Test extract_congestion_features with an empty Topology."""
    from nroute.core.topology import Topology

    topo = Topology()
    df = extract_congestion_features(topo, [])
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_create_congestion_labels_empty():
    """Test create_congestion_labels with an empty Topology."""
    from nroute.core.topology import Topology

    topo = Topology()
    labels = create_congestion_labels(topo)
    assert isinstance(labels, np.ndarray)
    assert len(labels) == 0


def test_extract_anomaly_features_duration_less_than_one():
    """Test extract_anomaly_features when duration is less than 1.0."""
    # duration = max_time - min_time
    # flow 1: timestamp=100.0, duration=0.1 -> end=100.1
    # max_time = 100.1, min_time = 100.0 -> diff = 0.1
    # Code uses duration = max(1.0, max_time - min_time), so it should be 1.0
    flow = FlowRecord(
        source="10.0.0.1",
        destination="10.0.0.2",
        bytes=1000,
        packets=10,
        duration=0.1,
        protocol="TCP",
        timestamp=100.0,
    )
    traffic = TrafficMatrix(flows=[flow])
    df = extract_anomaly_features(traffic)

    row = df.iloc[0]
    # Total bytes 1000, duration 1.0
    assert row["bytes_per_second"] == 1000.0
