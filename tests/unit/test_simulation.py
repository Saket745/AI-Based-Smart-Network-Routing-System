"""Unit tests for the network simulation engine."""

from __future__ import annotations

from typing import Any

import pytest

from nroute import Simulator
from nroute.core.topology import Topology
from nroute.routing.dijkstra import DijkstraRouter
from nroute.simulation.engine import SimulationEngine
from nroute.simulation.failure_injector import FailureInjector
from nroute.simulation.traffic_gen import TrafficGenerator


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


def test_simulation_engine_basic_run(small_graph_data: dict[str, Any]) -> None:
    """Test that the simulation engine runs successfully and aggregates metrics."""
    topo = _get_topo(small_graph_data)
    router = DijkstraRouter()
    traffic = TrafficGenerator(model="uniform", n_flows_per_tick=3, seed=42)
    engine = SimulationEngine(topo, router, traffic)

    results = engine.run(duration_ticks=10, seed=42)
    
    assert len(results.results) == 10
    assert results.total_throughput() >= 0.0
    assert results.mean_latency() >= 0.0
    assert 0.0 <= results.peak_utilization() <= 1.0


def test_simulator_facade(small_graph_data: dict[str, Any]) -> None:
    """Test the Simulator package-level facade class."""
    topo = _get_topo(small_graph_data)
    router = DijkstraRouter()
    sim = Simulator(topology=topo, algorithm=router, duration=5)
    
    results = sim.run(seed=10)
    assert len(results.results) == 5


def test_simulation_failure_injection_reroute(small_graph_data: dict[str, Any]) -> None:
    """Test failure injection triggers flow rerouting and increments metrics."""
    topo = _get_topo(small_graph_data)
    router = DijkstraRouter()
    
    # We want a deterministic single flow from A to D
    # We create a traffic generator that will create a flow from A to D at tick 0
    # and then stops generating new flows.
    class FixedTrafficGenerator(TrafficGenerator):
        def generate(self, topology: Topology, tick: int = 0) -> list[Any]:
            if tick == 0:
                return [self._create_flow("A", "D", tick)]
            return []

    traffic = FixedTrafficGenerator(model="uniform", n_flows_per_tick=1, seed=42)
    
    # Setup failure injector: Break link B -> D at tick 1 (flow is mid-route)
    injector = FailureInjector()
    injector.schedule_link_failure("B", "D", tick=1)

    engine = SimulationEngine(topo, router, traffic, failure_injector=injector)
    results = engine.run(duration_ticks=5, seed=42)

    # Check if a reroute occurred
    total_reroutes = sum(tick_metric.reroute_count for tick_metric in results.results)
    assert total_reroutes >= 1


def test_simulation_packet_loss_drop(small_graph_data: dict[str, Any]) -> None:
    """Test flows are dropped probabilistically when packet loss is present."""
    topo = _get_topo(small_graph_data)
    router = DijkstraRouter()
    
    # Set high packet loss on all edges
    for u, v in topo.edges:
        topo.update_edge(u, v, packet_loss=0.8)

    traffic = TrafficGenerator(model="uniform", n_flows_per_tick=10, seed=42)
    engine = SimulationEngine(topo, router, traffic)
    results = engine.run(duration_ticks=5, seed=42)

    # Verify that some loss was recorded
    total_loss_rate = sum(m.packet_loss_rate for m in results.results) / len(results.results)
    assert total_loss_rate > 0.0
