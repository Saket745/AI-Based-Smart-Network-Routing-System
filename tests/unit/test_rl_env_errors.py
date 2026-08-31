"""Unit tests for error paths, edge cases, transitions, and reward calculation in NetworkRoutingEnv."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from nroute.core.topology import Topology
from nroute.exceptions import TopologyError
from nroute.ml.rl_env import NetworkRoutingEnv


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


def test_init_too_few_nodes() -> None:
    """Test that TopologyError is raised if topology has fewer than 2 nodes."""
    topo = Topology()
    topo.add_node("A")
    with pytest.raises(TopologyError, match="Topology must contain at least 2 nodes"):
        NetworkRoutingEnv(topology=topo)


def test_precompute_distances_inner_exception(small_graph_data: dict[str, Any]) -> None:
    """Test the inner exception handling in _precompute_distances."""
    topo = _get_topo(small_graph_data)

    with patch("networkx.single_source_shortest_path_length") as mock_bfs:

        def side_effect(_graph, source):
            if source == "A":
                raise ValueError("BFS failure")
            return {source: 0}

        mock_bfs.side_effect = side_effect

        env = NetworkRoutingEnv(topology=topo)
        assert env._shortest_distances["A"] == {}
        assert "B" in env._shortest_distances
        assert env._shortest_distances["B"] == {"B": 0}


def test_precompute_distances_outer_exception(small_graph_data: dict[str, Any]) -> None:
    """Test the outer exception handling in _precompute_distances."""
    topo = _get_topo(small_graph_data)

    with patch.object(NetworkRoutingEnv, "_precompute_distances", side_effect=None):
        env = NetworkRoutingEnv(topology=topo)

    env.nodes = None  # type: ignore
    env._shortest_distances = {"existing": "data"}
    env._precompute_distances()


def test_init_no_edges() -> None:
    """Test that max_out_degree is set to 1 if there are nodes but no edges."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    env = NetworkRoutingEnv(topology=topo)
    assert env.num_edges == 0
    assert env.max_out_degree == 1


def test_reset_too_few_up_nodes(small_graph_data: dict[str, Any]) -> None:
    """Test that reset raises TopologyError if fewer than 2 nodes are 'up'."""
    topo = _get_topo(small_graph_data)
    for node in topo.nodes:
        if node != "A":
            topo.set_node_down(node)

    env = NetworkRoutingEnv(topology=topo)
    with pytest.raises(TopologyError, match="Topology must have at least 2 active"):
        env.reset()


def test_step_link_down(small_graph_data: dict[str, Any]) -> None:
    """Test that stepping onto a down link/node results in failure and penalty."""
    topo = _get_topo(small_graph_data)
    env = NetworkRoutingEnv(topology=topo, training_mode=False)

    env.reset(seed=42)
    env.current_node = "A"
    neighbors = sorted(list(env.topology.neighbors("A")))
    b_idx = neighbors.index("B")

    env.topology.set_link_down("A", "B")

    _obs, reward, terminated, _truncated, info = env.step(b_idx)
    assert terminated
    assert reward == -50.0
    assert info["status"] == "failed_link_down"


def test_step_node_down(small_graph_data: dict[str, Any]) -> None:
    """Test that stepping onto a down node results in failure and penalty."""
    topo = _get_topo(small_graph_data)
    env = NetworkRoutingEnv(topology=topo, training_mode=False)

    env.reset(seed=42)
    env.current_node = "A"
    neighbors = sorted(list(env.topology.neighbors("A")))
    b_idx = neighbors.index("B")

    env.topology.set_node_down("B")

    _obs, reward, terminated, _truncated, info = env.step(b_idx)
    assert terminated
    assert reward == -50.0
    assert info["status"] == "failed_link_down"


def test_step_max_hops(small_graph_data: dict[str, Any]) -> None:
    """Test that exceeding max_hops results in truncation."""
    topo = _get_topo(small_graph_data)
    env = NetworkRoutingEnv(topology=topo, max_hops=1, training_mode=False)

    env.reset(seed=42)
    neighbors = sorted(list(topo.neighbors(env.current_node)))

    action = 0
    next_node = neighbors[action]
    if next_node == env.destination:
        action = 1

    _obs, _reward, _terminated, truncated, _info = env.step(action)
    if not truncated:
        env.hops = 1
        _obs, _reward, _terminated, truncated, _info = env.step(0)

    assert truncated
    assert _info["status"] == "truncated_max_hops"
    assert _reward < 0


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
    env.current_node = "A"
    env.destination = "C"

    edge_attr = {"latency": 10.0, "bandwidth": 1000.0, "packet_loss": 0.0}
    info: dict[str, Any] = {}

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

    assert reward == 90.0
