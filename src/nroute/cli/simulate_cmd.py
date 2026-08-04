"""CLI subcommands for simulation operations (run, compare)."""

from __future__ import annotations

import inspect
=======
=======
=======
import inspect
=======
import json
from pathlib import Path
from typing import Any

import click
from pydantic import BaseModel, Field
=======
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from nroute.core.topology import Topology
from nroute.exceptions import SimulationError
from nroute.routing import BaseRouter, get_router
from nroute.simulation.engine import SimulationEngine
from nroute.simulation.traffic_gen import TrafficGenerator

console = Console()


class BaseSimulationArgs(BaseModel):
    """Base arguments for simulation commands."""

    topo_path: str
    duration: int
    traffic_model: str
    flows_per_tick: int
    seed: int | None = None
    output: str | None = None
    model_path: str | None = None
    custom_router: str | None = None
    allow_unsafe: bool = False


class SimulationArgs(BaseSimulationArgs):
    """Arguments for the 'run' command."""

    algorithm: str
    visualize: bool = False
    visualize_delay: float = 0.2


class ComparisonArgs(BaseSimulationArgs):
    """Arguments for the 'compare' command."""

    algorithms: str
=======
class SimulationArgs(BaseModel):
    """Arguments for the simulation run command."""

=======
    allow_unsafe: bool
    topo_path: str
    algorithm: str
    duration: int
    traffic_model: str
    flows_per_tick: int
    seed: int | None
    output: str | None
    visualize: bool
    visualize_delay: float
    model_path: str | None
    custom_router: str | None
    allow_unsafe: bool
=======


class ComparisonArgs(BaseModel):
    """Arguments for the simulation compare command."""

=======
    allow_unsafe: bool
    topo_path: str
    algorithms: str
    duration: int
    traffic_model: str
    flows_per_tick: int
    seed: int | None
    output: str | None
    model_path: str | None
    custom_router: str | None
    allow_unsafe: bool
=======


@click.group(name="simulate")
def simulate_cmd() -> None:
    """Run and compare network simulations."""


class SimulationArgs(BaseModel):
    """Arguments for running a simulation."""

    allow_unsafe: bool = Field(default=False, description="Allow loading of unsafe models.")
    topo_path: str = Field(..., description="Path to a topology JSON file.")
    algorithm: str = Field(default="dijkstra", description="Routing algorithm to use.")
    duration: int = Field(default=50, description="Number of simulation ticks.")
    traffic_model: str = Field(default="uniform", description="Traffic generation model.")
    flows_per_tick: int = Field(default=5, description="Number of flows generated per tick.")
    seed: int | None = Field(default=None, description="Random seed for reproducibility.")
    output: str | None = Field(default=None, description="Output path for metrics JSON.")
    visualize: bool = Field(default=False, description="Enable real-time visualization.")
    visualize_delay: float = Field(default=0.2, description="Delay during visualization.")
    model_path: str | None = Field(default=None, description="Path to a pretrained model.")
    custom_router: str | None = Field(default=None, description="Import target for custom router.")
=======
def _load_topology(topo_path: str, is_json: bool) -> Topology:
    """Load topology from path or exit on error."""
    try:
        return Topology.load(topo_path)
    except Exception as e:
        if is_json:
            click.echo(json.dumps({"error": f"Failed to load topology: {e}"}), err=True)
        else:
            console.print(f"[red]x Failed to load topology:[/red] {e}")
=======
def _handle_error(msg: str, is_json: bool, e: Exception | None = None) -> None:
    """Helper to handle errors consistently based on output format."""
    if is_json:
        click.echo(json.dumps({"error": msg}), err=True)
    else:
        console.print(f"[red]x {msg}[/red]")

    if e:
        raise SystemExit(1) from e
    raise SystemExit(1)


def _load_topology(topo_path: str, is_json: bool) -> Topology:
    """Load and return a Topology object."""
    try:
        return Topology.load(topo_path)
    except Exception as e:
        _handle_error(f"Failed to load topology: {e}", is_json, e)
        # Unreachable as _handle_error raises SystemExit
        raise SystemExit(1) from e


