"""Metrics collector to aggregate per-tick statistics during network simulations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nroute.core.metrics import MetricsCollectionResult, SimulationMetrics

if TYPE_CHECKING:
    from nroute.core.topology import Topology
    from nroute.core.traffic import FlowRecord


@dataclass(frozen=True)
class SimulationTickData:
    """
    Data representing the state of a simulation at a single tick, used for recording metrics.
    """

    tick: int
    timestamp: float
    tick_duration: float
    topology: Topology
    active_flows_count: int
    completed_flows: list[FlowRecord]
    dropped_flows: list[tuple[FlowRecord, str]]  # (flow, reason)
    reroute_count: int


class MetricsCollector:
    """
    Collects per-tick performance statistics and wraps them in a MetricsCollectionResult.
    """

    def __init__(self) -> None:
        self.results: list[SimulationMetrics] = []

    def record_tick(self, data: SimulationTickData) -> SimulationMetrics:
        """
        Record performance statistics for the current tick.

        Args:
            data: The simulation tick data.
        """
        # 1. Calculate Throughput (Mbps)
        # throughput = (total_bytes * 8) / (tick_duration * 1e6)
        total_bytes_completed = sum(flow.bytes for flow in data.completed_flows)
        throughput = (total_bytes_completed * 8) / (data.tick_duration * 1e6)

        # 2. Calculate average latency (ms)
        # We can calculate the average latency of the completed flows.
        # FlowRecord has a 'duration' attribute which can serve as its latency,
        # or we can compute it from the path latency. Since we want avg flow latency,
        # let's average the 'duration' attribute or paths latency. Let's use flow.duration.
        if data.completed_flows:
            avg_latency = sum(flow.duration * 1000.0 for flow in data.completed_flows) / len(
                data.completed_flows
            )
        else:
            avg_latency = 0.0

        # 3. Calculate packet loss rate (0.0 to 1.0)
        # packet_loss_rate = dropped_packets / (completed_packets + dropped_packets)
        completed_packets = sum(flow.packets for flow in data.completed_flows)
        dropped_packets = sum(flow.packets for flow, _ in data.dropped_flows)
        total_packets = completed_packets + dropped_packets

        packet_loss_rate = dropped_packets / total_packets if total_packets > 0 else 0.0

        # 4. Calculate average link utilization (0.0 to 1.0)
        # Average utilization across all links that are up.
        link_utilizations = []
        for u, v in data.topology.edges:
            try:
                edge_data = data.topology.get_edge(u, v)
                if edge_data.get("status", "up") != "down":
                    link_utilizations.append(float(edge_data.get("utilization", 0.0)))
            except Exception:
                pass

        if link_utilizations:
            avg_utilization = sum(link_utilizations) / len(link_utilizations)
        else:
            avg_utilization = 0.0

        # Clamp metrics to logical boundaries
        avg_utilization = min(1.0, max(0.0, avg_utilization))
        packet_loss_rate = min(1.0, max(0.0, packet_loss_rate))

        metrics = SimulationMetrics(
            tick=data.tick,
            timestamp=data.timestamp,
            throughput=throughput,
            avg_latency=avg_latency,
            packet_loss_rate=packet_loss_rate,
            avg_utilization=avg_utilization,
            reroute_count=data.reroute_count,
            active_flows=data.active_flows_count,
        )

        self.results.append(metrics)
        return metrics

    def get_results(self) -> MetricsCollectionResult:
        """Return the aggregated collection of metrics."""
        return MetricsCollectionResult(results=self.results)
