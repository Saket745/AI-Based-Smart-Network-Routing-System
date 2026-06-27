"""Unit tests for the Normalizer class."""

from __future__ import annotations

import pytest

from nroute.exceptions import IngestionError
from nroute.ingestion.normalizer import Normalizer


def test_normalize_topology_valid() -> None:
    """Test Normalizer.normalize_topology with valid data."""
    raw_nodes = [
        {"id": "A", "type": "router", "capacity": 1000.0},
        {"name": "B", "node_type": "switch", "location": "DC1"},
    ]
    raw_edges = [
        {"source": "A", "dst": "B", "bandwidth": 100.0, "latency": 5.0},
        {"from": "D", "target": "C", "speed": 50.0},  # D and C are auto-created
    ]

    topo = Normalizer.normalize_topology(raw_nodes, raw_edges)

    assert topo.node_count == 4
    assert "A" in topo.nodes
    assert "B" in topo.nodes
    assert "C" in topo.nodes
    assert "D" in topo.nodes

    assert topo.get_node("A")["type"] == "router"
    assert topo.get_node("B")["type"] == "switch"
    assert topo.get_node("B")["location"] == "DC1"

    assert topo.get_edge("A", "B")["bandwidth"] == 100.0
    assert topo.get_edge("D", "C")["bandwidth"] == 50.0


def test_normalize_topology_missing_node_id() -> None:
    """Test Normalizer.normalize_topology with missing node ID/name."""
    raw_nodes = [{"capacity": 1000.0}]
    raw_edges = []

    with pytest.raises(IngestionError, match="Node at index 0 is missing 'id' or 'name'"):
        Normalizer.normalize_topology(raw_nodes, raw_edges)


def test_normalize_topology_invalid_node_attrs() -> None:
    """Test Normalizer.normalize_topology with invalid node attributes."""
    raw_nodes = [{"id": "A", "type": "invalid_type"}]
    raw_edges = []

    with pytest.raises(IngestionError, match="Failed to normalize node 'A'"):
        Normalizer.normalize_topology(raw_nodes, raw_edges)


def test_normalize_topology_missing_edge_endpoints() -> None:
    """Test Normalizer.normalize_topology with missing edge source/destination."""
    raw_nodes = [{"id": "A"}, {"id": "B"}]

    # Missing destination
    raw_edges = [{"source": "A"}]
    with pytest.raises(IngestionError, match="Edge at index 0 is missing source"):
        Normalizer.normalize_topology(raw_nodes, raw_edges)

    # Missing source
    raw_edges = [{"dst": "B"}]
    with pytest.raises(IngestionError, match="Edge at index 0 is missing source"):
        Normalizer.normalize_topology(raw_nodes, raw_edges)


def test_normalize_topology_invalid_edge_attrs() -> None:
    """Test Normalizer.normalize_topology with invalid edge attributes."""
    raw_nodes = [{"id": "A"}, {"id": "B"}]
    raw_edges = [{"src": "A", "dst": "B", "bandwidth": -100.0}]

    with pytest.raises(IngestionError, match="Failed to normalize edge from 'A' to 'B'"):
        Normalizer.normalize_topology(raw_nodes, raw_edges)


def test_normalize_traffic_valid() -> None:
    """Test Normalizer.normalize_traffic with valid data."""
    raw_records = [
        {
            "source": "10.0.0.1",
            "destination": "10.0.0.2",
            "bytes": 1000,
            "packets": 10,
            "duration": 1.5,
            "protocol": "TCP",
            "timestamp": 1234567.8,
        },
        {
            "src": "10.0.0.2",
            "dst_addr": "10.0.0.3",
            "octets": 500,
            "pkts": 5,
            "proto": "UDP",
            # duration and timestamp missing, should default to 0.0
        },
    ]

    tm = Normalizer.normalize_traffic(raw_records)

    assert len(tm.flows) == 2
    assert tm.flows[0].source == "10.0.0.1"
    assert tm.flows[0].bytes == 1000
    assert tm.flows[1].source == "10.0.0.2"
    assert tm.flows[1].destination == "10.0.0.3"
    assert tm.flows[1].bytes == 500
    assert tm.flows[1].duration == 0.0
    assert tm.flows[1].timestamp == 0.0


def test_normalize_traffic_missing_fields() -> None:
    """Test Normalizer.normalize_traffic with missing required fields."""
    raw_records = [{"source": "10.0.0.1", "destination": "10.0.0.2"}]

    with pytest.raises(IngestionError, match="Flow record at index 0 is missing required fields"):
        Normalizer.normalize_traffic(raw_records)


def test_normalize_traffic_invalid_record() -> None:
    """Test Normalizer.normalize_traffic with invalid field data."""
    raw_records = [
        {
            "source": "10.0.0.1",
            "destination": "10.0.0.2",
            "bytes": "not_an_int",
            "packets": 10,
            "protocol": "TCP",
        }
    ]

    with pytest.raises(IngestionError, match="Failed to normalize flow record at index 0"):
        Normalizer.normalize_traffic(raw_records)
