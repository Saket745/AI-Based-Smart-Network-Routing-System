"""Direction-C 60-Run Pilot Experiment Runner & Statistical Analyzer.

Executes the pre-declared 60-run Direction-C pilot:
- 2 Topologies: Fat-Tree (N=36), Scale-Free (N=50)
- 5 Stratified Cuts per topology (High, Med, Low betweenness, Articulation/Bridge)
- 2 Evaluation Seeds: 42, 43
- 3 Predictive Models: Edge-Only MLP, GCN, GraphSAGE
- Total: 2 x 5 x 2 x 3 = 60 matched experiment evaluations.

Saves machine-readable CSV/JSON artifacts and generates complete statistical reports.
"""

import hashlib
import json
import subprocess
import time
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import scipy.stats as stats
import torch
import torch.nn as nn
import torch.optim as optim

from nroute.benchmark.blast_radius_oracle import (
    BlastRadiusOracle,
    FailureConditionedFeatureExtractor,
    FlowDemand,
)
from nroute.core.generators import TopologyGenerator
from nroute.core.topology import Topology

# --- Direction-C Model Architectures ---


class DirectionCEdgeMLP(nn.Module):
    """Local edge-only MLP for Direction-C (6-dim input)."""

    def __init__(self, in_dim: int = 6, hidden_dim: int = 64) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
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
    ) -> torch.Tensor:
        return self.net(edge_features).squeeze(-1)


