"""GNN trainer implementation for multi-task link predictions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset

if TYPE_CHECKING:
    from pandas import DataFrame


class GNNGraphDataset(Dataset[dict[str, Any]]):
    """
    PyTorch Dataset loading graph snapshots from compiled Parquet DataFrames.
    """

    def __init__(self, node_df: DataFrame, edge_df: DataFrame) -> None:
        self.ticks = sorted(node_df["tick"].unique())
        self.node_df_grouped = {t: group for t, group in node_df.groupby("tick")}
        self.edge_df_grouped = {t: group for t, group in edge_df.groupby("tick")}

    def __len__(self) -> int:
        return len(self.ticks)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        tick = self.ticks[idx]
        ndf = self.node_df_grouped[tick].sort_values("node_id")
        edf = self.edge_df_grouped[tick].sort_values(["source", "destination"])

        # Node features: [capacity, status, degree, queue_length, packet_load, congestion_score, btw_cent, cls_cent]
        node_features = ndf[
            [
                "capacity",
                "status",
                "degree",
                "queue_length",
                "packet_load",
                "congestion_score",
                "betweenness_centrality",
                "closeness_centrality",
            ]
        ].values.astype(np.float32)

        # Edge index & features: [bandwidth, latency, utilization, packet_loss, reliability, failure_frequency]
        edge_index = edf[["source_idx", "destination_idx"]].values.astype(np.int64).T
        edge_features = edf[
            [
                "bandwidth",
                "latency",
                "utilization",
                "packet_loss",
                "reliability",
                "failure_frequency",
            ]
        ].values.astype(np.float32)

        # Targets
        congested_labels = edf["congested_label"].values.astype(np.float32)
        latency_targets = edf["latency"].values.astype(np.float32)

        return {
            "node_features": torch.from_numpy(node_features),
            "edge_index": torch.from_numpy(edge_index),
            "edge_features": torch.from_numpy(edge_features),
            "congested_labels": torch.from_numpy(congested_labels),
            "latency_targets": torch.from_numpy(latency_targets),
        }


def collate_dataset_batch(batch: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Collate function to combine multiple disjoint graph snapshots into a mini-batch.
    """
    node_features_list = []
    edge_index_list = []
    edge_features_list = []
    congested_labels_list = []
    latency_targets_list = []
    batch_idx_list = []

    cumulative_nodes = 0
    for idx, sample in enumerate(batch):
        n_feats = sample["node_features"]
        e_idx = sample["edge_index"]
        e_feats = sample["edge_features"]
        labels = sample["congested_labels"]
        latencies = sample["latency_targets"]

        num_nodes = n_feats.size(0)

        node_features_list.append(n_feats)
        edge_features_list.append(e_feats)
        congested_labels_list.append(labels)
        latency_targets_list.append(latencies)

        offset_e_idx = e_idx + cumulative_nodes
        edge_index_list.append(offset_e_idx)

        batch_idx_list.append(torch.full((num_nodes,), idx, dtype=torch.long))

        cumulative_nodes += num_nodes

    return {
        "node_features": torch.cat(node_features_list, dim=0),
        "edge_index": torch.cat(edge_index_list, dim=1),
        "edge_features": torch.cat(edge_features_list, dim=0),
        "congested_labels": torch.cat(congested_labels_list, dim=0),
        "latency_targets": torch.cat(latency_targets_list, dim=0),
        "batch": torch.cat(batch_idx_list, dim=0),
    }


class GNNTrainer:
    """Orchestrates the training process of multi-task GNN models."""

    def __init__(
        self, model: nn.Module, lr: float = 0.005, weight_decay: float = 1e-4
    ) -> None:
        self.model = model
        self.optimizer = optim.Adam(
            model.parameters(), lr=lr, weight_decay=weight_decay
        )
        self.criterion_cls = nn.BCEWithLogitsLoss()
        self.criterion_reg = nn.MSELoss()

    def train_epoch(self, dataloader: Any) -> dict[str, float]:
        """Train model for a single epoch."""
        self.model.train()
        total_loss = 0.0
        total_cls_loss = 0.0
        total_reg_loss = 0.0

        for batch in dataloader:
            self.optimizer.zero_grad()

            node_feats = batch["node_features"]
            edge_idx = batch["edge_index"]
            edge_feats = batch["edge_features"]
            labels = batch["congested_labels"]
            latencies = batch["latency_targets"]

            # Forward pass
            logits, pred_lat = self.model(node_feats, edge_idx, edge_feats)

            if logits.size(0) > 0:
                # Loss calculation
                loss_cls = self.criterion_cls(logits, labels)
                loss_reg = self.criterion_reg(pred_lat, latencies)
                loss = (
                    loss_cls + loss_reg * 10.0
                )  # Scale regression loss to match classification magnitude
            else:
                loss = torch.tensor(0.0, requires_grad=True)
                loss_cls = torch.tensor(0.0)
                loss_reg = torch.tensor(0.0)

            loss.backward()
            self.optimizer.step()

            total_loss += loss.item()
            total_cls_loss += loss_cls.item()
            total_reg_loss += loss_reg.item()

        num_batches = len(dataloader) if len(dataloader) > 0 else 1
        return {
            "loss": total_loss / num_batches,
            "cls_loss": total_cls_loss / num_batches,
            "reg_loss": total_reg_loss / num_batches,
        }

    def evaluate(self, dataloader: Any) -> dict[str, float]:
        """Evaluate model on validation/test set."""
        self.model.eval()
        total_loss = 0.0
        total_cls_loss = 0.0
        total_reg_loss = 0.0

        with torch.no_grad():
            for batch in dataloader:
                node_feats = batch["node_features"]
                edge_idx = batch["edge_index"]
                edge_feats = batch["edge_features"]
                labels = batch["congested_labels"]
                latencies = batch["latency_targets"]

                logits, pred_lat = self.model(node_feats, edge_idx, edge_feats)

                if logits.size(0) > 0:
                    loss_cls = self.criterion_cls(logits, labels)
                    loss_reg = self.criterion_reg(pred_lat, latencies)
                    loss = loss_cls + loss_reg * 10.0
                else:
                    loss = torch.tensor(0.0)
                    loss_cls = torch.tensor(0.0)
                    loss_reg = torch.tensor(0.0)

                total_loss += loss.item()
                total_cls_loss += loss_cls.item()
                total_reg_loss += loss_reg.item()

        num_batches = len(dataloader) if len(dataloader) > 0 else 1
        return {
            "val_loss": total_loss / num_batches,
            "val_cls_loss": total_cls_loss / num_batches,
            "val_reg_loss": total_reg_loss / num_batches,
        }
