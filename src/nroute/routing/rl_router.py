"""Reinforcement learning-based routing strategy."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

from stable_baselines3 import DQN, PPO

from nroute.exceptions import ModelError, RoutingError
from nroute.ml.rl_env import NetworkRoutingEnv
from nroute.routing.base import BaseRouter
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
    """

    def __init__(
        self,
        topology: Topology | None = None,
        algorithm: str = "ppo",
    ) -> None:
        """
        Initialize the RLRouter.

        Args:
            topology: Optional topology context.
            algorithm: RL algorithm: "ppo" | "dqn".
        """
        self.topology = topology
        self.algorithm = algorithm.lower().strip()
        self.model: Any = None
        self.is_trained = False

        if self.algorithm not in {"ppo", "dqn"}:
            raise ValueError(f"Unknown RL algorithm '{algorithm}'. Supported: ppo, dqn.")

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
        env = NetworkRoutingEnv(self.topology)

        # Seeding environment
        if seed is not None:
            env.reset(seed=seed)

        # Estimate timesteps needed
        # We assume average episode duration is max_hops (20)
        total_timesteps = episodes * env.max_hops

        logger.info(
            f"Training RL agent using {self.algorithm.upper()} for {episodes} episodes ({total_timesteps} steps)..."
        )

        if self.algorithm == "ppo":
            self.model = PPO(
                "MlpPolicy",
                env,
                verbose=0,
                seed=seed,
                learning_rate=0.0003,
                n_steps=256,
                batch_size=64,
            )
        else:  # dqn
            self.model = DQN(
                "MlpPolicy",
                env,
                verbose=0,
                seed=seed,
                learning_rate=0.001,
                buffer_size=10000,
                batch_size=64,
            )

        self.model.learn(total_timesteps=total_timesteps)
        self.is_trained = True
        logger.info("RL training completed successfully.")

        return {
            "algorithm": self.algorithm,
            "episodes": episodes,
            "total_timesteps": total_timesteps,
            "is_trained": True,
        }

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
    ) -> list[str]:
        """
        Compute path from source to destination. Falls back to Dijkstra if model is not trained.

        Args:
            topology: The network topology.
            source: Source node ID.
            destination: Destination node ID.
            weight: Unused, kept for signature compatibility (RL works on multi-attribute state).
        """
        # 1. Fallback if not trained
        if not self.is_trained or self.model is None:
            logger.warning("RLRouter is not trained. Falling back to DijkstraRouter.")
            dijkstra = DijkstraRouter()
            return dijkstra.compute_path(topology, source, destination, weight=weight)

        # 2. Run RL inference step-by-step
        try:
            # Create a temporary environment to run deterministic steps
            env = NetworkRoutingEnv(topology)

            # Setup env state manually to the source/destination pair
            if source not in env.node_to_idx or destination not in env.node_to_idx:
                raise RoutingError(
                    f"Source '{source}' or Destination '{destination}' not in topology."
                )

            env.current_node = source
            env.destination = destination
            env.path = [source]
            env.hops = 0

            obs = env._get_obs()
            terminated = False
            truncated = False

            while not (terminated or truncated):
                action, _ = self.model.predict(obs, deterministic=True)
                obs, _reward, terminated, truncated, info = env.step(int(action))

            if info.get("status") == "success" and env.current_node == destination:
                path = list(env.path)
                self.validate_path(topology, path, source, destination)
                return path

            # If terminated in failure
            logger.warning(
                f"RL path computation failed (env status: {info.get('status')}). Falling back to DijkstraRouter."
            )
            dijkstra = DijkstraRouter()
            return dijkstra.compute_path(topology, source, destination, weight=weight)

        except Exception as e:
            logger.error(
                f"RL path inference encountered an error: {e}. Falling back to DijkstraRouter."
            )
            dijkstra = DijkstraRouter()
            return dijkstra.compute_path(topology, source, destination, weight=weight)

    def save(self, path: str) -> None:
        """Save the trained model weights and type information."""
        if not self.is_trained or self.model is None:
            raise ModelError("Cannot save an untrained model.")

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

        # Save stable-baselines3 model weights
        self.model.save(path)

        # Save metadata info next to it
        meta_path = f"{path}.meta"
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"algorithm": self.algorithm, "is_trained": self.is_trained}, f, indent=2)
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