class DirectionCGCN(nn.Module):
    """GCN surrogate for Direction-C with edge regression head."""

    def __init__(self, node_in: int = 5, edge_in: int = 6, hidden_dim: int = 64) -> None:
        super().__init__()
        self.node_proj = nn.Linear(node_in, hidden_dim)
        self.conv1_weight = nn.Linear(hidden_dim, hidden_dim)
        self.conv2_weight = nn.Linear(hidden_dim, hidden_dim)
        self.edge_head = nn.Sequential(
            nn.Linear(hidden_dim * 2 + edge_in, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )
        self.relu = nn.ReLU()

    def forward(
        self,
        node_features: torch.Tensor,
        edge_index: torch.Tensor,
        edge_features: torch.Tensor,
    ) -> torch.Tensor:
        h = self.relu(self.node_proj(node_features))
        num_nodes = node_features.size(0)

        # Compute degree-normalized adjacency
        src, dst = edge_index[0], edge_index[1]
        deg = torch.zeros(num_nodes, device=node_features.device)
        deg.scatter_add_(0, dst, torch.ones_like(dst, dtype=torch.float32))
        deg_inv_sqrt = torch.pow(deg.clamp(min=1.0), -0.5)
        norm = deg_inv_sqrt[src] * deg_inv_sqrt[dst]

        # Layer 1
        msg1 = h[src] * norm.unsqueeze(-1)
        agg1 = torch.zeros_like(h)
        agg1.scatter_add_(0, dst.unsqueeze(-1).expand_as(msg1), msg1)
        h = self.relu(self.conv1_weight(agg1))

        # Layer 2
        msg2 = h[src] * norm.unsqueeze(-1)
        agg2 = torch.zeros_like(h)
        agg2.scatter_add_(0, dst.unsqueeze(-1).expand_as(msg2), msg2)
        h = self.relu(self.conv2_weight(agg2))

        # Edge head
        edge_h = torch.cat([h[src], h[dst], edge_features], dim=-1)
        return self.edge_head(edge_h).squeeze(-1)


class DirectionCGraphSAGE(nn.Module):
    """GraphSAGE surrogate for Direction-C with mean neighbor aggregation and edge head."""

    def __init__(self, node_in: int = 5, edge_in: int = 6, hidden_dim: int = 64) -> None:
        super().__init__()
        self.node_proj = nn.Linear(node_in, hidden_dim)
        self.sage1 = nn.Linear(hidden_dim * 2, hidden_dim)
        self.sage2 = nn.Linear(hidden_dim * 2, hidden_dim)
        self.edge_head = nn.Sequential(
            nn.Linear(hidden_dim * 2 + edge_in, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )
        self.relu = nn.ReLU()

    def forward(
        self,
        node_features: torch.Tensor,
        edge_index: torch.Tensor,
        edge_features: torch.Tensor,
    ) -> torch.Tensor:
        h = self.relu(self.node_proj(node_features))
        num_nodes = node_features.size(0)
        src, dst = edge_index[0], edge_index[1]

        deg = torch.zeros(num_nodes, device=node_features.device)
        deg.scatter_add_(0, dst, torch.ones_like(dst, dtype=torch.float32)).clamp_(min=1.0)

        # Layer 1
        msg1 = h[src]
        agg1 = torch.zeros_like(h)
        agg1.scatter_add_(0, dst.unsqueeze(-1).expand_as(msg1), msg1)
        agg1 = agg1 / deg.unsqueeze(-1)
        h = self.relu(self.sage1(torch.cat([h, agg1], dim=-1)))

        # Layer 2
        msg2 = h[src]
        agg2 = torch.zeros_like(h)
        agg2.scatter_add_(0, dst.unsqueeze(-1).expand_as(msg2), msg2)
        agg2 = agg2 / deg.unsqueeze(-1)
        h = self.relu(self.sage2(torch.cat([h, agg2], dim=-1)))

        edge_h = torch.cat([h[src], h[dst], edge_features], dim=-1)
        return self.edge_head(edge_h).squeeze(-1)


# --- Training & Checkpoint Freezing ---


def train_and_freeze_direction_c_models() -> dict[str, str]:
    """Train models on disjoint training partition and freeze checkpoints."""
    print("\n1. Training Direction-C Surrogate Models on Disjoint Partition...")
    train_topos = [
        TopologyGenerator.small_world(n_nodes=30, k_neighbors=4, rewire_prob=0.1, seed=1001),
        TopologyGenerator.random(n_nodes=40, edge_prob=0.08, seed=1002),
        TopologyGenerator.scale_free(n_nodes=45, seed=1003),
    ]

    rng = np.random.default_rng(1001)
    dataset = []

    for topo in train_topos:
        nodes = sorted(topo.nodes)
        edges = sorted(topo.edges)
        # Generate active flows
        flows = []
        for i in range(40):
            src, dst = rng.choice(nodes, size=2, replace=False)
            demand = float(rng.uniform(10.0, 40.0))
            flows.append(FlowDemand(f"flow_{i}", str(src), str(dst), demand))

        # Sample 15 random cuts per topology
        cut_candidates = list(rng.choice(edges, size=min(15, len(edges)), replace=False))
        for cut in cut_candidates:
            cut_tuple = (str(cut[0]), str(cut[1]))
            oracle_res = BlastRadiusOracle.compute_reroute_ground_truth(topo, flows, cut_tuple)
            bundle = FailureConditionedFeatureExtractor.extract_failure_features(
                topo, cut_tuple, u_pre=oracle_res["u_pre"]
            )
            # Create target vector aligned with bundle['edges']
            target = []
            for e in bundle["edges"]:
                target.append(oracle_res["delta_u"].get(e, -oracle_res["u_pre"].get(e, 0.0)))
            target_tensor = torch.tensor(target, dtype=torch.float32)
            dataset.append((bundle, target_tensor))

    print(f"   Generated {len(dataset)} training graph-cut snapshots.")

    mlp = DirectionCEdgeMLP()
    gcn = DirectionCGCN()
    sage = DirectionCGraphSAGE()

    opt_mlp = optim.Adam(mlp.parameters(), lr=0.005, weight_decay=1e-4)
    opt_gcn = optim.Adam(gcn.parameters(), lr=0.005, weight_decay=1e-4)
    opt_sage = optim.Adam(sage.parameters(), lr=0.005, weight_decay=1e-4)
    loss_fn = nn.SmoothL1Loss()

    for _epoch in range(25):
        mlp.train()
        gcn.train()
        sage.train()
        for bundle, target in dataset:
            surv = bundle["surviving_edge_indices"]
            # MLP
            opt_mlp.zero_grad()
            p_m = mlp(bundle["node_features"], bundle["edge_index"], bundle["edge_features"])
            l_m = loss_fn(p_m[surv], target[surv])
            l_m.backward()
            opt_mlp.step()

            # GCN
            opt_gcn.zero_grad()
            p_g = gcn(bundle["node_features"], bundle["edge_index"], bundle["edge_features"])
            l_g = loss_fn(p_g[surv], target[surv])
            l_g.backward()
            opt_gcn.step()

            # SAGE
            opt_sage.zero_grad()
            p_s = sage(bundle["node_features"], bundle["edge_index"], bundle["edge_features"])
            l_s = loss_fn(p_s[surv], target[surv])
            l_s.backward()
            opt_sage.step()

    Path("models/gnn").mkdir(parents=True, exist_ok=True)
    paths = {
        "edge_mlp": "models/gnn/direction_c_edge_mlp.pt",
        "gcn": "models/gnn/direction_c_gcn.pt",
        "graphsage": "models/gnn/direction_c_graphsage.pt",
    }
    torch.save(mlp.state_dict(), paths["edge_mlp"])
    torch.save(gcn.state_dict(), paths["gcn"])
    torch.save(sage.state_dict(), paths["graphsage"])

    hashes = {}
    for k, p in paths.items():
        with open(p, "rb") as f:
            hashes[k] = hashlib.sha256(f.read()).hexdigest()
        print(f"   Saved {k}: {p} (SHA-256: {hashes[k][:16]}...)")

    return hashes


# --- Stratified Cut Selection ---


def select_stratified_cuts(topo: Topology, seed: int = 42) -> list[tuple[tuple[str, str], str]]:
    """Sample exactly 5 stratified cuts (2 High, 1 Med, 1 Low, 1 Articulation/Bridge)."""
    graph = topo.graph
    edges = list(graph.edges)
    rng = np.random.default_rng(seed)

    # Compute edge betweenness
    edge_bc = nx.edge_betweenness_centrality(graph)
    sorted_edges = sorted(edge_bc.items(), key=lambda x: x[1], reverse=True)

    n_edges = len(sorted_edges)
    # Stratum 1: High Betweenness (Top 15%)
    high_candidates = [e for e, _ in sorted_edges[: max(2, int(n_edges * 0.15))]]
    high_selected = list(rng.choice(high_candidates, size=2, replace=False))

    # Stratum 2: Medium Betweenness (40th-65th percentile)
    med_candidates = [e for e, _ in sorted_edges[int(n_edges * 0.40) : int(n_edges * 0.65)]]
    med_selected = [rng.choice(med_candidates)]

    # Stratum 3: Low Betweenness (Bottom 25%)
    low_candidates = [e for e, _ in sorted_edges[int(n_edges * 0.75) :]]
    low_selected = [rng.choice(low_candidates)]

    # Stratum 4: Bridge / Non-redundant Cut
    # Check bridges
    undirected = graph.to_undirected()
    bridges = list(nx.bridges(undirected))
    directed_bridges = [e for e in edges if (e[0], e[1]) in bridges or (e[1], e[0]) in bridges]

    if directed_bridges:
        bridge_selected = [rng.choice(directed_bridges)]
    else:
        # Fallback to a high-degree node's chord
        bridge_selected = [sorted_edges[max(0, int(n_edges * 0.25))][0]]

    selected_cuts = []
    for e in high_selected:
        selected_cuts.append(((str(e[0]), str(e[1])), "high_betweenness"))
    for e in med_selected:
        selected_cuts.append(((str(e[0]), str(e[1])), "medium_betweenness"))
    for e in low_selected:
        selected_cuts.append(((str(e[0]), str(e[1])), "low_betweenness"))
    for e in bridge_selected:
        selected_cuts.append(((str(e[0]), str(e[1])), "bridge_or_critical"))

    return selected_cuts


# --- Flow Generation ---


def generate_evaluation_flows(
    topo: Topology, seed: int = 42, n_flows: int = 60
) -> list[FlowDemand]:
    """Generate deterministic evaluation flow demands."""
    nodes = sorted(topo.nodes)
    rng = np.random.default_rng(seed)
    flows = []
    for i in range(n_flows):
        src, dst = rng.choice(nodes, size=2, replace=False)
        demand = float(rng.uniform(15.0, 45.0))
        flows.append(FlowDemand(f"eval_flow_{i}", str(src), str(dst), demand))
    return flows


# --- Metric Calculation ---


def compute_experiment_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, float]:
    """Compute experiment-level regression, ranking, and severe-spike metrics."""
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))

    # R2 score
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = float(1.0 - (ss_res / (ss_tot + 1e-8)))

    # Top-3 Bottleneck Recall
    k = min(3, len(y_true))
    top_k_true = set(np.argsort(y_true)[-k:])
    top_k_pred = set(np.argsort(y_pred)[-k:])
    top3_recall = float(len(top_k_true.intersection(top_k_pred)) / k)

    # Top-5% Recall
    top_pct_count = max(1, int(len(y_true) * 0.05))
    top_pct_true = set(np.argsort(y_true)[-top_pct_count:])
    top_pct_pred = set(np.argsort(y_pred)[-top_pct_count:])
    top5pct_recall = float(len(top_pct_true.intersection(top_pct_pred)) / top_pct_count)

    # Severe Spike False Negative Rate (True Delta_U >= 0.25)
    severe_mask = y_true >= 0.25
    if np.sum(severe_mask) > 0:
        fn_count = np.sum((y_true[severe_mask] >= 0.25) & (y_pred[severe_mask] < 0.25))
        severe_fn_rate = float(fn_count / np.sum(severe_mask))
    else:
        severe_fn_rate = 0.0

    return {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "top3_recall": top3_recall,
        "top5pct_recall": top5pct_recall,
        "severe_fn_rate": severe_fn_rate,
    }


