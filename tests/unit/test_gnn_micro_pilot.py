"""Unit tests protecting Phase-2 GNN routing and tensor pipeline components."""

from __future__ import annotations

import networkx as nx
import torch

from nroute.benchmark.gnn_router import GNNRouter
from nroute.core.topology import Topology
from nroute.ml.features.extractor import DefaultGraphFeatureExtractor
from nroute.ml.models.gcn import GCNModel
from nroute.ml.models.graphsage import GraphSAGEModel


def _build_test_topology() -> Topology:
    g = nx.DiGraph()
    for n in ["A", "B", "C", "D"]:
        g.add_node(n, capacity=1000.0, status="up", type="router")
    g.add_edge("A", "B", bandwidth=10.0, latency=5.0, utilization=0.0, packet_loss=0.0, status="up")
    g.add_edge("B", "D", bandwidth=10.0, latency=5.0, utilization=0.0, packet_loss=0.0, status="up")
    g.add_edge(
        "A", "C", bandwidth=100.0, latency=10.0, utilization=0.0, packet_loss=0.0, status="up"
    )
    g.add_edge(
        "C", "D", bandwidth=100.0, latency=10.0, utilization=0.0, packet_loss=0.0, status="up"
    )
    return Topology(g)


def test_gnn_feature_extraction_and_shapes() -> None:
    """Verify DefaultGraphFeatureExtractor produces valid CPU tensors without NaNs."""
    topo = _build_test_topology()
    extractor = DefaultGraphFeatureExtractor(use_pytorch=True)
    bundle = extractor.extract_features(topo)

    assert bundle.node_features.shape == (4, 3)
    assert bundle.edge_index.shape == (2, 4)
    assert bundle.edge_features.shape == (4, 5)
    assert bundle.node_features.device.type == "cpu"
    assert not torch.isnan(bundle.node_features).any()
    assert not torch.isnan(bundle.edge_features).any()


def test_gnn_models_forward_and_dimension_invariance() -> None:
    """Verify GCN and GraphSAGE output expected tensor shapes across varying graph sizes."""
    topo = _build_test_topology()
    extractor = DefaultGraphFeatureExtractor(use_pytorch=True)
    bundle = extractor.extract_features(topo)

    torch.manual_seed(42)
    gcn = GCNModel(node_in_dim=3, edge_in_dim=5, hidden_dim=32, num_layers=2)
    sage = GraphSAGEModel(node_in_dim=3, edge_in_dim=5, hidden_dim=32, num_layers=2)

    gcn.eval()
    sage.eval()

    with torch.no_grad():
        c_gcn, l_gcn = gcn(bundle.node_features, bundle.edge_index, bundle.edge_features)
        c_sage, l_sage = sage(bundle.node_features, bundle.edge_index, bundle.edge_features)

    assert c_gcn.shape == (4,)
    assert l_gcn.shape == (4,)
    assert c_sage.shape == (4,)
    assert l_sage.shape == (4,)
    assert not torch.isnan(c_gcn).any()
    assert not torch.isnan(c_sage).any()


def test_gnn_router_path_deflection_under_bottleneck() -> None:
    """Verify GNNRouter maps predicted congestion to edge weights and shifts paths."""
    topo = _build_test_topology()

    class MockGNN(torch.nn.Module):
        def forward(
            self,
            nf: torch.Tensor,
            ei: torch.Tensor,
            ef: torch.Tensor,
        ) -> tuple[torch.Tensor, torch.Tensor]:
            # ef[:, 2] is utilization
            utils = ef[:, 2]
            c_logits = torch.where(utils >= 0.70, torch.tensor(5.0), torch.tensor(-5.0))
            l_preds = ef[:, 1] * 100.0
            return c_logits, l_preds

    router = GNNRouter(MockGNN(), alpha=5.0)

    # 1. Uncongested state: A -> B -> D (Cost 10ms)
    path_uncong = router.compute_path(topo, "A", "D")
    assert path_uncong == ["A", "B", "D"]

    # 2. Congested state: A->B is 95% utilized -> path shifts to A -> C -> D (Cost 20ms)
    topo.update_edge("A", "B", utilization=0.95)
    path_cong = router.compute_path(topo, "A", "D")
    assert path_cong == ["A", "C", "D"]


def test_gnn_router_permutation_equivariance() -> None:
    """Verify GNNRouter path decisions are invariant to node label permutations."""
    topo = _build_test_topology()

    class MockGNN(torch.nn.Module):
        def forward(
            self,
            nf: torch.Tensor,
            ei: torch.Tensor,
            ef: torch.Tensor,
        ) -> tuple[torch.Tensor, torch.Tensor]:
            utils = ef[:, 2]
            c_logits = torch.where(utils >= 0.70, torch.tensor(5.0), torch.tensor(-5.0))
            l_preds = ef[:, 1] * 100.0
            return c_logits, l_preds

    router = GNNRouter(MockGNN(), alpha=5.0)
    orig_path = router.compute_path(topo, "A", "D")

    perm_map = {"A": "NODE_3", "B": "NODE_0", "C": "NODE_1", "D": "NODE_2"}
    inv_map = {v: k for k, v in perm_map.items()}
    perm_topo = Topology(nx.relabel_nodes(topo.graph, perm_map))

    perm_path = router.compute_path(perm_topo, "NODE_3", "NODE_2")
    mapped_back = [inv_map[n] for n in perm_path]

    assert mapped_back == orig_path
