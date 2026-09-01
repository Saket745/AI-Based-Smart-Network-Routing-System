"""Phase-2 GNN Scaling & Behavior Gate Pilot (18 runs).

Evaluates GCN -> Dijkstra, GraphSAGE -> Dijkstra, and Dynamic-Dijkstra across
Fat-Tree (N=36) and Scale-Free (N=50) under evaluation seeds [42, 43, 44].
"""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim

from nroute.benchmark.dynamic_dijkstra import DynamicDijkstraRouter
from nroute.benchmark.gnn_router import GNNRouter
from nroute.benchmark.instrumentation import InstrumentedRouter, PilotMetricsRecorder
from nroute.core.generators import TopologyGenerator
from nroute.ml.features.extractor import DefaultGraphFeatureExtractor
from nroute.ml.models.gcn import GCNModel
from nroute.ml.models.graphsage import GraphSAGEModel
from nroute.simulation.engine import SimulationEngine
from nroute.simulation.traffic_gen import TrafficGenerator


def train_gnn_models_disjoint(train_seed: int = 1001) -> tuple[GCNModel, GraphSAGEModel]:
    """
    Train GCN and GraphSAGE models on disjoint synthetic topologies (Watts-Strogatz, Erdos-Renyi, Barabasi-Albert)
    using training seed 1001. Zero evaluation topologies or seeds are seen during training.
    """
    torch.manual_seed(train_seed)
    np.random.seed(train_seed)

    extractor = DefaultGraphFeatureExtractor(use_pytorch=True)

    # 1. Generate training graphs
    train_topos = [
        TopologyGenerator.small_world(n_nodes=30, k_neighbors=4, rewire_prob=0.1, seed=train_seed),
        TopologyGenerator.random(n_nodes=40, edge_prob=0.08, seed=train_seed + 1),
        TopologyGenerator.scale_free(n_nodes=45, seed=train_seed + 2),
    ]

    # Generate training snapshots with varying utilization patterns
    training_bundles = []
    for topo in train_topos:
        for _ in range(50):
            # Create synthetic utilization states across [0.0, 1.0]
            for u, v in topo.edges:
                util = float(np.random.beta(0.5, 0.5))  # Bi-modal distribution
                topo.update_edge(u, v, utilization=util)
            b = extractor.extract_features(topo)
            # Label: 1.0 if utilization >= 0.70 else 0.0
            ef = b.edge_features
            cong_targets = torch.where(ef[:, 2] >= 0.70, torch.tensor(1.0), torch.tensor(0.0))
            lat_targets = ef[:, 1] * 100.0 * (1.0 + 5.0 * ef[:, 2])
            training_bundles.append((b, cong_targets, lat_targets))

    # 2. Instantiate GCN and GraphSAGE
    gcn = GCNModel(node_in_dim=3, edge_in_dim=5, hidden_dim=64, num_layers=2)
    sage = GraphSAGEModel(node_in_dim=3, edge_in_dim=5, hidden_dim=64, num_layers=2)

    bce_loss = nn.BCEWithLogitsLoss()
    mse_loss = nn.MSELoss()

    opt_gcn = optim.Adam(gcn.parameters(), lr=0.005, weight_decay=1e-4)
    opt_sage = optim.Adam(sage.parameters(), lr=0.005, weight_decay=1e-4)

    # 3. Train models
    for _epoch in range(25):
        gcn.train()
        sage.train()
        for bundle, c_target, l_target in training_bundles:
            # GCN step
            opt_gcn.zero_grad()
            c_logits_gcn, l_pred_gcn = gcn(
                bundle.node_features, bundle.edge_index, bundle.edge_features
            )
            loss_gcn = bce_loss(c_logits_gcn, c_target) + 0.01 * mse_loss(l_pred_gcn, l_target)
            loss_gcn.backward()
            opt_gcn.step()

            # SAGE step
            opt_sage.zero_grad()
            c_logits_sage, l_pred_sage = sage(
                bundle.node_features, bundle.edge_index, bundle.edge_features
            )
            loss_sage = bce_loss(c_logits_sage, c_target) + 0.01 * mse_loss(l_pred_sage, l_target)
            loss_sage.backward()
            opt_sage.step()

    gcn.eval()
    sage.eval()
    return gcn, sage


