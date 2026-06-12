"""Real-time console visualization using Rich Live and Plotext for nroute simulations."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import plotext as plt
from rich.ansi import AnsiDecoder
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from nroute.core.metrics import MetricsCollectionResult
    from nroute.simulation.engine import SimulationEngine


class PlotextRenderable:
    """Rich renderable wrapper for Plotext plots to insert them into Rich panels."""

    def __init__(self, plot_func: Any) -> None:
        self.plot_func = plot_func

    def __rich_console__(self, console: Console, options: Any) -> Any:
        width = options.max_width
        # Default to height of 10 if not specified
        height = options.height or 10

        plt.clf()
        plt.plotsize(width, height)
        plt.theme("dark")

        self.plot_func(plt)

        ansi_output = plt.build()
        decoder = AnsiDecoder()
        yield from decoder.decode(ansi_output)


class LiveSimulationConsole:
    """Manages full-screen CLI visualizer updating live as the simulation progresses."""

    def __init__(
        self,
        engine: SimulationEngine,
        duration_ticks: int,
        seed: int | None = None,
        delay: float = 0.2,
    ) -> None:
        self.engine = engine
        self.duration_ticks = duration_ticks
        self.seed = seed
        self.delay = delay

        self.console = Console()
        self.event_log: list[str] = []
        self.prev_down_links: set[tuple[str, str]] = set()
        self.prev_down_nodes: set[str] = set()

        # History for plotting
        self.ticks_history: list[int] = []
        self.throughput_history: list[float] = []
        self.latency_history: list[float] = []

    def log_event(self, text: str) -> None:
        """Log a formatted simulation event with a timestamp."""
        timestamp = time.strftime("%H:%M:%S")
        self.event_log.append(f"[{timestamp}] {text}")
        if len(self.event_log) > 50:
            self.event_log.pop(0)

    def update_events(self, tick: int) -> None:
        """Inspect engine state and log node/link status changes and packet events."""
        # 1. Check for topology status changes (links & nodes going down/up)
        current_down_links = set()
        for u, v in self.engine.topology.edges:
            try:
                edge_data = self.engine.topology.get_edge(u, v)
                if edge_data.get("status") == "down":
                    current_down_links.add((u, v))
            except Exception:
                pass

        current_down_nodes = set()
        for node in self.engine.topology.nodes:
            try:
                node_data = self.engine.topology.get_node(node)
                if node_data.get("status") == "down":
                    current_down_nodes.add(node)
            except Exception:
                pass

        # Links going down
        for u, v in (current_down_links - self.prev_down_links):
            self.log_event(f"[bold red]⚠ Link {u} ➔ {v} went DOWN![/bold red]")
        # Links recovering
        for u, v in (self.prev_down_links - current_down_links):
            self.log_event(f"[bold green]✓ Link {u} ➔ {v} recovered (UP)[/bold green]")

        # Nodes going down
        for node in (current_down_nodes - self.prev_down_nodes):
            self.log_event(f"[bold red]⚠ Node {node} went DOWN![/bold red]")
        # Nodes recovering
        for node in (self.prev_down_nodes - current_down_nodes):
            self.log_event(f"[bold green]✓ Node {node} recovered (UP)[/bold green]")

        self.prev_down_links = current_down_links
        self.prev_down_nodes = current_down_nodes

        # 2. Check for completions, drops, reroutes
        completed = getattr(self.engine, "last_tick_completed_flows", [])
        dropped = getattr(self.engine, "last_tick_dropped_flows", [])
        reroutes = getattr(self.engine, "last_tick_reroute_count", 0)

        for flow in completed:
            self.log_event(
                f"[green]✔ Flow {flow.source} ➔ {flow.destination} completed[/green] "
                f"({flow.bytes / 1e3:.1f} KB, {flow.duration * 1000.0:.1f}ms)"
            )

        for flow, reason in dropped:
            self.log_event(
                f"[red]❌ Flow {flow.source} ➔ {flow.destination} DROPPED[/red] "
                f"(Reason: {reason})"
            )

        if reroutes > 0:
            self.log_event(
                f"[yellow]⚡ Mid-flow rerouting triggered for {reroutes} flow(s)[/yellow]"
            )

    def plot_throughput(self, plt_ctx: Any) -> None:
        """Plot throughput history in plotext context."""
        if not self.ticks_history:
            plt_ctx.title("Throughput (Mbps) over time")
            return
        plt_ctx.plot(self.ticks_history, self.throughput_history, color="cyan")
        plt_ctx.title("Throughput (Mbps)")
        plt_ctx.grid(True)

    def plot_latency(self, plt_ctx: Any) -> None:
        """Plot average latency history in plotext context."""
        if not self.ticks_history:
            plt_ctx.title("Avg Latency (ms) over time")
            return
        plt_ctx.plot(self.ticks_history, self.latency_history, color="gold")
        plt_ctx.title("Average Latency (ms)")
        plt_ctx.grid(True)

    def run(self) -> MetricsCollectionResult:
        """Run the simulation while displaying the live console interface."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=8),
        )
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )
        layout["right"].split_column(
            Layout(name="throughput_plot", ratio=1),
            Layout(name="latency_plot", ratio=1),
        )

        algo_name = self.engine.router.__class__.__name__

        def tick_callback(tick: int, engine: SimulationEngine) -> None:
            # Update history
            last_metric = engine.collector.results[-1]
            self.ticks_history.append(tick)
            self.throughput_history.append(last_metric.throughput)
            self.latency_history.append(last_metric.avg_latency)

            # Update event log
            self.update_events(tick)

            # Build elements for render
            # Header
            header_text = Text.assemble(
                ("nroute LIVE SIMULATION CONSOLE", "bold cyan"),
                ("  |  Algorithm: ", "white"),
                (algo_name, "bold green"),
                ("  |  Tick: ", "white"),
                (f"{tick + 1}/{self.duration_ticks}", "bold yellow"),
                ("  |  Active Flows: ", "white"),
                (str(last_metric.active_flows), "bold magenta"),
            )
            layout["header"].update(Panel(header_text, style="cyan"))

            # Left Panel: Link Status Table
            table = Table(
                title="Link Status & Utilization",
                show_header=True,
                header_style="bold magenta",
                expand=True,
            )
            table.add_column("Link (U ➔ V)", style="cyan")
            table.add_column("Status", justify="center")
            table.add_column("Bandwidth", justify="right")
            table.add_column("Latency", justify="right")
            table.add_column("Utilization", justify="right")

            # Sort edges for stable rendering
            sorted_edges = sorted(engine.topology.edges)
            for u, v in sorted_edges:
                edge_data = engine.topology.get_edge(u, v)
                status = str(edge_data.get("status", "up")).upper()
                if status == "DOWN":
                    status_str = "[bold red]🔴 DOWN[/bold red]"
                else:
                    status_str = "[bold green]🟢 UP[/bold green]"

                bw = f"{edge_data.get('bandwidth', 1000):.0f} Mbps"
                lat = f"{edge_data.get('latency', 5):.1f} ms"
                util = float(edge_data.get("utilization", 0.0))

                # Color coding based on utilization
                if status == "DOWN":
                    util_str = "[grey]--[/grey]"
                elif util > 0.85:
                    util_str = f"[bold red]{util:.1%}[/bold red] 🔴"
                elif util > 0.60:
                    util_str = f"[bold yellow]{util:.1%}[/bold yellow] 🟡"
                else:
                    util_str = f"[bold green]{util:.1%}[/bold green] 🟢"

                table.add_row(f"{u} ➔ {v}", status_str, bw, lat, util_str)

            layout["left"].update(Panel(table, style="magenta"))

            # Right Panel: Plots
            layout["right"]["throughput_plot"].update(
                Panel(PlotextRenderable(self.plot_throughput), style="cyan")
            )
            layout["right"]["latency_plot"].update(
                Panel(PlotextRenderable(self.plot_latency), style="gold")
            )

            # Footer: Event Log
            events_to_show = self.event_log[-5:] if self.event_log else ["No events yet."]
            footer_text = Text("\n".join(events_to_show))
            layout["footer"].update(Panel(footer_text, title="Real-Time Event Log", style="white"))

            # Force sleep to pace the visualization
            time.sleep(self.delay)

        # Start live context
        with Live(layout, refresh_per_second=10, screen=True):
            self.log_event("[bold cyan]Simulation started[/bold cyan]")
            result = self.engine.run(
                duration_ticks=self.duration_ticks,
                seed=self.seed,
                callback=tick_callback,
                show_progress=False,  # Turn off standard progress bar
            )
            self.log_event("[bold green]Simulation completed[/bold green]")
            # Sleep a tiny bit at the end so the user can see the final state
            time.sleep(1.0)

        return result