def _setup_router(
    algorithm: str,
    topo: Topology,
    allow_unsafe: bool,
    custom_router: str | None = None,
    model_path: str | None = None,
) -> Any:
    """Initialize router and load pretrained model if provided."""
    from nroute.routing.base import BaseRouter

=======
    custom_router: str | None,
    model_path: str | None,
    is_json: bool,
) -> BaseRouter:
    """Initialize router and optionally load a pretrained model."""
    if algorithm.lower() == "custom":
        if not custom_router:
            raise click.UsageError(
                "Option '--custom-router' is required when using algorithm 'custom'."
            )

=======
        from nroute.utils.loader import load_custom_class

        router_cls = load_custom_class(
            custom_router, expected_superclass=BaseRouter, allow_unsafe=allow_unsafe
        )
        sig = inspect.signature(router_cls)
        router = router_cls(topology=topo) if "topology" in sig.parameters else router_cls()
    else:
        router = get_router(algorithm, topology=topo, allow_unsafe=allow_unsafe)
=======
        router_instance = (
            router_cls(topology=topo) if "topology" in sig.parameters else router_cls()
        )
    else:
        router_instance = get_router(algorithm, topology=topo, allow_unsafe=allow_unsafe)

        if not isinstance(router_instance, BaseRouter):
            raise TypeError(f"Initialized class {type(router_instance)} is not a BaseRouter")
        router = router_instance

    # Load pretrained model if provided
    if model_path and hasattr(router, "load"):
        try:

            sig = inspect.signature(router.load)
            if "allow_unsafe" in sig.parameters:
                router.load(model_path, allow_unsafe=allow_unsafe)
            else:
                router.load(model_path)
            console.print(
                f"[green]+[/green] Loaded pretrained model from [bold]{model_path}[/bold]"
            )
        except Exception as e:
            console.print(f"[yellow]! Failed to load model for {algorithm.upper()}:[/yellow] {e}")

    return router


def _get_metrics_summary(
    result: Any, algorithm: str, duration: int, traffic_model: str, seed: int | None
) -> dict[str, Any]:
    """Compute summary metrics from simulation results."""
=======
            if not is_json:
                console.print(
                    f"[green]+[/green] Loaded pretrained model from [bold]{model_path}[/bold]"
                )
        except Exception as e:
            if not is_json:
                console.print(
                    f"[yellow]! Failed to load model for {algorithm.upper()}:[/yellow] {e}"
                )
    return router


def _get_metrics_data(
    result: Any,
    algorithm: str,
    duration: int,
    traffic_model: str,
    seed: int | None,
) -> dict[str, Any]:
    """Compile simulation result metrics into a dictionary."""
    total_reroutes = sum(m.reroute_count for m in result.results)
    avg_loss = (
        sum(m.packet_loss_rate for m in result.results) / len(result.results)
        if result.results
        else 0.0
    )
    return {
        "algorithm": algorithm,
        "duration_ticks": duration,
        "traffic_model": traffic_model,
        "seed": seed,
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


def _save_json_results(
    metrics_data: dict[str, Any], output: str | None = None, echo: bool = True
) -> None:
    """Print metrics as JSON and optionally save to file."""
    if echo:
        click.echo(json.dumps(metrics_data, indent=2))
=======
def _save_json_results(metrics_data: dict[str, Any], output: str | None, echo: bool = True) -> None:
    """Save metrics to JSON file and optionally echo to stdout."""
    json_str = json.dumps(metrics_data, indent=2)
    if echo:
        click.echo(json_str)

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(metrics_data, indent=2))


def _render_comparison_table(results: dict[str, Any], algo_list: list[str]) -> None:
    """Build and print comparison table using Rich."""
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
=======
        out_path.write_text(json_str)
        if not echo:
            console.print(f"[green]+[/green] Metrics saved to [bold]{out_path}[/bold]")

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
    args = SimulationArgs.model_validate(kwargs)
    seed = args.seed or (ctx.obj.get("seed") if ctx.obj is not None else None)
