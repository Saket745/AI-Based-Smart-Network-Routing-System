"""CLI subcommands for anomaly detection."""

from __future__ import annotations

from typing import Any

import click
from rich.console import Console
from rich.table import Table

from nroute.exceptions import ModelError

console = Console()


@click.group(name="detect")
def detect_cmd() -> None:
    """Detect network traffic anomalies."""


def _load_and_prepare_features(traffic_path: str, is_json: bool) -> Any:
    """Load traffic CSV and prepare feature matrix."""
    import json

    import pandas as pd

    try:
        raw_df = pd.read_csv(traffic_path)
    except Exception as e:
        if is_json:
            click.echo(json.dumps({"error": f"Failed to load traffic data: {e}"}), err=True)
            raise SystemExit(1) from e
        console.print(f"[red]x Failed to load traffic data:[/red] {e}")
        raise SystemExit(1) from e

    cols_lower = {str(c).lower().strip() for c in raw_df.columns}
    is_raw_traffic = (
        any(c in cols_lower for c in ("source", "src", "src_addr", "from"))
        and any(c in cols_lower for c in ("destination", "dst", "dst_addr", "to"))
        and any(c in cols_lower for c in ("bytes", "octets", "doctets"))
    )

    if is_raw_traffic:
        from nroute.ingestion.normalizer import Normalizer
        from nroute.ml.feature_eng import extract_anomaly_features

        try:
            tm = Normalizer.normalize_traffic(raw_df.to_dict(orient="records"))
            return extract_anomaly_features(tm)
        except Exception as e:
            if is_json:
                click.echo(
                    json.dumps({"error": f"Failed to extract anomaly features: {e}"}),
                    err=True,
                )
                raise SystemExit(1) from e
            console.print(f"[red]x Failed to extract anomaly features:[/red] {e}")
            raise SystemExit(1) from e

    return raw_df


def _run_anomaly_detection(
    features: Any, model_path: str, allow_unsafe: bool, is_json: bool
) -> Any:
    """Load detector model and run anomaly detection."""
    import json

    from nroute.ml.anomaly import AnomalyDetector

    try:
        detector = AnomalyDetector()
        detector.load(model_path, allow_unsafe=allow_unsafe)
    except ModelError as e:
        if is_json:
            click.echo(json.dumps({"error": f"Failed to load model: {e}"}), err=True)
            raise SystemExit(1) from e
        console.print(f"[red]x Failed to load model:[/red] {e}")
        raise SystemExit(1) from e

    try:
        return detector.detect(features)
    except ModelError as e:
        if is_json:
            click.echo(json.dumps({"error": f"Detection failed: {e}"}), err=True)
            raise SystemExit(1) from e
        console.print(f"[red]x Detection failed:[/red] {e}")
        raise SystemExit(1) from e


def _render_json_results(results: Any) -> None:
    """Format and print detection results as JSON."""
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


def _render_terminal_results(results: Any) -> None:
    """Render detection results as formatted terminal tables and summaries."""
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
        anom_icon = "🔴 [bold red]YES[/bold red]" if is_anom else "🟢 [green]NO[/green]"
        type_style = anomaly_type_colors.get(atype, "white")

        table.add_row(
            str(idx),
            f"[{score_style}]{score:.3f}[/{score_style}]",
            anom_icon,
            f"[{type_style}]{atype}[/{type_style}]",
        )

    console.print(table)

    total = len(results)
    anomalies_found = int(results["is_anomaly"].sum())
    console.print(f"\n  [bold]{anomalies_found}[/bold] anomalies detected out of {total} samples")

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
def anomalies(
    ctx: click.Context,
    traffic_path: str,
    model_path: str,
    allow_unsafe: bool,
) -> None:
    """Detect anomalies in network traffic data."""
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"

    features = _load_and_prepare_features(traffic_path, is_json)
    results = _run_anomaly_detection(features, model_path, allow_unsafe, is_json)

    if is_json:
        _render_json_results(results)
    else:
        _render_terminal_results(results)
