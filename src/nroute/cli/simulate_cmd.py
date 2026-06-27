"""CLI subcommands for simulation operations (run, compare)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from nroute.core.topology import Topology
from nroute.exceptions import SimulationError
from nroute.routing import get_router
from nroute.simulation.engine import SimulationEngine
from nroute.simulation.traffic_gen import TrafficGenerator

console = Console()


@click.group(name="simulate")
def simulate_cmd() -> None:
    """Run and compare network simulations."""


@simulate_cmd.command(name="run")
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
@click.option(
    "--duration",
    "-d",
    type=int,
    default=50,
    show_default=True,
    help="Number of simulation ticks.",
)
@click.option(
    "--traffic-model",
    type=click.Choice(["uniform", "gravity", "hotspot", "bursty"], case_sensitive=False),
    default="uniform",
    show_default=True,
    help="Traffic generation model.",
)
@click.option(
    "--flows-per-tick",
    type=int,
    default=5,
    show_default=True,
    help="Number of flows generated per tick.",
)
@click.option("--seed", type=int, default=None, help="Random seed for reproducibility.")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output path for metrics JSON.",
)
@click.option(
    "--visualize",
    is_flag=True,
    default=False,
    help="Enable interactive real-time console visualization.",
)
@click.option(
    "--visualize-delay",
    type=float,
    default=0.2,
    help="Delay in seconds between ticks during visualization.",
)
@click.option(
    "--model-path",
    "-m",
    type=click.Path(),
    default=None,
    help="Path to a pretrained model to load into the RL/AI router.",
)
@click.option(
    "--custom-router",
    type=str,
    default=None,
    help="Import target for custom router in path/to/file.py:ClassName format (requires -a custom).",
)
@click.pass_context
def run_sim(
    ctx: click.Context,
    allow_unsafe: bool,
    topo_path: str,
    algorithm: str,
    duration: int,
    traffic_model: str,
    flows_per_tick: int,
    seed: int | None,
    output: str | None,
    visualize: bool,
    visualize_delay: float,
    model_path: str | None,
    custom_router: str | None,
) -> None:
    """Run a network simulation."""
    seed = seed or (ctx.obj.get("seed") if ctx.obj is not None else None)
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"

    topo = _load_topology(topo_path, is_json)

    try:
        router = _setup_router(
            algorithm, topo, allow_unsafe, model_path=model_path, custom_router=custom_router
        )
        traffic_gen = TrafficGenerator(model=traffic_model, n_flows_per_tick=flows_per_tick)
        engine = SimulationEngine(topo, router, traffic_gen)

        if visualize:
            from nroute.visualization import LiveSimulationConsole

            console.print("[cyan]Initializing real-time console visualization...[/cyan]")
            visualizer = LiveSimulationConsole(
                engine=engine,
                duration_ticks=duration,
                seed=seed,
                delay=visualize_delay,
            )
            result = visualizer.run()
        else:
            console.print(
                f"\n[cyan]Running simulation:[/cyan] {algorithm.upper()} on "
                f"{topo.node_count} nodes, {duration} ticks, "
                f"{traffic_model} traffic ({flows_per_tick} flows/tick)\n"
            )
            result = engine.run(duration_ticks=duration, seed=seed)

    except SimulationError as e:
        console.print(f"[red]x Simulation error:[/red] {e}")
        raise SystemExit(1) from e
    except Exception as e:
        console.print(f"[red]x Simulation failed:[/red] {e}")
        raise SystemExit(1) from e

    metrics = _get_metrics_summary(result)
    metrics_data = {
        "algorithm": algorithm,
        "duration_ticks": duration,
        "traffic_model": traffic_model,
        "seed": seed,
        **metrics,
        "ticks": [
            {
                "tick": m.tick,
                "throughput": m.throughput,
                "avg_latency": m.avg_latency,
                "packet_loss_rate": m.packet_loss_rate,
                "reroute_count": m.reroute_count,
                "avg_utilization": m.avg_utilization,
            }
            for m in result.results
        ],
    }

    if is_json:
        click.echo(json.dumps(metrics_data, indent=2))
        if output:
            _save_json_results(output, metrics_data)
        return

    # Display results
    _print_simulation_results(result, algorithm)

    # Save to file if requested
    if output:
        _save_json_results(output, metrics_data)
        console.print(f"[green]+[/green] Metrics saved to [bold]{output}[/bold]")


@simulate_cmd.command(name="compare")
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
    "--algorithms",
    "-a",
    type=str,
    required=True,
    help="Comma-separated list of algorithms to compare (e.g. dijkstra,ecmp,negotiation).",
)
@click.option(
    "--duration",
    "-d",
    type=int,
    default=50,
    show_default=True,
    help="Number of simulation ticks.",
)
@click.option(
    "--traffic-model",
    type=click.Choice(["uniform", "gravity", "hotspot", "bursty"], case_sensitive=False),
    default="uniform",
    show_default=True,
    help="Traffic generation model.",
)
@click.option(
    "--flows-per-tick",
    type=int,
    default=5,
    show_default=True,
    help="Number of flows generated per tick.",
)
@click.option("--seed", type=int, default=None, help="Random seed for reproducibility.")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output path for comparison JSON.",
)
@click.option(
    "--model-path",
    "-m",
    type=click.Path(),
    default=None,
    help="Path to a pretrained model to load into RL/AI routers.",
)
@click.option(
    "--custom-router",
    type=str,
    default=None,
    help="Import target for custom router in path/to/file.py:ClassName format (requires custom in -a).",
)
@click.pass_context
def compare(
    ctx: click.Context,
    allow_unsafe: bool,
    topo_path: str,
    algorithms: str,
    duration: int,
    traffic_model: str,
    flows_per_tick: int,
    seed: int | None,
    output: str | None,
    model_path: str | None,
    custom_router: str | None,
) -> None:
    """Compare multiple routing algorithms on the same topology and traffic."""
    seed = seed or (ctx.obj.get("seed") if ctx.obj is not None else None)
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"
    algo_list = [a.strip() for a in algorithms.split(",") if a.strip()]

    if len(algo_list) < 2:
        if is_json:
            click.echo(
                json.dumps({"error": "Please provide at least 2 algorithms to compare."}), err=True
            )
            raise SystemExit(1) from None
        console.print("[red]x Please provide at least 2 algorithms to compare.[/red]")
        raise SystemExit(1) from None

    topo = _load_topology(topo_path, is_json)

    if not is_json:
        console.print(
            f"\n[cyan]Comparing algorithms:[/cyan] {', '.join(a.upper() for a in algo_list)}\n"
            f"  Topology: {topo.node_count} nodes, {topo.edge_count} edges\n"
            f"  Duration: {duration} ticks | Traffic: {traffic_model} ({flows_per_tick} flows/tick)\n"
        )

    results: dict[str, Any] = {}

    for algo in algo_list:
        try:
            router = _setup_router(
                algo, topo, allow_unsafe, model_path=model_path, custom_router=custom_router
            )
            traffic_gen = TrafficGenerator(model=traffic_model, n_flows_per_tick=flows_per_tick)
            engine = SimulationEngine(topo, router, traffic_gen)
            result = engine.run(duration_ticks=duration, seed=seed)
            results[algo] = result
        except Exception as e:
            console.print(f"[yellow]⚠ {algo.upper()} failed:[/yellow] {e}")
            results[algo] = None

    comparison_data: dict[str, Any] = {}
    for algo in algo_list:
        r = results[algo]
        if r is not None:
            comparison_data[algo] = _get_metrics_summary(r)
        else:
            comparison_data[algo] = {"error": "simulation_failed"}

    if is_json:
        click.echo(json.dumps(comparison_data, indent=2))
        if output:
            _save_json_results(output, comparison_data)
        return

    # Build and print comparison table
    _render_comparison_table(algo_list, results)

    # Save comparison if requested
    if output:
        _save_json_results(output, comparison_data)
        console.print(f"\n[green]+[/green] Comparison saved to [bold]{output}[/bold]")

    console.print()


def _load_topology(topo_path: str, is_json: bool) -> Topology:
    """Load topology from file with error handling."""
    try:
        return Topology.load(topo_path)
    except Exception as e:
        if is_json:
            click.echo(json.dumps({"error": f"Failed to load topology: {e}"}), err=True)
            raise SystemExit(1) from e
        console.print(f"[red]x Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e


def _setup_router(
    algorithm: str,
    topology: Topology,
    allow_unsafe: bool,
    model_path: str | None = None,
    custom_router: str | None = None,
) -> Any:
    """Initialize router and load pretrained model if provided."""
    if algorithm.lower() == "custom":
        if not custom_router:
            raise click.UsageError(
                "Option '--custom-router' is required when using algorithm 'custom'."
            )

        from nroute.routing.base import BaseRouter
        from nroute.utils.loader import load_custom_class

        router_cls = load_custom_class(
            custom_router, expected_superclass=BaseRouter, allow_unsafe=allow_unsafe
        )
        sig = inspect.signature(router_cls)
        router = router_cls(topology=topology) if "topology" in sig.parameters else router_cls()
    else:
        router = get_router(algorithm, topology=topology, allow_unsafe=allow_unsafe)

    # Load pretrained model if provided
    if model_path and hasattr(router, "load"):
        try:
            # Some routers might need allow_unsafe passed to load
            sig = inspect.signature(router.load)
            if "allow_unsafe" in sig.parameters:
                router.load(model_path, allow_unsafe=allow_unsafe)
            else:
                router.load(model_path)
            console.print(
                f"[green]+[/green] Loaded pretrained model for {algorithm.upper()} "
                f"from [bold]{model_path}[/bold]"
            )
        except Exception as e:
            console.print(f"[yellow]! Failed to load model for {algorithm.upper()}:[/yellow] {e}")

    return router


def _get_metrics_summary(result: Any) -> dict[str, Any]:
    """Extract summary metrics from simulation result."""
    total_reroutes = sum(m.reroute_count for m in result.results)
    avg_loss = (
        sum(m.packet_loss_rate for m in result.results) / len(result.results)
        if result.results
        else 0.0
    )
    return {
        "total_throughput": result.total_throughput(),
        "mean_latency": result.mean_latency(),
        "avg_packet_loss_rate": avg_loss,
        "total_reroutes": total_reroutes,
    }


def _save_json_results(output_path: str, data: dict[str, Any]) -> None:
    """Save metrics data to a JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _render_comparison_table(algo_list: list[str], results: dict[str, Any]) -> None:
    """Build and print comparison table using Rich."""
    table = Table(
        title="Algorithm Comparison",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Metric", style="cyan")
    for algo in algo_list:
        table.add_column(algo.upper(), style="green", justify="right")

    metrics_rows = [
        ("Total Throughput", lambda r: f"{r.total_throughput():.0f}"),
        ("Mean Latency (ms)", lambda r: f"{r.mean_latency():.2f}"),
        (
            "Avg Packet Loss Rate",
            lambda r: (
                f"{sum(m.packet_loss_rate for m in r.results) / len(r.results):.2%}"
                if r.results
                else "0.00%"
            ),
        ),
        ("Total Reroutes", lambda r: str(sum(m.reroute_count for m in r.results))),
    ]

    for label, extractor in metrics_rows:
        row_values = []
        for algo in algo_list:
            r = results[algo]
            if r is not None:
                try:
                    row_values.append(extractor(r))  # type: ignore[no-untyped-call]
                except Exception:
                    row_values.append("ERR")
            else:
                row_values.append("FAILED")
        table.add_row(label, *row_values)

    console.print(table)


def _print_simulation_results(result: Any, algorithm: str) -> None:
    """Print simulation results as a Rich table."""
    console.print()
    console.rule("[bold cyan]Simulation Results[/bold cyan]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")

    metrics = _get_metrics_summary(result)

    table.add_row("Algorithm", algorithm.upper())
    table.add_row("Total Throughput", f"{metrics['total_throughput']:.0f} Mbps")
    table.add_row("Mean Latency", f"{metrics['mean_latency']:.2f} ms")
    table.add_row("Avg Packet Loss Rate", f"{metrics['avg_packet_loss_rate']:.2%}")
    table.add_row("Total Reroutes", str(metrics["total_reroutes"]))
    table.add_row("Ticks Simulated", str(len(result.results)))

    console.print(table)
    console.print()
