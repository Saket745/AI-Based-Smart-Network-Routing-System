"""nroute CLI — root command group."""

from __future__ import annotations

import click

import nroute


@click.group(
    name="nroute",
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(version=nroute.__version__, prog_name="nroute")
@click.option(
    "--verbose", "-v",
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


# ── Subcommand groups (registered as phases are built) ──────
# Phase 3: cli.add_command(topology_cmd)
# Phase 5: cli.add_command(route_cmd)
# Phase 6: cli.add_command(simulate_cmd)
# Phase 7: cli.add_command(train_cmd)
# Phase 7: cli.add_command(predict_cmd)
# Phase 7: cli.add_command(detect_cmd)
# Phase 9: cli.add_command(export_cmd)
