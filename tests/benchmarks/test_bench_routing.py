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


@pytest.mark.benchmark
@pytest.mark.parametrize("scale", [50])
def test_bench_ai_routing(scale: int, benchmark: Any) -> None:
    """Benchmark AIRouter path computation with trained congestion predictor."""
    import numpy as np
    import pandas as pd

    from nroute.core.generators import TopologyGenerator
    from nroute.ml.feature_eng import extract_congestion_features
    from nroute.routing.ai import AIRouter

    topo = TopologyGenerator.random(n_nodes=scale, edge_prob=0.1, seed=42)
    # Set high utilization on some edges
    edges = list(topo.graph.edges)
    for u, v in edges[:5]:
        topo.update_edge(u, v, utilization=0.95)

    router = AIRouter(topology=topo)
    df = extract_congestion_features(topo, [])
    labels = np.array([1 if idx in [f"{u}->{v}" for u, v in edges[:5]] else 0 for idx in df.index])

    # Train predictor with duplicates to satisfy splits
    train_df = pd.concat([df] * 10)
    train_labels = np.concatenate([labels] * 10)
    router.train(features_congestion=train_df, labels_congestion=train_labels)

    src = "0"
    dst = str(scale - 1)

    # We do a batch of 50 paths to simulate batch routing in a single tick
    def run_ai_routing() -> None:
        for _ in range(50):
            router.compute_path(topo, src, dst)

    benchmark(run_ai_routing)