=======
def run_sim(ctx: click.Context, /, **kwargs: Any) -> None:
    """Run a network simulation."""
    args = SimulationArgs(**kwargs)
    seed = args.seed or (ctx.obj.get("seed") if ctx.obj is not None else None)
=======
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"
    seed = args.seed or (ctx.obj.get("seed") if ctx.obj is not None else None)

    topo = _load_topology(topo_path, is_json)

    try:
        router = _setup_router(
            algorithm, topo, allow_unsafe, model_path=model_path, custom_router=custom_router
        )
        traffic_gen = TrafficGenerator(model=traffic_model, n_flows_per_tick=flows_per_tick)
=======
    try:
        topo = Topology.load(args.topo_path)
    except Exception as e:
        if is_json:
            click.echo(json.dumps({"error": f"Failed to load topology: {e}"}), err=True)
            raise SystemExit(1) from e
        console.print(f"[red]x Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e

    try:
        import inspect

        if args.algorithm.lower() == "custom":
            if not args.custom_router:
                raise click.UsageError(
                    "Option '--custom-router' is required when using algorithm 'custom'."
                )

            from nroute.routing.base import BaseRouter
            from nroute.utils.loader import load_custom_class

            router_cls = load_custom_class(
                args.custom_router, expected_superclass=BaseRouter, allow_unsafe=args.allow_unsafe
            )
            sig = inspect.signature(router_cls)
            router = router_cls(topology=topo) if "topology" in sig.parameters else router_cls()
        else:
            router = get_router(args.algorithm, topology=topo, allow_unsafe=args.allow_unsafe)

        # Load pretrained model if provided
        if args.model_path and hasattr(router, "load"):
            try:
                # Some routers might need allow_unsafe passed to load
                sig = inspect.signature(router.load)
                if "allow_unsafe" in sig.parameters:
                    router.load(args.model_path, allow_unsafe=args.allow_unsafe)
                else:
                    router.load(args.model_path)
                console.print(
                    f"[green]+[/green] Loaded pretrained model from [bold]{args.model_path}[/bold]"
                )
            except Exception as e:
                console.print(f"[yellow]! Failed to load model:[/yellow] {e}")

=======
    topo = _load_topology(args.topo_path, is_json)

    try:
        router = _setup_router(
            args.algorithm, topo, args.allow_unsafe, args.custom_router, args.model_path, is_json
=======
            args.algorithm, topo, args.allow_unsafe, args.custom_router, args.model_path
=======
            args.algorithm,
            topo,
            args.allow_unsafe,
            args.custom_router,
            args.model_path,
            is_json,
        )
        traffic_gen = TrafficGenerator(
            model=args.traffic_model, n_flows_per_tick=args.flows_per_tick
        )
        engine = SimulationEngine(topo, router, traffic_gen)

        if args.visualize:
            from nroute.visualization import LiveSimulationConsole

            if not is_json:
                console.print("[cyan]Initializing real-time console visualization...[/cyan]")
            visualizer = LiveSimulationConsole(
                engine=engine,
                duration_ticks=args.duration,
                seed=seed,
                delay=args.visualize_delay,
            )
            result = visualizer.run()
        else:
            console.print(
                f"\n[cyan]Running simulation:[/cyan] {args.algorithm.upper()} on "
                f"{topo.node_count} nodes, {args.duration} ticks, "
                f"{args.traffic_model} traffic ({args.flows_per_tick} flows/tick)\n"
            )
=======
=======
            if not is_json:
                console.print(
                    f"\n[cyan]Running simulation:[/cyan] {args.algorithm.upper()} on "
                    f"{topo.node_count} nodes, {args.duration} ticks, "
                    f"{args.traffic_model} traffic ({args.flows_per_tick} flows/tick)\n"
                )
            result = engine.run(duration_ticks=args.duration, seed=seed)

    except SimulationError as e:
        _handle_error(f"Simulation error: {e}", is_json, e)
    except Exception as e:
        _handle_error(f"Simulation failed: {e}", is_json, e)

    metrics_data = _get_metrics_data(
        result, args.algorithm, args.duration, args.traffic_model, seed
    )

    metrics_data = _get_metrics_summary(
        result, args.algorithm, args.duration, args.traffic_model, seed
    )

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
=======
        total_reroutes = sum(m.reroute_count for m in result.results)
        avg_loss = (
            sum(m.packet_loss_rate for m in result.results) / len(result.results)
            if result.results
            else 0.0
        )
        metrics_data = {
            "algorithm": args.algorithm,
            "duration_ticks": args.duration,
            "traffic_model": args.traffic_model,
            "seed": seed,
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
        click.echo(json.dumps(metrics_data, indent=2))
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(metrics_data, indent=2))
=======
        click.echo(json.dumps(metrics_data, indent=2))
        _save_json_results(metrics_data, args.output)
=======
        _save_json_results(metrics_data, args.output, echo=True)
        return

    # Display results
    _print_simulation_results(result, args.algorithm)

    # Save to file if requested
    if output:
        _save_json_results(output, metrics_data)
        console.print(f"[green]+[/green] Metrics saved to [bold]{output}[/bold]")
=======
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        total_reroutes = sum(m.reroute_count for m in result.results)
        avg_loss = (
            sum(m.packet_loss_rate for m in result.results) / len(result.results)
            if result.results
            else 0.0
        )
        metrics_data = {
            "algorithm": args.algorithm,
            "duration_ticks": args.duration,
            "traffic_model": args.traffic_model,
            "seed": seed,
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
        out_path.write_text(json.dumps(metrics_data, indent=2))
        console.print(f"[green]+[/green] Metrics saved to [bold]{out_path}[/bold]")
=======
        _save_json_results(metrics_data, args.output)
        console.print(f"[green]+[/green] Metrics saved to [bold]{args.output}[/bold]")
=======
        _save_json_results(metrics_data, args.output, echo=False)
        console.print(f"[green]+[/green] Metrics saved to [bold]{args.output}[/bold]")
=======


def _build_comparison_data(results: dict[str, Any], algo_list: list[str]) -> dict[str, Any]:
    """Build comparison data dictionary from algorithm results.

    Args:
        results: Dictionary mapping algorithm names to simulation results.
        algo_list: List of algorithm names that were compared.

    Returns:
        Dictionary with comparison metrics for each algorithm.
    """
    comparison_data: dict[str, Any] = {}
    for algo in algo_list:
        r = results[algo]
        if r is not None:
            total_reroutes = sum(m.reroute_count for m in r.results)
            avg_loss = (
                sum(m.packet_loss_rate for m in r.results) / len(r.results) if r.results else 0.0
            )
            comparison_data[algo] = {
                "total_throughput": r.total_throughput(),
                "mean_latency": r.mean_latency(),
                "avg_packet_loss_rate": avg_loss,
                "total_reroutes": total_reroutes,
            }
        else:
            comparison_data[algo] = {"error": "simulation_failed"}
    return comparison_data


def _run_compare_simulations(
    topo: Topology,
    algo_list: list[str],
    duration: int,
    traffic_model: str,
    flows_per_tick: int,
    seed: int | None,
    allow_unsafe: bool,
    model_path: str | None,
    custom_router: str | None,
) -> dict[str, Any]:
    """Run simulations for each algorithm on the topology."""
    results: dict[str, Any] = {}

    for algo in algo_list:
        try:
            if algo.lower() == "custom":
                if not custom_router:
                    raise click.UsageError(
                        "Option '--custom-router' is required when using algorithm 'custom'."
                    )
                import inspect

                from nroute.routing.base import BaseRouter
                from nroute.utils.loader import load_custom_class

                router_cls = load_custom_class(
                    custom_router, expected_superclass=BaseRouter, allow_unsafe=allow_unsafe
                )
                sig = inspect.signature(router_cls)
                router = router_cls(topology=topo) if "topology" in sig.parameters else router_cls()
            else:
                router = get_router(algo, topology=topo, allow_unsafe=allow_unsafe)

            # Load pretrained model if provided and router supports it
            if model_path and hasattr(router, "load"):
                try:
                    import inspect

                    sig = inspect.signature(router.load)
                    if "allow_unsafe" in sig.parameters:
                        router.load(model_path, allow_unsafe=allow_unsafe)
                    else:
                        router.load(model_path)
                except Exception as e:
                    console.print(
                        f"[yellow]! Failed to load model for {algo.upper()}:[/yellow] {e}"
                    )

            traffic_gen = TrafficGenerator(model=traffic_model, n_flows_per_tick=flows_per_tick)
            engine = SimulationEngine(topo, router, traffic_gen)
            result = engine.run(duration_ticks=duration, seed=seed)
            results[algo] = result
        except Exception as e:
            console.print(f"[yellow]⚠ {algo.upper()} failed:[/yellow] {e}")
            results[algo] = None

    return results


def _print_compare_table(results: dict[str, Any], algo_list: list[str]) -> None:
    """Print the comparison table for the simulation results."""
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


def _save_compare_results(output: str, comparison_data: dict[str, Any]) -> None:
    """Save the comparison metrics to a JSON file."""
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(comparison_data, indent=2))


class ComparisonArgs(BaseModel):
    """Arguments for comparing routing algorithms."""

    allow_unsafe: bool = Field(default=False, description="Allow loading of unsafe models.")
    topo_path: str = Field(..., description="Path to a topology JSON file.")
    algorithms: str = Field(..., description="Comma-separated list of algorithms to compare.")
    duration: int = Field(default=50, description="Number of simulation ticks.")
    traffic_model: str = Field(default="uniform", description="Traffic generation model.")
    flows_per_tick: int = Field(default=5, description="Number of flows generated per tick.")
    seed: int | None = Field(default=None, description="Random seed for reproducibility.")
    output: str | None = Field(default=None, description="Output path for comparison JSON.")
    model_path: str | None = Field(default=None, description="Path to a pretrained model.")
    custom_router: str | None = Field(default=None, description="Import target for custom router.")


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
    args = ComparisonArgs.model_validate(kwargs)
=======
def compare(ctx: click.Context, /, **kwargs: Any) -> None:
    """Compare multiple routing algorithms on the same topology and traffic."""
    args = ComparisonArgs(**kwargs)
    seed = args.seed or (ctx.obj.get("seed") if ctx.obj is not None else None)
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"
    algo_list = [a.strip() for a in args.algorithms.split(",") if a.strip()]

    if len(algo_list) < 2:
        error_msg = "Please provide at least 2 algorithms to compare."
        if is_json:
            msg = {"error": "Please provide at least 2 algorithms to compare."}
            click.echo(json.dumps(msg), err=True)
            raise SystemExit(1) from None
        console.print("[red]x Please provide at least 2 algorithms to compare.[/red]")
=======
            click.echo(json.dumps({"error": error_msg}), err=True)
        else:
            console.print(f"[red]x {error_msg}[/red]")
        raise SystemExit(1) from None

    topo = _load_topology(topo_path, is_json)
=======
    try:
        topo = Topology.load(args.topo_path)
    except Exception as e:
        if is_json:
            click.echo(json.dumps({"error": f"Failed to load topology: {e}"}), err=True)
            raise SystemExit(1) from e
        console.print(f"[red]x Failed to load topology:[/red] {e}")
        raise SystemExit(1) from e
=======
    is_json = ctx.obj is not None and ctx.obj.get("output_format") == "json"
    seed = args.seed or (ctx.obj.get("seed") if ctx.obj is not None else None)
    algo_list = [a.strip() for a in args.algorithms.split(",") if a.strip()]

    if len(algo_list) < 2:
        _handle_error("Please provide at least 2 algorithms to compare.", is_json)

    topo = _load_topology(args.topo_path, is_json)

    if not is_json:
        console.print(
            f"\n[cyan]Comparing algorithms:[/cyan] {', '.join(a.upper() for a in algo_list)}\n"
            f"  Topology: {topo.node_count} nodes, {topo.edge_count} edges\n"
            f"  Duration: {args.duration} ticks | Traffic: {args.traffic_model} ({args.flows_per_tick} flows/tick)\n"

            f"  Duration: {args.duration} ticks | Traffic: {args.traffic_model} "
            f"({args.flows_per_tick} flows/tick)\n"
        )


        results = _run_compare_simulations(
        topo=topo,
        algo_list=algo_list,
        duration=duration,
        traffic_model=traffic_model,
        flows_per_tick=flows_per_tick,
        seed=seed,
        allow_unsafe=allow_unsafe,
        model_path=model_path,
        custom_router=custom_router,
    )
=======
    results: dict[str, Any] = {}
    for algo in algo_list:
        try:
            router = _setup_router(
                algo, topo, allow_unsafe, model_path=model_path, custom_router=custom_router
            )
            traffic_gen = TrafficGenerator(model=traffic_model, n_flows_per_tick=flows_per_tick)
=======
            import inspect

            if algo.lower() == "custom":
                if not args.custom_router:
                    raise click.UsageError(
                        "Option '--custom-router' is required when using algorithm 'custom'."
                    )

                from nroute.routing.base import BaseRouter
                from nroute.utils.loader import load_custom_class

                router_cls = load_custom_class(
                    args.custom_router, expected_superclass=BaseRouter, allow_unsafe=args.allow_unsafe
                )
                sig = inspect.signature(router_cls)
                router = router_cls(topology=topo) if "topology" in sig.parameters else router_cls()
            else:
                router = get_router(algo, topology=topo, allow_unsafe=args.allow_unsafe)

            # Load pretrained model if provided and router supports it
            if args.model_path and hasattr(router, "load"):
                try:
                    sig = inspect.signature(router.load)
                    if "allow_unsafe" in sig.parameters:
                        router.load(args.model_path, allow_unsafe=args.allow_unsafe)
                    else:
                        router.load(args.model_path)
                except Exception as e:
                    console.print(
                        f"[yellow]! Failed to load model for {algo.upper()}:[/yellow] {e}"
                    )
=======
            router = _setup_router(
                algo, topo, args.allow_unsafe, args.custom_router, args.model_path, is_json
=======
                algo, topo, args.allow_unsafe, args.custom_router, args.model_path
            )
=======
                algo,
                topo,
                args.allow_unsafe,
                args.custom_router,
                args.model_path,
                is_json,
            )
            traffic_gen = TrafficGenerator(
                model=args.traffic_model, n_flows_per_tick=args.flows_per_tick
            )
            engine = SimulationEngine(topo, router, traffic_gen)
            result = engine.run(duration_ticks=args.duration, seed=seed)
            results[algo] = result
        except Exception as e:
            if not is_json:
                console.print(f"[yellow]⚠ {algo.upper()} failed:[/yellow] {e}")
            results[algo] = None

    comparison_data: dict[str, Any] = {}
    for algo in algo_list:
        r = results[algo]
        if r is not None:
            comparison_data[algo] = _get_metrics_summary(r)
        else:
            comparison_data[algo] = {"error": "simulation_failed"}