# --- Main 60-Run Pilot Execution ---


def run_60_pilot():
    print("=" * 80)
    print("DIRECTION-C 60-RUN PILOT BENCHMARK EXECUTION")
    print("=" * 80)

    # 1. Train and Freeze Models
    hashes = train_and_freeze_direction_c_models()

    # Load frozen weights
    mlp = DirectionCEdgeMLP()
    gcn = DirectionCGCN()
    sage = DirectionCGraphSAGE()

    mlp.load_state_dict(torch.load("models/gnn/direction_c_edge_mlp.pt", map_location="cpu"))
    gcn.load_state_dict(torch.load("models/gnn/direction_c_gcn.pt", map_location="cpu"))
    sage.load_state_dict(torch.load("models/gnn/direction_c_graphsage.pt", map_location="cpu"))

    mlp.eval()
    gcn.eval()
    sage.eval()

    # Get Git SHA
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        git_sha = "unknown_sha"

    topologies = [
        ("fat_tree", TopologyGenerator.fat_tree(k=4)),
        ("scale_free", TopologyGenerator.scale_free(n_nodes=50, seed=42)),
    ]
    seeds = [42, 43]
    models = [
        ("Edge-Only MLP", mlp, hashes["edge_mlp"]),
        ("GCN", gcn, hashes["gcn"]),
        ("GraphSAGE", sage, hashes["graphsage"]),
    ]

    results = []
    scenario_counter = 0

    print("\n2. Executing 60 Pilot Evaluations (2 Topologies x 5 Cuts x 2 Seeds x 3 Models)...")

    for topo_name, topo in topologies:
        for seed in seeds:
            # Generate deterministic flows for this evaluation seed
            flows = generate_evaluation_flows(topo, seed=seed, n_flows=60)
            stratified_cuts = select_stratified_cuts(topo, seed=seed)

            for cut_edge, stratum in stratified_cuts:
                scenario_counter += 1

                # Execute Oracle (Ground Truth Label Generator)
                t0_oracle = time.perf_counter_ns()
                oracle_res = BlastRadiusOracle.compute_reroute_ground_truth(topo, flows, cut_edge)
                t_oracle_us = (time.perf_counter_ns() - t0_oracle) / 1000.0

                u_pre = oracle_res["u_pre"]
                delta_u = oracle_res["delta_u"]

                # Extract Failure-Conditioned Feature Bundle
                t0_enc = time.perf_counter_ns()
                bundle = FailureConditionedFeatureExtractor.extract_failure_features(
                    topo, cut_edge, u_pre=u_pre
                )
                t_enc_us = (time.perf_counter_ns() - t0_enc) / 1000.0

                surv_indices = bundle["surviving_edge_indices"]
                surv_edges = [bundle["edges"][i] for i in surv_indices]

                # True Delta_U array for surviving edges
                y_true = np.array([delta_u[e] for e in surv_edges], dtype=np.float32)

                # Evaluate Each Model
                for model_name, model, model_hash in models:
                    t0_inf = time.perf_counter_ns()
                    with torch.no_grad():
                        preds = model(
                            bundle["node_features"], bundle["edge_index"], bundle["edge_features"]
                        )
                    t_inf_us = (time.perf_counter_ns() - t0_inf) / 1000.0

                    t0_dec = time.perf_counter_ns()
                    y_pred = preds[surv_indices].cpu().numpy()
                    metrics = compute_experiment_metrics(y_true, y_pred)
                    t_dec_us = (time.perf_counter_ns() - t0_dec) / 1000.0

                    t_total_us = t_enc_us + t_inf_us + t_dec_us

                    row = {
                        "scenario_id": f"{topo_name}_{stratum}_cut_{cut_edge[0]}_{cut_edge[1]}_s{seed}",
                        "topology": topo_name,
                        "topology_nodes": topo.node_count,
                        "topology_edges": topo.edge_count,
                        "eval_seed": seed,
                        "failed_edge": f"{cut_edge[0]}->{cut_edge[1]}",
                        "failure_stratum": stratum,
                        "routing_policy": "shortest_path_igp_reroute",
                        "model": model_name,
                        "model_hash": model_hash,
                        "git_sha": git_sha,
                        "mae": metrics["mae"],
                        "rmse": metrics["rmse"],
                        "r2": metrics["r2"],
                        "top3_recall": metrics["top3_recall"],
                        "top5pct_recall": metrics["top5pct_recall"],
                        "severe_fn_rate": metrics["severe_fn_rate"],
                        "t_encode_us": t_enc_us,
                        "t_inference_us": t_inf_us,
                        "t_decode_us": t_dec_us,
                        "t_online_total_us": t_total_us,
                        "t_oracle_us": t_oracle_us,
                        "mean_true_delta_u": float(np.mean(y_true)),
                        "max_true_delta_u": float(np.max(y_true)),
                    }
                    results.append(row)

    df = pd.DataFrame(results)
    df.to_csv("artifacts/direction_c_60_pilot_results.csv", index=False)
    with open("artifacts/direction_c_60_pilot_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\nSaved 60 evaluation records to artifacts/direction_c_60_pilot_results.csv.")
    return df


