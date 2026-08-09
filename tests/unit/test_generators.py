"""Unit tests for the TopologyGenerator class."""

from __future__ import annotations

import numpy as np
import pytest

from nroute.core.topology import Topology
from nroute.exceptions import TopologyError


def test_random_generator() -> None:
    """Test Erdos-Renyi random topology generation."""
    topo = Topology.generate("random", n_nodes=30, edge_prob=0.15, seed=42)
    assert topo.node_count == 30
    # Check that all nodes have correct type router
    for node in topo.nodes:
        assert topo.get_node(node)["type"] == "router"
        assert topo.get_node(node)["status"] == "up"

    # Edge attributes should be populated and valid
    for src, dst in topo.edges:
        attrs = topo.get_edge(src, dst)
        assert "bandwidth" in attrs
        assert "latency" in attrs
        assert attrs["status"] == "up"

    # Error conditions
    with pytest.raises(TopologyError):
        Topology.generate("random", n_nodes=-5, edge_prob=0.5)
    with pytest.raises(TopologyError):
        Topology.generate("random", n_nodes=10, edge_prob=1.5)


def test_scale_free_generator() -> None:
    """Test Barabasi-Albert scale-free topology generation."""
    topo = Topology.generate("scale-free", n_nodes=25, seed=42)
    assert topo.node_count == 25
    # For m=2, number of edges should be (N - m) * m * 2 (since it is directed)
    # Undirected BA graph has (25 - 2) * 2 = 46 edges.
    # Directed conversion makes it 46 * 2 = 92 edges.
    assert topo.edge_count == 92

    with pytest.raises(TopologyError):
        Topology.generate("scale-free", n_nodes=2)


def test_small_world_generator() -> None:
    """Test Watts-Strogatz small-world topology generation."""
    topo = Topology.generate("small-world", n_nodes=20, k_neighbors=4, rewire_prob=0.1, seed=42)
    assert topo.node_count == 20
    # Every node has k neighbors -> 20 * 4 = 80 directed edges
    assert topo.edge_count == 80

    with pytest.raises(TopologyError):
        Topology.generate("small-world", n_nodes=10, k_neighbors=12)


def test_fat_tree_generator() -> None:
    """Test hierarchical k-ary Fat-Tree topology generation."""
    k = 4
    topo = Topology.generate("fat-tree", k=k)

    # Core: (k/2)^2 = 4
    # Aggregation: k * (k/2) = 8
    # Edge: k * (k/2) = 8
    # Hosts: k * (k/2)^2 = 16
    # Total Nodes = 36
    assert topo.node_count == 36

    # Verify node types
    switches = [n for n in topo.nodes if topo.get_node(n)["type"] == "switch"]
    hosts = [n for n in topo.nodes if topo.get_node(n)["type"] == "host"]
    assert len(switches) == 20
    assert len(hosts) == 16

    # Verify specific nodes exist
    assert "core_0" in topo.nodes
    assert "pod_0_agg_0" in topo.nodes
    assert "pod_0_edge_0" in topo.nodes
    assert "pod_0_host_0_0" in topo.nodes

    # Verify edge counts:
    # Hosts <--> Edge: 16 hosts * 2 links each = 32 links
    # Edge <--> Agg: 8 edge switches * (k/2) agg switches * 2 links = 32 links
    # Agg <--> Core: 8 agg switches * (k/2) core switches * 2 links = 32 links
    # Total Edges = 96
    assert topo.edge_count == 96

    # Verify hierarchical edge properties
    host_edge = topo.get_edge("pod_0_host_0_0", "pod_0_edge_0")
    assert host_edge["bandwidth"] == 1000.0
    assert host_edge["latency"] == 0.5

    pod_edge = topo.get_edge("pod_0_edge_0", "pod_0_agg_0")
    assert pod_edge["bandwidth"] == 10000.0
    assert pod_edge["latency"] == 1.0

    core_edge = topo.get_edge("pod_0_agg_0", "core_0")
    assert core_edge["bandwidth"] == 40000.0
    assert core_edge["latency"] == 2.0

    with pytest.raises(TopologyError):
        Topology.generate("fat-tree", k=3)


def test_from_adjacency_matrix() -> None:
    """Test generating a topology from a NumPy adjacency matrix."""
    from nroute.core.generators import TopologyGenerator

    matrix = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]])

    topo = TopologyGenerator.from_adjacency_matrix(
        matrix, node_labels=["Node0", "Node1", "Node2"], seed=100
    )

    assert topo.node_count == 3
    assert topo.edge_count == 3
    assert set(topo.nodes) == {"Node0", "Node1", "Node2"}
    assert ("Node0", "Node1") in topo.edges
    assert ("Node1", "Node2") in topo.edges
    assert ("Node2", "Node0") in topo.edges

    # Validation errors
    non_square = np.zeros((3, 2))
    with pytest.raises(TopologyError):
        TopologyGenerator.from_adjacency_matrix(non_square)

    mismatched_labels = ["A", "B"]
    with pytest.raises(TopologyError):
        TopologyGenerator.from_adjacency_matrix(matrix, node_labels=mismatched_labels)


def test_seeded_reproducibility() -> None:
    """Test that same seed results in identical randomized link attributes."""
    topo1 = Topology.generate("random", n_nodes=50, edge_prob=0.1, seed=12345)
    topo2 = Topology.generate("random", n_nodes=50, edge_prob=0.1, seed=12345)

    assert topo1.node_count == topo2.node_count
    assert topo1.edge_count == topo2.edge_count
    assert topo1.nodes == topo2.nodes
    assert topo1.edges == topo2.edges

    # Check that attributes are identical
    for src, dst in topo1.edges:
        attr1 = topo1.get_edge(src, dst)
        attr2 = topo2.get_edge(src, dst)
        assert attr1["bandwidth"] == attr2["bandwidth"]
        assert attr1["latency"] == attr2["latency"]
        assert attr1["jitter"] == attr2["jitter"]
        assert attr1["packet_loss"] == attr2["packet_loss"]


def test_invalid_type_generate() -> None:
    """Test that invalid generate type raises TopologyError."""
    with pytest.raises(TopologyError):
        Topology.generate("ring")
