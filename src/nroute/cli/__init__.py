"""nroute CLI — root command group."""

from __future__ import annotations

import click

import nroute
from nroute.cli.detect_cmd import detect_cmd
from nroute.cli.predict_cmd import predict_cmd
from nroute.cli.route_cmd import route_cmd
from nroute.cli.simulate_cmd import simulate_cmd
from nroute.cli.topology_cmd import topology_cmd
from nroute.cli.train_cmd import train_cmd
from nroute.cli.twin_cmd import twin_cmd


@click.group(
    name="nroute",
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(version=nroute.__version__, prog_name="nroute")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose (DEBUG) logging.",
)
@click.option(
    "--config",
    type=click.Path(exists=False),
    default=None,
    help="Path to nroute.yaml configuration file.",
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Global random seed for reproducibility.",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config: str | None, seed: int | None) -> None:
    """nroute - AI-Based Smart Network Routing System.

    Simulate, visualize, and optimize network routing
    with AI/ML: congestion prediction, anomaly detection,
    and intelligent path rerouting.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["config"] = config
    ctx.obj["seed"] = seed

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ── Register Subcommand Groups ──────────────────────────────
cli.add_command(topology_cmd, "topology")
cli.add_command(route_cmd, "route")
cli.add_command(simulate_cmd, "simulate")
cli.add_command(train_cmd, "train")
cli.add_command(predict_cmd, "predict")
cli.add_command(detect_cmd, "detect")
cli.add_command(twin_cmd, "twin")
