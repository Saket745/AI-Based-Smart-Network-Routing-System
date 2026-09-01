"""nroute CLI — root command group."""

from __future__ import annotations

import os
import sys
from typing import Any

import click

import nroute
from nroute.cli import (
    api_cmd,
    configs_cmd,
    detect_cmd,
    export_cmd,
    predict_cmd,
    route_cmd,
    simulate_cmd,
    topology_cmd,
    train_cmd,
    twin_cmd,
)
from nroute.cli.api_cmd import api_cmd as api_group
from nroute.cli.configs_cmd import config_cmd as config_group
from nroute.cli.detect_cmd import detect_cmd as detect_group
from nroute.cli.export_cmd import export_cmd as export_group
from nroute.cli.predict_cmd import predict_cmd as predict_group
from nroute.cli.route_cmd import route_cmd as route_group
from nroute.cli.simulate_cmd import simulate_cmd as simulate_group
from nroute.cli.topology_cmd import topology_cmd as topology_group
from nroute.cli.train_cmd import train_cmd as train_group
from nroute.cli.twin_cmd import twin_cmd as twin_group
import nroute.cli.api_cmd as api_cmd_mod
import nroute.cli.configs_cmd as configs_cmd_mod
import nroute.cli.detect_cmd as detect_cmd_mod
import nroute.cli.export_cmd as export_cmd_mod
import nroute.cli.predict_cmd as predict_cmd_mod
import nroute.cli.route_cmd as route_cmd_mod
import nroute.cli.simulate_cmd as simulate_cmd_mod
import nroute.cli.topology_cmd as topology_cmd_mod
import nroute.cli.train_cmd as train_cmd_mod
import nroute.cli.twin_cmd as twin_cmd_mod



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
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress non-error logs (set logging level to ERROR).",
)
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    help="Disable colored output.",
)
@click.option(
    "--output-format",
    "-f",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Choose text for people or JSON for scripts and automation.",
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
def cli(ctx: click.Context, /, **kwargs: Any) -> None:
    """nroute - AI-Based Smart Network Routing System.

    Simulate, visualize, and optimize network routing
    with AI/ML: congestion prediction, anomaly detection,
    and intelligent path rerouting.
    """
    ctx.ensure_object(dict)
    ctx.obj.update(kwargs)

    # Handle NO_COLOR environment variable setting
    if ctx.obj.get("no_color"):
        os.environ["NO_COLOR"] = "1"

    # Load configuration
    from nroute.core.config import load_config

    try:
        cfg = load_config(ctx.obj.get("config"))
    except Exception as exc:
        click.echo(f"Error loading configuration: {exc}", err=True)
        sys.exit(1)

    ctx.obj["config_obj"] = cfg

    # Resolve global seed
    # Precedence: CLI --seed flag, then config file seed
    seed = ctx.obj.get("seed")
    resolved_seed = seed if seed is not None else cfg.general.seed
    ctx.obj["seed"] = resolved_seed

    # Configure global logging
    from nroute.utils.logging import configure_logging

    # Check if stderr is a TTY. If not, force json format (C4 requirement)
    json_format = cfg.general.log_format.lower() == "json"
    if not sys.stderr.isatty():
        json_format = True

    configure_logging(
        verbose=ctx.obj.get("verbose", False),
        quiet=ctx.obj.get("quiet", False),
        json_format=json_format,
        colors=not ctx.obj.get("no_color", False),
        log_level_override=cfg.general.log_level,
    )

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ── Register Subcommand Groups ──────────────────────────────
cli.add_command(topology_cmd.topology_cmd, "topology")
cli.add_command(route_cmd.route_cmd, "route")
cli.add_command(simulate_cmd.simulate_cmd, "simulate")
cli.add_command(train_cmd.train_cmd, "train")
cli.add_command(predict_cmd.predict_cmd, "predict")
cli.add_command(detect_cmd.detect_cmd, "detect")
cli.add_command(twin_cmd.twin_cmd, "twin")
cli.add_command(export_cmd.export_cmd, "export")
cli.add_command(api_cmd.api_cmd, "api")
cli.add_command(configs_cmd.config_cmd, "config")
cli.add_command(topology_group, "topology")
cli.add_command(route_group, "route")
cli.add_command(simulate_group, "simulate")
cli.add_command(train_group, "train")
cli.add_command(predict_group, "predict")
cli.add_command(detect_group, "detect")
cli.add_command(twin_group, "twin")
cli.add_command(export_group, "export")
cli.add_command(api_group, "api")
cli.add_command(config_group, "config")
cli.add_command(topology_cmd_mod.topology_cmd, "topology")
cli.add_command(route_cmd_mod.route_cmd, "route")
cli.add_command(simulate_cmd_mod.simulate_cmd, "simulate")
cli.add_command(train_cmd_mod.train_cmd, "train")
cli.add_command(predict_cmd_mod.predict_cmd, "predict")
cli.add_command(detect_cmd_mod.detect_cmd, "detect")
cli.add_command(twin_cmd_mod.twin_cmd, "twin")
cli.add_command(export_cmd_mod.export_cmd, "export")
cli.add_command(api_cmd_mod.api_cmd, "api")
cli.add_command(configs_cmd_mod.config_cmd, "config")



# ── Shell Completion Subcommand ─────────────────────────────
@cli.command(name="completion", help="Generate shell completion scripts.")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion(shell: str) -> None:
    """Generate shell completion scripts for bash, zsh, or fish."""
    if shell == "bash":
        click.echo('eval "$(_NROUTE_COMPLETE=bash_source nroute)"')
    elif shell == "zsh":
        click.echo('eval "$(_NROUTE_COMPLETE=zsh_source nroute)"')
    elif shell == "fish":
        click.echo('eval "$(_NROUTE_COMPLETE=fish_source nroute)"')
