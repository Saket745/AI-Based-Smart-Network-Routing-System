"""CLI subcommands for route computation."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

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
def compute(
    topo_path: str,
    algorithm: str,
    source: str,
    destination: str,
    weight: str,
) -> None:
    """Compute the optimal route between two nodes."""
    try:
        topo = Topology.load(topo_path)
    except Exception as e:
        console.print(f"[red]x Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    # Validate that source and destination exist
    if source not in topo.nodes:
        console.print(f"[red]x Source node '{source}' not found in topology.[/red]")
        raise SystemExit(1)
    if destination not in topo.nodes:
        console.print(f"[red]x Destination node '{destination}' not found in topology.[/red]")
        raise SystemExit(1)

    try:
        router = get_router(algorithm, topology=topo)
        path = router.compute_path(topo, source, destination, weight=weight)
    except RoutingError as e:
        console.print(f"[red]x Routing error:[/red] {e}")
        raise SystemExit(1) from e
    except Exception as e:
        console.print(f"[red]x Failed to compute route:[/red] {e}")
        raise SystemExit(1) from e

    # Compute route metrics
    total_latency = 0.0
    total_hops = len(path) - 1
    bottleneck_bw = float("inf")
    bottleneck_util = 0.0

    for i in range(total_hops):
        u, v = path[i], path[i + 1]
        try:
            edge = topo.get_edge(u, v)
            total_latency += float(edge.get("latency", 0.0))
            bw = float(edge.get("bandwidth", float("inf")))
            util = float(edge.get("utilization", 0.0))
            if bw < bottleneck_bw:
                bottleneck_bw = bw
                bottleneck_util = util
        except Exception:
            pass

    # Display results
    console.print()
    console.rule(f"[bold cyan]Route: {source} → {destination}[/bold cyan]")

    # Path display
    path_str = " → ".join(path)
    console.print(f"\n  [bold]Path:[/bold] {path_str}\n")

    # Metrics table
    table = Table(title="Route Metrics", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")

    table.add_row("Algorithm", algorithm.upper())
    table.add_row("Hops", str(total_hops))
    table.add_row("Total Latency", f"{total_latency:.2f} ms")
    table.add_row(
        "Bottleneck Bandwidth",
        f"{bottleneck_bw:.0f} Mbps" if bottleneck_bw < float("inf") else "N/A",
    )
    table.add_row("Bottleneck Utilization", f"{bottleneck_util:.1%}")

    console.print(table)

    # Per-hop breakdown
    if total_hops > 0:
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

        for i in range(total_hops):
            u, v = path[i], path[i + 1]
            try:
                edge = topo.get_edge(u, v)
                lat_str = f"{float(edge.get('latency', 0)):.1f}"
                bw_str = f"{float(edge.get('bandwidth', 0)):.0f}"
                util_str = f"{float(edge.get('utilization', 0)):.1%}"
                status = edge.get("status", "up")
                status_icon = "🟢" if status == "up" else "🔴"
            except Exception:
                lat_str = "?"
                bw_str = "?"
                util_str = "?"
                status_icon = "❓"

            hop_table.add_row(str(i + 1), u, v, lat_str, bw_str, util_str, status_icon)

        console.print(hop_table)

    console.print()
