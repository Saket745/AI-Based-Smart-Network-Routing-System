"""CLI subcommands for route computation."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from nroute.core.metrics import RouteMetrics
from nroute.core.topology import Topology
from nroute.exceptions import RoutingError
from nroute.routing import get_router

console = Console()


@click.group(name="route")
def route_cmd() -> None:
    """Compute and inspect network routes."""


@route_cmd.command(name="compute")
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
    topo_path: str,
    algorithm: str,
    source: str,
    destination: str,
    weight: str,
    custom_router: str | None,
) -> None:
    """Compute the optimal route between two nodes."""
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"

    try:
        topo = Topology.load(topo_path)
    except Exception as e:
        if is_json:
            import json

            click.echo(json.dumps({"error": f"Failed to load topology: {e}"}), err=True)
            raise SystemExit(1) from None
        console.print(f"[red]x Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    # Validate that source and destination exist
    if source not in topo.nodes:
        if is_json:
            import json

            click.echo(
                json.dumps({"error": f"Source node '{source}' not found in topology."}), err=True
            )
            raise SystemExit(1) from None
        console.print(f"[red]x Source node '{source}' not found in topology.[/red]")
        raise SystemExit(1) from None
    if destination not in topo.nodes:
        if is_json:
            import json

            click.echo(
                json.dumps({"error": f"Destination node '{destination}' not found in topology."}),
                err=True,
            )
            raise SystemExit(1) from None
        console.print(f"[red]x Destination node '{destination}' not found in topology.[/red]")
        raise SystemExit(1) from None

    try:
        if algorithm.lower() == "custom":
            if not custom_router:
                raise click.UsageError(
                    "Option '--custom-router' is required when using algorithm 'custom'."
                )
            import inspect

            from nroute.routing.base import BaseRouter
            from nroute.utils.loader import load_custom_class

            router_cls = load_custom_class(custom_router, expected_superclass=BaseRouter)
            sig = inspect.signature(router_cls)
            router = router_cls(topology=topo) if "topology" in sig.parameters else router_cls()
        else:
            router = get_router(algorithm, topology=topo)
        path = router.compute_path(topo, source, destination, weight=weight)
    except RoutingError as e:
        if is_json:
            import json

            click.echo(json.dumps({"error": f"Routing error: {e}"}), err=True)
            raise SystemExit(1) from None
        console.print(f"[red]x Routing error:[/red] {e}")
        raise SystemExit(1) from e
    except Exception as e:
        if is_json:
            import json

            click.echo(json.dumps({"error": f"Failed to compute route: {e}"}), err=True)
            raise SystemExit(1) from None
        console.print(f"[red]x Failed to compute route:[/red] {e}")
        raise SystemExit(1) from e

    # Compute route metrics
    metrics = RouteMetrics.from_path(topo, path)

    if is_json:
        import json

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
        return

    # Display results
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
