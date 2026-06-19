"""Reinforcement learning-based routing strategy."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import numpy as np
from stable_baselines3 import DQN, PPO

from nroute.exceptions import ModelError, RoutingError
from nroute.ml.rl_env import NetworkRoutingEnv
from nroute.routing.base import BaseRouter, FallbackRouter
from nroute.routing.bfs import BFSRouter
from nroute.routing.dijkstra import DijkstraRouter
from nroute.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from nroute.core.topology import Topology


logger = get_logger(__name__)


class RLRouter(BaseRouter):
    """
    RL-based router that trains a neural network policy (PPO/DQN) to route packets,
    with a robust fallback to Dijkstra shortest path on failure.

    Caches the training topology's node/edge ordering so observation vectors are
    consistent between training and inference, even when the live topology changes.
    """

    def __init__(
        self,
        topology: Topology | None = None,
        algorithm: str = "ppo",
        confidence_threshold: float = 0.4,
    ) -> None:
        """
        Initialize the RLRouter.

        Args:
            topology: Optional topology context.
            algorithm: RL algorithm: "ppo" | "dqn".
            confidence_threshold: Minimum action probability to trust the RL
                policy. If the model's chosen action has probability below this
                threshold, the router falls back to Dijkstra.
        """
        self.topology = topology
        self.algorithm = algorithm.lower().strip()
        self.model: Any = None
        self.is_trained = False
        self.confidence_threshold = confidence_threshold

        # Training topology metadata — cached at train time, reused at inference
        self._training_nodes: list[str] | None = None
        self._training_edges: list[tuple[str, str]] | None = None
        self._training_node_to_idx: dict[str, int] | None = None
        self._training_edge_to_idx: dict[tuple[str, str], int] | None = None
        self._training_obs_dim: int | None = None
        self._training_max_out_degree: int | None = None
        self._training_max_hops: int = 20

        if self.algorithm not in {"ppo", "dqn"}:
            raise ValueError(f"Unknown RL algorithm '{algorithm}'. Supported: ppo, dqn.")

    def _check_topology_compatibility(self, topology: Topology) -> tuple[bool, str]:
        """Check if a live topology is compatible with the training topology.

        Returns:
            Tuple of (is_compatible, reason_string).
        """
        if self._training_nodes is None or self._training_edges is None:
            return False, "No training topology metadata available"

        live_nodes = set(sorted(topology.nodes))
        train_nodes = set(self._training_nodes)

        added_nodes = live_nodes - train_nodes
        removed_nodes = train_nodes - live_nodes

        live_edges = set(sorted(topology.edges))
        train_edges = set(self._training_edges)

        added_edges = live_edges - train_edges
        removed_edges = train_edges - live_edges

        if added_nodes or removed_nodes or added_edges or removed_edges:
            parts = []
            if added_nodes:
                parts.append(f"added_nodes={added_nodes}")
            if removed_nodes:
                parts.append(f"removed_nodes={removed_nodes}")
            if added_edges:
                parts.append(f"added_edges={len(added_edges)}")
            if removed_edges:
                parts.append(f"removed_edges={len(removed_edges)}")
            return False, f"Topology mismatch: {', '.join(parts)}"

        return True, "compatible"

    def train(
        self,
        traffic_data: Any = None,
        episodes: int = 1000,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """
        Train the RL routing agent in the Gymnasium environment.

        Args:
            traffic_data: Unused, kept for API compatibility.
            episodes: Number of episodes to train for.
            seed: Global random seed.

        Returns:
            Dictionary of training metrics.
        """
        if self.topology is None:
            raise ModelError("Cannot train RLRouter without a topology context.")

        logger.info("Initializing Gymnasium environment for RL training...")
        env = NetworkRoutingEnv(self.topology, training_mode=True)

        # Cache training topology ordering for consistent inference later
        self._training_nodes = list(env.nodes)
        self._training_edges = list(env.edges)
        self._training_node_to_idx = dict(env.node_to_idx)
        self._training_edge_to_idx = dict(env.edge_to_idx)
        self._training_obs_dim = env.obs_dim
        self._training_max_out_degree = env.max_out_degree
        self._training_max_hops = env.max_hops

        # Seeding environment
        if seed is not None:
            env.reset(seed=seed)

        # Estimate timesteps needed
        # We assume average episode duration is max_hops (20)
        total_timesteps = episodes * env.max_hops

        logger.info(
            f"Training RL agent using {self.algorithm.upper()} for {episodes} episodes ({total_timesteps} steps)..."
        )

        # Scale n_steps relative to topology size to avoid too-few-updates problem
        n_steps = min(256, max(64, env.max_hops * 4))

        if self.algorithm == "ppo":
            # Ensure batch_size divides n_steps evenly
            batch_size = min(64, n_steps)
            while n_steps % batch_size != 0 and batch_size > 1:
                batch_size -= 1

            self.model = PPO(
                "MlpPolicy",
                env,
                verbose=0,
                seed=seed,
                learning_rate=0.0003,
                n_steps=n_steps,
                batch_size=batch_size,
                n_epochs=10,
                ent_coef=0.01,  # Encourage exploration
            )
        else:  # dqn
            self.model = DQN(
                "MlpPolicy",
                env,
                verbose=0,
                seed=seed,
                learning_rate=0.001,
                buffer_size=max(10000, total_timesteps),
                batch_size=64,
                learning_starts=max(100, n_steps),
                exploration_fraction=0.3,
            )

        self.model.learn(total_timesteps=total_timesteps)
        self.is_trained = True

        # Restore edge attributes after training
        env._restore_edge_attributes()

        logger.info("RL training completed successfully.")

        return {
            "algorithm": self.algorithm,
            "episodes": episodes,
            "total_timesteps": total_timesteps,
            "n_steps": n_steps,
            "is_trained": True,
        }

    def _cascade_fallback(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
    ) -> list[str]:
        """Cascade fallback: Dijkstra -> BFS -> RoutingError."""
        fallback = FallbackRouter([DijkstraRouter(), BFSRouter()])
        return fallback.compute_path(topology, source, destination, weight=weight)

    def _get_action_confidence(self, obs: np.ndarray) -> tuple[int, float]:
        """Extract action and its probability from the RL model.

        Returns:
            Tuple of (chosen_action, action_probability).
        """
        try:
            if self.algorithm == "ppo":
                # PPO: use action_probability from the policy distribution
                obs_tensor, _ = self.model.policy.obs_to_tensor(obs)
                distribution = self.model.policy.get_distribution(obs_tensor)
                probs = distribution.distribution.probs.detach().cpu().numpy().flatten()
                action = int(np.argmax(probs))
                confidence = float(probs[action])
                return action, confidence
            else:
                # DQN: use softmax of Q-values as proxy for confidence
                obs_tensor, _ = self.model.policy.obs_to_tensor(obs)
                q_values = self.model.policy.q_net(obs_tensor).detach().cpu().numpy().flatten()
                # Softmax to get pseudo-probabilities
                exp_q = np.exp(q_values - np.max(q_values))
                probs = exp_q / exp_q.sum()
                action = int(np.argmax(q_values))
                confidence = float(probs[action])
                return action, confidence
        except Exception:
            # If confidence extraction fails, fall back to normal predict
            action, _ = self.model.predict(obs, deterministic=True)
            return int(action), 1.0  # Assume full confidence on failure

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
    ) -> list[str]:
        """
        Compute path from source to destination.

        Cascade fallback chain: RL -> Dijkstra -> BFS -> RoutingError.
        If the RL model's action confidence is below ``confidence_threshold``,
        the policy is not trusted and the cascade fallback is used instead.

        Args:
            topology: The network topology.
            source: Source node ID.
            destination: Destination node ID.
            weight: Unused, kept for signature compatibility (RL works on multi-attribute state).
        """
        # 1. Fallback if not trained
        if not self.is_trained or self.model is None:
            logger.warning("RLRouter is not trained. Using cascade fallback.")
            return self._cascade_fallback(topology, source, destination, weight=weight)

        # 2. Check topology compatibility with training topology
        is_compatible, reason = self._check_topology_compatibility(topology)
        if not is_compatible:
            logger.warning(
                f"Topology incompatible with training topology: {reason}. "
                "Using cascade fallback."
            )
            return self._cascade_fallback(topology, source, destination, weight=weight)

        # 3. Run RL inference step-by-step
        try:
            # Create inference environment with training_mode=False
            # to avoid randomizing edge attributes during inference
            env = NetworkRoutingEnv(topology, training_mode=False)

            # Verify observation space matches training
            if env.obs_dim != self._training_obs_dim:
                logger.warning(
                    f"Observation dimension mismatch (training={self._training_obs_dim}, "
                    f"inference={env.obs_dim}). Using cascade fallback."
                )
                return self._cascade_fallback(topology, source, destination, weight=weight)

            # Setup env state manually to the source/destination pair
            if source not in env.node_to_idx or destination not in env.node_to_idx:
                raise RoutingError(
                    f"Source '{source}' or Destination '{destination}' not in topology."
                )

            env.current_node = source
            env.destination = destination
            env.path = [source]
            env.hops = 0
            env._visit_counts = {source: 1}

            obs = env._get_obs()
            terminated = False
            truncated = False

            while not (terminated or truncated):
                action, confidence = self._get_action_confidence(obs)

                if confidence < self.confidence_threshold:
                    logger.warning(
                        f"RL action confidence {confidence:.3f} below threshold "
                        f"{self.confidence_threshold}. Using cascade fallback."
                    )
                    return self._cascade_fallback(topology, source, destination, weight=weight)

                obs, _reward, terminated, truncated, info = env.step(action)

            if info.get("status") == "success" and env.current_node == destination:
                path = list(env.path)
                self.validate_path(topology, path, source, destination)
                return path

            # If terminated in failure
            logger.warning(
                f"RL path computation failed (env status: {info.get('status')}). "
                "Using cascade fallback."
            )
            return self._cascade_fallback(topology, source, destination, weight=weight)

        except Exception as e:
            if isinstance(e, RoutingError):
                raise
            logger.error(
                f"RL path inference encountered an error: {e}. Using cascade fallback."
            )
            return self._cascade_fallback(topology, source, destination, weight=weight)

    def save(self, path: str) -> None:
        """Save the trained model weights and type information."""
        if not self.is_trained or self.model is None:
            raise ModelError("Cannot save an untrained model.")

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

        # Save stable-baselines3 model weights
        self.model.save(path)

        # Save metadata info next to it (including training topology ordering)
        meta_path = f"{path}.meta"
        try:
            meta = {
                "algorithm": self.algorithm,
                "is_trained": self.is_trained,
                "training_nodes": self._training_nodes,
                "training_edges": (
                    [list(e) for e in self._training_edges]
                    if self._training_edges
                    else None
                ),
                "training_obs_dim": self._training_obs_dim,
                "training_max_out_degree": self._training_max_out_degree,
                "training_max_hops": self._training_max_hops,
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception as e:
            raise ModelError(f"Failed to save RLRouter metadata to {meta_path}: {e}") from e

    def load(self, path: str) -> None:
        """Load model weights and type information from file."""
        meta_path = f"{path}.meta"
        if not os.path.exists(meta_path):
            raise ModelError(f"RLRouter metadata file not found: {meta_path}")

        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            self.algorithm = meta["algorithm"]
            self.is_trained = meta["is_trained"]

            # Restore training topology metadata if present
            self._training_nodes = meta.get("training_nodes")
            training_edges_raw = meta.get("training_edges")
            if training_edges_raw is not None:
                self._training_edges = [tuple(e) for e in training_edges_raw]
                self._training_edge_to_idx = {
                    edge: idx for idx, edge in enumerate(self._training_edges)
                }
            if self._training_nodes is not None:
                self._training_node_to_idx = {
                    node: idx for idx, node in enumerate(self._training_nodes)
                }
            self._training_obs_dim = meta.get("training_obs_dim")
            self._training_max_out_degree = meta.get("training_max_out_degree")
            self._training_max_hops = meta.get("training_max_hops", 20)
        except Exception as e:
            raise ModelError(f"Failed to load RLRouter metadata from {meta_path}: {e}") from e

        try:
            if self.algorithm == "ppo":
                self.model = PPO.load(path)
            elif self.algorithm == "dqn":
                self.model = DQN.load(path)
            else:
                raise ModelError(f"Unsupported algorithm type in metadata: {self.algorithm}")
        except Exception as e:
            if isinstance(e, ModelError):
                raise
            raise ModelError(f"Failed to load stable-baselines3 model from {path}: {e}") from e
