"""Analytical Ground-Truth Oracle and Failure-Conditioned Feature Extraction for Direction-C."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx
import torch

if TYPE_CHECKING:
    from nroute.core.topology import Topology


class FlowDemand:
    """Represents an active source-destination traffic flow with a specified bandwidth demand."""

    def __init__(self, flow_id: str, source: str, destination: str, demand_mbps: float) -> None:
        self.flow_id = flow_id
        self.source = source
        self.destination = destination
        self.demand_mbps = demand_mbps


class BlastRadiusOracle:
    """
    Analytical ground-truth oracle for post-failure traffic redistribution under Link-State IGP rerouting.
    Computes exact U_pre, U_post, and Delta_U without mutating the input topology.
    """

    @staticmethod
    def compute_reroute_ground_truth(
        topology: Topology,
        flows: list[FlowDemand],
        cut_edge: tuple[str, str],
    ) -> dict[str, Any]:
        """
        Compute exact post-failure flow redistribution for severed flows.

        Args:
            topology: The pre-failure network topology.
            flows: List of active flow demands.
            cut_edge: The hypothetical failed edge (u, v).

        Returns:
            Dictionary containing u_pre, u_post, delta_u, disconnected_flows, and routing paths.
        """
        graph = topology.graph
        u_cut, v_cut = cut_edge

        # 1. Pre-Failure Shortest Path Routing
        pre_paths: dict[str, list[str]] = {}
        edge_loads_pre: dict[tuple[str, str], float] = {e: 0.0 for e in graph.edges}

        for f in flows:
            try:
                p = nx.shortest_path(graph, source=f.source, target=f.destination, weight="latency")
                pre_paths[f.flow_id] = p
                for i in range(len(p) - 1):
                    e = (p[i], p[i + 1])
                    edge_loads_pre[e] += f.demand_mbps
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                pre_paths[f.flow_id] = []

        u_pre: dict[tuple[str, str], float] = {}
        for e, load in edge_loads_pre.items():
            cap = float(graph.edges[e].get("bandwidth", 1000.0))
            u_pre[e] = load / cap if cap > 0 else 0.0

        # 2. Construct Perturbed Graph Copy G' = G \ {cut_edge}
        perturbed_graph = graph.copy()
        if perturbed_graph.has_edge(u_cut, v_cut):
            perturbed_graph.remove_edge(u_cut, v_cut)

        # 3. Post-Failure Selective Flow Rerouting
        post_paths: dict[str, list[str]] = {}
        edge_loads_post: dict[tuple[str, str], float] = {e: 0.0 for e in perturbed_graph.edges}
        disconnected_count = 0

        for f in flows:
            old_p = pre_paths.get(f.flow_id, [])
            uses_cut_edge = any(
                (old_p[i] == u_cut and old_p[i + 1] == v_cut) for i in range(len(old_p) - 1)
            )

            if not uses_cut_edge:
                # Flow is unaffected: remains on original path
                post_paths[f.flow_id] = old_p
                for i in range(len(old_p) - 1):
                    e = (old_p[i], old_p[i + 1])
                    if e in edge_loads_post:
                        edge_loads_post[e] += f.demand_mbps
            else:
                # Flow severed: re-route on G'
                try:
                    new_p = nx.shortest_path(
                        perturbed_graph, source=f.source, target=f.destination, weight="latency"
                    )
                    post_paths[f.flow_id] = new_p
                    for i in range(len(new_p) - 1):
                        e = (new_p[i], new_p[i + 1])
                        edge_loads_post[e] += f.demand_mbps
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    post_paths[f.flow_id] = []
                    disconnected_count += 1

        u_post: dict[tuple[str, str], float] = {}
        for e, load in edge_loads_post.items():
            cap = float(perturbed_graph.edges[e].get("bandwidth", 1000.0))
            u_post[e] = load / cap if cap > 0 else 0.0

        # 4. Compute Delta_U for surviving edges
        delta_u: dict[tuple[str, str], float] = {}
        for e in perturbed_graph.edges:
            delta_u[e] = u_post[e] - u_pre.get(e, 0.0)

        return {
            "cut_edge": cut_edge,
            "u_pre": u_pre,
            "u_post": u_post,
            "delta_u": delta_u,
            "pre_paths": pre_paths,
            "post_paths": post_paths,
            "disconnected_flows": disconnected_count,
        }


class FailureConditionedFeatureExtractor:
    """
    Extracts failure-conditioned PyTorch graph feature bundles for Direction-C GNN surrogates.
    Encodes cut_edge explicitly without mutating the underlying graph or leaking post-failure telemetry.
    """

    @staticmethod
    def extract_failure_features(
        topology: Topology,
        cut_edge: tuple[str, str],
        u_pre: dict[tuple[str, str], float] | None = None,
    ) -> dict[str, Any]:
        nodes = sorted(topology.nodes)
        edges = sorted(topology.edges)
        node_to_idx = {n: i for i, n in enumerate(nodes)}
        u_cut, v_cut = cut_edge
        graph = topology.graph

        # Node Features: [capacity/1000, status, out_degree, is_cut_source, is_cut_target] (dim = 5)
        node_features = []
        for n in nodes:
            attrs = graph.nodes[n]
            cap = float(attrs.get("capacity", 1000.0)) / 1000.0
            status = 1.0 if attrs.get("status", "up").lower() == "up" else 0.0
            degree = float(len(list(graph.successors(n))))
            is_cut_src = 1.0 if n == u_cut else 0.0
            is_cut_dst = 1.0 if n == v_cut else 0.0
            node_features.append([cap, status, degree, is_cut_src, is_cut_dst])

        # Edge Index and Edge Features: [bw/1000, lat/100, u_pre, loss_pre, status, is_cut_edge] (dim = 6)
        edge_index = []
        edge_features = []
        surviving_edge_indices = []

        for idx, (src, dst) in enumerate(edges):
            edge_index.append([node_to_idx[src], node_to_idx[dst]])
            attrs = graph.edges[src, dst]
            bw = float(attrs.get("bandwidth", 1000.0)) / 1000.0
            lat = float(attrs.get("latency", 5.0)) / 100.0
            util = (
                float(u_pre.get((src, dst), attrs.get("utilization", 0.0)))
                if u_pre
                else float(attrs.get("utilization", 0.0))
            )
            loss = float(attrs.get("packet_loss", 0.0))

            is_cut = 1.0 if (src == u_cut and dst == v_cut) else 0.0
            edge_status = (
                0.0 if is_cut else (1.0 if attrs.get("status", "up").lower() == "up" else 0.0)
            )

            edge_features.append([bw, lat, util, loss, edge_status, is_cut])
            if not is_cut:
                surviving_edge_indices.append(idx)

        return {
            "node_features": torch.tensor(node_features, dtype=torch.float32),
            "edge_index": torch.tensor(edge_index, dtype=torch.int64).T,
            "edge_features": torch.tensor(edge_features, dtype=torch.float32),
            "node_to_idx": node_to_idx,
            "idx_to_node": nodes,
            "edges": edges,
            "surviving_edge_indices": surviving_edge_indices,
            "cut_edge": cut_edge,
        }
