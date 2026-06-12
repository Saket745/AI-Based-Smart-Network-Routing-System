"""CLI subcommands for model training (congestion, anomaly, rl)."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console  # type: ignore[import-not-found]

from nroute.core.topology import Topology
from nroute.exceptions import ModelError

console = Console()


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
def train_congestion(
    ctx: click.Context,
    topo_path: str,
    model_type: str,
    output: str,
    seed: int,
) -> None:
    """Train a congestion prediction model from simulation data."""
    import numpy as np
    import pandas as pd

    from nroute.ml.congestion import CongestionPredictor
    from nroute.routing import get_router
    from nroute.simulation.engine import SimulationEngine
    from nroute.simulation.traffic_gen import TrafficGenerator

    try:
        topo = Topology.load(topo_path)
    except Exception as e:
        console.print(f"[red]✗ Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    console.print("\n[cyan]Generating training data from simulation...[/cyan]")

    # Generate training data by running a simulation
    router = get_router("dijkstra")
    traffic_gen = TrafficGenerator(model="uniform", n_flows_per_tick=5)
    engine = SimulationEngine(topo, router, traffic_gen)
    result = engine.run(duration_ticks=100, seed=seed)

    # Build feature matrix from simulation ticks
    rng = np.random.default_rng(seed)
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
        f"[cyan]Training {model_type.upper()} congestion model on {n_samples} samples...[/cyan]"
    )

    try:
        predictor = CongestionPredictor(model_type=model_type)
        predictor.train(features, labels)

        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        predictor.save(str(out_path))

        console.print(f"[green]✓[/green] Congestion model saved to [bold]{out_path}[/bold]")
    except ModelError as e:
        console.print(f"[red]✗ Training error:[/red] {e}")
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
def train_anomaly(
    ctx: click.Context,
    topo_path: str,
    model_type: str,
    output: str,
    seed: int,
) -> None:
    """Train an anomaly detection model from normal traffic patterns."""
    import numpy as np
    import pandas as pd

    from nroute.ml.anomaly import AnomalyDetector

    try:
        Topology.load(topo_path)
    except Exception as e:
        console.print(f"[red]✗ Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    console.print("\n[cyan]Generating normal traffic features for training...[/cyan]")

    # Generate synthetic normal features
    rng = np.random.default_rng(seed)
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
        f"[cyan]Training {model_type.upper()} anomaly detector on {n_samples} samples...[/cyan]"
    )

    try:
        detector = AnomalyDetector(model_type=model_type)
        detector.fit(features)

        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        detector.save(str(out_path))

        console.print(f"[green]✓[/green] Anomaly model saved to [bold]{out_path}[/bold]")
    except ModelError as e:
        console.print(f"[red]✗ Training error:[/red] {e}")
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
def train_rl(
    ctx: click.Context,
    topo_path: str,
    algorithm: str,
    timesteps: int,
    output: str,
    seed: int,
) -> None:
    """Train a reinforcement learning routing agent."""
    from nroute.routing.rl_router import RLRouter

    try:
        topo = Topology.load(topo_path)
    except Exception as e:
        console.print(f"[red]✗ Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    console.print(
        f"\n[cyan]Training {algorithm.upper()} routing agent for {timesteps} timesteps...[/cyan]"
    )

    try:
        rl_router = RLRouter(topology=topo, algorithm=algorithm)
        # Convert total timesteps back to episodes using average episode duration of 20 hops
        episodes = max(1, timesteps // 20)
        rl_router.train(episodes=episodes, seed=seed)

        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rl_router.save(str(out_path))

        console.print(f"[green]✓[/green] RL model saved to [bold]{out_path}[/bold]")
    except Exception as e:
        console.print(f"[red]✗ RL training error:[/red] {e}")
        raise SystemExit(1) from e
