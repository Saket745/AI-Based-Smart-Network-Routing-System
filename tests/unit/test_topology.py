"""Unit tests for the Topology class."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nroute.core.topology import Topology
from nroute.exceptions import TopologyError, ValidationError


def test_empty_topology() -> None:
    """Test initial state of an empty topology."""
    topo = Topology()
    assert topo.node_count == 0
    assert topo.edge_count == 0
    assert len(topo.nodes) == 0
    assert len(topo.edges) == 0


def test_add_node_valid() -> None:
    """Test adding a node with default and custom attributes."""
    topo = Topology()
    topo.add_node("A", type="router", capacity=5000.0, location="Core")
    assert topo.node_count == 1
    assert "A" in topo.nodes

    attrs = topo.get_node("A")
    assert attrs["type"] == "router"
    assert attrs["capacity"] == 5000.0
    assert attrs["status"] == "up"
    assert attrs["location"] == "Core"


def test_add_node_invalid_attrs() -> None:
    """Test adding a node with invalid attribute types or values."""
    topo = Topology()

    # Invalid type
    with pytest.raises(ValidationError):
        topo.add_node("A", type="hub")

    # Negative capacity
    with pytest.raises(ValidationError):
        topo.add_node("A", capacity=-100.0)

    # Invalid status
    with pytest.raises(ValidationError):
        topo.add_node("A", status="degraded")

    # Invalid location type
    with pytest.raises(ValidationError):
        topo.add_node("A", location=123)


def test_remove_node() -> None:
    """Test removing a node and checking error conditions."""
    topo = Topology()
    topo.add_node("A")
    assert topo.node_count == 1

    topo.remove_node("A")
    assert topo.node_count == 0
    assert "A" not in topo.nodes

    with pytest.raises(TopologyError):
        topo.remove_node("A")

    with pytest.raises(TopologyError):
        topo.get_node("A")


def test_add_edge_valid() -> None:
    """Test adding an edge and verifying default and custom attributes."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")

    topo.add_edge("A", "B", bandwidth=100.0, latency=10.0, jitter=1.5, packet_loss=0.01)
    assert topo.edge_count == 1
    assert ("A", "B") in topo.edges

    attrs = topo.get_edge("A", "B")
    assert attrs["bandwidth"] == 100.0
    assert attrs["latency"] == 10.0
    assert attrs["jitter"] == 1.5
    assert attrs["packet_loss"] == 0.01
    assert attrs["utilization"] == 0.0
    assert attrs["weight"] == 10.0
    assert attrs["status"] == "up"


def test_add_edge_missing_nodes() -> None:
    """Test that adding an edge between non-existent nodes fails."""
    topo = Topology()
    topo.add_node("A")

    with pytest.raises(TopologyError):
        topo.add_edge("A", "B")

    with pytest.raises(TopologyError):
        topo.add_edge("B", "A")


def test_add_edge_invalid_attrs() -> None:
    """Test adding an edge with invalid attribute values."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")

    # Negative latency
    with pytest.raises(ValidationError):
        topo.add_edge("A", "B", latency=-5.0)

    # Invalid packet loss probability
    with pytest.raises(ValidationError):
        topo.add_edge("A", "B", packet_loss=1.5)

    # Invalid status value
    with pytest.raises(ValidationError):
        topo.add_edge("A", "B", status="broken")


def test_remove_edge() -> None:
    """Test removing an edge."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_edge("A", "B")

    topo.remove_edge("A", "B")
    assert topo.edge_count == 0

    with pytest.raises(TopologyError):
        topo.remove_edge("A", "B")

    with pytest.raises(TopologyError):
        topo.get_edge("A", "B")


def test_update_edge() -> None:
    """Test updating existing edge attributes."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_edge("A", "B", latency=5.0)

    # Verify update
    topo.update_edge("A", "B", latency=12.0, utilization=0.55, status="degraded")
    attrs = topo.get_edge("A", "B")
    assert attrs["latency"] == 12.0
    assert attrs["utilization"] == 0.55
    assert attrs["status"] == "degraded"

    # Verify invalid update
    with pytest.raises(ValidationError):
        topo.update_edge("A", "B", utilization=-0.1)

    # Verify update on non-existent edge
    with pytest.raises(TopologyError):
        topo.update_edge("A", "C", latency=1.0)


def test_link_status_toggling() -> None:
    """Test setting links up and down."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_edge("A", "B")

    assert topo.get_edge("A", "B")["status"] == "up"

    topo.set_link_down("A", "B")
    assert topo.get_edge("A", "B")["status"] == "down"

    topo.set_link_up("A", "B")
    assert topo.get_edge("A", "B")["status"] == "up"


