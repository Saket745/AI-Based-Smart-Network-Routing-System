"""CLI subcommands for anomaly detection."""

from __future__ import annotations

import click
from rich.console import Console  # type: ignore[import-not-found]
from rich.table import Table  # type: ignore[import-not-found]

from nroute.exceptions import ModelError

console = Console()


@click.group(name="detect")
def detect_cmd() -> None:
    """Detect network traffic anomalies."""


@detect_cmd.command(name="anomalies")
@click.option(
    "--traffic",
    "-t",
    "traffic_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to a traffic features CSV file.",
)
@click.option(
    "--model",
    "-m",
    "model_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to a trained anomaly detection model.",
)
def anomalies(traffic_path: str, model_path: str) -> None:
    """Detect anomalies in network traffic data."""
    import pandas as pd

    from nroute.ml.anomaly import AnomalyDetector

    try:
        features = pd.read_csv(traffic_path)
    except Exception as e:
        console.print(f"[red]✗ Failed to load traffic data:[/red] {e}")
        raise SystemExit(1) from e

    try:
        detector = AnomalyDetector()
        detector.load(model_path)
    except ModelError as e:
        console.print(f"[red]✗ Failed to load model:[/red] {e}")
        raise SystemExit(1) from e

    try:
        results = detector.detect(features)
    except ModelError as e:
        console.print(f"[red]✗ Detection failed:[/red] {e}")
        raise SystemExit(1) from e

    # Display results
    console.print()
    console.rule("[bold cyan]Anomaly Detection Results[/bold cyan]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Sample", style="dim", justify="center")
    table.add_column("Score", justify="right")
    table.add_column("Anomaly?", justify="center")
    table.add_column("Type", style="cyan")

    anomaly_type_colors = {
        "DDoS": "bold red",
        "link_failure": "yellow",
        "black_hole": "magenta",
        "normal": "green",
    }

    for idx, row in results.iterrows():
        score = float(row["anomaly_score"])
        is_anom = bool(row["is_anomaly"])
        atype = str(row["anomaly_type"])

        score_style = "red" if score > 0.5 else "green"
        anom_icon = "🔴 YES" if is_anom else "🟢 NO"
        type_style = anomaly_type_colors.get(atype, "white")

        table.add_row(
            str(idx),
            f"[{score_style}]{score:.3f}[/{score_style}]",
            anom_icon,
            f"[{type_style}]{atype}[/{type_style}]",
        )

    console.print(table)

    # Summary
    total = len(results)
    anomalies_found = int(results["is_anomaly"].sum())
    console.print(f"\n  [bold]{anomalies_found}[/bold] anomalies detected out of {total} samples")

    # Breakdown by type
    if anomalies_found > 0:
        type_counts = results[results["is_anomaly"]]["anomaly_type"].value_counts()
        breakdown_table = Table(
            title="Anomaly Type Breakdown",
            show_header=True,
            header_style="bold magenta",
        )
        breakdown_table.add_column("Type", style="cyan")
        breakdown_table.add_column("Count", style="green", justify="right")

        for atype, count in type_counts.items():
            breakdown_table.add_row(str(atype), str(count))

        console.print(breakdown_table)

    console.print()
