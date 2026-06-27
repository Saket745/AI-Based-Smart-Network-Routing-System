"""CLI command to export topologies or simulation metrics to various formats."""

from __future__ import annotations

import json
from pathlib import Path

import click

from nroute.core.metrics import MetricsCollectionResult
from nroute.core.topology import Topology
from nroute.visualization.exporters import MetricsExporter, TopologyExporter


@click.command(name="export")
@click.option(
    "--type",
    "-t",
    type=click.Choice(["topology", "metrics"]),
    required=True,
    help="Type of data to export.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "csv", "graphml"]),
    required=True,
    help="Target export format (graphml is only supported for topology).",
)
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
    help="Path to the input JSON file (source data).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(exists=False, file_okay=True, dir_okay=False),
    required=True,
    help="Path to write the exported file(s).",
)
def export_cmd(type: str, format: str, input: str, output: str) -> None:
    """Export network topology or simulation metrics to JSON, CSV, or GraphML."""
    input_path = Path(input)
    output_path = Path(output)

    if type == "topology":
        try:
            topo = Topology.from_json(input_path)
        except Exception as exc:
            raise click.ClickException(
                f"Failed to load topology from {input_path}: {exc}"
            ) from exc

        if format == "json":
            TopologyExporter.to_json(topo, output_path)
            click.echo(f"Successfully exported topology to JSON: {output_path}")
        elif format == "graphml":
            TopologyExporter.to_graphml(topo, output_path)
            click.echo(f"Successfully exported topology to GraphML: {output_path}")
        elif format == "csv":
            TopologyExporter.to_csv(topo, output_path)
            click.echo(
                f"Successfully exported topology to CSV files using base path: {output_path}"
            )

    elif type == "metrics":
        if format == "graphml":
            raise click.BadParameter(
                "GraphML format is not supported for simulation metrics."
            )

        try:
            with open(input_path, encoding="utf-8") as f:
                data = json.load(f)
            # Support both flat list of metrics or wrapped results
            if isinstance(data, dict) and "results" in data:
                metrics_col = MetricsCollectionResult.model_validate(data)
            elif isinstance(data, list):
                metrics_col = MetricsCollectionResult(results=data)
            else:
                raise click.ClickException(
                    "Input file does not contain valid simulation metrics format."
                )
        except Exception as exc:
            raise click.ClickException(
                f"Failed to load metrics from {input_path}: {exc}"
            ) from exc

        if format == "json":
            MetricsExporter.to_json(metrics_col, output_path)
            click.echo(f"Successfully exported metrics to JSON: {output_path}")
        elif format == "csv":
            MetricsExporter.to_csv(metrics_col, output_path)
            click.echo(f"Successfully exported metrics to CSV: {output_path}")
