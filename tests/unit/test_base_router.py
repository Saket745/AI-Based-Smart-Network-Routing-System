"""Unit tests for the base router and fallback router."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

from nroute.core.topology import Topology
from nroute.core.traffic import FlowRecord, TrafficMatrix
from nroute.exceptions import RoutingError
from nroute.routing.base import BaseRouter, FallbackRouter


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


class DummyRouter(BaseRouter):
    """A dummy router implementation for testing BaseRouter methods."""

    def __init__(self, paths: dict[tuple[str, str], list[str]] | None = None) -> None:
        self.paths = paths or {}
        self.call_count = 0

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
    ) -> list[str]:
        self.call_count += 1
        path = self.paths.get((source, destination))
        if not path:
            raise RoutingError(f"No path found from {source} to {destination}")
        return path


def test_base_router_compute_routes(small_graph_data: dict[str, Any]) -> None:
    """Test compute_routes handles multiple flows and skips unreachable ones."""
    topo = _get_topo(small_graph_data)
    paths = {("A", "D"): ["A", "B", "D"], ("A", "C"): ["A", "C"]}
    router = DummyRouter(paths)

    flows = [
        FlowRecord(
            source="A",
            destination="D",
            bytes=100,
            packets=10,
            duration=1.0,
            protocol="TCP",
            timestamp=0.0,
        ),
        FlowRecord(
            source="A",
            destination="C",
            bytes=100,
            packets=10,
            duration=1.0,
            protocol="TCP",
            timestamp=0.0,
        ),
        FlowRecord(
            source="B",
            destination="C",
            bytes=100,
            packets=10,
            duration=1.0,
            protocol="TCP",
            timestamp=0.0,
        ),  # Unreachable in DummyRouter
    ]
    tm = TrafficMatrix(flows=flows)

    routes = router.compute_routes(topo, tm)

    assert routes[("A", "D")] == ["A", "B", "D"]
    assert routes[("A", "C")] == ["A", "C"]
    assert ("B", "C") not in routes
    assert len(routes) == 2


def test_base_router_validate_path(small_graph_data: dict[str, Any]) -> None:
    """Test comprehensive path validation logic."""
    topo = _get_topo(small_graph_data)
    router = DummyRouter()

    # Valid path
    assert (
        router.validate_path(topo, ["A", "B", "D"], source="A", destination="D") is True
    )

    # Empty path
    with pytest.raises(RoutingError, match="Path is empty"):
        router.validate_path(topo, [])

    # Source mismatch
    with pytest.raises(
        RoutingError, match="Path source 'B' does not match expected source 'A'"
    ):
        router.validate_path(topo, ["B", "D"], source="A")

    # Destination mismatch
    with pytest.raises(
        RoutingError,
        match="Path destination 'B' does not match expected destination 'D'",
    ):
        router.validate_path(topo, ["A", "B"], destination="D")

    # Non-existent node
    with pytest.raises(
        RoutingError, match="Node 'X' in path does not exist in topology"
    ):
        router.validate_path(topo, ["A", "X", "D"])

    # Down node
    topo.set_node_down("B")
    with pytest.raises(RoutingError, match="Node 'B' in path is down"):
        router.validate_path(topo, ["A", "B", "D"])
    topo.set_node_up("B")

    # Non-existent edge
    with pytest.raises(
        RoutingError, match="Edge 'A->D' in path does not exist in topology"
    ):
        router.validate_path(topo, ["A", "D"])

    # Down edge
    topo.set_link_down("A", "B")
    with pytest.raises(RoutingError, match="Edge 'A->B' in path is down"):
        router.validate_path(topo, ["A", "B", "D"])


def test_base_router_get_active_subgraph(small_graph_data: dict[str, Any]) -> None:
    """Test filtering of topology to only active components."""
    topo = _get_topo(small_graph_data)
    router = DummyRouter()

    # All up initially
    subgraph = router._get_active_subgraph(topo)
    assert subgraph.number_of_nodes() == 5
    assert subgraph.number_of_edges() == 7

    # Set a node down
    topo.set_node_down("C")
    subgraph = router._get_active_subgraph(topo)
    assert "C" not in subgraph.nodes
    # Edges A->C and C->E should be gone
    assert ("A", "C") not in subgraph.edges
    assert ("C", "E") not in subgraph.edges
    assert subgraph.number_of_nodes() == 4
    assert subgraph.number_of_edges() == 5

    # Set an edge down
    topo.set_link_down("B", "D")
    subgraph = router._get_active_subgraph(topo)
    assert ("B", "D") not in subgraph.edges
    assert subgraph.number_of_edges() == 4


def test_fallback_router_success(small_graph_data: dict[str, Any]) -> None:
    """Test FallbackRouter successfully falling back when first router fails."""
    topo = _get_topo(small_graph_data)
    r1 = DummyRouter()  # Fails
    r2 = DummyRouter({("A", "D"): ["A", "B", "D"]})  # Succeeds

    fallback = FallbackRouter([r1, r2])
    path = fallback.compute_path(topo, "A", "D")
    assert path == ["A", "B", "D"]
    assert r1.call_count == 1
    assert r2.call_count == 1


def test_fallback_router_all_fail(small_graph_data: dict[str, Any]) -> None:
    """Test FallbackRouter when all sub-routers fail."""
    topo = _get_topo(small_graph_data)
    r1 = DummyRouter()
    r2 = DummyRouter()

    fallback = FallbackRouter([r1, r2])
    with pytest.raises(RoutingError, match="All routers in the fallback chain failed"):
        fallback.compute_path(topo, "A", "D")


def test_fallback_router_invalid_init() -> None:
    """Test FallbackRouter requires at least one sub-router."""
    with pytest.raises(
        ValueError, match="FallbackRouter requires at least one sub-router"
    ):
        FallbackRouter([])


def test_fallback_router_invalid_path_returned(
    small_graph_data: dict[str, Any],
) -> None:
    """Test FallbackRouter ignores invalid paths returned by sub-routers."""
    topo = _get_topo(small_graph_data)
    # r1 returns an invalid path (A->D doesn't exist directly)
    r1 = DummyRouter({("A", "D"): ["A", "D"]})
    r2 = DummyRouter({("A", "D"): ["A", "B", "D"]})

    fallback = FallbackRouter([r1, r2])
    # It should fail r1's path validation and move to r2
    path = fallback.compute_path(topo, "A", "D")
    assert path == ["A", "B", "D"]
    assert r1.call_count == 1
    assert r2.call_count == 1
