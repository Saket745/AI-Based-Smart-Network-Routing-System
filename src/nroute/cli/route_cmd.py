"""CLI subcommands for route computation."""

from __future__ import annotations

import json

import click
from rich.console import Console
from rich.table import Table

from nroute.core.metrics import RouteMetrics
from nroute.core.topology import Topology
from nroute.exceptions import RoutingError
from nroute.routing import BaseRouter, get_router

console = Console()


@click.group(name="route")
def route_cmd() -> None:
    """Compute and inspect network routes."""


@route_cmd.command(name="compute")
@click.option(
    "--allow-unsafe",
    is_flag=True,
    default=False,
    help="Allow loading of unsafe models (joblib/pickle) and custom classes from file paths.",
)
@click.option(
    "--topology",
    "-t",
    "topo_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to a topology JSON file.",
)
@click.option(
    "--algorithm",
    "-a",
    type=click.Choice(
        [
            "dijkstra",
            "bellman-ford",
            "ecmp",
            "ai",
            "rl",
            "ppo",
            "dqn",
            "negotiation",
            "negotiation-latency",
            "negotiation-congestion",
            "negotiation-balanced",
            "custom",
        ],
        case_sensitive=False,
    ),
    default="dijkstra",
    show_default=True,
    help="Routing algorithm to use.",
)
@click.option("--source", "-s", type=str, required=True, help="Source node ID.")
@click.option("--destination", "-d", type=str, required=True, help="Destination node ID.")
@click.option(
    "--weight",
    "-w",
    type=str,
    default="latency",
    show_default=True,
    help="Edge weight attribute for path computation.",
)
@click.option(
    "--custom-router",
    type=str,
    default=None,
    help="Import target for custom router in path/to/file.py:ClassName format (requires -a custom).",
)
@click.pass_context
def compute(
    ctx: click.Context,
    allow_unsafe: bool,
    topo_path: str,
    algorithm: str,
    source: str,
    destination: str,
    weight: str,
    custom_router: str | None,
) -> None:
    """Compute the optimal route between two nodes."""
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"

    # Load and validate topology
    topo = _load_and_validate_topo(topo_path, source, destination, is_json)

    # Initialize router and compute path
    try:
        router = _init_router(algorithm, topo, allow_unsafe, custom_router)
        path = router.compute_path(topo, source, destination, weight=weight)
    except RoutingError as e:
        _handle_error(f"Routing error: {e}", is_json, e)
    except Exception as e:
        _handle_error(f"Failed to compute route: {e}", is_json, e)

    # Compute route metrics
    metrics = RouteMetrics.from_path(topo, path)

    # Display results
    if is_json:
        _print_json_metrics(source, destination, path, metrics)
    else:
        _print_console_metrics(algorithm, source, destination, path, metrics, topo)


def _handle_error(msg: str, is_json: bool, e: Exception | None = None) -> None:
    """Helper to handle errors consistently based on output format."""
    if is_json:
        click.echo(json.dumps({"error": msg}), err=True)
    else:
        console.print(f"[red]x {msg}[/red]")

    if e:
        raise SystemExit(1) from e
    raise SystemExit(1)


def _load_and_validate_topo(
    topo_path: str, source: str, destination: str, is_json: bool
) -> Topology:
    """Load topology and validate source/destination nodes."""
    try:
        topo = Topology.load(topo_path)
    except Exception as e:
        _handle_error(f"Failed to load topology: {e}", is_json, e)

    if source not in topo.nodes:
        _handle_error(f"Source node '{source}' not found in topology.", is_json)
    if destination not in topo.nodes:
        _handle_error(f"Destination node '{destination}' not found in topology.", is_json)

    return topo


def _init_router(
    algorithm: str,
    topo: Topology,
    allow_unsafe: bool,
    custom_router: str | None,
) -> BaseRouter:
    """Initialize the appropriate router based on algorithm name."""
    if algorithm.lower() == "custom":
        if not custom_router:
            raise click.UsageError(
                "Option '--custom-router' is required when using algorithm 'custom'."
            )
        import inspect
        import typing

        from nroute.utils.loader import load_custom_class

        router_cls = load_custom_class(
            custom_router, expected_superclass=BaseRouter, allow_unsafe=allow_unsafe
        )
        sig = inspect.signature(router_cls)
        res = router_cls(topology=topo) if "topology" in sig.parameters else router_cls()
        return typing.cast("BaseRouter", res)

    return get_router(algorithm, topology=topo, allow_unsafe=allow_unsafe)


def _print_json_metrics(
    source: str, destination: str, path: list[str], metrics: RouteMetrics
) -> None:
    """Output route metrics in JSON format."""
    out = {
        "source": source,
        "destination": destination,
        "path": path,
        "metrics": {
            "hops": metrics.total_hops,
            "total_latency": metrics.total_latency,
            "bottleneck_bandwidth": metrics.bottleneck_bandwidth
            if metrics.bottleneck_bandwidth < float("inf")
            else None,
            "bottleneck_utilization": metrics.bottleneck_utilization,
        },
    }
    click.echo(json.dumps(out, indent=2))


def _print_console_metrics(
    algorithm: str,
    source: str,
    destination: str,
    path: list[str],
    metrics: RouteMetrics,
    topo: Topology,
) -> None:
    """Output route metrics and hop breakdown to console."""
    console.print()
    console.rule(f"[bold cyan]Route: {source} -> {destination}[/bold cyan]")

    # Path display
    path_str = " -> ".join(path)
    console.print(f"\n  [bold]Path:[/bold] {path_str}\n")

    # Metrics table
    table = Table(title="Route Metrics", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")

    table.add_row("Algorithm", algorithm.upper())
    table.add_row("Hops", str(metrics.total_hops))
    table.add_row("Total Latency", f"{metrics.total_latency:.2f} ms")
    table.add_row(
        "Bottleneck Bandwidth",
        f"{metrics.bottleneck_bandwidth:.0f} Mbps"
        if metrics.bottleneck_bandwidth < float("inf")
        else "N/A",
    )
    table.add_row("Bottleneck Utilization", f"{metrics.bottleneck_utilization:.1%}")

    console.print(table)

    # Per-hop breakdown
    if metrics.total_hops > 0:
        hop_table = Table(
            title="Hop-by-Hop Breakdown", show_header=True, header_style="bold magenta"
        )
        hop_table.add_column("Hop", style="dim", justify="center")
        hop_table.add_column("From", style="cyan")
        hop_table.add_column("To", style="cyan")
        hop_table.add_column("Latency (ms)", style="green", justify="right")
        hop_table.add_column("Bandwidth (Mbps)", style="green", justify="right")
        hop_table.add_column("Utilization", style="green", justify="right")
        hop_table.add_column("Status", justify="center")

        for i in range(metrics.total_hops):
            u, v = path[i], path[i + 1]
            try:
                edge = topo.get_edge(u, v)
                lat_str = f"{float(edge.get('latency', 0)):.1f}"
                bw_str = f"{float(edge.get('bandwidth', 0)):.0f}"
                util_str = f"{float(edge.get('utilization', 0)):.1%}"
                status = edge.get("status", "up")
                status_icon = "[green]up[/green]" if status == "up" else "[red]down[/red]"
            except Exception:
                lat_str = "?"
                bw_str = "?"
                util_str = "?"
                status_icon = "[yellow]?[/yellow]"

            hop_table.add_row(str(i + 1), u, v, lat_str, bw_str, util_str, status_icon)

        console.print(hop_table)

    console.print()
