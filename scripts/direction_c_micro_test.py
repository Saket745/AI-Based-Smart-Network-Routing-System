"""Direction-C Deterministic Micro-Test Validation Script.

Validates:
1. Target Delta_U generation via exact analytical oracle
2. Manual mathematical vs. oracle implementation match
3. Zero information leakage before inference
4. Failure conditioning under alternative cuts
5. Pre/post topology state immutability & restoration
6. Rigorous proof of local feature vector identity (equality) vs. target inequality
"""

import copy

import networkx as nx
import numpy as np

from nroute.benchmark.blast_radius_oracle import (
    BlastRadiusOracle,
    FailureConditionedFeatureExtractor,
    FlowDemand,
)
from nroute.core.topology import Topology


def build_micro_scenario() -> tuple[Topology, list[FlowDemand]]:
    """
    Construct deterministic 7-node test scenario with EXACT local feature equality between
    detour edge (C -> B) and isolated edge (F -> G).

    Primary Path:   A -> B -> D (Cost 5 + 5 = 10ms)
    Detour Path:    A -> C -> B -> D (Cost 6 + 6 + 5 = 17ms)
    High-Cost Path: A -> F -> G -> D (Cost 20 + 6 + 20 = 46ms)
    """
    g = nx.DiGraph()
    for n in ["A", "B", "C", "D", "E", "F", "G"]:
        g.add_node(n, capacity=1000.0, status="up", type="router")

    edges = [
        ("A", "B", 100.0, 5.0),
        ("A", "C", 100.0, 6.0),
        ("C", "B", 100.0, 6.0),  # Edge 1 (Detour): Latency 6.0ms, Cap 100M
        ("B", "D", 100.0, 5.0),
        ("B", "E", 100.0, 5.0),
        ("C", "E", 100.0, 10.0),
        ("A", "F", 100.0, 20.0),
        ("F", "G", 100.0, 6.0),  # Edge 2 (Isolated): Latency 6.0ms, Cap 100M (IDENTICAL TO C->B!)
        ("G", "D", 100.0, 20.0),
    ]

    for u, v, bw, lat in edges:
        g.add_edge(
            u,
            v,
            bandwidth=bw,
            latency=lat,
            utilization=0.0,
            packet_loss=0.0,
            status="up",
            weight=lat,
        )

    topo = Topology(g)

    flows = [
        FlowDemand("f1_A_to_D", "A", "D", 50.0),  # Primary flow (50 Mbps)
        FlowDemand(
            "f2_C_to_B", "C", "B", 10.0
        ),  # Background probe on C->B (10 Mbps -> U_pre = 0.10)
        FlowDemand(
            "f3_F_to_G", "F", "G", 10.0
        ),  # Background probe on F->G (10 Mbps -> U_pre = 0.10)
    ]

    return topo, flows


