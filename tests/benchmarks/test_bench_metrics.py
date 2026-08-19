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
def test_bench_metrics_to_dataframe(benchmark: Any) -> None:
    from nroute.core.metrics import MetricsCollectionResult, SimulationMetrics

    results = [
        SimulationMetrics(
            tick=i,
            timestamp=float(i),
            throughput=100.0,
            avg_latency=5.0,
            packet_loss_rate=0.01,
            avg_utilization=0.5,
            reroute_count=0,
            active_flows=10,
        )
        for i in range(10000)
    ]
    mc = MetricsCollectionResult(results=results)

    def run_to_dataframe() -> None:
        mc.to_dataframe()

    benchmark(run_to_dataframe)
