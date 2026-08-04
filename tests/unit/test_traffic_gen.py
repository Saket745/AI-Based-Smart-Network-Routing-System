"""Unit tests for the traffic generator."""

from __future__ import annotations

from typing import Any

import pytest

from nroute.core.topology import Topology
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


def test_traffic_gen_uniform(small_graph_data: dict[str, Any]) -> None:
    """Test uniform traffic generator generates flows correctly."""
    topo = _get_topo(small_graph_data)
    gen = TrafficGenerator(model="uniform", n_flows_per_tick=5, seed=42)

    flows = gen.generate(topo, tick=0)
    assert len(flows) == 5
    for flow in flows:
        assert flow.source in topo.nodes
        assert flow.destination in topo.nodes
        assert flow.source != flow.destination
        assert flow.bytes > 0
        assert flow.packets > 0
        assert flow.timestamp == 0.0


def test_traffic_gen_gravity(small_graph_data: dict[str, Any]) -> None:
    """Test gravity traffic model selection is biased by node capacities."""
    topo = _get_topo(small_graph_data)

    # Modify node capacities to create huge disparity
    # Nodes A, B capacity = 10000.0, C, D, E capacity = 1.0
    topo.add_node("A", capacity=10000.0)
    topo.add_node("B", capacity=10000.0)
    topo.add_node("C", capacity=1.0)
    topo.add_node("D", capacity=1.0)
    topo.add_node("E", capacity=1.0)

    gen = TrafficGenerator(model="gravity", n_flows_per_tick=20, seed=42)
    flows = gen.generate(topo, tick=1)

    assert len(flows) == 20
    ab_flow_count = 0
    for flow in flows:
        # Check if endpoints are A and B
        if flow.source in {"A", "B"} and flow.destination in {"A", "B"}:
            ab_flow_count += 1

    # Under gravity model, flows between A and B should be highly dominant
    assert ab_flow_count >= 15


def test_traffic_gen_hotspot(small_graph_data: dict[str, Any]) -> None:
    """Test hotspot traffic generator biases destination choices."""
    topo = _get_topo(small_graph_data)

    # We specify "D" as the only hotspot node
    gen = TrafficGenerator(model="hotspot", n_flows_per_tick=20, seed=42, hotspot_nodes=["D"])
    flows = gen.generate(topo, tick=2)

    assert len(flows) == 20
    d_count = sum(1 for f in flows if f.destination == "D")

    # Dest D should represent ~80% of choices
    assert d_count >= 12


def test_traffic_gen_bursty(small_graph_data: dict[str, Any]) -> None:
    """Test bursty traffic spikes in size and count."""
    topo = _get_topo(small_graph_data)

    # High burst probability to guarantee a burst
    gen = TrafficGenerator(
        model="bursty", n_flows_per_tick=5, seed=42, burst_prob=1.0, burst_multiplier=4.0
    )
    flows = gen.generate(topo, tick=3)

    # 5 * 4 = 20 flows
    assert len(flows) == 20
    for flow in flows:
        assert flow.bytes >= 2000  # elevated byte counts during burst


def test_traffic_gen_reproducibility(small_graph_data: dict[str, Any]) -> None:
    """Test that a fixed seed produces identical traffic flows."""
    topo = _get_topo(small_graph_data)

    gen1 = TrafficGenerator(model="uniform", n_flows_per_tick=5, seed=100)
    gen2 = TrafficGenerator(model="uniform", n_flows_per_tick=5, seed=100)

    flows1 = gen1.generate(topo, tick=0)
    flows2 = gen2.generate(topo, tick=0)

    assert len(flows1) == len(flows2)
    for f1, f2 in zip(flows1, flows2, strict=False):
        assert f1.source == f2.source
        assert f1.destination == f2.destination
        assert f1.bytes == f2.bytes
        assert f1.packets == f2.packets
        assert f1.protocol == f2.protocol


def test_traffic_gen_hotspot_auto_selection(small_graph_data: dict[str, Any]) -> None:
    """Test hotspot traffic generator auto-selects hotspots if not provided."""
    topo = _get_topo(small_graph_data)
    # Give node 'E' a high capacity
    topo.add_node("E", capacity=50000.0)

    gen = TrafficGenerator(model="hotspot", n_flows_per_tick=20, seed=42)
    flows = gen.generate(topo, tick=0)

    assert len(flows) == 20
    # Node E should be one of the top capacity nodes and thus a hotspot
    e_dest_count = sum(1 for f in flows if f.destination == "E")
    assert e_dest_count > 0


def test_traffic_gen_invalid_model(small_graph_data: dict[str, Any]) -> None:
    """Test that an invalid traffic model raises ValueError."""
    topo = _get_topo(small_graph_data)
    gen = TrafficGenerator(model="invalid_model")
    with pytest.raises(ValueError, match="Unknown traffic model 'invalid_model'"):
        gen.generate(topo)
