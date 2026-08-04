"""Unit tests for GNN training batch collation."""

from __future__ import annotations

import pytest
import torch

from nroute.ml.training.trainer import collate_dataset_batch


def test_collate_single_sample() -> None:
    """Test collation with a single sample in the batch."""
    node_features = torch.randn(3, 8)
    edge_index = torch.tensor([[0, 1], [1, 2]], dtype=torch.long)
    edge_features = torch.randn(2, 6)
    congested_labels = torch.tensor([0.0, 1.0])
    latency_targets = torch.tensor([0.05, 0.1])

    sample = {
        "node_features": node_features,
        "edge_index": edge_index,
        "edge_features": edge_features,
        "congested_labels": congested_labels,
        "latency_targets": latency_targets,
    }

    batch = [sample]
    collated = collate_dataset_batch(batch)

    assert torch.equal(collated["node_features"], node_features)
    assert torch.equal(collated["edge_index"], edge_index)
    assert torch.equal(collated["edge_features"], edge_features)
    assert torch.equal(collated["congested_labels"], congested_labels)
    assert torch.equal(collated["latency_targets"], latency_targets)
    assert torch.equal(collated["batch"], torch.zeros(3, dtype=torch.long))


def test_collate_multiple_samples() -> None:
    """Test collation with multiple samples of different sizes."""
    # Sample 1: 2 nodes, 1 edge
    s1 = {
        "node_features": torch.randn(2, 8),
        "edge_index": torch.tensor([[0], [1]], dtype=torch.long),
        "edge_features": torch.randn(1, 6),
        "congested_labels": torch.tensor([0.0]),
        "latency_targets": torch.tensor([0.1]),
    }

    # Sample 2: 3 nodes, 2 edges
    s2 = {
        "node_features": torch.randn(3, 8),
        "edge_index": torch.tensor([[0, 1], [1, 2]], dtype=torch.long),
        "edge_features": torch.randn(2, 6),
        "congested_labels": torch.tensor([1.0, 0.0]),
        "latency_targets": torch.tensor([0.2, 0.3]),
    }

    batch = [s1, s2]
    collated = collate_dataset_batch(batch)

    # Check shapes
    assert collated["node_features"].shape == (5, 8)
    assert collated["edge_index"].shape == (2, 3)
    assert collated["edge_features"].shape == (3, 6)
    assert collated["congested_labels"].shape == (3,)
    assert collated["latency_targets"].shape == (3,)
    assert collated["batch"].shape == (5,)

    # Check node feature concatenation
    assert torch.equal(collated["node_features"][:2], s1["node_features"])
    assert torch.equal(collated["node_features"][2:], s2["node_features"])

    # Check edge index offsets
    expected_edge_index = torch.tensor([[0, 2, 3], [1, 3, 4]], dtype=torch.long)
    assert torch.equal(collated["edge_index"], expected_edge_index)

    # Check batch indices
    expected_batch = torch.tensor([0, 0, 1, 1, 1], dtype=torch.long)
    assert torch.equal(collated["batch"], expected_batch)

    # Check other features
    assert torch.equal(collated["edge_features"][0:1], s1["edge_features"])
    assert torch.equal(collated["edge_features"][1:], s2["edge_features"])
    assert torch.equal(collated["congested_labels"], torch.tensor([0.0, 1.0, 0.0]))
    assert torch.equal(collated["latency_targets"], torch.tensor([0.1, 0.2, 0.3]))


def test_collate_empty_batch() -> None:
    """Test behavior with an empty batch (expected to fail with current implementation)."""
    with pytest.raises(ValueError, match="expected a non-empty list of Tensors"):
        collate_dataset_batch([])
