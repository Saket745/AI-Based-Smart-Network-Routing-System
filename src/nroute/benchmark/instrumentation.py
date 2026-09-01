"""High-precision metrics, timing, and fallback instrumentation for benchmarking."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import networkx as nx
import numpy as np

from nroute.routing.base import BaseRouter

if TYPE_CHECKING:
    from nroute.core.topology import Topology
    from nroute.simulation.engine import SimulationEngine


@dataclass
class QueryRecord:
    """Detailed telemetry recorded for a single routing query."""

    source: str
    destination: str
    path: list[str]
    total_latency_us: float
    predict_or_env_us: float
    path_solve_us: float
    route_source: str  # "classical_baseline" | "native_policy" | "fallback"
    fallback_reason: str | None = None


class InstrumentedRouter(BaseRouter):
    """
    Wrapper around any BaseRouter that captures per-query execution timings
    and non-invasively intercepts fallback activations for explicit provenance tracking.
    """

    def __init__(self, inner_router: BaseRouter) -> None:
        super().__init__()
        self.inner_router = inner_router
        self.query_records: list[QueryRecord] = []
        self.fallback_count = 0
        self.total_queries = 0

        # Hook fallback mechanism if router has one
        self._is_ai_router = hasattr(inner_router, "_cascade_fallback")
        self._last_fallback_triggered = False
        self._last_fallback_reason: str | None = None

        if self._is_ai_router:
            self._original_fallback = getattr(inner_router, "_cascade_fallback", None)

            def hooked_fallback(
                topology: Topology,
                source: str,
                destination: str,
                weight: Any = None,
                **kwargs: Any,
            ) -> list[str]:
                self._last_fallback_triggered = True
                self._last_fallback_reason = kwargs.get(
                    "reason", "policy_fallback_or_low_confidence"
                )
                if self._original_fallback is not None:
                    res = self._original_fallback(
                        topology, source, destination, weight=weight, **kwargs
                    )
                    return list(res)
                return []

            # Bind hook to inner instance
            object.__setattr__(inner_router, "_cascade_fallback", hooked_fallback)

    def reset_stats(self) -> None:
        """Reset query records and counters."""
        self.query_records.clear()
        self.fallback_count = 0
        self.total_queries = 0

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: Any = None,
        **kwargs: Any,
    ) -> list[str]:
        """Compute path while profiling execution stages and tracking provenance."""
        self._last_fallback_triggered = False
        self._last_fallback_reason = None
        self.total_queries += 1

        t_start = time.perf_counter_ns()

        # Track model-specific preprocessing if available
        if hasattr(self.inner_router, "_timing_last_env_construct_ns"):
            object.__setattr__(self.inner_router, "_timing_last_env_construct_ns", 0.0)

        path = self.inner_router.compute_path(
            topology, source, destination, weight=weight, **kwargs
        )
        t_end = time.perf_counter_ns()

        total_us = (t_end - t_start) / 1000.0

        # Determine route provenance
        if not self._is_ai_router:
            route_source = "classical_baseline"
            fallback_reason = None
        elif self._last_fallback_triggered:
            route_source = "fallback"
            fallback_reason = self._last_fallback_reason or "cascade_fallback"
            self.fallback_count += 1
        else:
            route_source = "native_policy"
            fallback_reason = None

        # Extract environment or prediction stage time if available
        env_ns = float(getattr(self.inner_router, "_timing_last_env_construct_ns", 0.0))
        predict_or_env_us = env_ns / 1000.0
        path_solve_us = max(0.0, total_us - predict_or_env_us)

        record = QueryRecord(
            source=source,
            destination=destination,
            path=path,
            total_latency_us=total_us,
            predict_or_env_us=predict_or_env_us,
            path_solve_us=path_solve_us,
            route_source=route_source,
            fallback_reason=fallback_reason,
        )
        self.query_records.append(record)
        return path

    @property
    def fallback_ratio(self) -> float:
        """Ratio of queries that fell back to classical heuristics."""
        return self.fallback_count / self.total_queries if self.total_queries > 0 else 0.0


class PilotMetricsRecorder:
    """
    Non-invasive observer hooked into SimulationEngine callbacks.
    Computes P95/P99 latency, path stretch, Jain fairness, route churn, and recovery time.
    """

    def __init__(
        self,
        base_topology: Topology,
        failure_tick: int | None = None,
        recovery_tick: int | None = None,
    ) -> None:
        self.base_topology = base_topology
        self.failure_tick = failure_tick
        self.recovery_tick = recovery_tick

        # Flow duration tracking (ms)
        self.completed_flow_durations: list[float] = []
        self.flow_stretches: list[float] = []

        # Per-tick network health
        self.tick_throughputs: list[float] = []
        self.tick_loss_rates: list[float] = []
        self.tick_jain_indices: list[float] = []
        self.tick_peak_utils: list[float] = []
        self.tick_avg_utils: list[float] = []

        # Route churn tracking: map (src, dst) -> most recent path
        self._pair_last_paths: dict[tuple[str, str], list[str]] = {}
        self.tick_churn_counts: list[int] = []

        # Precompute static unweighted shortest path distances on clean base graph
        self._static_shortest_hops: dict[tuple[str, str], int] = {}
        self._precompute_base_shortest_hops()

    def _precompute_base_shortest_hops(self) -> None:
        """Precompute unweighted shortest physical path hop count for all pairs."""
        g = self.base_topology.graph
        for src in g.nodes:
            try:
                lengths = nx.single_source_shortest_path_length(g, src)
                for dst, hops in lengths.items():
                    self._static_shortest_hops[(src, dst)] = hops
            except Exception:
                pass

    def on_tick(self, tick: int, engine: SimulationEngine) -> None:
        """Callback invoked by SimulationEngine at the end of each tick."""
        # 1. Process completed flows
        completed = getattr(engine, "last_tick_completed_flows", [])
        for flow in completed:
            dur_ms = flow.duration * 1000.0
            self.completed_flow_durations.append(dur_ms)

        # 2. Extract path stretch for active/completed flows
        for state in engine.active_flows:
            flow = state.get("flow")
            path = state.get("path")
            if flow and path and len(path) > 1:
                src, dst = flow.source, flow.destination
                base_hops = self._static_shortest_hops.get((src, dst), len(path) - 1)
                base_hops = max(1, base_hops)
                actual_hops = max(1, len(path) - 1)
                stretch = actual_hops / base_hops
                self.flow_stretches.append(stretch)

                # Track route churn
                pair = (src, dst)
                prev_path = self._pair_last_paths.get(pair)
                if prev_path is not None and prev_path != path:
                    self.tick_churn_counts.append(1)
                else:
                    self.tick_churn_counts.append(0)
                self._pair_last_paths[pair] = list(path)

        # 3. Compute Jain's Fairness Index on active link utilizations
        link_utils = []
        for _, _, d in engine.topology.graph.edges(data=True):
            if d.get("status", "up") != "down":
                link_utils.append(float(d.get("utilization", 0.0)))

        if link_utils:
            peak_u = max(link_utils)
            avg_u = sum(link_utils) / len(link_utils)
            u_arr = np.array(link_utils, dtype=np.float64)
            sum_u = u_arr.sum()
            sum_u2 = (u_arr**2).sum()
            n = len(u_arr)
            jain = (sum_u**2) / (n * sum_u2) if sum_u2 > 0 else 1.0
        else:
            peak_u, avg_u, jain = 0.0, 0.0, 1.0

        self.tick_peak_utils.append(peak_u)
        self.tick_avg_utils.append(avg_u)
        self.tick_jain_indices.append(jain)

        # 4. Tick throughput and loss
        if engine.collector.results:
            last_metric = engine.collector.results[-1]
            self.tick_throughputs.append(last_metric.throughput)
            self.tick_loss_rates.append(last_metric.packet_loss_rate)
        else:
            self.tick_throughputs.append(0.0)
            self.tick_loss_rates.append(0.0)

    def compute_recovery_time_ticks(self) -> int | None:
        """Compute ticks to recover >= 90% of pre-failure throughput baseline."""
        if self.failure_tick is None or not self.tick_throughputs:
            return None

        # Pre-failure baseline (mean throughput over 5 ticks before failure)
        pre_start = max(0, self.failure_tick - 5)
        pre_slice = self.tick_throughputs[pre_start : self.failure_tick]
        if not pre_slice:
            return None
        pre_baseline = sum(pre_slice) / len(pre_slice)
        if pre_baseline <= 0.0:
            return None

        target = 0.90 * pre_baseline
        # Check recovery after failure tick
        for offset, val in enumerate(self.tick_throughputs[self.failure_tick :]):
            if val >= target:
                return offset
        return len(self.tick_throughputs) - self.failure_tick

    def compute_summary(self, router_instrument: InstrumentedRouter) -> dict[str, Any]:
        """Aggregate all collected metrics into a structured summary dictionary."""
        durations = self.completed_flow_durations
        stretches = self.flow_stretches

        p50_lat = float(np.percentile(durations, 50)) if durations else 0.0
        p90_lat = float(np.percentile(durations, 90)) if durations else 0.0
        p95_lat = float(np.percentile(durations, 95)) if durations else 0.0
        p99_lat = float(np.percentile(durations, 99)) if durations else 0.0
        mean_lat = float(np.mean(durations)) if durations else 0.0

        mean_stretch = float(np.mean(stretches)) if stretches else 1.0
        max_stretch = float(np.max(stretches)) if stretches else 1.0

        mean_jain = float(np.mean(self.tick_jain_indices)) if self.tick_jain_indices else 1.0
        mean_peak_u = float(np.mean(self.tick_peak_utils)) if self.tick_peak_utils else 0.0
        max_peak_u = float(np.max(self.tick_peak_utils)) if self.tick_peak_utils else 0.0

        mean_throughput = float(np.mean(self.tick_throughputs)) if self.tick_throughputs else 0.0
        total_throughput = float(np.sum(self.tick_throughputs)) if self.tick_throughputs else 0.0
        mean_loss = float(np.mean(self.tick_loss_rates)) if self.tick_loss_rates else 0.0

        total_churn = sum(self.tick_churn_counts)
        churn_rate = total_churn / len(self.tick_churn_counts) if self.tick_churn_counts else 0.0

        recovery_ticks = self.compute_recovery_time_ticks()

        # Compute router timings
        compute_times = [r.total_latency_us for r in router_instrument.query_records]
        env_times = [r.predict_or_env_us for r in router_instrument.query_records]
        solve_times = [r.path_solve_us for r in router_instrument.query_records]

        mean_compute_us = float(np.mean(compute_times)) if compute_times else 0.0
        p95_compute_us = float(np.percentile(compute_times, 95)) if compute_times else 0.0
        mean_env_us = float(np.mean(env_times)) if env_times else 0.0
        mean_solve_us = float(np.mean(solve_times)) if solve_times else 0.0

        return {
            "total_completed_flows": len(durations),
            "mean_latency_ms": mean_lat,
            "p50_latency_ms": p50_lat,
            "p90_latency_ms": p90_lat,
            "p95_latency_ms": p95_lat,
            "p99_latency_ms": p99_lat,
            "mean_throughput_mbps": mean_throughput,
            "total_throughput_mbps": total_throughput,
            "packet_loss_rate": mean_loss,
            "mean_jain_fairness": mean_jain,
            "mean_peak_utilization": mean_peak_u,
            "max_peak_utilization": max_peak_u,
            "mean_path_stretch": mean_stretch,
            "max_path_stretch": max_stretch,
            "route_churn_rate": churn_rate,
            "recovery_time_ticks": recovery_ticks,
            "total_queries": router_instrument.total_queries,
            "fallback_count": router_instrument.fallback_count,
            "fallback_ratio": router_instrument.fallback_ratio,
            "mean_compute_latency_us": mean_compute_us,
            "p95_compute_latency_us": p95_compute_us,
            "mean_env_overhead_us": mean_env_us,
            "mean_path_solve_us": mean_solve_us,
        }
