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
        # Sort nodes and edges for deterministic ordering directly from graph views
        graph = topology.graph
        nodes = sorted(graph.nodes)
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
        succ = getattr(graph, "_succ", graph)
        max_degree = max(len(succ[n]) for n in nodes) if nodes else 1
        if max_degree == 0:
            max_degree = 1

        node_attrs = getattr(graph, "_node", graph.nodes)
        node_features = []
        for node in nodes:
            attrs = node_attrs[node]

            # Capacity (normalized by 1000.0)
            cap = float(attrs.get("capacity", 1000.0)) / 1000.0

            # Status: 1.0 if up, 0.0 if down
            st_val = attrs.get("status", "up")
            status = 1.0 if st_val in ("up", "UP") or str(st_val).lower() == "up" else 0.0

            # Degree normalized (O(1) degree lookup avoiding list allocation)
            degree = float(len(succ[node])) / max_degree

            # Queue length & Packet load & Congestion score (dynamic telemetry)
            queue_len = float(attrs.get("queue_length", 0.0))
            packet_load = float(attrs.get("packet_load", 0.0))

            # Congestion score = queue_length / capacity
            capacity_raw = float(attrs.get("capacity", 1000.0))
            congestion_score = queue_len / capacity_raw if capacity_raw > 0 else 0.0

            # Topological metrics
            btw_cent = betweenness.get(node, 0.0)
            cls_cent = closeness.get(node, 0.0)

            node_features.append(
                [
                    cap,
                    status,
                    degree,
                    queue_len / 100.0,  # Scaled queue length
                    packet_load / 1000.0,  # Scaled packet load
                    congestion_score,
                    btw_cent,
                    cls_cent,
                ]
            )

        return np.array(node_features, dtype=np.float32)

    @staticmethod
    def _build_edge_features(
        graph: Any,
        edges: list[tuple[Any, Any]],
        node_to_idx: dict[Any, int],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Construct edge index and edge feature matrices."""
        if not edges:
            return np.empty((2, 0), dtype=np.int64), np.empty((0, 6), dtype=np.float32)

        src_indices = [node_to_idx[src] for src, _ in edges]
        dst_indices = [node_to_idx[dst] for _, dst in edges]
        edge_index_arr = np.array([src_indices, dst_indices], dtype=np.int64)

        adj = getattr(graph, "_adj", graph.edges)
        edge_features = []
        for src, dst in edges:
            attrs = adj[src][dst] if hasattr(graph, "_adj") else adj[src, dst]

            # Bandwidth (normalized by 1000.0)
            bw = float(attrs.get("bandwidth", 1000.0)) / 1000.0

            # Latency (normalized by 100.0)
            lat = float(attrs.get("latency", 5.0)) / 100.0

            # Utilization (0.0 to 1.0)
            util = float(attrs.get("utilization", 0.0))

            # Packet loss (0.0 to 1.0)
            loss = float(attrs.get("packet_loss", 0.0))

            # Reliability (default 1.0)
            reliability = float(attrs.get("reliability", 1.0))

            # Failure frequency
            failure_freq = float(attrs.get("failure_frequency", 0.0)) / 10.0

            edge_features.append([bw, lat, util, loss, reliability, failure_freq])

        edge_features_arr = np.array(edge_features, dtype=np.float32)
        return edge_index_arr, edge_features_arr