def run_micro_test():
    print("=" * 80)
    print("DIRECTION-C DETERMINISTIC MICRO-TEST VALIDATION")
    print("=" * 80)

    topo, flows = build_micro_scenario()
    cut_edge = ("A", "B")

    # Record topology state before oracle invocation for restoration verification
    topo_nodes_before = sorted(topo.nodes)
    topo_edges_before = sorted(topo.edges)
    topo_attr_before = copy.deepcopy(dict(topo.graph.edges))

    # 1. Oracle Execution
    print(f"\n1. Executing Analytical Oracle for hypothetical cut: {cut_edge}...")
    oracle_res = BlastRadiusOracle.compute_reroute_ground_truth(topo, flows, cut_edge)

    u_pre = oracle_res["u_pre"]
    u_post = oracle_res["u_post"]
    delta_u = oracle_res["delta_u"]
    pre_paths = oracle_res["pre_paths"]
    post_paths = oracle_res["post_paths"]

    print("\n   [Pre-Failure Routing Paths & Loads]")
    for fid, p in pre_paths.items():
        print(f"     Flow {fid}: Path = {p}")
    print("   [Pre-Failure Link Utilizations U_pre]")
    for e, u in sorted(u_pre.items()):
        print(f"     Edge {e}: U_pre = {u:.2f}")

    print("\n   [Post-Failure Rerouted Paths & Loads (Cut: A -> B)]")
    for fid, p in post_paths.items():
        print(f"     Flow {fid}: Path = {p}")
    print("   [Post-Failure Link Utilizations U_post & Exact Delta_U]")
    for e, u in sorted(u_post.items()):
        print(f"     Edge {e}: U_post = {u:.2f} | Delta_U = {delta_u[e]:+.2f}")

    # 2. Manual vs. Oracle Verification
    print("\n2. Comparing Oracle Output vs. Independent Manual Mathematical Calculation:")
    assert abs(delta_u[("C", "B")] - 0.50) < 1e-6, "Manual check failed for (C, B)"
    assert abs(delta_u[("A", "C")] - 0.50) < 1e-6, "Manual check failed for (A, C)"
    assert abs(delta_u[("F", "G")] - 0.00) < 1e-6, "Manual check failed for (F, G)"
    assert abs(delta_u[("B", "D")] - 0.00) < 1e-6, "Manual check failed for (B, D)"
    print("   -> Manual Mathematical Calculation MATCHES Oracle Output (100% exact). [PASS]")

    # 3. State Restoration Verification
    print("\n3. Verifying Pre/Post Topology Immutability & Restoration:")
    assert sorted(topo.nodes) == topo_nodes_before, "Topology nodes mutated!"
    assert sorted(topo.edges) == topo_edges_before, "Topology edges mutated!"
    assert dict(topo.graph.edges) == topo_attr_before, "Topology attributes mutated!"
    print("   -> Original Topology graph state is 100% restored and unmutated. [PASS]")

    # 4. Feature Extraction & Zero Leakage Verification
    print("\n4. Feature Extraction & Zero Leakage Assertions:")
    feat_bundle = FailureConditionedFeatureExtractor.extract_failure_features(
        topo, cut_edge, u_pre=u_pre
    )

    node_feats = feat_bundle["node_features"]
    edge_feats = feat_bundle["edge_features"]
    edges_list = feat_bundle["edges"]

    assert node_feats.shape == (7, 5), f"Node features shape mismatch: {node_feats.shape}"
    assert edge_feats.shape == (9, 6), f"Edge features shape mismatch: {edge_feats.shape}"

    cut_idx = edges_list.index(cut_edge)
    assert edge_feats[cut_idx, 4] == 0.0, "Cut edge status is not 0.0"
    assert edge_feats[cut_idx, 5] == 1.0, "Cut edge is_cut flag is not 1.0"

    for idx, e in enumerate(edges_list):
        if e != cut_edge:
            assert edge_feats[idx, 2] == u_pre[e], f"Edge {e} utilization does not match U_pre"
            assert edge_feats[idx, 5] == 0.0, f"Edge {e} incorrectly flagged as cut"

    print(
        "   -> Feature conditioning verified. Input contains strictly pre-failure state and cut indicator. [PASS]"
    )

    # 5. Failure Conditioning Test (Alternative Cut)
    print("\n5. Testing Failure Conditioning under Alternative Cut (Cut: B -> D):")
    alt_cut = ("B", "D")
    oracle_alt = BlastRadiusOracle.compute_reroute_ground_truth(topo, flows, alt_cut)
    delta_u_alt = oracle_alt["delta_u"]

    print(
        f"   [Cut B -> D Output] Delta_U(F, G) = {delta_u_alt[('F', 'G')]:+.2f} | Delta_U(C, B) = {delta_u_alt[('C', 'B')]:+.2f}"
    )
    assert abs(delta_u_alt[("F", "G")] - 0.50) < 1e-6, "Alternative cut failed for (F, G)"
    assert abs(delta_u_alt[("C", "B")] - 0.00) < 1e-6, "Alternative cut failed for (C, B)"
    print("   -> Failure Conditioning VERIFIED (Target dynamically shifts based on e_cut). [PASS]")

    # 6. Rigorous Mathematical Proof of Local Feature Insufficiency
    print("\n6. Rigorous Mathematical Proof of Local Information Insufficiency:")
    cb_idx = edges_list.index(("C", "B"))
    fg_idx = edges_list.index(("F", "G"))

    feat_cb = edge_feats[cb_idx].numpy()
    feat_fg = edge_feats[fg_idx].numpy()

    print(f"   Local Feature Vector Edge 1 (C -> B): {feat_cb.tolist()}")
    print(f"   Local Feature Vector Edge 2 (F -> G): {feat_fg.tolist()}")

    # Assert exact bitwise feature equality
    assert np.array_equal(feat_cb, feat_fg), (
        f"Feature vectors not identical: {feat_cb} vs {feat_fg}"
    )
    print(
        "   -> EXACT FEATURE EQUALITY PROVED: feat(C -> B) == feat(F -> G) across all 6 dimensions."
    )

    # Assert target inequality
    target_cb = delta_u[("C", "B")]
    target_fg = delta_u[("F", "G")]
    print(f"   Oracle Delta_U Target for Edge 1 (C -> B): {target_cb:+.4f}")
    print(f"   Oracle Delta_U Target for Edge 2 (F -> G): {target_fg:+.4f}")
    assert target_cb != target_fg, "Targets are not distinct!"
    print(
        f"   -> TARGET INEQUALITY PROVED: Delta_U(C -> B) = {target_cb:+.2f} != Delta_U(F -> G) = {target_fg:+.2f}"
    )

    # Mathematical deduction
    print("\n   [Mathematical Impossibility Theorem for Edge-Only Predictors]:")
    print("   For ANY deterministic edge-only function f: R^6 -> R:")
    print("     f(feat(C -> B)) == f(feat(F -> G)) == y_hat")
    print("   Therefore, absolute error on these two edges must satisfy:")
    print(
        f"     |y_hat - ({target_cb})| + |y_hat - ({target_fg})| >= |{target_cb} - {target_fg}| = {abs(target_cb - target_fg):.2f}"
    )
    print(
        "   -> PROVED: Local edge-only features are mathematically insufficient for this constructed case;"
    )
    print("      additional graph/context information is strictly required.")

    print("\n" + "=" * 80)
    print("ALL DIRECTION-C MICRO-TEST CHECKS PASSED (6/6)!")
    print("=" * 80)


if __name__ == "__main__":
    run_micro_test()
