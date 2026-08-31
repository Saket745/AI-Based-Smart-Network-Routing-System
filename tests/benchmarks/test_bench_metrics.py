from __future__ import annotations

from typing import Any

import networkx as nx
import pytest

from nroute.core.metrics import RouteMetrics
from nroute.core.topology import Topology


@pytest.mark.benchmark
def test_bench_route_metrics_from_path(benchmark: Any) -> None:
    # Generate a topology
    topo = Topology.generate("random", n_nodes=200, edge_prob=0.3, seed=42)

    # We want a fairly long path to benchmark properly
    # Let's find a path in the topology using networkx
    try:
        path = nx.shortest_path(topo.graph, source="N0", target="N100")
    except Exception:
        # If no path, build a chain of 50 nodes manually
        path = [f"N{i}" for i in range(50)]
        for i in range(len(path) - 1):
            if path[i] not in topo.nodes:
                topo.add_node(path[i])
            if path[i + 1] not in topo.nodes:
                topo.add_node(path[i + 1])
            topo.add_edge(path[i], path[i + 1], latency=1.5, bandwidth=100.0, utilization=0.2)

    def run_metrics() -> None:
        for _ in range(1000):
            RouteMetrics.from_path(topo, path)

    benchmark(run_metrics)


@pytest.mark.benchmark
def test_bench_default_graph_feature_extractor(benchmark: Any) -> None:
    from nroute.ml.features.extractor import DefaultGraphFeatureExtractor

    topo = Topology.generate("random", n_nodes=300, edge_prob=0.05, seed=42)
    ext = DefaultGraphFeatureExtractor()

    def run_extractor() -> None:
        ext.extract_features(topo)

    benchmark(run_extractor)


@pytest.mark.benchmark
def test_bench_feature_builder(benchmark: Any) -> None:
    from nroute.ml.features.builder import FeatureBuilder

    topo = Topology.generate("random", n_nodes=200, edge_prob=0.05, seed=42)
    builder = FeatureBuilder()

    def run_builder() -> None:
        builder.build_features(topo)

    benchmark(run_builder)
