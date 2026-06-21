"""CLI subcommands for congestion prediction."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from nroute.core.topology import Topology
from nroute.exceptions import ModelError

console = Console()


@click.group(name="predict")
def predict_cmd() -> None:
    """Run ML predictions on network data."""


@predict_cmd.command(name="congestion")
@click.option(
    "--topology",
    "-t",
    "topo_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to a topology JSON file.",
)
@click.option(
    "--model",
    "-m",
    "model_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to a trained congestion model.",
)
@click.option(
    "--threshold",
    type=float,
    default=0.75,
    show_default=True,
    help="Congestion probability threshold for flagging.",
)
@click.option(
    "--allow-unsafe",
    is_flag=True,
    default=False,
    help="Allow loading of legacy joblib/pickle models (Insecure).",
)
def congestion(topo_path: str, model_path: str, threshold: float, allow_unsafe: bool) -> None:
    """Predict per-link congestion probabilities."""
    import pandas as pd

    from nroute.ml.congestion import CongestionPredictor

    try:
        topo = Topology.load(topo_path)
    except Exception as e:
        console.print(f"[red]x Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    try:
        predictor = CongestionPredictor()
        predictor.load(model_path, allow_unsafe=allow_unsafe)
    except ModelError as e:
        console.print(f"[red]x Failed to load model:[/red] {e}")
        raise SystemExit(1) from e

    # Extract current link features
    rows = []
    edge_ids = []
    for u, v in topo.edges:
        edge = topo.get_edge(u, v)
        rows.append(
            {
                "utilization": float(edge.get("utilization", 0.0)),
                "bandwidth": float(edge.get("bandwidth", 1000.0)),
                "latency": float(edge.get("latency", 5.0)),
                "jitter": float(edge.get("jitter", 0.5)),
                "packet_loss": float(edge.get("packet_loss", 0.0)),
                "flow_count": 10,  # default placeholder
                "queue_depth": 0.0,  # default placeholder
            }
        )
        edge_ids.append(f"{u} -> {v}")

    if not rows:
        console.print("[yellow]No edges found in topology.[/yellow]")
        return

    features = pd.DataFrame(rows)

    try:
        predictions = predictor.predict(features)
    except Exception as e:
        console.print(f"[red]x Prediction failed:[/red] {e}")
        raise SystemExit(1) from e

    # Display results
    console.print()
    console.rule("[bold cyan]Congestion Predictions[/bold cyan]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Link", style="cyan")
    table.add_column("Probability", justify="right")
    table.add_column("Status", justify="center")

    if isinstance(predictions, pd.DataFrame):
        probs = predictions["probability"].tolist()
    else:
        probs = predictions if hasattr(predictions, "__iter__") else [predictions]

    for edge_id, prob in zip(edge_ids, probs, strict=True):
        p = float(prob) if not isinstance(prob, int | float) else prob
        if p >= threshold:
            prob_style = "bold red"
            status = "[bold red]CONGESTED[/bold red]"
        elif p >= threshold * 0.7:
            prob_style = "yellow"
            status = "[yellow]AT RISK[/yellow]"
        else:
            prob_style = "green"
            status = "[green]NORMAL[/green]"

        table.add_row(edge_id, f"[{prob_style}]{p:.3f}[/{prob_style}]", status)

    console.print(table)

    # Summary
    congested_count = sum(1 for p in probs if float(p) >= threshold)
    console.print(
        f"\n  [bold]{congested_count}[/bold] of {len(edge_ids)} links flagged as congested "
        f"(threshold: {threshold})\n"
    )


@predict_cmd.command(name="gnn")
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
    type=click.Choice(["gcn", "graphsage"], case_sensitive=False),
    default="gcn",
    show_default=True,
    help="GNN model type (gcn or graphsage).",
)
@click.option(
    "--model-dir",
    type=click.Path(exists=True),
    default="models/gnn",
    show_default=True,
    help="Directory where GNN models are stored.",
)
@click.option(
    "--version",
    default="1.0.0",
    show_default=True,
    help="Version of the model to load.",
)
@click.option(
    "--threshold",
    type=float,
    default=0.85,
    show_default=True,
    help="Congestion probability threshold for flagging.",
)
@click.option(
    "--allow-unsafe",
    is_flag=True,
    default=False,
    help="Allow loading of models with insecure weights (Insecure).",
)
def predict_gnn(
    topo_path: str,
    model_type: str,
    model_dir: str,
    version: str,
    threshold: float,
    allow_unsafe: bool,
) -> None:
    """Predict link congestion and latency using trained GNN models."""
    import torch

    from nroute.ml.features.builder import FeatureBuilder
    from nroute.ml.model_store import ModelStore
    from nroute.ml.models.gcn import GCNModel
    from nroute.ml.models.graphsage import GraphSAGEModel

    try:
        topo = Topology.load(topo_path)
    except Exception as e:
        console.print(f"[red]x Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    node_in_dim = 8
    edge_in_dim = 6
    hidden_dim = 32

    # 1. Instantiate the GNN model structure
    model: torch.nn.Module
    if model_type.lower() == "gcn":
        model = GCNModel(node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=hidden_dim)
    else:
        model = GraphSAGEModel(
            node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=hidden_dim
        )

    # 2. Load model state via ModelStore
    try:
        store = ModelStore(base_dir=model_dir)
        store.load_model(model, name=model_type.lower(), version=version, allow_unsafe=allow_unsafe)
    except Exception as e:
        console.print(f"[red]x Failed to load model {model_type} (version {version}):[/red] {e}")
        raise SystemExit(1) from e

    # 3. Build graph representation & features
    try:
        builder = FeatureBuilder()
        bundle = builder.build_features(topo).to_tensors()
    except Exception as e:
        console.print(f"[red]x Feature engineering failed:[/red] {e}")
        raise SystemExit(1) from e

    # 4. Perform model prediction
    model.eval()
    with torch.no_grad():
        logits, pred_lat = model(bundle.node_features, bundle.edge_index, bundle.edge_features)

    # Compute probabilities using sigmoid
    probs = torch.sigmoid(logits).tolist()
    predicted_latencies = pred_lat.tolist()

    # Display results
    console.print()
    console.rule(f"[bold cyan]GNN ({model_type.upper()}) Predictions[/bold cyan]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Link", style="cyan")
    table.add_column("True Util", justify="right")
    table.add_column("True Latency", justify="right")
    table.add_column("Pred Latency", justify="right")
    table.add_column("Congestion Prob", justify="right")
    table.add_column("Status", justify="center")

    edges_sorted = sorted(topo.edges)
    congested_count = 0

    for idx, (u, v) in enumerate(edges_sorted):
        prob = probs[idx]
        pred_l = predicted_latencies[idx]

        edge = topo.get_edge(u, v)
        true_util = float(edge.get("utilization", 0.0))
        true_lat = float(edge.get("latency", 0.0))

        if prob >= threshold:
            prob_style = "bold red"
            status = "[bold red]CONGESTED[/bold red]"
            congested_count += 1
        elif prob >= threshold * 0.7:
            prob_style = "yellow"
            status = "[yellow]AT RISK[/yellow]"
        else:
            prob_style = "green"
            status = "[green]NORMAL[/green]"

        table.add_row(
            f"{u} -> {v}",
            f"{true_util:.2f}",
            f"{true_lat:.1f}ms",
            f"{pred_l * 100.0:.1f}ms",
            f"[{prob_style}]{prob:.3f}[/{prob_style}]",
            status,
        )

    console.print(table)
    console.print(
        f"\n  [bold]{congested_count}[/bold] of {len(edges_sorted)} links predicted as congested "
        f"(threshold: {threshold})\n"
    )
