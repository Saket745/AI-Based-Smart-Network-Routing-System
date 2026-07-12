"""Benchmarks for topology modification operations (add_node, add_edge, update_edge)."""

from __future__ import annotations

from typing import Any

import pytest

from nroute.core.topology import Topology


@pytest.mark.benchmark
def test_bench_add_node(benchmark: Any) -> None:
    """Benchmark adding nodes with standard and custom attributes."""
    def run_add_nodes() -> None:
        topo = Topology()
        for i in range(1000):
            topo.add_node(
                f"N{i}",
                type="router",
                capacity=1000.0 + i,
                status="up",
                location="datacenter",
                custom_attr_1="custom_value_1",
                custom_attr_2=12345,
                custom_attr_3=True,
            )

    benchmark(run_add_nodes)


@pytest.mark.benchmark
def test_bench_add_edge(benchmark: Any) -> None:
    """Benchmark adding edges with standard and custom attributes."""
    # Pre-build topology with nodes
    topo = Topology()
    for i in range(1001):
        topo.add_node(f"N{i}")

    def run_add_edges() -> None:
        # Clear existing edges from underlying graph if any (though NetworkX add_edge overrides)
        # To make it isolated, we create new edges inside the benchmark loop
        for i in range(1000):
            topo.add_edge(
                f"N{i}",
                f"N{i+1}",
                bandwidth=1000.0,
                latency=5.0,
                jitter=0.5,
                packet_loss=0.01,
                utilization=0.1,
                weight=5.0,
                status="up",
                custom_edge_attr="extra",
                custom_edge_int=999,
            )

    benchmark(run_add_edges)


@pytest.mark.benchmark
def test_bench_update_edge(benchmark: Any) -> None:
    """Benchmark updating edge attributes."""
    topo = Topology()
    for i in range(1001):
        topo.add_node(f"N{i}")
    for i in range(1000):
        topo.add_edge(f"N{i}", f"N{i+1}")

    def run_update_edges() -> None:
        for i in range(1000):
            topo.update_edge(
                f"N{i}",
                f"N{i+1}",
                bandwidth=2000.0,
                latency=10.0,
                jitter=1.0,
                packet_loss=0.02,
                utilization=0.2,
                weight=10.0,
                status="degraded",
                custom_edge_attr="updated_extra",
                another_custom=456,
            )

    benchmark(run_update_edges)
