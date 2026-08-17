"""Unit tests for the Ingestion Normalizer."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from nroute.exceptions import IngestionError
from nroute.ingestion.normalizer import Normalizer


def test_normalize_traffic_happy_path() -> None:
    """Test Normalizer.normalize_traffic with complete and standard field names."""
    raw_records = [
        {
            "source": "10.0.0.1",
            "destination": "10.0.0.2",
            "bytes": 5000,
            "packets": 10,
            "duration": 2.5,
            "protocol": "TCP",
            "timestamp": 123456.7,
        },
        {
            "source": "10.0.0.3",
            "destination": "10.0.0.4",
            "bytes": 200,
            "packets": 2,
            "duration": 0.1,
            "protocol": "UDP",
            "timestamp": 123458.0,
        },
    ]

    tm = Normalizer.normalize_traffic(raw_records)
    assert len(tm.flows) == 2

    flow1 = tm.flows[0]
    assert flow1.source == "10.0.0.1"
    assert flow1.destination == "10.0.0.2"
    assert flow1.bytes == 5000
    assert flow1.packets == 10
    assert flow1.duration == 2.5
    assert flow1.protocol == "TCP"
    assert flow1.timestamp == 123456.7

    flow2 = tm.flows[1]
    assert flow2.source == "10.0.0.3"
    assert flow2.destination == "10.0.0.4"
    assert flow2.bytes == 200
    assert flow2.packets == 2
    assert flow2.duration == 0.1
    assert flow2.protocol == "UDP"
    assert flow2.timestamp == 123458.0


def test_normalize_traffic_defaults() -> None:
    """Test that missing duration and timestamp default to 0.0."""
    raw_records = [
        {
            "source": "10.0.0.1",
            "destination": "10.0.0.2",
            "bytes": 5000,
            "packets": 10,
            "protocol": "TCP",
            # duration and timestamp omitted or None
            "duration": None,
            "timestamp": None,
        }
    ]

    tm = Normalizer.normalize_traffic(raw_records)
    assert len(tm.flows) == 1
    flow = tm.flows[0]
    assert flow.duration == 0.0
    assert flow.timestamp == 0.0


@pytest.mark.parametrize(
    ("src_key", "dst_key", "bytes_key", "packets_key", "proto_key", "time_key"),
    [
        ("src", "dst", "octets", "pkts", "proto", "time"),
        ("src_ip", "dst_ip", "dOctets", "dPkts", "protocol", "first_switched"),
        ("src_addr", "dst_addr", "bytes", "packets", "protocol", "last_switched"),
    ],
)
def test_normalize_traffic_fallback_mappings(
    src_key: str,
    dst_key: str,
    bytes_key: str,
    packets_key: str,
    proto_key: str,
    time_key: str,
) -> None:
    """Test all fallback sequences and alternate field names."""
    raw_records: list[dict[str, Any]] = [
        {
            src_key: "10.0.0.5",
            dst_key: "10.0.0.6",
            bytes_key: "1000",
            packets_key: "5",
            proto_key: "ICMP",
            time_key: "999.9",
        }
    ]

    tm = Normalizer.normalize_traffic(raw_records)
    assert len(tm.flows) == 1
    flow = tm.flows[0]
    assert flow.source == "10.0.0.5"
    assert flow.destination == "10.0.0.6"
    assert flow.bytes == 1000
    assert flow.packets == 5
    assert flow.protocol == "ICMP"
    assert flow.timestamp == 999.9


@pytest.mark.parametrize(
    "missing_field",
    ["source", "destination", "bytes", "packets", "protocol"],
)
def test_normalize_traffic_missing_required_fields(missing_field: str) -> None:
    """Test that missing required fields raises an IngestionError."""
    base_record = {
        "source": "10.0.0.1",
        "destination": "10.0.0.2",
        "bytes": 5000,
        "packets": 10,
        "protocol": "TCP",
    }
    # Delete the target field, along with any possible fallbacks to avoid matching
    if missing_field == "source":
        for k in ["source", "src", "src_ip", "src_addr"]:
            base_record.pop(k, None)
    elif missing_field == "destination":
        for k in ["destination", "dst", "dst_ip", "dst_addr"]:
            base_record.pop(k, None)
    elif missing_field == "bytes":
        for k in ["bytes", "octets", "dOctets"]:
            base_record.pop(k, None)
    elif missing_field == "packets":
        for k in ["packets", "pkts", "dPkts"]:
            base_record.pop(k, None)
    elif missing_field == "protocol":
        for k in ["protocol", "proto"]:
            base_record.pop(k, None)

    with pytest.raises(IngestionError, match=r"is missing required fields"):
        Normalizer.normalize_traffic([base_record])


def test_normalize_traffic_type_conversion_failure() -> None:
    """Test that invalid types for int/float fields raise IngestionError."""
    record_bad_bytes = {
        "source": "10.0.0.1",
        "destination": "10.0.0.2",
        "bytes": "not-an-int",
        "packets": 10,
        "protocol": "TCP",
    }
    with pytest.raises(IngestionError, match=r"Failed to normalize flow record at index 0"):
        Normalizer.normalize_traffic([record_bad_bytes])

    record_bad_packets = {
        "source": "10.0.0.1",
        "destination": "10.0.0.2",
        "bytes": 5000,
        "packets": "not-an-int",
        "protocol": "TCP",
    }
    with pytest.raises(IngestionError, match=r"Failed to normalize flow record at index 0"):
        Normalizer.normalize_traffic([record_bad_packets])

    record_bad_duration = {
        "source": "10.0.0.1",
        "destination": "10.0.0.2",
        "bytes": 5000,
        "packets": 10,
        "protocol": "TCP",
        "duration": "not-a-float",
    }
    with pytest.raises(IngestionError, match=r"Failed to normalize flow record at index 0"):
        Normalizer.normalize_traffic([record_bad_duration])


def test_normalize_topology_happy_path() -> None:
    """Test Normalizer.normalize_topology with valid raw nodes and edges."""
    raw_nodes = [
        {"id": "node1", "type": "router", "capacity": 1000},
        {"name": "node2", "node_type": "switch"},
    ]
    raw_edges = [
        {"source": "node1", "destination": "node2", "bandwidth": 10.0, "latency": 1.0},
    ]

    topo = Normalizer.normalize_topology(raw_nodes, raw_edges)
    assert topo.node_count == 2
    assert topo.edge_count == 1

    assert "node1" in topo.nodes
    assert topo.get_node("node1")["type"] == "router"
    assert topo.get_node("node1")["capacity"] == 1000

    assert "node2" in topo.nodes
    assert topo.get_node("node2")["type"] == "switch"

    assert topo.get_edge("node1", "node2")["bandwidth"] == 10.0
    assert topo.get_edge("node1", "node2")["latency"] == 1.0


def test_normalize_topology_missing_node_id() -> None:
    """Test that node missing ID/name raises IngestionError."""
    raw_nodes = [{"capacity": 1000}]
    with pytest.raises(IngestionError, match=r"Node at index 0 is missing 'id' or 'name'"):
        Normalizer.normalize_topology(raw_nodes, [])


def test_normalize_topology_missing_edge_endpoints() -> None:
    """Test that edge missing source or destination raises IngestionError."""
    raw_nodes = [{"id": "node1"}]
    raw_edges_no_dst = [{"source": "node1"}]
    with pytest.raises(IngestionError, match=r"Edge at index 0 is missing source"):
        Normalizer.normalize_topology(raw_nodes, raw_edges_no_dst)


def test_normalize_topology_edge_speed_fallback() -> None:
    """Test that speed field maps to bandwidth on edges."""
    raw_nodes = [{"id": "A"}, {"id": "B"}]
    raw_edges = [{"from": "A", "to": "B", "speed": 40.0}]

    topo = Normalizer.normalize_topology(raw_nodes, raw_edges)
    assert topo.get_edge("A", "B")["bandwidth"] == 40.0


def test_normalize_topology_exceptions() -> None:
    """Test that exception raised during node or edge creation is wrapped in IngestionError."""
    with (
        patch("nroute.core.topology.Topology.add_node", side_effect=ValueError("Mock Error")),
        pytest.raises(IngestionError, match=r"Failed to normalize node 'A'"),
    ):
        Normalizer.normalize_topology([{"id": "A"}], [])

    with (
        patch("nroute.core.topology.Topology.add_edge", side_effect=ValueError("Mock Edge Error")),
        pytest.raises(IngestionError, match=r"Failed to normalize edge from 'A' to 'B'"),
    ):
        Normalizer.normalize_topology([{"id": "A"}, {"id": "B"}], [{"from": "A", "to": "B"}])
