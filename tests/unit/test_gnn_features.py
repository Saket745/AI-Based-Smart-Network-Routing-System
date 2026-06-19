"""Unit tests for feature builder and GraphTensorBundle."""

from __future__ import annotations

import numpy as np
import torch

from nroute.core.topology import Topology
from nroute.ml.features.builder import FeatureBuilder
from nroute.ml.graph.bundle import GraphTensorBundle, collate_graph_batch


def test_graph_tensor_bundle_attributes() -> None:
    """Test GraphTensorBundle conversion and attributes."""
    node_features = np.ones((3, 4), dtype=np.float32)
    edge_index = np.array([[0, 1], [1, 2]], dtype=np.int64)
    edge_features = np.ones((2, 5), dtype=np.float32)

    bundle = GraphTensorBundle(
        node_features=node_features,
        edge_index=edge_index,
        edge_features=edge_features,
        node_to_idx={"A": 0, "B": 1, "C": 2},
        idx_to_node=["A", "B", "C"],
    )

    # Dict compatibility
    assert np.array_equal(bundle["node_features"], node_features)
    assert np.array_equal(bundle.get("edge_features"), edge_features)
    assert bundle.keys() == [
        "node_features",
        "edge_index",
        "edge_features",
        "node_to_idx",
        "idx_to_node",
    ]

    # Convert to tensors
    t_bundle = bundle.to_tensors()
    assert isinstance(t_bundle.node_features, torch.Tensor)
    assert isinstance(t_bundle.edge_index, torch.Tensor)
    assert isinstance(t_bundle.edge_features, torch.Tensor)
    assert t_bundle.node_features.shape == (3, 4)


def test_feature_builder_computation() -> None:
    """Test FeatureBuilder extracts all expected features."""
    topo = Topology()
    topo.add_node("A", capacity=1000.0)
    topo.add_node("B", capacity=2000.0)
    topo.add_node("C", capacity=1000.0)
    topo.add_edge("A", "B", bandwidth=100.0, latency=5.0)
    topo.add_edge("B", "C", bandwidth=100.0, latency=10.0)

    builder = FeatureBuilder()
    bundle = builder.build_features(topo)

    # Validate shapes
    assert bundle.node_features.shape == (3, 8)  # 8 features
    assert bundle.edge_index.shape == (2, 2)
    assert bundle.edge_features.shape == (2, 6)  # 6 features

    # Check capacity features
    assert bundle.node_features[0, 0] == 1.0  # 1000 / 1000
    assert bundle.node_features[1, 0] == 2.0  # 2000 / 1000

    # Check edge bandwidth and latency
    assert bundle.edge_features[0, 0] == 0.1  # 100 / 1000
    assert bundle.edge_features[0, 1] == 0.05  # 5 / 100


def test_collate_graph_batch() -> None:
    """Test collating multiple graphs into a batch."""
    b1 = GraphTensorBundle(
        node_features=np.ones((2, 3), dtype=np.float32),
        edge_index=np.array([[0], [1]], dtype=np.int64),
        edge_features=np.ones((1, 4), dtype=np.float32),
        node_to_idx={"A": 0, "B": 1},
        idx_to_node=["A", "B"],
    )
    b2 = GraphTensorBundle(
        node_features=np.ones((3, 3), dtype=np.float32),
        edge_index=np.array([[0, 1], [1, 2]], dtype=np.int64),
        edge_features=np.ones((2, 4), dtype=np.float32),
        node_to_idx={"C": 0, "D": 1, "E": 2},
        idx_to_node=["C", "D", "E"],
    )

    batch = collate_graph_batch([b1, b2])

    assert batch["node_features"].shape == (5, 3)
    assert batch["edge_features"].shape == (3, 4)
    # edge_index of b2 must be shifted by 2 (nodes of b1)
    # b2 edge_index: [[0, 1], [1, 2]] -> [[2, 3], [3, 4]]
    # b1 edge_index: [[0], [1]]
    expected_edge_index = torch.tensor([[0, 2, 3], [1, 3, 4]], dtype=torch.long)
    assert torch.equal(batch["edge_index"], expected_edge_index)
    # Batch indices: [0, 0, 1, 1, 1]
    assert torch.equal(batch["batch"], torch.tensor([0, 0, 1, 1, 1], dtype=torch.long))
