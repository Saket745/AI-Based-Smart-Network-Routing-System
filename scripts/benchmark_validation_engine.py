"""Performance Benchmark for NRoute Pre-Flight Validation Engine.

Measures:
  * Small 6-Node Topology
  * 36-Node Fat-Tree (K=4) Topology
  * 50-Node Scale-Free Topology

Records median, P95, min, max, and end-to-end turnaround latencies across 100 iterations.
"""

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from nroute.core.generators import TopologyGenerator
from nroute.core.openconfig import ConfigChange
from nroute.core.topology import Topology
from nroute.simulation.policy import PolicyGateConfig
from nroute.simulation.validator import PreFlightValidator


def benchmark_topology(topo, change, policy, n_runs=100, label=""):
    latencies = []
    # Warmup
    for _ in range(5):
        _ = PreFlightValidator.validate(topo, change=change, policy=policy)

    for _ in range(n_runs):
        t0 = time.perf_counter_ns()
        res = PreFlightValidator.validate(topo, change=change, policy=policy)
        t_us = (time.perf_counter_ns() - t0) / 1000.0
        latencies.append(t_us)

    lat_arr = np.array(latencies)
    print(f"\n[{label}] (N={topo.node_count} nodes, E={topo.edge_count} edges, {n_runs} runs)")
    print(f"  * Median Latency: {np.median(lat_arr):.2f} us ({np.median(lat_arr) / 1000.0:.3f} ms)")
    print(
        f"  * P95 Latency:    {np.percentile(lat_arr, 95):.2f} us ({np.percentile(lat_arr, 95) / 1000.0:.3f} ms)"
    )
    print(f"  * Min Latency:    {np.min(lat_arr):.2f} us ({np.min(lat_arr) / 1000.0:.3f} ms)")
    print(f"  * Max Latency:    {np.max(lat_arr):.2f} us ({np.max(lat_arr) / 1000.0:.3f} ms)")
    print(f"  * Mean Latency:   {np.mean(lat_arr):.2f} ± {np.std(lat_arr):.2f} us")
    print(f"  * Gate Verdict:   {res.verdict.value} (Summary: {res.summary})")
    return lat_arr


def _build_6node_network() -> Topology:
    import networkx as nx

    g = nx.DiGraph()
    for n in ["core0", "core1", "agg0", "agg1", "edge0", "edge1"]:
        g.add_node(n, capacity=1000.0, status="up", type="router")

    edges = [
        ("edge0", "agg0", 1000.0, 2.0),
        ("edge0", "agg1", 1000.0, 2.0),
        ("agg0", "edge0", 1000.0, 2.0),
        ("agg1", "edge0", 1000.0, 2.0),
        ("agg0", "core0", 1000.0, 5.0),
        ("agg0", "core1", 1000.0, 10.0),
        ("agg1", "core0", 1000.0, 10.0),
        ("agg1", "core1", 1000.0, 5.0),
        ("core0", "agg0", 1000.0, 5.0),
        ("core1", "agg0", 1000.0, 10.0),
        ("core0", "agg1", 1000.0, 10.0),
        ("core1", "agg1", 1000.0, 5.0),
        ("core0", "edge1", 1000.0, 5.0),
        ("edge1", "core0", 1000.0, 5.0),
        ("core1", "edge1", 1000.0, 5.0),
        ("edge1", "core1", 1000.0, 5.0),
    ]
    for u, v, bw, lat in edges:
        g.add_edge(
            u,
            v,
            bandwidth=bw,
            latency=lat,
            utilization=0.10,
            packet_loss=0.0,
            status="up",
            weight=lat,
        )
    return Topology(g)


def run_benchmarks():
    print("=" * 80)
    print("NROUTE PRE-FLIGHT VALIDATION ENGINE PERFORMANCE BENCHMARK")
    print("=" * 80)

    # 1. Small 6-Node Topology
    topo_6 = _build_6node_network()
    change_6 = ConfigChange(
        description="Cut primary link agg0->core0",
        link_changes=[{"src": "agg0", "dst": "core0", "status": "down"}],
    )
    policy_6 = PolicyGateConfig(max_latency_increase_warn_ms=3.0)
    benchmark_topology(topo_6, change_6, policy_6, n_runs=100, label="Small 6-Node Network")

    # 2. 36-Node Fat-Tree (K=4)
    topo_36 = TopologyGenerator.fat_tree(k=4)
    edges_36 = list(topo_36.edges)
    change_36 = ConfigChange(
        description="Cut core link",
        link_changes=[{"src": str(edges_36[0][0]), "dst": str(edges_36[0][1]), "status": "down"}],
    )
    policy_36 = PolicyGateConfig(max_latency_increase_warn_ms=5.0)
    benchmark_topology(topo_36, change_36, policy_36, n_runs=100, label="36-Node Fat-Tree (K=4)")

    # 3. 50-Node Scale-Free
    topo_50 = TopologyGenerator.scale_free(n_nodes=50, seed=42)
    edges_50 = list(topo_50.edges)
    change_50 = ConfigChange(
        description="Cut chord link",
        link_changes=[{"src": str(edges_50[0][0]), "dst": str(edges_50[0][1]), "status": "down"}],
    )
    policy_50 = PolicyGateConfig(max_latency_increase_warn_ms=5.0)
    benchmark_topology(
        topo_50, change_50, policy_50, n_runs=100, label="50-Node Scale-Free Network"
    )

    print("\n" + "=" * 80)


if __name__ == "__main__":
    run_benchmarks()
