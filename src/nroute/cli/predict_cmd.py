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
def congestion(topo_path: str, model_path: str, threshold: float) -> None:
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
        predictor.load(model_path)
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
