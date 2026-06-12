"""Unit tests for the Gymnasium RL environment and RLRouter."""

from __future__ import annotations

import os
import tempfile
from typing import Any

import pytest

from nroute.core.topology import Topology
from nroute.exceptions import ModelError
from nroute.ml.rl_env import NetworkRoutingEnv
from nroute.routing.rl_router import RLRouter


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


def test_rl_environment_lifecycle(small_graph_data: dict[str, Any]) -> None:
    """Test that NetworkRoutingEnv resets, steps, and computes rewards correctly."""
    topo = _get_topo(small_graph_data)
    env = NetworkRoutingEnv(topology=topo, max_hops=5)

    assert env.observation_space.shape == (4 * len(topo.nodes) + 5 * len(topo.edges),)
    assert env.action_space.n == env.max_out_degree

    obs, info = env.reset(seed=42)
    assert obs.shape == env.observation_space.shape
    assert info["source"] != info["destination"]
    assert info["hops"] == 0

    # Step transition
    action = 0  # Choose first neighbor in sorted successors list
    next_obs, reward, terminated, truncated, step_info = env.step(action)

    assert next_obs.shape == env.observation_space.shape
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert "status" in step_info


def test_rl_router_fallback(small_graph_data: dict[str, Any]) -> None:
    """Test that untrained RLRouter falls back to Dijkstra shortest path."""
    topo = _get_topo(small_graph_data)
    router = RLRouter(topology=topo, algorithm="ppo")

    assert not router.is_trained

    # Path A -> D should be standard shortest path: A -> B -> D
    path = router.compute_path(topo, "A", "D")
    assert path == ["A", "B", "D"]


def test_rl_router_training_and_saving(small_graph_data: dict[str, Any]) -> None:
    """Test that RLRouter trains PPO and saves/loads weights correctly."""
    topo = _get_topo(small_graph_data)
    router = RLRouter(topology=topo, algorithm="ppo")

    # Train model for a very small amount of episodes for quick test validation
    train_metrics = router.train(episodes=5, seed=42)
    assert train_metrics["is_trained"]
    assert router.is_trained

    # Verify RL path computation (with fallback mechanism on failure)
    path = router.compute_path(topo, "A", "D")
    assert len(path) >= 2
    assert path[0] == "A"
    assert path[-1] == "D"

    # Test save/load round-trip
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "ppo_routing_model")
        router.save(model_path)

        assert os.path.exists(f"{model_path}.zip")
        assert os.path.exists(f"{model_path}.meta")

        new_router = RLRouter(topology=topo)
        new_router.load(model_path)

        assert new_router.is_trained
        assert new_router.algorithm == "ppo"

        loaded_path = new_router.compute_path(topo, "A", "D")
        assert loaded_path == path


def test_rl_router_validation_errors(small_graph_data: dict[str, Any]) -> None:
    """Test validation errors for RLRouter."""
    # Instantiation errors
    with pytest.raises(ValueError, match="Unknown RL algorithm"):
        RLRouter(algorithm="invalid_algo")

    # Training without topology context
    router = RLRouter(algorithm="ppo")
    with pytest.raises(ModelError, match="Cannot train RLRouter without a topology"):
        router.train()
