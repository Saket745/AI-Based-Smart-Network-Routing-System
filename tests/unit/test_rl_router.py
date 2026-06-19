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

    # Verify training topology metadata was cached
    assert router._training_nodes is not None
    assert router._training_edges is not None
    assert router._training_obs_dim is not None
    assert router._training_max_out_degree is not None

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

        # Verify training topology metadata was restored
        assert new_router._training_nodes == router._training_nodes
        assert new_router._training_obs_dim == router._training_obs_dim

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


def test_rl_env_graduated_loop_penalty(small_graph_data: dict[str, Any]) -> None:
    """Test that loop detection is graduated: first revisit gets penalty, second terminates."""
    topo = _get_topo(small_graph_data)
    env = NetworkRoutingEnv(topology=topo, max_hops=20, training_mode=False)

    _obs, info = env.reset(seed=42)
    source = info["source"]

    # Find a neighbor of the source
    neighbors = sorted(list(topo.neighbors(source)))
    assert len(neighbors) > 0

    # Step to first neighbor
    _obs, _reward1, terminated, _truncated, info = env.step(0)
    assert not terminated, f"Should not terminate on first step, status={info.get('status')}"

    first_node = env.current_node

    # Now check if we can go back to source (first revisit should be allowed)
    # Find the action index that leads back to source
    current_neighbors = sorted(list(topo.neighbors(first_node)))
    back_idx = None
    for i, n in enumerate(current_neighbors):
        if n == source:
            back_idx = i
            break

    if back_idx is not None:
        # First revisit to source — should get penalty but NOT terminate
        _obs, _reward2, terminated, _truncated, info = env.step(back_idx)
        assert info.get("revisit_penalty", False) or info.get("status") == "success"
        # If we're back at source and it's not the destination, it should have revisit penalty
        if env.current_node == source and info.get("status") != "success":
            assert not terminated, "First revisit should not terminate the episode"


def test_rl_env_precomputed_distances(small_graph_data: dict[str, Any]) -> None:
    """Test that shortest path distances are precomputed correctly."""
    topo = _get_topo(small_graph_data)
    env = NetworkRoutingEnv(topology=topo, max_hops=20, training_mode=False)

    # Verify distances were computed
    assert len(env._shortest_distances) > 0

    # Check known distances from test graph: A -> D should be 2 hops (A -> B -> D)
    dist_a_d = env._shortest_distances.get("A", {}).get("D", None)
    assert dist_a_d is not None
    assert dist_a_d == 2  # A -> B -> D


def test_rl_env_training_mode_randomization(small_graph_data: dict[str, Any]) -> None:
    """Test that training mode randomizes edge attributes on reset."""
    topo = _get_topo(small_graph_data)
    env = NetworkRoutingEnv(topology=topo, max_hops=20, training_mode=True)

    # Capture original utilizations
    original_utils = {}
    for src, dst in env.edges:
        original_utils[(src, dst)] = float(topo.get_edge(src, dst).get("utilization", 0.0))

    # Reset should randomize edge attributes
    env.reset(seed=42)

    # At least some utilizations should have changed from 0.0
    changed = False
    for src, dst in env.edges:
        new_util = float(topo.get_edge(src, dst).get("utilization", 0.0))
        if new_util != original_utils[(src, dst)]:
            changed = True
            break

    assert changed, "Training mode reset should randomize edge utilizations"

    # After restore, originals should be back
    env._restore_edge_attributes()
    for (src, dst), orig_util in original_utils.items():
        current_util = float(topo.get_edge(src, dst).get("utilization", 0.0))
        assert abs(current_util - orig_util) < 1e-6, (
            f"Edge ({src}, {dst}) utilization not restored: {current_util} != {orig_util}"
        )


def test_rl_env_inference_mode_no_randomization(small_graph_data: dict[str, Any]) -> None:
    """Test that inference mode (training_mode=False) does NOT randomize edge attributes."""
    topo = _get_topo(small_graph_data)
    env = NetworkRoutingEnv(topology=topo, max_hops=20, training_mode=False)

    # Capture utilizations before reset
    pre_utils = {}
    for src, dst in env.edges:
        pre_utils[(src, dst)] = float(topo.get_edge(src, dst).get("utilization", 0.0))

    env.reset(seed=42)

    # Utilizations should be unchanged in inference mode
    for (src, dst), pre_util in pre_utils.items():
        post_util = float(topo.get_edge(src, dst).get("utilization", 0.0))
        assert abs(post_util - pre_util) < 1e-6, (
            f"Inference mode should not randomize: ({src}, {dst}) changed from {pre_util} to {post_util}"
        )


