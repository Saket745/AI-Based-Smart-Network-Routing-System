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
    topo.add_edge("C", "A", cost=1.0)  # negative cycle (2 - 5 + 1 = -2)

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
