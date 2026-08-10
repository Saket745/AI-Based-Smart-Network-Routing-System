"""CLI subcommands for congestion prediction."""

from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from nroute.core.topology import Topology
from nroute.exceptions import ModelError

console = Console()


@click.group(name="predict")
def predict_cmd() -> None:
    """Run ML predictions on network data."""


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
        import json

        click.echo(json.dumps({"error": msg}), err=True)
    else:
        console.print(f"[red]x {msg}[/red]")

    if e:
        raise SystemExit(1) from e
    raise SystemExit(1)


def _load_topology(topo_path: str, is_json: bool) -> Topology:
    """Load and return a Topology object."""
    try:
        return Topology.load(topo_path)
    except Exception as e:
        _handle_error(f"Failed to load topology: {e}", is_json, e)
        # Unreachable but for mypy
        raise SystemExit(1) from e


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
    args = CongestionPredictArgs(**kwargs)
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"

    topo = _load_topology(args.topo_path, is_json)

    from nroute.ml.congestion import CongestionPredictor

    try:
        predictor = CongestionPredictor()
        predictor.load(args.model_path, allow_unsafe=args.allow_unsafe)
    except ModelError as e:
        _handle_error(f"Failed to load model: {e}", is_json, e)

    # Extract current link features
    edge_ids, features = _extract_congestion_features(topo)

    if not edge_ids:
        console.print("[yellow]No edges found in topology.[/yellow]")
        return

    try:
        predictions = predictor.predict(features)
    except Exception as e:
        _handle_error(f"Prediction failed: {e}", is_json, e)

    import pandas as pd

    if isinstance(predictions, pd.DataFrame):
        probs = predictions["probability"].tolist()
    else:
        probs = predictions if hasattr(predictions, "__iter__") else [predictions]

    if is_json:
        _print_congestion_json(edge_ids, probs, args.threshold)
    else:
        _print_congestion_console(edge_ids, probs, args.threshold)


def _extract_congestion_features(topo: Topology) -> tuple[list[str], Any]:
    """Extract current link features from topology for congestion prediction."""
    import pandas as pd

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
        return [], None

    return edge_ids, pd.DataFrame(rows)


def _print_congestion_json(edge_ids: list[str], probs: list[Any], threshold: float) -> None:
    """Output congestion predictions in JSON format."""
    import json

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


def _print_congestion_console(edge_ids: list[str], probs: list[Any], threshold: float) -> None:
    """Output congestion predictions as a table to the console."""
    console.print()
    console.rule("[bold cyan]Congestion Predictions[/bold cyan]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Link", style="cyan")
    table.add_column("Probability", justify="right")
    table.add_column("Status", justify="center")

    for edge_id, prob in zip(edge_ids, probs, strict=True):
        p = float(prob) if not isinstance(prob, (int, float)) else prob
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
    help="Allow loading of unsafe models (joblib/pickle).",
)
@click.pass_context
def predict_gnn(ctx: click.Context, /, **kwargs: Any) -> None:
    """Predict link congestion and latency using trained GNN models."""
    args = GNNPredictArgs(**kwargs)
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"

    topo = _load_topology(args.topo_path, is_json)

    # 1. Instantiate the GNN model structure
    model = _init_gnn_model(args.model_type)

    # 2. Load model state via ModelStore
    _load_gnn_model_state(model, args, is_json)

    # 3. Build graph representation & features
    bundle = _build_gnn_features(topo, is_json)

    # 4. Perform model prediction
    probs, predicted_latencies = _run_gnn_inference(model, bundle)

    if is_json:
        _print_gnn_json(topo, probs, predicted_latencies, args)
    else:
        _print_gnn_console(topo, probs, predicted_latencies, args)


def _init_gnn_model(model_type: str) -> Any:
    """Initialize GNN model structure."""
    from nroute.ml.models.gcn import GCNModel
    from nroute.ml.models.graphsage import GraphSAGEModel

    node_in_dim = 8
    edge_in_dim = 6
    hidden_dim = 32

    if model_type.lower() == "gcn":
        return GCNModel(node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=hidden_dim)
    return GraphSAGEModel(node_in_dim=node_in_dim, edge_in_dim=edge_in_dim, hidden_dim=hidden_dim)


def _load_gnn_model_state(model: Any, args: GNNPredictArgs, is_json: bool) -> None:
    """Load model state from disk."""
    from nroute.ml.model_store import ModelStore

    try:
        store = ModelStore(base_dir=args.model_dir)
        store.load_model(
            model,
            name=args.model_type.lower(),
            version=args.version,
            allow_unsafe=args.allow_unsafe,
        )
    except Exception as e:
        msg = f"Failed to load model {args.model_type} (version {args.version}): {e}"
        _handle_error(msg, is_json, e)


def _build_gnn_features(topo: Topology, is_json: bool) -> Any:
    """Extract features from topology and convert to tensors."""
    from nroute.ml.features.builder import FeatureBuilder

    try:
        builder = FeatureBuilder()
        return builder.build_features(topo).to_tensors()
    except Exception as e:
        _handle_error(f"Feature engineering failed: {e}", is_json, e)


def _run_gnn_inference(model: Any, bundle: Any) -> tuple[list[float], list[float]]:
    """Run model inference and return probabilities and latencies."""
    import torch

    model.eval()
    with torch.no_grad():
        logits, pred_lat = model(bundle.node_features, bundle.edge_index, bundle.edge_features)

    probs = torch.sigmoid(logits).tolist()
    predicted_latencies = pred_lat.tolist()
    return probs, predicted_latencies


def _print_gnn_json(
    topo: Topology,
    probs: list[float],
    predicted_latencies: list[float],
    args: GNNPredictArgs,
) -> None:
    """Output GNN predictions in JSON format."""
    import json

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
                if prob >= args.threshold
                else ("AT RISK" if prob >= args.threshold * 0.7 else "NORMAL"),
            }
        )
    out = {
        "model_type": args.model_type,
        "version": args.version,
        "threshold": args.threshold,
        "congested_count": sum(1 for p in probs if p >= args.threshold),
        "links": links_out,
    }
    click.echo(json.dumps(out, indent=2))


def _print_gnn_console(
    topo: Topology,
    probs: list[float],
    predicted_latencies: list[float],
    args: GNNPredictArgs,
) -> None:
    """Output GNN predictions as a table to the console."""
    console.print()
    console.rule(f"[bold cyan]GNN ({args.model_type.upper()}) Predictions[/bold cyan]")

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

        if prob >= args.threshold:
            prob_style = "bold red"
            status = "[bold red]CONGESTED[/bold red]"
            congested_count += 1
        elif prob >= args.threshold * 0.7:
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
        f"(threshold: {args.threshold})\n"
    )