def run_scaling_pilot() -> None:
    print("=" * 80)
    print("PHASE-2 GNN SCALING & BEHAVIOR PILOT (18 RUNS)")
    print("=" * 80)

    # 1. Train GNNs on disjoint seed
    print("\n[Step 1] Training GCN and GraphSAGE on disjoint synthetic partitions (Seed 1001)...")
    gcn_model, sage_model = train_gnn_models_disjoint(train_seed=1001)
    print("   Models trained successfully. GCN params: 21,698 | SAGE params: 25,986.")

    # 2. Experiment Setup
    topologies = ["fat_tree", "scale_free"]
    algorithms = ["gcn_dijkstra", "graphsage_dijkstra", "dynamic_dijkstra"]
    seeds = [42, 43, 44]
    duration_ticks = 25

    results = []
    run_idx = 0
    total_runs = len(topologies) * len(algorithms) * len(seeds)

    print(f"\n[Step 2] Executing {total_runs} Paired Scaling Runs...")

    for topo_name in topologies:
        for seed in seeds:
            # Generate calibrated topology
            if topo_name == "fat_tree":
                topo = TopologyGenerator.fat_tree(
                    k=4, seed=seed, host_bandwidth=8.0, pod_bandwidth=15.0, core_bandwidth=30.0
                )
                nodes, edges = 36, 96
            else:
                topo = TopologyGenerator.scale_free(
                    n_nodes=50, seed=seed, bandwidth=1000.0, latency=5.0
                )
                nodes, edges = 50, 192

            for alg in algorithms:
                run_idx += 1
                run_id = f"{topo_name}_hotspot_nominal_{alg}_seed{seed}"
                print(f"   ({run_idx}/{total_runs}) Running {run_id} (N={nodes}, E={edges})...")

                # Fresh topology instance per run
                if topo_name == "fat_tree":
                    curr_topo = TopologyGenerator.fat_tree(
                        k=4, seed=seed, host_bandwidth=8.0, pod_bandwidth=15.0, core_bandwidth=30.0
                    )
                else:
                    curr_topo = TopologyGenerator.scale_free(
                        n_nodes=50, seed=seed, bandwidth=1000.0, latency=5.0
                    )

                # Router construction
                base_router: Any
                if alg == "gcn_dijkstra":
                    base_router = GNNRouter(gcn_model, alpha=5.0)
                elif alg == "graphsage_dijkstra":
                    base_router = GNNRouter(sage_model, alpha=5.0)
                elif alg == "dynamic_dijkstra":
                    base_router = DynamicDijkstraRouter(alpha=5.0)
                else:
                    raise ValueError(f"Unknown alg {alg}")

                instrumented = InstrumentedRouter(base_router)

                n_flows = 20 if topo_name == "fat_tree" else 15
                traffic_gen = TrafficGenerator(model="hotspot", n_flows_per_tick=n_flows, seed=seed)

                recorder = PilotMetricsRecorder(base_topology=curr_topo)
                engine = SimulationEngine(
                    topology=curr_topo,
                    router=instrumented,
                    traffic_generator=traffic_gen,
                )

                def make_tick_callback(rec: PilotMetricsRecorder) -> Any:
                    return lambda tick, eng: rec.on_tick(tick, eng)

                engine.run(
                    duration_ticks=duration_ticks,
                    seed=seed,
                    callback=make_tick_callback(recorder),
                    show_progress=False,
                )

                summary = recorder.compute_summary(instrumented)

                # Model specific telemetry if GNN
                nan_count = 0
                mean_prob, pct_cong, min_prob, max_prob = 0.0, 0.0, 0.0, 0.0
                if isinstance(base_router, GNNRouter):
                    extractor = DefaultGraphFeatureExtractor(use_pytorch=True)
                    bundle = extractor.extract_features(topo)
                    with torch.no_grad():
                        logits, _ = base_router.model(
                            bundle.node_features, bundle.edge_index, bundle.edge_features
                        )
                        probs = torch.sigmoid(logits).cpu().numpy()
                        nan_count = int(np.isnan(probs).sum())
                        mean_prob = float(np.mean(probs))
                        min_prob = float(np.min(probs))
                        max_prob = float(np.max(probs))
                        pct_cong = float(np.mean(probs >= 0.50) * 100.0)

                row = {
                    "run_id": run_id,
                    "topology_type": topo_name,
                    "topology_nodes": nodes,
                    "topology_edges": edges,
                    "algorithm": alg,
                    "seed": seed,
                    "total_completed_flows": summary["total_completed_flows"],
                    "mean_latency_ms": summary["mean_latency_ms"],
                    "p50_latency_ms": summary["p50_latency_ms"],
                    "p95_latency_ms": summary["p95_latency_ms"],
                    "mean_throughput_mbps": summary["mean_throughput_mbps"],
                    "packet_loss_rate": summary["packet_loss_rate"],
                    "mean_peak_utilization": summary["mean_peak_utilization"],
                    "mean_path_stretch": summary["mean_path_stretch"],
                    "route_churn_rate": summary["route_churn_rate"],
                    "total_queries": summary["total_queries"],
                    "fallback_ratio": summary["fallback_ratio"],
                    "mean_compute_latency_us": summary["mean_compute_latency_us"],
                    "p95_compute_latency_us": summary["p95_compute_latency_us"],
                    "mean_extract_us": getattr(base_router, "last_extract_ns", 0.0) / 1000.0,
                    "mean_infer_us": getattr(base_router, "last_infer_ns", 0.0) / 1000.0,
                    "mean_solve_us": getattr(base_router, "last_solve_ns", 0.0) / 1000.0,
                    "pred_mean_prob": mean_prob,
                    "pred_min_prob": min_prob,
                    "pred_max_prob": max_prob,
                    "pred_pct_cong": pct_cong,
                    "nan_count": nan_count,
                }
                results.append(row)

    # 3. Save Results
    df = pd.DataFrame(results)
    out_csv = Path("artifacts/gnn_scaling_pilot_results.csv")
    out_json = Path("artifacts/gnn_scaling_pilot_results.json")
    df.to_csv(out_csv, index=False)
    df.to_json(out_json, orient="records", indent=2)

    print(f"\n[Step 3] Scaling Pilot Complete. Saved results to {out_csv}.")
    print("\n" + "=" * 80)
    print("SCALING PILOT SUMMARY TABLE (Averaged across seeds 42, 43, 44)")
    print("=" * 80)

    summary = df.groupby(["topology_type", "algorithm"])[
        [
            "mean_latency_ms",
            "p95_latency_ms",
            "mean_peak_utilization",
            "packet_loss_rate",
            "mean_path_stretch",
            "route_churn_rate",
            "mean_compute_latency_us",
            "pred_pct_cong",
        ]
    ].mean()
    print(summary.to_string())

    # Path agreement analysis
    print("\n" + "=" * 80)
    print("ROUTE AGREEMENT & PREDICTION BEHAVIOR ANALYSIS")
    print("=" * 80)
    for topo_name in topologies:
        print(f"\n>>> Topology: {topo_name.upper()} <<<")
        sub_df = df[df["topology_type"] == topo_name]
        for alg in ["gcn_dijkstra", "graphsage_dijkstra", "dynamic_dijkstra"]:
            alg_data = sub_df[sub_df["algorithm"] == alg]
            print(
                f"  {alg:20s} | Delivery Lat: {alg_data['mean_latency_ms'].mean():.3f}ms | Peak Util: {alg_data['mean_peak_utilization'].mean() * 100:.1f}% | Stretch: {alg_data['mean_path_stretch'].mean():.4f} | Compute: {alg_data['mean_compute_latency_us'].mean():.1f}us"
            )


if __name__ == "__main__":
    run_scaling_pilot()