=======
            
    # Build comparison data once using helper function
    comparison_export_data = _build_comparison_data(results, algo_list)

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
=======
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(comparison_data, indent=2))
=======
        click.echo(json.dumps(comparison_export_data, indent=2))
        _save_json_results(comparison_export_data, args.output)
        return

=======
        _save_json_results(comparison_data, args.output, echo=True)
        return

    # Build and print comparison table
    _render_comparison_table(results, algo_list)

    # Save comparison if requested
    if args.output:
        _save_json_results(comparison_export_data, args.output)
        console.print(f"\n[green]+[/green] Comparison saved to [bold]{args.output}[/bold]")

    console.print()


def _load_topology(topo_path: str, is_json: bool) -> Topology:
    """Load topology from file with error handling."""
=======
    """Load topology from JSON file."""
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
=======
    topo: Topology,
    allow_unsafe: bool,
    custom_router: str | None,
    model_path: str | None,
    is_json: bool = False,
) -> Any:
    """Initialize and configure the router."""
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
=======
        router = router_cls(topology=topo) if "topology" in sig.parameters else router_cls()
    else:
        router = get_router(algorithm, topology=topo, allow_unsafe=allow_unsafe)

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
=======
            if not is_json:
                console.print(
                    f"[green]+[/green] Loaded pretrained model for [bold]{algorithm.upper()}[/bold] "
                    f"from [bold]{model_path}[/bold]"
                )
        except Exception as e:
            if not is_json:
                console.print(
                    f"[yellow]! Failed to load model for {algorithm.upper()}:[/yellow] {e}"
                )

    return router


