"""Feature engineering builders for GNN node and edge attributes."""

from __future__ import annotations

from typing import TYPE_CHECKING

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

        # 1. Compute Topological Centrality metrics using NetworkX on topology.graph
        # Convert to undirected for centralities if needed, but since topology is directed, we use DiGraph.
        graph = topology.graph
        betweenness = nx.betweenness_centrality(graph, weight="latency")
        closeness = nx.closeness_centrality(graph, distance="latency")

        max_degree = max(len(list(topology.neighbors(n))) for n in nodes) if nodes else 1
        if max_degree == 0:
            max_degree = 1

        # 2. Build Node Features
        node_features = []
        for node in nodes:
            attrs = topology.get_node(node)

            # Capacity (normalized by 1000.0)
            cap = float(attrs.get("capacity", 1000.0)) / 1000.0

            # Status: 1.0 if up, 0.0 if down
            status = 1.0 if attrs.get("status", "up").lower() == "up" else 0.0

            # Degree normalized
            degree = float(len(list(topology.neighbors(node)))) / max_degree

            # Queue length & Packet load & Congestion score (dynamic telemetry)
            queue_len = float(attrs.get("queue_length", 0.0))
            packet_load = float(attrs.get("packet_load", 0.0))

            # Congestion score = queue_length / capacity
            capacity_raw = float(attrs.get("capacity", 1000.0))
            congestion_score = queue_len / capacity_raw if capacity_raw > 0 else 0.0

            # Topological metrics
            btw_cent = float(betweenness.get(node, 0.0))
            cls_cent = float(closeness.get(node, 0.0))

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

        node_features_arr = np.array(node_features, dtype=np.float32)

        # 3. Build Edge Features
        edge_index = []
        edge_features = []
        for src, dst in edges:
            edge_index.append([node_to_idx[src], node_to_idx[dst]])
            attrs = topology.get_edge(src, dst)

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

        if len(edges) > 0:
            edge_index_arr = np.array(edge_index, dtype=np.int64).T
            edge_features_arr = np.array(edge_features, dtype=np.float32)
        else:
            edge_index_arr = np.empty((2, 0), dtype=np.int64)
            edge_features_arr = np.empty((0, 6), dtype=np.float32)

        return GraphTensorBundle(
            node_features=node_features_arr,
            edge_index=edge_index_arr,
            edge_features=edge_features_arr,
            node_to_idx=node_to_idx,
            idx_to_node=nodes,
        )
