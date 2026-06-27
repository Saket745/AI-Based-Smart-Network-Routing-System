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
    """Test standard minimum-hop path computation on small topology."""
    topo = _get_topo(small_graph_data)
    router = BFSRouter()

    # Path A -> D should be A -> B -> D (2 hops)
    path = router.compute_path(topo, "A", "D")
    assert path == ["A", "B", "D"]

    # Path A -> E should be A -> B -> E (2 hops)
    path_e = router.compute_path(topo, "A", "E")
    assert path_e == ["A", "B", "E"]


def test_bfs_ignores_weights(small_graph_data: dict[str, Any]) -> None:
    """Test that BFS ignores link metrics and always uses hop count."""
    topo = _get_topo(small_graph_data)
    router = BFSRouter()

    # Even if we pass a weight, BFSRouter should ignore it and return A -> B -> D
    # We can't easily verify it IGNORES it unless we modify the topology to make
    # the 2-hop path VERY expensive.

    # Modify A -> B to be very high latency
    for edge in topo.graph.edges("A", data=True):
        if edge[1] == "B":
            edge[2]["latency"] = 1000.0

    # Dijkstra would now avoid A -> B -> D (1005ms) in favor of A -> C -> E -> D (25ms)
    # BFS should still pick A -> B -> D (2 hops)
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
    assert len(path) == 4  # 3 hops = 4 nodes
    assert path[0] == "A"
    assert path[-1] == "D"

    # Break node B entirely
    topo.set_node_down("B")

    # Path must switch to A -> C -> E -> D (3 hops)
    path_nodes_down = router.compute_path(topo, "A", "D")
    assert path_nodes_down == ["A", "C", "E", "D"]


def test_bfs_routing_errors(small_graph_data: dict[str, Any]) -> None:
    """Test routing failures for disconnected nodes or invalid requests."""
    topo = _get_topo(small_graph_data)
    router = BFSRouter()

    # Make target unreachable
    topo.set_link_down("E", "D")
    topo.set_link_down("B", "D")

    with pytest.raises(RoutingError, match="No active path found"):
        router.compute_path(topo, "A", "D")

    # Non-existent nodes
    with pytest.raises(RoutingError, match="does not exist"):
        router.compute_path(topo, "A", "NON_EXISTENT")

    with pytest.raises(RoutingError, match="does not exist"):
        router.compute_path(topo, "NON_EXISTENT", "D")


def test_bfs_routing_unhandled_exception(
    small_graph_data: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test handling of unexpected exceptions during BFS computation."""
    topo = _get_topo(small_graph_data)
    router = BFSRouter()

    import networkx as nx

    def mock_shortest_path(*args: Any, **kwargs: Any) -> list[str]:
        raise RuntimeError("Unexpected error")

    monkeypatch.setattr(nx, "shortest_path", mock_shortest_path)

    with pytest.raises(RoutingError, match="BFS route computation failed"):
        router.compute_path(topo, "A", "D")


def test_bfs_routing_validation_error(
    small_graph_data: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test handling of RoutingError raised during path validation."""
    topo = _get_topo(small_graph_data)
    router = BFSRouter()

    def mock_validate_path(*args: Any, **kwargs: Any) -> None:
        raise RoutingError("Validation failed")

    monkeypatch.setattr(router, "validate_path", mock_validate_path)

    with pytest.raises(RoutingError, match="Validation failed"):
        router.compute_path(topo, "A", "D")
