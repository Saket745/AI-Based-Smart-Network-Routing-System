"""Unit tests protecting Direction-C BlastRadiusOracle and FailureConditionedFeatureExtractor."""

from __future__ import annotations

import copy

import networkx as nx

from nroute.benchmark.blast_radius_oracle import (
    BlastRadiusOracle,
    FailureConditionedFeatureExtractor,
    FlowDemand,
)
from nroute.core.topology import Topology


def _build_test_scenario() -> tuple[Topology, list[FlowDemand]]:
    g = nx.DiGraph()
    for n in ["A", "B", "C", "D"]:
        g.add_node(n, capacity=1000.0, status="up", type="router")
    g.add_edge(
        "A", "B", bandwidth=100.0, latency=5.0, utilization=0.0, packet_loss=0.0, status="up"
    )
    g.add_edge(
        "B", "D", bandwidth=100.0, latency=5.0, utilization=0.0, packet_loss=0.0, status="up"
    )
    g.add_edge(
        "A", "C", bandwidth=100.0, latency=6.0, utilization=0.0, packet_loss=0.0, status="up"
    )
    g.add_edge(
        "C", "D", bandwidth=100.0, latency=6.0, utilization=0.0, packet_loss=0.0, status="up"
    )

    topo = Topology(g)
    flows = [FlowDemand("f1", "A", "D", 50.0)]
    return topo, flows


def test_blast_radius_oracle_exact_delta_u() -> None:
    """Verify BlastRadiusOracle computes exact pre/post loads and delta_u."""
    topo, flows = _build_test_scenario()
    res = BlastRadiusOracle.compute_reroute_ground_truth(topo, flows, ("A", "B"))

    u_pre = res["u_pre"]
    u_post = res["u_post"]
    delta_u = res["delta_u"]

    assert abs(u_pre[("A", "B")] - 0.50) < 1e-6
    assert abs(u_pre[("B", "D")] - 0.50) < 1e-6
    assert abs(u_pre[("A", "C")] - 0.00) < 1e-6

    assert abs(u_post[("A", "C")] - 0.50) < 1e-6
    assert abs(u_post[("C", "D")] - 0.50) < 1e-6

    assert abs(delta_u[("A", "C")] - 0.50) < 1e-6
    assert abs(delta_u[("C", "D")] - 0.50) < 1e-6
    assert abs(delta_u[("B", "D")] - (-0.50)) < 1e-6


def test_oracle_topology_immutability() -> None:
    """Verify BlastRadiusOracle restores topology state without side-effects."""
    topo, flows = _build_test_scenario()
    edges_before = sorted(topo.edges)
    attr_before = copy.deepcopy(dict(topo.graph.edges))

    _ = BlastRadiusOracle.compute_reroute_ground_truth(topo, flows, ("A", "B"))

    assert sorted(topo.edges) == edges_before
    assert dict(topo.graph.edges) == attr_before


def test_failure_conditioned_feature_extraction() -> None:
    """Verify FailureConditionedFeatureExtractor shapes and cut-edge indicators."""
    topo, flows = _build_test_scenario()
    res = BlastRadiusOracle.compute_reroute_ground_truth(topo, flows, ("A", "B"))
    bundle = FailureConditionedFeatureExtractor.extract_failure_features(
        topo, ("A", "B"), u_pre=res["u_pre"]
    )

    nf = bundle["node_features"]
    ef = bundle["edge_features"]
    edges = bundle["edges"]

    assert nf.shape == (4, 5)
    assert ef.shape == (4, 6)

    cut_idx = edges.index(("A", "B"))
    assert ef[cut_idx, 4] == 0.0  # status = 0.0
    assert ef[cut_idx, 5] == 1.0  # is_cut = 1.0

    for i, e in enumerate(edges):
        if e != ("A", "B"):
            assert ef[i, 4] == 1.0
            assert ef[i, 5] == 0.0
