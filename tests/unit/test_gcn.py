"""Unit tests for Graph Convolutional Network (GCN) model."""

from __future__ import annotations

import tempfile
from pathlib import Path

import torch

from nroute.ml.models.gcn import GCNConv, GCNModel


def test_gcn_conv_forward() -> None:
    """Test GCNConv layer forward pass."""
    in_channels = 16
    out_channels = 32
    num_nodes = 10
    num_edges = 20

    conv = GCNConv(in_channels, out_channels)
    x = torch.randn(num_nodes, in_channels)
    edge_index = torch.randint(0, num_nodes, (2, num_edges))

    out = conv(x, edge_index)

    assert out.shape == (num_nodes, out_channels)
    assert not torch.isnan(out).any()


def test_gcn_conv_normalization() -> None:
    """Test GCNConv layer normalization handling of isolated nodes."""
    in_channels = 4
    out_channels = 4
    num_nodes = 3

    # 3 nodes, but only one edge between node 0 and 1. Node 2 is isolated.
    edge_index = torch.tensor([[0], [1]], dtype=torch.long)
    x = torch.ones(num_nodes, in_channels)

    conv = GCNConv(in_channels, out_channels)
    # Set weights to identity and bias to zero to easily track values
    with torch.no_grad():
        conv.linear.weight.fill_(0)
        conv.linear.weight.fill_diagonal_(1)
        conv.bias.fill_(0)

    out = conv(x, edge_index)

    assert out.shape == (num_nodes, out_channels)
    assert not torch.isnan(out).any()
    # Isolated node 2 should still have features (from self-loop)
    assert torch.all(out[2] > 0)


def test_gcn_model_forward() -> None:
    """Test GCNModel forward pass."""
    node_in_dim = 8
    edge_in_dim = 4
    hidden_dim = 16
    num_nodes = 5
    num_edges = 8

    model = GCNModel(node_in_dim, edge_in_dim, hidden_dim)
    node_features = torch.randn(num_nodes, node_in_dim)
    edge_index = torch.randint(0, num_nodes, (2, num_edges))
    edge_features = torch.randn(num_edges, edge_in_dim)

    congestion_logits, latency_pred = model(node_features, edge_index, edge_features)

    assert congestion_logits.shape == (num_edges,)
    assert latency_pred.shape == (num_edges,)


def test_gcn_model_zero_edges() -> None:
    """Test GCNModel with zero edges."""
    node_in_dim = 8
    edge_in_dim = 4
    num_nodes = 5

    model = GCNModel(node_in_dim, edge_in_dim)
    node_features = torch.randn(num_nodes, node_in_dim)
    edge_index = torch.empty((2, 0), dtype=torch.long)
    edge_features = torch.empty((0, edge_in_dim))

    congestion_logits, latency_pred = model(node_features, edge_index, edge_features)

    assert congestion_logits.shape == (0,)
    assert latency_pred.shape == (0,)


def test_gcn_model_backward() -> None:
    """Test GCNModel backward pass for gradient computation."""
    node_in_dim = 8
    edge_in_dim = 4
    num_nodes = 5
    num_edges = 8

    model = GCNModel(node_in_dim, edge_in_dim)
    node_features = torch.randn(num_nodes, node_in_dim)
    edge_index = torch.randint(0, num_nodes, (2, num_edges))
    edge_features = torch.randn(num_edges, edge_in_dim)

    congestion_logits, latency_pred = model(node_features, edge_index, edge_features)

    loss = congestion_logits.sum() + latency_pred.sum()
    loss.backward()

    # Check if gradients are computed for parameters
    for name, param in model.named_parameters():
        assert param.grad is not None, f"Gradient not computed for {name}"
        assert not torch.isnan(param.grad).any()


def test_gcn_model_save_load() -> None:
    """Test saving and loading the model."""
    model = GCNModel(8, 4)

    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = Path(tmpdir) / "model.pt"
        model.save(str(model_path))
        assert model_path.exists()

        new_model = GCNModel(8, 4)
        new_model.load(str(model_path))

        # Verify parameters match
        for p1, p2 in zip(model.parameters(), new_model.parameters(), strict=True):
            assert torch.equal(p1, p2)


def test_gcn_model_load_unsafe() -> None:
    """Test loading the model with allow_unsafe=True."""
    model = GCNModel(8, 4)

    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = Path(tmpdir) / "model_unsafe.pt"
        model.save(str(model_path))

        new_model = GCNModel(8, 4)
        # Should work with allow_unsafe=True
        new_model.load(str(model_path), allow_unsafe=True)

        for p1, p2 in zip(model.parameters(), new_model.parameters(), strict=True):
            assert torch.equal(p1, p2)
