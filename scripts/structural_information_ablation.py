"""Phase-2 Structural Information Sanity Gate & Ablation Experiment.

Conducts controlled diagnostic ablations:
- Ablation A: GNN without direct utilization feature (Graph topology + capacities/degrees only)
- Ablation B: Edge-Only MLP baseline (Edge features without graph message passing)
- Ablation C: Local utilization-threshold baseline (Instantaneous thresholding)
- Ablation D: Full official frozen GCN and GraphSAGE models

Also evaluates a controlled multi-hop structural funneling scenario to verify if
2-hop message passing detects downstream bottleneck accumulation.
"""

from typing import Any

import networkx as nx
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import f1_score, roc_auc_score

from nroute.benchmark.dynamic_dijkstra import DynamicDijkstraRouter
from nroute.benchmark.gnn_router import GNNRouter
from nroute.core.generators import TopologyGenerator
from nroute.core.topology import Topology
from nroute.ml.features.extractor import DefaultGraphFeatureExtractor
from nroute.ml.models.gcn import GCNModel
from nroute.ml.models.graphsage import GraphSAGEModel


# --- Ablation B Model: Edge-Only MLP (No Message Passing) ---
class EdgeOnlyMLP(nn.Module):
    """MLP classifier operating strictly on edge features without graph connectivity."""

    def __init__(self, edge_in_dim: int = 5, hidden_dim: int = 64) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(edge_in_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(
        self,
        node_features: torch.Tensor,
        edge_index: torch.Tensor,
        edge_features: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        logits = self.net(edge_features).squeeze(-1)
        lat_preds = edge_features[:, 1] * 100.0
        return logits, lat_preds


def generate_partition_data(
    topos: list[Topology],
    n_snapshots_per_topo: int = 50,
    seed: int = 1001,
    mask_utilization: bool = False,
) -> list[tuple[Any, torch.Tensor, torch.Tensor]]:
    """Generate graph feature bundles and targets, optionally zeroing out utilization."""
    extractor = DefaultGraphFeatureExtractor(use_pytorch=True)
    rng = np.random.default_rng(seed)
    dataset = []

    for topo in topos:
        for _ in range(n_snapshots_per_topo):
            for u, v in topo.edges:
                util = float(rng.beta(0.5, 0.5))
                topo.update_edge(u, v, utilization=util)

            bundle = extractor.extract_features(topo)
            ef = bundle.edge_features.clone()

            # Target is based on original unmasked utilization >= 0.70
            cong_target = torch.where(ef[:, 2] >= 0.70, torch.tensor(1.0), torch.tensor(0.0))
            lat_target = ef[:, 1] * 100.0 * (1.0 + 5.0 * ef[:, 2])

            if mask_utilization:
                # Zero out utilization column (index 2)
                ef[:, 2] = 0.0
                bundle.edge_features = ef

            dataset.append((bundle, cong_target, lat_target))

    return dataset


def evaluate_model(
    model: nn.Module,
    dataset: list[tuple[Any, torch.Tensor, torch.Tensor]],
) -> dict[str, float]:
    """Compute validation loss, ROC-AUC, F1, and BCE."""
    model.eval()
    bce_fn = nn.BCEWithLogitsLoss()
    all_preds = []
    all_targets = []
    total_bce = 0.0

    with torch.no_grad():
        for bundle, c_target, _ in dataset:
            c_logits, _ = model(bundle.node_features, bundle.edge_index, bundle.edge_features)
            bce = bce_fn(c_logits, c_target).item()
            total_bce += bce
            probs = torch.sigmoid(c_logits).cpu().numpy()
            all_preds.extend(probs)
            all_targets.extend(c_target.cpu().numpy())

    preds_arr = np.array(all_preds)
    targets_arr = np.array(all_targets)

    roc_auc = (
        float(roc_auc_score(targets_arr, preds_arr)) if len(np.unique(targets_arr)) > 1 else 0.5
    )
    f1 = float(f1_score(targets_arr, (preds_arr >= 0.50).astype(int)))
    pos_rate = float(np.mean(preds_arr >= 0.50))

    return {
        "bce_loss": total_bce / len(dataset),
        "roc_auc": roc_auc,
        "f1": f1,
        "pred_pos_rate": pos_rate,
        "mean_prob": float(np.mean(preds_arr)),
    }


def evaluate_local_threshold(
    dataset: list[tuple[Any, torch.Tensor, torch.Tensor]],
) -> dict[str, float]:
    """Evaluate simple deterministic local utilization threshold: prob = 1.0 if util >= 0.70 else 0.0."""
    all_preds = []
    all_targets = []
    bce_fn = nn.BCELoss()

    for bundle, c_target, _ in dataset:
        utils = bundle.edge_features[:, 2].cpu().numpy()
        # Calibrated smooth threshold prob
        probs = 1.0 / (1.0 + np.exp(-15.0 * (utils - 0.70)))
        all_preds.extend(probs)
        all_targets.extend(c_target.cpu().numpy())

    preds_arr = np.clip(np.array(all_preds), 1e-6, 1.0 - 1e-6)
    targets_arr = np.array(all_targets)

    bce = float(bce_fn(torch.from_numpy(preds_arr), torch.from_numpy(targets_arr)).item())
    roc_auc = float(roc_auc_score(targets_arr, preds_arr))
    f1 = float(f1_score(targets_arr, (preds_arr >= 0.50).astype(int)))

    return {
        "bce_loss": bce,
        "roc_auc": roc_auc,
        "f1": f1,
        "pred_pos_rate": float(np.mean(preds_arr >= 0.50)),
        "mean_prob": float(np.mean(preds_arr)),
    }


def build_downstream_funnel_topology() -> Topology:
    """
    Construct a controlled multi-hop structural funneling scenario.
    Source: S, Destination: D.
    Both immediate links (S -> Path1_Hop1) and (S -> Path2_Hop1) have IDENTICAL local utilization (U = 0.50, Lat = 5ms).

    Path 1 (Funnel): S -> B1 (U=0.50, L=5ms) -> B2 (Cut-vertex, U=0.95, Bottleneck L=5ms) -> D (L=5ms)
    Path 2 (Multi-path): S -> C1 (U=0.50, L=5ms) -> C2 (Wide multi-path trunk, U=0.10, L=5ms) -> D (L=5ms)
    """
    g = nx.DiGraph()
    nodes = ["S", "B1", "B2", "C1", "C2", "D"]
    for n in nodes:
        g.add_node(n, capacity=1000.0, status="up", type="router")

    edges = [
        # Path 1: Downstream Funnel (Severe 2-hop congestion at B2)
        ("S", "B1", 100.0, 5.0, 0.50),
        ("B1", "B2", 10.0, 5.0, 0.95),  # Bottleneck link 2 hops away from S
        ("B2", "D", 100.0, 5.0, 0.05),
        # Path 2: Downstream Clear Path
        ("S", "C1", 100.0, 5.0, 0.50),
        ("C1", "C2", 100.0, 5.0, 0.10),  # Clear link 2 hops away from S
        ("C2", "D", 100.0, 5.0, 0.05),
    ]
    for u, v, bw, lat, util in edges:
        g.add_edge(
            u,
            v,
            bandwidth=bw,
            latency=lat,
            utilization=util,
            packet_loss=0.0,
            status="up",
            weight=lat,
        )

    return Topology(g)


def run_ablation():
    print("=" * 80)
    print("PHASE-2 STRUCTURAL INFORMATION ABLATION EXPERIMENT")
    print("=" * 80)

    # 1. Load Data Partitions
    train_topos = [
        TopologyGenerator.small_world(n_nodes=30, k_neighbors=4, rewire_prob=0.1, seed=1001),
        TopologyGenerator.random(n_nodes=40, edge_prob=0.08, seed=1002),
        TopologyGenerator.scale_free(n_nodes=45, seed=1003),
    ]
    val_topos = [
        TopologyGenerator.small_world(n_nodes=35, k_neighbors=4, rewire_prob=0.1, seed=501),
        TopologyGenerator.random(n_nodes=45, edge_prob=0.06, seed=502),
    ]

    train_std = generate_partition_data(train_topos, n_snapshots_per_topo=60, seed=1001)
    val_std = generate_partition_data(val_topos, n_snapshots_per_topo=30, seed=501)

    train_nounscaled = generate_partition_data(
        train_topos, n_snapshots_per_topo=60, seed=1001, mask_utilization=True
    )
    val_nounscaled = generate_partition_data(
        val_topos, n_snapshots_per_topo=30, seed=501, mask_utilization=True
    )

    # 2. Ablation C: Local Utilization Threshold Baseline
    res_c = evaluate_local_threshold(val_std)

    # 3. Ablation D: Official Frozen GCN & GraphSAGE Models
    gcn_frozen = GCNModel(node_in_dim=3, edge_in_dim=5, hidden_dim=64, num_layers=2)
    sage_frozen = GraphSAGEModel(node_in_dim=3, edge_in_dim=5, hidden_dim=64, num_layers=2)

    gcn_frozen.load_state_dict(torch.load("models/gnn/gcn_model_frozen.pt", map_location="cpu"))
    sage_frozen.load_state_dict(
        torch.load("models/gnn/graphsage_model_frozen.pt", map_location="cpu")
    )

    res_d_gcn = evaluate_model(gcn_frozen, val_std)
    res_d_sage = evaluate_model(sage_frozen, val_std)

    # 4. Ablation B: Edge-Only MLP (No Graph Message Passing)
    mlp_model = EdgeOnlyMLP(edge_in_dim=5, hidden_dim=64)
    opt_mlp = optim.Adam(mlp_model.parameters(), lr=0.005, weight_decay=1e-4)
    bce_loss = nn.BCEWithLogitsLoss()

    for _ in range(30):
        mlp_model.train()
        for bundle, c_target, _ in train_std:
            opt_mlp.zero_grad()
            logits, _ = mlp_model(bundle.node_features, bundle.edge_index, bundle.edge_features)
            loss = bce_loss(logits, c_target)
            loss.backward()
            opt_mlp.step()

    res_b_mlp = evaluate_model(mlp_model, val_std)

    # 5. Ablation A: GNN with Utilization Feature REMOVED
    gcn_no_util = GCNModel(node_in_dim=3, edge_in_dim=5, hidden_dim=64, num_layers=2)
    sage_no_util = GraphSAGEModel(node_in_dim=3, edge_in_dim=5, hidden_dim=64, num_layers=2)

    opt_gcn_nu = optim.Adam(gcn_no_util.parameters(), lr=0.005, weight_decay=1e-4)
    opt_sage_nu = optim.Adam(sage_no_util.parameters(), lr=0.005, weight_decay=1e-4)

    for _ in range(30):
        gcn_no_util.train()
        sage_no_util.train()
        for bundle, c_target, _ in train_nounscaled:
            opt_gcn_nu.zero_grad()
            c_g, _ = gcn_no_util(bundle.node_features, bundle.edge_index, bundle.edge_features)
            loss_g = bce_loss(c_g, c_target)
            loss_g.backward()
            opt_gcn_nu.step()

            opt_sage_nu.zero_grad()
            c_s, _ = sage_no_util(bundle.node_features, bundle.edge_index, bundle.edge_features)
            loss_s = bce_loss(c_s, c_target)
            loss_s.backward()
            opt_sage_nu.step()

    res_a_gcn = evaluate_model(gcn_no_util, val_nounscaled)
    res_a_sage = evaluate_model(sage_no_util, val_nounscaled)

    # Print Ablation Summary Table
    print("\n" + "=" * 80)
    print("ABLATION COMPARISON MATRIX (Validation Partition Seeds 501, 502)")
    print("=" * 80)
    print(
        f"{'Model / Ablation Arm':<36} | {'ROC-AUC':<8} | {'Binary F1':<9} | {'BCE Loss':<8} | {'PosRate':<8}"
    )
    print("-" * 80)
    print(
        f"{'Ablation C: Local Threshold (Util >= 0.70)':<36} | {res_c['roc_auc']:<8.4f} | {res_c['f1']:<9.4f} | {res_c['bce_loss']:<8.4f} | {res_c['pred_pos_rate'] * 100:<7.1f}%"
    )
    print(
        f"{'Ablation B: Edge-Only MLP (No GNN MsgPass)':<36} | {res_b_mlp['roc_auc']:<8.4f} | {res_b_mlp['f1']:<9.4f} | {res_b_mlp['bce_loss']:<8.4f} | {res_b_mlp['pred_pos_rate'] * 100:<7.1f}%"
    )
    print(
        f"{'Ablation D: Frozen GCNModel (Full Graph)':<36} | {res_d_gcn['roc_auc']:<8.4f} | {res_d_gcn['f1']:<9.4f} | {res_d_gcn['bce_loss']:<8.4f} | {res_d_gcn['pred_pos_rate'] * 100:<7.1f}%"
    )
    print(
        f"{'Ablation D: Frozen GraphSAGEModel (Full Graph)':<36} | {res_d_sage['roc_auc']:<8.4f} | {res_d_sage['f1']:<9.4f} | {res_d_sage['bce_loss']:<8.4f} | {res_d_sage['pred_pos_rate'] * 100:<7.1f}%"
    )
    print(
        f"{'Ablation A: GCN without Utilization Feature':<36} | {res_a_gcn['roc_auc']:<8.4f} | {res_a_gcn['f1']:<9.4f} | {res_a_gcn['bce_loss']:<8.4f} | {res_a_gcn['pred_pos_rate'] * 100:<7.1f}%"
    )
    print(
        f"{'Ablation A: GraphSAGE without Utilization Feature':<36} | {res_a_sage['roc_auc']:<8.4f} | {res_a_sage['f1']:<9.4f} | {res_a_sage['bce_loss']:<8.4f} | {res_a_sage['pred_pos_rate'] * 100:<7.1f}%"
    )
    print("-" * 80)

    # 6. Controlled Multi-Hop Funneling Scenario
    print("\n" + "=" * 80)
    print("CONTROLLED MULTI-HOP DOWNSTREAM FUNNELING TEST")
    print("=" * 80)
    funnel_topo = build_downstream_funnel_topology()
    print("Scenario: S -> D routing query")
    print(
        "  Immediate links from S have IDENTICAL local state: S->B1 (U=0.50, L=5ms) vs S->C1 (U=0.50, L=5ms)"
    )
    print("  Path 1 (Downstream Funnel): S -> B1 -> B2 (U=0.95 BOTTLENECK) -> D")
    print("  Path 2 (Downstream Clear):  S -> C1 -> C2 (U=0.10 CLEAR) -> D")

    # Dynamic-Dijkstra Path
    dd_router = DynamicDijkstraRouter(alpha=5.0)
    path_dd = dd_router.compute_path(funnel_topo, "S", "D")

    # GCN and GraphSAGE Paths
    gcn_router = GNNRouter(gcn_frozen, alpha=5.0)
    sage_router = GNNRouter(sage_frozen, alpha=5.0)

    path_gcn = gcn_router.compute_path(funnel_topo, "S", "D")
    path_sage = sage_router.compute_path(funnel_topo, "S", "D")

    weights_gcn = gcn_router.compute_edge_weights(funnel_topo)
    weights_sage = sage_router.compute_edge_weights(funnel_topo)

    print("\nRouting Decisions for S -> D:")
    print(f"  Dynamic-Dijkstra Path: {path_dd}")
    print(f"  GCN-Dijkstra Path:     {path_gcn}")
    print(f"  GraphSAGE-Dijkstra:    {path_sage}")

    print("\nPredicted Edge Weights on Immediate Outgoing Links from S:")
    print(
        f"  Link (S -> B1): Dynamic-Dijkstra = 5.0*(1+5*0.50) = 17.50ms | GCN = {weights_gcn[('S', 'B1')]:.2f}ms | GraphSAGE = {weights_sage[('S', 'B1')]:.2f}ms"
    )
    print(
        f"  Link (S -> C1): Dynamic-Dijkstra = 5.0*(1+5*0.50) = 17.50ms | GCN = {weights_gcn[('S', 'C1')]:.2f}ms | GraphSAGE = {weights_sage[('S', 'C1')]:.2f}ms"
    )

    print("\nPredicted Edge Weights on Downstream 2nd-Hop Links:")
    print(
        f"  Link (B1 -> B2 - Congested): Dynamic-Dijkstra = 5.0*(1+5*0.95) = 28.75ms | GCN = {weights_gcn[('B1', 'B2')]:.2f}ms | GraphSAGE = {weights_sage[('B1', 'B2')]:.2f}ms"
    )
    print(
        f"  Link (C1 -> C2 - Clear):     Dynamic-Dijkstra = 5.0*(1+5*0.10) =  7.50ms | GCN = {weights_gcn[('C1', 'C2')]:.2f}ms | GraphSAGE = {weights_sage[('C1', 'C2')]:.2f}ms"
    )

    # Path cost comparison
    total_cost_path1_dd = 17.5 + 28.75 + 5.0 * (1 + 5 * 0.05)
    total_cost_path2_dd = 17.5 + 7.50 + 5.0 * (1 + 5 * 0.05)
    print("\nPath Total Weights in Dijkstra Graph Search:")
    print(
        f"  Path 1 (via B1->B2 Bottleneck): DynCost = {total_cost_path1_dd:.2f}ms | GCNCost = {weights_gcn[('S', 'B1')] + weights_gcn[('B1', 'B2')] + weights_gcn[('B2', 'D')]:.2f}ms"
    )
    print(
        f"  Path 2 (via C1->C2 Clear):      DynCost = {total_cost_path2_dd:.2f}ms | GCNCost = {weights_gcn[('S', 'C1')] + weights_gcn[('C1', 'C2')] + weights_gcn[('C2', 'D')]:.2f}ms"
    )

    print("=" * 80)


if __name__ == "__main__":
    run_ablation()
