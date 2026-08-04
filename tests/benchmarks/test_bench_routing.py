"""Routing benchmarks using pytest-benchmark."""

from __future__ import annotations

from typing import Any

import pytest

from nroute.core.generators import TopologyGenerator
from nroute.routing import get_router
from nroute.routing.rl_router import RLRouter


@pytest.mark.benchmark
@pytest.mark.parametrize("scale", [50, 100, 500])
@pytest.mark.parametrize("algo", ["dijkstra", "bellman-ford", "ecmp"])
def test_bench_routing_algorithms(scale: int, algo: str, benchmark: Any) -> None:
    """Benchmark traditional routing algorithms (Dijkstra, Bellman-Ford, ECMP)."""
    # Generate topology
    topo = TopologyGenerator.random(n_nodes=scale, edge_prob=0.1, seed=42)

    # Instantiate router
    router = get_router(algo, topology=topo)

    # Compute a path between first and last node
    src = "0"
    dst = str(scale - 1)

    def run_routing() -> None:
        router.compute_path(topo, src, dst)

    benchmark(run_routing)


@pytest.mark.benchmark
@pytest.mark.parametrize("scale", [50, 100, 500])
def test_bench_rl_routing(scale: int, benchmark: Any) -> None:
    """Benchmark RL Router inference (with fallback)."""
    topo = TopologyGenerator.random(n_nodes=scale, edge_prob=0.1, seed=42)

    # Instantiate RL Router
    router = RLRouter(topology=topo, algorithm="ppo")

    # In fallback state (untrained)
    src = "0"
    dst = str(scale - 1)

    def run_rl_fallback() -> None:
        router.compute_path(topo, src, dst)

    benchmark(run_rl_fallback)
