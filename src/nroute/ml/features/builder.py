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
        # Query topology.graph directly to avoid list allocation overhead from topology.nodes/edges
        graph = topology.graph
        nodes = sorted(graph)
        edges = sorted(graph.edges)
        node_to_idx = {node: idx for idx, node in enumerate(nodes)}

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
        if not nodes:
            return np.empty((0, 8), dtype=np.float32)

        succ = getattr(graph, "_succ", graph)
        max_degree = max(len(succ[n]) for n in nodes) if nodes else 1
        if max_degree == 0:
            max_degree = 1

        node_attrs = getattr(graph, "_node", graph.nodes)
        node_features = [
            (
                (cap_raw := float(attrs.get("capacity", 1000.0))) / 1000.0,
                1.0
                if (st := attrs.get("status", "up")) in ("up", "UP") or str(st).lower() == "up"
                else 0.0,
                float(len(succ[node])) / max_degree,
                (q_len := float(attrs.get("queue_length", 0.0))) / 100.0,
                float(attrs.get("packet_load", 0.0)) / 1000.0,
                q_len / cap_raw if cap_raw > 0 else 0.0,
                betweenness.get(node, 0.0),
                closeness.get(node, 0.0),
            )
            for node, attrs in ((n, node_attrs[n]) for n in nodes)
        ]

        return np.array(node_features, dtype=np.float32)

    @staticmethod
    def _build_edge_features(
        graph: Any,
        edges: list[tuple[Any, Any]],
        node_to_idx: dict[Any, int],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Construct edge index and edge feature matrices."""
        num_edges = len(edges)
        if not num_edges:
            return np.empty((2, 0), dtype=np.int64), np.empty((0, 6), dtype=np.float32)

        src_indices = [node_to_idx[src] for src, _ in edges]
        dst_indices = [node_to_idx[dst] for _, dst in edges]
        edge_index_arr = np.array([src_indices, dst_indices], dtype=np.int64)

        has_adj = hasattr(graph, "_adj")
        adj = graph._adj if has_adj else graph.edges

        edge_features = [
            (
                float(attrs.get("bandwidth", 1000.0)) / 1000.0,
                float(attrs.get("latency", 5.0)) / 100.0,
                float(attrs.get("utilization", 0.0)),
                float(attrs.get("packet_loss", 0.0)),
                float(attrs.get("reliability", 1.0)),
                float(attrs.get("failure_frequency", 0.0)) / 10.0,
            )
            for attrs in (adj[src][dst] if has_adj else adj[src, dst] for src, dst in edges)
        ]

        edge_features_arr = np.array(edge_features, dtype=np.float32)
        return edge_index_arr, edge_features_arr
