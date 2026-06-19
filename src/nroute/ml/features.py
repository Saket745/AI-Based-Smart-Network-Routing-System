"""Feature extractors for converting network topologies into ML/GNN formats."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any

import numpy as np

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from nroute.core.topology import Topology


class GraphTensorBundle:
    """
    Structured bundle of extracted graph features for GNN training/inference.
    Supports both attribute access (bundle.node_features) and dictionary access (bundle['node_features'])
    for backward compatibility.
    """

    def __init__(
        self,
        node_features: np.ndarray | Any,
        edge_index: np.ndarray | Any,
        edge_features: np.ndarray | Any,
        node_to_idx: dict[str, int],
        idx_to_node: list[str],
    ) -> None:
        self.node_features = node_features
        self.edge_index = edge_index
        self.edge_features = edge_features
        self.node_to_idx = node_to_idx
        self.idx_to_node = idx_to_node

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError as e:
            raise KeyError(key) from e

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def keys(self) -> list[str]:
        return ["node_features", "edge_index", "edge_features", "node_to_idx", "idx_to_node"]


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

        # Build node features: [capacity, status, degree]
        node_features = []
        for node in nodes:
            attrs = topology.get_node(node)
            cap = float(attrs.get("capacity", 1000.0)) / 1000.0
            status = 1.0 if attrs.get("status", "up").lower() == "up" else 0.0
            degree = float(len(list(topology.neighbors(node))))
            node_features.append([cap, status, degree])
        node_features_arr = np.array(node_features, dtype=np.float32)

        # Build edge index and edge features: [bandwidth, latency, utilization, packet_loss, status]
        edge_index = []
        edge_features = []
        for src, dst in edges:
            edge_index.append([node_to_idx[src], node_to_idx[dst]])
            attrs = topology.get_edge(src, dst)
            bw = float(attrs.get("bandwidth", 1000.0)) / 1000.0
            lat = float(attrs.get("latency", 5.0)) / 100.0
            util = float(attrs.get("utilization", 0.0))
            loss = float(attrs.get("packet_loss", 0.0))
            status = 1.0 if attrs.get("status", "up").lower() == "up" else 0.0
            edge_features.append([bw, lat, util, loss, status])

        if len(edges) > 0:
            edge_index_arr = np.array(edge_index, dtype=np.int64).T  # Shape: (2, E)
            edge_features_arr = np.array(edge_features, dtype=np.float32)
        else:
            edge_index_arr = np.empty((2, 0), dtype=np.int64)
            edge_features_arr = np.empty((0, 5), dtype=np.float32)

        node_features_val: Any = node_features_arr
        edge_index_val: Any = edge_index_arr
        edge_features_val: Any = edge_features_arr

        # Convert to PyTorch tensors if requested
        if self.use_pytorch and torch is not None:
            node_features_val = torch.from_numpy(node_features_val)
            edge_index_val = torch.from_numpy(edge_index_val)
            edge_features_val = torch.from_numpy(edge_features_val)

        return GraphTensorBundle(
            node_features=node_features_val,
            edge_index=edge_index_val,
            edge_features=edge_features_val,
            node_to_idx=node_to_idx,
            idx_to_node=nodes,
        )
