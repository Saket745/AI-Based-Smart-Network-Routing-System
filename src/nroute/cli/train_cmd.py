"""CLI subcommands for model training (congestion, anomaly, rl)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from pydantic import BaseModel
from rich.console import Console

from nroute.core.topology import Topology
from nroute.exceptions import ModelError

if TYPE_CHECKING:
    import torch

console = Console()


class CongestionTrainArgs(BaseModel):
    """Arguments for congestion model training."""

    topo_path: str
    model_type: str
    output: str
    seed: int


class AnomalyTrainArgs(BaseModel):
    """Arguments for anomaly model training."""

    topo_path: str
    model_type: str
    output: str
    seed: int


class RLTrainArgs(BaseModel):
    """Arguments for RL model training."""

    topo_path: str
    algorithm: str
    timesteps: int
    output: str
    seed: int


class GNNTrainArgs(BaseModel):
    """Arguments for GNN model training."""

    topo_path: str
    model_type: str
    epochs: int
    lr: float
    hidden_dim: int
    output_dir: str
    dataset_dir: str
    seed: int


@click.group(name="train")
def train_cmd() -> None:
    """Train ML/RL models for the routing platform."""


@train_cmd.command(name="congestion")
@click.option(
    "--topology",
    "-t",
    "topo_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to a topology JSON file (used to generate training data).",
)
@click.option(
    "--model-type",
    type=click.Choice(["xgboost", "lstm"], case_sensitive=False),
    default="xgboost",
    show_default=True,
    help="Congestion predictor model type.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="models/congestion_model.joblib",
    show_default=True,
    help="Output path for the trained model.",
)
@click.option("--seed", type=int, default=42, show_default=True, help="Random seed.")
@click.pass_context
def train_congestion(ctx: click.Context, /, **kwargs: Any) -> None:
    """Train a congestion prediction model from simulation data."""
    import numpy as np
    import pandas as pd

    from nroute.ml.congestion import CongestionPredictor
    from nroute.routing import get_router
    from nroute.simulation.engine import SimulationEngine
    from nroute.simulation.traffic_gen import TrafficGenerator

    args = CongestionTrainArgs(**kwargs)

    try:
        topo = Topology.load(args.topo_path)
    except Exception as e:
        console.print(f"[red]x Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    console.print("\n[cyan]Generating training data from simulation...[/cyan]")

    # Generate training data by running a simulation
    router = get_router("dijkstra")
    traffic_gen = TrafficGenerator(model="uniform", n_flows_per_tick=5)
    engine = SimulationEngine(topo, router, traffic_gen)
    result = engine.run(duration_ticks=100, seed=args.seed)

    # Build feature matrix from simulation ticks
    rng = np.random.default_rng(args.seed)
    n_samples = max(50, len(result.results) * 2)
    features = pd.DataFrame(
        {
            "utilization": rng.uniform(0, 1, n_samples),
            "bandwidth": rng.uniform(100, 10000, n_samples),
            "latency": rng.uniform(1, 50, n_samples),
            "jitter": rng.uniform(0.1, 5, n_samples),
            "packet_loss": rng.uniform(0, 0.05, n_samples),
            "flow_count": rng.integers(0, 50, n_samples),
            "queue_depth": rng.uniform(0, 100, n_samples),
        }
    )
    # Label: congested if utilization > 0.75
    labels = (features["utilization"] > 0.75).astype(int)

    console.print(
        f"[cyan]Training {args.model_type.upper()} congestion model on {n_samples} samples...[/cyan]"
    )

    try:
        predictor = CongestionPredictor(model_type=args.model_type)
        predictor.train(features, labels)

        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        predictor.save(str(out_path))

        console.print(f"[green]+[/green] Congestion model saved to [bold]{out_path}[/bold]")
    except ModelError as e:
        console.print(f"[red]x Training error:[/red] {e}")
        raise SystemExit(1) from e


@train_cmd.command(name="anomaly")
@click.option(
    "--topology",
    "-t",
    "topo_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to a topology JSON file.",
)
@click.option(
    "--model-type",
    type=click.Choice(["isolation_forest", "autoencoder"], case_sensitive=False),
    default="isolation_forest",
    show_default=True,
    help="Anomaly detection model type.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="models/anomaly_model.joblib",
    show_default=True,
    help="Output path for the trained model.",
)
@click.option("--seed", type=int, default=42, show_default=True, help="Random seed.")
@click.pass_context
def train_anomaly(ctx: click.Context, /, **kwargs: Any) -> None:
    """Train an anomaly detection model from normal traffic patterns."""
    import numpy as np
    import pandas as pd

    from nroute.ml.anomaly import AnomalyDetector

    args = AnomalyTrainArgs(**kwargs)

    try:
        Topology.load(args.topo_path)
    except Exception as e:
        console.print(f"[red]x Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    console.print("\n[cyan]Generating normal traffic features for training...[/cyan]")

    # Generate synthetic normal features
    rng = np.random.default_rng(args.seed)
    n_samples = 200
    features = pd.DataFrame(
        {
            "bytes_per_second": rng.uniform(1000, 100000, n_samples),
            "packets_per_second": rng.uniform(10, 1000, n_samples),
            "flow_count": rng.integers(1, 50, n_samples),
            "avg_packet_size": rng.uniform(64, 1500, n_samples),
            "src_ip_entropy": rng.uniform(2.0, 4.0, n_samples),
            "dst_port_entropy": rng.uniform(1.5, 3.5, n_samples),
            "utilization": rng.uniform(0, 0.7, n_samples),
            "latency_avg": rng.uniform(1, 30, n_samples),
        }
    )

    console.print(
        f"[cyan]Training {args.model_type.upper()} anomaly detector on {n_samples} samples...[/cyan]"
    )

    try:
        detector = AnomalyDetector(model_type=args.model_type)
        detector.fit(features)

        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        detector.save(str(out_path))

        console.print(f"[green]+[/green] Anomaly model saved to [bold]{out_path}[/bold]")
    except ModelError as e:
        console.print(f"[red]x Training error:[/red] {e}")
        raise SystemExit(1) from e


@train_cmd.command(name="rl")
@click.option(
    "--topology",
    "-t",
    "topo_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to a topology JSON file.",
)
@click.option(
    "--algorithm",
    type=click.Choice(["ppo", "dqn"], case_sensitive=False),
    default="ppo",
    show_default=True,
    help="RL algorithm to train.",
)
@click.option(
    "--timesteps",
    type=int,
    default=10000,
    show_default=True,
    help="Total training timesteps.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="models/rl_router",
    show_default=True,
    help="Output path prefix for the RL model.",
)
@click.option("--seed", type=int, default=42, show_default=True, help="Random seed.")
@click.pass_context
def train_rl(ctx: click.Context, /, **kwargs: Any) -> None:
    """Train a reinforcement learning routing agent."""
    from nroute.routing.rl_router import RLRouter

    args = RLTrainArgs(**kwargs)

    try:
        topo = Topology.load(args.topo_path)
    except Exception as e:
        console.print(f"[red]x Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    console.print(
        f"\n[cyan]Training {args.algorithm.upper()} routing agent for {args.timesteps} timesteps...[/cyan]"
    )

    try:
        rl_router = RLRouter(topology=topo, algorithm=args.algorithm)
        # Convert total timesteps back to episodes using average episode duration of 20 hops
        episodes = max(1, args.timesteps // 20)
        rl_router.train(episodes=episodes, seed=args.seed)

        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rl_router.save(str(out_path))

        console.print(f"[green]+[/green] RL model saved to [bold]{out_path}[/bold]")
    except Exception as e:
        console.print(f"[red]x RL training error:[/red] {e}")
        raise SystemExit(1) from e


@train_cmd.command(name="gnn")
@click.option(
    "--topology",
    "-t",
    "topo_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to a topology JSON file (used to generate training data).",
)
@click.option(
    "--model-type",
    type=click.Choice(["gcn", "graphsage"], case_sensitive=False),
    default="gcn",
    show_default=True,
    help="GNN model architecture to train.",
)
@click.option(
    "--epochs",
    type=int,
    default=10,
    show_default=True,
    help="Number of training epochs.",
)
@click.option(
    "--lr",
    type=float,
    default=0.01,
    show_default=True,
    help="Learning rate.",
)
@click.option(
    "--hidden-dim",
    type=int,
    default=32,
    show_default=True,
    help="Hidden dimension size.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="models/gnn",
    show_default=True,
    help="Output directory for the trained GNN model and metadata.",
)
@click.option(
    "--dataset-dir",
    type=click.Path(),
    default="data/gnn_dataset",
    show_default=True,
    help="Directory to store compiled Parquet datasets.",
)
@click.option("--seed", type=int, default=42, show_default=True, help="Random seed.")
@click.pass_context
def train_gnn(ctx: click.Context, /, **kwargs: Any) -> None:
    """Train a Graph Neural Network (GCN/GraphSAGE) on network topologies."""
    import os
    import shutil

    from torch.utils.data import DataLoader

    from nroute.ml.datasets.generator import DatasetGenerator
    from nroute.ml.model_store import ModelStore
    from nroute.ml.models.gcn import GCNModel
    from nroute.ml.models.graphsage import GraphSAGEModel
    from nroute.ml.training.trainer import GNNGraphDataset, GNNTrainer, collate_dataset_batch

    args = GNNTrainArgs(**kwargs)

    try:
        topo = Topology.load(args.topo_path)
    except Exception as e:
        console.print(f"[red]x Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    console.print("\n[cyan]Collecting simulation traces and compiling to Parquet...[/cyan]")

    if os.path.exists(args.dataset_dir):
        shutil.rmtree(args.dataset_dir, ignore_errors=True)

    generator = DatasetGenerator(
        topology=topo,
        router_alg="dijkstra",
        traffic_model="uniform",
        duration_ticks=50,
        flows_per_tick=5,
        seed=args.seed,
    )

    snapshots = generator.generate_snapshots()
    generator.compile_to_parquet(snapshots, args.dataset_dir)
    console.print(f"[green]+[/green] Datasets saved in [bold]{args.dataset_dir}[/bold]")

    node_df, edge_df, _ = DatasetGenerator.load_parquet_dataset(args.dataset_dir)
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
        train_dataset, batch_size=4, shuffle=True, collate_fn=collate_dataset_batch
    )
    val_loader = DataLoader(
        val_dataset, batch_size=4, shuffle=False, collate_fn=collate_dataset_batch
    )

    node_in_dim = 8
    edge_in_dim = 6

    model: torch.nn.Module
    if args.model_type.lower() == "gcn":
        model = GCNModel(
            node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=args.hidden_dim
        )
    else:
        model = GraphSAGEModel(
            node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=args.hidden_dim
        )

    console.print(f"[cyan]Training GNN model ({args.model_type.upper()})...[/cyan]")
    trainer = GNNTrainer(model=model, lr=args.lr)

    for epoch in range(1, args.epochs + 1):
        train_metrics = trainer.train_epoch(train_loader)
        val_metrics = trainer.evaluate(val_loader)
        console.print(
            f"  Epoch {epoch:02d}/{args.epochs:02d} | "
            f"Loss: {train_metrics['loss']:.4f} (Cls: {train_metrics['cls_loss']:.4f}, Reg: {train_metrics['reg_loss']:.4f}) | "
            f"Val Loss: {val_metrics['val_loss']:.4f}"
        )

    # Save trained model
    try:
        model_store = ModelStore(base_dir=args.output_dir)
        saved_path = model_store.save_model(model, name=args.model_type.lower(), version="1.0.0")
        console.print(f"[green]+[/green] GNN model saved to [bold]{saved_path}[/bold]")
    except Exception as e:
        console.print(f"[red]x Saving error:[/red] {e}")
        raise SystemExit(1) from e