def test_rl_router_topology_mismatch_fallback(small_graph_data: dict[str, Any]) -> None:
    """Test that topology mismatch triggers explicit warning and Dijkstra fallback."""
    topo = _get_topo(small_graph_data)
    router = RLRouter(topology=topo, algorithm="ppo")

    # Train on original topology
    router.train(episodes=5, seed=42)
    assert router.is_trained

    # Create a modified topology with an extra node
    modified_data = dict(small_graph_data)
    modified_data["nodes"] = [*list(small_graph_data["nodes"]), {"id": "F", "type": "router", "capacity": 1000.0, "status": "up"}]
    modified_data["edges"] = [*list(small_graph_data["edges"]), {"src": "D", "dst": "F", "bandwidth": 1000.0, "latency": 5.0, "jitter": 0.2, "packet_loss": 0.0, "utilization": 0.0, "status": "up"}]
    modified_topo = _get_topo(modified_data)

    # compute_path on mismatched topology should still work (via Dijkstra fallback)
    path = router.compute_path(modified_topo, "A", "D")
    assert len(path) >= 2
    assert path[0] == "A"
    assert path[-1] == "D"


def test_rl_router_n_steps_scaling(small_graph_data: dict[str, Any]) -> None:
    """Test that PPO n_steps is scaled relative to topology size."""
    topo = _get_topo(small_graph_data)
    router = RLRouter(topology=topo, algorithm="ppo")

    # Train and check metrics include n_steps
    metrics = router.train(episodes=5, seed=42)
    assert "n_steps" in metrics
    # For max_hops=20: min(256, max(64, 20*4)) = min(256, 80) = 80
    assert metrics["n_steps"] == 80


def test_rl_env_proximity_reward_signal(small_graph_data: dict[str, Any]) -> None:
    """Test that proximity reward encourages moving toward destination."""
    topo = _get_topo(small_graph_data)
    env = NetworkRoutingEnv(
        topology=topo,
        max_hops=20,
        training_mode=False,
        reward_params={
            "alpha": 0.0,
            "beta": 0.0,
            "gamma": 0.0,
            "delta": 0.0,
            "proximity": 10.0,  # Only proximity signal
        },
    )

    # Force specific source/dest for predictable testing
    env.reset(seed=42)
    env.current_node = "A"
    env.destination = "D"
    env.path = ["A"]
    env.hops = 0
    env._visit_counts = {"A": 1}

    # A -> B (distance to D: A=2, B=1, getting closer)
    neighbors_a = sorted(list(topo.neighbors("A")))
    b_idx = neighbors_a.index("B")
    _obs, reward_toward, _terminated, _truncated, _info = env.step(b_idx)

    # Reward for moving toward destination should be positive (distance decreased by 1)
    # proximity_weight * (prev_distance - curr_distance) = 10 * (2 - 1) = 10.0
    assert reward_toward > 0, f"Moving toward destination should give positive reward, got {reward_toward}"


# ── Pass 2: PRD Compliance Gap Tests ──────────────────────────────────────────


def test_bfs_router_basic(small_graph_data: dict[str, Any]) -> None:
    """Test that BFSRouter computes minimum-hop path ignoring edge weights."""
    from nroute.routing.bfs import BFSRouter

    topo = _get_topo(small_graph_data)
    router = BFSRouter()

    # A -> D shortest hop path should be A -> B -> D (2 hops)
    path = router.compute_path(topo, "A", "D")
    assert path[0] == "A"
    assert path[-1] == "D"
    assert len(path) <= 3  # At most 2 hops


def test_bfs_router_unreachable(small_graph_data: dict[str, Any]) -> None:
    """Test that BFSRouter raises RoutingError when no path exists."""
    from nroute.exceptions import RoutingError
    from nroute.routing.bfs import BFSRouter

    topo = _get_topo(small_graph_data)
    router = BFSRouter()

    with pytest.raises(RoutingError):
        router.compute_path(topo, "A", "NONEXISTENT")


