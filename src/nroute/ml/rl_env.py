"""Gymnasium environment for network routing optimization."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import gymnasium as gym
import networkx as nx
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

    metadata: dict[str, Any] = {"render_modes": []}  # noqa: RUF012

    def __init__(
        self,
        topology: Topology,
        max_hops: int = 20,
        reward_params: dict[str, float] | None = None,
        training_mode: bool = True,
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
                proximity: Proximity-to-destination bonus weight.
                fairness: Jain's fairness index bonus weight.
            training_mode: If True, randomize edge attributes on each reset
                to expose the agent to varied congestion states.
        """
        super().__init__()
        self.topology = topology
        self.max_hops = max_hops
        self.training_mode = training_mode

        # Default reward hyperparameters (rebalanced for better learning)
        self.reward_params = reward_params or {
            "alpha": 5.0,  # Latency coefficient (reduced from 10.0)
            "beta": 1.0,  # Bandwidth coefficient (normalized by 1000.0)
            "gamma": 50.0,  # Packet loss coefficient
            "delta": 0.5,  # Step/hop penalty (reduced from 2.0)
            "proximity": 5.0,  # Proximity-to-destination bonus weight
            "fairness": 2.0,  # Jain's fairness index bonus weight
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
        # Track visit counts per node for graduated loop penalty
        self._visit_counts: dict[str, int] = {}

        # Precompute all-pairs shortest path distances for proximity reward
        self._shortest_distances: dict[str, dict[str, int]] = {}
        self._precompute_distances()

        # Store original edge attributes for training-mode perturbation
        self._original_edge_attrs: dict[tuple[str, str], dict[str, float]] = {}
        if self.training_mode:
            for src, dst in self.edges:
                attrs = self.topology.get_edge(src, dst)
                self._original_edge_attrs[(src, dst)] = {
                    "utilization": float(attrs.get("utilization", 0.0)),
                    "latency": float(attrs.get("latency", 5.0)),
                    "packet_loss": float(attrs.get("packet_loss", 0.0)),
                }

    def _precompute_distances(self) -> None:
        """Precompute all-pairs unweighted shortest path distances using BFS."""
        try:
            # Use the underlying NetworkX graph for BFS distance computation
            for node in self.nodes:
                try:
                    lengths = nx.single_source_shortest_path_length(
                        self.topology.graph, node
                    )
                    self._shortest_distances[node] = dict(lengths)
                except Exception:
                    self._shortest_distances[node] = {}
        except Exception:
            # If distance computation fails, empty dict means no proximity bonus
            pass

    def _get_distance_to_dest(self, from_node: str) -> int:
        """Get precomputed hop distance from a node to the current destination."""
        dists = self._shortest_distances.get(from_node, {})
        return dists.get(self.destination, self.num_nodes)  # Fallback: max possible

    def _randomize_edge_attributes(self) -> None:
        """Randomize edge utilization, latency, and loss to simulate varied congestion.

        Only applied during training mode to expose the RL agent to diverse
        network states instead of always-zero utilization.
        """
        if not self.training_mode:
            return

        for src, dst in self.edges:
            orig = self._original_edge_attrs.get((src, dst), {})
            base_latency = orig.get("latency", 5.0)
            base_loss = orig.get("packet_loss", 0.0)

            # Randomize utilization: uniform [0.0, 0.85] to cover normal and congested
            rand_util = float(self.np_random.uniform(0.0, 0.85))
            # Perturb latency: base * (1 + utilization * random_factor)
            lat_factor = 1.0 + rand_util * float(self.np_random.uniform(0.5, 2.0))
            rand_latency = max(0.1, base_latency * lat_factor)
            # Perturb packet loss: small probability increase under congestion
            rand_loss = min(1.0, base_loss + rand_util * float(self.np_random.uniform(0.0, 0.03)))

            with contextlib.suppress(Exception):
                self.topology.update_edge(
                    src, dst,
                    utilization=rand_util,
                    latency=rand_latency,
                    packet_loss=rand_loss,
                )

    def _restore_edge_attributes(self) -> None:
        """Restore original edge attributes after training episode."""
        if not self.training_mode:
            return

        for (src, dst), orig in self._original_edge_attrs.items():
            with contextlib.suppress(Exception):
                self.topology.update_edge(
                    src, dst,
                    utilization=orig["utilization"],
                    latency=orig["latency"],
                    packet_loss=orig["packet_loss"],
                )

    def reset(
        self,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Reset the environment to a random source/destination pair."""
        super().reset(seed=seed)

        # Restore edge attrs from previous episode, then randomize for new episode
        self._restore_edge_attributes()
        self._randomize_edge_attributes()

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
        self._visit_counts = {self.current_node: 1}

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

        # 4. Graduated loop detection
        visit_count = self._visit_counts.get(next_node, 0)
        if visit_count >= 2:
            # Third visit to same node — terminate with heavy penalty
            reward = -30.0
            terminated = True
            info["status"] = "failed_loop_detected"
            return self._get_obs(), reward, terminated, truncated, info

        # Update path and visit counts
        self.path.append(next_node)
        self.current_node = next_node
        self.hops += 1
        self._visit_counts[next_node] = visit_count + 1

        # 5. Compute reward
        alpha = self.reward_params.get("alpha", 5.0)
        beta = self.reward_params.get("beta", 1.0)
        gamma = self.reward_params.get("gamma", 50.0)
        delta = self.reward_params.get("delta", 0.5)
        proximity_weight = self.reward_params.get("proximity", 5.0)

        # Base step reward: low latency, high bandwidth, low loss
        step_reward = (
            alpha * (1.0 / max(0.1, latency)) + beta * (bandwidth / 1000.0) - gamma * loss - delta
        )

        # Apply revisit penalty (graduated: -5.0 on first revisit)
        if visit_count == 1:
            step_reward -= 10.0
            info["revisit_penalty"] = True

        # Proximity-to-destination bonus (precomputed BFS distance)
        prev_distance = self._get_distance_to_dest(self.path[-2])  # where we came from
        curr_distance = self._get_distance_to_dest(self.current_node)

        # Bonus for getting closer, penalty for moving away
        distance_delta = prev_distance - curr_distance
        step_reward += proximity_weight * distance_delta

        reward = step_reward

        # Jain's fairness index of remaining edge capacities
        fairness_weight = self.reward_params.get("fairness", 2.0)
        if fairness_weight > 0 and self.num_edges > 0:
            remaining_caps = []
            for src, dst in self.edges:
                attrs = self.topology.get_edge(src, dst)
                util = float(attrs.get("utilization", 0.0))
                remaining_caps.append(max(0.0, 1.0 - util))
            remaining = np.array(remaining_caps, dtype=np.float64)
            sum_r = remaining.sum()
            sum_r2 = (remaining ** 2).sum()
            n = len(remaining)
            jains = (sum_r ** 2) / (n * sum_r2) if sum_r2 > 0 else 1.0
            reward += fairness_weight * jains


        # Check if reached destination
        if self.current_node == self.destination:
            # Reached destination bonus (scaled inversely by path length)
            efficiency_bonus = max(10.0, 100.0 - self.hops * 2.0)
            reward += efficiency_bonus
            terminated = True
            info["status"] = "success"
        elif self.hops >= self.max_hops:
            # Penalty for failing to reach destination within budget
            reward -= 10.0
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
