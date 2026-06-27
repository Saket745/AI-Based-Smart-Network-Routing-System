"""GNN trainer implementation for multi-task link predictions."""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING, Any

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from pydantic import BaseModel, Field
from torch.utils.data import DataLoader, Dataset

from nroute.core.topology import Topology
from nroute.ml.datasets.generator import DatasetGenerator
from nroute.ml.model_store import ModelStore
from nroute.ml.models.gcn import GCNModel
from nroute.ml.models.graphsage import GraphSAGEModel

if TYPE_CHECKING:
    from pandas import DataFrame


class GNNTrainingConfig(BaseModel):
    """Configuration for GNN training."""

    topo_path: str = Field(..., description="Path to topology JSON file")
    model_type: str = Field(default="gcn", description="gcn | graphsage")
    epochs: int = Field(default=10, description="Number of training epochs")
    lr: float = Field(default=0.01, description="Learning rate")
    hidden_dim: int = Field(default=32, description="Hidden dimension size")
    seed: int = Field(default=42, description="Random seed")
    batch_size: int = Field(default=4, description="Batch size for training")
    dataset_dir: str = Field(default="data/gnn_dataset", description="Directory for datasets")
    output_dir: str = Field(default="models/gnn", description="Directory for saved model")


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

    def __init__(self, model: nn.Module, lr: float = 0.005, weight_decay: float = 1e-4) -> None:
        self.model = model
        self.optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
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

    @staticmethod
    def run_training_workflow(
        config: GNNTrainingConfig, logger_callback: Any | None = None
    ) -> str:
        """
        Orchestrate the full GNN training workflow:
        1. Load Topology
        2. Generate Dataset
        3. Prepare DataLoaders
        4. Initialize Model
        5. Train and Evaluate
        6. Save Model
        """

        def log(msg: str) -> None:
            if logger_callback:
                logger_callback(msg)

        # 1. Load Topology
        topo = Topology.load(config.topo_path)

        # 2. Generate Dataset
        log("Collecting simulation traces and compiling to Parquet...")
        if os.path.exists(config.dataset_dir):
            shutil.rmtree(config.dataset_dir, ignore_errors=True)

        generator = DatasetGenerator(
            topology=topo,
            router_alg="dijkstra",
            traffic_model="uniform",
            duration_ticks=50,
            flows_per_tick=5,
            seed=config.seed,
        )

        snapshots = generator.generate_snapshots()
        generator.compile_to_parquet(snapshots, config.dataset_dir)
        log(f"Datasets saved in {config.dataset_dir}")

        node_df, edge_df, _ = DatasetGenerator.load_parquet_dataset(config.dataset_dir)
        ticks = sorted(node_df["tick"].unique())
        split_idx = int(len(ticks) * 0.8)
        train_ticks = ticks[:split_idx]
        val_ticks = ticks[split_idx:]

        train_node_df = node_df[node_df["tick"].isin(train_ticks)]
        train_edge_df = edge_df[edge_df["tick"].isin(train_ticks)]
        val_node_df = node_df[node_df["tick"].isin(val_ticks)]
        val_edge_df = edge_df[edge_df["tick"].isin(val_ticks)]

        train_dataset = GNNGraphDataset(train_node_df, train_edge_df)
        val_dataset = GNNGraphDataset(val_node_df, val_edge_df)

        train_loader = DataLoader(
            train_dataset,
            batch_size=config.batch_size,
            shuffle=True,
            collate_fn=collate_dataset_batch,
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=config.batch_size,
            shuffle=False,
            collate_fn=collate_dataset_batch,
        )

        # 3. Initialize Model
        node_in_dim = 8
        edge_in_dim = 6

        model: nn.Module
        if config.model_type.lower() == "gcn":
            model = GCNModel(
                node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=config.hidden_dim
            )
        else:
            model = GraphSAGEModel(
                node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=config.hidden_dim
            )

        # 4. Train
        log(f"Training GNN model ({config.model_type.upper()})...")
        trainer = GNNTrainer(model=model, lr=config.lr)

        for epoch in range(1, config.epochs + 1):
            train_metrics = trainer.train_epoch(train_loader)
            val_metrics = trainer.evaluate(val_loader)
            log(
                f"  Epoch {epoch:02d}/{config.epochs:02d} | "
                f"Loss: {train_metrics['loss']:.4f} (Cls: {train_metrics['cls_loss']:.4f}, Reg: {train_metrics['reg_loss']:.4f}) | "
                f"Val Loss: {val_metrics['val_loss']:.4f}"
            )

        # 5. Save
        model_store = ModelStore(base_dir=config.output_dir)
        saved_path = model_store.save_model(model, name=config.model_type.lower(), version="1.0.0")
        return saved_path
