"""Unit tests for GraphSAGE model architecture."""

from __future__ import annotations

import os
import tempfile

import torch

from nroute.ml.models.graphsage import GraphSAGEModel, SAGEConv


def test_sage_conv_forward() -> None:
    """Test SAGEConv forward pass."""
    in_features = 16
    out_features = 32
    num_nodes = 10
    num_edges = 20

    conv = SAGEConv(in_features, out_features)
    x = torch.randn(num_nodes, in_features)
    edge_index = torch.randint(0, num_nodes, (2, num_edges))

    out = conv(x, edge_index)

    assert out.shape == (num_nodes, out_features)


def test_sage_conv_no_edges() -> None:
    """Test SAGEConv forward pass with no edges."""
    in_features = 16
    out_features = 32
    num_nodes = 10

    conv = SAGEConv(in_features, out_features)
    x = torch.randn(num_nodes, in_features)
    edge_index = torch.empty((2, 0), dtype=torch.long)

    out = conv(x, edge_index)

    assert out.shape == (num_nodes, out_features)
    # With no edges, neigh_mean should be zero, so out should be lin_self(x) + bias
    expected = conv.lin_self(x) + conv.bias
    torch.testing.assert_close(out, expected)


def test_graphsage_model_forward() -> None:
    """Test GraphSAGEModel forward pass."""
    node_in_dim = 16
    edge_in_dim = 8
    hidden_dim = 32
    num_layers = 2
    num_nodes = 10
    num_edges = 20

    model = GraphSAGEModel(
        node_in_dim=node_in_dim,
        edge_in_dim=edge_in_dim,
        hidden_dim=hidden_dim,
        num_layers=num_layers,
    )

    node_features = torch.randn(num_nodes, node_in_dim)
    edge_index = torch.randint(0, num_nodes, (2, num_edges))
    edge_features = torch.randn(num_edges, edge_in_dim)

    congestion_logits, latency_pred = model(node_features, edge_index, edge_features)

    assert congestion_logits.shape == (num_edges,)
    assert latency_pred.shape == (num_edges,)


def test_graphsage_model_empty_edges() -> None:
    """Test GraphSAGEModel forward pass with empty edges."""
    node_in_dim = 16
    edge_in_dim = 8
    num_nodes = 10

    model = GraphSAGEModel(node_in_dim=node_in_dim, edge_in_dim=edge_in_dim)

    node_features = torch.randn(num_nodes, node_in_dim)
    edge_index = torch.empty((2, 0), dtype=torch.long)
    edge_features = torch.empty((0, edge_in_dim))

    congestion_logits, latency_pred = model(node_features, edge_index, edge_features)

    assert congestion_logits.shape == (0,)
    assert latency_pred.shape == (0,)


def test_graphsage_model_save_load() -> None:
    """Test saving and loading the GraphSAGEModel."""
    model = GraphSAGEModel(node_in_dim=16, edge_in_dim=8)

    with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        model.save(tmp_path)
        assert os.path.exists(tmp_path)

        new_model = GraphSAGEModel(node_in_dim=16, edge_in_dim=8)
        new_model.load(tmp_path)

        # Check weights match
        for p1, p2 in zip(model.parameters(), new_model.parameters(), strict=True):
            assert torch.equal(p1, p2)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_graphsage_model_training_mode() -> None:
    """Test GraphSAGEModel in training mode (dropout)."""
    # Use a high dropout rate to make it likely that outputs differ
    model = GraphSAGEModel(node_in_dim=16, edge_in_dim=8, dropout=0.9)
    node_features = torch.randn(10, 16)
    edge_index = torch.tensor([[0, 1], [1, 0]], dtype=torch.long)
    edge_features = torch.randn(2, 8)

    model.train()
    out1_c, out1_l = model(node_features, edge_index, edge_features)
    out2_c, out2_l = model(node_features, edge_index, edge_features)

    # With high dropout, outputs should be different
    assert not torch.equal(out1_c, out2_c)
    assert not torch.equal(out1_l, out2_l)

    model.eval()
    out3_c, out3_l = model(node_features, edge_index, edge_features)
    out4_c, out4_l = model(node_features, edge_index, edge_features)

    # In eval mode, outputs should be identical
    torch.testing.assert_close(out3_c, out4_c)
    torch.testing.assert_close(out3_l, out4_l)


def test_sage_conv_specific_graph() -> None:
    """Test SAGEConv with a simple specific graph to verify mean aggregation."""
    in_features = 2
    out_features = 2

    conv = SAGEConv(in_features, out_features)
    # Identity weights to make it easy to track
    conv.lin_self.weight.data = torch.eye(out_features)
    conv.lin_neigh.weight.data = torch.eye(out_features)
    conv.bias.data.zero_()

    x = torch.tensor([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]], dtype=torch.float32)

    # 0 -> 1, 2 -> 1 (node 1 has two incoming edges from 0 and 2)
    edge_index = torch.tensor([[0, 2], [1, 1]], dtype=torch.long)

    out = conv(x, edge_index)

    # For node 1:
    # self = [0, 1]
    # neighbors are 0 and 2. Features: [1, 0] and [1, 1]
    # neigh_mean = ([1, 0] + [1, 1]) / 2 = [1, 0.5]
    # out[1] = self + neigh_mean = [0, 1] + [1, 0.5] = [1, 1.5]
    expected_node_1 = torch.tensor([1.0, 1.5])
    torch.testing.assert_close(out[1], expected_node_1)

    # For node 0:
    # self = [1, 0]
    # neighbors = None
    # out[0] = [1, 0] + [0, 0] = [1, 0]
    expected_node_0 = torch.tensor([1.0, 0.0])
    torch.testing.assert_close(out[0], expected_node_0)

    # For node 2:
    # self = [1, 1]
    # neighbors = None
    # out[2] = [1, 1] + [0, 0] = [1, 1]
    expected_node_2 = torch.tensor([1.0, 1.0])
    torch.testing.assert_close(out[2], expected_node_2)
