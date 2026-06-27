"""CLI subcommands for simulation operations (run, compare)."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from nroute.core.topology import Topology
from nroute.exceptions import SimulationError
from nroute.routing import get_router
from nroute.simulation.engine import SimulationEngine, SimulationRunConfig
from nroute.simulation.traffic_gen import TrafficGenerator

console = Console()


@dataclass
class RouterConfig:
    """Configuration for router creation."""

    algorithm: str
    allow_unsafe: bool = False
    model_path: str | None = None
    custom_router: str | None = None


@click.group(name="simulate")
def simulate_cmd() -> None:
    """Run and compare network simulations."""


def _create_router(topology: Topology, config: RouterConfig) -> Any:
    """Helper to create and initialize a router from configuration."""
    if config.algorithm.lower() == "custom":
        if not config.custom_router:
            raise click.UsageError(
                "Option '--custom-router' is required when using algorithm 'custom'."
            )

        from nroute.routing.base import BaseRouter
        from nroute.utils.loader import load_custom_class

        router_cls = load_custom_class(
            config.custom_router, expected_superclass=BaseRouter, allow_unsafe=config.allow_unsafe
        )
        sig = inspect.signature(router_cls)
        router = router_cls(topology=topology) if "topology" in sig.parameters else router_cls()
    else:
        router = get_router(config.algorithm, topology=topology, allow_unsafe=config.allow_unsafe)

    # Load pretrained model if provided
    if config.model_path and hasattr(router, "load"):
        try:
            # Some routers might need allow_unsafe passed to load
            sig = inspect.signature(router.load)
            if "allow_unsafe" in sig.parameters:
                router.load(config.model_path, allow_unsafe=config.allow_unsafe)
            else:
                router.load(config.model_path)
            console.print(
                f"[green]+[/green] Loaded pretrained model from [bold]{config.model_path}[/bold]"
            )
        except Exception as e:
            console.print(f"[yellow]! Failed to load model:[/yellow] {e}")

    return router


def _get_sim_result_data(
    result: Any, algorithm: str, config: SimulationRunConfig
) -> dict[str, Any]:
    """Helper to format simulation results into a dictionary."""
    total_reroutes = sum(m.reroute_count for m in result.results)
    avg_loss = (
        sum(m.packet_loss_rate for m in result.results) / len(result.results)
        if result.results
        else 0.0
    )
    return {
        "algorithm": algorithm,
        "duration_ticks": config.duration,
        "traffic_model": config.traffic_model,
        "seed": config.seed,
        "total_throughput": result.total_throughput(),
        "mean_latency": result.mean_latency(),
        "avg_packet_loss_rate": avg_loss,
        "total_reroutes": total_reroutes,
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


def _run_simulation(
    topology: Topology,
    router_config: RouterConfig,
    run_config: SimulationRunConfig,
    visualize: bool = False,
    visualize_delay: float = 0.2,
    quiet: bool = False,
) -> Any:
    """Helper to orchestrate and run a simulation."""
    router = _create_router(topology, router_config)
    traffic_gen = TrafficGenerator(
        model=run_config.traffic_model, n_flows_per_tick=run_config.flows_per_tick
    )
    engine = SimulationEngine(topology, router, traffic_gen)

    if visualize:
        from nroute.visualization import LiveSimulationConsole

        if not quiet:
            console.print("[cyan]Initializing real-time console visualization...[/cyan]")
        visualizer = LiveSimulationConsole(
            engine=engine,
            duration_ticks=run_config.duration,
            seed=run_config.seed,
            delay=visualize_delay,
        )
        return visualizer.run()

    if not quiet:
        console.print(
            f"\n[cyan]Running simulation:[/cyan] {router_config.algorithm.upper()} on "
            f"{topology.node_count} nodes, {run_config.duration} ticks, "
            f"{run_config.traffic_model} traffic ({run_config.flows_per_tick} flows/tick)\n"
        )
    return engine.run(duration_ticks=run_config.duration, seed=run_config.seed)


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
def run_sim(ctx: click.Context, **kwargs: Any) -> None:
    """Run a network simulation."""
    # Extract context-dependent values
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"
    seed = kwargs.get("seed") or (ctx.obj.get("seed") if ctx.obj is not None else None)

    topo_path = kwargs.get("topo_path", "")
    try:
        topo = Topology.load(topo_path)
    except Exception as e:
        if is_json:
            click.echo(json.dumps({"error": f"Failed to load topology: {e}"}), err=True)
            raise SystemExit(1) from e
        console.print(f"[red]x Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    run_config = SimulationRunConfig(
        duration=kwargs.get("duration", 50),
        traffic_model=kwargs.get("traffic_model", "uniform"),
        flows_per_tick=kwargs.get("flows_per_tick", 5),
        seed=seed,
    )
    router_config = RouterConfig(
        algorithm=kwargs.get("algorithm", "dijkstra"),
        allow_unsafe=kwargs.get("allow_unsafe", False),
        model_path=kwargs.get("model_path"),
        custom_router=kwargs.get("custom_router"),
    )

    try:
        result = _run_simulation(
            topology=topo,
            router_config=router_config,
            run_config=run_config,
            visualize=kwargs.get("visualize", False),
            visualize_delay=kwargs.get("visualize_delay", 0.2),
        )
    except SimulationError as e:
        console.print(f"[red]x Simulation error:[/red] {e}")
        raise SystemExit(1) from e
    except Exception as e:
        console.print(f"[red]x Simulation failed:[/red] {e}")
        raise SystemExit(1) from e

    algorithm = router_config.algorithm
    metrics_data = _get_sim_result_data(result, algorithm, run_config)
    output = kwargs.get("output")

    if is_json:
        click.echo(json.dumps(metrics_data, indent=2))
        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(metrics_data, indent=2))
        return

    # Display results
    _print_simulation_results(result, algorithm)

    # Save to file if requested
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(metrics_data, indent=2))
        console.print(f"[green]+[/green] Metrics saved to [bold]{out_path}[/bold]")


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
def compare(ctx: click.Context, **kwargs: Any) -> None:
    """Compare multiple routing algorithms on the same topology and traffic."""
    # Extract context-dependent values
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"
    seed = kwargs.get("seed") or (ctx.obj.get("seed") if ctx.obj is not None else None)

    algorithms = kwargs.get("algorithms", "")
    algo_list = [a.strip() for a in algorithms.split(",") if a.strip()]

    if len(algo_list) < 2:
        if is_json:
            click.echo(
                json.dumps({"error": "Please provide at least 2 algorithms to compare."}), err=True
            )
            raise SystemExit(1) from None
        console.print("[red]x Please provide at least 2 algorithms to compare.[/red]")
        raise SystemExit(1) from None

    topo_path = kwargs.get("topo_path", "")
    try:
        topo = Topology.load(topo_path)
    except Exception as e:
        if is_json:
            click.echo(json.dumps({"error": f"Failed to load topology: {e}"}), err=True)
            raise SystemExit(1) from e
        console.print(f"[red]x Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    run_config = SimulationRunConfig(
        duration=kwargs.get("duration", 50),
        traffic_model=kwargs.get("traffic_model", "uniform"),
        flows_per_tick=kwargs.get("flows_per_tick", 5),
        seed=seed,
    )

    if not is_json:
        console.print(
            f"\n[cyan]Comparing algorithms:[/cyan] {', '.join(a.upper() for a in algo_list)}\n"
            f"  Topology: {topo.node_count} nodes, {topo.edge_count} edges\n"
            f"  Duration: {run_config.duration} ticks | Traffic: {run_config.traffic_model} ({run_config.flows_per_tick} flows/tick)\n"
        )

    results: dict[str, Any] = {}

    for algo in algo_list:
        try:
            router_cfg = RouterConfig(
                algorithm=algo,
                allow_unsafe=kwargs.get("allow_unsafe", False),
                model_path=kwargs.get("model_path"),
                custom_router=kwargs.get("custom_router"),
            )
            result = _run_simulation(
                topology=topo,
                router_config=router_cfg,
                run_config=run_config,
                quiet=True,
            )
            results[algo] = result
        except Exception as e:
            console.print(f"[yellow]⚠ {algo.upper()} failed:[/yellow] {e}")
            results[algo] = None

    output = kwargs.get("output")
    if is_json:
        comparison_data: dict[str, Any] = {}
        for algo in algo_list:
            r = results[algo]
            if r is not None:
                res_data = _get_sim_result_data(r, algo, run_config)
                comparison_data[algo] = {
                    "total_throughput": res_data["total_throughput"],
                    "mean_latency": res_data["mean_latency"],
                    "avg_packet_loss_rate": res_data["avg_packet_loss_rate"],
                    "total_reroutes": res_data["total_reroutes"],
                }
            else:
                comparison_data[algo] = {"error": "simulation_failed"}
        click.echo(json.dumps(comparison_data, indent=2))
        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(comparison_data, indent=2))
        return

    # Build comparison table
    table = Table(
        title="Algorithm Comparison",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Metric", style="cyan")
    for algo in algo_list:
        table.add_column(algo.upper(), style="green", justify="right")

    def _total_reroutes(r: Any) -> str:
        return str(sum(m.reroute_count for m in r.results))

    def _avg_loss(r: Any) -> str:
        if not r.results:
            return "0.0%"
        avg = sum(m.packet_loss_rate for m in r.results) / len(r.results)
        return f"{avg:.2%}"

    metrics_rows = [
        ("Total Throughput", lambda r: f"{r.total_throughput():.0f}"),
        ("Mean Latency (ms)", lambda r: f"{r.mean_latency():.2f}"),
        ("Avg Packet Loss Rate", _avg_loss),
        ("Total Reroutes", _total_reroutes),
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

    # Save comparison if requested
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        comparison_data: dict[str, Any] = {}
        for algo in algo_list:
            r = results[algo]
            if r is not None:
                res_data = _get_sim_result_data(r, algo, run_config)
                comparison_data[algo] = {
                    "total_throughput": res_data["total_throughput"],
                    "mean_latency": res_data["mean_latency"],
                    "avg_packet_loss_rate": res_data["avg_packet_loss_rate"],
                    "total_reroutes": res_data["total_reroutes"],
                }
            else:
                comparison_data[algo] = {"error": "simulation_failed"}
        out_path.write_text(json.dumps(comparison_data, indent=2))
        console.print(f"\n[green]+[/green] Comparison saved to [bold]{out_path}[/bold]")

    console.print()


def _print_simulation_results(result: Any, algorithm: str) -> None:
    """Print simulation results as a Rich table."""
    console.print()
    console.rule("[bold cyan]Simulation Results[/bold cyan]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")

    total_reroutes = sum(m.reroute_count for m in result.results)
    avg_loss = (
        sum(m.packet_loss_rate for m in result.results) / len(result.results)
        if result.results
        else 0.0
    )

    table.add_row("Algorithm", algorithm.upper())
    table.add_row("Total Throughput", f"{result.total_throughput():.0f} Mbps")
    table.add_row("Mean Latency", f"{result.mean_latency():.2f} ms")
    table.add_row("Avg Packet Loss Rate", f"{avg_loss:.2%}")
    table.add_row("Total Reroutes", str(total_reroutes))
    table.add_row("Ticks Simulated", str(len(result.results)))

    console.print(table)
    console.print()
