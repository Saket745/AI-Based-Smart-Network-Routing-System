"""CLI subcommands for topology operations (generate, show)."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from nroute.core.generators import TopologyGenerator
from nroute.core.topology import Topology
from nroute.exceptions import TopologyError

console = Console()


@click.group(name="topology")
def topology_cmd() -> None:
    """Manage and inspect network topologies."""


@topology_cmd.command(name="generate")
@click.option(
    "--type",
    "topo_type",
    type=click.Choice(["random", "scale-free", "small-world", "fat-tree"], case_sensitive=False),
    required=True,
    help="Topology generation model.",
)
@click.option("--nodes", "-n", type=int, default=10, show_default=True, help="Number of nodes.")
@click.option(
    "--edge-prob",
    type=float,
    default=0.3,
    show_default=True,
    help="Edge probability (random only).",
)
@click.option(
    "--k",
    type=int,
    default=4,
    show_default=True,
    help="Port count k (fat-tree) or k-neighbors (small-world).",
)
@click.option(
    "--rewire-prob",
    type=float,
    default=0.1,
    show_default=True,
    help="Rewire probability (small-world only).",
)
@click.option("--seed", type=int, default=None, help="Random seed for reproducibility.")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output path for the topology JSON. Defaults to stdout summary.",
)
@click.pass_context
def generate(
    ctx: click.Context,
    topo_type: str,
    nodes: int,
    edge_prob: float,
    k: int,
    rewire_prob: float,
    seed: int | None,
    output: str | None,
) -> None:
    """Generate a synthetic network topology."""
    # Inherit global seed if not overridden
    seed = seed or ctx.obj.get("seed")

    try:
        topo_type_lower = topo_type.lower()
        topo: Topology

        if topo_type_lower == "random":
            topo = TopologyGenerator.random(n_nodes=nodes, edge_prob=edge_prob, seed=seed)
        elif topo_type_lower == "scale-free":
            topo = TopologyGenerator.scale_free(n_nodes=nodes, seed=seed)
        elif topo_type_lower == "small-world":
            topo = TopologyGenerator.small_world(
                n_nodes=nodes, k_neighbors=k, rewire_prob=rewire_prob, seed=seed
            )
        elif topo_type_lower == "fat-tree":
            topo = TopologyGenerator.fat_tree(k=k, seed=seed)
        else:
            raise TopologyError(f"Unknown topology type: {topo_type}")

        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            topo.save(str(out_path))
            console.print(
                f"[green]✓[/green] Topology saved to [bold]{out_path}[/bold]  "
                f"({topo.node_count} nodes, {topo.edge_count} edges)"
            )
        else:
            # Print summary to stdout
            _print_topology_summary(topo, title=f"{topo_type} Topology")

    except TopologyError as e:
        console.print(f"[red]✗ Topology error:[/red] {e}")
        raise SystemExit(1) from e


@topology_cmd.command(name="show")
@click.option(
    "--file",
    "-f",
    "filepath",
    type=click.Path(exists=True),
    required=True,
    help="Path to a topology JSON file.",
)
def show(filepath: str) -> None:
    """Display a summary of an existing topology."""
    try:
        topo = Topology.load(filepath)
        _print_topology_summary(topo, title=f"Topology: {filepath}")
    except Exception as e:
        console.print(f"[red]✗ Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e


def _print_topology_summary(topo: Topology, title: str = "Topology Summary") -> None:
    """Print a Rich table summarizing the topology."""
    console.print()
    console.rule(f"[bold cyan]{title}[/bold cyan]")

    # Overview stats
    stats_table = Table(title="Overview", show_header=True, header_style="bold magenta")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green", justify="right")

    stats_table.add_row("Nodes", str(topo.node_count))
    stats_table.add_row("Edges", str(topo.edge_count))

    # Compute degree ranges
    degrees = [topo.graph.degree(n) for n in topo.graph.nodes]
    if degrees:
        stats_table.add_row("Min Degree", str(min(degrees)))
        stats_table.add_row("Max Degree", str(max(degrees)))
        stats_table.add_row("Avg Degree", f"{sum(degrees) / len(degrees):.1f}")

    # Count node statuses
    up_nodes = sum(1 for n in topo.nodes if topo.get_node(n).get("status") == "up")
    down_nodes = topo.node_count - up_nodes
    stats_table.add_row("Nodes Up", str(up_nodes))
    stats_table.add_row("Nodes Down", str(down_nodes))

    # Count edge statuses
    up_edges = sum(1 for u, v in topo.edges if topo.get_edge(u, v).get("status") == "up")
    down_edges = topo.edge_count - up_edges
    stats_table.add_row("Links Up", str(up_edges))
    stats_table.add_row("Links Down", str(down_edges))

    console.print(stats_table)

    # Node type breakdown
    node_types: dict[str, int] = {}
    for n in topo.nodes:
        ntype = topo.get_node(n).get("type", "unknown")
        node_types[ntype] = node_types.get(ntype, 0) + 1

    if node_types:
        type_table = Table(title="Node Types", show_header=True, header_style="bold magenta")
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Count", style="green", justify="right")
        for ntype, count in sorted(node_types.items()):
            type_table.add_row(ntype, str(count))
        console.print(type_table)

    console.print()
