"""Unit tests for the multi-agent negotiation routing system."""

from __future__ import annotations

from typing import Any

import pytest
from click.testing import CliRunner

from nroute.cli.main import cli
from nroute.core.topology import Topology
from nroute.exceptions import RoutingError
from nroute.routing import get_router
from nroute.routing.negotiation import NegotiationRouter
from nroute.simulation.engine import SimulationEngine
from nroute.simulation.traffic_gen import TrafficGenerator


def _get_topo(small_graph_data: dict[str, Any]) -> Topology:
    """Helper to convert test fixture graph data schema to Topology."""
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


def test_negotiation_profile_init() -> None:
    """Test initialization of NegotiationRouter and factory registration."""
    # Valid profiles
    r1 = NegotiationRouter(profile="latency")
    assert r1.profile == "latency"

    r2 = NegotiationRouter(profile="congestion")
    assert r2.profile == "congestion"

    r3 = NegotiationRouter(profile="balanced")
    assert r3.profile == "balanced"

    # Invalid profile
    with pytest.raises(ValueError, match="Unknown negotiation profile"):
        NegotiationRouter(profile="invalid")

    # Factory get_router tests
    assert isinstance(get_router("negotiation"), NegotiationRouter)
    assert get_router("negotiation").profile == "balanced"
    assert get_router("negotiation-latency").profile == "latency"
    assert get_router("negotiation-congestion").profile == "congestion"
    assert get_router("negotiation-balanced").profile == "balanced"


def test_negotiation_routing_latency(small_graph_data: dict[str, Any]) -> None:
    """Test that latency profile finds the shortest path by latency."""
    topo = _get_topo(small_graph_data)
    router = NegotiationRouter(profile="latency")

    # A -> D shortest path by latency should be A -> B -> D (10ms + 5ms = 15ms)
    path = router.compute_path(topo, "A", "D")
    assert path == ["A", "B", "D"]


def test_negotiation_routing_congestion(small_graph_data: dict[str, Any]) -> None:
    """Test that congestion-aware negotiation avoids highly utilized links."""
    topo = _get_topo(small_graph_data)

    # Congestion profile with default utilization=0.0
    router = NegotiationRouter(profile="congestion")
    path_clean = router.compute_path(topo, "A", "D")
    assert path_clean == ["A", "B", "D"]

    # Now make the link A -> B highly congested
    topo.update_edge("A", "B", utilization=0.95)

    # The router should now negotiate around A -> B and select A -> C -> E -> D
    path_congested = router.compute_path(topo, "A", "D")
    assert path_congested == ["A", "C", "E", "D"]


def test_negotiation_backtracking(small_graph_data: dict[str, Any]) -> None:
    """Test that negotiation backtracks when a path is blocked downstream."""
    topo = _get_topo(small_graph_data)
    router = NegotiationRouter(profile="latency")

    # Disable B -> D and B -> E links so B is a dead end for D
    topo.update_edge("B", "D", status="down")
    topo.update_edge("B", "E", status="down")

    # A will first negotiate with B (lowest cost), but B cannot route to D.
    # The agent at A should reject B (or backtrack) and route via C -> E -> D.
    path = router.compute_path(topo, "A", "D")
    assert path == ["A", "C", "E", "D"]


def test_negotiation_custom_weight(small_graph_data: dict[str, Any]) -> None:
    """Test that NegotiationRouter respects custom weight override string or callable."""
    topo = _get_topo(small_graph_data)
    router = NegotiationRouter(profile="balanced")

    # Custom weight as string: 'bandwidth' (Negotiation normally minimizes, so let's use it as cost metric)
    # Higher bandwidth should look more expensive if treated as cost, or we check that custom weight is called.
    # Let's verify custom callable weight function.
    def cost_by_hop(d: dict[str, Any]) -> float:
        # constant hop cost
        return 1.0

    path = router.compute_path(topo, "A", "D", weight=cost_by_hop)
    assert path == ["A", "B", "D"]  # Minimum hops


def test_negotiation_invalid_inputs(small_graph_data: dict[str, Any]) -> None:
    """Test that routing errors are raised for invalid inputs or disconnected topologies."""
    topo = _get_topo(small_graph_data)
    router = NegotiationRouter(profile="balanced")

    # Nonexistent source/dest
    with pytest.raises(RoutingError, match="does not exist"):
        router.compute_path(topo, "NONEXISTENT", "D")

    with pytest.raises(RoutingError, match="does not exist"):
        router.compute_path(topo, "A", "NONEXISTENT")

    # Source or destination down
    topo.set_node_down("A")
    with pytest.raises(RoutingError, match="is down"):
        router.compute_path(topo, "A", "D")

    topo.set_node_up("A")
    topo.set_node_down("D")
    with pytest.raises(RoutingError, match="is down"):
        router.compute_path(topo, "A", "D")

    # Fully disconnected destination
    topo.set_node_up("D")
    topo.update_edge("B", "D", status="down")
    topo.update_edge("E", "D", status="down")
    topo.update_edge("D", "A", status="down")

    with pytest.raises(RoutingError, match="failed to find a path"):
        router.compute_path(topo, "A", "D")


def test_negotiation_integration_simulation(small_graph_data: dict[str, Any]) -> None:
    """Test using NegotiationRouter in the SimulationEngine."""
    topo = _get_topo(small_graph_data)
    router = NegotiationRouter(profile="balanced")
    traffic_gen = TrafficGenerator(model="uniform", n_flows_per_tick=3)
    engine = SimulationEngine(topo, router, traffic_gen)

    # Run for a few ticks
    results = engine.run(duration_ticks=5, seed=42, show_progress=False)
    assert results.total_throughput() >= 0.0
    assert len(results.results) == 5


def test_negotiation_cli_integration(tmp_path: Any) -> None:
    """Test CLI commands accept negotiation routing option."""
    runner = CliRunner()

    # Create temporary topology file
    topo_file = tmp_path / "test_topo.json"
    topo_file.write_text("""{
        "nodes": [
            {"id": "A", "type": "router", "capacity": 1000.0, "status": "up"},
            {"id": "B", "type": "router", "capacity": 1000.0, "status": "up"}
        ],
        "edges": [
            {"source": "A", "target": "B", "bandwidth": 1000.0, "latency": 5.0, "jitter": 0.2, "packet_loss": 0.0, "utilization": 0.0, "status": "up"}
        ]
    }""")

    # Test route compute command
    res1 = runner.invoke(
        cli,
        [
            "route",
            "compute",
            "-t",
            str(topo_file),
            "-a",
            "negotiation-latency",
            "-s",
            "A",
            "-d",
            "B",
        ],
    )
    assert res1.exit_code == 0
    assert "NEGOTIATION-LATENCY" in res1.output

    # Test simulate run command
    res2 = runner.invoke(
        cli,
        [
            "simulate",
            "run",
            "-t",
            str(topo_file),
            "-a",
            "negotiation-congestion",
            "-d",
            "3",
            "--flows-per-tick",
            "2",
        ],
    )
    assert res2.exit_code == 0
    assert "NEGOTIATION-CONGESTION" in res2.output
