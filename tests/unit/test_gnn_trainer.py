"""Unit tests for GNN training dataset loading, collation, training, and metrics."""

from __future__ import annotations

import pandas as pd
import torch
from torch.utils.data import DataLoader

from nroute.ml.evaluation.metrics import GNNEvaluator
from nroute.ml.models.gcn import GCNModel
from nroute.ml.training.trainer import (
    GNNGraphDataset,
    GNNTrainer,
    collate_dataset_batch,
)


def test_gnn_trainer_flow() -> None:
    """Test training and validation loop using GNNTrainer and GNNGraphDataset."""
    # Build sample DataFrames
    node_records = [
        # Tick 0
        {
            "tick": 0,
            "node_id": "A",
            "capacity": 1.0,
            "status": 1.0,
            "degree": 0.5,
            "queue_length": 0.0,
            "packet_load": 0.0,
            "congestion_score": 0.0,
            "betweenness_centrality": 0.0,
            "closeness_centrality": 0.0,
        },
        {
            "tick": 0,
            "node_id": "B",
            "capacity": 1.0,
            "status": 1.0,
            "degree": 0.5,
            "queue_length": 0.0,
            "packet_load": 0.0,
            "congestion_score": 0.0,
            "betweenness_centrality": 0.0,
            "closeness_centrality": 0.0,
        },
        # Tick 1
        {
            "tick": 1,
            "node_id": "A",
            "capacity": 1.0,
            "status": 1.0,
            "degree": 0.5,
            "queue_length": 0.1,
            "packet_load": 0.1,
            "congestion_score": 0.1,
            "betweenness_centrality": 0.0,
            "closeness_centrality": 0.0,
        },
        {
            "tick": 1,
            "node_id": "B",
            "capacity": 1.0,
            "status": 1.0,
            "degree": 0.5,
            "queue_length": 0.1,
            "packet_load": 0.1,
            "congestion_score": 0.1,
            "betweenness_centrality": 0.0,
            "closeness_centrality": 0.0,
        },
    ]

    edge_records = [
        # Tick 0
        {
            "tick": 0,
            "source": "A",
            "destination": "B",
            "source_idx": 0,
            "destination_idx": 1,
            "bandwidth": 1.0,
            "latency": 0.05,
            "utilization": 0.1,
            "packet_loss": 0.0,
            "reliability": 1.0,
            "failure_frequency": 0.0,
            "congested_label": 0,
        },
        # Tick 1
        {
            "tick": 1,
            "source": "A",
            "destination": "B",
            "source_idx": 0,
            "destination_idx": 1,
            "bandwidth": 1.0,
            "latency": 0.05,
            "utilization": 0.9,
            "packet_loss": 0.0,
            "reliability": 1.0,
            "failure_frequency": 0.0,
            "congested_label": 1,
        },
    ]

    node_df = pd.DataFrame(node_records)
    edge_df = pd.DataFrame(edge_records)

    dataset = GNNGraphDataset(node_df, edge_df)
    assert len(dataset) == 2

    # Load via DataLoader with custom collation
    dataloader = DataLoader(
        dataset, batch_size=2, shuffle=False, collate_fn=collate_dataset_batch
    )

    # Initialize model and trainer
    model = GCNModel(node_in_dim=8, edge_in_dim=6, hidden_dim=16)
    trainer = GNNTrainer(model, lr=0.01)

    # Train epoch
    metrics = trainer.train_epoch(dataloader)
    assert "loss" in metrics
    assert "cls_loss" in metrics
    assert "reg_loss" in metrics
    assert metrics["loss"] > 0.0

    # Evaluate
    val_metrics = trainer.evaluate(dataloader)
    assert "val_loss" in val_metrics
    assert "val_cls_loss" in val_metrics
    assert "val_reg_loss" in val_metrics


def test_evaluator_metrics() -> None:
    """Test GNNEvaluator handles various output conditions correctly."""
    # 3 edges, perfect prediction
    logits = torch.tensor([5.0, -5.0, 5.0])
    labels = torch.tensor([1.0, 0.0, 1.0])
    pred_lat = torch.tensor([5.0, 10.0, 15.0])
    latencies = torch.tensor([5.0, 10.0, 15.0])

    metrics = GNNEvaluator.evaluate_predictions(logits, labels, pred_lat, latencies)
    assert metrics["accuracy"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert metrics["mse"] == 0.0
    assert metrics["mae"] == 0.0
    assert metrics["pearson_corr"] == 1.0

    # Test with empty tensors
    empty_t = torch.empty((0,))
    metrics_empty = GNNEvaluator.evaluate_predictions(
        empty_t, empty_t, empty_t, empty_t
    )
    assert metrics_empty["accuracy"] == 1.0
    assert metrics_empty["f1_score"] == 0.0
    assert metrics_empty["mse"] == 0.0
    assert metrics_empty["mae"] == 0.0
    assert metrics_empty["pearson_corr"] == 0.0
