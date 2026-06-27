"""Unit tests for GCN and GraphSAGE model architectures."""

from __future__ import annotations

import torch

from nroute.ml.models.gcn import GCNModel
from nroute.ml.models.graphsage import GraphSAGEModel


def test_gcn_model_forward() -> None:
    """Test GCN forward pass with sample features and edges."""
    node_in_dim = 8
    edge_in_dim = 6
    hidden_dim = 16

    model = GCNModel(
        node_in_dim=node_in_dim,
        edge_in_dim=edge_in_dim,
        hidden_dim=hidden_dim,
        num_layers=2,
    )

    # 4 nodes, 3 edges
    node_feats = torch.randn(4, node_in_dim)
    edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]], dtype=torch.long)
    edge_feats = torch.randn(3, edge_in_dim)

    logits, lat_pred = model(node_feats, edge_index, edge_feats)

    # 3 edges, output shapes should match
    assert logits.shape == (3,)
    assert lat_pred.shape == (3,)

    # Test with zero edges (disconnected)
    empty_edge_index = torch.empty((2, 0), dtype=torch.long)
    empty_edge_feats = torch.empty((0, edge_in_dim))
    logits_empty, lat_empty = model(node_feats, empty_edge_index, empty_edge_feats)
    assert logits_empty.shape == (0,)
    assert lat_empty.shape == (0,)


def test_graphsage_model_forward() -> None:
    """Test GraphSAGE forward pass with sample features and edges."""
    node_in_dim = 8
    edge_in_dim = 6
    hidden_dim = 16

    model = GraphSAGEModel(
        node_in_dim=node_in_dim,
        edge_in_dim=edge_in_dim,
        hidden_dim=hidden_dim,
        num_layers=2,
    )

    # 4 nodes, 3 edges
    node_feats = torch.randn(4, node_in_dim)
    edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]], dtype=torch.long)
    edge_feats = torch.randn(3, edge_in_dim)

    logits, lat_pred = model(node_feats, edge_index, edge_feats)

    # 3 edges
    assert logits.shape == (3,)
    assert lat_pred.shape == (3,)

    # Test with empty edges
    empty_edge_index = torch.empty((2, 0), dtype=torch.long)
    empty_edge_feats = torch.empty((0, edge_in_dim))
    logits_empty, lat_empty = model(node_feats, empty_edge_index, empty_edge_feats)
    assert logits_empty.shape == (0,)
    assert lat_empty.shape == (0,)
