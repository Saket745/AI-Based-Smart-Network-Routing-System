"""Feature extractors for converting network topologies into ML/GNN formats."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from nroute.core.topology import Topology
from nroute.ml.graph.bundle import GraphTensorBundle


class BaseFeatureExtractor(abc.ABC):
    """Abstract base class for all feature extraction pipelines."""

    @abc.abstractmethod
    def extract_features(self, topology: Topology) -> GraphTensorBundle:
        """
        Extract features from the topology.

        Args:
            topology: The network topology.

        Returns:
            A dictionary containing feature matrices/tensors and metadata.
        """
        pass


class DefaultGraphFeatureExtractor(BaseFeatureExtractor):
    """
    Default feature extractor that exports the topology graph as standard
    matrices suitable for Graph Neural Networks (GNNs) and other ML models.
    """

    def __init__(self, use_pytorch: bool = False) -> None:
        """
        Initialize the DefaultGraphFeatureExtractor.

        Args:
            use_pytorch: If True and PyTorch is installed, returns PyTorch tensors
                instead of NumPy arrays.
        """
        self.use_pytorch = use_pytorch

    def extract_features(self, topology: Topology) -> GraphTensorBundle:
        # Sort nodes and edges deterministic ordering
        nodes = sorted(topology.nodes)
        edges = sorted(topology.edges)
        node_to_idx = {node: idx for idx, node in enumerate(nodes)}
        graph = topology.graph

        # Fast direct dict access on NetworkX graph internals to avoid per-node/edge list allocations and view overhead
        node_attrs = graph._node
        succ = graph._succ

        # Build node features: [capacity, status, degree]
        n_nodes = len(nodes)
        node_features_arr = np.empty((n_nodes, 3), dtype=np.float32)
        for i, node in enumerate(nodes):
            attrs = node_attrs[node]
            cap = float(attrs.get("capacity", 1000.0)) / 1000.0
            st_val = attrs.get("status", "up")
            status = 1.0 if st_val in ("up", "UP") or str(st_val).lower() == "up" else 0.0
            degree = float(len(succ[node]))  # O(1) degree lookup avoiding list allocation
            node_features_arr[i, 0] = cap
            node_features_arr[i, 1] = status
            node_features_arr[i, 2] = degree

        # Build edge index and edge features: [bandwidth, latency, utilization, packet_loss, status]
        n_edges = len(edges)
        if n_edges > 0:
            edge_index_arr = np.empty((2, n_edges), dtype=np.int64)
            edge_features_arr = np.empty((n_edges, 5), dtype=np.float32)

            adj = graph._adj
            for i, (src, dst) in enumerate(edges):
                edge_index_arr[0, i] = node_to_idx[src]
                edge_index_arr[1, i] = node_to_idx[dst]
                attrs = adj[src][dst]
                bw = float(attrs.get("bandwidth", 1000.0)) / 1000.0
                lat = float(attrs.get("latency", 5.0)) / 100.0
                util = float(attrs.get("utilization", 0.0))
                loss = float(attrs.get("packet_loss", 0.0))
                st_val = attrs.get("status", "up")
                status = 1.0 if st_val in ("up", "UP") or str(st_val).lower() == "up" else 0.0
                edge_features_arr[i, 0] = bw
                edge_features_arr[i, 1] = lat
                edge_features_arr[i, 2] = util
                edge_features_arr[i, 3] = loss
                edge_features_arr[i, 4] = status
        else:
            edge_index_arr = np.empty((2, 0), dtype=np.int64)
            edge_features_arr = np.empty((0, 5), dtype=np.float32)

        node_features_val: Any = node_features_arr
        edge_index_val: Any = edge_index_arr
        edge_features_val: Any = edge_features_arr

        # Convert to PyTorch tensors if requested
        if self.use_pytorch:
            try:
                import torch

                node_features_val = torch.from_numpy(node_features_val)
                edge_index_val = torch.from_numpy(edge_index_val)
                edge_features_val = torch.from_numpy(edge_features_val)
            except ImportError:
                pass

        return GraphTensorBundle(
            node_features=node_features_val,
            edge_index=edge_index_val,
            edge_features=edge_features_val,
            node_to_idx=node_to_idx,
            idx_to_node=nodes,
        )
