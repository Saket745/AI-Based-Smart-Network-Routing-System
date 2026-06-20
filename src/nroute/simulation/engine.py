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
        self._initialize_run(duration_ticks, seed)

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
                self._run_tick(tick, tick_duration, callback)

                if progress is not None and task is not None:
                    progress.update(task, advance=1)
        finally:
            if progress is not None:
                progress.stop()

        results = self.collector.get_results()
        logger.info(
            "Simulation completed successfully",
            total_throughput=results.total_throughput(),
            mean_latency=results.mean_latency(),
        )

        return results

    def _initialize_run(self, duration_ticks: int, seed: int | None) -> None:
        """Prepare engine state for a new simulation run."""
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

    def _run_tick(
        self,
        tick: int,
        tick_duration: float,
        callback: Callable[[int, SimulationEngine], None] | None = None,
    ) -> None:
        """Execute a single simulation tick."""
        timestamp = tick * tick_duration

        # 1. Apply failures scheduled for this tick
        if self.failure_injector is not None:
            self.failure_injector.apply(self.topology, tick)

        # 2. Update Link Utilizations based on current active flows
        self._update_link_utilizations()

        # 3. Generate new traffic flows
        new_flows = self.traffic_generator.generate(self.topology, tick)

        # 4. Route new flows and add them to active flows
        completed_flows: list[FlowRecord] = []
        dropped_flows: list[tuple[FlowRecord, str]] = []

        self._route_new_flows(new_flows, dropped_flows)

        # 5. Forward active/in-flight flows
        reroute_count = self._forward_active_flows(completed_flows, dropped_flows)

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

        if callback is not None:
            callback(tick, self)

    def _forward_active_flows(
        self,
        completed_flows: list[FlowRecord],
        dropped_flows: list[tuple[FlowRecord, str]],
    ) -> int:
        """
        Advance active flows one hop, handle failures and rerouting.

        Args:
            completed_flows: List to append flows that reach their destination.
            dropped_flows: List to append flows dropped due to loss or routing failures.

        Returns:
            Number of rerouting events triggered.
        """
        still_active: list[dict[str, Any]] = []
        reroute_count = 0

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
            if self._is_path_blocked(u, v):
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
        return reroute_count

    def _is_path_blocked(self, u: str, v: str) -> bool:
        """Check if the edge u->v or node v is down."""
        try:
            edge_data = self.topology.get_edge(u, v)
            if edge_data.get("status", "up") == "down":
                return True
        except Exception:
            return True

        try:
            node_data = self.topology.get_node(v)
            if node_data.get("status", "up") == "down":
                return True
        except Exception:
            return True

        return False

    def _route_new_flows(
        self, new_flows: list[FlowRecord], dropped_flows: list[tuple[FlowRecord, str]]
    ) -> None:
        """
        Route new flows and add them to active flows.

        Args:
            new_flows: List of new FlowRecords to route.
            dropped_flows: List to append flows that fail at ingress.
        """
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

    def _update_link_utilizations(self) -> None:
        """
        Recalculate link utilization metrics based on current active flows.
        """
        # 1. Reset all edges to 0 utilization
        for u, v in self.topology.edges:
            self.topology.update_edge(u, v, utilization=0.0)

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
