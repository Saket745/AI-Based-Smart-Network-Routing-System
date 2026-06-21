"""Simulation benchmarks using pytest-benchmark."""

from __future__ import annotations

from typing import Any

import pytest
from nroute.core.generators import TopologyGenerator
from nroute.routing.dijkstra import DijkstraRouter
from nroute.simulation.engine import SimulationEngine
from nroute.simulation.traffic_gen import TrafficGenerator


@pytest.mark.benchmark
@pytest.mark.parametrize("scale", [100, 500, 1000])
def test_bench_simulation_tick_rate(scale: int, benchmark: Any) -> None:
    """Benchmark the packet-level simulation tick rate on different scale topologies."""
    # Real-world network topologies are sparse and scale-free.
    # We use Barabasi-Albert scale-free generator for realistic routing & fast updates.
    topo = TopologyGenerator.scale_free(n_nodes=scale, seed=42)

    # Setup router and traffic generator
    router = DijkstraRouter()
    # We use 1 flow per tick to benchmark standard operational ticks.
    traffic = TrafficGenerator(model="uniform", n_flows_per_tick=1, seed=42)

    # Configure engine
    engine = SimulationEngine(topo, router, traffic)

    # Run for 1 tick to benchmark the per-tick throughput
    def run_step() -> None:
        engine.run(duration_ticks=1, seed=42, show_progress=False)

    benchmark(run_step)
