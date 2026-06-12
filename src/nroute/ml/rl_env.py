"""Gymnasium environment for network routing optimization."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from nroute.exceptions import TopologyError

if TYPE_CHECKING:
    from nroute.core.topology import Topology


class NetworkRoutingEnv(gym.Env[np.ndarray, int]):
    """
    Gymnasium environment that models a network topology for routing.

    The state space consists of the current node, target destination node,
    and current network features (capacity, utilization, latency, etc.).
    The action space selects which outgoing neighbor to forward to next.
    """

    metadata: dict[str, Any] = {"render_modes": []}

    def __init__(
        self,
        topology: Topology,
        max_hops: int = 20,
        reward_params: dict[str, float] | None = None,
    ) -> None:
        """
        Initialize the environment.

        Args:
            topology: The network topology.
            max_hops: Maximum path length before truncation.
            reward_params: Hyperparameters for reward function:
                alpha: Latency multiplier (encourages low latency).
                beta: Bandwidth multiplier (encourages high bandwidth).
                gamma: Packet loss multiplier (discourages high packet loss).
                delta: Step/hop penalty (discourages long paths).
        """
        super().__init__()
        self.topology = topology
        self.max_hops = max_hops

        # Default reward hyperparameters
        self.reward_params = reward_params or {
            "alpha": 10.0,  # Latency coefficient
            "beta": 1.0,  # Bandwidth coefficient (normalized by 1000.0)
            "gamma": 50.0,  # Packet loss coefficient
            "delta": 2.0,  # Step/hop penalty
        }

        # Keep deterministic sort of nodes and edges
        self.nodes = sorted(self.topology.nodes)
        self.edges = sorted(self.topology.edges)

        self.num_nodes = len(self.nodes)
        self.num_edges = len(self.edges)

        if self.num_nodes < 2:
            raise TopologyError("Topology must contain at least 2 nodes for routing.")

        self.node_to_idx = {node: idx for idx, node in enumerate(self.nodes)}
        self.edge_to_idx = {edge: idx for idx, edge in enumerate(self.edges)}

        # Determine max out-degree in graph
        out_degrees = [len(list(self.topology.neighbors(node))) for node in self.nodes]
        self.max_out_degree = max(out_degrees) if out_degrees else 1
        if self.max_out_degree == 0:
            self.max_out_degree = 1

        # Action space: select neighbor index from sorted successor list
        self.action_space = spaces.Discrete(self.max_out_degree)

        # Observation space size:
        # - current_node (one-hot, size num_nodes)
        # - destination_node (one-hot, size num_nodes)
        # - node capacity + status (size 2 * num_nodes)
        # - edge bandwidth + latency + utilization + loss + status (size 5 * num_edges)
        self.obs_dim = 4 * self.num_nodes + 5 * self.num_edges

        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.obs_dim,),
            dtype=np.float32,
        )

        # Episode state variables
        self.current_node = self.nodes[0]
        self.destination = self.nodes[0]
        self.path: list[str] = []
        self.hops = 0

    def reset(
        self,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Reset the environment to a random source/destination pair."""
        super().reset(seed=seed)

        # Pick active nodes for source and destination
        up_nodes = [
            n for n in self.nodes if self.topology.get_node(n).get("status", "up").lower() == "up"
        ]

        if len(up_nodes) < 2:
            raise TopologyError("Topology must have at least 2 active ('up') nodes.")

        # Ensure seed reproducibility using self.np_random
        src_idx = self.np_random.integers(0, len(up_nodes))
        dst_idx = src_idx
        while dst_idx == src_idx:
            dst_idx = self.np_random.integers(0, len(up_nodes))

        self.current_node = up_nodes[src_idx]
        self.destination = up_nodes[dst_idx]
        self.path = [self.current_node]
        self.hops = 0

        obs = self._get_obs()
        info = {
            "source": self.current_node,
            "destination": self.destination,
            "path": list(self.path),
            "hops": self.hops,
        }
        return obs, info

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """Advance the routing packet by selecting the next hop."""
        neighbors = sorted(list(self.topology.neighbors(self.current_node)))
        terminated = False
        truncated = False
        info: dict[str, Any] = {}

        # 1. Invalid action checks (exceeding neighbor list)
        if action < 0 or action >= len(neighbors):
            # Heavy penalty for invalid choice, end episode
            reward = -50.0
            terminated = True
            info["status"] = "failed_invalid_action"
            return self._get_obs(), reward, terminated, truncated, info

        next_node = neighbors[action]
        edge = (self.current_node, next_node)

        # 2. Check if next link or node is down
        node_down = self.topology.get_node(next_node).get("status", "up").lower() == "down"
        edge_down = self.topology.get_edge(*edge).get("status", "up").lower() == "down"

        if node_down or edge_down:
            # Heavy penalty for hitting a failure, end episode
            reward = -50.0
            terminated = True
            info["status"] = "failed_link_down"
            return self._get_obs(), reward, terminated, truncated, info

        # 3. Retrieve link metrics
        edge_attr = self.topology.get_edge(*edge)
        latency = float(edge_attr.get("latency", 5.0))
        bandwidth = float(edge_attr.get("bandwidth", 1000.0))
        loss = float(edge_attr.get("packet_loss", 0.0))

        # Check loop detection
        if next_node in self.path:
            reward = -20.0
            terminated = True
            info["status"] = "failed_loop_detected"
            return self._get_obs(), reward, terminated, truncated, info

        # Update path
        self.path.append(next_node)
        self.current_node = next_node
        self.hops += 1

        # 4. Compute reward
        # Step reward encourages: short hop length, low latency, high bandwidth, low loss
        alpha = self.reward_params["alpha"]
        beta = self.reward_params["beta"]
        gamma = self.reward_params["gamma"]
        delta = self.reward_params["delta"]

        step_reward = (
            alpha * (1.0 / max(0.1, latency)) + beta * (bandwidth / 1000.0) - gamma * loss - delta
        )
        reward = step_reward

        # Check if reached destination
        if self.current_node == self.destination:
            # Reached destination bonus
            reward += 100.0
            terminated = True
            info["status"] = "success"
        elif self.hops >= self.max_hops:
            truncated = True
            info["status"] = "truncated_max_hops"
        else:
            info["status"] = "moving"

        info["path"] = list(self.path)
        info["hops"] = self.hops

        return self._get_obs(), reward, terminated, truncated, info

    def _get_obs(self) -> np.ndarray:
        """Construct the 1D state observation array."""
        obs = []

        # 1. Current node index (one-hot)
        curr_idx = self.node_to_idx[self.current_node]
        curr_onehot = np.zeros(self.num_nodes, dtype=np.float32)
        curr_onehot[curr_idx] = 1.0
        obs.append(curr_onehot)

        # 2. Destination node index (one-hot)
        dst_idx = self.node_to_idx[self.destination]
        dst_onehot = np.zeros(self.num_nodes, dtype=np.float32)
        dst_onehot[dst_idx] = 1.0
        obs.append(dst_onehot)

        # 3. Node attributes (capacity + status)
        node_caps = []
        node_stats = []
        for node in self.nodes:
            attrs = self.topology.get_node(node)
            node_caps.append(
                float(attrs.get("capacity", 1000.0)) / 1000.0
            )  # simple scale normalization
            node_stats.append(1.0 if attrs.get("status", "up").lower() == "up" else 0.0)

        obs.append(np.array(node_caps, dtype=np.float32))
        obs.append(np.array(node_stats, dtype=np.float32))

        # 4. Edge attributes (bandwidth, latency, utilization, loss, status)
        edge_bws = []
        edge_lats = []
        edge_utils = []
        edge_losses = []
        edge_stats = []

        for src, dst in self.edges:
            attrs = self.topology.get_edge(src, dst)
            edge_bws.append(float(attrs.get("bandwidth", 1000.0)) / 1000.0)
            edge_lats.append(float(attrs.get("latency", 5.0)) / 100.0)
            edge_utils.append(float(attrs.get("utilization", 0.0)))
            edge_losses.append(float(attrs.get("packet_loss", 0.0)))
            edge_stats.append(1.0 if attrs.get("status", "up").lower() == "up" else 0.0)

        obs.append(np.array(edge_bws, dtype=np.float32))
        obs.append(np.array(edge_lats, dtype=np.float32))
        obs.append(np.array(edge_utils, dtype=np.float32))
        obs.append(np.array(edge_losses, dtype=np.float32))
        obs.append(np.array(edge_stats, dtype=np.float32))

        # Flatten list of arrays into a single float32 vector
        return np.concatenate(obs).astype(np.float32)
