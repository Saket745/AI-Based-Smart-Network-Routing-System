"""Feature engineering builders for GNN node and edge attributes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx
import numpy as np

from nroute.ml.graph.bundle import GraphTensorBundle

if TYPE_CHECKING:
    from nroute.core.topology import Topology


class FeatureBuilder:
    """Builds node and edge features from network topologies."""

    def __init__(self) -> None:
        pass

    def build_features(self, topology: Topology) -> GraphTensorBundle:
        """
        Build engineered topological and dynamic features from a Topology object.

        Args:
            topology: The network topology.

        Returns:
            GraphTensorBundle containing normalized feature tensors.
        """
        # Sort nodes and edges for deterministic ordering
        nodes = sorted(topology.nodes)
        edges = sorted(topology.edges)
        node_to_idx = {node: idx for idx, node in enumerate(nodes)}

        graph = topology.graph
        betweenness, closeness = self._compute_centralities(graph)
        node_features_arr = self._build_node_features(
            graph, nodes, topology, betweenness, closeness
        )
        edge_index_arr, edge_features_arr = self._build_edge_features(graph, edges, node_to_idx)

        return GraphTensorBundle(
            node_features=node_features_arr,
            edge_index=edge_index_arr,
            edge_features=edge_features_arr,
            node_to_idx=node_to_idx,
            idx_to_node=nodes,
        )

    @staticmethod
    def _compute_centralities(graph: Any) -> tuple[dict[Any, float], dict[Any, float]]:
        """Compute topological centrality metrics using NetworkX on topology.graph."""
        betweenness: dict[Any, float] = nx.betweenness_centrality(graph, weight="latency")
        closeness: dict[Any, float] = nx.closeness_centrality(graph, distance="latency")
        return betweenness, closeness

    @staticmethod
    def _build_node_features(
        graph: Any,
        nodes: list[Any],
        topology: Topology,
        betweenness: dict[Any, float],
        closeness: dict[Any, float],
    ) -> np.ndarray:
        """Construct normalized node feature array."""
        succ = getattr(graph, "_succ", graph)
        max_degree = max(len(succ[n]) for n in nodes) if nodes else 1
        if max_degree == 0:
            max_degree = 1

        node_attrs = getattr(graph, "_node", graph.nodes)
        n_nodes = len(nodes)
        node_features_arr = np.empty((n_nodes, 8), dtype=np.float32)

        for i, node in enumerate(nodes):
            attrs = node_attrs[node]

            # Capacity (normalized by 1000.0)
            capacity_raw = float(attrs.get("capacity", 1000.0))
            node_features_arr[i, 0] = capacity_raw / 1000.0

            # Status: 1.0 if up, 0.0 if down
            st_val = attrs.get("status", "up")
            node_features_arr[i, 1] = (
                1.0 if st_val in ("up", "UP") or str(st_val).lower() == "up" else 0.0
            )

            # Degree normalized (O(1) degree lookup avoiding list allocation)
            node_features_arr[i, 2] = float(len(succ[node])) / max_degree

            # Queue length & Packet load & Congestion score (dynamic telemetry)
            queue_len = float(attrs.get("queue_length", 0.0))
            packet_load = float(attrs.get("packet_load", 0.0))

            node_features_arr[i, 3] = queue_len / 100.0  # Scaled queue length
            node_features_arr[i, 4] = packet_load / 1000.0  # Scaled packet load

            # Congestion score = queue_length / capacity
            node_features_arr[i, 5] = queue_len / capacity_raw if capacity_raw > 0 else 0.0

            # Topological metrics
            node_features_arr[i, 6] = betweenness.get(node, 0.0)
            node_features_arr[i, 7] = closeness.get(node, 0.0)

        return node_features_arr

    @staticmethod
    def _build_edge_features(
        graph: Any,
        edges: list[tuple[Any, Any]],
        node_to_idx: dict[Any, int],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Construct edge index and edge feature matrices."""
        n_edges = len(edges)
        if not n_edges:
            return np.empty((2, 0), dtype=np.int64), np.empty((0, 6), dtype=np.float32)

        edge_index_arr = np.empty((2, n_edges), dtype=np.int64)
        edge_features_arr = np.empty((n_edges, 6), dtype=np.float32)

        adj_dict: Any = getattr(graph, "_adj", None)
        has_adj = adj_dict is not None
        if not has_adj:
            adj_dict = graph.edges

        src_row = edge_index_arr[0]
        dst_row = edge_index_arr[1]

        # BOLT OPTIMIZATION: Direct single-pass population into pre-allocated NumPy arrays
        # bypassing inner list creations and intermediate list-of-lists conversion overhead.
        if has_adj:
            for i, (src, dst) in enumerate(edges):
                src_row[i] = node_to_idx[src]
                dst_row[i] = node_to_idx[dst]

                attrs = adj_dict[src][dst]
                edge_features_arr[i, 0] = float(attrs.get("bandwidth", 1000.0)) / 1000.0
                edge_features_arr[i, 1] = float(attrs.get("latency", 5.0)) / 100.0
                edge_features_arr[i, 2] = float(attrs.get("utilization", 0.0))
                edge_features_arr[i, 3] = float(attrs.get("packet_loss", 0.0))
                edge_features_arr[i, 4] = float(attrs.get("reliability", 1.0))
                edge_features_arr[i, 5] = float(attrs.get("failure_frequency", 0.0)) / 10.0
        else:
            for i, (src, dst) in enumerate(edges):
                src_row[i] = node_to_idx[src]
                dst_row[i] = node_to_idx[dst]

                attrs = adj_dict[src, dst]
                edge_features_arr[i, 0] = float(attrs.get("bandwidth", 1000.0)) / 1000.0
                edge_features_arr[i, 1] = float(attrs.get("latency", 5.0)) / 100.0
                edge_features_arr[i, 2] = float(attrs.get("utilization", 0.0))
                edge_features_arr[i, 3] = float(attrs.get("packet_loss", 0.0))
                edge_features_arr[i, 4] = float(attrs.get("reliability", 1.0))
                edge_features_arr[i, 5] = float(attrs.get("failure_frequency", 0.0)) / 10.0

        return edge_index_arr, edge_features_arr
