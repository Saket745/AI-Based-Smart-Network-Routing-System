"""Unit tests for the SimulationEngine focused on edge cases and error handling."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from nroute.core.topology import Topology
from nroute.core.traffic import FlowRecord
from nroute.simulation.engine import SimulationEngine
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


def test_engine_custom_config(small_graph_data: dict[str, Any]) -> None:
    """Test engine with custom configuration (tick_duration)."""
    topo = _get_topo(small_graph_data)
    router = MagicMock()
    traffic = MagicMock(spec=TrafficGenerator)
    traffic.generate.return_value = []
    traffic.model = "mock"

    # Mock NRouteConfig-like object
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

    # Flow should be dropped
    assert results.results[0].packet_loss_rate == 1.0
    assert any("routing_failed_ingress" in reason for _, reason in engine.last_tick_dropped_flows)


def test_engine_midflow_reroute_failure(small_graph_data: dict[str, Any]) -> None:
    """Test engine when rerouting fails mid-flow."""
    topo = _get_topo(small_graph_data)
    router = MagicMock()
    # Initial path: A -> B -> D
    router.compute_path.side_effect = [
        ["A", "B", "D"],  # Initial
        Exception("Reroute failed"),  # Reroute attempt
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
            # Force link B->D down for the next tick
            eng.topology.update_edge("B", "D", status="down")

    results = engine.run(duration_ticks=2, show_progress=False, callback=callback)

    # Tick 1: B->D is down. Detects B->D down. Tries reroute from B to D. Fails.
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

    # Mock get_edge and get_node to raise exception during Tick 0 forwarding
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
        # Tick 0: Route A->B->D. Forward A->B.
        # Edge u=A, v=B. get_edge(A, B) fails -> edge_down=True.
        # Reroute attempt from A to D. Let's make reroute succeed to avoid drop.
        router.compute_path.side_effect = [["A", "B", "D"], ["A", "C", "E", "D"]]

        results = engine.run(duration_ticks=1, show_progress=False)

    assert results.results[0].reroute_count >= 1


def test_engine_forwarding_exception(small_graph_data: dict[str, Any]) -> None:
    """Test engine handling exceptions during forwarding (lines 205-207)."""
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

    # We want edge_down/node_down to be False, but line 202 to fail.
    # get_edge is called at 172 and 202.
    call_count = 0
    original_get_edge = topo.get_edge

    def mock_get_edge(u, v):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # Second call for A->B in tick 0
            raise Exception("Fail at line 202")
        return original_get_edge(u, v)

    with patch.object(Topology, "get_edge", side_effect=mock_get_edge):
        engine.run(duration_ticks=1, show_progress=False)

    # Should hit lines 206-207 and continue


def test_engine_link_utilization_exception(small_graph_data: dict[str, Any]) -> None:
    """Test engine handling exceptions during link utilization update (lines 297-298)."""
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

    # Tick 0: flow added to active_flows.
    # Tick 1: _update_link_utilizations will process the flow.
    with patch.object(Topology, "update_edge", side_effect=Exception("Update failed")):
        engine.run(duration_ticks=2, show_progress=False)
    # Should complete without raising


def test_engine_already_completed_flow_handling(small_graph_data: dict[str, Any]) -> None:
    """Test engine handling a flow state that somehow has hop_idx already at end."""
    topo = _get_topo(small_graph_data)
    router = MagicMock()
    router.compute_path.return_value = ["A", "B"]

    flow = FlowRecord(
        source="A",
        destination="B",
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
            # Add a flow that is already at destination
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
