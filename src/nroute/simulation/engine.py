"""Discrete-event simulation engine for simulating traffic and topology events."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from rich.progress import Progress

from nroute.simulation.collector import MetricsCollector
from nroute.utils.logging import get_logger
from nroute.utils.random import get_rng

if TYPE_CHECKING:
    from collections.abc import Callable

    from nroute.core.metrics import MetricsCollectionResult
    from nroute.core.topology import Topology
    from nroute.core.traffic import FlowRecord
    from nroute.routing.base import BaseRouter
    from nroute.simulation.failure_injector import FailureInjector
    from nroute.simulation.traffic_gen import TrafficGenerator

logger = get_logger(__name__)


class SimulationEngine:
    """
    Runs discrete-event loops simulating dynamic network traffic, link failures,
    and routing performance over time.
    """

    def __init__(
        self,
        topology: Topology,
        router: BaseRouter,
        traffic_generator: TrafficGenerator,
        failure_injector: FailureInjector | None = None,
        config: Any = None,
    ) -> None:
        """
        Initialize the SimulationEngine.

        Args:
            topology: The network topology (will be copied to avoid mutating the original).
            router: A BaseRouter implementation.
            traffic_generator: A TrafficGenerator instance.
            failure_injector: Optional FailureInjector scheduling link/node events.
            config: Optional NRouteConfig instance.
        """
        self.topology = topology.copy()
        self.router = router
        self.traffic_generator = traffic_generator
        self.failure_injector = failure_injector
        self.config = config

        self.collector = MetricsCollector()
        self.rng = get_rng()

        # List of active flows in-flight
        # Each flow dict has keys:
        # - "flow": FlowRecord
        # - "path": list[str]
        # - "current_hop_idx": int
        # - "accumulated_latency": float
        self.active_flows: list[dict[str, Any]] = []

    def run(
        self,
        duration_ticks: int,
        seed: int | None = None,
        callback: Callable[[int, SimulationEngine], None] | None = None,
        show_progress: bool = True,
    ) -> MetricsCollectionResult:
        """
        Run the simulation for a specified number of ticks.

        Args:
            duration_ticks: Total number of ticks to simulate.
            seed: Optional random seed for reproducibility.
            callback: Optional callback invoked after each tick.
            show_progress: Whether to show the default Rich progress bar.

        Returns:
            A MetricsCollectionResult containing chronological performance metrics.
        """
        self.rng = get_rng(seed)
        self.traffic_generator.set_seed(seed)

        # Reset collector and active flows
        self.collector = MetricsCollector()
        self.active_flows = []

        logger.info(
            "Starting network simulation",
            ticks=duration_ticks,
            nodes=self.topology.node_count,
            edges=self.topology.edge_count,
            router=self.router.__class__.__name__,
            traffic_model=self.traffic_generator.model,
        )

        tick_duration = 1.0  # default tick duration in seconds
        if self.config is not None and hasattr(self.config, "simulation"):
            tick_duration = getattr(self.config.simulation, "tick_duration", 1.0)

        # Use rich progress bar for visibility if requested
        if show_progress:
            progress = Progress(transient=True)
            progress.start()
            task = progress.add_task("[cyan]Running Simulation...", total=duration_ticks)
        else:
            progress = None
            task = None

        try:
            for tick in range(duration_ticks):
                timestamp = tick * tick_duration
                self._run_tick(tick, timestamp, tick_duration)

                if callback is not None:
                    callback(tick, self)

                if progress is not None and task is not None:
                    progress.update(task, advance=1)
        finally:
            if progress is not None:
                progress.stop()

        logger.info(
            "Simulation completed successfully",
            total_throughput=self.collector.get_results().total_throughput(),
            mean_latency=self.collector.get_results().mean_latency(),
        )

        return self.collector.get_results()

    def _run_tick(self, tick: int, timestamp: float, tick_duration: float) -> None:
        """Process a single simulation tick."""
        # 1. Apply failures scheduled for this tick
        if self.failure_injector is not None:
            self.failure_injector.apply(self.topology, tick)

        # 2. Update Link Utilizations based on current active flows
        self._update_link_utilizations()

        # 3. Generate new traffic flows
        new_flows = self.traffic_generator.generate(self.topology, tick)

        # 4. Route new flows and add them to active flows
        dropped_flows = self._route_new_flows(new_flows)

        # 5. Forward active/in-flight flows
        completed_flows, active_dropped, reroute_count = self._forward_active_flows()
        dropped_flows.extend(active_dropped)

        # 6. Record tick metrics
        self.collector.record_tick(
            tick=tick,
            timestamp=timestamp,
            tick_duration=tick_duration,
            topology=self.topology,
            active_flows_count=len(self.active_flows),
            completed_flows=completed_flows,
            dropped_flows=dropped_flows,
            reroute_count=reroute_count,
        )

        # Store temporary attributes for dynamic event logging in callbacks
        self.last_tick_completed_flows = completed_flows
        self.last_tick_dropped_flows = dropped_flows
        self.last_tick_reroute_count = reroute_count

    def _route_new_flows(self, new_flows: list[FlowRecord]) -> list[tuple[FlowRecord, str]]:
        """Compute initial paths for new flows and add them to the active pool."""
        dropped_flows: list[tuple[FlowRecord, str]] = []
        for flow in new_flows:
            try:
                # Compute path using router
                path = self.router.compute_path(self.topology, flow.source, flow.destination)
                self.active_flows.append(
                    {
                        "flow": flow,
                        "path": path,
                        "current_hop_idx": 0,
                        "accumulated_latency": 0.0,
                    }
                )
            except Exception as e:
                # Dropped at ingress: no route found
                dropped_flows.append((flow, f"routing_failed_ingress: {e}"))
        return dropped_flows

    def _forward_active_flows(self) -> tuple[list[FlowRecord], list[tuple[FlowRecord, str]], int]:
        """Advance all active flows by one hop, handling failures and rerouting."""
        completed_flows: list[FlowRecord] = []
        dropped_flows: list[tuple[FlowRecord, str]] = []
        reroute_count = 0
        still_active: list[dict[str, Any]] = []

        for state in self.active_flows:
            flow = state["flow"]
            path = state["path"]
            hop_idx = state["current_hop_idx"]

            # Ensure path is valid and not completed
            if hop_idx >= len(path) - 1:
                completed_flows.append(flow)
                continue

            u = path[hop_idx]
            v = path[hop_idx + 1]

            # Check if the edge or target node is down
            if self._is_path_obstructed(u, v):
                # Link goes down mid-flow: trigger rerouting from current node
                try:
                    new_path = self.router.compute_path(self.topology, u, flow.destination)
                    state["path"] = new_path
                    state["current_hop_idx"] = 0
                    path = new_path
                    hop_idx = 0
                    u = path[hop_idx]
                    v = path[hop_idx + 1]
                    reroute_count += 1
                except Exception as e:
                    # Rerouting failed: flow dropped
                    dropped_flows.append((flow, f"rerouting_failed_midflow: {e}"))
                    continue

            # Forward across edge u -> v
            try:
                edge_data = self.topology.get_edge(u, v)
                loss_prob = float(edge_data.get("packet_loss", 0.0))
                edge_latency = float(edge_data.get("latency", 5.0))
            except Exception:
                loss_prob = 0.0
                edge_latency = 5.0

            # Apply packet loss probabilistically
            if self.rng.random_float() < loss_prob:
                dropped_flows.append((flow, "packet_loss_drop"))
                continue

            # Accumulate latency and advance hop
            state["accumulated_latency"] += edge_latency
            state["current_hop_idx"] += 1

            # Check if reached destination
            if state["current_hop_idx"] >= len(path) - 1:
                # Set actual accumulated duration
                flow.duration = state["accumulated_latency"] / 1000.0
                completed_flows.append(flow)
            else:
                still_active.append(state)

        self.active_flows = still_active
        return completed_flows, dropped_flows, reroute_count

    def _is_path_obstructed(self, u: str, v: str) -> bool:
        """Check if the edge u->v or node v is currently down."""
        edge_down = False
        try:
            edge_data = self.topology.get_edge(u, v)
            edge_down = edge_data.get("status", "up") == "down"
        except Exception:
            edge_down = True

        if edge_down:
            return True

        node_down = False
        try:
            node_data = self.topology.get_node(v)
            node_down = node_data.get("status", "up") == "down"
        except Exception:
            node_down = True

        return node_down

    def _update_link_utilizations(self) -> None:
        """
        Recalculate link utilization metrics based on current active flows.
        """
        # 1. Reset all edges to 0 utilization directly in networkx graph for performance
        g = self.topology.graph
        for u, v in g.edges:
            g.edges[u, v]["utilization"] = 0.0

        # 2. Accumulate bandwidth demands of in-flight flows on their active link
        # Flow bandwidth demand = (bytes * 8) / (duration * 1e6) in Mbps.
        # If duration is 0, default to 1s.
        link_demands: dict[tuple[str, str], float] = defaultdict(float)

        for state in self.active_flows:
            flow = state["flow"]
            path = state["path"]
            hop_idx = state["current_hop_idx"]

            if hop_idx < len(path) - 1:
                u = path[hop_idx]
                v = path[hop_idx + 1]
                duration = flow.duration if flow.duration > 0.0 else 1.0
                mbps = (flow.bytes * 8.0) / (duration * 1e6)
                link_demands[(u, v)] += mbps

        # 3. Update edge utilization ratios in topology
        for (u, v), demand in link_demands.items():
            try:
                edge_data = self.topology.get_edge(u, v)
                bandwidth = float(edge_data.get("bandwidth", 1000.0))
                util = demand / bandwidth if bandwidth > 0.0 else 0.0
                # Clamp to [0.0, 1.0] for topology validation rules
                util = min(1.0, max(0.0, util))
                self.topology.update_edge(u, v, utilization=util)
            except Exception:
                pass
