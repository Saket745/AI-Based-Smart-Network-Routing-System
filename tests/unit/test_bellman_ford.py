"""Unit tests for the Bellman-Ford router."""

from __future__ import annotations

from typing import Any

import pytest

from nroute.core.topology import Topology
from nroute.exceptions import RoutingError
from nroute.routing.bellman_ford import BellmanFordRouter


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


def test_bellman_ford_basic(small_graph_data: dict[str, Any]) -> None:
    """Test basic route computation with Bellman-Ford."""
    topo = _get_topo(small_graph_data)
    router = BellmanFordRouter()

    path = router.compute_path(topo, "A", "D", weight="latency")
    assert path == ["A", "B", "D"]


def test_bellman_ford_negative_cycle() -> None:
    """Test Bellman-Ford router raises RoutingError on negative cycle detection."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")

    # Use custom attribute 'cost' instead of standard validated 'weight' to support negative weights
    topo.add_edge("A", "B", cost=2.0)
    topo.add_edge("B", "C", cost=-5.0)  # negative cost
    topo.add_edge("C", "A", cost=1.0)  # negative cycle (2 - 5 + 1  =  -2)

    router = BellmanFordRouter()

    with pytest.raises(RoutingError, match="negative weight cycle detected"):
        router.compute_path(topo, "A", "C", weight="cost")


def test_bellman_ford_failures(small_graph_data: dict[str, Any]) -> None:
    """Test routing failures when nodes/links are down."""
    topo = _get_topo(small_graph_data)
    router = BellmanFordRouter()

    topo.set_link_down("B", "D")
    topo.set_link_down("E", "D")

    with pytest.raises(RoutingError, match="No active path found"):
        router.compute_path(topo, "A", "D", weight="latency")


def test_bellman_ford_node_down(small_graph_data: dict[str, Any]) -> None:
    """Test routing failures when source or destination nodes are down."""
    topo = _get_topo(small_graph_data)
    router = BellmanFordRouter()

    # Source down
    topo.set_node_down("A")
    with pytest.raises(RoutingError, match="Source node 'A' is down"):
        router.compute_path(topo, "A", "D", weight="latency")

    # Destination down
    topo.set_node_up("A")
    topo.set_node_down("D")
    with pytest.raises(RoutingError, match="Destination node 'D' is down"):
        router.compute_path(topo, "A", "D", weight="latency")


def test_bellman_ford_weights(small_graph_data: dict[str, Any]) -> None:
    """Test routing with default and callable weights."""
    topo = _get_topo(small_graph_data)
    router = BellmanFordRouter()

    # Default weight (all edges weight=1.0)
    # Path A->B->D (2 hops) or A->C->E->D (3 hops)
    path_default = router.compute_path(topo, "A", "D", weight=None)
    assert path_default == ["A", "B", "D"]

    # Callable weight
    def custom_weight(d: dict[str, Any]) -> float:
        return float(d.get("latency", 0.0)) + float(d.get("jitter", 0.0))

    path_callable = router.compute_path(topo, "A", "D", weight=custom_weight)
    assert path_callable is not None


def test_bellman_ford_generic_exception(small_graph_data: dict[str, Any], monkeypatch: Any) -> None:
    """Test handling of generic exceptions during route computation."""
    topo = _get_topo(small_graph_data)
    router = BellmanFordRouter()

    def mock_path(*args: Any, **kwargs: Any) -> list[str]:
        raise RuntimeError("Unexpected error")

    import networkx as nx

    monkeypatch.setattr(nx, "bellman_ford_path", mock_path)

    with pytest.raises(
        RoutingError, match="Bellman-Ford route computation failed: Unexpected error"
    ):
        router.compute_path(topo, "A", "D")


def test_bellman_ford_routing_error_re_raise(
    small_graph_data: dict[str, Any], monkeypatch: Any
) -> None:
    """Test re-raising of RoutingError during route computation."""
    topo = _get_topo(small_graph_data)
    router = BellmanFordRouter()

    def mock_validate(*args: Any, **kwargs: Any) -> bool:
        raise RoutingError("Validation failed")

    monkeypatch.setattr(router, "validate_path", mock_validate)

    with pytest.raises(RoutingError, match="Validation failed"):
        router.compute_path(topo, "A", "D")


def test_bellman_ford_disconnected_graph() -> None:
    """Test routing between disconnected components."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    topo.add_node("D")

    # Component 1: A-B
    topo.add_edge("A", "B", weight=1.0)
    # Component 2: C-D
    topo.add_edge("C", "D", weight=1.0)

    router = BellmanFordRouter()

    with pytest.raises(RoutingError, match="No active path found between 'A' and 'D'"):
        router.compute_path(topo, "A", "D")