def _get_metrics_summary(result: Any) -> dict[str, Any]:
    """Extract summary metrics from simulation result."""
=======
def _get_metrics_summary(
    result: Any, algorithm: str, duration: int, traffic_model: str, seed: int | None
) -> dict[str, Any]:
    """Build summary metrics dictionary."""
    total_reroutes = sum(m.reroute_count for m in result.results)
    avg_loss = (
        sum(m.packet_loss_rate for m in result.results) / len(result.results)
        if result.results
        else 0.0
    )
    return {
=======
        "algorithm": algorithm,
        "duration_ticks": duration,
        "traffic_model": traffic_model,
        "seed": seed,
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
=======
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


def _save_json_results(metrics_data: dict[str, Any], output: str | None) -> None:
    """Save metrics to a JSON file."""
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(metrics_data, indent=2))


def _render_comparison_table(results: dict[str, Any], algo_list: list[str]) -> None:
    """Render Rich comparison table."""
    table = Table(
        title="Algorithm Comparison",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Metric", style="cyan")
    for algo in algo_list:
        table.add_column(algo.upper(), style="green", justify="right")
=======
        _save_json_results(comparison_data, args.output, echo=False)
        console.print(f"\n[green]+[/green] Comparison saved to [bold]{args.output}[/bold]")
=======

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
=======
      click.echo(json.dumps(comparison_data, indent=2))
        if output:
            _save_compare_results(output, comparison_data)
=======
        _save_json_results(comparison_data, args.output, echo=True)

  return

    _print_compare_table(results, algo_list)


=======
    # Save comparison if requested
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        comparison_dict: dict[str, Any] = {}
=======
        comparison_export_data: dict[str, Any] = {}
=======
        comparison_data_out: dict[str, Any] = {}
        for algo in algo_list:
            r = results[algo]
            if r is not None:
                total_reroutes = sum(m.reroute_count for m in r.results)
                avg_loss = (
                    sum(m.packet_loss_rate for m in r.results) / len(r.results)
                    if r.results
                    else 0.0
                )
                comparison_dict[algo] = {

                comparison_export_data[algo] = {
                comparison_data_out[algo] = {
                    "total_throughput": r.total_throughput(),
                    "mean_latency": r.mean_latency(),
                    "avg_packet_loss_rate": avg_loss,
                    "total_reroutes": total_reroutes,
                }
            else:
                comparison_dict[algo] = {"error": "simulation_failed"}
        out_path.write_text(json.dumps(comparison_dict, indent=2))
=======
                comparison_export_data[algo] = {"error": "simulation_failed"}
        out_path.write_text(json.dumps(comparison_export_data, indent=2))
=======
                comparison_data_out[algo] = {"error": "simulation_failed"}
        out_path.write_text(json.dumps(comparison_data_out, indent=2))
        console.print(f"\n[green]+[/green] Comparison saved to [bold]{out_path}[/bold]")
=======

    if output:
        _save_compare_results(output, comparison_data)
        console.print(f"\n[green]+[/green] Comparison saved to [bold]{output}[/bold]")
=======
    if args.output:
        _save_json_results(comparison_data, args.output, echo=False)

      
    console.print()

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


# Force reformat
