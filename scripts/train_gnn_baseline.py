import os
import shutil
import sys

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import torch
from torch.utils.data import DataLoader

from nroute.core.topology import Topology
from nroute.ml.datasets.generator import DatasetGenerator
from nroute.ml.evaluation.metrics import GNNEvaluator
from nroute.ml.model_store import ModelStore
from nroute.ml.models.gcn import GCNModel
from nroute.ml.models.graphsage import GraphSAGEModel
from nroute.ml.training.trainer import GNNGraphDataset, GNNTrainer, collate_dataset_batch


def main():
    print("=== Phase 2 GNN Baseline Training & Evaluation E2E Script ===")

    # 1. Load topology
    topo_path = "data/sample_topology.json"
    if not os.path.exists(topo_path):
        print(
            f"[ERROR] Sample topology not found at {topo_path}. Make sure to run from project root."
        )
        sys.exit(1)

    topo = Topology.load(topo_path)
    print(f"Loaded topology: {topo.node_count} nodes, {topo.edge_count} edges")

    # 2. Run simulation dataset collection
    output_dir = "data/gnn_dataset"
    print(
        f"\n[1/5] Collecting simulation snapshots and compiling to Parquet dataset in '{output_dir}'..."
    )
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)

    # Use 50 ticks, 5 flows per tick for a quick training demo
    generator = DatasetGenerator(
        topology=topo,
        router_alg="dijkstra",
        traffic_model="uniform",
        duration_ticks=50,
        flows_per_tick=5,
        seed=42,
    )

    print("Running simulation engine...")
    snapshots = generator.generate_snapshots()
    print(f"Generated {len(snapshots)} snapshots.")

    print("Compiling to Parquet...")
    generator.compile_to_parquet(snapshots, output_dir)
    print("Parquet compilation complete.")

    # 3. Load Parquet datasets and split into Train/Val sets
    print("\n[2/5] Loading datasets and splitting into train/validation sets...")
    node_df, edge_df, _global_df = DatasetGenerator.load_parquet_dataset(output_dir)

    ticks = sorted(node_df["tick"].unique())
    split_idx = int(len(ticks) * 0.8)
    train_ticks = ticks[:split_idx]
    val_ticks = ticks[split_idx:]

    print(
        f"Total ticks: {len(ticks)} | Train: {len(train_ticks)} ticks | Val: {len(val_ticks)} ticks"
    )

    train_node_df = node_df[node_df["tick"].isin(train_ticks)]
    train_edge_df = edge_df[edge_df["tick"].isin(train_ticks)]
    val_node_df = node_df[node_df["tick"].isin(val_ticks)]
    val_edge_df = edge_df[edge_df["tick"].isin(val_ticks)]

    train_dataset = GNNGraphDataset(train_node_df, train_edge_df)
    val_dataset = GNNGraphDataset(val_node_df, val_edge_df)

    train_loader = DataLoader(
        train_dataset, batch_size=4, shuffle=True, collate_fn=collate_dataset_batch
    )
    val_loader = DataLoader(
        val_dataset, batch_size=4, shuffle=False, collate_fn=collate_dataset_batch
    )

    # 4. Instantiate Models
    node_in_dim = 8  # [capacity, status, degree, queue_length, packet_load, congestion_score, btw_cent, cls_cent]
    edge_in_dim = (
        6  # [bandwidth, latency, utilization, packet_loss, reliability, failure_frequency]
    )
    hidden_dim = 32
    epochs = 10

    models_to_test = {
        "GCN": GCNModel(
            node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=hidden_dim, num_layers=2
        ),
        "GraphSAGE": GraphSAGEModel(
            node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=hidden_dim, num_layers=2
        ),
    }

    model_store = ModelStore(base_dir="models/gnn")

    for name, model in models_to_test.items():
        print(f"\n[3/5] Training baseline model: {name}...")
        trainer = GNNTrainer(model=model, lr=0.01)

        for epoch in range(1, epochs + 1):
            train_metrics = trainer.train_epoch(train_loader)
            val_metrics = trainer.evaluate(val_loader)
            print(
                f"  Epoch {epoch:02d}/{epochs:02d} | "
                f"Loss: {train_metrics['loss']:.4f} (Cls: {train_metrics['cls_loss']:.4f}, Reg: {train_metrics['reg_loss']:.4f}) | "
                f"Val Loss: {val_metrics['val_loss']:.4f}"
            )

        # 5. Evaluate and save
        print(f"\n[4/5] Evaluating {name} on the validation set...")
        model.eval()

        all_logits = []
        all_labels = []
        all_pred_lat = []
        all_latencies = []

        with torch.no_grad():
            for batch in val_loader:
                logits, pred_lat = model(
                    batch["node_features"], batch["edge_index"], batch["edge_features"]
                )
                all_logits.append(logits)
                all_labels.append(batch["congested_labels"])
                all_pred_lat.append(pred_lat)
                all_latencies.append(batch["latency_targets"])

        concat_logits = torch.cat(all_logits, dim=0) if all_logits else torch.empty((0,))
        concat_labels = torch.cat(all_labels, dim=0) if all_labels else torch.empty((0,))
        concat_pred_lat = torch.cat(all_pred_lat, dim=0) if all_pred_lat else torch.empty((0,))
        concat_latencies = torch.cat(all_latencies, dim=0) if all_latencies else torch.empty((0,))

        metrics = GNNEvaluator.evaluate_predictions(
            logits=concat_logits,
            labels=concat_labels,
            pred_lat=concat_pred_lat,
            latencies=concat_latencies,
        )

        print(f"=== Metrics for {name} ===")
        print("  Congestion Prediction (Classification):")
        print(f"    Accuracy:  {metrics['accuracy']:.4f}")
        print(f"    Precision: {metrics['precision']:.4f}")
        print(f"    Recall:    {metrics['recall']:.4f}")
        print(f"    F1 Score:  {metrics['f1_score']:.4f}")
        print("  Latency Prediction (Regression):")
        print(f"    MSE:       {metrics['mse']:.4f}")
        print(f"    MAE:       {metrics['mae']:.4f}")
        print(f"    Corr Coef: {metrics['pearson_corr']:.4f}")

        # 6. Save model using ModelStore
        print(f"\n[5/5] Saving {name} model checkpoint and metadata via ModelStore...")
        saved_path = model_store.save_model(model, name=name.lower(), version="1.0.0")
        print(f"Saved {name} to: {saved_path}")

        # Load back to verify
        print("Verifying checkpoint integrity by reloading...")
        reloaded_model = (
            GCNModel(node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=hidden_dim)
            if name == "GCN"
            else GraphSAGEModel(
                node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=hidden_dim
            )
        )
        model_store.load_model(reloaded_model, name=name.lower(), version="1.0.0")
        print(f"[SUCCESS] Integrity validation for {name} passed successfully!")

    print("\n=== E2E Training and Evaluation baseline verification completed successfully! ===")


if __name__ == "__main__":
    main()
