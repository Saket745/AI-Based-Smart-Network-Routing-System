"""Unit tests for refactored NetworkRoutingEnv methods."""

from __future__ import annotations

from typing import Any

from nroute.core.topology import Topology
from nroute.ml.rl_env import NetworkRoutingEnv


def _get_topo(small_graph_data: dict[str, Any]) -> Topology:
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


def test_apply_transition(small_graph_data: dict[str, Any]) -> None:
    """Test the private _apply_transition method."""
    topo = _get_topo(small_graph_data)
    env = NetworkRoutingEnv(topology=topo)
    env.reset(seed=42)

    initial_node = env.current_node
    next_node = "B" if initial_node != "B" else "A"

    env._apply_transition(next_node)

    assert env.current_node == next_node
    assert env.path[-1] == next_node
    assert env.hops == 1
    assert env._visit_counts[next_node] == 1


def test_calculate_reward_basic(small_graph_data: dict[str, Any]) -> None:
    """Test the private _calculate_reward method for basic step."""
    topo = _get_topo(small_graph_data)
    env = NetworkRoutingEnv(
        topology=topo,
        reward_params={
            "alpha": 1.0,
            "beta": 0.0,
            "gamma": 0.0,
            "delta": 0.1,
            "proximity": 0.0,
            "fairness": 0.0,
        },
    )
    env.reset(seed=42)
    # Ensure current_node and destination are not what we're testing
    env.current_node = "A"
    env.destination = "C"

    edge_attr = {"latency": 10.0, "bandwidth": 1000.0, "packet_loss": 0.0}
    info: dict[str, Any] = {}

    # reward = alpha * (1/latency) - delta = 1.0 * (1/10.0) - 0.1 = 0.0
    reward = env._calculate_reward(
        prev_node="A", curr_node="B", edge_attr=edge_attr, visit_count_before=0, info=info
    )

    assert abs(reward) < 1e-6


def test_calculate_reward_revisit(small_graph_data: dict[str, Any]) -> None:
    """Test revisit penalty in _calculate_reward."""
    topo = _get_topo(small_graph_data)
    env = NetworkRoutingEnv(
        topology=topo,
        reward_params={
            "alpha": 0.0,
            "beta": 0.0,
            "gamma": 0.0,
            "delta": 0.0,
            "proximity": 0.0,
            "fairness": 0.0,
        },
    )
    env.reset(seed=42)
    env.current_node = "A"
    env.destination = "C"

    edge_attr = {"latency": 10.0, "bandwidth": 1000.0, "packet_loss": 0.0}
    info: dict[str, Any] = {}

    reward = env._calculate_reward(
        prev_node="A", curr_node="B", edge_attr=edge_attr, visit_count_before=1, info=info
    )

    assert reward == -10.0
    assert info.get("revisit_penalty") is True


def test_calculate_reward_destination(small_graph_data: dict[str, Any]) -> None:
    """Test destination bonus in _calculate_reward."""
    topo = _get_topo(small_graph_data)
    env = NetworkRoutingEnv(
        topology=topo,
        reward_params={
            "alpha": 0.0,
            "beta": 0.0,
            "gamma": 0.0,
            "delta": 0.0,
            "proximity": 0.0,
            "fairness": 0.0,
        },
    )
    env.reset(seed=42)

    destination = env.destination
    env.hops = 5

    edge_attr = {"latency": 10.0, "bandwidth": 1000.0, "packet_loss": 0.0}
    info: dict[str, Any] = {}

    reward = env._calculate_reward(
        prev_node="A", curr_node=destination, edge_attr=edge_attr, visit_count_before=0, info=info
    )

    # efficiency_bonus = max(10.0, 100.0 - 5 * 2.0) = 90.0
    assert reward == 90.0
