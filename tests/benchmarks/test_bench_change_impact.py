"""Benchmarks for ChangeImpactSimulator and AnalyticalEngine."""

from __future__ import annotations

from typing import Any

import pytest

from nroute.core.generators import TopologyGenerator
from nroute.core.openconfig import ConfigChange
from nroute.simulation.change_impact import ChangeImpactSimulator


@pytest.mark.benchmark
@pytest.mark.parametrize("scale", [50, 100])
def test_bench_change_impact_simulation(scale: int, benchmark: Any) -> None:
    """Benchmark ChangeImpactSimulator before-vs-after analytical comparison."""
    topo = TopologyGenerator.random(n_nodes=scale, edge_prob=0.1, seed=42)

    # Pick a link that exists in the topology to tear down
    edges = list(topo.graph.edges)
    src, dst = edges[0] if edges else ("0", "1")

    change = ConfigChange(
        description=f"Link failure simulation {src}->{dst}",
        link_changes=[{"src": src, "dst": dst, "status": "down"}],
    )

    sim = ChangeImpactSimulator(topo)

    def run_sim() -> None:
        sim.simulate(change, weight="latency")

    benchmark(run_sim)