# --- Statistical Analysis ---


def analyze_pilot_results(df: pd.DataFrame):
    print("\n" + "=" * 80)
    print("DIRECTION-C 60-RUN PILOT STATISTICAL AUDIT & COMPARATIVE ANALYSIS")
    print("=" * 80)

    print(f"Total Observations: {len(df)} evaluations across 20 matched scenario blocks.")

    # 1. Primary Aggregate Metrics Table
    summary = (
        df.groupby("model")
        .agg(
            mean_mae=("mae", "mean"),
            std_mae=("mae", "std"),
            mean_rmse=("rmse", "mean"),
            mean_r2=("r2", "mean"),
            mean_top3=("top3_recall", "mean"),
            mean_top5pct=("top5pct_recall", "mean"),
            mean_severe_fn=("severe_fn_rate", "mean"),
            mean_online_us=("t_online_total_us", "mean"),
        )
        .reset_index()
    )

    print("\n[Overall Model Performance Summary across N=20 Matched Scenarios]")
    print("-" * 100)
    print(
        f"{'Model':<16} | {'MAE':<12} | {'RMSE':<12} | {'R² Score':<10} | {'Top-3 Rec':<10} | {'Top-5% Rec':<10} | {'Severe FN':<10} | {'Online Latency'}"
    )
    print("-" * 100)
    for _, r in summary.iterrows():
        print(
            f"{r['model']:<16} | {r['mean_mae']:.4f} ± {r['std_mae']:.4f} | {r['mean_rmse']:.4f}     | {r['mean_r2']:.4f}     | {r['mean_top3'] * 100:<9.1f}% | {r['mean_top5pct'] * 100:<9.1f}% | {r['mean_severe_fn'] * 100:<9.1f}% | {r['mean_online_us']:.1f} us"
        )
    print("-" * 100)

    # 2. Matched Paired Statistical Tests
    mlp_df = df[df["model"] == "Edge-Only MLP"].sort_values("scenario_id").reset_index(drop=True)
    gcn_df = df[df["model"] == "GCN"].sort_values("scenario_id").reset_index(drop=True)
    sage_df = df[df["model"] == "GraphSAGE"].sort_values("scenario_id").reset_index(drop=True)

    print("\n[Inferential Paired Statistical Tests (N=20 Matched Pairs)]")

    # GCN vs Edge MLP
    diff_mae_gcn = mlp_df["mae"].values - gcn_df["mae"].values  # Positive means GCN has lower error
    _stat_gcn, p_val_gcn = stats.wilcoxon(mlp_df["mae"], gcn_df["mae"], alternative="greater")
    dz_gcn = np.mean(diff_mae_gcn) / (np.std(diff_mae_gcn) + 1e-8)

    # SAGE vs Edge MLP
    diff_mae_sage = mlp_df["mae"].values - sage_df["mae"].values
    _stat_sage, p_val_sage = stats.wilcoxon(mlp_df["mae"], sage_df["mae"], alternative="greater")
    dz_sage = np.mean(diff_mae_sage) / (np.std(diff_mae_sage) + 1e-8)

    print(
        f"  * GCN vs. Edge-Only MLP:      MAE Reduction = {np.mean(diff_mae_gcn):+.4f} | Cohen's d_z = {dz_gcn:+.2f} | Wilcoxon p = {p_val_gcn:.4e}"
    )
    print(
        f"  * GraphSAGE vs. Edge-Only MLP: MAE Reduction = {np.mean(diff_mae_sage):+.4f} | Cohen's d_z = {dz_sage:+.2f} | Wilcoxon p = {p_val_sage:.4e}"
    )

    # 3. Breakdown by Stratum
    print("\n[Performance Breakdown by Failure Stratum (Mean R² and Top-3 Recall)]")
    stratum_summary = (
        df.groupby(["failure_stratum", "model"])
        .agg(
            r2=("r2", "mean"),
            top3=("top3_recall", "mean"),
            mae=("mae", "mean"),
        )
        .reset_index()
    )
    print(stratum_summary.to_string(index=False))

    # 4. Latency Accounting
    oracle_mean_us = df["t_oracle_us"].mean()
    gcn_online_us = gcn_df["t_online_total_us"].mean()
    sage_online_us = sage_df["t_online_total_us"].mean()

    print("\n[Computation Cost Accounting]")
    print(
        f"  * Exact Analytical Oracle Recomputation: {oracle_mean_us:.1f} us (Ground Truth Generation)"
    )
    print(
        f"  * GCN Online Surrogate Latency:          {gcn_online_us:.1f} us (Feature Encode: {gcn_df['t_encode_us'].mean():.1f}us | Forward: {gcn_df['t_inference_us'].mean():.1f}us | Decode: {gcn_df['t_decode_us'].mean():.1f}us)"
    )
    print(
        f"  * GraphSAGE Online Surrogate Latency:    {sage_online_us:.1f} us (Feature Encode: {sage_df['t_encode_us'].mean():.1f}us | Forward: {sage_df['t_inference_us'].mean():.1f}us | Decode: {sage_df['t_decode_us'].mean():.1f}us)"
    )
    print("=" * 80)


if __name__ == "__main__":
    df_results = run_60_pilot()
    analyze_pilot_results(df_results)
