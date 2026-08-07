"""CLI subcommands for congestion prediction."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import click
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from nroute.core.topology import Topology
from nroute.exceptions import ModelError

if TYPE_CHECKING:
    import torch

    from nroute.ml.congestion import CongestionPredictor

console = Console()


class CongestionPredictArgs(BaseModel):
    """Arguments for the congestion prediction command."""

    topo_path: str
    model_path: str
    threshold: float
    allow_unsafe: bool


class GNNPredictArgs(BaseModel):
    """Arguments for the GNN prediction command."""

    topo_path: str
    model_type: str
    model_dir: str
    version: str
    threshold: float
    allow_unsafe: bool


def _handle_error(msg: str, is_json: bool, e: Exception | None = None) -> None:
    """Helper to handle errors consistently based on output format."""
    if is_json:
        click.echo(json.dumps({"error": msg}), err=True)
    else:
        console.print(f"[red]x {msg}[/red]")

    if e:
        raise SystemExit(1) from e
    raise SystemExit(1)


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
    help="Allow loading of unsafe models (joblib/pickle).",
)
@click.pass_context
def congestion(ctx: click.Context, /, **kwargs: Any) -> None:
    """Predict per-link congestion probabilities."""
    import pandas as pd

    args = CongestionPredictArgs(**kwargs)
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"

    topo = _load_topology(args.topo_path, is_json)
    predictor = _load_predictor(args.model_path, args.allow_unsafe, is_json)

    # Extract current link features
    rows, edge_ids = _extract_link_features(topo)

    if not rows:
        if is_json:
            click.echo(json.dumps({"links": [], "threshold": args.threshold, "congested_count": 0}))
        else:
            console.print("[yellow]No edges found in topology.[/yellow]")
        return

    features = pd.DataFrame(rows)

    try:
        predictions = predictor.predict(features)
    except Exception as e:
        _handle_error(f"Prediction failed: {e}", is_json, e)

    if isinstance(predictions, pd.DataFrame):
        probs = [float(p) for p in predictions["probability"]]
    else:
        probs = [
            float(p) for p in (predictions if hasattr(predictions, "__iter__") else [predictions])
        ]

    if is_json:
        _print_congestion_json(edge_ids, probs, args.threshold)
    else:
        _print_congestion_console(edge_ids, probs, args.threshold)


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
    help="Allow loading of unsafe models (joblib/pickle).",
)
@click.pass_context
def predict_gnn(ctx: click.Context, /, **kwargs: Any) -> None:
    """Predict link congestion and latency using trained GNN models."""
    import torch

    from nroute.ml.features.builder import FeatureBuilder

    args = GNNPredictArgs(**kwargs)
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"

    topo = _load_topology(args.topo_path, is_json)

    # 1. Instantiate and load model
    model = _init_gnn_model(args.model_type, node_in_dim=8, edge_in_dim=6, hidden_dim=32)
    _load_gnn_state(
        model, args.model_dir, args.model_type, args.version, args.allow_unsafe, is_json
    )

    # 2. Build graph representation & features
    try:
        builder = FeatureBuilder()
        bundle = builder.build_features(topo).to_tensors()
    except Exception as e:
        _handle_error(f"Feature engineering failed: {e}", is_json, e)

    # 3. Perform model prediction
    model.eval()
    with torch.no_grad():
        logits, pred_lat = model(bundle.node_features, bundle.edge_index, bundle.edge_features)

    probs = torch.sigmoid(logits).tolist()
    predicted_latencies = pred_lat.tolist()

    if is_json:
        _print_gnn_json(
            topo, probs, predicted_latencies, args.threshold, args.model_type, args.version
        )
    else:
        _print_gnn_console(topo, probs, predicted_latencies, args.threshold, args.model_type)


def _load_topology(topo_path: str, is_json: bool) -> Topology:
    """Load topology and handle errors."""
    try:
        return Topology.load(topo_path)
    except Exception as e:
        _handle_error(f"Failed to load topology: {e}", is_json, e)
        raise  # Should not reach here due to SystemExit in _handle_error


def _load_predictor(model_path: str, allow_unsafe: bool, is_json: bool) -> CongestionPredictor:
    """Load congestion predictor and handle errors."""
    from nroute.ml.congestion import CongestionPredictor

    try:
        predictor = CongestionPredictor()
        predictor.load(model_path, allow_unsafe=allow_unsafe)
        return predictor
    except ModelError as e:
        _handle_error(f"Failed to load model: {e}", is_json, e)
        raise


def _extract_link_features(topo: Topology) -> tuple[list[dict[str, Any]], list[str]]:
    """Extract current link features from topology."""
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
    return rows, edge_ids


def _print_congestion_json(edge_ids: list[str], probs: list[float], threshold: float) -> None:
    """Output congestion predictions in JSON format."""
    out = {
        "links": [
            {
                "link": edge_id,
                "probability": float(prob),
                "status": "CONGESTED"
                if float(prob) >= threshold
                else ("AT RISK" if float(prob) >= threshold * 0.7 else "NORMAL"),
            }
            for edge_id, prob in zip(edge_ids, probs, strict=True)
        ],
        "threshold": threshold,
        "congested_count": sum(1 for p in probs if float(p) >= threshold),
    }
    click.echo(json.dumps(out, indent=2))


def _print_congestion_console(edge_ids: list[str], probs: list[float], threshold: float) -> None:
    """Output congestion predictions to console."""
    console.print()
    console.rule("[bold cyan]Congestion Predictions[/bold cyan]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Link", style="cyan")
    table.add_column("Probability", justify="right")
    table.add_column("Status", justify="center")

    for edge_id, prob in zip(edge_ids, probs, strict=True):
        p = float(prob)
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

    congested_count = sum(1 for p in probs if float(p) >= threshold)
    console.print(
        f"\n  [bold]{congested_count}[/bold] of {len(edge_ids)} links flagged as congested "
        f"(threshold: {threshold})\n"
    )


def _init_gnn_model(
    model_type: str, node_in_dim: int, edge_in_dim: int, hidden_dim: int
) -> torch.nn.Module:
    """Initialize GNN model based on type."""
    from nroute.ml.models.gcn import GCNModel
    from nroute.ml.models.graphsage import GraphSAGEModel

    if model_type.lower() == "gcn":
        return GCNModel(node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=hidden_dim)
    return GraphSAGEModel(node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=hidden_dim)


def _load_gnn_state(
    model: torch.nn.Module,
    model_dir: str,
    model_type: str,
    version: str,
    allow_unsafe: bool,
    is_json: bool,
) -> None:
    """Load GNN model state via ModelStore."""
    from nroute.ml.model_store import ModelStore

    try:
        store = ModelStore(base_dir=model_dir)
        store.load_model(model, name=model_type.lower(), version=version, allow_unsafe=allow_unsafe)
    except Exception as e:
        _handle_error(f"Failed to load model {model_type} (version {version}): {e}", is_json, e)


def _print_gnn_json(
    topo: Topology,
    probs: list[float],
    predicted_latencies: list[float],
    threshold: float,
    model_type: str,
    version: str,
) -> None:
    """Output GNN predictions in JSON format."""
    edges_sorted = sorted(topo.edges)
    links_out = []
    for idx, (u, v) in enumerate(edges_sorted):
        prob = probs[idx]
        pred_l = predicted_latencies[idx]
        edge = topo.get_edge(u, v)
        true_util = float(edge.get("utilization", 0.0))
        true_lat = float(edge.get("latency", 0.0))
        links_out.append(
            {
                "link": f"{u} -> {v}",
                "true_utilization": true_util,
                "true_latency": true_lat,
                "predicted_latency": pred_l * 100.0,
                "congestion_probability": prob,
                "status": "CONGESTED"
                if prob >= threshold
                else ("AT RISK" if prob >= threshold * 0.7 else "NORMAL"),
            }
        )
    out = {
        "model_type": model_type,
        "version": version,
        "threshold": threshold,
        "congested_count": sum(1 for p in probs if p >= threshold),
        "links": links_out,
    }
    click.echo(json.dumps(out, indent=2))


def _print_gnn_console(
    topo: Topology,
    probs: list[float],
    predicted_latencies: list[float],
    threshold: float,
    model_type: str,
) -> None:
    """Output GNN predictions to console."""
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