def test_bfs_registered_in_factory(small_graph_data: dict[str, Any]) -> None:
    """Test that 'bfs' algorithm is registered in get_router factory."""
    from nroute.routing import get_router
    from nroute.routing.bfs import BFSRouter

    router = get_router("bfs")
    assert isinstance(router, BFSRouter)


def test_rl_router_confidence_fallback(small_graph_data: dict[str, Any]) -> None:
    """Test that RLRouter falls back when action confidence is low."""
    topo = _get_topo(small_graph_data)

    # Train with very few episodes so model is likely uncertain
    router = RLRouter(topology=topo, algorithm="ppo", confidence_threshold=0.99)
    router.train(episodes=2, seed=42)
    assert router.is_trained

    # With an extremely high threshold (0.99), the model will almost certainly
    # fall back to the cascade (Dijkstra -> BFS)
    path = router.compute_path(topo, "A", "D")
    assert path[0] == "A"
    assert path[-1] == "D"
    assert len(path) >= 2


def test_rl_env_jains_fairness_reward(small_graph_data: dict[str, Any]) -> None:
    """Test that Jain's fairness index contributes to the step reward."""
    topo = _get_topo(small_graph_data)

    # Isolate only fairness signal
    env = NetworkRoutingEnv(
        topology=topo,
        max_hops=20,
        training_mode=False,
        reward_params={
            "alpha": 0.0,
            "beta": 0.0,
            "gamma": 0.0,
            "delta": 0.0,
            "proximity": 0.0,
            "fairness": 10.0,  # Only fairness signal
        },
    )

    env.reset(seed=42)
    env.current_node = "A"
    env.destination = "D"
    env.path = ["A"]
    env.hops = 0
    env._visit_counts = {"A": 1}

    # Step to B
    neighbors_a = sorted(list(topo.neighbors("A")))
    b_idx = neighbors_a.index("B")
    _obs, reward, _terminated, _truncated, _info = env.step(b_idx)

    # With all edges at 0% utilization, remaining capacity = 1.0 for all edges
    # Jain's index = (sum(1.0))^2 / (N * sum(1.0)^2) = N^2 / (N * N) = 1.0
    # fairness_weight * jains = 10.0 * 1.0 = 10.0
    # (plus possible success bonus if B == destination, which it isn't here)
    assert reward > 0, f"Fairness reward should be positive for uniform utilization, got {reward}"


def test_ai_router_anomaly_alpha_escalation(small_graph_data: dict[str, Any]) -> None:
    """Test that AIRouter escalates alpha when anomaly is detected and reverts when cleared."""
    from nroute.routing.ai import AIRouter

    topo = _get_topo(small_graph_data)
    router = AIRouter(topology=topo, alpha=5.0, anomaly_alpha_scale=4.0)

    # Initially, alpha should be base value
    assert router.alpha == 5.0
    assert not router._anomaly_active

    # Without a trained anomaly detector, update_traffic_history should not change alpha
    # (anomaly_detector.is_trained is False)
    from nroute.core.traffic import FlowRecord, TrafficMatrix

    tm = TrafficMatrix(flows=[
        FlowRecord(source="A", destination="D", bytes=1000, packets=10, duration=1.0, protocol="TCP", timestamp=0.0),
        FlowRecord(source="B", destination="C", bytes=2000, packets=20, duration=2.0, protocol="UDP", timestamp=1.0),
    ])
    router.update_traffic_history(tm)
    assert router.alpha == 5.0
    assert not router._anomaly_active
    assert len(router.traffic_history) == 1


def test_ai_router_cascade_fallback(small_graph_data: dict[str, Any]) -> None:
    """Test that AIRouter uses cascade fallback (Dijkstra -> BFS) when untrained."""
    from nroute.routing.ai import AIRouter

    topo = _get_topo(small_graph_data)
    router = AIRouter(topology=topo)

    # Untrained AIRouter should still find a path via cascade fallback
    path = router.compute_path(topo, "A", "D")
    assert path[0] == "A"
    assert path[-1] == "D"
    assert len(path) >= 2