def test_node_status_toggling() -> None:
    """Test toggling node status and cascading to incident edges."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    topo.add_edge("A", "B")
    topo.add_edge("B", "C")

    # Set node B down
    topo.set_node_down("B")
    assert topo.get_node("B")["status"] == "down"
    # Incident links should go down
    assert topo.get_edge("A", "B")["status"] == "down"
    assert topo.get_edge("B", "C")["status"] == "down"

    # Set node B back up
    topo.set_node_up("B")
    assert topo.get_node("B")["status"] == "up"
    assert topo.get_edge("A", "B")["status"] == "up"
    assert topo.get_edge("B", "C")["status"] == "up"


def test_copy_independence() -> None:
    """Test that copy creates a completely independent topology."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_edge("A", "B", latency=10.0)

    topo_copy = topo.copy()
    assert topo_copy.node_count == 2
    assert topo_copy.edge_count == 1

    # Mutate the copy
    topo_copy.add_node("C")
    topo_copy.add_edge("B", "C")
    topo_copy.update_edge("A", "B", latency=99.0)

    # Original topology should remain unchanged
    assert topo.node_count == 2
    assert topo.edge_count == 1
    assert "C" not in topo.nodes
    assert topo.get_edge("A", "B")["latency"] == 10.0


def test_serialization_dict() -> None:
    """Test serialization and deserialization using dictionaries."""
    topo = Topology()
    topo.add_node("A", type="router", capacity=1000.0)
    topo.add_node("B", type="host", capacity=100.0)
    topo.add_edge("A", "B", bandwidth=100.0, latency=5.0)

    d = topo.to_dict()
    assert "nodes" in d
    assert "edges" in d
    assert len(d["nodes"]) == 2
    assert len(d["edges"]) == 1

    topo_reconstructed = Topology.from_dict(d)
    assert topo_reconstructed.node_count == 2
    assert topo_reconstructed.edge_count == 1
    assert topo_reconstructed.get_node("B")["type"] == "host"
    assert topo_reconstructed.get_edge("A", "B")["latency"] == 5.0


def test_save_load_file() -> None:
    """Test saving and loading topology from files."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_edge("A", "B", latency=15.0)

    with tempfile.TemporaryDirectory() as tempdir:
        filepath = Path(tempdir) / "topology.json"
        topo.save(filepath)

        topo_loaded = Topology.load(filepath)
        assert topo_loaded.node_count == 2
        assert topo_loaded.edge_count == 1
        assert topo_loaded.get_edge("A", "B")["latency"] == 15.0


def test_summary_and_neighbors() -> None:
    """Test summary string format and neighbors querying."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    topo.add_edge("A", "B", latency=5.0, bandwidth=100.0)
    topo.add_edge("A", "C", latency=10.0, bandwidth=10.0)

    assert set(topo.neighbors("A")) == {"B", "C"}

    summary = topo.summary()
    assert "Nodes: 3" in summary
    assert "Edges: 2" in summary
    assert "Latency range: 5.0ms to 10.0ms" in summary
    assert "Bandwidth range: 10.0Mbps to 100.0Mbps" in summary


def test_topology_compute_routes() -> None:
    """Test the Topology.compute_routes convenience wrapper."""
    from nroute.core.traffic import FlowRecord, TrafficMatrix

    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_edge("A", "B", latency=5.0)

    tm = TrafficMatrix(
        flows=[
            FlowRecord(
                source="A",
                destination="B",
                bytes=100,
                packets=1,
                duration=1.0,
                protocol="TCP",
                timestamp=0.0,
            )
        ]
    )

    routes = topo.compute_routes(tm, router="dijkstra", weight="latency")
    assert routes[("A", "B")] == ["A", "B"]

    # Invalid router name should raise ValueError
    with pytest.raises(ValueError, match="Unknown router name"):
        topo.compute_routes(tm, router="invalid-router")
