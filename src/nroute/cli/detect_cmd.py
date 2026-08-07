"""CLI subcommands for anomaly detection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import click
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from nroute.exceptions import ModelError

if TYPE_CHECKING:
    import pandas as pd

    from nroute.ml.anomaly import AnomalyDetector

console = Console()


@click.group(name="detect")
def detect_cmd() -> None:
    """Detect network traffic anomalies."""


class AnomalyDetectArgs(BaseModel):
    """Arguments for the anomalies detection command."""

    traffic_path: str
    model_path: str
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


def _load_traffic_data(traffic_path: str, is_json: bool) -> pd.DataFrame:
    """Load traffic features from CSV."""
    import pandas as pd

    try:
        return pd.read_csv(traffic_path)
    except Exception as e:
        _handle_error(f"Failed to load traffic data: {e}", is_json, e)
        # Unreachable but for mypy
        raise SystemExit(1) from e


def _init_detector(model_path: str, allow_unsafe: bool, is_json: bool) -> AnomalyDetector:
    """Initialize detector and load model."""
    from nroute.ml.anomaly import AnomalyDetector

    try:
        detector = AnomalyDetector()
        detector.load(model_path, allow_unsafe=allow_unsafe)
        return detector
    except ModelError as e:
        _handle_error(f"Failed to load model: {e}", is_json, e)
        # Unreachable but for mypy
        raise SystemExit(1) from e


def _run_detection(
    detector: AnomalyDetector, features: pd.DataFrame, is_json: bool
) -> pd.DataFrame:
    """Run anomaly detection on features."""
    try:
        return detector.detect(features)
    except ModelError as e:
        _handle_error(f"Detection failed: {e}", is_json, e)
        # Unreachable but for mypy
        raise SystemExit(1) from e


def _output_json_results(results: pd.DataFrame) -> None:
    """Format and output detection results in JSON."""
    import json

    samples = []
    for idx, row in results.iterrows():
        samples.append(
            {
                "sample_id": int(idx),
                "anomaly_score": float(row["anomaly_score"]),
                "is_anomaly": bool(row["is_anomaly"]),
                "anomaly_type": str(row["anomaly_type"]),
            }
        )

    type_counts = results[results["is_anomaly"]]["anomaly_type"].value_counts().to_dict()
    out = {
        "total_samples": len(results),
        "anomalies_detected": int(results["is_anomaly"].sum()),
        "anomaly_type_breakdown": {str(k): int(v) for k, v in type_counts.items()},
        "samples": samples,
    }
    click.echo(json.dumps(out, indent=2))


def _output_console_results(results: pd.DataFrame) -> None:
    """Format and output detection results to console with Rich."""
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
        anom_icon = "[bold red]YES[/bold red]" if is_anom else "[green]NO[/green]"
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
@click.option(
    "--allow-unsafe",
    is_flag=True,
    default=False,
    help="Allow loading of unsafe models (joblib/pickle).",
)
@click.pass_context
def anomalies(ctx: click.Context, /, **kwargs: Any) -> None:
    """Detect anomalies in network traffic data."""
    args = AnomalyDetectArgs(**kwargs)
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"

    features = _load_traffic_data(args.traffic_path, is_json)
    detector = _init_detector(args.model_path, args.allow_unsafe, is_json)
    results = _run_detection(detector, features, is_json)

    if is_json:
        _output_json_results(results)
    else:
        _output_console_results(results)
