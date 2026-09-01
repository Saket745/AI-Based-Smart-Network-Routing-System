"""Phase-2 GNN Model Training, Validation & Checkpoint Freezing Script.

Trains GCNModel and GraphSAGEModel on strictly disjoint synthetic topology families
(Watts-Strogatz N=30, Erdos-Renyi N=40, Barabasi-Albert N=45) with training seeds [1001, 1002, 1003].
Validates on disjoint validation partition (Seeds 501, 502).
Saves frozen model checkpoints to models/gnn/ and computes SHA-256 hashes.
Compares trained models against untrained/random baselines for learned-prediction sanity.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import f1_score, roc_auc_score

from nroute.core.generators import TopologyGenerator
from nroute.core.topology import Topology
from nroute.ml.features.extractor import DefaultGraphFeatureExtractor
from nroute.ml.models.gcn import GCNModel
from nroute.ml.models.graphsage import GraphSAGEModel


def get_file_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def generate_partition_data(
    topos: list[Topology],
    n_snapshots_per_topo: int = 50,
    seed: int = 1001,
) -> list[tuple[Any, torch.Tensor, torch.Tensor]]:
    """Generate graph feature bundles and congestion/latency ground-truth targets."""
    extractor = DefaultGraphFeatureExtractor(use_pytorch=True)
    rng = np.random.default_rng(seed)
    dataset = []

    for topo in topos:
        for _ in range(n_snapshots_per_topo):
            for u, v in topo.edges:
                util = float(rng.beta(0.5, 0.5))  # Bi-modal utilization in [0.0, 1.0]
                topo.update_edge(u, v, utilization=util)

            bundle = extractor.extract_features(topo)
            ef = bundle.edge_features
            # Ground truth: congested if utilization >= 0.70
            cong_target = torch.where(ef[:, 2] >= 0.70, torch.tensor(1.0), torch.tensor(0.0))
            lat_target = ef[:, 1] * 100.0 * (1.0 + 5.0 * ef[:, 2])
            dataset.append((bundle, cong_target, lat_target))

    return dataset


def evaluate_dataset(
    model: nn.Module,
    dataset: list[tuple[Any, torch.Tensor, torch.Tensor]],
) -> dict[str, float]:
    """Evaluate model on a dataset partition and return BCE loss, MSE loss, ROC-AUC, and F1."""
    model.eval()
    bce_fn = nn.BCEWithLogitsLoss()
    mse_fn = nn.MSELoss()

    all_preds = []
    all_targets = []
    total_bce = 0.0
    total_mse = 0.0

    with torch.no_grad():
        for bundle, c_target, l_target in dataset:
            c_logits, l_pred = model(bundle.node_features, bundle.edge_index, bundle.edge_features)
            bce = bce_fn(c_logits, c_target).item()
            mse = mse_fn(l_pred, l_target).item()
            total_bce += bce
            total_mse += mse

            probs = torch.sigmoid(c_logits).cpu().numpy()
            all_preds.extend(probs)
            all_targets.extend(c_target.cpu().numpy())

    preds_arr = np.array(all_preds)
    targets_arr = np.array(all_targets)

    # Compute binary metrics
    roc_auc = (
        float(roc_auc_score(targets_arr, preds_arr)) if len(np.unique(targets_arr)) > 1 else 0.5
    )
    f1 = float(f1_score(targets_arr, (preds_arr >= 0.50).astype(int)))
    pos_rate = float(np.mean(preds_arr >= 0.50))

    return {
        "bce_loss": total_bce / len(dataset),
        "mse_loss": total_mse / len(dataset),
        "roc_auc": roc_auc,
        "f1": f1,
        "pred_pos_rate": pos_rate,
        "mean_prob": float(np.mean(preds_arr)),
        "std_prob": float(np.std(preds_arr)),
    }


def main():
    print("=" * 80)
    print("PHASE-2 GNN TRAINING PROVENANCE & SANITY GATE")
    print("=" * 80)

    output_dir = Path("models/gnn")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Construct Training & Validation Topology Partitions
    print("\n1. Generating Disjoint Synthetic Topology Partitions:")
    train_topos = [
        TopologyGenerator.small_world(n_nodes=30, k_neighbors=4, rewire_prob=0.1, seed=1001),
        TopologyGenerator.random(n_nodes=40, edge_prob=0.08, seed=1002),
        TopologyGenerator.scale_free(n_nodes=45, seed=1003),
    ]
    print(
        "   Training Partition (Seeds 1001, 1002, 1003): Small-World N=30, Random N=40, Scale-Free N=45"
    )

    val_topos = [
        TopologyGenerator.small_world(n_nodes=35, k_neighbors=4, rewire_prob=0.1, seed=501),
        TopologyGenerator.random(n_nodes=45, edge_prob=0.06, seed=502),
    ]
    print("   Validation Partition (Seeds 501, 502): Small-World N=35, Random N=45")

    train_data = generate_partition_data(train_topos, n_snapshots_per_topo=60, seed=1001)
    val_data = generate_partition_data(val_topos, n_snapshots_per_topo=30, seed=501)

    print(
        f"   Generated {len(train_data)} training snapshots and {len(val_data)} validation snapshots."
    )

    # 2. Instantiate Models
    torch.manual_seed(1001)
    gcn = GCNModel(node_in_dim=3, edge_in_dim=5, hidden_dim=64, num_layers=2)
    sage = GraphSAGEModel(node_in_dim=3, edge_in_dim=5, hidden_dim=64, num_layers=2)

    # Untrained copies for learned-prediction sanity check
    torch.manual_seed(9999)
    gcn_untrained = GCNModel(node_in_dim=3, edge_in_dim=5, hidden_dim=64, num_layers=2)
    sage_untrained = GraphSAGEModel(node_in_dim=3, edge_in_dim=5, hidden_dim=64, num_layers=2)

    bce_loss = nn.BCEWithLogitsLoss()
    mse_loss = nn.MSELoss()

    opt_gcn = optim.Adam(gcn.parameters(), lr=0.005, weight_decay=1e-4)
    opt_sage = optim.Adam(sage.parameters(), lr=0.005, weight_decay=1e-4)

    epochs = 30
    print(f"\n2. Training GCNModel and GraphSAGEModel for {epochs} epochs...")

    for epoch in range(1, epochs + 1):
        gcn.train()
        sage.train()
        gcn_epoch_loss = 0.0
        sage_epoch_loss = 0.0

        for bundle, c_target, l_target in train_data:
            # Train GCN
            opt_gcn.zero_grad()
            c_log_g, l_pred_g = gcn(bundle.node_features, bundle.edge_index, bundle.edge_features)
            loss_g = bce_loss(c_log_g, c_target) + 0.01 * mse_loss(l_pred_g, l_target)
            loss_g.backward()
            opt_gcn.step()
            gcn_epoch_loss += loss_g.item()

            # Train SAGE
            opt_sage.zero_grad()
            c_log_s, l_pred_s = sage(bundle.node_features, bundle.edge_index, bundle.edge_features)
            loss_s = bce_loss(c_log_s, c_target) + 0.01 * mse_loss(l_pred_s, l_target)
            loss_s.backward()
            opt_sage.step()
            sage_epoch_loss += loss_s.item()

        if epoch % 10 == 0 or epoch == epochs:
            gcn_val_metrics = evaluate_dataset(gcn, val_data)
            sage_val_metrics = evaluate_dataset(sage, val_data)
            print(
                f"   Epoch {epoch:02d}/{epochs} | "
                f"GCN TrainLoss: {gcn_epoch_loss / len(train_data):.4f}, ValROC: {gcn_val_metrics['roc_auc']:.4f}, ValF1: {gcn_val_metrics['f1']:.4f} | "
                f"SAGE TrainLoss: {sage_epoch_loss / len(train_data):.4f}, ValROC: {sage_val_metrics['roc_auc']:.4f}, ValF1: {sage_val_metrics['f1']:.4f}"
            )

    # 3. Save and Freeze Checkpoints
    gcn_path = output_dir / "gcn_model_frozen.pt"
    sage_path = output_dir / "graphsage_model_frozen.pt"

    torch.save(gcn.state_dict(), gcn_path)
    torch.save(sage.state_dict(), sage_path)

    gcn_hash = get_file_sha256(gcn_path)
    sage_hash = get_file_sha256(sage_path)

    print("\n3. Saved and Frozen Model Checkpoints:")
    print(f"   GCN Checkpoint:       {gcn_path} (SHA-256: {gcn_hash})")
    print(f"   GraphSAGE Checkpoint: {sage_path} (SHA-256: {sage_hash})")

    # 4. Learned-Prediction Sanity Check on Validation Partition
    print(
        "\n4. Learned-Prediction Sanity Check (Trained vs. Untrained Random Baseline on Validation Partition):"
    )
    gcn_trained_eval = evaluate_dataset(gcn, val_data)
    gcn_untrained_eval = evaluate_dataset(gcn_untrained, val_data)
    sage_trained_eval = evaluate_dataset(sage, val_data)
    sage_untrained_eval = evaluate_dataset(sage_untrained, val_data)

    print("\n[GCNModel Sanity]")
    print(
        f"  Trained GCN:   ROC-AUC = {gcn_trained_eval['roc_auc']:.4f} | F1 = {gcn_trained_eval['f1']:.4f} | BCE = {gcn_trained_eval['bce_loss']:.4f} | PosRate = {gcn_trained_eval['pred_pos_rate'] * 100:.1f}%"
    )
    print(
        f"  Untrained GCN: ROC-AUC = {gcn_untrained_eval['roc_auc']:.4f} | F1 = {gcn_untrained_eval['f1']:.4f} | BCE = {gcn_untrained_eval['bce_loss']:.4f} | PosRate = {gcn_untrained_eval['pred_pos_rate'] * 100:.1f}%"
    )

    print("\n[GraphSAGEModel Sanity]")
    print(
        f"  Trained SAGE:   ROC-AUC = {sage_trained_eval['roc_auc']:.4f} | F1 = {sage_trained_eval['f1']:.4f} | BCE = {sage_trained_eval['bce_loss']:.4f} | PosRate = {sage_trained_eval['pred_pos_rate'] * 100:.1f}%"
    )
    print(
        f"  Untrained SAGE: ROC-AUC = {sage_untrained_eval['roc_auc']:.4f} | F1 = {sage_untrained_eval['f1']:.4f} | BCE = {sage_untrained_eval['bce_loss']:.4f} | PosRate = {sage_untrained_eval['pred_pos_rate'] * 100:.1f}%"
    )

    # Save Provenance Manifest
    manifest = {
        "models": {
            "gcn_model": {
                "status": "trained_and_frozen",
                "checkpoint_path": str(gcn_path),
                "checkpoint_sha256": gcn_hash,
                "parameter_count": sum(p.numel() for p in gcn.parameters()),
                "training_seed_set": [1001, 1002, 1003],
                "validation_seed_set": [501, 502],
                "training_epochs": epochs,
                "val_roc_auc": gcn_trained_eval["roc_auc"],
                "val_f1": gcn_trained_eval["f1"],
                "untrained_val_roc_auc": gcn_untrained_eval["roc_auc"],
            },
            "graphsage_model": {
                "status": "trained_and_frozen",
                "checkpoint_path": str(sage_path),
                "checkpoint_sha256": sage_hash,
                "parameter_count": sum(p.numel() for p in sage.parameters()),
                "training_seed_set": [1001, 1002, 1003],
                "validation_seed_set": [501, 502],
                "training_epochs": epochs,
                "val_roc_auc": sage_trained_eval["roc_auc"],
                "val_f1": sage_trained_eval["f1"],
                "untrained_val_roc_auc": sage_untrained_eval["roc_auc"],
            },
        }
    }
    manifest_path = Path("artifacts/gnn_training_provenance.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nSaved training provenance manifest to {manifest_path}.")
    print("=" * 80)


if __name__ == "__main__":
    main()
