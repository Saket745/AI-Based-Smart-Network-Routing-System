"""CLI commands for the Digital Twin Engine.

Adds the ``nroute twin`` command group with sub-commands:
  * ``nroute twin health``       — Show network health summary.
  * ``nroute twin impact``       — Simulate a change and report blast-radius.
  * ``nroute twin rca``          — Run root-cause analysis on events.
  * ``nroute twin reachability`` — Compute pairwise reachability.
  * ``nroute twin audit``        — Export the audit trail.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click

from nroute.utils.logging import configure_logging


@click.group(name="twin", help="Digital Twin Engine commands.")
@click.pass_context
def twin_cmd(ctx: click.Context) -> None:
    """Digital Twin Engine — Change-Impact, RCA, and Audit."""
    configure_logging(verbose=ctx.obj.get("verbose", False))


# ── twin health ──────────────────────────────────────────────


@twin_cmd.command("health")
@click.option(
    "--topology",
    "-t",
    type=click.Path(exists=True),
    required=True,
    help="Path to topology JSON file.",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default=None,
    help="Path to device config YAML/JSON to ingest before reporting.",
)
@click.pass_context
def health_cmd(ctx: click.Context, topology: str, config: str | None) -> None:
    """Show network health summary."""
    from nroute.simulation.digital_twin import DigitalTwinEngine

    twin = DigitalTwinEngine()
    twin.load_topology(topology)

    if config:
        twin.ingest_config(config)

    summary = twin.health_summary()
    click.echo(json.dumps(summary, indent=2, default=str))


# ── twin impact ──────────────────────────────────────────────


@twin_cmd.command("impact")
@click.option(
    "--topology",
    "-t",
    type=click.Path(exists=True),
    required=True,
    help="Path to topology JSON file.",
)
@click.option(
    "--change",
    "-ch",
    type=click.Path(exists=True),
    required=True,
    help="Path to change proposal YAML/JSON file.",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default=None,
    help="Optional device config to ingest before simulation.",
)
@click.option(
    "--weight",
    "-w",
    default="latency",
    help="Edge weight attribute for path computation.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Write blast-radius report to JSON file.",
)
@click.pass_context
def impact_cmd(
    ctx: click.Context,
    topology: str,
    change: str,
    config: str | None,
    weight: str,
    output: str | None,
) -> None:
    """Simulate a config change and report blast-radius."""
    from nroute.simulation.digital_twin import DigitalTwinEngine

    twin = DigitalTwinEngine()
    twin.load_topology(topology)

    if config:
        twin.ingest_config(config)

    result = twin.simulate_change(change, weight=weight)
    report = result.to_dict()

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        click.echo(f"Blast-radius report written to {output}")
    else:
        click.echo(json.dumps(report, indent=2))


# ── twin rca ─────────────────────────────────────────────────


@twin_cmd.command("rca")
@click.option(
    "--topology",
    "-t",
    type=click.Path(exists=True),
    required=True,
    help="Path to topology JSON file.",
)
@click.option(
    "--events",
    "-e",
    type=click.Path(exists=True),
    required=True,
    help="Path to events/alarms YAML/JSON file.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Write RCA report to JSON file.",
)
@click.pass_context
def rca_cmd(
    ctx: click.Context,
    topology: str,
    events: str,
    output: str | None,
) -> None:
    """Run Root-Cause Analysis on a set of events."""
    from nroute.simulation.digital_twin import DigitalTwinEngine

    twin = DigitalTwinEngine()
    twin.load_topology(topology)

    result = twin.diagnose(events)
    report = result.to_dict()

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        click.echo(f"RCA report written to {output}")
    else:
        click.echo(json.dumps(report, indent=2, default=str))


# ── twin reachability ────────────────────────────────────────


@twin_cmd.command("reachability")
@click.option(
    "--topology",
    "-t",
    type=click.Path(exists=True),
    required=True,
    help="Path to topology JSON file.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Write reachability matrix to JSON file.",
)
@click.pass_context
def reachability_cmd(
    ctx: click.Context,
    topology: str,
    output: str | None,
) -> None:
    """Compute pairwise reachability matrix."""
    from nroute.simulation.digital_twin import DigitalTwinEngine

    twin = DigitalTwinEngine()
    twin.load_topology(topology)

    reach = twin.compute_reachability()
    # Convert sets to sorted lists for JSON serialization
    serializable = {k: sorted(v) for k, v in reach.items()}

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)
        click.echo(f"Reachability matrix written to {output}")
    else:
        total_pairs = sum(len(v) for v in serializable.values())
        click.echo(f"Reachability: {len(serializable)} nodes, {total_pairs} reachable pairs")
        click.echo(json.dumps(serializable, indent=2))


# ── twin audit ───────────────────────────────────────────────


@twin_cmd.command("audit")
@click.option(
    "--log",
    "-l",
    type=click.Path(exists=True),
    required=True,
    help="Path to the NDJSON audit log file.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Export audit records to JSON file.",
)
@click.option(
    "--action",
    "-a",
    default=None,
    help="Filter by action type.",
)
@click.pass_context
def audit_cmd(
    ctx: click.Context,
    log: str,
    output: str | None,
    action: str | None,
) -> None:
    """View or export the audit trail."""
    records: list[dict[str, Any]] = []
    try:
        with open(log, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except Exception as exc:
        click.echo(f"Error reading audit log: {exc}", err=True)
        sys.exit(1)

    if action:
        records = [r for r in records if r.get("action") == action]

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        click.echo(f"Exported {len(records)} audit records to {output}")
    else:
        click.echo(f"Audit trail: {len(records)} record(s)")
        click.echo(json.dumps(records, indent=2))
