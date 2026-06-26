"""Unit tests for the BFS router."""

from __future__ import annotations

from typing import Any

import pytest

from nroute.core.topology import Topology
from nroute.exceptions import RoutingError
from nroute.routing.bfs import BFSRouter


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


def test_bfs_routing_basic(small_graph_data: dict[str, Any]) -> None:
    """Test standard unweighted shortest path computation on small topology."""
    topo = _get_topo(small_graph_data)
    router = BFSRouter()

    # Path A -> D should be A -> B -> D (2 hops)
    path = router.compute_path(topo, "A", "D")
    assert path == ["A", "B", "D"]

    # Path A -> E should be A -> B -> E or A -> C -> E (both 2 hops)
    # NetworkX shortest_path for unweighted graph returns one of them.
    path_e = router.compute_path(topo, "A", "E")
    assert len(path_e) == 3
    assert path_e[0] == "A"
    assert path_e[2] == "E"
    assert path_e[1] in ["B", "C"]


def test_bfs_ignores_weights(small_graph_data: dict[str, Any]) -> None:
    """Test that BFS router ignores weights and always uses hop count."""
    topo = _get_topo(small_graph_data)
    router = BFSRouter()

    # Even if we provide a weight that would favor a longer hop path,
    # BFS should still return the minimum-hop path.
    # For A -> D:
    # A -> B -> D: 2 hops, 15ms latency
    # A -> C -> E -> D: 3 hops, 25ms latency
    # Let's make A -> B -> D very "expensive" by latency
    topo.graph["A"]["B"]["latency"] = 100.0
    topo.graph["B"]["D"]["latency"] = 100.0

    # Dijkstra with latency would now choose A -> C -> E -> D (25ms)
    # But BFS should still choose A -> B -> D (2 hops)
    path = router.compute_path(topo, "A", "D", weight="latency")
    assert path == ["A", "B", "D"]


def test_bfs_routing_failure_recovery(small_graph_data: dict[str, Any]) -> None:
    """Test BFS router correctly routes around down nodes and links."""
    topo = _get_topo(small_graph_data)
    router = BFSRouter()

    # Initially: A -> B -> D (2 hops)
    assert router.compute_path(topo, "A", "D") == ["A", "B", "D"]

    # Break link B -> D
    topo.set_link_down("B", "D")

    # Path should switch to another 3-hop path, e.g., A -> B -> E -> D or A -> C -> E -> D
    path = router.compute_path(topo, "A", "D")
    assert len(path) == 4
    assert path[0] == "A"
    assert path[-1] == "D"

    # Break node B entirely
    topo.set_node_down("B")

    # Path must be A -> C -> E -> D
    path_nodes_down = router.compute_path(topo, "A", "D")
    assert path_nodes_down == ["A", "C", "E", "D"]


def test_bfs_routing_errors(small_graph_data: dict[str, Any]) -> None:
    """Test routing failures for disconnected nodes or invalid requests."""
    topo = _get_topo(small_graph_data)
    router = BFSRouter()

    # Make target unreachable by bringing down links
    topo.set_link_down("E", "D")
    topo.set_link_down("B", "D")

    with pytest.raises(RoutingError, match="No active path found"):
        router.compute_path(topo, "A", "D")

    # Non-existent nodes
    with pytest.raises(RoutingError, match="does not exist"):
        router.compute_path(topo, "A", "NON_EXISTENT")

    with pytest.raises(RoutingError, match="does not exist"):
        router.compute_path(topo, "NON_EXISTENT", "D")

    # Node down
    topo.set_node_down("A")
    with pytest.raises(RoutingError, match="Source node 'A' is down"):
        router.compute_path(topo, "A", "D")
