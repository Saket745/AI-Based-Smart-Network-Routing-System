"""Unit tests for the SimulationEngine."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from nroute.core.topology import Topology
from nroute.core.traffic import FlowRecord
from nroute.routing.base import BaseRouter
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


@pytest.fixture
def engine_setup(small_graph_data: dict[str, Any]) -> tuple[SimulationEngine, Topology, MagicMock, MagicMock]:
    topo = _get_topo(small_graph_data)
    router = MagicMock(spec=BaseRouter)
    traffic_gen = MagicMock(spec=TrafficGenerator)
    traffic_gen.model = "mock"
    engine = SimulationEngine(topo, router, traffic_gen)
    return engine, topo, router, traffic_gen


def test_engine_init(engine_setup: tuple[SimulationEngine, Topology, MagicMock, MagicMock]) -> None:
    engine, _, router, traffic_gen = engine_setup
    assert engine.topology is not None
    assert engine.router == router
    assert engine.traffic_generator == traffic_gen
    assert len(engine.active_flows) == 0


def test_update_link_utilizations(engine_setup: tuple[SimulationEngine, Topology, MagicMock, MagicMock]) -> None:
    engine, _, _, _ = engine_setup

    # Create a mock flow
    # Bandwidth demand = (bytes * 8) / (duration * 1e6)
    # 1.25 MB * 8 = 10,000,000 bits = 10 Megabits
    # If duration = 1.0s, demand is 10 Mbps
    flow = FlowRecord(
        source="A",
        destination="D",
        bytes=1250000,
        packets=1000,
        duration=1.0,
        protocol="TCP",
        timestamp=0.0
    )

    engine.active_flows = [
        {
            "flow": flow,
            "path": ["A", "B", "D"],
            "current_hop_idx": 0,
            "accumulated_latency": 0.0,
        }
    ]

    # Edge A->B has 1000 Mbps bandwidth in fixture.
    # Expected utilization = 10 / 1000 = 0.01

    engine._update_link_utilizations()

    edge_data = engine.topology.get_edge("A", "B")
    assert edge_data["utilization"] == pytest.approx(0.01)

    # Other edges should be 0
    assert engine.topology.get_edge("B", "D")["utilization"] == 0.0


def test_run_basic_flow_completion(engine_setup: tuple[SimulationEngine, Topology, MagicMock, MagicMock]) -> None:
    engine, _, router, traffic_gen = engine_setup

    # Flow from A to B (1 hop)
    flow = FlowRecord(
        source="A",
        destination="B",
        bytes=125000, # 1 Mbps
        packets=10,
        duration=1.0,
        protocol="UDP",
        timestamp=0.0
    )
    traffic_gen.generate.side_effect = [[flow], []]
    router.compute_path.return_value = ["A", "B"]

    results = engine.run(duration_ticks=2, show_progress=False)

    assert len(results.results) == 2
    # Should complete in Tick 0 because it's only 1 hop
    assert results.results[0].throughput == 1.0
    assert len(engine.active_flows) == 0


def test_run_multi_hop_flow(engine_setup: tuple[SimulationEngine, Topology, MagicMock, MagicMock]) -> None:
    engine, _, router, traffic_gen = engine_setup

    # Flow from A to D via B (2 hops)
    flow = FlowRecord(
        source="A",
        destination="D",
        bytes=1000,
        packets=1,
        duration=1.0,
        protocol="TCP",
        timestamp=0.0
    )
    traffic_gen.generate.side_effect = [[flow], [], []]
    router.compute_path.return_value = ["A", "B", "D"]

    results = engine.run(duration_ticks=3, show_progress=False)

    # Tick 0: Generates, forwards A->B. Remains active at B.
    assert results.results[0].throughput == 0.0
    assert results.results[0].active_flows == 1

    # Tick 1: Forwards B->D. Reaches destination.
    assert results.results[1].throughput > 0.0
    assert results.results[1].active_flows == 0

    # Check that flow duration was updated based on accumulated latency
    # Edge A-B: 10ms, B-D: 5ms. Total 15ms. 15ms / 1000.0 = 0.015s
    assert flow.duration == 0.015


def test_run_routing_failure_ingress(engine_setup: tuple[SimulationEngine, Topology, MagicMock, MagicMock]) -> None:
    engine, _, router, traffic_gen = engine_setup

    flow = FlowRecord(
        source="A",
        destination="D",
        bytes=1000,
        packets=1,
        duration=1.0,
        protocol="TCP",
        timestamp=0.0
    )
    traffic_gen.generate.return_value = [flow]
    router.compute_path.side_effect = Exception("No path found")

    results = engine.run(duration_ticks=1, show_progress=False)

    assert results.results[0].packet_loss_rate == 1.0
    assert len(engine.active_flows) == 0


def test_run_midflow_failure_reroute(engine_setup: tuple[SimulationEngine, Topology, MagicMock, MagicMock]) -> None:
    engine, _, router, traffic_gen = engine_setup

    flow = FlowRecord(
        source="A",
        destination="D",
        bytes=1000,
        packets=1,
        duration=1.0,
        protocol="TCP",
        timestamp=0.0
    )
    traffic_gen.generate.side_effect = [[flow], [], [], []]

    # Initially A -> B -> D
    # At tick 1, flow is at node B. B->D fails. Reroute from B to D.
    router.compute_path.side_effect = [
        ["A", "B", "D"], # Initial path
        ["B", "E", "D"]  # Reroute from B when B->D fails
    ]

    injector = FailureInjector()
    injector.schedule_link_failure("B", "D", tick=1)
    engine.failure_injector = injector

    results = engine.run(duration_ticks=4, show_progress=False)

    # Tick 0: Starts at A. Forwards A->B. current_hop_idx=1.
    # Tick 1: B->D fails. Flow at B. Reroutes to ["B", "E", "D"].
    #         current_hop_idx reset to 0.
    #         Then it forwards B->E in same tick. current_hop_idx=1.
    # Tick 2: Forwards E->D. Finishes.

    total_reroutes = sum(r.reroute_count for r in results.results)
    assert total_reroutes == 1
    assert results.results[2].throughput > 0.0


def test_run_packet_loss(engine_setup: tuple[SimulationEngine, Topology, MagicMock, MagicMock]) -> None:
    engine, _, router, traffic_gen = engine_setup

    # Set 100% packet loss on A->B
    engine.topology.update_edge("A", "B", packet_loss=1.0)

    flow = FlowRecord(
        source="A",
        destination="B",
        bytes=1000,
        packets=1,
        duration=1.0,
        protocol="TCP",
        timestamp=0.0
    )
    traffic_gen.generate.return_value = [flow]
    router.compute_path.return_value = ["A", "B"]

    results = engine.run(duration_ticks=1, show_progress=False)

    # Tick 0: Route found, added to active flows.
    # Then it tries to forward A->B, hits 100% loss.
    assert results.results[0].packet_loss_rate == 1.0
    assert len(engine.active_flows) == 0


def test_run_callback(engine_setup: tuple[SimulationEngine, Topology, MagicMock, MagicMock]) -> None:
    engine, _, _, traffic_gen = engine_setup
    callback = MagicMock()

    traffic_gen.generate.return_value = []

    engine.run(duration_ticks=3, callback=callback, show_progress=False)

    assert callback.call_count == 3
    # Check arguments: tick and engine
    callback.assert_called_with(2, engine)


def test_rerouting_failure_midflow(engine_setup: tuple[SimulationEngine, Topology, MagicMock, MagicMock]) -> None:
    engine, _, router, traffic_gen = engine_setup

    flow = FlowRecord(
        source="A",
        destination="D",
        bytes=1000,
        packets=1,
        duration=1.0,
        protocol="TCP",
        timestamp=0.0
    )
    traffic_gen.generate.side_effect = [[flow], [], []]

    # Initially A -> B -> D
    router.compute_path.side_effect = [
        ["A", "B", "D"], # Initial path
        Exception("No alternative path") # Reroute failure
    ]

    injector = FailureInjector()
    injector.schedule_link_failure("B", "D", tick=1)
    engine.failure_injector = injector

    results = engine.run(duration_ticks=2, show_progress=False)

    # Tick 1: B->D fails. Reroute fails. Flow dropped.
    assert results.results[1].packet_loss_rate == 1.0
    assert len(engine.active_flows) == 0
