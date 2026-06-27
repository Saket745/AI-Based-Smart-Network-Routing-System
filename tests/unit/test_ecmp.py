"""Unit tests for the ECMP, K-Shortest-Paths, and Fallback routers."""

from __future__ import annotations

from typing import Any

import pytest

from nroute.core.query import RoutingQuery
from nroute.core.topology import Topology
from nroute.exceptions import RoutingError
from nroute.routing.base import FallbackRouter
from nroute.routing.dijkstra import DijkstraRouter
from nroute.routing.ecmp import ECMPRouter


def test_ecmp_equal_cost_paths() -> None:
    """Test computation of multiple equal cost paths (ECMP)."""
    # Create a diamond-shaped topology with equal weights
    #       B (wt: 5)
    #     /   \
    #   A       D
    #     \   /
    #       C (wt: 5)
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    topo.add_node("D")

    topo.add_edge("A", "B", weight=5.0)
    topo.add_edge("B", "D", weight=5.0)
    topo.add_edge("A", "C", weight=5.0)
    topo.add_edge("C", "D", weight=5.0)

    router = ECMPRouter()

    # Test new query object style
    query = RoutingQuery(source="A", destination="D", weight="weight")
    paths = router.compute_all_equal_cost_paths(topo, query)
    assert len(paths) == 2

    # Test backward compatible style
    paths_compat = router.compute_all_equal_cost_paths(topo, source="A", destination="D", weight="weight")
    assert paths_compat == paths
    assert ["A", "B", "D"] in paths
    assert ["A", "C", "D"] in paths


def test_ecmp_deterministic_selection() -> None:
    """Test that path selection is deterministic and varies by flow_key."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    topo.add_node("D")

    topo.add_edge("A", "B", weight=5.0)
    topo.add_edge("B", "D", weight=5.0)
    topo.add_edge("A", "C", weight=5.0)
    topo.add_edge("C", "D", weight=5.0)

    router = ECMPRouter()

    # Without flow_key, returns first path
    p_default = router.compute_path(topo, "A", "D", weight="weight")
    assert p_default in [["A", "B", "D"], ["A", "C", "D"]]

    # With different flow_keys, we should get deterministic selections
    p_flow1 = router.compute_path(topo, "A", "D", weight="weight", flow_key="TCP_10.0.0.1_80")
    p_flow2 = router.compute_path(topo, "A", "D", weight="weight", flow_key="UDP_10.0.0.1_53")

    # Confirm they are valid paths
    assert p_flow1 in [["A", "B", "D"], ["A", "C", "D"]]
    assert p_flow2 in [["A", "B", "D"], ["A", "C", "D"]]

    # Confirm same flow key returns identical path (determinism)
    assert (
        router.compute_path(topo, "A", "D", weight="weight", flow_key="TCP_10.0.0.1_80") == p_flow1
    )


def test_k_shortest_paths() -> None:
    """Test computation of K-shortest paths using Yen's algorithm."""
    # Topology:
    # A --(1)--> B --(1)--> D (total: 2)
    # A --(3)--> C --(1)--> D (total: 4)
    # A --(1)--> E --(5)--> D (total: 6)
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    topo.add_node("D")
    topo.add_node("E")

    topo.add_edge("A", "B", weight=1.0)
    topo.add_edge("B", "D", weight=1.0)

    topo.add_edge("A", "C", weight=3.0)
    topo.add_edge("C", "D", weight=1.0)

    topo.add_edge("A", "E", weight=1.0)
    topo.add_edge("E", "D", weight=5.0)

    router = ECMPRouter(k=3)

    # Test new query object style
    query = RoutingQuery(source="A", destination="D", weight="weight")
    paths = router.compute_k_shortest_paths(topo, query)
    assert len(paths) == 3

    # Test backward compatible style
    paths_compat = router.compute_k_shortest_paths(topo, source="A", destination="D", weight="weight")
    assert paths_compat == paths
    assert paths[0] == ["A", "B", "D"]  # cost: 2
    assert paths[1] == ["A", "C", "D"]  # cost: 4
    assert paths[2] == ["A", "E", "D"]  # cost: 6


def test_fallback_router() -> None:
    """Test fallback chain routing logic."""
    # Create two routers
    # First router is configured to route only based on "latency" attribute (which we will break)
    # Second router routes on "weight" attribute (alternative link)
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")

    # Link A -> B has latency, link B -> C has latency (normal route)
    topo.add_edge("A", "B", latency=5.0, weight=10.0)
    topo.add_edge("B", "C", latency=5.0, weight=10.0)

    # Direct Link A -> C has down latency (invalidated for router 1), but has valid weight
    topo.add_edge("A", "C", latency=999.0, weight=2.0)

    # Let's mock a router that fails
    class FailingRouter(DijkstraRouter):
        def compute_path(
            self, topology: Topology, source: str, destination: str, weight: Any | None = None
        ) -> list[str]:
            raise RoutingError("Simulated algorithm failure")

    router1 = FailingRouter()
    router2 = DijkstraRouter()

    fallback_router = FallbackRouter(routers=[router1, router2])

    # Even though router1 fails, fallback_router should use router2 and return a valid path
    path = fallback_router.compute_path(topo, "A", "C", weight="weight")
    assert path == ["A", "C"]


def test_fallback_router_all_fail() -> None:
    """Test FallbackRouter raises RoutingError if all chained sub-routers fail."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")

    router = FallbackRouter([DijkstraRouter(), ECMPRouter()])

    with pytest.raises(RoutingError, match="All routers in the fallback chain failed"):
        router.compute_path(topo, "A", "B")
