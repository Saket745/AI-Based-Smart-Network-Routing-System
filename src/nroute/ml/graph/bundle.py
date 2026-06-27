"""Structured GNN GraphTensorBundle representation and exporters."""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]


class GraphTensorBundle:
    """
    Structured bundle of extracted graph features for GNN training/inference.
    Supports both attribute access (bundle.node_features) and dictionary access (bundle['node_features']).
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
        return [
            "node_features",
            "edge_index",
            "edge_features",
            "node_to_idx",
            "idx_to_node",
        ]

    def to_tensors(self) -> GraphTensorBundle:
        """Convert numpy arrays inside the bundle to PyTorch tensors."""
        if torch is None:
            return self

        node_feats = self.node_features
        if isinstance(node_feats, np.ndarray):
            node_feats = torch.from_numpy(node_feats)

        e_idx = self.edge_index
        if isinstance(e_idx, np.ndarray):
            e_idx = torch.from_numpy(e_idx)

        e_feats = self.edge_features
        if isinstance(e_feats, np.ndarray):
            e_feats = torch.from_numpy(e_feats)

        return GraphTensorBundle(
            node_features=node_feats,
            edge_index=e_idx,
            edge_features=e_feats,
            node_to_idx=self.node_to_idx,
            idx_to_node=self.idx_to_node,
        )


def collate_graph_batch(batches: list[GraphTensorBundle]) -> dict[str, Any]:
    """
    Collate a list of GraphTensorBundle objects into a single batched representation
    using disjoint union representation (diagonal adjacency/edge_index concatenation).
    """
    if torch is None:
        raise ImportError("PyTorch is required for GNN batch collation.")

    node_features_list: list[torch.Tensor] = []
    edge_index_list: list[torch.Tensor] = []
    edge_features_list: list[torch.Tensor] = []
    batch_idx_list: list[torch.Tensor] = []

    cumulative_nodes = 0

    for idx, bundle in enumerate(batches):
        t_bundle = bundle.to_tensors()
        n_feats = t_bundle.node_features
        e_idx = t_bundle.edge_index
        e_feats = t_bundle.edge_features

        # Assert types for mypy static analysis
        assert isinstance(n_feats, torch.Tensor)
        assert isinstance(e_idx, torch.Tensor)
        assert isinstance(e_feats, torch.Tensor)

        num_nodes = n_feats.shape[0]

        node_features_list.append(n_feats)
        edge_features_list.append(e_feats)

        # Offset the edge_index indices by cumulative nodes in the batch
        offset_edge_index = e_idx + cumulative_nodes
        edge_index_list.append(offset_edge_index)

        # Record which graph in the batch each node belongs to
        batch_idx_list.append(torch.full((num_nodes,), idx, dtype=torch.long))

        cumulative_nodes += num_nodes

    return {
        "node_features": torch.cat(node_features_list, dim=0),
        "edge_index": torch.cat(edge_index_list, dim=1),
        "edge_features": torch.cat(edge_features_list, dim=0),
        "batch": torch.cat(batch_idx_list, dim=0),
    }
