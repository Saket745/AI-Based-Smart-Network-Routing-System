"""Unit tests for the SimulationEngine and Simulator facade."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from nroute import Simulator
from nroute.core.topology import Topology
from nroute.core.traffic import FlowRecord
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

    sim_str = Simulator(topology=topo, algorithm="dijkstra", duration=5)
    assert isinstance(sim_str.router, DijkstraRouter)
    results_str = sim_str.run(seed=10)
    assert len(results_str.results) == 5


def test_simulation_failure_injection_reroute(small_graph_data: dict[str, Any]) -> None:
    """Test failure injection triggers flow rerouting and increments metrics."""
    topo = _get_topo(small_graph_data)
    router = DijkstraRouter()

    class FixedTrafficGenerator(TrafficGenerator):
        def generate(self, topology: Topology, tick: int = 0) -> list[Any]:
            if tick == 0:
                return [self._create_flow("A", "D", tick)]
            return []

    traffic = FixedTrafficGenerator(model="uniform", n_flows_per_tick=1, seed=42)

    injector = FailureInjector()
    injector.schedule_link_failure("B", "D", tick=1)

    engine = SimulationEngine(topo, router, traffic, failure_injector=injector)
    results = engine.run(duration_ticks=5, seed=42)

    total_reroutes = sum(tick_metric.reroute_count for tick_metric in results.results)
    assert total_reroutes >= 1


def test_simulation_packet_loss_drop(small_graph_data: dict[str, Any]) -> None:
    """Test flows are dropped probabilistically when packet loss is present."""
    topo = _get_topo(small_graph_data)
    router = DijkstraRouter()

    for u, v in topo.edges:
        topo.update_edge(u, v, packet_loss=0.8)

    traffic = TrafficGenerator(model="uniform", n_flows_per_tick=10, seed=42)
    engine = SimulationEngine(topo, router, traffic)
    results = engine.run(duration_ticks=5, seed=42)

    total_loss_rate = sum(m.packet_loss_rate for m in results.results) / len(results.results)
    assert total_loss_rate > 0.0


def test_engine_custom_config(small_graph_data: dict[str, Any]) -> None:
    """Test engine with custom configuration (tick_duration)."""
    topo = _get_topo(small_graph_data)
    router = MagicMock()
    traffic = MagicMock(spec=TrafficGenerator)
    traffic.generate.return_value = []
    traffic.model = "mock"

    config = MagicMock()
    config.simulation.tick_duration = 2.5

    engine = SimulationEngine(topo, router, traffic, config=config)
    results = engine.run(duration_ticks=2, show_progress=False)

    assert len(results.results) == 2
    assert results.results[0].timestamp == 0.0
    assert results.results[1].timestamp == 2.5


def test_engine_progress_bar_usage(small_graph_data: dict[str, Any]) -> None:
    """Test engine with show_progress=True (default) and verify Progress is used."""
    topo = _get_topo(small_graph_data)
    router = MagicMock()
    traffic = MagicMock(spec=TrafficGenerator)
    traffic.generate.return_value = []
    traffic.model = "mock"

    with patch("nroute.simulation.engine.Progress") as mock_progress:
        mock_instance = mock_progress.return_value
        engine = SimulationEngine(topo, router, traffic)
        engine.run(duration_ticks=2, show_progress=True)

        mock_instance.start.assert_called_once()
        mock_instance.stop.assert_called_once()
        assert mock_instance.add_task.called


def test_engine_ingress_routing_failure(small_graph_data: dict[str, Any]) -> None:
    """Test engine when initial routing fails at ingress."""
    topo = _get_topo(small_graph_data)
    router = MagicMock()
    router.compute_path.side_effect = Exception("Routing failed")

    flow = FlowRecord(
        source="A",
        destination="D",
        bytes=1000,
        packets=10,
        duration=0.1,
        protocol="TCP",
        timestamp=0.0,
    )
    traffic = MagicMock(spec=TrafficGenerator)
    traffic.generate.side_effect = lambda t, tick: [flow] if tick == 0 else []
    traffic.model = "mock"

    engine = SimulationEngine(topo, router, traffic)
    results = engine.run(duration_ticks=1, show_progress=False)

    assert results.results[0].packet_loss_rate == 1.0
    assert any("routing_failed_ingress" in reason for _, reason in engine.last_tick_dropped_flows)


def test_engine_midflow_reroute_failure(small_graph_data: dict[str, Any]) -> None:
    """Test engine when rerouting fails mid-flow."""
    topo = _get_topo(small_graph_data)
    router = MagicMock()
    router.compute_path.side_effect = [
        ["A", "B", "D"],
        Exception("Reroute failed"),
    ]

    flow = FlowRecord(
        source="A",
        destination="D",
        bytes=1000,
        packets=10,
        duration=0.1,
        protocol="TCP",
        timestamp=0.0,
    )
    traffic = MagicMock(spec=TrafficGenerator)
    traffic.generate.side_effect = lambda t, tick: [flow] if tick == 0 else []
    traffic.model = "mock"

    engine = SimulationEngine(topo, router, traffic)

    def callback(tick, eng):
        if tick == 0:
            eng.topology.update_edge("B", "D", status="down")

    results = engine.run(duration_ticks=2, show_progress=False, callback=callback)

    assert results.results[1].packet_loss_rate == 1.0
    assert any("rerouting_failed_midflow" in reason for _, reason in engine.last_tick_dropped_flows)


def test_engine_topology_exceptions(small_graph_data: dict[str, Any]) -> None:
    """Test engine handling topology access exceptions."""
    topo = _get_topo(small_graph_data)
    router = MagicMock()
    router.compute_path.return_value = ["A", "B", "D"]

    flow = FlowRecord(
        source="A",
        destination="D",
        bytes=1000,
        packets=10,
        duration=0.1,
        protocol="TCP",
        timestamp=0.0,
    )
    traffic = MagicMock(spec=TrafficGenerator)
    traffic.generate.side_effect = lambda t, tick: [flow] if tick == 0 else []
    traffic.model = "mock"

    engine = SimulationEngine(topo, router, traffic)

    original_get_edge = topo.get_edge

    def mock_get_edge(u, v):
        if u == "A" and v == "B":
            raise Exception("Edge lookup failed")
        return original_get_edge(u, v)

    original_get_node = topo.get_node

    def mock_get_node(n):
        if n == "B":
            raise Exception("Node lookup failed")
        return original_get_node(n)

    with (
        patch.object(Topology, "get_edge", side_effect=mock_get_edge),
        patch.object(Topology, "get_node", side_effect=mock_get_node),
    ):
        router.compute_path.side_effect = [["A", "B", "D"], ["A", "C", "E", "D"]]
        results = engine.run(duration_ticks=1, show_progress=False)

    assert results.results[0].reroute_count >= 1


def test_engine_forwarding_exception(small_graph_data: dict[str, Any]) -> None:
    """Test engine handling exceptions during forwarding."""
    topo = _get_topo(small_graph_data)
    router = MagicMock()
    router.compute_path.return_value = ["A", "B", "D"]

    flow = FlowRecord(
        source="A",
        destination="D",
        bytes=1000,
        packets=10,
        duration=0.1,
        protocol="TCP",
        timestamp=0.0,
    )
    traffic = MagicMock(spec=TrafficGenerator)
    traffic.generate.side_effect = lambda t, tick: [flow] if tick == 0 else []
    traffic.model = "mock"

    engine = SimulationEngine(topo, router, traffic)

    call_count = 0
    original_get_edge = topo.get_edge

    def mock_get_edge(u, v):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise Exception("Fail at line 202")
        return original_get_edge(u, v)

    with patch.object(Topology, "get_edge", side_effect=mock_get_edge):
        engine.run(duration_ticks=1, show_progress=False)


def test_engine_link_utilization_exception(small_graph_data: dict[str, Any]) -> None:
    """Test engine handling exceptions during link utilization update."""
    topo = _get_topo(small_graph_data)
    router = MagicMock()
    router.compute_path.return_value = ["A", "B", "D"]

    flow = FlowRecord(
        source="A",
        destination="D",
        bytes=1000,
        packets=10,
        duration=0.1,
        protocol="TCP",
        timestamp=0.0,
    )
    traffic = MagicMock(spec=TrafficGenerator)
    traffic.generate.side_effect = lambda t, tick: [flow] if tick == 0 else []
    traffic.model = "mock"

    engine = SimulationEngine(topo, router, traffic)

    with patch.object(Topology, "update_edge", side_effect=Exception("Update failed")):
        engine.run(duration_ticks=2, show_progress=False)


def test_engine_already_completed_flow_handling(small_graph_data: dict[str, Any]) -> None:
    """Test engine handling a flow state that somehow has hop_idx already at end."""
    topo = _get_topo(small_graph_data)
    router = MagicMock()
    router.compute_path.return_value = ["A", "B"]

    traffic = MagicMock(spec=TrafficGenerator)
    traffic.generate.return_value = []
    traffic.model = "mock"

    engine = SimulationEngine(topo, router, traffic)

    def callback(tick, eng):
        if tick == 0:
            eng.active_flows.append(
                {
                    "flow": FlowRecord(
                        source="A",
                        destination="B",
                        bytes=0,
                        packets=0,
                        duration=0,
                        protocol="TCP",
                        timestamp=0,
                    ),
                    "path": ["A", "B"],
                    "current_hop_idx": 1,
                    "accumulated_latency": 0.0,
                }
            )

    engine.run(duration_ticks=2, show_progress=False, callback=callback)
    assert any(f.bytes == 0 for f in engine.last_tick_completed_flows)
