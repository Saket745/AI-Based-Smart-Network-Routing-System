"""Unit tests for the Dijkstra router."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import networkx as nx
import pytest

from nroute.core.topology import Topology
from nroute.exceptions import RoutingError
from nroute.routing.dijkstra import DijkstraRouter


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


def test_dijkstra_routing_basic(small_graph_data: dict[str, Any]) -> None:
    """Test standard shortest path computation on small topology using default weight."""
    topo = _get_topo(small_graph_data)
    router = DijkstraRouter()

    # Path A -> D should be A -> B -> D (latency 10 + 5 = 15)
    path = router.compute_path(topo, "A", "D", weight="latency")
    assert path == ["A", "B", "D"]

    # Path A -> E should be A -> B -> E (latency 10 + 8 = 18)
    path_e = router.compute_path(topo, "A", "E", weight="latency")
    assert path_e == ["A", "B", "E"]


def test_dijkstra_routing_custom_weights(small_graph_data: dict[str, Any]) -> None:
    """Test routing with custom edge weights and callable weight functions."""
    topo = _get_topo(small_graph_data)
    router = DijkstraRouter()

    # If we use bandwidth as weight, it should minimize total bandwidth
    path = router.compute_path(topo, "A", "D", weight="bandwidth")
    assert path == ["A", "C", "E", "D"]

    # Test callable weight function (e.g. latency + 2ms jitter penalty)
    def composite_weight(edge_data: dict[str, Any]) -> float:
        return float(edge_data.get("latency", 0.0) + 2.0 * edge_data.get("jitter", 0.0))

    path_composite = router.compute_path(topo, "A", "D", weight=composite_weight)
    assert path_composite == ["A", "B", "D"]


def test_dijkstra_routing_failure_recovery(small_graph_data: dict[str, Any]) -> None:
    """Test Dijkstra router correctly routes around down nodes and links."""
    topo = _get_topo(small_graph_data)
    router = DijkstraRouter()

    # Initially: A -> B -> D (15ms)
    assert router.compute_path(topo, "A", "D", weight="latency") == ["A", "B", "D"]

    # Break link B -> D
    topo.set_link_down("B", "D")

    # Path should switch to A -> B -> E -> D (latency 10 + 8 + 3 = 21ms)
    path = router.compute_path(topo, "A", "D", weight="latency")
    assert path == ["A", "B", "E", "D"]

    # Break node B entirely
    topo.set_node_down("B")

    # Path should switch to A -> C -> E -> D (latency 15 + 7 + 3 = 25ms)
    path_nodes_down = router.compute_path(topo, "A", "D", weight="latency")
    assert path_nodes_down == ["A", "C", "E", "D"]


def test_dijkstra_routing_errors(small_graph_data: dict[str, Any]) -> None:
    """Test routing failures for disconnected nodes or invalid requests."""
    topo = _get_topo(small_graph_data)
    router = DijkstraRouter()

    # Make target unreachable by bringing down links
    topo.set_link_down("E", "D")
    topo.set_link_down("B", "D")

    with pytest.raises(RoutingError, match="No active path found"):
        router.compute_path(topo, "A", "D", weight="latency")

    # Non-existent nodes
    with pytest.raises(RoutingError, match="does not exist"):
        router.compute_path(topo, "A", "NON_EXISTENT")

    with pytest.raises(RoutingError, match="does not exist"):
        router.compute_path(topo, "NON_EXISTENT", "D")


def test_dijkstra_default_weight(small_graph_data: dict[str, Any]) -> None:
    """Test Dijkstra router using default weight function."""
    topo = _get_topo(small_graph_data)
    router = DijkstraRouter()

    # Path A -> D with default weights (1.0) should be A -> B -> D (2 hops)
    path = router.compute_path(topo, "A", "D", weight=None)
    assert path == ["A", "B", "D"]


def test_dijkstra_routing_exception_handling(small_graph_data: dict[str, Any]) -> None:
    """Test Dijkstra router exception handling paths."""
    topo = _get_topo(small_graph_data)
    router = DijkstraRouter()

    with patch("networkx.shortest_path") as mock_shortest:
        # Test RoutingError re-raise (lines 70-71)
        mock_shortest.side_effect = RoutingError("Custom routing error")
        with pytest.raises(RoutingError, match="Custom routing error"):
            router.compute_path(topo, "A", "D")

        # Test Generic Exception wrapping (line 72)
        mock_shortest.side_effect = RuntimeError("Something went wrong")
        with pytest.raises(
            RoutingError,
            match="Dijkstra route computation failed: Something went wrong",
        ):
            router.compute_path(topo, "A", "D")

    # Test NetworkXNoPath (lines 65-68) - already in test_dijkstra_routing_errors but let's be explicit
    with patch("networkx.shortest_path") as mock_shortest:
        mock_shortest.side_effect = nx.NetworkXNoPath("No path")
        with pytest.raises(RoutingError, match="No active path found"):
            router.compute_path(topo, "A", "D")
